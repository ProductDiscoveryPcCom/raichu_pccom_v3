"""
Web Scraper - PcComponentes Content Generator
Versión 4.2.0

Módulo de scraping para extraer contenido de páginas web.
Incluye timeout configurable, reintentos con backoff exponencial,
y manejo robusto de errores HTTP.

Este módulo proporciona:
- Scraping de PDPs de PcComponentes
- Scraping de páginas de competidores
- Extracción de contenido HTML limpio
- Validación de URLs
- Sistema de reintentos configurable

Autor: PcComponentes - Product Discovery & Content
"""

import re
import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from enum import Enum

# Configurar logging
logger = logging.getLogger(__name__)

# ============================================================================
# IMPORTS CON MANEJO DE ERRORES
# ============================================================================

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    _requests_available = True
except ImportError as e:
    logger.error(f"No se pudo importar requests: {e}")
    _requests_available = False

try:
    from bs4 import BeautifulSoup
    _bs4_available = True
except ImportError as e:
    logger.warning(f"BeautifulSoup no disponible: {e}")
    _bs4_available = False

try:
    from config.settings import (
        REQUEST_TIMEOUT as SETTINGS_TIMEOUT,
        MAX_RETRIES as SETTINGS_MAX_RETRIES,
        USER_AGENT as SETTINGS_USER_AGENT,
        PCCOMPONENTES_DOMAINS as SETTINGS_DOMAINS,
    )
    _settings_available = True
except ImportError:
    _settings_available = False
    SETTINGS_TIMEOUT = 30
    SETTINGS_MAX_RETRIES = 3
    SETTINGS_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    SETTINGS_DOMAINS = ['www.pccomponentes.com', 'pccomponentes.com']


# ============================================================================
# VERSIÓN Y CONSTANTES
# ============================================================================

__version__ = "4.2.0"

# Configuración de timeout por defecto
DEFAULT_TIMEOUT = 30  # segundos
MIN_TIMEOUT = 5
MAX_TIMEOUT = 120

# Configuración de reintentos
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 30.0
BACKOFF_MULTIPLIER = 2.0

# ALIAS PARA COMPATIBILIDAD CON core/__init__.py
REQUEST_TIMEOUT: int = SETTINGS_TIMEOUT if _settings_available else DEFAULT_TIMEOUT
MAX_RETRIES: int = SETTINGS_MAX_RETRIES if _settings_available else DEFAULT_MAX_RETRIES
USER_AGENT: str = SETTINGS_USER_AGENT if _settings_available else 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
PCCOMPONENTES_DOMAINS: List[str] = SETTINGS_DOMAINS if _settings_available else ['www.pccomponentes.com', 'pccomponentes.com']

# Headers por defecto
DEFAULT_HEADERS = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
}

# Códigos HTTP que permiten reintento
RETRYABLE_STATUS_CODES = [408, 429, 500, 502, 503, 504]

# Tamaño máximo de respuesta (10 MB)
MAX_RESPONSE_SIZE = 10 * 1024 * 1024

# Selectores CSS para extracción de contenido
CONTENT_SELECTORS = [
    'article',
    'main',
    '.content',
    '.article-content',
    '.post-content',
    '#content',
    '.entry-content',
]

# Elementos a eliminar del contenido
REMOVE_SELECTORS = [
    'script',
    'style',
    'nav',
    'header',
    'footer',
    'aside',
    '.sidebar',
    '.navigation',
    '.menu',
    '.ads',
    '.advertisement',
    '.social-share',
    '.comments',
    '.related-posts',
]


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class ScraperError(Exception):
    """Excepción base para errores de scraping."""
    
    def __init__(self, message: str, url: str = "", details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.url = url
        self.details = details or {}
    
    def __str__(self):
        if self.url:
            return f"{self.message} (URL: {self.url})"
        return self.message


class TimeoutError(ScraperError):
    """Error de timeout en la petición."""
    pass


class ConnectionError(ScraperError):
    """Error de conexión."""
    pass


class HTTPError(ScraperError):
    """Error HTTP (4xx, 5xx)."""
    
    def __init__(
        self,
        message: str,
        url: str = "",
        status_code: int = 0,
        details: Optional[Dict] = None
    ):
        super().__init__(message, url, details)
        self.status_code = status_code


class ContentExtractionError(ScraperError):
    """Error al extraer contenido de la página."""
    pass


class URLValidationError(ScraperError):
    """Error de validación de URL."""
    pass


class RetryExhaustedError(ScraperError):
    """Error cuando se agotan los reintentos."""
    pass


# ============================================================================
# ENUMS Y DATA CLASSES
# ============================================================================

class ContentType(Enum):
    """Tipos de contenido a extraer."""
    HTML = "html"
    TEXT = "text"
    JSON = "json"


@dataclass
class TimeoutConfig:
    """Configuración de timeout."""
    connect: float = 10.0  # Timeout de conexión
    read: float = 30.0     # Timeout de lectura
    
    def as_tuple(self) -> Tuple[float, float]:
        """Retorna como tupla para requests."""
        return (self.connect, self.read)
    
    @classmethod
    def from_seconds(cls, seconds: float) -> 'TimeoutConfig':
        """Crea config desde un valor único."""
        return cls(connect=min(seconds / 3, 10), read=seconds)


@dataclass
class RetryConfig:
    """Configuración de reintentos."""
    max_retries: int = DEFAULT_MAX_RETRIES
    retry_delay: float = DEFAULT_RETRY_DELAY
    backoff_multiplier: float = BACKOFF_MULTIPLIER
    max_delay: float = MAX_RETRY_DELAY
    retry_on_status: List[int] = field(default_factory=lambda: RETRYABLE_STATUS_CODES.copy())


@dataclass
class ScraperConfig:
    """Configuración completa del scraper."""
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    headers: Dict[str, str] = field(default_factory=lambda: DEFAULT_HEADERS.copy())
    verify_ssl: bool = True
    follow_redirects: bool = True
    max_redirects: int = 5
    max_response_size: int = MAX_RESPONSE_SIZE


@dataclass
class ScrapeResult:
    """Resultado de una operación de scraping."""
    success: bool
    url: str
    content: str = ""
    title: str = ""
    meta_description: str = ""
    word_count: int = 0
    status_code: int = 0
    response_time: float = 0.0
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# CLASE PRINCIPAL: WebScraper
# ============================================================================

class WebScraper:
    """
    Scraper web con timeout configurable y reintentos.
    
    Características:
    - Timeout configurable (conexión y lectura separados)
    - Reintentos con backoff exponencial
    - Headers personalizables
    - Manejo robusto de errores HTTP
    - Extracción de contenido limpio
    - Validación de URLs
    
    Example:
        >>> scraper = WebScraper(timeout=30, max_retries=3)
        >>> result = scraper.scrape_url("https://example.com")
        >>> if result.success:
        ...     print(result.content)
    """
    
    def __init__(
        self,
        timeout: Union[int, float, TimeoutConfig] = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        headers: Optional[Dict[str, str]] = None,
        config: Optional[ScraperConfig] = None
    ):
        """
        Inicializa el scraper.
        
        Args:
            timeout: Timeout en segundos o TimeoutConfig
            max_retries: Número máximo de reintentos
            headers: Headers HTTP personalizados
            config: Configuración completa (sobrescribe otros parámetros)
        """
        if not _requests_available:
            raise ImportError("El módulo 'requests' es requerido. Instálalo con: pip install requests")
        
        # Usar config si se proporciona, sino construir desde parámetros
        if config:
            self._config = config
        else:
            # Construir TimeoutConfig
            if isinstance(timeout, TimeoutConfig):
                timeout_config = timeout
            else:
                timeout = max(MIN_TIMEOUT, min(float(timeout), MAX_TIMEOUT))
                timeout_config = TimeoutConfig.from_seconds(timeout)
            
            self._config = ScraperConfig(
                timeout=timeout_config,
                retry=RetryConfig(max_retries=max_retries),
                headers={**DEFAULT_HEADERS, **(headers or {})}
            )
        
        # Crear sesión con retry automático
        self._session = self._create_session()
        
        logger.info(
            f"WebScraper inicializado: timeout={self._config.timeout.read}s, "
            f"max_retries={self._config.retry.max_retries}"
        )
    
    def _create_session(self) -> 'requests.Session':
        """Crea una sesión de requests con retry configurado."""
        session = requests.Session()
        
        # Nota: NO configurar retry en el adapter — _make_request() maneja
        # reintentos manualmente con backoff exponencial y logging.
        # Tener ambos causaría retries duplicados (max_retries² intentos).
        retry_strategy = Retry(
            total=0,
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Configurar headers por defecto
        session.headers.update(self._config.headers)
        
        return session
    
    def scrape_url(
        self,
        url: str,
        extract_content: bool = True,
        timeout: Optional[float] = None
    ) -> ScrapeResult:
        """
        Extrae contenido de una URL.
        
        Args:
            url: URL a scrapear
            extract_content: Si True, extrae solo el contenido principal
            timeout: Timeout específico para esta petición (opcional)
            
        Returns:
            ScrapeResult con el contenido extraído
        """
        start_time = time.time()
        
        # Validar URL
        try:
            validated_url = self._validate_url(url)
        except URLValidationError as e:
            return ScrapeResult(
                success=False,
                url=url,
                error=str(e),
                response_time=time.time() - start_time
            )
        
        # Configurar timeout
        if timeout is not None:
            timeout = max(MIN_TIMEOUT, min(float(timeout), MAX_TIMEOUT))
            request_timeout = TimeoutConfig.from_seconds(timeout).as_tuple()
        else:
            request_timeout = self._config.timeout.as_tuple()
        
        # Realizar petición con manejo de errores específico
        try:
            response = self._make_request(validated_url, request_timeout)
            
            # Verificar tamaño de respuesta
            content_length = int(response.headers.get('content-length', 0))
            if content_length > self._config.max_response_size:
                return ScrapeResult(
                    success=False,
                    url=validated_url,
                    status_code=response.status_code,
                    error=f"Respuesta demasiado grande: {content_length} bytes",
                    response_time=time.time() - start_time
                )
            
            # Verificar código de estado
            if not response.ok:
                return ScrapeResult(
                    success=False,
                    url=validated_url,
                    status_code=response.status_code,
                    error=f"HTTP {response.status_code}: {response.reason}",
                    response_time=time.time() - start_time
                )
            
            # Extraer contenido
            html_content = response.text
            
            if extract_content and _bs4_available:
                extracted = self._extract_content(html_content)
                content = extracted['content']
                title = extracted['title']
                meta_description = extracted['meta_description']
            else:
                content = html_content
                title = ""
                meta_description = ""
            
            # Contar palabras
            word_count = len(content.split()) if content else 0
            
            return ScrapeResult(
                success=True,
                url=validated_url,
                content=content,
                title=title,
                meta_description=meta_description,
                word_count=word_count,
                status_code=response.status_code,
                response_time=time.time() - start_time,
                metadata={
                    'content_type': response.headers.get('content-type', ''),
                    'encoding': response.encoding,
                }
            )
        
        except requests.exceptions.Timeout as e:
            logger.warning(f"Timeout al acceder a {validated_url}: {e}")
            return ScrapeResult(
                success=False,
                url=validated_url,
                error=f"Timeout después de {request_timeout[1]}s",
                response_time=time.time() - start_time
            )
        
        except requests.exceptions.ConnectionError as e:
            logger.warning(f"Error de conexión a {validated_url}: {e}")
            return ScrapeResult(
                success=False,
                url=validated_url,
                error=f"Error de conexión: {self._simplify_error(e)}",
                response_time=time.time() - start_time
            )
        
        except requests.exceptions.TooManyRedirects as e:
            logger.warning(f"Demasiados redirects en {validated_url}: {e}")
            return ScrapeResult(
                success=False,
                url=validated_url,
                error="Demasiados redirects",
                response_time=time.time() - start_time
            )
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de request a {validated_url}: {e}")
            return ScrapeResult(
                success=False,
                url=validated_url,
                error=f"Error de petición: {self._simplify_error(e)}",
                response_time=time.time() - start_time
            )
        
        except Exception as e:
            logger.error(f"Error inesperado scrapeando {validated_url}: {e}")
            return ScrapeResult(
                success=False,
                url=validated_url,
                error=f"Error inesperado: {type(e).__name__}",
                response_time=time.time() - start_time
            )
    
    def _make_request(
        self,
        url: str,
        timeout: Tuple[float, float]
    ) -> 'requests.Response':
        """
        Realiza la petición HTTP con reintentos manuales adicionales.
        
        Args:
            url: URL a solicitar
            timeout: Tupla (connect_timeout, read_timeout)
            
        Returns:
            Response de requests
        """
        last_error = None
        current_delay = self._config.retry.retry_delay
        
        for attempt in range(1, self._config.retry.max_retries + 1):
            try:
                logger.debug(f"Intento {attempt}/{self._config.retry.max_retries}: {url}")
                
                response = self._session.get(
                    url,
                    timeout=timeout,
                    verify=self._config.verify_ssl,
                    allow_redirects=self._config.follow_redirects,
                )
                
                # Si es un error recuperable y no es el último intento
                if response.status_code in self._config.retry.retry_on_status:
                    if attempt < self._config.retry.max_retries:
                        logger.warning(
                            f"HTTP {response.status_code}, reintentando en {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay = min(
                            current_delay * self._config.retry.backoff_multiplier,
                            self._config.retry.max_delay
                        )
                        continue
                
                return response
            
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                last_error = e
                
                if attempt < self._config.retry.max_retries:
                    logger.warning(
                        f"Error en intento {attempt}, reintentando en {current_delay}s: {e}"
                    )
                    time.sleep(current_delay)
                    current_delay = min(
                        current_delay * self._config.retry.backoff_multiplier,
                        self._config.retry.max_delay
                    )
                else:
                    raise
        
        # Si llegamos aquí, se agotaron los reintentos
        if last_error:
            raise last_error
        
        raise RetryExhaustedError(f"Reintentos agotados para {url}", url)
    
    def _validate_url(self, url: str) -> str:
        """
        Valida y normaliza una URL.
        
        Args:
            url: URL a validar
            
        Returns:
            URL normalizada
            
        Raises:
            URLValidationError: Si la URL no es válida
        """
        if not url:
            raise URLValidationError("URL vacía", url)
        
        url = url.strip()
        
        # Añadir protocolo si falta
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        # Parsear y validar
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise URLValidationError(f"URL mal formada: {e}", url)
        
        if not parsed.scheme or not parsed.netloc:
            raise URLValidationError("URL incompleta: falta esquema o dominio", url)
        
        if parsed.scheme not in ('http', 'https'):
            raise URLValidationError(f"Esquema no soportado: {parsed.scheme}", url)
        
        return url
    
    def _extract_content(self, html: str) -> Dict[str, str]:
        """
        Extrae contenido principal de HTML.
        
        Args:
            html: HTML completo de la página
            
        Returns:
            Dict con 'content', 'title', 'meta_description'
        """
        if not _bs4_available:
            return {'content': html, 'title': '', 'meta_description': ''}
        
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extraer título
            title = ""
            title_tag = soup.find('title')
            if title_tag:
                title = title_tag.get_text(strip=True)
            
            # Extraer meta description
            meta_description = ""
            meta_tag = soup.find('meta', attrs={'name': 'description'})
            if meta_tag:
                meta_description = meta_tag.get('content', '')
            
            # Eliminar elementos no deseados
            for selector in REMOVE_SELECTORS:
                for element in soup.select(selector):
                    element.decompose()
            
            # Buscar contenido principal
            content_element = None
            for selector in CONTENT_SELECTORS:
                content_element = soup.select_one(selector)
                if content_element:
                    break
            
            # Si no se encuentra, usar body
            if not content_element:
                content_element = soup.body or soup
            
            # Extraer texto limpio
            content = content_element.get_text(separator=' ', strip=True)
            
            # Limpiar espacios múltiples
            content = re.sub(r'\s+', ' ', content).strip()
            
            return {
                'content': content,
                'title': title,
                'meta_description': meta_description
            }
        
        except Exception as e:
            logger.warning(f"Error extrayendo contenido: {e}")
            return {'content': html, 'title': '', 'meta_description': ''}
    
    def _simplify_error(self, error: Exception) -> str:
        """Simplifica mensaje de error para el usuario."""
        error_str = str(error)
        
        # Truncar errores muy largos
        if len(error_str) > 200:
            error_str = error_str[:200] + "..."
        
        return error_str
    
    def set_timeout(self, timeout: Union[int, float]) -> None:
        """
        Actualiza el timeout del scraper.
        
        Args:
            timeout: Nuevo timeout en segundos
        """
        timeout = max(MIN_TIMEOUT, min(float(timeout), MAX_TIMEOUT))
        self._config.timeout = TimeoutConfig.from_seconds(timeout)
        logger.info(f"Timeout actualizado a {timeout}s")
    
    def set_headers(self, headers: Dict[str, str]) -> None:
        """
        Actualiza headers del scraper.
        
        Args:
            headers: Nuevos headers (se mezclan con existentes)
        """
        self._config.headers.update(headers)
        self._session.headers.update(headers)
    
    def close(self) -> None:
        """Cierra la sesión de requests."""
        if self._session:
            self._session.close()
            logger.debug("Sesión de scraper cerrada")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False


# ============================================================================
# INSTANCIA GLOBAL DEL SCRAPER
# ============================================================================

_default_scraper: Optional[WebScraper] = None


def get_scraper(
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None
) -> WebScraper:
    """
    Obtiene el scraper global (singleton).
    
    Args:
        timeout: Timeout personalizado (opcional)
        max_retries: Reintentos personalizados (opcional)
        
    Returns:
        Instancia de WebScraper
    """
    global _default_scraper
    
    if _default_scraper is None:
        _default_scraper = WebScraper(
            timeout=timeout or DEFAULT_TIMEOUT,
            max_retries=max_retries or DEFAULT_MAX_RETRIES
        )
    
    return _default_scraper


def reset_scraper() -> None:
    """Resetea el scraper global."""
    global _default_scraper
    
    if _default_scraper:
        _default_scraper.close()
        _default_scraper = None


# ============================================================================
# FUNCIONES DE ALTO NIVEL
# ============================================================================

def scrape_url(
    url: str,
    timeout: Optional[float] = None,
    extract_content: bool = True
) -> ScrapeResult:
    """
    Scrapea una URL usando el scraper global.
    
    Args:
        url: URL a scrapear
        timeout: Timeout específico (opcional)
        extract_content: Si extraer solo contenido principal
        
    Returns:
        ScrapeResult con el contenido
    """
    scraper = get_scraper()
    return scraper.scrape_url(url, extract_content=extract_content, timeout=timeout)


def scrape_pdp_data(
    url: str,
    timeout: Optional[float] = None
) -> Optional[Dict[str, Any]]:
    """
    Extrae datos de un PDP de PcComponentes.
    
    Args:
        url: URL del PDP
        timeout: Timeout específico (opcional)
        
    Returns:
        Dict con datos del producto o None si hay error
    """
    # Validar que sea URL de PcComponentes
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        
        if not any(pcc in domain for pcc in PCCOMPONENTES_DOMAINS):
            logger.warning(f"URL no es de PcComponentes: {url}")
            return None
    except Exception:
        return None
    
    result = scrape_url(url, timeout=timeout, extract_content=True)
    
    if not result.success:
        logger.warning(f"Error scrapeando PDP: {result.error}")
        return None
    
    return {
        'url': result.url,
        'title': result.title,
        'meta_description': result.meta_description,
        'content': result.content,
        'word_count': result.word_count,
        'scraped_at': time.strftime('%Y-%m-%d %H:%M:%S'),
        'response_time': result.response_time,
    }


def scrape_competitor_urls(
    urls: List[str],
    timeout: Optional[float] = None,
    max_concurrent: int = 1
) -> List[Dict[str, Any]]:
    """
    Scrapea múltiples URLs de competidores.
    
    Args:
        urls: Lista de URLs a scrapear
        timeout: Timeout por URL (opcional)
        max_concurrent: Número máximo de requests concurrentes (futuro)
        
    Returns:
        Lista de dicts con datos de cada competidor
    """
    results = []
    scraper = get_scraper()
    
    for url in urls:
        logger.info(f"Scrapeando competidor: {url}")
        
        result = scraper.scrape_url(url, extract_content=True, timeout=timeout)
        
        competitor_data = {
            'url': url,
            'success': result.success,
            'title': result.title if result.success else '',
            'content': result.content if result.success else '',
            'word_count': result.word_count,
            'error': result.error,
            'response_time': result.response_time,
        }
        
        results.append(competitor_data)
        
        # Pequeña pausa entre requests para no sobrecargar
        if len(urls) > 1:
            time.sleep(0.5)
    
    successful = sum(1 for r in results if r['success'])
    logger.info(f"Scraping completado: {successful}/{len(urls)} URLs exitosas")
    
    return results


def scrape_multiple_urls(
    urls: List[str],
    timeout: Optional[float] = None
) -> List[ScrapeResult]:
    """
    Scrapea múltiples URLs y retorna resultados.
    
    Args:
        urls: Lista de URLs
        timeout: Timeout por URL (opcional)
        
    Returns:
        Lista de ScrapeResult
    """
    scraper = get_scraper()
    results = []
    
    for url in urls:
        result = scraper.scrape_url(url, timeout=timeout)
        results.append(result)
        
        # Pausa entre requests
        if len(urls) > 1:
            time.sleep(0.3)
    
    return results


# ============================================================================
# FUNCIONES DE EXTRACCIÓN
# ============================================================================

def extract_product_info(html: str) -> Dict[str, Any]:
    """
    Extrae información de producto de HTML de PDP.
    
    Args:
        html: HTML de la página de producto
        
    Returns:
        Dict con información del producto
    """
    if not _bs4_available:
        return {'error': 'BeautifulSoup no disponible'}
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Buscar título del producto
        title = ""
        for selector in ['h1', '.product-title', '.product-name', '[data-product-name]']:
            element = soup.select_one(selector)
            if element:
                title = element.get_text(strip=True)
                break
        
        # Buscar precio
        price = ""
        for selector in ['.price', '.product-price', '[data-price]', '.current-price']:
            element = soup.select_one(selector)
            if element:
                price = element.get_text(strip=True)
                break
        
        # Buscar descripción
        description = ""
        for selector in ['.description', '.product-description', '[data-description]']:
            element = soup.select_one(selector)
            if element:
                description = element.get_text(strip=True)[:500]
                break
        
        return {
            'title': title,
            'price': price,
            'description': description,
        }
    
    except Exception as e:
        logger.warning(f"Error extrayendo info de producto: {e}")
        return {'error': str(e)}


def extract_page_content(html: str) -> str:
    """
    Extrae contenido textual limpio de HTML.
    
    Args:
        html: HTML de la página
        
    Returns:
        Texto limpio
    """
    if not _bs4_available:
        # Fallback: eliminar tags con regex
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        # Eliminar scripts y estilos
        for tag in soup(['script', 'style', 'nav', 'header', 'footer']):
            tag.decompose()
        
        # Obtener texto
        text = soup.get_text(separator=' ', strip=True)
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()
    
    except Exception as e:
        logger.warning(f"Error extrayendo contenido: {e}")
        return ""


def extract_meta_tags(html: str) -> Dict[str, str]:
    """
    Extrae meta tags de HTML.
    
    Args:
        html: HTML de la página
        
    Returns:
        Dict con meta tags
    """
    if not _bs4_available:
        return {}
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        
        meta_tags = {}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            meta_tags['title'] = title_tag.get_text(strip=True)
        
        # Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            meta_tags['description'] = meta_desc.get('content', '')
        
        # Meta keywords
        meta_kw = soup.find('meta', attrs={'name': 'keywords'})
        if meta_kw:
            meta_tags['keywords'] = meta_kw.get('content', '')
        
        # Canonical
        canonical = soup.find('link', attrs={'rel': 'canonical'})
        if canonical:
            meta_tags['canonical'] = canonical.get('href', '')
        
        # Robots
        robots = soup.find('meta', attrs={'name': 'robots'})
        if robots:
            meta_tags['robots'] = robots.get('content', '')
        
        return meta_tags
    
    except Exception as e:
        logger.warning(f"Error extrayendo meta tags: {e}")
        return {}


def clean_html_content(html: str, max_length: Optional[int] = None) -> str:
    """
    Limpia contenido HTML para análisis.
    
    Args:
        html: HTML a limpiar
        max_length: Longitud máxima del resultado (opcional)
        
    Returns:
        Texto limpio
    """
    text = extract_page_content(html)
    
    if max_length and len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text


def normalize_text(text: str) -> str:
    """
    Normaliza texto (espacios, caracteres especiales).
    
    Args:
        text: Texto a normalizar
        
    Returns:
        Texto normalizado
    """
    if not text:
        return ""
    
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    
    # Eliminar caracteres de control
    text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
    
    return text.strip()


# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validate_url(url: str) -> bool:
    """
    Valida que una URL sea válida.
    
    Args:
        url: URL a validar
        
    Returns:
        True si es válida
    """
    if not url:
        return False
    
    try:
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)
    except Exception:
        return False


def is_valid_pdp_url(url: str) -> bool:
    """
    Valida que una URL sea un PDP de PcComponentes.
    
    Args:
        url: URL a validar
        
    Returns:
        True si es un PDP válido
    """
    if not validate_url(url):
        return False
    
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        return any(pcc in domain for pcc in PCCOMPONENTES_DOMAINS)
    except Exception:
        return False


def validate_urls_for_scraping(urls: List[str]) -> List[str]:
    """
    Filtra y valida URLs para scraping.
    
    Args:
        urls: Lista de URLs a validar
        
    Returns:
        Lista de URLs válidas
    """
    valid_urls = []
    for url in urls:
        if validate_url(url):
            valid_urls.append(url)
        else:
            logger.warning(f"URL inválida descartada: {url}")
    return valid_urls


# ============================================================================
# UTILIDADES
# ============================================================================

def is_scraper_available() -> bool:
    """Verifica si el scraper está disponible."""
    return _requests_available


def get_scraper_info() -> Dict[str, Any]:
    """Obtiene información del scraper."""
    return {
        'available': _requests_available,
        'bs4_available': _bs4_available,
        'default_timeout': DEFAULT_TIMEOUT,
        'default_max_retries': DEFAULT_MAX_RETRIES,
        'version': __version__,
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Excepciones
    'ScraperError',
    'TimeoutError',
    'ConnectionError',
    'HTTPError',
    'ContentExtractionError',
    'URLValidationError',
    'RetryExhaustedError',
    
    # Clases
    'ContentType',
    'TimeoutConfig',
    'RetryConfig',
    'ScraperConfig',
    'ScrapeResult',
    'WebScraper',
    
    # Scraper global
    'get_scraper',
    'reset_scraper',
    
    # Funciones de scraping
    'scrape_url',
    'scrape_pdp_data',
    'scrape_competitor_urls',
    'scrape_multiple_urls',
    
    # Funciones de extracción
    'extract_product_info',
    'extract_page_content',
    'extract_meta_tags',
    'clean_html_content',
    'normalize_text',
    
    # Validación
    'validate_url',
    'is_valid_pdp_url',
    'validate_urls_for_scraping',
    
    # Utilidades
    'is_scraper_available',
    'get_scraper_info',
    
    # Constantes - IMPORTANTES PARA COMPATIBILIDAD
    'DEFAULT_TIMEOUT',
    'DEFAULT_MAX_RETRIES',
    'MIN_TIMEOUT',
    'MAX_TIMEOUT',
    'REQUEST_TIMEOUT',
    'MAX_RETRIES',
    'USER_AGENT',
    'PCCOMPONENTES_DOMAINS',
]
