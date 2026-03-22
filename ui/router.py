"""
Header, footer y panel de debug de la aplicación.

Renderiza el selector de modo, el footer con versión, y el panel de debug.
"""

import streamlit as st

from core.session import _save_mode_results, _restore_mode_results, clear_session_state


def render_app_header(app_title: str, version: str) -> str:
    """
    Renderiza el header de la aplicación.

    Args:
        app_title: Título de la aplicación
        version: Versión de la aplicación

    Returns:
        Modo seleccionado ('new', 'rewrite', 'verify', 'opportunities' o 'assistant')
    """
    st.title(f"\U0001f680 {app_title}")
    st.caption(f"Versión {version} | Generación de contenido SEO en 3 etapas")

    st.markdown("---")

    # Selector de modo + botón limpiar en una fila compacta
    col_mode, col_clear = st.columns([5, 1])

    with col_mode:
        mode = st.radio(
            "Modo",
            options=['new', 'rewrite', 'verify', 'opportunities', 'assistant'],
            format_func=lambda x: {
                'new': '\U0001f4dd Nuevo',
                'rewrite': '\U0001f504 Reescritura Competitiva',
                'verify': '\U0001f50d Verificar',
                'opportunities': '\U0001f4ca Oportunidades',
                'assistant': '\U0001f4ac Asistente',
            }.get(x, x),
            horizontal=True,
            key='mode_selector_main',
            label_visibility="collapsed"
        )

    with col_clear:
        if st.button("\U0001f5d1\ufe0f Limpiar", use_container_width=True, key="btn_clear_all"):
            st.session_state['_confirm_clear'] = True
            st.rerun()

    if st.session_state.get('_confirm_clear'):
        st.warning("\u26a0\ufe0f \u00bfSeguro que quieres limpiar todos los datos? Se perderá el contenido generado.")
        col_yes, col_no = st.columns(2)
        with col_yes:
            if st.button("\u2705 Sí, limpiar todo", type="primary", key="btn_confirm_clear"):
                st.session_state.pop('_confirm_clear', None)
                clear_session_state()
                st.rerun()
        with col_no:
            if st.button("\u274c Cancelar", key="btn_cancel_clear"):
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


def render_footer(version: str, debug_mode: bool) -> None:
    """Renderiza el footer de la aplicación."""

    st.markdown("---")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.caption(f"\U0001f4e6 Versión {version}")

    with col2:
        st.caption("\U0001f3e2 PcComponentes - Product Discovery & Content")

    with col3:
        if debug_mode:
            st.caption("\U0001f41b Modo Debug Activo")


def render_debug_panel(debug_mode: bool, module_flags: dict) -> None:
    """Renderiza panel de debug (solo si debug_mode=True).

    Args:
        debug_mode: Si el modo debug está activo
        module_flags: Dict con flags de disponibilidad de módulos
    """

    if not debug_mode:
        return

    with st.expander("\U0001f41b Debug Panel"):
        st.json({
            'mode': st.session_state.get('mode'),
            'generation_in_progress': st.session_state.get('generation_in_progress'),
            'current_stage': st.session_state.get('current_stage'),
            'has_draft': st.session_state.get('draft_html') is not None,
            'has_analysis': st.session_state.get('analysis_json') is not None,
            'has_final': st.session_state.get('final_html') is not None,
            'history_length': len(st.session_state.get('content_history', [])),
            'modules': module_flags,
        })
