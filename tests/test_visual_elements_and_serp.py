"""
Tests exhaustivos — Visual Elements Pipeline + SERP Research.

Verifica que cada uno de los 21 elementos visuales tiene:
1. Instrucciones Stage 1 (borrador) con template HTML y selector CSS
2. Instrucciones Stage 3 (imperativas) con template, colocación, OBLIGATORIO
3. Checklist pre-entrega con selector CSS
4. Structure hints (placeholders en template)
5. CSS en el prompt (design_system + fallback merge)
6. Patrón de detección en app.py (_DETECT + _NAMES)
7. Consistencia selector-template ↔ detección

SERP Research:
8. format_for_prompt incluye TODOS los competidores scrapeados
9. Métricas individuales (words, H2, H3, elements) por competidor
10. Estructura de headings y resúmenes
11. Promedios competitivos, intención, búsquedas relacionadas
12. Integración con Stage 1 via guiding_context

Ejecutar: python -m pytest tests/test_visual_elements_and_serp.py -v
"""
import os
import sys
import re
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from prompts.new_content import (
    build_new_content_prompt_stage1,
    build_final_prompt_stage3,
    _build_stage3_visual_instructions,
    _build_stage3_checklist,
    _stage3_structure_hints,
    _format_visual_elements_instructions,
    _get_css_for_prompt,
    _CSS_FALLBACK,
)
from utils.serp_research import (
    format_for_prompt,
    format_for_display,
    SerpResult,
    CompetitorAnalysis,
    SerpResearchResult,
    SKIP_DOMAINS,
)


# ============================================================================
# ALL 21 VISUAL ELEMENT IDS
# ============================================================================
ALL_ELEMENTS = [
    'toc', 'callout', 'callout_promo', 'callout_alert', 'verdict',
    'grid', 'badges', 'buttons', 'faqs', 'intro_box', 'check_list',
    'specs_list', 'product_module', 'price_highlight', 'stats_grid',
    'section_divider', 'table', 'light_table', 'comparison_table',
    'mod_cards', 'vcard_cards',
]

# CSS selectors que deben estar en templates Y en detección
CSS_SELECTORS = {
    'toc': ['class="toc"'],
    'callout': ['class="callout"'],
    'callout_promo': ['callout-bf'],
    'callout_alert': ['callout-alert'],
    'verdict': ['verdict-box'],
    'grid': ['grid cols-'],
    'badges': ['class="badge'],
    'buttons': ['class="btn'],
    'faqs': ['contentgenerator__faqs', 'class="faqs'],
    'intro_box': ['class="intro"'],
    'check_list': ['check-list'],
    'specs_list': ['specs-list'],
    'product_module': ['product-module'],
    'price_highlight': ['price-highlight'],
    'stats_grid': ['font-size:32px', 'font-size: 32px'],
    'section_divider': ['linear-gradient(135deg,#170453', 'linear-gradient(135deg, #170453'],
    'table': ['<table'],
    'light_table': ['class="lt '],
    'comparison_table': ['comparison-table', 'comparison-highlight'],
    'mod_cards': ['mod-section', 'mod-grid', 'mod-card'],
    'vcard_cards': ['vcard-module', 'vcard-grid'],
}


def _has_any_selector(text: str, selectors: list) -> bool:
    """Helper: check if any selector appears in text (case-insensitive)."""
    text_lower = text.lower()
    return any(s.lower() in text_lower for s in selectors)


# ============================================================================
# 1. STAGE 1 — Visual Element Instructions
# ============================================================================
class TestStage1Instructions:
    """_format_visual_elements_instructions genera instrucciones para Stage 1."""

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_generates_instructions(self, elem):
        output = _format_visual_elements_instructions([elem])
        assert len(output) > 50, f"Stage 1: sin instrucciones para '{elem}'"

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_has_html_template(self, elem):
        output = _format_visual_elements_instructions([elem])
        assert '```' in output, f"Stage 1: sin template HTML para '{elem}'"

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_has_css_selector(self, elem):
        output = _format_visual_elements_instructions([elem])
        assert _has_any_selector(output, CSS_SELECTORS[elem]), (
            f"Stage 1: template de '{elem}' no contiene selectores {CSS_SELECTORS[elem]}"
        )

    def test_multiple_elements(self):
        combo = ['toc', 'callout', 'grid', 'table', 'faqs', 'verdict']
        output = _format_visual_elements_instructions(combo)
        for e in combo:
            assert _has_any_selector(output, CSS_SELECTORS[e]), f"'{e}' falta en combo"

    def test_header_present(self):
        output = _format_visual_elements_instructions(['toc'])
        assert 'ELEMENTOS VISUALES' in output.upper() or 'VISUAL' in output.upper()


# ============================================================================
# 2. STAGE 3 — Imperative Visual Instructions
# ============================================================================
class TestStage3Instructions:
    """_build_stage3_visual_instructions genera instrucciones imperativas."""

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_generates_instructions(self, elem):
        output = _build_stage3_visual_instructions([elem])
        assert len(output) > 50, f"Stage 3: sin instrucciones para '{elem}'"

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_has_html_template(self, elem):
        output = _build_stage3_visual_instructions([elem])
        assert '```' in output, f"Stage 3: sin template para '{elem}'"

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_has_placement(self, elem):
        output = _build_stage3_visual_instructions([elem]).lower()
        keywords = ['coloca', 'inserta', 'obligatorio', 'después', 'antes', 'dentro', 'usa']
        assert any(k in output for k in keywords), f"Stage 3: sin placement para '{elem}'"

    def test_obligatorio_header(self):
        output = _build_stage3_visual_instructions(['toc', 'callout'])
        assert 'OBLIGATORI' in output.upper()

    def test_error_critico_warning(self):
        output = _build_stage3_visual_instructions(['toc', 'callout'])
        assert 'ERROR' in output.upper() and 'CRÍTICO' in output.upper()

    def test_disambiguation_with_mod_cards_and_basic(self):
        output = _build_stage3_visual_instructions(['mod_cards', 'callout', 'grid'])
        assert 'DISTINTOS' in output or 'DIFERENTES' in output
        assert 'NO sustituye' in output or 'no sustituye' in output.lower()

    def test_no_disambiguation_without_conflict(self):
        output = _build_stage3_visual_instructions(['toc', 'table', 'verdict'])
        assert 'DISTINTOS' not in output


# ============================================================================
# 3. STAGE 3 — Checklist Pre-Entrega
# ============================================================================
class TestStage3Checklist:
    """_build_stage3_checklist genera checklist con selectores CSS."""

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_has_checklist_entry(self, elem):
        checklist = _build_stage3_checklist([elem])
        assert '[ ]' in checklist, f"Checklist: sin entrada para '{elem}'"

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_checklist_has_selector(self, elem):
        checklist = _build_stage3_checklist([elem])
        selectors = CSS_SELECTORS[elem]
        assert _has_any_selector(checklist, selectors), (
            f"Checklist de '{elem}' sin selector. Esperados: {selectors}"
        )

    def test_always_includes_verdict_and_faqs(self):
        checklist = _build_stage3_checklist(['toc'])
        assert 'verdict-box' in checklist.lower()
        assert 'contentgenerator__faqs' in checklist.lower()

    def test_no_duplicate_verdict(self):
        checklist = _build_stage3_checklist(['verdict', 'toc'])
        assert checklist.lower().count('verdict-box') == 1


# ============================================================================
# 4. STAGE 3 — Structure Hints
# ============================================================================
class TestStage3Hints:
    """_stage3_structure_hints genera placeholders HTML."""

    @pytest.mark.parametrize("elem", [e for e in ALL_ELEMENTS if e not in ('verdict', 'faqs')])
    def test_has_structure_hint(self, elem):
        hints = _stage3_structure_hints([elem])
        assert 'obligatori' in hints.lower() or '<!--' in hints

    def test_empty_returns_default(self):
        hints = _stage3_structure_hints([])
        assert '<!-- contenido -->' in hints


# ============================================================================
# 5. CSS Coverage
# ============================================================================
class TestCSSCoverage:
    """CSS inyectado en prompt incluye estilos para todos los componentes."""

    @pytest.mark.parametrize("elem,marker", [
        ('toc', '.toc'),
        ('callout', '.callout{'),
        ('callout_promo', '.callout-bf'),
        ('callout_alert', '.callout-alert'),
        ('verdict', '.verdict-box'),
        ('grid', '.grid'),
        ('faqs', '.faqs'),
        ('intro_box', '.intro{'),
        ('check_list', '.check-list'),
        ('specs_list', '.specs-list'),
        ('product_module', '.product-module'),
        ('price_highlight', '.price-highlight'),
        ('table', 'table{'),
        ('light_table', '.lt'),
        ('mod_cards', '.mod-card'),
    ])
    def test_css_has_styles(self, elem, marker):
        css = _get_css_for_prompt(visual_elements=[elem])
        assert marker in css, f"CSS falta estilos para '{elem}' (buscando '{marker}')"


# ============================================================================
# 6. Detection Patterns in app.py
# ============================================================================
class TestDetectionPatterns:
    """core/pipeline.py tiene patterns de detección para cada elemento visual.

    NOTA v5.1: _check_visual_elements_presence se movió de app.py a core/pipeline.py.
    """

    @pytest.fixture(scope="class")
    def pipeline_src(self):
        return open('core/pipeline.py').read()

    @pytest.fixture(scope="class")
    def detect_block(self, pipeline_src):
        idx = pipeline_src.index('def _detect_missing_visual_elements')
        return pipeline_src[idx:idx+4000]

    @pytest.fixture(scope="class")
    def names_block(self, pipeline_src):
        idx = pipeline_src.index('def _get_visual_element_names')
        return pipeline_src[idx:idx+3000]

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_detect_pattern_exists(self, detect_block, elem):
        assert f"'{elem}'" in detect_block, f"No hay patrón de detección para '{elem}'"

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_display_name_exists(self, names_block, elem):
        assert f"'{elem}'" in names_block, f"No hay nombre legible para '{elem}' en _get_visual_element_names"


# ============================================================================
# 7. Consistency — Stage 3 templates match detection selectors
# ============================================================================
class TestConsistency:

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_template_matches_detection(self, elem):
        stage3 = _build_stage3_visual_instructions([elem])
        assert _has_any_selector(stage3, CSS_SELECTORS[elem]), (
            f"Inconsistencia: Stage 3 de '{elem}' no usa selectores que el detector busca"
        )


# ============================================================================
# 8. Full Stage 3 Prompt Integration
# ============================================================================
class TestStage3FullPrompt:

    def _prompt(self, elements):
        return build_final_prompt_stage3(
            draft_content="<h2>Test</h2><p>Borrador.</p>",
            analysis_feedback="Mejorar estructura.",
            keyword="test", target_length=1500, visual_elements=elements,
        )

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_prompt_contains_element(self, elem):
        prompt = self._prompt([elem])
        assert _has_any_selector(prompt, CSS_SELECTORS[elem])

    def test_has_checklist_section(self):
        assert 'CHECKLIST' in self._prompt(['toc', 'callout']).upper()

    def test_has_style_block(self):
        assert '<style>' in self._prompt(['callout']).lower()

    def test_order_visual_before_reglas_before_checklist(self):
        prompt = self._prompt(['toc', 'callout']).upper()
        i_visual = prompt.find('ELEMENTOS VISUALES')
        i_reglas = prompt.find('REGLAS ABSOLUTAS')
        i_check = prompt.find('CHECKLIST')
        assert 0 < i_visual < i_reglas < i_check


# ============================================================================
# 9. Full Stage 1 Prompt Integration
# ============================================================================
class TestStage1FullPrompt:

    def _prompt(self, elements):
        arq = {'name': 'Guía', 'description': 'Test', 'system_instructions': '', 'default_length': 1500}
        return build_new_content_prompt_stage1(
            keyword="test", arquetipo=arq, target_length=1500, visual_elements=elements,
        )

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_prompt_contains_element(self, elem):
        prompt = self._prompt([elem])
        assert _has_any_selector(prompt, CSS_SELECTORS[elem])


# ============================================================================
# SERP RESEARCH TESTS
# ============================================================================

def _build_research(n_competitors=3, n_results=5):
    """Factory: crea SerpResearchResult con N competidores realistas."""
    data = [
        ("xataka.com", "Mejores LEGO adultos - Xataka", 3200, 8, 15, True, True, 12, 6,
         ["H2: Qué son los LEGO adultos", "  H3: Tipos", "H2: Mejores sets"],
         "Análisis completo de sets LEGO para adultos con comparativa técnica."),
        ("computerhoy.com", "Guía LEGO adultos", 2500, 6, 12, True, False, 8, 4,
         ["H2: Top LEGO", "H2: Cómo elegir", "H2: Precios"],
         "Guía de compra con precios y recomendaciones."),
        ("hardzone.es", "Mejores sets LEGO ranking", 4100, 10, 20, True, True, 15, 8,
         ["H2: Criterios", "H2: Top 10", "H2: Veredicto"],
         "Review técnica con tests de calidad."),
        ("profesionalreview.com", "LEGO adultos review", 2800, 7, 14, False, True, 10, 5,
         ["H2: Análisis", "H2: Conclusiones"],
         "Review profesional de sets LEGO."),
        ("geeknetic.es", "Mejores LEGO 2025", 3500, 9, 18, True, False, 11, 7,
         ["H2: Novedades 2025", "H2: Clásicos", "H2: Sets premium"],
         "Artículo actualizado con novedades 2025."),
    ]

    competitors = [
        CompetitorAnalysis(
            url=f"https://{d[0]}/art", domain=d[0], title=d[1],
            word_count=d[2], h2_count=d[3], h3_count=d[4],
            has_table=d[5], has_faq=d[6], image_count=d[7], list_count=d[8],
            heading_structure=d[9], content_summary=d[10],
        )
        for d in data[:n_competitors]
    ]

    serps = [
        SerpResult(title=d[1][:30], url=f"https://{d[0]}/art",
                   domain=d[0], snippet="", position=i + 1)
        for i, d in enumerate(data[:n_results])
    ] + [
        SerpResult(title="Amazon LEGO", url="https://amazon.es/lego",
                   domain="amazon.es", snippet="", position=n_results + 1),
    ]

    return SerpResearchResult(
        keyword="mejores legos para adultos",
        serp_results=serps, competitors=competitors,
        related_searches=["lego adultos baratos", "lego architecture", "lego technic adultos", "lego star wars adultos"],
        insights={
            'intent': 'mixed_transactional_informational',
            'avg_word_count': sum(d[2] for d in data[:n_competitors]) // max(n_competitors, 1),
            'avg_h2': sum(d[3] for d in data[:n_competitors]) // max(n_competitors, 1),
            'has_retailers': True, 'has_review_sites': True, 'has_pccom': False,
            'competitors_scraped': n_competitors,
        },
    )


# ============================================================================
# 10. format_for_prompt — Multi-competitor Context
# ============================================================================
class TestSerpFormatMultiCompetitor:
    """format_for_prompt debe incluir datos de TODOS los competidores."""

    def test_all_competitors_present(self):
        output = format_for_prompt(_build_research(n_competitors=4))
        for domain in ["xataka.com", "computerhoy.com", "hardzone.es", "profesionalreview.com"]:
            assert domain in output, f"Competidor {domain} no aparece"

    def test_word_counts_per_competitor(self):
        output = format_for_prompt(_build_research(n_competitors=3))
        assert "3200" in output  # xataka
        assert "2500" in output  # computerhoy
        assert "4100" in output  # hardzone

    def test_heading_structure_included(self):
        output = format_for_prompt(_build_research(n_competitors=2))
        assert "H2:" in output

    def test_content_summaries_included(self):
        output = format_for_prompt(_build_research(n_competitors=2))
        assert "Resumen:" in output or "comparativa" in output.lower()

    def test_elements_detected(self):
        output = format_for_prompt(_build_research(n_competitors=3)).lower()
        assert "tabla" in output or "faq" in output.lower()

    def test_averages_included(self):
        output = format_for_prompt(_build_research(n_competitors=3))
        assert "Promedio" in output or "promedio" in output.lower()

    def test_related_searches_included(self):
        output = format_for_prompt(_build_research())
        for term in ["lego adultos baratos", "lego architecture"]:
            assert term in output, f"Related search '{term}' missing"

    def test_serp_positions(self):
        output = format_for_prompt(_build_research())
        assert "#1" in output and "#2" in output

    def test_intent_recommendations(self):
        output = format_for_prompt(_build_research())
        # Has both retailers (Amazon) and review sites
        assert "TRANSACCIONAL" in output.upper() or "transaccional" in output.lower()
        assert "INFORMATIV" in output.upper() or "informativ" in output.lower()

    def test_competitive_length_recommendation(self):
        output = format_for_prompt(_build_research(n_competitors=3))
        assert "palabras" in output.lower()

    def test_h2_recommendation(self):
        output = format_for_prompt(_build_research(n_competitors=3))
        assert "H2" in output

    def test_single_competitor_still_works(self):
        output = format_for_prompt(_build_research(n_competitors=1))
        assert "xataka.com" in output and "3200" in output

    def test_zero_competitors_no_crash(self):
        output = format_for_prompt(_build_research(n_competitors=0))
        assert "mejores legos" in output.lower()

    def test_five_competitors_all_present(self):
        """Con 5 competidores scrapeados, todos deben aparecer."""
        output = format_for_prompt(_build_research(n_competitors=5))
        for domain in ["xataka.com", "computerhoy.com", "hardzone.es",
                        "profesionalreview.com", "geeknetic.es"]:
            assert domain in output, f"Competidor {domain} falta con 5 scrapeados"


# ============================================================================
# 11. SerpResearchResult — Computed Properties
# ============================================================================
class TestSerpProperties:

    def test_avg_word_count(self):
        r = _build_research(n_competitors=3)
        assert r.avg_word_count == (3200 + 2500 + 4100) // 3

    def test_avg_ignores_failures(self):
        r = SerpResearchResult(keyword="t", competitors=[
            CompetitorAnalysis(url="a", domain="a", title="", word_count=2000),
            CompetitorAnalysis(url="b", domain="b", title="", word_count=0, success=False),
        ])
        assert r.avg_word_count == 2000

    def test_avg_zero_when_empty(self):
        assert SerpResearchResult(keyword="t").avg_word_count == 0

    def test_has_pccom(self):
        r = SerpResearchResult(keyword="t", serp_results=[
            SerpResult(title="", url="", domain="www.pccomponentes.com", snippet="", position=1),
        ])
        assert r.has_pccom is True

    def test_has_retailers(self):
        r = SerpResearchResult(keyword="t", serp_results=[
            SerpResult(title="", url="", domain="amazon.es", snippet="", position=1),
        ])
        assert r.has_retailers is True

    def test_has_review_sites(self):
        r = SerpResearchResult(keyword="t", serp_results=[
            SerpResult(title="", url="", domain="xataka.com", snippet="", position=1),
        ])
        assert r.has_review_sites is True


# ============================================================================
# 12. SERP — Domain Filtering
# ============================================================================
class TestSerpFiltering:

    def test_skip_domains_include_common(self):
        for domain in ['pccomponentes.com', 'youtube.com', 'amazon.', 'reddit.com']:
            assert domain in SKIP_DOMAINS, f"'{domain}' should be in SKIP_DOMAINS"

    def test_max_scrape_default_is_5(self):
        """max_scrape default should be 5 for rich context."""
        import inspect
        from utils.serp_research import research_serp
        sig = inspect.signature(research_serp)
        default = sig.parameters['max_scrape'].default
        assert default >= 5, f"max_scrape default is {default}, should be ≥5"


# ============================================================================
# 13. format_for_display (UI)
# ============================================================================
class TestSerpDisplay:

    def test_not_empty(self):
        output = format_for_display(_build_research())
        assert len(output) > 100

    def test_has_markup(self):
        output = format_for_display(_build_research())
        assert "**" in output or "#" in output


# ============================================================================
# 14. Integration — SERP context in Stage 1
# ============================================================================
class TestSerpStage1Integration:

    def _arq(self):
        return {'name': 'Guía', 'description': 'T', 'system_instructions': '', 'default_length': 1500}

    def test_serp_context_injected(self):
        serp_ctx = "## ANÁLISIS SERP\n- xataka: 3200 palabras"
        prompt = build_new_content_prompt_stage1(
            keyword="test", arquetipo=self._arq(), target_length=1500, guiding_context=serp_ctx,
        )
        assert "xataka" in prompt.lower() or "3200" in prompt

    def test_combined_with_user_context(self):
        combined = "El usuario quiere portátiles ligeros.\n\n## SERP\nCompetidores analizan portabilidad."
        prompt = build_new_content_prompt_stage1(
            keyword="test", arquetipo=self._arq(), target_length=1500, guiding_context=combined,
        )
        assert "ligeros" in prompt.lower() or "portabilidad" in prompt.lower()


# ============================================================================
# 15. Context Richness — Verify SERP output has enough detail for Claude
# ============================================================================
class TestSerpContextRichness:
    """Verify that format_for_prompt generates context rich enough to be useful."""

    def test_output_has_meaningful_length(self):
        """Output should be >500 chars for 3 competitors."""
        output = format_for_prompt(_build_research(n_competitors=3))
        assert len(output) > 500, f"Output too short ({len(output)} chars) for 3 competitors"

    def test_output_has_structured_sections(self):
        output = format_for_prompt(_build_research())
        sections = ['posiciona en las SERPs', 'Análisis de competidores', 'Recomendaciones', 'Búsquedas relacionadas']
        for section in sections:
            assert section.lower() in output.lower(), f"Sección '{section}' falta"

    def test_heading_structure_provides_seed(self):
        """Heading structure should be detailed enough to seed Claude's outline."""
        output = format_for_prompt(_build_research(n_competitors=2))
        # Should have actual heading text, not just counts
        assert "Qué son los LEGO" in output or "Top LEGO" in output

    def test_per_competitor_element_detection(self):
        """Each competitor should have its element types listed."""
        output = format_for_prompt(_build_research(n_competitors=3))
        # xataka has tables + FAQs + 12 imgs + 6 lists
        assert "tablas" in output.lower()
        assert "imgs" in output.lower() or "imag" in output.lower()


# ============================================================================
# 16. Auto-retry: _detect_missing_visual_elements
# ============================================================================
class TestDetectMissingElements:
    """Verifica que _detect_missing_visual_elements funciona correctamente.

    NOTA v5.1: Función movida de app.py a core/pipeline.py. Se importa directamente.
    """

    def _import_func(self):
        from core.pipeline import _detect_missing_visual_elements
        return _detect_missing_visual_elements

    def test_detects_missing_callout(self):
        func = self._import_func()
        html = '<div class="toc">TOC</div><table><tr><td>data</td></tr></table>'
        missing = func(html, ['toc', 'callout', 'table'])
        assert 'callout' in missing
        assert 'toc' not in missing
        assert 'table' not in missing

    def test_detects_all_present(self):
        func = self._import_func()
        html = '<nav class="toc">TOC</nav><div class="callout">Info</div><table><tr><td>x</td></tr></table>'
        missing = func(html, ['toc', 'callout', 'table'])
        assert missing == []

    def test_detects_multiple_missing(self):
        func = self._import_func()
        html = '<p>Simple text</p>'
        missing = func(html, ['toc', 'callout', 'grid', 'table'])
        assert set(missing) == {'toc', 'callout', 'grid', 'table'}

    def test_empty_html(self):
        func = self._import_func()
        missing = func('', ['toc'])
        assert 'toc' in missing

    def test_empty_elements(self):
        func = self._import_func()
        missing = func('<div class="toc">x</div>', [])
        assert missing == []

    def test_mod_cards_detection(self):
        func = self._import_func()
        html = '<div class="mod-section"><div class="mod-grid"><div class="mod-card">Card</div></div></div>'
        missing = func(html, ['mod_cards'])
        assert missing == []

    def test_vcard_detection(self):
        func = self._import_func()
        html = '<div class="vcard-module"><div class="vcard-grid">Cards</div></div>'
        missing = func(html, ['vcard_cards'])
        assert missing == []

    def test_case_insensitive(self):
        func = self._import_func()
        html = '<div CLASS="callout">Info</div>'
        missing = func(html, ['callout'])
        assert missing == []


# ============================================================================
# 17. Auto-retry: _auto_retry_missing_elements prompt structure
# ============================================================================
class TestAutoRetryPrompt:
    """Verifica que auto-retry construye un prompt correcto.

    NOTA v5.1: Funciones movidas de app.py a core/pipeline.py.
    """

    def test_auto_retry_function_exists(self):
        """_auto_retry_missing_elements debe existir en core/pipeline.py."""
        src = open("core/pipeline.py").read()
        assert 'def _auto_retry_missing_elements(' in src

    def test_retry_uses_visual_instructions(self):
        """El retry debe usar _build_stage3_visual_instructions para los templates."""
        src = open("core/pipeline.py").read()
        assert '_build_stage3_visual_instructions' in src

    def test_retry_has_strict_rules(self):
        """El prompt de retry debe tener reglas de no-modificación."""
        src = open("core/pipeline.py").read()
        idx = src.index('def _auto_retry_missing_elements')
        block = src[idx:idx + 3000]
        assert 'NO modifiques' in block or 'NO elimines' in block

    def test_retry_limited_to_3_elements(self):
        """_check_visual_elements_presence solo hace retry si ≤3 faltantes."""
        src = open("core/pipeline.py").read()
        idx = src.index('def _check_visual_elements_presence')
        block = src[idx:idx + 1000]
        assert '<= 3' in block or '≤ 3' in block


# ============================================================================
# 18. Refinement context: generation_metadata injection
# ============================================================================
class TestRefinementContext:
    """Verifica que el prompt de refinamiento incluye contexto de generación."""

    def _get_refinement_block(self):
        src = open("ui/results.py").read()
        idx = src.index('def _execute_refinement')
        return src[idx:idx + 4000]

    def test_reads_generation_metadata(self):
        block = self._get_refinement_block()
        assert 'generation_metadata' in block

    def test_includes_keyword(self):
        block = self._get_refinement_block()
        assert 'keyword' in block.lower()

    def test_includes_arquetipo(self):
        block = self._get_refinement_block()
        assert 'arquetipo' in block.lower()

    def test_includes_visual_elements(self):
        block = self._get_refinement_block()
        assert 'visual_elements' in block or 'visual_elems' in block

    def test_includes_target_length(self):
        block = self._get_refinement_block()
        assert 'target_length' in block

    def test_context_section_built(self):
        """Debe construir sección CONTEXTO DE GENERACIÓN."""
        block = self._get_refinement_block()
        assert 'CONTEXTO DE GENERACIÓN' in block or 'CONTEXTO DE GENERACI' in block

    def test_includes_secondary_keywords(self):
        block = self._get_refinement_block()
        assert 'keywords' in block.lower() or 'secundarias' in block.lower()


# ============================================================================
# 19. REWRITE Stage 3 — Visual Elements Parity
# ============================================================================
class TestRewriteStage3VisualElements:
    """Verifica que rewrite Stage 3 ahora incluye visual elements como new mode."""

    def _prompt(self, elements):
        from prompts.rewrite import build_rewrite_final_prompt_stage3
        config = {
            'keyword': 'test keyword', 'target_length': 1500,
            'rewrite_mode': 'single', 'rewrite_instructions': {},
            'visual_elements': elements,
        }
        return build_rewrite_final_prompt_stage3(
            draft_content='<h2>Test</h2><p>Borrador.</p>',
            corrections_json='{"ok": true}',
            config=config,
        )

    @pytest.mark.parametrize("elem", ALL_ELEMENTS)
    def test_rewrite_stage3_contains_element(self, elem):
        """Rewrite Stage 3 must include instructions for each visual element."""
        prompt = self._prompt([elem])
        assert _has_any_selector(prompt, CSS_SELECTORS[elem]), (
            f"Rewrite Stage 3 no contiene selector para '{elem}'"
        )

    def test_rewrite_has_checklist(self):
        prompt = self._prompt(['toc', 'callout', 'grid'])
        assert 'CHECKLIST' in prompt.upper()

    def test_rewrite_has_css(self):
        prompt = self._prompt(['callout'])
        assert 'css' in prompt.lower()

    def test_rewrite_has_obligatorio(self):
        prompt = self._prompt(['toc', 'callout'])
        assert 'OBLIGATORI' in prompt.upper()

    def test_rewrite_without_elements_still_works(self):
        """Sin visual elements, el prompt debe funcionar normalmente."""
        prompt = self._prompt([])
        assert 'VERSIÓN FINAL' in prompt
        assert 'CHECKLIST' not in prompt.upper()


# ============================================================================
# 20. Enriched SERP Extraction
# ============================================================================
class TestEnrichedSerpExtraction:
    """Verifica que la extracción enriquecida de competidores funciona."""

    def _html(self):
        return """<article>
<h2>Los mejores portátiles gaming 2025</h2>
<p>Guía completa para elegir tu portátil gaming ideal.</p>
<h3>1. ASUS ROG Strix G16 - El más potente</h3>
<p>El ASUS ROG Strix G16 con RTX 4070 y Core i9 14900HX ofrece rendimiento brutal por 1.799€. Pantalla 16" QHD 240Hz, 32GB DDR5.</p>
<h3>2. Lenovo Legion Pro 5 - Mejor calidad-precio</h3>
<p>A 1.299€ el Lenovo Legion Pro 5 monta Ryzen 9 7945HX y RTX 4060. 16" WQXGA 165Hz, 16GB DDR5, 1TB SSD.</p>
<h3>Cómo elegir un portátil gaming</h3>
<p>Los factores clave son GPU, CPU, pantalla y refrigeración. El presupuesto mínimo recomendado es 999€.</p>
</article>"""

    def test_section_summaries_extracted(self):
        from utils.serp_research import _extract_section_summaries
        sections = _extract_section_summaries(self._html())
        assert len(sections) >= 3
        # Should have product specs, not just titles
        combined = ' '.join(sections)
        assert '1.799€' in combined or 'RTX 4070' in combined

    def test_section_has_heading_and_content(self):
        from utils.serp_research import _extract_section_summaries
        sections = _extract_section_summaries(self._html())
        for s in sections:
            assert 'H2:' in s or 'H3:' in s
            assert '\n  ' in s  # Has indented content

    def test_section_max_limit(self):
        from utils.serp_research import _extract_section_summaries
        sections = _extract_section_summaries(self._html(), max_sections=2)
        assert len(sections) <= 2

    def test_products_extracted(self):
        from utils.serp_research import _extract_products_mentioned
        from bs4 import BeautifulSoup
        text = BeautifulSoup(self._html(), 'html.parser').get_text()
        products = _extract_products_mentioned(text)
        assert any('ASUS' in p for p in products)
        assert any('Lenovo' in p for p in products)

    def test_products_no_stopwords(self):
        from utils.serp_research import _extract_products_mentioned
        products = _extract_products_mentioned("El HyperX Cloud III es muy bueno. Samsung Galaxy S25 para todos.")
        for p in products:
            assert not p.lower().endswith(' es')
            assert not p.lower().endswith(' para')

    def test_prices_extracted(self):
        from utils.serp_research import _extract_prices
        text = "El precio es 1.799€ y la alternativa cuesta 1.299€. También hay opciones desde 999€."
        prices = _extract_prices(text)
        assert '1.799€' in prices
        assert '1.299€' in prices
        assert '999€' in prices

    def test_prices_deduped(self):
        from utils.serp_research import _extract_prices
        text = "Cuesta 89,99€ en Amazon y 89,99€ en PcComponentes."
        prices = _extract_prices(text)
        assert prices.count('89,99€') == 1

    def test_format_for_prompt_includes_sections(self):
        """format_for_prompt debe incluir section_summaries si están disponibles."""
        research = _build_research(n_competitors=1)
        # Enrich first competitor with section_summaries
        research.competitors[0].section_summaries = [
            "H3: Producto Test\n  Specs concretas del producto a 199€"
        ]
        research.competitors[0].products_mentioned = ["Producto Test X1"]
        research.competitors[0].prices_found = ["199€"]
        output = format_for_prompt(research)
        assert "Contenido clave" in output
        assert "199€" in output
        assert "Producto Test X1" in output

    def test_format_falls_back_to_summary(self):
        """Sin section_summaries, debe usar content_summary."""
        research = _build_research(n_competitors=1)
        research.competitors[0].section_summaries = []
        research.competitors[0].content_summary = "Resumen legacy del artículo"
        output = format_for_prompt(research)
        assert "Resumen:" in output

    def test_competitor_analysis_has_new_fields(self):
        """CompetitorAnalysis debe tener los 3 campos nuevos."""
        c = CompetitorAnalysis(url="test", domain="test", title="test")
        assert hasattr(c, 'section_summaries')
        assert hasattr(c, 'products_mentioned')
        assert hasattr(c, 'prices_found')
        assert c.section_summaries == []
        assert c.products_mentioned == []
        assert c.prices_found == []


# ============================================================================
# 21. AI Phrase Detection
# ============================================================================
class TestAIPhraseDetection:
    """Verifica detección programática de frases IA."""

    def test_detects_common_phrases(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>En el mundo actual, es importante destacar que sin lugar a dudas...</p>'
        result = detect_ai_phrases(html)
        phrases = [r['phrase'] for r in result]
        assert 'En el mundo actual...' in phrases
        assert 'Es importante destacar...' in phrases
        assert 'Sin lugar a dudas...' in phrases

    def test_clean_content_no_detection(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>Este portátil monta un Ryzen 7 7800X3D. Para gaming, va sobrado.</p>'
        assert detect_ai_phrases(html) == []

    def test_ignores_css_and_tags(self):
        from utils.html_utils import detect_ai_phrases
        html = '<style>.en-el-mundo-actual{color:red}</style><p>Contenido limpio.</p>'
        assert detect_ai_phrases(html) == []

    def test_context_included(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>Como sabemos, a la hora de elegir un portátil hay que mirar el procesador.</p>'
        result = detect_ai_phrases(html)
        assert len(result) >= 1
        assert 'context' in result[0]
        assert len(result[0]['context']) > 10

    def test_empty_html(self):
        from utils.html_utils import detect_ai_phrases
        assert detect_ai_phrases('') == []
        assert detect_ai_phrases(None) == []

    def test_returns_phrase_and_context(self):
        from utils.html_utils import detect_ai_phrases
        html = '<p>Cabe mencionar que este modelo es bueno.</p>'
        result = detect_ai_phrases(html)
        assert len(result) == 1
        assert result[0]['phrase'] == 'Cabe mencionar que...'


# ============================================================================
# 22. Refinement Tone Examples
# ============================================================================
class TestRefinementToneExamples:
    """Verifica que el refinement prompt incluye ejemplos de tono."""

    def _get_refinement_block(self):
        src = open("ui/results.py").read()
        idx = src.index('def _execute_refinement')
        return src[idx:idx + 5000]

    def test_imports_tone_examples(self):
        block = self._get_refinement_block()
        assert 'EJEMPLOS_TONO_STAGE3' in block

    def test_has_before_after_examples(self):
        block = self._get_refinement_block()
        # The examples should be injected in the prompt template
        assert 'EJEMPLOS_TONO_STAGE3' in block


# ============================================================================
# 23. Stage 3 New Content Tone Examples
# ============================================================================
class TestStage3ToneExamples:
    """Verifica que Stage 3 new content incluye ejemplos contrastados."""

    def test_stage3_has_before_after(self):
        from prompts.new_content import build_final_prompt_stage3
        prompt = build_final_prompt_stage3(
            draft_content='<h2>Test</h2>',
            analysis_feedback='{}',
            keyword='test', target_length=1500,
        )
        assert '❌' in prompt and '✅' in prompt

    def test_stage3_has_pccomponentes_examples(self):
        from prompts.new_content import build_final_prompt_stage3
        prompt = build_final_prompt_stage3(
            draft_content='<h2>Test</h2>',
            analysis_feedback='{}',
            keyword='test', target_length=1500,
        )
        assert '144Hz' in prompt or 'partidas' in prompt

    def test_brand_tone_has_ejemplos(self):
        from prompts.brand_tone import EJEMPLOS_TONO_STAGE3
        assert len(EJEMPLOS_TONO_STAGE3) > 500
        assert '❌' in EJEMPLOS_TONO_STAGE3
        assert '✅' in EJEMPLOS_TONO_STAGE3
