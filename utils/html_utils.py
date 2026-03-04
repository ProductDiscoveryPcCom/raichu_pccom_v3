"""
Utilidades HTML - PcComponentes Content Generator
Versión 1.2.0

CAMBIOS v1.2.0:
- Añadida extract_html_content(): limpia marcadores markdown de respuestas de Claude
- Ahora html_utils es autosuficiente: no depende de core.generator para extracción HTML

Autor: PcComponentes - Product Discovery & Content
"""

import re
from typing import Dict, List, Tuple, Optional, Any
from html.parser import HTMLParser as BaseHTMLParser
from dataclasses import dataclass, field

__version__ = "1.2.0"

# ============================================================================
# VERIFICAR BEAUTIFULSOUP
# ============================================================================

try:
    from bs4 import BeautifulSoup
    _bs4_available = True
except ImportError:
    _bs4_available = False

def is_bs4_available() -> bool:
    """Verifica si BeautifulSoup está disponible."""
    return _bs4_available

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ExtractedContent:
    """Contenido extraído de HTML."""
    text: str = ""
    title: str = ""
    headings: List[Dict[str, str]] = field(default_factory=list)
    links: List[Dict[str, str]] = field(default_factory=list)
    word_count: int = 0
    meta: Dict[str, str] = field(default_factory=dict)

# ============================================================================
# HTML PARSER CLASS
# ============================================================================

class HTMLParser(BaseHTMLParser):
    """Parser HTML personalizado para extracción de contenido."""
    
    def __init__(self):
        super().__init__()
        self.text_content = []
        self.current_tag = None
        self.headings = []
        self.links = []
        self.in_script = False
        self.in_style = False
    
    def handle_starttag(self, tag: str, attrs: list):
        self.current_tag = tag
        if tag == 'script':
            self.in_script = True
        elif tag == 'style':
            self.in_style = True
        elif tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.headings.append({'level': tag, 'text': ''})
        elif tag == 'a':
            href = dict(attrs).get('href', '')
            if href:
                self.links.append({'href': href, 'text': ''})
    
    def handle_endtag(self, tag: str):
        if tag == 'script':
            self.in_script = False
        elif tag == 'style':
            self.in_style = False
        self.current_tag = None
    
    def handle_data(self, data: str):
        if self.in_script or self.in_style:
            return
        text = data.strip()
        if text:
            self.text_content.append(text)
            if self.headings and self.current_tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                self.headings[-1]['text'] += text
            if self.links and self.current_tag == 'a':
                self.links[-1]['text'] += text
    
    def get_text(self) -> str:
        return ' '.join(self.text_content)
    
    def get_headings(self) -> List[Dict]:
        return self.headings
    
    def get_links(self) -> List[Dict]:
        return self.links

# ============================================================================
# FUNCIONES DE PARSER
# ============================================================================

def get_html_parser() -> HTMLParser:
    """Retorna una nueva instancia del HTMLParser."""
    return HTMLParser()

def get_parser():
    """Retorna el parser de BeautifulSoup o 'html.parser'."""
    return 'html.parser'

def get_bs4_parser():
    """Alias para get_parser."""
    return get_parser()

# ============================================================================
# FUNCIONES DE CONTEO
# ============================================================================

def count_words_in_html(html_content: str) -> int:
    """Cuenta palabras en HTML excluyendo tags."""
    if not html_content:
        return 0
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    text = re.sub(r'&#\d+;', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return len(text.split()) if text else 0

def get_word_count(html_content: str) -> int:
    """Alias para count_words_in_html."""
    return count_words_in_html(html_content)

def strip_html_tags(html_content: str) -> str:
    """Elimina tags HTML dejando solo texto."""
    if not html_content:
        return ""
    text = re.sub(r'<[^>]+>', ' ', html_content)
    return re.sub(r'\s+', ' ', text).strip()

def strip_tags(html_content: str) -> str:
    """Alias para strip_html_tags."""
    return strip_html_tags(html_content)

# ============================================================================
# FUNCIONES DE EXTRACCIÓN
# ============================================================================

def extract_content_structure(html_content: str) -> Dict:
    """Extrae estructura del contenido HTML."""
    if not html_content:
        return {'word_count': 0, 'structure_valid': False}
    
    try:
        title_match = re.search(r'<h[12][^>]*>(.*?)</h[12]>', html_content, re.I | re.DOTALL)
        title = strip_html_tags(title_match.group(1)) if title_match else None
        
        headings = []
        for level, text in re.findall(r'<(h[1-6])[^>]*>(.*?)</\1>', html_content, re.I | re.DOTALL):
            headings.append({'level': level.lower(), 'text': strip_html_tags(text)})
        
        html_lower = html_content.lower()
        links = re.findall(r'href=["\']([^"\']+)["\']', html_content, re.I)
        
        return {
            'title': title,
            'headings': headings,
            'word_count': count_words_in_html(html_content),
            'has_table': '<table' in html_lower,
            'has_callout': 'callout' in html_lower,
            'has_faq': 'faq' in html_lower,
            'has_verdict': 'verdict' in html_lower,
            'internal_links_count': len([l for l in links if 'pccomponentes.com' in l]),
            'external_links_count': len([l for l in links if l.startswith('http') and 'pccomponentes.com' not in l]),
            'structure_valid': True
        }
    except Exception as e:
        return {'error': str(e), 'structure_valid': False}

def extract_content(html_content: str) -> ExtractedContent:
    """Extrae contenido estructurado de HTML."""
    result = ExtractedContent()
    
    if not html_content:
        return result
    
    result.text = strip_html_tags(html_content)
    result.word_count = count_words_in_html(html_content)
    
    # Título
    title_match = re.search(r'<title[^>]*>(.*?)</title>', html_content, re.I | re.DOTALL)
    result.title = strip_html_tags(title_match.group(1)) if title_match else ""
    
    # Headings
    for level, text in re.findall(r'<(h[1-6])[^>]*>(.*?)</\1>', html_content, re.I | re.DOTALL):
        result.headings.append({'level': level.lower(), 'text': strip_html_tags(text)})
    
    # Links
    for match in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_content, re.I | re.DOTALL):
        result.links.append({'href': match[0], 'text': strip_html_tags(match[1])})
    
    return result

def extract_text(html_content: str) -> str:
    """Extrae solo el texto de HTML."""
    return strip_html_tags(html_content)

def extract_meta_tags(html_content: str) -> Dict[str, str]:
    """Extrae meta tags de HTML."""
    meta = {}
    if not html_content:
        return meta
    
    for match in re.findall(r'<meta[^>]+>', html_content, re.I):
        name_match = re.search(r'name=["\']([^"\']+)["\']', match, re.I)
        property_match = re.search(r'property=["\']([^"\']+)["\']', match, re.I)
        content_match = re.search(r'content=["\']([^"\']+)["\']', match, re.I)
        
        key = (name_match or property_match)
        if key and content_match:
            meta[key.group(1)] = content_match.group(1)
    
    return meta

# ============================================================================
# FUNCIONES DE LIMPIEZA
# ============================================================================

def sanitize_html(html_content: str) -> str:
    """Sanitiza HTML eliminando scripts y styles."""
    if not html_content:
        return ""
    
    html = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.I)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.I)
    html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
    
    return html.strip()

def clean_html(html_content: str) -> str:
    """Alias para sanitize_html."""
    return sanitize_html(html_content)


def extract_html_content(content: str) -> str:
    """
    Extrae HTML limpio de una respuesta de Claude.
    
    Elimina marcadores markdown (```html, ```, etc.) y texto espurio
    antes/después del HTML. Útil para procesar la salida directa de la API
    que puede venir envuelta en bloques de código markdown.
    
    Args:
        content: Texto que puede contener HTML envuelto en markdown
        
    Returns:
        HTML limpio sin marcadores markdown
    """
    if not content:
        return ""
    
    # Paso 1: Limpiar espacios
    content = content.strip()
    
    # Paso 2: Eliminar marcadores markdown al inicio
    markdown_start_patterns = [
        r'^```html\s*\n?',
        r'^```HTML\s*\n?',
        r'^```xml\s*\n?',
        r'^```\s*\n?',
    ]
    for pattern in markdown_start_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # Paso 3: Eliminar marcadores markdown al final
    markdown_end_patterns = [
        r'\n?```\s*$',
        r'\n?```html\s*$',
    ]
    for pattern in markdown_end_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # Paso 4: Limpiar espacios de nuevo
    content = content.strip()
    
    # Paso 5: Si todavía hay marcadores en medio, extraer el contenido
    html_match = re.search(r'```(?:html)?\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
    if html_match:
        content = html_match.group(1).strip()
    
    # Paso 6: Si no empieza con <, buscar el primer tag HTML
    if not content.startswith('<'):
        first_tag = content.find('<')
        if first_tag > 0:
            content = content[first_tag:]
    
    # Paso 7: Si no termina con >, recortar hasta el último tag
    if content and not content.rstrip().endswith('>'):
        last_tag = content.rfind('>')
        if last_tag > 0:
            content = content[:last_tag + 1]
    
    return content.strip()

# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validate_html_structure(html_content: str) -> Dict[str, bool]:
    """
    Valida estructura HTML básica y detecta elementos clave.
    
    Returns:
        Dict con flags de validación:
        - has_article: Tiene al menos un <article>
        - kicker_uses_span: Kicker usa <span> correctamente
        - css_has_root: Tiene bloque <style> con :root
        - has_bf_callout: Tiene callout de Black Friday
        - no_markdown: No tiene marcadores markdown residuales
        - has_table: Tiene tablas
        - has_callout: Tiene callouts normales
        - has_verdict_box: Tiene verdict-box
        - has_toc: Tiene tabla de contenidos
        - has_grid: Tiene grid layout
    """
    if not html_content:
        return {
            'has_article': False,
            'kicker_uses_span': False,
            'css_has_root': False,
            'has_bf_callout': False,
            'no_markdown': True,
            'has_table': False,
            'has_callout': False,
            'has_verdict_box': False,
            'has_toc': False,
            'has_grid': False,
        }
    
    html_lower = html_content.lower()
    
    # Detectar marcadores markdown (```html, ```, etc.)
    has_markdown = any(md in html_content for md in ['```html', '```', '~~~'])
    
    # Detectar kicker correctamente (con span, no div)
    has_span_kicker = ('class="kicker"' in html_lower or "class='kicker'" in html_lower) and '<span' in html_lower
    
    # Detectar callouts (varios formatos posibles)
    has_bf_callout = any(x in html_lower for x in ['callout-bf', 'callout_bf', 'bf-callout', 'black-friday', 'cyber-monday'])
    has_callout = 'class="callout"' in html_lower or "class='callout'" in html_lower
    
    # Detectar verdict-box (varios formatos)
    has_verdict = any(x in html_lower for x in ['verdict-box', 'verdict_box', 'verdictbox', 'veredicto'])
    
    # Detectar TOC
    has_toc = any(x in html_lower for x in ['class="toc"', "class='toc'", 'nav class="toc', 'class="toc ', 'class="toc__'])
    
    # Detectar Grid (various class patterns used in prompts and CSS)
    has_grid = any(x in html_lower for x in [
        'grid-layout', 'grid_layout', 'display: grid', 'display:grid',
        'class="grid', "class='grid", 'class="mod-grid', 'class="vcard-grid',
        'cols-2', 'cols-3', 'cols-4',
    ])
    
    # Detectar tablas
    has_table = '<table' in html_lower and '</table>' in html_lower
    
    return {
        'has_article': '<article' in html_lower,
        'kicker_uses_span': has_span_kicker,
        'css_has_root': ':root' in html_content and '<style' in html_lower,
        'has_bf_callout': has_bf_callout,
        'no_markdown': not has_markdown,
        'has_table': has_table,
        'has_callout': has_callout or has_bf_callout,
        'has_verdict_box': has_verdict,
        'has_toc': has_toc,
        'has_grid': has_grid,
    }

def validate_cms_structure(html_content: str) -> Tuple[bool, List[str], List[str]]:
    """Valida que el HTML cumpla con requisitos del CMS."""
    errors = []
    warnings = []
    
    if not html_content:
        return False, ["❌ El contenido HTML está vacío"], []
    
    html_lower = html_content.lower()
    
    article_count = html_lower.count('<article')
    if article_count < 3:
        errors.append(f"❌ Se encontraron {article_count} tags <article>, deben ser mínimo 3")
    elif article_count > 3:
        warnings.append(f"⚠️ Se encontraron {article_count} tags <article>, lo normal son 3")
    
    has_div_kicker = '<div class="kicker">' in html_lower
    has_span_kicker = '<span class="kicker">' in html_lower
    if has_div_kicker and not has_span_kicker:
        errors.append("❌ El kicker usa <div> pero debe usar <span>")
    
    if '<h1' in html_lower:
        errors.append("❌ Se encontró <h1> pero el CMS usa H2 como título principal")
    if '<h2' not in html_lower:
        warnings.append("⚠️ No se encontró ningún <h2> para el título principal")
    
    if 'contentgenerator__main' not in html_lower and 'content-generator' not in html_lower:
        warnings.append("⚠️ No se encontró article principal")
    if 'faq' not in html_lower:
        warnings.append("⚠️ No se encontró sección de FAQs")
    if 'verdict' not in html_lower:
        warnings.append("⚠️ No se encontró sección de veredicto")
    
    word_count = count_words_in_html(html_content)
    if word_count < 300:
        errors.append(f"❌ Solo {word_count} palabras. Mínimo: 300")
    elif word_count < 500:
        warnings.append(f"⚠️ {word_count} palabras. Recomendado: 800+")
    
    if any(md in html_content for md in ['```', '**', '## ']):
        warnings.append("⚠️ Se detectó posible Markdown residual")
    
    return len(errors) == 0, errors, warnings

def validate_word_count_target(html_content: str, target: int, tolerance: float = 0.05) -> Dict:
    """Valida si el word count está dentro del rango objetivo."""
    actual = count_words_in_html(html_content)
    min_ok = int(target * (1 - tolerance))
    max_ok = int(target * (1 + tolerance))
    diff = actual - target
    pct = (diff / target * 100) if target > 0 else 0
    
    return {
        'actual': actual,
        'target': target,
        'min_acceptable': min_ok,
        'max_acceptable': max_ok,
        'within_range': min_ok <= actual <= max_ok,
        'difference': diff,
        'percentage_diff': round(pct, 2)
    }

# ============================================================================
# FUNCIONES DE ANÁLISIS DE ENLACES
# ============================================================================

def analyze_links(html_content: str) -> Dict:
    """
    Analiza enlaces del HTML.
    
    Detecta y categoriza enlaces en:
    - Internos (pccomponentes.com)
    - Externos
    - PDPs (productos)
    - Blog
    
    Returns:
        Dict con conteos y listas de enlaces
    """
    if not html_content:
        return {
            'total': 0,
            'internal': [],
            'external': [],
            'pdp': [],
            'blog': [],
            'internal_links_count': 0,
            'external_links_count': 0
        }
    
    # Buscar todos los enlaces <a href="...">...</a>
    matches = re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html_content, re.I | re.DOTALL)
    
    internal, external, pdp, blog = [], [], [], []
    
    for url, anchor in matches:
        # Limpiar anchor de tags HTML
        clean_anchor = strip_html_tags(anchor).strip()
        info = {'url': url, 'anchor': clean_anchor}
        
        # Clasificar enlaces
        url_lower = url.lower()
        
        if 'pccomponentes.com' in url_lower or url.startswith('/'):
            internal.append(info)
            
            # Sub-clasificar
            if '/blog/' in url_lower:
                blog.append(info)
            # PDPs tienen varios patrones
            elif any(pattern in url_lower for pattern in [
                '/producto/', '/p/', 'portatil-', 'monitor-', 'tarjeta-', 
                'procesador-', 'movil-', 'tablet-', 'televisor-', 'auricular-',
                'teclado-', 'raton-', 'silla-', 'ordenador-'
            ]):
                pdp.append(info)
        elif url.startswith('http'):
            external.append(info)
    
    return {
        'total': len(matches),
        'internal': internal,
        'external': external,
        'pdp': pdp,
        'blog': blog,
        # Aliases para compatibilidad con results.py
        'internal_count': len(internal),
        'external_count': len(external),
        'internal_links_count': len(internal),
        'external_links_count': len(external),
    }

def get_heading_hierarchy(html_content: str) -> List[Dict[str, str]]:
    """Extrae jerarquía de encabezados."""
    if not html_content:
        return []
    
    return [
        {'level': level.lower(), 'text': strip_html_tags(text)}
        for level, text in re.findall(r'<(h[1-6])[^>]*>(.*?)</\1>', html_content, re.I | re.DOTALL)
    ]

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    # Parser
    'HTMLParser',
    'get_html_parser',
    'get_parser',
    'get_bs4_parser',
    'is_bs4_available',
    # Data classes
    'ExtractedContent',
    # Conteo
    'count_words_in_html',
    'get_word_count',
    'strip_html_tags',
    'strip_tags',
    # Extracción
    'extract_content_structure',
    'extract_content',
    'extract_text',
    'extract_meta_tags',
    # Limpieza
    'sanitize_html',
    'clean_html',
    'extract_html_content',
    # Validación
    'validate_html_structure',
    'validate_cms_structure',
    'validate_word_count_target',
    # Enlaces
    'analyze_links',
    'get_heading_hierarchy',
    # Anti-IA
    'detect_ai_phrases',
]


# ============================================================================
# DETECCIÓN DE FRASES IA
# ============================================================================

# Frases prohibidas: si aparecen en el texto, es señal clara de escritura IA.
# Cada tupla: (patrón regex, frase legible para mostrar al usuario)
_AI_PHRASE_PATTERNS = [
    (r'en el mundo actual', 'En el mundo actual...'),
    (r'en la era digital', 'En la era digital...'),
    (r'sin lugar a dudas', 'Sin lugar a dudas...'),
    (r'es importante destacar', 'Es importante destacar...'),
    (r'cabe mencionar que', 'Cabe mencionar que...'),
    (r'es fundamental', 'Es fundamental...'),
    (r'a la hora de', 'A la hora de...'),
    (r'en lo que respecta', 'En lo que respecta...'),
    (r'ofrece una experiencia', 'Ofrece una experiencia...'),
    (r'brinda la posibilidad', 'Brinda la posibilidad...'),
    (r'esto se traduce en', 'Esto se traduce en...'),
    (r'lo que permite', 'Lo que permite...'),
    (r'no es de extra[ñn]ar', 'No es de extrañar...'),
    (r'en definitiva', 'En definitiva...'),
    (r'cabe destacar', 'Cabe destacar...'),
    (r'resulta especialmente', 'Resulta especialmente...'),
    (r'en este sentido', 'En este sentido...'),
]


def detect_ai_phrases(html_content: str) -> List[Dict[str, str]]:
    """
    Detecta frases típicas de escritura IA en el contenido HTML.
    
    Solo busca en el texto visible (no en HTML/CSS/atributos).
    Usa patrones de alta precisión (pocas frases pero muy fiables).
    
    Args:
        html_content: HTML del contenido generado
        
    Returns:
        Lista de dicts {'phrase': frase legible, 'context': fragmento donde aparece}
    """
    if not html_content:
        return []
    
    # Extraer solo texto visible
    text = strip_html_tags(html_content)
    text_lower = text.lower()
    
    found = []
    for pattern, display_phrase in _AI_PHRASE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            # Extraer contexto (±40 chars alrededor)
            start = max(0, match.start() - 40)
            end = min(len(text), match.end() + 40)
            context = text[start:end].strip()
            if start > 0:
                context = '...' + context
            if end < len(text):
                context = context + '...'
            found.append({
                'phrase': display_phrase,
                'context': context,
            })
    
    return found
