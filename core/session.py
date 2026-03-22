"""
Gestión del estado de sesión de Streamlit.

Inicialización, aislamiento por modo, limpieza y persistencia de metadata.
"""

import logging
from datetime import datetime
from typing import Dict, Any

import streamlit as st

logger = logging.getLogger(__name__)


# Keys de resultados de generación que se aíslan por modo
_MODE_RESULT_KEYS = [
    'draft_html', 'analysis_json', 'final_html',
    'rewrite_analysis', 'content_history', 'generation_metadata',
    'last_config', 'timestamp',
]


def initialize_app(openai_client=None, openai_api_key="", openai_model="") -> None:
    """Inicializa el estado de la aplicación.

    Args:
        openai_client: Módulo openai_client (None si no disponible)
        openai_api_key: API key de OpenAI para corrección dual
        openai_model: Modelo de OpenAI
    """

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
        if openai_client and openai_api_key:
            openai_client.configure(openai_api_key)
            logger.info(f"OpenAI configurado para corrección dual (modelo: {openai_model})")

        logger.info("Aplicación inicializada")


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
