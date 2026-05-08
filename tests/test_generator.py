"""
Tests for core/generator.py — GenerationResult, extract_html_content, validate_response.
No live API calls.
"""
from core.generator import (
    GenerationResult,
    _sleep_with_jitter,
    extract_html_content,
    validate_response,
)


# ---------------------------------------------------------------------------
# GenerationResult dataclass
# ---------------------------------------------------------------------------

def test_generation_result_defaults():
    result = GenerationResult(
        success=True,
        content="<p>test</p>",
        stage=1,
        model="claude-sonnet-4-20250514",
        tokens_used=100,
        generation_time=1.5,
    )
    assert result.success is True
    assert result.content == "<p>test</p>"
    assert result.stage == 1
    assert result.model == "claude-sonnet-4-20250514"
    assert result.tokens_used == 100
    assert result.generation_time == 1.5
    assert result.error is None
    assert result.metadata == {}


def test_generation_result_with_error():
    result = GenerationResult(
        success=False,
        content="",
        stage=2,
        model="claude-sonnet-4-20250514",
        tokens_used=0,
        generation_time=0.1,
        error="Rate limit exceeded",
        metadata={"retry_count": 3},
    )
    assert result.success is False
    assert result.error == "Rate limit exceeded"
    assert result.metadata == {"retry_count": 3}


# ---------------------------------------------------------------------------
# extract_html_content
# ---------------------------------------------------------------------------

def test_extract_html_content():
    # Strips markdown wrappers
    wrapped = '```html\n<div class="test"><p>Hello</p></div>\n```'
    result = extract_html_content(wrapped)
    assert "```" not in result
    assert '<div class="test">' in result

    # Clean HTML passes through
    clean = "<article><h2>Title</h2></article>"
    assert extract_html_content(clean) == clean

    # Text before HTML is stripped
    mixed = 'Here is the HTML:\n<div><p>content</p></div>'
    result = extract_html_content(mixed)
    assert result.startswith("<div>")

    # Empty input
    assert extract_html_content("") == ""


# ---------------------------------------------------------------------------
# validate_response
# ---------------------------------------------------------------------------

def test_validate_response():
    html = (
        '<article class="contentGenerator__main">'
        "<h2>Titulo principal</h2>"
        "<p>" + " ".join(["palabra"] * 150) + "</p>"
        "</article>"
    )
    result = validate_response(html)
    assert result["is_valid"] is True
    assert result["has_html"] is True
    assert result["has_article"] is True
    assert result["has_headings"] is True
    assert result["word_count"] >= 100
    assert result["errors"] == []


def test_validate_response_empty():
    result = validate_response("")
    assert result["has_html"] is False
    assert result["has_article"] is False
    assert result["has_headings"] is False
    assert result["word_count"] == 0
    assert "No se detectó contenido HTML" in result["warnings"]
    assert any("Contenido muy corto" in w for w in result["warnings"])


# ---------------------------------------------------------------------------
# _sleep_with_jitter (R2.1)
# ---------------------------------------------------------------------------

def test_sleep_with_jitter_within_bounds(monkeypatch):
    """Jitter debe estar en [delay, delay*1.1] cuando jitter_ratio=0.1."""
    captured = {}

    def fake_uniform(a, b):
        captured["uniform_args"] = (a, b)
        return b  # peor caso: jitter máximo

    def fake_sleep(seconds):
        captured["slept"] = seconds

    monkeypatch.setattr("core.generator.random.uniform", fake_uniform)
    monkeypatch.setattr("core.generator.time.sleep", fake_sleep)

    _sleep_with_jitter(10.0)

    assert captured["uniform_args"] == (0, 1.0)
    assert 10.0 <= captured["slept"] <= 11.0


def test_sleep_with_jitter_zero_delay(monkeypatch):
    """delay=0 no debe llamar a time.sleep ni a random.uniform."""
    called = {"sleep": False, "uniform": False}

    def fake_sleep(seconds):
        called["sleep"] = True

    def fake_uniform(a, b):
        called["uniform"] = True
        return 0

    monkeypatch.setattr("core.generator.time.sleep", fake_sleep)
    monkeypatch.setattr("core.generator.random.uniform", fake_uniform)

    _sleep_with_jitter(0)

    assert called["sleep"] is False
    assert called["uniform"] is False


def test_sleep_with_jitter_custom_ratio(monkeypatch):
    """jitter_ratio personalizado modifica el upper bound."""
    captured = {}

    def fake_uniform(a, b):
        captured["range"] = (a, b)
        return 0.0

    def fake_sleep(s):
        captured["slept"] = s

    monkeypatch.setattr("core.generator.random.uniform", fake_uniform)
    monkeypatch.setattr("core.generator.time.sleep", fake_sleep)

    _sleep_with_jitter(8.0, jitter_ratio=0.25)

    assert captured["range"] == (0, 2.0)
    assert captured["slept"] == 8.0
