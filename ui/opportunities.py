# -*- coding: utf-8 -*-
"""
UI de Oportunidades SEO - PcComponentes Content Generator
Versión 1.2.0

Pantalla que combina datos de GSC con el OpportunityScorer para mostrar:
- Quick wins (posiciones 11-20 con alto volumen)
- Contenido con CTR bajo (underperformers)
- Keywords en declive (necesitan actualización)
- Tabla priorizada con score y recomendación por keyword

Cada oportunidad tiene un botón "Generar" que pre-rellena el modo
"Nuevo Contenido" o "Reescritura" según el tipo.

CAMBIOS v1.2.0:
- URL visible en cada tarjeta de oportunidad
- Botón "Análisis en profundidad" con tendencias 7d/28d/3mo
- Detección de SWAPs de URL entre períodos
- Comparativas de posición, clics e impresiones entre períodos
- Recomendaciones contextuales basadas en la tendencia

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

__version__ = "1.2.0"


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
        api_configured = _is_api_configured()

        if api_configured:
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

    for i, opp in enumerate(opportunities[:20], 1):
        _render_opportunity_card(i, opp, has_api=_is_api_configured())


# ============================================================================
# TARJETA DE OPORTUNIDAD (con URL y análisis)
# ============================================================================

def _render_opportunity_card(rank: int, opp: Dict[str, Any], has_api: bool = False) -> None:
    """Renderiza una tarjeta de oportunidad con URL, score y botones de acción."""
    current = opp['current']
    factors = opp['factors']
    keyword = opp['keyword']
    url = current.get('url', '')

    # Color según tipo
    type_icons = {
        'quick_win': '🟢',
        'improvement': '🔵',
        'underperformer': '🟡',
        'declining': '🔴',
        'new_content': '⚪',
    }
    icon = type_icons.get(opp['type'], '⚪')

    # Score badge
    score = opp['score']
    if score >= 70:
        score_display = f"🔥 **{score:.0f}/100**"
    elif score >= 50:
        score_display = f"📊 **{score:.0f}/100**"
    else:
        score_display = f"📉 {score:.0f}/100"

    # ── Fila principal ──
    with st.container():
        cols = st.columns([0.4, 4, 1.2, 1, 1, 1.4, 1.4])

        with cols[0]:
            st.markdown(f"**#{rank}**")
        with cols[1]:
            st.markdown(f"**{keyword}**")
            # URL visible
            if url:
                short_url = url.replace("https://www.pccomponentes.com", "")
                if len(short_url) > 60:
                    short_url = short_url[:57] + "..."
                st.caption(f"🔗 `{short_url}`")
            st.caption(
                f"{icon} {opp['type_label']} · "
                f"Pos. {current['position']:.0f} · "
                f"{current['impressions']} impr. · "
                f"{current.get('clicks', 0)} clics"
            )
        with cols[2]:
            st.markdown(score_display)
        with cols[3]:
            ctr_val = current.get('ctr', 0)
            ctr_pct = ctr_val * 100 if ctr_val < 1 else ctr_val
            st.caption(f"CTR: {ctr_pct:.1f}%")
        with cols[4]:
            st.caption(f"+{opp['potential_clicks']} clics pot.")
        with cols[5]:
            # Botón análisis en profundidad (solo si API disponible)
            if has_api:
                analysis_key = f"opp_analysis_{rank}_{keyword[:15]}"
                if st.button("🔍 Analizar", key=analysis_key, use_container_width=True):
                    st.session_state[f'show_analysis_{keyword}'] = True
        with cols[6]:
            action = "Reescribir" if url else "Generar"
            btn_key = f"opp_action_{rank}_{keyword[:15]}"
            if st.button(f"✏️ {action}", key=btn_key, use_container_width=True):
                _launch_generation(opp)

    # Recomendación
    st.caption(f"  💡 {opp['recommendation']}")

    # ── Panel de análisis en profundidad (desplegable) ──
    if st.session_state.get(f'show_analysis_{keyword}'):
        _render_deep_analysis(keyword, current)

    st.markdown("")  # Spacer


# ============================================================================
# ANÁLISIS EN PROFUNDIDAD
# ============================================================================

def _render_deep_analysis(keyword: str, current: Dict[str, Any]) -> None:
    """Renderiza el panel de análisis en profundidad con tendencias 7d/28d/3mo."""

    with st.container():
        st.markdown(f"---")
        st.markdown(f"#### 🔍 Análisis en profundidad: *{keyword}*")

        # Intentar obtener tendencias via API
        trends_data = _fetch_trends(keyword)

        if trends_data is None:
            st.info(
                "⚠️ No se pudieron obtener tendencias desde la API. "
                "Mostrando datos disponibles del dataset actual."
            )
            _render_basic_analysis(keyword, current)
            # Botón para cerrar
            if st.button("✕ Cerrar análisis", key=f"close_analysis_{keyword}"):
                del st.session_state[f'show_analysis_{keyword}']
                st.rerun()
            st.markdown("---")
            return

        periods = trends_data.get('periods', {})
        trends = trends_data.get('trends', {})

        # ── Métricas comparativas por período ──
        st.markdown("##### 📊 Comparativa por período")

        period_labels = {"7d": "Últimos 7 días", "28d": "Últimos 28 días", "90d": "Últimos 3 meses"}
        metric_cols = st.columns(3)

        for i, (period_key, label) in enumerate(period_labels.items()):
            with metric_cols[i]:
                p = periods.get(period_key, {})
                if p:
                    pos = p.get('position', 0)
                    clicks = p.get('clicks', 0)
                    impressions = p.get('impressions', 0)
                    ctr = p.get('ctr', 0)
                    ctr_pct = ctr * 100 if ctr < 1 else ctr

                    st.markdown(f"**{label}**")
                    st.metric("Posición", f"{pos:.1f}" if pos else "—")
                    st.metric("Clics", f"{clicks:,}")
                    st.metric("Impresiones", f"{impressions:,}")
                    st.metric("CTR", f"{ctr_pct:.1f}%")

                    # URL principal del período
                    top_url = p.get('top_url', '')
                    if top_url:
                        short = top_url.replace("https://www.pccomponentes.com", "")
                        if len(short) > 45:
                            short = short[:42] + "..."
                        st.caption(f"🔗 `{short}`")
                else:
                    st.markdown(f"**{label}**")
                    st.caption("Sin datos")

        # ── Indicadores de tendencia ──
        st.markdown("##### 📈 Tendencias")

        trend_cols = st.columns(4)

        # Cambio de posición 7d vs 28d
        pos_7_28 = trends.get('position_change_7d_vs_28d', 0)
        with trend_cols[0]:
            if pos_7_28 < -1:
                st.metric("Posición 7d vs 28d", f"{abs(pos_7_28):.1f}", delta=f"↑ mejora", delta_color="normal")
            elif pos_7_28 > 1:
                st.metric("Posición 7d vs 28d", f"{pos_7_28:.1f}", delta=f"↓ caída", delta_color="inverse")
            else:
                st.metric("Posición 7d vs 28d", "Estable", delta="0")

        # Cambio de posición 28d vs 90d
        pos_28_90 = trends.get('position_change_28d_vs_90d', 0)
        with trend_cols[1]:
            if pos_28_90 < -1:
                st.metric("Posición 28d vs 3mo", f"{abs(pos_28_90):.1f}", delta=f"↑ mejora", delta_color="normal")
            elif pos_28_90 > 1:
                st.metric("Posición 28d vs 3mo", f"{pos_28_90:.1f}", delta=f"↓ caída", delta_color="inverse")
            else:
                st.metric("Posición 28d vs 3mo", "Estable", delta="0")

        # Cambio de clics
        clicks_pct = trends.get('clicks_change_7d_vs_28d', 0)
        with trend_cols[2]:
            if abs(clicks_pct) > 5:
                direction = "↑" if clicks_pct > 0 else "↓"
                color = "normal" if clicks_pct > 0 else "inverse"
                st.metric("Clics 7d vs 28d", f"{abs(clicks_pct):.0f}%", delta=f"{direction}", delta_color=color)
            else:
                st.metric("Clics 7d vs 28d", "Estable", delta="0")

        # Cambio de impresiones
        impr_pct = trends.get('impressions_change_7d_vs_28d', 0)
        with trend_cols[3]:
            if abs(impr_pct) > 5:
                direction = "↑" if impr_pct > 0 else "↓"
                color = "normal" if impr_pct > 0 else "inverse"
                st.metric("Impresiones 7d vs 28d", f"{abs(impr_pct):.0f}%", delta=f"{direction}", delta_color=color)
            else:
                st.metric("Impresiones 7d vs 28d", "Estable", delta="0")

        # ── SWAPs de URL ──
        swaps = trends.get('url_swaps', [])
        if swaps:
            st.markdown("##### ⚠️ SWAPs de URL detectados")
            st.warning(
                "Google ha cambiado la URL que posiciona para esta keyword. "
                "Esto puede indicar canibalización o un cambio en la relevancia del contenido."
            )
            for swap in swaps:
                from_short = swap["from"].replace("https://www.pccomponentes.com", "")
                to_short = swap["to"].replace("https://www.pccomponentes.com", "")
                st.markdown(
                    f"**{swap['period']}:** "
                    f"`{from_short}` → `{to_short}`"
                )

        # ── URLs que posicionan ──
        p7_urls = periods.get("7d", {}).get("urls", [])
        if p7_urls and len(p7_urls) > 1:
            st.markdown("##### 🔗 URLs que compiten (últimos 7 días)")
            for u in p7_urls[:5]:
                short = u["url"].replace("https://www.pccomponentes.com", "")
                if len(short) > 55:
                    short = short[:52] + "..."
                st.caption(
                    f"`{short}` — "
                    f"Pos. {u['position']:.1f} · "
                    f"{u['clicks']} clics · "
                    f"{u['impressions']} impr."
                )

        # ── Análisis textual ──
        analysis_text = trends_data.get('analysis', '')
        if analysis_text:
            st.markdown("##### 💡 Diagnóstico")
            # Dirección general como badge
            direction = trends.get('direction', 'stable')
            direction_badges = {
                'improving': '🟢 **MEJORANDO**',
                'stable': '🔵 **ESTABLE**',
                'declining': '🔴 **EN DECLIVE**',
            }
            st.markdown(f"Estado general: {direction_badges.get(direction, '⚪ Desconocido')}")
            st.markdown(analysis_text)

        # Botón cerrar
        if st.button("✕ Cerrar análisis", key=f"close_analysis_{keyword}"):
            del st.session_state[f'show_analysis_{keyword}']
            st.rerun()

        st.markdown("---")


def _render_basic_analysis(keyword: str, current: Dict[str, Any]) -> None:
    """Análisis básico cuando no hay API disponible (solo datos del dataset)."""
    cols = st.columns(4)
    with cols[0]:
        st.metric("Posición", f"{current.get('position', 0):.0f}")
    with cols[1]:
        st.metric("Clics", f"{current.get('clicks', 0):,}")
    with cols[2]:
        st.metric("Impresiones", f"{current.get('impressions', 0):,}")
    with cols[3]:
        ctr = current.get('ctr', 0)
        ctr_pct = ctr * 100 if ctr < 1 else ctr
        st.metric("CTR", f"{ctr_pct:.1f}%")

    url = current.get('url', '')
    if url:
        st.caption(f"🔗 URL: `{url}`")

    st.info(
        "Para un análisis completo con tendencias 7d/28d/3mo y detección de SWAPs, "
        "conecta la API de GSC desde los secrets."
    )


def _fetch_trends(keyword: str) -> Optional[Dict]:
    """Obtiene tendencias de la API de GSC para una keyword."""
    try:
        from utils.gsc_api import fetch_keyword_trends, is_gsc_api_configured

        if not is_gsc_api_configured():
            return None

        return fetch_keyword_trends(keyword)
    except ImportError:
        logger.warning("fetch_keyword_trends no disponible")
        return None
    except Exception as e:
        logger.warning(f"Error obteniendo tendencias para '{keyword}': {e}")
        return None


# ============================================================================
# ACCIONES
# ============================================================================

def _launch_generation(opp: Dict[str, Any]) -> None:
    """Pre-rellena modo de generación y redirige."""
    current = opp['current']

    if current.get('url'):
        st.session_state.mode = 'rewrite'
        st.session_state['prefill_keyword'] = opp['keyword']
        st.session_state['prefill_url'] = current['url']
        st.info(
            f"📝 Keyword **{opp['keyword']}** configurada para reescritura. "
            f"Cambia al modo '🔄 Reescritura Competitiva' para continuar."
        )
    else:
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
    cached = st.session_state.get('gsc_opportunities_data')
    if cached is not None:
        return cached

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
                try:
                    from utils.gsc_api import test_gsc_api_connection, fetch_all_keywords

                    test_result = test_gsc_api_connection()

                    if not test_result.get('success'):
                        st.error(f"❌ {test_result.get('message', 'Error de conexión')}")
                        return

                    st.success(f"✅ {test_result['message']}")

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
            content = uploaded.getvalue().decode('utf-8')
            sep = ';' if content.count(';') > content.count(',') else ','

            import io
            df = pd.read_csv(io.StringIO(content), sep=sep)
            df.columns = df.columns.str.lower().str.strip()

            csv_path = "gsc_keywords.csv"
            df.to_csv(csv_path, index=False)
            st.success(f"✅ {len(df)} keywords cargadas. Recarga la página para ver oportunidades.")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Error procesando CSV: {e}")
