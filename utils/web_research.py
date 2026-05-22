# -*- coding: utf-8 -*-
"""
Web Research - PcComponentes Content Generator

Enriquece la generación de contenido con información ACTUAL de la web vía la
búsqueda web de OpenAI (Responses API + herramienta web_search), con FALLBACK
al SERP research existente (SerpAPI/DuckDuckGo) si OpenAI no está disponible o
falla. Nunca depende de Gemini.

Cadena: OpenAI web search → SERP research → (sin enriquecer, graceful).

Las fuentes consultadas se usan SOLO como contexto factual; NO se inyectan como
enlaces externos en el HTML (el contenido usa enlaces internos curados).

Autor: PcComponentes - Product Discovery & Content
"""

import logging
from typing import List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

# Tipos de herramienta de búsqueda web en la Responses API. Se prueban en orden
# para tolerar diferencias entre versiones del SDK/API de OpenAI.
_WEB_SEARCH_TOOL_TYPES = ["web_search_preview", "web_search"]

DEFAULT_OPENAI_MODEL = "gpt-4.1-2025-04-14"


@dataclass
class WebResearchResult:
    """Resultado de la investigación web."""
    success: bool = True
    summary: str = ""
    sources: List[str] = field(default_factory=list)
    model: str = ""
    provider: str = ""   # 'openai_web' | 'serp'
    error: str = ""


# ============================================================================
# CLIENTE OPENAI
# ============================================================================

def _get_openai_client():
    """Cliente OpenAI para Responses API. Mismo patrón de key que el resto:
    core.config (inyección directa) → st.secrets (fallback local).
    Returns: (client|None, error_str)."""
    try:
        from openai import OpenAI
    except ImportError:
        return None, "openai SDK no instalado"
    api_key = ""
    try:
        from core.config import OPENAI_API_KEY
        api_key = OPENAI_API_KEY
    except ImportError:
        pass
    if not api_key:
        try:
            import streamlit as st
            api_key = st.secrets.get('openai_key', '') or st.secrets.get('OPENAI_API_KEY', '')
        except Exception:
            pass
    if not api_key:
        return None, "OPENAI_API_KEY no configurada"
    return OpenAI(api_key=api_key), ""


def _get_openai_model() -> str:
    try:
        from core.config import OPENAI_MODEL
        return OPENAI_MODEL or DEFAULT_OPENAI_MODEL
    except ImportError:
        return DEFAULT_OPENAI_MODEL


def is_web_research_available() -> Tuple[bool, str]:
    """True si la búsqueda web de OpenAI está disponible (SDK + key + Responses API)."""
    client, error = _get_openai_client()
    if not client:
        return False, error
    if not hasattr(client, 'responses'):
        return False, "Responses API no disponible en este SDK de OpenAI"
    return True, ""


# ============================================================================
# BÚSQUEDA WEB CON OPENAI
# ============================================================================

def _build_research_prompt(keyword: str) -> str:
    """Prompt de investigación factual y actual sobre la keyword."""
    return (
        f"Investiga en la web información ACTUAL y verificable sobre: \"{keyword}\".\n\n"
        "Para una guía de compra/contenido SEO de PcComponentes (España), resume en "
        "español los datos objetivos más relevantes y recientes:\n"
        "- Modelos/productos actuales y sus especificaciones clave\n"
        "- Novedades, lanzamientos o cambios recientes (con año)\n"
        "- Rangos de precio orientativos en España si los hay\n"
        "- Datos técnicos comparables (no opiniones de marketing)\n\n"
        "Sé conciso y factual (máx ~400 palabras). No inventes datos: si algo no "
        "está confirmado, omítelo. No incluyas conclusiones promocionales."
    )


def _extract_sources(resp: Any) -> List[str]:
    """Extrae URLs de las citas (url_citation) de la respuesta de la Responses API."""
    sources: List[str] = []
    try:
        for item in getattr(resp, 'output', None) or []:
            for content in getattr(item, 'content', None) or []:
                for ann in getattr(content, 'annotations', None) or []:
                    url = getattr(ann, 'url', None)
                    if url and url not in sources:
                        sources.append(url)
    except Exception:
        pass
    return sources[:10]


def research_with_openai(
    keyword: str,
    model: Optional[str] = None,
    client: Optional[Any] = None,
) -> WebResearchResult:
    """Investiga la keyword con la búsqueda web de OpenAI (Responses API).

    Prueba los tipos de herramienta de _WEB_SEARCH_TOOL_TYPES en orden para
    tolerar variaciones de versión. No propaga excepciones.
    """
    if client is None:
        client, error = _get_openai_client()
        if not client:
            return WebResearchResult(success=False, error=error, provider='openai_web')
    if not hasattr(client, 'responses'):
        return WebResearchResult(
            success=False, error="Responses API no disponible", provider='openai_web'
        )

    model = model or _get_openai_model()
    prompt = _build_research_prompt(keyword)
    last_error = ""

    for tool_type in _WEB_SEARCH_TOOL_TYPES:
        try:
            resp = client.responses.create(
                model=model,
                tools=[{"type": tool_type}],
                input=prompt,
            )
            summary = (getattr(resp, 'output_text', '') or '').strip()
            if not summary:
                last_error = "Respuesta vacía de OpenAI web search"
                continue
            return WebResearchResult(
                success=True,
                summary=summary,
                sources=_extract_sources(resp),
                model=getattr(resp, 'model', model) or model,
                provider='openai_web',
            )
        except Exception as e:  # noqa: BLE001 — probar siguiente variante / fallback
            last_error = str(e)
            logger.warning(f"OpenAI web search ({tool_type}) falló: {last_error}")
            continue

    return WebResearchResult(success=False, error=last_error or "desconocido", provider='openai_web')


# ============================================================================
# FORMATO PARA EL PROMPT
# ============================================================================

def format_for_prompt(result: WebResearchResult) -> str:
    """Bloque de contexto factual para inyectar en Stage 1.

    Las fuentes se listan SOLO como referencia de respaldo; el prompt deja claro
    que NO deben citarse como enlaces externos en el HTML.
    """
    if not result or not result.success or not result.summary:
        return ""

    parts = [
        "## INVESTIGACIÓN WEB ACTUALIZADA",
        "Datos actuales obtenidos de la web. Úsalos como CONTEXTO FACTUAL para que "
        "el contenido sea preciso y actual.",
        "",
        result.summary.strip(),
    ]
    if result.sources:
        parts.append("")
        parts.append(
            "Fuentes de respaldo (solo contexto — NO las cites ni las añadas como "
            "enlaces externos en el HTML): " + ", ".join(result.sources)
        )
    return "\n".join(parts)


# ============================================================================
# CADENA CON FALLBACK: OpenAI web search → SERP research
# ============================================================================

def to_prompt_context(result: WebResearchResult) -> str:
    """Devuelve el bloque de contexto listo para Stage 1 para cualquier proveedor.

    - openai_web: formatea el resumen con format_for_prompt.
    - serp: el summary ya viene formateado por utils.serp_research.format_for_prompt.
    """
    if not result or not result.success:
        return ""
    if result.provider == 'serp':
        return result.summary or ""
    return format_for_prompt(result)


def research_enriched(keyword: str) -> WebResearchResult:
    """Cadena de investigación: OpenAI web search (primario) → SERP (fallback).

    Devuelve siempre un WebResearchResult normalizado. Si ambos fallan,
    success=False (el caller continúa sin enriquecer, graceful).
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return WebResearchResult(success=False, error="keyword vacía")

    # 1) OpenAI web search (primario)
    available, avail_err = is_web_research_available()
    if available:
        wr = research_with_openai(keyword)
        if wr.success and wr.summary:
            return wr
        logger.info(f"OpenAI web search no usable ({wr.error}); probando fallback SERP")
    else:
        logger.info(f"OpenAI web search no disponible ({avail_err}); usando fallback SERP")

    # 2) Fallback: SERP research existente
    try:
        from utils.serp_research import research_serp, format_for_prompt as _serp_format
        sr = research_serp(keyword)
        if getattr(sr, 'success', False):
            return WebResearchResult(
                success=True,
                summary=_serp_format(sr),
                sources=[],
                model="serp",
                provider='serp',
            )
        return WebResearchResult(success=False, error=getattr(sr, 'error', 'SERP sin resultados'), provider='serp')
    except ImportError:
        return WebResearchResult(success=False, error="serp_research no disponible", provider='serp')
    except Exception as e:  # noqa: BLE001
        logger.warning(f"Fallback SERP falló: {e}")
        return WebResearchResult(success=False, error=str(e), provider='serp')


__all__ = [
    '__version__',
    'WebResearchResult',
    'is_web_research_available',
    'research_with_openai',
    'research_enriched',
    'format_for_prompt',
    'to_prompt_context',
]
