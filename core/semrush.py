"""
SEMrush Client - PcComponentes Content Generator
Versión 4.2.0

Cliente para la API de SEMrush con patrón Singleton thread-safe.
Incluye rate limiting, caché, reintentos y connection pooling.

Este módulo proporciona:
- Cliente singleton thread-safe
- Integración con SEMrush API
- Rate limiting automático
- Caché de respuestas con TTL
- Reintentos con backoff exponencial
- Connection pooling

Autor: PcComponentes - Product Discovery & Content
"""

import os
import time
import logging
import threading
import hashlib
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from collections import OrderedDict
from functools import wraps

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# VERSIÓN Y CONSTANTES
# ============================================================================

__version__ = "4.2.0"

# Configuración por defecto
DEFAULT_API_URL = "https://api.semrush.com"
DEFAULT_TIMEOUT = 30
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
DEFAULT_BACKOFF_MULTIPLIER = 2.0
DEFAULT_MAX_RETRY_DELAY = 30.0

# Rate limiting
DEFAULT_RATE_LIMIT = 10  # requests por segundo
DEFAULT_RATE_WINDOW = 1.0  # ventana en segundos

# Caché
DEFAULT_CACHE_TTL = 3600  # 1 hora
DEFAULT_CACHE_MAX_SIZE = 500

# Endpoints de SEMrush
SEMRUSH_ENDPOINTS = {
    'domain_overview': '/analytics/v1/',
    'domain_organic': '/analytics/v1/',
    'domain_adwords': '/analytics/v1/',
    'keyword_overview': '/analytics/v1/',
    'keyword_difficulty': '/analytics/v1/',
    'related_keywords': '/analytics/v1/',
    'phrase_questions': '/analytics/v1/',
    'backlinks_overview': '/analytics/v1/',
    'url_organic': '/analytics/v1/',
}

# Bases de datos regionales
SEMRUSH_DATABASES = {
    'es': 'es',  # España
    'us': 'us',  # Estados Unidos
    'uk': 'uk',  # Reino Unido
    'fr': 'fr',  # Francia
    'de': 'de',  # Alemania
    'it': 'it',  # Italia
    'br': 'br',  # Brasil
    'mx': 'mx',  # México
}

DEFAULT_DATABASE = 'es'


# ============================================================================
# IMPORTS CONDICIONALES
# ============================================================================

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _requests_available = True
except ImportError:
    _requests_available = False
    logger.warning("requests no disponible - SEMrush client limitado")


# ============================================================================
# EXCEPCIONES
# ============================================================================

class SEMrushError(Exception):
    """Excepción base para errores de SEMrush."""
    
    def __init__(
        self,
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class SEMrushAPIError(SEMrushError):
    """Error de la API de SEMrush."""
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None
    ):
        super().__init__(message, error_code="API_ERROR")
        self.status_code = status_code
        self.response_text = response_text


class SEMrushRateLimitError(SEMrushError):
    """Error de rate limit excedido."""
    
    def __init__(self, message: str = "Rate limit excedido", retry_after: float = 0):
        super().__init__(message, error_code="RATE_LIMIT")
        self.retry_after = retry_after


class SEMrushAuthError(SEMrushError):
    """Error de autenticación."""
    
    def __init__(self, message: str = "Error de autenticación"):
        super().__init__(message, error_code="AUTH_ERROR")


class SEMrushConfigError(SEMrushError):
    """Error de configuración."""
    
    def __init__(self, message: str):
        super().__init__(message, error_code="CONFIG_ERROR")


class SEMrushTimeoutError(SEMrushError):
    """Error de timeout."""
    
    def __init__(self, message: str = "Timeout en la petición"):
        super().__init__(message, error_code="TIMEOUT")


# ============================================================================
# ENUMS Y DATA CLASSES
# ============================================================================

class ReportType(Enum):
    """Tipos de reportes de SEMrush."""
    DOMAIN_OVERVIEW = "domain_overview"
    DOMAIN_ORGANIC = "domain_organic"
    DOMAIN_ADWORDS = "domain_adwords"
    KEYWORD_OVERVIEW = "keyword_overview"
    KEYWORD_DIFFICULTY = "keyword_difficulty"
    RELATED_KEYWORDS = "related_keywords"
    PHRASE_QUESTIONS = "phrase_questions"
    BACKLINKS_OVERVIEW = "backlinks_overview"
    URL_ORGANIC = "url_organic"


@dataclass
class RateLimitConfig:
    """Configuración de rate limiting."""
    requests_per_second: float = DEFAULT_RATE_LIMIT
    window_seconds: float = DEFAULT_RATE_WINDOW
    burst_limit: int = 20  # Permite burst hasta este límite


@dataclass
class RetryConfig:
    """Configuración de reintentos."""
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY
    backoff_multiplier: float = DEFAULT_BACKOFF_MULTIPLIER
    max_delay: float = DEFAULT_MAX_RETRY_DELAY
    retry_on_status: List[int] = field(
        default_factory=lambda: [429, 500, 502, 503, 504]
    )


@dataclass
class CacheConfig:
    """Configuración de caché."""
    enabled: bool = True
    ttl: int = DEFAULT_CACHE_TTL
    max_size: int = DEFAULT_CACHE_MAX_SIZE


@dataclass
class SEMrushConfig:
    """Configuración completa del cliente SEMrush."""
    api_key: Optional[str] = None
    api_url: str = DEFAULT_API_URL
    database: str = DEFAULT_DATABASE
    timeout: float = DEFAULT_TIMEOUT
    rate_limit: RateLimitConfig = field(default_factory=RateLimitConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    
    def __post_init__(self):
        """Validar configuración después de inicializar."""
        if not self.api_key:
            # Intentar obtener de variables de entorno
            self.api_key = os.environ.get('SEMRUSH_API_KEY')


@dataclass
class CacheEntry:
    """Entrada de caché."""
    key: str
    value: Any
    created_at: datetime
    expires_at: datetime
    hits: int = 0
    
    def is_expired(self) -> bool:
        """Verifica si la entrada ha expirado."""
        return datetime.now() > self.expires_at
    
    def touch(self) -> None:
        """Actualiza contador de hits."""
        self.hits += 1


@dataclass
class APIResponse:
    """Respuesta de la API."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    status_code: int = 0
    response_time: float = 0
    from_cache: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'status_code': self.status_code,
            'response_time': self.response_time,
            'from_cache': self.from_cache,
        }


# ============================================================================
# RATE LIMITER
# ============================================================================

class RateLimiter:
    """
    Rate limiter thread-safe con token bucket algorithm.
    """
    
    def __init__(self, config: RateLimitConfig):
        self._config = config
        self._tokens = config.burst_limit
        self._last_update = time.monotonic()
        self._lock = threading.Lock()
    
    def acquire(self, timeout: float = 10.0) -> bool:
        """
        Adquiere un token para hacer una petición.
        
        Args:
            timeout: Tiempo máximo de espera
            
        Returns:
            True si se adquirió el token
        """
        deadline = time.monotonic() + timeout
        
        while time.monotonic() < deadline:
            with self._lock:
                self._refill_tokens()
                
                if self._tokens >= 1:
                    self._tokens -= 1
                    return True
            
            # Esperar un poco antes de reintentar
            time.sleep(0.05)
        
        return False
    
    def _refill_tokens(self) -> None:
        """Rellena tokens basado en el tiempo transcurrido."""
        now = time.monotonic()
        elapsed = now - self._last_update
        
        # Calcular tokens a añadir
        tokens_to_add = elapsed * self._config.requests_per_second
        
        self._tokens = min(
            self._config.burst_limit,
            self._tokens + tokens_to_add
        )
        self._last_update = now
    
    def get_wait_time(self) -> float:
        """Retorna tiempo estimado de espera."""
        with self._lock:
            self._refill_tokens()
            
            if self._tokens >= 1:
                return 0
            
            tokens_needed = 1 - self._tokens
            return tokens_needed / self._config.requests_per_second


# ============================================================================
# CACHÉ
# ============================================================================

class ResponseCache:
    """
    Caché de respuestas con TTL y LRU eviction.
    Thread-safe.
    """
    
    def __init__(self, config: CacheConfig):
        self._config = config
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = threading.RLock()
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
        }
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor del caché."""
        if not self._config.enabled:
            return None
        
        with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats['misses'] += 1
                return None
            
            if entry.is_expired():
                del self._cache[key]
                self._stats['misses'] += 1
                return None
            
            # Mover al final (LRU)
            self._cache.move_to_end(key)
            entry.touch()
            self._stats['hits'] += 1
            
            return entry.value
    
    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Guarda valor en caché."""
        if not self._config.enabled:
            return
        
        with self._lock:
            # Limpiar expirados ocasionalmente
            if len(self._cache) % 50 == 0:
                self._cleanup_expired()
            
            # Evict si está lleno
            while len(self._cache) >= self._config.max_size:
                self._evict_oldest()
            
            ttl = ttl or self._config.ttl
            now = datetime.now()
            
            entry = CacheEntry(
                key=key,
                value=value,
                created_at=now,
                expires_at=now + timedelta(seconds=ttl)
            )
            
            self._cache[key] = entry
    
    def invalidate(self, key: str) -> bool:
        """Invalida una entrada específica."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalida entradas que contienen el patrón."""
        with self._lock:
            keys_to_delete = [
                k for k in self._cache.keys()
                if pattern in k
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
            
            return len(keys_to_delete)
    
    def clear(self) -> int:
        """Limpia todo el caché."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché."""
        with self._lock:
            total = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total * 100) if total > 0 else 0
            
            return {
                'size': len(self._cache),
                'max_size': self._config.max_size,
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': f"{hit_rate:.1f}%",
                'evictions': self._stats['evictions'],
                'enabled': self._config.enabled,
            }
    
    def _evict_oldest(self) -> None:
        """Elimina la entrada más antigua (LRU)."""
        if self._cache:
            self._cache.popitem(last=False)
            self._stats['evictions'] += 1
    
    def _cleanup_expired(self) -> int:
        """Limpia entradas expiradas."""
        expired_keys = [
            k for k, v in self._cache.items()
            if v.is_expired()
        ]
        
        for key in expired_keys:
            del self._cache[key]
        
        return len(expired_keys)


# ============================================================================
# SINGLETON METACLASS
# ============================================================================

class SingletonMeta(type):
    """
    Metaclass para implementar Singleton thread-safe.
    """
    
    _instances: Dict[type, Any] = {}
    _lock = threading.Lock()
    
    def __call__(cls, *args, **kwargs):
        # Double-checked locking
        if cls not in cls._instances:
            with cls._lock:
                if cls not in cls._instances:
                    instance = super().__call__(*args, **kwargs)
                    cls._instances[cls] = instance
        return cls._instances[cls]
    
    @classmethod
    def reset_instance(mcs, cls: type) -> None:
        """Resetea la instancia singleton (útil para testing)."""
        with mcs._lock:
            if cls in mcs._instances:
                # Cerrar recursos si tiene método close
                instance = mcs._instances[cls]
                if hasattr(instance, 'close'):
                    try:
                        instance.close()
                    except Exception:
                        pass
                del mcs._instances[cls]


# ============================================================================
# CLIENTE SEMRUSH - SINGLETON
# ============================================================================

class SEMrushClient(metaclass=SingletonMeta):
    """
    Cliente SEMrush con patrón Singleton thread-safe.
    
    Características:
    - Singleton: Solo una instancia en toda la aplicación
    - Thread-safe: Seguro para uso concurrente
    - Rate limiting: Control de velocidad de peticiones
    - Caché: Almacenamiento de respuestas con TTL
    - Reintentos: Backoff exponencial en errores
    - Connection pooling: Reutilización de conexiones
    
    Example:
        >>> client = SEMrushClient(api_key="your_key")
        >>> # Misma instancia en cualquier lugar
        >>> client2 = SEMrushClient()
        >>> assert client is client2
        >>> 
        >>> data = client.get_keyword_overview("monitores gaming")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        config: Optional[SEMrushConfig] = None,
        **kwargs
    ):
        """
        Inicializa el cliente SEMrush.
        
        NOTA: Como es singleton, la configuración solo se aplica
        en la primera inicialización.
        
        Args:
            api_key: API key de SEMrush
            config: Configuración completa (opcional)
            **kwargs: Argumentos adicionales para SEMrushConfig
        """
        # Evitar re-inicialización del singleton
        if hasattr(self, '_initialized') and self._initialized:
            return
        
        # Crear configuración
        if config:
            self._config = config
        else:
            self._config = SEMrushConfig(api_key=api_key, **kwargs)
        
        # Validar API key
        if not self._config.api_key:
            logger.warning(
                "SEMrush API key no configurada. "
                "Configura SEMRUSH_API_KEY en variables de entorno."
            )
        
        # Inicializar componentes
        self._rate_limiter = RateLimiter(self._config.rate_limit)
        self._cache = ResponseCache(self._config.cache)
        self._session: Optional[requests.Session] = None
        self._lock = threading.RLock()
        
        # Crear sesión HTTP si requests está disponible
        if _requests_available:
            self._create_session()
        
        self._initialized = True
        logger.info(f"SEMrushClient inicializado (database={self._config.database})")
    
    def _create_session(self) -> None:
        """Crea sesión HTTP con connection pooling y reintentos."""
        self._session = requests.Session()
        
        # Configurar reintentos
        retry_strategy = Retry(
            total=self._config.retry.max_retries,
            backoff_factor=self._config.retry.retry_delay,
            status_forcelist=self._config.retry.retry_on_status,
            allowed_methods=["GET", "POST"],
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20,
        )
        
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)
    
    def _generate_cache_key(self, endpoint: str, params: Dict) -> str:
        """Genera clave única para caché."""
        # Ordenar params para consistencia
        sorted_params = sorted(params.items())
        key_string = f"{endpoint}:{sorted_params}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    def _make_request(
        self,
        endpoint: str,
        params: Dict[str, Any],
        use_cache: bool = True
    ) -> APIResponse:
        """
        Realiza una petición a la API de SEMrush.
        
        Args:
            endpoint: Endpoint de la API
            params: Parámetros de la petición
            use_cache: Si usar caché
            
        Returns:
            APIResponse con el resultado
        """
        if not _requests_available:
            return APIResponse(
                success=False,
                error="requests no disponible"
            )
        
        if not self._config.api_key:
            return APIResponse(
                success=False,
                error="API key no configurada"
            )
        
        # Generar clave de caché
        cache_key = self._generate_cache_key(endpoint, params)
        
        # Verificar caché
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit para {endpoint}")
                return APIResponse(
                    success=True,
                    data=cached,
                    from_cache=True
                )
        
        # Aplicar rate limiting
        if not self._rate_limiter.acquire(timeout=30):
            return APIResponse(
                success=False,
                error="Rate limit: no se pudo adquirir token"
            )
        
        # Añadir API key a params
        params['key'] = self._config.api_key
        
        # Construir URL
        url = f"{self._config.api_url}{endpoint}"
        
        start_time = time.time()
        
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._config.timeout
            )
            
            response_time = time.time() - start_time
            
            # Verificar errores
            if response.status_code == 429:
                retry_after = float(response.headers.get('Retry-After', 60))
                raise SEMrushRateLimitError(
                    f"Rate limit excedido. Reintentar en {retry_after}s",
                    retry_after=retry_after
                )
            
            if response.status_code == 401:
                raise SEMrushAuthError("API key inválida o expirada")
            
            if response.status_code != 200:
                raise SEMrushAPIError(
                    f"Error de API: {response.status_code}",
                    status_code=response.status_code,
                    response_text=response.text
                )
            
            # Parsear respuesta
            data = self._parse_response(response.text)
            
            # Guardar en caché
            if use_cache and data:
                self._cache.set(cache_key, data)
            
            return APIResponse(
                success=True,
                data=data,
                status_code=response.status_code,
                response_time=response_time
            )
        
        except requests.exceptions.Timeout:
            return APIResponse(
                success=False,
                error="Timeout en la petición",
                response_time=time.time() - start_time
            )
        
        except requests.exceptions.ConnectionError as e:
            return APIResponse(
                success=False,
                error=f"Error de conexión: {e}",
                response_time=time.time() - start_time
            )
        
        except SEMrushError:
            raise
        
        except Exception as e:
            logger.error(f"Error inesperado en SEMrush request: {e}")
            return APIResponse(
                success=False,
                error=f"Error inesperado: {e}",
                response_time=time.time() - start_time
            )
    
    def _parse_response(self, text: str) -> List[Dict[str, Any]]:
        """
        Parsea la respuesta de SEMrush (formato CSV/TSV).
        
        Args:
            text: Texto de respuesta
            
        Returns:
            Lista de diccionarios con los datos
        """
        if not text or text.startswith('ERROR'):
            if 'ERROR' in text:
                raise SEMrushAPIError(f"Error de SEMrush: {text}")
            return []
        
        lines = text.strip().split('\n')
        
        if len(lines) < 2:
            return []
        
        # Primera línea son headers
        headers = lines[0].split(';')
        
        results = []
        for line in lines[1:]:
            if not line.strip():
                continue
            
            values = line.split(';')
            
            if len(values) == len(headers):
                row = {
                    headers[i]: self._parse_value(values[i])
                    for i in range(len(headers))
                }
                results.append(row)
        
        return results
    
    def _parse_value(self, value: str) -> Any:
        """Parsea un valor individual."""
        if not value or value == '':
            return None
        
        # Intentar convertir a número
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            return value
    
    # ========================================================================
    # MÉTODOS PÚBLICOS - KEYWORDS
    # ========================================================================
    
    def get_keyword_overview(
        self,
        keyword: str,
        database: Optional[str] = None,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene overview de una keyword.
        
        Args:
            keyword: Keyword a analizar
            database: Base de datos regional
            use_cache: Si usar caché
            
        Returns:
            APIResponse con datos de la keyword
        """
        params = {
            'type': 'phrase_this',
            'phrase': keyword,
            'database': database or self._config.database,
            'export_columns': 'Ph,Nq,Cp,Co,Nr,Td',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['keyword_overview'],
            params,
            use_cache
        )
    
    def get_keyword_difficulty(
        self,
        keyword: str,
        database: Optional[str] = None,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene dificultad de una keyword.
        
        Args:
            keyword: Keyword a analizar
            database: Base de datos regional
            use_cache: Si usar caché
            
        Returns:
            APIResponse con dificultad
        """
        params = {
            'type': 'phrase_kdi',
            'phrase': keyword,
            'database': database or self._config.database,
            'export_columns': 'Ph,Kd',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['keyword_difficulty'],
            params,
            use_cache
        )
    
    def get_related_keywords(
        self,
        keyword: str,
        database: Optional[str] = None,
        limit: int = 20,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene keywords relacionadas.
        
        Args:
            keyword: Keyword base
            database: Base de datos regional
            limit: Número máximo de resultados
            use_cache: Si usar caché
            
        Returns:
            APIResponse con keywords relacionadas
        """
        params = {
            'type': 'phrase_related',
            'phrase': keyword,
            'database': database or self._config.database,
            'display_limit': limit,
            'export_columns': 'Ph,Nq,Cp,Co,Nr,Td,Rr',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['related_keywords'],
            params,
            use_cache
        )
    
    def get_phrase_questions(
        self,
        keyword: str,
        database: Optional[str] = None,
        limit: int = 10,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene preguntas relacionadas con una keyword.
        
        Args:
            keyword: Keyword base
            database: Base de datos regional
            limit: Número máximo de resultados
            use_cache: Si usar caché
            
        Returns:
            APIResponse con preguntas
        """
        params = {
            'type': 'phrase_questions',
            'phrase': keyword,
            'database': database or self._config.database,
            'display_limit': limit,
            'export_columns': 'Ph,Nq,Cp,Co',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['phrase_questions'],
            params,
            use_cache
        )
    
    # ========================================================================
    # MÉTODOS PÚBLICOS - DOMINIOS
    # ========================================================================
    
    def get_domain_overview(
        self,
        domain: str,
        database: Optional[str] = None,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene overview de un dominio.
        
        Args:
            domain: Dominio a analizar
            database: Base de datos regional
            use_cache: Si usar caché
            
        Returns:
            APIResponse con datos del dominio
        """
        params = {
            'type': 'domain_ranks',
            'domain': domain,
            'database': database or self._config.database,
            'export_columns': 'Dn,Rk,Or,Ot,Oc,Ad,At,Ac',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['domain_overview'],
            params,
            use_cache
        )
    
    def get_domain_organic_keywords(
        self,
        domain: str,
        database: Optional[str] = None,
        limit: int = 100,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene keywords orgánicas de un dominio.
        
        Args:
            domain: Dominio a analizar
            database: Base de datos regional
            limit: Número máximo de resultados
            use_cache: Si usar caché
            
        Returns:
            APIResponse con keywords orgánicas
        """
        params = {
            'type': 'domain_organic',
            'domain': domain,
            'database': database or self._config.database,
            'display_limit': limit,
            'export_columns': 'Ph,Po,Pp,Pd,Nq,Cp,Ur,Tr,Tc,Co,Nr,Td',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['domain_organic'],
            params,
            use_cache
        )
    
    def get_url_organic_keywords(
        self,
        url: str,
        database: Optional[str] = None,
        limit: int = 50,
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene keywords orgánicas de una URL específica.
        
        Args:
            url: URL a analizar
            database: Base de datos regional
            limit: Número máximo de resultados
            use_cache: Si usar caché
            
        Returns:
            APIResponse con keywords de la URL
        """
        params = {
            'type': 'url_organic',
            'url': url,
            'database': database or self._config.database,
            'display_limit': limit,
            'export_columns': 'Ph,Po,Nq,Cp,Co,Tr,Tc',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['url_organic'],
            params,
            use_cache
        )
    
    # ========================================================================
    # MÉTODOS PÚBLICOS - BACKLINKS
    # ========================================================================
    
    def get_backlinks_overview(
        self,
        target: str,
        target_type: str = 'domain',
        use_cache: bool = True
    ) -> APIResponse:
        """
        Obtiene overview de backlinks.
        
        Args:
            target: Dominio o URL objetivo
            target_type: 'domain' o 'url'
            use_cache: Si usar caché
            
        Returns:
            APIResponse con datos de backlinks
        """
        params = {
            'type': 'backlinks_overview',
            'target': target,
            'target_type': target_type,
            'export_columns': 'ascore,total,domains_num,urls_num,ips_num,follows_num,nofollows_num',
        }
        
        return self._make_request(
            SEMRUSH_ENDPOINTS['backlinks_overview'],
            params,
            use_cache
        )
    
    # ========================================================================
    # MÉTODOS DE UTILIDAD
    # ========================================================================
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché."""
        return self._cache.get_stats()
    
    def clear_cache(self) -> int:
        """Limpia el caché."""
        return self._cache.clear()
    
    def invalidate_cache(self, pattern: str) -> int:
        """Invalida entradas del caché por patrón."""
        return self._cache.invalidate_pattern(pattern)
    
    def get_rate_limit_wait(self) -> float:
        """Obtiene tiempo de espera del rate limiter."""
        return self._rate_limiter.get_wait_time()
    
    def is_configured(self) -> bool:
        """Verifica si el cliente está configurado."""
        return bool(self._config.api_key)
    
    def get_config(self) -> Dict[str, Any]:
        """Obtiene configuración actual (sin API key)."""
        return {
            'api_url': self._config.api_url,
            'database': self._config.database,
            'timeout': self._config.timeout,
            'cache_enabled': self._config.cache.enabled,
            'is_configured': self.is_configured(),
        }
    
    def close(self) -> None:
        """Cierra el cliente y libera recursos."""
        with self._lock:
            if self._session:
                self._session.close()
                self._session = None
            self._cache.clear()
        
        logger.info("SEMrushClient cerrado")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================================================
# FUNCIONES DE ACCESO GLOBAL
# ============================================================================

_client_lock = threading.Lock()


def get_semrush_client(
    api_key: Optional[str] = None,
    **kwargs
) -> SEMrushClient:
    """
    Obtiene la instancia singleton del cliente SEMrush.
    
    Args:
        api_key: API key (solo se usa en primera llamada)
        **kwargs: Argumentos adicionales
        
    Returns:
        Instancia de SEMrushClient
    """
    return SEMrushClient(api_key=api_key, **kwargs)


def reset_semrush_client() -> None:
    """Resetea el cliente singleton."""
    SingletonMeta.reset_instance(SEMrushClient)
    logger.info("SEMrushClient reseteado")


def is_semrush_available() -> bool:
    """Verifica si SEMrush está disponible y configurado."""
    if not _requests_available:
        return False
    
    try:
        client = get_semrush_client()
        return client.is_configured()
    except Exception:
        return False


def is_semrush_configured() -> bool:
    """Alias para is_semrush_available."""
    return is_semrush_available()


# ============================================================================
# FUNCIONES DE CONVENIENCIA
# ============================================================================

def get_keyword_data(
    keyword: str,
    database: str = DEFAULT_DATABASE
) -> Optional[Dict[str, Any]]:
    """
    Obtiene datos de una keyword (función de conveniencia).
    
    Args:
        keyword: Keyword a analizar
        database: Base de datos regional
        
    Returns:
        Dict con datos o None si hay error
    """
    client = get_semrush_client()
    
    if not client.is_configured():
        logger.warning("SEMrush no configurado")
        return None
    
    response = client.get_keyword_overview(keyword, database)
    
    if response.success and response.data:
        return response.data[0] if response.data else None
    
    return None


def get_related_keywords(
    keyword: str,
    limit: int = 20,
    database: str = DEFAULT_DATABASE
) -> List[Dict[str, Any]]:
    """
    Obtiene keywords relacionadas (función de conveniencia).
    
    Args:
        keyword: Keyword base
        limit: Número máximo de resultados
        database: Base de datos regional
        
    Returns:
        Lista de keywords relacionadas
    """
    client = get_semrush_client()
    
    if not client.is_configured():
        return []
    
    response = client.get_related_keywords(keyword, database, limit)
    
    return response.data if response.success else []


def get_domain_keywords(
    domain: str,
    limit: int = 100,
    database: str = DEFAULT_DATABASE
) -> List[Dict[str, Any]]:
    """
    Obtiene keywords de un dominio (función de conveniencia).
    
    Args:
        domain: Dominio a analizar
        limit: Número máximo de resultados
        database: Base de datos regional
        
    Returns:
        Lista de keywords del dominio
    """
    client = get_semrush_client()
    
    if not client.is_configured():
        return []
    
    response = client.get_domain_organic_keywords(domain, database, limit)
    
    return response.data if response.success else []


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Excepciones
    'SEMrushError',
    'SEMrushAPIError',
    'SEMrushRateLimitError',
    'SEMrushAuthError',
    'SEMrushConfigError',
    'SEMrushTimeoutError',
    
    # Enums y Data Classes
    'ReportType',
    'RateLimitConfig',
    'RetryConfig',
    'CacheConfig',
    'SEMrushConfig',
    'APIResponse',
    
    # Componentes
    'RateLimiter',
    'ResponseCache',
    
    # Cliente principal
    'SEMrushClient',
    
    # Funciones de acceso
    'get_semrush_client',
    'reset_semrush_client',
    'is_semrush_available',
    'is_semrush_configured',
    
    # Funciones de conveniencia
    'get_keyword_data',
    'get_related_keywords',
    'get_domain_keywords',
    
    # Constantes
    'DEFAULT_DATABASE',
    'SEMRUSH_DATABASES',
    'SEMRUSH_ENDPOINTS',
]
