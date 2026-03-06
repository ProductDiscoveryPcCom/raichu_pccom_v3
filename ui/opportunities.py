# -*- coding: utf-8 -*-
"""
UI de Oportunidades SEO - PcComponentes Content Generator
Versión 1.1.0

Pantalla que combina datos de GSC con el OpportunityScorer para mostrar:
- Quick wins (posiciones 11-20 con alto volumen)
- Contenido con CTR bajo (underperformers)
- Keywords en declive (necesitan actualización)
- Tabla priorizada con score y recomendación por keyword

Cada oportunidad tiene un botón "Generar" que pre-rellena el modo
"Nuevo Contenido" o "Reescritura" según el tipo.

CAMBIOS v1.1.0:
- Conexión directa con API de GSC si las credenciales están en secrets
- Botón "Conectar con Google Search Console" cuando la API está disponible
- Fallback automático a CSV si la API no está disponible
- Indicador de fuente de datos (API vs CSV)

Autor: PcComponentes - Product Discovery & Content
"""

import streamlit as st
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

__version__ = "1.1.0"


def render_opportunities_mode() -> None:
    """Renderiza el modo de oportunidades SEO."""

    st.markdown("### 📊 Oportunidades SEO")
    st.markdown(
        "Análisis de tus datos de GSC para identificar las mejores oportunidades "
        "de contenido. Ordena por score de oportunidad para priorizar."
    )

    # ================================================================
    # PASO 1: Cargar datos de GSC (API primero, CSV fallback)
    # ================================================================
    gsc_data = _load_gsc_data()

    if gsc_data is None:
        # Comprobar si la API está configurada en secrets
        api_configured = _is_api_configured()

        if api_configured:
            # API disponible pero no se ha conectado aún → botón de conexión
            _render_api_connect()
        else:
            st.warning(
                "⚠️ **No hay datos de GSC disponibles.** "
                "Configura la API de GSC en los secrets o sube un CSV."
            )

        _render_csv_upload()
        return

    records = gsc_data.get('data', [])
    if not records:
        st.warning("⚠️ El dataset de GSC está vacío.")
        return

    # Indicador de fuente
    source = gsc_data.get('source', 'csv')
    period = gsc_data.get('period', '')
    if source == 'api':
        st.caption(f"📡 {len(records)} keywords cargadas desde GSC API · {period}")
    else:
        st.caption(f"📄 {len(records)} keywords cargadas desde CSV")

    # Botón para refrescar datos desde API
    if source == 'api':
        if st.button("🔄 Actualizar datos de GSC", key="gsc_refresh"):
            _clear_gsc_cache()
            st.rerun()

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


# ============================================================================
# CARGA DE DATOS GSC (API primero, CSV fallback)
# ============================================================================

def _is_api_configured() -> bool:
    """Comprueba si la API de GSC está configurada en secrets."""
    try:
        from utils.gsc_api import is_gsc_api_configured
        return is_gsc_api_configured()
    except ImportError:
        return False


def _load_gsc_data() -> Optional[Dict]:
    """
    Carga datos de GSC. Orden de prioridad:
    1. Cache en session_state (si existe y es reciente)
    2. API de GSC (si configurada en secrets)
    3. CSV local (fallback)
    """
    # 1. Cache en session_state
    cached = st.session_state.get('gsc_opportunities_data')
    if cached is not None:
        return cached

    # 2. API de GSC
    if _is_api_configured():
        try:
            from utils.gsc_api import fetch_all_keywords
            api_data = fetch_all_keywords()
            if api_data and api_data.get('data'):
                st.session_state['gsc_opportunities_data'] = api_data
                return api_data
        except ImportError:
            logger.warning("fetch_all_keywords no disponible en gsc_api")
        except Exception as e:
            logger.warning(f"Error cargando GSC via API: {e}")

    # 3. CSV fallback
    try:
        from utils.gsc_utils import load_gsc_data
        csv_data = load_gsc_data()
        if csv_data:
            csv_data['source'] = 'csv'
            st.session_state['gsc_opportunities_data'] = csv_data
            return csv_data
    except ImportError:
        logger.warning("gsc_utils no disponible")
    except Exception as e:
        logger.warning(f"Error cargando GSC desde CSV: {e}")

    return None


def _clear_gsc_cache() -> None:
    """Limpia la caché de datos GSC para forzar recarga."""
    keys_to_clear = [k for k in st.session_state if k.startswith('gsc_')]
    for k in keys_to_clear:
        del st.session_state[k]


def _render_api_connect() -> None:
    """Botón para conectar con la API de GSC cuando las credenciales están disponibles."""
    st.info(
        "🔗 **API de Google Search Console detectada.** "
        "Las credenciales están configuradas en los secrets. "
        "Pulsa el botón para conectar y descargar tus datos."
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("📡 Conectar con GSC", key="gsc_connect_btn", type="primary", use_container_width=True):
            with st.spinner("Conectando con Google Search Console..."):
                # Primero testear la conexión
                try:
                    from utils.gsc_api import test_gsc_api_connection, fetch_all_keywords

                    test_result = test_gsc_api_connection()

                    if not test_result.get('success'):
                        st.error(f"❌ {test_result.get('message', 'Error de conexión')}")
                        return

                    st.success(f"✅ {test_result['message']}")

                    # Descargar datos
                    with st.spinner("Descargando keywords de GSC (esto puede tardar unos segundos)..."):
                        api_data = fetch_all_keywords()

                    if api_data and api_data.get('data'):
                        st.session_state['gsc_opportunities_data'] = api_data
                        st.success(
                            f"📊 {len(api_data['data'])} keywords descargadas "
                            f"({api_data.get('period', '')})"
                        )
                        st.rerun()
                    else:
                        st.warning(
                            "⚠️ La conexión fue exitosa pero no se obtuvieron datos. "
                            "Verifica que la propiedad tenga tráfico en los últimos 90 días."
                        )

                except ImportError as e:
                    st.error(
                        f"❌ Dependencias no instaladas: {e}. "
                        "Ejecuta: `pip install google-api-python-client google-auth`"
                    )
                except Exception as e:
                    st.error(f"❌ Error conectando con GSC: {e}")

    with col2:
        st.caption(
            "La conexión usa la Service Account configurada en secrets. "
            "Los datos se cachean 30 minutos para no saturar la API."
        )

    st.markdown("---")
    st.markdown("**Alternativa:** también puedes subir un CSV exportado desde GSC.")


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
