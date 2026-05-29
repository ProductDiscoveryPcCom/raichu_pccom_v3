"""
Orquestador del Repurposer — N llamadas paralelas a Claude (1 por asset LLM) +
construcción determinista del JSON-LD. Patrón espejo de
`core.pipeline._run_parallel_stage2` (ThreadPoolExecutor, max 7).

Resultados como `RepurposeResult` por asset, con metadata mínima (tokens,
latencia, intentos, prefill_used). No persiste el HTML fuente fuera del
proceso — el contenido sólo vive en memoria.
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from prompts.repurpose import (
    JSON_ASSETS,
    PROMPT_BUILDERS,
    SUPPORTED_ASSETS,
    get_repurpose_system_prompt,
)
from utils import repurpose_validators as validators
from utils.jsonld_builder import build_article_jsonld

try:
    from utils.html_utils import sanitize_html, strip_html_tags
    _html_utils_available = True
except ImportError:
    _html_utils_available = False

    def sanitize_html(s: str) -> str:  # type: ignore[no-redef]
        return s

    def strip_html_tags(s: str) -> str:  # type: ignore[no-redef]
        return re.sub(r"<[^>]+>", " ", s or "")

logger = logging.getLogger(__name__)


REPURPOSE_MAX_PARALLEL = 7
MAX_ARTICLE_WORDS = 6000
LLM_MAX_TOKENS = 2000  # techos por asset — suficiente para RSA/Carousel


VALIDATOR_MAP = {
    "meta_description": lambda payload, ctx: validators.validate_meta_description(payload, ctx.get("keyword", "")),
    "serp_title": lambda payload, ctx: validators.validate_serp_title(payload, ctx.get("keyword", "")),
    "rsa": lambda payload, ctx: validators.validate_rsa(payload),
    "newsletter": lambda payload, ctx: validators.validate_newsletter(payload),
    "x_thread": lambda payload, ctx: validators.validate_x_thread(payload),
    "linkedin_carousel": lambda payload, ctx: validators.validate_linkedin_carousel(payload),
    "featured_snippet": lambda payload, ctx: validators.validate_featured_snippet(payload),
    "whatsapp": lambda payload, ctx: validators.validate_whatsapp(payload),
    "jsonld": lambda payload, ctx: validators.validate_jsonld(payload, expects_faqs=ctx.get("expects_faqs", False)),
}


@dataclass
class RepurposeResult:
    asset_id: str
    ok: bool
    payload: Any = None
    error: Optional[str] = None
    validation_errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _parse_json_payload(text: str) -> Any:
    """Parsea JSON limpiando markdown fences y BOM."""
    if not text:
        raise ValueError("empty response")
    cleaned = text.lstrip("﻿").strip()
    cleaned = _JSON_FENCE_RE.sub("", cleaned).strip()
    return json.loads(cleaned)


def _prepare_article_text(article_html: str) -> Tuple[str, bool]:
    """
    Sanitiza HTML pegado y reduce a texto para inyectar en prompts.

    Returns:
        (article_text, expects_faqs) — la flag se calcula a partir del HTML
        original (antes del strip) para que validate_jsonld sepa si exigir FAQPage.
    """
    raw = article_html or ""
    expects_faqs = 'contentGenerator__faqs' in raw
    safe = sanitize_html(raw)
    text = strip_html_tags(safe).strip()
    words = text.split()
    if len(words) > MAX_ARTICLE_WORDS:
        text = " ".join(words[:MAX_ARTICLE_WORDS])
    return text, expects_faqs


def _run_llm_asset(
    asset_id: str,
    generator: Any,
    article_text: str,
    context: Dict[str, Any],
    system_prompt: str,
) -> RepurposeResult:
    """
    Lanza la llamada a Claude para un asset LLM. Reintenta UNA vez con
    temperature=0.3 si el JSON viene malformado.
    """
    builder = PROMPT_BUILDERS[asset_id]
    prompt = builder(article_text=article_text, **context)
    is_json = asset_id in JSON_ASSETS
    prefill = "{" if is_json else None

    started = time.time()
    attempts = 0
    last_error: Optional[str] = None
    payload: Any = None
    raw_text: str = ""
    metadata: Dict[str, Any] = {"prefill_used": bool(prefill)}

    for attempt_temperature in (None, 0.3):
        attempts += 1
        try:
            result = generator.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=attempt_temperature,
                prefill=prefill,
            )
        except TypeError:
            # ContentGenerator sin parámetro prefill (legacy / tests)
            result = generator.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                max_tokens=LLM_MAX_TOKENS,
                temperature=attempt_temperature,
            )

        if not getattr(result, "success", False):
            last_error = getattr(result, "error", "generación fallida")
            break  # error no recuperable a este nivel

        raw_text = result.content or ""
        meta = result.metadata or {}
        metadata.update({
            "input_tokens": meta.get("input_tokens"),
            "output_tokens": meta.get("output_tokens"),
            "model": result.model,
            "latency_ms": int((time.time() - started) * 1000),
            "attempts": attempts,
        })

        if is_json:
            try:
                payload = _parse_json_payload(raw_text)
                last_error = None
                break
            except (ValueError, json.JSONDecodeError) as e:
                last_error = f"JSON inválido: {e}"
                continue  # reintenta con temp=0.3
        else:
            payload = raw_text.strip()
            last_error = None
            break

    if last_error and payload is None:
        return RepurposeResult(
            asset_id=asset_id,
            ok=False,
            error=last_error,
            metadata=metadata,
        )

    validator = VALIDATOR_MAP.get(asset_id)
    if validator:
        ok, errors, normalized = validator(payload, context)
        return RepurposeResult(
            asset_id=asset_id,
            ok=ok,
            payload=normalized,
            validation_errors=errors,
            metadata=metadata,
        )

    return RepurposeResult(asset_id=asset_id, ok=True, payload=payload, metadata=metadata)


def _run_jsonld(article_html: str, context: Dict[str, Any]) -> RepurposeResult:
    started = time.time()
    try:
        payload = build_article_jsonld(
            article_html=article_html,
            keyword=context.get("keyword", ""),
            meta_description=context.get("meta_description"),
            products=context.get("products"),
        )
        latency_ms = int((time.time() - started) * 1000)
        validator = VALIDATOR_MAP["jsonld"]
        ok, errors, normalized = validator(payload, context)
        return RepurposeResult(
            asset_id="jsonld",
            ok=ok,
            payload=normalized,
            validation_errors=errors,
            metadata={
                "source": "deterministic_builder",
                "latency_ms": latency_ms,
            },
        )
    except Exception as e:
        logger.exception("JSON-LD builder falló")
        return RepurposeResult(
            asset_id="jsonld",
            ok=False,
            error=str(e),
            metadata={"source": "deterministic_builder"},
        )


def execute_repurpose_pipeline(
    article_html: str,
    assets_requested: List[str],
    config: Dict[str, Any],
    generator: Any,
) -> Dict[str, RepurposeResult]:
    """
    Orquesta la generación de assets derivados.

    Args:
        article_html: HTML del artículo fuente (será sanitizado).
        assets_requested: lista de asset_ids (subset de SUPPORTED_ASSETS).
        config: dict con `keyword` (obligatorio), opcional `products`,
            `meta_description` para el JSON-LD.
        generator: instancia con método `.generate(prompt, system_prompt, max_tokens, temperature, prefill)`.

    Returns:
        Dict {asset_id: RepurposeResult}. Assets no soportados quedan con
        `ok=False, error='unsupported'` para visibilidad.
    """
    article_text, expects_faqs = _prepare_article_text(article_html)
    context = dict(config)
    context.setdefault("keyword", "")
    context["expects_faqs"] = expects_faqs

    system_prompt = get_repurpose_system_prompt()
    results: Dict[str, RepurposeResult] = {}

    llm_assets = [a for a in assets_requested if a in PROMPT_BUILDERS]
    has_jsonld = "jsonld" in assets_requested

    unsupported = [a for a in assets_requested if a not in SUPPORTED_ASSETS]
    for asset_id in unsupported:
        results[asset_id] = RepurposeResult(asset_id=asset_id, ok=False, error="unsupported")

    if has_jsonld:
        results["jsonld"] = _run_jsonld(article_html, context)

    if not llm_assets:
        return results

    workers = min(REPURPOSE_MAX_PARALLEL, len(llm_assets))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_asset = {
            executor.submit(
                _run_llm_asset, asset_id, generator, article_text, context, system_prompt
            ): asset_id
            for asset_id in llm_assets
        }
        for future in future_to_asset:
            asset_id = future_to_asset[future]
            try:
                results[asset_id] = future.result()
            except Exception as e:
                logger.exception(f"Asset {asset_id} levantó excepción")
                results[asset_id] = RepurposeResult(
                    asset_id=asset_id, ok=False, error=str(e)
                )

    return results


def regenerate_single_asset(
    asset_id: str,
    article_html: str,
    config: Dict[str, Any],
    generator: Any,
) -> RepurposeResult:
    """Atajo para regenerar un único asset (para botón 'regenerar' en UI)."""
    out = execute_repurpose_pipeline(article_html, [asset_id], config, generator)
    return out.get(asset_id, RepurposeResult(asset_id=asset_id, ok=False, error="missing"))
