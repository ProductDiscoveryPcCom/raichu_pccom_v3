"""
Tests del research web (OpenAI web search) + fallback a SERP.

No se hacen llamadas reales: se inyecta un cliente OpenAI mock con Responses API,
y se monkeypatchea utils.serp_research para el fallback.
"""
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from utils import web_research as wr
from utils.web_research import (
    WebResearchResult,
    research_with_openai,
    research_enriched,
    format_for_prompt,
    to_prompt_context,
)


def _mock_responses_client(output_text="resumen factual", sources=None, raises=None):
    client = MagicMock()
    resp = MagicMock()
    resp.output_text = output_text
    resp.model = "gpt-4.1-2025-04-14"
    items = []
    if sources:
        anns = []
        for u in sources:
            a = MagicMock()
            a.url = u
            anns.append(a)
        content = MagicMock()
        content.annotations = anns
        item = MagicMock()
        item.content = [content]
        items = [item]
    resp.output = items
    if raises is not None:
        client.responses.create.side_effect = raises
    else:
        client.responses.create.return_value = resp
    return client, resp


# ── research_with_openai ──────────────────────────────────────────────────

class TestResearchWithOpenAI:
    def test_success_returns_summary_and_sources(self):
        client, _ = _mock_responses_client(
            "El MacBook Air M5 trae chip M5.", sources=["https://a.com", "https://b.com"]
        )
        r = research_with_openai("portatiles 2026", client=client)
        assert r.success is True
        assert r.provider == "openai_web"
        assert "M5" in r.summary
        assert r.sources == ["https://a.com", "https://b.com"]

    def test_uses_web_search_tool(self):
        client, _ = _mock_responses_client("x")
        research_with_openai("kw", client=client)
        kwargs = client.responses.create.call_args.kwargs
        assert kwargs["tools"][0]["type"] in ("web_search_preview", "web_search")
        assert "input" in kwargs

    def test_tool_type_fallback_on_error(self):
        # Primer tipo de herramienta falla, el segundo funciona
        ok_resp = MagicMock()
        ok_resp.output_text = "ok con segundo tool"
        ok_resp.model = "gpt-4.1"
        ok_resp.output = []
        client = MagicMock()
        client.responses.create.side_effect = [RuntimeError("unknown tool web_search_preview"), ok_resp]
        r = research_with_openai("kw", client=client)
        assert r.success is True
        assert client.responses.create.call_count == 2

    def test_empty_output_fails(self):
        client, _ = _mock_responses_client(output_text="")
        r = research_with_openai("kw", client=client)
        assert r.success is False

    def test_exception_captured_not_propagated(self):
        client = MagicMock()
        client.responses.create.side_effect = RuntimeError("boom")
        r = research_with_openai("kw", client=client)
        assert r.success is False
        assert "boom" in r.error

    def test_no_responses_api_fails_gracefully(self):
        client = MagicMock(spec=[])  # sin atributo responses
        r = research_with_openai("kw", client=client)
        assert r.success is False
        assert "Responses API" in r.error


# ── format_for_prompt / to_prompt_context ─────────────────────────────────

class TestFormatting:
    def test_format_includes_heading_and_no_cite_note(self):
        r = WebResearchResult(success=True, summary="datos", sources=["https://x.com"], provider="openai_web")
        out = format_for_prompt(r)
        assert "INVESTIGACIÓN WEB" in out
        assert "datos" in out
        assert "NO las cites" in out  # las fuentes no deben citarse como enlaces

    def test_format_empty_when_unsuccessful(self):
        assert format_for_prompt(WebResearchResult(success=False)) == ""

    def test_to_prompt_context_serp_passthrough(self):
        # Para provider 'serp' el summary ya viene formateado: no se re-envuelve
        r = WebResearchResult(success=True, summary="## SERP ya formateado", provider="serp")
        assert to_prompt_context(r) == "## SERP ya formateado"

    def test_to_prompt_context_openai_wraps(self):
        r = WebResearchResult(success=True, summary="datos", provider="openai_web")
        assert "INVESTIGACIÓN WEB" in to_prompt_context(r)


# ── research_enriched: cadena con fallback ─────────────────────────────────

class TestResearchEnriched:
    def test_openai_primary_used_when_available(self, monkeypatch):
        monkeypatch.setattr(wr, "is_web_research_available", lambda: (True, ""))
        monkeypatch.setattr(
            wr, "research_with_openai",
            lambda kw: WebResearchResult(success=True, summary="web ok", provider="openai_web"),
        )
        r = research_enriched("kw")
        assert r.success is True
        assert r.provider == "openai_web"

    def test_falls_back_to_serp_when_openai_unavailable(self, monkeypatch):
        monkeypatch.setattr(wr, "is_web_research_available", lambda: (False, "sin key"))
        import utils.serp_research as serp
        fake = MagicMock()
        fake.success = True
        monkeypatch.setattr(serp, "research_serp", lambda kw: fake)
        monkeypatch.setattr(serp, "format_for_prompt", lambda res: "## SERP ctx")
        r = research_enriched("kw")
        assert r.success is True
        assert r.provider == "serp"
        assert r.summary == "## SERP ctx"

    def test_falls_back_to_serp_when_openai_fails(self, monkeypatch):
        monkeypatch.setattr(wr, "is_web_research_available", lambda: (True, ""))
        monkeypatch.setattr(
            wr, "research_with_openai",
            lambda kw: WebResearchResult(success=False, error="429", provider="openai_web"),
        )
        import utils.serp_research as serp
        fake = MagicMock(); fake.success = True
        monkeypatch.setattr(serp, "research_serp", lambda kw: fake)
        monkeypatch.setattr(serp, "format_for_prompt", lambda res: "## SERP ctx")
        r = research_enriched("kw")
        assert r.success is True
        assert r.provider == "serp"

    def test_both_fail_returns_unsuccessful(self, monkeypatch):
        monkeypatch.setattr(wr, "is_web_research_available", lambda: (False, "sin key"))
        import utils.serp_research as serp
        fake = MagicMock(); fake.success = False; fake.error = "sin resultados"
        monkeypatch.setattr(serp, "research_serp", lambda kw: fake)
        r = research_enriched("kw")
        assert r.success is False

    def test_empty_keyword(self):
        assert research_enriched("   ").success is False


# ── Wiring: pipeline + UI (source inspection) ──────────────────────────────

class TestWebResearchWiring:
    def test_pipeline_uses_research_enriched(self):
        src = Path("core/pipeline.py").read_text(encoding="utf-8")
        assert "research_enriched" in src
        assert "config.get('web_research'" in src

    def test_form_has_web_research_toggle(self):
        src = Path("ui/inputs.py").read_text(encoding="utf-8")
        assert "main_web_research" in src
        assert "'web_research': form_data.web_research" in src
