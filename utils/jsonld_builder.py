"""
Builder DETERMINISTA de JSON-LD a partir del HTML de un artículo Raichu.

NO usa LLM. Extrae con BeautifulSoup el `<article class="contentGenerator__main">`
para `Article`, el `<article class="contentGenerator__faqs">` para `FAQPage`, y
opcionalmente añade `Product` si se pasan productos. Esto evita reintentos por
JSON malformado y elimina coste por asset.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

try:
    from bs4 import BeautifulSoup
    _bs4_available = True
except ImportError:
    _bs4_available = False

logger = logging.getLogger(__name__)


def _extract_headline(soup: "BeautifulSoup") -> str:
    """Extrae el primer H1/H2 del artículo principal."""
    main = soup.find('article', class_='contentGenerator__main') or soup
    for tag_name in ('h1', 'h2'):
        tag = main.find(tag_name)
        if tag and tag.get_text(strip=True):
            return tag.get_text(strip=True)
    return ""


_FAQ_HEADINGS = ('h3', 'h4', 'h5', 'h6')


def _extract_faqs(soup: "BeautifulSoup") -> List[Dict[str, str]]:
    """
    Extrae pares (pregunta, respuesta) del article __faqs.

    Tolera tres markups habituales (Raichu usa headings; el HTML pegado del CMS
    puede traer acordeones o listas de definición):
      1. `<details><summary>Pregunta</summary> respuesta </details>`
      2. `<dl><dt>Pregunta</dt><dd>Respuesta</dd>`
      3. Headings h3-h6 como pregunta + hermanos hasta el siguiente heading.

    Antes solo reconocía h3/h4: con HTML pegado en otro markup devolvía [] y
    `validate_jsonld(expects_faqs=True)` marcaba el asset como fallido pese a que
    el artículo SÍ tenía FAQs.
    """
    faqs_article = soup.find('article', class_='contentGenerator__faqs')
    if not faqs_article:
        return []

    items: List[Dict[str, str]] = []

    # 1) Acordeones <details><summary>…</summary>…</details>
    for det in faqs_article.find_all('details'):
        summary = det.find('summary')
        if not summary:
            continue
        question_text = summary.get_text(strip=True)
        answer_parts = [
            child.get_text(' ', strip=True)
            for child in det.find_all(recursive=False)
            if child.name != 'summary'
        ]
        answer_text = ' '.join(p for p in answer_parts if p).strip()
        if question_text and answer_text:
            items.append({"question": question_text, "answer": answer_text})
    if items:
        return items

    # 2) Listas de definición <dt>Pregunta</dt><dd>Respuesta</dd>
    for dt in faqs_article.find_all('dt'):
        question_text = dt.get_text(strip=True)
        dd = dt.find_next_sibling('dd')
        answer_text = dd.get_text(' ', strip=True) if dd else ""
        if question_text and answer_text:
            items.append({"question": question_text, "answer": answer_text})
    if items:
        return items

    # 3) Headings h3-h6 (no h2: suele ser el título "Preguntas frecuentes")
    for q in faqs_article.find_all(list(_FAQ_HEADINGS)):
        question_text = q.get_text(strip=True)
        if not question_text:
            continue
        answer_parts = []
        for sibling in q.find_next_siblings():
            if sibling.name in _FAQ_HEADINGS:
                break
            text = sibling.get_text(' ', strip=True)
            if text:
                answer_parts.append(text)
        answer_text = ' '.join(answer_parts).strip()
        if answer_text:
            items.append({"question": question_text, "answer": answer_text})
    return items


def _build_product_block(product: Dict[str, Any]) -> Dict[str, Any]:
    """Construye un dict @type=Product a partir de los campos esperados."""
    block: Dict[str, Any] = {
        "@type": "Product",
        "name": product.get("name", ""),
    }
    if product.get("sku"):
        block["sku"] = product["sku"]
    if product.get("brand"):
        block["brand"] = {"@type": "Brand", "name": product["brand"]}
    if product.get("url"):
        block["url"] = product["url"]
    price = product.get("price")
    if price is not None:
        block["offers"] = {
            "@type": "Offer",
            "price": str(price),
            "priceCurrency": product.get("currency", "EUR"),
            "url": product.get("url", ""),
            "availability": product.get("availability", "https://schema.org/InStock"),
        }
    return block


def build_article_jsonld(
    article_html: str,
    keyword: str,
    meta_description: Optional[str] = None,
    products: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Construye un JSON-LD válido para un artículo Raichu.

    Args:
        article_html: HTML completo del artículo (con la estructura CMS 3-article).
        keyword: keyword principal — se usa como `keywords` del Article.
        meta_description: descripción opcional; si no se pasa, queda vacía.
        products: lista opcional de dicts con campos {name, sku, brand, url, price, currency}.

    Returns:
        Dict serializable a JSON-LD con `@context`, `Article` y opcionalmente
        `FAQPage` + `Product`. Si BS4 no está disponible o el HTML es malformado,
        retorna un Article mínimo con headline vacío (graceful, sin excepción).
    """
    if not _bs4_available:
        logger.warning("BeautifulSoup no disponible; JSON-LD mínimo retornado")
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "",
            "keywords": keyword,
            "description": meta_description or "",
        }

    try:
        soup = BeautifulSoup(article_html or "", 'html.parser')
    except Exception as e:
        logger.warning(f"Error parseando HTML para JSON-LD: {e}")
        return {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "",
            "keywords": keyword,
            "description": meta_description or "",
        }

    headline = _extract_headline(soup)
    faqs = _extract_faqs(soup)

    article_block: Dict[str, Any] = {
        "@type": "Article",
        "headline": headline,
        "keywords": keyword,
    }
    if meta_description:
        article_block["description"] = meta_description

    blocks: List[Dict[str, Any]] = [article_block]

    if faqs:
        blocks.append({
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": faq["question"],
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": faq["answer"],
                    },
                }
                for faq in faqs
            ],
        })

    if products:
        for product in products:
            blocks.append(_build_product_block(product))

    if len(blocks) == 1:
        return {"@context": "https://schema.org", **blocks[0]}

    return {"@context": "https://schema.org", "@graph": blocks}
