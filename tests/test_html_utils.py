"""
Tests for utils/html_utils.py — word counting, HTML validation, AI detection.
"""
from utils.html_utils import (
    count_words_in_html,
    strip_html_tags,
    extract_html_content,
    validate_html_structure,
    detect_ai_phrases,
)


# ---------------------------------------------------------------------------
# count_words_in_html
# ---------------------------------------------------------------------------

def test_count_words_basic():
    assert count_words_in_html("<p>one two three</p>") == 3
    assert count_words_in_html("<div><p>hello</p><p>world</p></div>") == 2


def test_count_words_empty():
    assert count_words_in_html("") == 0
    assert count_words_in_html(None) == 0


def test_count_words_entities():
    # &amp; and &ndash; are replaced with spaces, not counted as words
    result = count_words_in_html("<p>one &amp; two &ndash; three</p>")
    assert result == 3


# ---------------------------------------------------------------------------
# strip_html_tags
# ---------------------------------------------------------------------------

def test_strip_html_tags():
    assert strip_html_tags("<h1>Title</h1><p>Body text</p>") == "Title Body text"
    assert strip_html_tags("") == ""
    assert strip_html_tags(None) == ""


# ---------------------------------------------------------------------------
# extract_html_content
# ---------------------------------------------------------------------------

def test_extract_html_content_strips_markdown(markdown_wrapped_html):
    result = extract_html_content(markdown_wrapped_html)
    assert "```" not in result
    assert "<div" in result
    assert "<p>Hello world</p>" in result


def test_extract_html_content_clean_passthrough():
    clean = "<article><h2>Test</h2></article>"
    assert extract_html_content(clean) == clean


def test_extract_html_content_empty():
    assert extract_html_content("") == ""
    assert extract_html_content(None) == ""


# ---------------------------------------------------------------------------
# validate_html_structure
# ---------------------------------------------------------------------------

def test_validate_html_structure(sample_html):
    result = validate_html_structure(sample_html)
    assert result["has_article"] is True
    assert result["css_has_root"] is True
    assert result["no_markdown"] is True
    assert result["has_table"] is True
    assert result["has_callout"] is True
    assert result["has_toc"] is True
    assert result["has_verdict_box"] is True
    assert result["kicker_uses_span"] is True


def test_validate_html_structure_empty():
    result = validate_html_structure("")
    assert result["has_article"] is False
    assert result["has_table"] is False
    assert result["no_markdown"] is True  # no markdown in empty string


# ---------------------------------------------------------------------------
# detect_ai_phrases
# ---------------------------------------------------------------------------

def test_detect_ai_phrases(sample_html_with_ai_phrases):
    found = detect_ai_phrases(sample_html_with_ai_phrases)
    assert len(found) >= 3
    phrases = [f["phrase"] for f in found]
    assert "En el mundo actual..." in phrases
    assert "Sin lugar a dudas..." in phrases
    assert "Ofrece una experiencia..." in phrases
    # Each detection has required keys
    for item in found:
        assert "phrase" in item
        assert "context" in item


def test_detect_ai_phrases_clean(sample_html):
    found = detect_ai_phrases(sample_html)
    assert found == []
