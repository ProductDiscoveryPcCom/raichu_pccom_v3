# -*- coding: utf-8 -*-
"""
Design System Manager - PcComponentes Content Generator
Versión 5.0

Centraliza toda la configuración visual del design system:
- Carga CSS desde archivos externos (no hardcodeado)
- Registro de componentes disponibles con sus variantes
- Opciones de look&feel para la UI
- Sanitización de inputs para seguridad
- Generación de CSS minificado para prompts

Autor: PcComponentes - Product Discovery & Content
"""

import logging
import os
import re
import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ============================================================================
# RUTAS Y CARGA DE ARCHIVOS
# ============================================================================

# Directorio base del proyecto
_BASE_DIR = Path(__file__).parent
_CSS_DIR = _BASE_DIR  # CSS files live alongside design_system.py in config/
_CONFIG_DIR = _BASE_DIR

# Archivos CSS fuente
CSS_FILES = {
    'base': _CONFIG_DIR / "cms_compatible.css",
    'cards_horizontal': _CSS_DIR / "cards_con_imagenes.css",
    'cards_vertical': _CSS_DIR / "cards_recomendacion.css",
}

# Cache de CSS cargados
_css_cache: Dict[str, str] = {}
_css_hash_cache: Dict[str, str] = {}
_sections_cache: Dict[str, List] = {}  # Cache de secciones parseadas


def _load_css_file(filepath: Path) -> str:
    """
    Carga un archivo CSS con validación.
    
    Args:
        filepath: Ruta al archivo CSS
        
    Returns:
        Contenido CSS o cadena vacía si no existe
        
    Raises:
        ValueError: Si el archivo contiene contenido sospechoso
    """
    key = str(filepath)
    
    if key in _css_cache:
        return _css_cache[key]
    
    if not filepath.exists():
        logger.debug(f"CSS file not found: {filepath}")
        return ""
    
    try:
        content = filepath.read_text(encoding='utf-8')
    except (OSError, UnicodeDecodeError):
        return ""
    
    # Sanitización de seguridad
    content = _sanitize_css(content)
    
    _css_cache[key] = content
    _css_hash_cache[key] = hashlib.md5(content.encode()).hexdigest()[:8]
    
    return content


def _sanitize_css(css: str) -> str:
    """
    Sanitiza CSS para prevenir inyección de código.
    
    Elimina:
    - @import (evita carga de recursos externos)
    - javascript: en URLs
    - expression() (IE legacy)
    - behavior: (IE legacy)
    - -moz-binding (Firefox legacy)
    - Comentarios con contenido sospechoso
    
    Args:
        css: Contenido CSS sin sanitizar
        
    Returns:
        CSS sanitizado
    """
    # Eliminar @import
    css = re.sub(r'@import\s+[^;]+;', '/* @import removed */', css)
    
    # Eliminar javascript: en url()
    css = re.sub(r'url\s*\(\s*["\']?\s*javascript:', 'url(/* blocked */', css, flags=re.IGNORECASE)
    
    # Eliminar expression()
    css = re.sub(r'expression\s*\(', '/* expression blocked */(', css, flags=re.IGNORECASE)
    
    # Eliminar behavior:
    css = re.sub(r'behavior\s*:', '/* behavior blocked */', css, flags=re.IGNORECASE)
    
    # Eliminar -moz-binding
    css = re.sub(r'-moz-binding\s*:', '/* binding blocked */', css, flags=re.IGNORECASE)
    
    return css


def reload_css_cache():
    """Fuerza recarga de todos los CSS desde disco."""
    _css_cache.clear()
    _css_hash_cache.clear()
    _sections_cache.clear()


# ============================================================================
# REGISTRO DE COMPONENTES
# ============================================================================

@dataclass
class ComponentVariant:
    """Variante de un componente CSS."""
    css_class: str
    label: str
    description: str = ""


@dataclass
class CSSComponent:
    """Componente del design system."""
    id: str
    name: str
    description: str
    css_file: str  # Key en CSS_FILES
    base_class: str
    variants: List[ComponentVariant] = field(default_factory=list)
    available_in_prompt: bool = True
    html_template: str = ""


# Registro completo de componentes disponibles en el CMS
COMPONENT_REGISTRY: Dict[str, CSSComponent] = {
    
    # ── Estructura principal ──
    'article_main': CSSComponent(
        id='article_main',
        name='Artículo Principal',
        description='Contenedor principal del contenido generado',
        css_file='base',
        base_class='contentGenerator__main',
        html_template='<article class="contentGenerator__main">...</article>',
    ),
    
    # ── Kicker ──
    'kicker': CSSComponent(
        id='kicker',
        name='Kicker',
        description='Etiqueta superior del artículo',
        css_file='base',
        base_class='kicker',
        html_template='<span class="kicker">TEXTO</span>',
    ),
    
    # ── Tabla de contenidos ──
    'toc': CSSComponent(
        id='toc',
        name='Tabla de Contenidos',
        description='Índice de navegación del artículo',
        css_file='base',
        base_class='toc',
        html_template='<nav class="toc"><p class="toc__title">Contenido</p><ol class="toc__list"><li><a href="#s1">Sección</a></li></ol></nav>',
    ),
    
    # ── Callouts ──
    'callout': CSSComponent(
        id='callout',
        name='Callout',
        description='Caja de texto destacado',
        css_file='base',
        base_class='callout',
        variants=[
            ComponentVariant('callout', 'Standard', 'Borde izquierdo azul con fondo gris'),
            ComponentVariant('callout accent', 'Accent', 'Borde izquierdo naranja'),
        ],
        html_template='<div class="callout"><p>Texto destacado</p></div>',
    ),
    
    # ── Callout BF / Promocional ──
    'callout_promo': CSSComponent(
        id='callout_promo',
        name='Callout Promocional',
        description='Caja promocional con fondo naranja degradado',
        css_file='base',
        base_class='callout-bf',
        html_template='<div class="callout-bf"><p>TÍTULO</p><p>Texto <a href="#">enlace</a></p></div>',
    ),
    
    # ── Tablas ──
    'table': CSSComponent(
        id='table',
        name='Tabla',
        description='Tabla de datos responsive',
        css_file='base',
        base_class='table',
        html_template='<table><thead><tr><th>Col1</th><th>Col2</th></tr></thead><tbody>...</tbody></table>',
    ),
    
    # ── Light Table System ──
    'light_table': CSSComponent(
        id='light_table',
        name='Light Table (CSS Grid)',
        description='Tabla basada en grid CSS, más flexible que <table>',
        css_file='base',
        base_class='lt',
        variants=[
            ComponentVariant('lt cols-2', '2 columnas', ''),
            ComponentVariant('lt cols-3', '3 columnas', ''),
            ComponentVariant('lt cols-7', '7 columnas', 'Responsive: 2 en móvil, 7 en desktop'),
            ComponentVariant('lt zebra', 'Filas alternas', 'Con fondo alterno en filas'),
        ],
        html_template='<div class="lt cols-3"><div class="r"><div class="c">Header</div>...</div><div class="r"><div class="c">Data</div>...</div></div>',
    ),
    
    # ── Grid Layout ──
    'grid': CSSComponent(
        id='grid',
        name='Grid Layout',
        description='Layout de columnas para organizar contenido',
        css_file='base',
        base_class='grid',
        variants=[
            ComponentVariant('grid cols-2', '2 columnas', ''),
            ComponentVariant('grid cols-3', '3 columnas', ''),
        ],
        html_template='<div class="grid cols-2"><div class="card">...</div><div class="card">...</div></div>',
    ),
    
    # ── Cards ──
    'card': CSSComponent(
        id='card',
        name='Card',
        description='Tarjeta de contenido básica',
        css_file='base',
        base_class='card',
        html_template='<div class="card"><h4>Título</h4><p>Contenido</p></div>',
    ),
    
    # ── Verdict Box ──
    'verdict': CSSComponent(
        id='verdict',
        name='Veredicto',
        description='Caja de veredicto/conclusión final',
        css_file='base',
        base_class='verdict-box',
        html_template='<article class="contentGenerator__verdict"><div class="verdict-box"><h2>Veredicto</h2><p>Conclusión</p></div></article>',
    ),
    
    # ── FAQs ──
    'faqs': CSSComponent(
        id='faqs',
        name='FAQs',
        description='Sección de preguntas frecuentes',
        css_file='base',
        base_class='faqs',
        html_template='<article class="contentGenerator__faqs"><h2>Preguntas frecuentes</h2><div class="faqs"><div class="faqs__item"><h3 class="faqs__question">¿Pregunta?</h3><p class="faqs__answer">Respuesta</p></div></div></article>',
    ),
    
    # ── Badges ──
    'badges': CSSComponent(
        id='badges',
        name='Badges',
        description='Etiquetas inline para categorías o tags',
        css_file='base',
        base_class='badges',
        html_template='<div class="badges"><span class="badge">Tag 1</span><span class="badge">Tag 2</span></div>',
    ),
    
    # ── Botones CTA ──
    'buttons': CSSComponent(
        id='buttons',
        name='Botones',
        description='Botones de acción (CTA)',
        css_file='base',
        base_class='btn',
        variants=[
            ComponentVariant('btn primary', 'Primary', 'Botón naranja principal'),
            ComponentVariant('btn ghost', 'Ghost', 'Botón con borde sin fondo'),
        ],
        html_template='<div class="btns"><a href="#" class="btn primary">Ver producto</a></div>',
    ),
    
    # ── Cards Horizontales (CMS Module) ──
    'mod_cards': CSSComponent(
        id='mod_cards',
        name='Cards Horizontales (Módulo CMS)',
        description='Sistema de cards con imagen, ideal para comparativas de productos',
        css_file='cards_horizontal',
        base_class='mod-section',
        variants=[
            ComponentVariant('mod-section', 'Standard', 'Fondo gris con borde'),
            ComponentVariant('mod-section mod-section--white', 'Fondo blanco', ''),
            ComponentVariant('mod-section mod-section--transparent', 'Sin fondo', ''),
            ComponentVariant('mod-section mod-section--dark', 'Fondo oscuro', 'Texto blanco'),
            ComponentVariant('mod-section mod-section--compact', 'Compacto', 'Padding reducido'),
        ],
        html_template='''<div class="mod-section">
  <h3 class="mod-section__title">Título</h3>
  <p class="mod-section__intro">Introducción</p>
  <div class="mod-grid">
    <article class="mod-card mod-card--horizontal">
      <div class="mod-card__top">
        <div class="mod-card__content">
          <span class="mod-chip">Etiqueta</span>
          <h4 class="mod-card__title">Producto</h4>
          <ul class="mod-card__list">
            <li><strong>Spec:</strong> Valor</li>
          </ul>
        </div>
        <figure class="mod-figure">
          <img class="mod-figure__img" src="..." alt="...">
          <figcaption class="mod-figure__caption"><strong>Desde 999€</strong></figcaption>
        </figure>
      </div>
      <div class="mod-card__bottom">
        <p class="mod-card__benefit">✓ Beneficio clave</p>
        <a href="#" class="mod-cta">Ver producto</a>
      </div>
    </article>
  </div>
</div>''',
    ),
    
    # ── Cards Verticales (CMS Module) ──
    'vcard_cards': CSSComponent(
        id='vcard_cards',
        name='Cards Verticales (Módulo CMS)',
        description='Cards verticales para recomendaciones y listados',
        css_file='cards_vertical',
        base_class='vcard-module',
        variants=[
            ComponentVariant('vcard-module', 'Standard', 'Fondo gris'),
            ComponentVariant('vcard-module vcard-module--white', 'Fondo blanco', ''),
            ComponentVariant('vcard-module vcard-module--transparent', 'Sin fondo', ''),
            ComponentVariant('vcard-module vcard-module--bordered', 'Con borde', ''),
        ],
        html_template='''<div class="vcard-module">
  <h3 class="vcard-module__title">Título</h3>
  <div class="vcard-grid">
    <article class="vcard vcard--hoverable">
      <span class="vcard__chip vcard__chip--primary">Etiqueta</span>
      <h4 class="vcard__title">Producto</h4>
      <ul class="vcard__list">
        <li><strong>Feature</strong> detalle</li>
      </ul>
      <hr class="vcard__divider">
      <p class="vcard__benefit">Beneficio clave</p>
      <a href="#" class="vcard__cta">Ver opciones</a>
    </article>
  </div>
</div>''',
    ),
    
    # ── Tabla de comparación ──
    'comparison_table': CSSComponent(
        id='comparison_table',
        name='Tabla de Comparación',
        description='Tabla comparativa de productos con columna destacada',
        css_file='base',
        base_class='comparison-table',
        html_template='''<table class="comparison-table">
  <thead><tr><th>Característica</th><th>Producto A</th><th class="comparison-highlight">Producto B</th></tr></thead>
  <tbody><tr><td><strong>Spec</strong></td><td>Valor</td><td class="comparison-highlight">Valor</td></tr></tbody>
</table>''',
    ),
}


# ── Sub-componentes de los módulos CMS ──

MOD_CHIP_VARIANTS = [
    ComponentVariant('mod-chip', 'Default', 'Naranja claro'),
    ComponentVariant('mod-chip mod-chip--primary', 'Primary', 'Naranja sólido, texto blanco'),
    ComponentVariant('mod-chip mod-chip--dark', 'Dark', 'Oscuro, texto blanco'),
    ComponentVariant('mod-chip mod-chip--outline', 'Outline', 'Sin fondo, con borde'),
]

MOD_CTA_VARIANTS = [
    ComponentVariant('mod-cta', 'Primary', 'Botón naranja'),
    ComponentVariant('mod-cta mod-cta--outline', 'Outline', 'Borde naranja, sin fondo'),
    ComponentVariant('mod-cta mod-cta--dark', 'Dark', 'Botón oscuro'),
    ComponentVariant('mod-cta mod-cta--ghost', 'Ghost', 'Sin fondo ni borde'),
]

MOD_CARD_VARIANTS = [
    ComponentVariant('mod-card', 'Standard', 'Card básica'),
    ComponentVariant('mod-card mod-card--horizontal', 'Horizontal', 'Con imagen a la derecha'),
    ComponentVariant('mod-card mod-card--compact', 'Compact', 'Padding reducido'),
    ComponentVariant('mod-card mod-card--featured', 'Featured', 'Borde naranja destacado'),
    ComponentVariant('mod-card mod-card--elevated', 'Elevated', 'Sombra más pronunciada'),
    ComponentVariant('mod-card mod-card--clickable', 'Clickable', 'Con hover effect'),
]

MOD_GRID_VARIANTS = [
    ComponentVariant('mod-grid', '2 columnas', 'Default responsive'),
    ComponentVariant('mod-grid mod-grid--3cols', '3 columnas', 'Desktop grande'),
    ComponentVariant('mod-grid mod-grid--4cols', '4 columnas', 'Desktop XL'),
    ComponentVariant('mod-grid mod-grid--1col', '1 columna', 'Lista vertical'),
]

MOD_FIGURE_VARIANTS = [
    ComponentVariant('mod-figure', 'Standard', 'Imagen libre'),
    ComponentVariant('mod-figure mod-figure--ratio', 'Ratio fijo', '343x200'),
    ComponentVariant('mod-figure mod-figure--16x9', '16:9', 'Panorámico'),
    ComponentVariant('mod-figure mod-figure--4x3', '4:3', 'Clásico'),
    ComponentVariant('mod-figure mod-figure--1x1', '1:1', 'Cuadrado'),
]

VCARD_CHIP_VARIANTS = [
    ComponentVariant('vcard__chip', 'Default', 'Naranja claro'),
    ComponentVariant('vcard__chip vcard__chip--primary', 'Primary', 'Naranja sólido'),
    ComponentVariant('vcard__chip vcard__chip--dark', 'Dark', 'Fondo oscuro'),
    ComponentVariant('vcard__chip vcard__chip--success', 'Success', 'Verde'),
    ComponentVariant('vcard__chip vcard__chip--warning', 'Warning', 'Naranja'),
    ComponentVariant('vcard__chip vcard__chip--info', 'Info', 'Azul'),
    ComponentVariant('vcard__chip vcard__chip--outline', 'Outline', 'Con borde'),
]

VCARD_CTA_VARIANTS = [
    ComponentVariant('vcard__cta', 'Primary', 'Naranja sólido'),
    ComponentVariant('vcard__cta vcard__cta--ghost', 'Ghost', 'Sin fondo'),
    ComponentVariant('vcard__cta vcard__cta--secondary', 'Secondary', 'Borde gris'),
    ComponentVariant('vcard__cta vcard__cta--dark', 'Dark', 'Fondo oscuro'),
    ComponentVariant('vcard__cta vcard__cta--block', 'Full Width', 'Ancho completo'),
]

VCARD_VARIANTS = [
    ComponentVariant('vcard', 'Standard', 'Card básica'),
    ComponentVariant('vcard vcard--hoverable', 'Hoverable', 'Con efecto hover'),
    ComponentVariant('vcard vcard--featured', 'Featured', 'Borde naranja'),
    ComponentVariant('vcard vcard--compact', 'Compact', 'Padding reducido'),
    ComponentVariant('vcard vcard--flat', 'Flat', 'Sin sombra'),
    ComponentVariant('vcard vcard--centered', 'Centered', 'Texto centrado'),
]

VCARD_LIST_VARIANTS = [
    ComponentVariant('vcard__list', 'Standard', 'Sin bullets'),
    ComponentVariant('vcard__list vcard__list--bullets', 'Bullets', 'Con bullets'),
    ComponentVariant('vcard__list vcard__list--checks', 'Checks', 'Con ✓ naranja'),
]

VCARD_GRID_VARIANTS = [
    ComponentVariant('vcard-grid', '3 columnas', 'Default responsive'),
    ComponentVariant('vcard-grid vcard-grid--2cols', '2 columnas', ''),
    ComponentVariant('vcard-grid vcard-grid--3cols', '3 columnas', 'Forzado'),
    ComponentVariant('vcard-grid vcard-grid--4cols', '4 columnas', 'Desktop'),
]


# ============================================================================
# GENERACIÓN DE CSS PARA PROMPTS
# ============================================================================

def get_base_css() -> str:
    """Retorna el CSS base (cms_compatible.css) para inyectar en artículos."""
    return _load_css_file(CSS_FILES['base'])


def get_component_css(component_id: str) -> str:
    """Retorna el CSS de un componente específico."""
    component = COMPONENT_REGISTRY.get(component_id)
    if not component:
        return ""
    return _load_css_file(CSS_FILES.get(component.css_file, ''))


# ============================================================================
# TREE-SHAKING: Solo incluir CSS de componentes seleccionados
# ============================================================================

# Mapeo: nombre de sección en cms_compatible.css → component IDs que la necesitan.
# '_core' = siempre se incluye (variables, reset, tipografía)
_BASE_CSS_SECTION_MAP = {
    'VARIABLES CSS':       '_core',
    'RESET Y BASE':        '_core',
    'TIPOGRAFÍA':          '_core',
    'Kicker':              'kicker',
    'Badges':              'badges',
    'Callouts':            'callout,callout_promo',
    'Botones':             'buttons',
    'Tabla de Contenidos': 'toc',
    'Utilidades':          '_core',
    'Grid System':         'grid',
    'Cards':               'card,grid',
    'Separadores':         '_core',
    'Tablas HTML':         'table',
    'Tablas (Light Table': 'table,light_table',
    'FAQs':                'faqs',
    'Verdict Box':         'verdict',
    'Tabla de Comparación': 'comparison_table',
    'FIN DEL CSS':         '_skip',
}


def _parse_css_sections(css_content: str) -> List[dict]:
    """
    Parsea un CSS con secciones delimitadas por comentarios tipo:
      /* ====... NOMBRE_SECCION ====... */
    
    Returns:
        Lista de dicts {name, content, component_ids}
    """
    # Patrón: /* ==={3,} ... TEXT ... ==={3,} */
    pattern = re.compile(
        r'/\*\s*={10,}\s*\n\s*(.*?)\n\s*={10,}\s*\*/',
        re.DOTALL
    )
    
    markers = list(pattern.finditer(css_content))
    if not markers:
        # Sin secciones → devolver todo como una sola sección core
        return [{'name': '_all', 'content': css_content, 'component_ids': {'_core'}}]
    
    sections = []
    for i, m in enumerate(markers):
        section_name = m.group(1).strip()
        content_start = m.end()
        content_end = markers[i + 1].start() if i + 1 < len(markers) else len(css_content)
        content = css_content[content_start:content_end].strip()
        
        # Mapear a component IDs
        component_ids = set()
        for key, ids in _BASE_CSS_SECTION_MAP.items():
            if key in section_name:
                if ids == '_skip':
                    component_ids = {'_skip'}
                elif ids == '_core':
                    component_ids = {'_core'}
                else:
                    component_ids = set(ids.split(','))
                break
        
        # Si no mapeada, incluir como core (safe default)
        if not component_ids:
            component_ids = {'_core'}
        
        if content and '_skip' not in component_ids:
            sections.append({
                'name': section_name,
                'content': content,
                'component_ids': component_ids,
            })
    
    return sections


def _get_base_sections() -> List[dict]:
    """Parsea y cachea las secciones del CSS base."""
    if 'base' not in _sections_cache:
        css = _load_css_file(CSS_FILES['base'])
        _sections_cache['base'] = _parse_css_sections(css)
    return _sections_cache['base']


def _tree_shake_base_css(selected_components: List[str]) -> str:
    """
    Extrae solo las secciones CSS del base que necesitan los componentes
    seleccionados.
    
    Siempre incluye secciones '_core' (variables, reset, tipografía).
    
    Args:
        selected_components: IDs de componentes seleccionados
        
    Returns:
        CSS filtrado con solo las secciones necesarias
    """
    sections = _get_base_sections()
    selected_set = set(selected_components)
    
    # Componentes siempre presentes en artículos
    always_include = {'article_main', 'kicker'}
    selected_set.update(always_include)
    
    parts = []
    for section in sections:
        # Incluir si es core O si algún component_id del usuario coincide
        if '_core' in section['component_ids']:
            parts.append(section['content'])
        elif section['component_ids'] & selected_set:
            parts.append(section['content'])
    
    return '\n'.join(parts)


def get_css_for_prompt(
    selected_components: Optional[List[str]] = None,
    minify: bool = True,
) -> str:
    """
    Genera el bloque CSS para inyectar en el prompt con tree-shaking.
    
    Solo incluye:
    - Secciones del CSS base que coincidan con los componentes seleccionados
    - Archivos CSS externos completos (cards_horizontal, cards_vertical)
      solo si se seleccionó el módulo CMS correspondiente
    
    Args:
        selected_components: IDs de componentes a incluir. Si None, solo core.
        minify: Si True, minifica el CSS resultado
        
    Returns:
        CSS optimizado listo para <style>
    """
    components = selected_components or []
    
    # 1. Tree-shake del CSS base
    base_css = _tree_shake_base_css(components)
    css_parts = [base_css]
    
    # 2. Archivos CSS externos: solo si su módulo está seleccionado
    # Mapeo directo: component_id → css_file key
    _EXTERNAL_CSS_MAP = {
        'mod_cards': 'cards_horizontal',
        'vcard_cards': 'cards_vertical',
    }
    
    seen_files = set()
    for comp_id in components:
        css_key = _EXTERNAL_CSS_MAP.get(comp_id)
        if css_key and css_key not in seen_files:
            css = _load_css_file(CSS_FILES.get(css_key, ''))
            if css:
                css_parts.append(css)
                seen_files.add(css_key)
    
    combined = '\n'.join(css_parts)
    
    if minify:
        combined = _minify_css(combined)
    
    return combined


def _minify_css(css: str) -> str:
    """
    Minifica CSS básico (sin dependencias externas).
    
    Elimina comentarios, espacios innecesarios, saltos de línea.
    """
    # Eliminar comentarios
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
    # Eliminar saltos de línea y espacios múltiples
    css = re.sub(r'\s+', ' ', css)
    # Eliminar espacios antes/después de { } : ; ,
    css = re.sub(r'\s*([{};:,])\s*', r'\1', css)
    # Eliminar último ; antes de }
    css = css.replace(';}', '}')
    return css.strip()


# ============================================================================
# API PARA LA UI (STREAMLIT)
# ============================================================================

def get_available_components() -> List[Dict[str, Any]]:
    """
    Retorna la lista de componentes disponibles para la UI.
    
    Returns:
        Lista de dicts con id, name, description, variants
    """
    components = []
    for comp_id, comp in COMPONENT_REGISTRY.items():
        if comp.available_in_prompt:
            components.append({
                'id': comp.id,
                'name': comp.name,
                'description': comp.description,
                'variants': [
                    {'class': v.css_class, 'label': v.label, 'description': v.description}
                    for v in comp.variants
                ],
                'has_variants': len(comp.variants) > 0,
                'html_template': comp.html_template,
            })
    return components


def get_component_instructions(
    selected_components: Optional[List[str]] = None,
    selected_variants: Optional[Dict[str, str]] = None,
) -> str:
    """
    Genera instrucciones para el prompt sobre qué componentes usar.
    
    Args:
        selected_components: IDs de componentes seleccionados
        selected_variants: Dict {component_id: variant_class} 
        
    Returns:
        Instrucciones formateadas para el prompt
    """
    if not selected_components:
        return ""
    
    lines = ["\n## 🎨 COMPONENTES VISUALES DISPONIBLES"]
    lines.append("Usa estos componentes del design system de PcComponentes:\n")
    
    for comp_id in selected_components:
        comp = COMPONENT_REGISTRY.get(comp_id)
        if not comp:
            continue
        
        lines.append(f"### {comp.name}")
        lines.append(f"{comp.description}")
        
        # Variante seleccionada
        if selected_variants and comp_id in selected_variants:
            selected = selected_variants[comp_id]
            lines.append(f"**Usar clase:** `{selected}`")
        
        # Template HTML
        if comp.html_template:
            lines.append(f"\n**Ejemplo HTML:**\n```html\n{comp.html_template}\n```")
        
        # Variantes disponibles
        if comp.variants:
            lines.append("\n**Variantes disponibles:**")
            for v in comp.variants:
                desc = f" — {v.description}" if v.description else ""
                lines.append(f"  - `.{v.css_class}`: {v.label}{desc}")
        
        lines.append("")
    
    return "\n".join(lines)


def get_css_variables() -> Dict[str, Dict[str, str]]:
    """
    Retorna las variables CSS del design system organizadas por categoría.
    Útil para mostrar en la UI como referencia.
    """
    return {
        'colores_marca': {
            '--color-brand-dark': '#cc4d00',
            '--color-brand-main': '#ff6000',
            '--color-brand-light': '#ffa066',
            '--color-brand-lighter': '#ffd8c1',
            '--color-brand-ultra-lighter': '#ffeade',
        },
        'colores_marca_azul': {
            '--color-brand-blue-dark': '#090029',
            '--color-brand-blue-main': '#170453',
            '--color-brand-blue-light': '#51437e',
            '--color-brand-blue-lighter': '#c5c0d4',
        },
        'colores_estado': {
            '--color-success-main': '#118000',
            '--color-warning-main': '#ffa90d',
            '--color-danger-main': '#bf0019',
            '--color-secondary-main': '#0069a7',
        },
        'colores_neutros': {
            '--color-black': '#333',
            '--color-environment-percent40': '#6e6e6e',
            '--color-environment-percent20': '#ccc',
            '--color-environment-percent05': '#f2f2f2',
            '--color-white': '#fff',
        },
        'tipografia': {
            '--font-family-global': "'Open Sans', sans-serif",
            '--font-h2-size': '1.5rem',
            '--font-h3-size': '1.25rem',
            '--font-body1-size': '1.0625rem',
            '--font-body2-size': '0.875rem',
        },
    }


# ============================================================================
# VALIDACIÓN DE COMPONENTES
# ============================================================================

def validate_component_selection(component_ids: List[str]) -> Tuple[List[str], List[str]]:
    """
    Valida una selección de componentes.
    
    Args:
        component_ids: Lista de IDs a validar
        
    Returns:
        Tuple (valid_ids, invalid_ids)
    """
    valid = []
    invalid = []
    for cid in component_ids:
        if cid in COMPONENT_REGISTRY:
            valid.append(cid)
        else:
            invalid.append(cid)
    return valid, invalid


def validate_css_class(css_class: str) -> bool:
    """
    Valida que una clase CSS solo contiene caracteres seguros.
    
    Previene inyección de código vía nombres de clase.
    """
    return bool(re.match(r'^[a-zA-Z0-9_\-\s]+$', css_class))


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    'COMPONENT_REGISTRY',
    'CSS_FILES',
    'CSSComponent',
    'ComponentVariant',
    # Sub-componentes
    'MOD_CHIP_VARIANTS',
    'MOD_CTA_VARIANTS',
    'MOD_CARD_VARIANTS',
    'MOD_GRID_VARIANTS',
    'MOD_FIGURE_VARIANTS',
    'VCARD_CHIP_VARIANTS',
    'VCARD_CTA_VARIANTS',
    'VCARD_VARIANTS',
    'VCARD_LIST_VARIANTS',
    'VCARD_GRID_VARIANTS',
    # Functions
    'get_base_css',
    'get_component_css',
    'get_css_for_prompt',
    'get_available_components',
    'get_component_instructions',
    'get_css_variables',
    'validate_component_selection',
    'validate_css_class',
    'reload_css_cache',
]
