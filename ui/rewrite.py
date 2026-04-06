# -*- coding: utf-8 -*-
"""
UI de Reescritura - PcComponentes Content Generator
Versión 4.7.1

Este módulo maneja la interfaz de usuario para el modo REESCRITURA,
que analiza contenido competidor y genera una versión mejorada.

CAMBIOS v4.7.1:
- Productos Alternativos: checkbox opcional + N productos con JSON cada uno (nuevo paso 8)
- Enlaces Posts/PLPs: selector tipo (Post/PLP) + campos HTML específicos
  - PLP: Top text + Bottom text (dos campos)
  - Post: Un campo HTML único
- Eliminado JSON de productos en enlaces editoriales (no necesario)

CAMBIOS v4.7.0:
- NUEVO: Paso 2 ahora es HTML a Reescribir (antes era Producto Principal)
- NUEVO: Instrucciones detalladas de reescritura (qué mejorar, mantener, eliminar)
- NUEVO: Modo Fusión de Artículos (para canibalizaciones con múltiples URLs)
- NUEVO: Modo Desambiguación (separar contenido Post vs PLP)
- NUEVO: Soporte para múltiples HTMLs a fusionar
- Todos los 34 arquetipos disponibles
- JSON con tabs (subir/pegar) en todos los enlaces

Flujo actualizado:
1. Input de keyword principal + Verificación GSC
2. Contenido HTML a reescribir (con opciones de fusión/desambiguación)
3. Instrucciones de reescritura (qué mejorar, mantener, eliminar)
4. Producto Principal (opcional con JSON)
5. Obtención de competidores (SEMrush API o manual)
6. Configuración de parámetros (con arquetipo completo)
7. Enlaces a posts/PLPs (con HTML contextual) y productos (con JSON)
8. Productos Alternativos (opcional con JSON cada uno) - NUEVO v4.7.1
9. Generación del contenido mejorado

Autor: PcComponentes - Product Discovery & Content
"""

import streamlit as st
from typing import Dict, List, Optional, Tuple, Any
import html as html_module
import json
import logging
import unicodedata
from datetime import datetime
import re

logger = logging.getLogger(__name__)

# Importar utilidades
from utils.html_utils import count_words_in_html

# Importar configuración
from config.settings import (
    GSC_VERIFICATION_ENABLED,
    SEMRUSH_ENABLED,
    SEMRUSH_API_KEY
)

# Importar arquetipos - TODOS los 34
try:
    from config.arquetipos import (
        ARQUETIPOS,
        get_arquetipo,
        get_arquetipo_names,
        get_guiding_questions,
        get_default_length,
        get_length_range,
        get_structure,
        get_tone,
    )
    _arquetipos_available = True
except ImportError:
    _arquetipos_available = False
    ARQUETIPOS = {}
    def get_arquetipo(code): return None
    def get_arquetipo_names(): return {}
    def get_guiding_questions(code, include_universal=True): return []
    def get_default_length(code): return 1500
    def get_length_range(code): return (800, 3000)
    def get_structure(code): return []
    def get_tone(code): return ""

# Importar sección GSC (con manejo de errores)
try:
    from ui.gsc_section import render_gsc_verification_section
    GSC_AVAILABLE = True
except ImportError:
    GSC_AVAILABLE = False

# Importar cliente SEMrush
try:
    from core.semrush import (
        SEMrushClient,
        SEMrushResponse,
        CompetitorData,
        format_competitors_for_display,
        is_semrush_available
    )
    SEMRUSH_MODULE_AVAILABLE = True
except ImportError:
    SEMRUSH_MODULE_AVAILABLE = False
    def is_semrush_available(): return False

# Importar utilidades de JSON de productos
try:
    from utils.product_json_utils import (
        parse_product_json,
        validate_product_json,
        format_product_for_prompt,
        create_product_summary,
    )
    _product_json_available = True
except ImportError:
    _product_json_available = False


# ============================================================================
# VERSIÓN Y CONSTANTES
# ============================================================================

__version__ = "4.7.1"

MAX_COMPETITORS = 10
DEFAULT_REWRITE_LENGTH = 1600
COMPETITION_BEAT_FACTOR = 1.2
MAX_ARTICLES_TO_MERGE = 5
MAX_ALTERNATIVE_PRODUCTS = 10  # NUEVO v4.7.1
MAX_EDITORIAL_LINKS = 10  # NUEVO v4.7.1
MAX_PRODUCT_LINKS = 10  # NUEVO v4.7.1


# ============================================================================
# MODOS DE REESCRITURA
# ============================================================================

class RewriteMode:
    """Modos de reescritura disponibles."""
    SINGLE = "single"           # Reescribir un solo artículo
    MERGE = "merge"             # Fusionar múltiples artículos (canibalización)
    DISAMBIGUATE = "disambiguate"  # Desambiguar post vs PLP


REWRITE_MODE_OPTIONS = {
    RewriteMode.SINGLE: {
        "name": "📝 Reescribir artículo",
        "description": "Mejora un artículo existente manteniendo su esencia",
        "help": "Ideal para actualizar contenido obsoleto o mejorar posicionamiento"
    },
    RewriteMode.MERGE: {
        "name": "🔀 Fusionar artículos",
        "description": "Combina varios artículos que canibalizan la misma keyword",
        "help": "Para resolver canibalizaciones: crea UN contenido definitivo a partir de varios"
    },
    RewriteMode.DISAMBIGUATE: {
        "name": "🎯 Desambiguar contenido",
        "description": "Separa contenido editorial (post) de contenido transaccional (PLP)",
        "help": "Cuando un post está robando tráfico a una PLP o viceversa"
    }
}


# ============================================================================
# TIPOS DE CONTENIDO EDITORIAL (NUEVO v4.7.1)
# ============================================================================

class EditorialType:
    """Tipos de contenido editorial para enlaces."""
    POST = "post"
    PLP = "plp"


EDITORIAL_TYPE_OPTIONS = {
    EditorialType.POST: {
        "name": "📝 Post / Guía / Blog",
        "description": "Contenido editorial con un único bloque HTML",
        "placeholder": """<article>
  <h1>Título del post...</h1>
  <p>Contenido del post que servirá de contexto para enlazar...</p>
</article>"""
    },
    EditorialType.PLP: {
        "name": "🛒 PLP / Categoría",
        "description": "Página de listado con Top text y Bottom text",
        "placeholder_top": """<div class="category-top">
  <h1>Portátiles Gaming</h1>
  <p>Descubre nuestra selección de portátiles gaming...</p>
</div>""",
        "placeholder_bottom": """<div class="category-bottom">
  <h2>¿Cómo elegir tu portátil gaming?</h2>
  <p>A la hora de elegir un portátil gaming...</p>
</div>"""
    }
}


# ============================================================================
# FUNCIÓN PRINCIPAL DE RENDERIZADO
# ============================================================================


def _render_gsc_api_results(urls: List[Dict], check: Dict, suffix: str = "") -> None:
    """Renderiza los resultados de la API de GSC (evita duplicación de código).

    Args:
        urls: Lista de dicts con datos de URLs de GSC.
        check: Dict con resumen de la consulta (total_clicks, period_days...).
        suffix: Texto extra para el caption (ej. "(cacheado)").
    """
    period = check.get('period_days', 7)
    caption = f"Datos en tiempo real — últimos {period} días"
    if suffix:
        caption += f" {suffix}"

    st.markdown("### 🔍 Verificación en Google Search Console")
    st.caption(caption)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("URLs encontradas", len(urls))
    with c2:
        st.metric("Clicks totales", check.get('total_clicks', 0))
    with c3:
        best_pos = min(u.get('position', 100) for u in urls) if urls else 100
        st.metric("Mejor posición", f"#{best_pos:.1f}")

    html_rows = []
    for u in urls[:8]:
        safe_url = html_module.escape(u.get('url', ''), quote=True)
        safe_query = html_module.escape(u.get('query', ''), quote=True)
        score_icon = '🎯' if u.get('match_score', 0) >= 80 else '🔹'
        html_rows.append(
            f'{score_icon} <a href="{safe_url}" target="_blank" '
            f'rel="noopener" style="color:#1a73e8;word-break:break-all;">{safe_url}</a>'
            f'<br><small style="margin-left:20px;">'
            f'Query: <em>{safe_query}</em> · '
            f'{u.get("clicks", 0)} clicks · '
            f'{u.get("impressions", 0)} imp · '
            f'Pos. {u.get("position", 0):.1f}</small>'
        )
    st.markdown(
        '<div style="margin:10px 0;font-size:14px;">'
        + '<br>'.join(html_rows) + '</div>',
        unsafe_allow_html=True,
    )


def render_rewrite_section() -> Tuple[bool, Dict]:
    """
    Renderiza la sección completa del modo reescritura.
    
    Flujo v5.1 (reordenado para coherencia):
    - Paso 1: Keyword + GSC
    - Paso 2: Configuración (Arquetipo, Briefing, Objetivo, Longitud, Keywords)
    - Paso 3: Contenido HTML a reescribir
    - Paso 4: Instrucciones de reescritura (3 campos simplificados)
    - Paso 5: Competidores
    - Paso 6: Productos + Enlaces editoriales
    
    Returns:
        Tuple[bool, Dict]: (debe_generar, config_dict)
    """
    
    # Determinar método de obtención de competidores
    semrush_available = SEMRUSH_MODULE_AVAILABLE and is_semrush_available()

    # Indicador compacto de estado
    _semrush_label = "SEMrush conectada" if semrush_available else "Competidores manuales"
    st.caption(f"{'✅' if semrush_available else '📝'} {_semrush_label}")
    
    # Inicializar estado si no existe
    _initialize_rewrite_state()
    
    # Procesar eliminaciones pendientes ANTES de renderizar widgets
    _process_pending_deletions()
    
    # =========================================================================
    # PASO 1: Keyword y verificación GSC
    # =========================================================================
    st.markdown("##### 1. Keyword Principal")
    
    keyword, should_search = render_keyword_input()
    
    # Verificación GSC: API en tiempo real (7 días) → fallback gsc_section (CSV)
    gsc_analysis = None
    if keyword and len(keyword.strip()) >= 3:
        st.markdown("---")
        
        # Normalizar keyword (eliminar ZWS y otros chars invisibles)
        _kw_clean = ' '.join(
            ''.join(c for c in keyword if unicodedata.category(c) not in ('Cf', 'Cc') or c in ('\n', '\t'))
            .split()
        ).strip().lower()
        _rw_cache_key = f"_rewrite_gsc_{_kw_clean}"
        _cached_gsc = st.session_state.get(_rw_cache_key)
        
        if _cached_gsc is not None:
            # Usar resultado cacheado
            gsc_analysis = _cached_gsc.get("analysis")
            _used_api = _cached_gsc.get("used_api", False)
            if _used_api and gsc_analysis and gsc_analysis.get('has_matches'):
                # Re-renderizar desde cache
                check = _cached_gsc.get("check", {})
                urls = check.get('urls', [])
                period = check.get('period_days', 7)
                
                _render_gsc_api_results(urls, check, suffix="(cacheado)")
            elif not _used_api and GSC_AVAILABLE and gsc_analysis:
                # CSV fallback fue usado — re-renderizar via gsc_section
                render_gsc_verification_section(keyword=keyword, show_disclaimer=True)
        else:
            # Primera llamada — ejecutar y cachear
            _used_api = False
            check = {}  # Inicializar para evitar UnboundLocalError
            try:
                from utils.gsc_api import is_gsc_api_configured as _is_api_ok, quick_keyword_check as _quick_check
                if _is_api_ok():
                    check = _quick_check(keyword, days_back=7)
                    if check.get('has_data') and check.get('urls'):
                        _used_api = True
                        urls = check['urls']
                        period = check.get('period_days', 7)
                        
                        _render_gsc_api_results(urls, check)

                        gsc_analysis = {
                            'has_matches': True,
                            'matches': [
                                {'url': u['url'], 'query': u.get('query',''), 
                                 'clicks': u.get('clicks',0), 'impressions': u.get('impressions',0),
                                 'position': u.get('position',0)}
                                for u in urls
                            ],
                            'recommendation': 'already_ranking_well' if (
                                any(u.get('position', 100) <= 10 for u in urls)
                            ) else 'related_content',
                            'data_source': 'gsc_api',
                        }
            except (ImportError, Exception) as e:
                logger.debug(f"GSC API en rewrite falló: {e}")
            
            # Intento 2: Fallback a gsc_section (CSV)
            if not _used_api and GSC_AVAILABLE:
                # Si la API está configurada, no mostrar disclaimer del CSV viejo
                _api_configured = False
                try:
                    from utils.gsc_api import is_gsc_api_configured as _is_api_check
                    _api_configured = _is_api_check()
                except (ImportError, Exception):
                    pass
                
                try:
                    gsc_analysis = render_gsc_verification_section(
                        keyword=keyword,
                        show_disclaimer=not _api_configured,
                    )
                except Exception as e:
                    logger.warning(f"GSC CSV fallback falló: {e}")
                    gsc_analysis = None
            
            # Cachear resultado
            st.session_state[_rw_cache_key] = {
                "analysis": gsc_analysis,
                "used_api": _used_api,
                "check": check if _used_api else {},
            }
        
        st.session_state.rewrite_gsc_analysis = gsc_analysis
        
        if gsc_analysis and gsc_analysis.get('has_matches'):
            if gsc_analysis.get('recommendation') == 'already_ranking_well':
                st.warning("""
                ⚠️ **Precaución**: Ya rankeas en top 10 para esta keyword.
                
                Considera si realmente necesitas crear contenido nuevo o si deberías 
                mejorar el contenido existente.
                """)
            
            urls_ranking = gsc_analysis.get('matches', [])
            if len(set(m.get('url') for m in urls_ranking)) > 1:
                st.info("""
                💡 **Detectadas múltiples URLs rankeando** - Considera usar el modo 
                **🔀 Fusionar artículos** para consolidar el contenido y evitar canibalización.
                """)
    
    # =========================================================================
    # PASO 2: Configuración del Contenido
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 2. Configuración del Contenido")
    
    rewrite_config = render_rewrite_configuration(keyword, RewriteMode.SINGLE)
    
    # =========================================================================
    # PASO 3: Contenido HTML a Reescribir
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 3. Contenido a Reescribir")
    
    rewrite_mode, html_contents, disambiguation_config = render_html_content_section()
    
    # Actualizar rewrite_config con el modo real (puede haber cambiado)
    # (render_rewrite_configuration usó SINGLE como default, pero aquí tenemos el modo real)
    
    # =========================================================================
    # PASO 4: Instrucciones de Reescritura
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 4. Instrucciones de Reescritura")
    
    rewrite_instructions = render_rewrite_instructions_section(rewrite_mode)
    
    # =========================================================================
    # PASO 5: Obtener competidores
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 5. Competidores")
    
    if semrush_available:
        # Modo SEMrush automático
        if should_search and keyword:
            _fetch_competitors_semrush(keyword, gsc_analysis)
    else:
        # Modo manual
        render_manual_competitors_input(keyword)
    
    # Mostrar competidores si existen
    if st.session_state.rewrite_competitors_data:
        render_competitors_summary(st.session_state.rewrite_competitors_data)
    
    # =========================================================================
    # PASO 6: Productos + Enlaces Editoriales
    # =========================================================================
    st.markdown("---")
    st.markdown("##### 6. Productos y Enlaces *(opcional)*")
    
    # Productos
    try:
        from ui.inputs import render_products_block, ProductEntry
    except ImportError:
        from inputs import render_products_block, ProductEntry
    
    rewrite_products = render_products_block(key_prefix="rewrite_products")
    
    # Backward compat: derivar main_product_data y alternative_products
    main_product_data = None
    alternative_products = []
    
    if rewrite_products:
        first_principal = next((p for p in rewrite_products if p.role == "principal"), None)
        if first_principal:
            main_product_data = {
                'url': first_principal.url or '',
                'json_data': first_principal.json_data,
            }
        
        for p in rewrite_products:
            if p.role == "alternativo":
                alt_dict = {
                    'url': p.url or '',
                    'name': p.name or '',
                    'json_data': p.json_data,
                }
                alternative_products.append(alt_dict)
    
    # Enlaces editoriales
    with st.expander("📝 Enlaces a Posts / PLPs (Contenido Editorial)", expanded=False):
        st.caption("Añade el HTML del contenido destino para que los enlaces sean más contextuales y naturales.")
        posts_plps_links = render_posts_plps_links_section()
    
    product_links = []  # Backward compat
    
    # =========================================================================
    # VALIDAR Y PREPARAR
    # =========================================================================
    
    # Validar que todo esté listo para generar
    can_generate = validate_rewrite_inputs(
        keyword,
        st.session_state.rewrite_competitors_data,
        rewrite_config,
        gsc_analysis,
        html_contents,
        rewrite_mode,
        rewrite_instructions
    )
    
    st.markdown("---")
    
    if not can_generate:
        st.warning("⚠️ Completa los campos obligatorios para poder generar el contenido.")
        return False, {}
    
    # Mostrar resumen antes de generar
    render_generation_summary(
        keyword, rewrite_config, gsc_analysis, html_contents, 
        main_product_data, rewrite_mode, rewrite_instructions,
        alternative_products, posts_plps_links
    )
    
    # Preparar configuración completa (el botón está en app.py)
    full_config = prepare_rewrite_config(
        keyword=keyword,
        competitors_data=st.session_state.rewrite_competitors_data,
        rewrite_config=rewrite_config,
        gsc_analysis=gsc_analysis,
        html_contents=html_contents,
        rewrite_mode=rewrite_mode,
        rewrite_instructions=rewrite_instructions,
        disambiguation_config=disambiguation_config,
        main_product_data=main_product_data,
        posts_plps_links=posts_plps_links,
        product_links=product_links,
        alternative_products=alternative_products,
        products=rewrite_products,
    )
    
    return True, full_config


# ============================================================================
# INICIALIZACIÓN DE ESTADO
# ============================================================================

def _initialize_rewrite_state() -> None:
    """Inicializa variables de estado para el modo rewrite."""
    
    if 'rewrite_competitors_data' not in st.session_state:
        st.session_state.rewrite_competitors_data = None
    if 'rewrite_analysis' not in st.session_state:
        st.session_state.rewrite_analysis = None
    if 'rewrite_gsc_analysis' not in st.session_state:
        st.session_state.rewrite_gsc_analysis = None
    if 'last_rewrite_keyword' not in st.session_state:
        st.session_state.last_rewrite_keyword = ''
    if 'manual_urls_input' not in st.session_state:
        st.session_state.manual_urls_input = ''
    if 'semrush_response' not in st.session_state:
        st.session_state.semrush_response = None
    # Estado para modo de reescritura
    if 'rewrite_mode' not in st.session_state:
        st.session_state.rewrite_mode = RewriteMode.SINGLE
    # Estado para HTMLs (puede ser uno o múltiples)
    if 'html_contents' not in st.session_state:
        st.session_state.html_contents = []
    if 'html_articles_count' not in st.session_state:
        st.session_state.html_articles_count = 1
    # Estado para enlaces
    if 'rewrite_posts_plps_count' not in st.session_state:
        st.session_state.rewrite_posts_plps_count = 1
    if 'rewrite_product_links_count' not in st.session_state:
        st.session_state.rewrite_product_links_count = 1
    # Estado para producto principal
    if 'rewrite_main_product_enabled' not in st.session_state:
        st.session_state.rewrite_main_product_enabled = False
    if 'rewrite_main_product_json' not in st.session_state:
        st.session_state.rewrite_main_product_json = None
    # Estado para productos alternativos (NUEVO v4.7.1)
    if 'rewrite_alt_products_enabled' not in st.session_state:
        st.session_state.rewrite_alt_products_enabled = False
    if 'rewrite_alt_products_count' not in st.session_state:
        st.session_state.rewrite_alt_products_count = 1


# ============================================================================
# SECCIÓN: CONTENIDO HTML A REESCRIBIR (MEJORADA)
# ============================================================================

def render_html_content_section() -> Tuple[str, List[Dict[str, Any]], Optional[Dict]]:
    """
    Renderiza la sección de contenido HTML con opciones de:
    - Reescritura simple
    - Fusión de artículos
    - Desambiguación
    
    Returns:
        Tuple[mode, html_contents, disambiguation_config]
        - mode: Modo de reescritura (single/merge/disambiguate)
        - html_contents: Lista de dicts con {url, html, title, word_count}
        - disambiguation_config: Config para desambiguación (si aplica)
    """
    
    # Selector de modo
    st.markdown("**¿Qué quieres hacer?**")
    
    mode_options = list(REWRITE_MODE_OPTIONS.keys())
    mode_labels = [REWRITE_MODE_OPTIONS[m]["name"] for m in mode_options]
    
    selected_mode_idx = st.radio(
        "Modo de reescritura",
        options=range(len(mode_options)),
        format_func=lambda x: mode_labels[x],
        horizontal=True,
        key="rewrite_mode_selector",
        label_visibility="collapsed"
    )
    
    selected_mode = mode_options[selected_mode_idx]
    st.session_state.rewrite_mode = selected_mode
    
    # Mostrar descripción del modo
    mode_info = REWRITE_MODE_OPTIONS[selected_mode]
    st.caption(f"ℹ️ {mode_info['description']}")
    
    html_contents = []
    disambiguation_config = None
    
    # =========================================================================
    # MODO: Reescribir artículo único
    # =========================================================================
    if selected_mode == RewriteMode.SINGLE:
        html_contents = render_single_article_input()
    
    # =========================================================================
    # MODO: Fusionar artículos
    # =========================================================================
    elif selected_mode == RewriteMode.MERGE:
        html_contents = render_merge_articles_input()
    
    # =========================================================================
    # MODO: Desambiguar contenido
    # =========================================================================
    elif selected_mode == RewriteMode.DISAMBIGUATE:
        html_contents, disambiguation_config = render_disambiguate_input()
    
    return selected_mode, html_contents, disambiguation_config


def render_single_article_input() -> List[Dict[str, Any]]:
    """
    Renderiza input para un solo artículo a reescribir.
    
    Returns:
        Lista con un solo dict {url, html, title, word_count}
    """
    
    st.caption("Pega el código HTML del artículo que quieres mejorar. "
               "Si lo dejas vacío, se generará contenido nuevo basado en competidores.")

    # URL del artículo original
    article_url = st.text_input(
        "URL del artículo original",
        key="rewrite_single_url",
        placeholder="https://www.pccomponentes.com/blog/...",
        help="URL actual del artículo (para referencia)"
    )
    
    # Título del artículo
    article_title = st.text_input(
        "Título del artículo",
        key="rewrite_single_title",
        placeholder="Título actual del artículo",
        help="Título H1 del artículo actual"
    )
    
    # HTML del artículo
    html_content = st.text_area(
        "Código HTML del artículo",
        value=st.session_state.get('html_to_rewrite', ''),
        height=200,
        key="rewrite_single_html",
        placeholder="""<article>
  <h1>Título del artículo...</h1>
  <p>Contenido...</p>
</article>""",
        help="Pega el código HTML completo del artículo"
    )
    
    # Guardar en session state
    st.session_state.html_to_rewrite = html_content
    
    # Mostrar estadísticas si hay contenido
    if html_content and html_content.strip():
        _show_html_stats(html_content)
        
        return [{
            'url': article_url.strip() if article_url else '',
            'html': html_content,
            'title': article_title.strip() if article_title else '',
            'word_count': len(_strip_html_tags(html_content).split()),
            'type': 'main'
        }]
    
    return []


def render_merge_articles_input() -> List[Dict[str, Any]]:
    """
    Renderiza input para múltiples artículos a fusionar.
    
    Returns:
        Lista de dicts {url, html, title, word_count, priority}
    """
    
    st.markdown("""
    **🔀 Fusión de Artículos**
    
    Añade todos los artículos que están canibalizando la misma keyword.
    Se creará UN único contenido definitivo que consolide lo mejor de cada uno.
    """)
    
    st.info("""
    💡 **Tips para fusionar:**
    - Ordena los artículos por **prioridad** (el primero será la base principal)
    - Indica qué **secciones únicas** de cada artículo deben conservarse
    - El nuevo contenido tendrá una estructura coherente sin duplicidades
    """)
    
    count_key = 'html_articles_count'
    current_count = st.session_state.get(count_key, 2)  # Mínimo 2 para fusión
    
    if current_count < 2:
        st.session_state[count_key] = 2
        current_count = 2
    
    html_contents = []
    
    for i in range(current_count):
        priority_label = "🥇 Principal" if i == 0 else f"🔗 Artículo {i + 1}"
        
        with st.expander(f"{priority_label}", expanded=(i < 2)):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                url = st.text_input(
                    f"URL del artículo {i+1}",
                    key=f"merge_url_{i}",
                    placeholder="https://www.pccomponentes.com/...",
                    help="URL actual del artículo"
                )
            
            with col2:
                title = st.text_input(
                    f"Título {i+1}",
                    key=f"merge_title_{i}",
                    placeholder="Título del artículo",
                    help="Título H1"
                )
            
            html = st.text_area(
                f"HTML del artículo {i+1}",
                height=150,
                key=f"merge_html_{i}",
                placeholder="<article>...</article>",
                help="Código HTML del artículo"
            )
            
            # Notas sobre qué conservar de este artículo
            keep_notes = st.text_input(
                f"¿Qué conservar de este artículo?",
                key=f"merge_keep_{i}",
                placeholder="Ej: La sección de comparativa, los datos técnicos...",
                help="Indica qué partes únicas de este artículo deben incluirse en el fusionado"
            )
            
            if html and html.strip():
                word_count = len(_strip_html_tags(html).split())
                st.caption(f"📊 {word_count} palabras")
                
                html_contents.append({
                    'url': url.strip() if url else '',
                    'html': html,
                    'title': title.strip() if title else f'Artículo {i+1}',
                    'word_count': word_count,
                    'priority': i + 1,
                    'keep_notes': keep_notes.strip() if keep_notes else '',
                    'type': 'main' if i == 0 else 'merge'
                })
            
            # Botón eliminar (solo si hay más de 2)
            if current_count > 2 and i > 0:
                if st.button(f"🗑️ Eliminar", key=f"merge_del_{i}"):
                    # Shift hacia arriba
                    for j in range(i, current_count - 1):
                        for field in ['url', 'title', 'html', 'keep']:
                            next_val = st.session_state.get(f"merge_{field}_{j+1}", "")
                            st.session_state[f"merge_{field}_{j}"] = next_val
                    
                    # Limpiar última
                    last_idx = current_count - 1
                    for field in ['url', 'title', 'html', 'keep']:
                        if f"merge_{field}_{last_idx}" in st.session_state:
                            del st.session_state[f"merge_{field}_{last_idx}"]
                    
                    st.session_state[count_key] = max(2, current_count - 1)
                    st.rerun()
    
    # Botón añadir
    if current_count < MAX_ARTICLES_TO_MERGE:
        if st.button("➕ Añadir otro artículo", key="merge_add"):
            st.session_state[count_key] = current_count + 1
            st.rerun()
    
    # Resumen
    if len(html_contents) >= 2:
        total_words = sum(a['word_count'] for a in html_contents)
        st.success(f"✅ {len(html_contents)} artículos para fusionar ({total_words:,} palabras totales)")
    elif len(html_contents) == 1:
        st.warning("⚠️ Necesitas al menos 2 artículos para fusionar")
    
    return html_contents


def render_disambiguate_input() -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Renderiza input para desambiguar contenido (Post vs PLP).
    
    Returns:
        Tuple[html_contents, disambiguation_config]
    """
    
    st.markdown("""
    **🎯 Desambiguación de Contenido**
    
    Cuando un Post está canibalizando a una PLP (o viceversa), necesitas 
    diferenciar claramente la intención de cada uno.
    """)
    
    # Explicación de los tipos
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("""
        **📝 Post / Editorial**
        - Intención: Informativa
        - Contenido: Guías, tutoriales, comparativas
        - Enfoque: Educar, informar, ayudar
        - Keywords: "cómo", "qué es", "mejores"
        """)
    
    with col2:
        st.markdown("""
        **🛒 PLP / Categoría**
        - Intención: Transaccional
        - Contenido: Listado de productos
        - Enfoque: Vender, convertir
        - Keywords: "comprar", "precio", "oferta"
        """)
    
    st.markdown("---")
    
    # Qué tipo de contenido vas a crear
    output_type = st.radio(
        "¿Qué tipo de contenido quieres generar?",
        options=["post", "plp"],
        format_func=lambda x: "📝 Post / Editorial" if x == "post" else "🛒 PLP / Categoría",
        horizontal=True,
        key="disambiguate_output_type"
    )
    
    st.markdown("---")
    
    # Input del contenido conflictivo
    st.markdown("**Contenido actual que genera conflicto:**")
    
    conflict_url = st.text_input(
        "URL del contenido conflictivo",
        key="disambiguate_conflict_url",
        placeholder="https://www.pccomponentes.com/...",
        help="URL del contenido que está canibalizando"
    )
    
    conflict_html = st.text_area(
        "HTML del contenido conflictivo",
        height=200,
        key="disambiguate_conflict_html",
        placeholder="<article>...</article>",
        help="Pega el HTML del contenido que causa el conflicto"
    )
    
    html_contents = []
    
    if conflict_html and conflict_html.strip():
        word_count = len(_strip_html_tags(conflict_html).split())
        st.caption(f"📊 {word_count} palabras en contenido conflictivo")
        
        html_contents.append({
            'url': conflict_url.strip() if conflict_url else '',
            'html': conflict_html,
            'title': 'Contenido conflictivo',
            'word_count': word_count,
            'type': 'conflict'
        })
    
    # Instrucciones de desambiguación
    st.markdown("---")
    st.markdown("**Instrucciones de desambiguación:**")
    
    if output_type == "post":
        disambiguate_instructions = st.text_area(
            "¿Qué enfoque debe tener el POST?",
            key="disambiguate_post_instructions",
            height=100,
            placeholder="""Ej:
- Enfocarse en "cómo elegir" en lugar de "comprar"
- Añadir más contenido educativo sobre especificaciones
- Incluir comparativas detalladas
- Eliminar listados de productos y CTAs de compra""",
            help="Indica cómo debe diferenciarse el post de la PLP"
        )
    else:
        disambiguate_instructions = st.text_area(
            "¿Qué enfoque debe tener la PLP?",
            key="disambiguate_plp_instructions",
            height=100,
            placeholder="""Ej:
- Enfocarse en productos disponibles y precios
- Reducir contenido informativo extenso
- Destacar ofertas y CTAs de compra
- Mantener solo specs esenciales para filtrar""",
            help="Indica cómo debe diferenciarse la PLP del post"
        )
    
    # URL de la otra pieza (opcional)
    other_url = st.text_input(
        f"URL de la {'PLP' if output_type == 'post' else 'Post'} que debe diferenciarse",
        key="disambiguate_other_url",
        placeholder="https://www.pccomponentes.com/...",
        help="URL del otro contenido para asegurar que no se solapen"
    )
    
    disambiguation_config = {
        'output_type': output_type,
        'instructions': disambiguate_instructions.strip() if disambiguate_instructions else '',
        'other_url': other_url.strip() if other_url else '',
        'conflict_url': conflict_url.strip() if conflict_url else ''
    }
    
    return html_contents, disambiguation_config


# ============================================================================
# SECCIÓN: INSTRUCCIONES DE REESCRITURA (NUEVO)
# ============================================================================

def render_rewrite_instructions_section(rewrite_mode: str) -> Dict[str, Any]:
    """
    Renderiza la sección de instrucciones de reescritura.
    
    v5.1: Simplificado de 8 campos a 3 campos claros:
    1. ¿Qué cambiar? (fusiona: mejorar + eliminar + tono + estructura)
    2. ¿Qué añadir? (fusiona: añadir + SEO)
    3. ¿Qué conservar? (mantener)
    
    Los datos se mapean al formato legacy para compatibilidad con prompts.
    
    Args:
        rewrite_mode: Modo actual (single/merge/disambiguate)
        
    Returns:
        Dict con instrucciones de reescritura (formato compatible con prompts)
    """
    
    instructions = {
        'improve': [],
        'maintain': [],
        'remove': [],
        'add': [],
        'tone_changes': '',
        'structure_changes': '',
        'seo_focus': '',
        'additional_notes': ''
    }
    
    st.markdown("""
    Indica qué cambios específicos quieres. Estas instrucciones guiarán la reescritura.
    """)
    
    # =========================================================================
    # CAMPO 1: ¿Qué CAMBIAR? (mejorar + eliminar + tono + estructura)
    # =========================================================================
    with st.expander("✏️ ¿Qué CAMBIAR o MEJORAR?", expanded=True):
        st.caption("Aspectos a mejorar, eliminar, corregir. Incluye cambios de tono, estructura, SEO, contenido obsoleto...")
        
        change_text = st.text_area(
            "Cambios a realizar",
            key="rewrite_changes",
            height=120,
            placeholder="""Ej:
- La introducción es muy larga y poco atractiva → más directa
- Faltan datos técnicos actualizados (benchmarks 2025)
- Eliminar referencias a productos descatalogados
- Tono demasiado formal → más cercano y directo
- Estructura: mover FAQs al final, dividir secciones largas
- SEO: keyword principal en H1 y primer párrafo
- Eliminar enlaces rotos o a competidores""",
            help="Todo lo que necesita cambiar: mejoras, eliminaciones, tono, estructura, SEO",
            label_visibility="collapsed"
        )
        
        if change_text:
            items = [
                line.strip().lstrip('-•*→') .strip()
                for line in change_text.split('\n') 
                if line.strip()
            ]
            # Mapear a campos legacy para compatibilidad
            instructions['improve'] = items
    
    # =========================================================================
    # CAMPO 2: ¿Qué AÑADIR?
    # =========================================================================
    with st.expander("➕ ¿Qué AÑADIR de nuevo?", expanded=False):
        st.caption("Contenido, secciones, datos o funcionalidades nuevas que deben incluirse")
        
        add_text = st.text_area(
            "Contenido a añadir",
            key="rewrite_add",
            height=120,
            placeholder="""Ej:
- Sección sobre modelos 2025
- Comparativa con nuevos competidores
- Benchmarks actualizados
- Sección "¿Para quién es cada opción?"
- Más productos de PcComponentes enlazados
- Keywords secundarias: "mejor calidad precio", "comparativa 2025"
- Schema FAQ para featured snippets""",
            help="Todo lo nuevo: secciones, datos, enlaces, optimizaciones SEO",
            label_visibility="collapsed"
        )
        
        if add_text:
            instructions['add'] = [
                line.strip().lstrip('-•*') 
                for line in add_text.split('\n') 
                if line.strip()
            ]
    
    # =========================================================================
    # CAMPO 3: ¿Qué CONSERVAR?
    # =========================================================================
    with st.expander("✅ ¿Qué CONSERVAR tal como está?", expanded=False):
        st.caption("Elementos que funcionan bien y NO deben modificarse")
        
        maintain_text = st.text_area(
            "Puntos a mantener",
            key="rewrite_maintain",
            height=100,
            placeholder="""Ej:
- La tabla comparativa de especificaciones
- El tono experto pero accesible
- Las FAQs (están bien posicionadas en SERPs)
- Los enlaces internos actuales
- El veredicto final (bien argumentado)""",
            help="Todo lo que funciona y debe mantenerse intacto",
            label_visibility="collapsed"
        )
        
        if maintain_text:
            instructions['maintain'] = [
                line.strip().lstrip('-•*') 
                for line in maintain_text.split('\n') 
                if line.strip()
            ]
    
    return instructions


# ============================================================================
# SECCIÓN: PRODUCTO PRINCIPAL
# ============================================================================

def render_main_product_section() -> Optional[Dict[str, Any]]:
    """
    Renderiza la sección de Producto Principal.
    
    Returns:
        Dict con datos del producto principal o None si no está habilitado
    """
    
    st.markdown("""
    Si el contenido se centra en un producto específico (review, análisis, etc.),
    puedes añadir sus datos aquí para enriquecer la generación.
    """)
    
    # Checkbox para habilitar
    is_enabled = st.checkbox(
        "Este contenido se centra en un producto específico",
        value=st.session_state.get('rewrite_main_product_enabled', False),
        key="rewrite_main_product_checkbox",
        help="Activa esta opción si el contenido es sobre un producto concreto"
    )
    
    st.session_state.rewrite_main_product_enabled = is_enabled
    
    if not is_enabled:
        st.caption("💡 Deja desactivado si el contenido es genérico (ej: 'mejores portátiles gaming')")
        st.session_state.rewrite_main_product_json = None
        return None
    
    # URL del producto
    col1, col2 = st.columns([3, 1])
    
    with col1:
        product_url = st.text_input(
            "🔗 URL del Producto Principal",
            key="rewrite_main_product_url",
            placeholder="https://www.pccomponentes.com/...",
            help="URL del producto en PcComponentes"
        )
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("📦 Añade el JSON abajo")
    
    # Widget JSON con TABS
    st.markdown(
        "💡 **Obtén el JSON completo del producto** usando el "
        "[workflow de n8n](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV)."
    )
    
    json_tab1, json_tab2 = st.tabs(["📁 Subir archivo", "📋 Pegar JSON"])
    
    json_content = None
    
    with json_tab1:
        uploaded_json = st.file_uploader(
            "Subir JSON del producto",
            type=['json'],
            key="rewrite_main_product_json_upload",
            help="JSON generado por el workflow de n8n"
        )
        
        if uploaded_json is not None:
            try:
                json_content = uploaded_json.read().decode('utf-8')
            except Exception as e:
                st.error(f"❌ Error al leer archivo: {str(e)}")
    
    with json_tab2:
        pasted_json = st.text_area(
            "Pegar JSON aquí",
            height=150,
            key="rewrite_main_product_json_paste",
            placeholder='{"id": "...", "name": "...", ...}',
            help="Pega el JSON directamente desde el workflow de n8n"
        )
        
        if pasted_json and pasted_json.strip():
            json_content = pasted_json.strip()
    
    product_json_data = None
    
    # Procesar JSON
    if json_content:
        try:
            if _product_json_available:
                is_valid, error_msg = validate_product_json(json_content)
                
                if is_valid:
                    product_data = parse_product_json(json_content)
                    
                    if product_data:
                        product_json_data = {
                            'product_id': product_data.product_id,
                            'legacy_id': product_data.legacy_id,
                            'title': product_data.title,
                            'description': product_data.description,
                            'brand_name': product_data.brand_name,
                            'family_name': product_data.family_name,
                            'attributes': product_data.attributes,
                            'images': product_data.images,
                            'total_comments': product_data.total_comments,
                            'advantages': product_data.advantages,
                            'disadvantages': product_data.disadvantages,
                            'comments': product_data.comments,
                        }
                        
                        st.session_state.rewrite_main_product_json = product_json_data
                        st.success(f"✅ JSON cargado: **{product_data.title}**")
                        
                        # Preview de datos
                        with st.expander("👁️ Preview de datos JSON", expanded=False):
                            summary = create_product_summary(product_data)
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"**Producto:** {summary['title']}")
                                st.markdown(f"**Marca:** {summary['brand']}")
                                st.markdown(f"**Familia:** {summary['family']}")
                            with col_b:
                                st.markdown(f"**ID:** {summary['product_id']}")
                                st.markdown(f"**Reviews:** {summary.get('total_comments', 0)}")
                                st.markdown(f"**Imágenes:** {summary.get('images_count', 0)}")
                    else:
                        st.error("❌ Error al parsear el JSON del producto")
                        st.session_state.rewrite_main_product_json = None
                else:
                    # Quitar prefijo "JSON inválido:" si ya viene en el mensaje
                    clean_error = error_msg.replace("JSON inválido: ", "").replace("JSON inválido:", "")
                    st.error(f"❌ JSON inválido: {clean_error}")
                    st.session_state.rewrite_main_product_json = None
            else:
                # Fallback sin validación
                parsed_json = json.loads(json_content)
                st.session_state.rewrite_main_product_json = parsed_json
                product_json_data = parsed_json
                st.success("✅ JSON cargado (sin validación detallada)")
                
        except json.JSONDecodeError as e:
            st.error(f"❌ Error JSON: {str(e)}")
            st.session_state.rewrite_main_product_json = None
        except Exception as e:
            logger.error(f"Error inesperado procesando JSON de producto: {e}")
            st.error("❌ Error inesperado al procesar el JSON.")
            st.session_state.rewrite_main_product_json = None
    
    # Recuperar JSON si ya estaba cargado
    if st.session_state.get('rewrite_main_product_json') and not product_json_data:
        product_json_data = st.session_state.rewrite_main_product_json
        if product_json_data:
            title = product_json_data.get('title', 'Producto')
            st.caption(f"📦 JSON cargado previamente: {title[:50]}")
    
    # Retornar datos
    if product_url or product_json_data:
        return {
            'url': product_url.strip() if product_url else '',
            'json_data': product_json_data
        }
    
    return None


# ============================================================================
# SECCIÓN: PRODUCTOS ALTERNATIVOS (NUEVO v4.7.1)
# ============================================================================

def render_alternative_products_section() -> List[Dict[str, Any]]:
    """
    Renderiza la sección de productos alternativos.
    Cada producto tiene URL + JSON con tabs (subir/pegar).
    
    Returns:
        Lista de dicts con {url, anchor, product_data}
    """
    
    st.markdown("""
    Si quieres recomendar productos alternativos en el contenido, 
    añádelos aquí con sus datos para que los enlaces sean más contextuales.
    """)
    
    # Checkbox para habilitar
    is_enabled = st.checkbox(
        "Incluir productos alternativos",
        value=st.session_state.get('rewrite_alt_products_enabled', False),
        key="rewrite_alt_products_checkbox",
        help="Activa esta opción si quieres recomendar alternativas"
    )
    
    st.session_state.rewrite_alt_products_enabled = is_enabled
    
    if not is_enabled:
        st.caption("💡 Activa esta opción si quieres recomendar alternativas al producto principal o a los productos mencionados.")
        return []
    
    st.markdown(
        "💡 **Obtén el JSON de cada producto** usando el "
        "[workflow de n8n](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV)."
    )
    
    count_key = 'rewrite_alt_products_count'
    current_count = st.session_state.get(count_key, 1)
    
    alternative_products = []
    
    for i in range(current_count):
        with st.expander(f"🎯 Producto Alternativo {i+1}", expanded=(i == 0)):
            col1, col2 = st.columns([3, 2])
            
            with col1:
                url = st.text_input(
                    f"URL del producto {i+1}",
                    key=f"alt_prod_url_{i}",
                    placeholder="https://www.pccomponentes.com/producto",
                    help="URL del producto alternativo"
                )
            
            with col2:
                anchor = st.text_input(
                    f"Texto del enlace {i+1}",
                    key=f"alt_prod_anchor_{i}",
                    placeholder="Nombre del producto",
                    help="Texto que se usará para enlazar"
                )
            
            # Widget JSON con TABS
            st.markdown("**📦 JSON del producto**")
            
            json_tab1, json_tab2 = st.tabs(["📁 Subir JSON", "📋 Pegar JSON"])
            
            json_content = None
            json_key = f"alt_prod_json_{i}"
            
            with json_tab1:
                uploaded_json = st.file_uploader(
                    f"Subir JSON",
                    type=['json'],
                    key=f"alt_prod_json_upload_{i}",
                    help="JSON del producto"
                )
                
                if uploaded_json is not None:
                    try:
                        json_content = uploaded_json.read().decode('utf-8')
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            
            with json_tab2:
                pasted_json = st.text_area(
                    "Pegar JSON",
                    height=100,
                    key=f"alt_prod_json_paste_{i}",
                    placeholder='{"id": "...", "name": "...", ...}'
                )
                
                if pasted_json and pasted_json.strip():
                    json_content = pasted_json.strip()
            
            product_json_data = _process_json_content(json_content, json_key)
            
            # Botón eliminar
            if current_count > 1:
                if st.button("🗑️ Eliminar producto", key=f"alt_prod_del_{i}"):
                    _delete_link_at_index(i, current_count, count_key, 'alt_prod')
            
            if url and url.strip():
                alternative_products.append({
                    'url': url.strip(),
                    'anchor': anchor.strip() if anchor else '',
                    'product_data': product_json_data
                })
    
    # Botón añadir
    if current_count < MAX_ALTERNATIVE_PRODUCTS:
        if st.button("➕ Añadir otro producto alternativo", key="alt_prod_add"):
            st.session_state[count_key] = current_count + 1
            st.rerun()
    
    if alternative_products:
        with_json = sum(1 for p in alternative_products if p.get('product_data'))
        st.success(f"✅ {len(alternative_products)} producto(s) alternativo(s) ({with_json} con JSON)")
    
    return alternative_products


# ============================================================================
# UTILIDADES HTML
# ============================================================================

def _strip_html_tags(html: str) -> str:
    """Elimina tags HTML y retorna texto plano."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def _show_html_stats(html_content: str) -> None:
    """Muestra estadísticas del contenido HTML."""
    text_content = _strip_html_tags(html_content)
    word_count = len(text_content.split())
    char_count = len(html_content)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📝 Palabras", f"{word_count:,}")
    with col2:
        st.metric("📊 Caracteres", f"{char_count:,}")
    with col3:
        h1_count = html_content.lower().count('<h1')
        h2_count = html_content.lower().count('<h2')
        st.metric("📑 Encabezados", f"{h1_count} H1, {h2_count} H2")
    
    if word_count < 100:
        st.warning("⚠️ El contenido parece muy corto. Asegúrate de haber pegado el artículo completo.")
    else:
        st.success(f"✅ Contenido detectado: {word_count} palabras")


# ============================================================================
# SECCIÓN: ENLACES A POSTS/PLPs CON HTML CONTEXTUAL (ACTUALIZADO v4.7.1)
# ============================================================================

def render_posts_plps_links_section() -> List[Dict[str, Any]]:
    """
    Renderiza la sección de enlaces a posts/PLPs con HTML contextual.
    
    ACTUALIZADO v4.7.1:
    - Selector tipo: Post / PLP
    - Post: Un campo HTML único
    - PLP: Dos campos (Top text, Bottom text)
    - Eliminado JSON de productos (no necesario aquí)
    
    Returns:
        Lista de dicts con datos del enlace + HTML contextual
    """
    count_key = 'rewrite_posts_plps_count'
    current_count = st.session_state.get(count_key, 1)
    
    links = []
    
    for i in range(current_count):
        with st.expander(f"📝 Enlace Editorial {i+1}", expanded=(i == 0)):
            # Selector de tipo (NUEVO v4.7.1)
            editorial_type = st.radio(
                f"Tipo de contenido destino {i+1}",
                options=[EditorialType.POST, EditorialType.PLP],
                format_func=lambda x: EDITORIAL_TYPE_OPTIONS[x]["name"],
                horizontal=True,
                key=f"rewrite_editorial_type_{i}",
                help="Selecciona el tipo de contenido al que enlazas"
            )
            
            col1, col2 = st.columns([3, 2])
            
            with col1:
                url = st.text_input(
                    f"URL {i+1}",
                    key=f"rewrite_posts_url_{i}",
                    placeholder="https://www.pccomponentes.com/...",
                    help="URL del post, guía, categoría o PLP"
                )
            
            with col2:
                anchor = st.text_input(
                    f"Anchor text {i+1}",
                    key=f"rewrite_posts_anchor_{i}",
                    placeholder="Texto del enlace",
                    help="Texto visible del enlace"
                )
            
            # Campos HTML según tipo (NUEVO v4.7.1)
            html_content_data = {}
            
            if editorial_type == EditorialType.POST:
                # Un solo campo HTML para posts
                st.markdown("**📄 Contenido HTML del Post** (para contexto)")
                html_content = st.text_area(
                    "HTML del post",
                    height=150,
                    key=f"rewrite_posts_html_{i}",
                    placeholder=EDITORIAL_TYPE_OPTIONS[EditorialType.POST]["placeholder"],
                    help="Pega el HTML del post para que el enlace sea más contextual",
                    label_visibility="collapsed"
                )
                
                html_content_data['html_content'] = html_content
                html_content_data['editorial_type'] = EditorialType.POST
                
                if html_content and html_content.strip():
                    word_count = len(_strip_html_tags(html_content).split())
                    st.caption(f"📊 {word_count} palabras de contexto")
            
            else:  # PLP
                # Dos campos para PLPs
                st.markdown("**📄 Contenido de la PLP** (para contexto)")
                
                top_text = st.text_area(
                    "Top text (antes de productos)",
                    height=100,
                    key=f"rewrite_posts_top_{i}",
                    placeholder=EDITORIAL_TYPE_OPTIONS[EditorialType.PLP]["placeholder_top"],
                    help="Texto que aparece ANTES del listado de productos"
                )
                
                bottom_text = st.text_area(
                    "Bottom text (después de productos)",
                    height=100,
                    key=f"rewrite_posts_bottom_{i}",
                    placeholder=EDITORIAL_TYPE_OPTIONS[EditorialType.PLP]["placeholder_bottom"],
                    help="Texto que aparece DESPUÉS del listado de productos"
                )
                
                html_content_data['top_text'] = top_text
                html_content_data['bottom_text'] = bottom_text
                html_content_data['editorial_type'] = EditorialType.PLP
                
                # Estadísticas combinadas
                total_content = (top_text or '') + ' ' + (bottom_text or '')
                if total_content.strip():
                    word_count = len(_strip_html_tags(total_content).split())
                    st.caption(f"📊 {word_count} palabras de contexto (top + bottom)")
            
            # Botón eliminar
            if current_count > 1:
                if st.button("🗑️ Eliminar enlace", key=f"rewrite_posts_del_{i}"):
                    _delete_link_at_index(i, current_count, count_key, 'rewrite_posts')
            
            if url and url.strip():
                link_data = {
                    'url': url.strip(),
                    'anchor': anchor.strip() if anchor else '',
                    'type': 'editorial',
                    'editorial_type': html_content_data.get('editorial_type', EditorialType.POST),
                }
                
                # Añadir campos HTML según tipo
                if html_content_data.get('editorial_type') == EditorialType.POST:
                    link_data['html_content'] = html_content_data.get('html_content', '')
                else:
                    link_data['top_text'] = html_content_data.get('top_text', '')
                    link_data['bottom_text'] = html_content_data.get('bottom_text', '')
                
                links.append(link_data)
    
    # Botón añadir
    if current_count < MAX_EDITORIAL_LINKS:
        if st.button("➕ Añadir enlace a post/PLP", key="rewrite_posts_add"):
            st.session_state[count_key] = current_count + 1
            st.rerun()
    
    if links:
        posts = sum(1 for l in links if l.get('editorial_type') == EditorialType.POST)
        plps = sum(1 for l in links if l.get('editorial_type') == EditorialType.PLP)
        with_context = sum(1 for l in links if l.get('html_content') or l.get('top_text') or l.get('bottom_text'))
        st.caption(f"✅ {len(links)} enlace(s): {posts} posts, {plps} PLPs ({with_context} con contexto HTML)")
    
    return links


# ============================================================================
# SECCIÓN: ENLACES A PRODUCTOS CON JSON
# ============================================================================

def render_product_links_section() -> List[Dict[str, Any]]:
    """
    Renderiza la sección de enlaces a productos con JSON.
    
    Returns:
        Lista de dicts con {'url': str, 'anchor': str, 'product_data': dict|None}
    """
    count_key = 'rewrite_product_links_count'
    current_count = st.session_state.get(count_key, 1)
    
    links = []
    
    for i in range(current_count):
        with st.expander(f"🛒 Producto {i+1}", expanded=(i == 0)):
            col1, col2 = st.columns([3, 2])
            
            with col1:
                url = st.text_input(
                    f"URL del producto {i+1}",
                    key=f"rewrite_prod_url_{i}",
                    placeholder="https://www.pccomponentes.com/producto",
                    help="URL del PDP"
                )
            
            with col2:
                anchor = st.text_input(
                    f"Anchor text {i+1}",
                    key=f"rewrite_prod_anchor_{i}",
                    placeholder="Texto del enlace",
                    help="Texto visible"
                )
            
            # Widget JSON
            json_key = f"rewrite_prod_json_{i}"
            
            st.markdown(f"**📦 JSON del producto (opcional)**")
            
            json_tab1, json_tab2 = st.tabs(["📁 Subir archivo", "📋 Pegar JSON"])
            
            json_content = None
            
            with json_tab1:
                uploaded_json = st.file_uploader(
                    f"Subir JSON",
                    type=['json'],
                    key=f"rewrite_prod_json_upload_{i}",
                    help="JSON con datos del producto"
                )
                
                if uploaded_json is not None:
                    try:
                        json_content = uploaded_json.read().decode('utf-8')
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            
            with json_tab2:
                pasted_json = st.text_area(
                    "Pegar JSON aquí",
                    height=120,
                    key=f"rewrite_prod_json_paste_{i}",
                    placeholder='{"id": "...", "name": "...", ...}'
                )
                
                if pasted_json and pasted_json.strip():
                    json_content = pasted_json.strip()
            
            product_json_data = _process_json_content(json_content, json_key)
            
            # Botón eliminar
            if current_count > 1:
                if st.button("🗑️ Eliminar producto", key=f"rewrite_prod_del_{i}"):
                    _delete_link_at_index(i, current_count, count_key, 'rewrite_prod')
            
            if url and url.strip():
                links.append({
                    'url': url.strip(),
                    'anchor': anchor.strip() if anchor else '',
                    'type': 'product',
                    'product_data': product_json_data
                })
    
    # Botón añadir
    if current_count < MAX_PRODUCT_LINKS:
        if st.button("➕ Añadir producto", key="rewrite_prod_add"):
            st.session_state[count_key] = current_count + 1
            st.rerun()
    
    if links:
        with_json = sum(1 for l in links if l.get('product_data'))
        st.caption(f"✅ {len(links)} producto(s) configurado(s) ({with_json} con JSON)")
    
    return links


def _process_json_content(json_content: Optional[str], json_key: str) -> Optional[Dict]:
    """Procesa contenido JSON y lo guarda en session state."""
    if not json_content:
        # Recuperar si ya estaba cargado
        if json_key in st.session_state:
            product_json_data = st.session_state[json_key]
            if product_json_data:
                title = product_json_data.get('title', 'Producto')
                st.caption(f"📦 JSON cargado: {title[:40]}")
            return product_json_data
        return None
    
    try:
        if _product_json_available:
            is_valid, error_msg = validate_product_json(json_content)
            
            if is_valid:
                product_data = parse_product_json(json_content)
                
                if product_data:
                    product_json_data = {
                        'product_id': product_data.product_id,
                        'legacy_id': product_data.legacy_id,
                        'title': product_data.title,
                        'description': product_data.description,
                        'brand_name': product_data.brand_name,
                        'family_name': product_data.family_name,
                        'attributes': product_data.attributes,
                        'images': product_data.images,
                        'total_comments': product_data.total_comments,
                        'advantages': product_data.advantages,
                        'disadvantages': product_data.disadvantages,
                        'comments': product_data.comments,
                    }
                    
                    st.session_state[json_key] = product_json_data
                    st.success(f"✅ JSON: {product_data.title[:50]}")
                    return product_json_data
                else:
                    st.error("❌ Error al parsear JSON")
            else:
                # Quitar prefijo duplicado si existe
                clean_error = error_msg.replace("JSON inválido: ", "").replace("JSON inválido:", "")
                st.error(f"❌ JSON inválido: {clean_error}")
        else:
            parsed_json = json.loads(json_content)
            st.session_state[json_key] = parsed_json
            st.success("✅ JSON cargado")
            return parsed_json
            
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
    
    return None


def _delete_link_at_index(idx: int, current_count: int, count_key: str, prefix: str) -> None:
    """
    Marca un enlace para eliminación.
    La eliminación real se procesa con _process_pending_deletions al inicio.
    """
    # Guardar la operación pendiente para procesarla en el siguiente rerun
    st.session_state[f"_pending_delete_{prefix}"] = {
        'idx': idx,
        'count': current_count,
        'count_key': count_key,
        'prefix': prefix
    }
    st.rerun()


def _process_pending_deletions() -> None:
    """
    Procesa eliminaciones pendientes al inicio del renderizado.
    Debe llamarse ANTES de renderizar los widgets de enlaces.
    """
    prefixes_to_check = ['rewrite_posts', 'rewrite_prod', 'alt_prod']
    
    for prefix in prefixes_to_check:
        pending_key = f"_pending_delete_{prefix}"
        
        if pending_key in st.session_state:
            pending = st.session_state[pending_key]
            del st.session_state[pending_key]
            
            idx = pending['idx']
            current_count = pending['count']
            count_key = pending['count_key']
            
            # Determinar campos según prefijo
            if prefix == 'rewrite_posts':
                fields = ['url', 'anchor', 'html', 'top', 'bottom']
            elif prefix == 'alt_prod':
                fields = ['url', 'anchor', 'json']
            else:
                fields = ['url', 'anchor', 'json']
            
            # Shift de valores hacia arriba
            for j in range(idx, current_count - 1):
                for field in fields:
                    next_key = f"{prefix}_{field}_{j+1}"
                    curr_key = f"{prefix}_{field}_{j}"
                    next_val = st.session_state.get(next_key, "")
                    st.session_state[curr_key] = next_val
            
            # Limpiar última posición
            last_idx = current_count - 1
            for field in fields:
                key_to_delete = f"{prefix}_{field}_{last_idx}"
                if key_to_delete in st.session_state:
                    del st.session_state[key_to_delete]
            
            # También limpiar keys relacionadas con editorial_type y uploads
            extra_keys = [
                f"rewrite_editorial_type_{last_idx}",
                f"{prefix}_json_upload_{last_idx}",
                f"{prefix}_json_paste_{last_idx}",
                f"alt_prod_json_upload_{last_idx}",
                f"alt_prod_json_paste_{last_idx}",
            ]
            for key in extra_keys:
                if key in st.session_state:
                    del st.session_state[key]
            
            # Decrementar contador
            st.session_state[count_key] = max(1, current_count - 1)


# ============================================================================
# INPUT DE KEYWORD Y BÚSQUEDA
# ============================================================================

def render_keyword_input() -> Tuple[str, bool]:
    """Renderiza el input de keyword principal y botón de búsqueda."""
    
    st.markdown("Introduce la **keyword principal** para la que quieres rankear.")
    
    semrush_available = SEMRUSH_MODULE_AVAILABLE and is_semrush_available()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        current_keyword = st.text_input(
            "Keyword principal *",
            placeholder="Ej: mejor portátil gaming 2025",
            help="Keyword específica para la que quieres crear/mejorar contenido",
            key="rewrite_keyword_input"
        )
    
    with col2:
        if semrush_available:
            search_disabled = not current_keyword or len(current_keyword.strip()) < 3
            search_button = st.button(
                "🔍 Buscar Competidores",
                disabled=search_disabled,
                use_container_width=True,
                type="primary",
                key="btn_search_competitors"
            )
        else:
            search_button = False
            st.caption("💡 Introduce URLs manualmente abajo")
    
    # Detectar si cambió la keyword
    if 'last_rewrite_keyword' in st.session_state:
        if st.session_state.last_rewrite_keyword != current_keyword:
            st.session_state.rewrite_competitors_data = None
            st.session_state.rewrite_analysis = None
            st.session_state.rewrite_gsc_analysis = None
            st.session_state.semrush_response = None
    
    st.session_state.last_rewrite_keyword = current_keyword
    
    return current_keyword, search_button


# ============================================================================
# OBTENCIÓN DE COMPETIDORES
# ============================================================================

def _fetch_competitors_semrush(keyword: str, gsc_analysis: Optional[Dict]) -> None:
    """Obtiene competidores usando SEMrush API."""
    
    if gsc_analysis and gsc_analysis.get('has_matches'):
        st.info("💡 Procederemos a analizar competidores. Recuerda que ya tienes contenido rankeando.")
    
    with st.spinner("🔍 Consultando SEMrush y analizando competidores..."):
        try:
            client = SEMrushClient(api_key=SEMRUSH_API_KEY, database='es')
            
            response = client.get_organic_competitors(
                keyword=keyword,
                num_results=5,
                scrape_content=True,
                exclude_domains=['pccomponentes.com', 'pccomponentes.pt']
            )
            
            st.session_state.semrush_response = response
            
            if response.success and response.competitors:
                competitors_data = format_competitors_for_display(response.competitors)
                st.session_state.rewrite_competitors_data = competitors_data
                
                scraped_ok = sum(1 for c in competitors_data if c.get('scrape_success', False))
                
                st.success(f"✅ **SEMrush**: {len(competitors_data)} competidores encontrados ({scraped_ok} scrapeados)")
            else:
                st.error(f"❌ **Error de SEMrush**: {response.error_message}")
                st.session_state['show_manual_fallback'] = True
        
        except Exception as e:
            logger.error(f"Error inesperado en SEMrush: {e}")
            st.error("❌ **Error inesperado** al buscar competidores. Usa el modo manual.")
            st.session_state['show_manual_fallback'] = True
        
        st.rerun()


def render_manual_competitors_input(keyword: str) -> None:
    """Renderiza el input manual para URLs de competidores."""
    
    st.markdown("**Introduce las URLs de los competidores** que quieres analizar.")
    
    urls_input = st.text_area(
        "URLs de competidores (una por línea) *",
        value=st.session_state.get('manual_urls_input', ''),
        placeholder="""https://competitor1.com/article
https://competitor2.com/guide
https://competitor3.com/review""",
        height=150,
        help="Introduce las URLs de los competidores que rankean para tu keyword"
    )
    
    st.session_state.manual_urls_input = urls_input
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        analyze_btn = st.button(
            "🔍 Analizar URLs",
            disabled=not urls_input.strip(),
            type="primary",
            key="btn_analyze_urls"
        )
    
    with col2:
        if urls_input:
            urls = [u.strip() for u in urls_input.split('\n') if u.strip() and u.startswith('http')]
            st.caption(f"📋 {len(urls)} URLs detectadas")
    
    if analyze_btn and urls_input:
        _scrape_manual_urls(urls_input, keyword)


def _scrape_manual_urls(urls_input: str, keyword: str) -> None:
    """Scrapea las URLs introducidas manualmente."""
    
    urls = [u.strip() for u in urls_input.split('\n') if u.strip() and u.startswith('http')]
    
    if not urls:
        st.error("❌ No se encontraron URLs válidas")
        return
    
    if len(urls) > 10:
        st.warning("⚠️ Máximo 10 URLs. Solo se procesarán las primeras 10.")
        urls = urls[:10]
    
    with st.spinner(f"🔍 Analizando {len(urls)} URLs..."):
        competitors_data = []
        
        for i, url in enumerate(urls, 1):
            try:
                content_data = _scrape_single_url(url, i)
                competitors_data.append(content_data)
            except Exception as e:
                competitors_data.append({
                    'url': url,
                    'title': 'Error al scrapear',
                    'domain': _extract_domain(url),
                    'position': i,
                    'ranking_position': i,
                    'content': '',
                    'word_count': 0,
                    'scrape_success': False,
                    'error': str(e)[:100]
                })
        
        st.session_state.rewrite_competitors_data = competitors_data
        
        success_count = sum(1 for c in competitors_data if c.get('scrape_success', False))
        
        if success_count > 0:
            st.success(f"✅ Contenido analizado: {success_count}/{len(competitors_data)} URLs")
        else:
            st.error("❌ No se pudo scrapear ninguna URL")
        
        st.rerun()


def _scrape_single_url(url: str, position: int) -> Dict:
    """Scrapea una URL individual."""
    import requests
    from bs4 import BeautifulSoup
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'es-ES,es;q=0.9',
    }
    
    response = requests.get(url, headers=headers, timeout=15)
    
    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    title_tag = soup.find('title')
    title = title_tag.get_text(strip=True) if title_tag else ''
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    description = meta_desc.get('content', '') if meta_desc else ''
    
    for element in soup(['script', 'style', 'nav', 'footer', 'header', 'aside']):
        element.decompose()
    
    main = soup.find('main') or soup.find('article') or soup.find('body')
    content = main.get_text(' ', strip=True) if main else ''
    content = re.sub(r'\s+', ' ', content).strip()
    
    if len(content) > 8000:
        content = content[:8000] + "..."
    
    return {
        'url': url,
        'title': title[:200] if title else 'Sin título',
        'domain': _extract_domain(url),
        'position': position,
        'ranking_position': position,
        'content': content,
        'word_count': len(content.split()),
        'meta_description': description[:300] if description else '',
        'scrape_success': True,
        'error': None
    }


def _extract_domain(url: str) -> str:
    """Extrae el dominio de una URL."""
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        return parsed.netloc.replace('www.', '')
    except Exception:
        return url


# ============================================================================
# RESUMEN DE COMPETIDORES
# ============================================================================

def render_competitors_summary(competitors_data: List[Dict]) -> None:
    """Renderiza un resumen de los competidores analizados."""
    
    st.markdown("#### 📊 Competidores Analizados")
    
    col1, col2, col3 = st.columns(3)
    
    scraped_ok = [c for c in competitors_data if c.get('scrape_success', False)]
    
    with col1:
        st.metric("📊 Total URLs", len(competitors_data))
    
    with col2:
        if scraped_ok:
            avg_words = sum(c.get('word_count', 0) for c in scraped_ok) / len(scraped_ok)
            st.metric("📝 Promedio palabras", f"{int(avg_words):,}")
        else:
            st.metric("📝 Promedio palabras", "N/A")
    
    with col3:
        st.metric("✅ Scrapeados", f"{len(scraped_ok)}/{len(competitors_data)}")
    
    for i, comp in enumerate(competitors_data, 1):
        position = comp.get('ranking_position', comp.get('position', i))
        title = comp.get('title', 'Sin título')[:60]
        
        if comp.get('scrape_success', False):
            icon = "✅"
            status = f"{comp.get('word_count', 0):,} palabras"
        else:
            icon = "❌"
            status = comp.get('error', 'Error')[:30]
        
        with st.expander(f"{icon} #{position} - {title}", expanded=False):
            st.markdown(f"**URL:** [{comp.get('url', 'N/A')}]({comp.get('url', '#')})")
            st.markdown(f"**Dominio:** {comp.get('domain', 'N/A')}")
            
            if comp.get('content') and comp.get('scrape_success'):
                content_preview = comp['content'][:400] + "..."
                st.text_area("Preview", content_preview, height=100, disabled=True, key=f"preview_comp_{i}")


# ============================================================================
# CONFIGURACIÓN DE REESCRITURA
# ============================================================================

def render_rewrite_configuration(keyword: str, rewrite_mode: str) -> Dict:
    """
    Renderiza los controles de configuración.
    
    v5.1: Reordenado para coherencia:
    1. Arquetipo (define estructura y tono)
    2. Briefing (preguntas guía del arquetipo)
    3. Objetivo y contexto (fusionados en un campo)
    4. Longitud
    5. Keywords secundarias
    6. Elementos visuales + Encabezados
    """
    
    config = {}
    
    # ── 1. Arquetipo ──────────────
    use_arquetipo = st.checkbox(
        "Usar arquetipo como guía estructural",
        value=True,
        help="El arquetipo define estructura y tono del contenido"
    )
    
    if use_arquetipo and _arquetipos_available:
        arquetipo_names = get_arquetipo_names()
        arquetipo_codes = sorted(arquetipo_names.keys())
        
        selected_arquetipo = st.selectbox(
            "Seleccionar arquetipo",
            options=arquetipo_codes,
            format_func=lambda x: f"{x}: {arquetipo_names.get(x, x)}",
            index=0,
            key="rewrite_arquetipo_selector"
        )
        
        config['arquetipo_codigo'] = selected_arquetipo
        
        arq_data = get_arquetipo(selected_arquetipo)
        if arq_data:
            description = arq_data.get('description', '')
            tone = arq_data.get('tone', '')
            
            if description:
                st.caption(f"ℹ️ **{description}**")
            if tone:
                st.caption(f"🎭 Tono: {tone}")
        
        # ── 2. Briefing (preguntas guía del arquetipo) ──────────────
        try:
            from ui.inputs import render_guiding_questions as _render_gq
        except ImportError:
            try:
                from inputs import render_guiding_questions as _render_gq
            except ImportError:
                _render_gq = None
        
        if _render_gq:
            rewrite_guiding_answers = _render_gq(selected_arquetipo, key_prefix="rewrite_guiding")
            if rewrite_guiding_answers:
                parts = [f"**{q}**\n{a}" for q, a in rewrite_guiding_answers.items()]
                config['guiding_context'] = "\n\n".join(parts)
            else:
                config['guiding_context'] = ''
        else:
            config['guiding_context'] = ''
        
        min_len, max_len = get_length_range(selected_arquetipo)
        default_len = get_default_length(selected_arquetipo)
    else:
        config['arquetipo_codigo'] = None
        config['guiding_context'] = ''
        min_len, max_len = 800, 3000
        default_len = 1600
    
    # ── 3. Objetivo y contexto ──────────────────
    
    config['objetivo'] = st.text_area(
        "Objetivo y contexto del contenido",
        placeholder="Describe qué quieres lograr con este contenido y cualquier contexto relevante.\n"
                    "Ej: Mejorar posicionamiento para portátiles gaming 2025. "
                    "Tenemos datos internos de ventas que muestran preferencia por ASUS y MSI. "
                    "El artículo actual está desactualizado y le faltan modelos nuevos.",
        help="Combina tu objetivo (qué lograr) con cualquier contexto útil (datos internos, perspectiva única, etc.)",
        height=120
    )
    # Mapear a 'context' para backward compat (el prompt usa ambos)
    config['context'] = ''  # Ya no necesitamos campo separado
    
    # ── 4. Longitud ─────────────────────────────────────────────────
    
    col1, col2 = st.columns(2)
    
    with col1:
        config['target_length'] = st.number_input(
            "Longitud objetivo (palabras) *",
            min_value=min_len,
            max_value=max_len,
            value=default_len,
            step=100
        )
    
    with col2:
        if st.session_state.rewrite_competitors_data:
            scraped = [c for c in st.session_state.rewrite_competitors_data if c.get('scrape_success')]
            if scraped:
                avg = int(sum(c.get('word_count', 0) for c in scraped) / len(scraped))
                suggested = int(avg * 1.2)
                st.info(f"💡 Sugerencia: ~{suggested:,} palabras (20% más que promedio: {avg:,})")
    
    # ── 5. Keywords secundarias ─────────────────────────────────────
    with st.expander("🔑 Keywords SEO Adicionales", expanded=False):
        keywords_input = st.text_area(
            "Keywords secundarias (una por línea)",
            placeholder=f"{keyword}\nkeyword relacionada 1\nkeyword relacionada 2",
            height=80,
            label_visibility="collapsed"
        )
        
        config['keywords'] = [keyword] + [
            k.strip() for k in keywords_input.split('\n') 
            if k.strip() and k.strip() != keyword
        ]
    
    # ── 5b. Preguntas FAQ (PAA) ─────────────────────────────────────
    try:
        from ui.inputs import render_paa_selector as _render_paa
    except ImportError:
        try:
            from inputs import render_paa_selector as _render_paa
        except ImportError:
            _render_paa = None

    if _render_paa and keyword:
        faq_questions = _render_paa(keyword, key_prefix="rewrite_paa")
        if faq_questions:
            config['faq_questions'] = faq_questions

    # ── 6. Elementos visuales + Encabezados (colapsados) ────────────
    try:
        from ui.inputs import render_visual_elements_selector
    except ImportError:
        try:
            from inputs import render_visual_elements_selector
        except ImportError:
            render_visual_elements_selector = None
    
    if render_visual_elements_selector:
        visual_config = render_visual_elements_selector(key_prefix="rewrite_visual")
        if isinstance(visual_config, dict):
            config['visual_elements'] = visual_config.get('selected', [])
            config['visual_config'] = visual_config
        else:
            # Backward compat: si retorna lista simple
            config['visual_elements'] = visual_config or []
            config['visual_config'] = {'selected': visual_config or [], 'variants': {}, 'components_css': []}
    
    # Estructura de encabezados
    
    try:
        from ui.inputs import render_headings_config
    except ImportError:
        from inputs import render_headings_config
    
    config['headings_config'] = render_headings_config(key_prefix="rewrite_headings")
    
    return config


# ============================================================================
# VALIDACIÓN DE INPUTS
# ============================================================================

def validate_rewrite_inputs(
    keyword: str,
    competitors_data: Optional[List[Dict]],
    config: Dict,
    gsc_analysis: Optional[Dict],
    html_contents: List[Dict],
    rewrite_mode: str,
    rewrite_instructions: Optional[Dict] = None
) -> bool:
    """Valida que todos los inputs necesarios estén completos.
    
    v5.1: Objetivo ya no es obligatorio si hay instrucciones de reescritura suficientes.
    """
    
    missing = []
    
    if not keyword or len(keyword.strip()) < 3:
        missing.append("Keyword principal")
    
    # Validar según modo
    if rewrite_mode == RewriteMode.MERGE:
        if len(html_contents) < 2:
            missing.append("Al menos 2 artículos para fusionar")
    elif rewrite_mode == RewriteMode.DISAMBIGUATE:
        if len(html_contents) < 1:
            missing.append("Contenido conflictivo para desambiguar")
    else:
        # Modo single: necesita competidores O HTML
        has_competitors = competitors_data and len(competitors_data) > 0
        has_html = len(html_contents) > 0
        
        if not has_competitors and not has_html:
            missing.append("Análisis de competidores O contenido HTML a reescribir")
    
    # REC-9: Objetivo no obligatorio si hay instrucciones de reescritura
    has_objetivo = config.get('objetivo') and len(config['objetivo'].strip()) >= 10
    has_instructions = False
    if rewrite_instructions:
        total_items = (
            len(rewrite_instructions.get('improve', [])) +
            len(rewrite_instructions.get('add', [])) +
            len(rewrite_instructions.get('maintain', []))
        )
        has_instructions = total_items >= 2
    
    if not has_objetivo and not has_instructions:
        missing.append("Objetivo del contenido O al menos 2 instrucciones de reescritura")
    
    if not config.get('target_length') or config['target_length'] < 800:
        missing.append("Longitud objetivo válida (mínimo 800 palabras)")
    
    if missing:
        error_html = "<div style='background-color:#fff3cd;border:1px solid #ffc107;border-radius:5px;padding:10px;margin:10px 0;'>"
        error_html += "<span style='color:#856404;font-weight:bold;'>⚠️ Campos pendientes:</span>"
        error_html += "<ul style='margin:5px 0;padding-left:20px;color:#856404;'>"
        for m in missing:
            error_html += f"<li>{html_module.escape(str(m))}</li>"
        error_html += "</ul></div>"
        st.markdown(error_html, unsafe_allow_html=True)
        return False
    
    return True


# ============================================================================
# RESUMEN ANTES DE GENERAR (ACTUALIZADO v4.7.1)
# ============================================================================

def render_generation_summary(
    keyword: str, 
    config: Dict, 
    gsc_analysis: Optional[Dict],
    html_contents: List[Dict],
    main_product_data: Optional[Dict],
    rewrite_mode: str,
    rewrite_instructions: Dict,
    alternative_products: List[Dict] = None,
    posts_plps_links: List[Dict] = None
) -> None:
    """Muestra un resumen de la configuración antes de generar."""
    
    # Resumen compacto antes de generar
    mode_info = REWRITE_MODE_OPTIONS.get(rewrite_mode, {})
    st.markdown(f"**Resumen** — {mode_info.get('name', rewrite_mode)}")
    
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**Configuración básica:**")
            st.markdown(f"- 🎯 Keyword: `{keyword}`")
            st.markdown(f"- 📝 Longitud: `{config['target_length']:,}` palabras")
            
            if config.get('arquetipo_codigo'):
                arq_names = get_arquetipo_names()
                arq_name = arq_names.get(config['arquetipo_codigo'], config['arquetipo_codigo'])
                st.markdown(f"- 📚 Arquetipo: `{arq_name}`")
            
            if html_contents:
                total_words = sum(a.get('word_count', 0) for a in html_contents)
                st.markdown(f"- 📄 Artículos: `{len(html_contents)}` ({total_words:,} palabras)")
            
            if main_product_data and main_product_data.get('json_data'):
                title = main_product_data['json_data'].get('title', 'Producto')
                st.markdown(f"- 📦 Producto principal: `{title[:30]}...`")
            
            # Productos alternativos (NUEVO v4.7.1)
            if alternative_products:
                with_json = sum(1 for p in alternative_products if p.get('product_data'))
                st.markdown(f"- 🎯 Productos alternativos: `{len(alternative_products)}` ({with_json} con JSON)")
        
        with col2:
            st.markdown("**Instrucciones de reescritura:**")
            
            total = (
                len(rewrite_instructions.get('improve', [])) +
                len(rewrite_instructions.get('maintain', [])) +
                len(rewrite_instructions.get('remove', [])) +
                len(rewrite_instructions.get('add', []))
            )
            
            st.markdown(f"- ✨ Mejorar: `{len(rewrite_instructions.get('improve', []))}` puntos")
            st.markdown(f"- ✅ Mantener: `{len(rewrite_instructions.get('maintain', []))}` puntos")
            st.markdown(f"- 🗑️ Eliminar: `{len(rewrite_instructions.get('remove', []))}` puntos")
            st.markdown(f"- ➕ Añadir: `{len(rewrite_instructions.get('add', []))}` puntos")
            
            if st.session_state.rewrite_competitors_data:
                scraped = [c for c in st.session_state.rewrite_competitors_data if c.get('scrape_success')]
                st.markdown(f"- 🏆 Competidores: `{len(scraped)}`")
            
            # Enlaces editoriales (NUEVO v4.7.1)
            if posts_plps_links:
                with_context = sum(1 for l in posts_plps_links if l.get('html_content') or l.get('top_text'))
                st.markdown(f"- 📝 Enlaces editoriales: `{len(posts_plps_links)}` ({with_context} con contexto)")
    
    st.caption("✅ Todo listo — el pipeline generará borrador → análisis crítico → versión final.")


# ============================================================================
# PREPARACIÓN DE CONFIGURACIÓN FINAL (ACTUALIZADO v4.7.1)
# ============================================================================

def prepare_rewrite_config(
    keyword: str,
    competitors_data: List[Dict],
    rewrite_config: Dict,
    gsc_analysis: Optional[Dict],
    html_contents: List[Dict],
    rewrite_mode: str,
    rewrite_instructions: Dict,
    disambiguation_config: Optional[Dict],
    main_product_data: Optional[Dict],
    posts_plps_links: List[Dict],
    product_links: List[Dict],
    alternative_products: List[Dict] = None,
    products: List = None  # NUEVO v5.0: lista unificada de productos
) -> Dict:
    """Prepara la configuración completa para el proceso de generación."""
    
    # Configuración base
    config = {
        'mode': 'rewrite',
        'rewrite_mode': rewrite_mode,  # single/merge/disambiguate
        'keyword': keyword,
        'target_length': rewrite_config['target_length'],
        'objetivo': rewrite_config['objetivo'],
        'keywords': rewrite_config.get('keywords', [keyword]),
        'context': rewrite_config.get('context', ''),
        'arquetipo_codigo': rewrite_config.get('arquetipo_codigo'),
        'guiding_context': rewrite_config.get('guiding_context', ''),  # v1.3.0: briefing del arquetipo
        'headings_config': rewrite_config.get('headings_config'),  # v5.0
        'faq_questions': rewrite_config.get('faq_questions', []),  # PAA + custom FAQ questions
    }
    
    # =========================================================================
    # INSTRUCCIONES DE REESCRITURA (para los prompts)
    # =========================================================================
    config['rewrite_instructions'] = {
        'improve': rewrite_instructions.get('improve', []),
        'maintain': rewrite_instructions.get('maintain', []),
        'remove': rewrite_instructions.get('remove', []),
        'add': rewrite_instructions.get('add', []),
        'tone_changes': rewrite_instructions.get('tone_changes', ''),
        'structure_changes': rewrite_instructions.get('structure_changes', ''),
        'seo_focus': rewrite_instructions.get('seo_focus', ''),
        'additional_notes': rewrite_instructions.get('additional_notes', ''),
    }
    
    # =========================================================================
    # CONTENIDO HTML (puede ser uno o múltiples)
    # =========================================================================
    config['html_contents'] = html_contents
    
    # Compatibilidad con código antiguo que espera html_to_rewrite
    if html_contents:
        config['html_to_rewrite'] = html_contents[0].get('html', '')
    else:
        config['html_to_rewrite'] = None
    
    # =========================================================================
    # CONFIGURACIÓN DE DESAMBIGUACIÓN (si aplica)
    # =========================================================================
    if rewrite_mode == RewriteMode.DISAMBIGUATE and disambiguation_config:
        config['disambiguation'] = {
            'output_type': disambiguation_config.get('output_type', 'post'),
            'instructions': disambiguation_config.get('instructions', ''),
            'other_url': disambiguation_config.get('other_url', ''),
            'conflict_url': disambiguation_config.get('conflict_url', ''),
        }
    else:
        config['disambiguation'] = None
    
    # =========================================================================
    # PRODUCTO PRINCIPAL
    # =========================================================================
    if main_product_data:
        config['main_product'] = {
            'url': main_product_data.get('url', ''),
            'json_data': main_product_data.get('json_data')
        }
        config['pdp_data'] = main_product_data.get('json_data')
        config['pdp_json_data'] = main_product_data.get('json_data')
    else:
        config['main_product'] = None
        config['pdp_data'] = None
        config['pdp_json_data'] = None
    
    # =========================================================================
    # PRODUCTOS ALTERNATIVOS (NUEVO v4.7.1)
    # =========================================================================
    config['alternative_products'] = alternative_products or []
    
    # NUEVO v5.0: Lista unificada de productos
    config['products'] = [
        {
            'url': p.get('url', '') if isinstance(p, dict) else getattr(p, 'url', ''),
            'name': p.get('name', '') if isinstance(p, dict) else getattr(p, 'name', ''),
            'json_data': p.get('json_data') if isinstance(p, dict) else getattr(p, 'json_data', None),
            'role': p.get('role', 'principal') if isinstance(p, dict) else getattr(p, 'role', 'principal'),
        }
        for p in (products or [])
    ]
    
    # =========================================================================
    # ENLACES EDITORIALES (ACTUALIZADO v4.7.1)
    # =========================================================================
    config['editorial_links'] = []
    
    if posts_plps_links:
        for link in posts_plps_links:
            link_dict = {
                'url': link.get('url', ''),
                'anchor': link.get('anchor', ''),
                'text': link.get('anchor', ''),
                'type': 'editorial',
                'editorial_type': link.get('editorial_type', EditorialType.POST),
            }
            
            # Añadir campos HTML según tipo
            if link.get('editorial_type') == EditorialType.PLP:
                link_dict['top_text'] = link.get('top_text', '')
                link_dict['bottom_text'] = link.get('bottom_text', '')
            else:
                link_dict['html_content'] = link.get('html_content', '')
            
            config['editorial_links'].append(link_dict)
    
    # =========================================================================
    # ENLACES A PRODUCTOS
    # =========================================================================
    config['product_links'] = []
    
    if product_links:
        for link in product_links:
            link_dict = {
                'url': link.get('url', ''),
                'anchor': link.get('anchor', ''),
                'text': link.get('anchor', ''),
                'type': 'product'
            }
            if link.get('product_data'):
                link_dict['product_data'] = link['product_data']
            config['product_links'].append(link_dict)
    
    # =========================================================================
    # ENLACES UNIFICADOS (compatibilidad)
    # =========================================================================
    all_links = config['editorial_links'] + config['product_links']
    config['links'] = all_links
    config['enlaces'] = all_links  # Alias
    
    # Producto alternativo — derivado de products v5.0 (primer alternativo)
    first_alt = next(
        (p for p in (products or []) if (getattr(p, 'role', None) or p.get('role', '')) == 'alternativo'),
        None
    )
    if first_alt:
        alt_name = getattr(first_alt, 'name', None) or first_alt.get('name', '')
        alt_url = getattr(first_alt, 'url', None) or first_alt.get('url', '')
        config['producto_alternativo'] = {
            'url': alt_url,
            'text': alt_name,
        }
    else:
        config['producto_alternativo'] = {'url': '', 'text': ''}
    
    # Product links — derivar productos enlazados de products v5.0
    if products and not product_links:
        for p in (products or []):
            p_role = getattr(p, 'role', None) or p.get('role', '')
            p_url = getattr(p, 'url', None) or p.get('url', '')
            p_name = getattr(p, 'name', None) or p.get('name', '')
            p_json = getattr(p, 'json_data', None) or p.get('json_data')
            if p_role == 'enlazado' and p_url:
                link_dict = {
                    'url': p_url,
                    'anchor': p_name,
                    'text': p_name,
                    'type': 'product',
                }
                if p_json:
                    link_dict['product_data'] = p_json
                config['product_links'].append(link_dict)
        # Recalcular links unificados
        all_links = config['editorial_links'] + config['product_links']
        config['links'] = all_links
        config['enlaces'] = all_links
    
    # Datos de competidores
    if competitors_data:
        config['competitors_data'] = [
            c for c in competitors_data if c.get('scrape_success', False)
        ]
    else:
        config['competitors_data'] = []
    
    # Análisis de GSC
    config['gsc_analysis'] = gsc_analysis
    
    # Campos específicos de arquetipo
    config['campos_arquetipo'] = {}
    
    # Metadata
    config['timestamp'] = datetime.now().isoformat()
    config['data_source'] = 'semrush' if SEMRUSH_ENABLED else 'manual'
    
    return config


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'RewriteMode',
    'REWRITE_MODE_OPTIONS',
    'EditorialType',
    'EDITORIAL_TYPE_OPTIONS',
    'render_rewrite_section',
    'render_keyword_input',
    'render_html_content_section',
    'render_rewrite_instructions_section',
    'render_main_product_section',
    'render_alternative_products_section',
    'render_posts_plps_links_section',
    'render_product_links_section',
    'render_manual_competitors_input',
    'render_competitors_summary',
    'render_rewrite_configuration',
    'validate_rewrite_inputs',
    'render_generation_summary',
    'prepare_rewrite_config',
    'MAX_COMPETITORS',
    'MAX_ALTERNATIVE_PRODUCTS',
    'MAX_EDITORIAL_LINKS',
    'MAX_PRODUCT_LINKS',
    'DEFAULT_REWRITE_LENGTH',
    'COMPETITION_BEAT_FACTOR',
    'MAX_ARTICLES_TO_MERGE',
]
