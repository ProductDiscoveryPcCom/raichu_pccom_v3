"""
Tests for R1.1 — _run_parallel_stage2 helper.

No live API calls: usamos callables sintéticos que simulan los workers
de Claude y OpenAI.
"""
import threading
import time

import pytest

from core.pipeline import _run_parallel_stage2


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
