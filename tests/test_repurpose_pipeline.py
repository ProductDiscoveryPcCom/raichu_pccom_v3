"""
Tests del orquestador del Repurposer (core/repurpose_pipeline.py).

Usa un FakeGenerator que respeta la firma de `ContentGenerator.generate(...)`
y devuelve respuestas pre-configuradas por asset. Sin API keys.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from core.repurpose_pipeline import (
    REPURPOSE_MAX_PARALLEL,
    RepurposeResult,
    execute_repurpose_pipeline,
    regenerate_single_asset,
)


# ----------------------- Fake generator (sin SDK) -----------------------

@dataclass
class FakeResult:
    success: bool
    content: str
    model: str = "fake-claude"
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {"input_tokens": 100, "output_tokens": 50}


class FakeGenerator:
    """Stub minimal de ContentGenerator. Para cada llamada a generate(),
    consulta `responder` que decide el output mirando el prompt."""

    def __init__(self, responder: Callable[[str], FakeResult]):
        self.responder = responder
        self.calls: list = []
        self._lock = threading.Lock()

    def generate(self, prompt: str, **kwargs) -> FakeResult:
        with self._lock:
            self.calls.append({"prompt": prompt, **kwargs})
        return self.responder(prompt)


# ----------------------- Fixtures de HTML -----------------------

HTML_CON_FAQS = """
<article class="contentGenerator__main">
  <h2>Mejores PC gaming 2026</h2>
  <p>Análisis de las mejores torres gaming del mercado actual.</p>
</article>
<article class="contentGenerator__faqs">
  <h3>¿Qué procesador es mejor?</h3><p>Ryzen 7 o Intel i5 de última generación.</p>
</article>
"""

KEYWORD = "pc gaming 2026"


# ----------------------- Helpers responders -----------------------

def _rsa_json() -> str:
    return json.dumps({
        "titles": [f"PC Gaming {i:02d}" for i in range(15)],
        "descriptions": [f"Descripción detallada {i} con CTA." for i in range(4)],
    })


def _newsletter_json() -> str:
    return json.dumps({
        "subject": "Nueva guía PC gaming",
        "preheader": "Descubre los mejores PCs",
        "body": " ".join(["palabra"] * 60),
        "cta_text": "Ver guía",
    })


def _x_thread_json() -> str:
    return json.dumps({"tweets": [{"n": i + 1, "text": f"Tweet PC gaming 2026 #{i}"} for i in range(10)]})


def _linkedin_json() -> str:
    return json.dumps({"slides": [{"n": i + 1, "title": f"Slide {i}", "body_markdown": "..."} for i in range(6)]})


def _featured_snippet_json() -> str:
    return json.dumps({"question": "¿Qué es un PC gaming?", "answer": " ".join(["palabra"] * 50)})


def _meta_desc_text() -> str:
    return "Descubre los mejores PC gaming 2026 con un análisis completo de cada componente, precios actualizados y comparativa entre modelos. Encuentra el ideal."


def _serp_title_text() -> str:
    return "PC Gaming 2026 | Comparativa PcComponentes"


def _whatsapp_text() -> str:
    return "📢 Nueva guía PC gaming 2026 👉 Mira las mejores torres del año {url}"


def _route_response(prompt: str) -> FakeResult:
    """Decide qué responder mirando marcadores únicos del prompt."""
    if "META DESCRIPTION" in prompt:
        return FakeResult(True, _meta_desc_text())
    if "TÍTULO SERP" in prompt:
        return FakeResult(True, _serp_title_text())
    if "GOOGLE RSA" in prompt:
        # Sin el '{' inicial — el prefill lo prepende
        return FakeResult(True, _rsa_json()[1:])
    if "NEWSLETTER" in prompt:
        return FakeResult(True, _newsletter_json()[1:])
    if "HILO X" in prompt:
        return FakeResult(True, _x_thread_json()[1:])
    if "CARRUSEL LINKEDIN" in prompt:
        return FakeResult(True, _linkedin_json()[1:])
    if "FEATURED SNIPPET" in prompt:
        return FakeResult(True, _featured_snippet_json()[1:])
    if "WHATSAPP" in prompt:
        return FakeResult(True, _whatsapp_text())
    return FakeResult(False, "", metadata={"input_tokens": 0, "output_tokens": 0})


def _simulate_prefill(prompt: str, fake: FakeResult, *, kwargs: Dict[str, Any]) -> FakeResult:
    """Aplica el prefill como lo haría call_claude_api (prepend al content)."""
    prefill = kwargs.get("prefill")
    if prefill and fake.success:
        return FakeResult(True, prefill + fake.content, model=fake.model, metadata=fake.metadata)
    return fake


class PrefillAwareGenerator(FakeGenerator):
    """Simula el comportamiento de prefill que tendría call_claude_api."""

    def generate(self, prompt: str, **kwargs) -> FakeResult:
        with self._lock:
            self.calls.append({"prompt": prompt, **kwargs})
        base = self.responder(prompt)
        return _simulate_prefill(prompt, base, kwargs=kwargs)


# ----------------------- Tests -----------------------

def test_pipeline_genera_los_assets_pedidos_y_todos_ok():
    gen = PrefillAwareGenerator(_route_response)

    results = execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["meta_description", "serp_title", "rsa", "newsletter", "x_thread", "linkedin_carousel", "featured_snippet", "whatsapp", "jsonld"],
        config={"keyword": KEYWORD},
        generator=gen,
    )

    assert set(results.keys()) == {
        "meta_description", "serp_title", "rsa", "newsletter",
        "x_thread", "linkedin_carousel", "featured_snippet", "whatsapp", "jsonld",
    }
    for asset_id, res in results.items():
        assert res.ok, f"{asset_id} falló: errors={res.validation_errors}, error={res.error}"


def test_jsonld_no_llama_al_generator():
    gen = PrefillAwareGenerator(_route_response)

    results = execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["meta_description", "jsonld"],
        config={"keyword": KEYWORD},
        generator=gen,
    )

    assert len(gen.calls) == 1, "Solo meta_description debería llamar al LLM"
    assert gen.calls[0]["prompt"].count("META DESCRIPTION") == 1
    assert results["jsonld"].ok
    assert results["jsonld"].metadata["source"] == "deterministic_builder"


def test_asset_fallido_no_afecta_a_los_demas():
    def responder(prompt: str) -> FakeResult:
        if "META DESCRIPTION" in prompt:
            raise RuntimeError("simulated API down")
        return _route_response(prompt)

    gen = PrefillAwareGenerator(responder)

    results = execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["meta_description", "serp_title", "whatsapp"],
        config={"keyword": KEYWORD},
        generator=gen,
    )

    assert not results["meta_description"].ok
    assert "simulated API down" in results["meta_description"].error
    assert results["serp_title"].ok
    assert results["whatsapp"].ok


def test_json_malformado_reintenta_con_temp_baja():
    attempts: Dict[str, int] = {"n": 0}

    def responder(prompt: str) -> FakeResult:
        if "GOOGLE RSA" in prompt:
            attempts["n"] += 1
            if attempts["n"] == 1:
                return FakeResult(True, "esto no es JSON")
            return FakeResult(True, _rsa_json()[1:])
        return _route_response(prompt)

    gen = PrefillAwareGenerator(responder)
    results = execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["rsa"],
        config={"keyword": KEYWORD},
        generator=gen,
    )

    assert results["rsa"].ok, results["rsa"].validation_errors
    assert attempts["n"] == 2
    assert results["rsa"].metadata["attempts"] == 2

    # Verificamos que el segundo intento bajó la temperatura
    second_temp = gen.calls[1].get("temperature")
    assert second_temp == 0.3


def test_prefill_se_usa_en_assets_json():
    gen = PrefillAwareGenerator(_route_response)
    execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["rsa", "meta_description"],
        config={"keyword": KEYWORD},
        generator=gen,
    )
    # En la llamada del RSA tiene que aparecer prefill='{'; en meta_description no
    rsa_call = next(c for c in gen.calls if "GOOGLE RSA" in c["prompt"])
    meta_call = next(c for c in gen.calls if "META DESCRIPTION" in c["prompt"])
    assert rsa_call.get("prefill") == "{"
    assert meta_call.get("prefill") is None


def test_html_pegado_se_sanitiza_antes_de_inyectar():
    html_malo = (
        "<article class='contentGenerator__main'>"
        "<h2>Título legítimo</h2>"
        "<script>alert('xss')</script>"
        "<iframe src='http://malo'></iframe>"
        "<a onclick=\"doSomething()\" href=\"javascript:steal()\">link</a>"
        "<p>Texto normal sobre PC gaming.</p>"
        "</article>"
    )
    gen = PrefillAwareGenerator(_route_response)
    execute_repurpose_pipeline(
        article_html=html_malo,
        assets_requested=["meta_description"],
        config={"keyword": KEYWORD},
        generator=gen,
    )
    prompt = gen.calls[0]["prompt"]
    # Nada del payload debe haber llegado al prompt
    assert "<script>" not in prompt
    assert "alert" not in prompt
    assert "<iframe" not in prompt
    assert "onclick" not in prompt
    assert "javascript:" not in prompt
    # Pero el texto legítimo sí
    assert "Título legítimo" in prompt
    assert "PC gaming" in prompt


def test_paralelismo_real_con_barrier():
    """Verifica que los assets LLM efectivamente se ejecutan en paralelo."""
    barrier = threading.Barrier(3)

    def slow_responder(prompt: str) -> FakeResult:
        barrier.wait(timeout=2.0)
        time.sleep(0.1)
        return _route_response(prompt)

    gen = PrefillAwareGenerator(slow_responder)
    t0 = time.time()
    results = execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["meta_description", "serp_title", "whatsapp"],
        config={"keyword": KEYWORD},
        generator=gen,
    )
    wall = time.time() - t0

    assert all(r.ok for r in results.values())
    # Si fueran secuenciales: ~0.3s. En paralelo: ~0.1s + overhead.
    assert wall < 0.5, f"No parece paralelo (wall={wall:.2f}s)"


def test_regenerate_single_asset_atajo():
    gen = PrefillAwareGenerator(_route_response)
    result = regenerate_single_asset(
        asset_id="meta_description",
        article_html=HTML_CON_FAQS,
        config={"keyword": KEYWORD},
        generator=gen,
    )
    assert isinstance(result, RepurposeResult)
    assert result.ok
    assert len(gen.calls) == 1


def test_asset_no_soportado_se_marca_unsupported():
    gen = PrefillAwareGenerator(_route_response)
    results = execute_repurpose_pipeline(
        article_html=HTML_CON_FAQS,
        assets_requested=["asset_inventado", "meta_description"],
        config={"keyword": KEYWORD},
        generator=gen,
    )
    assert not results["asset_inventado"].ok
    assert results["asset_inventado"].error == "unsupported"
    assert results["meta_description"].ok


def test_constante_max_parallel_no_supera_techo():
    assert REPURPOSE_MAX_PARALLEL == 7
