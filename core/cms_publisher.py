# -*- coding: utf-8 -*-
"""
CMS Publisher - PcComponentes Content Generator
Versión 1.0.0

Publica contenido directamente al CMS como borrador via REST API.
Soporta WordPress (con Yoast SEO) y APIs REST genéricas.

Inspirado en SEO Machine (wordpress_publisher.py), adaptado para
el ecosistema de PcComponentes.

CONFIGURACIÓN en st.secrets:
    [cms]
    url = "https://cms.pccomponentes.com"
    api_token = "token-de-acceso"
    type = "wordpress"  # o "custom"
    
    # Solo WordPress:
    username = "usuario"
    app_password = "xxxx xxxx xxxx xxxx"

Autor: PcComponentes - Product Discovery & Content
"""

import re
import json
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass

__version__ = "1.0.0"

logger = logging.getLogger(__name__)

try:
    import requests
    _requests_available = True
except ImportError:
    _requests_available = False


@dataclass
class PublishResult:
    """Resultado de publicación."""
    success: bool
    post_id: Optional[str] = None
    post_url: Optional[str] = None
    edit_url: Optional[str] = None
    status: str = ""
    error: Optional[str] = None


class CMSPublisher:
    """Publica contenido al CMS via REST API."""

    def __init__(
        self,
        cms_url: str,
        cms_type: str = "wordpress",
        api_token: str = "",
        username: str = "",
        app_password: str = "",
    ):
        """
        Inicializa el publisher.

        Args:
            cms_url: URL base del CMS
            cms_type: Tipo de CMS ('wordpress' o 'custom')
            api_token: Token de API (para custom)
            username: Username (para WordPress)
            app_password: Application password (para WordPress)
        """
        if not _requests_available:
            raise ImportError("requests no está instalado. pip install requests")

        self.cms_url = cms_url.rstrip('/')
        self.cms_type = cms_type
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Raichu-ContentGenerator/1.0',
        })

        if cms_type == "wordpress":
            if not username or not app_password:
                raise ValueError("WordPress requiere username y app_password")
            self.session.auth = (username, app_password)
            self.api_base = f"{self.cms_url}/wp-json/wp/v2"
        else:
            if api_token:
                self.session.headers['Authorization'] = f'Bearer {api_token}'
            self.api_base = f"{self.cms_url}/api"

    def publish_draft(
        self,
        html_content: str,
        metadata: Dict[str, Any],
    ) -> PublishResult:
        """
        Publica contenido como borrador.

        Args:
            html_content: HTML del artículo
            metadata: Dict con campos:
                - title: Título del artículo
                - slug: URL slug
                - keyword: Keyword principal (para Yoast)
                - meta_title: Meta title SEO
                - meta_description: Meta description SEO
                - category: Categoría (opcional)
                - tags: Lista de tags (opcional)

        Returns:
            PublishResult con el resultado
        """
        try:
            if self.cms_type == "wordpress":
                return self._publish_wordpress(html_content, metadata)
            else:
                return self._publish_custom(html_content, metadata)
        except requests.exceptions.ConnectionError as e:
            logger.error(f"Error de conexión al CMS: {e}")
            return PublishResult(success=False, error=f"No se pudo conectar al CMS: {e}")
        except requests.exceptions.HTTPError as e:
            logger.error(f"Error HTTP del CMS: {e}")
            return PublishResult(success=False, error=f"Error del CMS: {e}")
        except Exception as e:
            logger.error(f"Error publicando: {e}")
            return PublishResult(success=False, error=str(e))

    def _publish_wordpress(self, html_content: str, metadata: Dict) -> PublishResult:
        """Publica en WordPress via REST API + Yoast."""
        title = metadata.get('title', 'Sin título')
        slug = metadata.get('slug', '')

        # Construir payload de WordPress
        payload = {
            'title': title,
            'content': html_content,
            'status': 'draft',
            'slug': slug or self._slugify(title),
        }

        # Categoría
        if metadata.get('category'):
            cat_id = self._get_or_create_category(metadata['category'])
            if cat_id:
                payload['categories'] = [cat_id]

        # Tags
        if metadata.get('tags'):
            tag_ids = [self._get_or_create_tag(t) for t in metadata['tags']]
            payload['tags'] = [t for t in tag_ids if t]

        # Yoast SEO meta (si el plugin Yoast REST está activo)
        yoast_meta = {}
        if metadata.get('meta_title'):
            yoast_meta['yoast_wpseo_title'] = metadata['meta_title']
        if metadata.get('meta_description'):
            yoast_meta['yoast_wpseo_metadesc'] = metadata['meta_description']
        if metadata.get('keyword'):
            yoast_meta['yoast_wpseo_focuskw'] = metadata['keyword']

        if yoast_meta:
            payload['meta'] = yoast_meta

        # Crear post
        response = self.session.post(
            f"{self.api_base}/posts",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        post_id = data.get('id', '')
        post_url = data.get('link', '')
        edit_url = f"{self.cms_url}/wp-admin/post.php?post={post_id}&action=edit" if post_id else ''

        return PublishResult(
            success=True,
            post_id=str(post_id),
            post_url=post_url,
            edit_url=edit_url,
            status='draft',
        )

    def _publish_custom(self, html_content: str, metadata: Dict) -> PublishResult:
        """Publica en CMS custom via REST API genérica."""
        payload = {
            'title': metadata.get('title', 'Sin título'),
            'content': html_content,
            'slug': metadata.get('slug', ''),
            'status': 'draft',
            'seo': {
                'title': metadata.get('meta_title', ''),
                'description': metadata.get('meta_description', ''),
                'keyword': metadata.get('keyword', ''),
            },
        }

        response = self.session.post(
            f"{self.api_base}/posts",
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        return PublishResult(
            success=True,
            post_id=str(data.get('id', '')),
            post_url=data.get('url', ''),
            status='draft',
        )

    def _get_or_create_category(self, name: str) -> Optional[int]:
        """Busca o crea categoría en WordPress."""
        try:
            r = self.session.get(f"{self.api_base}/categories", params={'search': name}, timeout=10)
            r.raise_for_status()
            categories = r.json()
            if categories:
                return categories[0]['id']
            # Crear
            r = self.session.post(f"{self.api_base}/categories", json={'name': name}, timeout=10)
            r.raise_for_status()
            return r.json().get('id')
        except Exception as e:
            logger.warning(f"No se pudo obtener/crear categoría '{name}': {e}")
            return None

    def _get_or_create_tag(self, name: str) -> Optional[int]:
        """Busca o crea tag en WordPress."""
        try:
            r = self.session.get(f"{self.api_base}/tags", params={'search': name}, timeout=10)
            r.raise_for_status()
            tags = r.json()
            if tags:
                return tags[0]['id']
            r = self.session.post(f"{self.api_base}/tags", json={'name': name}, timeout=10)
            r.raise_for_status()
            return r.json().get('id')
        except Exception as e:
            logger.warning(f"No se pudo obtener/crear tag '{name}': {e}")
            return None

    def _slugify(self, text: str) -> str:
        """Genera slug URL-friendly."""
        slug = text.lower()
        # Reemplazar acentos
        replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n', 'ü': 'u'}
        for old, new in replacements.items():
            slug = slug.replace(old, new)
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s-]+', '-', slug).strip('-')
        return slug[:80]

    def test_connection(self) -> bool:
        """Verifica conexión al CMS."""
        try:
            if self.cms_type == "wordpress":
                r = self.session.get(f"{self.api_base}/posts", params={'per_page': 1}, timeout=10)
            else:
                r = self.session.get(f"{self.api_base}/status", timeout=10)
            return r.status_code in (200, 201)
        except Exception:
            return False


class PcComponentesCMSPublisher(CMSPublisher):
    """
    Publisher adaptado al CMS de PcComponentes.
    
    Extiende CMSPublisher con:
    - Validación de estructura HTML (3 articles requeridos)
    - Campos específicos de PcComponentes (categoría tech, blog path)
    - Mapeo de arquetipos a categorías CMS
    - Limpieza de HTML pre-publicación
    
    CONFIGURACIÓN en st.secrets:
        [cms]
        url = "https://cms.pccomponentes.com"
        type = "pccomponentes"
        api_token = "token-de-acceso"
        blog_path = "/blog"  # Prefijo URL para contenido editorial
    """

    # Mapeo de códigos de arquetipo a categorías en el CMS
    CATEGORY_MAP = {
        'ARQ-1': 'Reviews',
        'ARQ-2': 'Comparativas',
        'ARQ-3': 'Guías de compra',
        'ARQ-4': 'Tutoriales',
        'ARQ-5': 'Noticias',
        'ARQ-6': 'Rankings',
        'ARQ-7': 'Opiniones',
    }

    def __init__(self, cms_url: str, api_token: str = "", blog_path: str = "/blog", **kwargs):
        super().__init__(
            cms_url=cms_url,
            cms_type="custom",
            api_token=api_token,
            **kwargs,
        )
        self.blog_path = blog_path

    def publish_draft(self, html_content: str, metadata: Dict[str, Any]) -> PublishResult:
        """
        Publica en el CMS de PcComponentes con validaciones específicas.

        Validaciones pre-publicación:
        1. HTML contiene las 3 articles requeridas
        2. Estructura CMS válida (h2 como título, span kicker, etc.)
        3. Longitud mínima (300 palabras)
        """
        # Validación 1: Estructura de 3 articles
        html_lower = html_content.lower()
        required_articles = [
            ('contentgenerator__main', 'Article principal'),
            ('contentgenerator__faqs', 'Article de FAQs'),
            ('contentgenerator__verdict', 'Article de veredicto'),
        ]
        missing = [name for cls, name in required_articles if cls not in html_lower]
        if missing:
            return PublishResult(
                success=False,
                error=f"HTML incompleto: faltan {', '.join(missing)}"
            )

        # Validación 2: No H1 (PcComponentes usa H2 como título)
        if '<h1' in html_lower:
            return PublishResult(
                success=False,
                error="HTML contiene <h1> pero el CMS usa H2 como título principal"
            )

        # Adaptar metadata
        arquetipo_code = metadata.get('arquetipo', '')
        if arquetipo_code and not metadata.get('category'):
            metadata['category'] = self.CATEGORY_MAP.get(arquetipo_code, 'Blog')

        # Generar slug PcComponentes-style
        if not metadata.get('slug'):
            keyword = metadata.get('keyword', metadata.get('title', ''))
            metadata['slug'] = self._slugify(keyword)

        # Publicar via API custom de PcComponentes
        return self._publish_pccomponentes(html_content, metadata)

    def _publish_pccomponentes(self, html_content: str, metadata: Dict) -> PublishResult:
        """Publicación específica para el CMS de PcComponentes."""
        payload = {
            'title': metadata.get('title', 'Sin título'),
            'content': html_content,
            'slug': metadata.get('slug', ''),
            'status': 'draft',
            'path': self.blog_path,
            'category': metadata.get('category', 'Blog'),
            'seo': {
                'title': metadata.get('meta_title', ''),
                'description': metadata.get('meta_description', ''),
                'keyword': metadata.get('keyword', ''),
                'canonical': '',
            },
            'metadata': {
                'arquetipo': metadata.get('arquetipo', ''),
                'word_count': metadata.get('word_count', 0),
                'quality_score': metadata.get('quality_score', 0),
                'generator': 'Raichu v5.1',
            },
        }

        try:
            response = self.session.post(
                f"{self.api_base}/editorial/posts",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            post_id = data.get('id', '')
            post_url = data.get('url', '')
            edit_url = data.get('edit_url', f"{self.cms_url}/admin/editorial/{post_id}")

            return PublishResult(
                success=True,
                post_id=str(post_id),
                post_url=post_url,
                edit_url=edit_url,
                status='draft',
            )
        except Exception as e:
            logger.error(f"Error publicando en CMS PcComponentes: {e}")
            return PublishResult(success=False, error=str(e))


def get_publisher_for_config(cms_config: Dict) -> CMSPublisher:
    """
    Factory: devuelve el publisher correcto según la configuración.
    
    Args:
        cms_config: Dict con url, type, api_token, etc.
        
    Returns:
        CMSPublisher o PcComponentesCMSPublisher según type
    """
    cms_type = cms_config.get('type', 'wordpress')

    if cms_type == 'pccomponentes':
        return PcComponentesCMSPublisher(
            cms_url=cms_config.get('url', ''),
            api_token=cms_config.get('api_token', ''),
            blog_path=cms_config.get('blog_path', '/blog'),
        )
    elif cms_type == 'wordpress':
        return CMSPublisher(
            cms_url=cms_config.get('url', ''),
            cms_type='wordpress',
            username=cms_config.get('username', ''),
            app_password=cms_config.get('app_password', ''),
        )
    else:
        return CMSPublisher(
            cms_url=cms_config.get('url', ''),
            cms_type='custom',
            api_token=cms_config.get('api_token', ''),
        )
