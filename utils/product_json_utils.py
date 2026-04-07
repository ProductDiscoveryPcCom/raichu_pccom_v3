# -*- coding: utf-8 -*-
"""
Product JSON Utils - PcComponentes Content Generator
Versión 2.0.0 - 2026-02-11

Utilidades para parsear y formatear JSON de productos desde n8n.
Soporta el formato real de n8n (wrapper con meta/data/rows + markdown)
y extrae datos estructurados del campo markdown con tolerancia a
secciones faltantes.

Formato de entrada n8n:
    [{"meta": [...], "data": [{"product_id", "markdown", "name", ...}], "rows": N}]

El campo 'markdown' contiene toda la información del producto en formato
markdown estructurado con secciones: CARACTERISTICAS, ESPECIFICACIONES,
SUMMARY, DESCRIPCION, FAQs, ES PARA TI SI, NO ES PARA TI SI, OPINIONES.

CAMBIOS v2.0.0:
- Soporte para formato real n8n (wrapper meta/data/rows/statistics)
- Parser de markdown para extraer secciones variables
- Campos mapeados: name->title, brand->brand_name, family->family_name
- Extracción de precio, URL, valoración, FAQs desde markdown
- ProductData ampliado con price, product_url, rating, faqs, category
- Backward compatible: sigue aceptando formato plano legacy

Autor: PcComponentes - Product Discovery & Content
"""

import json
import re
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__version__ = "2.0.0"


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class ProductData:
    """Datos estructurados de un producto."""
    product_id: str
    legacy_id: str
    title: str
    description: str
    brand_name: str
    family_name: str
    attributes: Dict[str, str]
    images: List[str]
    features: Optional[Any]
    total_comments: int
    advantages: str
    disadvantages: str
    comments: List[Dict[str, str]]
    # Campos nuevos v2.0
    price: str = ""
    product_url: str = ""
    rating: str = ""
    category: str = ""
    faqs: List[Dict[str, str]] = field(default_factory=list)
    advantages_list: List[str] = field(default_factory=list)
    disadvantages_list: List[str] = field(default_factory=list)
    raw_markdown: str = ""

    @property
    def main_image(self) -> Optional[str]:
        """Primera imagen del producto."""
        return self.images[0] if self.images else None

    @property
    def has_reviews(self) -> bool:
        """Indica si tiene reseñas."""
        return self.total_comments > 0 or bool(self.rating)

    @property
    def key_attributes(self) -> List[Tuple[str, str]]:
        """Atributos principales como lista de tuplas."""
        return list(self.attributes.items())


# ============================================================================
# PARSER DE MARKDOWN (secciones del producto)
# ============================================================================

def _parse_markdown_section(markdown: str, header: str) -> Optional[str]:
    """Extrae una sección del markdown por su header."""
    pattern = rf'##\s*{re.escape(header)}\s*\n(.*?)(?=\n##\s|\Z)'
    match = re.search(pattern, markdown, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


def _parse_characteristics(markdown: str) -> Dict[str, str]:
    """Extrae pares clave: valor de la sección CARACTERISTICAS."""
    section = _parse_markdown_section(markdown, 'CARACTERISTICAS')
    if not section:
        return {}
    chars = {}
    for line in section.split('\n'):
        m = re.match(r'-\s*(.+?):\s*(.+)', line.strip())
        if m:
            chars[m.group(1).strip()] = m.group(2).strip()
    return chars


def _parse_specifications(markdown: str) -> Dict[str, str]:
    """Extrae la tabla de especificaciones del markdown."""
    section = _parse_markdown_section(markdown, 'ESPECIFICACIONES')
    if not section:
        return {}
    specs = {}
    for line in section.split('\n'):
        if line.startswith('|') and '---' not in line:
            parts = [p.strip() for p in line.split('|')[1:-1]]
            # P3.4: aceptar tablas con >2 columnas (ej: | Clave | Valor | Unidad |)
            if len(parts) >= 2 and parts[0] and parts[0] != 'Clave':
                specs[parts[0]] = ' '.join(p for p in parts[1:] if p).strip()
    return specs


def _parse_list_section(markdown: str, header: str) -> List[str]:
    """Extrae una sección con formato de lista (- item)."""
    section = _parse_markdown_section(markdown, header)
    if not section:
        return []
    items = []
    for line in section.split('\n'):
        line = line.strip()
        if line.startswith('-'):
            item = line.lstrip('- ').strip()
            if item:
                items.append(item)
    return items


def _parse_faqs(markdown: str) -> List[Dict[str, str]]:
    """Extrae FAQs del markdown (formato ### pregunta + respuesta)."""
    faq_match = re.search(
        r'(?:FAQs|## FAQS|## PREGUNTAS).*?\n[-=]*\s*\n(.*?)(?=\n## |\Z)',
        markdown, re.DOTALL | re.IGNORECASE,
    )
    if not faq_match:
        return []
    faqs_text = faq_match.group(1)
    faqs = []
    parts = re.split(r'###\s*', faqs_text)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        lines = part.split('\n', 1)
        question = lines[0].strip()
        answer = lines[1].strip() if len(lines) > 1 else ""
        if question:
            faqs.append({"question": question, "answer": answer})
    return faqs


def _parse_rating(markdown: str) -> str:
    """Extrae la valoración media del markdown."""
    match = re.search(r'Valoraci\S*n\s*Media:\*?\*?\s*([\d.]+(?:/\d+)?)', markdown)
    return match.group(1) if match else ""


def parse_markdown_content(markdown: str) -> Dict[str, Any]:
    """
    Parsea todo el contenido del campo markdown de n8n.

    Returns:
        Dict con todos los datos extraídos
    """
    chars = _parse_characteristics(markdown)
    specs = _parse_specifications(markdown)
    advantages = _parse_list_section(markdown, 'ES PARA TI SI')
    disadvantages = _parse_list_section(markdown, 'NO ES PARA TI SI')
    summary = _parse_markdown_section(markdown, 'SUMMARY') or ""
    description = _parse_markdown_section(markdown, 'DESCRIPCION') or ""

    return {
        "characteristics": chars,
        "specifications": specs,
        "summary": summary,
        "description": description,
        "faqs": _parse_faqs(markdown),
        "advantages_list": advantages,
        "disadvantages_list": disadvantages,
        "advantages_text": "\n".join(f"- {a}" for a in advantages),
        "disadvantages_text": "\n".join(f"- {d}" for d in disadvantages),
        "rating": _parse_rating(markdown),
        "price": chars.get("PRECIO", ""),
        "category": chars.get("CATEGORÍA", chars.get("CATEGORIA", "")),
        "product_url": chars.get("URL", ""),
    }


# ============================================================================
# DETECCIÓN DE FORMATO Y EXTRACCIÓN
# ============================================================================

def _is_n8n_wrapper_format(data: Any) -> bool:
    """Detecta si el JSON tiene formato wrapper de n8n (meta/data/rows)."""
    if isinstance(data, list) and len(data) > 0:
        first = data[0]
        return isinstance(first, dict) and 'data' in first and 'meta' in first
    return False


def _extract_products_from_n8n(data: list) -> List[Dict]:
    """Extrae los productos del formato wrapper de n8n."""
    products = []
    for wrapper in data:
        if isinstance(wrapper, dict) and 'data' in wrapper:
            items = wrapper['data']
            if isinstance(items, list):
                products.extend(items)
    return products


def _normalize_n8n_product(raw: Dict, markdown_data: Dict) -> Dict:
    """Normaliza un producto n8n al formato esperado por ProductData."""
    attributes = {}
    attributes.update(markdown_data.get("specifications", {}))

    return {
        "product_id": str(raw.get("product_id", "")),
        "legacy_id": "",
        "title": raw.get("name", ""),
        "description": markdown_data.get("description", "")
            or markdown_data.get("summary", ""),
        "brand_name": raw.get("brand", ""),
        "family_name": raw.get("family", ""),
        "attributes": attributes,
        "images": [],
        "features": markdown_data.get("characteristics", {}),
        # P3.2: leer del raw con doble fallback (snake_case y camelCase)
        "totalComments": raw.get("total_comments", raw.get("totalComments", 0)),
        "advantages": markdown_data.get("advantages_text", ""),
        "disadvantages": markdown_data.get("disadvantages_text", ""),
        "comments": [],
        "price": markdown_data.get("price", ""),
        "product_url": raw.get("product_url", "")
            or markdown_data.get("product_url", ""),
        "rating": markdown_data.get("rating", ""),
        "category": markdown_data.get("category", ""),
        "faqs": markdown_data.get("faqs", []),
        "advantages_list": markdown_data.get("advantages_list", []),
        "disadvantages_list": markdown_data.get("disadvantages_list", []),
        "raw_markdown": raw.get("markdown", ""),
    }


# ============================================================================
# PARSEO DE JSON (API pública)
# ============================================================================

def _build_product_data(d: Dict) -> ProductData:
    """Construye ProductData desde un dict normalizado."""
    return ProductData(
        product_id=d.get('product_id', ''),
        legacy_id=d.get('legacy_id', ''),
        title=d.get('title', ''),
        description=d.get('description', ''),
        brand_name=d.get('brand_name', ''),
        family_name=d.get('family_name', ''),
        attributes=d.get('attributes', {}),
        images=d.get('images', []),
        features=d.get('features'),
        total_comments=d.get('totalComments', 0),
        advantages=d.get('advantages', ''),
        disadvantages=d.get('disadvantages', ''),
        comments=d.get('comments', []),
        price=d.get('price', ''),
        product_url=d.get('product_url', ''),
        rating=d.get('rating', ''),
        category=d.get('category', ''),
        faqs=d.get('faqs', []),
        advantages_list=d.get('advantages_list', []),
        disadvantages_list=d.get('disadvantages_list', []),
        raw_markdown=d.get('raw_markdown', ''),
    )


def parse_product_json(json_data: str) -> Optional[ProductData]:
    """
    Parsea JSON de producto desde n8n.
    Soporta ambos formatos:
      - n8n wrapper: [{"meta":..., "data":[{product}], "rows":N}]
      - Legacy plano: {"product_id":..., "title":...} o [{...}]

    Args:
        json_data: String con JSON del producto

    Returns:
        ProductData si es válido, None si hay error
    """
    try:
        data = json.loads(json_data)

        # Detectar formato n8n wrapper
        if _is_n8n_wrapper_format(data):
            raw_products = _extract_products_from_n8n(data)
            if not raw_products:
                logger.error("JSON n8n sin productos en 'data'")
                return None
            raw = raw_products[0]
            markdown = raw.get("markdown", "")
            markdown_data = parse_markdown_content(markdown) if markdown else {}
            product_dict = _normalize_n8n_product(raw, markdown_data)

        else:
            # Formato legacy (plano)
            if isinstance(data, list) and len(data) > 0:
                product_dict = data[0]
            elif isinstance(data, dict):
                product_dict = data
            else:
                logger.error("Formato de JSON inválido")
                return None

            if 'product_id' not in product_dict:
                logger.error("Falta campo 'product_id'")
                return None

            # Normalizar campos legacy
            if 'title' not in product_dict and 'name' in product_dict:
                product_dict['title'] = product_dict['name']
            if 'brand_name' not in product_dict and 'brand' in product_dict:
                product_dict['brand_name'] = product_dict['brand']
            if 'family_name' not in product_dict and 'family' in product_dict:
                product_dict['family_name'] = product_dict['family']

        return _build_product_data(product_dict)

    except json.JSONDecodeError as e:
        logger.error(f"Error al parsear JSON: {e}")
        return None
    except Exception as e:
        logger.error(f"Error inesperado al parsear JSON: {e}")
        return None


def validate_product_json(json_data: str) -> Tuple[bool, Optional[str]]:
    """
    Valida que el JSON tenga una estructura reconocida.

    Returns:
        Tuple (is_valid, error_message)
    """
    try:
        data = json.loads(json_data)

        if _is_n8n_wrapper_format(data):
            products = _extract_products_from_n8n(data)
            if not products:
                return False, "JSON n8n válido pero sin productos en 'data'"
            first = products[0]
            if 'product_id' not in first:
                return False, "Producto sin 'product_id'"
            if 'markdown' not in first and 'name' not in first:
                return False, "Producto sin 'markdown' ni 'name'"
            return True, None

        if isinstance(data, list):
            if len(data) == 0:
                return False, "El array está vacío"
            product = data[0]
        elif isinstance(data, dict):
            product = data
        else:
            return False, "El JSON debe ser un objeto o un array"

        if 'product_id' not in product:
            return False, "Falta 'product_id'"

        return True, None

    except json.JSONDecodeError as e:
        return False, f"JSON inválido: {str(e)}"
    except Exception as e:
        return False, f"Error: {str(e)}"


# ============================================================================
# FORMATEO PARA PROMPTS
# ============================================================================

def format_product_for_prompt(
    product: ProductData, include_reviews: bool = True
) -> str:
    """
    Formatea datos de producto para incluir en prompts de Claude.
    Si tiene markdown raw de n8n, usa formato enriquecido.
    Si es legacy, construye manualmente.
    """
    if product.raw_markdown:
        return _format_from_markdown(product)
    return _format_from_fields(product, include_reviews)


def _format_from_markdown(product: ProductData) -> str:
    """Formatea producto usando datos parseados del markdown de n8n."""
    sections = []

    sections.append(f"**PRODUCTO: {product.title}**")
    sections.append(f"ID: {product.product_id}")
    if product.brand_name:
        sections.append(f"Marca: {product.brand_name}")
    if product.family_name:
        sections.append(f"Familia: {product.family_name}")
    if product.price:
        sections.append(f"Precio: {product.price}")
    if product.product_url:
        sections.append(f"URL: {product.product_url}")

    if product.attributes:
        sections.append("\n**Especificaciones técnicas:**")
        for key, value in product.key_attributes:
            sections.append(f"- {key}: {value}")

    if product.description:
        sections.append(f"\n**Descripción:**")
        sections.append(product.description)

    if product.advantages_list:
        sections.append("\n**Es para ti si:**")
        for a in product.advantages_list:
            sections.append(f"- {a}")

    if product.disadvantages_list:
        sections.append("\n**No es para ti si:**")
        for d in product.disadvantages_list:
            sections.append(f"- {d}")

    if product.faqs:
        sections.append(f"\n**FAQs del producto ({len(product.faqs)}):**")
        for faq in product.faqs[:5]:
            sections.append(f"- P: {faq['question']}")
            answer = faq.get('answer', '')
            if answer:
                short = answer[:200] + "..." if len(answer) > 200 else answer
                sections.append(f"  R: {short}")

    if product.rating:
        sections.append(f"\n**Valoración:** {product.rating}")

    return "\n".join(sections)


def _format_from_fields(product: ProductData, include_reviews: bool = True) -> str:
    """Formatea producto desde campos individuales (formato legacy)."""
    sections = []

    sections.append(f"**PRODUCTO: {product.title}**")
    sections.append(f"ID: {product.product_id}")
    if product.brand_name:
        sections.append(f"Marca: {product.brand_name}")
    if product.family_name:
        sections.append(f"Familia: {product.family_name}")

    if product.attributes:
        sections.append("\n**Características principales:**")
        for key, value in product.key_attributes:
            sections.append(f"- {key}: {value}")

    if product.description:
        sections.append(f"\n**Descripción del producto:**")
        sections.append(product.description)

    if product.has_reviews:
        sections.append(
            f"\n**Basado en {product.total_comments} opiniones de usuarios:**"
        )
        if product.advantages:
            sections.append("\n**Ventajas mencionadas por usuarios:**")
            adv = product.advantages[:1000] + "..." if len(product.advantages) > 1000 else product.advantages
            sections.append(adv)
        if product.disadvantages:
            sections.append("\n**Aspectos a mejorar mencionados por usuarios:**")
            dis = product.disadvantages[:1000] + "..." if len(product.disadvantages) > 1000 else product.disadvantages
            sections.append(dis)

    if include_reviews and product.comments:
        sections.append("\n**Opiniones destacadas de usuarios:**")
        for i, comment in enumerate(product.comments[:3], 1):
            opinion = comment.get('opinion', '')
            if opinion:
                short = opinion[:300] + "..." if len(opinion) > 300 else opinion
                sections.append(f"{i}. {short}")

    if product.images:
        sections.append(f"\n**Imágenes del producto:** {len(product.images)} disponibles")

    return "\n".join(sections)


def format_product_brief(product: ProductData) -> str:
    """Formatea versión breve del producto (para listas de enlaces)."""
    parts = [product.title]
    if product.brand_name:
        parts.append(f"({product.brand_name})")
    if product.price:
        parts.append(f"- {product.price}")
    key_attrs = [f"{k}: {v}" for k, v in list(product.key_attributes)[:2]]
    if key_attrs:
        parts.append("- " + ", ".join(key_attrs))
    return " ".join(parts)


def extract_key_features(product: ProductData, max_features: int = 5) -> List[str]:
    """Extrae características clave del producto."""
    return [f"{k}: {v}" for k, v in product.key_attributes[:max_features]]


# ============================================================================
# HELPERS PARA UI
# ============================================================================

def create_product_summary(product: ProductData) -> Dict[str, Any]:
    """Crea resumen del producto para mostrar en UI."""
    return {
        'title': product.title,
        'brand': product.brand_name,
        'family': product.family_name,
        'product_id': product.product_id,
        'has_reviews': product.has_reviews,
        'total_comments': product.total_comments,
        'rating': product.rating,
        'price': product.price,
        'product_url': product.product_url,
        'category': product.category,
        'attributes_count': len(product.attributes),
        'images_count': len(product.images),
        'main_image': product.main_image,
        'key_features': extract_key_features(product, 3),
        'faqs_count': len(product.faqs),
        'has_advantages': bool(product.advantages_list),
        'has_disadvantages': bool(product.disadvantages_list),
    }


# ============================================================================
# PROCESAMIENTO DE MÚLTIPLES PRODUCTOS
# ============================================================================

def parse_multiple_products(json_data: str) -> List[ProductData]:
    """Parsea múltiples productos desde JSON (n8n o legacy)."""
    try:
        data = json.loads(json_data)
        products = []

        if _is_n8n_wrapper_format(data):
            for raw in _extract_products_from_n8n(data):
                try:
                    markdown = raw.get("markdown", "")
                    md_data = parse_markdown_content(markdown) if markdown else {}
                    normalized = _normalize_n8n_product(raw, md_data)
                    products.append(_build_product_data(normalized))
                except Exception as e:
                    logger.warning(f"Error al parsear producto n8n: {e}")

        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    try:
                        if 'title' not in item and 'name' in item:
                            item['title'] = item['name']
                        if 'brand_name' not in item and 'brand' in item:
                            item['brand_name'] = item['brand']
                        if 'family_name' not in item and 'family' in item:
                            item['family_name'] = item['family']
                        products.append(_build_product_data(item))
                    except Exception as e:
                        logger.warning(f"Error al parsear producto: {e}")

        return products
    except json.JSONDecodeError:
        return []
    except Exception as e:
        logger.error(f"Error al parsear múltiples productos: {e}")
        return []


def format_multiple_products_for_prompt(
    products: List[ProductData], include_reviews: bool = False
) -> str:
    """Formatea múltiples productos para prompt."""
    if not products:
        return ""
    sections = [f"**INFORMACIÓN DE {len(products)} PRODUCTO(S):**\n"]
    for i, product in enumerate(products, 1):
        sections.append(f"\n--- PRODUCTO {i} ---")
        sections.append(format_product_for_prompt(product, include_reviews=include_reviews))
    return "\n".join(sections)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'ProductData',
    'parse_product_json',
    'validate_product_json',
    'parse_multiple_products',
    'parse_markdown_content',
    'format_product_for_prompt',
    'format_product_brief',
    'format_multiple_products_for_prompt',
    'extract_key_features',
    'create_product_summary',
]
