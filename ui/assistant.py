# -*- coding: utf-8 -*-
"""
Assistant Mode - PcComponentes Content Generator
Versión 1.0.0 - 2026-02-11

Chat asistencial con acceso a funciones internas de Raichu:
- Verificar keyword en GSC (canibalización/cobertura)
- Consultar arquetipos disponibles y recomendar uno
- Analizar datos de producto (parsear JSON pegado en el chat)
- Consejos de redacción SEO según contexto
- Lanzar generación de contenido desde el chat

El asistente usa Claude con un system prompt que describe las herramientas
disponibles. Cuando detecta que necesita ejecutar una función interna,
la ejecuta en Python y añade el resultado al contexto de la conversación.

Autor: PcComponentes - Product Discovery & Content
"""

import json
import logging
import re
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

# ============================================================================
# IMPORTS CON MANEJO DE ERRORES
# ============================================================================

try:
    import streamlit as st
    _st_available = True
except ImportError:
    _st_available = False

try:
    from config.arquetipos import (
        get_arquetipo, get_arquetipo_names, get_arquetipo_by_name,
        get_guiding_questions, get_default_length, get_length_range,
        get_structure, get_visual_elements, get_arquetipo_summary,
        ARQUETIPOS,
    )
    _arquetipos_available = True
except ImportError:
    _arquetipos_available = False
    logger.warning("Módulo arquetipos no disponible para asistente")

try:
    from utils.gsc_utils import (
        search_existing_content,
        get_content_coverage_summary,
    )
    _gsc_available = True
except ImportError:
    _gsc_available = False
    logger.warning("Módulo GSC no disponible para asistente")

try:
    from utils.product_json_utils import (
        parse_product_json,
        validate_product_json,
        create_product_summary,
    )
    _product_json_available = True
except ImportError:
    _product_json_available = False
    logger.warning("Módulo product_json no disponible para asistente")

try:
    from config.design_system import (
        COMPONENT_REGISTRY,
        get_available_components,
        get_css_for_prompt,
        get_component_instructions,
    )
    _design_system_available = True
except ImportError:
    _design_system_available = False
    logger.warning("Módulo design_system no disponible para asistente")

try:
    from core.scraper import get_scraper
    _scraper_available = True
except ImportError:
    _scraper_available = False
    logger.warning("Módulo scraper no disponible para asistente")

try:
    from utils.serp_research import research_serp, format_for_display
    _serp_available = True
except ImportError:
    _serp_available = False
    logger.warning("Módulo serp_research no disponible para asistente")


# ============================================================================
# SYSTEM PROMPT
# ============================================================================

ASSISTANT_SYSTEM_PROMPT = """Eres el asistente de Raichu, el generador de contenido SEO de PcComponentes.
Tu rol es ayudar al equipo de contenido con consultas sobre redacción, verificación de keywords, 
selección de arquetipos, análisis de productos y configuración de elementos visuales.

IMPORTANTE: Responde siempre en español. Sé conciso y práctico.

## Tus capacidades

Tienes acceso a estas herramientas internas. Para usarlas, incluye el comando exacto en tu respuesta
entre corchetes. El sistema ejecutará la función y te dará el resultado.

### 1. Verificar keyword en GSC
Comprueba si ya hay contenido posicionando para una keyword.
Comando: [GSC_CHECK: keyword aquí]
Ejemplo: [GSC_CHECK: mejores portátiles gaming 2025]

### 2. Consultar arquetipos
Lista los tipos de contenido disponibles o recomienda uno.
Comando: [ARQUETIPOS_LIST] — para listar todos
Comando: [ARQUETIPO_INFO: ARQ-1] — para detalle de uno específico
Comando: [ARQUETIPO_RECOMENDAR: descripción del contenido] — para que recomiendes uno

### 3. Analizar JSON de producto
Si el usuario pega un JSON de producto, analízalo automáticamente.
Comando: [PRODUCTO_ANALIZAR: el JSON]

### 4. Investigar SERPs de Google
Busca qué contenido posiciona en Google para una keyword y analiza los resultados.
Comando: [SERP_RESEARCH: keyword aquí]
Ejemplo: [SERP_RESEARCH: mejores portátiles gaming 2025]
Esto buscará los top 10 resultados en Google.es, scrapeará los más relevantes y te dará un resumen
de qué están haciendo los competidores (estructura, longitud, enfoque, elementos visuales).
Úsalo SIEMPRE que el usuario quiera conceptualizar una idea o cuando necesites contexto antes de generar.

### 5. Elementos visuales del design system
Consulta los componentes CSS disponibles para enriquecer los artículos.
Comando: [VISUAL_LIST] — lista todos los componentes disponibles con sus variantes
Comando: [VISUAL_RECOMENDAR: tipo de artículo] — recomienda componentes según el tipo de contenido

Cuando el usuario pida generar contenido, sugiere qué componentes visuales usar según el tipo de artículo:
- Guías de compra / comparativas → tabla comparativa, mod_cards (cards horizontales), verdict, specs_list, check_list
- Listados / rankings → vcard_cards (cards verticales), badges, grid, faqs
- Reviews / análisis → callout, comparison_table, verdict, specs_list, price_highlight, faqs
- Ofertas / deals → callout_promo, callout_alert, badges, buttons, price_highlight
- Artículos informativos → toc, callout, light_table, faqs, intro_box
- Mega-guías / eventos → toc, section_divider, stats_grid, grid, callout, faqs, verdict
- Lanzamientos / producto nuevo → intro_box, specs_list, price_highlight, product_module, verdict
- Nota de prensa / Guest posting / Afiliados → SIN componentes visuales (contenido externo, HTML estándar)

### 6. Lanzar generación
Cuando el usuario quiera generar contenido y ya tenga keyword + arquetipo definidos.
Comando: [GENERAR: keyword=X, arquetipo=ARQ-X, longitud=XXXX, visual=comp1,comp2,comp3]
El parámetro visual es opcional pero recomendado. Valores posibles:
toc, callout, callout_promo, callout_alert, verdict, grid, badges, buttons, table, light_table, comparison_table,
faqs, intro_box, check_list, specs_list, product_module, price_highlight, stats_grid, section_divider,
mod_cards, vcard_cards

## Conocimiento del Design System

Tienes disponible un design system CSS con estos componentes:

**Estructura y layout:**
- toc: Tabla de Contenidos — índice de navegación clicable
- callout: Caja destacada con borde izquierdo naranja (tips, advertencias, datos clave)
- callout_promo: Caja promocional con degradado naranja (ofertas, campañas, Black Friday)
- callout_alert: Caja de alerta urgente con degradado naranja + borde oscuro (fechas límite, avisos críticos)
- verdict: Veredicto final — conclusión premium con degradado azul y enlaces dorados
- grid: Layout en rejilla de 2-3 columnas con cards
- badges: Etiquetas pill inline para categorías o tags
- buttons: Botones CTA (Ver producto, Comprar)

**Contenido enriquecido:**
- faqs: Preguntas frecuentes con pares pregunta/respuesta (importante para SEO/rich snippets)
- intro_box: Párrafo introductorio destacado con fondo gris (lead/resumen)
- check_list: Lista con checkmarks ✓ naranja (requisitos, verificaciones, compatibilidades)
- specs_list: Ficha técnica key-value con fondo gris (especificaciones de producto)
- product_module: Bloque destacado de producto con fondo gris y borde naranja
- price_highlight: Banner de precio con degradado naranja y tipografía grande
- stats_grid: Tarjetas con cifras grandes sobre fondo oscuro (métricas, datos impactantes)
- section_divider: Franja con degradado azul oscuro para separar bloques temáticos en mega-guías

**Tablas:**
- table: Tabla HTML estándar con estilos del CMS
- light_table: Tabla CSS Grid flexible (.lt) — soporta 2, 3 o 7 columnas con filas alternas (.zebra)
- comparison_table: Tabla comparativa con columna ganadora destacada

**Módulos CMS avanzados:**
- mod_cards: Cards horizontales con imagen, specs, chip y CTA — ideal para comparativas de 2-4 productos
- vcard_cards: Cards verticales con chip, lista y CTA — ideal para listados y recomendaciones

Cuando el usuario pida ayuda con la redacción o generar contenido, recomienda activamente qué componentes visuales usar para enriquecer el artículo según su tipo.

## Estilo de comunicación
- Habla como un compañero experto en SEO y contenido
- Sé directo y práctico, evita rodeos
- Usa datos concretos cuando los tengas (posiciones, clicks, impresiones)
- Si no tienes información suficiente, pregunta lo que necesites
- Cuando recomiendes un arquetipo, explica brevemente por qué

## Contexto del negocio
PcComponentes es un retailer de tecnología español. El contenido debe:
- Ser técnicamente preciso pero accesible
- Guiar al usuario hacia la compra sin ser agresivo
- Siempre ofrecer alternativas (nunca desalentar una compra sin proponer algo)
- Usar tono experto pero cercano
"""


# ============================================================================
# FUNCIONES INTERNAS (ejecutadas por el asistente)
# ============================================================================

def _execute_gsc_check(keyword: str) -> str:
    """Ejecuta verificación de keyword en GSC y devuelve resultado formateado."""
    if not _gsc_available:
        return "⚠️ Módulo GSC no disponible. No se puede verificar la keyword."

    try:
        summary = get_content_coverage_summary(keyword)
        matches = search_existing_content(keyword)

        if not summary.get('has_coverage') and not matches:
            return (
                f"✅ **No hay contenido existente para \"{keyword}\"**\n\n"
                "Puedes crear contenido nuevo sin riesgo de canibalización."
            )

        lines = [f"📊 **Resultados GSC para \"{keyword}\":**\n"]

        if summary.get('total_urls'):
            lines.append(f"- **URLs encontradas:** {summary['total_urls']}")
        if summary.get('total_clicks'):
            lines.append(f"- **Clicks totales:** {summary['total_clicks']}")

        # Matches detallados
        if matches:
            lines.append("\n**URLs que posicionan:**")
            for m in matches[:5]:
                url = m.get('url', '')
                pos = m.get('position', 0)
                clicks = m.get('clicks', 0)
                score = m.get('match_score', 0)
                risk = m.get('risk_label', '')
                lines.append(
                    f"- `{url[:60]}...` — Pos: #{pos:.0f}, "
                    f"Clicks: {clicks}, Score: {score} {risk}"
                )

        # Recomendación
        rec = summary.get('recommendation', '')
        if rec:
            lines.append(f"\n💡 **Recomendación:** {rec}")

        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Error en GSC check: {e}")
        return f"❌ Error al verificar keyword: {str(e)}"


def _execute_arquetipos_list() -> str:
    """Lista todos los arquetipos disponibles."""
    if not _arquetipos_available:
        return "⚠️ Módulo de arquetipos no disponible."

    names = get_arquetipo_names()
    lines = ["📋 **Arquetipos disponibles:**\n"]

    for code, name in names.items():
        arq = get_arquetipo(code)
        desc = arq.get('description', '') if arq else ''
        length = get_default_length(code)
        lines.append(f"- **{code}**: {name} (~{length} palabras)")
        if desc:
            lines.append(f"  _{desc}_")

    return "\n".join(lines)


def _execute_arquetipo_info(code: str) -> str:
    """Muestra información detallada de un arquetipo."""
    if not _arquetipos_available:
        return "⚠️ Módulo de arquetipos no disponible."

    code = code.strip().upper()
    arq = get_arquetipo(code)
    if not arq:
        # Intentar búsqueda por nombre
        arq = get_arquetipo_by_name(code)
        if not arq:
            return f"❌ Arquetipo '{code}' no encontrado. Usa [ARQUETIPOS_LIST] para ver los disponibles."

    arq_code = arq.get('code', code)
    lines = [f"📄 **{arq_code}: {arq.get('name', '')}**\n"]

    if arq.get('description'):
        lines.append(f"_{arq['description']}_\n")

    min_l, max_l = get_length_range(arq_code)
    default_l = get_default_length(arq_code)
    lines.append(f"**Longitud:** {min_l}-{max_l} palabras (recomendado: {default_l})")

    if arq.get('tone'):
        lines.append(f"**Tono:** {arq['tone']}")

    structure = get_structure(arq_code)
    if structure:
        lines.append("\n**Estructura recomendada:**")
        for s in structure:
            lines.append(f"  - {s}")

    visuals = get_visual_elements(arq_code)
    if visuals:
        lines.append(f"\n**Elementos visuales:** {', '.join(visuals)}")

    # Preguntas específicas del arquetipo (TODAS)
    questions = get_guiding_questions(arq_code, include_universal=False)
    if questions:
        lines.append(f"\n**Preguntas de briefing ({len(questions)}):**")
        for q in questions:
            lines.append(f"  - {q}")

    # Preguntas universales
    try:
        from config.arquetipos import PREGUNTAS_UNIVERSALES
        if PREGUNTAS_UNIVERSALES:
            lines.append(f"\n**Preguntas universales ({len(PREGUNTAS_UNIVERSALES)}) — aplican a todos:**")
            for q in PREGUNTAS_UNIVERSALES:
                lines.append(f"  - {q}")
    except ImportError:
        pass

    return "\n".join(lines)


def _execute_product_analysis(json_str: str) -> str:
    """Analiza un JSON de producto."""
    if not _product_json_available:
        return "⚠️ Módulo de análisis de producto no disponible."

    try:
        is_valid, error_msg = validate_product_json(json_str)
        if not is_valid:
            return f"❌ JSON inválido: {error_msg}"

        product = parse_product_json(json_str)
        if not product:
            return "❌ No se pudo parsear el JSON del producto."

        summary = create_product_summary(product)

        lines = [f"📦 **Producto: {summary['title']}**\n"]
        lines.append(f"- **Marca:** {summary['brand']}")
        lines.append(f"- **Familia:** {summary['family']}")
        lines.append(f"- **ID:** {summary['id']}")
        lines.append(f"- **Reviews:** {summary['total_reviews']}")
        lines.append(f"- **Imágenes:** {summary['image_count']}")

        if summary.get('key_attributes'):
            lines.append("\n**Especificaciones clave:**")
            for attr, val in list(summary['key_attributes'].items())[:8]:
                lines.append(f"  - {attr}: {val}")

        lines.append("\n✅ Producto analizado correctamente. Puedo usarlo para generar contenido.")

        return "\n".join(lines)

    except json.JSONDecodeError:
        return "❌ El texto proporcionado no es JSON válido."
    except Exception as e:
        return f"❌ Error al analizar producto: {str(e)}"


def _execute_visual_list() -> str:
    """Lista todos los componentes visuales del design system."""
    if not _design_system_available:
        return "⚠️ Módulo design_system no disponible."
    
    components = get_available_components()
    
    lines = ["🎨 **Componentes visuales disponibles:**\n"]
    
    # Agrupar por tipo
    base = [c for c in components if c['id'] not in ('mod_cards', 'vcard_cards', 'comparison_table', 'light_table', 'table')]
    tables = [c for c in components if c['id'] in ('table', 'light_table', 'comparison_table')]
    cms = [c for c in components if c['id'] in ('mod_cards', 'vcard_cards')]
    
    lines.append("**Elementos de artículo:**")
    for c in base:
        variants_str = ""
        if c.get('has_variants'):
            vnames = [v['label'] for v in c['variants'][:3]]
            variants_str = f" — Variantes: {', '.join(vnames)}"
        lines.append(f"- `{c['id']}`: {c['name']} — {c['description']}{variants_str}")
    
    lines.append("\n**Tablas:**")
    for c in tables:
        lines.append(f"- `{c['id']}`: {c['name']} — {c['description']}")
    
    lines.append("\n**Módulos CMS avanzados:**")
    for c in cms:
        lines.append(f"- `{c['id']}`: {c['name']} — {c['description']}")
        if c.get('has_variants'):
            for v in c['variants'][:4]:
                lines.append(f"  - `.{v['class']}`: {v['label']}")
    
    lines.append("\n💡 Usa estos IDs con [GENERAR: ..., visual=toc,callout,verdict]")
    
    return "\n".join(lines)


def _execute_visual_recommend(content_type: str) -> str:
    """Recomienda componentes visuales según el tipo de contenido."""
    content_type_lower = content_type.strip().lower()
    
    recommendations = {
        'guía de compra': {
            'components': ['toc', 'callout', 'comparison_table', 'mod_cards', 'specs_list', 'check_list', 'verdict', 'faqs'],
            'reason': 'La tabla comparativa y las cards horizontales permiten mostrar specs lado a lado. La specs_list y check_list son ideales para fichas técnicas y compatibilidades.',
        },
        'comparativa': {
            'components': ['toc', 'comparison_table', 'mod_cards', 'callout', 'specs_list', 'verdict', 'faqs'],
            'reason': 'La tabla de comparación con columna destacada es ideal. Specs_list para fichas técnicas de cada producto.',
        },
        'listado': {
            'components': ['toc', 'vcard_cards', 'badges', 'verdict', 'faqs'],
            'reason': 'Las cards verticales son perfectas para listados de productos. Los badges permiten etiquetar cada recomendación.',
        },
        'ranking': {
            'components': ['toc', 'vcard_cards', 'badges', 'grid', 'verdict', 'faqs'],
            'reason': 'Cards verticales para cada puesto del ranking. Badges para marcar "Mejor precio", "Mejor rendimiento", etc.',
        },
        'review': {
            'components': ['toc', 'intro_box', 'callout', 'specs_list', 'price_highlight', 'verdict', 'faqs'],
            'reason': 'Intro_box para el resumen. Specs_list para ficha técnica. Price_highlight para el precio. Callouts para pros/contras.',
        },
        'análisis': {
            'components': ['toc', 'callout', 'specs_list', 'comparison_table', 'verdict', 'faqs'],
            'reason': 'Similar a review pero con tabla comparativa si se compara con competidores.',
        },
        'lanzamiento': {
            'components': ['toc', 'intro_box', 'specs_list', 'price_highlight', 'product_module', 'verdict', 'faqs'],
            'reason': 'Intro_box para resumen de novedades. Specs_list para ficha técnica. Price_highlight y product_module para datos de compra.',
        },
        'oferta': {
            'components': ['callout_promo', 'callout_alert', 'badges', 'buttons', 'price_highlight', 'grid'],
            'reason': 'Callout_alert para urgencia. Price_highlight para precio. Badges para descuentos. CTAs directos.',
        },
        'deal': {
            'components': ['callout_promo', 'callout_alert', 'badges', 'buttons', 'price_highlight', 'vcard_cards'],
            'reason': 'Callout_alert para la oferta principal. Cards verticales si hay múltiples deals.',
        },
        'mega-guía': {
            'components': ['toc', 'section_divider', 'stats_grid', 'grid', 'callout', 'specs_list', 'faqs', 'verdict'],
            'reason': 'Section_divider para separar bloques temáticos. Stats_grid para cifras. TOC imprescindible en guías largas.',
        },
        'evento': {
            'components': ['toc', 'section_divider', 'stats_grid', 'grid', 'callout', 'verdict'],
            'reason': 'Section_divider para separar verticales del evento. Stats_grid para cifras.',
        },
        'informativo': {
            'components': ['toc', 'intro_box', 'callout', 'light_table', 'check_list', 'faqs', 'verdict'],
            'reason': 'TOC para navegación. Intro_box como lead. Check_list para verificaciones. FAQs para resolver dudas.',
        },
        'nota de prensa': {
            'components': [],
            'reason': 'Las notas de prensa se publican en medios externos que aplican su propio formato. No usar componentes CSS de PcComponentes. Generar HTML limpio con estructura semántica estándar (h2, p, blockquote para citas).',
        },
        'comunicado': {
            'components': [],
            'reason': 'Los comunicados van a medios externos. No necesitan componentes visuales propietarios, solo HTML semántico estándar.',
        },
        'afiliados': {
            'components': [],
            'reason': 'El contenido de afiliación se publica en webs externas con su propio CSS. Generar HTML estándar con tablas, listas y headings semánticos que cualquier CMS pueda renderizar.',
        },
        'afiliación': {
            'components': [],
            'reason': 'Contenido para webs externas: usar HTML estándar (table, ul, h2/h3) sin componentes CSS propietarios de PcComponentes.',
        },
        'guest posting': {
            'components': [],
            'reason': 'El guest post se publica en un blog/medio externo. Usar solo HTML estándar que sea compatible con cualquier CMS. Sin componentes visuales propietarios.',
        },
        'guest post': {
            'components': [],
            'reason': 'Artículo para publicación externa. Solo HTML semántico estándar, sin estilos propietarios.',
        },
    }
    
    # Buscar match por keywords
    matched = None
    for key, rec in recommendations.items():
        if key in content_type_lower or content_type_lower in key:
            matched = rec
            break
    
    if not matched:
        # Default
        matched = {
            'components': ['toc', 'callout', 'verdict'],
            'reason': f'Recomendación base para "{content_type}". Puedes ajustar según las necesidades del artículo.',
        }
    
    comps_str = ', '.join(matched['components'])
    lines = [
        f"🎨 **Componentes recomendados para \"{content_type}\":**\n",
        f"```\nvisual={comps_str}\n```\n",
        f"**¿Por qué?** {matched['reason']}\n",
        "**Componentes sugeridos:**",
    ]
    
    for comp_id in matched['components']:
        comp = COMPONENT_REGISTRY.get(comp_id) if _design_system_available else None
        name = comp.name if comp else comp_id
        desc = comp.description if comp else ''
        lines.append(f"- `{comp_id}`: {name} — {desc}")
    
    lines.append(f"\n💡 Usa en el comando: [GENERAR: keyword=..., arquetipo=..., visual={comps_str}]")
    
    return "\n".join(lines)


def _execute_serp_research(keyword: str) -> str:
    """Investiga los top resultados de búsqueda para una keyword."""
    if not _serp_available:
        return "⚠️ Módulo serp_research no disponible."

    research = research_serp(keyword)
    return format_for_display(research)


# ============================================================================
# PROCESAMIENTO DE COMANDOS
# ============================================================================

# Patrones de comandos en la respuesta del asistente
COMMAND_PATTERNS = {
    'gsc_check': re.compile(r'\[GSC_CHECK:\s*(.+?)\]', re.IGNORECASE),
    'arquetipos_list': re.compile(r'\[ARQUETIPOS_LIST\]', re.IGNORECASE),
    'arquetipo_info': re.compile(r'\[ARQUETIPO_INFO:\s*(.+?)\]', re.IGNORECASE),
    'arquetipo_recomendar': re.compile(r'\[ARQUETIPO_RECOMENDAR:\s*(.+?)\]', re.IGNORECASE),
    'producto_analizar': re.compile(r'\[PRODUCTO_ANALIZAR:\s*(.+?)\]', re.IGNORECASE | re.DOTALL),
    'serp_research': re.compile(r'\[SERP_RESEARCH:\s*(.+?)\]', re.IGNORECASE),
    'visual_list': re.compile(r'\[VISUAL_LIST\]', re.IGNORECASE),
    'visual_recomendar': re.compile(r'\[VISUAL_RECOMENDAR:\s*(.+?)\]', re.IGNORECASE),
    'generar': re.compile(r'\[GENERAR:\s*(.+?)\]', re.IGNORECASE),
}


def detect_and_execute_commands(assistant_response: str) -> Tuple[str, List[Dict[str, str]]]:
    """
    Detecta comandos en la respuesta del asistente y los ejecuta.

    Returns:
        Tuple[cleaned_response, tool_results]
        - cleaned_response: respuesta sin los comandos
        - tool_results: lista de {command, result} ejecutados
    """
    tool_results = []
    cleaned = assistant_response

    # GSC Check
    for match in COMMAND_PATTERNS['gsc_check'].finditer(assistant_response):
        keyword = match.group(1).strip()
        result = _execute_gsc_check(keyword)
        tool_results.append({'command': f'GSC_CHECK: {keyword}', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Arquetipos list
    for match in COMMAND_PATTERNS['arquetipos_list'].finditer(assistant_response):
        result = _execute_arquetipos_list()
        tool_results.append({'command': 'ARQUETIPOS_LIST', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Arquetipo info
    for match in COMMAND_PATTERNS['arquetipo_info'].finditer(assistant_response):
        code = match.group(1).strip()
        result = _execute_arquetipo_info(code)
        tool_results.append({'command': f'ARQUETIPO_INFO: {code}', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Arquetipo recomendar (Claude recomienda, ejecutamos lista como contexto)
    for match in COMMAND_PATTERNS['arquetipo_recomendar'].finditer(assistant_response):
        description = match.group(1).strip()
        result = _execute_arquetipos_list()
        tool_results.append({'command': f'ARQUETIPO_RECOMENDAR: {description}', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Producto analizar
    for match in COMMAND_PATTERNS['producto_analizar'].finditer(assistant_response):
        json_str = match.group(1).strip()
        result = _execute_product_analysis(json_str)
        tool_results.append({'command': 'PRODUCTO_ANALIZAR', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Visual list
    for match in COMMAND_PATTERNS['visual_list'].finditer(assistant_response):
        result = _execute_visual_list()
        tool_results.append({'command': 'VISUAL_LIST', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Visual recomendar
    for match in COMMAND_PATTERNS['visual_recomendar'].finditer(assistant_response):
        content_type = match.group(1).strip()
        result = _execute_visual_recommend(content_type)
        tool_results.append({'command': f'VISUAL_RECOMENDAR: {content_type}', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # SERP Research
    for match in COMMAND_PATTERNS['serp_research'].finditer(assistant_response):
        keyword = match.group(1).strip()
        result = _execute_serp_research(keyword)
        tool_results.append({'command': f'SERP_RESEARCH: {keyword}', 'result': result})
        cleaned = cleaned.replace(match.group(0), '')

    # Generar — se marca para que app.py lo ejecute
    for match in COMMAND_PATTERNS['generar'].finditer(assistant_response):
        params_str = match.group(1).strip()
        tool_results.append({
            'command': 'GENERAR',
            'result': f'⏳ Preparando generación con: {params_str}',
            'params': params_str,
            'action': 'generate',
        })
        cleaned = cleaned.replace(match.group(0), '')

    cleaned = cleaned.strip()
    return cleaned, tool_results


def parse_generation_params(params_str: str) -> Dict[str, str]:
    """
    Parsea parámetros de generación del comando [GENERAR: ...].

    Args:
        params_str: "keyword=X, arquetipo=ARQ-X, longitud=XXXX, visual=toc,callout,verdict"

    Returns:
        Dict con keyword, arquetipo, longitud, visual
    """
    params = {}
    
    # visual= va al final y contiene comas, así que lo extraemos primero
    visual_match = re.search(r'visual\s*=\s*(.+?)$', params_str, re.IGNORECASE)
    remaining = params_str
    if visual_match:
        params['visual'] = visual_match.group(1).strip().rstrip(',')
        remaining = params_str[:visual_match.start()].rstrip(', ')
    
    # Parsear el resto normalmente
    for part in remaining.split(','):
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.strip().lower()] = value.strip()
    
    return params


# ============================================================================
# DETECCIÓN DE JSON EN MENSAJES DEL USUARIO
# ============================================================================

def detect_product_json_in_message(message: str) -> Optional[str]:
    """
    Detecta si el mensaje del usuario contiene un JSON de producto.

    Busca patrones como {"product_id": ..., "title": ...}

    Returns:
        El JSON string si se detecta, None en caso contrario
    """
    # Intentar encontrar JSON válido
    # Primero buscar bloques de código
    code_block = re.search(r'```(?:json)?\s*(\{.+?\})\s*```', message, re.DOTALL)
    if code_block:
        try:
            json.loads(code_block.group(1))
            return code_block.group(1)
        except json.JSONDecodeError:
            pass

    # Luego buscar JSON directo que empiece con { o [
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start_idx = message.find(start_char)
        if start_idx == -1:
            continue

        # Encontrar el cierre correspondiente
        depth = 0
        for i in range(start_idx, len(message)):
            if message[i] == start_char:
                depth += 1
            elif message[i] == end_char:
                depth -= 1
            if depth == 0:
                candidate = message[start_idx:i + 1]
                try:
                    parsed = json.loads(candidate)
                    # Verificar que tenga campos de producto
                    if isinstance(parsed, dict):
                        if any(k in parsed for k in ['product_id', 'title', 'legacy_id']):
                            return candidate
                    elif isinstance(parsed, list) and parsed:
                        if isinstance(parsed[0], dict) and any(
                            k in parsed[0] for k in ['product_id', 'title', 'legacy_id']
                        ):
                            return candidate
                except json.JSONDecodeError:
                    pass
                break

    return None


# ============================================================================
# RENDERIZADO DEL CHAT
# ============================================================================

def initialize_chat_state() -> None:
    """Inicializa el estado del chat si no existe."""
    if 'assistant_messages' not in st.session_state:
        st.session_state.assistant_messages = []
    if 'assistant_generation_pending' not in st.session_state:
        st.session_state.assistant_generation_pending = None


def render_chat_messages() -> None:
    """Renderiza los mensajes del historial del chat."""
    for msg in st.session_state.assistant_messages:
        role = msg.get('role', 'user')
        content = msg.get('content', '')

        with st.chat_message(role):
            st.markdown(content)

            # Mostrar resultados de herramientas si hay
            tool_results = msg.get('tool_results', [])
            for tr in tool_results:
                with st.expander(f"🔧 {tr['command']}", expanded=True):
                    st.markdown(tr['result'])


def build_messages_for_api() -> List[Dict[str, str]]:
    """
    Construye la lista de mensajes para la API de Claude.
    Incluye el historial completo incluyendo resultados de herramientas.
    """
    messages = []

    for msg in st.session_state.assistant_messages:
        role = msg['role']
        content = msg['content']

        # Para mensajes del asistente, incluir resultados de herramientas
        if role == 'assistant' and msg.get('tool_results'):
            tool_context = "\n\n".join(
                f"[Resultado de {tr['command']}]:\n{tr['result']}"
                for tr in msg['tool_results']
            )
            content = f"{content}\n\n{tool_context}"

        messages.append({'role': role, 'content': content})

    return messages


def get_system_prompt() -> str:
    """
    Devuelve el system prompt con información dinámica
    sobre los módulos disponibles.
    """
    availability = []
    if _gsc_available:
        availability.append("✅ GSC: disponible")
    else:
        availability.append("❌ GSC: no disponible")

    if _arquetipos_available:
        availability.append("✅ Arquetipos: disponible")
    else:
        availability.append("❌ Arquetipos: no disponible")

    if _product_json_available:
        availability.append("✅ Análisis de producto: disponible")
    else:
        availability.append("❌ Análisis de producto: no disponible")

    if _design_system_available:
        n_components = len(get_available_components())
        availability.append(f"✅ Design System: disponible ({n_components} componentes)")
    else:
        availability.append("❌ Design System: no disponible")

    if _serp_available:
        availability.append("✅ Investigación SERP: disponible (búsqueda + scraping)")
    else:
        availability.append("❌ Investigación SERP: no disponible")

    availability_str = "\n".join(availability)

    return f"{ASSISTANT_SYSTEM_PROMPT}\n\n## Estado de herramientas\n{availability_str}"


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    # State
    'initialize_chat_state',
    # Rendering
    'render_chat_messages',
    # API
    'build_messages_for_api',
    'get_system_prompt',
    # Processing
    'detect_and_execute_commands',
    'detect_product_json_in_message',
    'parse_generation_params',
    # Constants
    'ASSISTANT_SYSTEM_PROMPT',
]
