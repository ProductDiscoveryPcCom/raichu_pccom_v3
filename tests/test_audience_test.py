"""
Tests del Audience Tester (Stage 2.5):
- config/audiencias.py: integridad de personas + auto-pick por arquetipo
- core/audience_test.py: orquestación paralela con mock generator
- prompts/audience.py: merge directive
- prompts/new_content.build_final_prompt_stage3: retrocompatibilidad cuando
  audience_feedback=None y inyección cuando se pasa.

Sin API keys — FakeGenerator local.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import pytest

from config.audiencias import (
    PERSONAS,
    PERSONAS_POR_ARQUETIPO,
    _pick_personas_for_arquetipo,
)
from core.audience_test import (
    AUDIENCE_MAX_PARALLEL,
    MIN_OK_PERSONAS,
    AudienceTestResult,
    PersonaFeedback,
    run_audience_test,
)
from prompts.audience import build_audience_merge_directive, build_audience_test_prompt


# ----------------------- FakeGenerator -----------------------

@dataclass
class FakeResult:
    success: bool
    content: str
    model: str = "fake-claude"
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {"input_tokens": 200, "output_tokens": 80}


class FakeGenerator:
    def __init__(self, responder: Callable[[str], FakeResult]):
        self.responder = responder
        self.calls: list = []
        self._lock = threading.Lock()

    def generate(self, prompt: str, **kwargs):
        with self._lock:
            self.calls.append({"prompt": prompt, **kwargs})
        base = self.responder(prompt)
        prefill = kwargs.get("prefill")
        if prefill and base.success:
            return FakeResult(True, prefill + base.content, model=base.model, metadata=base.metadata)
        return base


# ----------------------- Helpers -----------------------

DRAFT_HTML = """
<article class="contentGenerator__main">
  <h2>Mejores PC gaming 2026</h2>
  <p>Análisis del mercado actual de torres gaming.</p>
</article>
"""
KEYWORD = "pc gaming 2026"


def _feedback_payload(conviction: int = 7, veredicto: str = "si") -> str:
    """JSON SIN el '{' inicial — el prefill lo prepende."""
    return json.dumps({
        "nivel_conviccion": conviction,
        "dudas_no_resueltas": ["¿Dura 3 años?"],
        "fricciones_copy": [{"cita": "gama media-alta", "problema": "ambiguo"}],
        "sugerencias": ["Añadir tabla de FPS"],
        "veredicto_compra": veredicto,
        "razon_veredicto": "El análisis es claro y los precios competitivos.",
    })[1:]


def _default_responder(prompt: str) -> FakeResult:
    return FakeResult(True, _feedback_payload())


# ----------------------- config/audiencias -----------------------

def test_personas_tienen_todos_los_campos_no_vacios():
    assert len(PERSONAS) >= 5
    for pid, p in PERSONAS.items():
        assert p.id == pid
        assert p.nombre
        assert p.edad
        assert p.presupuesto
        assert p.contexto
        assert p.dolores
        assert p.objeciones
        assert p.criterios_decision


def test_mapeo_arquetipos_solo_referencia_ids_existentes():
    for code, persona_ids in PERSONAS_POR_ARQUETIPO.items():
        assert persona_ids, f"{code} tiene lista vacía"
        for pid in persona_ids:
            assert pid in PERSONAS, f"{code} → {pid} no existe"


def test_pick_personas_arquetipo_mapeado():
    out = _pick_personas_for_arquetipo("ARQ-7")
    assert set(out) == {"gamer_entry", "gamer_enthusiast"}


def test_pick_personas_arquetipo_amplio_arq4():
    out = _pick_personas_for_arquetipo("ARQ-4")
    assert set(out) == set(PERSONAS.keys())


def test_pick_personas_fallback_arquetipo_inexistente(caplog):
    with caplog.at_level(logging.INFO, logger="config.audiencias"):
        out = _pick_personas_for_arquetipo("ARQ-99-INEXISTENTE")
    assert set(out) == set(PERSONAS.keys())
    assert any("sin mapeo" in rec.message for rec in caplog.records)


# ----------------------- run_audience_test -----------------------

def test_run_audience_3_personas_todas_ok():
    gen = FakeGenerator(_default_responder)
    persona_ids = ["gamer_entry", "gamer_enthusiast", "creativo_pro"]
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=persona_ids,
        keyword=KEYWORD,
        generator=gen,
    )

    assert isinstance(result, AudienceTestResult)
    assert set(result.by_persona.keys()) == set(persona_ids)
    assert all(pf.ok for pf in result.by_persona.values())
    assert result.avg_conviction == pytest.approx(7.0)
    assert result.has_usable_feedback
    assert "convicción media" in result.audience_feedback_text.lower() \
        or "convicci" in result.audience_feedback_text.lower()


def test_run_audience_persona_levanta_excepcion_no_rompe_las_otras():
    def responder(prompt: str) -> FakeResult:
        if "Gamer entry-level" in prompt:
            raise RuntimeError("API caída")
        return _default_responder(prompt)

    gen = FakeGenerator(responder)
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "gamer_enthusiast", "creativo_pro"],
        keyword=KEYWORD,
        generator=gen,
    )

    assert not result.by_persona["gamer_entry"].ok
    assert result.by_persona["gamer_enthusiast"].ok
    assert result.by_persona["creativo_pro"].ok
    # 2 OK ≥ MIN_OK_PERSONAS → audience_feedback_text presente
    assert result.has_usable_feedback


def test_json_malformado_reintenta_con_temp_baja():
    attempts: Dict[str, int] = {"n": 0}

    def responder(prompt: str) -> FakeResult:
        if "Gamer entry-level" in prompt:
            attempts["n"] += 1
            if attempts["n"] == 1:
                return FakeResult(True, "esto no es JSON")
            return FakeResult(True, _feedback_payload())
        return _default_responder(prompt)

    gen = FakeGenerator(responder)
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "gamer_enthusiast"],
        keyword=KEYWORD,
        generator=gen,
    )

    assert result.by_persona["gamer_entry"].ok
    assert attempts["n"] == 2
    # Segunda llamada para gamer_entry debe haber bajado la temperatura
    gamer_calls = [c for c in gen.calls if "Gamer entry-level" in c["prompt"]]
    assert gamer_calls[1].get("temperature") == 0.3


def test_todas_las_personas_fallan_sin_feedback_usable():
    def responder(prompt: str) -> FakeResult:
        return FakeResult(False, "", metadata={"input_tokens": 0, "output_tokens": 0})

    gen = FakeGenerator(responder)
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "gamer_enthusiast"],
        keyword=KEYWORD,
        generator=gen,
    )

    assert all(not pf.ok for pf in result.by_persona.values())
    assert result.audience_feedback_text == ""
    assert not result.has_usable_feedback


def test_solo_una_persona_ok_no_alcanza_minimo():
    def responder(prompt: str) -> FakeResult:
        if "Gamer entry-level" in prompt:
            return _default_responder(prompt)
        return FakeResult(False, "")

    gen = FakeGenerator(responder)
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "gamer_enthusiast"],
        keyword=KEYWORD,
        generator=gen,
    )
    assert MIN_OK_PERSONAS == 2  # documenta umbral
    # 1 OK < MIN_OK → no feedback usable
    assert not result.has_usable_feedback


def test_prefill_se_usa_en_cada_llamada():
    gen = FakeGenerator(_default_responder)
    run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "creativo_pro"],
        keyword=KEYWORD,
        generator=gen,
    )
    for call in gen.calls:
        assert call.get("prefill") == "{"


def test_paralelismo_real_con_barrier():
    barrier = threading.Barrier(3)

    def slow_responder(prompt: str) -> FakeResult:
        barrier.wait(timeout=2.0)
        time.sleep(0.1)
        return _default_responder(prompt)

    gen = FakeGenerator(slow_responder)
    t0 = time.time()
    run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "gamer_enthusiast", "creativo_pro"],
        keyword=KEYWORD,
        generator=gen,
    )
    wall = time.time() - t0
    assert wall < 0.5, f"No parece paralelo (wall={wall:.2f}s)"


def test_blocking_objections_solo_de_baja_conviccion():
    def responder(prompt: str) -> FakeResult:
        if "Gamer entry-level" in prompt:
            return FakeResult(True, _feedback_payload(conviction=4, veredicto="talvez"))
        return FakeResult(True, _feedback_payload(conviction=8, veredicto="si"))

    gen = FakeGenerator(responder)
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["gamer_entry", "creativo_pro"],
        keyword=KEYWORD,
        generator=gen,
    )
    # Sólo gamer_entry (conv=4 < 6) aporta blocking_objections
    assert len(result.blocking_objections) >= 1
    assert "¿Dura 3 años?" in result.blocking_objections


def test_html_pegado_se_sanitiza():
    html_xss = (
        "<article class='contentGenerator__main'>"
        "<h2>Legítimo</h2>"
        "<script>alert(1)</script>"
        "<iframe src='evil'></iframe>"
        "<p>Texto sobre gaming.</p>"
        "</article>"
    )
    gen = FakeGenerator(_default_responder)
    run_audience_test(
        draft_html=html_xss,
        persona_ids=["gamer_entry"],
        keyword=KEYWORD,
        generator=gen,
    )
    prompt = gen.calls[0]["prompt"]
    assert "<script>" not in prompt
    assert "<iframe" not in prompt
    assert "Legítimo" in prompt


def test_max_parallel_documenta_techo():
    assert AUDIENCE_MAX_PARALLEL == 5


def test_run_audience_sin_personas_validas_no_lanza():
    gen = FakeGenerator(_default_responder)
    result = run_audience_test(
        draft_html=DRAFT_HTML,
        persona_ids=["persona_inexistente"],
        keyword=KEYWORD,
        generator=gen,
    )
    assert result.by_persona == {}
    assert not result.has_usable_feedback
    assert gen.calls == []


# ----------------------- prompts/audience -----------------------

def test_audience_test_prompt_contiene_persona_y_keyword():
    p = PERSONAS["gamer_entry"]
    prompt = build_audience_test_prompt("Texto del artículo", p, "pc gaming 2026")
    assert "Gamer entry-level" in prompt
    assert "pc gaming 2026" in prompt
    assert "Texto del artículo" in prompt
    assert "JSON" in prompt
    assert "Empieza tu respuesta con `{`" in prompt


def test_merge_directive_resume_correctamente():
    feedbacks = [
        {
            "persona_id": "gamer_entry",
            "persona_nombre": "Gamer entry-level",
            "ok": True,
            "feedback": {
                "nivel_conviccion": 4,
                "veredicto_compra": "talvez",
                "razon_veredicto": "No me convence el precio",
                "dudas_no_resueltas": ["¿Garantía?"],
                "fricciones_copy": [{"cita": "rendimiento medio", "problema": "ambiguo"}],
                "sugerencias": ["Añadir tabla FPS"],
            },
        },
        {
            "persona_id": "creativo_pro",
            "persona_nombre": "Creativo profesional",
            "ok": True,
            "feedback": {
                "nivel_conviccion": 9,
                "veredicto_compra": "si",
                "razon_veredicto": "Cumple mi workflow",
                "dudas_no_resueltas": [],
                "fricciones_copy": [],
                "sugerencias": [],
            },
        },
    ]
    text = build_audience_merge_directive(feedbacks)
    assert "2 personas" in text
    assert "convicción: 6.5/10" in text or "6.5/10" in text
    assert "Gamer entry-level" in text
    assert "¿Garantía?" in text
    assert "INSTRUCCIÓN PARA STAGE 3" in text


def test_merge_directive_sin_feedbacks_devuelve_vacio():
    assert build_audience_merge_directive([]) == ""
    assert build_audience_merge_directive([{"ok": False}]) == ""


# ----------------------- prompts/new_content (regresión + inyección) -----------------------

def test_stage3_prompt_sin_audience_feedback_es_retrocompatible():
    from prompts.new_content import build_final_prompt_stage3

    prompt = build_final_prompt_stage3(
        draft_content="<p>borrador</p>",
        analysis_feedback='{"problemas":[]}',
        keyword="pc gaming",
        target_length=1500,
    )
    assert "FEEDBACK DE AUDIENCIA SIMULADA" not in prompt
    assert "STAGE 2.5" not in prompt


def test_stage3_prompt_con_audience_feedback_inyecta_seccion():
    from prompts.new_content import build_final_prompt_stage3

    feedback = "[FEEDBACK DE AUDIENCIA SIMULADA — 3 personas testeadas]\nNivel medio: 6.5/10"
    prompt = build_final_prompt_stage3(
        draft_content="<p>borrador</p>",
        analysis_feedback='{"problemas":[]}',
        keyword="pc gaming",
        target_length=1500,
        audience_feedback=feedback,
    )
    assert "FEEDBACK DE AUDIENCIA SIMULADA" in prompt
    assert "STAGE 2.5" in prompt
    assert "6.5/10" in prompt


def test_stage3_rewrite_con_audience_feedback_via_config():
    from prompts.rewrite import build_rewrite_final_prompt_stage3

    feedback = "[FEEDBACK DE AUDIENCIA SIMULADA — test]\nMedia 6.0/10"
    prompt = build_rewrite_final_prompt_stage3(
        draft_content="<p>borrador</p>",
        corrections_json='{}',
        config={
            "target_length": 1500,
            "keyword": "x",
            "audience_feedback": feedback,
        },
    )
    assert "FEEDBACK DE AUDIENCIA SIMULADA" in prompt
    assert "6.0/10" in prompt


def test_stage3_rewrite_sin_audience_feedback_es_retrocompatible():
    from prompts.rewrite import build_rewrite_final_prompt_stage3

    prompt = build_rewrite_final_prompt_stage3(
        draft_content="<p>borrador</p>",
        corrections_json='{}',
        config={"target_length": 1500, "keyword": "x"},
    )
    assert "FEEDBACK DE AUDIENCIA SIMULADA" not in prompt
