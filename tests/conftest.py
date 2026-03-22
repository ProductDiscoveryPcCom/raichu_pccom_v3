"""
Shared fixtures for Raichu test suite.
"""
import copy
import pytest

from config.arquetipos import ARQUETIPOS


@pytest.fixture
def sample_arquetipo():
    """Deep copy of ARQ-1 for safe mutation in tests."""
    return copy.deepcopy(ARQUETIPOS["ARQ-1"])


@pytest.fixture(scope="session")
def sample_html():
    """Realistic 3-article CMS HTML with all required elements."""
    return (
        '<style>:root { --color-primary: #FF6600; }</style>\n'
        '<article class="contentGenerator__main">\n'
        '  <span class="kicker">Tecnologia</span>\n'
        '  <h2>Mejores tarjetas graficas 2024</h2>\n'
        '  <nav class="toc"><ul><li><a href="#intro">Introduccion</a></li></ul></nav>\n'
        '  <p>Las tarjetas graficas son componentes esenciales para cualquier PC gaming.</p>\n'
        '  <p>En esta guia analizamos los modelos mas vendidos del mercado actual.</p>\n'
        '  <table><tr><th>Modelo</th><th>Precio</th></tr>'
        '<tr><td>RTX 4090</td><td>1599 EUR</td></tr></table>\n'
        '  <div class="callout"><p>Recuerda comparar precios antes de comprar.</p></div>\n'
        '</article>\n'
        '<article class="contentGenerator__faqs">\n'
        '  <h2>Preguntas frecuentes</h2>\n'
        '  <p>Respuesta detallada sobre tarjetas graficas y rendimiento.</p>\n'
        '</article>\n'
        '<article class="contentGenerator__verdict">\n'
        '  <div class="verdict-box"><p>Nuestro veredicto final sobre las mejores opciones.</p></div>\n'
        '</article>'
    )


@pytest.fixture(scope="session")
def sample_html_with_ai_phrases():
    """HTML with AI-detectable phrases injected."""
    return (
        '<article class="contentGenerator__main">\n'
        '  <h2>Titulo de prueba</h2>\n'
        '  <p>En el mundo actual, la tecnologia avanza rapidamente.</p>\n'
        '  <p>Sin lugar a dudas, los procesadores modernos son potentes.</p>\n'
        '  <p>Este producto ofrece una experiencia unica para el usuario.</p>\n'
        '</article>'
    )


@pytest.fixture(scope="session")
def markdown_wrapped_html():
    """HTML wrapped in markdown code fences."""
    return '```html\n<div class="test"><p>Hello world</p></div>\n```'


@pytest.fixture
def rewrite_config():
    """Minimal valid config dict for rewrite prompt functions."""
    return {
        "rewrite_mode": "single",
        "rewrite_instructions": {
            "improve": ["mejorar SEO"],
            "maintain": ["enlaces"],
            "remove": [],
            "add": [],
        },
        "html_contents": [
            {
                "html": '<article class="contentGenerator__main"><h2>Contenido original</h2>'
                        '<p>Texto del articulo original para reescribir.</p></article>',
                "url": "https://www.pccomponentes.com/articulo-original",
                "word_count": 50,
            }
        ],
        "target_length": 1500,
        "objetivo": "Mejorar posicionamiento SEO",
        "context": "",
        "arquetipo_codigo": "ARQ-1",
        "products": [],
        "headings_config": {},
        "editorial_links": [],
        "product_links": [],
        "alternative_products": [],
    }


# Exclude bulk-generated test files that require Streamlit runtime
collect_ignore_glob = [
    "test_fixes.py",
    "test_design_system.py",
    "test_tables.py",
    "test_ux_ui_functionality.py",
    "test_v51_modules.py",
    "test_visual_elements_and_serp.py",
]
