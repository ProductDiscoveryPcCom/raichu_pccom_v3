"""
Validadores puros para los assets derivados del Repurposer.

Cada validador recibe el output ya parseado (str para texto, dict/list para JSON)
y retorna (ok: bool, errors: List[str], normalized: Any). El campo `normalized`
es el mismo input cuando el validador no necesita ajustar nada — sirve como
hook futuro para limpieza ligera (strip, dedup).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F9FF]",
    re.UNICODE,
)
_URL_RE = re.compile(r"https?://\S+")

ValidatorResult = Tuple[bool, List[str], Any]


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword.strip().lower() in text.lower()


def validate_meta_description(text: str, keyword: str) -> ValidatorResult:
    errors: List[str] = []
    text = (text or "").strip().strip('"').strip("'")
    n = len(text)
    if n < 140:
        errors.append(f"Demasiado corta ({n} chars, mínimo 140)")
    if n > 170:
        errors.append(f"Demasiado larga ({n} chars, máximo 170)")
    if keyword and not _contains_keyword(text, keyword):
        errors.append(f"No contiene la keyword '{keyword}'")
    if _EMOJI_RE.search(text):
        errors.append("Contiene emojis")
    return (not errors, errors, text)


def validate_serp_title(text: str, keyword: str) -> ValidatorResult:
    errors: List[str] = []
    text = (text or "").strip().strip('"').strip("'")
    n = len(text)
    if n > 60:
        errors.append(f"Demasiado largo ({n} chars, máximo 60)")
    if n < 25:
        errors.append(f"Demasiado corto ({n} chars, mínimo 25)")
    if keyword and not _contains_keyword(text, keyword):
        errors.append(f"No contiene la keyword '{keyword}'")
    return (not errors, errors, text)


def validate_rsa(payload: Dict[str, Any]) -> ValidatorResult:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return (False, ["RSA debe ser un objeto JSON"], payload)
    titles = payload.get("titles") or []
    descriptions = payload.get("descriptions") or []
    if len(titles) != 15:
        errors.append(f"Se esperaban 15 títulos, hay {len(titles)}")
    if len(descriptions) != 4:
        errors.append(f"Se esperaban 4 descripciones, hay {len(descriptions)}")
    for i, t in enumerate(titles):
        if not isinstance(t, str) or len(t) > 30:
            errors.append(f"Título #{i+1} excede 30 chars o no es string")
    for i, d in enumerate(descriptions):
        if not isinstance(d, str) or len(d) > 90:
            errors.append(f"Descripción #{i+1} excede 90 chars o no es string")
    if len(set(titles)) != len(titles):
        errors.append("Hay títulos duplicados")
    return (not errors, errors, payload)


def validate_x_thread(payload: Dict[str, Any]) -> ValidatorResult:
    errors: List[str] = []
    warnings: List[str] = []
    if not isinstance(payload, dict):
        return (False, ["Thread debe ser objeto JSON"], payload)
    tweets = payload.get("tweets") or []
    if len(tweets) < 8:
        errors.append(f"Hilo demasiado corto ({len(tweets)} tweets, mínimo 8)")
    if len(tweets) > 12:
        errors.append(f"Hilo demasiado largo ({len(tweets)} tweets, máximo 12)")
    for i, tw in enumerate(tweets):
        if not isinstance(tw, dict):
            errors.append(f"Tweet #{i+1} no es objeto JSON")
            continue
        text = tw.get("text", "")
        if len(text) > 280:
            errors.append(f"Tweet #{i+1}: {len(text)} chars (máximo 280)")
        if _URL_RE.search(text):
            warnings.append(f"Tweet #{i+1}: contiene URL completa — usa enlace acortado")
    return (not errors, errors + warnings, payload)


def validate_newsletter(payload: Dict[str, Any]) -> ValidatorResult:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return (False, ["Newsletter debe ser objeto JSON"], payload)
    required = ("subject", "preheader", "body", "cta_text")
    for field in required:
        if not payload.get(field):
            errors.append(f"Falta campo '{field}'")
    body = payload.get("body", "")
    words = len(body.split())
    if body and (words < 40 or words > 100):
        errors.append(f"Body fuera de rango ({words} palabras, esperado 50-80)")
    return (not errors, errors, payload)


def validate_linkedin_carousel(payload: Dict[str, Any]) -> ValidatorResult:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return (False, ["Carrusel debe ser objeto JSON"], payload)
    slides = payload.get("slides") or []
    if not (5 <= len(slides) <= 7):
        errors.append(f"Carrusel debe tener 5-7 slides ({len(slides)} dado)")
    for i, slide in enumerate(slides):
        if not isinstance(slide, dict):
            errors.append(f"Slide #{i+1} no es objeto")
            continue
        if not slide.get("title"):
            errors.append(f"Slide #{i+1} sin título")
    return (not errors, errors, payload)


def validate_featured_snippet(payload: Dict[str, Any]) -> ValidatorResult:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return (False, ["Featured snippet debe ser objeto JSON"], payload)
    question = payload.get("question", "")
    answer = payload.get("answer", "")
    if not question:
        errors.append("Falta 'question'")
    if not answer:
        errors.append("Falta 'answer'")
    words = len(answer.split())
    if answer and (words < 30 or words > 70):
        errors.append(f"Answer fuera de rango ({words} palabras, esperado 40-60)")
    return (not errors, errors, payload)


def validate_whatsapp(text: str) -> ValidatorResult:
    errors: List[str] = []
    text = (text or "").strip()
    if len(text) > 350:
        errors.append(f"Mensaje demasiado largo ({len(text)} chars, máximo 350)")
    if len(text) < 30:
        errors.append(f"Mensaje demasiado corto ({len(text)} chars, mínimo 30)")
    return (not errors, errors, text)


def validate_jsonld(payload: Dict[str, Any], expects_faqs: bool = False) -> ValidatorResult:
    errors: List[str] = []
    if not isinstance(payload, dict):
        return (False, ["JSON-LD debe ser objeto"], payload)
    if payload.get("@context") != "https://schema.org":
        errors.append("Falta '@context' = https://schema.org")
    types = []
    if "@type" in payload:
        types.append(payload["@type"])
    for node in payload.get("@graph", []):
        if isinstance(node, dict) and "@type" in node:
            types.append(node["@type"])
    if "Article" not in types:
        errors.append("No contiene ningún '@type: Article'")
    if expects_faqs and "FAQPage" not in types:
        errors.append("Se esperaba 'FAQPage' (el artículo tiene FAQs)")
    return (not errors, errors, payload)
