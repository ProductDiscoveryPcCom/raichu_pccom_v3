"""
Tests básicos para validar la modularización
"""


def test_imports():
    """Verifica que todos los módulos se importan correctamente"""
    from config.settings import ANTHROPIC_API_KEY
    from config.arquetipos import ARQUETIPOS, get_arquetipo
    from core.generator import ContentGenerator
    from core.scraper import scrape_pdp_data
    from utils.html_utils import count_words_in_html


def test_archetipos():
    """Verifica que los arquetipos están bien definidos"""
    from config.arquetipos import ARQUETIPOS, get_arquetipo

    assert len(ARQUETIPOS) >= 18, f"Deben haber al menos 18 arquetipos, hay {len(ARQUETIPOS)}"

    arq1 = get_arquetipo("ARQ-1")
    assert arq1 is not None
    assert arq1['code'] == "ARQ-1"
    assert 'name' in arq1
    assert 'default_length' in arq1


def test_html_utils():
    """Verifica utilidades HTML"""
    from utils.html_utils import count_words_in_html, validate_html_structure

    html = "<article><h1>Test</h1><p>This is a test with ten words here</p></article>"
    words = count_words_in_html(html)
    assert words == 9, f"Expected 9 words, got {words}"

    validation = validate_html_structure(html)
    assert validation['has_article']
