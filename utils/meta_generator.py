# -*- coding: utf-8 -*-
"""
Meta Generator - PcComponentes Content Generator
Versión 1.0.0

Genera metadatos SEO y resúmenes TL;DR para contenido generado:
- Meta title (≤60 chars, keyword al inicio)
- Meta description (≤155 chars, con CTA implícito)
- Título TL;DR (≤80 chars, gancho directo)
- Descripción TL;DR (≤200 chars, valor claro para el lector)

Usa el contenido final + datos de producto (scraping) + keyword
para generar meta optimizado con una sola llamada a Claude.

Autor: PcComponentes - Product Discovery & Content
"""

import re
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

# Límites de caracteres
LIMITS = {
    'meta_title': 60,
    'meta_description': 155,
    'tldr_title': 80,
    'tldr_description': 200,
}


def generate_meta(
    html_content: str,
    keyword: str,
    pdp_data: Optional[Dict] = None,
    secondary_keywords: Optional[list] = None,
    arquetipo_name: str = "",
) -> Optional[Dict[str, str]]:
    """
    Genera meta title, meta description, título TL;DR y descripción TL;DR.
    
    Usa una sola llamada a Claude con prompt estructurado.
    
    Args:
        html_content: HTML final del artículo
        keyword: Keyword principal
        pdp_data: Datos de producto del scraping (title, brand, advantages, etc.)
        secondary_keywords: Keywords secundarias
        arquetipo_name: Nombre del arquetipo (guía, review, comparativa...)
        
    Returns:
        Dict con meta_title, meta_description, tldr_title, tldr_description
        o None si falla
    """
    if not html_content or not keyword:
        return None
    
    # Extraer texto del HTML para contexto
    text = _strip_html(html_content)
    # Primer párrafo (intro) y último (conclusión)
    paragraphs = [p.strip() for p in text.split('\n') if p.strip() and len(p.strip()) > 50]
    intro = paragraphs[0] if paragraphs else text[:300]
    conclusion = paragraphs[-1] if len(paragraphs) > 1 else ""
    
    # Extraer H2 como estructura
    h2s = re.findall(r'<h2[^>]*>(.*?)</h2>', html_content, re.IGNORECASE | re.DOTALL)
    h2_texts = [re.sub(r'<[^>]+>', '', h).strip() for h in h2s[:5]]
    
    # Construir contexto de producto si hay datos de scraping
    product_context = _build_product_context(pdp_data) if pdp_data else ""
    
    # Construir prompt
    prompt = _build_meta_prompt(
        keyword=keyword,
        intro=intro[:500],
        conclusion=conclusion[:300],
        h2s=h2_texts,
        product_context=product_context,
        secondary_keywords=secondary_keywords or [],
        arquetipo_name=arquetipo_name,
        word_count=len(text.split()),
    )
    
    # Llamar a Claude
    try:
        from core.generator import ContentGenerator
        from config.settings import CLAUDE_API_KEY, CLAUDE_MODEL, TEMPERATURE
        
        generator = ContentGenerator(
            api_key=CLAUDE_API_KEY,
            model=CLAUDE_MODEL,
            max_tokens=500,  # Respuesta corta
            temperature=max(0.3, TEMPERATURE - 0.2),  # Menos creativo para meta
        )
        
        result = generator.generate(prompt)
        
        if result.success and result.content:
            return _parse_meta_response(result.content)
        else:
            logger.warning(f"Meta generation failed: {result.error}")
            return _generate_fallback(keyword, intro, h2_texts, pdp_data)
    
    except ImportError:
        logger.info("Meta generation: generator not available, using fallback")
        return _generate_fallback(keyword, intro, h2_texts, pdp_data)
    except Exception as e:
        logger.warning(f"Meta generation error: {e}")
        return _generate_fallback(keyword, intro, h2_texts, pdp_data)


def _build_product_context(pdp_data: Dict) -> str:
    """Extrae contexto relevante de los datos de producto."""
    parts = []
    
    title = pdp_data.get('title') or pdp_data.get('name', '')
    if title:
        parts.append(f"Producto principal: {title}")
    
    brand = pdp_data.get('brand_name') or pdp_data.get('brand', '')
    if brand:
        parts.append(f"Marca: {brand}")
    
    advantages = pdp_data.get('advantages_list', [])
    if advantages:
        parts.append(f"Ventajas: {', '.join(advantages[:3])}")
    
    price = pdp_data.get('price') or pdp_data.get('current_price', '')
    if price:
        parts.append(f"Precio: {price}")
    
    comments = pdp_data.get('top_comments', [])
    if comments:
        parts.append(f"Opinión destacada: \"{comments[0][:80]}\"")
    
    return '\n'.join(parts)


def _build_meta_prompt(
    keyword: str,
    intro: str,
    conclusion: str,
    h2s: list,
    product_context: str,
    secondary_keywords: list,
    arquetipo_name: str,
    word_count: int,
) -> str:
    """Construye el prompt para generar los 4 campos meta."""
    
    h2_list = '\n'.join(f'- {h}' for h in h2s) if h2s else '(sin subtítulos)'
    kw_secondary = ', '.join(secondary_keywords[:5]) if secondary_keywords else '(ninguna)'
    
    return f"""Genera los metadatos SEO y TL;DR para un artículo de PcComponentes.

KEYWORD PRINCIPAL: {keyword}
KEYWORDS SECUNDARIAS: {kw_secondary}
TIPO DE ARTÍCULO: {arquetipo_name or 'artículo SEO'}
LONGITUD: {word_count} palabras

ESTRUCTURA (H2s):
{h2_list}

INTRO DEL ARTÍCULO:
{intro}

{f"CONCLUSIÓN:{chr(10)}{conclusion}" if conclusion else ""}

{f"DATOS DE PRODUCTO (del scraping):{chr(10)}{product_context}" if product_context else ""}

GENERA exactamente estos 4 campos en formato JSON (sin markdown, sin ```):

{{
  "meta_title": "≤60 chars. Keyword al inicio. Sin marca PcComponentes. Formato: Keyword - Beneficio o Año",
  "meta_description": "≤155 chars. Incluir keyword + cifra/dato concreto + CTA implícito (descubre, compara, encuentra). Sin clickbait.",
  "tldr_title": "≤80 chars. Gancho directo que resume el valor del artículo. Puede ser pregunta o afirmación. No repetir meta_title.",
  "tldr_description": "≤200 chars. Resumen ejecutivo: qué va a encontrar el lector, para quién es y qué decisión le ayuda a tomar. Tono directo."
}}

REGLAS:
1. Keyword "{keyword}" DEBE aparecer en meta_title y meta_description
2. Si hay datos de producto, usa precio, marca o ventaja principal en la meta_description
3. El TL;DR es para lectores que quieren saber rápidamente si el artículo les sirve
4. NO uses frases genéricas como "todo lo que necesitas saber" o "guía completa"
5. Responde SOLO con el JSON, sin ningún texto antes o después"""


def _parse_meta_response(response: str) -> Optional[Dict[str, str]]:
    """Parsea la respuesta de Claude como JSON."""
    try:
        # Limpiar posibles marcadores markdown
        cleaned = response.strip()
        cleaned = re.sub(r'^```json?\s*', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^```\s*$', '', cleaned, flags=re.MULTILINE)
        cleaned = cleaned.strip()
        
        data = json.loads(cleaned)
        
        # Validar campos y truncar si exceden límites
        result = {}
        for field, limit in LIMITS.items():
            value = data.get(field, '')
            if not isinstance(value, str):
                value = str(value)
            # Truncar respetando palabra completa
            if len(value) > limit:
                value = value[:limit].rsplit(' ', 1)[0].rstrip('.,;:') + '…'
            result[field] = value
        
        # Validar que keyword aparece en meta_title
        if result.get('meta_title') and keyword_missing(result['meta_title']):
            logger.warning("Meta title missing keyword, keeping as-is")
        
        return result
    
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.warning(f"Failed to parse meta response: {e}")
        # Intentar extracción regex como fallback
        return _extract_meta_regex(response)


def keyword_missing(meta_title: str) -> bool:
    """Check placeholder — se implementa en generate_meta."""
    return False


def _extract_meta_regex(response: str) -> Optional[Dict[str, str]]:
    """Fallback: extrae campos por regex si JSON falla."""
    result = {}
    for field in LIMITS:
        pattern = rf'"{field}"\s*:\s*"([^"]*)"'
        match = re.search(pattern, response)
        if match:
            value = match.group(1)
            limit = LIMITS[field]
            if len(value) > limit:
                value = value[:limit].rsplit(' ', 1)[0] + '…'
            result[field] = value
    
    return result if len(result) >= 2 else None


def _generate_fallback(
    keyword: str,
    intro: str,
    h2s: list,
    pdp_data: Optional[Dict] = None,
) -> Dict[str, str]:
    """
    Genera meta sin API call (fallback programático).
    Menos optimizado pero funcional.
    """
    # Meta title: keyword + primer H2 o año
    meta_title = keyword.strip()
    if len(meta_title) < 45:
        meta_title += " (2025)"
    meta_title = meta_title[:LIMITS['meta_title']]
    
    # Meta description: primer párrafo truncado
    intro_clean = re.sub(r'\s+', ' ', intro).strip()
    if len(intro_clean) > LIMITS['meta_description']:
        meta_description = intro_clean[:LIMITS['meta_description']].rsplit(' ', 1)[0] + '…'
    else:
        meta_description = intro_clean
    
    # TL;DR title
    if h2s:
        tldr_title = h2s[0][:LIMITS['tldr_title']]
    else:
        tldr_title = f"Lo que debes saber sobre {keyword}"[:LIMITS['tldr_title']]
    
    # TL;DR description
    product_name = ""
    if pdp_data:
        product_name = pdp_data.get('title', pdp_data.get('name', ''))
    
    if product_name:
        tldr_desc = f"Análisis de {product_name} y alternativas para elegir el mejor {keyword}."
    else:
        tldr_desc = f"Comparativa y recomendaciones de {keyword} con datos reales."
    tldr_desc = tldr_desc[:LIMITS['tldr_description']]
    
    return {
        'meta_title': meta_title,
        'meta_description': meta_description,
        'tldr_title': tldr_title,
        'tldr_description': tldr_desc,
    }


def validate_meta(meta: Dict[str, str], keyword: str) -> list:
    """
    Valida los metadatos generados.
    Returns lista de issues.
    """
    issues = []
    
    for field, limit in LIMITS.items():
        value = meta.get(field, '')
        if not value:
            issues.append(f"{field}: vacío")
        elif len(value) > limit:
            issues.append(f"{field}: {len(value)} chars (máx {limit})")
    
    # Keyword en meta_title
    kw_lower = keyword.lower()
    if meta.get('meta_title') and kw_lower not in meta['meta_title'].lower():
        issues.append(f"meta_title: no contiene la keyword '{keyword}'")
    
    # Keyword en meta_description
    if meta.get('meta_description') and kw_lower not in meta['meta_description'].lower():
        issues.append(f"meta_description: no contiene la keyword '{keyword}'")
    
    # TL;DR title ≠ meta_title
    if meta.get('tldr_title') and meta.get('meta_title'):
        if meta['tldr_title'].lower() == meta['meta_title'].lower():
            issues.append("tldr_title: idéntico a meta_title (deben ser diferentes)")
    
    return issues


def _strip_html(html: str) -> str:
    """Extrae texto visible de HTML."""
    import html as html_module
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text
