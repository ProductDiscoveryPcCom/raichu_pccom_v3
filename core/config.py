"""
Configuración de la aplicación.

Carga cascada: st.secrets (Streamlit Cloud) → config.settings → env vars.
Incluye puentes st.secrets → os.environ para módulos downstream.
"""

import os
import logging
from typing import List, Tuple

import streamlit as st

logger = logging.getLogger(__name__)


# ============================================================================
# CARGA DE CONFIGURACIÓN
# ============================================================================

def _load_config():
    """Carga la configuración desde múltiples fuentes."""
    config = {
        'api_key': '',
        'model': 'claude-sonnet-4-20250514',
        'max_tokens': 16000,
        'temperature': 0.7,
        'debug_mode': False,
    }

    # 1. Intentar cargar desde st.secrets (Streamlit Cloud)
    try:
        # Nombres según tu archivo secrets.toml
        # Usamos acceso directo con fallback para compatibilidad
        if 'claude_key' in st.secrets:
            config['api_key'] = st.secrets['claude_key']
        if 'claude_model' in st.secrets:
            config['model'] = st.secrets['claude_model']
        if 'max_tokens' in st.secrets:
            config['max_tokens'] = st.secrets['max_tokens']
        if 'temperature' in st.secrets:
            config['temperature'] = st.secrets['temperature']

        # Debug mode está en [settings]
        if 'settings' in st.secrets and 'debug_mode' in st.secrets.settings:
            config['debug_mode'] = st.secrets.settings['debug_mode']

        if config['api_key']:
            logger.info("Configuración cargada desde st.secrets")
            return config
    except Exception as e:
        logger.debug(f"No se pudo cargar de st.secrets: {e}")

    # 2. Intentar cargar desde config.settings
    try:
        from config.settings import (
            CLAUDE_API_KEY as _settings_api_key,
            CLAUDE_MODEL as _settings_model,
            MAX_TOKENS as _settings_max_tokens,
            TEMPERATURE as _settings_temperature,
            DEBUG_MODE as _settings_debug_mode,
        )
        config['api_key'] = _settings_api_key
        config['model'] = _settings_model
        config['max_tokens'] = _settings_max_tokens
        config['temperature'] = _settings_temperature
        config['debug_mode'] = _settings_debug_mode

        if config['api_key']:
            logger.info("Configuración cargada desde config.settings")
            return config
    except ImportError:
        logger.debug("config.settings no disponible")

    # 3. Fallback a variables de entorno
    config['api_key'] = os.getenv('CLAUDE_API_KEY', os.getenv('ANTHROPIC_API_KEY', ''))
    config['model'] = os.getenv('CLAUDE_MODEL', config['model'])
    config['max_tokens'] = int(os.getenv('MAX_TOKENS', config['max_tokens']))
    config['temperature'] = float(os.getenv('TEMPERATURE', config['temperature']))
    config['debug_mode'] = os.getenv('DEBUG_MODE', 'false').lower() == 'true'

    if config['api_key']:
        logger.info("Configuración cargada desde variables de entorno")
    else:
        logger.warning("No se encontró API key en ninguna fuente")

    return config


# ============================================================================
# INICIALIZACIÓN DE CONFIGURACIÓN (se ejecuta al importar)
# ============================================================================

_config = _load_config()
CLAUDE_API_KEY = _config['api_key']
CLAUDE_MODEL = _config['model']
MAX_TOKENS = _config['max_tokens']
TEMPERATURE = _config['temperature']
DEBUG_MODE = _config['debug_mode']

# Puente st.secrets → os.environ para modelo y parámetros de generación.
# NOTA: ANTHROPIC_API_KEY ya NO se copia al entorno — se inyecta directamente
# vía el parámetro api_key de ContentGenerator (ver F7 en docs/audit-2026-03.md).
if CLAUDE_MODEL:
    os.environ['CLAUDE_MODEL'] = CLAUDE_MODEL
os.environ['MAX_TOKENS'] = str(MAX_TOKENS)
os.environ['TEMPERATURE'] = str(TEMPERATURE)

# OpenAI config (corrección dual)
OPENAI_API_KEY = ""
OPENAI_MODEL = "gpt-4.1-2025-04-14"
try:
    if hasattr(st, 'secrets'):
        OPENAI_API_KEY = st.secrets.get('openai_key', '')
        OPENAI_MODEL = st.secrets.get('openai_model', OPENAI_MODEL)
except Exception:
    pass
if not OPENAI_API_KEY:
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', OPENAI_MODEL)

# Gemini config (generación de imágenes)
GEMINI_API_KEY = ""
try:
    if hasattr(st, 'secrets'):
        GEMINI_API_KEY = st.secrets.get('gemini_key', '')
except Exception:
    pass
if not GEMINI_API_KEY:
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
# Inyectar en entorno para que utils/image_gen.py la encuentre
if GEMINI_API_KEY:
    os.environ['GEMINI_API_KEY'] = GEMINI_API_KEY

# SEMrush: puente st.secrets → os.environ (para config/settings.py y core/semrush.py)
try:
    if hasattr(st, 'secrets') and 'semrush' in st.secrets:
        _semrush_key = st.secrets['semrush'].get('api_key', '')
        _semrush_db = st.secrets['semrush'].get('database', 'es')
        if _semrush_key:
            os.environ['SEMRUSH_API_KEY'] = _semrush_key
            os.environ['SEMRUSH_DATABASE'] = _semrush_db
            os.environ['SEMRUSH_ENABLED'] = 'true'
except Exception:
    pass

# SerpAPI: puente st.secrets → os.environ (para utils/serp_research.py)
try:
    if hasattr(st, 'secrets'):
        # Intentar acceso directo primero (más fiable en Streamlit Cloud)
        _serpapi_key = None
        try:
            _serpapi_key = st.secrets["serpapi_key"]
        except (KeyError, FileNotFoundError):
            pass
        # Fallback a .get()
        if not _serpapi_key:
            try:
                _serpapi_key = st.secrets.get('serpapi_key', '')
            except Exception:
                pass
        if _serpapi_key:
            os.environ['SERPAPI_API_KEY'] = str(_serpapi_key)
            logger.info("SerpAPI key cargada desde st.secrets")
except Exception as e:
    logger.debug(f"SerpAPI key bridge: {e}")


# ============================================================================
# VERIFICACIÓN DE CONFIGURACIÓN
# ============================================================================

def check_configuration(
    _generator_available: bool,
    _new_content_available: bool,
    _openai_client_available: bool,
) -> Tuple[bool, List[str]]:
    """
    Verifica que la configuración sea válida.

    Args:
        _generator_available: Si ContentGenerator se importó correctamente
        _new_content_available: Si prompts.new_content se importó correctamente
        _openai_client_available: Si el cliente OpenAI está disponible

    Returns:
        Tuple (is_valid, list_of_errors)
    """
    errors = []

    if not CLAUDE_API_KEY:
        errors.append(
            "API Key no configurada. Verifica que en tu secrets.toml tengas: "
            "claude_key = \"sk-ant-...\""
        )
    elif not CLAUDE_API_KEY.startswith('sk-ant-'):
        errors.append(
            "API Key tiene formato inválido (debe empezar con 'sk-ant-'). "
            "Verifica el valor en tu secrets.toml o variables de entorno."
        )

    if not _generator_available:
        errors.append("ContentGenerator no está disponible - verifica core/generator.py")

    if not _new_content_available:
        errors.append("Módulo prompts.new_content no está disponible")

    # Log para debug
    if errors:
        logger.error(f"Errores de configuración: {errors}")
        logger.debug(f"CLAUDE_API_KEY presente: {bool(CLAUDE_API_KEY)}")
        logger.debug(f"CLAUDE_MODEL: {CLAUDE_MODEL}")
    else:
        logger.info("Configuración verificada correctamente")

    # Info sobre corrección dual (no es error, solo informativo)
    if _openai_client_available and OPENAI_API_KEY:
        logger.info(f"Corrección dual activa: OpenAI {OPENAI_MODEL}")
    else:
        logger.info("Corrección dual deshabilitada (sin openai_key en secrets)")

    return len(errors) == 0, errors
