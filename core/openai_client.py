# -*- coding: utf-8 -*-
"""
OpenAI Client - PcComponentes Content Generator
Versión 1.0.0 - 2026-02-11

Cliente de OpenAI para corrección dual en la etapa 2 del pipeline.
Claude genera el borrador (etapa 1), OpenAI + Claude analizan (etapa 2),
Claude genera la versión final con feedback combinado (etapa 3).

Configuración en secrets.toml:
    openai_key = "sk-..."
    openai_model = "gpt-4.1-2025-04-14"  # opcional, default: gpt-4.1

Modelos soportados:
    - gpt-4.1-2025-04-14: Mejor para análisis estructurado y seguimiento de instrucciones
    - gpt-4o-2024-11-20: Alternativa multimodal rápida
    - gpt-4o-mini-2024-07-18: Opción económica para análisis ligeros

Autor: PcComponentes - Product Discovery & Content
"""

import time
import json
import re
import logging
from typing import Dict, Optional, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__version__ = "1.0.0"


# ============================================================================
# IMPORTS
# ============================================================================

try:
    from openai import OpenAI, APIError, RateLimitError, APIConnectionError
    _openai_available = True
except ImportError:
    _openai_available = False
    logger.info("OpenAI SDK no instalado. Corrección dual deshabilitada.")


# ============================================================================
# CONSTANTES
# ============================================================================

DEFAULT_MODEL = "gpt-4.1-2025-04-14"

AVAILABLE_MODELS = {
    "gpt-4.1-2025-04-14": "GPT-4.1",
    "gpt-4o-2024-11-20": "GPT-4o",
    "gpt-4o-mini-2024-07-18": "GPT-4o Mini",
}

DEFAULT_MAX_TOKENS = 8000
DEFAULT_TEMPERATURE = 0.4  # Más bajo que Claude: queremos análisis preciso
MAX_RETRIES = 2
RETRY_DELAY = 2.0


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class OpenAIResponse:
    """Respuesta parseada de la API de OpenAI."""
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    finish_reason: str


# ============================================================================
# CLIENTE (SINGLETON)
# ============================================================================

_client: Optional[Any] = None
_api_key: Optional[str] = None


def configure(api_key: str) -> None:
    """Configura la API key de OpenAI."""
    global _api_key, _client
    _api_key = api_key
    _client = None  # Forzar recreación


def get_client() -> Any:
    """Obtiene el cliente de OpenAI (singleton)."""
    global _client

    if not _openai_available:
        raise ImportError(
            "El módulo 'openai' no está instalado. "
            "Instálalo con: pip install openai"
        )

    if _client is None:
        if not _api_key:
            raise ValueError("OpenAI API key no configurada")
        _client = OpenAI(api_key=_api_key)
        logger.info("Cliente de OpenAI inicializado")

    return _client


def is_available() -> bool:
    """Verifica si OpenAI está disponible y configurado."""
    return _openai_available and bool(_api_key)


# ============================================================================
# LLAMADA A LA API
# ============================================================================

def call_openai_api(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    system_prompt: Optional[str] = None,
) -> OpenAIResponse:
    """
    Llama a la API de OpenAI con reintentos.

    Args:
        prompt: Prompt del usuario
        model: Modelo a usar
        max_tokens: Máximo de tokens de salida
        temperature: Temperatura de generación
        system_prompt: System prompt opcional

    Returns:
        OpenAIResponse con el contenido generado

    Raises:
        ValueError: Si no está configurado
        Exception: Si se agotan los reintentos
    """
    client = get_client()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            logger.info(
                f"Llamando a OpenAI API ({model}, intento {attempt + 1}/{MAX_RETRIES})"
            )

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            choice = response.choices[0]
            usage = response.usage

            return OpenAIResponse(
                content=choice.message.content or "",
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
                model=response.model,
                finish_reason=choice.finish_reason or "unknown",
            )

        except RateLimitError as e:
            last_error = e
            wait = RETRY_DELAY * (attempt + 1)
            logger.warning(f"OpenAI rate limit, esperando {wait}s...")
            time.sleep(wait)

        except APIConnectionError as e:
            last_error = e
            logger.warning(f"OpenAI connection error: {e}")
            time.sleep(RETRY_DELAY)

        except APIError as e:
            last_error = e
            if hasattr(e, 'status_code') and e.status_code >= 500:
                logger.warning(f"OpenAI server error ({e.status_code}), reintentando...")
                time.sleep(RETRY_DELAY)
            else:
                raise

        except Exception as e:
            raise RuntimeError(f"Error inesperado en OpenAI: {str(e)}") from e

    raise RuntimeError(
        f"OpenAI: se agotaron los {MAX_RETRIES} reintentos. "
        f"Último error: {last_error}"
    )


# ============================================================================
# ANÁLISIS DUAL (ETAPA 2)
# ============================================================================

def generate_dual_analysis(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Genera el análisis de OpenAI para la etapa 2 de corrección dual.

    Args:
        prompt: El mismo prompt de análisis que se envía a Claude
        model: Modelo de OpenAI a usar
        max_tokens: Máximo de tokens
        temperature: Temperatura

    Returns:
        Tuple[success, analysis_content, metadata]
    """
    if not is_available():
        return False, "", {"error": "OpenAI no disponible"}

    try:
        start_time = time.time()

        system = (
            "Eres un editor SEO experto. Analiza el contenido de forma rigurosa "
            "y responde ÚNICAMENTE con el JSON solicitado. "
            "Sé especialmente crítico con: frases genéricas de IA, "
            "estructura HTML incorrecta, y falta de personalidad en el tono."
        )

        response = call_openai_api(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system,
        )

        elapsed = time.time() - start_time

        metadata = {
            "model": response.model,
            "tokens": response.total_tokens,
            "time": round(elapsed, 2),
            "provider": "openai",
        }

        logger.info(
            f"OpenAI análisis completado: {response.total_tokens} tokens, "
            f"{elapsed:.1f}s"
        )

        return True, response.content, metadata

    except Exception as e:
        logger.error(f"Error en análisis OpenAI: {e}")
        return False, "", {"error": str(e)}


def merge_dual_analyses(
    claude_analysis: str,
    openai_analysis: str,
) -> str:
    """
    Fusiona los análisis de Claude y OpenAI en un solo feedback para la etapa 3.

    Intenta parsear ambos como JSON y combinar los problemas detectados.
    Si el parsing falla, concatena como texto.

    Args:
        claude_analysis: Análisis de Claude (etapa 2)
        openai_analysis: Análisis de OpenAI (etapa 2)

    Returns:
        Feedback combinado para la etapa 3
    """
    claude_json = _try_parse_json(claude_analysis)
    openai_json = _try_parse_json(openai_analysis)

    # Si ambos son JSON, fusionar inteligentemente
    if claude_json and openai_json:
        return _merge_json_analyses(claude_json, openai_json)

    # Fallback: concatenar como texto
    return (
        "# ANÁLISIS DE CLAUDE\n\n"
        f"{claude_analysis}\n\n"
        "---\n\n"
        "# ANÁLISIS DE OPENAI (corrección dual)\n\n"
        f"{openai_analysis}"
    )


def _try_parse_json(text: str) -> Optional[Dict]:
    """Intenta parsear JSON de un texto, limpiando bloques de código."""
    if not text:
        return None

    # Limpiar bloques de código markdown
    cleaned = re.sub(r'```(?:json)?\s*', '', text)
    cleaned = re.sub(r'```\s*$', '', cleaned.strip())

    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


def _merge_json_analyses(claude: Dict, openai: Dict) -> str:
    """Fusiona dos análisis JSON en un feedback combinado."""

    # Combinar problemas de ambos (sin duplicados)
    claude_problems = claude.get('problemas', [])
    openai_problems = openai.get('problemas', [])

    # Deduplicar por descripción similar
    seen = set()
    merged_problems = []
    for p in claude_problems + openai_problems:
        desc = p.get('descripcion', '')[:50].lower()
        if desc not in seen:
            seen.add(desc)
            merged_problems.append(p)

    # Tomar el peor score (defensivo: puntuacion_general puede ser dict o número)
    claude_score = claude.get('puntuacion_general', 0)
    openai_score = openai.get('puntuacion_general', 0)
    if isinstance(claude_score, dict):
        claude_score = claude_score.get('general', claude_score.get('total', 0))
    if isinstance(openai_score, dict):
        openai_score = openai_score.get('general', openai_score.get('total', 0))
    claude_score = claude_score if isinstance(claude_score, (int, float)) else 0
    openai_score = openai_score if isinstance(openai_score, (int, float)) else 0
    min_score = min(claude_score, openai_score) if claude_score and openai_score else claude_score or openai_score

    # Combinar frases de IA detectadas
    claude_ai = claude.get('tono', {}).get('frases_ia_detectadas', [])
    openai_ai = openai.get('tono', {}).get('frases_ia_detectadas', [])
    all_ai_phrases = list(set(claude_ai + openai_ai))

    # Combinar enlaces faltantes
    claude_missing = claude.get('enlaces', {}).get('faltantes', [])
    openai_missing = openai.get('enlaces', {}).get('faltantes', [])
    all_missing = list(set(claude_missing + openai_missing))

    # Construir análisis fusionado
    merged = dict(claude)  # Base de Claude
    merged['problemas'] = merged_problems
    merged['puntuacion_general'] = min_score
    merged['correccion_dual'] = True
    merged['modelos_usados'] = ['claude', 'openai']

    if all_ai_phrases:
        if 'tono' not in merged:
            merged['tono'] = {}
        merged['tono']['frases_ia_detectadas'] = all_ai_phrases

    if all_missing:
        if 'enlaces' not in merged:
            merged['enlaces'] = {}
        merged['enlaces']['faltantes'] = all_missing

    # Añadir aspectos positivos de ambos (defensivo: pueden ser dicts no hashables)
    claude_positives = claude.get('aspectos_positivos', [])
    openai_positives = openai.get('aspectos_positivos', [])
    seen_positives = []
    for p in claude_positives + openai_positives:
        if p not in seen_positives:
            seen_positives.append(p)
    merged['aspectos_positivos'] = seen_positives

    # Recomendación combinada
    claude_rec = claude.get('recomendacion_principal', '')
    openai_rec = openai.get('recomendacion_principal', '')
    if openai_rec and openai_rec != claude_rec:
        merged['recomendacion_principal'] = (
            f"{claude_rec} | Corrección dual: {openai_rec}"
        )

    return json.dumps(merged, ensure_ascii=False, indent=2)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'configure',
    'is_available',
    'get_client',
    'call_openai_api',
    'generate_dual_analysis',
    'merge_dual_analyses',
    'OpenAIResponse',
    'AVAILABLE_MODELS',
    'DEFAULT_MODEL',
]
