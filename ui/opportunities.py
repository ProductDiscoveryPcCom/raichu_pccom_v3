# -*- coding: utf-8 -*-
"""
UI de Oportunidades SEO - PcComponentes Content Generator
Versión 1.0.0

Pantalla que combina datos de GSC con el OpportunityScorer para mostrar:
- Quick wins (posiciones 11-20 con alto volumen)
- Contenido con CTR bajo (underperformers)
- Keywords en declive (necesitan actualización)
- Tabla priorizada con score y recomendación por keyword

Cada oportunidad tiene un botón "Generar" que pre-rellena el modo 
"Nuevo Contenido" o "Reescritura" según el tipo.

Autor: PcComponentes - Product Discovery & Content
"""

import streamlit as st
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

__version__ = "1.0.0"


def render_opportunities_mode() -> None:
    """Renderiza el modo de oportunidades SEO."""

    st.markdown("### 📊 Oportunidades SEO")
    st.markdown(
        "Análisis de tus datos de GSC para identificar las mejores oportunidades "
        "de contenido. Ordena por score de oportunidad para priorizar."
    )

    # ================================================================
    # PASO 1: Cargar datos de GSC
    # ================================================================
    gsc_data = _load_gsc_data()

    if gsc_data is None:
        st.warning(
            "⚠️ **No hay datos de GSC disponibles.** "
            "Sube un CSV de Google Search Console (`gsc_keywords.csv`) "
            "o configura la API de GSC en los secrets."
        )
        _render_csv_upload()
        return

    records = gsc_data.get('data', [])
    if not records:
        st.warning("⚠️ El dataset de GSC está vacío.")
        return

    st.caption(f"📄 {len(records)} keywords cargadas desde GSC")

    # ================================================================
    # PASO 2: Filtros
    # ================================================================
    with st.expander("🔧 Filtros", expanded=False):
        filter_cols = st.columns(3)
        with filter_cols[0]:
            min_impressions = st.number_input(
                "Impresiones mínimas", min_value=0, value=50, step=10,
                help="Filtra keywords con pocas impresiones"
            )
        with filter_cols[1]:
            position_range = st.slider(
                "Rango de posición", min_value=1, max_value=100,
                value=(1, 50),
                help="Solo mostrar keywords en este rango de posición"
            )
        with filter_cols[2]:
            opp_types = st.multiselect(
                "Tipo de oportunidad",
                options=['quick_win', 'improvement', 'underperformer', 'declining'],
                default=['quick_win', 'improvement', 'underperformer'],
                format_func=lambda x: {
                    'quick_win': '⚡ Quick Win',
                    'improvement': '📈 Mejora',
                    'underperformer': '🔧 Bajo rendimiento',
                    'declining': '📉 En declive',
                }.get(x, x),
            )

    # ================================================================
    # PASO 3: Calcular scores
    # ================================================================
    try:
        from utils.opportunity_scorer import OpportunityScorer
    except ImportError:
        st.error("❌ Módulo opportunity_scorer no disponible.")
        return

    scorer = OpportunityScorer()

    # Filtrar registros
    filtered = [
        r for r in records
        if r.get('impressions', 0) >= min_impressions
        and position_range[0] <= r.get('position', 0) <= position_range[1]
    ]

    if not filtered:
        st.info("No hay keywords que cumplan los filtros. Ajusta los parámetros.")
        return

    # Calcular oportunidades
    with st.spinner(f"Analizando {len(filtered)} keywords..."):
        opportunities = []
        for record in filtered:
            opp = scorer.score_keyword(
                keyword=record.get('query', ''),
                position=record.get('position', 0),
                impressions=record.get('impressions', 0),
                clicks=record.get('clicks', 0),
                ctr=record.get('ctr', 0),
                url=record.get('url', record.get('page', '')),
            )
            if not opp_types or opp['type'] in opp_types:
                opportunities.append(opp)

        # Ordenar por score descendente
        opportunities.sort(key=lambda x: -x['score'])

    if not opportunities:
        st.info("No se encontraron oportunidades con los filtros actuales.")
        return

    # ================================================================
    # PASO 4: Resumen rápido
    # ================================================================
    st.markdown("---")

    summary_cols = st.columns(4)
    type_counts = {}
    for opp in opportunities:
        t = opp['type']
        type_counts[t] = type_counts.get(t, 0) + 1

    with summary_cols[0]:
        st.metric("Total oportunidades", len(opportunities))
    with summary_cols[1]:
        st.metric("⚡ Quick Wins", type_counts.get('quick_win', 0))
    with summary_cols[2]:
        st.metric("📈 Mejoras", type_counts.get('improvement', 0))
    with summary_cols[3]:
        underp = type_counts.get('underperformer', 0) + type_counts.get('declining', 0)
        st.metric("🔧 Necesitan atención", underp)

    # ================================================================
    # PASO 5: Tabla de oportunidades
    # ================================================================
    st.markdown("---")
    st.markdown("### 🏆 Top oportunidades")

    # Mostrar top 20
    for i, opp in enumerate(opportunities[:20], 1):
        _render_opportunity_card(i, opp)


def _render_opportunity_card(rank: int, opp: Dict[str, Any]) -> None:
    """Renderiza una tarjeta de oportunidad con botón de acción."""
    current = opp['current']
    factors = opp['factors']

    # Color según tipo
    type_colors = {
        'quick_win': '🟢',
        'improvement': '🔵',
        'underperformer': '🟡',
        'declining': '🔴',
        'new_content': '⚪',
    }
    color = type_colors.get(opp['type'], '⚪')

    with st.container():
        cols = st.columns([0.5, 3, 1.5, 1, 1, 1, 2])

        with cols[0]:
            st.markdown(f"**#{rank}**")
        with cols[1]:
            st.markdown(f"**{opp['keyword']}**")
            st.caption(f"{color} {opp['type_label']} · Pos. {current['position']:.0f} · {current['impressions']} impr.")
        with cols[2]:
            # Score badge
            score = opp['score']
            if score >= 70:
                st.markdown(f"🔥 **{score:.0f}/100**")
            elif score >= 50:
                st.markdown(f"📊 **{score:.0f}/100**")
            else:
                st.markdown(f"📉 {score:.0f}/100")
        with cols[3]:
            st.caption(f"CTR: {current['ctr']*100:.1f}%")
        with cols[4]:
            st.caption(f"+{opp['potential_clicks']} clics pot.")
        with cols[5]:
            st.caption(f"Vol:{factors['volume']:.0f} Pos:{factors['position']:.0f} Int:{factors['intent']:.0f}")
        with cols[6]:
            # Botón de acción
            action = "Reescribir" if current.get('url') else "Generar"
            btn_key = f"opp_action_{rank}_{opp['keyword'][:20]}"

            if st.button(f"✏️ {action}", key=btn_key, use_container_width=True):
                _launch_generation(opp)

    # Recomendación en gris
    st.caption(f"  💡 {opp['recommendation']}")
    st.markdown("")  # Spacer


def _launch_generation(opp: Dict[str, Any]) -> None:
    """Pre-rellena modo de generación y redirige."""
    current = opp['current']

    if current.get('url'):
        # Tiene URL → modo reescritura
        st.session_state.mode = 'rewrite'
        st.session_state['prefill_keyword'] = opp['keyword']
        st.session_state['prefill_url'] = current['url']
        st.info(
            f"📝 Keyword **{opp['keyword']}** configurada para reescritura. "
            f"Cambia al modo '🔄 Reescritura Competitiva' para continuar."
        )
    else:
        # Sin URL → modo nuevo contenido
        st.session_state.mode = 'new'
        st.session_state['prefill_keyword'] = opp['keyword']
        st.info(
            f"📝 Keyword **{opp['keyword']}** configurada para nuevo contenido. "
            f"Cambia al modo '📝 Nuevo Contenido' para continuar."
        )


def _load_gsc_data() -> Optional[Dict]:
    """Carga datos de GSC usando el sistema existente."""
    try:
        from utils.gsc_utils import load_gsc_data
        return load_gsc_data()
    except ImportError:
        logger.warning("gsc_utils no disponible")
        return None
    except Exception as e:
        logger.warning(f"Error cargando GSC: {e}")
        return None


def _render_csv_upload() -> None:
    """Widget para subir CSV de GSC manualmente."""
    st.markdown("#### 📤 Subir CSV de Google Search Console")
    st.markdown(
        "Exporta tus datos desde [Google Search Console](https://search.google.com/search-console) "
        "→ Rendimiento → Exportar (CSV). El archivo debe tener columnas: `query`, `clicks`, "
        "`impressions`, `ctr`, `position`."
    )

    uploaded = st.file_uploader(
        "CSV de GSC", type=['csv', 'tsv'],
        key='opp_csv_upload',
        help="Formato: query, clicks, impressions, ctr, position"
    )

    if uploaded:
        try:
            import pandas as pd
            # Detectar separador
            content = uploaded.getvalue().decode('utf-8')
            sep = ';' if content.count(';') > content.count(',') else ','
            
            import io
            df = pd.read_csv(io.StringIO(content), sep=sep)
            df.columns = df.columns.str.lower().str.strip()

            # Guardar temporalmente
            csv_path = "gsc_keywords.csv"
            df.to_csv(csv_path, index=False)
            st.success(f"✅ {len(df)} keywords cargadas. Recarga la página para ver oportunidades.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error procesando CSV: {e}")
