# -*- coding: utf-8 -*-
"""
New Content Prompts - PcComponentes Content Generator
Versión 4.9.3

Prompts para generación de contenido nuevo en 3 etapas.

CAMBIOS v4.9.3:
- FIX: Font-family corregido de 'Inter' a 'Open Sans' para coincidir con el design system real de PcComponentes

CAMBIOS v4.9.1:
- FIX: Tablas con table-layout:fixed para alinear columnas correctamente
- FIX: Más espaciado entre headings y cajas (margin-bottom en h2/h3)
- FIX: Mayor padding interno en grid-item y product-module
- FIX: Enlaces en fondos oscuros ahora son visibles (dorado en verdict-box, blanco en callout-bf)
- Nueva variable CSS --space-xl:32px para espaciados mayores

CAMBIOS v4.9.0:
- Fusión de pdp_data (n8n) + pdp_json_data (JSON subido)
- Procesamiento de product_data en enlaces PDP
- Soporte completo para alternative_product.json_data
- Implementación de visual_elements (TOC, tablas, callouts, etc.)
- Nuevo parámetro pdp_json_data en build_new_content_prompt_stage1

CARACTERÍSTICAS:
- Funciona igual de bien CON o SIN datos de producto
- CON datos: usa ventajas/desventajas/opiniones para contenido auténtico
- SIN datos: instrucciones alternativas basadas en conocimiento general
- Tono de marca PcComponentes integrado (desde config/brand.py)
- Instrucciones anti-IA para evitar patrones artificiales

CAMPOS DE PRODUCTO SOPORTADOS (del Dict pdp_data o pdp_json_data):
| Campo              | Tipo         | Uso en Prompt                         |
|--------------------|--------------|---------------------------------------|
| title              | str          | Nombre del producto                   |
| brand_name         | str          | Marca                                 |
| family_name        | str          | Categoría                             |
| attributes         | Dict         | Especificaciones técnicas             |
| total_comments     | int          | Credibilidad (N valoraciones)         |
| advantages_list    | List[str]    | Ventajas procesadas → argumentar      |
| disadvantages_list | List[str]    | Desventajas → honestidad              |
| top_comments       | List[str]    | Opiniones → lenguaje natural          |
| has_user_feedback  | bool         | Flag si hay feedback de usuarios      |

Autor: PcComponentes - Product Discovery & Content
"""

from typing import Dict, List, Optional, Any

__version__ = "4.9.4"

# ============================================================================
# ARQUETIPOS QUE REQUIEREN MINI-HISTORIAS (solo si hay reviews disponibles)
# Son los arquetipos orientados a producto donde las experiencias de usuario
# reales aportan credibilidad y engagement.
# ============================================================================
ARQUETIPOS_CON_MINI_STORIES = {
    "ARQ-1",   # Artículos SEO con Enlaces Internos
    "ARQ-4",   # Review / Análisis de Producto
    "ARQ-5",   # Comparativa A vs B
    "ARQ-6",   # Guía de Compra
    "ARQ-7",   # Roundup / Mejores X
    "ARQ-8",   # Lista de Recomendaciones
    "ARQ-9",   # Mejores Productos por Precio
    "ARQ-10",  # Productos para Perfil Específico
    "ARQ-19",  # Ofertas y Promociones
    "ARQ-20",  # Black Friday / Cyber Monday
    "ARQ-21",  # Setup Gaming Completo
    "ARQ-22",  # Requisitos de Videojuegos
    "ARQ-23",  # Streaming y Creación de Contenido
    "ARQ-24",  # Periféricos Gaming
    "ARQ-25",  # Consolas y Gaming Portátil
    "ARQ-26",  # Workstation Profesional
    "ARQ-27",  # Teletrabajo y Home Office
    "ARQ-31",  # Hogar Inteligente / Smart Home
    "ARQ-32",  # Fotografía y Vídeo
    "ARQ-33",  # Movilidad y Gadgets
}

# Importar constantes de tono desde prompts.brand_tone (fuente única de tono)
try:
    from prompts.brand_tone import get_tone_instructions, get_system_prompt_base, EJEMPLOS_TONO_STAGE3
except ImportError:
    try:
        from brand_tone import get_tone_instructions, get_system_prompt_base, EJEMPLOS_TONO_STAGE3
    except ImportError:
        # Fallback inline si no existen las funciones
        def get_tone_instructions(has_product_data: bool = False) -> str:
            return ""
        def get_system_prompt_base() -> str:
            return "Eres un redactor SEO experto de PcComponentes."
        EJEMPLOS_TONO_STAGE3 = ""


# ============================================================================
# CSS MINIFICADO v4.9.2
# Correcciones:
# - Tablas: table-layout:fixed para alinear columnas correctamente
# - Espaciado: más margen entre headings y cajas, padding interno aumentado
# - Enlaces: color claro en fondos oscuros (verdict-box, callout-bf)
# - Callouts: padding ajustado, p:last-child sin margin, responsive
# ============================================================================

# CSS_INLINE_MINIFIED ahora se carga dinámicamente desde design_system.py
# Fallback hardcodeado solo si design_system no está disponible
_CSS_FALLBACK = """:root{--orange-900:#FF6000;--blue-m-900:#170453;--white:#FFFFFF;--gray-100:#F5F5F5;--gray-200:#E5E5E5;--gray-700:#404040;--gray-900:#171717;--space-md:16px;--space-lg:24px;--space-xl:32px;--radius-md:8px;}
.contentGenerator__main,.contentGenerator__faqs,.contentGenerator__verdict{font-family:'Open Sans',sans-serif;line-height:1.7;color:var(--gray-900);max-width:100%;}
.contentGenerator__main h2,.contentGenerator__main h3{margin-bottom:var(--space-lg);}
.kicker{display:inline-block;background:var(--orange-900);color:var(--white);padding:4px 12px;font-size:12px;font-weight:700;text-transform:uppercase;border-radius:4px;margin-bottom:16px;}
.toc{background:var(--gray-100);border-radius:var(--radius-md);padding:var(--space-lg);margin:var(--space-lg) 0;}
.toc__title{font-weight:700;margin-bottom:12px;}.toc__list{margin:0;padding-left:20px;}.toc__list li{margin-bottom:8px;}
.faqs__item{border-bottom:1px solid var(--gray-200);padding:var(--space-md) 0;}.faqs__question{font-weight:600;margin-bottom:8px;}
.verdict-box{background:linear-gradient(135deg,var(--blue-m-900),#2E1A7A);color:var(--white);padding:var(--space-xl);border-radius:var(--radius-md);margin-top:var(--space-lg);}
.verdict-box a{color:#FFD700;text-decoration:underline;}.verdict-box a:hover{color:var(--white);}.verdict-box p:last-child{margin-bottom:0;}
.callout{background:var(--gray-100);border-left:4px solid var(--orange-900);padding:var(--space-md) var(--space-lg);margin:var(--space-lg) 0;border-radius:0 var(--radius-md) var(--radius-md) 0;}.callout p:last-child{margin-bottom:0;}
.callout-bf{background:linear-gradient(135deg,#FF6000,#FF8533);color:var(--white);padding:var(--space-lg);border-radius:var(--radius-md);text-align:center;margin:var(--space-lg) 0;}
.callout-alert{background:linear-gradient(135deg,#FF6000,#FF8533);color:var(--white);padding:var(--space-lg);border-radius:var(--radius-md);text-align:center;margin:var(--space-lg) 0;border-left:6px solid #CC4D00;}
.callout-alert p:first-of-type{font-weight:700;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px;font-size:1.2em;}
table{width:100%;border-collapse:collapse;margin:var(--space-lg) 0;table-layout:fixed;font-size:15px;}
thead th{background:var(--gray-100);font-weight:700;text-align:left;padding:12px 16px;border-bottom:2px solid var(--gray-200);}
tbody td{padding:10px 16px;text-align:left;border-bottom:1px solid var(--gray-200);}
tbody tr:hover{background:rgba(0,0,0,0.02);}
.table-responsive{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:var(--space-lg) 0;}
.table-responsive table{margin:0;}
@media(max-width:768px){table{table-layout:auto;font-size:14px;}thead th,tbody td{padding:8px 10px;}.table-responsive{border:1px solid var(--gray-200);border-radius:var(--radius-md);}}
.grid{display:grid;gap:16px;margin:var(--space-lg) 0;}
.grid-layout{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:var(--space-lg);margin-top:var(--space-lg);}
.grid-item{background:var(--white);border:1px solid var(--gray-200);border-radius:var(--radius-md);padding:var(--space-md) var(--space-lg);}
.grid-item.destacado{border:2px solid var(--orange-900);position:relative;}.grid-item.destacado::before{content:'DESTACADO';position:absolute;top:-10px;left:20px;background:var(--orange-900);color:var(--white);padding:2px 8px;font-size:11px;border-radius:4px;}
.intro{font-size:17px;color:#1a1a1a;margin-bottom:32px;padding:20px;background-color:var(--gray-100);border-radius:var(--radius-md);line-height:1.8;}
.check-list{list-style:none;padding-left:0;}.check-list li{padding-left:28px;position:relative;margin-bottom:12px;}.check-list li::before{content:"✓";position:absolute;left:0;color:var(--orange-900);font-weight:700;font-size:18px;}
.specs-list{background-color:var(--gray-100);padding:20px 24px;border-radius:var(--radius-md);margin:28px 0;}.specs-list h4{font-weight:600;margin:0 0 14px 0;}.specs-list ul{list-style:none;margin:0;padding:0;}.specs-list ul li{padding:8px 0;border-bottom:1px solid #e0e0e0;display:flex;justify-content:space-between;font-size:15px;}.specs-list ul li:last-child{border-bottom:none;}
.product-module{background:var(--gray-100);padding:var(--space-lg);border-radius:var(--radius-md);margin:var(--space-lg) 0;border-left:4px solid var(--orange-900);}.product-module h4{margin-top:0;margin-bottom:12px;color:var(--orange-900);}.product-module a{color:var(--orange-900);font-weight:600;}
.video-container{position:relative;padding-bottom:56.25%;height:0;overflow:hidden;margin:28px 0;border-radius:var(--radius-md);}.video-container iframe{position:absolute;top:0;left:0;width:100%;height:100%;border-radius:var(--radius-md);}
.price-highlight{background:linear-gradient(90deg,#FF6000,#FF8640);color:var(--white);padding:20px 28px;border-radius:var(--radius-md);margin:28px 0;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;}.price-highlight .price{font-size:28px;font-weight:700;}.price-highlight .price-label{font-size:14px;color:rgba(255,255,255,0.9);}
.compact-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:var(--space-md);margin:var(--space-lg) 0;}
.compact-card{background:var(--white);border-top:3px solid var(--orange-900);padding:var(--space-md);box-shadow:0 1px 4px rgba(0,0,0,0.08);}
.compact-card__title{font-size:15px;font-weight:700;margin:0 0 10px 0;color:var(--ink,#171717);display:flex;align-items:center;gap:10px;}
.compact-card__icon{width:28px;height:28px;background:var(--orange-900);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.compact-card__icon svg{width:16px;height:16px;fill:var(--white);}
.compact-card ul{font-size:14px;margin:0;padding-left:18px;color:var(--muted,#404040);line-height:1.6;}
.compact-card ul li{margin-bottom:4px;}.compact-card ul li:last-child{margin-bottom:0;}
.use-cases{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:var(--space-md);margin:var(--space-lg) 0;}
.use-case{background:var(--gray-100);border-radius:var(--radius-md);padding:var(--space-md);border-left:3px solid var(--blue-m-900);}
.use-case__title{font-size:14px;font-weight:700;margin:0 0 8px 0;color:var(--blue-m-900);display:flex;align-items:center;gap:10px;}
.use-case__icon{width:26px;height:26px;background:var(--blue-m-900);border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0;}
.use-case__icon svg{width:14px;height:14px;fill:var(--white);}
.use-case p{font-size:13px;margin:0 0 8px 0;color:var(--muted,#404040);line-height:1.5;}
.use-case p:last-child{margin-bottom:0;}.use-case strong{color:var(--ink,#171717);}
.use-case a{color:var(--orange-900);font-weight:600;}
@media(max-width:768px){.compact-cards,.use-cases{grid-template-columns:1fr;}}"""


def _get_css_for_prompt(
    visual_elements: Optional[List[str]] = None,
    visual_config: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Obtiene el CSS para inyectar en el prompt.
    
    Usa design_system.py para tree-shaking del CSS base (cms_compatible.css).
    Complementa con _CSS_FALLBACK para componentes que design_system no cubra
    (callout_alert, intro_box, check_list, specs_list, product_module, price_highlight).
    
    Args:
        visual_elements: Lista de IDs de componentes seleccionados
        visual_config: Config completa con variants y components_css
        
    Returns:
        CSS minificado listo para <style>
    """
    selected = visual_elements or []
    if visual_config and isinstance(visual_config, dict):
        selected = visual_config.get('selected', selected)
    
    # 1. Intentar design_system (tree-shaking desde cms_compatible.css)
    ds_css = ""
    try:
        from config.design_system import get_css_for_prompt
        ds_css = get_css_for_prompt(selected_components=selected, minify=True)
    except ImportError:
        return _CSS_FALLBACK
    
    # 2. Complementar con fallback para componentes que design_system no cubre
    _COMPONENT_MARKERS = {
        'callout_promo': '.callout-bf',
        'callout_alert': '.callout-alert',
        'intro_box': '.intro{',
        'check_list': '.check-list',
        'specs_list': '.specs-list',
        'product_module': '.product-module',
        'price_highlight': '.price-highlight',
    }
    
    missing_parts = []
    ds_lower = ds_css.lower()
    for comp_id in selected:
        marker = _COMPONENT_MARKERS.get(comp_id)
        if marker and marker.lower() not in ds_lower:
            # Extraer reglas CSS del fallback para este componente
            import re as _re
            prefix = marker.rstrip('{')
            pattern = _re.compile(
                _re.escape(prefix) + r'[^{]*\{[^}]*\}', _re.IGNORECASE
            )
            for match in pattern.finditer(_CSS_FALLBACK):
                missing_parts.append(match.group(0))
    
    if missing_parts:
        ds_css = ds_css + ' ' + ' '.join(missing_parts)
    
    return ds_css


# Backward compat: mantener CSS_INLINE_MINIFIED como referencia
CSS_INLINE_MINIFIED = _CSS_FALLBACK


# ============================================================================
# FUSIÓN DE DATOS DE PRODUCTO
# ============================================================================

def _merge_product_data(
    pdp_data: Optional[Dict],
    pdp_json_data: Optional[Dict]
) -> Optional[Dict]:
    """
    Fusiona datos de producto de múltiples fuentes.
    
    Prioridad:
    1. pdp_json_data (JSON subido por usuario) - más completo
    2. pdp_data (datos de n8n webhook) - fallback
    
    Args:
        pdp_data: Datos del webhook n8n
        pdp_json_data: Datos del JSON subido
        
    Returns:
        Dict fusionado con todos los datos disponibles
    """
    if not pdp_data and not pdp_json_data:
        return None
    
    # Si solo hay una fuente, usarla
    if not pdp_data:
        return pdp_json_data
    if not pdp_json_data:
        return pdp_data
    
    # Fusionar: pdp_json_data tiene prioridad
    merged = dict(pdp_data)  # Copiar base
    
    # Campos de pdp_json_data que tienen prioridad
    priority_fields = [
        'title', 'description', 'brand_name', 'family_name',
        'attributes', 'images', 'totalComments', 'total_comments',
        'advantages', 'disadvantages', 'comments',
        'advantages_list', 'disadvantages_list', 'top_comments',
        'has_user_feedback'
    ]
    
    for field in priority_fields:
        if field in pdp_json_data and pdp_json_data[field]:
            merged[field] = pdp_json_data[field]
    
    # Normalizar campos
    if 'totalComments' in merged and 'total_comments' not in merged:
        merged['total_comments'] = merged['totalComments']
    
    # Procesar ventajas/desventajas si vienen como string
    if 'advantages' in merged and isinstance(merged['advantages'], str):
        if 'advantages_list' not in merged:
            merged['advantages_list'] = _parse_advantages_string(merged['advantages'])
    
    if 'disadvantages' in merged and isinstance(merged['disadvantages'], str):
        if 'disadvantages_list' not in merged:
            merged['disadvantages_list'] = _parse_advantages_string(merged['disadvantages'])
    
    # Procesar comentarios
    if 'comments' in merged and isinstance(merged['comments'], list):
        if 'top_comments' not in merged:
            merged['top_comments'] = _extract_comment_texts(merged['comments'])
    
    # Flag de feedback
    if 'has_user_feedback' not in merged:
        merged['has_user_feedback'] = bool(
            merged.get('advantages_list') or 
            merged.get('disadvantages_list') or 
            merged.get('top_comments')
        )
    
    return merged


def _parse_advantages_string(text: str, max_items: int = 10) -> List[str]:
    """Parsea string de ventajas/desventajas a lista."""
    if not text:
        return []
    
    # Normalizar separadores
    normalized = text.replace('\n\n', '\n')
    items = [item.strip() for item in normalized.split('\n')]
    
    # Filtrar
    skip_words = ['ninguno', 'nada', 'ninguna', 'n/a', '-', '']
    filtered = []
    for item in items:
        if not item or len(item) < 8:
            continue
        if item.lower().strip() in skip_words:
            continue
        filtered.append(item)
    
    return filtered[:max_items]


def _extract_comment_texts(comments: List[Any], max_items: int = 5) -> List[str]:
    """Extrae textos de comentarios."""
    if not comments:
        return []
    
    result = []
    for item in comments:
        if isinstance(item, dict):
            text = item.get('opinion') or item.get('text') or item.get('content')
            if text and isinstance(text, str) and len(text) >= 15:
                result.append(text.strip())
        elif isinstance(item, str) and len(item) >= 15:
            result.append(item.strip())
    
    return result[:max_items]


# ============================================================================
# FORMATEAR DATOS DE PRODUCTO PARA PROMPT
# ============================================================================

def _format_product_section(pdp_data: Optional[Dict]) -> tuple:
    """
    Formatea datos del producto para el prompt.
    
    Args:
        pdp_data: Dict con datos del producto (ya fusionados)
        
    Returns:
        Tuple[section_text: str, has_feedback: bool]
    """
    if not pdp_data:
        return "", False
    
    lines = []
    has_feedback = pdp_data.get('has_user_feedback', False)
    
    lines.append("=" * 60)
    lines.append("[PRODUCTO] DATOS DEL PRODUCTO PRINCIPAL")
    lines.append("=" * 60)
    
    # Info básica
    title = pdp_data.get('title') or pdp_data.get('name', '')
    if title:
        lines.append(f"\n**Producto:** {title}")
    
    brand = pdp_data.get('brand_name') or pdp_data.get('brand', '')
    if brand:
        lines.append(f"**Marca:** {brand}")
    
    family = pdp_data.get('family_name') or pdp_data.get('family', '')
    if family:
        lines.append(f"**Categoría:** {family}")
    
    # Descripción breve
    desc = pdp_data.get('description', '')
    if desc and len(desc) > 50:
        short_desc = desc[:300] + "..." if len(desc) > 300 else desc
        lines.append(f"\n**Descripción:** {short_desc}")
    
    # Especificaciones
    attrs = pdp_data.get('attributes', {})
    if attrs:
        lines.append("\n**📋 ESPECIFICACIONES:**")
        for i, (k, v) in enumerate(attrs.items()):
            if i >= 10:
                lines.append(f"  ... (+{len(attrs) - 10} más)")
                break
            lines.append(f"  • {k}: {v}")
    
    # Credibilidad
    total = pdp_data.get('total_comments') or pdp_data.get('totalComments', 0)
    if total and total > 0:
        lines.append(f"\n**[PRINCIPAL] VALORACIONES:** {total} opiniones de compradores")
    
    # Ventajas (procesadas)
    advs = pdp_data.get('advantages_list', [])
    if advs:
        lines.append("\n**🟢 LO QUE VALORAN LOS USUARIOS (usa para argumentar):**")
        for adv in advs[:8]:
            lines.append(f"  ✓ {adv}")
    
    # Desventajas (procesadas)
    disadvs = pdp_data.get('disadvantages_list', [])
    if disadvs:
        lines.append("\n**🟡 PUNTOS A CONSIDERAR (menciona con honestidad):**")
        for dis in disadvs[:5]:
            lines.append(f"  • {dis}")
    
    # Opiniones
    comments = pdp_data.get('top_comments', [])
    if comments:
        lines.append("\n**💬 ASÍ HABLAN LOS USUARIOS (inspírate en su lenguaje):**")
        for i, c in enumerate(comments[:3]):
            short = c[:200] + "..." if len(c) > 200 else c
            lines.append(f'\n  [{i+1}] "{short}"')
    
    lines.append("\n" + "=" * 60)
    return "\n".join(lines), has_feedback


def _format_pdp_links_with_data(links_data: Optional[List[Dict]]) -> str:
    """
    Formatea enlaces PDP incluyendo datos de producto de cada uno.
    
    Args:
        links_data: Lista de enlaces [{url, anchor, type, product_data}]
        
    Returns:
        Sección formateada para el prompt
    """
    if not links_data:
        return ""
    
    lines = []
    lines.append("\n## [ENLAZADO] ENLACES OBLIGATORIOS")
    lines.append("Incluye TODOS estos enlaces de forma natural en el contenido.\n")
    
    pdp_with_data = []
    other_links = []
    
    for link in links_data:
        if link.get('product_data'):
            pdp_with_data.append(link)
        else:
            other_links.append(link)
    
    # Primero enlaces con datos de producto
    if pdp_with_data:
        lines.append("###  Productos con datos (enriquece el contenido con esta info):\n")
        
        for i, link in enumerate(pdp_with_data, 1):
            url = link.get('url', '')
            anchor = link.get('anchor', '')
            pdata = link.get('product_data', {})
            
            lines.append(f"**{i}. [{anchor}]({url})**")
            
            # Info del producto
            title = pdata.get('title', '')
            if title:
                lines.append(f"   • Producto: {title}")
            
            brand = pdata.get('brand_name', '')
            if brand:
                lines.append(f"   • Marca: {brand}")
            
            # Ventajas breves
            advs = pdata.get('advantages_list', [])[:3]
            if advs:
                lines.append(f"   • Puntos fuertes: {', '.join(advs)}")
            
            # Desventajas breves
            disadvs = pdata.get('disadvantages_list', [])[:2]
            if disadvs:
                lines.append(f"   • A considerar: {', '.join(disadvs)}")
            
            lines.append("")
    
    # Luego enlaces sin datos
    if other_links:
        lines.append("### [ENLAZADO] Enlaces adicionales:\n")
        for i, link in enumerate(other_links, 1):
            url = link.get('url', '')
            anchor = link.get('anchor', '')
            ltype = link.get('type', 'interno')
            lines.append(f"{i}. [{anchor}]({url}) - {ltype}")
    
    return "\n".join(lines)


def _format_alternative_product(alternative_product: Optional[Dict]) -> str:
    """
    Formatea producto alternativo incluyendo datos JSON si disponibles.
    
    Args:
        alternative_product: Dict con url, name y opcionalmente json_data
        
    Returns:
        Sección formateada
    """
    if not alternative_product:
        return ""
    
    url = alternative_product.get('url', '')
    name = alternative_product.get('name', 'Alternativa')
    json_data = alternative_product.get('json_data')
    
    if not url and not json_data:
        return ""
    
    lines = []
    lines.append("\n## [ALTERNATIVO] PRODUCTO ALTERNATIVO A MENCIONAR")
    lines.append("Incluye este producto como alternativa en el contenido.\n")
    
    if json_data:
        # Tenemos datos completos
        title = json_data.get('title', name)
        brand = json_data.get('brand_name', '')
        
        lines.append(f"**Producto:** {title}")
        if brand:
            lines.append(f"**Marca:** {brand}")
        if url:
            lines.append(f"**URL:** {url}")
        
        # Atributos clave
        attrs = json_data.get('attributes', {})
        if attrs:
            key_attrs = list(attrs.items())[:5]
            lines.append("\n**Características clave:**")
            for k, v in key_attrs:
                lines.append(f"  • {k}: {v}")
        
        # Ventajas
        advs = json_data.get('advantages_list', [])[:4]
        if advs:
            lines.append("\n**Puntos fuertes:**")
            for adv in advs:
                lines.append(f"  ✓ {adv}")
        
        # Por qué recomendarlo
        lines.append("\n**Cómo mencionarlo:**")
        lines.append("  - Como alternativa para un perfil diferente de usuario")
        lines.append("  - Cuando el producto principal no encaje con ciertas necesidades")
        lines.append("  - En la sección de veredicto como opción complementaria")
    else:
        # Solo URL y nombre
        lines.append(f"- **{name}**: {url}")
        lines.append("\nMenciónalo como alternativa sin inventar características.")
    
    return "\n".join(lines)


def _format_products_for_prompt(products: Optional[List[Dict]]) -> str:
    """
    Formatea la lista unificada de productos para el prompt (v5.0).
    
    Agrupa por rol y formatea cada producto con sus datos JSON.
    Reemplaza las funciones separadas de producto principal y alternativo.
    
    Args:
        products: Lista de dicts [{url, name, json_data, role}]
        
    Returns:
        Sección formateada para el prompt (vacía si no hay productos)
    """
    if not products:
        return ""
    
    # Agrupar por rol
    principals = [p for p in products if p.get('role') == 'principal']
    alternatives = [p for p in products if p.get('role') == 'alternativo']
    linked = [p for p in products if p.get('role') == 'enlazado']
    
    sections = []
    
    # ── Productos principales ──
    if principals:
        sections.append("=" * 60)
        if len(principals) == 1:
            sections.append("[PRODUCTO] PRODUCTO PRINCIPAL")
        else:
            sections.append(f"[PRODUCTO] PRODUCTOS PRINCIPALES ({len(principals)})")
        sections.append("=" * 60)
        
        for i, prod in enumerate(principals):
            if len(principals) > 1:
                sections.append(f"\n### Producto principal {i+1}")
            sections.append(_format_single_product(prod))
        
        sections.append("\n### 📋 USO DE PRODUCTOS PRINCIPALES")
        if len(principals) == 1:
            sections.append("- Es el **protagonista**: el contenido gira en torno a este producto")
        else:
            sections.append("- Son los **protagonistas**: el contenido debe analizar/comparar estos productos")
        sections.append("- Usa las specs reales para argumentar")
        sections.append("- Incluye ventajas/desventajas de usuarios reales")
        sections.append("- Enlaza directamente a cada PDP")
    
    # ── Productos alternativos ──
    if alternatives:
        sections.append("\n" + "=" * 60)
        sections.append(f"[ALTERNATIVO] PRODUCTO{'S' if len(alternatives) > 1 else ''} ALTERNATIVO{'S' if len(alternatives) > 1 else ''}")
        sections.append("=" * 60)
        sections.append("Incluye como alternativas para perfiles de usuario distintos.\n")
        
        for i, prod in enumerate(alternatives):
            if len(alternatives) > 1:
                sections.append(f"\n### Alternativa {i+1}")
            sections.append(_format_single_product(prod))
        
        sections.append("\n**Cómo mencionarlos:**")
        sections.append("- Como alternativa para un perfil diferente de usuario")
        sections.append("- Cuando el producto principal no encaje con ciertas necesidades")
        sections.append("- En la sección de veredicto como opción complementaria")
    
    # ── Productos enlazados ──
    if linked:
        sections.append("\n" + "-" * 40)
        sections.append(f"[ENLAZADO] PRODUCTOS A ENLAZAR ({len(linked)})")
        sections.append("-" * 40)
        sections.append("Menciona/enlaza estos productos de forma natural.\n")
        
        for prod in linked:
            json_data = prod.get('json_data', {}) or {}
            title = json_data.get('title', '') or prod.get('name', '')
            url = prod.get('url', '')
            brand = json_data.get('brand_name', '')
            
            parts = []
            if title:
                parts.append(f"**{title}**")
            if brand:
                parts.append(f"({brand})")
            if url:
                parts.append(f"— {url}")
            
            if parts:
                sections.append("- " + " ".join(parts))
            
            # Breve info si hay JSON
            advs = json_data.get('advantages_list', [])[:2]
            if advs:
                sections.append(f"  Puntos fuertes: {', '.join(advs)}")
    
    return "\n".join(sections)


def _format_single_product(product: Dict) -> str:
    """Formatea un solo producto con sus datos JSON."""
    json_data = product.get('json_data', {}) or {}
    url = product.get('url', '')
    
    lines = []
    
    # Info básica
    title = json_data.get('title', '') or product.get('name', '')
    if title:
        lines.append(f"\n**Producto:** {title}")
    
    brand = json_data.get('brand_name', '') or json_data.get('brand', '')
    if brand:
        lines.append(f"**Marca:** {brand}")
    
    family = json_data.get('family_name', '') or json_data.get('family', '')
    if family:
        lines.append(f"**Categoría:** {family}")
    
    price = json_data.get('price', '')
    if price:
        lines.append(f"**Precio:** {price}")
    
    if url:
        lines.append(f"**URL:** {url}")
    
    # Descripción
    desc = json_data.get('description', '')
    if desc and len(desc) > 50:
        short_desc = desc[:300] + "..." if len(desc) > 300 else desc
        lines.append(f"\n**Descripción:** {short_desc}")
    
    # Especificaciones
    attrs = json_data.get('attributes', {})
    if attrs and isinstance(attrs, dict):
        lines.append("\n**📋 Especificaciones:**")
        for i, (k, v) in enumerate(attrs.items()):
            if i >= 10:
                lines.append(f"  ... (+{len(attrs) - 10} más)")
                break
            lines.append(f"  • {k}: {v}")
    
    # Rating
    rating = json_data.get('rating', '')
    total_comments = json_data.get('total_comments', 0) or json_data.get('totalComments', 0)
    if rating or total_comments:
        parts = []
        if rating:
            parts.append(f"valoración {rating}")
        if total_comments:
            parts.append(f"{total_comments} opiniones")
        lines.append(f"\n**[PRINCIPAL] Valoraciones:** {', '.join(parts)}")
    
    # Ventajas
    advs = json_data.get('advantages_list', [])
    if advs:
        lines.append("\n**🟢 Lo que valoran los usuarios:**")
        for adv in advs[:6]:
            lines.append(f"  ✓ {adv}")
    
    # Desventajas
    disadvs = json_data.get('disadvantages_list', [])
    if disadvs:
        lines.append("\n**🟡 Puntos a considerar:**")
        for dis in disadvs[:4]:
            lines.append(f"  • {dis}")
    
    # FAQs (si hay, breve)
    faqs = json_data.get('faqs', [])
    if faqs:
        lines.append(f"\n**❓ FAQs del producto:** {len(faqs)} preguntas disponibles")
        for faq in faqs[:2]:
            lines.append(f"  - {faq.get('question', '')}")
    
    return "\n".join(lines)


def _build_stage3_visual_instructions(visual_elements: List[str]) -> str:
    """
    Genera instrucciones IMPERATIVAS de elementos visuales para Stage 3.
    
    A diferencia de Stage 1 (donde se dan hints de uso), aquí se le dice
    explícitamente a Claude que DEBE incluir cada elemento, con el template
    HTML exacto, y que si falta alguno debe CREARLO.
    
    Args:
        visual_elements: Lista de IDs de elementos seleccionados
        
    Returns:
        Bloque de instrucciones con templates para el prompt de Stage 3
    """
    if not visual_elements:
        return ""
    
    # Obtener templates del design_system o usar fallback
    templates = {}
    try:
        from config.design_system import COMPONENT_REGISTRY
        for elem in visual_elements:
            comp = COMPONENT_REGISTRY.get(elem)
            if comp and comp.html_template:
                templates[elem] = comp.html_template
    except ImportError:
        pass
    
    # Fallback templates (compactos para stage 3)
    _FALLBACK_COMPACT = {
        'toc': '<nav class="toc"><p class="toc__title">Contenido</p><ul><li><a href="#seccion">Sección</a></li></ul></nav>',
        'table': '<table><thead><tr><th>Característica</th><th>Valor</th></tr></thead><tbody><tr><td>Dato</td><td>Valor</td></tr></tbody></table>',
        'light_table': '<div class="lt cols-3"><div class="r"><div class="c">Header</div><div class="c">Header</div><div class="c">Header</div></div><div class="r"><div class="c">Data</div><div class="c">Data</div><div class="c">Data</div></div></div>',
        'comparison_table': '<table class="comparison-table"><thead><tr><th>Spec</th><th>Producto A</th><th class="comparison-highlight">Producto B</th></tr></thead><tbody><tr><td><strong>Dato</strong></td><td>Valor</td><td class="comparison-highlight">Valor</td></tr></tbody></table>',
        'callout': '<div class="callout"><p><strong>Consejo:</strong> Información destacada.</p></div>',
        'callout_promo': '<div class="callout-bf"><p><strong>OFERTA</strong></p><p>Texto <a href="#">enlace</a></p></div>',
        'callout_alert': '<div class="callout-alert"><p>Aviso importante</p><p>Texto de la alerta con <strong>fecha límite</strong> o dato urgente.</p></div>',
        'verdict': '<article class="contentGenerator__verdict"><div class="verdict-box"><h2>Nuestro veredicto</h2><p>Conclusión honesta...</p></div></article>',
        'grid': '<div class="grid cols-2"><div class="card"><h4>Item 1</h4><p>Descripción</p></div><div class="card"><h4>Item 2</h4><p>Descripción</p></div></div>',
        'badges': '<div class="badges"><span class="badge">Tag 1</span><span class="badge">Tag 2</span></div>',
        'buttons': '<div class="btns"><a href="#" class="btn primary">Ver producto</a></div>',
        'faqs': '<article class="contentGenerator__faqs"><h2>Preguntas frecuentes</h2><div class="faqs"><div class="faqs__item"><h3 class="faqs__question">¿Pregunta?</h3><p class="faqs__answer">Respuesta detallada.</p></div></div></article>',
        'intro_box': '<div class="intro"><p>Resumen introductorio que destaca visualmente del resto del contenido. Contexto clave para el lector.</p></div>',
        'check_list': '<ul class="check-list"><li><strong>Requisito 1:</strong> Descripción del punto verificado.</li><li><strong>Requisito 2:</strong> Otro punto a comprobar.</li></ul>',
        'specs_list': '<div class="specs-list"><h4>Especificaciones</h4><ul><li><span>Resolución</span><span>4K (3840×2160)</span></li><li><span>Procesador</span><span>AMD Ryzen 9</span></li></ul></div>',
        'product_module': '<div class="product-module"><h4>Nombre del Producto</h4><p>Descripción y características principales del producto destacado.</p><p><a href="#">Ver en PcComponentes</a></p></div>',
        'price_highlight': '<div class="price-highlight"><div class="price-info"><p class="price-label">PVP recomendado</p><p class="price">199,99 €</p></div><div class="availability"><strong>Disponible en:</strong> PcComponentes</div></div>',
        'stats_grid': '<div style="display:flex;flex-wrap:wrap;gap:15px;margin:30px 0;"><div style="flex:1;min-width:140px;background:linear-gradient(135deg,#170453,#2a0a6e);padding:25px 20px;border-radius:10px;text-align:center;"><p style="color:#ff6000;font-size:32px;font-weight:bold;margin:0;">+100K</p><p style="color:#ffffff;font-size:13px;margin:8px 0 0 0;">Descripción</p></div></div>',
        'section_divider': '<div style="background:linear-gradient(135deg,#170453 0%,#0a0220 100%);margin:60px -20px 40px -20px;padding:30px 40px;"><p style="color:#ff6000;font-size:13px;text-transform:uppercase;letter-spacing:2px;margin:0 0 5px 0;">Subtema</p><h2 style="color:#ffffff;font-size:32px;margin:0;">Título de Sección</h2></div>',
        'mod_cards': '<div class="mod-section"><h3 class="mod-section__title">Título</h3><div class="mod-grid"><article class="mod-card mod-card--horizontal">...</article></div></div>',
        'vcard_cards': '<div class="vcard-module"><h3 class="vcard-module__title">Título</h3><div class="vcard-grid"><article class="vcard vcard--hoverable">...</article></div></div>',
        'compact_cards': '<div class="compact-cards"><div class="compact-card"><p class="compact-card__title"><span class="compact-card__icon"><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></span>Punto clave</p><ul><li>Dato concreto con cifra</li><li>Otro dato relevante</li><li>Rango o referencia</li></ul></div></div>',
        'use_cases': '<div class="use-cases"><div class="use-case"><p class="use-case__title"><span class="use-case__icon"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/></svg></span>Caso de uso</p><p>Descripción del escenario y necesidad del usuario.</p><p><strong>Recomendación:</strong> <a href="URL">Producto recomendado</a> — Razón concreta.</p></div></div>',
    }
    for elem in visual_elements:
        if elem not in templates:
            templates[elem] = _FALLBACK_COMPACT.get(elem, '')
    
    # Nombres legibles
    _NAMES = {
        'toc': 'Tabla de Contenidos (TOC)',
        'table': 'Tabla HTML',
        'light_table': 'Light Table (CSS Grid)',
        'comparison_table': 'Tabla de Comparación',
        'callout': 'Callout / Destacado',
        'callout_promo': 'Callout Promocional',
        'callout_alert': 'Callout de Alerta',
        'verdict': 'Verdict Box',
        'grid': 'Grid Layout',
        'badges': 'Badges',
        'buttons': 'Botones CTA',
        'faqs': 'Preguntas Frecuentes (FAQ)',
        'intro_box': 'Intro Destacada',
        'check_list': 'Check List',
        'specs_list': 'Lista de Especificaciones',
        'product_module': 'Módulo de Producto',
        'price_highlight': 'Destacado de Precio',
        'stats_grid': 'Cifras / Estadísticas',
        'section_divider': 'Separador de Sección',
        'mod_cards': 'Cards Horizontales (Módulo CMS)',
        'vcard_cards': 'Cards Verticales (Módulo CMS)',
        'compact_cards': 'Compact Cards (Resumen Visual Naranja)',
        'use_cases': 'Cards de Casos de Uso (Azul)',
    }
    
    # Instrucciones de colocación
    _PLACEMENT = {
        'toc': 'Colócala justo DESPUÉS del kicker y H2 principal, ANTES del primer contenido.',
        'table': 'Inserta al menos UNA tabla comparativa donde se comparen productos o características.',
        'light_table': 'Inserta al menos UNA light table donde se listen especificaciones.',
        'comparison_table': 'Inserta la tabla de comparación donde se contrasten los productos analizados.',
        'callout': 'Inserta 1-3 callouts distribuidos por el artículo con tips, avisos o datos clave.',
        'callout_promo': 'Inserta el callout promocional donde encaje con una oferta o campaña.',
        'callout_alert': 'Inserta el callout de alerta donde haya un aviso urgente, fecha límite o información crítica.',
        'verdict': 'OBLIGATORIO al final, dentro de <article class="contentGenerator__verdict">.',
        'grid': 'Inserta un grid con cards donde se listen productos o características en 2-3 columnas.',
        'badges': 'Inserta badges donde haya categorías o tags relevantes.',
        'buttons': 'Inserta botones CTA después de menciones a productos con enlace.',
        'faqs': 'OBLIGATORIO: Inserta la sección FAQ dentro de <article class="contentGenerator__faqs"> DESPUÉS del contenido principal y ANTES del verdict. 4-8 preguntas relevantes.',
        'intro_box': 'Coloca el intro_box justo después del kicker/H2, ANTES de la TOC. Resume la propuesta de valor del artículo.',
        'check_list': 'Inserta la check list donde haya requisitos, compatibilidades o puntos de verificación.',
        'specs_list': 'Inserta la lista de specs donde se detallen características técnicas de un producto.',
        'product_module': 'Inserta 1-3 módulos de producto para destacar productos concretos con sus features y enlace.',
        'price_highlight': 'Inserta el destacado de precio tras presentar el producto principal, antes de la sección de compra.',
        'stats_grid': 'Inserta las cifras donde haya métricas impactantes o datos numéricos clave.',
        'section_divider': 'Usa separadores de sección para dividir mega-guías en bloques temáticos visuales.',
        'mod_cards': 'Inserta el módulo de cards horizontales para comparar 2-4 productos con specs detalladas.',
        'vcard_cards': 'Inserta el módulo de cards verticales para listar recomendaciones.',
        'compact_cards': 'Inserta compact cards para resumir puntos clave (specs, criterios de compra, datos técnicos). 3-6 cards con título + icono SVG + 3-4 bullets cada una. Ideal después de la introducción o en la sección de criterios.',
        'use_cases': 'Inserta cards de casos de uso para segmentar recomendaciones por perfil/necesidad. 2-4 cards con escenario + recomendación de producto con enlace. Ideal antes del veredicto.',
    }
    
    lines = []
    lines.append("\n## ⚠️ ELEMENTOS VISUALES — OBLIGATORIOS")
    lines.append("El usuario seleccionó los siguientes elementos visuales.")
    lines.append("**TODOS deben estar presentes en la versión final.** Si el borrador no los tiene, CRÉALOS.\n")
    
    for elem in visual_elements:
        name = _NAMES.get(elem, elem)
        template = templates.get(elem, '')
        placement = _PLACEMENT.get(elem, 'Coloca donde sea relevante.')
        
        lines.append(f"### {name}")
        lines.append(placement)
        if template:
            lines.append(f"```html\n{template}\n```")
        lines.append("")
    
    # Disambiguation: si hay mod_cards/vcard Y también grid/callout básicos
    has_cards = any(e in visual_elements for e in ('mod_cards', 'vcard_cards'))
    has_basic = any(e in visual_elements for e in ('callout', 'grid', 'table'))
    if has_cards and has_basic:
        lines.append("### ⚠️ NOTA IMPORTANTE: Los elementos son DISTINTOS")
        lines.append("Los `mod-card` / `vcard` y los elementos básicos (`callout`, `grid`, `table`) son componentes DIFERENTES.")
        lines.append("Si el usuario seleccionó AMBOS, debes incluir AMBOS en ubicaciones distintas del artículo.")
        lines.append("Un `mod-section` con `mod-card` NO sustituye a un `<div class=\"callout\">` ni a un `<div class=\"grid cols-2\">`.")
        lines.append("")
    
    lines.append("**REGLA ABSOLUTA:** Si un elemento visual de los listados arriba NO aparece en tu respuesta final, es un ERROR CRÍTICO. Revisa antes de entregar.")
    
    return "\n".join(lines)


def _build_stage3_checklist(visual_elements: Optional[List[str]]) -> str:
    """
    Genera un checklist compacto de verificación para el final del prompt Stage 3.
    
    Posicionado al final del prompt para máxima atención del modelo.
    Cada item incluye el CSS class/selector que Claude debe buscar en su output.
    
    Args:
        visual_elements: Lista de IDs de elementos seleccionados
        
    Returns:
        Checklist formateado como string
    """
    if not visual_elements:
        return "- [ ] verdict-box presente\n- [ ] FAQs presentes"
    
    _CHECKS = {
        'toc': '[ ] TOC → `<nav class="toc">`',
        'callout': '[ ] Callout → `<div class="callout">`',
        'callout_promo': '[ ] Callout Promo → `<div class="callout-bf">`',
        'callout_alert': '[ ] Callout Alerta → `<div class="callout-alert">`',
        'verdict': '[ ] Verdict → `<div class="verdict-box">`',
        'grid': '[ ] Grid Layout → `<div class="grid cols-2">` o `<div class="grid cols-3">`',
        'table': '[ ] Tabla HTML → `<table>`',
        'light_table': '[ ] Light Table → `<div class="lt cols-N">`',
        'comparison_table': '[ ] Tabla Comparación → `<table class="comparison-table">`',
        'faqs': '[ ] FAQs → `<article class="contentGenerator__faqs">`',
        'intro_box': '[ ] Intro → `<div class="intro">`',
        'check_list': '[ ] Check List → `<ul class="check-list">`',
        'specs_list': '[ ] Specs List → `<div class="specs-list">`',
        'product_module': '[ ] Product Module → `<div class="product-module">`',
        'price_highlight': '[ ] Price Highlight → `<div class="price-highlight">`',
        'stats_grid': '[ ] Stats Grid → `font-size:32px` en cifras',
        'section_divider': '[ ] Section Divider → `background:linear-gradient(135deg,#170453`',
        'badges': '[ ] Badges → `<div class="badges">`',
        'buttons': '[ ] Botones → `<div class="btns">`',
        'mod_cards': '[ ] Mod Cards → `<div class="mod-section">` con `<div class="mod-grid">`',
        'vcard_cards': '[ ] VCard Cards → `<div class="vcard-module">`',
        'compact_cards': '[ ] Compact Cards → `<div class="compact-cards">`',
        'use_cases': '[ ] Casos de Uso → `<div class="use-cases">`',
    }
    
    lines = []
    for elem in visual_elements:
        check = _CHECKS.get(elem)
        if check:
            lines.append(f"- {check}")
    
    # Siempre añadir verdict y FAQs si no están ya
    if 'verdict' not in visual_elements:
        lines.append('- [ ] Verdict → `<div class="verdict-box">`')
    if 'faqs' not in visual_elements:
        lines.append('- [ ] FAQs → `<article class="contentGenerator__faqs">`')
    
    return "\n".join(lines)


def _stage3_structure_hints(visual_elements: Optional[List[str]]) -> str:
    """
    Genera placeholders en el template de ESTRUCTURA FINAL de Stage 3
    para indicar dónde van los elementos visuales.
    
    Args:
        visual_elements: Lista de IDs de elementos seleccionados
        
    Returns:
        Líneas de placeholder para el template HTML
    """
    if not visual_elements:
        return "    <!-- contenido -->"
    
    hints = []
    
    # Orden lógico de aparición en el artículo
    _ORDER = {
        'intro_box': (0, '    <div class="intro"><!-- Intro destacada obligatoria --></div>'),
        'toc': (1, '    <nav class="toc"><!-- TOC obligatorio aquí --></nav>'),
        'section_divider': (2, '    <div style="background:linear-gradient(...)"><!-- Separador de sección --></div>'),
        'callout': (3, '    <div class="callout"><!-- Callout obligatorio --></div>'),
        'callout_promo': (3, '    <div class="callout-bf"><!-- Callout promo obligatorio --></div>'),
        'callout_alert': (3, '    <div class="callout-alert"><!-- Callout alerta obligatorio --></div>'),
        'table': (4, '    <table><!-- Tabla obligatoria --></table>'),
        'light_table': (4, '    <div class="lt cols-3"><!-- Light table obligatoria --></div>'),
        'comparison_table': (4, '    <table class="comparison-table"><!-- Tabla comparación obligatoria --></table>'),
        'specs_list': (4, '    <div class="specs-list"><!-- Lista de specs obligatoria --></div>'),
        'grid': (5, '    <div class="grid cols-2"><!-- Grid obligatorio --></div>'),
        'stats_grid': (5, '    <div><!-- Cifras/estadísticas obligatorias --></div>'),
        'check_list': (5, '    <ul class="check-list"><!-- Check list obligatoria --></ul>'),
        'product_module': (6, '    <div class="product-module"><!-- Módulo de producto obligatorio --></div>'),
        'price_highlight': (6, '    <div class="price-highlight"><!-- Destacado de precio obligatorio --></div>'),
        'badges': (7, '    <div class="badges"><!-- Badges obligatorios --></div>'),
        'buttons': (7, '    <div class="btns"><!-- Botones CTA obligatorios --></div>'),
        'mod_cards': (8, '    <div class="mod-section"><!-- Cards horizontales obligatorias --></div>'),
        'vcard_cards': (8, '    <div class="vcard-module"><!-- Cards verticales obligatorias --></div>'),
        'compact_cards': (6, '    <div class="compact-cards"><!-- Compact cards obligatorias --></div>'),
        'use_cases': (7, '    <div class="use-cases"><!-- Cards casos de uso obligatorias --></div>'),
    }
    
    ordered = []
    for elem in visual_elements:
        if elem in _ORDER and elem not in ('verdict', 'faqs'):  # verdict y faqs van fuera de main
            ordered.append(_ORDER[elem])
    
    ordered.sort(key=lambda x: x[0])
    hints = [h[1] for h in ordered]
    
    return "\n".join(hints) if hints else "    <!-- contenido -->"


def _format_headings_instructions(headings_config: Optional[Dict[str, int]]) -> str:
    """
    Genera instrucciones de estructura de encabezados para el prompt.
    
    Args:
        headings_config: Dict {'h2': N, 'h3': N, 'h4': N} o None
        
    Returns:
        Instrucciones formateadas o cadena vacía
    """
    if not headings_config:
        return ""
    
    h2 = headings_config.get('h2', 0)
    h3 = headings_config.get('h3', 0)
    h4 = headings_config.get('h4', 0)
    
    if h2 == 0 and h3 == 0 and h4 == 0:
        return ""
    
    lines = ["\n## 🏷️ ESTRUCTURA DE ENCABEZADOS OBLIGATORIA"]
    lines.append("El usuario ha definido una estructura específica. Respétala:\n")
    
    if h2:
        lines.append(f"- **{h2} encabezados H2** (secciones principales)")
    if h3:
        lines.append(f"- **{h3} encabezados H3** (subsecciones dentro de los H2)")
    if h4:
        lines.append(f"- **{h4} encabezados H4** (sub-subsecciones o FAQs individuales)")
    
    lines.append("\n⚠️ **Reglas:**")
    if h2:
        lines.append(f"- Usa EXACTAMENTE {h2} etiquetas `<h2>` en el artículo")
    if h3:
        lines.append(f"- Usa EXACTAMENTE {h3} etiquetas `<h3>` distribuidas entre los H2")
    if h4:
        lines.append(f"- Usa EXACTAMENTE {h4} etiquetas `<h4>` donde corresponda")
    lines.append("- El H2 principal del `<article>` NO cuenta (ese es el título)")
    lines.append("- Los encabezados de FAQs (H3 dentro de `.faqs`) SÍ cuentan en el total de H3")
    
    return "\n".join(lines)


def _format_visual_elements_instructions(visual_elements: Optional[List[str]]) -> str:
    """
    Genera instrucciones para elementos visuales seleccionados.
    
    Args:
        visual_elements: Lista de elementos ['toc', 'table', 'callout', etc.]
        
    Returns:
        Instrucciones para el prompt
    """
    if not visual_elements:
        return ""
    
    # Mapeo de IDs legacy → nuevos
    _LEGACY_MAP = {
        'callout_bf': 'callout_promo',
        'verdict_box': 'verdict',
    }
    visual_elements = [_LEGACY_MAP.get(e, e) for e in visual_elements]
    
    # Intentar usar design_system para templates reales
    try:
        from config.design_system import COMPONENT_REGISTRY, get_component_instructions
        _ds_available = True
    except ImportError:
        _ds_available = False
    
    lines = []
    lines.append("\n## 🎨 ELEMENTOS VISUALES A INCLUIR")
    lines.append("El usuario ha solicitado estos elementos. Inclúyelos donde corresponda:\n")
    
    # Instrucciones contextuales por componente
    # (cuándo y dónde usar cada uno — no duplica el HTML template)
    _USAGE_HINTS = {
        'toc': "Colócala después del H2 principal, antes del primer <section>.",
        'table': "Úsala para comparar productos o características de forma visual.",
        'light_table': "Usa la Light Table (CSS Grid) cuando necesites más control de columnas o filas alternas.",
        'comparison_table': "Ideal para comparar 2-3 productos lado a lado con columna destacada.",
        'callout': "Usa callouts para tips, advertencias o información clave. 1-3 por artículo.",
        'callout_promo': "Para destacar ofertas especiales, promociones o campañas. Máximo 1 por artículo.",
        'callout_alert': "Para avisos urgentes, fechas límite o alertas críticas. Máximo 1 por artículo. Fondo naranja con borde oscuro.",
        'verdict': "OBLIGATORIO al final del artículo. Escríbelo como un párrafo redaccional con opinión propia, no como un resumen con viñetas. Usa un tono conversacional: como si le dijeras a un amigo 'mira, la verdad es que...'. Evita listas, bullets o estructuras rígidas dentro del veredicto. El H2 puede ser 'Nuestro veredicto', 'Entonces, ¿merece la pena?' o similar — no siempre 'Nuestro veredicto'.",
        'grid': "Para mostrar múltiples productos o características en rejilla de 2-3 columnas.",
        'badges': "Para tags de categorías, filtros o etiquetas inline dentro de secciones.",
        'buttons': "Para CTAs de producto — usar dentro de grids, cards o al final de secciones.",
        'faqs': "Sección de preguntas frecuentes al final del artículo. 4-8 preguntas relevantes. Dentro de <article class='contentGenerator__faqs'>.",
        'intro_box': "Párrafo introductorio destacado con fondo gris. Va antes de la TOC. Resume la propuesta de valor.",
        'check_list': "Lista con checkmarks (✓) naranja. Para requisitos, compatibilidades o verificaciones.",
        'specs_list': "Ficha técnica con pares clave-valor en filas. Para especificaciones de producto.",
        'product_module': "Bloque de producto destacado con fondo gris y borde naranja. 1-3 por artículo.",
        'price_highlight': "Banner de precio con fondo naranja. Precio grande + disponibilidad. Tras presentar el producto.",
        'stats_grid': "Cards con cifras grandes sobre fondo oscuro. Para métricas o datos impactantes.",
        'section_divider': "Franja a ancho completo con degradado azul para dividir mega-guías en bloques temáticos.",
        'mod_cards': "Para comparativas detalladas de 2-4 productos con specs, imagen y CTA. Incluye chip de etiqueta, lista de características, imagen con caption y botón.",
        'vcard_cards': "Para listados/recomendaciones de 3-4 productos. Cada card tiene chip, título, lista, beneficio y CTA.",
        'compact_cards': "Para resumir puntos clave con icono SVG + bullets. Ideal tras la intro o en criterios de compra. 3-6 cards.",
        'use_cases': "Para segmentar recomendaciones por perfil/necesidad. 2-4 cards con escenario + recomendación + enlace.",
    }
    
    for elem_id in visual_elements:
        # Obtener template HTML del registry o fallback
        template = ""
        comp_name = elem_id
        
        if _ds_available and elem_id in COMPONENT_REGISTRY:
            comp = COMPONENT_REGISTRY[elem_id]
            comp_name = comp.name
            template = comp.html_template
        
        # Fallback templates (corregidos con clases reales del CMS)
        if not template:
            _FALLBACK = {
                'toc': '<nav class="toc">\n  <h4>En este artículo</h4>\n  <a href="#seccion">Sección</a>\n</nav>',
                'table': '<table>\n  <thead><tr><th>Spec</th><th>Producto A</th><th>Producto B</th></tr></thead>\n  <tbody><tr><td>Valor</td><td>X</td><td>Y</td></tr></tbody>\n</table>',
                'light_table': '<div class="lt cols-3">\n  <div class="r"><div class="c">Header</div><div class="c">Header</div><div class="c">Header</div></div>\n  <div class="r"><div class="c">Data</div><div class="c">Data</div><div class="c">Data</div></div>\n</div>',
                'comparison_table': '<table class="comparison-table">\n  <thead><tr><th>Spec</th><th>A</th><th class="comparison-highlight">B</th></tr></thead>\n  <tbody><tr><td>Valor</td><td>X</td><td class="comparison-highlight">Y</td></tr></tbody>\n</table>',
                'callout': '<div class="callout">\n  <p><strong>Consejo:</strong> Información destacada.</p>\n</div>',
                'callout_promo': '<div class="callout-bf">\n  <p><strong>OFERTA</strong></p>\n  <p>Texto <a href="#">enlace</a></p>\n</div>',
                'callout_alert': '<div class="callout-alert">\n  <p>Aviso importante</p>\n  <p>Texto de la alerta con <strong>dato urgente</strong>.</p>\n</div>',
                'verdict': '<article class="contentGenerator__verdict">\n  <div class="verdict-box">\n    <h2>Nuestro veredicto</h2>\n    <p>Conclusión...</p>\n  </div>\n</article>',
                'grid': '<div class="grid cols-2">\n  <div class="card"><h4>Item</h4><p>...</p></div>\n</div>',
                'badges': '<div class="badges"><span class="badge">Tag 1</span></div>',
                'buttons': '<div class="btns"><a href="#" class="btn primary">Ver producto</a></div>',
                'faqs': '<article class="contentGenerator__faqs">\n  <h2>Preguntas frecuentes</h2>\n  <div class="faqs">\n    <div class="faqs__item">\n      <h3 class="faqs__question">¿Pregunta?</h3>\n      <p class="faqs__answer">Respuesta.</p>\n    </div>\n  </div>\n</article>',
                'intro_box': '<div class="intro">\n  <p>Resumen introductorio destacado.</p>\n</div>',
                'check_list': '<ul class="check-list">\n  <li><strong>Punto 1:</strong> Descripción.</li>\n  <li><strong>Punto 2:</strong> Descripción.</li>\n</ul>',
                'specs_list': '<div class="specs-list">\n  <h4>Especificaciones</h4>\n  <ul>\n    <li><span>Clave</span><span>Valor</span></li>\n  </ul>\n</div>',
                'product_module': '<div class="product-module">\n  <h4>Producto</h4>\n  <p>Descripción.</p>\n  <p><a href="#">Ver en PcComponentes</a></p>\n</div>',
                'price_highlight': '<div class="price-highlight">\n  <div class="price-info"><p class="price-label">PVP</p><p class="price">199,99 €</p></div>\n  <div class="availability"><strong>Disponible</strong></div>\n</div>',
                'stats_grid': '<div style="display:flex;gap:15px;margin:30px 0;">\n  <div style="flex:1;background:linear-gradient(135deg,#170453,#2a0a6e);padding:25px;border-radius:10px;text-align:center;">\n    <p style="color:#ff6000;font-size:32px;font-weight:bold;margin:0;">+100K</p>\n    <p style="color:#fff;font-size:13px;margin:8px 0 0;">Dato</p>\n  </div>\n</div>',
                'section_divider': '<div style="background:linear-gradient(135deg,#170453,#0a0220);padding:30px 40px;margin:60px 0 40px;">\n  <p style="color:#ff6000;font-size:13px;text-transform:uppercase;letter-spacing:2px;margin:0 0 5px;">Subtema</p>\n  <h2 style="color:#fff;font-size:32px;margin:0;">Título</h2>\n</div>',
                'mod_cards': '<div class="mod-section">\n  <h3 class="mod-section__title">Título</h3>\n  <div class="mod-grid">\n    <article class="mod-card mod-card--horizontal">...</article>\n  </div>\n</div>',
                'vcard_cards': '<div class="vcard-module">\n  <h3 class="vcard-module__title">Título</h3>\n  <div class="vcard-grid">\n    <article class="vcard vcard--hoverable">...</article>\n  </div>\n</div>',
                'compact_cards': '<div class="compact-cards">\n  <div class="compact-card">\n    <p class="compact-card__title"><span class="compact-card__icon"><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></span>Punto clave</p>\n    <ul><li>Dato 1</li><li>Dato 2</li></ul>\n  </div>\n</div>',
                'use_cases': '<div class="use-cases">\n  <div class="use-case">\n    <p class="use-case__title"><span class="use-case__icon"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg></span>Caso de uso</p>\n    <p>Descripción del escenario.</p>\n    <p><strong>Recomendación:</strong> <a href="URL">Producto</a></p>\n  </div>\n</div>',
            }
            template = _FALLBACK.get(elem_id, '')
        
        hint = _USAGE_HINTS.get(elem_id, '')
        
        lines.append(f"**{comp_name}:**")
        if template:
            lines.append(f"```html\n{template}\n```")
        if hint:
            lines.append(hint)
        lines.append("")
    
    return "\n".join(lines)


def _get_data_usage_instructions(has_data: bool, has_feedback: bool) -> str:
    """
    Genera instrucciones específicas según los datos disponibles.
    """
    if has_data and has_feedback:
        return """
## [PRODUCTO] CÓMO USAR LOS DATOS DEL PRODUCTO

Tienes datos REALES del producto incluyendo opiniones de usuarios. ÚSALOS:

1. **Ventajas (🟢):** Puntos que compradores REALES han destacado
   - Úsalos para argumentar beneficios con credibilidad
   - Parafrasea con tu estilo, no copies literalmente

2. **Desventajas (🟡):** Los "peros" que han encontrado
   - MENCIÓNALOS con honestidad (genera CONFIANZA)
   - Contextualiza: "para el precio no se puede pedir más"

3. **Opiniones (💬):** Lenguaje de usuarios reales
   - Inspírate en sus expresiones naturales
   - Evita sonar robótico: ellos hablan como personas

4. **Especificaciones:** Traduce datos técnicos a beneficios PRÁCTICOS
"""
    elif has_data:
        return """
## [PRODUCTO] DATOS DISPONIBLES

Tienes información básica del producto pero sin feedback de usuarios.
Usa los datos como contexto y complementa con tu conocimiento del sector.
"""
    else:
        return """
## [POST] SIN DATOS ESPECÍFICOS DE PRODUCTO

No tienes datos del producto, pero puedes crear contenido IGUAL DE BUENO:

1. **Céntrate en la keyword:** Es tu guía principal
2. **Usa conocimiento general:** Eres experto en tecnología
3. **Habla de la categoría:** Qué busca alguien interesado en esto
4. **Da consejos prácticos:** Qué debería considerar el comprador
5. **Sé honesto:** "Depende de tu uso" es mejor que inventar

El tono debe ser el mismo: cercano, experto, con chispa y honesto.
"""


# ============================================================================
# ARCHETYPE-SPECIFIC STAGE 1 INSTRUCTIONS
# ============================================================================

_ARCHETYPE_STAGE1_INSTRUCTIONS: Dict[str, str] = {
    'ARQ-5': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Comparativa A vs B)

### Declaración de ganador (OBLIGATORIO)
El veredicto DEBE declarar un ganador claro. Si es un empate técnico, explica concretamente para qué perfil de usuario es mejor cada opción. No vale "depende de tus necesidades" sin perfiles concretos.
Ejemplo válido: "Para gaming competitivo, el A es mejor por X. Para productividad multimedia, el B gana por Y."
Ejemplo inválido: "Depende de lo que busques."

### Tabla comparativa principal
Usa `<table class="comparison-table">` (NO `<table>` genérico) para la tabla comparativa principal lado a lado.""",

    'ARQ-7': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Ranking / Mejores X)

### Ranking numerado (OBLIGATORIO)
Numera los productos del 1 al N en orden de recomendación. El #1 es tu recomendación principal. Cada producto debe tener su número visible en el heading (ej: "1. Nombre del producto").

### Badges (OBLIGATORIO)
El producto #1 debe llevar badge "Mejor en general". Si hay uno con mejor relación calidad-precio distinto del #1, añadirle badge "Mejor calidad-precio".
Usa `<span class="badge">Mejor en general</span>` junto al nombre del producto.

### Grid de fichas de producto
Usa `<div class="grid cols-2">` o `<div class="grid cols-3">` para mostrar la ficha resumen de cada producto con specs clave, precio y badge.""",

    'ARQ-16': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Novedades y Lanzamientos)

### Pirámide invertida (OBLIGATORIO)
Los primeros 2 párrafos deben responder: qué producto es, qué novedad principal trae, cuándo estará disponible y a qué precio. El resto del artículo desarrolla los detalles. No empieces con introducciones genéricas.

### Temporalidad y fechas
Incluye fechas concretas de disponibilidad. Diferencia claramente entre "ya disponible", "preventa abierta" y "próximamente". Si no tienes fecha exacta, indica "fecha por confirmar" en vez de omitirlo.

### Veredicto concreto
La sección final (tercer article CMS) debe responder directamente "¿merece la pena?" con una recomendación concreta, no una conclusión genérica. Indica para qué perfil de usuario tiene sentido la compra o el upgrade.""",

    'ARQ-2': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Guía Paso a Paso)

### Diferenciación check-list vs pasos (OBLIGATORIO)
Usa `<ul class="check-list">` SOLO para requisitos previos (herramientas, materiales necesarios antes de empezar).
Usa `<ol>` con pasos numerados para el proceso en sí.
No mezclar ambos formatos: la check-list es para "qué necesitas", la lista ordenada es para "qué hacer".""",

    'ARQ-4': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Review / Análisis de Producto)

### Tabla de benchmark
Si hay datos de rendimiento o specs comparables con la competencia, preséntalos en una `<table>` con al menos una alternativa como referencia. El lector necesita contexto comparativo para evaluar si los números son buenos o malos.""",

    # ── product_verdict ──────────────────────────────────────────────

    'ARQ-1': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Artículos SEO con Enlaces Internos)

### Densidad de enlaces internos (OBLIGATORIO)
Incluye al menos 1 enlace interno contextual cada 200-250 palabras. Los enlaces deben apuntar a categorías o productos de PcComponentes proporcionados en los datos de entrada. No agrupes todos los enlaces en un solo párrafo: distribúyelos de forma natural a lo largo del artículo.

### CTA final específico
El tercer `<article>` (veredicto) DEBE terminar con un CTA concreto que dirija al usuario a una acción: visitar una categoría, ver un producto o consultar una guía. Nada de "visita nuestra web" genérico.

### Tabla comparativa solo si procede
Usa `<table>` solo si hay 2+ productos comparables. Si el artículo es puramente informativo sin comparación directa, sustituye la tabla por un `<div class="callout">` resumen con los puntos clave.""",

    'ARQ-6': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Guía de Compra)

### Factores de compra antes que productos (OBLIGATORIO)
La primera mitad del artículo DEBE explicar los factores de decisión (specs clave, rangos de precio, tipos de producto) ANTES de recomendar productos concretos. El lector necesita criterio antes de ver opciones.

### Segmentación por rango de precio
Organiza las recomendaciones en al menos 2 rangos de precio (ej: "Menos de 200€", "200-500€", "Más de 500€"). Usa `<table>` para presentar las opciones por rango con specs clave y enlace.

### Errores comunes (OBLIGATORIO)
Incluye una sección "Errores comunes al comprar [categoría]" con un `<div class="callout">` que liste al menos 3 errores reales y específicos, no obviedades como "no comprar lo más barato".""",

    'ARQ-20': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Black Friday / Cyber Monday)

### Urgencia con datos, no con adjetivos (OBLIGATORIO)
La urgencia debe venir de fechas, stock y precios concretos, NO de adjetivos como "increíble" o "imperdible". Ejemplo válido: "Disponible hasta el 28/11 o fin de stock (quedan 50 uds)." Ejemplo inválido: "¡No te pierdas esta oferta increíble!"

### Callout promocional obligatorio
Usa `<div class="callout-bf">` para las ofertas estrella (máximo 3 callouts promocionales en todo el artículo). Cada uno debe incluir: producto, precio original, precio oferta y enlace directo.

### Grid de ofertas por categoría
Usa `<div class="grid cols-3">` con `<div class="card">` para agrupar las mejores ofertas por categoría (ej: portátiles, monitores, periféricos). Cada card debe mostrar nombre, precio y descuento.""",

    'ARQ-25': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Consolas y Gaming Portátil)

### Tabla comparativa de consolas (OBLIGATORIO)
Usa `<table class="comparison-table">` para comparar specs clave lado a lado: precio, catálogo de exclusivos, rendimiento, almacenamiento y servicios online. No omitas ninguna consola relevante del mercado actual.

### Posicionamiento honesto por perfil
El veredicto DEBE recomendar consolas específicas por perfil de jugador (casual, competitivo, familiar, portátil). Evita "todas son buenas a su manera" — cada perfil necesita una respuesta concreta.

### Ecosistema y accesorios
Dedica una sección a los accesorios imprescindibles para cada consola con enlace a productos PcComponentes.""",

    'ARQ-33': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Movilidad y Gadgets)

### Tabla comparativa de dispositivos (OBLIGATORIO)
Usa `<table>` para comparar al menos 3 dispositivos con specs clave (batería, pantalla, peso, precio). El lector espera datos concretos para decidir.

### Integración de ecosistema
Indica explícitamente la compatibilidad de cada dispositivo con ecosistemas (Apple, Google, Samsung, etc.) y cómo afecta a la decisión de compra.

### Veredicto por caso de uso
El veredicto DEBE recomendar un dispositivo distinto para al menos 2 casos de uso concretos (ej: "Para productividad móvil...", "Para entretenimiento...").""",

    # ── step_by_step ─────────────────────────────────────────────────

    'ARQ-11': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Solución de Problemas / Troubleshooting)

### Diagnóstico antes que solución (OBLIGATORIO)
Estructura el contenido como: 1) Identificar síntomas → 2) Diagnosticar causa → 3) Aplicar solución. Nunca saltes directamente a la solución sin ayudar al lector a identificar qué variante del problema tiene.

### Orden por probabilidad
Las soluciones deben ir ordenadas de más probable/sencilla a menos probable/compleja. Usa `<ol>` para los pasos de diagnóstico y solución.

### Cuándo buscar ayuda profesional
Incluye un `<div class="callout">` al final con criterios claros de cuándo el problema requiere un técnico. Indica qué productos de PcComponentes podrían ser la solución si el componente está dañado.""",

    'ARQ-13': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Configuración y Setup)

### Requisitos previos con check-list (OBLIGATORIO)
Abre con una `<ul class="check-list">` de todo lo necesario antes de empezar: hardware, software, cables, herramientas y tiempo estimado. No mezclar esto con los pasos del proceso.

### Pasos numerados con resultado esperado
Cada paso en la `<ol>` debe describir: qué hacer, cómo verificar que se hizo bien y qué debería verse/pasar si funciona correctamente.

### Troubleshooting inline
Tras cada paso crítico (instalación de drivers, configuración de BIOS, etc.), añade un `<div class="callout">` con los errores más frecuentes en ese paso específico y cómo resolverlos.""",

    # ── educational ──────────────────────────────────────────────────

    'ARQ-3': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Explicación / Educativo)

### De lo concreto a lo abstracto (OBLIGATORIO)
Empieza con una definición en 1-2 frases llanas (como si lo explicaras a alguien sin conocimientos técnicos). Después profundiza en contexto técnico, historia y funcionamiento interno.

### Mitos vs realidad
Si el tema tiene mitos comunes, dedica una sección con `<div class="callout">` por mito, usando formato "MITO: ... / REALIDAD: ...".

### Ejemplos prácticos obligatorios
Cada concepto abstracto DEBE ir acompañado de un ejemplo práctico o caso de uso real. "Esto significa que..." seguido de una situación concreta.""",

    'ARQ-9': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Mejores Productos por Precio)

### Tabla de rangos de precio (OBLIGATORIO)
Usa `<table>` con columnas: Rango de precio | Mejor opción | Punto fuerte | Para quién. Debe cubrir al menos 3 franjas de presupuesto.

### Sweet spot destacado
Usa un `<div class="callout">` para destacar el "sweet spot" (mejor relación calidad-precio global) con una justificación concreta de por qué ese rango ofrece el mejor valor.

### Sin juicios sobre el presupuesto
Nunca uses expresiones como "si te lo puedes permitir" o "para presupuestos ajustados". Describe cada rango de forma neutral: qué obtienes a ese precio y qué sacrificas.""",

    'ARQ-12': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Especificaciones Técnicas Explicadas)

### Spec → Impacto real (OBLIGATORIO)
Cada especificación DEBE explicarse en términos de impacto para el usuario. No basta con definir "latencia CAS"; hay que añadir "esto significa que al abrir 20 pestañas de Chrome notarás...".

### Tabla de valores recomendados
Usa `<table>` con columnas: Spec | Valor mínimo aceptable | Recomendado | Gama alta, segmentado por caso de uso (gaming, ofimática, edición, etc.).

### Callout de mitos técnicos
Usa `<div class="callout">` para desmontar al menos 1 mito técnico común sobre las specs (ej: "más GHz siempre es mejor").""",

    'ARQ-14': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Optimización y Mejora)

### Diagnóstico antes que optimización (OBLIGATORIO)
Empieza con cómo medir el rendimiento actual (herramientas, métricas) ANTES de proponer mejoras. El lector necesita saber su punto de partida.

### Mejoras ordenadas por impacto/coste
Organiza las mejoras de mayor a menor ratio impacto/coste. Usa `<table>` con columnas: Mejora | Coste aproximado | Mejora esperada | Dificultad.

### Mejor inversión destacada
Usa `<div class="callout">` para destacar la mejora con mejor relación impacto/precio, con enlace al producto correspondiente en PcComponentes.""",

    'ARQ-15': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Mantenimiento y Cuidados)

### Calendario de mantenimiento (OBLIGATORIO)
Usa `<table>` con columnas: Tarea | Frecuencia | Tiempo estimado | Materiales necesarios. Organiza por frecuencia: diario/semanal → mensual → anual.

### Señales de alerta
Incluye un `<div class="callout">` con los signos que indican que algo va mal y hay que actuar ya (ruidos, temperaturas, rendimiento degradado).

### Productos de mantenimiento
Enlaza productos de limpieza y mantenimiento de PcComponentes (aire comprimido, pasta térmica, kits de limpieza) donde sea pertinente.""",

    'ARQ-22': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Requisitos de Videojuegos)

### Tablas de requisitos obligatorias (OBLIGATORIO)
Usa `<table>` para presentar: requisitos mínimos, recomendados y 4K/Ultra en columnas lado a lado. Incluye CPU, GPU, RAM, almacenamiento y SO.

### Configuraciones de hardware probadas
Incluye al menos 2 builds concretas (presupuesto y rendimiento) con componentes específicos de PcComponentes y los FPS esperados a cada calidad gráfica.

### Optimización de ajustes gráficos
Usa un `<div class="callout">` para indicar qué ajustes gráficos bajar primero para ganar más FPS con menor impacto visual (ej: sombras, reflejos ray-tracing).""",

    'ARQ-24': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Periféricos Gaming)

### Specs clave por tipo de periférico (OBLIGATORIO)
Usa `<table>` con las specs que realmente importan para cada periférico: sensor/DPI para ratones, switches/respuesta para teclados, driver/respuesta para auriculares. No listes specs irrelevantes.

### Recomendaciones por presupuesto
Segmenta las recomendaciones en al menos 2 rangos de precio. Cada producto debe tener nombre concreto, precio y enlace.

### Combos recomendados
Cierra con un `<div class="callout">` que recomiende un combo completo de periféricos (ratón + teclado + auriculares) para al menos 2 perfiles: competitivo y casual.""",

    'ARQ-26': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Workstation Profesional)

### Configuración por disciplina (OBLIGATORIO)
Usa `<table>` con configuraciones específicas por disciplina profesional (3D, vídeo, CAD, desarrollo, etc.). No mezcles requisitos de disciplinas distintas en una sola recomendación.

### Software → Hardware
Organiza cada sección partiendo del software principal de la disciplina y derivando los requisitos de hardware que necesita. No al revés.

### Ergonomía como inversión
Incluye una sección sobre monitor, silla y escritorio como parte integral de la workstation, no como accesorio opcional. Usa `<div class="callout">` para destacar que la ergonomía afecta directamente a la productividad.""",

    'ARQ-28': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Productividad y Software)

### Stack recomendado (OBLIGATORIO)
Cierra con una tabla-resumen del stack completo recomendado por área: herramienta, precio (gratis/pago), plataforma y alternativa.

### Hardware complementario
Cada categoría de software debe mencionar si hay hardware que mejora la experiencia (monitor ultrawide para multitarea, SSD para compilación, etc.) con enlace a PcComponentes.

### Tips accionables
Usa `<div class="callout">` para tips de productividad concretos y accionables, no consejos genéricos como "organiza tu tiempo".""",

    'ARQ-29': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Seguridad y Privacidad)

### Nivel de amenaza real (OBLIGATORIO)
Empieza cada sección de amenaza con el impacto real y la probabilidad, no con alarmismo. Formato: "Qué es → Cómo te afecta → Cómo protegerte".

### Checklist de seguridad
Cierra el artículo con una tabla-checklist: Medida | Dificultad | Importancia | Estado (para que el lector pueda evaluar su propia situación).

### Productos de seguridad
Incluye productos físicos de seguridad (llaves USB FIDO, webcam covers, routers con firewall) con enlace cuando sean pertinentes. Usa `<div class="callout">` para la medida de protección más crítica.""",

    'ARQ-30': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Redes y Conectividad)

### Diagnóstico de red actual (OBLIGATORIO)
Empieza con cómo evaluar la red actual del lector (herramientas de test, qué medir) antes de recomendar equipamiento.

### Tabla de equipamiento por tamaño de espacio
Usa `<table>` con recomendaciones de equipamiento según tamaño del espacio y número de dispositivos. Columnas: Espacio | Dispositivos | Router recomendado | Extensores necesarios.

### Configuración paso a paso
Incluye al menos una sección con pasos numerados (`<ol>`) para la configuración básica del router/red. Usa `<div class="callout">` para los errores de configuración más frecuentes.""",

    'ARQ-32': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Fotografía y Vídeo)

### Equipamiento por nivel (OBLIGATORIO)
Usa `<table>` con 3 columnas de nivel: Iniciación | Intermedio | Profesional. Filas por tipo de equipo (cámara, objetivo, iluminación, audio, almacenamiento).

### Triángulo cámara-objetivo-luz
Dedica una sección a explicar que el equipo fotográfico/vídeo funciona como sistema: no vale invertir todo en el cuerpo de la cámara sin buenos objetivos o luz.

### Kit recomendado completo
Cierra con un `<div class="callout">` que liste un kit completo recomendado para el nivel más demandado, con precios y enlaces a PcComponentes.""",

    'ARQ-34': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Sostenibilidad y Eficiencia Energética)

### Datos de consumo reales (OBLIGATORIO)
Incluye cifras concretas de consumo energético (W, kWh/año, coste anual estimado) siempre que sea posible. Usa `<table>` para comparar consumo entre productos eficientes y convencionales.

### Certificaciones como criterio de compra
Explica las certificaciones relevantes (Energy Star, 80 Plus, EPEAT) en términos prácticos: qué garantizan al comprador y cómo buscarlas.

### Impacto personal cuantificado
Usa `<div class="callout">` para mostrar el ahorro estimado en euros/año al elegir productos eficientes frente a los convencionales.""",

    # ── grid_recommendations ─────────────────────────────────────────

    'ARQ-8': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Lista de Recomendaciones)

### Grid de productos (OBLIGATORIO)
Usa `<div class="grid cols-2">` o `<div class="grid cols-3">` con `<div class="card">` para cada producto recomendado. Cada card debe incluir: nombre, para quién es ideal y el punto fuerte diferencial.

### Criterios de selección antes de la lista
Explica brevemente (2-3 párrafos) los criterios usados para seleccionar los productos ANTES de mostrar la lista. El lector debe entender por qué estos y no otros.

### Callout con recomendación rápida
Abre con un `<div class="callout">` que diga "Si tienes prisa: [producto] es nuestra recomendación principal por [razón]." para lectores que no quieren leer todo el artículo.""",

    'ARQ-10': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Productos para Perfil Específico)

### Perfil de usuario concreto (OBLIGATORIO)
Los primeros 2 párrafos DEBEN definir el perfil de usuario con detalle: qué hace, qué necesita, qué presupuesto maneja, qué errores típicos comete al comprar. No vale "gamers" a secas — sé específico.

### Grid de productos recomendados
Usa `<div class="grid cols-2">` con `<div class="card">` para cada producto. Cada card debe explicar por qué encaja en ESE perfil específico, no por qué es buen producto en general.

### Kit ideal completo
Cierra con un `<div class="callout">` que presente el kit ideal completo para ese perfil con precio total aproximado.""",

    'ARQ-18': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Eventos y Ferias Tech)

### Pirámide invertida por anuncio (OBLIGATORIO)
Cada anuncio destacado debe abrir con lo más importante: qué es, cuándo llega y a qué precio. Los detalles técnicos van después.

### Grid de anuncios por categoría
Usa `<div class="grid cols-2">` con `<div class="card">` para agrupar anuncios por categoría (procesadores, GPUs, portátiles, etc.). Cada card: nombre del producto, novedad principal y fecha estimada.

### Callout de impacto para el consumidor
Usa `<div class="callout">` para explicar en lenguaje llano qué significan los anuncios técnicos para el consumidor final: "Esto significa que los portátiles de 2025 tendrán X% más de batería por el mismo precio.".""",

    'ARQ-23': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Streaming y Creación de Contenido)

### Kit por nivel (OBLIGATORIO)
Usa `<div class="grid cols-3">` para presentar 3 niveles: Principiante | Intermedio | Profesional. Cada card del grid debe listar los equipos esenciales con precio total del kit.

### Software antes que hardware
Empieza explicando qué software se usará (OBS, DaVinci, etc.) y sus requisitos, para que las recomendaciones de hardware tengan contexto.

### Callout de errores de principiante
Usa `<div class="callout">` para los 3 errores más comunes al montar un setup de streaming (ej: invertir todo en cámara sin buena iluminación, ignorar el audio).""",

    'ARQ-27': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Teletrabajo y Home Office)

### Kit por presupuesto (OBLIGATORIO)
Usa `<div class="grid cols-3">` con `<div class="card">` para 3 kits: Básico (<300€) | Confort (300-700€) | Premium (>700€). Cada card debe listar todos los elementos del kit con precio total.

### Ergonomía como prioridad
La ergonomía NO es una sección secundaria: dedica al menos 1 sección H2 completa a silla, escritorio, postura y pausas. Usa `<div class="callout">` para destacar que invertir en ergonomía reduce bajas laborales.

### Conectividad como requisito
Incluye recomendaciones de router/conexión como parte esencial del setup de teletrabajo, no como accesorio.""",

    'ARQ-31': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Hogar Inteligente / Smart Home)

### Ecosistema primero (OBLIGATORIO)
Antes de recomendar dispositivos, explica los ecosistemas disponibles (Google Home, Alexa, HomeKit, Matter) y ayuda al lector a elegir uno. Cada dispositivo recomendado debe indicar su compatibilidad.

### Grid de starter kits
Usa `<div class="grid cols-2">` con `<div class="card">` para presentar kits de inicio por ecosistema. Cada card: ecosistema, dispositivos incluidos y precio total.

### Callout de seguridad y privacidad
Usa `<div class="callout">` para abordar brevemente las preocupaciones de seguridad/privacidad del smart home y cómo mitigarlas.""",

    # ── promo ────────────────────────────────────────────────────────

    'ARQ-19': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Ofertas y Promociones)

### Urgencia basada en datos (OBLIGATORIO)
La urgencia debe venir de fechas y condiciones concretas ("Válido del 15 al 22 de marzo"), NO de adjetivos ("¡Oferta increíble!"). Incluye siempre fecha de fin y condiciones.

### Callout promocional para ofertas estrella
Usa `<div class="callout-bf">` para las 2-3 ofertas estrella de la promoción. Cada callout debe incluir: producto, precio original tachado, precio oferta y enlace directo. Máximo 3 callouts promocionales en todo el artículo.

### Grid de ofertas por categoría
Usa `<div class="grid cols-2">` con `<div class="card">` para agrupar ofertas por categoría. Cada card: nombre, descuento y enlace. Añade `<span class="badge">-X%</span>` con el porcentaje de descuento.""",

    # ── gaming_multicomponent ────────────────────────────────────────

    'ARQ-21': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Setup Gaming Completo)

### Builds completas por presupuesto (OBLIGATORIO)
Presenta al menos 2 builds completas (presupuesto y rendimiento) con TODOS los componentes: CPU, GPU, RAM, placa, SSD, fuente, caja, monitor, teclado, ratón, auriculares. Usa `<table>` para cada build con componente, modelo recomendado y precio.

### Grid de componentes por prioridad
Usa `<div class="grid cols-2">` para mostrar los componentes donde más importa invertir vs donde se puede ahorrar. No tratar todos los componentes con la misma importancia.

### Ruta de upgrade futuro
Incluye un `<div class="callout">` con la ruta de upgrade a 1-2 años: qué componente cambiar primero para mejorar rendimiento sin rehacer todo el setup.""",

    # ── trends ───────────────────────────────────────────────────────

    'ARQ-17': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Tendencias del Sector)

### Predicciones con base (OBLIGATORIO)
Cada tendencia o predicción DEBE apoyarse en al menos un dato concreto, fuente o evidencia observable. No escribas "se espera que..." sin indicar quién lo espera o por qué. Si no hay fuente, indica explícitamente que es una proyección editorial.

### Sin tablas ni grids forzados
Este arquetipo NO requiere tablas ni grids. Usa formato narrativo con H2/H3. Solo añade una tabla si hay datos numéricos reales que comparar (cuotas de mercado, precios históricos, etc.).

### Callout de impacto para el consumidor
Cada tendencia debe cerrar con un `<div class="callout">` explicando qué significa para el comprador medio de PcComponentes: "Esto significa que en 6 meses podrás comprar...".""",

    # ── external_text ────────────────────────────────────────────────

    'ARQ-35': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Nota de Prensa)

### Tono institucional estricto (OBLIGATORIO)
Escribe en tercera persona ("PcComponentes anuncia..."). Cero adjetivos promocionales: no uses "líder", "mejor", "increíble", "revolucionario". Los datos hablan solos.

### Estructura de pirámide invertida
El primer párrafo (lead) DEBE responder quién, qué, cuándo, dónde y por qué. El resto del comunicado desarrolla detalles en orden decreciente de importancia.

### Cita del portavoz
Si se proporcionan datos del portavoz (campos_especificos), incluye una cita textual entrecomillada. La cita debe sonar natural y aportar contexto, no repetir lo que ya dice el texto.""",

    'ARQ-36': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Contenido para Web de Afiliados)

### Honestidad persuasiva (OBLIGATORIO)
El tono debe ser de experto independiente que recomienda con criterio. Incluye siempre al menos 1 "contra" real por producto recomendado. La credibilidad vende más que la hipérbole.

### Tabla resumen rápida al inicio
Tras la introducción, incluye una tabla-resumen con los 3-5 productos analizados: Producto | Mejor para | Precio | Nota. El lector que tiene prisa necesita esto arriba.

### CTAs de afiliado naturales
Los enlaces de compra deben ir integrados en el flujo del texto ("Ver precio actual en PcComponentes"), nunca como botones agresivos ni con urgencia artificial.""",

    'ARQ-37': """## INSTRUCCIONES ESPECÍFICAS DEL ARQUETIPO (Guest Posting)

### Tono de autor invitado (OBLIGATORIO)
Escribe como un experto independiente publicando en un medio ajeno. NUNCA uses "en PcComponentes" como sujeto de frase. La mención a PcComponentes debe ser contextual y limitada a 1-2 apariciones en todo el artículo.

### Valor primero, marca después
El 80% del artículo debe ser contenido de valor puro sin mencionar ninguna marca. La sección con mención de PcComponentes debe aportar valor adicional, no ser un anuncio insertado.

### Sin estructura CMS visible
Aunque técnicamente se mantiene la estructura de 3 articles para el CMS, el contenido debe leerse como un artículo editorial continuo. No uses "Nuestro veredicto" ni "FAQs" como headers — usa títulos editoriales naturales.""",
}


def _build_archetype_stage1_instructions(arquetipo_code: str) -> str:
    """Retorna instrucciones específicas del arquetipo para Stage 1.
    Retorna string vacío si el arquetipo no tiene instrucciones específicas."""
    return _ARCHETYPE_STAGE1_INSTRUCTIONS.get(arquetipo_code, "")


# ============================================================================
# ETAPA 1: BORRADOR INICIAL
# ============================================================================

def build_new_content_prompt_stage1(
    keyword: str,
    arquetipo: Dict[str, Any],
    target_length: int = 1500,
    pdp_data: Optional[Dict] = None,
    pdp_json_data: Optional[Dict] = None,  # NUEVO v4.9.0
    links_data: Optional[List[Dict]] = None,
    secondary_keywords: Optional[List[str]] = None,
    additional_instructions: str = "",
    campos_especificos: Optional[Dict] = None,
    visual_elements: Optional[List[str]] = None,
    guiding_context: str = "",
    alternative_product: Optional[Dict] = None,
    products: Optional[List[Dict]] = None,  # NUEVO v5.0
    headings_config: Optional[Dict[str, int]] = None,  # NUEVO v5.0
) -> str:
    """
    Construye prompt para Etapa 1: Borrador inicial.
    
    Funciona igual de bien CON o SIN datos de producto.
    
    NUEVO v4.9.0:
    - Fusiona pdp_data + pdp_json_data
    - Procesa product_data en enlaces PDP
    - Usa alternative_product.json_data
    - Implementa visual_elements
    
    Args:
        keyword: Keyword principal
        arquetipo: Dict con name, description del arquetipo
        target_length: Longitud objetivo en palabras
        pdp_data: Dict con datos del producto (de n8n webhook)
        pdp_json_data: Dict con datos del JSON subido (NUEVO - tiene prioridad)
        links_data: Lista de enlaces [{url, anchor, type, product_data}]
        secondary_keywords: Keywords secundarias
        additional_instructions: Instrucciones adicionales del usuario
        campos_especificos: Campos específicos del arquetipo
        visual_elements: Elementos visuales a incluir ['toc', 'table', etc.]
        guiding_context: Contexto guía del usuario
        alternative_product: Producto alternativo {url, name, json_data}
        
    Returns:
        Prompt completo para Claude
    """
    arquetipo_name = arquetipo.get('name', 'Contenido SEO')
    arquetipo_desc = arquetipo.get('description', '')
    arquetipo_tone = arquetipo.get('tone', '')
    arquetipo_structure = arquetipo.get('structure', [])
    
    # v5.0: Si hay products (lista unificada), usarlo preferentemente
    if products:
        products_section = _format_products_for_prompt(products)
        has_product_data = bool(products)
        # Detectar si algún producto tiene feedback de usuarios
        has_feedback = any(
            (p.get('json_data') or {}).get('advantages_list')
            or (p.get('json_data') or {}).get('disadvantages_list')
            or (p.get('json_data') or {}).get('top_comments')
            for p in products
        )
        product_section = products_section
        alt_prod = ""  # Ya incluido en products_section
    else:
        # Fallback legacy: fusionar pdp_data + pdp_json_data
        merged_product_data = _merge_product_data(pdp_data, pdp_json_data)
        product_section, has_feedback = _format_product_section(merged_product_data)
        has_product_data = bool(merged_product_data)
        alt_prod = _format_alternative_product(alternative_product)
    
    # Instrucciones de tono (adapta según si hay datos)
    tone_instructions = get_tone_instructions(has_product_data)
    
    # Instrucciones de uso de datos
    data_instructions = _get_data_usage_instructions(has_product_data, has_feedback)
    
    # NUEVO: Enlaces con datos de producto
    links_section = _format_pdp_links_with_data(links_data)
    
    # Keywords secundarias
    sec_kw = ""
    if secondary_keywords:
        sec_kw = "\n## 🔑 KEYWORDS SECUNDARIAS\n" + "\n".join(f"- {k}" for k in secondary_keywords)
    
    # Contexto guía
    context = f"\n## 📖 CONTEXTO DEL USUARIO\n{guiding_context}\n" if guiding_context else ""
    
    # NUEVO: Elementos visuales
    visual_section = _format_visual_elements_instructions(visual_elements)
    
    # NUEVO v5.0: Estructura de encabezados
    headings_section = _format_headings_instructions(headings_config)
    
    # CSS dinámico: carga desde design_system si disponible
    css_for_prompt = _get_css_for_prompt(visual_elements=visual_elements)
    
    # Campos específicos del arquetipo
    campos_section = ""
    if campos_especificos:
        campos_section = "\n## 📋 CAMPOS ESPECÍFICOS DEL ARQUETIPO\n"
        for key, value in campos_especificos.items():
            if value:
                campos_section += f"- **{key}:** {value}\n"
    
    # Formatear sección del arquetipo para el prompt
    arquetipo_detail = ""
    if arquetipo_tone:
        arquetipo_detail += f"- **Tono del arquetipo:** {arquetipo_tone}\n"
    if arquetipo_structure:
        structure_items = "\n".join(f"  {i}. {s}" for i, s in enumerate(arquetipo_structure, 1))
        arquetipo_detail += f"\n**Estructura recomendada del arquetipo:**\n{structure_items}\n"

    # Determinar si incluir mini-historias:
    # Solo si (1) el arquetipo lo requiere Y (2) hay reviews/feedback de usuarios
    arquetipo_code = arquetipo.get('code', '')
    archetype_specific_section = _build_archetype_stage1_instructions(arquetipo_code)
    include_mini_stories = (
        arquetipo_code in ARQUETIPOS_CON_MINI_STORIES
        and has_feedback
    )

    # Construir sección de engagement condicionalmente
    engagement_section = "## ENGAGEMENT: CTAs DISTRIBUIDOS"
    if include_mini_stories:
        engagement_section = """## ENGAGEMENT: MINI-HISTORIAS Y CTAs DISTRIBUIDOS

### Mini-historias (INCLUIR 2-3 por artículo)
Incluye 2-3 mini-escenarios BASADOS EN LAS REVIEWS REALES de los productos. Usa:
- Una **persona concreta** (nombres españoles: María, Carlos, Laura, Pedro...)
- Una **situación específica** con detalles (presupuesto, uso, problema concreto) inspirados en las opiniones reales
- Un **resultado claro** que ilustre el punto de la sección (50-100 palabras cada una)

IMPORTANTE: Las mini-historias deben reflejar experiencias de las reviews reales de los usuarios.
No inventes escenarios genéricos; basa cada historia en ventajas, desventajas u opiniones concretas del producto.

Distribución: una al inicio (enganchar), una en el medio (re-enganchar), una cerca del final (reforzar).

Ejemplo: "Carlos buscaba un portátil para edición de vídeo con un presupuesto de 1.200€. Empezó con 8 GB de RAM y cada proyecto tardaba 3 horas en renderizar. Tras pasarse a 32 GB y SSD NVMe, el mismo proyecto tarda 40 minutos.\""""

    # Construir prompt
    prompt = f"""Eres un redactor SEO de PcComponentes, la tienda líder de tecnología en España.

# TAREA
Genera un BORRADOR tipo "{arquetipo_name}" para la keyword "{keyword}".

{arquetipo_desc}

## PARÁMETROS
- **Keyword principal:** {keyword}
- **Longitud objetivo:** ~{target_length} palabras
- **Tipo de contenido:** {arquetipo_name}
{arquetipo_detail}

## 🔑 OPTIMIZACIÓN DE KEYWORD (OBLIGATORIO)

La keyword "{keyword}" DEBE aparecer de forma natural en el contenido:
- **Densidad objetivo:** 1-2% (aprox. {max(3, target_length // 200)}-{max(6, target_length // 100)} veces en {target_length} palabras)
- **Primeras 100 palabras:** La keyword DEBE aparecer en las primeras 100 palabras del artículo
- **Al menos 1 H2:** La keyword (o variación natural) DEBE aparecer en al menos un encabezado H2
- **Distribución:** Repartida entre inicio, medio y final del artículo (no concentrada en un solo bloque)
- **Natural:** Integrada en frases reales, nunca forzada ni repetitiva

{product_section}

{tone_instructions}

{data_instructions}
{links_section}
{sec_kw}
{context}
{alt_prod}
{visual_section}
{headings_section}
{campos_section}

{archetype_specific_section}

{engagement_section}

### CTAs distribuidos (INCLUIR 2-3 por artículo)
NO pongas los CTAs solo al final. Distribúyelos:
- **Tras primera sección de valor** → CTA suave: "Echa un vistazo a [nuestra selección de X →](URL)"
- **Tras sección de comparación** → CTA medio: "Mira el [nombre del producto](URL_PDP) para ver precio y disponibilidad."
- **Final del artículo** → CTA fuerte: enlace directo al PDP o categoría.

El primer CTA debe aparecer antes de las 500 primeras palabras.

## ESTRUCTURA HTML REQUERIDA

El HTML debe empezar DIRECTAMENTE con <style>:

```
<style>
{css_for_prompt}
</style>

<article class="contentGenerator__main">
    <span class="kicker">KICKER ATRACTIVO</span>
    <h2>Título que incluya {keyword}</h2>
    
    <nav class="toc">
        <p class="toc__title">En este artículo</p>
        <ol class="toc__list">
            <li><a href="#seccion1">Sección 1</a></li>
        </ol>
    </nav>
    
    <section id="seccion1">
        <h3>Subtítulo</h3>
        <p>Contenido...</p>
    </section>
</article>

<article class="contentGenerator__faqs">
    <h2>Preguntas frecuentes sobre {keyword}</h2>
    <div class="faqs">
        <div class="faqs__item">
            <h3 class="faqs__question">¿Pregunta con keyword?</h3>
            <p class="faqs__answer">Respuesta útil...</p>
        </div>
    </div>
</article>

<article class="contentGenerator__verdict">
    <div class="verdict-box">
        <h2>Nuestro veredicto</h2>
        <p>Conclusión honesta que APORTE valor real, no un resumen...</p>
    </div>
</article>
```


## INSTRUCCIONES ADICIONALES
{additional_instructions or "(Ninguna)"}

---

## REGLAS CRÍTICAS

1. **NO** uses ```html ni marcadores markdown
2. Empieza con `<!-- META: [meta description max 155 chars con keyword] -->` y luego `<style>`
3. FAQs DEBEN incluir keyword: "Preguntas frecuentes sobre {keyword}"
4. Si tienes datos de usuarios, ÚSALOS (ventajas/desventajas)
5. Si tienes datos de productos enlazados, MENCIÓNALOS con sus características
6. SÉ HONESTO: si hay "peros", menciónalos
7. **EVITA frases de IA:** "en el mundo actual", "sin lugar a dudas", etc.
8. El veredicto debe APORTAR, no solo resumir
9. Incluye TODOS los enlaces proporcionados con su anchor text exacto
10. **EMOJIS:** No usar emojis en el contenido generado.
11. **FECHAS:** NO incluyas años concretos (2024, 2025, 2026) en títulos ni encabezados salvo que la keyword del usuario ya incluya un año.
11. **ELEMENTOS VISUALES:** Si arriba se listaron elementos visuales (tablas, callouts, FAQs, grid, etc.), TODOS deben aparecer en el HTML generado. Un elemento solicitado pero ausente es un error grave.

**Genera el HTML ahora:**
"""
    return prompt


# ============================================================================
# ETAPA 2: ANÁLISIS Y CORRECCIONES
# ============================================================================

# --- Archetype groups for Stage 2 conditional checklist (QW-1) ---
_ARCHETYPE_STAGE2_GROUPS = {
    'product_verdict': {
        'ARQ-1', 'ARQ-4', 'ARQ-5', 'ARQ-6', 'ARQ-7',
        'ARQ-20', 'ARQ-25', 'ARQ-33',
    },
    'step_by_step': {'ARQ-2', 'ARQ-11', 'ARQ-13'},
    'educational': {
        'ARQ-3', 'ARQ-9', 'ARQ-12', 'ARQ-14', 'ARQ-15', 'ARQ-16',
        'ARQ-22', 'ARQ-24', 'ARQ-26', 'ARQ-28', 'ARQ-29', 'ARQ-30',
        'ARQ-32', 'ARQ-34',
    },
    'grid_recommendations': {
        'ARQ-8', 'ARQ-10', 'ARQ-18', 'ARQ-23', 'ARQ-27', 'ARQ-31',
    },
    'promo': {'ARQ-19'},
    'gaming_multicomponent': {'ARQ-21'},
    'trends': {'ARQ-17'},
    'external_text': {'ARQ-35', 'ARQ-36', 'ARQ-37'},
}

_GROUP_CHECKLISTS_STAGE2 = {
    'product_verdict': [
        "¿El veredicto aporta una opinión ORIGINAL y no es un simple resumen del artículo?",
        "¿La tabla comparativa usa datos reales (specs, precios, características concretas)?",
        "¿Se mencionan pros Y contras de forma honesta (no solo ventajas)?",
        "¿Los datos de producto proporcionados se usan de forma sustantiva en el texto?",
        "¿El CTA final es específico y orientado a la acción?",
    ],
    'step_by_step': [
        "¿Los pasos están numerados en una lista ordenada (<ol>) o con numeración explícita?",
        "¿Cada paso es autocontenido y accionable?",
        "¿Existe una sección de requisitos previos separada de los pasos?",
        "¿Hay guidance para errores comunes o problemas durante el proceso?",
    ],
    'educational': [
        "¿Las definiciones son claras y evitan jerga innecesaria?",
        "¿Incluye ejemplos prácticos o casos de uso concretos?",
        "¿Las tablas se usan para datos estructurados (specs, comparaciones, calendarios)?",
        "¿Los callouts destacan información clave o advertencias?",
    ],
    'grid_recommendations': [
        "¿Las recomendaciones están segmentadas por perfil, presupuesto o nivel?",
        "¿Cada ítem recomendado tiene nombre, descripción breve y contexto de uso?",
        "¿Hay al menos 3 recomendaciones para justificar el formato grid?",
    ],
    'promo': [
        "¿Se mencionan fechas/plazos concretos de la promoción?",
        "¿El tono de urgencia es natural y no agresivo?",
        "¿Los precios mencionados son actuales y específicos?",
        "¿Se indica claramente cómo aprovechar la oferta?",
    ],
    'gaming_multicomponent': [
        "¿Cubre componentes, periféricos Y configuración de software?",
        "¿Ofrece opciones por rangos de presupuesto?",
        "¿La sección de upgrades futuros es práctica y no genérica?",
        "¿Las recomendaciones son específicas (modelos concretos, no solo categorías)?",
    ],
    'trends': [
        "¿El contenido usa lenguaje orientado al futuro con base en datos?",
        "¿Las predicciones se apoyan en evidencia o fuentes?",
        "¿Evita añadir tablas/grids innecesarios solo para rellenar?",
    ],
    'external_text': [
        "¿El tono es apropiado para publicación externa (no promocional)?",
        "¿La estructura CMS de 3 articles se mantiene aunque el contenido sea externo?",
        "¿Las menciones a PcComponentes son naturales e integradas?",
    ],
}


def _get_archetype_group(arquetipo_code: str) -> Optional[str]:
    """Devuelve el grupo de Stage 2 al que pertenece el arquetipo, o None."""
    if not arquetipo_code:
        return None
    for group, codes in _ARCHETYPE_STAGE2_GROUPS.items():
        if arquetipo_code in codes:
            return group
    return None


def _build_archetype_checklist_stage2(
    arquetipo_code: str,
    arquetipo_structure: Optional[List[str]] = None,
) -> str:
    """
    Genera el bloque de checklist específico del arquetipo para Stage 2.
    Retorna string vacío si no hay arquetipo o no se reconoce.
    """
    if not arquetipo_code:
        return ""

    group = _get_archetype_group(arquetipo_code)
    if not group:
        return ""

    # Nombre del arquetipo
    arq_name = arquetipo_code
    try:
        from config.arquetipos import get_arquetipo
        arq = get_arquetipo(arquetipo_code)
        if arq:
            arq_name = arq.get('name', arquetipo_code)
    except ImportError:
        pass

    items = _GROUP_CHECKLISTS_STAGE2.get(group, [])
    if not items:
        return ""

    lines = [f"\n## 7. CHECKLIST DEL ARQUETIPO ({arq_name})"]
    for item in items:
        lines.append(f"- [ ] {item}")

    # Estructura esperada del arquetipo
    if arquetipo_structure:
        lines.append("\n### Estructura esperada del arquetipo:")
        for section in arquetipo_structure:
            lines.append(f"- [ ] ¿Incluye sección: \"{section}\"?")
        lines.append("")
        lines.append("Si falta alguna sección estructural del arquetipo, repórtalo como problema de severidad ALTO.")

    return "\n".join(lines)


def _build_visual_elements_minimum_check(
    arquetipo_code: str,
    user_visual_elements: Optional[List[str]] = None,
) -> str:
    """
    Genera bloque de verificación de elementos visuales mínimos del arquetipo.
    Retorna string vacío si no hay arquetipo, no se reconoce, o no faltan elementos.
    """
    if not arquetipo_code:
        return ""

    try:
        from config.arquetipos import get_visual_elements
    except ImportError:
        return ""

    archetype_elements = get_visual_elements(arquetipo_code)
    if not archetype_elements:
        return ""

    user_set = set(user_visual_elements or [])
    missing = [e for e in archetype_elements if e not in user_set]

    if not missing:
        return ""

    lines = ["\n### ELEMENTOS VISUALES MÍNIMOS DEL ARQUETIPO"]
    lines.append(f"El arquetipo {arquetipo_code} requiere como mínimo estos elementos visuales:")
    for elem in archetype_elements:
        status = "✓ incluido" if elem in user_set else "⚠️ FALTANTE"
        lines.append(f"- {elem}: {status}")
    lines.append("")
    lines.append("Si faltan elementos mínimos del arquetipo, repórtalo como problema de severidad ALTO.")

    return "\n".join(lines)


def build_new_content_correction_prompt_stage2(
    draft_content: str,
    target_length: int = 1500,
    keyword: str = "",
    links_to_verify: Optional[List[Dict]] = None,
    alternative_product: Optional[Dict] = None,
    products: Optional[List[Dict]] = None,  # v5.0
    visual_elements: Optional[List[str]] = None,
    arquetipo_code: str = "",                          # QW-1
    arquetipo_structure: Optional[List[str]] = None,   # QW-1
) -> str:
    """
    Construye prompt para Etapa 2: Análisis crítico del borrador.
    
    Args:
        draft_content: HTML del borrador generado en Stage 1
        target_length: Longitud objetivo
        keyword: Keyword principal
        links_to_verify: Enlaces que deben estar presentes
        alternative_product: Producto alternativo que debe aparecer
        
    Returns:
        Prompt para análisis
    """
    # Verificación de enlaces
    links_check = ""
    if links_to_verify:
        links_check = "\n## ENLACES A VERIFICAR\n"
        links_check += "Cada uno de estos enlaces DEBE aparecer en el contenido:\n"
        for link in links_to_verify:
            anchor = link.get('anchor', '')
            url = link.get('url', '')
            has_data = "✓ con datos" if link.get('product_data') else ""
            links_check += f"- [{anchor}]({url}) {has_data}\n"
    
    # Verificación de productos
    alt_check = ""
    if products:
        # v5.0: verificar todos los productos por rol
        product_checks = []
        for p in products:
            name = p.get('name', '') or (p.get('json_data', {}) or {}).get('title', '')
            url = p.get('url', '')
            role = p.get('role', 'principal')
            role_label = {"principal": "[PRINCIPAL] Principal", "alternativo": "[ALTERNATIVO] Alternativo", "enlazado": "[ENLAZADO] Enlazado"}.get(role, role)
            has_json = "✓ con JSON" if p.get('json_data') else ""
            if name or url:
                product_checks.append(f"- [{role_label}] {name} ({url}) {has_json}")
        if product_checks:
            alt_check = "\n## PRODUCTOS QUE DEBEN APARECER EN EL CONTENIDO\n" + "\n".join(product_checks) + "\n"
    elif alternative_product:
        # Fallback legacy
        url = alternative_product.get('url', '')
        name = alternative_product.get('name', '')
        has_json = "✓ con datos JSON" if alternative_product.get('json_data') else ""
        if url or name:
            alt_check = f"\n## PRODUCTO ALTERNATIVO QUE DEBE APARECER\n- {name} ({url}) {has_json}\n"
    
    # Verificación de elementos visuales
    visual_check = ""
    visual_elements_json = "[]"
    if visual_elements:
        import json as _json
        visual_elements_json = _json.dumps(visual_elements)
        visual_check = "\n## ELEMENTOS VISUALES REQUERIDOS\nEl usuario seleccionó estos componentes visuales. Verifica que TODOS están presentes en el HTML:\n"
        for elem in visual_elements:
            visual_check += f"- {elem}\n"
        visual_check += "\nSi falta CUALQUIER elemento visual, repórtalo como problema de severidad CRÍTICA.\n"

    # QW-1: Checklist específico del arquetipo
    archetype_checklist = _build_archetype_checklist_stage2(arquetipo_code, arquetipo_structure)
    # QW-2: Elementos visuales mínimos del arquetipo
    visual_minimum_check = _build_visual_elements_minimum_check(arquetipo_code, visual_elements)

    return f"""Eres un editor SEO senior de PcComponentes. Analiza críticamente este borrador.

# BORRADOR A ANALIZAR

{draft_content[:12000]}

# PARÁMETROS
- **Keyword:** {keyword}
- **Longitud objetivo:** ~{target_length} palabras
{links_check}
{alt_check}
{visual_check}

# CHECKLIST DE VERIFICACIÓN

## 1. TONO DE MARCA PCCOMPONENTES
- [ ] ¿Suena a PcComponentes? (cercano, experto, con chispa)
- [ ] ¿Tutea al lector de forma natural?
- [ ] ¿Es honesto sobre pros y contras?
- [ ] ¿Tiene personalidad o suena genérico?

## 2. ANTI-IA (CRÍTICO)
- [ ] ¿Evita "En el mundo actual...", "Sin lugar a dudas..."?
- [ ] ¿Evita adjetivos vacíos (increíble, revolucionario)?
- [ ] ¿Varía la estructura de los párrafos?
- [ ] ¿El veredicto aporta valor o solo resume?

## 3. ESTRUCTURA HTML
- [ ] ¿Empieza con <style> (NO con ```html)?
- [ ] ¿Tiene contentGenerator__main con kicker y toc?
- [ ] ¿Tiene contentGenerator__faqs con keyword en título?
- [ ] ¿Tiene contentGenerator__verdict con verdict-box?

## 4. SEO Y KEYWORD (CRÍTICO)
- [ ] ¿La keyword "{keyword}" aparece en las primeras 100 palabras?
- [ ] ¿La keyword aparece en al menos un H2?
- [ ] ¿La densidad de keyword es 1-2%? (contar apariciones y calcular)
- [ ] ¿La keyword está distribuida en inicio, medio y final?
- [ ] ¿La keyword aparece de forma natural, no forzada?
- [ ] ¿TODOS los enlaces proporcionados están incluidos?
- [ ] ¿Se mencionan los datos de los productos enlazados?
- [ ] ¿La longitud es aproximada al objetivo?

## 5. ELEMENTOS VISUALES
- [ ] ¿Están TODOS los elementos visuales que pidió el usuario?
- [ ] Si falta alguno (TOC, tabla, callout, grid, etc.), reportarlo como problema CRÍTICO
{visual_minimum_check}

## 6. DATOS DE PRODUCTO (si aplica)
- [ ] ¿Se usan las ventajas/desventajas proporcionadas?
- [ ] ¿Se menciona el producto alternativo?
- [ ] ¿Los datos de productos enlazados enriquecen el contenido?
{archetype_checklist}

---

**Responde SOLO con JSON estructurado:**

```json
{{
    "longitud_actual": 0,
    "longitud_objetivo": {target_length},
    "necesita_ajuste_longitud": false,

    "keyword_seo": {{
        "keyword": "{keyword}",
        "apariciones_total": 0,
        "densidad_porcentaje": 0.0,
        "en_primeras_100_palabras": false,
        "en_algun_h2": false,
        "distribucion": "buena/concentrada/ausente",
        "correcciones_keyword": []
    }},

    "estructura": {{
        "tiene_style": false,
        "tiene_main": false,
        "tiene_faqs": false,
        "tiene_verdict": false,
        "faqs_incluye_keyword": false,
        "tiene_markdown_wrapper": false
    }},
    
    "tono": {{
        "es_cercano": false,
        "es_honesto": false,
        "tiene_personalidad": false,
        "evita_frases_ia": false,
        "frases_ia_detectadas": []
    }},
    
    "enlaces": {{
        "presentes": [],
        "faltantes": [],
        "con_datos_usados": []
    }},
    
    "datos_producto": {{
        "usa_ventajas": false,
        "usa_desventajas": false,
        "menciona_alternativa": false,
        "datos_pdp_links_usados": false
    }},
    
    "elementos_visuales": {{
        "solicitados": {visual_elements_json},
        "presentes": [],
        "faltantes": [],
        "minimos_arquetipo": [],
        "minimos_faltantes": []
    }},

    "arquetipo": {{
        "code": "{arquetipo_code}",
        "cumplimiento_estructura": []
    }},

    "problemas": [
        {{
            "tipo": "estructura|seo|tono|formato|datos",
            "severidad": "critico|alto|medio|bajo",
            "descripcion": "...",
            "solucion": "..."
        }}
    ],
    
    "aspectos_positivos": [],
    "puntuacion_general": 0,
    "recomendacion_principal": ""
}}
```

**Responde ÚNICAMENTE con el JSON, sin texto adicional.**
"""


# Alias de compatibilidad
def build_correction_prompt_stage2(*args, **kwargs):
    return build_new_content_correction_prompt_stage2(*args, **kwargs)


# ============================================================================
# ETAPA 3: VERSIÓN FINAL
# ============================================================================

def build_final_prompt_stage3(
    draft_content: str,
    analysis_feedback: str,
    keyword: str = "",
    target_length: int = 1500,
    links_data: Optional[List[Dict]] = None,
    alternative_product: Optional[Dict] = None,
    products: Optional[List[Dict]] = None,  # v5.0
    visual_elements: Optional[List[str]] = None,
) -> str:
    """
    Construye prompt para Etapa 3: Versión final corregida.
    
    Args:
        draft_content: HTML del borrador
        analysis_feedback: Feedback del análisis (JSON o texto)
        keyword: Keyword principal
        target_length: Longitud objetivo
        links_data: Enlaces obligatorios (ahora con product_data)
        alternative_product: Producto alternativo (ahora con json_data)
        products: Lista unificada de productos (v5.0)
        visual_elements: Elementos visuales a preservar ['toc', 'table', etc.]
        
    Returns:
        Prompt para generación final
    """
    # Enlaces con datos
    links_section = ""
    if links_data:
        links_section = "\n## ENLACES OBLIGATORIOS (con datos si disponibles)\n"
        for i, link in enumerate(links_data, 1):
            anchor = link.get('anchor', '')
            url = link.get('url', '')
            pdata = link.get('product_data')
            
            links_section += f"{i}. [{anchor}]({url})"
            if pdata:
                title = pdata.get('title', '')
                if title:
                    links_section += f" - {title}"
            links_section += "\n"
    
    # Productos
    alt_section = ""
    if products:
        # v5.0: recordatorio de todos los productos
        prod_lines = []
        for p in products:
            json_data = p.get('json_data', {}) or {}
            name = json_data.get('title', '') or p.get('name', '')
            url = p.get('url', '')
            role = p.get('role', 'principal')
            role_label = {"principal": "[PRINCIPAL]", "alternativo": "[ALTERNATIVO]", "enlazado": "[ENLAZADO]"}.get(role, "[PRODUCTO]")
            
            if name or url:
                line = f"- {role_label} **{name}**"
                brand = json_data.get('brand_name', '')
                if brand:
                    line += f" ({brand})"
                if url:
                    line += f" — {url}"
                prod_lines.append(line)
        if prod_lines:
            alt_section = "\n## PRODUCTOS DEL CONTENIDO\nAsegúrate de que TODOS estos productos aparecen correctamente:\n" + "\n".join(prod_lines) + "\n"
    elif alternative_product:
        # Fallback legacy
        url = alternative_product.get('url', '')
        name = alternative_product.get('name', '')
        json_data = alternative_product.get('json_data')
        
        if url or json_data:
            alt_section = f"\n## PRODUCTO ALTERNATIVO\n"
            if json_data:
                title = json_data.get('title', name)
                brand = json_data.get('brand_name', '')
                alt_section += f"- **{title}** ({brand}) - {url}\n"
                advs = json_data.get('advantages_list', [])[:3]
                if advs:
                    alt_section += f"  Puntos fuertes: {', '.join(advs)}\n"
            else:
                alt_section += f"- {name} ({url})\n"
    
    # CSS dinámico (incluye componentes seleccionados)
    css_for_prompt = _get_css_for_prompt(visual_elements=visual_elements)
    
    # Instrucciones imperativas de elementos visuales para stage 3
    visual_reminder = ""
    if visual_elements:
        visual_reminder = _build_stage3_visual_instructions(visual_elements)
    
    return f"""Genera la VERSIÓN FINAL corregida como editor SEO senior de PcComponentes.

# BORRADOR ORIGINAL

{draft_content[:12000]}

# ANÁLISIS Y CORRECCIONES A APLICAR

{analysis_feedback[:4000]}
{links_section}
{alt_section}
{visual_reminder}
{EJEMPLOS_TONO_STAGE3}

##  EVITAR SIGNOS DE IA (CRÍTICO)
- "En el mundo actual..." / "Sin lugar a dudas..." / "Es importante destacar..."
- "Cabe mencionar que..." / "A la hora de..." / "Ofrece una experiencia..."
- Adjetivos vacíos: increíble, revolucionario, impresionante, excepcional
- El veredicto NO debe repetir lo ya dicho
- Estructuras repetitivas párrafo tras párrafo

# ESTRUCTURA FINAL REQUERIDA

```
<style>
{css_for_prompt}
</style>

<article class="contentGenerator__main">
    <span class="kicker">KICKER</span>
    <h2>Título con {keyword}</h2>
{_stage3_structure_hints(visual_elements)}
    <section>...</section>
</article>

<article class="contentGenerator__faqs">
    <h2>Preguntas frecuentes sobre {keyword}</h2>
    <div class="faqs">...</div>
</article>

<article class="contentGenerator__verdict">
    <div class="verdict-box">
        <h2>Nuestro veredicto</h2>
        <p>Conclusión que APORTE valor real...</p>
    </div>
</article>
```

---

## REGLAS ABSOLUTAS

1. **NUNCA** uses ```html ni markdown
2. Empieza con `<!-- META: ... -->` y luego `<style>`
3. Longitud aproximada: ~{target_length} palabras
4. FAQs: "Preguntas frecuentes sobre {keyword}"
5. Incluye verdict-box
6. Aplica TODAS las correcciones del análisis
7. Incluye TODOS los enlaces con datos de producto si disponibles
8. Menciona el producto alternativo si lo hay
9. Tono PcComponentes en cada párrafo
10. **EMOJIS:** No usar emojis en el contenido generado.
11. **ELEMENTOS VISUALES:** TODOS los elementos visuales solicitados DEBEN estar presentes.
12. **META DESCRIPTION:** Incluye `<!-- META: ... -->` (max 155 chars con keyword) ANTES del `<style>` como primera línea del output.

## 🔍 CHECKLIST PRE-ENTREGA (OBLIGATORIO)

Antes de generar tu respuesta, verifica mentalmente que tu HTML incluye TODOS estos elementos.
Si falta alguno, AÑÁDELO antes de entregar. Un elemento faltante es un ERROR CRÍTICO.

{_build_stage3_checklist(visual_elements)}

**Genera SOLO el HTML final, sin explicaciones:**
"""


# Alias de compatibilidad
def build_final_generation_prompt_stage3(
    draft_content: str,
    corrections_json: str,
    target_length: int = 1500,
) -> str:
    return build_final_prompt_stage3(
        draft_content=draft_content,
        analysis_feedback=corrections_json,
        keyword="",
        target_length=target_length,
    )


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def build_system_prompt() -> str:
    """System prompt para todas las etapas."""
    return get_system_prompt_base()


def get_css_styles() -> str:
    """Retorna el CSS minificado (usa design_system si disponible)."""
    return _get_css_for_prompt()


def get_element_template(name: str) -> str:
    """
    Retorna plantilla de elemento.
    Lee del COMPONENT_REGISTRY con fallback local.
    Soporta IDs legacy (callout_bf, verdict_box) y nuevos (callout_promo, verdict).
    """
    # Mapeo de IDs legacy → nuevos
    _LEGACY_MAP = {
        'callout_bf': 'callout_promo',
        'verdict_box': 'verdict',
    }
    normalized = _LEGACY_MAP.get(name, name)
    
    try:
        from config.design_system import COMPONENT_REGISTRY
        comp = COMPONENT_REGISTRY.get(normalized)
        if comp and comp.html_template:
            return comp.html_template
    except ImportError:
        pass
    
    # Fallback
    templates = {
        'callout': '<div class="callout"><p><strong> Dato:</strong> [Contenido]</p></div>',
        'callout_promo': '<div class="callout-bf"><p><strong>OFERTA</strong></p><p>[Contenido]</p></div>',
        'callout_bf': '<div class="callout-bf"><p><strong>OFERTA</strong></p><p>[Contenido]</p></div>',
        'verdict': '<article class="contentGenerator__verdict"><div class="verdict-box"><h2>Nuestro veredicto</h2><p>[Conclusión]</p></div></article>',
        'verdict_box': '<article class="contentGenerator__verdict"><div class="verdict-box"><h2>Nuestro veredicto</h2><p>[Conclusión]</p></div></article>',
        'table': '<table><thead><tr><th>Spec</th><th>Valor</th></tr></thead><tbody><tr><td>...</td><td>...</td></tr></tbody></table>',
        'grid': '<div class="grid cols-2"><div class="card">...</div></div>',
    }
    return templates.get(name, "")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    # Funciones principales
    'build_new_content_prompt_stage1',
    'build_new_content_correction_prompt_stage2',
    'build_correction_prompt_stage2',
    'build_final_prompt_stage3',
    'build_final_generation_prompt_stage3',
    'build_system_prompt',
    # Utilidades
    'get_css_styles',
    'get_element_template',
    # Constantes
    'CSS_INLINE_MINIFIED',
]
