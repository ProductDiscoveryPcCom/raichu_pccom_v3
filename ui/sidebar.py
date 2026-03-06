"""
Sidebar de la aplicación
"""
import streamlit as st

try:
    from version import __version__
except ImportError:
    __version__ = "5.1.0"


def render_sidebar():
    """Renderiza el sidebar con información de la app"""
    with st.sidebar:
        st.markdown("## Content Generator")
        st.markdown("**PcComponentes**")
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
