"""
Prompt Templates - PcComponentes Content Generator
Versión 4.3.1

Sistema de templates para prompts de generación de contenido.
Usa string.Template para evitar problemas con f-strings y llaves dobles.

Este módulo proporciona:
- Templates seguros sin conflictos de llaves
- Funciones builder para construir prompts
- Validación de variables requeridas
- Soporte para JSON embebido en prompts
- Sistema mejorado de enlaces con tipos (blog, listado, producto)

IMPORTANTE: Este módulo usa string.Template con sintaxis $variable
en lugar de f-strings para evitar conflictos con JSON y código.

CAMBIOS v4.3.1:
- Eliminados templates HTML legacy no utilizados:
  HTML_STRUCTURE_TEMPLATE, COMPARISON_TABLE_TEMPLATE,
  PRODUCT_GRID_TEMPLATE, PRODUCT_CARD_TEMPLATE
  (los templates reales viven en new_content.py y rewrite.py
  con clases BEM del design system actual)
- Corregido _get_default_html_structure: h1 → h2 (CMS PcComponentes)

Autor: PcComponentes - Product Discovery & Content
"""

import re
import json
import logging
from string import Template
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# VERSIÓN Y CONSTANTES
# ============================================================================

__version__ = "4.3.1"


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class TemplateError(Exception):
    """Excepción base para errores de templates."""
    
    def __init__(self, message: str, template_name: str = "", details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.template_name = template_name
        self.details = details or {}


class MissingVariableError(TemplateError):
    """Error cuando faltan variables requeridas."""
    
    def __init__(self, missing_vars: List[str], template_name: str = ""):
        message = f"Variables faltantes: {', '.join(missing_vars)}"
        super().__init__(message, template_name, {"missing": missing_vars})
        self.missing_vars = missing_vars


class InvalidTemplateError(TemplateError):
    """Error cuando el template es inválido."""
    pass


# ============================================================================
# CLASE SAFETTEMPLATE - TEMPLATE SEGURO
# ============================================================================

class SafeTemplate:
    """
    Template seguro que usa $variable en lugar de {variable}.
    
    Evita conflictos con:
    - JSON embebido en prompts
    - Código con llaves
    - CSS con llaves
    - Cualquier contenido que use { }
    
    Sintaxis:
    - $variable - Variable simple
    - ${variable} - Variable con delimitador explícito
    - $$ - Literal $ (escapado)
    
    Example:
        >>> template = SafeTemplate("Hola $nombre, tu JSON es: {\"key\": \"value\"}")
        >>> result = template.render(nombre="Usuario")
        >>> # Result: 'Hola Usuario, tu JSON es: {"key": "value"}'
    """
    
    def __init__(self, template_string: str, name: str = "unnamed"):
        """
        Inicializa el template.
        
        Args:
            template_string: String del template con $variables
            name: Nombre del template para debugging
        """
        self._raw = template_string
        self._name = name
        self._template = Template(template_string)
        self._variables = self._extract_variables()
    
    def _extract_variables(self) -> List[str]:
        """Extrae nombres de variables del template."""
        # Patrón para encontrar $variable o ${variable}
        pattern = r'\$\{?([a-zA-Z_][a-zA-Z0-9_]*)\}?'
        matches = re.findall(pattern, self._raw)
        return list(set(matches))
    
    def render(self, **kwargs) -> str:
        """
        Renderiza el template con las variables proporcionadas.
        
        Args:
            **kwargs: Variables para sustituir
            
        Returns:
            String con variables sustituidas
            
        Raises:
            MissingVariableError: Si faltan variables requeridas
        """
        # Verificar variables requeridas
        missing = [var for var in self._variables if var not in kwargs]
        
        if missing:
            raise MissingVariableError(missing, self._name)
        
        try:
            return self._template.safe_substitute(**kwargs)
        except Exception as e:
            raise InvalidTemplateError(
                f"Error renderizando template: {e}",
                self._name,
                {"error": str(e)}
            )
    
    def safe_render(self, **kwargs) -> str:
        """
        Renderiza el template, dejando variables faltantes sin sustituir.
        
        Args:
            **kwargs: Variables para sustituir
            
        Returns:
            String con variables sustituidas (las faltantes quedan como $variable)
        """
        return self._template.safe_substitute(**kwargs)
    
    def get_variables(self) -> List[str]:
        """Retorna lista de variables del template."""
        return self._variables.copy()
    
    def validate(self, **kwargs) -> List[str]:
        """
        Valida que todas las variables estén presentes.
        
        Args:
            **kwargs: Variables a validar
            
        Returns:
            Lista de variables faltantes (vacía si todas están)
        """
        return [var for var in self._variables if var not in kwargs]
    
    def __str__(self) -> str:
        return f"SafeTemplate({self._name})"
    
    def __repr__(self) -> str:
        return f"SafeTemplate(name={self._name!r}, variables={self._variables})"


# ============================================================================
# REGISTRO DE TEMPLATES
# ============================================================================

class TemplateRegistry:
    """
    Registro centralizado de templates.
    
    Permite registrar, obtener y validar templates de forma centralizada.
    """
    
    def __init__(self):
        self._templates: Dict[str, SafeTemplate] = {}
    
    def register(self, name: str, template_string: str) -> SafeTemplate:
        """
        Registra un nuevo template.
        
        Args:
            name: Nombre único del template
            template_string: String del template
            
        Returns:
            SafeTemplate registrado
        """
        template = SafeTemplate(template_string, name)
        self._templates[name] = template
        logger.debug(f"Template registrado: {name}")
        return template
    
    def get(self, name: str) -> Optional[SafeTemplate]:
        """Obtiene un template por nombre."""
        return self._templates.get(name)
    
    def render(self, name: str, **kwargs) -> str:
        """
        Renderiza un template por nombre.
        
        Args:
            name: Nombre del template
            **kwargs: Variables para sustituir
            
        Returns:
            String renderizado
            
        Raises:
            TemplateError: Si el template no existe
        """
        template = self._templates.get(name)
        
        if not template:
            raise TemplateError(f"Template no encontrado: {name}", name)
        
        return template.render(**kwargs)
    
    def list_templates(self) -> List[str]:
        """Lista todos los templates registrados."""
        return list(self._templates.keys())
    
    def __contains__(self, name: str) -> bool:
        return name in self._templates


# Instancia global del registro
_registry = TemplateRegistry()


def get_registry() -> TemplateRegistry:
    """Obtiene el registro global de templates."""
    return _registry


# ============================================================================
# TEMPLATES BASE - SISTEMA DE PROMPTS
# ============================================================================

# Template del system prompt principal
SYSTEM_PROMPT_TEMPLATE = SafeTemplate("""
Eres un experto en SEO y redacción de contenido para PcComponentes, 
la tienda líder de tecnología en España.

CONTEXTO DE MARCA:
$brand_context

INSTRUCCIONES GENERALES:
- Escribe en español de España (tutea al lector)
- Usa un tono $tone (experto pero cercano)
- Optimiza para la keyword principal: "$keyword"
- Longitud objetivo: $target_length palabras aproximadamente
- Formato: HTML semántico con las clases CSS proporcionadas

ESTRUCTURA HTML REQUERIDA:
$html_structure

$additional_instructions
""", name="system_prompt")


# Template para generación de contenido nuevo
CONTENT_GENERATION_TEMPLATE = SafeTemplate("""
Genera contenido SEO de tipo "$content_type" para la keyword: "$keyword"

DATOS DEL PRODUCTO/CATEGORÍA:
$product_data

KEYWORDS SECUNDARIAS A INCLUIR:
$secondary_keywords

ENLACES A INCLUIR:
$links_section

ESTRUCTURA ESPERADA:
$structure_guide

REQUISITOS ESPECÍFICOS:
$specific_requirements

Genera el contenido HTML completo siguiendo las instrucciones.
""", name="content_generation")


# Template para reescritura de contenido
REWRITE_TEMPLATE = SafeTemplate("""
Reescribe y mejora el siguiente contenido SEO.

CONTENIDO ORIGINAL:
$original_content

ANÁLISIS DE COMPETIDORES:
$competitor_analysis

KEYWORD PRINCIPAL: "$keyword"
KEYWORDS A POTENCIAR: $keywords_to_boost

MEJORAS REQUERIDAS:
$improvements_needed

MANTENER:
$elements_to_keep

INSTRUCCIONES DE REESCRITURA:
$rewrite_instructions

Genera el contenido HTML mejorado.
""", name="rewrite")


# Template para análisis de contenido
ANALYSIS_TEMPLATE = SafeTemplate("""
Analiza el siguiente contenido y proporciona recomendaciones de mejora.

CONTENIDO A ANALIZAR:
$content

KEYWORD PRINCIPAL: "$keyword"
TIPO DE CONTENIDO: $content_type

CRITERIOS DE ANÁLISIS:
1. Optimización SEO (uso de keyword, estructura, meta)
2. Calidad del contenido (profundidad, valor, originalidad)
3. Experiencia de usuario (legibilidad, estructura, CTAs)
4. Alineación con la marca PcComponentes

Proporciona el análisis en formato JSON:
{
    "seo_score": <1-10>,
    "content_quality": <1-10>,
    "ux_score": <1-10>,
    "brand_alignment": <1-10>,
    "strengths": ["..."],
    "weaknesses": ["..."],
    "recommendations": ["..."],
    "priority_improvements": ["..."]
}
""", name="analysis")


# Template para sección de enlaces (versión simple - compatibilidad)
LINKS_SECTION_TEMPLATE = SafeTemplate("""
ENLACES INTERNOS (incluir de forma natural):
$internal_links

ENLACES A PRODUCTOS (PDPs):
$pdp_links

INSTRUCCIONES DE ENLAZADO:
- Integra los enlaces de forma natural en el texto
- Usa anchor text descriptivo y variado
- No fuerces enlaces donde no encajen
- Prioriza enlaces en la primera mitad del contenido
""", name="links_section")


# Template para sección de enlaces mejorados con tipos
ENHANCED_LINKS_SECTION_TEMPLATE = SafeTemplate("""
## ENLACES A INCLUIR EN EL CONTENIDO

Incluye estos enlaces de forma natural en el texto, respetando el tipo y contexto de cada uno.

$blog_links_section

$category_links_section

$pdp_links_section

### INSTRUCCIONES DE ENLAZADO:
1. **Integración natural**: Los enlaces deben fluir con el texto, no parecer forzados
2. **Contexto apropiado**:
   - Enlaces a BLOG: en menciones de temas relacionados, guías complementarias
   - Enlaces a LISTADOS: cuando se recomiende explorar opciones o categorías
   - Enlaces a PRODUCTOS: en recomendaciones específicas, menciones de productos, CTAs
3. **Anchor text**: Usa EXACTAMENTE el texto ancla proporcionado para cada enlace
4. **Distribución**: Reparte los enlaces a lo largo del contenido, no los agrupes
5. **Prioridad**: Incluye TODOS los enlaces proporcionados
""", name="enhanced_links_section")


# Template para grupo de enlaces de blog
BLOG_LINKS_GROUP_TEMPLATE = SafeTemplate("""
### [POST] Enlaces a otros artículos del blog:
Estos enlaces deben aparecer en contextos donde se mencionen temas relacionados, 
guías complementarias o información adicional.

$links_list
""", name="blog_links_group")


# Template para grupo de enlaces de categorías/listados
CATEGORY_LINKS_GROUP_TEMPLATE = SafeTemplate("""
### 📂 Enlaces a listados/categorías de productos:
Estos enlaces deben aparecer cuando se mencionen categorías de productos, 
comparativas generales o recomendaciones de explorar más opciones.

$links_list
""", name="category_links_group")


# Template para grupo de enlaces de productos (PDPs)
PDP_LINKS_GROUP_TEMPLATE = SafeTemplate("""
###  Enlaces a fichas de producto:
Estos enlaces deben aparecer cuando se mencione un producto específico, 
en recomendaciones concretas o en CTAs de compra.

$links_list
""", name="pdp_links_group")


# Template para enlace individual mejorado
ENHANCED_LINK_ITEM_TEMPLATE = SafeTemplate("""
- **Anchor:** "$anchor_text"
  **URL:** $url
""", name="enhanced_link_item")


# Template para datos de competidores
COMPETITOR_TEMPLATE = SafeTemplate("""
COMPETIDOR $index: $competitor_url

Título: $competitor_title
Palabras: $word_count

Contenido relevante:
$competitor_content

Puntos fuertes a considerar:
$strengths
---
""", name="competitor")



# Template para FAQs
FAQS_TEMPLATE = SafeTemplate("""
<section class="faqs">
    <h2>Preguntas frecuentes</h2>
    $faq_items
</section>
""", name="faqs")


# Template para item de FAQ individual
FAQ_ITEM_TEMPLATE = SafeTemplate("""
    <div class="faq-item">
        <p class="q">$question</p>
        <p class="a">$answer</p>
    </div>
""", name="faq_item")


# Template para callout/destacado
CALLOUT_TEMPLATE = SafeTemplate("""
<div class="callout $callout_type">
    <p><strong>$callout_title</strong></p>
    <p>$callout_content</p>
</div>
""", name="callout")



# ============================================================================
# FUNCIONES BUILDER PARA CONSTRUIR PROMPTS
# ============================================================================

def build_system_prompt(
    keyword: str,
    tone: str = "profesional y cercano",
    target_length: int = 1500,
    brand_context: str = "",
    html_structure: str = "",
    additional_instructions: str = ""
) -> str:
    """
    Construye el system prompt principal.
    
    Args:
        keyword: Keyword principal
        tone: Tono del contenido
        target_length: Longitud objetivo en palabras
        brand_context: Contexto de marca
        html_structure: Estructura HTML a seguir
        additional_instructions: Instrucciones adicionales
        
    Returns:
        System prompt completo
    """
    return SYSTEM_PROMPT_TEMPLATE.render(
        keyword=keyword,
        tone=tone,
        target_length=str(target_length),
        brand_context=brand_context or _get_default_brand_context(),
        html_structure=html_structure or _get_default_html_structure(),
        additional_instructions=additional_instructions
    )


def build_content_prompt(
    keyword: str,
    content_type: str,
    product_data: str = "",
    secondary_keywords: Optional[List[str]] = None,
    internal_links: Optional[List[str]] = None,
    pdp_links: Optional[List[str]] = None,
    structure_guide: str = "",
    specific_requirements: str = ""
) -> str:
    """
    Construye el prompt de generación de contenido.
    
    Args:
        keyword: Keyword principal
        content_type: Tipo de contenido (GC, RV, CP, etc.)
        product_data: Datos del producto/categoría
        secondary_keywords: Keywords secundarias
        internal_links: Enlaces internos
        pdp_links: Enlaces a PDPs
        structure_guide: Guía de estructura
        specific_requirements: Requisitos específicos
        
    Returns:
        Prompt de generación completo
    """
    # Construir sección de enlaces
    links_section = build_links_section(internal_links, pdp_links)
    
    # Formatear keywords secundarias
    secondary_kw_str = ""
    if secondary_keywords:
        secondary_kw_str = "\n".join(f"- {kw}" for kw in secondary_keywords)
    else:
        secondary_kw_str = "- (Ninguna especificada, usar variaciones naturales de la keyword principal)"
    
    return CONTENT_GENERATION_TEMPLATE.render(
        keyword=keyword,
        content_type=_get_content_type_name(content_type),
        product_data=product_data or "(No hay datos específicos de producto)",
        secondary_keywords=secondary_kw_str,
        links_section=links_section,
        structure_guide=structure_guide or _get_structure_guide(content_type),
        specific_requirements=specific_requirements or _get_default_requirements(content_type)
    )


def build_rewrite_prompt(
    keyword: str,
    original_content: str,
    competitor_analysis: str = "",
    keywords_to_boost: Optional[List[str]] = None,
    improvements_needed: str = "",
    elements_to_keep: str = "",
    rewrite_instructions: str = ""
) -> str:
    """
    Construye el prompt de reescritura.
    
    Args:
        keyword: Keyword principal
        original_content: Contenido original a reescribir
        competitor_analysis: Análisis de competidores
        keywords_to_boost: Keywords a potenciar
        improvements_needed: Mejoras necesarias
        elements_to_keep: Elementos a mantener
        rewrite_instructions: Instrucciones de reescritura
        
    Returns:
        Prompt de reescritura completo
    """
    # Formatear keywords a potenciar
    kw_boost_str = ""
    if keywords_to_boost:
        kw_boost_str = ", ".join(f'"{kw}"' for kw in keywords_to_boost)
    else:
        kw_boost_str = "(Mantener las actuales)"
    
    return REWRITE_TEMPLATE.render(
        keyword=keyword,
        original_content=_truncate_content(original_content, 5000),
        competitor_analysis=competitor_analysis or "(Sin análisis de competidores)",
        keywords_to_boost=kw_boost_str,
        improvements_needed=improvements_needed or _get_default_improvements(),
        elements_to_keep=elements_to_keep or _get_default_keep_elements(),
        rewrite_instructions=rewrite_instructions or _get_default_rewrite_instructions()
    )


def build_analysis_prompt(
    content: str,
    keyword: str,
    content_type: str = "GC"
) -> str:
    """
    Construye el prompt de análisis.
    
    Args:
        content: Contenido a analizar
        keyword: Keyword principal
        content_type: Tipo de contenido
        
    Returns:
        Prompt de análisis completo
    """
    return ANALYSIS_TEMPLATE.render(
        content=_truncate_content(content, 8000),
        keyword=keyword,
        content_type=_get_content_type_name(content_type)
    )


def build_links_section(
    internal_links: Optional[List[str]] = None,
    pdp_links: Optional[List[str]] = None
) -> str:
    """
    Construye la sección de enlaces para el prompt (versión simple).
    
    NOTA: Para enlaces con tipos y anchors, usar build_enhanced_links_section().
    
    Args:
        internal_links: Lista de enlaces internos
        pdp_links: Lista de enlaces a PDPs
        
    Returns:
        Sección de enlaces formateada
    """
    internal_str = ""
    if internal_links:
        internal_str = "\n".join(f"- {link}" for link in internal_links)
    else:
        internal_str = "(Ninguno especificado)"
    
    pdp_str = ""
    if pdp_links:
        pdp_str = "\n".join(f"- {link}" for link in pdp_links)
    else:
        pdp_str = "(Ninguno especificado)"
    
    return LINKS_SECTION_TEMPLATE.render(
        internal_links=internal_str,
        pdp_links=pdp_str
    )


def build_enhanced_links_section(
    enhanced_links: Optional[List[Any]] = None
) -> str:
    """
    Construye la sección de enlaces mejorados con tipos y anchors.
    
    Args:
        enhanced_links: Lista de EnhancedLink o dicts con:
            - url: URL del enlace
            - anchor: Texto ancla
            - link_type: Tipo de enlace ('blog', 'category', 'pdp')
            
    Returns:
        Sección de enlaces formateada para el prompt
    """
    if not enhanced_links:
        return "(Sin enlaces especificados)"
    
    # Agrupar enlaces por tipo
    blog_links = []
    category_links = []
    pdp_links = []
    
    for link in enhanced_links:
        # Soportar tanto objetos como dicts
        if hasattr(link, 'link_type'):
            # Es un objeto EnhancedLink
            link_type = link.link_type.value if hasattr(link.link_type, 'value') else str(link.link_type)
            url = link.url
            anchor = link.anchor
        else:
            # Es un dict
            link_type = link.get('type', 'blog')
            url = link.get('url', '')
            anchor = link.get('anchor', '')
        
        link_item = ENHANCED_LINK_ITEM_TEMPLATE.render(
            anchor_text=anchor,
            url=url
        )
        
        if link_type == 'blog':
            blog_links.append(link_item)
        elif link_type == 'category':
            category_links.append(link_item)
        elif link_type == 'pdp':
            pdp_links.append(link_item)
        else:
            # Por defecto, añadir como blog
            blog_links.append(link_item)
    
    # Construir secciones
    blog_section = ""
    if blog_links:
        blog_section = BLOG_LINKS_GROUP_TEMPLATE.render(
            links_list="\n".join(blog_links)
        )
    
    category_section = ""
    if category_links:
        category_section = CATEGORY_LINKS_GROUP_TEMPLATE.render(
            links_list="\n".join(category_links)
        )
    
    pdp_section = ""
    if pdp_links:
        pdp_section = PDP_LINKS_GROUP_TEMPLATE.render(
            links_list="\n".join(pdp_links)
        )
    
    # Si no hay ningún enlace en ninguna categoría
    if not blog_section and not category_section and not pdp_section:
        return "(Sin enlaces especificados)"
    
    return ENHANCED_LINKS_SECTION_TEMPLATE.render(
        blog_links_section=blog_section or "(Sin enlaces de blog)",
        category_links_section=category_section or "(Sin enlaces de listados)",
        pdp_links_section=pdp_section or "(Sin enlaces de productos)"
    )


def format_enhanced_links_for_prompt(
    enhanced_links: Optional[List[Any]] = None,
    use_simple_format: bool = False
) -> str:
    """
    Formatea enlaces mejorados para incluir en prompts.
    
    Función de conveniencia que detecta el formato de entrada y
    genera el texto apropiado para el prompt.
    
    Args:
        enhanced_links: Lista de enlaces (EnhancedLink o dicts)
        use_simple_format: Si True, usa formato simple sin templates
        
    Returns:
        String formateado para el prompt
    """
    if not enhanced_links:
        return ""
    
    if use_simple_format:
        # Formato simple (más compacto)
        lines = ["ENLACES A INCLUIR:", ""]
        
        for link in enhanced_links:
            if hasattr(link, 'link_type'):
                link_type = link.link_type.value if hasattr(link.link_type, 'value') else str(link.link_type)
                url = link.url
                anchor = link.anchor
            else:
                link_type = link.get('type', 'blog')
                url = link.get('url', '')
                anchor = link.get('anchor', '')
            
            type_names = {
                'blog': 'Blog',
                'category': 'Listado',
                'pdp': 'Producto'
            }
            type_name = type_names.get(link_type, 'Enlace')
            
            lines.append(f"- [{anchor}]({url}) → Tipo: {type_name}")
        
        lines.append("")
        lines.append("Incluye TODOS estos enlaces de forma natural en el contenido.")
        
        return "\n".join(lines)
    
    # Formato completo con templates
    return build_enhanced_links_section(enhanced_links)


def build_competitor_section(
    competitors: List[Dict[str, Any]]
) -> str:
    """
    Construye la sección de análisis de competidores.
    
    Args:
        competitors: Lista de dicts con datos de competidores
        
    Returns:
        Sección de competidores formateada
    """
    if not competitors:
        return "(Sin datos de competidores)"
    
    sections = []
    
    for i, comp in enumerate(competitors, 1):
        section = COMPETITOR_TEMPLATE.render(
            index=str(i),
            competitor_url=comp.get('url', 'URL no disponible'),
            competitor_title=comp.get('title', 'Sin título'),
            word_count=str(comp.get('word_count', 0)),
            competitor_content=_truncate_content(comp.get('content', ''), 1500),
            strengths=comp.get('strengths', 'Por analizar')
        )
        sections.append(section)
    
    return "\n".join(sections)


def build_faqs_section(faqs: List[Dict[str, str]]) -> str:
    """
    Construye la sección de FAQs.
    
    Args:
        faqs: Lista de dicts con 'question' y 'answer'
        
    Returns:
        HTML de FAQs
    """
    if not faqs:
        return ""
    
    faq_items = []
    for faq in faqs:
        item = FAQ_ITEM_TEMPLATE.render(
            question=faq.get('question', ''),
            answer=faq.get('answer', '')
        )
        faq_items.append(item)
    
    return FAQS_TEMPLATE.render(faq_items="\n".join(faq_items))


def build_callout(
    title: str,
    content: str,
    callout_type: str = ""
) -> str:
    """
    Construye un callout/destacado.
    
    Args:
        title: Título del callout
        content: Contenido del callout
        callout_type: Tipo (accent, info, success, warning)
        
    Returns:
        HTML del callout
    """
    return CALLOUT_TEMPLATE.render(
        callout_title=title,
        callout_content=content,
        callout_type=callout_type
    )


# ============================================================================
# FUNCIONES HELPER PRIVADAS
# ============================================================================

def _get_default_brand_context() -> str:
    """Retorna contexto de marca por defecto."""
    return """
PcComponentes es la tienda líder de tecnología en España.
Tono de marca: Expertos sin ser pedantes, frikis sin vergüenza, cercanos pero profesionales.
Hablamos claro, no vendemos humo, nos ponemos en el lugar del usuario.
Usamos analogías tech cuando aportan valor, tuteamos al lector.
"""


def _get_default_html_structure() -> str:
    """Retorna estructura HTML por defecto."""
    return """
- Usar clases CSS: .kicker, .toc, .callout, .verdict-box, .faqs, .note
- Estructura semántica: article > h2 > sections con h3
- Incluir tabla de contenidos (.toc) al inicio
- Cerrar con veredicto/conclusión (.verdict-box)
"""


def _get_content_type_name(code: str) -> str:
    """Convierte código de arquetipo a nombre legible."""
    types = {
        'GC': 'Guía de Compra',
        'RV': 'Review/Análisis',
        'CP': 'Comparativa',
        'TU': 'Tutorial',
        'TP': 'Top/Ranking',
        'NW': 'Noticias',
    }
    return types.get(code.upper(), code)


def _get_structure_guide(content_type: str) -> str:
    """Retorna guía de estructura según tipo de contenido."""
    guides = {
        'GC': """
1. Introducción con promesa de valor
2. ¿Para quién es esta guía? (perfiles de usuario)
3. Criterios de selección clave
4. Selección de productos recomendados (3-5)
5. Comparativa rápida (tabla)
6. Consejos de compra
7. FAQs
8. Veredicto final
""",
        'RV': """
1. Introducción y primera impresión
2. Especificaciones técnicas clave
3. Diseño y construcción
4. Rendimiento en uso real
5. Puntos fuertes y débiles
6. ¿Para quién es ideal?
7. Alternativas a considerar
8. Veredicto y puntuación
""",
        'CP': """
1. Introducción: ¿Qué comparamos y por qué?
2. Tabla comparativa rápida
3. Análisis detallado de cada opción
4. Comparativa punto por punto
5. ¿Cuál elegir según tu caso?
6. FAQs
7. Conclusión: El ganador para cada perfil
""",
        'TU': """
1. Introducción y objetivo del tutorial
2. Lo que necesitas (requisitos/materiales)
3. Pasos detallados con capturas
4. Consejos y trucos
5. Problemas comunes y soluciones
6. FAQs
7. Conclusión y siguientes pasos
""",
        'TP': """
1. Introducción y criterios del ranking
2. El top 5/10 con breve descripción
3. Análisis detallado de cada posición
4. Tabla resumen
5. Menciones honoríficas
6. Cómo elegir el tuyo
7. Conclusión
"""
    }
    return guides.get(content_type.upper(), guides['GC'])


def _get_default_requirements(content_type: str) -> str:
    """Retorna requisitos por defecto según tipo."""
    return """
- Contenido original y de valor
- Optimizado para la keyword sin keyword stuffing
- Incluir datos actualizados y verificables
- Usar bullet points solo cuando aporten claridad
- Incluir CTAs naturales hacia productos
- Lenguaje claro y accesible
"""


def _get_default_improvements() -> str:
    """Retorna mejoras por defecto para reescritura."""
    return """
- Mejorar la densidad de keyword sin forzar
- Ampliar secciones con poco contenido
- Añadir más datos y especificaciones
- Mejorar estructura y legibilidad
- Actualizar información desactualizada
- Potenciar CTAs y conversión
"""


def _get_default_keep_elements() -> str:
    """Retorna elementos a mantener por defecto."""
    return """
- Estructura general si funciona
- Datos verificados y actuales
- Enlaces que funcionan
- Elementos diferenciadores
"""


def _get_default_rewrite_instructions() -> str:
    """Retorna instrucciones de reescritura por defecto."""
    return """
- No copies literalmente del contenido original
- Mejora el engagement en la introducción
- Asegura que cada sección aporte valor único
- Optimiza para featured snippets donde aplique
- Mantén el tono de marca PcComponentes
"""


def _truncate_content(content: str, max_length: int) -> str:
    """Trunca contenido si excede longitud máxima."""
    if not content:
        return ""
    
    if len(content) <= max_length:
        return content
    
    return content[:max_length] + "\n\n[... contenido truncado ...]"


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def escape_for_json(text: str) -> str:
    """
    Escapa texto para inclusión segura en JSON.
    
    Args:
        text: Texto a escapar
        
    Returns:
        Texto escapado
    """
    if not text:
        return ""
    
    # Usar json.dumps para escapar correctamente
    escaped = json.dumps(text)
    # Remover comillas externas
    return escaped[1:-1]


def format_list_for_prompt(items: List[str], prefix: str = "-") -> str:
    """
    Formatea una lista para incluir en prompt.
    
    Args:
        items: Lista de items
        prefix: Prefijo para cada item
        
    Returns:
        String formateado
    """
    if not items:
        return "(Ninguno)"
    
    return "\n".join(f"{prefix} {item}" for item in items)


def format_dict_for_prompt(data: Dict[str, Any], indent: int = 0) -> str:
    """
    Formatea un diccionario para incluir en prompt.
    
    Args:
        data: Diccionario a formatear
        indent: Nivel de indentación
        
    Returns:
        String formateado
    """
    if not data:
        return "(Ninguno)"
    
    lines = []
    prefix = "  " * indent
    
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(format_dict_for_prompt(value, indent + 1))
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                lines.append(f"{prefix}  - {item}")
        else:
            lines.append(f"{prefix}{key}: {value}")
    
    return "\n".join(lines)


def validate_template_variables(
    template: SafeTemplate,
    variables: Dict[str, Any]
) -> List[str]:
    """
    Valida que un dict contenga todas las variables del template.
    
    Args:
        template: Template a validar
        variables: Variables proporcionadas
        
    Returns:
        Lista de variables faltantes
    """
    return template.validate(**variables)


def render_template_safe(
    template: SafeTemplate,
    variables: Dict[str, Any],
    defaults: Optional[Dict[str, str]] = None
) -> str:
    """
    Renderiza template con valores por defecto para variables faltantes.
    
    Args:
        template: Template a renderizar
        variables: Variables proporcionadas
        defaults: Valores por defecto para variables faltantes
        
    Returns:
        String renderizado
    """
    defaults = defaults or {}
    
    # Combinar variables con defaults
    all_vars = {**defaults}
    all_vars.update(variables)
    
    return template.safe_render(**all_vars)


# ============================================================================
# REGISTRAR TEMPLATES EN EL REGISTRO GLOBAL
# ============================================================================

def _register_all_templates():
    """Registra todos los templates en el registro global."""
    templates = [
        ("system_prompt", SYSTEM_PROMPT_TEMPLATE._raw),
        ("content_generation", CONTENT_GENERATION_TEMPLATE._raw),
        ("rewrite", REWRITE_TEMPLATE._raw),
        ("analysis", ANALYSIS_TEMPLATE._raw),
        ("links_section", LINKS_SECTION_TEMPLATE._raw),
        ("enhanced_links_section", ENHANCED_LINKS_SECTION_TEMPLATE._raw),
        ("blog_links_group", BLOG_LINKS_GROUP_TEMPLATE._raw),
        ("category_links_group", CATEGORY_LINKS_GROUP_TEMPLATE._raw),
        ("pdp_links_group", PDP_LINKS_GROUP_TEMPLATE._raw),
        ("enhanced_link_item", ENHANCED_LINK_ITEM_TEMPLATE._raw),
        ("competitor", COMPETITOR_TEMPLATE._raw),
        ("faqs", FAQS_TEMPLATE._raw),
        ("faq_item", FAQ_ITEM_TEMPLATE._raw),
        ("callout", CALLOUT_TEMPLATE._raw),
    ]
    
    for name, template_str in templates:
        _registry.register(name, template_str)


# Registrar templates al importar el módulo
_register_all_templates()


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Excepciones
    'TemplateError',
    'MissingVariableError',
    'InvalidTemplateError',
    
    # Clases
    'SafeTemplate',
    'TemplateRegistry',
    
    # Registro global
    'get_registry',
    
    # Templates predefinidos
    'SYSTEM_PROMPT_TEMPLATE',
    'CONTENT_GENERATION_TEMPLATE',
    'REWRITE_TEMPLATE',
    'ANALYSIS_TEMPLATE',
    'LINKS_SECTION_TEMPLATE',
    'ENHANCED_LINKS_SECTION_TEMPLATE',
    'BLOG_LINKS_GROUP_TEMPLATE',
    'CATEGORY_LINKS_GROUP_TEMPLATE',
    'PDP_LINKS_GROUP_TEMPLATE',
    'ENHANCED_LINK_ITEM_TEMPLATE',
    'COMPETITOR_TEMPLATE',
    'FAQS_TEMPLATE',
    'FAQ_ITEM_TEMPLATE',
    'CALLOUT_TEMPLATE',
    
    # Funciones builder
    'build_system_prompt',
    'build_content_prompt',
    'build_rewrite_prompt',
    'build_analysis_prompt',
    'build_links_section',
    'build_enhanced_links_section',
    'format_enhanced_links_for_prompt',
    'build_competitor_section',
    'build_faqs_section',
    'build_callout',
    
    # Utilidades
    'escape_for_json',
    'format_list_for_prompt',
    'format_dict_for_prompt',
    'validate_template_variables',
    'render_template_safe',
]
