"""
Tests for R1.1 — _run_parallel_stage2 helper + fallback Haiku para validación dual.

No live API calls: usamos callables sintéticos que simulan los workers
de Claude y OpenAI, y la fixture mock_anthropic_client para el helper de Haiku.
"""
import inspect
import threading
import time

import pytest

from core.pipeline import _run_parallel_stage2, _haiku_secondary_analysis


def test_parallel_returns_both_when_dual_enabled():
    claude = lambda: "claude_ok"
    openai = lambda: ("oa_ok", {"tokens": 100}, {"time": 1.0})

    claude_payload, openai_payload = _run_parallel_stage2(claude, openai, dual_enabled=True)

    assert claude_payload[0] is True
    assert claude_payload[1] == "claude_ok"
    assert claude_payload[2] is None
    assert claude_payload[3] >= 0

    assert openai_payload is not None
    assert openai_payload[0] is True
    assert openai_payload[1] == ("oa_ok", {"tokens": 100}, {"time": 1.0})


def test_parallel_skips_openai_when_dual_disabled():
    claude = lambda: "claude_ok"
    openai_called = {"flag": False}

    def openai():
        openai_called["flag"] = True
        return "should_not_run"

    claude_payload, openai_payload = _run_parallel_stage2(claude, openai, dual_enabled=False)

    assert claude_payload[0] is True
    assert openai_payload is None
    assert openai_called["flag"] is False


def test_parallel_skips_when_openai_callable_is_none():
    claude_payload, openai_payload = _run_parallel_stage2(
        lambda: "ok", None, dual_enabled=True,
    )
    assert claude_payload[0] is True
    assert openai_payload is None


def test_parallel_captures_claude_exception():
    def claude():
        raise RuntimeError("claude exploded")

    openai = lambda: "ok"

    claude_payload, openai_payload = _run_parallel_stage2(claude, openai, dual_enabled=True)

    assert claude_payload[0] is False
    assert claude_payload[1] is None
    assert isinstance(claude_payload[2], RuntimeError)
    # OpenAI no debe verse afectado
    assert openai_payload[0] is True
    assert openai_payload[1] == "ok"


def test_parallel_captures_openai_exception():
    def openai():
        raise ValueError("openai exploded")

    claude = lambda: "claude_ok"

    claude_payload, openai_payload = _run_parallel_stage2(claude, openai, dual_enabled=True)

    assert claude_payload[0] is True
    assert claude_payload[1] == "claude_ok"
    assert openai_payload[0] is False
    assert isinstance(openai_payload[2], ValueError)


def test_parallel_runs_concurrently():
    """Wall time debe ser ~max(claude, openai), no la suma."""
    barrier = threading.Barrier(2, timeout=2.0)

    def slow_claude():
        barrier.wait()  # confirma que ambos workers están vivos a la vez
        time.sleep(0.2)
        return "c"

    def slow_openai():
        barrier.wait()
        time.sleep(0.2)
        return "o"

    t0 = time.time()
    claude_payload, openai_payload = _run_parallel_stage2(slow_claude, slow_openai, dual_enabled=True)
    wall = time.time() - t0

    assert claude_payload[0] is True and openai_payload[0] is True
    # Si fuera secuencial: ~0.4s. En paralelo: ~0.2s. Margen generoso para CI.
    assert wall < 0.35, f"Wall {wall:.2f}s sugiere ejecución secuencial"


# ============================================================================
# Fallback Haiku para validación dual — _haiku_secondary_analysis
# ============================================================================

class TestHaikuSecondaryAnalysis:
    """El helper devuelve la MISMA forma que openai_client.generate_dual_analysis:
    (ok, analysis, metadata). Es un fallback: no debe propagar excepciones."""

    def test_returns_provider_haiku_on_success(self, mock_anthropic_client):
        mock_anthropic_client.set_response('{"problemas": [], "puntuacion_general": 6}')
        from core.generator import ContentGenerator

        ok, analysis, meta = _haiku_secondary_analysis(
            "prompt de análisis",
            5000,
            api_key="sk-ant-dummy",
            model="claude-haiku-4-5-20251001",
            content_generator_cls=ContentGenerator,
        )

        assert ok is True
        assert '"problemas"' in analysis
        assert meta["provider"] == "haiku"
        assert "tokens" in meta

    def test_no_api_key_returns_unavailable(self):
        from core.generator import ContentGenerator

        ok, analysis, meta = _haiku_secondary_analysis(
            "prompt", 5000,
            api_key="",
            model="claude-haiku-4-5-20251001",
            content_generator_cls=ContentGenerator,
        )
        assert ok is False
        assert analysis == ""
        assert "error" in meta

    def test_none_generator_returns_unavailable(self):
        ok, analysis, meta = _haiku_secondary_analysis(
            "prompt", 5000,
            api_key="sk-ant-dummy",
            model="claude-haiku-4-5-20251001",
            content_generator_cls=None,
        )
        assert ok is False
        assert "error" in meta

    def test_exception_is_captured_not_propagated(self):
        class _Boom:
            def __init__(self, *a, **kw):
                raise RuntimeError("constructor explotó")

        ok, analysis, meta = _haiku_secondary_analysis(
            "prompt", 5000,
            api_key="sk-ant-dummy",
            model="claude-haiku-4-5-20251001",
            content_generator_cls=_Boom,
        )
        assert ok is False
        assert "constructor explotó" in meta["error"]

    def test_uses_critical_system_not_brand_tone(self, mock_anthropic_client):
        """El segundo análisis debe pedir un revisor crítico (no el tono de marca)."""
        from core.generator import ContentGenerator
        from core.pipeline import _DUAL_FALLBACK_SYSTEM

        _haiku_secondary_analysis(
            "prompt", 5000,
            api_key="sk-ant-dummy",
            model="claude-haiku-4-5-20251001",
            content_generator_cls=ContentGenerator,
        )
        # El system prompt se envía como lista de bloques (con cache_control).
        # Debe contener el system crítico, no el tono de marca.
        _, kwargs = mock_anthropic_client.messages.create.call_args
        system_arg = kwargs.get("system")
        assert isinstance(system_arg, list) and system_arg
        assert system_arg[0]["text"] == _DUAL_FALLBACK_SYSTEM


# ============================================================================
# Wiring de la orquestación Stage 2 (source-inspection)
#
# El bloque de orquestación vive dentro de execute_generation_pipeline, que
# usa st.spinner/st.session_state → no es testeable por mock unitario. Igual
# que TestTruncationGuard/TestDynamicTokenBudget, verificamos el cableado por
# inspección de fuente.
# ============================================================================

class TestDualFallbackWiring:
    @pytest.fixture(scope="class")
    def pipeline_src(self):
        import core.pipeline as _p
        return inspect.getsource(_p)

    def test_secondary_is_openai_when_available_else_haiku(self, pipeline_src):
        assert "use_openai_secondary = openai_available" in pipeline_src
        assert "secondary_provider = 'openai' if use_openai_secondary else 'haiku'" in pipeline_src

    def test_haiku_worker_wired_as_secondary_callable(self, pipeline_src):
        assert "_haiku_worker" in pipeline_src
        assert "secondary_callable = _haiku_worker" in pipeline_src
        assert "_haiku_secondary_analysis(" in pipeline_src

    def test_openai_failure_backstops_to_haiku(self, pipeline_src):
        # El backstop secuencial solo se activa si el secundario era OpenAI y falló
        assert "if secondary_analysis is None and use_openai_secondary and haiku_available:" in pipeline_src

    def test_merge_passes_secondary_provider(self, pipeline_src):
        assert "secondary_provider=secondary_provider" in pipeline_src

    def test_dual_enabled_covers_haiku(self, pipeline_src):
        assert "dual_enabled = openai_available or haiku_available" in pipeline_src
