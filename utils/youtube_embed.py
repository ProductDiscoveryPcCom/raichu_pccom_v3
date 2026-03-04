# -*- coding: utf-8 -*-
"""
YouTube Embed - PcComponentes Content Generator
Version 1.0.0 - 2026-02-12

Extrae datos de videos de YouTube y genera HTML de embed responsive
compatible con el CMS de PcComponentes.

Autor: PcComponentes - Product Discovery & Content
"""

import re
import html as html_module
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

MAX_VIDEOS = 3


@dataclass
class YouTubeVideo:
    """Datos extraidos de un video de YouTube."""
    video_id: str
    url: str
    title: str = ""
    channel: str = ""
    thumbnail_url: str = ""
    embed_url: str = ""
    heading_id: str = ""
    heading_text: str = ""

    def __post_init__(self):
        if not self.embed_url:
            self.embed_url = f"https://www.youtube.com/embed/{self.video_id}"
        if not self.thumbnail_url:
            self.thumbnail_url = f"https://i.ytimg.com/vi/{self.video_id}/hqdefault.jpg"


def extract_video_id(url_or_embed: str) -> Optional[str]:
    """
    Extrae el video ID de cualquier formato de URL o código embed de YouTube.
    
    Soporta:
      - https://www.youtube.com/watch?v=VIDEO_ID
      - https://youtu.be/VIDEO_ID
      - https://www.youtube.com/embed/VIDEO_ID
      - https://www.youtube.com/v/VIDEO_ID
      - URLs con parametros adicionales
      - Código iframe: <iframe ... src="https://www.youtube.com/embed/VIDEO_ID" ...>
    """
    if not url_or_embed:
        return None

    text = url_or_embed.strip()

    # 1. Intentar extraer de iframe embed code primero
    iframe_match = re.search(
        r'src=["\']https?://(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})',
        text,
    )
    if iframe_match:
        return iframe_match.group(1)

    # 2. Patrones de URL estándar
    patterns = [
        r'(?:youtube\.com/watch\?.*?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/v/)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$',  # Solo el ID
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)

    return None


def parse_iframe_embed(embed_code: str) -> Optional[Dict[str, str]]:
    """
    Parsea un código iframe embed de YouTube y extrae video_id, title y otros attrs.
    
    Args:
        embed_code: Código HTML del iframe, ej:
            <iframe width="560" height="315" 
             src="https://www.youtube.com/embed/dQw4w9WgXcQ" 
             title="Never Gonna Give You Up" 
             frameborder="0" allowfullscreen></iframe>
    
    Returns:
        Dict con video_id, title, embed_url o None si no se detecta
    """
    if not embed_code or '<iframe' not in embed_code.lower():
        return None
    
    # Extraer video_id del src
    video_id = extract_video_id(embed_code)
    if not video_id:
        return None
    
    result = {
        'video_id': video_id,
        'embed_url': f"https://www.youtube.com/embed/{video_id}",
        'url': f"https://www.youtube.com/watch?v={video_id}",
    }
    
    # Extraer title del atributo title=""
    title_match = re.search(r'title=["\']([^"\']*)["\']', embed_code)
    if title_match:
        result['title'] = html_module.unescape(title_match.group(1))
    
    return result


def fetch_video_metadata(video_id: str) -> Dict[str, str]:
    """
    Obtiene metadatos del video via oembed (no requiere API key).
    
    Returns:
        Dict con title, author_name, thumbnail_url
    """
    import urllib.request
    import json

    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"

    try:
        req = urllib.request.Request(
            oembed_url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            return {
                'title': data.get('title', ''),
                'channel': data.get('author_name', ''),
                'thumbnail_url': data.get('thumbnail_url', ''),
            }
    except Exception as e:
        logger.warning(f"No se pudo obtener metadata de video {video_id}: {e}")
        return {
            'title': '',
            'channel': '',
            'thumbnail_url': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        }


def parse_youtube_url(url: str) -> Optional[YouTubeVideo]:
    """
    Parsea una URL de YouTube y devuelve un objeto YouTubeVideo con metadatos.
    """
    video_id = extract_video_id(url)
    if not video_id:
        return None

    metadata = fetch_video_metadata(video_id)

    return YouTubeVideo(
        video_id=video_id,
        url=url.strip(),
        title=metadata.get('title', ''),
        channel=metadata.get('channel', ''),
        thumbnail_url=metadata.get('thumbnail_url', ''),
    )


def generate_embed_html(video: YouTubeVideo) -> str:
    """
    Genera HTML de embed responsive para un video de YouTube.
    Formato compatible con el CMS de PcComponentes.
    """
    title_attr = html_module.escape(video.title if video.title else "Video de YouTube")

    html = (
        f'<div style="position:relative;padding-bottom:56.25%;height:0;overflow:hidden;'
        f'max-width:100%;margin:1.5rem 0;border-radius:8px;">'
        f'<iframe src="{video.embed_url}" '
        f'title="{title_attr}" '
        f'style="position:absolute;top:0;left:0;width:100%;height:100%;border:0;border-radius:8px;" '
        f'allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture" '
        f'allowfullscreen loading="lazy"></iframe>'
        f'</div>'
    )

    return html


def generate_contextual_embed(
    video: YouTubeVideo,
    heading_text: str = "",
) -> str:
    """
    Genera embed con contexto: referencia al heading donde se inserta.
    """
    embed = generate_embed_html(video)

    if video.title:
        caption = f'<p style="font-size:0.85rem;color:#666;margin-top:0.5rem;text-align:center;">{html_module.escape(video.title)}</p>'
        embed += caption

    return embed


def insert_video_after_heading(
    html_content: str,
    video: YouTubeVideo,
    heading_id: str,
) -> str:
    """
    Inserta el embed de video despues del heading especificado.
    
    Busca el heading por: 1) ID real en el HTML, 2) texto exacto del heading,
    3) texto parcial. Inserta después del primer párrafo posterior al heading.
    """
    if not html_content or (not heading_id and not video.heading_text):
        return html_content

    embed_html = generate_contextual_embed(video, heading_id)
    heading_text = video.heading_text or ""

    def _insert_after_heading(match_end: int) -> str:
        """Inserta el embed después del primer </p> tras el heading."""
        insert_pos = match_end
        next_p = re.search(r'</p>', html_content[insert_pos:])
        if next_p:
            insert_pos += next_p.end()
        return html_content[:insert_pos] + '\n' + embed_html + '\n' + html_content[insert_pos:]

    # 1. Buscar heading por ID real en el HTML
    if heading_id:
        pattern = re.compile(
            rf'(<h[23][^>]*id=["\']?{re.escape(heading_id)}["\']?[^>]*>.*?</h[23]>)',
            re.IGNORECASE | re.DOTALL
        )
        match = pattern.search(html_content)
        if match:
            return _insert_after_heading(match.end())

    # 2. Buscar heading por texto exacto
    if heading_text:
        for level in ['h2', 'h3']:
            text_pattern = re.compile(
                rf'(<{level}[^>]*>)(.*?)(</{level}>)',
                re.IGNORECASE | re.DOTALL
            )
            for m in text_pattern.finditer(html_content):
                clean_text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                if clean_text == heading_text:
                    return _insert_after_heading(m.end())
    
    # 3. Buscar heading por texto parcial (contiene)
    if heading_text and len(heading_text) > 5:
        ht_lower = heading_text.lower()
        for level in ['h2', 'h3']:
            text_pattern = re.compile(
                rf'(<{level}[^>]*>)(.*?)(</{level}>)',
                re.IGNORECASE | re.DOTALL
            )
            for m in text_pattern.finditer(html_content):
                clean_text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
                if ht_lower in clean_text.lower() or clean_text.lower() in ht_lower:
                    return _insert_after_heading(m.end())

    # Fallback: insertar al final del contenido
    logger.warning(f"Heading '{heading_id}' / '{heading_text}' no encontrado, insertando video al final")
    return html_content + '\n' + embed_html


def insert_videos_in_html(
    html_content: str,
    videos: List[YouTubeVideo],
) -> str:
    """
    Inserta multiples videos en el HTML segun sus heading assignments.
    """
    result = html_content
    for video in videos:
        if video.heading_id:
            result = insert_video_after_heading(result, video, video.heading_id)
    return result
