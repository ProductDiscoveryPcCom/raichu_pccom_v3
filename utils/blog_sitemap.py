# -*- coding: utf-8 -*-
"""
Blog Sitemap Parser - PcComponentes Content Generator
Versión 1.0.0

Parsea el sitemap del blog de PcComponentes para obtener la lista de
posts publicados. Se usa en Oportunidades para cruzar con datos de GSC
y detectar qué posts del blog tienen oportunidades de mejora.

Autor: PcComponentes - Product Discovery & Content
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Optional, Any
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

BLOG_SITEMAP_URL = "https://www.pccomponentes.com/sitemap/blog.xml"

# Caché TTL en segundos (1 hora)
_CACHE_TTL = 3600


def fetch_blog_urls(
    sitemap_url: str = BLOG_SITEMAP_URL,
    timeout: int = 15,
) -> Optional[List[Dict[str, Any]]]:
    """
    Descarga y parsea el sitemap XML del blog.

    Args:
        sitemap_url: URL del sitemap XML
        timeout: Timeout de la request en segundos

    Returns:
        Lista de dicts con url, lastmod (si disponible), o None si falla.
        [{"url": "https://...", "lastmod": "2026-01-15"}, ...]
    """
    # Cache en session_state de Streamlit
    try:
        import streamlit as st
        cached = st.session_state.get('_blog_sitemap_cache')
        if cached:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < _CACHE_TTL:
                logger.debug(f"Blog sitemap cache hit ({age:.0f}s)")
                return cached["data"]
    except ImportError:
        st = None

    try:
        import requests
        resp = requests.get(sitemap_url, timeout=timeout, headers={
            "User-Agent": "PcComponentes-ContentGenerator/1.0"
        })
        resp.raise_for_status()
        xml_content = resp.text
    except ImportError:
        # Fallback sin requests
        import urllib.request
        req = urllib.request.Request(sitemap_url, headers={
            "User-Agent": "PcComponentes-ContentGenerator/1.0"
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            xml_content = resp.read().decode('utf-8')
    except Exception as e:
        logger.error(f"Error descargando sitemap {sitemap_url}: {e}")
        return None

    # Parsear XML
    try:
        urls = _parse_sitemap_xml(xml_content)
    except Exception as e:
        logger.error(f"Error parseando sitemap XML: {e}")
        return None

    logger.info(f"Blog sitemap: {len(urls)} URLs parseadas desde {sitemap_url}")

    # Cachear
    if st is not None:
        st.session_state['_blog_sitemap_cache'] = {
            "data": urls,
            "timestamp": datetime.now(),
        }

    return urls


def _parse_sitemap_xml(xml_content: str) -> List[Dict[str, Any]]:
    """Parsea el contenido XML del sitemap."""
    # Eliminar namespace para simplificar el parsing
    xml_content = re.sub(r'\sxmlns="[^"]+"', '', xml_content, count=1)

    root = ET.fromstring(xml_content)
    urls = []

    for url_elem in root.findall('.//url'):
        loc = url_elem.findtext('loc', '').strip()
        if not loc:
            continue

        entry: Dict[str, Any] = {"url": loc}

        lastmod = url_elem.findtext('lastmod', '').strip()
        if lastmod:
            entry["lastmod"] = lastmod

        changefreq = url_elem.findtext('changefreq', '').strip()
        if changefreq:
            entry["changefreq"] = changefreq

        priority = url_elem.findtext('priority', '').strip()
        if priority:
            try:
                entry["priority"] = float(priority)
            except ValueError:
                pass

        urls.append(entry)

    return urls


def get_blog_url_set(sitemap_url: str = BLOG_SITEMAP_URL) -> set:
    """
    Obtiene un set de URLs del blog para lookup rápido.

    Returns:
        set de strings (URLs normalizadas)
    """
    urls = fetch_blog_urls(sitemap_url)
    if not urls:
        return set()
    return {_normalize_url(u["url"]) for u in urls}


def _normalize_url(url: str) -> str:
    """Normaliza URL para comparación (sin trailing slash, sin www variantes)."""
    url = url.rstrip('/')
    url = url.replace("http://", "https://")
    return url


def filter_blog_opportunities(
    gsc_records: List[Dict[str, Any]],
    blog_urls: Optional[set] = None,
) -> List[Dict[str, Any]]:
    """
    Filtra registros de GSC para quedarse solo con los que pertenecen al blog.

    Args:
        gsc_records: Lista de registros GSC [{"query": ..., "url": ..., ...}]
        blog_urls: Set de URLs del blog. Si None, lo descarga.

    Returns:
        Lista filtrada de registros cuya URL pertenece al blog.
    """
    if blog_urls is None:
        blog_urls = get_blog_url_set()

    if not blog_urls:
        logger.warning("Blog sitemap vacío o no disponible — no se puede filtrar")
        return []

    filtered = []
    for record in gsc_records:
        url = record.get('url', '') or record.get('page', '')
        if url and _normalize_url(url) in blog_urls:
            filtered.append({**record, 'is_blog': True})

    return filtered
