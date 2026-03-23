# -*- coding: utf-8 -*-
"""
Rewrite Prompts - PcComponentes Content Generator
Versión 4.7.1

Prompts para reescritura de contenido basada en análisis competitivo.

CAMBIOS v4.7.1:
- NUEVO: Formateo de productos alternativos con JSON
- NUEVO: Formateo de enlaces editoriales con HTML contextual
  - Post: campo html_content único
  - PLP: campos top_text y bottom_text
- Mantiene todo de v4.7.0: instrucciones, fusión, desambiguación

Flujo de 3 etapas:
1. Borrador basado en análisis + instrucciones del usuario
2. Análisis crítico y correcciones
3. Versión final

Autor: PcComponentes - Product Discovery & Content
"""

from typing import Dict, List, Optional, Any
import json
import re

# v5.0: Formateo unificado de productos + visual elements + headings
try:
    from prompts.new_content import (
        _format_products_for_prompt,
        _format_headings_instructions,
        _format_visual_elements_instructions,
        _get_css_for_prompt,
        _build_stage3_visual_instructions,
        _build_stage3_checklist,
        _build_archetype_checklist_stage2,
        _build_visual_elements_minimum_check,
    )
except ImportError:
    _format_products_for_prompt = None
    _format_headings_instructions = None
    _format_visual_elements_instructions = None
    _get_css_for_prompt = None
    _build_stage3_visual_instructions = None
    _build_stage3_checklist = None
    _build_archetype_checklist_stage2 = None
    _build_visual_elements_minimum_check = None

# Importar tono de marca centralizado
try:
    from prompts.brand_tone import (
        get_tone_instructions,
        get_system_prompt_base,
        INSTRUCCIONES_ANTI_IA,
        ANTI_IA_CHECKLIST_STAGE2,
        REGLAS_CRITICAS_COMUNES,
    )
    _brand_tone_available = True
except ImportError:
    try:
        from brand_tone import (
            get_tone_instructions,
            get_system_prompt_base,
            INSTRUCCIONES_ANTI_IA,
            ANTI_IA_CHECKLIST_STAGE2,
            REGLAS_CRITICAS_COMUNES,
        )
        _brand_tone_available = True
    except ImportError:
        _brand_tone_available = False

__version__ = "4.7.1"

# ============================================================================
# CONSTANTES
# ============================================================================

DEFAULT_LENGTH_TOLERANCE = 0.05
MAX_COMPETITORS_ANALYZED = 5
MAX_COMPETITOR_CONTENT_CHARS = 8000
MIN_VALID_CONTENT_CHARS = 200

# Estructura HTML del CMS
HTML_STRUCTURE_INSTRUCTIONS = """
## ESTRUCTURA HTML OBLIGATORIA (CMS PcComponentes)

El contenido DEBE seguir esta estructura exacta de 3 articles:

```html
<!-- ARTICLE 1: CONTENIDO PRINCIPAL -->
<article class="contentGenerator__main">
    <span class="kicker">TEXTO DEL KICKER</span>
    <h2>Título Principal (NUNCA h1)</h2>
    
    <nav class="toc">
        <p class="toc__title">Contenido</p>
        <ol class="toc__list">
            <li><a href="#seccion1">Sección 1</a></li>
        </ol>
    </nav>
    
    <section id="seccion1">
        <h3>Título de Sección</h3>
        <p>Contenido...</p>
    </section>
</article>

<!-- ARTICLE 2: FAQS -->
<article class="contentGenerator__faqs">
    <h2>Preguntas frecuentes</h2>
    <div class="faqs">
        <div class="faqs__item">
            <h3 class="faqs__question">¿Pregunta?</h3>
            <p class="faqs__answer">Respuesta...</p>
        </div>
    </div>
</article>

<!-- ARTICLE 3: VEREDICTO -->
<article class="contentGenerator__verdict">
    <div class="verdict-box">
        <h2>Nuestro veredicto</h2>
        <p>Conclusión...</p>
    </div>
</article>
```

REGLAS CRÍTICAS:
- El título principal SIEMPRE es <h2>, NUNCA <h1>
- El kicker SIEMPRE usa <span class="kicker">, NUNCA <div>
- Las secciones usan <h3>
- Las FAQs van en un article SEPARADO con clase contentGenerator__faqs
- El veredicto va en un article SEPARADO con clase contentGenerator__verdict
- NO usar estilos inline, solo clases CSS definidas
- Incluir 2-3 mini-historias con nombres concretos y cifras específicas (distribuidas: inicio, medio, final)
- Incluir 2-3 CTAs distribuidos (no solo al final). Primer CTA antes de las 500 palabras.
"""

# Tono de marca PcComponentes (importado de brand_tone.py, con fallback inline)
if _brand_tone_available:
    BRAND_TONE = get_tone_instructions(has_product_data=False)
else:
    BRAND_TONE = """
## TONO DE MARCA PCCOMPONENTES

Características esenciales:
- **Expertos sin ser pedantes**: Conocemos la tecnología pero la explicamos para todos
- **Frikis sin vergüenza**: Nos apasiona la tech y se nota
- **Cercanos pero profesionales**: Tuteamos, usamos humor sutil, pero con rigor
- **Orientados a ayudar**: Siempre guiamos hacia la mejor opción para el usuario
- **Nunca desanimamos**: Si algo no encaja, ofrecemos alternativas

Evitar:
- Lenguaje corporativo frío o distante
- Tecnicismos innecesarios sin explicación
- Frases negativas tipo "no hay opciones" o "no recomendamos"
- Comparaciones despectivas con competidores
- Promesas exageradas o marketing vacío
- **Frases de IA:** "En el mundo actual...", "Sin lugar a dudas...", "Es importante destacar..."
- **Adjetivos vacíos:** increíble, revolucionario, impresionante, excepcional
- **Estructuras repetitivas** párrafo tras párrafo
- **Emojis:** No usar emojis en el contenido generado

Usar:
- Segunda persona (tú/te/tu)
- Analogías tech cuando aportan valor
- Datos concretos y verificables
- Estructura clara y escaneable
- CTAs naturales integrados en el contenido
- Variación en la estructura de cada párrafo
- Opinión honesta, incluyendo "peros"
"""


# ============================================================================
# FORMATEO DE INSTRUCCIONES DE REESCRITURA
# ============================================================================

def format_rewrite_instructions(instructions: Dict[str, Any]) -> str:
    """
    Formatea las instrucciones de reescritura del usuario.
    
    v5.1: Compatible con ambos formatos (8 campos legacy y 3 campos simplificados).
    Los campos vacíos simplemente se omiten.
    """
    if not instructions:
        return ""
    
    sections = []
    
    improve = instructions.get('improve', [])
    if improve:
        sections.append("### ✏️ QUÉ CAMBIAR / MEJORAR (obligatorio aplicar)")
        for item in improve:
            sections.append(f"- {item}")
        sections.append("")
    
    add = instructions.get('add', [])
    if add:
        sections.append("### ➕ QUÉ AÑADIR DE NUEVO (obligatorio incluir)")
        for item in add:
            sections.append(f"- {item}")
        sections.append("")
    
    maintain = instructions.get('maintain', [])
    if maintain:
        sections.append("### ✅ QUÉ CONSERVAR TAL COMO ESTÁ (no modificar)")
        for item in maintain:
            sections.append(f"- {item}")
        sections.append("")
    
    # Campos legacy (vacíos en v5.1, pero compatibles si se usan)
    remove = instructions.get('remove', [])
    if remove:
        sections.append("### 🗑️ CONTENIDO A ELIMINAR (obligatorio quitar)")
        for item in remove:
            sections.append(f"- {item}")
        sections.append("")
    
    tone_changes = instructions.get('tone_changes', '')
    if tone_changes and tone_changes.strip():
        sections.append("### 🎭 CAMBIOS DE TONO")
        sections.append(tone_changes.strip())
        sections.append("")
    
    structure_changes = instructions.get('structure_changes', '')
    if structure_changes and structure_changes.strip():
        sections.append("### 📐 CAMBIOS DE ESTRUCTURA")
        sections.append(structure_changes.strip())
        sections.append("")
    
    seo_focus = instructions.get('seo_focus', '')
    if seo_focus and seo_focus.strip():
        sections.append("### 🔍 ENFOQUE SEO ESPECÍFICO")
        sections.append(seo_focus.strip())
        sections.append("")
    
    additional_notes = instructions.get('additional_notes', '')
    if additional_notes and additional_notes.strip():
        sections.append("### 📝 NOTAS ADICIONALES")
        sections.append(additional_notes.strip())
        sections.append("")
    
    if not sections:
        return ""
    
    return "## 📋 INSTRUCCIONES DE REESCRITURA DEL USUARIO\n\n" + "\n".join(sections)


# ============================================================================
# FORMATEO DE ARTÍCULOS PARA FUSIÓN
# ============================================================================

def format_merge_articles_info(html_contents: List[Dict[str, Any]]) -> str:
    """Formatea información de múltiples artículos para fusión."""
    if not html_contents or len(html_contents) < 2:
        return ""
    
    sections = ["## 🔀 ARTÍCULOS A FUSIONAR\n"]
    sections.append(f"Total: {len(html_contents)} artículos")
    sections.append(f"Palabras totales: {sum(a.get('word_count', 0) for a in html_contents):,}\n")
    
    for i, article in enumerate(html_contents):
        priority = "🥇 PRINCIPAL" if i == 0 else f"[ENLAZADO] Artículo {i + 1}"
        title = article.get('title', f'Artículo {i + 1}')
        url = article.get('url', 'Sin URL')
        word_count = article.get('word_count', 0)
        keep_notes = article.get('keep_notes', '')
        
        sections.append(f"### {priority}: {title}")
        sections.append(f"- **URL:** {url}")
        sections.append(f"- **Palabras:** {word_count:,}")
        
        if keep_notes:
            sections.append(f"- **[PRINCIPAL] CONSERVAR:** {keep_notes}")
        
        html_content = article.get('html', '')
        if html_content:
            text = _strip_html(html_content)
            preview = text[:500] + "..." if len(text) > 500 else text
            sections.append(f"- **Preview:** {preview}")
        
        sections.append("")
    
    sections.append("""
### 📋 INSTRUCCIONES DE FUSIÓN

1. **Estructura base**: Usa el artículo principal (🥇) como base estructural
2. **Contenido único**: Incorpora las secciones únicas de cada artículo secundario
3. **Sin duplicidades**: Elimina contenido repetido entre artículos
4. **Coherencia**: El resultado debe leerse como UN SOLO artículo coherente
5. **Conservar lo marcado**: Presta especial atención a las notas "[PRINCIPAL] CONSERVAR"
6. **Mejor de cada uno**: Combina lo mejor de cada artículo
""")
    
    return "\n".join(sections)


# ============================================================================
# FORMATEO DE DESAMBIGUACIÓN
# ============================================================================

def format_disambiguation_info(
    disambiguation_config: Dict[str, Any],
    html_contents: List[Dict[str, Any]]
) -> str:
    """Formatea información para desambiguación post/PLP."""
    if not disambiguation_config:
        return ""
    
    output_type = disambiguation_config.get('output_type', 'post')
    instructions = disambiguation_config.get('instructions', '')
    other_url = disambiguation_config.get('other_url', '')
    conflict_url = disambiguation_config.get('conflict_url', '')
    
    sections = ["##  DESAMBIGUACIÓN DE CONTENIDO\n"]
    
    if output_type == 'post':
        sections.append("### OBJETIVO: Crear contenido EDITORIAL (Post/Guía)")
        sections.append("""
El contenido debe tener **intención INFORMATIVA**:
- Enfoque: Educar, informar, ayudar a decidir
- Tono: Experto y consultivo
- Estructura: Guía, tutorial, comparativa
- Keywords: "cómo elegir", "qué es", "mejores", "diferencias"
- CTAs: Suaves, orientados a seguir leyendo
- NO incluir: Listados de productos con precios, CTAs de compra directa
""")
    else:
        sections.append("### OBJETIVO: Crear contenido TRANSACCIONAL (PLP/Categoría)")
        sections.append("""
El contenido debe tener **intención TRANSACCIONAL**:
- Enfoque: Vender, convertir, facilitar la compra
- Tono: Directo y orientado a la acción
- Estructura: Intro breve + destacados + filtros
- Keywords: "comprar", "precio", "oferta", "en stock"
- CTAs: Directos a producto o categoría
- NO incluir: Contenido extenso educativo
""")
    
    sections.append("")
    
    if conflict_url:
        sections.append(f"**URL conflictiva (a reescribir):** {conflict_url}")
    if other_url:
        sections.append(f"**URL que debe diferenciarse:** {other_url}")
        sections.append(f"⚠️ El nuevo contenido debe ser CLARAMENTE DIFERENTE")
    
    if instructions:
        sections.append("\n### 📋 INSTRUCCIONES DE DESAMBIGUACIÓN")
        sections.append(instructions)
    
    if html_contents:
        content = html_contents[0]
        sections.append("\n### 📄 CONTENIDO CONFLICTIVO ACTUAL")
        sections.append(f"- **Palabras:** {content.get('word_count', 0):,}")
        
        html = content.get('html', '')
        if html:
            text = _strip_html(html)
            preview = text[:800] + "..." if len(text) > 800 else text
            sections.append(f"\n**Preview:**\n{preview}")
    
    return "\n".join(sections)


# ============================================================================
# FORMATEO DE COMPETIDORES
# ============================================================================

def format_competitors_for_prompt(competitors: List[Dict]) -> str:
    """Formatea lista de competidores para el prompt."""
    if not competitors:
        return "(Sin datos de competidores)"
    
    sections = ["##  ANÁLISIS DE COMPETIDORES\n"]
    
    valid_competitors = [c for c in competitors if c.get('scrape_success', False)]
    
    if valid_competitors:
        word_counts = [c.get('word_count', 0) for c in valid_competitors]
        avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
        
        sections.append(f"**Estadísticas:**")
        sections.append(f"- Competidores analizados: {len(valid_competitors)}")
        sections.append(f"- Promedio de palabras: {int(avg_words):,}")
        sections.append(f"- Rango: {min(word_counts):,} - {max(word_counts):,} palabras")
        sections.append("")
    
    for i, comp in enumerate(competitors[:MAX_COMPETITORS_ANALYZED], 1):
        if not comp.get('scrape_success', False):
            continue
        
        title = comp.get('title', 'Sin título')[:80]
        domain = comp.get('domain', 'desconocido')
        position = comp.get('ranking_position', comp.get('position', i))
        word_count = comp.get('word_count', 0)
        content = comp.get('content', '')
        
        sections.append(f"### #{position} - {domain}")
        sections.append(f"**Título:** {title}")
        sections.append(f"**Palabras:** {word_count:,}")
        
        if content:
            preview = content[:1500] + "..." if len(content) > 1500 else content
            sections.append(f"\n**Contenido:**\n{preview}")
        
        sections.append("")
    
    return "\n".join(sections)


def format_competitor_data_for_analysis(competitors: List[Dict]) -> str:
    """Alias para compatibilidad."""
    return format_competitors_for_prompt(competitors)


# ============================================================================
# FORMATEO DE ENLACES EDITORIALES (NUEVO v4.7.1)
# ============================================================================

def format_editorial_links_for_prompt(links: List[Dict[str, Any]]) -> str:
    """
    Formatea enlaces editoriales con su HTML contextual.
    - Post: html_content único
    - PLP: top_text + bottom_text
    """
    if not links:
        return ""
    
    sections = ["## [POST] ENLACES EDITORIALES A INCLUIR\n"]
    sections.append("""
Estos enlaces deben integrarse de forma **natural y contextual** en el contenido.
El HTML proporcionado te ayuda a entender el contexto del destino para crear
enlaces más relevantes y útiles.
""")
    
    for i, link in enumerate(links, 1):
        url = link.get('url', '')
        anchor = link.get('anchor', '')
        editorial_type = link.get('editorial_type', 'post')
        
        type_label = "[POST] Post/Guía" if editorial_type == 'post' else " PLP/Categoría"
        
        sections.append(f"### {i}. {type_label}: [{anchor}]({url})")
        sections.append(f"- **Anchor sugerido:** {anchor}")
        sections.append(f"- **URL destino:** {url}")
        
        # Contenido según tipo
        if editorial_type == 'post':
            html_content = link.get('html_content', '')
            if html_content:
                text = _strip_html(html_content)
                preview = text[:600] + "..." if len(text) > 600 else text
                sections.append(f"\n**Contexto del Post destino:**\n{preview}")
                sections.append("")
                sections.append(" *Usa este contexto para crear un enlace que fluya naturalmente y aporte valor al lector.*")
        else:  # PLP
            top_text = link.get('top_text', '')
            bottom_text = link.get('bottom_text', '')
            
            if top_text:
                text = _strip_html(top_text)
                preview = text[:400] + "..." if len(text) > 400 else text
                sections.append(f"\n**Top text de la PLP:**\n{preview}")
            
            if bottom_text:
                text = _strip_html(bottom_text)
                preview = text[:400] + "..." if len(text) > 400 else text
                sections.append(f"\n**Bottom text de la PLP:**\n{preview}")
            
            if top_text or bottom_text:
                sections.append("")
                sections.append(" *Enlaza a esta PLP cuando hables de categorías de productos o cuando el usuario pueda querer explorar opciones.*")
        
        sections.append("")
    
    sections.append("""
### 📋 BUENAS PRÁCTICAS PARA ENLACES EDITORIALES

1. **Contextuales**: El enlace debe aparecer donde tenga sentido temático
2. **Naturales**: Debe leerse como parte del contenido, no como publicidad
3. **Útiles**: Aporta valor al lector, no solo SEO
4. **Distribuidos**: No agrupar todos los enlaces juntos
5. **Con el anchor correcto**: Usa el anchor sugerido o uno similar con keywords
""")
    
    return "\n".join(sections)


# ============================================================================
# FORMATEO DE ENLACES A PRODUCTOS (CON JSON)
# ============================================================================

def format_product_links_for_prompt(links: List[Dict[str, Any]]) -> str:
    """Formatea enlaces a productos con sus datos JSON."""
    if not links:
        return ""
    
    sections = ["##  ENLACES A PRODUCTOS A INCLUIR\n"]
    sections.append("Estos enlaces a productos deben integrarse donde sea relevante.\n")
    
    for i, link in enumerate(links, 1):
        url = link.get('url', '')
        anchor = link.get('anchor', '')
        prod_data = link.get('product_data')
        
        sections.append(f"### {i}. [{anchor}]({url})")
        sections.append(f"- **Anchor:** {anchor}")
        sections.append(f"- **URL:** {url}")
        
        if prod_data:
            title = prod_data.get('title', '')
            brand = prod_data.get('brand_name', '')
            family = prod_data.get('family_name', '')
            
            if title:
                sections.append(f"- **Producto:** {brand} {title}")
            if family:
                sections.append(f"- **Familia:** {family}")
            
            # Atributos clave
            attributes = prod_data.get('attributes', {})
            if attributes and isinstance(attributes, dict):
                key_attrs = list(attributes.items())[:5]
                if key_attrs:
                    specs = ", ".join(f"{k}: {v}" for k, v in key_attrs)
                    sections.append(f"- **Specs:** {specs}")
            
            # Reviews
            total_comments = prod_data.get('totalComments', 0) or prod_data.get('total_comments', 0)
            if total_comments:
                sections.append(f"- **Reviews:** {total_comments} opiniones")
            
            advantages = prod_data.get('advantages_list') or prod_data.get('advantages', [])
            if advantages and isinstance(advantages, list):
                sections.append(f"- **Puntos fuertes:** {', '.join(advantages[:3])}")
        
        sections.append("")
    
    return "\n".join(sections)


# ============================================================================
# FORMATEO DE PRODUCTOS ALTERNATIVOS (NUEVO v4.7.1)
# ============================================================================

def format_alternative_products_for_prompt(products: List[Dict[str, Any]]) -> str:
    """
    Formatea productos alternativos con sus datos JSON.
    """
    if not products:
        return ""
    
    sections = ["##  PRODUCTOS ALTERNATIVOS A RECOMENDAR\n"]
    sections.append("""
Estos productos deben mencionarse como **alternativas** al producto principal
o como opciones adicionales para diferentes perfiles de usuario.
""")
    
    for i, product in enumerate(products, 1):
        url = product.get('url', '')
        anchor = product.get('anchor', '')
        prod_data = product.get('product_data')
        
        sections.append(f"### Alternativa {i}: [{anchor}]({url})")
        sections.append(f"- **URL:** {url}")
        
        if prod_data:
            title = prod_data.get('title', '')
            brand = prod_data.get('brand_name', '')
            family = prod_data.get('family_name', '')
            description = prod_data.get('description', '')
            
            if title:
                sections.append(f"- **Producto:** {brand} {title}")
            if family:
                sections.append(f"- **Familia:** {family}")
            
            # Atributos para comparar
            attributes = prod_data.get('attributes', {})
            if attributes and isinstance(attributes, dict):
                key_attrs = list(attributes.items())[:8]
                if key_attrs:
                    sections.append("- **Especificaciones:**")
                    for k, v in key_attrs:
                        sections.append(f"  - {k}: {v}")
            
            # Reviews
            total_comments = prod_data.get('totalComments', 0) or prod_data.get('total_comments', 0)
            advantages = prod_data.get('advantages_list') or prod_data.get('advantages', [])
            disadvantages = prod_data.get('disadvantages_list') or prod_data.get('disadvantages', [])
            
            if total_comments:
                sections.append(f"- **Reviews:** {total_comments} opiniones")
            
            if advantages and isinstance(advantages, list):
                sections.append(f"- **Ventajas:** {', '.join(advantages[:3])}")
            
            if disadvantages and isinstance(disadvantages, list):
                sections.append(f"- **⚠️ Consideraciones:** {', '.join(disadvantages[:2])}")
            
            if description:
                desc_preview = description[:300] + "..." if len(description) > 300 else description
                sections.append(f"- **Descripción:** {desc_preview}")
        else:
            sections.append("- *(Sin datos JSON - mencionar de forma genérica)*")
        
        sections.append("")
    
    sections.append("""
### 📋 CÓMO INTEGRAR ALTERNATIVAS

1. **Por perfil**: "Si buscas más potencia, el [Alternativa 1] es ideal..."
2. **Por presupuesto**: "Para quien busque una opción más económica..."
3. **Por uso**: "Si tu enfoque es gaming competitivo, considera..."
4. **Comparativa**: Puedes crear una mini-tabla comparando specs clave
5. **Natural**: No forzar, solo donde tenga sentido
""")
    
    return "\n".join(sections)


# ============================================================================
# FORMATEO DE PRODUCTO PRINCIPAL
# ============================================================================

def format_main_product_for_prompt(main_product: Dict[str, Any]) -> str:
    """Formatea datos del producto principal."""
    if not main_product:
        return ""
    
    url = main_product.get('url', '')
    json_data = main_product.get('json_data')
    
    if not json_data and not url:
        return ""
    
    sections = ["## [PRODUCTO] PRODUCTO PRINCIPAL\n"]
    
    if url:
        sections.append(f"**URL:** {url}")
    
    if json_data:
        title = json_data.get('title', '')
        brand = json_data.get('brand_name', '')
        family = json_data.get('family_name', '')
        description = json_data.get('description', '')
        
        if title:
            sections.append(f"**Producto:** {title}")
        if brand:
            sections.append(f"**Marca:** {brand}")
        if family:
            sections.append(f"**Familia:** {family}")
        
        # Atributos
        attributes = json_data.get('attributes', {})
        if attributes and isinstance(attributes, dict):
            sections.append("\n**Especificaciones técnicas:**")
            for key, value in list(attributes.items())[:15]:
                sections.append(f"- {key}: {value}")
        
        # Reviews
        total_comments = json_data.get('totalComments', 0)
        advantages = json_data.get('advantages', [])
        disadvantages = json_data.get('disadvantages', [])
        
        if total_comments:
            sections.append(f"\n**Reviews:** {total_comments} opiniones")
        
        if advantages:
            sections.append("\n**Ventajas destacadas por usuarios:**")
            for adv in advantages[:5]:
                sections.append(f"-  {adv}")
        
        if disadvantages:
            sections.append("\n**Puntos a mejorar según usuarios:**")
            for dis in disadvantages[:3]:
                sections.append(f"- ⚠️ {dis}")
        
        if description:
            desc_preview = description[:500] + "..." if len(description) > 500 else description
            sections.append(f"\n**Descripción:**\n{desc_preview}")
    
    sections.append("""
### 📋 USO DEL PRODUCTO PRINCIPAL

1. **Es el protagonista**: Todo el contenido gira en torno a este producto
2. **Usa las specs**: Menciona especificaciones técnicas relevantes
3. **Incluye opiniones**: Referencia las ventajas/desventajas de usuarios
4. **Enlaza al producto**: Debe haber enlaces directos al PDP
""")
    
    return "\n".join(sections)


# ============================================================================
# UTILIDADES
# ============================================================================

def _strip_html(html: str) -> str:
    """Elimina tags HTML y retorna texto plano."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


# ============================================================================
# ETAPA 1: BORRADOR
# ============================================================================

def build_rewrite_prompt_stage1(
    keyword: str,
    competitor_analysis: str,
    config: Dict[str, Any],
) -> str:
    """
    Construye el prompt para la Etapa 1: Borrador.
    
    Incluye toda la información del usuario para generar contenido de calidad.
    """
    # Extraer configuración
    rewrite_mode = config.get('rewrite_mode', 'single')
    rewrite_instructions = config.get('rewrite_instructions', {})
    html_contents = config.get('html_contents', [])
    disambiguation = config.get('disambiguation')
    main_product = config.get('main_product')
    editorial_links = config.get('editorial_links', [])
    product_links = config.get('product_links', [])
    alternative_products = config.get('alternative_products', [])
    products = config.get('products', [])  # v5.0
    headings_config = config.get('headings_config')  # v5.0
    target_length = config.get('target_length', 1500)
    objetivo = config.get('objetivo', '')
    context = config.get('context', '')
    arquetipo_codigo = config.get('arquetipo_codigo', '')
    
    min_length = int(target_length * 0.95)
    max_length = int(target_length * 1.05)
    
    # Determinar título según modo
    if rewrite_mode == 'merge':
        mode_title = "FUSIÓN DE ARTÍCULOS"
        mode_description = "Vas a FUSIONAR múltiples artículos en UNO SOLO definitivo."
    elif rewrite_mode == 'disambiguate':
        output_type = disambiguation.get('output_type', 'post') if disambiguation else 'post'
        mode_title = f"DESAMBIGUACIÓN - Crear {'POST' if output_type == 'post' else 'PLP'}"
        mode_description = "Vas a crear contenido CLARAMENTE DIFERENCIADO del contenido conflictivo."
    else:
        mode_title = "REESCRITURA DE ARTÍCULO"
        mode_description = "Vas a MEJORAR un artículo existente siguiendo las instrucciones."
    
    sections = [f"""# TAREA: {mode_title} (ETAPA 1/3)

{mode_description}

##  INFORMACIÓN BÁSICA

**Keyword principal:** {keyword}
**Longitud objetivo:** {target_length} palabras (rango: {min_length}-{max_length})
**Objetivo:** {objetivo if objetivo else 'Crear contenido superior a la competencia'}

## 🔑 OPTIMIZACIÓN DE KEYWORD (OBLIGATORIO)

La keyword "{keyword}" DEBE aparecer de forma natural en el contenido:
- **Densidad objetivo:** 1-2% (aprox. {max(3, target_length // 200)}-{max(6, target_length // 100)} veces en {target_length} palabras)
- **Primeras 100 palabras:** La keyword DEBE aparecer en las primeras 100 palabras del artículo
- **Al menos 1 H2:** La keyword (o variación natural) DEBE aparecer en al menos un encabezado H2
- **Distribución:** Repartida entre inicio, medio y final del artículo (no concentrada en un solo bloque)
- **Natural:** Integrada en frases reales, nunca forzada ni repetitiva
- **FAQs:** El H2 de FAQs debe incluir la keyword: "Preguntas frecuentes sobre {keyword}"
"""]
    
    if context:
        sections.append(f"\n**Contexto adicional:**\n{context}")
    
    # Arquetipo: inyectar información completa (name, description, structure, tone)
    if arquetipo_codigo:
        try:
            from config.arquetipos import get_arquetipo, get_structure, get_tone
            arq = get_arquetipo(arquetipo_codigo)
            if arq:
                sections.append(f"\n## 📚 ARQUETIPO: {arq.get('name', arquetipo_codigo)}")
                arq_desc = arq.get('description', '')
                if arq_desc:
                    sections.append(f"**Descripción:** {arq_desc}")
                arq_tone = arq.get('tone', '')
                if arq_tone:
                    sections.append(f"**Tono del arquetipo:** {arq_tone}")
                structure = get_structure(arquetipo_codigo)
                if structure:
                    sections.append("**Estructura recomendada:**")
                    for i, s in enumerate(structure, 1):
                        sections.append(f"  {i}. {s}")
            else:
                sections.append(f"\n**Arquetipo:** {arquetipo_codigo}")
        except ImportError:
            sections.append(f"\n**Arquetipo:** {arquetipo_codigo}")
    
    # Contexto del briefing (respuestas a preguntas guía)
    guiding_context = config.get('guiding_context', '')
    if guiding_context:
        sections.append(f"\n## 📖 CONTEXTO DEL BRIEF\n{guiding_context}")
    
    sections.append("")
    
    # Tono de marca
    sections.append(BRAND_TONE)
    
    # Instrucciones de reescritura
    instructions_text = format_rewrite_instructions(rewrite_instructions)
    if instructions_text:
        sections.append(instructions_text)
    
    # Información según modo
    if rewrite_mode == 'merge':
        merge_info = format_merge_articles_info(html_contents)
        if merge_info:
            sections.append(merge_info)
    elif rewrite_mode == 'disambiguate':
        disamb_info = format_disambiguation_info(disambiguation, html_contents)
        if disamb_info:
            sections.append(disamb_info)
    else:
        if html_contents:
            content = html_contents[0]
            sections.append("## 📄 ARTÍCULO ORIGINAL A REESCRIBIR\n")
            sections.append(f"**URL:** {content.get('url', 'N/A')}")
            sections.append(f"**Título:** {content.get('title', 'N/A')}")
            sections.append(f"**Palabras:** {content.get('word_count', 0):,}")
            
            html = content.get('html', '')
            if html:
                html_preview = html[:6000] + "\n\n[... truncado ...]" if len(html) > 6000 else html
                sections.append(f"\n**Contenido HTML:**\n```html\n{html_preview}\n```")
            sections.append("")
    
    # Productos (v5.0: lista unificada con fallback a legacy)
    if products and _format_products_for_prompt:
        products_info = _format_products_for_prompt(products)
        if products_info:
            sections.append(products_info)
    else:
        # Fallback legacy: producto principal + alternativos por separado
        product_info = format_main_product_for_prompt(main_product)
        if product_info:
            sections.append(product_info)
        
        alt_products_info = format_alternative_products_for_prompt(alternative_products)
        if alt_products_info:
            sections.append(alt_products_info)
    
    # Competidores
    sections.append(competitor_analysis)
    
    # Enlaces editoriales
    editorial_links_info = format_editorial_links_for_prompt(editorial_links)
    if editorial_links_info:
        sections.append(editorial_links_info)
    
    # Enlaces a productos (solo si NO se usó products v5.0, para evitar duplicar)
    if not products:
        product_links_info = format_product_links_for_prompt(product_links)
        if product_links_info:
            sections.append(product_links_info)
    
    # Estructura de encabezados (v5.0)
    if headings_config and _format_headings_instructions:
        headings_info = _format_headings_instructions(headings_config)
        if headings_info:
            sections.append(headings_info)
    
    # Elementos visuales (v5.0)
    visual_elements = config.get('visual_elements', [])
    if visual_elements and _format_visual_elements_instructions:
        visual_info = _format_visual_elements_instructions(visual_elements)
        if visual_info:
            sections.append(visual_info)
    
    # Estructura HTML
    sections.append(HTML_STRUCTURE_INSTRUCTIONS)
    
    # Instrucciones finales
    sections.append(f"""
# 📋 INSTRUCCIONES FINALES

## Prioridades de esta etapa:

1. **APLICAR INSTRUCCIONES DEL USUARIO** - Las instrucciones son OBLIGATORIAS
2. **KEYWORD "{keyword}"** - Densidad 1-2%, en primeras 100 palabras, en al menos 1 H2, distribuida inicio/medio/final
3. **USAR EL TONO DE MARCA** - PcComponentes: experto, cercano, nunca negativo
4. **SUPERAR A LA COMPETENCIA** - Mejor contenido que todos los competidores
5. **INCLUIR TODOS LOS ENLACES** - Cada enlace proporcionado debe aparecer
6. **INTEGRAR PRODUCTOS** - Usar datos de producto principal y alternativos
7. **LONGITUD CORRECTA** - Entre {min_length} y {max_length} palabras
8. **EVITAR frases de IA:** "En el mundo actual...", "Sin lugar a dudas...", "Es importante destacar...", "Cabe mencionar que...", "Ofrece una experiencia..."
9. **EVITAR adjetivos vacíos:** increíble, revolucionario, impresionante, excepcional
10. **VARIAR** la estructura de cada párrafo (NO empezar todos igual)
11. **EMOJIS:** No usar emojis en el contenido generado.
12. **VEREDICTO** que aporte perspectiva nueva, no solo resuma
13. **FECHAS:** NO incluyas años concretos (2024, 2025, 2026) en títulos ni encabezados salvo que la keyword del usuario ya incluya un año. Los años envejecen el contenido.

## Checklist antes de generar:

- [ ] ¿Apliqué TODOS los puntos a mejorar?
- [ ] ¿Mantuve los puntos que funcionan bien?
- [ ] ¿Eliminé el contenido obsoleto/incorrecto?
- [ ] ¿Añadí el contenido nuevo solicitado?
- [ ] ¿El tono es el de PcComponentes?
- [ ] ¿Incluí todos los enlaces editoriales de forma contextual?
- [ ] ¿Incluí todos los enlaces a productos?
- [ ] ¿Mencioné los productos alternativos donde tiene sentido?
- [ ] ¿Es mejor que la competencia?
- [ ] ¿Suena a persona real, NO a texto generado por IA?
- [ ] ¿Varía la estructura entre párrafos?

---

**GENERA AHORA EL BORRADOR HTML COMPLETO.**

Responde SOLO con el HTML (desde el primer <article> hasta el último </article>).
NO incluyas explicaciones ni texto fuera del HTML.
""")
    
    return "\n".join(sections)


# ============================================================================
# ETAPA 2: ANÁLISIS CRÍTICO
# ============================================================================

def build_rewrite_correction_prompt_stage2(
    draft_content: str,
    target_length: int,
    keyword: str,
    competitor_analysis: str,
    config: Dict[str, Any],
) -> str:
    """Construye el prompt para la Etapa 2: Análisis crítico."""
    
    rewrite_instructions = config.get('rewrite_instructions', {})
    rewrite_mode = config.get('rewrite_mode', 'single')
    objetivo = config.get('objetivo', '')
    editorial_links = config.get('editorial_links', [])
    product_links = config.get('product_links', [])
    alternative_products = config.get('alternative_products', [])
    products = config.get('products', [])  # v5.0
    arquetipo_code = config.get('arquetipo_codigo', '')
    visual_elements = config.get('visual_elements', [])

    # QW-1: Checklist específico del arquetipo
    archetype_checklist = ""
    visual_minimum_check = ""
    if _build_archetype_checklist_stage2 and arquetipo_code:
        try:
            from config.arquetipos import get_structure
            archetype_checklist = _build_archetype_checklist_stage2(
                arquetipo_code, get_structure(arquetipo_code),
            )
        except ImportError:
            pass
    # QW-2: Elementos visuales mínimos del arquetipo
    if _build_visual_elements_minimum_check and arquetipo_code:
        visual_minimum_check = _build_visual_elements_minimum_check(arquetipo_code, visual_elements)

    min_length = int(target_length * 0.95)
    max_length = int(target_length * 1.05)
    
    # Checklist de instrucciones
    instruction_checklist = []
    
    improve = rewrite_instructions.get('improve', [])
    if improve:
        instruction_checklist.append("### Verificar MEJORAS aplicadas:")
        for item in improve:
            instruction_checklist.append(f"- [ ] {item}")
    
    maintain = rewrite_instructions.get('maintain', [])
    if maintain:
        instruction_checklist.append("\n### Verificar ELEMENTOS MANTENIDOS:")
        for item in maintain:
            instruction_checklist.append(f"- [ ] {item}")
    
    remove = rewrite_instructions.get('remove', [])
    if remove:
        instruction_checklist.append("\n### Verificar CONTENIDO ELIMINADO:")
        for item in remove:
            instruction_checklist.append(f"- [ ] {item} (debe estar ausente)")
    
    add = rewrite_instructions.get('add', [])
    if add:
        instruction_checklist.append("\n### Verificar CONTENIDO AÑADIDO:")
        for item in add:
            instruction_checklist.append(f"- [ ] {item}")
    
    instruction_checklist_text = "\n".join(instruction_checklist) if instruction_checklist else "(Sin instrucciones específicas)"
    
    # Checklist de enlaces
    links_checklist = ""
    if editorial_links or product_links or alternative_products or products:
        links_checklist = "\n### Verificar ENLACES incluidos:\n"
        
        for link in editorial_links:
            url = link.get('url', '')
            anchor = link.get('anchor', '')
            links_checklist += f"- [ ] Editorial: [{anchor}]({url})\n"
        
        # v5.0: productos unificados (incluye principal, alternativo, enlazado)
        if products:
            for prod in products:
                url = prod.get('url', '')
                name = prod.get('name', '') or (prod.get('json_data', {}) or {}).get('title', '')
                role = prod.get('role', 'principal')
                role_label = {"principal": "[PRINCIPAL] Principal", "alternativo": "[ALTERNATIVO] Alternativo", "enlazado": "[ENLAZADO] Enlazado"}.get(role, role)
                links_checklist += f"- [ ] [{role_label}] {name} ({url})\n"
        else:
            # Fallback legacy
            for link in product_links:
                url = link.get('url', '')
                anchor = link.get('anchor', '')
                links_checklist += f"- [ ] Producto: [{anchor}]({url})\n"
            
            for prod in alternative_products:
                url = prod.get('url', '')
                anchor = prod.get('anchor', '')
                links_checklist += f"- [ ] Alternativo: [{anchor}]({url})\n"
    
    prompt = f"""# TAREA: ANÁLISIS CRÍTICO DEL BORRADOR (ETAPA 2/3)

Eres un editor SEO senior de PcComponentes. Analiza el borrador y genera un informe de correcciones.

## BORRADOR A ANALIZAR

```html
{draft_content[:12000]}
```

## KEYWORD OBJETIVO
"{keyword}"

## OBJETIVO DEL CONTENIDO
{objetivo if objetivo else 'Superar a la competencia'}

## MODO DE REESCRITURA
{rewrite_mode.upper()}

## CHECKLIST DE INSTRUCCIONES DEL USUARIO

{instruction_checklist_text}
{links_checklist}

## REFERENCIA COMPETITIVA

{competitor_analysis[:3000] if competitor_analysis else "(Sin referencia)"}

{ANTI_IA_CHECKLIST_STAGE2 if _brand_tone_available else '''
## ANTI-IA (CRÍTICO)
- [ ] ¿Evita frases como "En el mundo actual...", "Sin lugar a dudas..."?
- [ ] ¿Evita adjetivos vacíos (increíble, revolucionario, impresionante)?
- [ ] ¿Varía la estructura entre párrafos?
- [ ] ¿El veredicto aporta valor nuevo?
- [ ] ¿No contiene emojis?
'''}
{visual_minimum_check}
{archetype_checklist}

---

# ANÁLISIS REQUERIDO

Genera un JSON con esta estructura:

```json
{{
  "analisis_tecnico": {{
    "estructura_html_correcta": true/false,
    "errores_estructura": ["lista de errores"],
    "longitud_actual": número,
    "longitud_objetivo": {target_length},
    "dentro_de_rango": true/false,
    "ajuste_necesario": "ninguno/aumentar/reducir"
  }},

  "keyword_seo": {{
    "keyword": "{keyword}",
    "apariciones_total": número,
    "densidad_porcentaje": número,
    "en_primeras_100_palabras": true/false,
    "en_algun_h2": true/false,
    "distribucion": "buena/concentrada/ausente",
    "correcciones_keyword": ["lista de ajustes necesarios"]
  }},
  
  "cumplimiento_instrucciones": {{
    "mejoras_aplicadas": ["lista"],
    "mejoras_pendientes": ["lista"],
    "elementos_mantenidos": ["lista"],
    "elementos_modificados_indebidamente": ["lista"],
    "contenido_eliminado": ["lista"],
    "contenido_no_eliminado": ["lista"],
    "contenido_añadido": ["lista"],
    "contenido_faltante": ["lista"]
  }},
  
  "cumplimiento_enlaces": {{
    "editoriales_incluidos": ["URLs"],
    "editoriales_faltantes": ["URLs"],
    "productos_incluidos": ["URLs"],
    "productos_faltantes": ["URLs"],
    "alternativos_mencionados": ["URLs"],
    "alternativos_faltantes": ["URLs"],
    "integracion_natural": true/false
  }},
  
  "tono_marca": {{
    "es_correcto": true/false,
    "problemas_detectados": ["lista"],
    "frases_a_corregir": ["lista"],
    "frases_ia_detectadas": ["lista de frases genéricas/artificiales encontradas"],
    "tiene_personalidad": true/false,
    "varia_estructura_parrafos": true/false,
    "emojis_encontrados": ["lista de emojis encontrados en el contenido"]
  }},
  
  "superioridad_competitiva": {{
    "es_superior": true/false,
    "gaps_cubiertos": ["lista"],
    "gaps_pendientes": ["lista"],
    "diferenciacion": "descripción"
  }},
  
  "elementos_visuales": {{
    "solicitados": [],
    "presentes": [],
    "faltantes": [],
    "minimos_arquetipo": [],
    "minimos_faltantes": []
  }},

  "arquetipo": {{
    "code": "{arquetipo_code}",
    "cumplimiento_estructura": []
  }},

  "correcciones_prioritarias": [
    {{
      "tipo": "tecnico/contenido/enlace/tono/anti-ia",
      "descripcion": "problema",
      "solucion": "cómo corregir",
      "prioridad": "alta/media/baja"
    }}
  ],

  "puntuacion_general": {{
    "tecnica": 0-100,
    "instrucciones": 0-100,
    "enlaces": 0-100,
    "tono": 0-100,
    "competitiva": 0-100,
    "total": 0-100
  }}
}}
```

---

Responde SOLO con el JSON puro.
"""
    
    return prompt


# ============================================================================
# ETAPA 3: VERSIÓN FINAL
# ============================================================================

def build_rewrite_final_prompt_stage3(
    draft_content: str,
    corrections_json: str,
    config: Dict[str, Any],
) -> str:
    """Construye el prompt para la Etapa 3: Versión final."""
    
    target_length = config.get('target_length', 1500)
    keyword = config.get('keyword', '')
    editorial_links = config.get('editorial_links', [])
    product_links = config.get('product_links', [])
    alternative_products = config.get('alternative_products', [])
    products = config.get('products', [])  # v5.0
    rewrite_instructions = config.get('rewrite_instructions', {})
    rewrite_mode = config.get('rewrite_mode', 'single')
    
    min_length = int(target_length * 0.95)
    max_length = int(target_length * 1.05)
    
    # Recordatorios críticos
    critical_reminders = []
    
    improve = rewrite_instructions.get('improve', [])
    if improve:
        critical_reminders.append("### ✨ MEJORAS OBLIGATORIAS:")
        for item in improve:
            critical_reminders.append(f"- {item}")
    
    add = rewrite_instructions.get('add', [])
    if add:
        critical_reminders.append("\n### ➕ CONTENIDO OBLIGATORIO:")
        for item in add:
            critical_reminders.append(f"- {item}")
    
    if editorial_links:
        critical_reminders.append("\n### [POST] ENLACES EDITORIALES OBLIGATORIOS:")
        for link in editorial_links:
            url = link.get('url', '')
            anchor = link.get('anchor', '')
            critical_reminders.append(f"- [{anchor}]({url})")
    
    # v5.0: productos unificados (incluye principal, alternativo, enlazado)
    if products:
        critical_reminders.append("\n### [PRODUCTO] PRODUCTOS QUE DEBEN APARECER:")
        for prod in products:
            url = prod.get('url', '')
            name = prod.get('name', '') or (prod.get('json_data', {}) or {}).get('title', '')
            role = prod.get('role', 'principal')
            role_icon = {"principal": "[PRINCIPAL]", "alternativo": "[ALTERNATIVO]", "enlazado": "[ENLAZADO]"}.get(role, "[PRODUCTO]")
            critical_reminders.append(f"- {role_icon} {name} ({url})")
    else:
        # Fallback legacy
        if product_links:
            critical_reminders.append("\n###  ENLACES A PRODUCTOS OBLIGATORIOS:")
            for link in product_links:
                url = link.get('url', '')
                anchor = link.get('anchor', '')
                critical_reminders.append(f"- [{anchor}]({url})")
        
        if alternative_products:
            critical_reminders.append("\n###  PRODUCTOS ALTERNATIVOS A MENCIONAR:")
            for prod in alternative_products:
                url = prod.get('url', '')
                anchor = prod.get('anchor', '')
                critical_reminders.append(f"- [{anchor}]({url})")
    
    reminders_text = "\n".join(critical_reminders) if critical_reminders else ""
    
    # v5.0: Visual elements en Stage 3 rewrite
    visual_elements = config.get('visual_elements', [])
    visual_section = ""
    css_section = ""
    checklist_section = ""
    
    if visual_elements:
        # Templates e instrucciones imperativas
        if _build_stage3_visual_instructions:
            visual_section = "\n" + _build_stage3_visual_instructions(visual_elements)
        
        # CSS para los componentes
        if _get_css_for_prompt:
            css_for_prompt = _get_css_for_prompt(visual_elements=visual_elements)
            if css_for_prompt:
                css_section = f"\n## CSS DE COMPONENTES\nIncluye este CSS en el <style> del HTML:\n```css\n{css_for_prompt}\n```\n"
        
        # Checklist pre-entrega
        if _build_stage3_checklist:
            checklist_items = _build_stage3_checklist(visual_elements)
            if checklist_items:
                checklist_section = f"\n## 🔍 CHECKLIST PRE-ENTREGA\nAntes de entregar, verifica que TODOS estos elementos están en el HTML:\n{checklist_items}\n"
    
    prompt = f"""# TAREA: VERSIÓN FINAL CON CORRECCIONES (ETAPA 3/3)

Esta es la ETAPA FINAL. Genera la versión DEFINITIVA aplicando TODAS las correcciones.

## KEYWORD OBJETIVO
"{keyword}"

## MODO
{rewrite_mode.upper()}
{visual_section}
{css_section}

## BORRADOR ORIGINAL (ETAPA 1)

```html
{draft_content[:12000]}
```

## ANÁLISIS Y CORRECCIONES (ETAPA 2)

```json
{corrections_json[:4000]}
```

{reminders_text}

{BRAND_TONE}

{REGLAS_CRITICAS_COMUNES if _brand_tone_available else '''
##  EVITAR SIGNOS DE IA (CRÍTICO)
- "En el mundo actual..." / "Sin lugar a dudas..." / "Es importante destacar..."
- Adjetivos vacíos: increíble, revolucionario, impresionante, excepcional
- El veredicto NO debe repetir lo ya dicho
- Estructuras repetitivas párrafo tras párrafo
- No usar emojis en el contenido generado.
'''}

---

# INSTRUCCIONES CRÍTICAS

## Requisitos Técnicos:

1. **Estructura de 3 articles** exacta del CMS
2. **Título principal con <h2>** (NUNCA <h1>)
3. **Kicker con <span class="kicker">**
4. **Longitud entre {min_length} y {max_length} palabras**
5. **HTML puro** sin markdown
6. **Clases CSS correctas**

## Requisitos de Contenido:

7. **APLICAR todas las correcciones**
8. **KEYWORD "{keyword}"** - Densidad 1-2%, en primeras 100 palabras, en al menos 1 H2, distribuida en inicio/medio/final
9. **INCLUIR todos los enlaces** (editoriales, productos, alternativos)
10. **TONO PcComponentes** - Experto, cercano, nunca negativo
11. **SUPERAR a la competencia**
12. **VARIAR** la estructura de cada párrafo
13. **VEREDICTO** que aporte perspectiva nueva, no solo resuma
14. **EMOJIS:** No usar emojis en el contenido generado
{checklist_section}
---

**GENERA AHORA LA VERSIÓN FINAL.**

Responde SOLO con el HTML completo.
NO incluyas explicaciones.
"""
    
    return prompt


# ============================================================================
# SISTEMA
# ============================================================================

def build_system_prompt() -> str:
    """System prompt para los agentes (usa brand_tone centralizado)."""
    if _brand_tone_available:
        return get_system_prompt_base()
    
    # Fallback si brand_tone no está disponible
    return """Eres un experto redactor y editor SEO de PcComponentes, la tienda líder de tecnología en España.

Tu trabajo es crear contenido que:
1. Sea útil y valioso para los usuarios
2. Esté optimizado para SEO sin sobre-optimizar
3. Siga el tono de marca de PcComponentes
4. Cumpla con la estructura CMS requerida
5. APLIQUE todas las instrucciones del usuario

Tono de marca PcComponentes:
- Expertos sin ser pedantes
- Frikis sin vergüenza  
- Cercanos pero profesionales
- Tuteamos al lector
- Usamos analogías tech cuando aportan valor
- Hablamos claro, no vendemos humo
- SIEMPRE orientados a ayudar
- NUNCA desanimamos, siempre ofrecemos alternativas

EVITA SIGNOS DE IA:
- "En el mundo actual...", "Sin lugar a dudas...", "Es importante destacar..."
- "Cabe mencionar que...", "Es fundamental...", "A la hora de..."
- Adjetivos vacíos: increíble, revolucionario, impresionante, excepcional
- Estructuras repetitivas párrafo tras párrafo
- No usar ningun emoji.

Reglas críticas:
- Las instrucciones del usuario son OBLIGATORIAS
- Todos los enlaces proporcionados DEBEN aparecer
- El contenido debe ser SUPERIOR a la competencia
- La estructura HTML del CMS es INNEGOCIABLE
"""


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'HTML_STRUCTURE_INSTRUCTIONS',
    'BRAND_TONE',
    'DEFAULT_LENGTH_TOLERANCE',
    'MAX_COMPETITORS_ANALYZED',
    # Formateo
    'format_rewrite_instructions',
    'format_merge_articles_info',
    'format_disambiguation_info',
    'format_competitors_for_prompt',
    'format_competitor_data_for_analysis',
    'format_editorial_links_for_prompt',
    'format_product_links_for_prompt',
    'format_alternative_products_for_prompt',
    'format_main_product_for_prompt',
    # Prompts
    'build_rewrite_prompt_stage1',
    'build_rewrite_correction_prompt_stage2',
    'build_rewrite_final_prompt_stage3',
    'build_system_prompt',
]
