# -*- coding: utf-8 -*-
"""
SERP Research - PcComponentes Content Generator
Versión 2.0.0 - 2026-02-12

Investigación de SERPs para enriquecer la generación de contenido.
Busca en DuckDuckGo (HTML), scrapea competidores y genera análisis.

Usado por:
- ui/assistant.py (comando [SERP_RESEARCH: keyword])
- app.py (Etapa 0 del pipeline de generación)

Autor: PcComponentes - Product Discovery & Content
"""

import ipaddress
import json
import logging
import os
import re
import time
import urllib.parse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

__version__ = "2.0.0"

# ============================================================================
# CONFIGURACIÓN DE FUENTES SERP (prioridad: SerpAPI > SEMrush > DuckDuckGo)
# ============================================================================

def _get_serpapi_key() -> str:
    """Obtiene API key de SerpAPI desde secrets o env.
    
    Orden de búsqueda:
    1. Variable de entorno SERPAPI_API_KEY
    2. st.secrets['serpapi_key'] (acceso directo)
    3. st.secrets.get('serpapi_key') (método get)
    """
    # 1. Variable de entorno (puesta por app.py o externamente)
    key = os.environ.get('SERPAPI_API_KEY', '')
    if key:
        return key
    
    # 2. Streamlit secrets (intentar múltiples métodos)
    try:
        import streamlit as st
        if hasattr(st, 'secrets'):
            # Método directo (más fiable en Streamlit Cloud)
            try:
                key = st.secrets["serpapi_key"]
                if key:
                    # Cachear en os.environ para llamadas futuras
                    os.environ['SERPAPI_API_KEY'] = str(key)
                    return str(key)
            except (KeyError, FileNotFoundError):
                pass
            # Método get (fallback)
            try:
                key = st.secrets.get('serpapi_key', '')
                if key:
                    os.environ['SERPAPI_API_KEY'] = str(key)
                    return str(key)
            except Exception as e:
                logger.debug(f"SerpAPI secrets.get fallback failed: {e}")
    except ImportError:
        pass
    
    return ''


def _get_semrush_available() -> bool:
    """Verifica si SEMrush está disponible."""
    return os.environ.get('SEMRUSH_ENABLED', '').lower() == 'true'


# Dominios a excluir del scraping de competidores
SKIP_DOMAINS = [
    'pccomponentes.com', 'youtube.com', 'twitter.com', 'facebook.com',
    'instagram.com', 'reddit.com', 'tiktok.com', 'amazon.',
    'google.', 'wikipedia.org', 'msn.com', 'duckduckgo.com',
]

# Dominios conocidos para clasificar intención
RETAILER_DOMAINS = ['amazon', 'mediamarkt', 'fnac', 'carrefour', 'elcorteingles', 'coolmod', 'alternate']
REVIEW_DOMAINS = ['xataka', 'computerhoy', 'hardzone', 'profesionalreview', 'geeknetic', 'techradar', 'tomsguide']

# Configuración por defecto
DEFAULT_MAX_RESULTS = 10
DEFAULT_MAX_SCRAPE = 4
DEFAULT_TIMEOUT = 15
DEFAULT_SCRAPE_DELAY = 0.5


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class SerpResult:
    """Un resultado individual de búsqueda."""
    position: int
    title: str
    url: str
    domain: str
    snippet: str = ""


@dataclass
class CompetitorAnalysis:
    """Análisis de un competidor scrapeado."""
    url: str
    domain: str
    title: str
    word_count: int = 0
    h2_count: int = 0
    h3_count: int = 0
    has_table: bool = False
    has_faq: bool = False
    image_count: int = 0
    list_count: int = 0
    heading_structure: List[str] = field(default_factory=list)  # ["H2: Titulo", "H3: Sub"]
    content_summary: str = ""  # Resumen breve del contenido
    section_summaries: List[str] = field(default_factory=list)  # ["H3: Producto X\n  89€, 53mm drivers..."]
    products_mentioned: List[str] = field(default_factory=list)  # ["HyperX Cloud III", "Arctis Nova 7"]
    prices_found: List[str] = field(default_factory=list)  # ["89,99€", "179,99€"]
    success: bool = True
    error: str = ""


@dataclass
class SerpResearchResult:
    """Resultado completo de una investigación SERP."""
    keyword: str
    serp_results: List[SerpResult] = field(default_factory=list)
    competitors: List[CompetitorAnalysis] = field(default_factory=list)
    related_searches: List[str] = field(default_factory=list)  # Búsquedas relacionadas de Google
    insights: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: str = ""

    @property
    def avg_word_count(self) -> int:
        successful = [c for c in self.competitors if c.success and c.word_count > 0]
        if not successful:
            return 0
        return sum(c.word_count for c in successful) // len(successful)

    @property
    def avg_h2_count(self) -> int:
        successful = [c for c in self.competitors if c.success and c.h2_count > 0]
        if not successful:
            return 0
        return sum(c.h2_count for c in successful) // len(successful)

    @property
    def has_pccom(self) -> bool:
        return any('pccomponentes' in r.domain for r in self.serp_results[:5])

    @property
    def has_retailers(self) -> bool:
        domains = [r.domain for r in self.serp_results[:5]]
        return any(any(rd in d for rd in RETAILER_DOMAINS) for d in domains)

    @property
    def has_review_sites(self) -> bool:
        domains = [r.domain for r in self.serp_results[:5]]
        return any(any(rd in d for rd in REVIEW_DOMAINS) for d in domains)


# ============================================================================
# BÚSQUEDA VIA SERPAPI (prioridad 1 - 1 crédito por búsqueda, solo top 3)
# ============================================================================

def _search_serpapi(
    keyword: str,
    max_results: int = 10,
) -> tuple:
    """
    Busca via SerpAPI con configuración España.
    1 búsqueda = 1 crédito independientemente de resultados.
    Devuelve 10 resultados orgánicos (1 crédito) para poder scrapear
    los 3 primeros que sean artículos/reviews (no tiendas).
    
    Returns:
        Tuple[List[SerpResult], List[str]]:
          - Lista de SerpResult orgánicos
          - Lista de búsquedas relacionadas (para enriquecer SEO)
    """
    api_key = _get_serpapi_key()
    if not api_key:
        logger.warning("SerpAPI: API key no configurada (SERPAPI_API_KEY / serpapi_key)")
        return [], []

    try:
        params = {
            'q': keyword,
            'api_key': api_key,
            'engine': 'google',
            'location': 'Spain',
            'google_domain': 'google.es',
            'gl': 'es',
            'hl': 'es',
            'num': min(max_results, 10),
            'no_cache': 'false',  # Usar cache para no gastar créditos extra
        }

        resp = requests.get(
            'https://serpapi.com/search.json',
            params=params,
            timeout=DEFAULT_TIMEOUT,
        )
        
        # Log HTTP errors con detalle
        if resp.status_code != 200:
            error_body = resp.text[:200]
            logger.error(f"SerpAPI HTTP {resp.status_code}: {error_body}")
            resp.raise_for_status()

        try:
            data = resp.json()
        except (ValueError, json.JSONDecodeError):
            logger.error(f"SerpAPI respuesta no es JSON válido: {resp.text[:200]}")
            return [], []
        
        # Verificar si SerpAPI devolvió error en el JSON
        if 'error' in data:
            logger.error(f"SerpAPI error: {data['error']}")
            return [], []

        results = []
        for item in data.get('organic_results', [])[:max_results]:
            url = item.get('link', '')
            domain = urllib.parse.urlparse(url).netloc or ''
            results.append(SerpResult(
                position=item.get('position', len(results) + 1),
                title=item.get('title', ''),
                url=url,
                domain=domain,
                snippet=item.get('snippet', '')[:200],
            ))

        # Extraer búsquedas relacionadas (útiles para keywords secundarias)
        related = []
        for rs in data.get('related_searches', []):
            q = rs.get('query', '').strip()
            if q:
                related.append(q)

        logger.info(
            f"SerpAPI: {len(results)} resultados, "
            f"{len(related)} related searches para '{keyword}'"
        )
        return results, related

    except requests.exceptions.HTTPError as e:
        logger.error(f"SerpAPI HTTP error: {e}")
        return [], []
    except requests.exceptions.Timeout:
        logger.error(f"SerpAPI timeout ({DEFAULT_TIMEOUT}s) para '{keyword}'")
        return [], []
    except Exception as e:
        logger.warning(f"SerpAPI fallo: {e}. Se usara DuckDuckGo como fallback.")
        return [], []


# ============================================================================
# BÚSQUEDA EN DUCKDUCKGO (fallback gratuito)
# ============================================================================

def _search_duckduckgo(
    keyword: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    lang: str = "es-es",
) -> List[SerpResult]:
    """
    Busca en DuckDuckGo HTML y devuelve resultados orgánicos.
    Gratuito, sin API key. Fallback cuando SerpAPI no está disponible.
    """
    headers = {
        'User-Agent': (
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
    }

    try:
        resp = requests.get(
            'https://html.duckduckgo.com/html/',
            params={'q': keyword, 'kl': lang},
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.error(f"Error buscando en DuckDuckGo: {e}")
        return []

    soup = BeautifulSoup(resp.text, 'html.parser')

    results = []
    for r in soup.select('.result'):
        title_el = r.select_one('.result__title a, .result__a')
        snippet_el = r.select_one('.result__snippet')

        if not title_el:
            continue

        href = title_el.get('href', '')
        # DuckDuckGo envuelve URLs en redirect
        if 'uddg=' in href:
            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
            href = parsed.get('uddg', [href])[0]

        if not href.startswith('http'):
            continue

        # Filtrar ads de DuckDuckGo
        if 'duckduckgo.com' in href:
            continue

        domain = urllib.parse.urlparse(href).netloc or href

        results.append(SerpResult(
            position=len(results) + 1,
            title=title_el.get_text(strip=True),
            url=href,
            domain=domain,
            snippet=snippet_el.get_text(strip=True)[:150] if snippet_el else '',
        ))

        if len(results) >= max_results:
            break

    return results


def search_serp(
    keyword: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    lang: str = "es-es",
) -> tuple:
    """
    Busca en SERPs con prioridad: SerpAPI > DuckDuckGo.
    SerpAPI devuelve 10 resultados orgánicos (1 crédito).
    
    Returns:
        Tuple[List[SerpResult], List[str]]:
          - Lista de resultados orgánicos
          - Lista de búsquedas relacionadas (solo con SerpAPI)
    """
    # Intentar SerpAPI primero (10 resultados = 1 crédito)
    results, related = _search_serpapi(keyword, max_results=max_results)
    if results:
        return results, related

    # Fallback: DuckDuckGo (sin related searches)
    return _search_duckduckgo(keyword, max_results=max_results, lang=lang), []


# ============================================================================
# SCRAPING DE COMPETIDORES
# ============================================================================

_BLOCKED_HOSTNAMES = {'localhost', 'metadata.google.internal'}


def _is_safe_url(url: str) -> bool:
    """Validate URL doesn't target private/internal networks (SSRF protection)."""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        hostname = parsed.hostname or ''
        if not hostname:
            return False
        if hostname in _BLOCKED_HOSTNAMES:
            return False
        try:
            ip = ipaddress.ip_address(hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return False
        except ValueError:
            pass  # Not an IP literal — regular hostname is fine
        return True
    except Exception:
        return False


def scrape_competitor(url: str, timeout: int = DEFAULT_TIMEOUT) -> CompetitorAnalysis:
    """
    Scrapea una URL de competidor y extrae métricas de estructura.

    Args:
        url: URL a scrapear
        timeout: Timeout en segundos

    Returns:
        CompetitorAnalysis con métricas
    """
    domain = urllib.parse.urlparse(url).netloc or url

    if not _is_safe_url(url):
        logger.warning(f"URL bloqueada por SSRF check: {domain}")
        return CompetitorAnalysis(
            url=url, domain=domain, title='',
            success=False, error='URL blocked: private/internal network',
        )

    try:
        # Intentar usar el scraper del proyecto si está disponible
        try:
            from core.scraper import get_scraper
            scraper = get_scraper()
            result = scraper.scrape_url(url, extract_content=False, timeout=timeout)
            if not result.success:
                return CompetitorAnalysis(
                    url=url, domain=domain, title='',
                    success=False, error=result.error or 'Scrape failed',
                )
            raw_html = result.content or ""
            title = result.title or ""
        except ImportError:
            # Fallback: requests directo
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                    '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                ),
            }
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            raw_html = resp.text
            soup_title = BeautifulSoup(raw_html, 'html.parser')
            title = soup_title.title.get_text(strip=True) if soup_title.title else ''

        # Conteo de palabras (texto visible del contenido principal)
        soup = BeautifulSoup(raw_html, 'html.parser')
        
        # Intentar aislar contenido principal (article/main) antes de contar
        main_content = soup.find('article') or soup.find('main') or soup.find(role='main')
        content_soup = main_content if main_content else soup
        
        # Eliminar elementos no relevantes
        for tag in content_soup.find_all(
            ['script', 'style', 'nav', 'footer', 'header', 'aside',
             'noscript', 'form', 'select', 'button', 'iframe', 'svg']
        ):
            tag.decompose()
        text = content_soup.get_text(separator=' ', strip=True)
        word_count = len(text.split())

        # Estructura HTML
        html_lower = raw_html.lower()
        h2_count = html_lower.count('<h2')
        h3_count = html_lower.count('<h3')
        has_table = '<table' in html_lower
        has_faq = 'faq' in html_lower or 'pregunta frecuente' in html_lower
        image_count = html_lower.count('<img')
        list_count = html_lower.count('<ul') + html_lower.count('<ol')

        return CompetitorAnalysis(
            url=url, domain=domain, title=title,
            word_count=word_count, h2_count=h2_count, h3_count=h3_count,
            has_table=has_table, has_faq=has_faq,
            image_count=image_count, list_count=list_count,
            heading_structure=_extract_heading_structure(raw_html),
            content_summary=_extract_content_summary(text, title),
            section_summaries=_extract_section_summaries(raw_html),
            products_mentioned=_extract_products_mentioned(text),
            prices_found=_extract_prices(text),
        )

    except Exception as e:
        logger.warning(f"Error scrapeando {url}: {e}")
        return CompetitorAnalysis(
            url=url, domain=domain, title='',
            success=False, error=str(e),
        )


def _extract_heading_structure(html: str) -> List[str]:
    """Extrae la estructura de headings H2/H3 de un HTML."""
    headings = []
    pattern = re.compile(r'<(h[23])[^>]*>(.*?)</\1>', re.IGNORECASE | re.DOTALL)
    for m in pattern.finditer(html):
        level = m.group(1).upper()
        text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        if text and len(text) > 2:
            prefix = "  " if level == "H3" else ""
            headings.append(f"{prefix}{level}: {text[:80]}")
    return headings[:20]  # Max 20 headings


def _extract_content_summary(text: str, title: str = "") -> str:
    """Genera resumen breve del contenido (primeras 300 palabras significativas)."""
    words = text.split()
    if len(words) > 300:
        summary_text = ' '.join(words[:300]) + '...'
    else:
        summary_text = text
    # Limpiar exceso de espacios
    summary_text = re.sub(r'\s+', ' ', summary_text).strip()
    return summary_text[:800]


def _extract_section_summaries(raw_html: str, max_sections: int = 8, max_chars: int = 200) -> List[str]:
    """
    Extrae heading + primer párrafo por sección.
    
    Cada entrada: "H2: Título de sección\n  Primer párrafo truncado a max_chars..."
    Esto da a Claude el CONTENIDO real bajo cada heading, no solo los títulos.
    
    Args:
        raw_html: HTML crudo del competidor
        max_sections: Máximo de secciones a extraer
        max_chars: Máximo de caracteres del texto por sección
        
    Returns:
        Lista de strings "LEVEL: Título\\n  Texto..."
    """
    soup = BeautifulSoup(raw_html, 'html.parser')
    
    # Aislar contenido principal
    main = soup.find('article') or soup.find('main') or soup.find(role='main') or soup
    
    sections = []
    for heading in main.find_all(['h2', 'h3']):
        title = heading.get_text(strip=True)
        if not title or len(title) < 3:
            continue
        
        # Recoger texto de siblings hasta el siguiente heading
        content_parts = []
        for sib in heading.find_next_siblings():
            if sib.name in ['h2', 'h3', 'h1']:
                break
            if sib.name in ['p', 'li', 'td', 'span', 'div']:
                text = sib.get_text(strip=True)
                if text and len(text) > 10:
                    content_parts.append(text)
        
        content = ' '.join(content_parts)
        if not content:
            continue
            
        # Truncar contenido
        if len(content) > max_chars:
            content = content[:max_chars].rsplit(' ', 1)[0] + '...'
        
        level = heading.name.upper()
        sections.append(f"{level}: {title[:80]}\n  {content}")
        
        if len(sections) >= max_sections:
            break
    
    return sections


def _extract_products_mentioned(text: str) -> List[str]:
    """
    Extrae nombres de producto del texto usando patrones de marcas tech.
    
    Busca: Marca + Modelo (ej: "HyperX Cloud III", "ASUS ROG Strix G16").
    Filtra ruido con lista de marcas tech conocidas y stopwords.
    
    Args:
        text: Texto limpio del competidor
        
    Returns:
        Lista deduplicada de nombres de producto (max 15)
    """
    # Marcas tech comunes en PcComponentes
    brands = (
        r'ASUS|Acer|AMD|Apple|Corsair|Dell|EVGA|Gigabyte|HP|HyperX|Intel|Kingston|'
        r'Lenovo|LG|Logitech|MSI|NVIDIA|Razer|Samsung|SteelSeries|Sony|Cooler Master|'
        r'Noctua|Seagate|Western Digital|WD|TP-Link|Xiaomi|Huawei|Crucial|G\.Skill|'
        r'be quiet|NZXT|Philips|BenQ|AOC|ViewSonic|Realme|OPPO|OnePlus|Nothing|'
        r'Creative|Sennheiser|Audio-Technica|JBL|Bose|Rode|Elgato|Shure|'
        r'Ryzen|GeForce|Radeon|Core i[3579]|RTX \d{4}|RX \d{4}'
    )
    
    # Patrón: Marca seguida de 1-4 palabras que empiecen con mayúscula o número,
    # pero NO palabras comunes españolas
    stopwords = {'es', 'el', 'la', 'los', 'las', 'un', 'una', 'de', 'del', 'en',
                 'con', 'por', 'para', 'que', 'se', 'su', 'al', 'no', 'son', 'tiene',
                 'ofrece', 'cuenta', 'viene', 'incluye', 'permite', 'precio', 'mejor',
                 'muy', 'más', 'como', 'sin', 'sobre', 'este', 'esta', 'pero', 'tiene'}
    
    pattern = rf'(?:{brands})(?:\s+[A-Z0-9][a-zA-Z0-9+\-]*){{1,4}}'
    matches = re.findall(pattern, text)
    
    # Limpiar: quitar stopwords del final del match
    seen = set()
    products = []
    for m in matches:
        words = m.strip().split()
        # Recortar desde el final si hay stopwords
        while len(words) > 1 and words[-1].lower() in stopwords:
            words.pop()
        clean = ' '.join(words).rstrip('.,;:!?')
        if len(clean) < 5 or len(words) < 2:
            continue
        key = clean.lower()
        if key not in seen:
            seen.add(key)
            products.append(clean)
    
    return products[:15]


def _extract_prices(text: str) -> List[str]:
    """
    Extrae precios del texto (formatos EUR comunes).
    
    Detecta: 89,99€, 89.99€, 89,99 €, 89€, desde 89€
    
    Args:
        text: Texto limpio del competidor
        
    Returns:
        Lista deduplicada de precios (max 20)
    """
    # Patrón flexible para precios en euros (soporta 89€, 89,99€, 1.799€, 1.299,99€)
    prices = re.findall(r'(\d{1,3}(?:\.\d{3})*(?:,\d{2})?)\s*€', text)
    
    # Deduplicar
    seen = set()
    unique = []
    for p in prices:
        if p not in seen:
            seen.add(p)
            unique.append(f"{p}€")
    
    return unique[:20]


def scrape_competitors(
    serp_results: List[SerpResult],
    max_scrape: int = DEFAULT_MAX_SCRAPE,
    skip_domains: Optional[List[str]] = None,
) -> List[CompetitorAnalysis]:
    """
    Scrapea los primeros N competidores relevantes de los resultados SERP.

    Args:
        serp_results: Resultados de búsqueda
        max_scrape: Máximo de URLs a scrapear
        skip_domains: Dominios adicionales a excluir

    Returns:
        Lista de CompetitorAnalysis
    """
    all_skip = SKIP_DOMAINS + (skip_domains or [])

    urls_to_scrape = []
    skipped = []
    for r in serp_results:
        domain = urllib.parse.urlparse(r.url).netloc.lower()
        if any(d in domain for d in all_skip):
            skipped.append(domain)
            continue
        urls_to_scrape.append(r.url)
        if len(urls_to_scrape) >= max_scrape:
            break

    if skipped:
        logger.info(f"SERP scrape: {len(skipped)} dominios filtrados: {', '.join(skipped[:5])}")
    logger.info(f"SERP scrape: {len(urls_to_scrape)} URLs a scrapear de {len(serp_results)} resultados")

    results = []
    for url in urls_to_scrape:
        analysis = scrape_competitor(url)
        results.append(analysis)
        if not analysis.success:
            logger.warning(f"SERP scrape fallido: {analysis.domain} — {analysis.error[:80]}")
        else:
            logger.info(f"SERP scrape OK: {analysis.domain} — {analysis.word_count} palabras, {analysis.h2_count} H2")
        time.sleep(DEFAULT_SCRAPE_DELAY)

    return results


# ============================================================================
# INVESTIGACIÓN COMPLETA
# ============================================================================

def research_serp(
    keyword: str,
    max_results: int = DEFAULT_MAX_RESULTS,
    max_scrape: int = 5,  # Default 5: top 5 orgánicos para análisis competitivo rico
    skip_domains: Optional[List[str]] = None,
) -> SerpResearchResult:
    """
    Ejecuta una investigación SERP completa: busca + scrapea + analiza.

    Args:
        keyword: Keyword a investigar
        max_results: Máximo de resultados de búsqueda
        max_scrape: Máximo de competidores a scrapear
        skip_domains: Dominios adicionales a excluir

    Returns:
        SerpResearchResult con toda la investigación
    """
    keyword = keyword.strip()
    if not keyword:
        return SerpResearchResult(keyword=keyword, success=False, error="Keyword vacía")

    # 1. Buscar (returns tuple: results, related_searches)
    serp_results, related_searches = search_serp(keyword, max_results=max_results)
    if not serp_results:
        # Diagnóstico: ¿hay API key?
        has_key = bool(_get_serpapi_key())
        if not has_key:
            error_msg = (
                f"SerpAPI key no detectada. "
                f"Verifica que `serpapi_key` está en Settings > Secrets "
                f"(formato: serpapi_key = \"tu_clave\"). "
                f"Si ya la tienes configurada, reinicia la app (Manage app > Reboot)."
            )
        else:
            error_msg = (
                f"No se encontraron resultados para \"{keyword}\". "
                f"Verifica que la API key de SerpAPI es válida y tiene créditos."
            )
        return SerpResearchResult(
            keyword=keyword, success=False,
            error=error_msg,
        )

    # 2. Scrapear competidores
    competitors = scrape_competitors(
        serp_results, max_scrape=max_scrape,
        skip_domains=skip_domains,
    )

    # 3. Generar insights
    research = SerpResearchResult(
        keyword=keyword,
        serp_results=serp_results,
        related_searches=related_searches,
        competitors=competitors,
    )

    insights = {
        'intent': 'mixed',
        'avg_word_count': research.avg_word_count,
        'avg_h2': research.avg_h2_count,
        'has_pccom': research.has_pccom,
        'has_retailers': research.has_retailers,
        'has_review_sites': research.has_review_sites,
        'competitors_scraped': sum(1 for c in competitors if c.success),
        'total_results': len(serp_results),
    }

    if research.has_retailers and research.has_review_sites:
        insights['intent'] = 'mixed_transactional_informational'
    elif research.has_retailers:
        insights['intent'] = 'transactional'
    elif research.has_review_sites:
        insights['intent'] = 'informational'

    research.insights = insights
    return research


# ============================================================================
# FORMATEO PARA PROMPTS
# ============================================================================

def format_for_prompt(research: SerpResearchResult) -> str:
    """
    Formatea el resultado de investigación para inyectar en un prompt de Claude.

    Args:
        research: SerpResearchResult

    Returns:
        Texto formateado para incluir en el prompt
    """
    if not research.success:
        return ""

    lines = [
        f"## 🔍 ANÁLISIS COMPETITIVO SERP — \"{research.keyword}\"",
        "",
    ]

    # Top 5 resultados
    lines.append("### Qué posiciona en las SERPs")
    for r in research.serp_results[:5]:
        lines.append(f"- #{r.position} `{r.domain}` — {r.title[:60]}")
    lines.append("")

    # Análisis de competidores
    successful = [c for c in research.competitors if c.success]
    if successful:
        lines.append("### Análisis de competidores")
        for c in successful:
            elements = []
            if c.has_table:
                elements.append("tablas")
            if c.has_faq:
                elements.append("FAQs")
            if c.image_count > 2:
                elements.append(f"{c.image_count} imgs")
            if c.list_count > 1:
                elements.append(f"{c.list_count} listas")
            elem_str = f" | Elementos: {', '.join(elements)}" if elements else ""

            lines.append(
                f"- **{c.domain}**: ~{c.word_count} palabras, "
                f"{c.h2_count} H2, {c.h3_count} H3{elem_str}"
            )
            
            # Estructura de headings (seed critico para generacion)
            if c.heading_structure:
                lines.append(f"  Estructura:")
                for h in c.heading_structure[:10]:
                    lines.append(f"    {h}")
            
            # Contenido por sección (datos concretos bajo cada heading)
            if c.section_summaries:
                lines.append(f"  Contenido clave:")
                for s in c.section_summaries[:6]:
                    # Indentar cada línea del section summary
                    for line in s.split('\n'):
                        lines.append(f"    {line}")
            elif c.content_summary:
                # Fallback a content_summary si no hay secciones
                summary = c.content_summary[:300]
                lines.append(f"  Resumen: {summary}")
            
            # Productos mencionados
            if c.products_mentioned:
                lines.append(f"  Productos: {', '.join(c.products_mentioned[:10])}")
            
            # Precios encontrados
            if c.prices_found:
                lines.append(f"  Precios: {', '.join(c.prices_found[:10])}")
            
            lines.append("")

        lines.append("")
        lines.append(f"**Promedios:** ~{research.avg_word_count} palabras, {research.avg_h2_count} H2")
        lines.append("")

    # Insights
    insights = research.insights
    lines.append("### Recomendaciones basadas en SERPs")
    if insights.get('has_retailers'):
        lines.append("- Intención TRANSACCIONAL detectada: incluye comparativas, precios y CTAs directos")
    if insights.get('has_review_sites'):
        lines.append("- Intención INFORMATIVA detectada: incluye análisis técnico detallado")
    if insights.get('has_pccom'):
        lines.append("- PcComponentes YA posiciona: el contenido debe SUPERAR lo existente")
    if research.avg_word_count > 0:
        lines.append(f"- Longitud competitiva: apunta a ≥{research.avg_word_count} palabras")
    if research.avg_h2_count > 0:
        lines.append(f"- Estructura competitiva: ≥{research.avg_h2_count} secciones H2")

    # Búsquedas relacionadas (keywords secundarias de Google)
    if research.related_searches:
        lines.append("")
        lines.append("### Búsquedas relacionadas (Google)")
        lines.append("Estas son las búsquedas que Google sugiere — úsalas como keywords secundarias o subsecciones:")
        for rs in research.related_searches[:8]:
            lines.append(f"- {rs}")

    return "\n".join(lines)


def format_for_display(research: SerpResearchResult) -> str:
    """
    Formatea para mostrar en el asistente (Markdown con emojis).

    Args:
        research: SerpResearchResult

    Returns:
        Texto Markdown para UI
    """
    if not research.success:
        return f"⚠️ {research.error}"

    lines = [f"🔍 **Investigación SERP para: \"{research.keyword}\"**\n"]

    # Resultados
    lines.append(f"**Top {len(research.serp_results)} resultados:**\n")
    for r in research.serp_results:
        title_short = r.title[:60] + ('...' if len(r.title) > 60 else '')
        lines.append(f"{r.position}. **{title_short}**")
        lines.append(f"   `{r.domain}`")
        if r.snippet:
            lines.append(f"   _{r.snippet[:120]}_")

    # Competidores
    successful = [c for c in research.competitors if c.success]
    if successful:
        lines.append("\n---\n**📊 Análisis de competidores:**\n")
        for c in successful:
            elements = []
            if c.has_table:
                elements.append("tablas")
            if c.image_count > 2:
                elements.append(f"{c.image_count} imágenes")
            if c.list_count > 1:
                elements.append(f"{c.list_count} listas")
            if c.has_faq:
                elements.append("FAQs")

            lines.append(f"**{c.domain}** — _{c.title[:60]}_")
            lines.append(f"- Longitud: ~{c.word_count} palabras")
            lines.append(f"- Estructura: {c.h2_count} H2, {c.h3_count} H3")
            if elements:
                lines.append(f"- Elementos: {', '.join(elements)}")
            lines.append("")

        lines.append("**📏 Promedios de la competencia:**")
        lines.append(f"- Longitud media: ~{research.avg_word_count} palabras")
        lines.append(f"- Secciones H2 media: {research.avg_h2_count}")

    # Insights
    lines.append("\n---\n**💡 Insights para tu contenido:**\n")
    if research.has_retailers:
        lines.append("- 🛒 Hay retailers en las SERPs → intención transaccional. Prioriza comparativas y CTAs.")
    if research.has_review_sites:
        lines.append("- 📝 Hay medios tech → intención informativa. Incluye análisis técnico detallado.")
    if research.has_pccom:
        lines.append("- 🟠 PcComponentes ya posiciona. Verifica con [GSC_CHECK] para más detalle.")
    if not research.has_retailers and not research.has_review_sites:
        lines.append("- 🔎 SERPs mixtas. Combina información y producto.")

    scraped = sum(1 for c in research.competitors if c.success)
    lines.append(f"- Competidores analizados: {scraped} de {len(research.serp_results)} resultados")

    # Búsquedas relacionadas
    if research.related_searches:
        lines.append("\n---\n**🔗 Búsquedas relacionadas (Google):**\n")
        for rs in research.related_searches[:8]:
            lines.append(f"- {rs}")

    return "\n".join(lines)


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'SerpResult',
    'CompetitorAnalysis',
    'SerpResearchResult',
    'search_serp',
    'scrape_competitor',
    'scrape_competitors',
    'research_serp',
    'format_for_prompt',
    'format_for_display',
    '_get_serpapi_key',  # Usado por app.py para diagnóstico
]
