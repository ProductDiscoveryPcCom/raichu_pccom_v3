# -*- coding: utf-8 -*-
"""
N8N Integration Module - PcComponentes Content Generator
Versión 1.2.1 - 2026-02-11

Módulo para obtener datos de producto de PcComponentes.

Métodos de obtención (por prioridad):
1. JSON manual (subir/pegar) — siempre funciona, más completo
2. Webhook n8n (opcional) — requiere acceso de red al servidor n8n

Seguridad:
- No hay tokens, URLs internas ni credenciales en el código
- Todo se lee desde st.secrets (sección [n8n])
- SSL siempre verificado (no se permite deshabilitar)

Configuración en Streamlit Secrets:
    [n8n]
    webhook_url = "https://tu-servidor-n8n.com/webhook/extract-product-data"

Autor: PcComponentes - Product Discovery & Content
"""

import requests
import re
import json
import logging
from typing import Dict, Optional, Any, Tuple, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

__version__ = "1.2.1"


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Patrones para extraer legacy_id de URLs de PcComponentes
URL_PATTERNS = [
    r'/(\d{6,10})(?:\?|$|/)',
    r'-(\d{6,10})(?:\?|$)',
    r'(\d{7,10})$',
]

# Timeout para requests HTTP
DEFAULT_TIMEOUT = 30


# ============================================================================
# DATACLASSES
# ============================================================================

@dataclass
class ProductData:
    """Datos de un producto de PcComponentes obtenidos via webhook."""
    legacy_id: str
    product_id: str = ""
    name: str = ""
    brand: str = ""
    price: float = 0.0
    price_formatted: str = ""
    description: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    images: List[str] = field(default_factory=list)
    url: str = ""
    available: bool = True
    category: str = ""

    def to_dict(self) -> Dict:
        """Convierte a diccionario."""
        return {
            'legacy_id': self.legacy_id,
            'product_id': self.product_id,
            'name': self.name,
            'brand': self.brand,
            'price': self.price,
            'price_formatted': self.price_formatted,
            'description': self.description,
            'attributes': self.attributes or {},
            'images': self.images or [],
            'url': self.url,
            'available': self.available,
            'category': self.category,
        }


# ============================================================================
# EXTRACCIÓN DE ID
# ============================================================================

def extract_legacy_id_from_url(url: str) -> Optional[str]:
    """
    Extrae el legacy_id de una URL de PcComponentes.

    Args:
        url: URL del producto

    Returns:
        legacy_id o None si no se encuentra
    """
    if not url:
        return None

    for pattern in URL_PATTERNS:
        match = re.search(pattern, url)
        if match:
            legacy_id = match.group(1)
            logger.info(f"legacy_id extraído de URL: {legacy_id}")
            return legacy_id

    return None


def extract_legacy_id_from_slug(slug: str) -> Optional[str]:
    """
    Extrae el legacy_id del slug del producto.

    Args:
        slug: Slug del producto (última parte de la URL)

    Returns:
        legacy_id o None
    """
    if not slug:
        return None

    match = re.search(r'(\d{6,10})', slug)
    if match:
        return match.group(1)

    return None


# ============================================================================
# WEBHOOK N8N
# ============================================================================

def fetch_product_via_n8n_webhook(
    legacy_id: str,
    product_url: str,
    webhook_url: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> Tuple[bool, Optional[ProductData], str]:
    """
    Obtiene datos del producto via webhook de n8n.
    Intenta múltiples formatos de payload.

    Args:
        legacy_id: ID legacy del producto
        product_url: URL completa del producto
        webhook_url: URL del webhook de n8n
        timeout: Timeout en segundos

    Returns:
        Tuple[success, ProductData, error_message]
    """
    if not webhook_url:
        return False, None, "No se ha configurado webhook_url en secrets [n8n]"

    headers = {"Content-Type": "application/json"}

    # Payloads a intentar en orden de prioridad
    payloads_to_try = [
        {"legacy_id": legacy_id} if legacy_id else None,
        {"chatInput": product_url, "sessionId": "streamlit"} if product_url else None,
        {"product_url": product_url} if product_url else None,
        {"url": product_url} if product_url else None,
    ]
    payloads_to_try = [p for p in payloads_to_try if p]

    last_error = "No hay datos para enviar"

    for payload in payloads_to_try:
        try:
            logger.info(f"Intentando webhook con payload: {list(payload.keys())}")

            response = requests.post(
                webhook_url,
                json=payload,
                headers=headers,
                timeout=timeout,
                verify=True,
            )

            logger.info(f"Respuesta HTTP {response.status_code}")

            if response.status_code == 200:
                try:
                    data = response.json()

                    if isinstance(data, list) and len(data) > 0:
                        data = data[0]

                    if data.get('error') is True:
                        last_error = data.get('message', 'Error en el webhook')
                        continue

                    product = _parse_n8n_response(data, legacy_id, product_url)
                    if product:
                        return True, product, ""
                    else:
                        last_error = "Respuesta vacía o inválida del webhook"
                        continue

                except json.JSONDecodeError:
                    last_error = f"Respuesta no es JSON válido: {response.text[:200]}"
                    continue
            else:
                last_error = f"Error HTTP {response.status_code}: {response.text[:200]}"
                continue

        except requests.exceptions.Timeout:
            last_error = f"Timeout después de {timeout}s"
            continue
        except requests.exceptions.ConnectionError:
            last_error = "No se pudo conectar al servidor n8n. Verifica que la URL sea accesible."
            continue
        except requests.exceptions.RequestException as e:
            last_error = f"Error de conexión: {str(e)}"
            continue
        except Exception as e:
            last_error = f"Error inesperado: {str(e)}"
            continue

    return False, None, last_error


def _parse_n8n_response(data: Dict, legacy_id: str, product_url: str) -> Optional[ProductData]:
    """Parsea la respuesta del webhook de n8n."""
    if not data:
        return None

    has_valid_data = any([
        data.get('title'),
        data.get('name'),
        data.get('brand'),
        data.get('brand_name'),
        data.get('price'),
    ])

    if not has_valid_data:
        return None

    # Extraer atributos (múltiples formatos soportados)
    attributes = {}
    if data.get('attributes_dict'):
        attributes = data['attributes_dict']
    elif data.get('attributes'):
        if isinstance(data['attributes'], dict):
            attributes = data['attributes']
        elif isinstance(data['attributes'], list):
            for attr in data['attributes']:
                if isinstance(attr, dict) and 'label' in attr and 'value' in attr:
                    attributes[attr['label']] = attr['value']
    elif data.get('specifications'):
        for spec in data.get('specifications', []):
            if isinstance(spec, dict) and 'label' in spec and 'value' in spec:
                attributes[spec['label']] = spec['value']

    # Parsear precio
    price = data.get('price', 0)
    if isinstance(price, str):
        try:
            price = float(price.replace('€', '').replace(',', '.').strip())
        except (ValueError, AttributeError):
            price = 0.0

    price_formatted = data.get('price_formatted', '')
    if not price_formatted and price:
        price_formatted = f"{price:.2f}€"

    return ProductData(
        legacy_id=data.get('legacy_id', legacy_id) or legacy_id or '',
        product_id=data.get('product_id', ''),
        name=data.get('title', data.get('name', data.get('simplified_name', ''))),
        brand=data.get('brand_name', data.get('brand', '')),
        price=float(price) if price else 0.0,
        price_formatted=price_formatted,
        description=data.get('description', ''),
        attributes=attributes,
        images=data.get('images', []),
        url=data.get('url', product_url) or product_url,
        available=data.get('available', data.get('hasValidData', True)),
        category=data.get('category', data.get('family_name', '')),
    )


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def get_product_data(
    url_or_id: str,
    n8n_webhook_url: Optional[str] = None,
) -> Tuple[bool, Optional[ProductData], str]:
    """
    Obtiene datos del producto via webhook n8n.

    Args:
        url_or_id: URL del producto o legacy_id directo
        n8n_webhook_url: URL del webhook de n8n

    Returns:
        Tuple[success, ProductData, error_message]
    """
    product_url = ""
    legacy_id = ""

    if url_or_id.startswith('http'):
        product_url = url_or_id
        legacy_id = extract_legacy_id_from_url(url_or_id)
        if not legacy_id:
            slug = url_or_id.split('/')[-1].split('?')[0]
            legacy_id = extract_legacy_id_from_slug(slug)
    else:
        legacy_id = url_or_id

    if n8n_webhook_url:
        success, product, error = fetch_product_via_n8n_webhook(
            legacy_id=legacy_id,
            product_url=product_url,
            webhook_url=n8n_webhook_url,
        )
        if success:
            return success, product, error
        logger.warning(f"Webhook n8n falló: {error}")

    if not n8n_webhook_url:
        return False, None, "Configuración requerida: webhook_url en secrets [n8n]"

    return False, None, "No se pudo obtener datos del producto"


# ============================================================================
# FUNCIÓN PARA STREAMLIT
# ============================================================================

def fetch_product_for_streamlit(
    url: str,
    secrets: Optional[Dict] = None,
    manual_id: Optional[str] = None
) -> Tuple[bool, Dict[str, Any], str]:
    """
    Función wrapper para uso en Streamlit.

    Lee la URL del webhook desde st.secrets de forma segura.

    Args:
        url: URL del producto
        secrets: st.secrets o dict con configuración
        manual_id: ID del producto introducido manualmente (opcional)

    Returns:
        Tuple[success, product_dict, error_message]
    """
    webhook_url = None

    if secrets:
        webhook_url = (
            secrets.get('n8n', {}).get('webhook_url') or
            secrets.get('n8n', {}).get('N8N_WEBHOOK_URL') or
            secrets.get('N8N_WEBHOOK_URL') or
            secrets.get('n8n_webhook_url')
        )

    if not webhook_url:
        return False, {}, (
            "Webhook n8n no configurado. "
            "Usa el método JSON manual (pegar/subir JSON del workflow n8n)."
        )

    url_or_id = manual_id if manual_id else url

    success, product, error = get_product_data(
        url_or_id=url_or_id,
        n8n_webhook_url=webhook_url,
    )

    if success and product:
        product_dict = product.to_dict()
        if url and not product_dict.get('url'):
            product_dict['url'] = url
        return True, product_dict, ""
    else:
        return False, {}, error


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'ProductData',
    'extract_legacy_id_from_url',
    'extract_legacy_id_from_slug',
    'fetch_product_via_n8n_webhook',
    'get_product_data',
    'fetch_product_for_streamlit',
]
