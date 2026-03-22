"""
Modo de verificación de keyword.

Comprueba si una keyword ya rankea en GSC para detectar canibalización.
"""

import html
import logging
from typing import Dict, List

import streamlit as st

logger = logging.getLogger(__name__)


def render_verify_mode() -> None:
    """
    Renderiza el modo de verificación de keyword.
    Solo comprueba si la keyword ya rankea sin generar contenido.
    """

    # Guía de uso
    _render_verify_guide()

    # ── Configuración principal ──────────────────────────────────
    st.markdown("#### \U0001f3af Keyword a verificar")

    col_kw, col_spacer = st.columns([3, 2])
    with col_kw:
        keyword = st.text_input(
            "Keyword",
            placeholder="Ej: mejores portátiles gaming 2025",
            help="Introduce la keyword que quieres verificar",
            label_visibility="collapsed"
        )

    if not keyword or len(keyword.strip()) < 3:
        st.caption("\U0001f446 Introduce una keyword de al menos 3 caracteres para verificar")
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
            "\U0001f50d Verificar Keyword",
            type="primary",
            use_container_width=True,
            key="btn_verify_keyword"
        )

    if verify_clicked:
        if _gsc_utils_available:
            st.markdown("---")
            with st.spinner(f"\U0001f50d Buscando '{keyword}' en datos de GSC..."):
                try:
                    df = load_gsc_keywords_csv()

                    if df is None or (hasattr(df, 'empty') and df.empty):
                        st.warning("\u26a0\ufe0f No se pudieron cargar los datos de GSC")
                        return

                    matches = search_existing_content(keyword)
                    summary = get_content_coverage_summary(keyword)

                    render_verify_results(keyword, matches, summary)

                except Exception as e:
                    logger.error(f"Error en verificación GSC: {e}")
                    st.error("\u274c Error al verificar contenido existente. Revisa los logs para más detalles.")

        else:
            st.error("""
            \u274c **Módulo GSC no disponible**

            Para usar esta funcionalidad necesitas:
            1. El archivo `utils/gsc_utils.py` con las funciones de búsqueda
            2. Credenciales de GSC API configuradas en Secrets, o un CSV con datos de GSC
            """)


def _render_verify_guide() -> None:
    """Guía de uso para el modo verificar keyword."""

    with st.expander("\U0001f4d6 \u00bfCómo funciona? \u2014 Guía rápida", expanded=False):
        st.markdown("""
**Verifica si ya tienes contenido posicionando para una keyword antes de crear algo nuevo.**

Esto te ayuda a evitar **canibalización** (cuando múltiples URLs de tu sitio compiten por la misma búsqueda en Google).

| Resultado | Qué significa | Qué hacer |
|-----------|---------------|-----------|
| \U0001f7e2 **Sin resultados** | No hay contenido para esta keyword | Puedes crear contenido nuevo |
| \U0001f7e1 **1 URL encontrada** | Ya tienes contenido posicionando | Valora actualizar el existente |
| \U0001f534 **Múltiples URLs** | Posible canibalización | Consolida con el modo Fusión en Reescritura |

**Fuente de datos:** Google Search Console (últimos 6 meses via API, o CSV local como fallback).
        """)

        st.info(
            "\U0001f4a1 **Consejo**: Verifica siempre la keyword antes de generar contenido nuevo. "
            "Es más rentable mejorar un artículo existente que crear uno desde cero."
        )


def render_verify_results(keyword: str, matches: List[Dict], summary: Dict) -> None:
    """
    Renderiza los resultados de verificación de keyword.

    Args:
        keyword: Keyword verificada
        matches: Lista de URLs que coinciden
        summary: Resumen del análisis
    """

    st.markdown("#### \U0001f4ca Resultados")

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
            f'<p>\U0001f517 <a href="{safe_url}" target="_blank" rel="noopener" '
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
            '<div style="margin:8px 0;">' + '<br>'.join(f'\u2022 {u}' for u in urls_html) + extra + '</div>',
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
    with st.expander("\U0001f4cb Detalle de URLs que rankean", expanded=True):
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
            st.markdown("#### \U0001f4a1 Recomendación")

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
