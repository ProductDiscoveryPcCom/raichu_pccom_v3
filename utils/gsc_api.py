# -*- coding: utf-8 -*-
"""
GSC API - PcComponentes Content Generator
Versión 1.2.1 - 2026-02-11

Conexión directa con la API de Google Search Console usando Service Account.
Las credenciales se leen de st.secrets (nunca del código fuente).

Este módulo proporciona:
- Autenticación via Service Account (sin intervención del usuario)
- Consulta de Search Analytics (keywords, URLs, métricas)
- Detección de canibalización en tiempo real con matching inteligente
- Caché en session_state para evitar llamadas repetidas

Algoritmo de matching v1.2.1:
- Stopwords filtradas (preposiciones, artículos, etc.)
- Ratio de solapamiento mínimo del 40%
- Ponderación de riesgo por posición en SERP
- Período ampliado a 180 días
- Mínimo 50 impresiones para reducir falsos positivos

Configuración requerida en Streamlit Secrets:
    [gsc]
    type = "service_account"
    project_id = "..."
    private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
    client_email = "...@...iam.gserviceaccount.com"
    token_uri = "https://oauth2.googleapis.com/token"

    [gsc_config]
    property_url = "https://www.pccomponentes.com/"

Autor: PcComponentes - Product Discovery & Content
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import unicodedata

logger = logging.getLogger(__name__)

__version__ = "1.2.1"

# ============================================================================
# IMPORTS CON MANEJO DE ERRORES
# ============================================================================

_streamlit_available = False
try:
    import streamlit as st
    _streamlit_available = True
except ImportError:
    pass

_google_api_available = False
try:
    from google.oauth2.service_account import Credentials
    from googleapiclient.discovery import build
    _google_api_available = True
except ImportError:
    logger.info(
        "google-api-python-client no disponible. "
        "Instalar con: pip install google-api-python-client google-auth"
    )


# ============================================================================
# CONSTANTES
# ============================================================================

GSC_SCOPES = ["https://www.googleapis.com/auth/webmasters.readonly"]
GSC_API_SERVICE = "searchconsole"
GSC_API_VERSION = "v1"

# Período de consulta: 180 días (6 meses) para detectar contenido
# que pueda haber perdido posiciones recientemente pero sigue indexado
DEFAULT_DAYS_BACK = 180

# Caché TTL en segundos (30 minutos)
CACHE_TTL_SECONDS = 1800

# Máximo de filas por consulta a la API
API_ROW_LIMIT = 1000

# Mínimo de impresiones por defecto para filtrar ruido
DEFAULT_MIN_IMPRESSIONS = 50

# Ratio mínimo de solapamiento de palabras (40%)
MIN_OVERLAP_RATIO = 0.4

# Stopwords en español (normalizadas sin acentos) — se excluyen del matching
# Ej: "monitor de cocina" vs "monitor de gaming" no debería puntuar por "de"
STOPWORDS_ES = frozenset({
    "a", "al", "ante", "con", "de", "del", "desde", "el", "en", "entre",
    "es", "esa", "ese", "eso", "esta", "este", "esto", "hay", "la", "las",
    "lo", "los", "mas", "o", "para", "pero", "por", "que", "se",
    "si", "sin", "sobre", "su", "sus", "tambien", "un", "una", "uno",
    "unos", "unas", "y", "ya",
    # Stopwords comunes en queries de producto
    "mejor", "mejores", "cual", "como", "donde", "cuando",
})


# ============================================================================
# FUNCIONES DE MATCHING
# ============================================================================

def _normalize_text(text: str) -> str:
    """
    Normaliza texto: minúsculas y elimina acentos/diacríticos.
    
    "Portátil" → "portatil", "ratón" → "raton"
    Necesario porque las queries de Google varían en acentuación.
    """
    text = text.strip().lower()
    # Descomponer caracteres Unicode y eliminar marcas de acento
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _clean_keywords(text: str) -> Set[str]:
    """
    Extrae palabras significativas de un texto, eliminando stopwords
    y normalizando acentos.
    
    Args:
        text: Texto a limpiar
        
    Returns:
        Set de palabras significativas normalizadas
    """
    normalized = _normalize_text(text)
    words = set(normalized.split())
    return words - STOPWORDS_ES


def _calculate_match_score(keyword: str, query: str) -> int:
    """
    Calcula puntuación de matching entre keyword objetivo y query de GSC.
    
    Mejoras sobre v1.2.0:
    - Stopwords excluidas del matching
    - Ratio de solapamiento mínimo del 40%
    - Keywords largas (3+ palabras) requieren 2+ palabras en común
    
    Args:
        keyword: Keyword objetivo del usuario
        query: Query encontrada en GSC
        
    Returns:
        Puntuación 0-100 (0 = sin match)
    """
    keyword_lower = keyword.strip().lower()
    query_lower = query.strip().lower()
    
    # Normalizar acentos para comparaciones de substring
    keyword_norm = _normalize_text(keyword)
    query_norm = _normalize_text(query)
    
    # Coincidencia exacta (máxima puntuación) — con y sin acentos
    if keyword_lower == query_lower or keyword_norm == query_norm:
        return 100
    
    # Keyword contenida completamente en la query
    if keyword_lower in query_lower or keyword_norm in query_norm:
        return 85
    
    # Query contenida completamente en la keyword
    if query_lower in keyword_lower or query_norm in keyword_norm:
        return 70
    
    # Matching por palabras significativas (sin stopwords)
    keyword_words = _clean_keywords(keyword)
    query_words = _clean_keywords(query)
    
    # Si después de limpiar stopwords no queda nada, no hay match
    if not keyword_words or not query_words:
        return 0
    
    common_words = keyword_words.intersection(query_words)
    
    if not common_words:
        return 0
    
    # Ratio de solapamiento: % de palabras de la keyword presentes en la query
    overlap_ratio = len(common_words) / len(keyword_words)
    
    # Filtro: mínimo 40% de solapamiento
    if overlap_ratio < MIN_OVERLAP_RATIO:
        return 0
    
    # Filtro: keywords de 3+ palabras requieren 2+ palabras en común
    if len(keyword_words) >= 3 and len(common_words) < 2:
        return 0
    
    # Puntuación base por solapamiento (30-65 rango)
    score = 30 + int(overlap_ratio * 35)
    
    return min(score, 65)  # Cap en 65 para que no supere "contenida"


def _calculate_risk_level(position: float) -> Dict[str, Any]:
    """
    Calcula nivel de riesgo de canibalización basado en posición SERP.
    
    Una URL en top 10 es canibalización grave.
    Una URL en posición 80+ es irrelevante.
    
    Args:
        position: Posición media en SERP
        
    Returns:
        Dict con risk_level, risk_label, risk_multiplier
    """
    if position <= 10:
        return {
            "risk_level": "high",
            "risk_label": "🔴 Alto",
            "risk_multiplier": 1.5
        }
    elif position <= 20:
        return {
            "risk_level": "medium_high",
            "risk_label": "🟠 Medio-Alto",
            "risk_multiplier": 1.3
        }
    elif position <= 30:
        return {
            "risk_level": "medium",
            "risk_label": "🟡 Medio",
            "risk_multiplier": 1.0
        }
    elif position <= 50:
        return {
            "risk_level": "low",
            "risk_label": "🟢 Bajo",
            "risk_multiplier": 0.7
        }
    else:
        return {
            "risk_level": "minimal",
            "risk_label": "⚪ Mínimo",
            "risk_multiplier": 0.4
        }


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

def _get_credentials() -> Optional[Any]:
    """
    Obtiene credenciales de Service Account desde st.secrets.
    
    Returns:
        Credentials object o None si no está configurado
    """
    if not _streamlit_available or not _google_api_available:
        return None
    
    try:
        gsc_secrets = dict(st.secrets["gsc"])
        
        # Validar campos mínimos requeridos
        required_fields = ["type", "project_id", "private_key", "client_email", "token_uri"]
        missing = [f for f in required_fields if f not in gsc_secrets]
        if missing:
            logger.warning(f"Campos faltantes en secrets[gsc]: {missing}")
            return None
        
        credentials = Credentials.from_service_account_info(
            gsc_secrets,
            scopes=GSC_SCOPES
        )
        return credentials
        
    except KeyError:
        logger.info("Sección [gsc] no encontrada en secrets - API GSC no configurada")
        return None
    except Exception as e:
        logger.error(f"Error creando credenciales GSC: {e}")
        return None


def _get_property_url() -> str:
    """
    Obtiene la URL de la propiedad de GSC desde secrets.
    
    Returns:
        URL de la propiedad (default: https://www.pccomponentes.com/)
    """
    try:
        return st.secrets["gsc_config"]["property_url"]
    except (KeyError, Exception):
        return "https://www.pccomponentes.com/"


def _build_service() -> Optional[Any]:
    """
    Construye el servicio de la API de Search Console.
    
    Returns:
        Service object o None
    """
    credentials = _get_credentials()
    if not credentials:
        return None
    
    try:
        service = build(
            GSC_API_SERVICE,
            GSC_API_VERSION,
            credentials=credentials,
            cache_discovery=False
        )
        return service
    except Exception as e:
        logger.error(f"Error construyendo servicio GSC API: {e}")
        return None


# ============================================================================
# CACHÉ EN SESSION STATE
# ============================================================================

def _get_cache_key(keyword: str) -> str:
    """Genera clave de caché para una keyword."""
    return f"gsc_api_cache_{keyword.strip().lower()}"


def _get_cached_result(keyword: str) -> Optional[List[Dict]]:
    """
    Obtiene resultado cacheado si existe y no ha expirado.
    
    Args:
        keyword: Keyword a buscar en caché
        
    Returns:
        Lista de resultados o None si no hay caché válido
    """
    if not _streamlit_available:
        return None
    
    cache_key = _get_cache_key(keyword)
    cache = st.session_state.get(cache_key)
    
    if cache is None:
        return None
    
    # Verificar TTL
    cached_at = cache.get("timestamp")
    if cached_at:
        age = (datetime.now() - cached_at).total_seconds()
        if age > CACHE_TTL_SECONDS:
            del st.session_state[cache_key]
            return None
    
    return cache.get("data")


def _set_cached_result(keyword: str, data: List[Dict]) -> None:
    """Guarda resultado en caché."""
    if not _streamlit_available:
        return
    
    cache_key = _get_cache_key(keyword)
    st.session_state[cache_key] = {
        "data": data,
        "timestamp": datetime.now()
    }


# ============================================================================
# CONSULTAS A LA API
# ============================================================================

def query_search_analytics(
    keyword: str,
    days_back: int = DEFAULT_DAYS_BACK,
    row_limit: int = API_ROW_LIMIT
) -> List[Dict[str, Any]]:
    """
    Consulta la API de Search Analytics para una keyword.
    
    Busca todas las URLs que posicionan para queries que contienen
    la keyword, agrupadas por página y query.
    
    Los resultados se cachean en session_state (TTL = CACHE_TTL_SECONDS)
    para evitar llamadas repetidas en cada rerun de Streamlit.
    
    Args:
        keyword: Keyword a buscar
        days_back: Días hacia atrás a consultar (default: 180)
        row_limit: Máximo de filas a devolver
        
    Returns:
        Lista de dicts con: query, page, clicks, impressions, ctr, position
    """
    # ── Cache en session_state ──
    import unicodedata as _ud
    _kw_norm = ''.join(
        c for c in keyword.strip()
        if _ud.category(c) not in ('Cf',)
    ).lower()
    _qa_cache_key = f"gsc_qa_{_kw_norm}_{days_back}_{row_limit}"
    if _streamlit_available:
        import streamlit as _st
        _qa_cached = _st.session_state.get(_qa_cache_key)
        if _qa_cached is not None:
            _age = (datetime.now() - _qa_cached.get("timestamp", datetime.min)).total_seconds()
            if _age < CACHE_TTL_SECONDS:
                logger.debug(f"query_search_analytics cache hit: '{keyword}' (age {_age:.0f}s)")
                return _qa_cached["data"]
            else:
                del _st.session_state[_qa_cache_key]
    
    service = _build_service()
    if not service:
        return []
    
    property_url = _get_property_url()
    
    # Rango de fechas: GSC tarda ~3 días en procesar datos
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days_back)
    
    try:
        response = service.searchanalytics().query(
            siteUrl=property_url,
            body={
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "dimensions": ["query", "page"],
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "query",
                        "operator": "contains",
                        "expression": keyword.strip().lower()
                    }]
                }],
                "rowLimit": row_limit,
                "startRow": 0
            }
        ).execute()
        
        rows = response.get("rows", [])
        
        results = []
        for row in rows:
            keys = row.get("keys", [])
            if len(keys) >= 2:
                results.append({
                    "query": keys[0],
                    "page": keys[1],
                    "clicks": row.get("clicks", 0),
                    "impressions": row.get("impressions", 0),
                    "ctr": round(row.get("ctr", 0) * 100, 2),
                    "position": round(row.get("position", 0), 1)
                })
        
        logger.info(
            f"GSC API: '{keyword}' → {len(results)} resultados "
            f"({start_date.strftime('%d/%m')} - {end_date.strftime('%d/%m')})"
        )
        
        # Cachear resultado
        if _streamlit_available:
            import streamlit as _st
            _st.session_state[_qa_cache_key] = {"data": results, "timestamp": datetime.now()}
        
        return results
        
    except Exception as e:
        logger.error(f"Error consultando GSC API para '{keyword}': {e}")
        return []


# ============================================================================
# FUNCIONES PRINCIPALES (misma interfaz que gsc_utils.py)
# ============================================================================

def api_check_cannibalization(
    keyword: str,
    min_impressions: int = DEFAULT_MIN_IMPRESSIONS,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Busca URLs existentes que ya posicionan para una keyword via API.
    
    Mejoras v1.2.1:
    - Período de 180 días (antes 90)
    - Mínimo 50 impresiones (antes 10) para reducir falsos positivos
    - Nivel de riesgo basado en posición SERP
    - Queries relacionadas incluidas en resultados
    
    Args:
        keyword: Keyword a analizar
        min_impressions: Mínimo de impresiones para considerar una URL
        max_results: Máximo de resultados a retornar
        
    Returns:
        Lista de dicts con: url, clicks, impressions, position, ctr,
        risk_level, risk_label, queries
    """
    if not keyword or not keyword.strip():
        return []
    
    # Intentar caché primero
    cached = _get_cached_result(keyword)
    if cached is not None:
        logger.debug(f"GSC API caché hit para '{keyword}'")
        return cached
    
    # Consultar API
    raw_results = query_search_analytics(keyword)
    
    if not raw_results:
        _set_cached_result(keyword, [])
        return []
    
    # Agrupar por URL (una URL puede aparecer con múltiples queries)
    url_metrics: Dict[str, Dict[str, Any]] = {}
    
    for row in raw_results:
        impressions = row.get("impressions", 0)
        if impressions < min_impressions:
            continue
        
        url = row.get("page", "")
        if not url:
            continue
        
        if url not in url_metrics:
            url_metrics[url] = {
                "clicks": 0,
                "impressions": 0,
                "position_sum": 0.0,
                "count": 0,
                "queries": []
            }
        
        metrics = url_metrics[url]
        metrics["clicks"] += row.get("clicks", 0)
        metrics["impressions"] += impressions
        metrics["position_sum"] += row.get("position", 0)
        metrics["count"] += 1
        metrics["queries"].append(row.get("query", ""))
    
    # Convertir a lista de resultados con nivel de riesgo
    results = []
    for url, metrics in url_metrics.items():
        avg_position = metrics["position_sum"] / metrics["count"] if metrics["count"] > 0 else 0
        ctr = (metrics["clicks"] / metrics["impressions"] * 100) if metrics["impressions"] > 0 else 0
        
        risk = _calculate_risk_level(avg_position)
        
        results.append({
            "url": url,
            "clicks": metrics["clicks"],
            "impressions": metrics["impressions"],
            "position": round(avg_position, 1),
            "ctr": round(ctr, 2),
            "risk_level": risk["risk_level"],
            "risk_label": risk["risk_label"],
            "risk_multiplier": risk["risk_multiplier"],
            "queries": metrics["queries"][:5]
        })
    
    # Ordenar por riesgo ponderado (posición × clicks)
    # Un URL en top 10 con muchos clicks es la mayor amenaza
    results.sort(
        key=lambda x: x["clicks"] * x["risk_multiplier"],
        reverse=True
    )
    results = results[:max_results]
    
    # Guardar en caché
    _set_cached_result(keyword, results)
    
    return results


def api_search_existing_content(
    keyword: str,
    min_impressions: int = 0,
    max_results: int = 10
) -> List[Dict[str, Any]]:
    """
    Busca URLs con contenido posicionando para una keyword via API.
    
    Mejoras v1.2.1:
    - Stopwords excluidas del matching
    - Ratio de solapamiento mínimo del 40%
    - Keywords de 3+ palabras requieren 2+ palabras en común
    - Nivel de riesgo por posición incluido
    
    Args:
        keyword: Keyword a buscar
        min_impressions: Mínimo de impresiones
        max_results: Máximo de resultados
        
    Returns:
        Lista de URLs con métricas, match_score y risk_level
    """
    if not keyword or not keyword.strip():
        return []
    
    keyword_lower = keyword.strip().lower()
    
    # Consultar API
    raw_results = query_search_analytics(keyword)
    
    if not raw_results:
        return []
    
    # Agrupar por URL con scoring mejorado
    url_data: Dict[str, Dict[str, Any]] = {}
    
    for row in raw_results:
        impressions = row.get("impressions", 0)
        if impressions < min_impressions:
            continue
        
        url = row.get("page", "")
        query = row.get("query", "")
        
        if not url:
            continue
        
        # Calcular match_score con algoritmo mejorado
        match_score = _calculate_match_score(keyword_lower, query)
        
        # Solo incluir si hay match significativo
        if match_score == 0:
            continue
        
        position = row.get("position", 0)
        risk = _calculate_risk_level(position)
        
        if url not in url_data:
            url_data[url] = {
                "url": url,
                "keyword": query,
                "clicks": 0,
                "impressions": 0,
                "position": position,
                "ctr": row.get("ctr", 0),
                "match_score": match_score,
                "risk_level": risk["risk_level"],
                "risk_label": risk["risk_label"],
                "last_updated": datetime.now().strftime("%Y-%m-%d")
            }
        
        entry = url_data[url]
        entry["clicks"] += row.get("clicks", 0)
        entry["impressions"] += impressions
        # Mantener el match_score más alto y su query asociada
        if match_score > entry["match_score"]:
            entry["match_score"] = match_score
            entry["keyword"] = query
            # Actualizar riesgo con la mejor posición
            entry["risk_level"] = risk["risk_level"]
            entry["risk_label"] = risk["risk_label"]
    
    results = list(url_data.values())
    results.sort(key=lambda x: (x["match_score"], x["clicks"]), reverse=True)
    
    return results[:max_results]


def api_get_content_coverage_summary(keyword: str) -> Dict[str, Any]:
    """
    Resumen de cobertura de contenido via API.
    
    Misma interfaz que get_content_coverage_summary() en gsc_utils.py
    con información de riesgo añadida.
    """
    results = api_search_existing_content(keyword, min_impressions=0, max_results=20)
    
    if not results:
        return {
            "has_coverage": False,
            "total_urls": 0,
            "exact_match": None,
            "partial_matches": [],
            "total_clicks": 0,
            "recommendation": "No hay contenido existente. Puedes crear contenido nuevo para esta keyword.",
            "data_source": "gsc_api",
            "period_days": DEFAULT_DAYS_BACK
        }
    
    exact = [r for r in results if r["match_score"] >= 80]
    partial = [r for r in results if 30 <= r["match_score"] < 80]
    total_clicks = sum(r["clicks"] for r in results)
    best_url = results[0] if results else None
    
    # Contar URLs de alto riesgo (top 20 de Google)
    high_risk_count = sum(
        1 for r in results
        if r.get("risk_level") in ("high", "medium_high")
    )
    
    if exact:
        best = exact[0]
        risk_info = f" ({best.get('risk_label', '')})" if best.get("risk_label") else ""
        if best["clicks"] > 50:
            recommendation = (
                f"⚠️ Ya existe contenido bien posicionado{risk_info} para esta keyword "
                f"en {best['url'][:60]}... Considera actualizar ese contenido."
            )
        else:
            recommendation = (
                f"Existe contenido para esta keyword pero con pocos clicks "
                f"({best['clicks']}){risk_info}. Podrías mejorarlo o crear contenido complementario."
            )
    elif partial:
        if high_risk_count > 0:
            recommendation = (
                f"Se encontraron {len(partial)} URLs con contenido relacionado, "
                f"{high_risk_count} en posiciones altas. "
                f"Revisa si cubren la intención de búsqueda antes de crear contenido nuevo."
            )
        else:
            recommendation = (
                f"Se encontraron {len(partial)} URLs con contenido relacionado en posiciones bajas. "
                f"Hay oportunidad de crear contenido mejor posicionado."
            )
    else:
        recommendation = "No hay contenido existente. Puedes crear contenido nuevo para esta keyword."
    
    return {
        "has_coverage": len(exact) > 0 or len(partial) > 0,
        "total_urls": len(results),
        "exact_match": exact[0] if exact else None,
        "partial_matches": partial[:5],
        "total_clicks": total_clicks,
        "best_url": best_url,
        "recommendation": recommendation,
        "high_risk_urls": high_risk_count,
        "data_source": "gsc_api",
        "period_days": DEFAULT_DAYS_BACK
    }


# ============================================================================
# FUNCIONES DE ESTADO
# ============================================================================

def is_gsc_api_configured() -> bool:
    """
    Verifica si la API de GSC está configurada y disponible.
    
    Returns:
        True si las credenciales están configuradas y las dependencias instaladas
    """
    if not _google_api_available:
        return False
    
    if not _streamlit_available:
        return False
    
    try:
        gsc_secrets = st.secrets.get("gsc")
        if not gsc_secrets:
            return False
        
        required = ["type", "private_key", "client_email"]
        return all(k in gsc_secrets for k in required)
    except Exception:
        return False


def test_gsc_api_connection() -> Dict[str, Any]:
    """
    Prueba la conexión con la API de GSC.
    
    Returns:
        Dict con: success, message, property_url
    """
    if not _google_api_available:
        return {
            "success": False,
            "message": "Dependencias no instaladas (google-api-python-client, google-auth)"
        }
    
    if not is_gsc_api_configured():
        return {
            "success": False,
            "message": "Credenciales GSC no configuradas en Streamlit Secrets"
        }
    
    service = _build_service()
    if not service:
        return {
            "success": False,
            "message": "Error construyendo servicio GSC API"
        }
    
    property_url = _get_property_url()
    
    try:
        # Consulta mínima para verificar acceso
        end_date = datetime.now() - timedelta(days=3)
        start_date = end_date - timedelta(days=7)
        
        response = service.searchanalytics().query(
            siteUrl=property_url,
            body={
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "dimensions": ["query"],
                "rowLimit": 1
            }
        ).execute()
        
        rows = response.get("rows", [])
        
        return {
            "success": True,
            "message": f"Conexión OK — propiedad: {property_url}",
            "property_url": property_url,
            "has_data": len(rows) > 0
        }
        
    except Exception as e:
        error_msg = str(e)
        if "403" in error_msg:
            hint = "La Service Account no tiene acceso a la propiedad. Añádela como usuario en GSC."
        elif "404" in error_msg:
            hint = f"Propiedad no encontrada: {property_url}. Verifica la URL en secrets."
        elif "401" in error_msg:
            hint = "Credenciales inválidas. Regenera la clave JSON de la Service Account."
        else:
            hint = error_msg
        
        return {
            "success": False,
            "message": f"Error de conexión: {hint}"
        }


# ============================================================================
# QUICK KEYWORD CHECK (últimos 7 días — para inline check al escribir keyword)
# ============================================================================

def quick_keyword_check(
    keyword: str,
    days_back: int = 7,
) -> Dict[str, Any]:
    """
    Comprobación rápida de keyword en GSC API — últimos N días.
    
    Retorna datos de impresiones, clicks y posición media para la keyword.
    Ideal para check inline al introducir keyword en modos new/rewrite.
    
    Los resultados se cachean en session_state (TTL = CACHE_TTL_SECONDS)
    para evitar llamadas repetidas a la API en cada rerun de Streamlit.
    
    Args:
        keyword: Keyword a comprobar
        days_back: Días hacia atrás (default: 7)
        
    Returns:
        Dict con: has_data, urls, total_clicks, total_impressions,
        data_source, period_days
    """
    empty = {
        "has_data": False,
        "urls": [],
        "total_clicks": 0,
        "total_impressions": 0,
        "data_source": "gsc_api",
        "period_days": days_back,
    }
    
    # ── Cache en session_state para evitar llamadas en cada rerun ──
    # Normalizar: strip + lowercase + eliminar zero-width chars (U+200B etc.)
    import unicodedata as _ud
    kw_normalized = ''.join(
        c for c in keyword.strip()
        if _ud.category(c) not in ('Cf',)  # Cf = Format chars (ZWS, ZWNJ, etc.)
    ).lower()
    cache_key = f"gsc_quick_{kw_normalized}_{days_back}"
    if _streamlit_available:
        import streamlit as _st
        cached = _st.session_state.get(cache_key)
        if cached is not None:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < CACHE_TTL_SECONDS:
                logger.debug(f"quick_keyword_check cache hit: '{keyword}' (age {age:.0f}s)")
                return cached["data"]
            else:
                del _st.session_state[cache_key]
    
    service = _build_service()
    if not service:
        return empty
    
    property_url = _get_property_url()
    
    # GSC tarda ~3 días en procesar → end = hoy - 3
    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days_back)
    
    try:
        response = service.searchanalytics().query(
            siteUrl=property_url,
            body={
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "dimensions": ["query", "page"],
                "dimensionFilterGroups": [{
                    "filters": [{
                        "dimension": "query",
                        "operator": "contains",
                        "expression": keyword.strip().lower()
                    }]
                }],
                "rowLimit": 25,
                "startRow": 0,
            }
        ).execute()
        
        rows = response.get("rows", [])
        if not rows:
            # Cachear resultado vacío para no repetir la consulta
            if _streamlit_available:
                import streamlit as _st
                _st.session_state[cache_key] = {"data": empty, "timestamp": datetime.now()}
            return empty
        
        # Agrupar por URL (una URL puede tener múltiples queries)
        url_data: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            keys = row.get("keys", [])
            if len(keys) < 2:
                continue
            query, page = keys[0], keys[1]
            clicks = row.get("clicks", 0)
            impressions = row.get("impressions", 0)
            position = row.get("position", 0)
            
            if page not in url_data:
                url_data[page] = {
                    "url": page,
                    "queries": [],
                    "clicks": 0,
                    "impressions": 0,
                    "best_position": 100,
                    "ctr": 0,
                }
            
            url_data[page]["queries"].append(query)
            url_data[page]["clicks"] += clicks
            url_data[page]["impressions"] += impressions
            url_data[page]["best_position"] = min(
                url_data[page]["best_position"], position
            )
            if url_data[page]["impressions"] > 0:
                url_data[page]["ctr"] = (
                    url_data[page]["clicks"] / url_data[page]["impressions"]
                )
        
        # Ordenar por clicks desc
        urls = sorted(url_data.values(), key=lambda x: x["clicks"], reverse=True)
        
        # Calcular match_score y limpiar
        for u in urls:
            best_query = max(u["queries"], key=lambda q: _calculate_match_score(keyword, q))
            u["query"] = best_query
            u["match_score"] = _calculate_match_score(keyword, best_query)
            u["position"] = round(u["best_position"], 1)
            del u["best_position"]
            del u["queries"]
        
        total_clicks = sum(u["clicks"] for u in urls)
        total_impressions = sum(u["impressions"] for u in urls)
        
        logger.info(
            f"GSC quick check: '{keyword}' → {len(urls)} URLs, "
            f"{total_clicks} clicks, {total_impressions} imp "
            f"(últimos {days_back} días)"
        )
        
        result = {
            "has_data": True,
            "urls": urls,
            "total_clicks": total_clicks,
            "total_impressions": total_impressions,
            "data_source": "gsc_api",
            "period_days": days_back,
        }
        
        # Cachear resultado
        if _streamlit_available:
            import streamlit as _st
            _st.session_state[cache_key] = {"data": result, "timestamp": datetime.now()}
        
        return result
        
    except Exception as e:
        logger.error(f"Error en quick_keyword_check para '{keyword}': {e}")
        return empty


# ============================================================================
# FETCH ALL KEYWORDS (para Oportunidades — sin filtro de keyword)
# ============================================================================

def fetch_all_keywords(
    days_back: int = 90,
    row_limit: int = 5000,
    min_impressions: int = 10,
) -> Optional[Dict[str, Any]]:
    """
    Descarga TODAS las keywords de GSC (sin filtro) para el análisis de oportunidades.

    Retorna un dict compatible con load_gsc_data() del CSV:
        {"data": [{"query": ..., "page": ..., "clicks": ..., ...}], "source": "api"}

    Los resultados se cachean 30 min en session_state.

    Args:
        days_back: Período de consulta (default: 90 días)
        row_limit: Máximo de filas por request (API max = 25000)
        min_impressions: Filtrar queries con pocas impresiones

    Returns:
        Dict compatible con load_gsc_data() o None si falla
    """
    # ── Cache ──
    cache_key = f"gsc_all_keywords_{days_back}_{row_limit}"
    if _streamlit_available:
        cached = st.session_state.get(cache_key)
        if cached is not None:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < CACHE_TTL_SECONDS:
                logger.debug(f"fetch_all_keywords cache hit (age {age:.0f}s)")
                return cached["data"]
            else:
                del st.session_state[cache_key]

    if not is_gsc_api_configured():
        return None

    service = _build_service()
    if not service:
        return None

    property_url = _get_property_url()

    end_date = datetime.now() - timedelta(days=3)
    start_date = end_date - timedelta(days=days_back)

    all_rows = []
    start_row = 0
    max_per_request = min(row_limit, 25000)

    try:
        while True:
            response = service.searchanalytics().query(
                siteUrl=property_url,
                body={
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                    "dimensions": ["query", "page"],
                    "rowLimit": max_per_request,
                    "startRow": start_row,
                }
            ).execute()

            rows = response.get("rows", [])
            if not rows:
                break

            for row in rows:
                keys = row.get("keys", [])
                if len(keys) >= 2:
                    impressions = row.get("impressions", 0)
                    if impressions >= min_impressions:
                        clicks = row.get("clicks", 0)
                        all_rows.append({
                            "query": keys[0],
                            "page": keys[1],
                            "url": keys[1],
                            "clicks": clicks,
                            "impressions": impressions,
                            "ctr": round(row.get("ctr", 0), 4),
                            "position": round(row.get("position", 0), 1),
                        })

            start_row += len(rows)
            if len(rows) < max_per_request or start_row >= row_limit:
                break

        logger.info(
            f"GSC API fetch_all_keywords: {len(all_rows)} keywords "
            f"({start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')})"
        )

        result = {
            "data": all_rows,
            "source": "api",
            "period": f"{start_date.strftime('%Y-%m-%d')} — {end_date.strftime('%Y-%m-%d')}",
            "total_rows": len(all_rows),
        }

        # Cachear
        if _streamlit_available:
            st.session_state[cache_key] = {"data": result, "timestamp": datetime.now()}

        return result

    except Exception as e:
        logger.error(f"Error en fetch_all_keywords: {e}")
        return None


def fetch_keyword_trends(
    keyword: str,
    periods: Optional[List[Dict[str, int]]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Consulta datos de GSC para una keyword en múltiples períodos temporales.

    Permite comparar rendimiento en 7d vs 28d vs 3mo para detectar
    tendencias, subidas/bajadas y SWAPs de URL.

    Args:
        keyword: Keyword a analizar
        periods: Lista de períodos [{"label": "7d", "days": 7}, ...]
            Si None, usa [7d, 28d, 90d]

    Returns:
        Dict con datos por período y análisis comparativo, o None si falla.
        {
            "keyword": str,
            "periods": {
                "7d": {"position": float, "clicks": int, "impressions": int,
                       "ctr": float, "urls": [{"url": ..., "clicks": ..., ...}]},
                "28d": {...},
                "90d": {...},
            },
            "trends": {
                "position_change_7d_vs_28d": float,
                "position_change_28d_vs_90d": float,
                "clicks_change_7d_vs_28d": float,
                "impressions_change_7d_vs_28d": float,
                "url_swaps": [{"from": url, "to": url, "period": str}],
                "direction": "improving" | "stable" | "declining",
            },
            "analysis": str,  # Resumen textual del análisis
        }
    """
    if periods is None:
        periods = [
            {"label": "7d", "days": 7},
            {"label": "28d", "days": 28},
            {"label": "90d", "days": 90},
        ]

    # Cache
    cache_key = f"gsc_trends_{keyword.strip().lower()}"
    if _streamlit_available:
        cached = st.session_state.get(cache_key)
        if cached is not None:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < CACHE_TTL_SECONDS:
                return cached["data"]
            else:
                del st.session_state[cache_key]

    if not is_gsc_api_configured():
        return None

    service = _build_service()
    if not service:
        return None

    property_url = _get_property_url()
    period_data = {}

    try:
        for period in periods:
            label = period["label"]
            days = period["days"]

            end_date = datetime.now() - timedelta(days=3)
            start_date = end_date - timedelta(days=days)

            response = service.searchanalytics().query(
                siteUrl=property_url,
                body={
                    "startDate": start_date.strftime("%Y-%m-%d"),
                    "endDate": end_date.strftime("%Y-%m-%d"),
                    "dimensions": ["query", "page"],
                    "dimensionFilterGroups": [{
                        "filters": [{
                            "dimension": "query",
                            "operator": "contains",
                            "expression": keyword.strip().lower()
                        }]
                    }],
                    "rowLimit": 50,
                    "startRow": 0,
                }
            ).execute()

            rows = response.get("rows", [])

            # Agrupar por URL
            url_metrics: Dict[str, Dict[str, Any]] = {}
            total_clicks = 0
            total_impressions = 0
            weighted_position = 0.0

            for row in rows:
                keys = row.get("keys", [])
                if len(keys) < 2:
                    continue
                query, page = keys[0], keys[1]
                clicks = row.get("clicks", 0)
                impressions = row.get("impressions", 0)
                position = row.get("position", 0)

                total_clicks += clicks
                total_impressions += impressions
                weighted_position += position * impressions

                if page not in url_metrics:
                    url_metrics[page] = {
                        "url": page,
                        "clicks": 0,
                        "impressions": 0,
                        "position_sum": 0.0,
                        "imp_weight": 0,
                        "queries": [],
                    }
                url_metrics[page]["clicks"] += clicks
                url_metrics[page]["impressions"] += impressions
                url_metrics[page]["position_sum"] += position * impressions
                url_metrics[page]["imp_weight"] += impressions
                if query not in url_metrics[page]["queries"]:
                    url_metrics[page]["queries"].append(query)

            # Calcular posición media ponderada por URL
            urls_list = []
            for url_data in sorted(url_metrics.values(), key=lambda x: -x["clicks"]):
                avg_pos = (
                    url_data["position_sum"] / url_data["imp_weight"]
                    if url_data["imp_weight"] > 0 else 0
                )
                urls_list.append({
                    "url": url_data["url"],
                    "clicks": url_data["clicks"],
                    "impressions": url_data["impressions"],
                    "position": round(avg_pos, 1),
                    "ctr": round(
                        url_data["clicks"] / url_data["impressions"], 4
                    ) if url_data["impressions"] > 0 else 0,
                    "queries": url_data["queries"][:5],
                })

            avg_position = (
                weighted_position / total_impressions
                if total_impressions > 0 else 0
            )

            period_data[label] = {
                "position": round(avg_position, 1),
                "clicks": total_clicks,
                "impressions": total_impressions,
                "ctr": round(
                    total_clicks / total_impressions, 4
                ) if total_impressions > 0 else 0,
                "urls": urls_list,
                "top_url": urls_list[0]["url"] if urls_list else "",
            }

        # ── Análisis de tendencias ──
        trends = _analyze_trends(period_data, periods)
        analysis_text = _generate_analysis_text(keyword, period_data, trends)

        result = {
            "keyword": keyword,
            "periods": period_data,
            "trends": trends,
            "analysis": analysis_text,
        }

        # Cachear
        if _streamlit_available:
            st.session_state[cache_key] = {"data": result, "timestamp": datetime.now()}

        return result

    except Exception as e:
        logger.error(f"Error en fetch_keyword_trends para '{keyword}': {e}")
        return None


def _analyze_trends(
    period_data: Dict[str, Any],
    periods: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calcula cambios entre períodos y detecta SWAPs de URL."""
    trends: Dict[str, Any] = {
        "position_change_7d_vs_28d": 0,
        "position_change_28d_vs_90d": 0,
        "clicks_change_7d_vs_28d": 0,
        "impressions_change_7d_vs_28d": 0,
        "url_swaps": [],
        "direction": "stable",
    }

    labels = [p["label"] for p in periods]

    # Comparar pares consecutivos
    if len(labels) >= 2 and labels[0] in period_data and labels[1] in period_data:
        p_short = period_data[labels[0]]
        p_long = period_data[labels[1]]

        if p_long["position"] > 0:
            # Negativo = mejoró (bajó en posición numérica)
            trends["position_change_7d_vs_28d"] = round(
                p_short["position"] - p_long["position"], 1
            )
        if p_long["clicks"] > 0:
            trends["clicks_change_7d_vs_28d"] = round(
                ((p_short["clicks"] - p_long["clicks"]) / p_long["clicks"]) * 100, 1
            )
        if p_long["impressions"] > 0:
            trends["impressions_change_7d_vs_28d"] = round(
                ((p_short["impressions"] - p_long["impressions"]) / p_long["impressions"]) * 100, 1
            )

    if len(labels) >= 3 and labels[1] in period_data and labels[2] in period_data:
        p_mid = period_data[labels[1]]
        p_long = period_data[labels[2]]
        if p_long["position"] > 0:
            trends["position_change_28d_vs_90d"] = round(
                p_mid["position"] - p_long["position"], 1
            )

    # Detectar SWAPs de URL (la URL principal cambia entre períodos)
    for i in range(len(labels) - 1):
        l_current = labels[i]
        l_prev = labels[i + 1]
        if l_current in period_data and l_prev in period_data:
            top_current = period_data[l_current].get("top_url", "")
            top_prev = period_data[l_prev].get("top_url", "")
            if top_current and top_prev and top_current != top_prev:
                trends["url_swaps"].append({
                    "from": top_prev,
                    "to": top_current,
                    "period": f"{l_prev} → {l_current}",
                })

    # Dirección general
    pos_7_28 = trends["position_change_7d_vs_28d"]
    pos_28_90 = trends["position_change_28d_vs_90d"]

    if pos_7_28 < -2 or pos_28_90 < -2:
        trends["direction"] = "improving"
    elif pos_7_28 > 2 or pos_28_90 > 2:
        trends["direction"] = "declining"
    else:
        trends["direction"] = "stable"

    return trends


def _generate_analysis_text(
    keyword: str,
    period_data: Dict[str, Any],
    trends: Dict[str, Any],
) -> str:
    """Genera un texto de análisis en español basado en los datos."""
    lines = []

    # Posición actual
    p7 = period_data.get("7d", {})
    p28 = period_data.get("28d", {})
    p90 = period_data.get("90d", {})

    if p7.get("position"):
        lines.append(
            f"Posición media últimos 7 días: **{p7['position']}** "
            f"({p7['clicks']} clics, {p7['impressions']} impresiones, "
            f"CTR {p7['ctr']*100:.1f}%)"
        )

    # Cambios de posición
    pos_change = trends.get("position_change_7d_vs_28d", 0)
    if pos_change < -1:
        lines.append(f"Mejora de **{abs(pos_change):.1f} posiciones** vs. últimos 28 días")
    elif pos_change > 1:
        lines.append(f"Caída de **{pos_change:.1f} posiciones** vs. últimos 28 días")
    else:
        lines.append("Posición **estable** respecto a los últimos 28 días")

    pos_change_long = trends.get("position_change_28d_vs_90d", 0)
    if abs(pos_change_long) > 1:
        direction = "mejora" if pos_change_long < 0 else "caída"
        lines.append(
            f"Tendencia a 3 meses: {direction} de "
            f"**{abs(pos_change_long):.1f} posiciones** (28d vs 90d)"
        )

    # Cambios de tráfico
    clicks_pct = trends.get("clicks_change_7d_vs_28d", 0)
    if abs(clicks_pct) > 10:
        direction = "subida" if clicks_pct > 0 else "bajada"
        lines.append(f"Clics: {direction} del **{abs(clicks_pct):.0f}%** (7d vs 28d)")

    # SWAPs de URL
    swaps = trends.get("url_swaps", [])
    if swaps:
        lines.append(f"**SWAP detectado:** Google ha cambiado la URL que posiciona:")
        for swap in swaps:
            from_short = swap["from"].replace("https://www.pccomponentes.com", "")
            to_short = swap["to"].replace("https://www.pccomponentes.com", "")
            lines.append(f"  {swap['period']}: `{from_short}` → `{to_short}`")

    # Recomendación según dirección
    direction = trends.get("direction", "stable")
    if direction == "improving":
        lines.append(
            "**Recomendación:** La keyword está mejorando. "
            "Refuerza el contenido existente para consolidar posición."
        )
    elif direction == "declining":
        lines.append(
            "**Recomendación:** La keyword está perdiendo posiciones. "
            "Revisa el contenido, actualiza datos y mejora la experiencia de usuario."
        )
    else:
        if p7.get("position", 0) > 10:
            lines.append(
                "**Recomendación:** Posición estable fuera de top 10. "
                "Optimiza title/meta, añade contenido de valor y mejora enlaces internos para subir."
            )
        else:
            lines.append(
                "**Recomendación:** Posición estable en top 10. "
                "Mantén el contenido actualizado y monitoriza competidores."
            )

    return "\n\n".join(lines)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "__version__",
    
    # Estado
    "is_gsc_api_configured",
    "test_gsc_api_connection",
    
    # Consultas
    "query_search_analytics",
    "quick_keyword_check",
    "fetch_all_keywords",
    "fetch_keyword_trends",
    
    # Funciones principales (compatibles con gsc_utils.py)
    "api_check_cannibalization",
    "api_search_existing_content",
    "api_get_content_coverage_summary",
    
    # Matching y riesgo
    "_calculate_match_score",
    "_calculate_risk_level",
    "_clean_keywords",
    "_normalize_text",
    
    # Constantes
    "DEFAULT_DAYS_BACK",
    "DEFAULT_MIN_IMPRESSIONS",
    "MIN_OVERLAP_RATIO",
    "STOPWORDS_ES",
    "CACHE_TTL_SECONDS",
]
