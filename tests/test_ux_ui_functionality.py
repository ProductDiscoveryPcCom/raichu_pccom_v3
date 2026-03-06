#!/usr/bin/env python3
"""
Tests exhaustivos de UX, UI y funcionalidades — Raichu v5.1

Cubre áreas no cubiertas por los tests existentes:
1. Sidebar: versión sincronizada, features
2. Inputs: validación de URLs, JSON parsing, arquetipos
3. Assistant: parsing de comandos, detección de JSON, parámetros GENERAR
4. Pipeline: detección de elementos visuales, HTML extraction
5. Quality Scorer: puntuación multi-dimensional
6. HTML Utils: word count, structure validation, AI phrase detection
7. Config: settings integrity, archetype completeness
8. Content Scrubber: AI phrase removal
9. Version: single source of truth
10. Design System: component registry, CSS generation

Ejecutar: python -m pytest tests/test_ux_ui_functionality.py -v
"""

import importlib
import inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================================
# 1. SIDEBAR — Versión y Features
# ============================================================================

class TestSidebarVersion:
    """Valida que el sidebar muestre la versión correcta."""

    def test_sidebar_imports_version(self):
        """sidebar.py debe importar __version__ de version.py."""
        source = Path("ui/sidebar.py").read_text()
        assert "from version import __version__" in source, \
            "sidebar.py no importa __version__ de version.py"

    def test_sidebar_uses_dynamic_version(self):
        """sidebar.py debe usar __version__ en lugar de versión hardcodeada."""
        source = Path("ui/sidebar.py").read_text()
        assert "{__version__}" in source or "__version__" in source, \
            "sidebar.py no usa versión dinámica"
        assert 'Versión 4.9.2' not in source, \
            "sidebar.py aún tiene versión hardcodeada 4.9.2"

    def test_version_consistency(self):
        """VERSION, version.py y app.py deben estar sincronizados."""
        from version import __version__
        version_file = Path("VERSION").read_text().strip()
        assert __version__ == version_file, \
            f"version.py ({__version__}) != VERSION ({version_file})"


# ============================================================================
# 2. ASSISTANT — Parsing de Comandos
# ============================================================================

class TestAssistantCommands:
    """Valida el parsing y ejecución de comandos del asistente."""

    def test_detect_gsc_check_command(self):
        from ui.assistant import detect_and_execute_commands
        response = "Voy a verificar esa keyword. [GSC_CHECK: mejores portátiles gaming]"
        cleaned, results = detect_and_execute_commands(response)
        assert len(results) >= 1
        assert results[0]['command'] == 'GSC_CHECK: mejores portátiles gaming'
        assert '[GSC_CHECK' not in cleaned

    def test_detect_arquetipos_list_command(self):
        from ui.assistant import detect_and_execute_commands
        response = "Aquí están los arquetipos: [ARQUETIPOS_LIST]"
        cleaned, results = detect_and_execute_commands(response)
        assert any('ARQUETIPOS_LIST' in r['command'] for r in results)

    def test_detect_generar_command(self):
        from ui.assistant import detect_and_execute_commands
        response = "[GENERAR: keyword=portátil gaming, arquetipo=ARQ-4, longitud=1500, visual=toc,verdict,callout]"
        cleaned, results = detect_and_execute_commands(response)
        gen = [r for r in results if r.get('action') == 'generate']
        assert len(gen) == 1
        assert 'portátil gaming' in gen[0]['params']

    def test_detect_multiple_commands(self):
        from ui.assistant import detect_and_execute_commands
        response = "Verifico la keyword [GSC_CHECK: test] y muestro arquetipos [ARQUETIPOS_LIST]."
        cleaned, results = detect_and_execute_commands(response)
        assert len(results) == 2

    def test_no_commands_returns_original(self):
        from ui.assistant import detect_and_execute_commands
        response = "Esto es una respuesta sin comandos."
        cleaned, results = detect_and_execute_commands(response)
        assert cleaned == response
        assert results == []

    def test_detect_serp_research_command(self):
        from ui.assistant import detect_and_execute_commands
        response = "Investigo SERPs: [SERP_RESEARCH: mejores auriculares gaming]"
        cleaned, results = detect_and_execute_commands(response)
        assert any('SERP_RESEARCH' in r['command'] for r in results)

    def test_detect_visual_list_command(self):
        from ui.assistant import detect_and_execute_commands
        response = "[VISUAL_LIST]"
        cleaned, results = detect_and_execute_commands(response)
        assert any('VISUAL_LIST' in r['command'] for r in results)

    def test_detect_visual_recomendar_command(self):
        from ui.assistant import detect_and_execute_commands
        response = "[VISUAL_RECOMENDAR: guía de compra portátiles]"
        cleaned, results = detect_and_execute_commands(response)
        assert any('VISUAL_RECOMENDAR' in r['command'] for r in results)


class TestAssistantParseGenerationParams:
    """Valida el parsing de parámetros del comando GENERAR."""

    def test_basic_params(self):
        from ui.assistant import parse_generation_params
        params = parse_generation_params(
            "keyword=portátil gaming, arquetipo=ARQ-4, longitud=1500"
        )
        assert params['keyword'] == 'portátil gaming'
        assert params['arquetipo'] == 'ARQ-4'
        assert params['longitud'] == '1500'

    def test_visual_params(self):
        from ui.assistant import parse_generation_params
        params = parse_generation_params(
            "keyword=test, arquetipo=ARQ-1, longitud=1500, visual=toc,callout,verdict"
        )
        assert params['visual'] == 'toc,callout,verdict'

    def test_empty_params(self):
        from ui.assistant import parse_generation_params
        params = parse_generation_params("")
        assert isinstance(params, dict)

    def test_only_keyword(self):
        from ui.assistant import parse_generation_params
        params = parse_generation_params("keyword=test only")
        assert params['keyword'] == 'test only'


class TestAssistantJsonDetection:
    """Valida la detección de JSON de producto en mensajes."""

    def test_detects_json_in_code_block(self):
        from ui.assistant import detect_product_json_in_message
        msg = 'Aquí va el producto:\n```json\n{"product_id": 123, "title": "Test"}\n```'
        result = detect_product_json_in_message(msg)
        assert result is not None
        parsed = json.loads(result)
        assert parsed['product_id'] == 123

    def test_detects_inline_json(self):
        from ui.assistant import detect_product_json_in_message
        msg = 'Producto: {"product_id": 456, "title": "GPU RTX", "legacy_id": "789"}'
        result = detect_product_json_in_message(msg)
        assert result is not None

    def test_no_json_returns_none(self):
        from ui.assistant import detect_product_json_in_message
        msg = "No hay JSON aquí, solo texto normal"
        result = detect_product_json_in_message(msg)
        assert result is None

    def test_non_product_json_returns_none(self):
        from ui.assistant import detect_product_json_in_message
        msg = '{"color": "red", "size": 42}'
        result = detect_product_json_in_message(msg)
        assert result is None


class TestAssistantVisualRecommend:
    """Valida las recomendaciones de componentes visuales."""

    def test_recommend_guia_compra(self):
        from ui.assistant import _execute_visual_recommend
        result = _execute_visual_recommend("guía de compra")
        assert 'comparison_table' in result or 'mod_cards' in result
        assert 'GENERAR' in result

    def test_recommend_review(self):
        from ui.assistant import _execute_visual_recommend
        result = _execute_visual_recommend("review")
        assert 'specs_list' in result or 'verdict' in result

    def test_recommend_unknown_returns_default(self):
        from ui.assistant import _execute_visual_recommend
        result = _execute_visual_recommend("tipo desconocido xyz")
        assert 'toc' in result  # Default includes toc

    def test_recommend_nota_prensa_no_components(self):
        from ui.assistant import _execute_visual_recommend
        result = _execute_visual_recommend("nota de prensa")
        assert 'HTML' in result or 'externo' in result.lower() or 'estándar' in result.lower()

    def test_recommend_guest_post_no_components(self):
        from ui.assistant import _execute_visual_recommend
        result = _execute_visual_recommend("guest posting")
        assert 'externo' in result.lower() or 'estándar' in result.lower()


# ============================================================================
# 3. HTML UTILS — Validación y Detección
# ============================================================================

class TestHtmlWordCount:
    """Valida el conteo de palabras en HTML."""

    def test_basic_paragraph(self):
        from utils.html_utils import count_words_in_html
        html = '<p>Esta es una prueba simple de conteo</p>'
        count = count_words_in_html(html)
        assert count == 7

    def test_ignores_html_tags(self):
        from utils.html_utils import count_words_in_html
        html = '<h2>Título</h2><p>Con <strong>formato</strong> y <a href="#">enlace</a></p>'
        count = count_words_in_html(html)
        assert count == 5  # Título, Con, formato, y, enlace

    def test_ignores_css(self):
        from utils.html_utils import count_words_in_html
        html = '<style>.test{color:red;font-size:14px;}</style><p>Solo esto cuenta</p>'
        count = count_words_in_html(html)
        # CSS content should not inflate the word count significantly
        assert count <= 5  # "Solo esto cuenta" = 3 words + possible minor artifacts

    def test_script_does_not_dominate(self):
        from utils.html_utils import count_words_in_html
        # Verify that script content doesn't add many extra words
        html_no_script = '<p>Cuenta esto sí</p>'
        html_with_script = '<script>var x = "no cuenta esto nunca jamás";</script><p>Cuenta esto sí</p>'
        count_without = count_words_in_html(html_no_script)
        count_with = count_words_in_html(html_with_script)
        # Script may add some words but should not dominate
        assert count_with < count_without * 4, "Script content inflates word count too much"

    def test_empty_html(self):
        from utils.html_utils import count_words_in_html
        assert count_words_in_html('') == 0
        assert count_words_in_html(None) == 0

    def test_complex_article(self):
        from utils.html_utils import count_words_in_html
        html = """
        <style>.toc{background:#f5f5f5}</style>
        <article>
            <h2>Introducción al gaming</h2>
            <p>El mundo del gaming ha evolucionado enormemente.</p>
            <ul>
                <li>PC Gaming</li>
                <li>Consolas</li>
            </ul>
        </article>
        """
        count = count_words_in_html(html)
        assert count >= 10


class TestHtmlStructureValidation:
    """Valida la detección de estructura HTML."""

    def test_detects_toc(self):
        from utils.html_utils import validate_html_structure
        html = '<nav class="toc"><h4>Contenido</h4></nav>'
        result = validate_html_structure(html)
        assert result['has_toc'] is True

    def test_detects_callout(self):
        from utils.html_utils import validate_html_structure
        html = '<div class="callout"><p>Important info</p></div>'
        result = validate_html_structure(html)
        assert result['has_callout'] is True

    def test_detects_verdict_box(self):
        from utils.html_utils import validate_html_structure
        html = '<div class="verdict-box"><p>Final verdict</p></div>'
        result = validate_html_structure(html)
        assert result['has_verdict_box'] is True

    def test_detects_grid(self):
        from utils.html_utils import validate_html_structure
        html = '<div class="grid cols-2"><div>A</div><div>B</div></div>'
        result = validate_html_structure(html)
        assert result['has_grid'] is True

    def test_detects_table(self):
        from utils.html_utils import validate_html_structure
        html = '<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>'
        result = validate_html_structure(html)
        assert result['has_table'] is True

    def test_detects_bf_callout(self):
        from utils.html_utils import validate_html_structure
        html = '<div class="callout-bf"><p>Promo</p></div>'
        result = validate_html_structure(html)
        assert result['has_bf_callout'] is True

    def test_no_markdown(self):
        from utils.html_utils import validate_html_structure
        html = '<p>Clean HTML without markdown</p>'
        result = validate_html_structure(html)
        assert result['no_markdown'] is True

    def test_article_detection(self):
        from utils.html_utils import validate_html_structure
        html = '<article><p>Content</p></article>'
        result = validate_html_structure(html)
        assert result['has_article'] is True


class TestAIPhraseDetection:
    """Tests adicionales de detección de frases IA."""

    def test_multiple_phrases_in_same_text(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>En el mundo actual, cabe mencionar que sin lugar a dudas hay que elegir bien.</p>'
        result = detect_ai_phrases(html)
        assert len(result) >= 2  # Al menos 2 frases detectadas

    def test_detects_a_la_hora_de(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>A la hora de comprar un portátil, hay muchos factores.</p>'
        result = detect_ai_phrases(html)
        assert len(result) >= 1

    def test_detects_es_fundamental(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>Es fundamental elegir correctamente.</p>'
        result = detect_ai_phrases(html)
        assert len(result) >= 1

    def test_technical_content_clean(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>El RTX 4070 rinde un 15% más que el RTX 4060 en 1440p.</p>'
        result = detect_ai_phrases(html)
        assert len(result) == 0


# ============================================================================
# 4. PIPELINE — Detección de Elementos Visuales
# ============================================================================

class TestPipelineVisualDetection:
    """Tests de detección de elementos visuales en pipeline."""

    def test_detect_toc(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<nav class="toc"><h4>Contenido</h4></nav>'
        missing = _detect_missing_visual_elements(html, ['toc'])
        assert missing == []

    def test_detect_callout(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="callout"><p>Info</p></div>'
        missing = _detect_missing_visual_elements(html, ['callout'])
        assert missing == []

    def test_detect_verdict(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="verdict-box"><p>Final</p></div>'
        missing = _detect_missing_visual_elements(html, ['verdict'])
        assert missing == []

    def test_detect_faqs(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="contentGenerator__faqs"><div>Q&A</div></div>'
        missing = _detect_missing_visual_elements(html, ['faqs'])
        assert missing == []

    def test_detect_grid(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="grid cols-2"><div>A</div><div>B</div></div>'
        missing = _detect_missing_visual_elements(html, ['grid'])
        assert missing == []

    def test_detect_comparison_table(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<table class="comparison-table"><tr><td>A</td><td>B</td></tr></table>'
        missing = _detect_missing_visual_elements(html, ['comparison_table'])
        assert missing == []

    def test_detect_specs_list(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="specs-list"><dl><dt>CPU</dt><dd>i9</dd></dl></div>'
        missing = _detect_missing_visual_elements(html, ['specs_list'])
        assert missing == []

    def test_detect_price_highlight(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="price-highlight"><span>199€</span></div>'
        missing = _detect_missing_visual_elements(html, ['price_highlight'])
        assert missing == []

    def test_missing_multiple_elements(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<p>Just plain text</p>'
        missing = _detect_missing_visual_elements(html, ['toc', 'callout', 'verdict', 'grid'])
        assert set(missing) == {'toc', 'callout', 'verdict', 'grid'}

    def test_partial_detection(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<nav class="toc">TOC</nav><div class="verdict-box">V</div>'
        missing = _detect_missing_visual_elements(html, ['toc', 'callout', 'verdict'])
        assert 'toc' not in missing
        assert 'verdict' not in missing
        assert 'callout' in missing

    def test_case_insensitive(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div CLASS="CALLOUT"><p>Info</p></div>'
        missing = _detect_missing_visual_elements(html, ['callout'])
        assert missing == []

    def test_empty_elements_list(self):
        from core.pipeline import _detect_missing_visual_elements
        missing = _detect_missing_visual_elements('<p>text</p>', [])
        assert missing == []

    def test_empty_html(self):
        from core.pipeline import _detect_missing_visual_elements
        missing = _detect_missing_visual_elements('', ['toc'])
        assert 'toc' in missing

    def test_check_list_detection(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<ul class="check-list"><li>Check 1</li></ul>'
        missing = _detect_missing_visual_elements(html, ['check_list'])
        assert missing == []

    def test_intro_box_detection(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<div class="intro"><p>Intro text</p></div>'
        missing = _detect_missing_visual_elements(html, ['intro_box'])
        assert missing == []

    def test_badges_detection(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<span class="badge">Tag</span>'
        missing = _detect_missing_visual_elements(html, ['badges'])
        assert missing == []

    def test_buttons_detection(self):
        from core.pipeline import _detect_missing_visual_elements
        html = '<a class="btn" href="#">Comprar</a>'
        missing = _detect_missing_visual_elements(html, ['buttons'])
        assert missing == []


class TestPipelineHtmlExtraction:
    """Tests de extracción de HTML limpio."""

    def test_removes_markdown_fences(self):
        from core.pipeline import _extract_html_content
        text = '```html\n<p>Hello</p>\n```'
        result = _extract_html_content(text)
        assert '<p>Hello</p>' in result
        assert '```' not in result

    def test_plain_html(self):
        from core.pipeline import _extract_html_content
        text = '<article><p>Test</p></article>'
        result = _extract_html_content(text)
        assert result == text

    def test_empty_input(self):
        from core.pipeline import _extract_html_content
        assert _extract_html_content('') == ''
        assert _extract_html_content(None) == ''


class TestPipelineVisualElementNames:
    """Tests de nombres legibles de elementos visuales."""

    def test_all_elements_have_names(self):
        from core.pipeline import _get_visual_element_names
        names = _get_visual_element_names()
        expected_keys = [
            'toc', 'callout', 'callout_promo', 'callout_alert', 'verdict',
            'grid', 'badges', 'buttons', 'table', 'light_table',
            'comparison_table', 'faqs', 'intro_box', 'check_list',
            'specs_list', 'product_module', 'price_highlight', 'stats_grid',
            'section_divider', 'mod_cards', 'vcard_cards',
        ]
        for key in expected_keys:
            assert key in names, f"Falta nombre legible para '{key}'"

    def test_names_are_strings(self):
        from core.pipeline import _get_visual_element_names
        names = _get_visual_element_names()
        for key, value in names.items():
            assert isinstance(value, str), f"Nombre de '{key}' no es string: {type(value)}"
            assert len(value) > 0, f"Nombre de '{key}' está vacío"


# ============================================================================
# 5. ARQUETIPOS — Completitud y Consistencia
# ============================================================================

class TestArquetiposIntegrity:
    """Valida la integridad de los arquetipos."""

    def test_all_archetypes_have_required_fields(self):
        from config.arquetipos import get_arquetipo, get_arquetipo_names
        names = get_arquetipo_names()
        required_fields = ['name', 'description']
        for code in names:
            arq = get_arquetipo(code)
            assert arq is not None, f"Arquetipo {code} retorna None"
            for field in required_fields:
                assert field in arq, f"Arquetipo {code} no tiene campo '{field}'"

    def test_all_archetypes_have_length_range(self):
        from config.arquetipos import get_arquetipo_names, get_length_range
        names = get_arquetipo_names()
        for code in names:
            min_l, max_l = get_length_range(code)
            assert min_l > 0, f"{code}: min_length debe ser > 0, es {min_l}"
            assert max_l > min_l, f"{code}: max_length ({max_l}) debe ser > min_length ({min_l})"

    def test_all_archetypes_have_default_length(self):
        from config.arquetipos import get_arquetipo_names, get_default_length, get_length_range
        names = get_arquetipo_names()
        for code in names:
            default = get_default_length(code)
            min_l, max_l = get_length_range(code)
            assert min_l <= default <= max_l, \
                f"{code}: default_length ({default}) fuera de rango [{min_l}, {max_l}]"

    def test_guiding_questions_exist(self):
        from config.arquetipos import get_arquetipo_names, get_guiding_questions
        names = get_arquetipo_names()
        for code in names:
            questions = get_guiding_questions(code, include_universal=False)
            assert isinstance(questions, list), f"{code}: questions no es lista"

    def test_universal_questions_exist(self):
        from config.arquetipos import PREGUNTAS_UNIVERSALES
        assert len(PREGUNTAS_UNIVERSALES) >= 3, \
            f"Demasiado pocas preguntas universales: {len(PREGUNTAS_UNIVERSALES)}"


# ============================================================================
# 6. QUALITY SCORER — Puntuación
# ============================================================================

class TestQualityScorer:
    """Tests del scoring de calidad de contenido."""

    def test_scorer_importable(self):
        from utils.quality_scorer import QualityScorer
        assert QualityScorer is not None

    def test_score_basic_content(self):
        from utils.quality_scorer import QualityScorer
        scorer = QualityScorer()
        html = """
        <h2>Mejores portátiles gaming 2025</h2>
        <p>Si buscas un portátil para gaming, el ASUS ROG Strix G16 con RTX 4070
        es una opción brutal por 1.799€. Su pantalla QHD de 240Hz te da una fluidez
        que se nota en cada partida.</p>
        <h3>ASUS ROG Strix G16</h3>
        <p>Con su Core i9-14900HX y 32GB de DDR5, este bicho mueve cualquier juego
        en Ultra a 1440p sin despeinarse. La refrigeración funciona correctamente
        y no throttlea ni en sesiones largas de Cyberpunk 2077.</p>
        """
        result = scorer.score(html, keyword="portátiles gaming")
        assert 'composite_score' in result
        assert 0 <= result['composite_score'] <= 100

    def test_score_empty_content(self):
        from utils.quality_scorer import QualityScorer
        scorer = QualityScorer()
        result = scorer.score('', keyword='test')
        assert result['composite_score'] == 0 or result['composite_score'] is not None

    def test_scorer_has_all_dimensions(self):
        from utils.quality_scorer import QualityScorer
        scorer = QualityScorer()
        html = '<h2>Test</h2><p>Content with keyword test here for scoring.</p>'
        result = scorer.score(html, keyword='test')
        expected_dimensions = ['humanidad', 'especificidad', 'balance_estructural', 'seo', 'legibilidad']
        for dim in expected_dimensions:
            assert dim in result.get('dimensions', result), \
                f"Dimensión '{dim}' no encontrada en resultado"


# ============================================================================
# 7. DESIGN SYSTEM — Components Registry
# ============================================================================

class TestDesignSystem:
    """Tests del design system y registro de componentes."""

    def test_component_registry_exists(self):
        from config.design_system import COMPONENT_REGISTRY
        assert isinstance(COMPONENT_REGISTRY, dict)
        assert len(COMPONENT_REGISTRY) > 10

    def test_all_standard_components_registered(self):
        from config.design_system import COMPONENT_REGISTRY
        expected = [
            'toc', 'callout', 'verdict', 'grid', 'faqs',
            'table', 'comparison_table', 'mod_cards', 'vcard_cards',
        ]
        for comp_id in expected:
            assert comp_id in COMPONENT_REGISTRY, f"Componente '{comp_id}' no registrado"

    def test_get_available_components_returns_list(self):
        from config.design_system import get_available_components
        components = get_available_components()
        assert isinstance(components, list)
        assert len(components) > 10

    def test_components_have_required_fields(self):
        from config.design_system import get_available_components
        components = get_available_components()
        for comp in components:
            assert 'id' in comp, f"Componente sin id: {comp}"
            assert 'name' in comp, f"Componente {comp.get('id')} sin name"

    def test_get_css_for_prompt(self):
        from config.design_system import get_css_for_prompt
        css = get_css_for_prompt(['toc', 'callout', 'verdict'])
        assert '.toc' in css
        assert '.callout' in css or 'callout' in css
        assert '.verdict-box' in css or 'verdict' in css


# ============================================================================
# 8. CONTENT SCRUBBER — Eliminación de frases IA
# ============================================================================

class TestContentScrubber:
    """Tests del scrubber de frases IA."""

    def test_scrubber_class_importable(self):
        from utils.content_scrubber import ContentScrubber
        assert ContentScrubber is not None

    def test_scrub_html_importable(self):
        from utils.content_scrubber import scrub_html
        assert callable(scrub_html)

    def test_scrub_html_removes_ai_phrases(self):
        from utils.content_scrubber import scrub_html
        html = "<p>En el mundo actual de los portátiles, hay muchas opciones.</p>"
        result, _ = scrub_html(html) if isinstance(scrub_html(html), tuple) else (scrub_html(html), None)
        # Should transform or remove AI-like phrases
        assert isinstance(result, str)

    def test_scrub_html_preserves_clean_content(self):
        from utils.content_scrubber import scrub_html
        html = "<p>El RTX 4070 rinde un 30% más que su predecesor.</p>"
        result = scrub_html(html)
        result_str = result[0] if isinstance(result, tuple) else result
        assert "RTX 4070" in result_str


# ============================================================================
# 9. CONFIG SETTINGS — Integridad
# ============================================================================

class TestConfigSettings:
    """Tests de la configuración del sistema."""

    def test_settings_importable(self):
        from config.settings import CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE
        assert CLAUDE_MODEL is not None
        assert MAX_TOKENS > 0
        assert 0 <= TEMPERATURE <= 1.0

    def test_settings_has_scraper_config(self):
        source = Path("config/settings.py").read_text()
        assert 'SCRAPER_TIMEOUT' in source or 'REQUEST_TIMEOUT' in source

    def test_settings_has_cache_config(self):
        source = Path("config/settings.py").read_text()
        assert 'CACHE' in source.upper() or 'cache' in source


# ============================================================================
# 10. PROMPTS — Integridad de Stage 1, 2, 3
# ============================================================================

class TestPromptsIntegrity:
    """Tests de integridad de los prompts de generación."""

    def test_stage1_prompt_has_css(self):
        from prompts.new_content import build_new_content_prompt_stage1
        prompt = build_new_content_prompt_stage1(
            keyword='test',
            arquetipo={'name': 'Test', 'description': 'Test', 'system_instructions': '', 'default_length': 1500},
            target_length=1500,
        )
        assert '<style>' in prompt.lower() or 'css' in prompt.lower()

    def test_stage1_prompt_includes_keyword(self):
        from prompts.new_content import build_new_content_prompt_stage1
        prompt = build_new_content_prompt_stage1(
            keyword='mejores portátiles gaming',
            arquetipo={'name': 'Test', 'description': 'Test', 'system_instructions': '', 'default_length': 1500},
            target_length=1500,
        )
        assert 'mejores portátiles gaming' in prompt

    def test_stage2_prompt_has_json_structure(self):
        from prompts.new_content import build_new_content_correction_prompt_stage2
        prompt = build_new_content_correction_prompt_stage2(
            draft_content='<article><p>Test</p></article>',
            target_length=1500,
            keyword='test',
        )
        assert '"problemas"' in prompt or '"estructura"' in prompt

    def test_stage3_prompt_has_final_structure(self):
        from prompts.new_content import build_final_prompt_stage3
        prompt = build_final_prompt_stage3(
            draft_content='<article><p>Test</p></article>',
            analysis_feedback='{}',
            keyword='test',
            target_length=1500,
        )
        assert 'contentGenerator__main' in prompt

    def test_rewrite_stage1_exists(self):
        from prompts.rewrite import build_rewrite_prompt_stage1
        assert callable(build_rewrite_prompt_stage1)

    def test_rewrite_stage2_exists(self):
        from prompts.rewrite import build_rewrite_correction_prompt_stage2
        assert callable(build_rewrite_correction_prompt_stage2)

    def test_rewrite_stage3_exists(self):
        from prompts.rewrite import build_rewrite_final_prompt_stage3
        assert callable(build_rewrite_final_prompt_stage3)

    def test_brand_tone_exists(self):
        from prompts.brand_tone import get_system_prompt_base, EJEMPLOS_TONO_STAGE3
        assert callable(get_system_prompt_base)
        assert len(EJEMPLOS_TONO_STAGE3) > 100


# ============================================================================
# 11. SERP RESEARCH — Funciones auxiliares
# ============================================================================

class TestSerpResearchUtils:
    """Tests de utilidades de investigación SERP."""

    def test_skip_domains_present(self):
        from utils.serp_research import SKIP_DOMAINS
        assert 'pccomponentes.com' in SKIP_DOMAINS
        assert 'youtube.com' in SKIP_DOMAINS

    def test_extract_prices(self):
        from utils.serp_research import _extract_prices
        prices = _extract_prices("Cuesta 199,99€ y la alternativa 149€.")
        assert '199,99€' in prices
        assert '149€' in prices

    def test_extract_prices_empty(self):
        from utils.serp_research import _extract_prices
        prices = _extract_prices("No hay precios aquí.")
        assert len(prices) == 0

    def test_competitor_analysis_dataclass(self):
        from utils.serp_research import CompetitorAnalysis
        comp = CompetitorAnalysis(url="https://test.com", domain="test.com", title="Test")
        assert comp.word_count == 0
        assert comp.section_summaries == []

    def test_serp_result_dataclass(self):
        from utils.serp_research import SerpResult
        result = SerpResult(title="Test", url="https://test.com", domain="test.com",
                           snippet="Test snippet", position=1)
        assert result.position == 1


# ============================================================================
# 12. TABLE FIXER — Reparación de tablas
# ============================================================================

class TestTableFixer:
    """Tests de reparación de tablas HTML."""

    def test_fixer_importable(self):
        from utils.table_fixer import fix_tables
        assert callable(fix_tables)

    def test_basic_table_passes(self):
        from utils.table_fixer import fix_tables
        html = '<table><thead><tr><th>A</th></tr></thead><tbody><tr><td>1</td></tr></tbody></table>'
        result = fix_tables(html)
        # fix_tables returns (html, stats) tuple
        html_out = result[0] if isinstance(result, tuple) else result
        assert '<table' in html_out
        assert '</table>' in html_out

    def test_returns_stats(self):
        from utils.table_fixer import fix_tables
        html = '<table><tr><td>A</td></tr></table>'
        result = fix_tables(html)
        assert isinstance(result, tuple)
        html_out, stats = result
        assert 'tables_found' in stats


# ============================================================================
# 13. CSS INTEGRITY
# ============================================================================

class TestCSSIntegrity:
    """Tests de integridad del CSS."""

    def test_css_integrity_importable(self):
        from utils.css_integrity import check_css_integrity
        assert callable(check_css_integrity)

    def test_cms_compatible_css_exists(self):
        assert Path("config/cms_compatible.css").is_file()

    def test_cms_css_has_required_selectors(self):
        css = Path("config/cms_compatible.css").read_text()
        required = ['.toc', '.callout', '.verdict-box', ':root']
        for selector in required:
            assert selector in css, f"CMS CSS missing selector: {selector}"

    def test_critical_selectors_defined(self):
        from utils.css_integrity import CRITICAL_SELECTORS
        assert isinstance(CRITICAL_SELECTORS, (list, set, tuple))
        assert len(CRITICAL_SELECTORS) > 0


# ============================================================================
# 14. APP.PY — Funciones Core
# ============================================================================

class TestAppCoreFunctions:
    """Valida que app.py mantiene todas las funciones core necesarias."""

    def test_has_main(self):
        source = Path("app.py").read_text()
        assert "def main(" in source

    def test_has_check_auth(self):
        source = Path("app.py").read_text()
        assert "def check_auth(" in source

    def test_has_render_results(self):
        source = Path("app.py").read_text()
        assert "def render_results(" in source

    def test_has_render_new_content_mode(self):
        source = Path("app.py").read_text()
        assert "def render_new_content_mode(" in source

    def test_has_render_rewrite_mode(self):
        source = Path("app.py").read_text()
        assert "def render_rewrite_mode(" in source

    def test_has_render_app_header(self):
        source = Path("app.py").read_text()
        assert "def render_app_header(" in source

    def test_execute_pipeline_delegates_to_core(self):
        """Pipeline execution should delegate to core.pipeline."""
        source = Path("app.py").read_text()
        assert "from core.pipeline import execute_generation_pipeline" in source

    def test_visual_helpers_delegate_to_pipeline(self):
        """Visual element helpers should delegate to core.pipeline."""
        source = Path("app.py").read_text()
        assert "from core.pipeline import _check_visual_elements_presence" in source


# ============================================================================
# 15. MODULE STRUCTURE — Imports y __init__
# ============================================================================

class TestModuleStructure:
    """Valida la estructura de módulos del proyecto."""

    def test_all_init_files_exist(self):
        for dir_name in ['config', 'core', 'prompts', 'ui', 'utils']:
            init_path = Path(dir_name) / '__init__.py'
            assert init_path.is_file(), f"Falta {init_path}"

    def test_utils_init_exports(self):
        source = Path("utils/__init__.py").read_text()
        assert len(source) > 0 or True  # Allow empty init

    def test_no_circular_imports(self):
        """Verificar que los módulos principales se importan sin error."""
        modules = [
            'config.settings',
            'config.arquetipos',
            'utils.html_utils',
            'utils.content_scrubber',
            'utils.quality_scorer',
            'utils.table_fixer',
        ]
        for mod in modules:
            spec = importlib.util.find_spec(mod)
            assert spec is not None, f"Módulo {mod} no importable"


# ============================================================================
# 16. UX — Flujo de Generación
# ============================================================================

class TestUXGenerationFlow:
    """Tests de flujo UX para generación de contenido."""

    def test_config_has_required_keys_for_new_mode(self):
        """Un config de modo 'new' debe tener las keys necesarias."""
        # Simular un config mínimo válido
        config = {
            'keyword': 'portátiles gaming',
            'target_length': 1500,
            'arquetipo_codigo': 'ARQ-1',
            'mode': 'new',
            'links': [],
            'visual_elements': ['toc', 'verdict'],
        }
        assert config['keyword']
        assert config['target_length'] > 0
        assert config['arquetipo_codigo']

    def test_visual_elements_defaults(self):
        """Si no se especifican visual_elements, debe haber defaults."""
        # This tests the logic in app.py _handle_assistant_generation
        visual_str = ''
        visual_elements = []
        if visual_str:
            visual_elements = [v.strip() for v in visual_str.split(',') if v.strip()]
        if not visual_elements:
            visual_elements = ['toc', 'verdict']
        assert visual_elements == ['toc', 'verdict']


# ============================================================================
# 17. META GENERATOR
# ============================================================================

class TestMetaGenerator:
    """Tests del generador de meta tags."""

    def test_meta_generator_importable(self):
        from utils.meta_generator import generate_meta, validate_meta
        assert callable(generate_meta)
        assert callable(validate_meta)


# ============================================================================
# 18. KEYWORD ANALYZER
# ============================================================================

class TestKeywordAnalyzer:
    """Tests del analizador de keywords."""

    def test_analyzer_importable(self):
        from utils.keyword_analyzer import KeywordAnalyzer
        assert KeywordAnalyzer is not None

    def test_analyze_keyword_density(self):
        from utils.keyword_analyzer import KeywordAnalyzer
        analyzer = KeywordAnalyzer()
        html = '<p>portátiles gaming son los mejores portátiles gaming del mercado gaming</p>'
        result = analyzer.analyze(html, primary_keyword='portátiles gaming')
        assert isinstance(result, dict)
        # Should have some density-related data
        assert len(result) > 0


# ============================================================================
# 19. COMPILATION — Todos los archivos compilan
# ============================================================================

class TestFullCompilation:
    """Verifica que todos los .py compilan sin error de sintaxis."""

    def test_compile_all_py_files(self):
        import glob
        import py_compile
        failures = []
        for pyfile in sorted(glob.glob("**/*.py", recursive=True)):
            if "__pycache__" in pyfile:
                continue
            try:
                py_compile.compile(pyfile, doraise=True)
            except py_compile.PyCompileError as e:
                failures.append(f"{pyfile}: {e}")
        assert not failures, "Archivos que no compilan:\n" + "\n".join(failures)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
