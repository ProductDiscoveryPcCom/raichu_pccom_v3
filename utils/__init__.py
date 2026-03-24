"""
Utils package - PcComponentes Content Generator
Versión 4.3.0
"""

import logging

logger = logging.getLogger(__name__)

__version__ = "4.3.0"

# ============================================================================
# IMPORTS DE HTML_UTILS
# ============================================================================

try:
    from .html_utils import (
        # Parser
        HTMLParser,
        get_html_parser,
        get_parser,
        get_bs4_parser,
        is_bs4_available,
        # Data classes
        ExtractedContent,
        # Conteo
        count_words_in_html,
        get_word_count,
        strip_html_tags,
        strip_tags,
        # Extracción
        extract_content_structure,
        extract_content,
        extract_text,
        extract_meta_tags,
        # Limpieza
        sanitize_html,
        clean_html,
        # Validación
        validate_html_structure,
        validate_cms_structure,
        validate_word_count_target,
        # Enlaces
        analyze_links,
        get_heading_hierarchy,
    )
    _html_utils_available = True
except ImportError as e:
    logger.warning(f"No se pudo importar html_utils: {e}")
    _html_utils_available = False
    
    # Fallbacks
    from html.parser import HTMLParser
    def get_html_parser(): return HTMLParser()
    def get_parser(): return 'html.parser'
    def get_bs4_parser(): return 'html.parser'
    def is_bs4_available(): return False
    class ExtractedContent: pass
    def count_words_in_html(html): return 0
    def get_word_count(html): return 0
    def strip_html_tags(html): return html
    def strip_tags(html): return html
    def extract_content_structure(html): return {}
    def extract_content(html): return ExtractedContent()
    def extract_text(html): return ""
    def extract_meta_tags(html): return {}
    def sanitize_html(html): return html
    def clean_html(html): return html
    def validate_html_structure(html): return {}
    def validate_cms_structure(html): return True, [], []
    def validate_word_count_target(html, target, tol=0.05): return {}
    def analyze_links(html): return {}
    def get_heading_hierarchy(html): return []

# ============================================================================
# GSC UTILS (OPCIONAL)
# ============================================================================

GSC_AVAILABLE = False
try:
    from .gsc_utils import load_gsc_data, get_dataset_age, analyze_keyword_coverage
    GSC_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# CONTENT SCRUBBER (NUEVO v5.1)
# ============================================================================

SCRUBBER_AVAILABLE = False
try:
    from .content_scrubber import ContentScrubber, scrub_html
    SCRUBBER_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# QUALITY SCORER (NUEVO v5.1)
# ============================================================================

QUALITY_SCORER_AVAILABLE = False
try:
    from .quality_scorer import QualityScorer, score_content
    QUALITY_SCORER_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# KEYWORD ANALYZER (NUEVO v5.1)
# ============================================================================

KEYWORD_ANALYZER_AVAILABLE = False
try:
    from .keyword_analyzer import KeywordAnalyzer, analyze_keywords
    KEYWORD_ANALYZER_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# OPPORTUNITY SCORER (NUEVO v5.1)
# ============================================================================

OPPORTUNITY_SCORER_AVAILABLE = False
try:
    from .opportunity_scorer import OpportunityScorer
    OPPORTUNITY_SCORER_AVAILABLE = True
except ImportError:
    pass

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    # HTML utils - Parser
    'HTMLParser',
    'get_html_parser',
    'get_parser',
    'get_bs4_parser',
    'is_bs4_available',
    # HTML utils - Data classes
    'ExtractedContent',
    # HTML utils - Conteo
    'count_words_in_html',
    'get_word_count',
    'strip_html_tags',
    'strip_tags',
    # HTML utils - Extracción
    'extract_content_structure',
    'extract_content',
    'extract_text',
    'extract_meta_tags',
    # HTML utils - Limpieza
    'sanitize_html',
    'clean_html',
    # HTML utils - Validación
    'validate_html_structure',
    'validate_cms_structure',
    'validate_word_count_target',
    # HTML utils - Enlaces
    'analyze_links',
    'get_heading_hierarchy',
    # Flags
    'GSC_AVAILABLE',
    'SCRUBBER_AVAILABLE',
    'QUALITY_SCORER_AVAILABLE',
    'KEYWORD_ANALYZER_AVAILABLE',
    'OPPORTUNITY_SCORER_AVAILABLE',
]
