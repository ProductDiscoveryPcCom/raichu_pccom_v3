"""
Config package - PcComponentes Content Generator
Versión 4.5.0

Autor: PcComponentes - Product Discovery & Content
"""

import logging

logger = logging.getLogger(__name__)

__version__ = "4.5.0"

# ============================================================================
# IMPORTAR SETTINGS
# ============================================================================

try:
    from .settings import (
        # API
        CLAUDE_API_KEY,
        ANTHROPIC_API_KEY,
        CLAUDE_MODEL,
        MAX_TOKENS,
        TEMPERATURE,
        # App
        APP_NAME,
        APP_TITLE,
        APP_VERSION,
        PAGE_ICON,
        DEBUG_MODE,
        # GSC
        GSC_VERIFICATION_ENABLED,
        GSC_CREDENTIALS_FILE,
        GSC_PROPERTY_URL,
        GSC_CACHE_TTL,
        # SEMrush
        SEMRUSH_ENABLED,
        SEMRUSH_API_KEY,
        SEMRUSH_DATABASE,
        # Scraper
        MAX_RETRIES,
        RETRY_DELAY,
        REQUEST_TIMEOUT,
        USER_AGENT,
        # N8N
        N8N_WEBHOOK_URL,
        N8N_ENABLED,
        # Content
        DEFAULT_CONTENT_LENGTH,
        MIN_CONTENT_LENGTH,
        MAX_CONTENT_LENGTH,
        MAX_COMPETITORS,
        TARGET_WORD_COUNT_TOLERANCE,
        # Domains
        PCCOMPONENTES_DOMAINS,
        # Cache
        CACHE_ENABLED,
        CACHE_TTL,
        CACHE_MAX_SIZE,
        # Functions
        validate_config,
        get_api_key,
        is_configured,
    )
    _settings_available = True
except ImportError as e:
    logger.warning(f"No se pudo importar settings: {e}")
    _settings_available = False
    
    # Fallbacks mínimos
    import os
    CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY', '')
    ANTHROPIC_API_KEY = CLAUDE_API_KEY
    CLAUDE_MODEL = 'claude-sonnet-4-20250514'
    MAX_TOKENS = 16000
    TEMPERATURE = 0.7
    APP_NAME = "PcComponentes Content Generator"
    APP_TITLE = APP_NAME
    APP_VERSION = "4.5.0"
    PAGE_ICON = "🚀"
    DEBUG_MODE = False
    GSC_VERIFICATION_ENABLED = False
    GSC_CREDENTIALS_FILE = 'credentials.json'
    GSC_PROPERTY_URL = 'https://www.pccomponentes.com/'
    GSC_CACHE_TTL = 3600
    SEMRUSH_ENABLED = False
    SEMRUSH_API_KEY = ""
    SEMRUSH_DATABASE = "es"
    MAX_RETRIES = 3
    RETRY_DELAY = 1.0
    REQUEST_TIMEOUT = 30
    USER_AGENT = 'Mozilla/5.0'
    N8N_WEBHOOK_URL = ""
    N8N_ENABLED = False
    DEFAULT_CONTENT_LENGTH = 1500
    MIN_CONTENT_LENGTH = 500
    MAX_CONTENT_LENGTH = 5000
    MAX_COMPETITORS = 5
    TARGET_WORD_COUNT_TOLERANCE = 0.05
    PCCOMPONENTES_DOMAINS = ['www.pccomponentes.com', 'pccomponentes.com']
    CACHE_ENABLED = True
    CACHE_TTL = 3600
    CACHE_MAX_SIZE = 100
    
    def validate_config(): return (False, ["Settings no disponible"])
    def get_api_key(): return CLAUDE_API_KEY
    def is_configured(): return bool(CLAUDE_API_KEY)


# ============================================================================
# IMPORTAR ARQUETIPOS
# ============================================================================

try:
    from .arquetipos import (
        # Datos principales
        ARQUETIPOS,
        # Funciones de acceso
        get_arquetipo,
        get_arquetipo_names,
        get_arquetipo_by_name,
        get_guiding_questions,
        get_structure,
        get_default_length,
        get_length_range,
        get_visual_elements,
        get_campos_especificos,
        get_tone,
        get_keywords,
        # Funciones de utilidad
        get_all_arquetipo_codes,
        get_arquetipos_by_category,
        format_arquetipo_for_prompt,
        validate_arquetipo_code,
        get_arquetipo_summary,
        # Constantes
        DEFAULT_MIN_LENGTH,
        DEFAULT_MAX_LENGTH,
    )
    _arquetipos_available = True
    logger.info(f"Arquetipos cargados correctamente: {len(ARQUETIPOS)} arquetipos disponibles")
except ImportError as e:
    logger.warning(f"No se pudo importar arquetipos: {e}")
    _arquetipos_available = False
    
    # Fallbacks
    ARQUETIPOS = {}
    DEFAULT_MIN_LENGTH = 800
    DEFAULT_MAX_LENGTH = 2500
    
    def get_arquetipo(code): return None
    def get_arquetipo_names(): return {}
    def get_arquetipo_by_name(name): return None
    def get_guiding_questions(code): return []
    def get_structure(code): return []
    def get_default_length(code): return 1500
    def get_length_range(code): return (800, 2500)
    def get_visual_elements(code): return []
    def get_campos_especificos(code): return []
    def get_tone(code): return ""
    def get_keywords(code): return []
    def get_all_arquetipo_codes(): return []
    def get_arquetipos_by_category(keywords): return []
    def format_arquetipo_for_prompt(code): return ""
    def validate_arquetipo_code(code): return False
    def get_arquetipo_summary(code): return {}

# Alias en inglés por compatibilidad
ARCHETYPES = ARQUETIPOS


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Flags de disponibilidad
    '_settings_available',
    '_arquetipos_available',
    
    # Settings - API
    'CLAUDE_API_KEY',
    'ANTHROPIC_API_KEY',
    'CLAUDE_MODEL',
    'MAX_TOKENS',
    'TEMPERATURE',
    
    # Settings - App
    'APP_NAME',
    'APP_TITLE',
    'APP_VERSION',
    'PAGE_ICON',
    'DEBUG_MODE',
    
    # Settings - GSC
    'GSC_VERIFICATION_ENABLED',
    'GSC_CREDENTIALS_FILE',
    'GSC_PROPERTY_URL',
    'GSC_CACHE_TTL',
    
    # Settings - SEMrush
    'SEMRUSH_ENABLED',
    'SEMRUSH_API_KEY',
    'SEMRUSH_DATABASE',
    
    # Settings - Scraper
    'MAX_RETRIES',
    'RETRY_DELAY',
    'REQUEST_TIMEOUT',
    'USER_AGENT',
    
    # Settings - N8N
    'N8N_WEBHOOK_URL',
    'N8N_ENABLED',
    
    # Settings - Content
    'DEFAULT_CONTENT_LENGTH',
    'MIN_CONTENT_LENGTH',
    'MAX_CONTENT_LENGTH',
    'MAX_COMPETITORS',
    'TARGET_WORD_COUNT_TOLERANCE',
    
    # Settings - Domains
    'PCCOMPONENTES_DOMAINS',
    
    # Settings - Cache
    'CACHE_ENABLED',
    'CACHE_TTL',
    'CACHE_MAX_SIZE',
    
    # Settings - Functions
    'validate_config',
    'get_api_key',
    'is_configured',
    
    # Arquetipos - Datos
    'ARQUETIPOS',
    'ARCHETYPES',
    'DEFAULT_MIN_LENGTH',
    'DEFAULT_MAX_LENGTH',
    
    # Arquetipos - Funciones de acceso
    'get_arquetipo',
    'get_arquetipo_names',
    'get_arquetipo_by_name',
    'get_guiding_questions',
    'get_structure',
    'get_default_length',
    'get_length_range',
    'get_visual_elements',
    'get_campos_especificos',
    'get_tone',
    'get_keywords',
    
    # Arquetipos - Funciones de utilidad
    'get_all_arquetipo_codes',
    'get_arquetipos_by_category',
    'format_arquetipo_for_prompt',
    'validate_arquetipo_code',
    'get_arquetipo_summary',
]
