# -*- coding: utf-8 -*-
"""
UI de Oportunidades SEO - PcComponentes Content Generator
Versión 1.3.0

Pantalla que muestra oportunidades SEO exclusivamente para URLs del blog,
combinando datos de GSC con el OpportunityScorer para mostrar:
- Quick wins (posiciones 11-20 con alto volumen)
- Contenido con CTR bajo (underperformers)
- Keywords en declive (necesitan actualización)
- Tabla priorizada con score y recomendación por keyword

Cada oportunidad tiene un botón "Generar" que pre-rellena el modo
"Nuevo Contenido" o "Reescritura" según el tipo.

CAMBIOS v1.3.0:
- Filtrado obligatorio por blog: solo se muestran URLs del sitemap/blog.xml
- UI simplificada: tarjetas de 4 columnas, filtros de 3 columnas
- Resumen compacto en una línea
- Eliminado checkbox "Solo posts del blog" (ahora es siempre activo)

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

__version__ = "1.3.0"


def render_opportunities_mode() -> None:
    """Renderiza el modo de oportunidades SEO."""

    st.markdown("### 📊 Oportunidades SEO — Blog")
    st.markdown(
        "Oportunidades de contenido del **blog** de PcComponentes, "
        "basadas en datos de GSC. Solo se muestran URLs del blog (sitemap/blog.xml)."
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
    total_before_filter = len(records)
    if source == 'api':
        st.caption(f"📡 {total_before_filter} keywords desde GSC API · {period}")
    else:
        st.caption(f"📄 {total_before_filter} keywords desde CSV")

    # Botón para refrescar datos desde API
    if source == 'api':
        if st.button("🔄 Actualizar datos de GSC", key="gsc_refresh"):
            _clear_gsc_cache()
            st.rerun()

    # ================================================================
    # PASO 2: Filtros
    # ================================================================
    with st.expander("🔧 Filtros", expanded=False):
        keyword_filter = st.text_input(
            "🔍 Filtrar por keyword",
            placeholder="Ej: portátil, gaming, monitor...",
            key="opp_keyword_filter",
        )

        filter_cols = st.columns(3)
        with filter_cols[0]:
            min_impressions = st.number_input(
                "Impresiones mínimas", min_value=0, value=50, step=10,
            )
        with filter_cols[1]:
            position_range = st.slider(
                "Rango de posición", min_value=1, max_value=100,
                value=(1, 50),
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

    # Filtrar solo URLs del blog (sitemap/blog.xml)
    records = _filter_blog_records(records)
    if not records:
        st.warning(
            "⚠️ No se encontraron URLs del blog en los datos de GSC. "
            "Verifica que el sitemap del blog sea accesible."
        )
        return

    st.caption(f"📝 {len(records)} keywords vinculadas a posts del blog (de {total_before_filter} totales)")

    # Filtrar registros por métricas y keyword
    kw_filter_lower = keyword_filter.strip().lower() if keyword_filter else ""
    filtered = [
        r for r in records
        if r.get('impressions', 0) >= min_impressions
        and position_range[0] <= r.get('position', 0) <= position_range[1]
        and (not kw_filter_lower or kw_filter_lower in r.get('query', '').lower())
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
    # PASO 4: Resumen + tabla
    # ================================================================
    st.divider()

    type_counts = {}
    for opp in opportunities:
        t = opp['type']
        type_counts[t] = type_counts.get(t, 0) + 1

    qw = type_counts.get('quick_win', 0)
    imp = type_counts.get('improvement', 0)
    underp = type_counts.get('underperformer', 0) + type_counts.get('declining', 0)
    st.markdown(
        f"**{len(opportunities)} oportunidades** encontradas — "
        f"⚡ {qw} Quick Wins · 📈 {imp} Mejoras · 🔧 {underp} Necesitan atención"
    )

    for i, opp in enumerate(opportunities[:20], 1):
        _render_opportunity_card(i, opp, has_api=_is_api_configured())


# ============================================================================
# TARJETA DE OPORTUNIDAD (con URL y análisis)
# ============================================================================

def _render_opportunity_card(rank: int, opp: Dict[str, Any], has_api: bool = False) -> None:
    """Renderiza una tarjeta de oportunidad con URL, score y botones de acción."""
    current = opp['current']
    keyword = opp['keyword']
    url = current.get('url', '')

    type_icons = {
        'quick_win': '🟢',
        'improvement': '🔵',
        'underperformer': '🟡',
        'declining': '🔴',
        'new_content': '⚪',
    }
    icon = type_icons.get(opp['type'], '⚪')

    score = opp['score']
    if score >= 70:
        score_color = "🔥"
    elif score >= 50:
        score_color = "📊"
    else:
        score_color = "📉"

    ctr_val = current.get('ctr', 0)
    ctr_pct = ctr_val * 100 if ctr_val < 1 else ctr_val

    # URL corta
    short_url = ""
    if url:
        short_url = url.replace("https://www.pccomponentes.com", "")
        if len(short_url) > 70:
            short_url = short_url[:67] + "..."

    # ── Layout: info + métricas + acciones ──
    with st.container():
        cols = st.columns([0.3, 3.5, 2.5, 1.5])

        with cols[0]:
            st.markdown(f"**#{rank}**")

        with cols[1]:
            st.markdown(f"**{keyword}**")
            if short_url:
                st.caption(f"🔗 `{short_url}`")

        with cols[2]:
            st.caption(
                f"{icon} {opp['type_label']} · {score_color} {score:.0f}/100  \n"
                f"Pos. **{current['position']:.0f}** · "
                f"{current['impressions']} impr. · "
                f"{current.get('clicks', 0)} clics · "
                f"CTR {ctr_pct:.1f}%"
            )

        with cols[3]:
            action = "Reescribir" if url else "Generar"
            btn_key = f"opp_action_{rank}_{keyword[:15]}"
            if st.button(f"✏️ {action}", key=btn_key, use_container_width=True):
                _launch_generation(opp)
            if has_api:
                analysis_key = f"opp_analysis_{rank}_{keyword[:15]}"
                if st.button("🔍 Analizar", key=analysis_key, use_container_width=True):
                    st.session_state[f'show_analysis_{keyword}'] = True

    # Recomendación inline
    st.caption(f"💡 {opp['recommendation']}")

    # Panel de análisis en profundidad
    if st.session_state.get(f'show_analysis_{keyword}'):
        _render_deep_analysis(keyword, current)

    st.divider()


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

        # ── Enriquecimiento SEMrush + SerpAPI ──
        semrush_data, serp_data = _fetch_enrichment(keyword)

        if semrush_data:
            st.markdown("##### 📊 Datos SEMrush")
            sem_cols = st.columns(4)
            with sem_cols[0]:
                st.metric("Volumen de búsqueda", f"{semrush_data.get('search_volume', '—'):,}")
            with sem_cols[1]:
                st.metric("CPC", f"{semrush_data.get('cpc', '—')}€")
            with sem_cols[2]:
                st.metric("Competencia", f"{semrush_data.get('competition', '—')}")
            with sem_cols[3]:
                kd = semrush_data.get('keyword_difficulty')
                st.metric("Dificultad KW", f"{kd}" if kd is not None else "—")

        if serp_data:
            st.markdown("##### 🌐 SERP actual (top resultados)")
            for i, result in enumerate(serp_data.get('results', [])[:5], 1):
                title = result.get('title', '')
                domain = result.get('domain', '')
                st.caption(f"**{i}.** {title} — `{domain}`")

            if serp_data.get('related_searches'):
                st.markdown("**Búsquedas relacionadas:** " + ", ".join(
                    f"`{s}`" for s in serp_data['related_searches'][:8]
                ))

        # ── Análisis textual ──
        analysis_text = trends_data.get('analysis', '')
        if analysis_text:
            st.markdown("##### 💡 Diagnóstico")
            direction = trends.get('direction', 'stable')
            direction_badges = {
                'improving': '🟢 **MEJORANDO**',
                'stable': '🔵 **ESTABLE**',
                'declining': '🔴 **EN DECLIVE**',
            }
            st.markdown(f"Estado general: {direction_badges.get(direction, '⚪ Desconocido')}")
            st.markdown(analysis_text)

        # ── Botón reescribir con todo el contexto enriquecido ──
        top_url = periods.get("7d", {}).get("top_url", "") or current.get("url", "")
        if top_url:
            rewrite_key = f"opp_rewrite_enriched_{keyword[:15]}"
            if st.button(
                "✏️ Reescribir con contexto enriquecido",
                key=rewrite_key, type="primary", use_container_width=False,
            ):
                _launch_enriched_rewrite(
                    keyword, top_url, trends_data, semrush_data, serp_data
                )

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
# BLOG SITEMAP FILTER
# ============================================================================

def _filter_blog_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filtra registros GSC para quedarse solo con URLs del blog."""
    try:
        from utils.blog_sitemap import filter_blog_opportunities
        blog_records = filter_blog_opportunities(records)
        logger.info(f"Blog filter: {len(records)} → {len(blog_records)} registros")
        return blog_records
    except ImportError:
        logger.warning("blog_sitemap no disponible")
        return records
    except Exception as e:
        logger.warning(f"Error filtrando blog: {e}")
        return records


# ============================================================================
# ENRIQUECIMIENTO SEMrush + SerpAPI
# ============================================================================

def _fetch_enrichment(
    keyword: str,
) -> tuple:
    """
    Enriquece el análisis con datos de SEMrush y SerpAPI.

    Returns:
        Tuple[Optional[Dict], Optional[Dict]]: (semrush_data, serp_data)
    """
    semrush_data = _fetch_semrush_data(keyword)
    serp_data = _fetch_serp_data(keyword)
    return semrush_data, serp_data


def _fetch_semrush_data(keyword: str) -> Optional[Dict]:
    """Obtiene datos de SEMrush para una keyword."""
    # Cache
    cache_key = f"opp_semrush_{keyword.strip().lower()}"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached

    try:
        import os
        api_key = os.environ.get('SEMRUSH_API_KEY', '')
        if not api_key:
            try:
                api_key = st.secrets.get('semrush', {}).get('api_key', '')
            except Exception:
                pass

        if not api_key:
            return None

        from core.semrush import SEMrushClient

        client = SEMrushClient(api_key=api_key, database='es')

        # Keyword overview
        overview = client.get_keyword_overview(keyword)
        result = {}

        if overview and overview.success and overview.data:
            # SEMrush devuelve TSV con headers
            lines = overview.data.strip().split('\n')
            if len(lines) >= 2:
                headers = lines[0].split(';')
                values = lines[1].split(';')
                row = dict(zip(headers, values))
                result['search_volume'] = int(row.get('Search Volume', '0') or '0')
                result['cpc'] = row.get('CPC', '0')
                result['competition'] = row.get('Competition', '—')
                result['results_count'] = row.get('Number of Results', '0')

        # Keyword difficulty
        try:
            kd_response = client.get_keyword_difficulty(keyword)
            if kd_response and kd_response.success and kd_response.data:
                kd_lines = kd_response.data.strip().split('\n')
                if len(kd_lines) >= 2:
                    kd_headers = kd_lines[0].split(';')
                    kd_values = kd_lines[1].split(';')
                    kd_row = dict(zip(kd_headers, kd_values))
                    result['keyword_difficulty'] = kd_row.get('Keyword Difficulty', None)
        except Exception:
            pass

        if result:
            st.session_state[cache_key] = result
            return result

    except ImportError:
        logger.debug("SEMrush module not available")
    except Exception as e:
        logger.warning(f"Error SEMrush para '{keyword}': {e}")

    return None


def _fetch_serp_data(keyword: str) -> Optional[Dict]:
    """Obtiene datos de SerpAPI para una keyword."""
    # Cache
    cache_key = f"opp_serp_{keyword.strip().lower()}"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        return cached

    try:
        from utils.serp_research import search_serp

        results, related = search_serp(keyword, max_results=10)

        if not results:
            return None

        serp_data = {
            "results": [
                {
                    "title": r.title,
                    "url": r.url,
                    "domain": r.domain,
                    "position": r.position,
                    "snippet": r.snippet[:150] if r.snippet else "",
                }
                for r in results[:10]
            ],
            "related_searches": related[:10] if related else [],
        }

        st.session_state[cache_key] = serp_data
        return serp_data

    except ImportError:
        logger.debug("serp_research module not available")
    except Exception as e:
        logger.warning(f"Error SerpAPI para '{keyword}': {e}")

    return None


# ============================================================================
# REESCRITURA CON CONTEXTO ENRIQUECIDO
# ============================================================================

def _launch_enriched_rewrite(
    keyword: str,
    url: str,
    trends_data: Optional[Dict],
    semrush_data: Optional[Dict],
    serp_data: Optional[Dict],
) -> None:
    """
    Lanza modo reescritura con contexto completo del análisis.
    Guarda todo el contexto enriquecido en session_state para que
    el prompt de reescritura lo use.
    """
    # Construir contexto enriquecido para el prompt
    context_lines = [f"## Contexto de análisis de oportunidad para: {keyword}\n"]

    # Tendencias GSC
    if trends_data:
        periods = trends_data.get('periods', {})
        trends = trends_data.get('trends', {})

        context_lines.append("### Datos GSC (tendencias)")
        for label, period_key in [("7 días", "7d"), ("28 días", "28d"), ("3 meses", "90d")]:
            p = periods.get(period_key, {})
            if p:
                ctr_pct = p.get('ctr', 0) * 100 if p.get('ctr', 0) < 1 else p.get('ctr', 0)
                context_lines.append(
                    f"- **{label}:** Pos. {p.get('position', '—')} · "
                    f"{p.get('clicks', 0)} clics · {p.get('impressions', 0)} impr. · "
                    f"CTR {ctr_pct:.1f}%"
                )

        direction = trends.get('direction', 'stable')
        context_lines.append(f"- **Tendencia general:** {direction}")

        swaps = trends.get('url_swaps', [])
        if swaps:
            context_lines.append("- **SWAPs de URL detectados** — Google ha cambiado la URL principal")
            for s in swaps:
                context_lines.append(f"  - {s['period']}: {s['from']} → {s['to']}")

        analysis = trends_data.get('analysis', '')
        if analysis:
            context_lines.append(f"\n{analysis}")

    # SEMrush
    if semrush_data:
        context_lines.append("\n### Datos SEMrush")
        if semrush_data.get('search_volume'):
            context_lines.append(f"- Volumen de búsqueda: {semrush_data['search_volume']:,}")
        if semrush_data.get('cpc'):
            context_lines.append(f"- CPC: {semrush_data['cpc']}€")
        if semrush_data.get('keyword_difficulty'):
            context_lines.append(f"- Dificultad KW: {semrush_data['keyword_difficulty']}")
        if semrush_data.get('competition'):
            context_lines.append(f"- Competencia: {semrush_data['competition']}")

    # SerpAPI
    if serp_data:
        context_lines.append("\n### SERP actual (top competidores)")
        for r in serp_data.get('results', [])[:5]:
            context_lines.append(f"- **{r.get('title', '')}** (`{r.get('domain', '')}`)")
        if serp_data.get('related_searches'):
            context_lines.append(
                f"\n**Búsquedas relacionadas:** {', '.join(serp_data['related_searches'][:8])}"
            )

    enriched_context = "\n".join(context_lines)

    # Guardar en session_state para el modo reescritura
    st.session_state.mode = 'rewrite'
    st.session_state['rewrite_keyword_input'] = keyword
    st.session_state['prefill_keyword'] = keyword
    st.session_state['prefill_url'] = url
    st.session_state['prefill_analysis_context'] = enriched_context

    st.success(
        f"✏️ Keyword **{keyword}** configurada para reescritura con contexto enriquecido "
        f"(GSC + {'SEMrush + ' if semrush_data else ''}{'SerpAPI' if serp_data else 'tendencias'}). "
        f"Cambia al modo '🔄 Reescritura Competitiva'."
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
