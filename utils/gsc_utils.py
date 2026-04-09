"""
GSC Utils - PcComponentes Content Generator
Versión 1.2.0 - 2026-02-11

Utilidades para Google Search Console (GSC).
Incluye sistema de caché robusto con TTL, invalidación automática y manual,
límite de tamaño, y manejo de datos de GSC.

Este módulo proporciona:
- Sistema de caché con TTL configurable
- Funciones para cargar y procesar datos de GSC
- Análisis de keywords y métricas
- Análisis de canibalización de contenido
- Gestión de fecha de datos GSC
- Integración con el flujo de generación de contenido
- Integración con API de GSC via Service Account (fuente principal)
- Fallback automático a CSV local si la API no está configurada

Autor: PcComponentes - Product Discovery & Content
"""

import os
import csv
import json
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple, Callable, TypeVar, Union
from dataclasses import dataclass, field
from functools import wraps
from collections import OrderedDict

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# IMPORTS CON MANEJO DE ERRORES
# ============================================================================

try:
    import pandas as pd
    _pandas_available = True
except ImportError:
    logger.warning("pandas no disponible - funcionalidad limitada")
    _pandas_available = False

# API de GSC (fuente principal, fallback a CSV si no está configurada)
_gsc_api_available = False
try:
    from utils.gsc_api import (
        is_gsc_api_configured,
        api_check_cannibalization,
        api_search_existing_content,
        api_get_content_coverage_summary,
    )
    _gsc_api_available = True
except ImportError:
    try:
        # Import relativo (cuando se ejecuta como parte del paquete utils)
        from .gsc_api import (
            is_gsc_api_configured,
            api_check_cannibalization,
            api_search_existing_content,
            api_get_content_coverage_summary,
        )
        _gsc_api_available = True
    except ImportError:
        logger.info("gsc_api no disponible - se usará CSV como fuente de datos")
        
        def is_gsc_api_configured():
            return False

try:
    from config.settings import DATA_DIR, GSC_DATA_FILE
except ImportError:
    DATA_DIR = Path("./data")
    GSC_DATA_FILE = DATA_DIR / "gsc_data.csv"


# ============================================================================
# VERSIÓN Y CONSTANTES
# ============================================================================

__version__ = "1.2.0"

# Configuración de caché por defecto
DEFAULT_CACHE_TTL = 3600  # 1 hora en segundos
DEFAULT_CACHE_MAX_SIZE = 100  # Máximo de entradas en caché
MIN_CACHE_TTL = 60  # Mínimo 1 minuto
MAX_CACHE_TTL = 86400  # Máximo 24 horas

# Configuración de GSC
GSC_DEFAULT_COLUMNS = [
    'query', 'page', 'clicks', 'impressions', 'ctr', 'position'
]
GSC_METRICS = ['clicks', 'impressions', 'ctr', 'position']

# Configuración de fecha de datos
GSC_DATA_STALE_DAYS = 7  # Días para considerar datos desactualizados

# Fechas del dataset (actualizar al cargar nuevos datos)
DATASET_START_DATE = datetime(2025, 1, 1)  # Actualizar con cada nuevo dataset
DATASET_END_DATE = datetime(2025, 1, 31)   # Actualizar con cada nuevo dataset

# ============================================================================
# CONSTANTES PARA UI/GSC_SECTION
# ============================================================================

# Mensajes de recomendación según análisis
RECOMMENDATION_MESSAGES = {
    'create_new': "✅ Puedes crear contenido nuevo para esta keyword sin riesgo de canibalización.",
    'already_ranking_well': "⚠️ Ya tienes contenido bien posicionado para esta keyword. Considera mejorar el existente.",
    'already_ranking': "⚠️ Ya tienes contenido rankeando. Evalúa si crear nuevo contenido o mejorar el existente.",
    'consolidate': "🔴 Tienes múltiples URLs compitiendo. Considera consolidar el contenido.",
    'low_performance': "🟡 El contenido existente tiene bajo rendimiento. Podrías crear algo mejor.",
}

# Colores para niveles de riesgo de canibalización
RISK_LEVEL_COLORS = {
    'none': '#28a745',    # Verde
    'low': '#6c757d',     # Gris
    'medium': '#ffc107',  # Amarillo
    'high': '#dc3545',    # Rojo
}

# Descripciones de tipos de match
MATCH_TYPE_DESCRIPTIONS = {
    'exact': 'Coincidencia exacta',
    'contains': 'Keyword contenida',
    'partial': 'Coincidencia parcial',
    'related': 'Relacionada',
}


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class GSCError(Exception):
    """Excepción base para errores de GSC."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class GSCFileError(GSCError):
    """Error al leer archivo de GSC."""
    pass


class GSCParseError(GSCError):
    """Error al parsear datos de GSC."""
    pass


class CacheError(GSCError):
    """Error relacionado con el caché."""
    pass


# ============================================================================
# SISTEMA DE CACHÉ CON TTL
# ============================================================================

@dataclass
class CacheEntry:
    """Entrada individual en el caché."""
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    hits: int = 0
    last_accessed: datetime = field(default_factory=datetime.now)
    
    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        return datetime.now() > self.expires_at
    
    def time_to_live(self) -> float:
        """Retorna segundos restantes de vida."""
        remaining = (self.expires_at - datetime.now()).total_seconds()
        return max(0, remaining)
    
    def touch(self) -> None:
        """Actualiza tiempo de acceso y contador de hits."""
        self.last_accessed = datetime.now()
        self.hits += 1


class TTLCache:
    """
    Caché con Time-To-Live (TTL) y límite de tamaño.
    
    Características:
    - TTL configurable por entrada o global
    - Límite máximo de entradas (LRU eviction)
    - Invalidación automática de entradas expiradas
    - Invalidación manual por clave o patrón
    - Thread-safe con locks
    - Estadísticas de uso
    
    Example:
        >>> cache = TTLCache(ttl=3600, max_size=100)
        >>> cache.set('key1', 'value1')
        >>> value = cache.get('key1')
        >>> cache.invalidate('key1')
    """
    
    def __init__(
        self,
        ttl: int = DEFAULT_CACHE_TTL,
        max_size: int = DEFAULT_CACHE_MAX_SIZE,
        name: str = "default"
    ):
        """
        Inicializa el caché.
        
        Args:
            ttl: Time-to-live en segundos (default: 3600)
            max_size: Número máximo de entradas (default: 100)
            name: Nombre del caché para logging
        """
        self._ttl = max(MIN_CACHE_TTL, min(ttl, MAX_CACHE_TTL))
        self._max_size = max(1, max_size)
        self._name = name
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        
        # Estadísticas
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'expirations': 0,
            'invalidations': 0,
        }
        
        logger.info(f"Caché '{name}' inicializado: TTL={self._ttl}s, max_size={self._max_size}")
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene un valor del caché.
        
        Args:
            key: Clave a buscar
            default: Valor por defecto si no existe o expiró
            
        Returns:
            Valor almacenado o default
        """
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats['misses'] += 1
                return default
            
            if entry.is_expired():
                self._remove_entry(key)
                self._stats['expirations'] += 1
                self._stats['misses'] += 1
                return default
            
            # Mover al final (más reciente) y actualizar stats
            self._cache.move_to_end(key)
            entry.touch()
            self._stats['hits'] += 1
            
            return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None
    ) -> None:
        """
        Almacena un valor en el caché.
        
        Args:
            key: Clave para almacenar
            value: Valor a almacenar
            ttl: TTL específico para esta entrada (opcional)
        """
        with self._lock:
            # Limpiar entradas expiradas periódicamente
            self._cleanup_expired()
            
            # Verificar límite de tamaño
            while len(self._cache) >= self._max_size:
                self._evict_oldest()
            
            # Calcular expiración
            entry_ttl = ttl if ttl is not None else self._ttl
            entry_ttl = max(MIN_CACHE_TTL, min(entry_ttl, MAX_CACHE_TTL))
            
            now = datetime.now()
            expires_at = now + timedelta(seconds=entry_ttl)
            
            # Crear entrada
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=expires_at,
                last_accessed=now
            )
            
            # Almacenar
            self._cache[key] = entry
            self._cache.move_to_end(key)
            
            logger.debug(f"Caché '{self._name}': SET {key} (TTL={entry_ttl}s)")
    
    def invalidate(self, key: str) -> bool:
        """
        Invalida (elimina) una entrada específica.
        
        Args:
            key: Clave a invalidar
            
        Returns:
            True si se eliminó, False si no existía
        """
        with self._lock:
            if key in self._cache:
                self._remove_entry(key)
                self._stats['invalidations'] += 1
                logger.debug(f"Caché '{self._name}': INVALIDATE {key}")
                return True
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalida todas las entradas que coincidan con un patrón.
        
        Args:
            pattern: Patrón a buscar (substring)
            
        Returns:
            Número de entradas invalidadas
        """
        with self._lock:
            keys_to_remove = [
                key for key in self._cache.keys()
                if pattern in key
            ]
            
            for key in keys_to_remove:
                self._remove_entry(key)
                self._stats['invalidations'] += 1
            
            if keys_to_remove:
                logger.info(
                    f"Caché '{self._name}': INVALIDATE_PATTERN '{pattern}' "
                    f"({len(keys_to_remove)} entradas)"
                )
            
            return len(keys_to_remove)
    
    def invalidate_all(self) -> int:
        """
        Invalida todas las entradas del caché.
        
        Returns:
            Número de entradas invalidadas
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats['invalidations'] += count
            logger.info(f"Caché '{self._name}': INVALIDATE_ALL ({count} entradas)")
            return count
    
    def invalidate_expired(self) -> int:
        """
        Invalida solo las entradas expiradas.
        
        Returns:
            Número de entradas invalidadas
        """
        with self._lock:
            return self._cleanup_expired()
    
    def contains(self, key: str) -> bool:
        """
        Verifica si una clave existe y no ha expirado.
        
        Args:
            key: Clave a verificar
            
        Returns:
            True si existe y es válida
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired():
                self._remove_entry(key)
                return False
            return True
    
    def get_ttl(self, key: str) -> Optional[float]:
        """
        Obtiene el TTL restante de una entrada.
        
        Args:
            key: Clave a consultar
            
        Returns:
            Segundos restantes o None si no existe
        """
        with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired():
                return None
            return entry.time_to_live()
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del caché.
        
        Returns:
            Dict con estadísticas de uso
        """
        with self._lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (
                self._stats['hits'] / total_requests * 100
                if total_requests > 0 else 0
            )
            
            return {
                'name': self._name,
                'size': len(self._cache),
                'max_size': self._max_size,
                'ttl': self._ttl,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': f"{hit_rate:.1f}%",
                'evictions': self._stats['evictions'],
                'expirations': self._stats['expirations'],
                'invalidations': self._stats['invalidations'],
            }
    
    def _remove_entry(self, key: str) -> None:
        """Elimina una entrada del caché (interno)."""
        if key in self._cache:
            del self._cache[key]
    
    def _evict_oldest(self) -> None:
        """Elimina la entrada más antigua (LRU)."""
        if self._cache:
            oldest_key = next(iter(self._cache))
            self._remove_entry(oldest_key)
            self._stats['evictions'] += 1
            logger.debug(f"Caché '{self._name}': EVICT {oldest_key}")
    
    def _cleanup_expired(self) -> int:
        """Limpia entradas expiradas (interno)."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        
        for key in expired_keys:
            self._remove_entry(key)
            self._stats['expirations'] += 1
        
        return len(expired_keys)
    
    def __len__(self) -> int:
        """Retorna número de entradas en caché."""
        return len(self._cache)
    
    def __contains__(self, key: str) -> bool:
        """Permite usar 'in' operator."""
        return self.contains(key)


# ============================================================================
# CACHÉ GLOBAL PARA GSC
# ============================================================================

# Instancia global del caché para datos GSC — almacenada en st.session_state
# para que persista entre reruns de Streamlit.
_GSC_CACHE_SESSION_KEY = '_gsc_cache_instance'

# Fallback module-level instance (used when Streamlit is not running, e.g. tests)
_gsc_cache_fallback = TTLCache(
    ttl=DEFAULT_CACHE_TTL,
    max_size=DEFAULT_CACHE_MAX_SIZE,
    name="gsc"
)


def _get_gsc_cache_instance() -> TTLCache:
    """Obtiene la instancia del caché GSC desde session_state (o fallback)."""
    try:
        import streamlit as st
        if _GSC_CACHE_SESSION_KEY not in st.session_state:
            st.session_state[_GSC_CACHE_SESSION_KEY] = TTLCache(
                ttl=DEFAULT_CACHE_TTL,
                max_size=DEFAULT_CACHE_MAX_SIZE,
                name="gsc"
            )
        return st.session_state[_GSC_CACHE_SESSION_KEY]
    except Exception:
        return _gsc_cache_fallback


# Module-level reference for backward compatibility (used by @cached decorator)
_gsc_cache = _get_gsc_cache_instance()


def get_gsc_cache() -> TTLCache:
    """Obtiene la instancia global del caché GSC."""
    return _get_gsc_cache_instance()


def reset_gsc_cache(
    ttl: Optional[int] = None,
    max_size: Optional[int] = None
) -> TTLCache:
    """
    Resetea el caché GSC con nueva configuración.

    Args:
        ttl: Nuevo TTL (opcional)
        max_size: Nuevo tamaño máximo (opcional)

    Returns:
        Nueva instancia del caché
    """
    global _gsc_cache

    new_cache = TTLCache(
        ttl=ttl or DEFAULT_CACHE_TTL,
        max_size=max_size or DEFAULT_CACHE_MAX_SIZE,
        name="gsc"
    )

    try:
        import streamlit as st
        st.session_state[_GSC_CACHE_SESSION_KEY] = new_cache
    except Exception:
        pass

    _gsc_cache = new_cache
    return new_cache


# ============================================================================
# DECORADOR DE CACHÉ
# ============================================================================

T = TypeVar('T')


def cached(
    ttl: Optional[int] = None,
    key_prefix: str = "",
    cache_instance: Optional[TTLCache] = None
) -> Callable:
    """
    Decorador para cachear resultados de funciones.
    
    Args:
        ttl: TTL específico (usa el del caché si no se especifica)
        key_prefix: Prefijo para las claves de caché
        cache_instance: Instancia de caché a usar (usa global si no se especifica)
        
    Returns:
        Decorador configurado
        
    Example:
        >>> @cached(ttl=1800, key_prefix="gsc_query")
        ... def get_keywords(url: str) -> List[str]:
        ...     # Lógica costosa
        ...     return keywords
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            cache = cache_instance or _gsc_cache
            
            # Generar clave única basada en argumentos
            key_parts = [key_prefix or func.__name__]
            
            for arg in args:
                key_parts.append(str(arg))
            
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")
            
            cache_key = hashlib.md5(
                ":".join(key_parts).encode()
            ).hexdigest()
            
            # Intentar obtener del caché
            cached_value = cache.get(cache_key)
            
            if cached_value is not None:
                logger.debug(f"Cache HIT: {func.__name__}")
                return cached_value
            
            # Ejecutar función y cachear resultado
            logger.debug(f"Cache MISS: {func.__name__}")
            result = func(*args, **kwargs)
            
            if result is not None:
                cache.set(cache_key, result, ttl=ttl)
            
            return result
        
        # Añadir método para invalidar caché de esta función
        def invalidate_cache(*args, **kwargs) -> bool:
            cache = cache_instance or _gsc_cache
            
            key_parts = [key_prefix or func.__name__]
            for arg in args:
                key_parts.append(str(arg))
            for k, v in sorted(kwargs.items()):
                key_parts.append(f"{k}={v}")
            
            cache_key = hashlib.md5(
                ":".join(key_parts).encode()
            ).hexdigest()
            
            return cache.invalidate(cache_key)
        
        wrapper.invalidate = invalidate_cache
        wrapper.invalidate_all = lambda: (cache_instance or _gsc_cache).invalidate_pattern(
            key_prefix or func.__name__
        )
        
        return wrapper
    
    return decorator


# ============================================================================
# FUNCIONES DE CARGA DE DATOS GSC
# ============================================================================

@cached(ttl=3600, key_prefix="gsc_file")
def load_gsc_data(
    file_path: Optional[Union[str, Path]] = None,
    encoding: str = 'utf-8'
) -> Optional[Dict[str, Any]]:
    """
    Carga datos de GSC desde un archivo CSV.
    
    Args:
        file_path: Ruta al archivo CSV (usa default si no se especifica)
        encoding: Codificación del archivo
        
    Returns:
        Dict con datos procesados o None si hay error
        
    Raises:
        GSCFileError: Si no se puede leer el archivo
        GSCParseError: Si no se puede parsear el contenido
    """
    file_path = Path(file_path) if file_path else GSC_DATA_FILE
    
    if not file_path.exists():
        logger.warning(f"Archivo GSC no encontrado: {file_path}")
        return None
    
    try:
        # Actualizar fecha de carga
        set_gsc_data_date(datetime.now())
        
        if _pandas_available:
            return _load_gsc_with_pandas(file_path, encoding)
        else:
            return _load_gsc_with_csv(file_path, encoding)
            
    except UnicodeDecodeError as e:
        logger.error(f"Error de codificación al leer {file_path}: {e}")
        raise GSCFileError(
            f"Error de codificación en archivo GSC",
            {"file": str(file_path), "encoding": encoding, "error": str(e)}
        )
    
    except PermissionError as e:
        logger.error(f"Sin permisos para leer {file_path}: {e}")
        raise GSCFileError(
            f"Sin permisos para leer archivo GSC",
            {"file": str(file_path), "error": str(e)}
        )
    
    except Exception as e:
        logger.error(f"Error inesperado al cargar GSC: {e}")
        return None


def _detect_csv_separator(file_path: Path, encoding: str = 'utf-8') -> str:
    """Detecta el separador del CSV (coma o punto y coma)."""
    try:
        with open(file_path, 'r', encoding=encoding) as f:
            first_line = f.readline()
            # Contar ocurrencias de cada separador
            semicolons = first_line.count(';')
            commas = first_line.count(',')
            return ';' if semicolons > commas else ','
    except Exception:
        return ','  # Default a coma


def _load_gsc_with_pandas(
    file_path: Path,
    encoding: str
) -> Dict[str, Any]:
    """Carga GSC usando pandas (más eficiente)."""
    # Detectar separador automáticamente
    separator = _detect_csv_separator(file_path, encoding)
    
    df = pd.read_csv(file_path, encoding=encoding, sep=separator)
    
    # Normalizar nombres de columnas
    df.columns = df.columns.str.lower().str.strip()
    
    # Limpiar BOM si existe
    if df.columns[0].startswith('\ufeff'):
        df.columns = [col.replace('\ufeff', '') for col in df.columns]
    
    # Mapear alias de columnas comunes (keyword → query, page → url)
    _COL_ALIASES = {'keyword': 'query', 'page': 'url', 'keys': 'query'}
    new_cols = []
    for col in df.columns:
        if col in _COL_ALIASES and _COL_ALIASES[col] not in df.columns:
            new_cols.append(_COL_ALIASES[col])
        else:
            new_cols.append(col)
    df.columns = new_cols
    
    # Verificar columnas requeridas
    # Fallback extra: si aún no hay 'query' pero sí 'keyword', renombrar directamente
    if 'query' not in df.columns and 'keyword' in df.columns:
        df = df.rename(columns={'keyword': 'query'})
    
    required = ['query']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise GSCParseError(
            f"Columnas requeridas no encontradas: {missing}",
            {"columns_found": list(df.columns)}
        )
    
    # Procesar métricas numéricas
    for metric in ['clicks', 'impressions', 'position']:
        if metric in df.columns:
            df[metric] = pd.to_numeric(df[metric], errors='coerce').fillna(0)
    
    # CTR especial (puede venir como porcentaje)
    if 'ctr' in df.columns:
        df['ctr'] = df['ctr'].apply(_parse_ctr)
    
    return {
        'data': df.to_dict('records'),
        'columns': list(df.columns),
        'row_count': len(df),
        'file_path': str(file_path),
        'loaded_at': datetime.now().isoformat(),
        'source': 'pandas'
    }


def _load_gsc_with_csv(
    file_path: Path,
    encoding: str
) -> Dict[str, Any]:
    """Carga GSC usando módulo csv estándar."""
    rows = []
    
    # Detectar separador
    separator = _detect_csv_separator(file_path, encoding)
    
    with open(file_path, 'r', encoding=encoding) as f:
        # Usar el separador detectado
        reader = csv.DictReader(f, delimiter=separator)
        
        # Normalizar nombres de columnas
        if reader.fieldnames:
            # Limpiar BOM y espacios
            fieldnames = [col.lower().strip().replace('\ufeff', '') for col in reader.fieldnames]
            # Mapear alias (keyword → query, page → url)
            _COL_ALIASES = {'keyword': 'query', 'page': 'url', 'keys': 'query'}
            mapped = []
            for f in fieldnames:
                alias = _COL_ALIASES.get(f)
                if alias and alias not in fieldnames:
                    mapped.append(alias)
                else:
                    mapped.append(f)
            reader.fieldnames = mapped
        else:
            raise GSCParseError("Archivo CSV sin cabeceras")
        
        for row in reader:
            # Normalizar claves
            normalized_row = {}
            for key, value in row.items():
                norm_key = key.lower().strip()
                
                # Convertir valores numéricos
                if norm_key in ['clicks', 'impressions']:
                    try:
                        normalized_row[norm_key] = int(value) if value else 0
                    except ValueError:
                        normalized_row[norm_key] = 0
                elif norm_key == 'position':
                    try:
                        normalized_row[norm_key] = float(value) if value else 0.0
                    except ValueError:
                        normalized_row[norm_key] = 0.0
                elif norm_key == 'ctr':
                    normalized_row[norm_key] = _parse_ctr(value)
                else:
                    normalized_row[norm_key] = value
                    
            rows.append(normalized_row)
    
    return {
        'data': rows,
        'columns': fieldnames,
        'row_count': len(rows),
        'file_path': str(file_path),
        'loaded_at': datetime.now().isoformat(),
        'source': 'csv'
    }


def _parse_ctr(value: Any) -> float:
    """Parsea valor de CTR (puede venir como %, decimal, etc.)."""
    if value is None or value == '':
        return 0.0
    
    try:
        if isinstance(value, (int, float)):
            # Si es mayor que 1, probablemente es porcentaje
            return value / 100 if value > 1 else value
        
        value_str = str(value).strip()
        
        # Remover símbolo de porcentaje
        if '%' in value_str:
            value_str = value_str.replace('%', '').strip()
            return float(value_str) / 100
        
        value_float = float(value_str)
        return value_float / 100 if value_float > 1 else value_float
        
    except (ValueError, TypeError):
        return 0.0


# ============================================================================
# FUNCIONES DE ANÁLISIS DE DATOS GSC
# ============================================================================

@cached(ttl=1800, key_prefix="gsc_keywords")
def get_keywords_for_url(
    url: str,
    min_clicks: int = 0,
    min_impressions: int = 0,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Obtiene keywords que llevan tráfico a una URL específica.
    
    Args:
        url: URL a analizar
        min_clicks: Mínimo de clicks requerido
        min_impressions: Mínimo de impresiones requerido
        limit: Número máximo de resultados
        
    Returns:
        Lista de keywords con métricas, ordenadas por clicks
    """
    gsc_data = load_gsc_data()
    
    if not gsc_data or not gsc_data.get('data'):
        return []
    
    # Filtrar por URL
    results = []
    
    for row in gsc_data['data']:
        page = row.get('page', '')
        
        # Verificar si la URL coincide
        if url.lower() not in page.lower():
            continue
        
        clicks = row.get('clicks', 0)
        impressions = row.get('impressions', 0)
        
        # Aplicar filtros
        if clicks < min_clicks:
            continue
        if impressions < min_impressions:
            continue
        
        results.append({
            'query': row.get('query', ''),
            'clicks': clicks,
            'impressions': impressions,
            'ctr': row.get('ctr', 0),
            'position': row.get('position', 0),
        })
    
    # Ordenar por clicks descendente
    results.sort(key=lambda x: x['clicks'], reverse=True)
    
    return results[:limit]


@cached(ttl=1800, key_prefix="gsc_top")
def get_top_keywords(
    limit: int = 100,
    min_clicks: int = 1
) -> List[Dict[str, Any]]:
    """
    Obtiene las keywords con más clicks.
    
    Args:
        limit: Número máximo de resultados
        min_clicks: Mínimo de clicks requerido
        
    Returns:
        Lista de keywords ordenadas por clicks
    """
    gsc_data = load_gsc_data()
    
    if not gsc_data or not gsc_data.get('data'):
        return []
    
    # Filtrar y agregar por query
    query_stats: Dict[str, Dict] = {}
    
    for row in gsc_data['data']:
        query = row.get('query', '').strip().lower()
        
        if not query:
            continue
        
        if query not in query_stats:
            query_stats[query] = {
                'query': row.get('query', ''),
                'clicks': 0,
                'impressions': 0,
                'ctr_sum': 0,
                'position_sum': 0,
                'count': 0
            }
        
        stats = query_stats[query]
        stats['clicks'] += row.get('clicks', 0)
        stats['impressions'] += row.get('impressions', 0)
        stats['ctr_sum'] += row.get('ctr', 0)
        stats['position_sum'] += row.get('position', 0)
        stats['count'] += 1
    
    # Calcular promedios y filtrar
    results = []
    
    for query, stats in query_stats.items():
        if stats['clicks'] < min_clicks:
            continue
        
        results.append({
            'query': stats['query'],
            'clicks': stats['clicks'],
            'impressions': stats['impressions'],
            'ctr': stats['ctr_sum'] / stats['count'] if stats['count'] > 0 else 0,
            'position': stats['position_sum'] / stats['count'] if stats['count'] > 0 else 0,
        })
    
    # Ordenar por clicks
    results.sort(key=lambda x: x['clicks'], reverse=True)
    
    return results[:limit]


@cached(ttl=1800, key_prefix="gsc_related")
def get_related_keywords(
    keyword: str,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """
    Encuentra keywords relacionadas con una keyword dada.
    
    Args:
        keyword: Keyword base para buscar relacionadas
        limit: Número máximo de resultados
        
    Returns:
        Lista de keywords relacionadas
    """
    gsc_data = load_gsc_data()
    
    if not gsc_data or not gsc_data.get('data'):
        return []
    
    keyword_lower = keyword.lower().strip()
    keyword_words = set(keyword_lower.split())
    
    results = []
    seen_queries = set()
    
    for row in gsc_data['data']:
        query = row.get('query', '').strip()
        query_lower = query.lower()
        
        # Evitar duplicados
        if query_lower in seen_queries:
            continue
        
        # Evitar la misma keyword
        if query_lower == keyword_lower:
            continue
        
        # Verificar relación (contiene la keyword o palabras comunes)
        query_words = set(query_lower.split())
        common_words = keyword_words.intersection(query_words)
        
        if keyword_lower in query_lower or len(common_words) >= 1:
            results.append({
                'query': query,
                'clicks': row.get('clicks', 0),
                'impressions': row.get('impressions', 0),
                'ctr': row.get('ctr', 0),
                'position': row.get('position', 0),
                'relevance': len(common_words) / len(keyword_words) if keyword_words else 0
            })
            seen_queries.add(query_lower)
    
    # Ordenar por relevancia y clicks
    results.sort(key=lambda x: (x['relevance'], x['clicks']), reverse=True)
    
    return results[:limit]


@cached(ttl=3600, key_prefix="gsc_summary")
def get_gsc_summary() -> Dict[str, Any]:
    """
    Obtiene un resumen de los datos de GSC.
    
    Returns:
        Dict con estadísticas resumidas
    """
    gsc_data = load_gsc_data()
    
    if not gsc_data or not gsc_data.get('data'):
        return {
            'available': False,
            'error': 'No hay datos de GSC disponibles'
        }
    
    data = gsc_data['data']
    
    total_clicks = sum(row.get('clicks', 0) for row in data)
    total_impressions = sum(row.get('impressions', 0) for row in data)
    unique_queries = len(set(row.get('query', '').lower() for row in data if row.get('query')))
    unique_pages = len(set(row.get('page', '').lower() for row in data if row.get('page')))
    
    avg_position = (
        sum(row.get('position', 0) for row in data) / len(data)
        if data else 0
    )
    
    avg_ctr = total_clicks / total_impressions if total_impressions > 0 else 0
    
    return {
        'available': True,
        'total_rows': len(data),
        'unique_queries': unique_queries,
        'unique_pages': unique_pages,
        'total_clicks': total_clicks,
        'total_impressions': total_impressions,
        'avg_position': round(avg_position, 2),
        'avg_ctr': round(avg_ctr * 100, 2),
        'file_path': gsc_data.get('file_path'),
        'loaded_at': gsc_data.get('loaded_at'),
    }


# ============================================================================
# FUNCIONES DE INVALIDACIÓN ESPECÍFICAS
# ============================================================================

def invalidate_gsc_cache() -> int:
    """
    Invalida todo el caché de GSC.
    
    Returns:
        Número de entradas invalidadas
    """
    return _gsc_cache.invalidate_all()


def invalidate_url_cache(url: str) -> int:
    """
    Invalida caché relacionado con una URL específica.
    
    Args:
        url: URL para invalidar
        
    Returns:
        Número de entradas invalidadas
    """
    # Generar hash de la URL para buscar en caché
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    return _gsc_cache.invalidate_pattern(url_hash)


def invalidate_keyword_cache(keyword: str) -> int:
    """
    Invalida caché relacionado con una keyword específica.
    
    Args:
        keyword: Keyword para invalidar
        
    Returns:
        Número de entradas invalidadas
    """
    keyword_hash = hashlib.md5(keyword.encode()).hexdigest()[:8]
    return _gsc_cache.invalidate_pattern(keyword_hash)


def refresh_gsc_data() -> Optional[Dict[str, Any]]:
    """
    Fuerza recarga de datos GSC invalidando caché.
    
    Returns:
        Datos frescos de GSC
    """
    # Invalidar caché de archivo
    _gsc_cache.invalidate_pattern("gsc_file")
    
    # Recargar
    return load_gsc_data()


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def is_gsc_available() -> bool:
    """
    Verifica si hay datos de GSC disponibles.
    
    Returns:
        True si hay datos disponibles
    """
    file_path = GSC_DATA_FILE
    return file_path.exists() and file_path.stat().st_size > 0


def get_cache_stats() -> Dict[str, Any]:
    """
    Obtiene estadísticas del caché GSC.
    
    Returns:
        Dict con estadísticas
    """
    return _gsc_cache.get_stats()


def format_gsc_for_prompt(
    keywords: List[Dict[str, Any]],
    max_keywords: int = 10
) -> str:
    """
    Formatea keywords de GSC para incluir en un prompt.
    
    Args:
        keywords: Lista de keywords con métricas
        max_keywords: Máximo de keywords a incluir
        
    Returns:
        String formateado para prompt
    """
    if not keywords:
        return "No hay datos de GSC disponibles."
    
    lines = ["Keywords de Google Search Console:"]
    
    for i, kw in enumerate(keywords[:max_keywords], 1):
        query = kw.get('query', '')
        clicks = kw.get('clicks', 0)
        impressions = kw.get('impressions', 0)
        position = kw.get('position', 0)
        
        lines.append(
            f"{i}. \"{query}\" - "
            f"Clicks: {clicks}, Impresiones: {impressions}, "
            f"Posición: {position:.1f}"
        )
    
    return "\n".join(lines)


# ============================================================================
# FECHA DE DATOS GSC
# ============================================================================

# Variable global para almacenar la fecha de carga
_gsc_loaded_date: Optional[datetime] = None


def get_gsc_data_date() -> Optional[datetime]:
    """
    Obtiene la fecha de los datos de GSC cargados.
    
    Intenta obtener de (en orden de prioridad):
    1. Variable global del módulo (_gsc_loaded_date)
    2. Estado de Streamlit (st.session_state['gsc_data_date'])
    3. Fecha de modificación del archivo CSV
    
    Returns:
        datetime o None si no hay datos
    """
    global _gsc_loaded_date
    
    # 1. Cache del módulo
    if _gsc_loaded_date is not None:
        return _gsc_loaded_date
    
    # 2. Estado de Streamlit
    try:
        import streamlit as st
        if 'gsc_data_date' in st.session_state:
            return st.session_state['gsc_data_date']
    except ImportError:
        pass
    
    # 3. Fecha de modificación del archivo
    try:
        gsc_file = GSC_DATA_FILE
        if isinstance(gsc_file, str):
            gsc_file = Path(gsc_file)
        
        if gsc_file.exists():
            mod_time = gsc_file.stat().st_mtime
            _gsc_loaded_date = datetime.fromtimestamp(mod_time)
            return _gsc_loaded_date
    except Exception as e:
        logger.debug(f"No se pudo obtener fecha del archivo GSC: {e}")
    
    return None


def set_gsc_data_date(date: Optional[datetime] = None) -> None:
    """
    Establece la fecha de los datos de GSC.
    
    Args:
        date: Fecha a establecer (usa datetime.now() si no se especifica)
    """
    global _gsc_loaded_date
    
    if date is None:
        date = datetime.now()
    
    _gsc_loaded_date = date
    
    # También guardar en Streamlit session_state si está disponible
    try:
        import streamlit as st
        st.session_state['gsc_data_date'] = date
    except ImportError:
        pass


def get_gsc_data_age_days() -> Optional[int]:
    """
    Obtiene la antigüedad de los datos de GSC en días.
    
    Returns:
        Número de días desde la carga/modificación, o None si no hay datos
    """
    date = get_gsc_data_date()
    if date is not None:
        return (datetime.now() - date).days
    return None


def is_gsc_data_stale(max_days: int = GSC_DATA_STALE_DAYS) -> bool:
    """
    Verifica si los datos de GSC están desactualizados.
    
    Args:
        max_days: Número máximo de días para considerar datos frescos
        
    Returns:
        True si los datos tienen más de max_days días o no hay datos
    """
    age = get_gsc_data_age_days()
    if age is None:
        return True  # Sin datos = desactualizado
    return age > max_days


def get_recommended_update_date() -> str:
    """
    Calcula la fecha recomendada para la próxima actualización del dataset.
    
    Returns:
        Fecha formateada como string (ej: "15 Feb 2025")
    """
    # La próxima actualización debería ser DATASET_END_DATE + GSC_DATA_STALE_DAYS
    next_update = DATASET_END_DATE + timedelta(days=GSC_DATA_STALE_DAYS)
    
    # Si ya pasó, recomendar "lo antes posible"
    if next_update < datetime.now():
        return "Lo antes posible"
    
    # Formatear fecha
    months_es = {
        1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
    }
    return f"{next_update.day} {months_es[next_update.month]} {next_update.year}"


# ============================================================================
# ANÁLISIS DE CANIBALIZACIÓN
# ============================================================================

def check_cannibalization(
    keyword: str,
    min_impressions: int = 10,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Busca URLs existentes que ya posicionan para una keyword.
    
    Fuente de datos (por prioridad):
    1. API de GSC via Service Account (tiempo real, si está configurada)
    2. CSV local gsc_keywords.csv (fallback)
    
    Esta función ayuda a detectar posible canibalización de contenido,
    identificando páginas que ya rankean para la keyword objetivo.
    
    Args:
        keyword: Keyword a analizar
        min_impressions: Mínimo de impresiones para considerar una URL
        max_results: Máximo de resultados a retornar
    
    Returns:
        Lista de dicts con URLs y métricas:
        - url: URL de la página
        - clicks: Total de clicks
        - impressions: Total de impresiones
        - position: Posición promedio
        - ctr: CTR calculado
    """
    if not keyword or not keyword.strip():
        return []
    
    # === FUENTE 1: API de GSC (prioridad) ===
    if _gsc_api_available and is_gsc_api_configured():
        try:
            results = api_check_cannibalization(keyword, min_impressions, max_results)
            if results is not None:
                logger.info(f"Canibalización via API GSC: '{keyword}' → {len(results)} URLs")
                return results
        except Exception as e:
            logger.warning(f"Error en API GSC, usando fallback CSV: {e}")
    
    # === FUENTE 2: CSV local (fallback) ===
    keyword_lower = keyword.strip().lower()
    
    # Obtener datos GSC
    gsc_data = None
    
    # Intentar desde Streamlit session_state primero
    try:
        import streamlit as st
        gsc_data = st.session_state.get('gsc_data')
    except ImportError:
        pass
    
    # Si no hay datos en session_state, cargar del archivo
    if gsc_data is None:
        try:
            loaded = load_gsc_data()
            if loaded:
                gsc_data = loaded.get('data', [])
        except Exception as e:
            logger.warning(f"Error cargando datos GSC para canibalización: {e}")
            return []
    
    if not gsc_data:
        return []
    
    # Si gsc_data es un dict con 'data', extraer la lista
    if isinstance(gsc_data, dict) and 'data' in gsc_data:
        gsc_data = gsc_data['data']
    
    # Procesar datos
    url_metrics: Dict[str, Dict[str, Any]] = {}
    
    # Si es DataFrame de pandas
    if _pandas_available and hasattr(gsc_data, 'iterrows'):
        try:
            df = gsc_data
            
            # Filtrar por keyword
            mask = df['query'].str.lower().str.contains(keyword_lower, na=False, regex=False)
            matching = df[mask]
            
            # Filtrar por impresiones mínimas
            if 'impressions' in matching.columns:
                matching = matching[matching['impressions'] >= min_impressions]
            
            # Determinar columna de URL
            url_col = 'page' if 'page' in matching.columns else 'url'
            if url_col not in matching.columns:
                return []
            
            # Agrupar por URL
            grouped = matching.groupby(url_col).agg({
                'clicks': 'sum',
                'impressions': 'sum',
                'position': 'mean'
            }).reset_index()
            
            # Calcular CTR
            grouped['ctr'] = (grouped['clicks'] / grouped['impressions'] * 100).round(2)
            
            # Ordenar y limitar
            grouped = grouped.sort_values('clicks', ascending=False).head(max_results)
            
            results = []
            for _, row in grouped.iterrows():
                results.append({
                    'url': row[url_col],
                    'clicks': int(row['clicks']),
                    'impressions': int(row['impressions']),
                    'position': round(float(row['position']), 1),
                    'ctr': float(row['ctr'])
                })
            
            return results
            
        except Exception as e:
            logger.warning(f"Error procesando GSC con pandas: {e}")
            # Continuar con procesamiento manual
    
    # Procesamiento manual (lista de dicts)
    if isinstance(gsc_data, list):
        for row in gsc_data:
            query = str(row.get('query', '')).lower()
            
            # Verificar si la keyword está en la query
            if keyword_lower not in query:
                continue
            
            # Filtrar por impresiones mínimas
            impressions = int(row.get('impressions', 0))
            if impressions < min_impressions:
                continue
            
            # Obtener URL
            url = row.get('page') or row.get('url', '')
            if not url:
                continue
            
            # Acumular métricas por URL
            if url not in url_metrics:
                url_metrics[url] = {
                    'clicks': 0,
                    'impressions': 0,
                    'position_sum': 0,
                    'count': 0
                }
            
            metrics = url_metrics[url]
            metrics['clicks'] += int(row.get('clicks', 0))
            metrics['impressions'] += impressions
            metrics['position_sum'] += float(row.get('position', 0))
            metrics['count'] += 1
        
        # Convertir a lista de resultados
        results = []
        for url, metrics in url_metrics.items():
            avg_position = metrics['position_sum'] / metrics['count'] if metrics['count'] > 0 else 0
            ctr = (metrics['clicks'] / metrics['impressions'] * 100) if metrics['impressions'] > 0 else 0
            
            results.append({
                'url': url,
                'clicks': metrics['clicks'],
                'impressions': metrics['impressions'],
                'position': round(avg_position, 1),
                'ctr': round(ctr, 2)
            })
        
        # Ordenar por clicks descendente
        results.sort(key=lambda x: x['clicks'], reverse=True)
        
        return results[:max_results]
    
    return []


def get_cannibalization_summary(keyword: str) -> Dict[str, Any]:
    """
    Obtiene un resumen del análisis de canibalización.
    
    Args:
        keyword: Keyword a analizar
        
    Returns:
        Dict con resumen:
        - has_risk: bool indicando si hay riesgo de canibalización
        - total_urls: número de URLs encontradas
        - total_clicks: suma de clicks
        - total_impressions: suma de impresiones
        - best_url: URL con más clicks
        - urls: lista de URLs con métricas
        - recommendation: recomendación textual
    """
    results = check_cannibalization(keyword)
    
    if not results:
        return {
            'has_risk': False,
            'total_urls': 0,
            'total_clicks': 0,
            'total_impressions': 0,
            'best_url': None,
            'urls': [],
            'recommendation': 'No hay contenido existente que posicione para esta keyword. Puedes crear contenido nuevo.'
        }
    
    total_urls = len(results)
    total_clicks = sum(r['clicks'] for r in results)
    total_impressions = sum(r['impressions'] for r in results)
    best_url = results[0]['url'] if results else None
    
    # Generar recomendación basada en la situación
    if total_urls == 1:
        if results[0]['clicks'] < 10:
            recommendation = f"Ya existe contenido con pocas visitas. Considera actualizar '{best_url}' en lugar de crear nuevo contenido."
        else:
            recommendation = f"Ya existe contenido posicionado en '{best_url}'. Evalúa si actualizar el existente o crear contenido complementario."
    elif total_urls <= 3:
        recommendation = f"Se encontraron {total_urls} URLs compitiendo. Considera consolidar el contenido o actualizar la página principal ({best_url})."
    else:
        recommendation = f"⚠️ Alta fragmentación detectada ({total_urls} URLs). Recomendamos consolidar contenido y usar etiquetas canonical para evitar canibalización."
    
    return {
        'has_risk': True,
        'total_urls': total_urls,
        'total_clicks': total_clicks,
        'total_impressions': total_impressions,
        'best_url': best_url,
        'urls': results,
        'recommendation': recommendation
    }


# ============================================================================
# CARGA DE CSV DE KEYWORDS (FORMATO ESPECÍFICO)
# ============================================================================

# Cache para el CSV de keywords
_gsc_keywords_cache: Optional[List[Dict[str, Any]]] = None
_gsc_keywords_cache_time: Optional[datetime] = None


def load_gsc_keywords_csv(
    file_path: Optional[Union[str, Path]] = None,
    force_reload: bool = False
) -> List[Dict[str, Any]]:
    """
    Carga el CSV de keywords de GSC con formato específico.
    
    Formato esperado del CSV (separador `;`):
    url;keyword;position;impressions;clicks;ctr;last_updated
    
    Args:
        file_path: Ruta al archivo CSV. Si no se especifica, busca 'gsc_keywords.csv'
        force_reload: Si True, recarga el archivo aunque esté en caché
    
    Returns:
        Lista de diccionarios con los datos del CSV
    """
    global _gsc_keywords_cache, _gsc_keywords_cache_time
    
    # Usar caché si está disponible y no ha pasado mucho tiempo
    if not force_reload and _gsc_keywords_cache is not None:
        if _gsc_keywords_cache_time:
            age = (datetime.now() - _gsc_keywords_cache_time).total_seconds()
            if age < 3600:  # 1 hora de caché
                return _gsc_keywords_cache
    
    # Buscar archivo
    if file_path:
        csv_path = Path(file_path)
    else:
        # Buscar en ubicaciones comunes
        possible_paths = [
            Path("./data/gsc_keywords.csv"),
            Path("./gsc_keywords.csv"),
            Path("data/gsc_keywords.csv"),
            GSC_DATA_FILE.parent / "gsc_keywords.csv" if GSC_DATA_FILE else None,
        ]
        csv_path = None
        for p in possible_paths:
            if p and p.exists():
                csv_path = p
                break
    
    if not csv_path or not csv_path.exists():
        logger.warning(f"Archivo gsc_keywords.csv no encontrado")
        return []
    
    try:
        rows = []
        separator = _detect_csv_separator(csv_path, 'utf-8')
        
        with open(csv_path, 'r', encoding='utf-8-sig') as f:  # utf-8-sig maneja BOM
            reader = csv.DictReader(f, delimiter=separator)
            
            for row in reader:
                # Normalizar claves
                normalized = {}
                for key, value in row.items():
                    norm_key = key.lower().strip().replace('\ufeff', '')
                    
                    if norm_key in ['clicks', 'impressions']:
                        try:
                            normalized[norm_key] = int(float(value)) if value else 0
                        except (ValueError, TypeError):
                            normalized[norm_key] = 0
                    elif norm_key in ['position', 'ctr']:
                        try:
                            normalized[norm_key] = float(value) if value else 0.0
                        except (ValueError, TypeError):
                            normalized[norm_key] = 0.0
                    else:
                        normalized[norm_key] = value.strip() if value else ''
                
                rows.append(normalized)
        
        # Actualizar caché
        _gsc_keywords_cache = rows
        _gsc_keywords_cache_time = datetime.now()
        
        logger.info(f"Cargadas {len(rows)} filas de gsc_keywords.csv")
        return rows
        
    except Exception as e:
        logger.error(f"Error cargando gsc_keywords.csv: {e}")
        return []


def search_existing_content(
    keyword: str,
    min_impressions: int = 0,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Busca URLs que ya tienen contenido posicionando para una keyword.
    
    Fuente de datos (por prioridad):
    1. API de GSC via Service Account (tiempo real, si está configurada)
    2. CSV local gsc_keywords.csv (fallback)
    
    Args:
        keyword: Keyword a buscar
        min_impressions: Mínimo de impresiones para incluir
        max_results: Máximo de resultados
    
    Returns:
        Lista de URLs con métricas ordenadas por clicks
    """
    if not keyword or not keyword.strip():
        return []
    
    # === FUENTE 1: API de GSC (prioridad) ===
    if _gsc_api_available and is_gsc_api_configured():
        try:
            results = api_search_existing_content(keyword, min_impressions, max_results)
            if results is not None:
                logger.info(f"search_existing_content via API GSC: '{keyword}' → {len(results)} URLs")
                return results
        except Exception as e:
            logger.warning(f"Error en API GSC, usando fallback CSV: {e}")
    
    # === FUENTE 2: CSV local (fallback) ===
    keyword_lower = keyword.strip().lower()
    keyword_words = set(keyword_lower.split())
    
    # Cargar datos
    data = load_gsc_keywords_csv()
    if not data:
        return []
    
    results = []
    
    for row in data:
        row_keyword = row.get('keyword', '').lower()
        impressions = row.get('impressions', 0)
        
        # Filtrar por impresiones mínimas
        if impressions < min_impressions:
            continue
        
        # Buscar coincidencia
        # 1. Coincidencia exacta
        # 2. La keyword buscada está contenida en la keyword del CSV
        # 3. Palabras en común
        row_words = set(row_keyword.split())
        common_words = keyword_words.intersection(row_words)
        
        match_score = 0
        if keyword_lower == row_keyword:
            match_score = 100  # Coincidencia exacta
        elif keyword_lower in row_keyword:
            match_score = 80  # Contenida
        elif row_keyword in keyword_lower:
            match_score = 70  # Inversa
        elif len(common_words) >= 2:
            match_score = 50 + (len(common_words) * 5)  # Múltiples palabras comunes
        elif len(common_words) == 1 and len(keyword_words) <= 2:
            match_score = 30  # Una palabra común (solo para keywords cortas)
        
        if match_score > 0:
            results.append({
                'url': row.get('url', ''),
                'keyword': row.get('keyword', ''),
                'clicks': row.get('clicks', 0),
                'impressions': impressions,
                'position': row.get('position', 0),
                'ctr': row.get('ctr', 0),
                'match_score': match_score,
                'last_updated': row.get('last_updated', '')
            })
    
    # Ordenar por score y clicks
    results.sort(key=lambda x: (x['match_score'], x['clicks']), reverse=True)
    
    return results[:max_results]


def get_content_coverage_summary(keyword: str) -> Dict[str, Any]:
    """
    Obtiene resumen de cobertura de contenido para una keyword.
    
    Args:
        keyword: Keyword a analizar
    
    Returns:
        Dict con resumen de cobertura
    """
    results = search_existing_content(keyword, min_impressions=0, max_results=20)
    
    if not results:
        return {
            'has_coverage': False,
            'total_urls': 0,
            'exact_match': None,
            'partial_matches': [],
            'total_clicks': 0,
            'recommendation': 'No hay contenido existente. Puedes crear contenido nuevo para esta keyword.'
        }
    
    # Separar coincidencias exactas de parciales
    exact = [r for r in results if r['match_score'] >= 80]
    partial = [r for r in results if 30 <= r['match_score'] < 80]
    
    total_clicks = sum(r['clicks'] for r in results)
    best_url = results[0] if results else None
    
    # Generar recomendación
    if exact:
        if exact[0]['clicks'] > 50:
            recommendation = f"⚠️ Ya existe contenido bien posicionado para esta keyword en {exact[0]['url'][:50]}... Considera actualizar ese contenido."
        else:
            recommendation = f"Existe contenido para esta keyword pero con pocos clicks ({exact[0]['clicks']}). Podrías mejorarlo o crear contenido complementario."
    elif partial:
        recommendation = f"Se encontraron {len(partial)} URLs con contenido relacionado. Revisa si cubren la intención de búsqueda antes de crear contenido nuevo."
    else:
        recommendation = "No hay contenido existente. Puedes crear contenido nuevo para esta keyword."
    
    return {
        'has_coverage': len(exact) > 0 or len(partial) > 0,
        'total_urls': len(results),
        'exact_match': exact[0] if exact else None,
        'partial_matches': partial[:5],
        'total_clicks': total_clicks,
        'best_url': best_url,
        'recommendation': recommendation
    }


# ============================================================================
# FUNCIONES DE COMPATIBILIDAD (requeridas por utils/__init__.py)
# ============================================================================

def get_dataset_age() -> Dict[str, Any]:
    """
    Obtiene información sobre la antigüedad del dataset GSC.
    
    Formato esperado por ui/gsc_section.py
    
    Returns:
        Dict con:
        - is_critical: bool - Si los datos son críticamente viejos (>60 días)
        - needs_update: bool - Si los datos necesitan actualización (>30 días)
        - warning_message: str - Mensaje de advertencia
        - dataset_period: str - Período del dataset (ej: "1 Ene - 31 Ene 2025")
        - days_since_end: int - Días desde el fin del dataset
    """
    now = datetime.now()
    days_since_end = (now - DATASET_END_DATE).days
    
    # Determinar niveles
    is_critical = days_since_end > 60
    needs_update = days_since_end > 30
    
    # Generar mensaje
    if is_critical:
        warning_message = f"🔴 **CRÍTICO**: Los datos tienen {days_since_end} días de antigüedad. Actualiza el dataset urgentemente."
    elif needs_update:
        warning_message = f"🟡 **ADVERTENCIA**: Los datos tienen {days_since_end} días. Considera actualizar el dataset."
    else:
        warning_message = f"✅ Los datos están actualizados ({days_since_end} días de antigüedad)."
    
    # Formatear período
    months_es = {
        1: 'Ene', 2: 'Feb', 3: 'Mar', 4: 'Abr', 5: 'May', 6: 'Jun',
        7: 'Jul', 8: 'Ago', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dic'
    }
    start_str = f"{DATASET_START_DATE.day} {months_es[DATASET_START_DATE.month]}"
    end_str = f"{DATASET_END_DATE.day} {months_es[DATASET_END_DATE.month]} {DATASET_END_DATE.year}"
    dataset_period = f"{start_str} - {end_str}"
    
    return {
        'is_critical': is_critical,
        'needs_update': needs_update,
        'warning_message': warning_message,
        'dataset_period': dataset_period,
        'days_since_end': days_since_end,
    }


def analyze_keyword_coverage(keyword: str) -> Dict[str, Any]:
    """
    Analiza la cobertura de una keyword en el contenido existente.
    
    Wrapper de get_content_coverage_summary() para compatibilidad con utils/__init__.py
    
    Args:
        keyword: Keyword a analizar
    
    Returns:
        Dict con análisis de cobertura
    """
    return get_content_coverage_summary(keyword)


# ============================================================================
# UI — CSV UPLOAD WIDGET (reutilizable)
# ============================================================================

def render_gsc_csv_upload(
    key_prefix: str = "gsc",
    label: str = "CSV de GSC",
) -> bool:
    """Widget reutilizable para subir un CSV de Google Search Console.

    Encapsula: file_uploader, detección de separador (;/,), parseo con
    pandas, normalización de columnas, guardado como ``gsc_keywords.csv``
    y ``st.rerun()``.

    Args:
        key_prefix: Prefijo para la key del file_uploader (evita colisiones
            cuando se usa en varias páginas a la vez).
        label: Etiqueta visible del file_uploader.

    Returns:
        ``True`` si se cargó un archivo correctamente, ``False`` en caso
        contrario.
    """
    try:
        import streamlit as st
    except ImportError:
        return False

    uploaded = st.file_uploader(
        label,
        type=["csv", "tsv"],
        key=f"{key_prefix}_csv_upload",
        help="Formato: page/query, clicks, impressions, ctr, position",
    )

    if not uploaded:
        return False

    try:
        import pandas as pd
        import io as _io

        content = uploaded.getvalue().decode("utf-8")
        sep = ";" if content.count(";") > content.count(",") else ","

        df = pd.read_csv(_io.StringIO(content), sep=sep)
        df.columns = df.columns.str.lower().str.strip()

        # Normalizar: GSC exporta "page" pero internamente usamos "url"
        if "page" in df.columns and "url" not in df.columns:
            df["url"] = df["page"]

        if "url" not in df.columns and "page" not in df.columns:
            st.warning(
                "El CSV no tiene columna `page` o `url`. "
                "Sin URLs no se podrán filtrar las oportunidades del blog."
            )

        csv_path = "gsc_keywords.csv"
        df.to_csv(csv_path, index=False)
        st.success(f"{len(df)} keywords cargadas. Recarga la página para continuar.")
        st.rerun()
        return True  # pragma: no cover – rerun interrupts execution
    except Exception as e:
        logger.error("Error procesando CSV de GSC: %s", e)
        st.error("Error procesando el archivo CSV. Verifica el formato.")
        return False


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Excepciones
    'GSCError',
    'GSCFileError',
    'GSCParseError',
    'CacheError',
    
    # Clases
    'CacheEntry',
    'TTLCache',
    
    # Caché global
    'get_gsc_cache',
    'reset_gsc_cache',
    
    # Decorador
    'cached',
    
    # Carga de datos
    'load_gsc_data',
    'load_gsc_keywords_csv',
    
    # Análisis
    'get_keywords_for_url',
    'get_top_keywords',
    'get_related_keywords',
    'get_gsc_summary',
    
    # Invalidación
    'invalidate_gsc_cache',
    'invalidate_url_cache',
    'invalidate_keyword_cache',
    'refresh_gsc_data',
    
    # Utilidades
    'is_gsc_available',
    'get_cache_stats',
    'format_gsc_for_prompt',
    
    # Fecha de datos GSC
    'get_gsc_data_date',
    'set_gsc_data_date',
    'get_gsc_data_age_days',
    'is_gsc_data_stale',
    
    # Análisis de canibalización
    'check_cannibalization',
    'get_cannibalization_summary',
    
    # Búsqueda de contenido existente
    'search_existing_content',
    'get_content_coverage_summary',
    
    # Compatibilidad con utils/__init__.py
    'get_dataset_age',
    'analyze_keyword_coverage',
    
    # Constantes
    'DEFAULT_CACHE_TTL',
    'DEFAULT_CACHE_MAX_SIZE',
    'GSC_DATA_STALE_DAYS',
    
    # Constantes para ui/gsc_section.py
    'RECOMMENDATION_MESSAGES',
    'RISK_LEVEL_COLORS',
    'MATCH_TYPE_DESCRIPTIONS',
    'DATASET_START_DATE',
    'DATASET_END_DATE',
    
    # Función de fecha recomendada
    'get_recommended_update_date',

    # UI — CSV upload widget
    'render_gsc_csv_upload',
]
