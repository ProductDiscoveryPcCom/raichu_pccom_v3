"""
Orquestador del Stage 2.5 — Audience Tester.

Lanza N llamadas en paralelo (una por persona) sobre el draft de Stage 1,
parsea la respuesta JSON forzada con prefill='{' y compone un texto
`audience_feedback` que se inyecta como input adicional en Stage 3.

Patrón espejo de `core.repurpose_pipeline._run_llm_asset`:
ThreadPoolExecutor, reintento único con temp=0.3 si el JSON falla.
"""
from __future__ import annotations

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.audiencias import PERSONAS, Persona
from prompts.audience import (
    build_audience_merge_directive,
    build_audience_test_prompt,
    coerce_conviction,
)

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


AUDIENCE_MAX_PARALLEL = 5
LLM_MAX_TOKENS = 1200
MAX_DRAFT_WORDS = 8000
MIN_OK_PERSONAS = 2  # Mínimo de personas OK para usar el feedback
MAX_FEEDBACK_TOKENS_CHARS = 8000  # ~2000 tokens cap (ver §riesgos del plan)

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


@dataclass
class PersonaFeedback:
    persona_id: str
    persona_nombre: str
    ok: bool
    feedback: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AudienceTestResult:
    by_persona: Dict[str, PersonaFeedback] = field(default_factory=dict)
    avg_conviction: Optional[float] = None
    blocking_objections: List[str] = field(default_factory=list)
    audience_feedback_text: str = ""
    total_tokens: int = 0

    @property
    def has_usable_feedback(self) -> bool:
        return bool(self.audience_feedback_text)


def _prepare_draft_text(draft_html: str) -> str:
    raw = draft_html or ""
    safe = sanitize_html(raw)
    text = strip_html_tags(safe).strip()
    words = text.split()
    if len(words) > MAX_DRAFT_WORDS:
        text = " ".join(words[:MAX_DRAFT_WORDS])
    return text


def _parse_json(text: str) -> Any:
    if not text:
        raise ValueError("empty response")
    cleaned = text.lstrip("﻿").strip()
    cleaned = _JSON_FENCE_RE.sub("", cleaned).strip()
    return json.loads(cleaned)


def _test_one_persona(
    persona: Persona,
    draft_text: str,
    keyword: str,
    generator: Any,
    system_prompt: Optional[str],
) -> PersonaFeedback:
    prompt = build_audience_test_prompt(draft_text=draft_text, persona=persona, keyword=keyword)

    started = time.time()
    attempts = 0
    last_error: Optional[str] = None
    parsed: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = {"prefill_used": True}

    for attempt_temperature in (None, 0.3):
        attempts += 1
        try:
            try:
                result = generator.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=LLM_MAX_TOKENS,
                    temperature=attempt_temperature,
                    prefill="{",
                )
            except TypeError:
                # ContentGenerator legacy sin parámetro prefill
                result = generator.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    max_tokens=LLM_MAX_TOKENS,
                    temperature=attempt_temperature,
                )
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            break

        if not getattr(result, "success", False):
            last_error = getattr(result, "error", "generación fallida")
            break

        meta = result.metadata or {}
        metadata.update({
            "input_tokens": meta.get("input_tokens"),
            "output_tokens": meta.get("output_tokens"),
            "model": getattr(result, "model", None),
            "latency_ms": int((time.time() - started) * 1000),
            "attempts": attempts,
        })

        try:
            parsed = _parse_json(result.content or "")
            last_error = None
            break
        except (ValueError, json.JSONDecodeError) as e:
            last_error = f"JSON inválido: {e}"
            continue

    if parsed is None:
        return PersonaFeedback(
            persona_id=persona.id,
            persona_nombre=persona.nombre,
            ok=False,
            error=last_error,
            metadata=metadata,
        )

    if not isinstance(parsed, dict):
        return PersonaFeedback(
            persona_id=persona.id,
            persona_nombre=persona.nombre,
            ok=False,
            error="respuesta no es dict",
            metadata=metadata,
        )

    return PersonaFeedback(
        persona_id=persona.id,
        persona_nombre=persona.nombre,
        ok=True,
        feedback=parsed,
        metadata=metadata,
    )


def run_audience_test(
    draft_html: str,
    persona_ids: List[str],
    keyword: str,
    generator: Any,
    system_prompt: Optional[str] = None,
) -> AudienceTestResult:
    """
    Ejecuta el Stage 2.5 contra N personas en paralelo.

    Devuelve siempre un `AudienceTestResult`: si menos de `MIN_OK_PERSONAS`
    completan correctamente, `audience_feedback_text` queda vacío y Stage 3
    debe seguir su camino normal sin el feedback (degradación graceful).
    """
    personas = [PERSONAS[pid] for pid in persona_ids if pid in PERSONAS]
    if not personas:
        logger.warning("run_audience_test sin personas válidas; nada que hacer")
        return AudienceTestResult()

    draft_text = _prepare_draft_text(draft_html)
    workers = min(AUDIENCE_MAX_PARALLEL, len(personas))

    result = AudienceTestResult()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        future_to_persona = {
            executor.submit(
                _test_one_persona, persona, draft_text, keyword, generator, system_prompt
            ): persona
            for persona in personas
        }
        for future, persona in future_to_persona.items():
            try:
                pf = future.result()
            except Exception as e:
                logger.exception(f"Persona {persona.id} levantó excepción")
                pf = PersonaFeedback(
                    persona_id=persona.id,
                    persona_nombre=persona.nombre,
                    ok=False,
                    error=str(e),
                )
            result.by_persona[persona.id] = pf

    # Agregados
    ok_feedbacks = [pf for pf in result.by_persona.values() if pf.ok and pf.feedback]
    if ok_feedbacks:
        # `nivel_conviccion` puede venir como string ("7") o faltar — coerce
        # defensivo (ver coerce_conviction): los no numéricos se EXCLUYEN de los
        # agregados en vez de contar como 0 o 10 (defaults antes inconsistentes).
        convictions = [
            c for c in (coerce_conviction(pf.feedback.get("nivel_conviccion")) for pf in ok_feedbacks)
            if c is not None
        ]
        result.avg_conviction = (sum(convictions) / len(convictions)) if convictions else None
        result.blocking_objections = [
            d
            for pf in ok_feedbacks
            if (_conv := coerce_conviction(pf.feedback.get("nivel_conviccion"))) is not None and _conv < 6
            for d in (pf.feedback.get("dudas_no_resueltas") or [])
        ]

    result.total_tokens = sum(
        (pf.metadata.get("input_tokens") or 0) + (pf.metadata.get("output_tokens") or 0)
        for pf in result.by_persona.values()
    )

    if len(ok_feedbacks) >= MIN_OK_PERSONAS:
        feedback_text = build_audience_merge_directive([
            {
                "persona_id": pf.persona_id,
                "persona_nombre": pf.persona_nombre,
                "feedback": pf.feedback,
                "ok": True,
            }
            for pf in ok_feedbacks
        ])
        # Cap defensivo — evita inflar Stage 3 cuando hay 5 personas verbosas
        if len(feedback_text) > MAX_FEEDBACK_TOKENS_CHARS:
            feedback_text = feedback_text[:MAX_FEEDBACK_TOKENS_CHARS] + "\n[…truncado]"
        result.audience_feedback_text = feedback_text
    else:
        logger.info(
            f"Audience test: solo {len(ok_feedbacks)}/{len(personas)} personas OK "
            f"(mínimo {MIN_OK_PERSONAS}). Stage 3 continuará sin feedback de audiencia."
        )

    return result
