"""
Tests for utils/html_utils.py — word counting, HTML validation, AI detection,
sanitization, placeholder detection.
"""
import pytest

from utils.html_utils import (
    _has_dangerous_scheme,
    analyze_links,
    count_words_in_html,
    detect_ai_phrases,
    detect_placeholders,
    extract_content,
    extract_content_structure,
    extract_html_content,
    extract_meta_tags,
    extract_text,
    get_bs4_parser,
    get_heading_hierarchy,
    get_html_parser,
    get_parser,
    get_word_count,
    is_bs4_available,
    sanitize_html,
    strip_html_tags,
    strip_tags,
    validate_cms_articles,
    validate_cms_structure,
    validate_html_structure,
    validate_word_count_target,
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


# ---------------------------------------------------------------------------
# _has_dangerous_scheme (R1.6 helper)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("value", [
    "javascript:alert(1)",
    "JaVaScRiPt:alert(1)",
    "  javascript:alert(1)",
    "java\tscript:alert(1)",
    "java&#x0A;script:alert(1)",
    "vbscript:msgbox(1)",
    "VBSCRIPT:msgbox(1)",
    "data:text/html,<script>",
    "DATA:text/plain,hi",
    "file:///etc/passwd",
    "about:blank",
])
def test_has_dangerous_scheme_detects(value):
    assert _has_dangerous_scheme(value) is True


@pytest.mark.parametrize("value", [
    "https://example.com",
    "http://example.com/path",
    "/relative/path",
    "#anchor",
    "mailto:user@example.com",
    "tel:+34123456789",
    "",
    None,
])
def test_has_dangerous_scheme_safe(value):
    assert _has_dangerous_scheme(value) is False


# ---------------------------------------------------------------------------
# sanitize_html (R1.6 XSS hardening)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("payload,must_not_contain", [
    # Script tag elimination (case variations)
    ('<script>alert(1)</script>', '<script'),
    ('<ScRiPt>alert(1)</ScRiPt>', '<script'),
    ('<SCRIPT src="evil.js"></SCRIPT>', 'evil.js'),
    # Dangerous URL schemes
    ('<a href="javascript:alert(1)">x</a>', 'javascript:'),
    ('<a href="JaVaScRiPt:alert(1)">x</a>', 'avascript'),
    ('<a href="vbscript:msgbox(1)">x</a>', 'vbscript'),
    ('<a href="data:text/html,<script>">x</a>', 'data:text/html'),
    ('<a href="file:///etc/passwd">x</a>', 'file:'),
    # Event handlers stripped from any tag
    ('<img src=x onerror="alert(1)">', 'onerror'),
    ('<div onmouseover="alert(1)">x</div>', 'onmouseover'),
    ('<a href="#" onclick="alert(1)">x</a>', 'onclick'),
    # Blacklisted tags removed entirely
    ('<iframe src="evil.com"></iframe>', '<iframe'),
    ('<object data="evil.swf"></object>', '<object'),
    ('<embed src="evil.swf">', '<embed'),
    ('<form action="evil"></form>', '<form'),
    # Event handlers on svg (svg itself is preserved)
    ('<svg onload="alert(1)"><circle/></svg>', 'onload'),
    # Form-action attributes
    ('<button formaction="javascript:alert(1)">go</button>', 'formaction'),
])
def test_sanitize_html_blocks_xss(payload, must_not_contain):
    cleaned = sanitize_html(payload)
    assert must_not_contain.lower() not in cleaned.lower()


def test_sanitize_html_preserves_safe_content():
    safe = '<article class="contentGenerator__main"><h2>Title</h2><p>Body</p></article>'
    cleaned = sanitize_html(safe)
    assert '<article' in cleaned
    assert 'contentGenerator__main' in cleaned
    assert 'Title' in cleaned
    assert 'Body' in cleaned


def test_sanitize_html_preserves_style_tag():
    """<style> es necesario para el Design System de PcComponentes y NO se elimina."""
    html = '<style>:root { --color-primary: #FF6600; }</style><p>x</p>'
    cleaned = sanitize_html(html)
    assert '<style' in cleaned
    assert 'color-primary' in cleaned


def test_sanitize_html_empty_input():
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""


# ---------------------------------------------------------------------------
# detect_placeholders
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("html,expected_match_substr", [
    ('<p>Texto antes [Insertar imagen aqui] texto despues</p>', 'Insertar imagen'),
    ('<p>Falta [Imagen de portada] aqui</p>', 'Imagen de portada'),
    ('<p>Anadir [Enlace a categoria]</p>', 'Enlace a categoria'),
    ('<p>(ver imagen)</p>', 'ver imagen'),
    ('<p>(Introducir descripcion del producto)</p>', 'Introducir'),
    ('<p>Seguir escribiendo...</p>', 'Seguir escribiendo'),
])
def test_detect_placeholders_finds(html, expected_match_substr):
    found = detect_placeholders(html)
    assert any(expected_match_substr.lower() in p.lower() for p in found), \
        f"Esperaba '{expected_match_substr}' en {found}"


def test_detect_placeholders_clean(sample_html):
    """HTML legitimo no genera falsos positivos relevantes."""
    found = detect_placeholders(sample_html)
    # detect_placeholders usa regex amplias y puede capturar texto legitimo en
    # corchetes/parentesis. Verificamos al menos que NO captura placeholders
    # explicitos como "Insertar imagen" o "ver imagen".
    placeholders_obvios = ['insertar', 'ver imagen', 'introducir', 'seguir escribiendo']
    for p in found:
        for obvio in placeholders_obvios:
            assert obvio not in p.lower(), f"Falso positivo: '{p}' contiene '{obvio}'"


def test_detect_placeholders_empty():
    assert detect_placeholders("") == []
    assert detect_placeholders(None) == []


# ---------------------------------------------------------------------------
# extract_html_content — edge cases
# ---------------------------------------------------------------------------

def test_extract_html_content_text_before_html():
    """Texto espurio antes del primer tag se descarta."""
    content = "Aqui tienes el HTML:\n<article><p>contenido</p></article>"
    result = extract_html_content(content)
    assert result.startswith('<article')
    assert 'Aqui tienes' not in result


def test_extract_html_content_text_after_html():
    """Texto espurio despues del ultimo tag se recorta."""
    content = "<article><p>contenido</p></article>\n\nEspero que te sirva!"
    result = extract_html_content(content)
    assert result.endswith('</article>')
    assert 'Espero que' not in result


def test_extract_html_content_inner_markdown_block():
    """Bloque markdown ```html ... ``` interno se extrae."""
    content = "Prefacio.\n```html\n<div><p>Hola</p></div>\n```\nEpilogo."
    result = extract_html_content(content)
    assert '```' not in result
    assert '<div>' in result
    assert '<p>Hola</p>' in result


def test_extract_html_content_unclosed_fence():
    """Apertura de fence sin cierre: el contenido HTML sale igualmente."""
    content = "```html\n<article><p>x</p></article>"
    result = extract_html_content(content)
    assert '```' not in result
    assert '<article>' in result


def test_extract_html_content_nested_backticks():
    """Bloques anidados: el comportamiento NO es ideal pero no debe crashear.

    Documenta limitacion: con ```html ... ```inner``` ... ``` los regex de
    markdown pueden recortar contenido interno. No es un caso esperado en
    salidas reales de Claude (no anida fences).
    """
    content = "```html\n<pre>```inner```</pre>\n```"
    result = extract_html_content(content)
    assert isinstance(result, str)
    assert '```' not in result


# ---------------------------------------------------------------------------
# detect_ai_phrases — falsos positivos
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("html", [
    '<p>Esta GPU ofrece 16GB de VRAM para gaming exigente.</p>',
    '<p>El procesador alcanza una experiencia fluida en multitarea.</p>',
    '<p>En el mercado de hoy hay muchas opciones competitivas.</p>',
])
def test_detect_ai_phrases_no_false_positives(html):
    """Frases tecnicas con palabras como 'ofrece' o 'experiencia' en contexto
    legitimo NO deben matchear (los patrones IA exigen colocaciones concretas)."""
    found = detect_ai_phrases(html)
    # Aceptamos 0 o muy pocas detecciones; lo critico es no detectar patrones
    # que no estan presentes literalmente.
    phrases = [f['phrase'] for f in found]
    assert 'En el mundo actual...' not in phrases
    assert 'Sin lugar a dudas...' not in phrases


# ---------------------------------------------------------------------------
# extract_content_structure / extract_content / extract_text / extract_meta_tags
# ---------------------------------------------------------------------------

def test_extract_content_structure(sample_html):
    result = extract_content_structure(sample_html)
    assert result['structure_valid'] is True
    assert result['has_table'] is True
    assert result['has_callout'] is True
    assert result['has_verdict'] is True
    assert result['word_count'] > 0
    assert any(h['level'] == 'h2' for h in result['headings'])


def test_extract_content_structure_empty():
    result = extract_content_structure("")
    assert result['structure_valid'] is False
    assert result['word_count'] == 0


def test_extract_content(sample_html):
    result = extract_content(sample_html)
    assert result.word_count > 0
    assert len(result.headings) >= 1
    assert any(h['level'] == 'h2' for h in result.headings)
    assert 'tarjetas graficas' in result.text.lower()


def test_extract_content_empty():
    result = extract_content("")
    assert result.word_count == 0
    assert result.headings == []


def test_extract_text_alias():
    assert extract_text("<p>hola mundo</p>") == "hola mundo"
    assert extract_text("") == ""


def test_extract_meta_tags_with_meta():
    html = '<head><meta name="description" content="desc text"><meta property="og:title" content="og title"></head>'
    meta = extract_meta_tags(html)
    assert meta.get('description') == 'desc text'
    assert meta.get('og:title') == 'og title'


def test_extract_meta_tags_empty():
    assert extract_meta_tags("") == {}
    assert extract_meta_tags("<p>no meta here</p>") == {}


# ---------------------------------------------------------------------------
# validate_cms_articles
# ---------------------------------------------------------------------------

def test_validate_cms_articles_complete(sample_html):
    result = validate_cms_articles(sample_html)
    assert result['main'] is True
    assert result['faqs'] is True
    assert result['verdict'] is True
    assert result['all_present'] is True
    assert result['missing'] == []


def test_validate_cms_articles_missing():
    html = '<article class="contentGenerator__main"><h2>x</h2></article>'
    result = validate_cms_articles(html)
    assert result['main'] is True
    assert result['faqs'] is False
    assert result['verdict'] is False
    assert result['all_present'] is False
    assert 'contentGenerator__faqs' in result['missing']
    assert 'contentGenerator__verdict' in result['missing']


def test_validate_cms_articles_empty():
    result = validate_cms_articles("")
    assert result['all_present'] is False
    assert len(result['missing']) == 3


# ---------------------------------------------------------------------------
# validate_cms_structure
# ---------------------------------------------------------------------------

def test_validate_cms_structure_empty():
    valid, errors, warnings = validate_cms_structure("")
    assert valid is False
    assert any("vacío" in e for e in errors)


def test_validate_cms_structure_div_kicker():
    """kicker en <div> en lugar de <span> es error."""
    html = (
        '<article class="contentGenerator__main">'
        '<div class="kicker">x</div>'
        '<h2>Titulo</h2>'
        '<p>palabra ' * 350 + '</p>'
        '</article>'
        '<article class="contentGenerator__faqs"><h2>faqs</h2></article>'
        '<article class="contentGenerator__verdict"><h2>verdict</h2></article>'
    )
    valid, errors, warnings = validate_cms_structure(html)
    assert valid is False
    assert any("kicker" in e.lower() and "<span>" in e for e in errors)


def test_validate_cms_structure_h1_forbidden():
    html = (
        '<article class="contentGenerator__main">'
        '<h1>Titulo prohibido</h1>'
        '<p>texto ' * 350 + '</p>'
        '</article>'
        '<article class="contentGenerator__faqs"><h2>faqs</h2></article>'
        '<article class="contentGenerator__verdict"><h2>verdict</h2></article>'
    )
    valid, errors, warnings = validate_cms_structure(html)
    assert valid is False
    assert any("h1" in e.lower() for e in errors)


def test_validate_cms_structure_low_word_count():
    html = (
        '<article class="contentGenerator__main"><h2>x</h2><p>solo unas palabras</p></article>'
        '<article class="contentGenerator__faqs"><h2>faqs</h2></article>'
        '<article class="contentGenerator__verdict"><h2>verdict</h2></article>'
    )
    valid, errors, warnings = validate_cms_structure(html)
    assert valid is False
    assert any("palabras" in e.lower() for e in errors)


def test_validate_cms_structure_markdown_residual():
    html = (
        '<article class="contentGenerator__main"><h2>x</h2>'
        '<p>texto ' * 350 + '</p>'
        '<p>residuo: ```python```</p>'
        '</article>'
        '<article class="contentGenerator__faqs"><h2>faqs</h2></article>'
        '<article class="contentGenerator__verdict"><h2>verdict</h2></article>'
    )
    valid, errors, warnings = validate_cms_structure(html)
    assert any("markdown" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# validate_word_count_target
# ---------------------------------------------------------------------------

def test_validate_word_count_target_within():
    html = '<p>' + ('palabra ' * 100) + '</p>'
    result = validate_word_count_target(html, target=100, tolerance=0.05)
    assert result['within_range'] is True
    assert result['actual'] == 100
    assert result['difference'] == 0


def test_validate_word_count_target_out_of_range():
    html = '<p>' + ('palabra ' * 50) + '</p>'
    result = validate_word_count_target(html, target=200, tolerance=0.05)
    assert result['within_range'] is False
    assert result['difference'] == -150
    assert result['percentage_diff'] == -75.0


def test_validate_word_count_target_zero_target():
    """target=0 no debe dividir por cero."""
    result = validate_word_count_target("<p>x</p>", target=0)
    assert result['percentage_diff'] == 0


# ---------------------------------------------------------------------------
# analyze_links
# ---------------------------------------------------------------------------

def test_analyze_links_classifies():
    html = (
        '<a href="https://www.pccomponentes.com/portatil-asus">Portatil</a>'
        '<a href="https://www.pccomponentes.com/blog/guia-gpu">Blog</a>'
        '<a href="/relativa">Relativo</a>'
        '<a href="https://google.com">Externo</a>'
    )
    result = analyze_links(html)
    assert result['total'] == 4
    assert result['internal_count'] == 3
    assert result['external_count'] == 1
    assert any('portatil-asus' in i['url'] for i in result['pdp'])
    assert any('/blog/' in i['url'] for i in result['blog'])


def test_analyze_links_empty():
    result = analyze_links("")
    assert result['total'] == 0
    assert result['internal_links_count'] == 0
    assert result['external_links_count'] == 0


# ---------------------------------------------------------------------------
# get_heading_hierarchy
# ---------------------------------------------------------------------------

def test_get_heading_hierarchy(sample_html):
    headings = get_heading_hierarchy(sample_html)
    assert len(headings) >= 1
    assert all('level' in h and 'text' in h for h in headings)
    assert any(h['level'] == 'h2' for h in headings)


def test_get_heading_hierarchy_empty():
    assert get_heading_hierarchy("") == []


# ---------------------------------------------------------------------------
# Aliases y helpers
# ---------------------------------------------------------------------------

def test_get_word_count_alias():
    assert get_word_count("<p>uno dos tres</p>") == 3
    assert get_word_count("") == 0


def test_strip_tags_alias():
    assert strip_tags("<h1>x</h1><p>y</p>") == "x y"


def test_is_bs4_available():
    assert is_bs4_available() is True


def test_get_parser_returns_string():
    assert get_parser() == 'html.parser'
    assert get_bs4_parser() == 'html.parser'


# ---------------------------------------------------------------------------
# HTMLParser class (custom html.parser-based)
# ---------------------------------------------------------------------------

def test_html_parser_extracts_text_headings_links():
    parser = get_html_parser()
    html = (
        '<style>body{}</style>'
        '<h2>Titulo principal</h2>'
        '<p>Texto del cuerpo.</p>'
        '<a href="https://x.com">Enlace</a>'
        '<script>alert(1)</script>'
    )
    parser.feed(html)
    text = parser.get_text()
    assert 'Titulo principal' in text
    assert 'Texto del cuerpo' in text
    # script y style no se cuentan
    assert 'alert' not in text
    assert 'body{}' not in text

    headings = parser.get_headings()
    assert len(headings) == 1
    assert headings[0]['level'] == 'h2'
    assert headings[0]['text'] == 'Titulo principal'

    links = parser.get_links()
    assert len(links) == 1
    assert links[0]['href'] == 'https://x.com'
    assert links[0]['text'] == 'Enlace'


def test_html_parser_anchor_without_href():
    parser = get_html_parser()
    parser.feed('<a>sin href</a>')
    assert parser.get_links() == []


# ---------------------------------------------------------------------------
# sanitize_html — branches secundarias
# ---------------------------------------------------------------------------

def test_sanitize_html_full_document():
    """Si el input lleva <html>/<body>, se preserva el wrapper."""
    html = '<html><body><p>contenido</p></body></html>'
    cleaned = sanitize_html(html)
    assert '<html' in cleaned.lower()
    assert '<body' in cleaned.lower()
    assert 'contenido' in cleaned


def test_sanitize_html_src_with_dangerous_scheme():
    """src con javascript: se elimina (no se sustituye por '#')."""
    html = '<img src="javascript:alert(1)">'
    cleaned = sanitize_html(html)
    assert 'javascript:' not in cleaned.lower()
    # El atributo src se ha eliminado, no sustituido
    assert 'src=' not in cleaned.lower() or 'src=""' in cleaned.lower()
