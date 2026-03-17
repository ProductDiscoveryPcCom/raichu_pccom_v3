"""
PcComponentes Content Generator - App Principal
Versión 1.2.0

Aplicación Streamlit para generación de contenido SEO.
Flujo de 3 etapas: Borrador → Análisis → Final

CAMBIOS v4.9.2:
- FIX: Import de count_words_in_html separado de extract_html_content (html_utils no exporta extract_html_content)
- FIX: extract_html_content ahora se importa de core.generator con fallback local
- FIX: Modo rewrite stages 1, 2 y 3 ahora pasan config dict correctamente (antes pasaban kwargs sueltos que no coincidían con la firma de las funciones)
- FIX: rewrite_config se construye una sola vez antes de las 3 etapas para garantizar consistencia

CAMBIOS v4.9.1:
- FIX: Enlaces de canibalización ahora son hipervínculos completos clickeables
- Compatibilidad con new_content.py v4.9.2

CAMBIOS v4.9.0:
- Nuevo parámetro pdp_json_data en build_new_content_prompt_stage1()
- Integración completa de JSON de productos (principal, enlaces PDP, alternativo)
- Los datos JSON ahora enriquecen los prompts con ventajas/desventajas/opiniones
- Compatibilidad total con new_content.py v4.9.0

CORRECCIONES PREVIAS v4.5.0:
- Nombres de funciones correctos (build_new_content_prompt_stage1, etc.)
- Parámetros correctos (secondary_keywords, guiding_context, links_data)
- GenerationResult.content en lugar de asignar GenerationResult a str
- Análisis competitivo inline (build_competitor_analysis_prompt no existe)
- Validaciones de entrada en execute_generation_pipeline()
- Safe access a config['keyword'] en modo rewrite

Autor: PcComponentes - Product Discovery & Content
"""

import streamlit as st
import time
import os
import re
import hmac
import html
import hashlib
import logging
import traceback
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# VERSIÓN
# ============================================================================

try:
    from version import __version__
except ImportError:
    __version__ = "5.1.0"
APP_TITLE = "PcComponentes Content Generator"

# ============================================================================
# IMPORTS CON MANEJO DE ERRORES
# ============================================================================

# Configuración - Primero st.secrets (Streamlit Cloud), luego config.settings, luego env vars
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
            CLAUDE_API_KEY,
            CLAUDE_MODEL,
            MAX_TOKENS,
            TEMPERATURE,
            DEBUG_MODE,
        )
        config['api_key'] = CLAUDE_API_KEY
        config['model'] = CLAUDE_MODEL
        config['max_tokens'] = MAX_TOKENS
        config['temperature'] = TEMPERATURE
        config['debug_mode'] = DEBUG_MODE
        
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

# Cargar configuración
_config = _load_config()
CLAUDE_API_KEY = _config['api_key']
CLAUDE_MODEL = _config['model']
MAX_TOKENS = _config['max_tokens']
TEMPERATURE = _config['temperature']
DEBUG_MODE = _config['debug_mode']

# Puente st.secrets → os.environ para que core/generator.py y config/settings.py
# encuentren los valores (importan desde os.getenv, no desde st.secrets)
if CLAUDE_API_KEY:
    os.environ['ANTHROPIC_API_KEY'] = CLAUDE_API_KEY
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

# Arquetipos
try:
    from config.arquetipos import get_arquetipo, get_arquetipo_names, ARQUETIPOS
except ImportError:
    logger.warning("No se pudo importar arquetipos")
    ARQUETIPOS = {}
    def get_arquetipo(code):
        return {'code': code, 'name': 'Default', 'tone': 'informativo'}
    def get_arquetipo_names():
        return []

# Generador de contenido
try:
    from core.generator import ContentGenerator, GenerationResult
    _generator_available = True
except ImportError as e:
    logger.error(f"No se pudo importar ContentGenerator: {e}")
    ContentGenerator = None
    GenerationResult = None
    _generator_available = False

# Prompts - new_content
try:
    from prompts import new_content
    _new_content_available = True
except ImportError as e:
    logger.error(f"No se pudo importar prompts.new_content: {e}")
    new_content = None
    _new_content_available = False

# Prompts - rewrite
try:
    from prompts import rewrite
    _rewrite_available = True
except ImportError as e:
    logger.error(f"No se pudo importar prompts.rewrite: {e}")
    rewrite = None
    _rewrite_available = False

# Brand tone (system prompt base) — fuente única: prompts.brand_tone
try:
    from prompts.brand_tone import get_system_prompt_base
    _brand_tone_available = True
except ImportError:
    try:
        from brand_tone import get_system_prompt_base
        _brand_tone_available = True
    except ImportError:
        _brand_tone_available = False
        def get_system_prompt_base():
            return None

# UI Components
try:
    from ui.inputs import render_content_inputs
    _inputs_available = True
except ImportError:
    logger.warning("No se pudo importar ui.inputs")
    _inputs_available = False
    render_content_inputs = None

try:
    from ui.rewrite import render_rewrite_section
    _rewrite_ui_available = True
except ImportError:
    logger.warning("No se pudo importar ui.rewrite")
    _rewrite_ui_available = False
    render_rewrite_section = None

try:
    from ui.results import render_results_section
    _results_available = True
except ImportError:
    logger.warning("No se pudo importar ui.results")
    _results_available = False
    render_results_section = None

try:
    from ui.sidebar import render_sidebar
    _sidebar_available = True
except ImportError:
    logger.warning("No se pudo importar ui.sidebar")
    _sidebar_available = False
    render_sidebar = None

try:
    from ui.assistant import (
        initialize_chat_state,
        render_chat_messages,
        build_messages_for_api,
        get_system_prompt,
        detect_and_execute_commands,
        detect_product_json_in_message,
        parse_generation_params,
    )
    _assistant_available = True
except ImportError:
    logger.warning("No se pudo importar ui.assistant")
    _assistant_available = False

# OpenAI para corrección dual
try:
    from core import openai_client
    _openai_client_available = True
except ImportError:
    try:
        import openai_client
        _openai_client_available = True
    except ImportError:
        _openai_client_available = False
        logger.info("Módulo openai_client no disponible. Corrección dual deshabilitada.")

# Utilidades HTML
try:
    from utils.html_utils import count_words_in_html
except ImportError:
    def count_words_in_html(html: str) -> int:
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        return len(text.split())

# extract_html_content: usar la de core.generator si está disponible, sino fallback local
try:
    from core.generator import extract_html_content
except ImportError:
    def extract_html_content(content: str) -> str:
        """Fallback: Extrae HTML limpio eliminando marcadores markdown."""
        import re
        if not content:
            return ""
        content = content.strip()
        # Eliminar ```html al inicio
        content = re.sub(r'^```html\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'^```\s*\n?', '', content)
        # Eliminar ``` al final
        content = re.sub(r'\n?```\s*$', '', content)
        content = content.strip()
        # Verificar que empieza con <
        if not content.startswith('<'):
            first_tag = content.find('<')
            if first_tag > 0:
                content = content[first_tag:]
        return content.strip()


# ============================================================================
# INICIALIZACIÓN
# ============================================================================

def initialize_app() -> None:
    """Inicializa el estado de la aplicación."""
    
    if 'initialized' not in st.session_state:
        st.session_state.initialized = True
        st.session_state.mode = 'new'
        st.session_state.generation_in_progress = False
        st.session_state.current_stage = 0
        st.session_state.draft_html = None
        st.session_state.analysis_json = None
        st.session_state.final_html = None
        st.session_state.rewrite_analysis = None
        st.session_state.content_history = []
        st.session_state.last_config = None
        st.session_state.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Configurar OpenAI para corrección dual
        if _openai_client_available and OPENAI_API_KEY:
            openai_client.configure(OPENAI_API_KEY)
            logger.info(f"OpenAI configurado para corrección dual (modelo: {OPENAI_MODEL})")
        
        logger.info("Aplicación inicializada")


def check_configuration() -> Tuple[bool, List[str]]:
    """
    Verifica que la configuración sea válida.
    
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


# ============================================================================
# HEADER Y NAVEGACIÓN
# ============================================================================

def render_app_header() -> str:
    """
    Renderiza el header de la aplicación.
    
    Returns:
        Modo seleccionado ('new', 'rewrite', 'verify' o 'assistant')
    """
    st.title(f"🚀 {APP_TITLE}")
    st.caption(f"Versión {__version__} | Generación de contenido SEO en 3 etapas")
    
    st.markdown("---")
    
    # Selector de modo + botón limpiar en una fila compacta
    col_mode, col_clear = st.columns([5, 1])

    with col_mode:
        mode = st.radio(
            "Modo",
            options=['new', 'rewrite', 'verify', 'opportunities', 'assistant'],
            format_func=lambda x: {
                'new': '📝 Nuevo',
                'rewrite': '🔄 Reescritura Competitiva',
                'verify': '🔍 Verificar',
                'opportunities': '📊 Oportunidades',
                'assistant': '💬 Asistente',
            }.get(x, x),
            horizontal=True,
            key='mode_selector_main',
            label_visibility="collapsed"
        )

    with col_clear:
        if st.button("🗑️ Limpiar", use_container_width=True, key="btn_clear_all"):
            st.session_state['_confirm_clear'] = True
            st.rerun()

    if st.session_state.get('_confirm_clear'):
        st.warning("⚠️ ¿Seguro que quieres limpiar todos los datos? Se perderá el contenido generado.")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("✅ Sí, limpiar todo", type="primary", key="btn_confirm_clear"):
                st.session_state.pop('_confirm_clear', None)
                clear_session_state()
                st.rerun()
        with col_no:
            if st.button("❌ Cancelar", key="btn_cancel_clear"):
                st.session_state.pop('_confirm_clear', None)
                st.rerun()
    
    # Detectar cambio de modo y aislar estados entre modos
    previous_mode = st.session_state.get('mode', '')
    if previous_mode and previous_mode != mode:
        # Reset generation flag (puede quedarse stuck si el modo anterior falló)
        st.session_state.generation_in_progress = False
        st.session_state.current_stage = 0
        
        # Guardar resultados del modo anterior (para restaurar si vuelve)
        _save_mode_results(previous_mode)
        
        # Restaurar resultados del nuevo modo (si existían)
        _restore_mode_results(mode)
    
    st.session_state.mode = mode
    return mode


# Keys de resultados de generación que se aíslan por modo
_MODE_RESULT_KEYS = [
    'draft_html', 'analysis_json', 'final_html',
    'rewrite_analysis', 'content_history', 'generation_metadata',
    'last_config', 'timestamp',
]


def _save_mode_results(mode: str) -> None:
    """Guarda los resultados de generación del modo actual en un namespace aislado."""
    saved = {}
    for key in _MODE_RESULT_KEYS:
        if key in st.session_state:
            saved[key] = st.session_state[key]
    
    # Guardar también keys dinámicas de traducción (translated_html_fr, etc.)
    for key in list(st.session_state.keys()):
        if key.startswith('translated_html_'):
            saved[key] = st.session_state[key]
    
    st.session_state[f'_saved_results_{mode}'] = saved
    
    # Limpiar las keys globales para que el nuevo modo empiece limpio
    for key in _MODE_RESULT_KEYS:
        if key in st.session_state:
            del st.session_state[key]
    for key in list(st.session_state.keys()):
        if key.startswith('translated_html_'):
            del st.session_state[key]


def _restore_mode_results(mode: str) -> None:
    """Restaura los resultados guardados de un modo (si existen)."""
    saved = st.session_state.get(f'_saved_results_{mode}', {})
    for key, value in saved.items():
        st.session_state[key] = value


def clear_session_state() -> None:
    """
    Limpia el estado de la sesión - resetea todos los campos del formulario.
    
    Limpia:
    - Resultados de generación (draft, análisis, final)
    - Campos de reescritura (competidores, HTML, enlaces)
    - Datos del formulario de nuevo contenido
    - Estado de búsquedas (SEMrush, GSC)
    - Valores de widgets (inputs de texto, selectores, etc.)
    
    NO limpia:
    - mode (mantiene el modo actual)
    - initialized (estado de inicialización)
    - mode_selector_main (selector de modo)
    """
    
    # --- Resultados de generación ---
    generation_keys = [
        'draft_html',
        'analysis_json', 
        'final_html',
        'rewrite_analysis',
        'generation_in_progress',
        'current_stage',
        'content_history',
        'last_config',
        'generation_metadata',
        'verify_result',
        # Refinamiento
        'refine_prompt_input',
        # Asistente
        'assistant_messages',
        'assistant_generation_pending',
    ]
    
    # --- Campos de reescritura ---
    rewrite_keys = [
        'html_to_rewrite',
        'last_rewrite_keyword',
        'manual_urls_input',
        'rewrite_competitors_data',
        'rewrite_gsc_analysis',
        'rewrite_links',
        'semrush_response',
        'show_manual_fallback',
        # Widgets de reescritura
        'html_rewrite_input',
        'rewrite_keyword_input',
    ]
    
    # --- Datos del formulario de nuevo contenido ---
    form_keys = [
        'form_data',
        # Widgets principales de inputs
        'main_keyword',
        'main_arquetipo', 
        'main_pdp_url',
        'main_length',
        'main_competitors',
        'main_instructions',
    ]
    
    # Combinar todas las keys a limpiar
    all_keys_to_clear = generation_keys + rewrite_keys + form_keys
    
    # Limpiar cada key
    for key in all_keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    
    # Limpiar keys dinámicas de enlaces y otros widgets dinámicos
    # Importante: convertir a lista para evitar "dictionary changed size during iteration"
    keys_to_delete = []
    for key in list(st.session_state.keys()):
        # NO borrar el selector de modo
        if key == 'mode_selector_main' or key == 'mode' or key == 'initialized':
            continue
            
        # Enlaces de inputs_FINAL.py (main_internal_url_X, main_pdp_anchor_X, etc.)
        # Enlaces de rewrite_FINAL.py (rewrite_link_url_X, rewrite_link_text_X)
        # Preguntas guía del briefing (main_guiding_X)
        # Producto alternativo (main_alt_url, main_alt_name)
        # Previews de competidores (preview_comp_X)
        # Contadores de enlaces (X_link_count)
        if any(pattern in key for pattern in [
            # Patrones de enlaces
            '_url_', '_anchor_', '_link_', '_del_', '_add',
            'link_url', 'link_anchor', 'link_text',
            'rewrite_link_url_', 'rewrite_link_text_', 'remove_rewrite_link_',
            # Patrones de briefing/guiding
            '_guiding_', 'guiding_',
            # Patrones de producto alternativo  
            '_alt_url', '_alt_name',
            # Patrones de competidores y previews
            'preview_comp_', 'competitor_',
            # Contadores
            '_link_count', '_count',
            # Resultados guardados por modo
            '_saved_results_',
        ]):
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        if key in st.session_state:
            del st.session_state[key]
    
    # Resetear timestamp
    st.session_state.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    logger.info(f"Estado de sesión limpiado: {len(all_keys_to_clear) + len(keys_to_delete)} keys eliminadas")


# ============================================================================
# MODOS DE GENERACIÓN
# ============================================================================

def render_new_content_mode() -> None:
    """Renderiza el modo de nuevo contenido."""
    
    if not _inputs_available or render_content_inputs is None:
        st.error("❌ El módulo de inputs no está disponible")
        return
    
    # Manual de uso — solo visible si el usuario no ha generado antes
    if not st.session_state.get('_has_generated_new'):
        _render_usage_guide()

    # Renderizar inputs y obtener configuración
    is_valid, config = render_content_inputs()
    
    if not is_valid:
        return
    
    # Botón de generación
    st.markdown("---")

    col_serp, col_btn = st.columns([2, 3])

    with col_serp:
        serp_enabled = st.checkbox(
            "🔍 Investigar SERPs",
            value=True,
            help="Analiza la competencia en Google antes de generar. "
                 "Mejora la calidad (~5-8s extra).",
            key="cb_serp_research_new",
        )
        config['serp_research'] = serp_enabled

    with col_btn:
        generate_clicked = st.button(
            "🚀 Generar Contenido",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get('generation_in_progress', False),
            key="btn_generate_new"
        )

    if generate_clicked:
        execute_generation_pipeline(config, mode='new')


def _render_usage_guide() -> None:
    """Renderiza guía de uso rápida para nuevos usuarios."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**Raichu genera artículos SEO en 3 etapas automáticas:** borrador → análisis → versión final.

**Para empezar solo necesitas 2 campos:**

| Paso | Campo | Ejemplo |
|------|-------|---------|
| **1** | **Keyword** — el término SEO objetivo | `mejores portátiles gaming 2025` |
| **2** | **Arquetipo** — el tipo de artículo | `ARQ-1: Guía de compra` |

**Campos opcionales que mejoran el resultado:**

| Campo | Para qué sirve |
|-------|----------------|
| **URL del producto** | Raichu extrae specs reales del PDP y las integra en el artículo |
| **Longitud** | Ajusta la extensión del artículo al arquetipo (por defecto ya optimizado) |
| **Briefing** | Preguntas contextuales que guían el enfoque del contenido |
| **Enlaces internos** | Links a categorías o artículos relacionados para SEO interno |
| **Enlaces PDP** | Productos a enlazar dentro del artículo con datos JSON enriquecidos |
| **Producto alternativo** | Alternativa a recomendar si el producto principal no encaja |
| **Elementos visuales** | Tablas comparativas, tarjetas de producto, cajas destacadas |
| **Instrucciones adicionales** | Cualquier indicación extra para el generador |
        """)
        
        st.info(
            "💡 **Consejo**: Empieza solo con keyword + arquetipo. "
            "Puedes refinar el resultado después con el panel de refinamiento."
        )


def render_rewrite_mode() -> None:
    """Renderiza el modo de reescritura competitiva."""
    
    if not _rewrite_ui_available or render_rewrite_section is None:
        st.error("❌ El módulo de reescritura no está disponible")
        return
    
    if not _rewrite_available:
        st.error("❌ El módulo prompts.rewrite no está disponible")
        return
    
    # Guía de uso — solo visible si el usuario no ha generado reescritura antes
    if not st.session_state.get('_has_generated_rewrite'):
        _render_rewrite_guide()

    # Renderizar sección de reescritura
    is_valid, config = render_rewrite_section()
    
    if not is_valid:
        return
    
    # Botón de generación
    st.markdown("---")

    generate_clicked = st.button(
        "🚀 Generar Reescritura",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get('generation_in_progress', False),
        key="btn_generate_rewrite"
    )

    if generate_clicked:
        execute_generation_pipeline(config, mode='rewrite')


def _render_rewrite_guide() -> None:
    """Guía de uso para el modo reescritura competitiva."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**Reescritura Competitiva analiza tu contenido actual y el de competidores para generar una versión superior.**

**El proceso sigue 8 pasos guiados:**

| Paso | Qué haces | Obligatorio |
|------|-----------|:-----------:|
| **1. Keyword** | Define el término SEO objetivo | ✅ |
| **2. Contenido HTML** | Pega el HTML del artículo a reescribir (o varios para fusionar) | ✅ |
| **3. Instrucciones** | Indica qué mejorar, mantener o eliminar | ✅ |
| **4. Producto principal** | Vincula el producto protagonista con su [JSON (n8n)](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV) | — |
| **5. Competidores** | Se analizan automáticamente (SEMrush) o los introduces a mano | ✅ |
| **6. Configuración** | Arquetipo, longitud, tono | ✅ |
| **7. Enlaces** | Links internos a posts/PLPs y a PDPs con datos enriquecidos | — |
| **8. Alternativos** | Productos alternativos a recomendar | — |

**3 modos disponibles:**
- **Reescritura simple** — mejora un artículo existente
- **Fusión** — combina 2+ artículos en uno superior (ideal contra canibalización)
- **Desambiguación** — separa un artículo genérico en varios específicos
        """)
        
        st.info(
            "💡 **Consejo**: Si GSC detecta múltiples URLs para tu keyword, "
            "usa el modo Fusión para consolidarlas en un único artículo."
        )


# ============================================================================
# MODO VERIFICAR KEYWORD
# ============================================================================

def render_verify_mode() -> None:
    """
    Renderiza el modo de verificación de keyword.
    Solo comprueba si la keyword ya rankea sin generar contenido.
    """
    
    # Guía de uso
    _render_verify_guide()
    
    # ── Configuración principal ──────────────────────────────────
    st.markdown("#### 🎯 Keyword a verificar")
    
    col_kw, col_spacer = st.columns([3, 2])
    with col_kw:
        keyword = st.text_input(
            "Keyword",
            placeholder="Ej: mejores portátiles gaming 2025",
            help="Introduce la keyword que quieres verificar",
            label_visibility="collapsed"
        )
    
    if not keyword or len(keyword.strip()) < 3:
        st.caption("👆 Introduce una keyword de al menos 3 caracteres para verificar")
        return
    
    # Cargar módulo GSC
    try:
        from utils.gsc_utils import (
            search_existing_content,
            get_content_coverage_summary,
            load_gsc_keywords_csv
        )
        _gsc_utils_available = True
    except ImportError:
        _gsc_utils_available = False
    
    # Botón de verificación
    st.markdown("---")
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        verify_clicked = st.button(
            "🔍 Verificar Keyword",
            type="primary",
            use_container_width=True,
            key="btn_verify_keyword"
        )
    
    if verify_clicked:
        if _gsc_utils_available:
            st.markdown("---")
            with st.spinner(f"🔍 Buscando '{keyword}' en datos de GSC..."):
                try:
                    df = load_gsc_keywords_csv()
                    
                    if df is None or (hasattr(df, 'empty') and df.empty):
                        st.warning("⚠️ No se pudieron cargar los datos de GSC")
                        return
                    
                    matches = search_existing_content(keyword)
                    summary = get_content_coverage_summary(keyword)
                    
                    render_verify_results(keyword, matches, summary)
                    
                except Exception as e:
                    logger.error(f"Error en verificación GSC: {e}")
                    st.error("❌ Error al verificar contenido existente. Revisa los logs para más detalles.")
        
        else:
            st.error("""
            ❌ **Módulo GSC no disponible**
            
            Para usar esta funcionalidad necesitas:
            1. El archivo `utils/gsc_utils.py` con las funciones de búsqueda
            2. Credenciales de GSC API configuradas en Secrets, o un CSV con datos de GSC
            """)


def _render_verify_guide() -> None:
    """Guía de uso para el modo verificar keyword."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**Verifica si ya tienes contenido posicionando para una keyword antes de crear algo nuevo.**

Esto te ayuda a evitar **canibalización** (cuando múltiples URLs de tu sitio compiten por la misma búsqueda en Google).

| Resultado | Qué significa | Qué hacer |
|-----------|---------------|-----------|
| 🟢 **Sin resultados** | No hay contenido para esta keyword | Puedes crear contenido nuevo |
| 🟡 **1 URL encontrada** | Ya tienes contenido posicionando | Valora actualizar el existente |
| 🔴 **Múltiples URLs** | Posible canibalización | Consolida con el modo Fusión en Reescritura |

**Fuente de datos:** Google Search Console (últimos 6 meses via API, o CSV local como fallback).
        """)
        
        st.info(
            "💡 **Consejo**: Verifica siempre la keyword antes de generar contenido nuevo. "
            "Es más rentable mejorar un artículo existente que crear uno desde cero."
        )


# ============================================================================
# MODO ASISTENTE
# ============================================================================


def _get_cached_generator() -> 'ContentGenerator':
    """Obtiene o crea un ContentGenerator cacheado en session_state.

    Evita recrear el cliente de Anthropic (y su connection pool) en cada
    mensaje del asistente. Se invalida si cambian las credenciales.
    """
    # Use hash of API key to avoid storing plaintext credentials in session state
    _key_hash = hashlib.sha256(CLAUDE_API_KEY.encode()).hexdigest()[:16] if CLAUDE_API_KEY else ''
    cache_key = f"{_key_hash}:{CLAUDE_MODEL}:{MAX_TOKENS}:{TEMPERATURE}"
    cached = st.session_state.get('_cached_generator')
    cached_key = st.session_state.get('_cached_generator_key')

    if cached is not None and cached_key == cache_key:
        return cached

    generator = ContentGenerator(
        api_key=CLAUDE_API_KEY,
        model=CLAUDE_MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
    )
    st.session_state['_cached_generator'] = generator
    st.session_state['_cached_generator_key'] = cache_key
    return generator


def render_assistant_mode() -> None:
    """Renderiza el modo asistente (chat con herramientas internas)."""
    
    if not _assistant_available:
        st.error("❌ El módulo de asistente no está disponible")
        return
    
    if not _generator_available or ContentGenerator is None:
        st.error("❌ ContentGenerator no disponible. Se requiere la API de Claude.")
        return
    
    # Guía
    _render_assistant_guide()
    
    # Inicializar estado del chat
    initialize_chat_state()
    
    # Renderizar historial
    render_chat_messages()
    
    # Input del usuario
    user_input = st.chat_input(
        "Pregunta sobre keywords, arquetipos, productos o pide generar contenido..."
    )
    
    if not user_input:
        return
    
    # Detectar si el usuario pegó un JSON de producto
    product_json = detect_product_json_in_message(user_input)
    if product_json:
        user_input = (
            f"El usuario ha pegado un JSON de producto. Analízalo con "
            f"[PRODUCTO_ANALIZAR: {product_json}]\n\n"
            f"Mensaje original del usuario: {user_input[:200]}"
        )
    
    # Añadir mensaje del usuario
    st.session_state.assistant_messages.append({
        'role': 'user',
        'content': user_input if not product_json else user_input.split("Mensaje original del usuario: ")[-1],
    })
    
    # Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(
            user_input if not product_json 
            else user_input.split("Mensaje original del usuario: ")[-1]
        )
    
    # Llamar a Claude
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                generator = _get_cached_generator()

                messages = build_messages_for_api()

                # Construir prompt con historial
                # La API de Claude recibe system + messages
                system = get_system_prompt()

                # Usar el último mensaje como prompt, el resto como contexto
                if len(messages) > 1:
                    context_parts = []
                    for m in messages[:-1]:
                        role_label = "Usuario" if m['role'] == 'user' else "Asistente"
                        context_parts.append(f"{role_label}: {m['content']}")
                    context = "\n\n".join(context_parts)
                    full_prompt = (
                        f"Historial de conversación:\n{context}\n\n"
                        f"Usuario: {messages[-1]['content']}"
                    )
                else:
                    full_prompt = messages[-1]['content']

                result = generator.generate(
                    prompt=full_prompt,
                    system_prompt=system,
                    temperature=0.7,
                )
                
                if not result.success:
                    st.error(f"❌ Error: {result.error}")
                    return
                
                # Detectar y ejecutar comandos en la respuesta
                cleaned_response, tool_results = detect_and_execute_commands(
                    result.content
                )
                
                # Mostrar respuesta del asistente
                if cleaned_response:
                    st.markdown(cleaned_response)
                
                # Mostrar resultados de herramientas
                for tr in tool_results:
                    with st.expander(f"🔧 {tr['command']}", expanded=True):
                        st.markdown(tr['result'])
                
                # Guardar en historial
                st.session_state.assistant_messages.append({
                    'role': 'assistant',
                    'content': cleaned_response,
                    'tool_results': tool_results,
                })
                
                # Si hay comando GENERAR, preparar para ejecutar
                gen_commands = [tr for tr in tool_results if tr.get('action') == 'generate']
                if gen_commands:
                    params = parse_generation_params(gen_commands[0].get('params', ''))
                    _handle_assistant_generation(params)
                
            except Exception as e:
                logger.error(f"Error en asistente: {e}")
                st.error("❌ Error del asistente. Por favor, inténtalo de nuevo.")


def _handle_assistant_generation(params: Dict[str, str]) -> None:
    """
    Maneja la generación de contenido lanzada desde el asistente.
    
    Args:
        params: Dict con keyword, arquetipo, longitud, visual (opcional)
    """
    keyword = params.get('keyword', '')
    arquetipo_code = params.get('arquetipo', 'ARQ-1')
    target_length = int(params.get('longitud', '1500'))
    visual_str = params.get('visual', '')
    
    if not keyword:
        st.warning("⚠️ Falta la keyword para generar contenido.")
        return
    
    # Parsear componentes visuales
    visual_elements = []
    if visual_str:
        visual_elements = [v.strip() for v in visual_str.split(',') if v.strip()]
    
    # Default: toc + verdict si no se especificó
    if not visual_elements:
        visual_elements = ['toc', 'verdict']
    
    visual_label = ', '.join(visual_elements) if visual_elements else 'por defecto'
    
    st.info(
        f"🚀 Lanzando generación: **{keyword}** | "
        f"Arquetipo: {arquetipo_code} | Longitud: {target_length} palabras | "
        f"Visual: {visual_label}"
    )
    
    # Construir guiding_context desde la conversación del asistente
    guiding_context = _build_assistant_guiding_context()
    
    config = {
        'keyword': keyword,
        'target_length': target_length,
        'arquetipo_codigo': arquetipo_code,
        'mode': 'new',
        'links': [],
        'additional_instructions': '',
        'guiding_context': guiding_context,
        'visual_elements': visual_elements,
        'visual_config': {
            'selected': visual_elements,
            'variants': {},
            'components_css': [],
        },
    }
    
    execute_generation_pipeline(config, mode='new')


def _build_assistant_guiding_context() -> str:
    """
    Construye guiding_context a partir del historial del asistente.
    
    Extrae contexto relevante de:
    1. Mensajes del usuario en la conversación del asistente
    2. Resultados de herramientas ejecutadas (SERP research, GSC, análisis de producto)
    """
    context_parts = []
    
    assistant_messages = st.session_state.get('assistant_messages', [])
    if not assistant_messages:
        return ""
    
    # 1. Extraer mensajes relevantes del usuario (máx últimos ~3 turnos)
    user_messages = [
        m['content'] for m in assistant_messages[-8:]
        if m.get('role') == 'user' and len(m.get('content', '')) > 10
    ]
    if user_messages:
        context_parts.append(
            "**Contexto de la conversación con el asistente:**\n" + 
            "\n".join(f"- {msg[:500]}" for msg in user_messages[-4:])
        )
    
    # 2. Extraer resultados de herramientas (SERP, GSC, producto, etc.)
    for m in assistant_messages[-6:]:
        tool_results = m.get('tool_results', [])
        for tr in tool_results:
            command = tr.get('command', '')
            result = tr.get('result', '')
            # Solo incluir resultados informativos, no errores ni comandos GENERAR
            if (result and len(result) > 20 
                    and not result.startswith('❌') 
                    and not result.startswith('⚠️')
                    and tr.get('action') != 'generate'):
                context_parts.append(
                    f"**Resultado de {command}:**\n{result[:1500]}"
                )
    
    return "\n\n".join(context_parts) if context_parts else ""


def _render_assistant_guide() -> None:
    """Guía de uso para el modo asistente."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**El asistente es tu copiloto para la creación de contenido.** Pregúntale en lenguaje natural y usará las herramientas internas de Raichu automáticamente.

**Ejemplos de lo que puedes preguntar:**

| Pregunta | Qué hace el asistente |
|----------|----------------------|
| "¿Qué contenido posiciona en Google para mejores portátiles gaming?" | Investiga las SERPs, scrapea competidores y analiza su estructura |
| "¿Tengo contenido para monitor gaming 4K?" | Verifica en GSC si ya posicionas para esa keyword |
| "¿Qué arquetipo me recomiendas para una guía de compra de portátiles?" | Consulta los arquetipos y recomienda el más adecuado |
| "Muéstrame los arquetipos disponibles" | Lista todos los tipos de contenido con su descripción |
| "¿Qué elementos visuales me recomiendas para una comparativa?" | Sugiere componentes del design system según el tipo de artículo |
| "¿Qué componentes visuales hay disponibles?" | Lista todos los componentes CSS del design system |
| *(pegar un [JSON de producto](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV))* | Analiza las specs, reviews y características del producto |
| "Genera un artículo para mejores auriculares gaming con ARQ-1" | Lanza la generación con componentes visuales recomendados |

**El historial se mantiene** durante toda la sesión, incluso si cambias a otro modo y vuelves.
        """)
        
        st.info(
            "💡 **Consejo**: Empieza verificando tu keyword, luego pide una recomendación "
            "de arquetipo, y finalmente lanza la generación — todo desde el chat."
        )


def render_verify_results(keyword: str, matches: List[Dict], summary: Dict) -> None:
    """
    Renderiza los resultados de verificación de keyword.
    
    Args:
        keyword: Keyword verificada
        matches: Lista de URLs que coinciden
        summary: Resumen del análisis
    """
    
    st.markdown("#### 📊 Resultados")
    
    if not matches:
        st.success(
            f'**No se encontró contenido existente para "{keyword}"**\n\n'
            'Puedes crear contenido nuevo para esta keyword sin riesgo de canibalización.\n\n'
            'Procede con el modo "Nuevo Contenido" o "Reescritura Competitiva".'
        )
        return
    
    # Hay matches - mostrar alerta según gravedad
    unique_urls = list(set(m.get('url', '') for m in matches if m.get('url')))
    num_urls = len(unique_urls)
    
    if num_urls == 1:
        url = unique_urls[0]
        st.warning(
            f'**Ya tienes contenido rankeando para "{keyword}"**\n\n'
            f'Se encontró **1 URL** que ya posiciona.\n\n'
            'Considera mejorar el contenido existente en lugar de crear uno nuevo.'
        )
        safe_url = html.escape(url, quote=True)
        st.markdown(
            f'<p>🔗 <a href="{safe_url}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;word-break:break-all;">{safe_url}</a></p>',
            unsafe_allow_html=True,
        )
    else:
        st.error(
            f'**Posible canibalización detectada para "{keyword}"**\n\n'
            f'Se encontraron **{num_urls} URLs** compitiendo por esta keyword. '
            'Consolida el contenido en una sola URL o diferencia '
            'claramente la intención de cada página.'
        )
        urls_html = []
        for url in unique_urls[:5]:
            safe_url = html.escape(url, quote=True)
            urls_html.append(
                f'<a href="{safe_url}" target="_blank" rel="noopener" '
                f'style="color:#1a73e8;word-break:break-all;">{safe_url}</a>'
            )
        extra = f'<br><small>... y {num_urls - 5} URLs más</small>' if num_urls > 5 else ''
        st.markdown(
            '<div style="margin:8px 0;">' + '<br>'.join(f'• {u}' for u in urls_html) + extra + '</div>',
            unsafe_allow_html=True,
        )
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("URLs Encontradas", num_urls)
    
    with col2:
        best_position = min(m.get('position', 100) for m in matches) if matches else 0
        st.metric("Mejor Posición", f"#{best_position:.0f}")
    
    with col3:
        total_clicks = sum(m.get('clicks', 0) for m in matches)
        st.metric("Total Clics", f"{total_clicks:,}")
    
    with col4:
        total_impressions = sum(m.get('impressions', 0) for m in matches)
        st.metric("Total Impresiones", f"{total_impressions:,}")
    
    # Tabla de matches
    with st.expander("📋 Detalle de URLs que rankean", expanded=True):
        table_data = []
        for m in matches:
            row = {
                'URL': m.get('url', ''),
                'Query': m.get('query', m.get('keyword', '')),
                'Posición': f"#{m.get('position', 0):.0f}",
                'Clics': m.get('clicks', 0),
                'Impresiones': f"{m.get('impressions', 0):,}",
                'Score': m.get('match_score', 0),
            }
            
            # Mostrar CTR formateado
            ctr = m.get('ctr', 0)
            if isinstance(ctr, (int, float)):
                row['CTR'] = f"{ctr:.2%}" if ctr < 1 else f"{ctr:.2f}%"
            else:
                row['CTR'] = str(ctr)
            
            # Mostrar riesgo si viene de la API mejorada
            if 'risk_label' in m:
                row['Riesgo'] = m['risk_label']
            
            table_data.append(row)
        
        if table_data:
            import pandas as pd
            df = pd.DataFrame(table_data)
            st.dataframe(
                df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    'URL': st.column_config.LinkColumn('URL', width='large'),
                    'Clics': st.column_config.NumberColumn('Clics', format='%d'),
                }
            )
    
    # Recomendación del sistema
    if summary:
        recommendation = summary.get('recommendation', '')
        if recommendation:
            st.markdown("---")
            st.markdown("#### 💡 Recomendación")
            
            # Detectar tipo de recomendación por contenido
            rec_lower = recommendation.lower()
            if 'no hay contenido' in rec_lower or 'puedes crear' in rec_lower:
                st.success(recommendation)
            elif 'actualizar' in rec_lower or 'mejorar' in rec_lower:
                st.info(recommendation)
            elif 'consolidar' in rec_lower or 'fragmentación' in rec_lower or num_urls > 2:
                st.error(recommendation)
            else:
                st.warning(recommendation)




# ============================================================================
# PIPELINE DE GENERACIÓN (delegado a core/pipeline.py)
# ============================================================================

def execute_generation_pipeline(config: Dict[str, Any], mode: str = 'new') -> None:
    """
    Ejecuta el pipeline completo de generación en 3 etapas.
    Delegado a core.pipeline para mantener app.py manejable.
    """
    # Recordar que el usuario ya ha generado en este modo (oculta guía)
    if mode == 'new':
        st.session_state['_has_generated_new'] = True
    elif mode == 'rewrite':
        st.session_state['_has_generated_rewrite'] = True

    from core.pipeline import execute_generation_pipeline as _execute
    _execute(config, mode)


# Helpers de pipeline (delegados a core.pipeline)
def _check_visual_elements_presence(html_content, selected_elements):
    from core.pipeline import _check_visual_elements_presence as _fn
    _fn(html_content, selected_elements)

def _check_ai_phrases(html_content):
    from core.pipeline import _check_ai_phrases as _fn
    _fn(html_content)

def _check_engagement_elements(html_content, check_mini_stories=True):
    from core.pipeline import _check_engagement_elements as _fn
    _fn(html_content, check_mini_stories=check_mini_stories)



def save_generation_to_state(config: Dict[str, Any], mode: str) -> None:
    """Guarda metadata de la generación."""
    
    st.session_state.generation_metadata = {
        'timestamp': datetime.now().isoformat(),
        'mode': mode,
        'keyword': config.get('keyword', ''),
        'target_length': config.get('target_length', 1500),
        'arquetipo': config.get('arquetipo_codigo', ''),
        'config': {k: v for k, v in config.items() if k not in ['html_to_rewrite', 'competitors_data', 'pdp_data', 'pdp_json_data']},
    }


# ============================================================================
# RESULTADOS Y FOOTER
# ============================================================================

def render_results() -> None:
    """Renderiza la sección de resultados.
    
    Solo muestra resultados si fueron generados por el modo ACTUAL.
    Esto evita que un artículo generado en 'new' se arrastre a 'rewrite' o 'assistant'.
    """
    current_mode = st.session_state.get('mode', 'new')
    
    if not any([
        st.session_state.get('draft_html'),
        st.session_state.get('analysis_json'),
        st.session_state.get('final_html')
    ]):
        return
    
    # Verificar que los resultados pertenecen al modo actual
    gen_meta = st.session_state.get('generation_metadata', {})
    result_mode = gen_meta.get('mode', '')
    
    # El asistente genera con mode='new' internamente, así que lo aceptamos en assistant
    if result_mode and result_mode != current_mode:
        if not (current_mode == 'assistant' and result_mode == 'new'):
            return
    
    if _results_available and render_results_section:
        render_results_section(
            draft_html=st.session_state.get('draft_html'),
            analysis_json=st.session_state.get('analysis_json'),
            final_html=st.session_state.get('final_html'),
            target_length=st.session_state.get('last_config', {}).get('target_length', 1500),
            mode=st.session_state.get('mode', 'new')
        )
    else:
        # Fallback simple si render_results_section no está disponible
        st.markdown("---")
        st.subheader("📊 Resultados")
        
        if st.session_state.get('final_html'):
            st.markdown("### ✅ Contenido Final")
            with st.expander("Ver HTML"):
                st.code(st.session_state.final_html, language="html")
            
            st.download_button(
                "📥 Descargar HTML",
                st.session_state.final_html,
                file_name=f"content_{st.session_state.get('timestamp', 'export')}.html",
                mime="text/html"
            )


def render_footer() -> None:
    """Renderiza el footer de la aplicación."""
    
    st.markdown("---")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.caption(f"📦 Versión {__version__}")
    
    with col2:
        st.caption("🏢 PcComponentes - Product Discovery & Content")
    
    with col3:
        if DEBUG_MODE:
            st.caption("🐛 Modo Debug Activo")


def render_debug_panel() -> None:
    """Renderiza panel de debug (solo si DEBUG_MODE=True)."""
    
    if not DEBUG_MODE:
        return
    
    with st.expander("🐛 Debug Panel"):
        st.json({
            'mode': st.session_state.get('mode'),
            'generation_in_progress': st.session_state.get('generation_in_progress'),
            'current_stage': st.session_state.get('current_stage'),
            'has_draft': st.session_state.get('draft_html') is not None,
            'has_analysis': st.session_state.get('analysis_json') is not None,
            'has_final': st.session_state.get('final_html') is not None,
            'history_length': len(st.session_state.get('content_history', [])),
            'modules': {
                'generator': _generator_available,
                'new_content': _new_content_available,
                'rewrite': _rewrite_available,
                'inputs_ui': _inputs_available,
                'rewrite_ui': _rewrite_ui_available,
                'results_ui': _results_available,
            }
        })


# ============================================================================
# AUTENTICACIÓN
# ============================================================================

def check_auth() -> bool:
    """
    Verifica autenticación por contraseña.
    Lee la contraseña de st.secrets['app']['password'].
    
    Returns:
        True si autenticado, False si no
    """
    # Si ya está autenticado en esta sesión, no pedir de nuevo
    if st.session_state.get('authenticated'):
        return True
    
    # Obtener contraseña configurada
    app_password = None
    try:
        app_password = st.secrets.get('app', {}).get('password')
    except Exception:
        pass
    
    # Si no hay contraseña configurada, permitir acceso libre
    if not app_password:
        return True
    
    # Mostrar formulario de login
    st.markdown(
        """
        <div style="max-width: 400px; margin: 80px auto; text-align: center;">
            <h2>🚀 Raichu Content Generator</h2>
            <p style="color: #666;">Introduce la contraseña para acceder</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        password_input = st.text_input(
            "Contraseña",
            type="password",
            key="login_password",
            placeholder="••••••••",
        )
        
        if st.button("Entrar", use_container_width=True, key="btn_login"):
            if hmac.compare_digest(password_input, app_password):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta")
    
    return False


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Función principal de la aplicación."""
    
    # Configuración de página
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Autenticación
    if not check_auth():
        st.stop()
    
    # Inicializar
    initialize_app()
    
    # Verificar configuración
    is_valid, errors = check_configuration()
    
    if not is_valid:
        st.error("❌ Error de Configuración")
        for error in errors:
            st.warning(f"• {error}")
        st.stop()
    
    # Sidebar
    if _sidebar_available and render_sidebar:
        render_sidebar()
    
    # Header con selector de modo
    mode = render_app_header()
    
    # Renderizar según modo
    if mode == 'new':
        render_new_content_mode()
    elif mode == 'rewrite':
        render_rewrite_mode()
    elif mode == 'verify':
        render_verify_mode()
    elif mode == 'opportunities':
        try:
            from ui.opportunities import render_opportunities_mode
            render_opportunities_mode()
        except ImportError as e:
            logger.error(f"Módulo de oportunidades no disponible: {e}")
            st.error("❌ Módulo de oportunidades no disponible. Verifica la instalación.")
    elif mode == 'assistant':
        render_assistant_mode()
    
    # Resultados (solo para modos de generación)
    # v5.0: results.py ahora incluye refinamiento integrado en el flujo
    if mode in ['new', 'rewrite', 'assistant']:
        render_results()
    
    # Footer
    render_footer()
    
    # Debug panel
    render_debug_panel()


if __name__ == "__main__":
    main()
