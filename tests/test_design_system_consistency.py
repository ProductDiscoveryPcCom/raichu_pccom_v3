"""R3.2: Verifica que el CSS canónico tiene una única fuente de verdad.

Los tres puntos que históricamente duplicaban el CSS minificado
(`prompts/new_content.py:_CSS_FALLBACK`, `prompts/new_content.py:CSS_INLINE_MINIFIED`,
`config/design_system.py:get_canonical_css`) deben retornar el mismo string
byte a byte.
"""
from config.design_system import get_canonical_css
from prompts.new_content import _CSS_FALLBACK, CSS_INLINE_MINIFIED


def test_css_fallback_equals_canonical():
    """_CSS_FALLBACK debe ser exactamente el CSS canónico de design_system."""
    assert _CSS_FALLBACK == get_canonical_css()


def test_css_inline_minified_alias():
    """CSS_INLINE_MINIFIED es alias retro-compat de _CSS_FALLBACK."""
    assert CSS_INLINE_MINIFIED is _CSS_FALLBACK


def test_canonical_css_contains_critical_variables():
    """El CSS canónico debe definir las variables de marca clave."""
    css = get_canonical_css()
    for var in ("--orange-900", "--blue-m-900", "--white", "--gray-100", "--space-md", "--radius-md"):
        assert var in css, f"Variable CSS '{var}' ausente en canonical CSS"


def test_canonical_css_contains_critical_components():
    """El CSS canónico debe definir las clases de componentes CMS obligatorios."""
    css = get_canonical_css()
    for cls in (".contentGenerator__main", ".contentGenerator__faqs", ".contentGenerator__verdict",
                ".kicker", ".toc", ".verdict-box", ".callout", ".faqs__item"):
        assert cls in css, f"Clase '{cls}' ausente en canonical CSS"
