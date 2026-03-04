"""
Core Module - PcComponentes Content Generator
Versión 4.2.0

Módulo principal que contiene la lógica de negocio:
- Generación de contenido con Claude API
- Scraping de PDPs y competidores
- Integración con SEMrush API

Este __init__.py centraliza todos los exports del paquete core
para facilitar las importaciones en el resto de la aplicación.

Uso:
    from core import generate_content, scrape_pdp_data
    from core import SEMrushClient, is_semrush_available

Autor: PcComponentes - Product Discovery & Content
"""

import logging
from typing import TYPE_CHECKING

# Configurar logger para el módulo
logger = logging.getLogger(__name__)

# ============================================================================
# VERSIÓN DEL MÓDULO
# ============================================================================

__version__ = "4.2.0"


# ============================================================================
# IMPORTS DEL MÓDULO GENERATOR
# ============================================================================

try:
    from core.generator import (
        generate_content,
        generate_with_stages,
        call_claude_api,
        count_tokens,
        validate_response,
        extract_html_content,
        GenerationError,
        APIError,
        TokenLimitError,
    )
    _generator_available = True
except ImportError as e:
    logger.warning(f"No se pudo importar el módulo generator: {e}")
    _generator_available = False
    
    # Definir placeholders para evitar errores de importación
    def generate_content(*args, **kwargs):
        raise ImportError("Módulo generator no disponible")
    
    def generate_with_stages(*args, **kwargs):
        raise ImportError("Módulo generator no disponible")
    
    def call_claude_api(*args, **kwargs):
        raise ImportError("Módulo generator no disponible")
    
    def count_tokens(*args, **kwargs):
        raise ImportError("Módulo generator no disponible")
    
    def validate_response(*args, **kwargs):
        raise ImportError("Módulo generator no disponible")
    
    def extract_html_content(*args, **kwargs):
        raise ImportError("Módulo generator no disponible")
    
    class GenerationError(Exception):
        pass
    
    class APIError(Exception):
        pass
    
    class TokenLimitError(Exception):
        pass


# ============================================================================
# IMPORTS DEL MÓDULO SCRAPER
# ============================================================================

try:
    from core.scraper import (
        # Funciones principales de scraping
        scrape_pdp_data,
        scrape_url,
        scrape_competitor_urls,
        scrape_multiple_urls,
        
        # Funciones de extracción
        extract_product_info,
        extract_page_content,
        extract_meta_tags,
        
        # Funciones de limpieza
        clean_html_content,
        normalize_text,
        
        # Validación
        validate_url,
        is_valid_pdp_url,
        
        # Constantes
        REQUEST_TIMEOUT,
        MAX_RETRIES,
        USER_AGENT,
    )
    _scraper_available = True
except ImportError as e:
    logger.warning(f"No se pudo importar el módulo scraper: {e}")
    _scraper_available = False
    
    # Definir placeholders
    def scrape_pdp_data(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def scrape_url(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def scrape_competitor_urls(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def scrape_multiple_urls(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def extract_product_info(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def extract_page_content(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def extract_meta_tags(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def clean_html_content(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def normalize_text(*args, **kwargs):
        raise ImportError("Módulo scraper no disponible")
    
    def validate_url(*args, **kwargs):
        return False
    
    def is_valid_pdp_url(*args, **kwargs):
        return False
    
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    USER_AGENT = "Mozilla/5.0"


# ============================================================================
# IMPORTS DEL MÓDULO SEMRUSH (OPCIONAL)
# ============================================================================

try:
    from core.semrush import (
        # Cliente principal (Singleton)
        SEMrushClient,
        get_semrush_client,
        reset_semrush_client,
        
        # Funciones de keywords
        get_keyword_data,
        get_related_keywords,
        get_domain_keywords,
        
        # Verificación
        is_semrush_available,
        is_semrush_configured,
        
        # Configuración
        SEMrushConfig,
        RateLimitConfig,
        RetryConfig,
        CacheConfig,
        APIResponse,
        
        # Excepciones
        SEMrushError,
        SEMrushAPIError,
        SEMrushRateLimitError,
        SEMrushAuthError,
        SEMrushConfigError,
        SEMrushTimeoutError,
        
        # Constantes
        DEFAULT_DATABASE,
        SEMRUSH_DATABASES,
    )
    _semrush_available = True
    logger.debug("Módulo SEMrush cargado correctamente")
    
except ImportError as e:
    logger.info(f"Módulo SEMrush no disponible (opcional): {e}")
    _semrush_available = False
    
    # Definir placeholders para SEMrush (es opcional)
    class SEMrushClient:
        """Placeholder para SEMrushClient cuando el módulo no está disponible."""
        
        _instance = None
        
        def __new__(cls, *args, **kwargs):
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
        
        def __init__(self, *args, **kwargs):
            pass
        
        def is_configured(self) -> bool:
            return False
        
        def get_keyword_overview(self, *args, **kwargs):
            logger.warning("SEMrush no disponible")
            return None
        
        def get_related_keywords(self, *args, **kwargs):
            logger.warning("SEMrush no disponible")
            return None
        
        def get_domain_organic_keywords(self, *args, **kwargs):
            logger.warning("SEMrush no disponible")
            return None
    
    def get_semrush_client(*args, **kwargs):
        """Retorna instancia placeholder del cliente."""
        return SEMrushClient()
    
    def reset_semrush_client():
        """No hace nada ya que SEMrush no está disponible."""
        pass
    
    def get_keyword_data(*args, **kwargs):
        logger.warning("SEMrush no disponible: get_keyword_data")
        return None
    
    def get_related_keywords(*args, **kwargs):
        logger.warning("SEMrush no disponible: get_related_keywords")
        return []
    
    def get_domain_keywords(*args, **kwargs):
        logger.warning("SEMrush no disponible: get_domain_keywords")
        return []
    
    def is_semrush_available() -> bool:
        """Retorna False ya que SEMrush no está disponible."""
        return False
    
    def is_semrush_configured() -> bool:
        """Retorna False ya que SEMrush no está disponible."""
        return False
    
    # Configuraciones placeholder
    class SEMrushConfig:
        pass
    
    class RateLimitConfig:
        pass
    
    class RetryConfig:
        pass
    
    class CacheConfig:
        pass
    
    class APIResponse:
        success: bool = False
        data: None = None
        error: str = "SEMrush no disponible"
    
    # Excepciones
    class SEMrushError(Exception):
        """Excepción base para errores de SEMrush."""
        pass
    
    class SEMrushAPIError(SEMrushError):
        """Error de API de SEMrush."""
        pass
    
    class SEMrushRateLimitError(SEMrushError):
        """Error de rate limit de SEMrush."""
        pass
    
    class SEMrushAuthError(SEMrushError):
        """Error de autenticación de SEMrush."""
        pass
    
    class SEMrushConfigError(SEMrushError):
        """Error de configuración de SEMrush."""
        pass
    
    class SEMrushTimeoutError(SEMrushError):
        """Error de timeout de SEMrush."""
        pass
    
    # Constantes
    DEFAULT_DATABASE = 'es'
    SEMRUSH_DATABASES = {'es': 'es', 'us': 'us', 'uk': 'uk'}


# ============================================================================
# FUNCIONES DE DISPONIBILIDAD
# ============================================================================

def is_generator_available() -> bool:
    """
    Verifica si el módulo generator está disponible.
    
    Returns:
        bool: True si el módulo está disponible
    """
    return _generator_available


def is_scraper_available() -> bool:
    """
    Verifica si el módulo scraper está disponible.
    
    Returns:
        bool: True si el módulo está disponible
    """
    return _scraper_available


def check_semrush_available() -> bool:
    """
    Verifica si el módulo SEMrush está disponible y configurado.
    
    Returns:
        bool: True si SEMrush está disponible y tiene API key válida
    """
    if not _semrush_available:
        return False
    
    try:
        return is_semrush_available()
    except Exception:
        return False


def get_available_modules() -> dict:
    """
    Retorna un diccionario con el estado de disponibilidad de cada módulo.
    
    Returns:
        dict: Estado de cada módulo
        
    Example:
        >>> modules = get_available_modules()
        >>> print(modules)
        {'generator': True, 'scraper': True, 'semrush': False}
    """
    return {
        'generator': _generator_available,
        'scraper': _scraper_available,
        'semrush': _semrush_available,
    }


def get_module_status() -> str:
    """
    Retorna un string con el estado de los módulos para debugging.
    
    Returns:
        str: Estado formateado de los módulos
    """
    modules = get_available_modules()
    lines = ["Estado de módulos core:"]
    
    for name, available in modules.items():
        status = "✅ Disponible" if available else "❌ No disponible"
        lines.append(f"  - {name}: {status}")
    
    return "\n".join(lines)


# ============================================================================
# INICIALIZACIÓN Y VALIDACIÓN
# ============================================================================

def validate_core_modules() -> tuple:
    """
    Valida que los módulos críticos estén disponibles.
    
    Returns:
        tuple: (is_valid, error_messages)
        
    Example:
        >>> is_valid, errors = validate_core_modules()
        >>> if not is_valid:
        ...     print("Errores:", errors)
    """
    errors = []
    
    if not _generator_available:
        errors.append("Módulo generator no disponible - la generación no funcionará")
    
    if not _scraper_available:
        errors.append("Módulo scraper no disponible - el scraping no funcionará")
    
    # SEMrush es opcional, solo advertencia
    if not _semrush_available:
        logger.info("SEMrush no disponible - funcionalidad de keywords limitada")
    
    is_valid = len(errors) == 0
    return is_valid, errors


def init_core() -> bool:
    """
    Inicializa el módulo core y verifica dependencias.
    
    Returns:
        bool: True si la inicialización fue exitosa
        
    Example:
        >>> if init_core():
        ...     print("Core inicializado correctamente")
    """
    is_valid, errors = validate_core_modules()
    
    if not is_valid:
        for error in errors:
            logger.error(error)
        return False
    
    logger.info(f"Core inicializado - v{__version__}")
    logger.info(get_module_status())
    
    return True


# ============================================================================
# EXPORTS (__all__)
# ============================================================================

__all__ = [
    # Versión
    "__version__",
    
    # === GENERATOR ===
    # Funciones principales
    "generate_content",
    "generate_with_stages",
    "call_claude_api",
    
    # Utilidades
    "count_tokens",
    "validate_response",
    "extract_html_content",
    
    # Excepciones
    "GenerationError",
    "APIError",
    "TokenLimitError",
    
    # === SCRAPER ===
    # Funciones principales
    "scrape_pdp_data",
    "scrape_url",
    "scrape_competitor_urls",
    "scrape_multiple_urls",
    
    # Extracción
    "extract_product_info",
    "extract_page_content",
    "extract_meta_tags",
    
    # Limpieza
    "clean_html_content",
    "normalize_text",
    
    # Validación
    "validate_url",
    "is_valid_pdp_url",
    
    # Constantes
    "REQUEST_TIMEOUT",
    "MAX_RETRIES",
    "USER_AGENT",
    
    # === SEMRUSH ===
    # Cliente (Singleton)
    "SEMrushClient",
    "get_semrush_client",
    "reset_semrush_client",
    
    # Funciones de conveniencia
    "get_keyword_data",
    "get_related_keywords",
    "get_domain_keywords",
    
    # Verificación
    "is_semrush_available",
    "is_semrush_configured",
    
    # Configuración
    "SEMrushConfig",
    "RateLimitConfig",
    "RetryConfig",
    "CacheConfig",
    "APIResponse",
    
    # Excepciones
    "SEMrushError",
    "SEMrushAPIError",
    "SEMrushRateLimitError",
    "SEMrushAuthError",
    "SEMrushConfigError",
    "SEMrushTimeoutError",
    
    # Constantes
    "DEFAULT_DATABASE",
    "SEMRUSH_DATABASES",
    
    # === FUNCIONES DE DISPONIBILIDAD ===
    "is_generator_available",
    "is_scraper_available",
    "check_semrush_available",
    "get_available_modules",
    "get_module_status",
    
    # === INICIALIZACIÓN ===
    "validate_core_modules",
    "init_core",
]


# ============================================================================
# AUTO-INICIALIZACIÓN (OPCIONAL)
# ============================================================================

# Descomentar para auto-inicializar al importar el módulo
# init_core()
