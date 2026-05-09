"""Tests del fallback regex de sanitize_html (R3.8)."""
import pytest

from utils import html_utils


@pytest.fixture
def force_regex_fallback(monkeypatch):
    """Forzar el fallback regex haciendo que BeautifulSoup raise ParserRejectedMarkup."""
    import bs4

    def boom(*args, **kwargs):
        raise bs4.ParserRejectedMarkup("forced for test")

    monkeypatch.setattr("utils.html_utils.BeautifulSoup", boom)
    yield


@pytest.mark.parametrize("payload,must_not_contain", [
    ("<iframe src='evil'></iframe>X", "<iframe"),
    ("<img onerror='alert(1)' src=x>", "onerror"),
    ("<svg onload='alert(1)'></svg>X", "<svg"),
    ("<object data='evil.swf'></object>X", "<object"),
    ("<embed src='evil'>X", "<embed"),
    ("<button onclick='x'>Y</button>", "<button"),
    ("<!-- evil --><p>ok</p>", "<!--"),
    ('<div onclick="x">y</div>', "onclick"),
    ("<div onmouseover='x'>y</div>", "onmouseover"),
    ("<applet code='evil'></applet>", "<applet"),
    ("<form action='/evil'><input name=x></form>", "<form"),
    ("<meta http-equiv='refresh'>", "<meta"),
])
def test_regex_fallback_blocks_xss_vectors(force_regex_fallback, payload, must_not_contain):
    out = html_utils.sanitize_html(payload)
    assert must_not_contain.lower() not in out.lower()


def test_regex_fallback_preserves_safe_html(force_regex_fallback):
    safe = "<p>Hola <strong>mundo</strong></p>"
    out = html_utils.sanitize_html(safe)
    assert "<p>" in out
    assert "<strong>" in out
    assert "mundo" in out


def test_regex_fallback_preserves_text_around_dangerous_tags(force_regex_fallback):
    payload = "antes<iframe src='x'></iframe>despues"
    out = html_utils.sanitize_html(payload)
    assert "<iframe" not in out.lower()
    assert "antes" in out
    assert "despues" in out


def test_bs4_not_available_uses_regex_fallback(monkeypatch):
    """Mismo cubrimiento cuando _bs4_available is False."""
    monkeypatch.setattr(html_utils, "_bs4_available", False)
    out = html_utils.sanitize_html("<iframe src='x'></iframe>OK")
    assert "<iframe" not in out.lower()
    assert "OK" in out


def test_regex_fallback_event_handler_no_quotes(force_regex_fallback):
    """Event handlers sin comillas también se eliminan."""
    payload = "<div onclick=alert(1)>y</div>"
    out = html_utils.sanitize_html(payload)
    assert "onclick" not in out.lower()


def test_regex_fallback_handles_self_closing_dangerous_tags(force_regex_fallback):
    payload = "<input type='text' name='x'/>OK<base href='evil'/>END"
    out = html_utils.sanitize_html(payload)
    assert "<input" not in out.lower()
    assert "<base" not in out.lower()
    assert "OK" in out
    assert "END" in out
