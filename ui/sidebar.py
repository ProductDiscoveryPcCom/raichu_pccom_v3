"""
Sidebar de la aplicación
"""
import streamlit as st

try:
    from version import __version__
except ImportError:
    __version__ = "5.1.0"


_MODE_LABELS = {
    'new': '📝 Nuevo Contenido',
    'rewrite': '🔄 Reescritura',
    'verify': '🔍 Verificar',
    'opportunities': '💡 Oportunidades',
    'assistant': '💬 Asistente',
}


def render_sidebar():
    """Renderiza el sidebar con información de la app"""
    with st.sidebar:
        st.markdown("## Content Generator")
        st.markdown("**PcComponentes**")
        st.markdown("---")

        # P4.1: indicador del modo activo
        current_mode = st.session_state.get('mode', 'new')
        current_label = _MODE_LABELS.get(current_mode, '—')
        st.markdown(f"**Modo activo:** {current_label}")
        st.markdown("---")

        st.markdown("### Funcionalidades")
        features = [
            "37 arquetipos de contenido",
            "Flujo 3 etapas (borrador → análisis → final)",
            "Modo Nuevo + Reescritura + Fusión",
            "Verificación GSC (API + CSV)",
            "Análisis competitivo (SEMrush / manual)",
            "JSON de productos (n8n)",
            "Elementos visuales (Design System)",
            "Traducción contextualizada",
            "Generación de imágenes (Gemini)",
            "Asistente Claude integrado",
            "CSS compatible con CMS",
        ]
        for feature in features:
            st.markdown(f"✅ {feature}")

        st.markdown("---")
        st.markdown("### Info")
        st.markdown(f"Versión {__version__}")
        st.markdown("© 2025 PcComponentes")
