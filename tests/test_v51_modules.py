# -*- coding: utf-8 -*-
"""
Tests de Pipeline y Módulos v5.1 - PcComponentes Content Generator

Cobertura:
- Content Scrubber: watermarks, em-dashes, idempotencia, edge cases
- Quality Scorer: 5 dimensiones, threshold, priority fixes, contenido bueno/malo
- Keyword Analyzer: density, placements, distribution, stuffing
- Opportunity Scorer: classification, scoring, quick wins, batch
- CMS Publisher: validation, factory, PcComponentes adapter
- CSS Integrity: detección de drift
- Prompt Optimizer: minificación, estimación de tokens
- Pipeline Integration: flujo completo simulado (sin API calls)

Ejecutar: pytest tests/test_v51_modules.py -v
"""

import re
import sys
import os

# Asegurar que el directorio raíz está en el path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# CONTENT SCRUBBER
# ============================================================================

class TestContentScrubber:
    """Tests para utils/content_scrubber.py"""

    def test_remove_zero_width_spaces(self):
        from utils.content_scrubber import scrub_html
        html = '<p>Hola\u200Bmundo\u200Btest</p>'
        cleaned, stats = scrub_html(html)
        assert '\u200B' not in cleaned
        assert stats['unicode_removed'] >= 2

    def test_remove_bom(self):
        from utils.content_scrubber import scrub_html
        html = '\uFEFF<p>Contenido con BOM</p>'
        cleaned, stats = scrub_html(html)
        assert '\uFEFF' not in cleaned
        assert stats['unicode_removed'] >= 1

    def test_remove_format_control_chars(self):
        from utils.content_scrubber import scrub_html
        html = '<p>Texto\u200Econ\u200Fcontrol</p>'
        cleaned, stats = scrub_html(html)
        assert '\u200E' not in cleaned
        assert '\u200F' not in cleaned

    def test_emdash_with_spaces_replaced(self):
        from utils.content_scrubber import scrub_html
        html = '<p>Texto largo — además de más texto</p>'
        cleaned, stats = scrub_html(html)
        assert '—' not in cleaned
        assert stats['emdashes_replaced'] >= 1

    def test_emdash_without_spaces_preserved(self):
        from utils.content_scrubber import scrub_html
        html = '<p>Texto em—dash sin espacios</p>'
        cleaned, stats = scrub_html(html)
        assert '—' in cleaned  # Sin espacios, no toca
        assert stats['emdashes_replaced'] == 0

    def test_emdash_in_html_attr_preserved(self):
        from utils.content_scrubber import scrub_html
        html = '<a title="algo — otro">texto</a>'
        cleaned, stats = scrub_html(html)
        assert '—' in cleaned  # Dentro de atributo, no toca

    def test_conjunctive_emdash_becomes_semicolon(self):
        from utils.content_scrubber import scrub_html
        html = '<p>El resultado — sin embargo, hay dudas</p>'
        cleaned, _ = scrub_html(html)
        assert '; sin embargo' in cleaned

    def test_idempotent(self):
        from utils.content_scrubber import scrub_html
        html = '<p>Contenido normal sin problemas.</p>'
        c1, s1 = scrub_html(html)
        c2, s2 = scrub_html(c1)
        assert c1 == c2
        assert sum(s2.values()) == 0

    def test_empty_input(self):
        from utils.content_scrubber import scrub_html
        cleaned, stats = scrub_html('')
        assert cleaned == ''
        assert sum(stats.values()) == 0

    def test_cleans_double_spaces(self):
        from utils.content_scrubber import scrub_html
        html = '<p>Texto  con   espacios  dobles</p>'
        cleaned, _ = scrub_html(html)
        assert '  ' not in re.sub(r'<[^>]+>', '', cleaned)


# ============================================================================
# QUALITY SCORER
# ============================================================================

class TestQualityScorer:
    """Tests para utils/quality_scorer.py"""

    def _good_html(self):
        return '''<article class="contentGenerator__main">
        <h2>Los mejores portátiles gaming de 2025</h2>
        <p>¿Buscas un portátil gaming? Carlos invirtió 1.200€ en el ASUS ROG Strix G15 
        y obtuvo 85 fps en Cyberpunk 2077 (eso sí, con ventiladores a tope).</p>
        <h3>Qué GPU elegir</h3>
        <p>Un RTX 4060 rinde un 45% más que la generación anterior. Laura compró el MSI 
        Katana por 999€ y ahora renderiza un 60% más rápido.</p>
        <p>Echa un vistazo a <a href="https://www.pccomponentes.com/gaming">nuestra selección</a>.</p>
        <p>Mira el <a href="https://www.pccomponentes.com/asus-rog">ASUS ROG</a> para ver precio.</p>
        </article>
        <article class="contentGenerator__faqs"><h2>FAQs portátiles gaming</h2></article>
        <article class="contentGenerator__verdict"><div class="verdict-box"><h2>Veredicto</h2>
        <p>El ASUS ROG ofrece la mejor relación calidad-precio en 2025.</p></div></article>'''

    def _bad_html(self):
        return '''<article class="contentGenerator__main">
        <h2>Título genérico</h2>
        <p>En el mundo actual, es importante destacar que la tecnología es fundamental. 
        Cabe mencionar que en la era digital, esto se traduce en avances. Sin lugar a dudas,
        resulta especialmente importante tener en cuenta varios factores fundamentales.</p>
        </article>'''

    def test_good_content_passes(self):
        from utils.quality_scorer import score_content
        result = score_content(self._good_html(), keyword='portátiles gaming')
        assert result['passed'] is True
        assert result['composite_score'] >= 70

    def test_bad_content_fails(self):
        from utils.quality_scorer import score_content
        result = score_content(self._bad_html(), keyword='portátiles gaming')
        assert result['passed'] is False
        assert result['composite_score'] < 70

    def test_dimensions_present(self):
        from utils.quality_scorer import score_content
        result = score_content(self._good_html(), keyword='test')
        expected_dims = ['humanidad', 'especificidad', 'balance_estructural', 'seo', 'legibilidad']
        for dim in expected_dims:
            assert dim in result['dimensions']
            assert 'score' in result['dimensions'][dim]
            assert 'weight' in result['dimensions'][dim]

    def test_priority_fixes_ordered_by_impact(self):
        from utils.quality_scorer import score_content
        result = score_content(self._bad_html(), keyword='portátiles gaming')
        fixes = result['priority_fixes']
        if len(fixes) >= 2:
            assert fixes[0]['impact'] >= fixes[1]['impact']

    def test_html_entities_decoded(self):
        from utils.quality_scorer import _strip_html
        text = _strip_html('<p>port&aacute;tiles 1.299&euro;</p>')
        assert 'portátiles' in text
        assert '€' in text

    def test_brand_detection_uppercase(self):
        from utils.quality_scorer import QualityScorer
        qs = QualityScorer()
        text = ('El ASUS ROG Strix G15 y el MSI Katana 15 son portátiles gaming. '
                'NVIDIA GeForce RTX 4060 con 16 GB de RAM por 1.199€. '
                'AMD Ryzen 7 ofrece un rendimiento un 30% superior en 2025.')
        result = qs._score_especificidad(text)
        # Should detect ASUS, MSI, NVIDIA, AMD as brands and find specs
        assert result['score'] >= 70

    def test_no_keyword_gives_neutral_seo(self):
        from utils.quality_scorer import score_content
        result = score_content('<p>Content</p>', keyword='')
        assert result['dimensions']['seo']['score'] == 50

    def test_flesch_spanish(self):
        from utils.quality_scorer import _flesch_fernandez_huerta
        easy = 'El gato come. El perro ladra. La casa es grande.'
        hard = 'La implementación arquitectónica requiere consideración pormenorizada.'
        assert _flesch_fernandez_huerta(easy) > _flesch_fernandez_huerta(hard)


# ============================================================================
# KEYWORD ANALYZER
# ============================================================================

class TestKeywordAnalyzer:
    """Tests para utils/keyword_analyzer.py"""

    def test_density_calculation(self):
        from utils.keyword_analyzer import analyze_keywords
        html = '<p>' + ' '.join(['palabra'] * 98 + ['portátiles gaming'] * 2) + '</p>'
        result = analyze_keywords(html, 'portátiles gaming')
        # 2 occurrences / 100 total words = 2%
        assert 1.0 <= result['primary_keyword']['density'] <= 3.0

    def test_zero_density(self):
        from utils.keyword_analyzer import analyze_keywords
        result = analyze_keywords('<p>texto sin keyword</p>', 'portátiles gaming')
        assert result['primary_keyword']['density'] == 0.0
        assert result['primary_keyword']['status'] == 'muy_baja'

    def test_stuffing_detection(self):
        from utils.keyword_analyzer import analyze_keywords
        html = '<p>' + ' portátiles gaming ' * 50 + '</p>'
        result = analyze_keywords(html, 'portátiles gaming')
        assert result['primary_keyword']['stuffing_risk'] == 'alto'

    def test_placements(self):
        from utils.keyword_analyzer import analyze_keywords
        html = '''<h2>Mejores portátiles gaming</h2>
        <p>Los portátiles gaming son geniales. Más texto aquí.</p>
        <h3>Subtítulo</h3>
        <p>Conclusión sobre portátiles gaming.</p>'''
        result = analyze_keywords(html, 'portátiles gaming')
        assert result['placements']['in_h2'] is True
        assert result['placements']['in_first_100_words'] is True

    def test_distribution(self):
        from utils.keyword_analyzer import analyze_keywords
        result = analyze_keywords('<p>portátiles gaming aquí</p>', 'portátiles gaming')
        assert 'inicio' in result['distribution']
        assert 'medio' in result['distribution']
        assert 'final' in result['distribution']

    def test_secondary_keywords(self):
        from utils.keyword_analyzer import analyze_keywords
        html = '<p>GPU dedicada y tarjeta gráfica para gaming.</p>'
        result = analyze_keywords(html, 'gaming', secondary_keywords=['GPU dedicada', 'tarjeta gráfica'])
        assert len(result['secondary_keywords']) == 2

    def test_html_entities_in_keywords(self):
        from utils.keyword_analyzer import _strip_html
        text = _strip_html('<p>port&aacute;tiles gaming</p>')
        assert 'portátiles' in text

    def test_seo_score(self):
        from utils.keyword_analyzer import KeywordAnalyzer
        analyzer = KeywordAnalyzer()
        analysis = analyzer.analyze(
            '<h2>portátiles gaming</h2><p>Los portátiles gaming son top.</p>',
            'portátiles gaming'
        )
        score = analyzer.get_seo_score(analysis)
        assert 0 <= score <= 100


# ============================================================================
# OPPORTUNITY SCORER
# ============================================================================

class TestOpportunityScorer:
    """Tests para utils/opportunity_scorer.py"""

    def test_quick_win_classification(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='test', position=15, impressions=500)
        assert result['type'] == 'quick_win'

    def test_improvement_classification(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='test', position=5, impressions=1000, ctr=0.06)
        assert result['type'] == 'improvement'

    def test_score_range(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='test', position=15, impressions=500)
        assert 0 <= result['score'] <= 100

    def test_factors_present(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='test', position=15, impressions=500)
        expected_factors = ['volume', 'position', 'intent', 'difficulty', 'ctr_gap', 'trend']
        for f in expected_factors:
            assert f in result['factors']

    def test_commercial_intent_high(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='comprar mejor portátil gaming', position=10, impressions=100)
        assert result['factors']['intent'] >= 80

    def test_informational_intent_low(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='qué es una GPU', position=10, impressions=100)
        assert result['factors']['intent'] <= 50

    def test_batch_sorted_by_score(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        results = scorer.score_batch([
            {'keyword': 'test1', 'position': 15, 'impressions': 100},
            {'keyword': 'test2', 'position': 12, 'impressions': 5000},
            {'keyword': 'test3', 'position': 18, 'impressions': 50},
        ])
        scores = [r['score'] for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_find_quick_wins(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        data = [
            {'query': 'kw1', 'position': 5, 'impressions': 100, 'clicks': 20, 'ctr': 0.2},
            {'query': 'kw2', 'position': 14, 'impressions': 500, 'clicks': 10, 'ctr': 0.02},
            {'query': 'kw3', 'position': 25, 'impressions': 1000, 'clicks': 5, 'ctr': 0.005},
        ]
        qw = scorer.find_quick_wins(data, min_impressions=50)
        assert len(qw) == 1
        assert qw[0]['keyword'] == 'kw2'

    def test_potential_clicks(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='test', position=15, impressions=1000)
        assert result['potential_clicks'] > 0

    def test_recommendation_present(self):
        from utils.opportunity_scorer import OpportunityScorer
        scorer = OpportunityScorer()
        result = scorer.score_keyword(keyword='test', position=15, impressions=100)
        assert len(result['recommendation']) > 10


# ============================================================================
# CMS PUBLISHER
# ============================================================================

class TestCMSPublisher:
    """Tests para core/cms_publisher.py"""

    def test_pccomponentes_rejects_missing_articles(self):
        from core.cms_publisher import PcComponentesCMSPublisher
        pub = PcComponentesCMSPublisher(cms_url='https://test.com', api_token='x')
        result = pub.publish_draft('<p>text</p>', {'keyword': 'test'})
        assert not result.success
        assert 'incompleto' in result.error

    def test_pccomponentes_rejects_h1(self):
        from core.cms_publisher import PcComponentesCMSPublisher
        pub = PcComponentesCMSPublisher(cms_url='https://test.com', api_token='x')
        html = (
            '<h1>Bad</h1>'
            '<article class="contentGenerator__main">a</article>'
            '<article class="contentGenerator__faqs">b</article>'
            '<article class="contentGenerator__verdict">c</article>'
        )
        result = pub.publish_draft(html, {'keyword': 'test'})
        assert not result.success
        assert 'h1' in result.error.lower()

    def test_factory_pccomponentes(self):
        from core.cms_publisher import get_publisher_for_config, PcComponentesCMSPublisher
        pub = get_publisher_for_config({'type': 'pccomponentes', 'url': 'x', 'api_token': 'y'})
        assert isinstance(pub, PcComponentesCMSPublisher)

    def test_factory_wordpress(self):
        from core.cms_publisher import get_publisher_for_config, CMSPublisher
        pub = get_publisher_for_config({
            'type': 'wordpress', 'url': 'x', 'username': 'u', 'app_password': 'p'
        })
        assert isinstance(pub, CMSPublisher)
        assert pub.cms_type == 'wordpress'

    def test_factory_custom(self):
        from core.cms_publisher import get_publisher_for_config, CMSPublisher
        pub = get_publisher_for_config({'type': 'custom', 'url': 'x'})
        assert isinstance(pub, CMSPublisher)
        assert pub.cms_type == 'custom'

    def test_slugify(self):
        from core.cms_publisher import CMSPublisher
        pub = CMSPublisher.__new__(CMSPublisher)
        assert pub._slugify('Portátiles Gaming 2025!') == 'portatiles-gaming-2025'

    def test_category_map(self):
        from core.cms_publisher import PcComponentesCMSPublisher
        assert 'ARQ-1' in PcComponentesCMSPublisher.CATEGORY_MAP
        assert PcComponentesCMSPublisher.CATEGORY_MAP['ARQ-1'] == 'Reviews'


# ============================================================================
# PROMPT OPTIMIZER
# ============================================================================

class TestPromptOptimizer:
    """Tests para utils/prompt_optimizer.py"""

    def test_minify_css(self):
        from utils.prompt_optimizer import optimize_prompt
        prompt = '<style>\n  .test {\n    color: red;\n    font-size: 16px;\n  }\n</style>'
        optimized = optimize_prompt(prompt)
        assert len(optimized) < len(prompt)
        assert '.test' in optimized

    def test_collapse_blank_lines(self):
        from utils.prompt_optimizer import optimize_prompt
        prompt = 'Line 1\n\n\n\n\nLine 2'
        optimized = optimize_prompt(prompt)
        assert '\n\n\n' not in optimized

    def test_token_estimation(self):
        from utils.prompt_optimizer import estimate_tokens_simple
        text = 'a' * 4000
        tokens = estimate_tokens_simple(text)
        assert 900 <= tokens <= 1100

    def test_check_prompt_size_ok(self):
        from utils.prompt_optimizer import check_prompt_size
        result = check_prompt_size('x' * 1000)
        assert result['warning'] is None

    def test_check_prompt_size_warning(self):
        from utils.prompt_optimizer import check_prompt_size
        # Create a very large prompt (>25% of context)
        result = check_prompt_size('x' * 400000)
        assert result['warning'] is not None


# ============================================================================
# VERSION
# ============================================================================

class TestVersion:
    """Tests para version.py"""

    def test_version_file_exists(self):
        from pathlib import Path
        assert Path('VERSION').exists() or Path(
            os.path.join(os.path.dirname(__file__), '..', 'VERSION')
        ).exists()

    def test_version_importable(self):
        from version import __version__
        assert __version__
        # Should be semver-ish
        parts = __version__.split('.')
        assert len(parts) >= 2


# ============================================================================
# INTEGRATION: Pipeline simulado (sin API calls)
# ============================================================================

class TestPipelineIntegration:
    """Tests de integración para el flujo completo."""

    def test_scrubber_then_scorer(self):
        """Verifica que scrubber + scorer trabajan en secuencia."""
        from utils.content_scrubber import scrub_html
        from utils.quality_scorer import score_content

        # HTML con watermarks
        html = '''<article class="contentGenerator__main">
        <h2>Portátiles\u200B gaming</h2>
        <p>Carlos\u200C compró un portátil por 1.200€ — además de un monitor.</p>
        </article>'''

        cleaned, stats = scrub_html(html)
        assert stats['unicode_removed'] >= 2

        result = score_content(cleaned, keyword='portátiles gaming')
        assert 'composite_score' in result
        assert isinstance(result['composite_score'], float)

    def test_scrubber_then_keyword_analyzer(self):
        """Verifica que scrubber + keyword analyzer trabajan en secuencia."""
        from utils.content_scrubber import scrub_html
        from utils.keyword_analyzer import analyze_keywords

        html = '<h2>Port\u200Bátiles gaming</h2><p>Los portátiles gaming son top.</p>'
        cleaned, _ = scrub_html(html)
        result = analyze_keywords(cleaned, 'portátiles gaming')
        assert result['primary_keyword']['count'] >= 1

    def test_opportunity_to_generation_config(self):
        """Verifica que un opportunity result genera config válida para pipeline."""
        from utils.opportunity_scorer import OpportunityScorer

        scorer = OpportunityScorer()
        opp = scorer.score_keyword(
            keyword='mejores portátiles gaming',
            position=14,
            impressions=3000,
            clicks=40,
            ctr=0.013,
            url='/blog/portatiles',
        )

        # Simular lo que haría ui/opportunities._launch_generation
        config = {
            'keyword': opp['keyword'],
            'target_length': 1500,
            'arquetipo_codigo': 'ARQ-1',
        }
        assert config['keyword'] == 'mejores portátiles gaming'
        assert config['target_length'] > 0

    def test_full_post_generation_flow(self):
        """Simula el flujo post-generación completo (sin API)."""
        from utils.content_scrubber import scrub_html
        from utils.quality_scorer import score_content
        from utils.keyword_analyzer import analyze_keywords

        # Simular output de Claude
        generated_html = '''<style>.test{}</style>
        <article class="contentGenerator__main">
        <h2>Mejores portátiles gaming 2025</h2>
        <p>Carlos buscaba un portátil gaming por 1.200\u200B€ y eligió el ASUS ROG.
        Con 32 GB de RAM y RTX 4060, Cyberpunk va a 85 fps — sin lugar a dudas genial.</p>
        <p>Echa un vistazo a <a href="https://www.pccomponentes.com/asus-rog">ASUS ROG</a>.</p>
        </article>
        <article class="contentGenerator__faqs">
        <h2>Preguntas frecuentes sobre portátiles gaming</h2>
        </article>
        <article class="contentGenerator__verdict">
        <div class="verdict-box"><h2>Veredicto</h2>
        <p>El ASUS ROG es la mejor opción en portátiles gaming 2025.</p></div>
        </article>'''

        # Step 1: Scrub
        cleaned, scrub_stats = scrub_html(generated_html)
        assert scrub_stats['unicode_removed'] >= 1

        # Step 2: Quality score
        quality = score_content(cleaned, keyword='portátiles gaming')
        assert quality['composite_score'] > 0

        # Step 3: Keyword analysis
        kw = analyze_keywords(cleaned, 'portátiles gaming')
        assert kw['primary_keyword']['count'] >= 2
        assert kw['placements']['in_h2'] is True

        # Step 4: CMS validation
        from core.cms_publisher import PcComponentesCMSPublisher
        pub = PcComponentesCMSPublisher(cms_url='https://test.com', api_token='x')
        cms_result = pub.publish_draft(cleaned, {'keyword': 'portátiles gaming'})
        # Should pass validation (3 articles present, no H1)
        # Will fail on API call, but that's expected
        assert cms_result.error is None or 'incompleto' not in cms_result.error


# ============================================================================
# Run with pytest or standalone
# ============================================================================

if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v', '--tb=short'])
