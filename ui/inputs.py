# -*- coding: utf-8 -*-
"""
UI Inputs - PcComponentes Content Generator
Versión 4.5.3

Componentes de entrada para la interfaz Streamlit.
Incluye: validación, anchor text, preguntas guía, producto alternativo,
fecha GSC, análisis de canibalización, campo HTML para reescritura,
integración con n8n para obtener datos de producto, CARGA DE JSON DE PRODUCTOS.

CAMBIOS v4.5.3:
- Añadida opción de PEGAR JSON además de subir archivo
- Tabs en widgets de JSON: "Subir archivo" / "Pegar JSON"
- Aplicado en: producto principal, enlaces PDP, producto alternativo

CAMBIOS v4.5.2:
- Añadida descripción del arquetipo bajo el selector
- Añadido soporte JSON en producto alternativo (igual que en PDPs)

CAMBIOS v4.5.1:
- Añadido soporte para carga de JSON de productos (workflow n8n)
- Widget JSON en producto principal
- Widget JSON en cada enlace PDP
- Mantiene compatibilidad con versiones anteriores

Autor: PcComponentes - Product Discovery & Content
"""

import re
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from urllib.parse import urlparse
from datetime import datetime
import json

import streamlit as st

# Importar integración con n8n (opcional)
try:
    from core.n8n_integration import fetch_product_for_streamlit
    _n8n_available = True
except ImportError:
    try:
        from n8n_integration import fetch_product_for_streamlit
        _n8n_available = True
    except ImportError:
        _n8n_available = False
        fetch_product_for_streamlit = None

# Importar utilidades de JSON de productos
try:
    from utils.product_json_utils import (
        parse_product_json,
        validate_product_json,
        format_product_for_prompt,
        create_product_summary,
    )
    _product_json_available = True
except ImportError:
    _product_json_available = False

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTES
# ============================================================================

__version__ = "4.5.3"

DEFAULT_CONTENT_LENGTH = 1500
MIN_CONTENT_LENGTH = 500
MAX_CONTENT_LENGTH = 5000
MAX_COMPETITORS = 5
MAX_LINKS_PER_TYPE = 10
MAX_ANCHOR_LENGTH = 100
MIN_KEYWORD_LENGTH = 2
MAX_KEYWORD_LENGTH = 100
MAX_URL_LENGTH = 2000
GSC_DATA_WARNING_DAYS = 7

PCCOMPONENTES_DOMAINS = ['www.pccomponentes.com', 'pccomponentes.com']

URL_PATTERN = re.compile(
    r'^https?://'
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
    r'localhost|'
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
    r'(?::\d+)?'
    r'(?:/?|[/?]\S+)$',
    re.IGNORECASE
)

ERROR_MESSAGES = {
    'keyword_empty': 'La keyword es obligatoria',
    'keyword_too_short': f'La keyword debe tener al menos {MIN_KEYWORD_LENGTH} caracteres',
    'keyword_too_long': f'La keyword no puede exceder {MAX_KEYWORD_LENGTH} caracteres',
    'url_invalid': 'La URL no tiene un formato válido',
    'url_not_pccomponentes': 'La URL debe ser de PcComponentes',
    'length_out_of_range': f'La longitud debe estar entre {MIN_CONTENT_LENGTH} y {MAX_CONTENT_LENGTH}',
    'anchor_too_long': f'El anchor text no puede exceder {MAX_ANCHOR_LENGTH} caracteres',
    'html_empty': 'El contenido HTML es obligatorio para reescritura',
}

# ============================================================================
# IMPORTS CON FALLBACKS ROBUSTOS
# ============================================================================

try:
    from config.settings import (
        DEFAULT_CONTENT_LENGTH as _DCL,
        MIN_CONTENT_LENGTH as _MCL,
        MAX_CONTENT_LENGTH as _MXCL,
        MAX_COMPETITORS as _MC,
        PCCOMPONENTES_DOMAINS as _PD,
    )
    DEFAULT_CONTENT_LENGTH = _DCL
    MIN_CONTENT_LENGTH = _MCL
    MAX_CONTENT_LENGTH = _MXCL
    MAX_COMPETITORS = _MC
    PCCOMPONENTES_DOMAINS = _PD
except ImportError:
    pass

# Arquetipos - Fallback completo con 34 arquetipos
_ARQUETIPOS_FALLBACK = {f"ARQ-{i}": {"code": f"ARQ-{i}", "name": f"Arquetipo {i}", "guiding_questions": []} for i in range(1, 35)}

try:
    from config.arquetipos import (
        ARQUETIPOS,
        get_arquetipo,
        get_arquetipo_names,
        get_guiding_questions,
        get_default_length,
        get_length_range,
    )
except ImportError:
    ARQUETIPOS = _ARQUETIPOS_FALLBACK
    def get_arquetipo(code): return ARQUETIPOS.get(code)
    def get_arquetipo_names(): return {k: v['name'] for k, v in ARQUETIPOS.items()}
    def get_guiding_questions(code, include_universal=True): return ARQUETIPOS.get(code, {}).get('guiding_questions', [])
    def get_default_length(code): return ARQUETIPOS.get(code, {}).get('default_length', DEFAULT_CONTENT_LENGTH)
    def get_length_range(code): 
        arq = ARQUETIPOS.get(code, {})
        return (arq.get('min_length', MIN_CONTENT_LENGTH), arq.get('max_length', MAX_CONTENT_LENGTH))

# GSC Utils - para verificación de canibalización (CSV fallback)
try:
    from utils.gsc_utils import (
        get_gsc_data_date,
        is_gsc_data_stale,
        check_cannibalization,
        get_cannibalization_summary,
        load_gsc_keywords_csv,
        search_existing_content,
        get_content_coverage_summary,
    )
    _gsc_available = True
except ImportError:
    _gsc_available = False
    def get_gsc_data_date(): return None
    def is_gsc_data_stale(days=7): return True
    def check_cannibalization(kw, **kwargs): return []
    def get_cannibalization_summary(kw): return {'has_risk': False, 'urls': [], 'recommendation': ''}
    def load_gsc_keywords_csv(): return []
    def search_existing_content(kw, **kwargs): return []
    def get_content_coverage_summary(kw): return {'has_coverage': False, 'recommendation': ''}

# GSC API - conexión directa para datos en tiempo real (últimos 7 días)
try:
    from utils.gsc_api import is_gsc_api_configured, quick_keyword_check
    _gsc_api_available = True
except ImportError:
    _gsc_api_available = False
    def is_gsc_api_configured(): return False
    def quick_keyword_check(kw, **kw2): return {'has_data': False, 'urls': []}


# ============================================================================
# CLASES DE DATOS
# ============================================================================

class InputValidationError(Exception):
    """Error de validación de input."""
    pass

class KeywordValidationError(InputValidationError):
    """Error de validación de keyword."""
    pass

class URLValidationError(InputValidationError):
    """Error de validación de URL."""
    pass

class LengthValidationError(InputValidationError):
    """Error de validación de longitud."""
    pass

class LinksValidationError(InputValidationError):
    """Error de validación de enlaces."""
    pass

class ArquetipoValidationError(InputValidationError):
    """Error de validación de arquetipo."""
    pass


class InputMode(Enum):
    """Modos de generación de contenido."""
    NEW = "new"
    REWRITE = "rewrite"


class LinkType(Enum):
    """Tipos de enlaces."""
    INTERNAL = "internal"
    PDP = "pdp"
    EXTERNAL = "external"


@dataclass
class LinkWithAnchor:
    """Enlace con anchor text personalizado y datos de producto opcionales."""
    url: str
    anchor: str = ""
    link_type: str = "internal"
    product_data: Optional[Dict[str, Any]] = None  # NUEVO: Datos del JSON del producto


class ProductRole(Enum):
    """Roles de producto en el contenido."""
    PRINCIPAL = "principal"
    ALTERNATIVO = "alternativo"
    ENLAZADO = "enlazado"


@dataclass
class ProductEntry:
    """Producto con URL, JSON y rol."""
    url: str = ""
    name: str = ""
    json_data: Optional[Dict[str, Any]] = None
    role: str = "principal"  # principal / alternativo / enlazado


@dataclass
class ValidationResult:
    """Resultado de validación."""
    is_valid: bool
    value: Any
    error: Optional[str] = None


@dataclass
class FormData:
    """Datos del formulario completo."""
    keyword: str
    pdp_url: Optional[str] = None
    pdp_data: Optional[Dict[str, Any]] = None  # Datos del producto obtenidos via n8n
    pdp_json_data: Optional[Dict[str, Any]] = None  # Datos del JSON del producto principal
    target_length: int = DEFAULT_CONTENT_LENGTH
    arquetipo: str = 'ARQ-1'
    mode: str = 'new'
    competitor_urls: Optional[List[str]] = None
    internal_links: Optional[List[LinkWithAnchor]] = None
    pdp_links: Optional[List[LinkWithAnchor]] = None  # Incluye product_data en cada enlace
    additional_instructions: Optional[str] = None
    guiding_answers: Optional[Dict[str, str]] = None
    alternative_product_url: Optional[str] = None
    alternative_product_name: Optional[str] = None
    alternative_product_json_data: Optional[Dict[str, Any]] = None  # NUEVO v4.5.2: JSON del producto alternativo
    visual_elements: Optional[List[str]] = None  # Elementos visuales seleccionados (IDs)
    visual_config: Optional[Dict[str, Any]] = None  # Config completa: selected, variants, components_css
    # NUEVO v5.0: Bloque unificado de productos
    products: Optional[List[ProductEntry]] = None
    # NUEVO v5.0: Configuración de encabezados HTML
    headings_config: Optional[Dict[str, int]] = None  # {'h2': N, 'h3': N, 'h4': N}
    # NUEVO v5.1: Keywords secundarias
    secondary_keywords: Optional[List[str]] = None


# ============================================================================
# FUNCIONES DE VALIDACIÓN
# ============================================================================

def validate_keyword(keyword: str) -> ValidationResult:
    """Valida la keyword principal."""
    if not keyword or not keyword.strip():
        return ValidationResult(False, '', ERROR_MESSAGES['keyword_empty'])
    keyword = keyword.strip()
    if len(keyword) < MIN_KEYWORD_LENGTH:
        return ValidationResult(False, keyword, ERROR_MESSAGES['keyword_too_short'])
    if len(keyword) > MAX_KEYWORD_LENGTH:
        return ValidationResult(False, keyword, ERROR_MESSAGES['keyword_too_long'])
    return ValidationResult(True, keyword)


def validate_url(url: str, require_pccomponentes: bool = False) -> ValidationResult:
    """Valida una URL."""
    if not url or not url.strip():
        return ValidationResult(True, '', None)
    url = url.strip()
    if len(url) > MAX_URL_LENGTH:
        return ValidationResult(False, url, 'URL demasiado larga')
    if not URL_PATTERN.match(url):
        return ValidationResult(False, url, ERROR_MESSAGES['url_invalid'])
    if require_pccomponentes:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if not any(pcc in domain for pcc in PCCOMPONENTES_DOMAINS):
                return ValidationResult(False, url, ERROR_MESSAGES['url_not_pccomponentes'])
        except Exception:
            return ValidationResult(False, url, ERROR_MESSAGES['url_invalid'])
    return ValidationResult(True, url)


def validate_length(length: int) -> ValidationResult:
    """Valida la longitud del contenido."""
    if length < MIN_CONTENT_LENGTH or length > MAX_CONTENT_LENGTH:
        return ValidationResult(False, length, ERROR_MESSAGES['length_out_of_range'])
    return ValidationResult(True, length)


def validate_arquetipo(arquetipo: str) -> ValidationResult:
    """Valida el código de arquetipo."""
    if arquetipo not in ARQUETIPOS:
        return ValidationResult(False, arquetipo, 'Arquetipo inválido')
    return ValidationResult(True, arquetipo)


def validate_html_content(html: str) -> ValidationResult:
    """Valida contenido HTML para reescritura."""
    if not html or not html.strip():
        return ValidationResult(False, '', ERROR_MESSAGES['html_empty'])
    html = html.strip()
    if len(html) < 100:
        return ValidationResult(False, html, 'El contenido HTML es demasiado corto (mínimo 100 caracteres)')
    return ValidationResult(True, html)


def validate_links_list(links_text: str, link_type: str = 'internal', max_links: int = MAX_LINKS_PER_TYPE) -> ValidationResult:
    """Valida una lista de enlaces."""
    if not links_text or not links_text.strip():
        return ValidationResult(True, [])
    lines = [line.strip() for line in links_text.strip().split('\n') if line.strip()]
    valid_links = []
    for line in lines[:max_links]:
        if URL_PATTERN.match(line):
            valid_links.append(line)
    return ValidationResult(True, valid_links)


def validate_competitor_urls(urls_text: str) -> ValidationResult:
    """Valida URLs de competidores (filtra PcComponentes)."""
    result = validate_links_list(urls_text, 'competitor', MAX_COMPETITORS)
    if result.is_valid and result.value:
        filtered = [u for u in result.value if not any(pcc in urlparse(u).netloc.lower() for pcc in PCCOMPONENTES_DOMAINS)]
        return ValidationResult(True, filtered)
    return result


# ============================================================================
# FUNCIONES DE ESTADO
# ============================================================================

def get_form_value(key: str, default: Any = None) -> Any:
    """Obtiene valor del formulario desde session_state."""
    form_data = st.session_state.get('form_data', {})
    return form_data.get(key, default)


def save_form_data(data: Dict[str, Any]) -> None:
    """Guarda datos en session_state."""
    if 'form_data' not in st.session_state:
        st.session_state.form_data = {}
    st.session_state.form_data.update(data)


def clear_form_data() -> None:
    """Limpia datos del formulario."""
    st.session_state.form_data = {}


# ============================================================================
# COMPONENTES UI: BÁSICOS
# ============================================================================

def render_keyword_input(
    key: str = "keyword_input",
    default_value: str = "",
    label: str = "🔑 Keyword Principal",
    required: bool = True,
    show_cannibalization: bool = True
) -> Tuple[str, Optional[str]]:
    """Renderiza input de keyword con validación y check de canibalización."""
    saved_value = get_form_value('keyword', default_value)
    keyword = st.text_input(
        label=label,
        value=saved_value,
        key=key,
        placeholder="Ej: mejores monitores gaming 2024"
    )
    
    if keyword:
        result = validate_keyword(keyword)
        if not result.is_valid:
            st.error(f"❌ {result.error}")
            return keyword, result.error
        save_form_data({'keyword': result.value})
        
        if show_cannibalization:
            _render_cannibalization_check(result.value)
        
        return result.value, None
    elif required:
        return "", "La keyword es obligatoria"
    return "", None


def render_url_input(
    key: str = "url_input",
    default_value: str = "",
    label: str = "🔗 URL del PDP",
    required: bool = False,
    require_pccomponentes: bool = True
) -> Tuple[str, Optional[str]]:
    """Renderiza input de URL."""
    saved_value = get_form_value('pdp_url', default_value)
    url = st.text_input(
        label=label,
        value=saved_value,
        key=key,
        placeholder="https://www.pccomponentes.com/..."
    )
    if url:
        result = validate_url(url, require_pccomponentes=require_pccomponentes)
        if not result.is_valid:
            st.error(f"❌ {result.error}")
            return url, result.error
        save_form_data({'pdp_url': result.value})
        return result.value, None
    elif required:
        return "", "La URL es obligatoria"
    return "", None


def render_product_url_with_fetch(
    key: str = "product_url",
    required: bool = False
) -> Tuple[str, Optional[Dict[str, Any]], Optional[str]]:
    """
    Renderiza input de URL de producto con:
    - JSON del producto (método principal, siempre funciona)
    - Botón para obtener datos via n8n (opcional, si el webhook es accesible)
    
    NOTA: Esta función mantiene compatibilidad retornando 3 valores.
    El JSON del producto se guarda en session_state y se puede recuperar
    usando la función auxiliar get_product_json_data().
    
    Args:
        key: Clave única para el widget
        required: Si la URL es obligatoria
        
    Returns:
        Tuple[url, product_data, error] - Mantiene compatibilidad con versión anterior
    """
    # Inicializar estado
    state_key_n8n = f"pdp_data_{key}"
    state_key_json = f"pdp_json_{key}"
    
    if state_key_n8n not in st.session_state:
        st.session_state[state_key_n8n] = None
    if state_key_json not in st.session_state:
        st.session_state[state_key_json] = None
    
    # URL del producto
    saved_value = get_form_value('pdp_url', '')
    url = st.text_input(
        label="🔗 URL del Producto",
        value=saved_value,
        key=f"{key}_url",
        placeholder="https://www.pccomponentes.com/...",
        help="Pega la URL de un producto de PcComponentes"
    )
    
    # ========================================================================
    # MÉTODO PRINCIPAL: JSON del producto
    # ========================================================================
    st.markdown("##### 📦 Datos del Producto (JSON)")
    st.caption(
        "Genera el JSON con el [workflow de n8n](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV) "
        "y pégalo o súbelo aquí."
    )
    
    json_tab1, json_tab2 = st.tabs(["📋 Pegar JSON", "📁 Subir archivo"])
    
    json_content = None
    
    with json_tab1:
        pasted_json = st.text_area(
            "Pegar JSON aquí",
            height=150,
            key=f"{key}_json_paste",
            placeholder='{"id": "...", "name": "...", ...}',
            help="Pega el JSON directamente desde el workflow de n8n"
        )
        
        if pasted_json and pasted_json.strip():
            json_content = pasted_json.strip()
    
    with json_tab2:
        uploaded_json = st.file_uploader(
            "Subir JSON del producto",
            type=['json'],
            key=f"{key}_json_upload",
            help="JSON generado por el workflow de n8n"
        )
        
        if uploaded_json is not None:
            try:
                json_content = uploaded_json.read().decode('utf-8')
            except Exception as e:
                st.error(f"❌ Error al leer archivo: {str(e)}")
    
    # Procesar JSON
    if json_content:
        try:
            if _product_json_available:
                is_valid, error_msg = validate_product_json(json_content)
                
                if is_valid:
                    product_data = parse_product_json(json_content)
                    
                    if product_data:
                        st.session_state[state_key_json] = {
                            'product_id': product_data.product_id,
                            'legacy_id': product_data.legacy_id,
                            'title': product_data.title,
                            'description': product_data.description,
                            'brand_name': product_data.brand_name,
                            'family_name': product_data.family_name,
                            'attributes': product_data.attributes,
                            'images': product_data.images,
                            'total_comments': product_data.total_comments,
                            'advantages': product_data.advantages,
                            'disadvantages': product_data.disadvantages,
                            'comments': product_data.comments,
                        }
                        
                        st.success(f"✅ JSON cargado: {product_data.title}")
                        
                        with st.expander("👁️ Preview de datos", expanded=False):
                            summary = create_product_summary(product_data)
                            
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"**Producto:** {summary['title']}")
                                st.markdown(f"**Marca:** {summary['brand']}")
                                st.markdown(f"**Familia:** {summary['family']}")
                            with col_b:
                                st.markdown(f"**ID:** {summary['product_id']}")
                                st.markdown(f"**Reviews:** {summary.get('total_comments', 0)}")
                                st.markdown(f"**Imágenes:** {summary.get('images_count', 0)}")
                            
                            if summary.get('key_attributes'):
                                st.markdown("**Atributos clave:**")
                                for attr, value in summary['key_attributes'].items():
                                    st.caption(f"• {attr}: {value}")
                    else:
                        st.error("❌ Error al parsear el JSON del producto")
                        st.session_state[state_key_json] = None
                else:
                    st.error(f"❌ JSON inválido: {error_msg}")
                    st.session_state[state_key_json] = None
            else:
                parsed_json = json.loads(json_content)
                st.session_state[state_key_json] = parsed_json
                st.success("✅ JSON cargado (sin validación)")
                
        except json.JSONDecodeError as e:
            st.error(f"❌ Error al leer JSON: {str(e)}")
            st.session_state[state_key_json] = None
        except Exception as e:
            st.error(f"❌ Error inesperado: {str(e)}")
            st.session_state[state_key_json] = None
    
    # ========================================================================
    # MÉTODO SECUNDARIO: Webhook n8n (colapsado, solo si está configurado)
    # ========================================================================
    if _n8n_available:
        with st.expander("🔌 Obtener datos via webhook n8n (alternativo)", expanded=False):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                manual_id = st.text_input(
                    label="🔢 ID del producto (opcional)",
                    value="",
                    key=f"{key}_manual_id",
                    placeholder="Ej: 6917499",
                    help="Si la extracción automática del ID falla, introdúcelo manualmente."
                )
            
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                fetch_disabled = not url and not manual_id
                
                if st.button("📥 Obtener datos", key=f"{key}_fetch", disabled=fetch_disabled):
                    with st.spinner("Obteniendo datos del producto..."):
                        try:
                            secrets_dict = {}
                            if hasattr(st, 'secrets'):
                                try:
                                    secrets_dict = dict(st.secrets)
                                except Exception:
                                    secrets_dict = {}
                            
                            success, product_data_resp, error = fetch_product_for_streamlit(
                                url=url or "",
                                secrets=secrets_dict,
                                manual_id=manual_id.strip() if manual_id else None
                            )
                            
                            if success:
                                st.session_state[state_key_n8n] = product_data_resp
                                st.success(f"✅ Datos obtenidos: {product_data_resp.get('name', 'Producto')}")
                            else:
                                st.error(f"❌ {error}")
                                st.session_state[state_key_n8n] = None
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
                            st.session_state[state_key_n8n] = None
    
    # ========================================================================
    # Validar URL
    # ========================================================================
    error = None
    if url:
        result = validate_url(url, require_pccomponentes=True)
        if not result.is_valid:
            st.error(f"❌ {result.error}")
            error = result.error
        else:
            save_form_data({'pdp_url': result.value})
            url = result.value
    elif required:
        error = "La URL es obligatoria"
    
    # Mostrar datos obtenidos via n8n (si existen y no hay JSON)
    product_data_n8n = st.session_state.get(state_key_n8n)
    if product_data_n8n and not st.session_state.get(state_key_json):
        with st.expander("📦 Datos del producto (vía webhook)", expanded=False):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Nombre:** {product_data_n8n.get('name', 'N/A')}")
                st.markdown(f"**Marca:** {product_data_n8n.get('brand', 'N/A')}")
            with col_b:
                price = product_data_n8n.get('price_formatted') or product_data_n8n.get('price', 'N/A')
                st.markdown(f"**Precio:** {price}")
                st.markdown(f"**ID:** {product_data_n8n.get('legacy_id', 'N/A')}")
            
            attrs = product_data_n8n.get('attributes', {})
            if attrs:
                st.markdown("**Características:**")
                for attr_name, attr_value in list(attrs.items())[:5]:
                    st.markdown(f"- {attr_name}: {attr_value}")
    
    return url or "", product_data_n8n, error


def get_product_json_data(key: str = "product_url") -> Optional[Dict[str, Any]]:
    """
    Recupera los datos del JSON de producto cargado.
    
    Esta función auxiliar permite acceder al JSON sin romper la compatibilidad
    de la función render_product_url_with_fetch().
    
    Args:
        key: Misma key usada en render_product_url_with_fetch()
        
    Returns:
        Dict con datos del JSON o None si no hay
    """
    state_key_json = f"pdp_json_{key}"
    return st.session_state.get(state_key_json)


def render_length_slider(
    key: str = "length_slider",
    default_value: int = None,
    arquetipo_code: str = None
) -> int:
    """Renderiza slider de longitud adaptado al arquetipo."""
    min_len, max_len = MIN_CONTENT_LENGTH, MAX_CONTENT_LENGTH
    default_len = DEFAULT_CONTENT_LENGTH
    
    if arquetipo_code:
        try:
            min_len, max_len = get_length_range(arquetipo_code)
            default_len = get_default_length(arquetipo_code)
        except Exception:
            pass
    
    if default_value is not None:
        default_len = default_value
    
    saved_value = get_form_value('target_length', default_len)
    saved_value = max(min_len, min(saved_value, max_len))
    
    length = st.slider(
        label="📏 Longitud objetivo (palabras)",
        min_value=min_len,
        max_value=max_len,
        value=saved_value,
        step=100,
        key=key
    )
    save_form_data({'target_length': length})
    return length


def render_arquetipo_selector(key: str = "arquetipo_selector") -> str:
    """Renderiza selector de arquetipo con descripción del tipo de contenido."""
    saved_value = get_form_value('arquetipo', 'ARQ-1')
    names = get_arquetipo_names()
    options = list(names.keys())
    
    try:
        default_index = options.index(saved_value)
    except ValueError:
        default_index = 0
    
    arquetipo = st.selectbox(
        label="📋 Tipo de Contenido (Arquetipo)",
        options=options,
        format_func=lambda x: f"{x}: {names.get(x, x)}",
        index=default_index,
        key=key
    )
    
    # Mostrar descripción del arquetipo seleccionado
    if arquetipo:
        arq_data = get_arquetipo(arquetipo)
        if arq_data:
            description = arq_data.get('description', '')
            if description:
                st.caption(f"ℹ️ {description}")
    
    save_form_data({'arquetipo': arquetipo})
    return arquetipo


def render_mode_selector(key: str = "mode_selector") -> str:
    """Renderiza selector de modo (nuevo/reescritura)."""
    saved_mode = get_form_value('mode', 'new')
    mode = st.radio(
        "🔄 Modo de Generación",
        options=['new', 'rewrite'],
        format_func=lambda x: '✨ Nuevo Contenido' if x == 'new' else '📝 Reescritura',
        index=0 if saved_mode == 'new' else 1,
        key=key,
        horizontal=True
    )
    save_form_data({'mode': mode})
    return mode


# ============================================================================
# COMPONENTES UI: AVANZADOS
# ============================================================================

def render_html_input(key: str = "html_input") -> Tuple[str, Optional[str]]:
    """Renderiza área de texto para pegar HTML de artículo a reescribir."""
    st.markdown("##### 📄 Contenido HTML a Reescribir")
    st.caption("Pega el código HTML del artículo que deseas reescribir")
    
    saved_value = get_form_value('html_content', '')
    html_content = st.text_area(
        label="Código HTML",
        value=saved_value,
        height=200,
        key=key,
        placeholder="<article>\n  <h1>Título del artículo...</h1>\n  <p>Contenido...</p>\n</article>",
        label_visibility="collapsed"
    )
    
    if html_content:
        result = validate_html_content(html_content)
        if not result.is_valid:
            st.error(f"❌ {result.error}")
            return html_content, result.error
        save_form_data({'html_content': result.value})
        
        # Mostrar preview
        word_count = len(html_content.split())
        char_count = len(html_content)
        st.caption(f"📊 {word_count} palabras · {char_count} caracteres")
        
        return result.value, None
    else:
        return "", "El contenido HTML es obligatorio para reescritura"


def render_links_with_anchors(
    key_prefix: str = "links",
    label: str = "Enlaces",
    link_type: str = "internal",
    max_links: int = 10,
    allow_json: bool = False
) -> List[LinkWithAnchor]:
    """
    Renderiza UI dinámica para enlaces con anchor text editable.
    
    NUEVO: Si allow_json=True, permite cargar JSON de producto para cada enlace.
    
    Args:
        key_prefix: Prefijo para las keys de los widgets
        label: Etiqueta del bloque
        link_type: Tipo de enlace (internal/pdp/external)
        max_links: Número máximo de enlaces
        allow_json: Si True, permite cargar JSON para cada enlace
        
    Returns:
        Lista de LinkWithAnchor (ahora incluye product_data si hay JSON)
    """
    count_key = f"{key_prefix}_count"
    delete_key = f"{key_prefix}_delete_idx"
    
    # Inicializar estado
    if count_key not in st.session_state:
        st.session_state[count_key] = 1
    if delete_key not in st.session_state:
        st.session_state[delete_key] = None
    
    current_count = st.session_state[count_key]
    
    # Procesar eliminación pendiente
    if st.session_state[delete_key] is not None:
        idx_to_delete = st.session_state[delete_key]
        if 0 <= idx_to_delete < current_count:
            # Shift valores hacia arriba
            for j in range(idx_to_delete, current_count - 1):
                next_url = st.session_state.get(f"{key_prefix}_url_{j+1}", "")
                next_anchor = st.session_state.get(f"{key_prefix}_anchor_{j+1}", "")
                next_json = st.session_state.get(f"{key_prefix}_json_{j+1}")
                
                st.session_state[f"{key_prefix}_url_{j}"] = next_url
                st.session_state[f"{key_prefix}_anchor_{j}"] = next_anchor
                if next_json:
                    st.session_state[f"{key_prefix}_json_{j}"] = next_json
            
            # Limpiar última fila
            last_idx = current_count - 1
            if f"{key_prefix}_url_{last_idx}" in st.session_state:
                del st.session_state[f"{key_prefix}_url_{last_idx}"]
            if f"{key_prefix}_anchor_{last_idx}" in st.session_state:
                del st.session_state[f"{key_prefix}_anchor_{last_idx}"]
            if f"{key_prefix}_json_{last_idx}" in st.session_state:
                del st.session_state[f"{key_prefix}_json_{last_idx}"]
            
            # Decrementar contador
            st.session_state[count_key] = max(1, current_count - 1)
        
        st.session_state[delete_key] = None
        st.rerun()
    
    current_count = st.session_state[count_key]
    links = []
    
    st.markdown(f"**{label}** (máx. {max_links})")
    
    # Si permite JSON, mostrar info
    if allow_json:
        st.caption("💡 Puedes cargar el JSON de cada producto desde el [workflow de n8n](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV)")
    
    # Renderizar cada enlace
    for i in range(current_count):
        # Si permite JSON, usar expander para mejor organización
        if allow_json:
            with st.expander(f"🔗 Enlace {i+1}", expanded=(i == 0)):
                link_data = _render_single_pdp_link(key_prefix, i, link_type, current_count)
                if link_data:
                    links.append(link_data)
        else:
            # Versión simple inline (sin JSON)
            link_data = _render_single_simple_link(key_prefix, i, link_type, current_count)
            if link_data:
                links.append(link_data)
    
    # Botón añadir
    if current_count < max_links:
        if st.button(f"➕ Añadir {label.lower()}", key=f"{key_prefix}_add"):
            st.session_state[count_key] = current_count + 1
            st.rerun()
    
    return links


def _render_single_simple_link(
    key_prefix: str, 
    i: int, 
    link_type: str, 
    current_count: int
) -> Optional[LinkWithAnchor]:
    """
    Renderiza un enlace simple (sin JSON) inline.
    
    Returns:
        LinkWithAnchor o None si no hay URL válida
    """
    col1, col2, col3 = st.columns([5, 4, 1])
    
    with col1:
        url = st.text_input(
            label=f"URL {i+1}",
            key=f"{key_prefix}_url_{i}",
            placeholder="https://www.pccomponentes.com/...",
            label_visibility="collapsed"
        )
    
    with col2:
        anchor = st.text_input(
            label=f"Anchor {i+1}",
            key=f"{key_prefix}_anchor_{i}",
            placeholder="Texto del enlace (anchor)",
            label_visibility="collapsed"
        )
    
    with col3:
        if current_count > 1:
            if st.button("🗑️", key=f"{key_prefix}_del_{i}", help="Eliminar"):
                st.session_state[f"{key_prefix}_delete_idx"] = i
                st.rerun()
    
    if url and url.strip():
        validated = validate_url(url.strip())
        if validated.is_valid:
            return LinkWithAnchor(
                url=validated.value,
                anchor=anchor.strip() if anchor else "",
                link_type=link_type,
                product_data=None
            )
    
    return None


def _render_single_pdp_link(
    key_prefix: str, 
    i: int, 
    link_type: str, 
    current_count: int
) -> Optional[LinkWithAnchor]:
    """
    Renderiza un enlace de producto CON opción de cargar JSON.
    
    Returns:
        LinkWithAnchor o None si no hay URL válida
    """
    # URL y anchor
    col1, col2 = st.columns([3, 2])
    
    with col1:
        url = st.text_input(
            label=f"URL del producto {i+1}",
            key=f"{key_prefix}_url_{i}",
            placeholder="https://www.pccomponentes.com/producto",
            help="URL del producto"
        )
    
    with col2:
        anchor = st.text_input(
            label=f"Anchor text {i+1}",
            key=f"{key_prefix}_anchor_{i}",
            placeholder="Texto del enlace",
            help="Texto visible del enlace"
        )
    
    # Widget de JSON con tabs
    json_key = f"{key_prefix}_json_{i}"
    
    with st.expander(f"📦 JSON del producto {i+1} (opcional)", expanded=False):
        json_tab1, json_tab2 = st.tabs(["📁 Subir", "📋 Pegar"])
        
        json_content = None
        
        with json_tab1:
            uploaded_json = st.file_uploader(
                f"Subir JSON",
                type=['json'],
                key=f"{key_prefix}_json_upload_{i}",
                help="JSON con datos del producto"
            )
            
            if uploaded_json is not None:
                try:
                    json_content = uploaded_json.read().decode('utf-8')
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")
        
        with json_tab2:
            pasted_json = st.text_area(
                "Pegar JSON",
                height=100,
                key=f"{key_prefix}_json_paste_{i}",
                placeholder='{"id": "...", ...}'
            )
            
            if pasted_json and pasted_json.strip():
                json_content = pasted_json.strip()
    
    product_json_data = None
    
    if json_content:
        try:
            if _product_json_available:
                is_valid, error_msg = validate_product_json(json_content)
                
                if is_valid:
                    product_data = parse_product_json(json_content)
                    
                    if product_data:
                        product_json_data = {
                            'product_id': product_data.product_id,
                            'legacy_id': product_data.legacy_id,
                            'title': product_data.title,
                            'description': product_data.description,
                            'brand_name': product_data.brand_name,
                            'family_name': product_data.family_name,
                            'attributes': product_data.attributes,
                            'images': product_data.images,
                            'total_comments': product_data.total_comments,
                            'advantages': product_data.advantages,
                            'disadvantages': product_data.disadvantages,
                            'comments': product_data.comments,
                        }
                        
                        st.session_state[json_key] = product_json_data
                        st.success(f"✅ JSON: {product_data.title[:50]}")
                    else:
                        st.error("❌ Error al parsear JSON")
                else:
                    st.error(f"❌ {error_msg}")
            else:
                # Fallback
                parsed_json = json.loads(json_content)
                st.session_state[json_key] = parsed_json
                st.success("✅ JSON cargado")
                product_json_data = parsed_json
                
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
    
    # Recuperar JSON si ya estaba cargado
    if json_key in st.session_state and not product_json_data:
        product_json_data = st.session_state[json_key]
        if product_json_data:
            title = product_json_data.get('title', 'Producto')
            st.caption(f"📦 JSON cargado: {title[:40]}")
    
    # Botón eliminar
    if current_count > 1:
        if st.button("🗑️ Eliminar enlace", key=f"{key_prefix}_del_{i}"):
            st.session_state[f"{key_prefix}_delete_idx"] = i
            st.rerun()
    
    # Retornar LinkWithAnchor si hay URL válida
    if url and url.strip():
        validated = validate_url(url.strip())
        if validated.is_valid:
            return LinkWithAnchor(
                url=validated.value,
                anchor=anchor.strip() if anchor else "",
                link_type=link_type,
                product_data=product_json_data
            )
    
    return None


def render_guiding_questions(arquetipo_code: str, key_prefix: str = "guiding") -> Dict[str, str]:
    """
    Renderiza preguntas guía del arquetipo en un expander.
    
    Muestra primero las preguntas específicas del arquetipo (más relevantes)
    y después las universales en una sección separada.
    """
    # Obtener preguntas separadas
    specific_questions = get_guiding_questions(arquetipo_code, include_universal=False)
    
    try:
        from config.arquetipos import PREGUNTAS_UNIVERSALES
        universal_questions = list(PREGUNTAS_UNIVERSALES)
    except ImportError:
        universal_questions = []
    
    if not specific_questions and not universal_questions:
        return {}
    
    arq = get_arquetipo(arquetipo_code)
    arq_name = arq.get('name', arquetipo_code) if arq else arquetipo_code
    
    with st.expander(f"💡 Briefing: {arq_name}", expanded=False):
        answers = {}
        
        # 1. Preguntas específicas del arquetipo PRIMERO (más relevantes)
        if specific_questions:
            st.markdown(f"**📋 Preguntas específicas — {arq_name}**")
            st.caption("Estas preguntas son las más importantes para este tipo de contenido")
            for i, question in enumerate(specific_questions):
                answer = st.text_area(
                    label=question,
                    key=f"{key_prefix}_spec_{i}",
                    height=80,
                    placeholder="Tu respuesta...",
                    label_visibility="visible"
                )
                if answer and answer.strip():
                    answers[question] = answer.strip()
        
        # 2. Preguntas universales después, separadas visualmente
        if universal_questions:
            st.markdown("---")
            st.markdown("**🌐 Contexto general** _(aplica a todos los tipos de contenido)_")
            for i, question in enumerate(universal_questions):
                answer = st.text_area(
                    label=question,
                    key=f"{key_prefix}_univ_{i}",
                    height=80,
                    placeholder="Tu respuesta...",
                    label_visibility="visible"
                )
                if answer and answer.strip():
                    answers[question] = answer.strip()
        
        return answers


def render_gsc_date_warning() -> None:
    """Muestra aviso si los datos de GSC están desactualizados."""
    if not _gsc_available:
        return
    
    try:
        gsc_date = get_gsc_data_date()
        if gsc_date:
            if is_gsc_data_stale(GSC_DATA_WARNING_DAYS):
                days_old = (datetime.now() - gsc_date).days
                st.warning(
                    f"⚠️ Datos GSC de hace {days_old} días ({gsc_date.strftime('%d/%m/%Y')}). "
                    f"Considera actualizar para mejor análisis.",
                    icon="📅"
                )
            else:
                st.caption(f"📅 Datos GSC: {gsc_date.strftime('%d/%m/%Y')}")
    except Exception:
        pass


def _normalize_keyword(keyword: str) -> str:
    """Normaliza keyword eliminando caracteres invisibles (ZWS, etc.)."""
    import unicodedata
    # Eliminar zero-width chars y normalizar whitespace
    cleaned = ''.join(
        c for c in keyword
        if unicodedata.category(c) not in ('Cf', 'Cc') or c in ('\n', '\t')
    )
    return ' '.join(cleaned.split()).strip()


def _render_cannibalization_check(keyword: str) -> None:
    """
    Renderiza check de canibalización/cobertura para una keyword.
    
    Prioridad:
    1. GSC API en tiempo real (últimos 7 días) — si configurada
    2. CSV local de GSC (fallback) — si disponible
    
    CACHE: Resultado completo cacheado en session_state por keyword 
    normalizada para evitar llamadas API en cada rerun de Streamlit.
    """
    if not keyword:
        return
    
    # Normalizar keyword (eliminar ZWS y otros chars invisibles)
    kw_clean = _normalize_keyword(keyword)
    if not kw_clean:
        return
    
    # ── Cache UI-level: evitar recalcular en cada rerun ──
    cache_key = f"_cannib_check_{kw_clean.lower()}"
    cached = st.session_state.get(cache_key)
    if cached is not None:
        # Renderizar desde cache
        source, data = cached.get("source"), cached.get("data")
        if source == "gsc_api" and data:
            _render_gsc_api_results(kw_clean, data)
        elif source == "csv" and data:
            _render_csv_coverage_results(kw_clean, data)
        # source == "none" → no renderizar nada (no hay datos)
        return
    
    # ── Intento 1: GSC API en tiempo real (últimos 7 días) ──
    if _gsc_api_available and is_gsc_api_configured():
        try:
            check = quick_keyword_check(kw_clean, days_back=7)
            if check.get('has_data') and check.get('urls'):
                st.session_state[cache_key] = {"source": "gsc_api", "data": check}
                _render_gsc_api_results(kw_clean, check)
                return
        except Exception as e:
            logger.debug(f"GSC API quick check falló: {e}")
    
    # ── Intento 2: CSV local (fallback) ──
    if _gsc_available:
        try:
            summary = get_content_coverage_summary(kw_clean)
            if summary.get('has_coverage'):
                st.session_state[cache_key] = {"source": "csv", "data": summary}
                _render_csv_coverage_results(kw_clean, summary)
                return
        except Exception as e:
            logger.debug(f"Error en check canibalización CSV: {e}")
    
    # Cachear resultado vacío para no repetir
    st.session_state[cache_key] = {"source": "none", "data": None}


def _render_gsc_api_results(keyword: str, check: dict) -> None:
    """Renderiza resultados del GSC API (últimos 7 días) con URLs clicables."""
    urls = check['urls']
    total_clicks = check.get('total_clicks', 0)
    total_impressions = check.get('total_impressions', 0)
    period = check.get('period_days', 7)
    n_urls = len(urls)
    
    # Color según gravedad
    if any(u.get('match_score', 0) >= 80 for u in urls):
        bg_color = "#fff3cd"
        border_color = "#ffc107"
        icon = "⚠️"
    else:
        bg_color = "#d1ecf1"
        border_color = "#17a2b8"
        icon = "ℹ️"
    
    html_parts = [
        f'<div style="background-color:{bg_color};padding:12px 14px;border-radius:5px;'
        f'border-left:4px solid {border_color};margin:10px 0;font-size:14px;">',
        f'<strong>{icon} Datos GSC en tiempo real</strong> '
        f'<small style="color:#666;">(últimos {period} días)</small><br>',
        f'<small><b>{n_urls}</b> URLs · '
        f'<b>{total_clicks}</b> clicks · '
        f'<b>{total_impressions}</b> impresiones</small>',
    ]
    
    for u in urls[:5]:
        url = u.get('url', '')
        clicks = u.get('clicks', 0)
        impressions = u.get('impressions', 0)
        position = u.get('position', 0)
        query = u.get('query', '')
        score = u.get('match_score', 0)
        score_label = '🎯' if score >= 80 else '🔹'
        
        html_parts.append(
            f'<div style="margin:6px 0 2px 0;">'
            f'{score_label} <a href="{url}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;word-break:break-all;">{url}</a><br>'
            f'<small style="margin-left:20px;">'
            f'Query: <em>{query}</em> · '
            f'{clicks} clicks · {impressions} imp · '
            f'Pos. {position:.1f}</small>'
            f'</div>'
        )
    
    if n_urls > 5:
        html_parts.append(f'<small>... y {n_urls - 5} URLs más</small>')
    
    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)
    
    # Recomendación
    best = urls[0] if urls else {}
    if best.get('match_score', 0) >= 80 and best.get('clicks', 0) > 20:
        st.info(
            f"💡 Ya tienes contenido posicionando bien para esta keyword "
            f"({best.get('clicks', 0)} clicks en {period} días). "
            f"Considera mejorar ese contenido en lugar de crear uno nuevo."
        )
    elif n_urls > 2:
        st.info(
            f"💡 {n_urls} URLs compiten por esta keyword. "
            f"Evalúa si necesitas consolidar contenido para evitar canibalización."
        )


def _render_csv_coverage_results(keyword: str, summary: dict) -> None:
    """Renderiza resultados de cobertura desde CSV (fallback) con URLs clicables."""
    exact = summary.get('exact_match')
    partial = summary.get('partial_matches', [])[:3]
    total = summary.get('total_urls', 0)
    
    if exact:
        bg_color = "#fff3cd"
        border_color = "#ffc107"
        icon = "⚠️"
    else:
        bg_color = "#d1ecf1"
        border_color = "#17a2b8"
        icon = "ℹ️"
    
    html_parts = [
        f'<div style="background-color:{bg_color};padding:12px 14px;border-radius:5px;'
        f'border-left:4px solid {border_color};margin:10px 0;font-size:14px;">',
        f'<strong>{icon} Contenido existente detectado</strong> '
        f'<small style="color:#666;">(datos CSV)</small><br>',
        f'<small>Se encontraron <b>{total}</b> URLs con contenido relacionado:</small>',
    ]
    
    if exact:
        url = exact.get('url', '')
        clicks = exact.get('clicks', 0)
        impressions = exact.get('impressions', 0)
        position = exact.get('position', 0)
        kw = exact.get('keyword', '')
        html_parts.append(
            f'<div style="margin:8px 0 4px 0;">'
            f'🎯 <strong>Coincidencia exacta:</strong><br>'
            f'<a href="{url}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;word-break:break-all;">{url}</a><br>'
            f'<small>Keyword: <em>{kw}</em> · '
            f'{clicks} clicks · {impressions} impresiones · '
            f'Pos. {position:.1f}</small>'
            f'</div>'
        )
    
    for url_data in partial:
        url = url_data.get('url', '')
        clicks = url_data.get('clicks', 0)
        kw = url_data.get('keyword', '')
        position = url_data.get('position', 0)
        html_parts.append(
            f'<div style="margin:4px 0 4px 8px;">'
            f'• <a href="{url}" target="_blank" rel="noopener" '
            f'style="color:#1a73e8;word-break:break-all;">{url}</a><br>'
            f'<small style="margin-left:12px;">Keyword: <em>{kw}</em> · '
            f'{clicks} clicks · Pos. {position:.1f}</small>'
            f'</div>'
        )
    
    html_parts.append('</div>')
    st.markdown("".join(html_parts), unsafe_allow_html=True)
    
    recommendation = summary.get('recommendation', '')
    if recommendation:
        st.info(f"💡 {recommendation}")


def render_alternative_product_input(
    key_prefix: str = "alt_product"
) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    """
    Renderiza inputs para producto alternativo CON soporte para JSON.
    
    NUEVO v4.5.2: Añadido widget para cargar JSON del producto alternativo.
    
    Args:
        key_prefix: Prefijo para las keys de los widgets
        
    Returns:
        Tuple[url, name, json_data] - URL, nombre y datos JSON del producto alternativo
    """
    st.markdown("Sugiere un producto alternativo para mencionar en el contenido")
    
    # Inicializar estado para JSON
    json_state_key = f"{key_prefix}_json_data"
    if json_state_key not in st.session_state:
        st.session_state[json_state_key] = None
    
    # URL y nombre en la misma fila
    col1, col2 = st.columns(2)
    
    with col1:
        alt_url = st.text_input(
            label="🔗 URL del producto alternativo",
            key=f"{key_prefix}_url",
            placeholder="https://www.pccomponentes.com/producto-alternativo"
        )
    
    with col2:
        alt_name = st.text_input(
            label="📝 Nombre del producto",
            key=f"{key_prefix}_name",
            placeholder="Ej: ASUS ROG Strix..."
        )
    
    # ========================================================================
    # NUEVO: Widget para cargar JSON del producto alternativo
    # ========================================================================
    st.markdown("---")
    st.markdown(f"""
    💡 **Enriquece el contenido** cargando el JSON del producto alternativo:
    Carga el JSON del producto desde n8n.
    """)
    
    # Tabs para subir o pegar JSON
    json_tab1, json_tab2 = st.tabs(["📁 Subir archivo", "📋 Pegar JSON"])
    
    json_content = None
    
    with json_tab1:
        uploaded_json = st.file_uploader(
            "📦 JSON del producto alternativo",
            type=['json'],
            key=f"{key_prefix}_json_upload",
            help="JSON con datos estructurados del producto"
        )
        
        if uploaded_json is not None:
            try:
                json_content = uploaded_json.read().decode('utf-8')
            except Exception as e:
                st.error(f"❌ Error al leer archivo: {str(e)}")
    
    with json_tab2:
        pasted_json = st.text_area(
            "Pegar JSON aquí",
            height=150,
            key=f"{key_prefix}_json_paste",
            placeholder='{"id": "...", "name": "...", ...}',
            help="Pega el JSON directamente"
        )
        
        if pasted_json and pasted_json.strip():
            json_content = pasted_json.strip()
    
    product_json_data = None
    
    if json_content:
        try:
            if _product_json_available:
                is_valid, error_msg = validate_product_json(json_content)
                
                if is_valid:
                    product_data = parse_product_json(json_content)
                    
                    if product_data:
                        product_json_data = {
                            'product_id': product_data.product_id,
                            'legacy_id': product_data.legacy_id,
                            'title': product_data.title,
                            'description': product_data.description,
                            'brand_name': product_data.brand_name,
                            'family_name': product_data.family_name,
                            'attributes': product_data.attributes,
                            'images': product_data.images,
                            'total_comments': product_data.total_comments,
                            'advantages': product_data.advantages,
                            'disadvantages': product_data.disadvantages,
                            'comments': product_data.comments,
                        }
                        
                        st.session_state[json_state_key] = product_json_data
                        st.success(f"✅ JSON cargado: {product_data.title[:50]}")
                        
                        # Preview compacto
                        with st.expander("👁️ Preview datos JSON", expanded=False):
                            summary = create_product_summary(product_data)
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.markdown(f"**Producto:** {summary['title']}")
                                st.markdown(f"**Marca:** {summary['brand']}")
                            with col_b:
                                st.markdown(f"**Reviews:** {summary.get('total_comments', 0)}")
                                st.markdown(f"**Imágenes:** {summary.get('images_count', 0)}")
                    else:
                        st.error("❌ Error al parsear JSON")
                        st.session_state[json_state_key] = None
                else:
                    st.error(f"❌ {error_msg}")
                    st.session_state[json_state_key] = None
            else:
                # Fallback sin validación
                parsed_json = json.loads(json_content)
                st.session_state[json_state_key] = parsed_json
                st.success("✅ JSON cargado")
                product_json_data = parsed_json
                
        except json.JSONDecodeError as e:
            st.error(f"❌ Error JSON: {str(e)}")
            st.session_state[json_state_key] = None
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.session_state[json_state_key] = None
    
    # Recuperar JSON si ya estaba cargado
    if json_state_key in st.session_state and not product_json_data:
        product_json_data = st.session_state[json_state_key]
        if product_json_data:
            title = product_json_data.get('title', 'Producto')
            st.caption(f"📦 JSON cargado: {title[:40]}")
    
    return (
        alt_url.strip() if alt_url else "",
        alt_name.strip() if alt_name else "",
        product_json_data
    )


def render_competitor_urls_input(key: str = "competitor_urls") -> Tuple[List[str], Optional[str]]:
    """Renderiza input para URLs de competidores."""
    st.markdown("##### 🏆 URLs de Competencia")
    st.caption("Añade URLs de artículos competidores para análisis (máx. 5)")
    
    urls_text = st.text_area(
        label="URLs de competidores",
        key=key,
        height=100,
        placeholder="https://competidor1.com/articulo\nhttps://competidor2.com/articulo",
        label_visibility="collapsed"
    )
    
    if urls_text:
        result = validate_competitor_urls(urls_text)
        if result.value:
            st.caption(f"✅ {len(result.value)} URLs válidas de competencia")
        return result.value, None
    return [], None


def render_additional_instructions(key: str = "additional_instructions") -> str:
    """Renderiza área de instrucciones adicionales."""
    instructions = st.text_area(
        label="Instrucciones adicionales para el generador",
        key=key,
        height=100,
        placeholder="Ej: Enfócate en el rendimiento gaming, menciona la garantía extendida..."
    )
    return instructions.strip() if instructions else ""


def render_visual_elements_selector(key_prefix: str = "visual_elem") -> Dict[str, Any]:
    """
    Renderiza selector de elementos visuales alimentado por design_system.py.
    
    Lee los componentes disponibles del COMPONENT_REGISTRY centralizado,
    divididos en componentes base (artículo) y módulos CMS avanzados.
    
    Args:
        key_prefix: Prefijo para las keys de los checkboxes
        
    Returns:
        Dict con:
          - 'selected': lista de IDs de componentes seleccionados
          - 'variants': dict {component_id: variant_class} con variantes elegidas
          - 'components_css': lista de css_file keys para inyectar CSS adicional
    """
    # Intentar cargar del design_system centralizado
    try:
        from config.design_system import (
            COMPONENT_REGISTRY,
            get_available_components,
            validate_css_class,
        )
        _ds_available = True
    except ImportError:
        _ds_available = False
    
    st.markdown("**Selecciona los elementos visuales a incluir:**")
    st.caption("Componentes del Design System PcComponentes — CSS cargado desde archivos externos")
    
    # Enlace a la biblioteca visual (servida como archivo estático por Streamlit)
    st.link_button(
        "📚 Ver Biblioteca Visual",
        url="/_statics/biblioteca_visual.html",
        help="Catálogo con todos los componentes renderizados con el CSS real del CMS. Se abre en pestaña nueva.",
    )
    
    selected_elements = []
    selected_variants = {}
    components_css = set()
    
    # ── Componentes base del artículo ──
    # Estos son los elementos que forman parte de la estructura del artículo
    BASE_ELEMENTS = {
        'toc': {
            'label': '📑 Tabla de Contenidos (TOC)',
            'description': 'Navegación interna del artículo',
            'help': 'Índice clicable al inicio del artículo. Se coloca tras el H2 principal. Permite al lector saltar a cualquier sección. Fundamental para SEO y usabilidad en artículos largos.',
            'default': True,
            'icon': '📑',
        },
        'callout': {
            'label': '💡 Callouts / Destacados',
            'description': 'Cajas de información destacada con borde izquierdo',
            'help': 'Caja con borde izquierdo naranja y fondo gris claro. Úsala para tips, datos clave, advertencias o información que el lector NO debe perderse. Recomendado: 1-3 por artículo.',
            'default': False,
            'icon': '💡',
        },
        'callout_promo': {
            'label': '🔥 Callout Promocional',
            'description': 'Caja de oferta (BF, CM, campaña) con fondo degradado naranja',
            'help': 'Banner llamativo con fondo degradado naranja y texto blanco centrado. Para ofertas, campañas o promociones activas. Máximo 1 por artículo para no saturar.',
            'default': False,
            'icon': '🔥',
        },
        'callout_alert': {
            'label': '🚨 Callout de Alerta',
            'description': 'Aviso urgente con degradado naranja + borde oscuro',
            'help': 'Similar al callout promo pero con borde izquierdo oscuro. Para avisos urgentes, fechas límite o alertas importantes (ej: "Netflix dejará de funcionar en tu TV").',
            'default': False,
            'icon': '🚨',
        },
        'verdict': {
            'label': '✅ Verdict Box',
            'description': 'Veredicto final con estilo premium',
            'help': 'Bloque de conclusión con fondo degradado azul oscuro, texto blanco y enlaces dorados. Va al final del artículo dentro de contentGenerator__verdict. Debe aportar valor, no resumir.',
            'default': True,
            'icon': '✅',
        },
        'grid': {
            'label': '📐 Grid Layout',
            'description': 'Distribución en rejilla (2-3 cols) para productos o características',
            'help': 'Rejilla responsive con cards de borde gris. Cada card tiene título (h4) y texto. Ideal para comparar opciones, listar características o mostrar productos lado a lado.',
            'default': False,
            'icon': '📐',
        },
        'badges': {
            'label': '🏷️ Badges / Tags',
            'description': 'Etiquetas inline para categorías, tags, o filtros',
            'help': 'Pequeñas etiquetas tipo "pill" con borde redondeado. Para categorías, características técnicas destacadas o filtros visuales dentro de cards o secciones.',
            'default': False,
            'icon': '🏷️',
        },
        'buttons': {
            'label': '🔘 Botones CTA',
            'description': 'Botones de acción (Ver producto, Comprar, etc.)',
            'help': 'Botones de llamada a la acción con fondo naranja (primary) o borde (ghost). Colocar tras menciones de producto con enlace a PcComponentes.',
            'default': False,
            'icon': '🔘',
        },
        'faqs': {
            'label': '❓ Preguntas Frecuentes (FAQ)',
            'description': 'Sección de preguntas y respuestas al final del artículo',
            'help': 'Bloque de FAQ con pares pregunta/respuesta. Va dentro de contentGenerator__faqs. Importante para SEO (rich snippets). Usar 4-8 preguntas relevantes.',
            'default': False,
            'icon': '❓',
        },
        'intro_box': {
            'label': '📝 Intro destacada',
            'description': 'Párrafo introductorio con fondo gris y bordes redondeados',
            'help': 'Caja de resumen introductorio que destaca visualmente del resto del texto. Ideal para artículos editoriales, guías de compra o cuando quieras un "lead" potente.',
            'default': False,
            'icon': '📝',
        },
        'check_list': {
            'label': '✔️ Check List',
            'description': 'Lista con checkmarks naranja en vez de bullets estándar',
            'help': 'Lista sin bullets con ✓ naranja como pseudo-element. Perfecta para requisitos, pasos de verificación, características confirmadas o listas de compatibilidad.',
            'default': False,
            'icon': '✔️',
        },
        'specs_list': {
            'label': '🔧 Lista de Especificaciones',
            'description': 'Lista key-value para fichas técnicas de producto',
            'help': 'Ficha técnica con fondo gris, cada fila muestra "Nombre → Valor" con flex justify-between. Ideal para reviews de producto, comparativas técnicas o fichas de referencia.',
            'default': False,
            'icon': '🔧',
        },
        'product_module': {
            'label': '📦 Módulo de Producto',
            'description': 'Bloque destacado de producto con fondo gris y borde naranja',
            'help': 'Caja con fondo gris, borde izquierdo naranja, título y descripción del producto. Para destacar un producto específico con sus features clave y enlace a PcComponentes.',
            'default': False,
            'icon': '📦',
        },
        'price_highlight': {
            'label': '💰 Destacado de Precio',
            'description': 'Banner con precio grande sobre fondo degradado naranja',
            'help': 'Banner llamativo con degradado naranja, precio en tipografía grande y datos de disponibilidad. Ideal para reviews de producto o artículos de lanzamiento.',
            'default': False,
            'icon': '💰',
        },
        'stats_grid': {
            'label': '📊 Cifras / Estadísticas',
            'description': 'Tarjetas con números grandes para métricas o datos clave',
            'help': 'Grid de tarjetas con cifra grande (naranja) + descripción corta sobre fondo oscuro. Para eventos, estadísticas de producto o datos impactantes.',
            'default': False,
            'icon': '📊',
        },
        'section_divider': {
            'label': '🔹 Separador de Sección',
            'description': 'Banner con degradado azul, kicker y título para separar bloques temáticos',
            'help': 'Franja a ancho completo con fondo degradado azul oscuro, kicker naranja y título blanco. Para mega-guías o artículos con múltiples verticales temáticas.',
            'default': False,
            'icon': '🔹',
        },
    }
    
    # ── Tablas (elegir tipo) ──
    TABLE_ELEMENTS = {
        'table': {
            'label': '📊 Tabla HTML estándar',
            'description': 'Tabla <table> con estilos base del CMS',
            'help': 'Tabla HTML clásica con <thead> y <tbody>. Estilos automáticos del CMS. Para comparativas simples, specs lado a lado o datos tabulares.',
            'default': False,
            'icon': '📊',
        },
        'light_table': {
            'label': '📋 Light Table (CSS Grid)',
            'description': 'Tabla flexible basada en grid CSS — soporta 2, 3 o 7 columnas con filas alternas',
            'help': 'Tabla basada en divs con CSS Grid (.lt). Más flexible que <table>: soporta 2, 3 o 7 columnas (.cols-2/3/7), filas alternas (.zebra) y es responsive. Ideal para specs detalladas.',
            'default': False,
            'icon': '📋',
        },
        'comparison_table': {
            'label': '⚖️ Tabla de Comparación',
            'description': 'Tabla comparativa con columna destacada — ideal para vs. de productos',
            'help': 'Tabla HTML con columna ganadora destacada (.comparison-highlight). Para enfrentar 2-3 productos y resaltar el recomendado. El header naranja se aplica a la columna elegida.',
            'default': False,
            'icon': '⚖️',
        },
    }
    
    # ── Módulos CMS avanzados ──
    CMS_MODULES = {
        'mod_cards': {
            'label': '🃏 Cards Horizontales (Módulo CMS)',
            'description': 'Cards con imagen lateral — ideal para comparativas de 2-4 productos con specs',
            'help': 'Módulo CMS avanzado con cards horizontales: imagen a la izquierda + specs a la derecha. Incluye chip de etiqueta, lista de características y botón CTA. Para comparativas de 2-4 productos.',
            'default': False,
            'icon': '🃏',
        },
        'vcard_cards': {
            'label': '📇 Cards Verticales (Módulo CMS)',
            'description': 'Cards verticales con chip, lista y CTA — ideal para recomendaciones y listados',
            'help': 'Módulo CMS con cards verticales apiladas. Cada card tiene chip de categoría, título, lista de beneficios y CTA. Para listados de 3-4 productos recomendados o rankings.',
            'default': False,
            'icon': '📇',
        },
        'compact_cards': {
            'label': '🟠 Compact Cards (Naranja)',
            'description': 'Cards naranjas con icono + bullets — ideal para resumir criterios, specs o puntos clave',
            'help': 'Grid de cards con borde naranja superior, icono SVG circular y lista de bullets. Perfecto para criterios de compra, specs resumidas o puntos clave del artículo. 3-6 cards.',
            'default': False,
            'icon': '🟠',
        },
        'use_cases': {
            'label': '🔵 Cards Casos de Uso (Azul)',
            'description': 'Cards azules con escenario + recomendación — ideal para segmentar por perfil de usuario',
            'help': 'Grid de cards con borde azul lateral, icono y texto descriptivo. Cada card presenta un caso de uso o perfil de comprador con recomendación de producto. 2-4 cards.',
            'default': False,
            'icon': '🔵',
        },
    }
    
    # ── Renderizar sección BASE ──
    st.markdown("##### Elementos de artículo")
    
    # Dividir en 2 grupos: Estructura (primeros 7) y Contenido enriquecido (resto)
    _STRUCTURE_IDS = ['toc', 'callout', 'callout_promo', 'callout_alert', 'verdict', 'grid', 'badges', 'buttons']
    _CONTENT_IDS = ['faqs', 'intro_box', 'check_list', 'specs_list', 'product_module',
                    'price_highlight', 'stats_grid', 'section_divider']
    
    structure_items = [(k, v) for k, v in BASE_ELEMENTS.items() if k in _STRUCTURE_IDS]
    content_items = [(k, v) for k, v in BASE_ELEMENTS.items() if k in _CONTENT_IDS]
    
    # -- Bloque Estructura --
    st.caption("Estructura y layout")
    col1, col2 = st.columns(2)
    for i, (elem_id, elem_cfg) in enumerate(structure_items):
        target_col = col1 if i % 2 == 0 else col2
        with target_col:
            is_selected = st.checkbox(
                elem_cfg['label'],
                value=elem_cfg['default'],
                key=f"{key_prefix}_{elem_id}",
                help=elem_cfg.get('help', elem_cfg['description']),
            )
            if is_selected:
                selected_elements.append(elem_id)
                if _ds_available and elem_id in COMPONENT_REGISTRY:
                    components_css.add(COMPONENT_REGISTRY[elem_id].css_file)

    # -- Bloque Contenido enriquecido --
    st.caption("Contenido enriquecido")
    col3, col4 = st.columns(2)
    for i, (elem_id, elem_cfg) in enumerate(content_items):
        target_col = col3 if i % 2 == 0 else col4
        with target_col:
            is_selected = st.checkbox(
                elem_cfg['label'],
                value=elem_cfg['default'],
                key=f"{key_prefix}_{elem_id}",
                help=elem_cfg.get('help', elem_cfg['description']),
            )
            if is_selected:
                selected_elements.append(elem_id)
                if _ds_available and elem_id in COMPONENT_REGISTRY:
                    components_css.add(COMPONENT_REGISTRY[elem_id].css_file)
    
    # ── Renderizar sección TABLAS ──
    st.markdown("##### Tablas")
    st.caption("Puedes combinar varios tipos de tabla en el mismo artículo")
    col_t1, col_t2, col_t3 = st.columns(3)
    table_cols = [col_t1, col_t2, col_t3]
    
    for i, (elem_id, elem_cfg) in enumerate(TABLE_ELEMENTS.items()):
        with table_cols[i]:
            is_selected = st.checkbox(
                elem_cfg['label'],
                value=elem_cfg['default'],
                key=f"{key_prefix}_{elem_id}",
                help=elem_cfg.get('help', elem_cfg['description']),
            )
            if is_selected:
                selected_elements.append(elem_id)
                # Añadir CSS file del componente
                if _ds_available and elem_id in COMPONENT_REGISTRY:
                    components_css.add(COMPONENT_REGISTRY[elem_id].css_file)
    
    # ── Renderizar sección MÓDULOS CMS ──
    st.markdown("##### Módulos CMS avanzados")
    st.caption("Componentes ricos del CMS con variantes de estilo configurables")
    
    for elem_id, elem_cfg in CMS_MODULES.items():
        is_selected = st.checkbox(
            elem_cfg['label'],
            value=elem_cfg['default'],
            key=f"{key_prefix}_{elem_id}",
            help=elem_cfg.get('help', elem_cfg['description']),
        )
        if is_selected:
            selected_elements.append(elem_id)
            if _ds_available and elem_id in COMPONENT_REGISTRY:
                components_css.add(COMPONENT_REGISTRY[elem_id].css_file)
            
            # Mostrar opciones de variantes para módulos CMS
            _render_cms_module_variants(
                elem_id, elem_cfg, key_prefix, 
                selected_variants, _ds_available
            )
    
    # ── Preview de elementos seleccionados ──
    if selected_elements:
        with st.expander("👁️ Preview HTML de componentes seleccionados", expanded=False):
            for elem_id in selected_elements:
                template = _get_component_template(elem_id, _ds_available)
                if template:
                    label = (
                        BASE_ELEMENTS.get(elem_id, {}).get('label') or
                        TABLE_ELEMENTS.get(elem_id, {}).get('label') or
                        CMS_MODULES.get(elem_id, {}).get('label', elem_id)
                    )
                    st.markdown(f"**{label}**")
                    st.code(template, language="html")
    
    return {
        'selected': selected_elements,
        'variants': selected_variants,
        'components_css': list(components_css),
    }


def _render_cms_module_variants(
    elem_id: str,
    elem_cfg: Dict,
    key_prefix: str,
    selected_variants: Dict[str, str],
    ds_available: bool,
) -> None:
    """Renderiza opciones de variantes para un módulo CMS seleccionado."""
    
    if not ds_available:
        return
    
    try:
        from config.design_system import COMPONENT_REGISTRY
    except ImportError:
        return
    
    comp = COMPONENT_REGISTRY.get(elem_id)
    if not comp or not comp.variants:
        return
    
    # Variantes del contenedor/sección
    variant_options = [v.label for v in comp.variants]
    variant_classes = [v.css_class for v in comp.variants]
    
    with st.container():
        col_v1, col_v2 = st.columns([1, 2])
        with col_v1:
            selected_idx = st.selectbox(
                f"Estilo del módulo",
                range(len(variant_options)),
                format_func=lambda i: variant_options[i],
                key=f"{key_prefix}_{elem_id}_variant",
            )
            selected_variants[elem_id] = variant_classes[selected_idx]
        
        with col_v2:
            desc = comp.variants[selected_idx].description
            if desc:
                st.caption(f"ℹ️ {desc}")
    
    # Sub-variantes específicas por módulo
    if elem_id == 'mod_cards':
        _render_mod_cards_suboptions(key_prefix, selected_variants, elem_id)
    elif elem_id == 'vcard_cards':
        _render_vcard_suboptions(key_prefix, selected_variants, elem_id)


def _render_mod_cards_suboptions(
    key_prefix: str, 
    selected_variants: Dict[str, str],
    elem_id: str,
) -> None:
    """Sub-opciones para Cards Horizontales."""
    try:
        from config.design_system import (
            MOD_GRID_VARIANTS, MOD_CARD_VARIANTS,
            MOD_CHIP_VARIANTS, MOD_CTA_VARIANTS,
        )
    except ImportError:
        return
    
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            # Grid columns
            grid_options = [v.label for v in MOD_GRID_VARIANTS]
            grid_classes = [v.css_class for v in MOD_GRID_VARIANTS]
            grid_idx = st.selectbox(
                "Columnas del grid",
                range(len(grid_options)),
                format_func=lambda i: grid_options[i],
                key=f"{key_prefix}_{elem_id}_grid",
            )
            selected_variants[f"{elem_id}_grid"] = grid_classes[grid_idx]
        
        with col2:
            # Card style
            card_options = [v.label for v in MOD_CARD_VARIANTS]
            card_classes = [v.css_class for v in MOD_CARD_VARIANTS]
            card_idx = st.selectbox(
                "Estilo de card",
                range(len(card_options)),
                format_func=lambda i: card_options[i],
                key=f"{key_prefix}_{elem_id}_card",
                index=1,  # Default: Horizontal
            )
            selected_variants[f"{elem_id}_card"] = card_classes[card_idx]
        
        col3, col4 = st.columns(2)
        
        with col3:
            # Chip style
            chip_options = [v.label for v in MOD_CHIP_VARIANTS]
            chip_classes = [v.css_class for v in MOD_CHIP_VARIANTS]
            chip_idx = st.selectbox(
                "Estilo de chip/etiqueta",
                range(len(chip_options)),
                format_func=lambda i: chip_options[i],
                key=f"{key_prefix}_{elem_id}_chip",
            )
            selected_variants[f"{elem_id}_chip"] = chip_classes[chip_idx]
        
        with col4:
            # CTA style
            cta_options = [v.label for v in MOD_CTA_VARIANTS]
            cta_classes = [v.css_class for v in MOD_CTA_VARIANTS]
            cta_idx = st.selectbox(
                "Estilo de botón CTA",
                range(len(cta_options)),
                format_func=lambda i: cta_options[i],
                key=f"{key_prefix}_{elem_id}_cta",
            )
            selected_variants[f"{elem_id}_cta"] = cta_classes[cta_idx]


def _render_vcard_suboptions(
    key_prefix: str, 
    selected_variants: Dict[str, str],
    elem_id: str,
) -> None:
    """Sub-opciones para Cards Verticales."""
    try:
        from config.design_system import (
            VCARD_GRID_VARIANTS, VCARD_VARIANTS,
            VCARD_CHIP_VARIANTS, VCARD_CTA_VARIANTS,
            VCARD_LIST_VARIANTS,
        )
    except ImportError:
        return
    
    with st.container():
        col1, col2 = st.columns(2)
        
        with col1:
            # Grid columns
            grid_options = [v.label for v in VCARD_GRID_VARIANTS]
            grid_classes = [v.css_class for v in VCARD_GRID_VARIANTS]
            grid_idx = st.selectbox(
                "Columnas del grid",
                range(len(grid_options)),
                format_func=lambda i: grid_options[i],
                key=f"{key_prefix}_{elem_id}_grid",
            )
            selected_variants[f"{elem_id}_grid"] = grid_classes[grid_idx]
        
        with col2:
            # Card style
            card_options = [v.label for v in VCARD_VARIANTS]
            card_classes = [v.css_class for v in VCARD_VARIANTS]
            card_idx = st.selectbox(
                "Estilo de card",
                range(len(card_options)),
                format_func=lambda i: card_options[i],
                key=f"{key_prefix}_{elem_id}_card",
                index=1,  # Default: Hoverable
            )
            selected_variants[f"{elem_id}_card"] = card_classes[card_idx]
        
        col3, col4 = st.columns(2)
        
        with col3:
            # Chip style
            chip_options = [v.label for v in VCARD_CHIP_VARIANTS]
            chip_classes = [v.css_class for v in VCARD_CHIP_VARIANTS]
            chip_idx = st.selectbox(
                "Estilo de chip",
                range(len(chip_options)),
                format_func=lambda i: chip_options[i],
                key=f"{key_prefix}_{elem_id}_chip",
            )
            selected_variants[f"{elem_id}_chip"] = chip_classes[chip_idx]
        
        with col4:
            # List style
            list_options = [v.label for v in VCARD_LIST_VARIANTS]
            list_classes = [v.css_class for v in VCARD_LIST_VARIANTS]
            list_idx = st.selectbox(
                "Estilo de lista",
                range(len(list_options)),
                format_func=lambda i: list_options[i],
                key=f"{key_prefix}_{elem_id}_list",
            )
            selected_variants[f"{elem_id}_list"] = list_classes[list_idx]


def _get_component_template(elem_id: str, ds_available: bool) -> str:
    """
    Retorna el template HTML de un componente.
    Lee del COMPONENT_REGISTRY si está disponible, fallback a templates locales.
    """
    if ds_available:
        try:
            from config.design_system import COMPONENT_REGISTRY
            comp = COMPONENT_REGISTRY.get(elem_id)
            if comp and comp.html_template:
                return comp.html_template
        except ImportError:
            pass
    
    # Fallback templates para cuando design_system no está disponible
    _FALLBACK_TEMPLATES = {
        'toc': '<nav class="toc">\n  <h4>En este artículo</h4>\n  <a href="#seccion">Sección</a>\n</nav>',
        'callout': '<div class="callout">\n  <p><strong>💡 Consejo:</strong> Información destacada.</p>\n</div>',
        'callout_promo': '<div class="callout-bf">\n  <p><strong>OFERTA</strong></p>\n  <p>Texto <a href="#">enlace</a></p>\n</div>',
        'verdict': '<article class="contentGenerator__verdict"><div class="verdict-box">\n  <h2>Veredicto Final</h2>\n  <p>Conclusión...</p>\n</div></article>',
        'grid': '<div class="grid cols-2">\n  <div class="card"><h4>Item</h4><p>...</p></div>\n</div>',
        'badges': '<div class="badges">\n  <span class="badge">Tag 1</span>\n  <span class="badge">Tag 2</span>\n</div>',
        'buttons': '<div class="btns">\n  <a href="#" class="btn primary">Ver producto</a>\n</div>',
        'table': '<table>\n  <thead><tr><th>Col 1</th><th>Col 2</th></tr></thead>\n  <tbody><tr><td>Dato</td><td>Dato</td></tr></tbody>\n</table>',
        'light_table': '<div class="lt cols-3">\n  <div class="r"><div class="c">Header</div><div class="c">Header</div><div class="c">Header</div></div>\n  <div class="r"><div class="c">Data</div><div class="c">Data</div><div class="c">Data</div></div>\n</div>',
        'comparison_table': '<table class="comparison-table">\n  <thead><tr><th>Spec</th><th>Producto A</th><th class="comparison-highlight">Producto B</th></tr></thead>\n  <tbody><tr><td>Valor</td><td>X</td><td class="comparison-highlight">Y</td></tr></tbody>\n</table>',
        'mod_cards': '<div class="mod-section">\n  <h3 class="mod-section__title">Título</h3>\n  <div class="mod-grid">\n    <article class="mod-card mod-card--horizontal">...</article>\n  </div>\n</div>',
        'vcard_cards': '<div class="vcard-module">\n  <h3 class="vcard-module__title">Título</h3>\n  <div class="vcard-grid">\n    <article class="vcard vcard--hoverable">...</article>\n  </div>\n</div>',
        'compact_cards': '<div class="compact-cards">\n  <div class="compact-card">\n    <p class="compact-card__title"><span class="compact-card__icon"><svg viewBox="0 0 24 24"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg></span>Punto clave</p>\n    <ul><li>Dato 1</li><li>Dato 2</li></ul>\n  </div>\n</div>',
        'use_cases': '<div class="use-cases">\n  <div class="use-case">\n    <p class="use-case__title"><span class="use-case__icon"><svg viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"/></svg></span>Caso de uso</p>\n    <p>Descripción del escenario.</p>\n    <p><strong>Recomendación:</strong> <a href="URL">Producto</a></p>\n  </div>\n</div>',
    }
    return _FALLBACK_TEMPLATES.get(elem_id, '')


# ============================================================================
# VALIDACIÓN DE ERRORES COMPACTA
# ============================================================================

def render_validation_errors(errors: List[str]) -> None:
    """Renderiza errores de validación de forma compacta."""
    if not errors:
        return
    
    error_html = "<div style='background-color:#f8d7da;border:1px solid #f5c6cb;border-radius:5px;padding:10px;margin:10px 0;'>"
    error_html += "<span style='color:#721c24;font-weight:bold;font-size:14px;'>⚠️ Corrige los siguientes errores:</span><ul style='margin:5px 0;padding-left:20px;color:#721c24;font-size:13px;'>"
    
    for e in errors:
        error_html += f"<li>{e}</li>"
    
    error_html += "</ul></div>"
    
    st.markdown(error_html, unsafe_allow_html=True)


# ============================================================================
# CONFIGURACIÓN DE ENCABEZADOS HTML (v5.0)
# ============================================================================

def render_headings_config(key_prefix: str = "headings") -> Optional[Dict[str, int]]:
    """
    Renderiza configuración opcional de encabezados HTML.
    
    Permite al usuario definir cuántos H2, H3 y H4 quiere.
    Si no se activa, Claude decide libremente.
    
    Args:
        key_prefix: Prefijo para keys de widgets
        
    Returns:
        Dict {'h2': N, 'h3': N, 'h4': N} o None si no se configura
    """
    enabled_key = f"{key_prefix}_enabled"
    
    is_enabled = st.checkbox(
        "Definir estructura de encabezados",
        value=st.session_state.get(enabled_key, False),
        key=f"{key_prefix}_enabled_cb",
        help="Opcional: define cuántos H2, H3 y H4 usar. Si no lo activas, Claude decide automáticamente.",
    )
    st.session_state[enabled_key] = is_enabled
    
    if not is_enabled:
        st.caption("💡 Claude decidirá la estructura de encabezados según el arquetipo y la longitud.")
        return None
    
    col_h2, col_h3, col_h4 = st.columns(3)
    
    with col_h2:
        h2_count = st.number_input(
            "Nº de H2",
            min_value=1,
            max_value=15,
            value=st.session_state.get(f"{key_prefix}_h2", 4),
            step=1,
            key=f"{key_prefix}_h2_input",
            help="Secciones principales del artículo",
        )
    
    with col_h3:
        h3_count = st.number_input(
            "Nº de H3",
            min_value=0,
            max_value=30,
            value=st.session_state.get(f"{key_prefix}_h3", 8),
            step=1,
            key=f"{key_prefix}_h3_input",
            help="Subsecciones dentro de los H2",
        )
    
    with col_h4:
        h4_count = st.number_input(
            "Nº de H4 (FAQs, etc.)",
            min_value=0,
            max_value=20,
            value=st.session_state.get(f"{key_prefix}_h4", 0),
            step=1,
            key=f"{key_prefix}_h4_input",
            help="Sub-subsecciones o preguntas FAQ individuales",
        )
    
    st.caption(f"📊 Estructura: {h2_count} H2 · {h3_count} H3 · {h4_count} H4")
    
    return {'h2': h2_count, 'h3': h3_count, 'h4': h4_count}




def _render_single_product_entry(
    index: int,
    key_prefix: str,
    expanded: bool = True,
) -> Optional[ProductEntry]:
    """
    Renderiza los inputs de un único producto (URL + JSON + rol).
    
    Args:
        index: Índice del producto (0-based)
        key_prefix: Prefijo para keys de widgets
        expanded: Si el expander está abierto por defecto
    
    Returns:
        ProductEntry con los datos o None si está vacío
    """
    product_key = f"{key_prefix}_product_{index}"
    json_state_key = f"{product_key}_json_data"
    
    # Inicializar estado JSON
    if json_state_key not in st.session_state:
        st.session_state[json_state_key] = None
    
    # Fila 1: URL + Rol
    col_url, col_role = st.columns([3, 1])
    
    with col_url:
        url = st.text_input(
            f"🔗 URL del producto",
            key=f"{product_key}_url",
            placeholder="https://www.pccomponentes.com/...",
            label_visibility="visible" if index == 0 else "collapsed",
        )
    
    with col_role:
        role_options = ["principal", "alternativo", "enlazado"]
        role_labels = {"principal": "⭐ Principal", "alternativo": "🔄 Alternativo", "enlazado": "🔗 Enlazado"}
        role = st.selectbox(
            "Rol",
            options=role_options,
            format_func=lambda x: role_labels[x],
            key=f"{product_key}_role",
            label_visibility="visible" if index == 0 else "collapsed",
            help="Principal: protagonista del artículo | Alternativo: se recomienda como opción | Enlazado: solo se menciona/enlaza",
        )
    
    # Fila 2: JSON (tabs pegar/subir)
    json_content = None
    
    json_tab1, json_tab2 = st.tabs(["📋 Pegar JSON", "📁 Subir archivo"])
    
    with json_tab1:
        pasted = st.text_area(
            "JSON",
            height=100,
            key=f"{product_key}_json_paste",
            placeholder='[{"meta": [...], "data": [...]}]',
            label_visibility="collapsed",
        )
        if pasted and pasted.strip():
            json_content = pasted.strip()
    
    with json_tab2:
        uploaded = st.file_uploader(
            "JSON",
            type=['json'],
            key=f"{product_key}_json_upload",
            label_visibility="collapsed",
        )
        if uploaded is not None:
            try:
                json_content = uploaded.read().decode('utf-8')
            except Exception as e:
                st.error(f"❌ Error al leer archivo: {str(e)}")
    
    # Procesar JSON
    product_json_data = None
    product_name = ""
    
    if json_content:
        try:
            if _product_json_available:
                is_valid, error_msg = validate_product_json(json_content)
                if is_valid:
                    product_data = parse_product_json(json_content)
                    if product_data:
                        product_json_data = {
                            'product_id': product_data.product_id,
                            'legacy_id': product_data.legacy_id,
                            'title': product_data.title,
                            'description': product_data.description,
                            'brand_name': product_data.brand_name,
                            'family_name': product_data.family_name,
                            'attributes': product_data.attributes,
                            'images': product_data.images,
                            'total_comments': product_data.total_comments,
                            'advantages': product_data.advantages,
                            'disadvantages': product_data.disadvantages,
                            'comments': product_data.comments,
                            'price': product_data.price,
                            'product_url': product_data.product_url,
                            'rating': product_data.rating,
                            'category': product_data.category,
                            'faqs': product_data.faqs,
                            'advantages_list': product_data.advantages_list,
                            'disadvantages_list': product_data.disadvantages_list,
                        }
                        product_name = product_data.title
                        st.session_state[json_state_key] = product_json_data
                        
                        # Preview compacto inline
                        preview_parts = [f"✅ **{product_data.title[:50]}**"]
                        if product_data.brand_name:
                            preview_parts.append(f"({product_data.brand_name})")
                        if product_data.price:
                            preview_parts.append(f"— {product_data.price}")
                        st.success(" ".join(preview_parts))
                    else:
                        st.error("❌ Error al parsear JSON")
                        st.session_state[json_state_key] = None
                else:
                    st.error(f"❌ {error_msg}")
                    st.session_state[json_state_key] = None
            else:
                # Fallback sin validación
                parsed = json.loads(json_content)
                st.session_state[json_state_key] = parsed
                product_json_data = parsed
                st.success("✅ JSON cargado")
        except json.JSONDecodeError as e:
            st.error(f"❌ JSON inválido: {str(e)}")
            st.session_state[json_state_key] = None
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")
            st.session_state[json_state_key] = None
    
    # Recuperar JSON previamente cargado
    if st.session_state.get(json_state_key) and not product_json_data:
        product_json_data = st.session_state[json_state_key]
        title = product_json_data.get('title', 'Producto')
        st.caption(f"📦 JSON cargado: {title[:50]}")
        product_name = title
    
    # Solo retornar si hay algo
    if url or product_json_data:
        return ProductEntry(
            url=url.strip() if url else "",
            name=product_name or "",
            json_data=product_json_data,
            role=role,
        )
    
    return None


def render_products_block(
    key_prefix: str = "products",
    default_count: int = 1,
) -> List[ProductEntry]:
    """
    Bloque unificado de productos reutilizable en ambos modos.
    
    Muestra un checkbox "¿El contenido incluye productos?" y si se activa,
    permite añadir N productos con URL + JSON + rol.
    
    Args:
        key_prefix: Prefijo para keys (evita colisiones entre modos)
        default_count: Número inicial de productos al activar
    
    Returns:
        Lista de ProductEntry (vacía si no se activan productos)
    """
    count_key = f"{key_prefix}_count"
    enabled_key = f"{key_prefix}_enabled"
    
    # Checkbox de activación
    is_enabled = st.checkbox(
        "El contenido incluye/analiza/compara productos",
        value=st.session_state.get(enabled_key, False),
        key=f"{key_prefix}_enabled_cb",
        help="Activa para añadir uno o varios productos con sus datos. "
             "Desactiva si el contenido es genérico (ej: 'qué es la fibra óptica')",
    )
    st.session_state[enabled_key] = is_enabled
    
    if not is_enabled:
        st.caption(
            "💡 Si el artículo habla sobre productos concretos (review, comparativa, "
            "guía de compra...), activa esta opción para enriquecer el contenido."
        )
        return []
    
    # Inicializar contador
    if count_key not in st.session_state:
        st.session_state[count_key] = default_count
    
    current_count = st.session_state[count_key]
    
    # Info de roles
    st.caption(
        "⭐ **Principal** = protagonista del artículo · "
        "🔄 **Alternativo** = se recomienda como opción · "
        "🔗 **Enlazado** = solo se menciona/enlaza"
    )
    
    # Renderizar cada producto en un expander
    products = []
    
    for i in range(current_count):
        # Determinar título del expander
        json_data = st.session_state.get(f"{key_prefix}_product_{i}_json_data")
        if json_data and isinstance(json_data, dict):
            title = json_data.get('title', f'Producto {i+1}')[:40]
            role_st = st.session_state.get(f"{key_prefix}_product_{i}_role", "principal")
            role_icon = {"principal": "⭐", "alternativo": "🔄", "enlazado": "🔗"}.get(role_st, "📦")
            expander_title = f"{role_icon} {title}"
        else:
            expander_title = f"📦 Producto {i+1}"
        
        with st.expander(expander_title, expanded=(i == current_count - 1)):
            entry = _render_single_product_entry(
                index=i,
                key_prefix=key_prefix,
                expanded=(i == 0),
            )
            if entry:
                products.append(entry)
    
    # Botones añadir/quitar
    col_add, col_remove, col_spacer = st.columns([1, 1, 3])
    
    with col_add:
        if st.button("➕ Añadir producto", key=f"{key_prefix}_add_btn"):
            st.session_state[count_key] = current_count + 1
            st.rerun()
    
    with col_remove:
        if current_count > 1:
            if st.button("➖ Quitar último", key=f"{key_prefix}_remove_btn"):
                # Limpiar estado del último producto
                last_idx = current_count - 1
                for suffix in ['_url', '_role', '_json_paste', '_json_upload', '_json_data']:
                    k = f"{key_prefix}_product_{last_idx}{suffix}"
                    if k in st.session_state:
                        del st.session_state[k]
                st.session_state[count_key] = current_count - 1
                st.rerun()
    
    # Resumen
    if products:
        principals = sum(1 for p in products if p.role == "principal")
        alternatives = sum(1 for p in products if p.role == "alternativo")
        linked = sum(1 for p in products if p.role == "enlazado")
        with_json = sum(1 for p in products if p.json_data)
        
        summary_parts = []
        if principals:
            summary_parts.append(f"⭐ {principals} principal{'es' if principals > 1 else ''}")
        if alternatives:
            summary_parts.append(f"🔄 {alternatives} alternativo{'s' if alternatives > 1 else ''}")
        if linked:
            summary_parts.append(f"🔗 {linked} enlazado{'s' if linked > 1 else ''}")
        
        st.caption(f"📊 {len(products)} producto{'s' if len(products) > 1 else ''} ({', '.join(summary_parts)}) · {with_json} con JSON")
    
    return products


# ============================================================================
# FORMULARIO PRINCIPAL
# ============================================================================

def render_main_form(mode: str = "new") -> Optional[FormData]:
    """Renderiza el formulario principal completo con jerarquía visual mejorada."""
    errors = []
    
    # ── SECCIÓN 1: Campos obligatorios ──────────────────────────────
    st.markdown("#### 🎯 Configuración principal")

    # Fecha GSC (solo si hay datos)
    render_gsc_date_warning()

    # Fila 1: Keyword (más ancha, es el campo más importante) + Arquetipo
    col_kw, col_arq = st.columns([3, 2])
    with col_kw:
        keyword, keyword_error = render_keyword_input(key="main_keyword", required=True)
        if keyword_error and keyword == "":
            errors.append(keyword_error)

    with col_arq:
        arquetipo = render_arquetipo_selector(key="main_arquetipo")

    # Fila 2: Longitud + Keywords secundarias en la misma fila
    col_len, col_sec_kw = st.columns([2, 3])
    with col_len:
        target_length = render_length_slider(key="main_length", arquetipo_code=arquetipo)

    with col_sec_kw:
        st.caption("Keywords secundarias *(opcional — una por línea)*")
        keywords_input = st.text_area(
            "Keywords secundarias",
            key="main_secondary_keywords",
            height=68,
            placeholder="keyword relacionada 1\nkeyword relacionada 2",
            label_visibility="collapsed"
        )
        secondary_keywords = [
            k.strip() for k in keywords_input.split('\n')
            if k.strip() and k.strip() != keyword
        ] if keywords_input else []

    # ── BRIEFING (semi-obligatorio, mejora calidad) ──────────────────
    # Mostrar indicador de estado ANTES del briefing para guiar al usuario
    if st.session_state.get('main_guiding_answered'):
        guiding_preview = st.session_state.get('main_guiding_answered', {})
        num_preview = len(guiding_preview) if isinstance(guiding_preview, dict) else 0
        if num_preview > 0:
            st.caption(f"📋 Briefing: {num_preview} preguntas respondidas ✅")
    else:
        st.caption("📋 **Completa el briefing** para mejorar la calidad del contenido")

    guiding_answers = render_guiding_questions(arquetipo, key_prefix="main_guiding")

    # Actualizar indicador post-render
    if guiding_answers:
        num_answered = len(guiding_answers)
        try:
            from config.arquetipos import get_guiding_questions as _get_gq, PREGUNTAS_UNIVERSALES
            total_q = len(_get_gq(arquetipo, include_universal=False)) + len(PREGUNTAS_UNIVERSALES)
        except Exception:
            total_q = num_answered + 3

    # ── SECCIÓN 2: Opciones opcionales (agrupadas) ──────────────────
    st.markdown("#### ⚙️ Opciones adicionales")
    st.caption("*Todos estos campos son opcionales. Empieza solo con keyword + arquetipo si es tu primera vez.*")

    # Productos — dentro de expander para indicar que es opcional
    with st.expander("📦 Productos *(opcional)*", expanded=False):
        products = render_products_block(key_prefix="main_products")

    # Backward compat: extraer pdp_url y pdp_json_data del primer producto principal
    pdp_url = None
    pdp_data = None
    pdp_json_data = None
    if products:
        first_principal = next((p for p in products if p.role == "principal"), None)
        if first_principal:
            pdp_url = first_principal.url or None
            pdp_json_data = first_principal.json_data

    # Enlaces internos con anchor
    with st.expander("🔗 Enlaces Internos *(opcional)*", expanded=False):
        internal_links = render_links_with_anchors(
            key_prefix="main_internal",
            label="Enlaces Internos",
            link_type="internal",
            max_links=10,
            allow_json=False
        )

    # Competidores (solo rewrite)
    competitor_urls = []
    if mode == "rewrite":
        with st.expander("🏆 Análisis de Competencia", expanded=True):
            competitor_urls, _ = render_competitor_urls_input(key="main_competitors")

    # Elementos visuales + Encabezados + Instrucciones — agrupados en un expander
    with st.expander("🎨 Visual, estructura e instrucciones *(opcional)*", expanded=False):
        # Elementos visuales
        st.markdown("**Elementos Visuales**")
        visual_config = render_visual_elements_selector(key_prefix="main_visual")
        visual_elements = visual_config.get('selected', []) if isinstance(visual_config, dict) else visual_config

        st.markdown("---")

        # Estructura de encabezados
        st.markdown("**Estructura de Encabezados**")
        headings_config = render_headings_config(key_prefix="main_headings")

        st.markdown("---")

        # Instrucciones adicionales
        st.markdown("**Instrucciones Adicionales**")
        additional_instructions = render_additional_instructions(key="main_instructions")
    
    # ── Validación ──────────────────────────────────────────────────
    if errors:
        render_validation_errors(errors)
        return None
    
    # Backward compat: construir campos legacy desde products
    pdp_links = None
    alt_url = ""
    alt_name = ""
    alt_json_data = None
    
    if products:
        # pdp_links: todos los productos enlazados como LinkWithAnchor
        pdp_links_list = []
        for p in products:
            if p.url:
                lwa = LinkWithAnchor(
                    url=p.url,
                    anchor=p.name or "",
                    link_type="pdp",
                    product_data=p.json_data,
                )
                pdp_links_list.append(lwa)
        pdp_links = pdp_links_list or None
        
        # alternative_product: primer producto con rol "alternativo"
        first_alt = next((p for p in products if p.role == "alternativo"), None)
        if first_alt:
            alt_url = first_alt.url or ""
            alt_name = first_alt.name or ""
            alt_json_data = first_alt.json_data
    
    return FormData(
        keyword=keyword,
        pdp_url=pdp_url or None,
        pdp_data=pdp_data,
        pdp_json_data=pdp_json_data,
        target_length=target_length,
        arquetipo=arquetipo,
        mode=mode,
        competitor_urls=competitor_urls or None,
        internal_links=internal_links or None,
        pdp_links=pdp_links,
        additional_instructions=additional_instructions or None,
        guiding_answers=guiding_answers or None,
        alternative_product_url=alt_url,
        alternative_product_name=alt_name,
        alternative_product_json_data=alt_json_data,
        visual_elements=visual_elements or None,
        visual_config=visual_config if isinstance(visual_config, dict) else None,
        products=products or None,
        headings_config=headings_config,
        secondary_keywords=secondary_keywords or None,
    )


# ============================================================================
# FUNCIÓN PRINCIPAL PARA APP.PY
# ============================================================================

def render_content_inputs() -> Tuple[bool, Dict[str, Any]]:
    """
    Renderiza inputs y retorna configuración.
    Esta es la función que app.py importa.
    
    NOTA: El selector de modo está en app.py (render_app_header), NO aquí.
    Esta función solo maneja el modo 'new'. El modo 'rewrite' usa render_rewrite_section().
    
    NO incluye botón de generación - ese está en app.py para centralizar la lógica.
    
    Returns:
        Tuple[bool, Dict]: (is_valid, config) donde is_valid indica si el formulario
        está completo y config contiene los datos formateados.
    """
    # El modo siempre es 'new' aquí - app.py maneja el routing
    mode = 'new'
    
    # Formulario principal
    form_data = render_main_form(mode=mode)
    
    # Si no hay datos válidos, retornar False
    if form_data is None:
        return False, {}
    
    # Formatear enlaces internos
    internal_links_fmt = []
    if form_data.internal_links:
        for link in form_data.internal_links:
            internal_links_fmt.append({
                'url': link.url,
                'anchor': link.anchor,
                'type': 'internal'
            })
    
    # Formatear enlaces PDP (ahora incluyen product_data)
    pdp_links_fmt = []
    if form_data.pdp_links:
        for link in form_data.pdp_links:
            link_dict = {
                'url': link.url,
                'anchor': link.anchor,
                'type': 'pdp'
            }
            
            # Añadir datos de producto si existen
            if link.product_data:
                link_dict['product_data'] = link.product_data
            
            pdp_links_fmt.append(link_dict)
    
    # Formatear contexto de preguntas guía
    context_from_questions = ""
    if form_data.guiding_answers:
        parts = [f"**{q}**\n{a}" for q, a in form_data.guiding_answers.items()]
        context_from_questions = "\n\n".join(parts)
    
    # Construir config
    # Combinar todos los enlaces en una lista única para el prompt
    all_links = internal_links_fmt + pdp_links_fmt
    
    # Construir objeto de producto alternativo
    alternative_product = None
    if form_data.alternative_product_url or form_data.alternative_product_name or form_data.alternative_product_json_data:
        alternative_product = {
            'url': form_data.alternative_product_url or '',
            'name': form_data.alternative_product_name or '',
            'json_data': form_data.alternative_product_json_data  # NUEVO v4.5.2
        }
    
    config = {
        'keyword': form_data.keyword,
        'pdp_url': form_data.pdp_url,
        'pdp_data': form_data.pdp_data,  # Datos del producto obtenidos via n8n
        'pdp_json_data': form_data.pdp_json_data,  # JSON del producto principal
        'target_length': form_data.target_length,
        'arquetipo_codigo': form_data.arquetipo,
        'mode': form_data.mode,
        'competitor_urls': form_data.competitor_urls or [],
        'internal_links': internal_links_fmt,
        'pdp_links': pdp_links_fmt,  # Incluye product_data
        'links': all_links,  # Lista combinada para el prompt
        'additional_instructions': form_data.additional_instructions or '',
        'guiding_context': context_from_questions,
        'alternative_product': alternative_product,  # Ahora incluye json_data
        'visual_elements': form_data.visual_elements or [],  # IDs de componentes seleccionados
        'visual_config': form_data.visual_config or {},  # Config completa: selected, variants, components_css
        # NUEVO v5.0: Lista unificada de productos
        'products': [
            {
                'url': p.url,
                'name': p.name,
                'json_data': p.json_data,
                'role': p.role,
            }
            for p in (form_data.products or [])
        ],
        # NUEVO v5.0: Configuración de encabezados
        'headings_config': form_data.headings_config,
        # NUEVO v5.1: Keywords secundarias
        'keywords': [form_data.keyword] + (form_data.secondary_keywords or []),
    }
    
    # REC-6: Resumen pre-generación compacto
    _render_creation_summary(form_data, config)
    
    return True, config


def _render_creation_summary(form_data, config: Dict) -> None:
    """Renderiza resumen compacto de configuración antes de generar."""
    arq_code = form_data.arquetipo
    arq_name = arq_code
    try:
        from config.arquetipos import get_arquetipo
        arq = get_arquetipo(arq_code)
        if arq:
            arq_name = f"{arq_code}: {arq.get('name', arq_code)}"
    except Exception:
        pass
    
    products_list = form_data.products or []
    n_products = len(products_list)
    n_with_json = sum(1 for p in products_list if p.json_data)
    n_links = len(config.get('links', []))
    n_keywords = len(config.get('keywords', [])) - 1  # sin la principal
    n_briefing = len(form_data.guiding_answers or {})
    visuals = config.get('visual_elements', [])
    
    parts = [f"**{form_data.keyword}**", f"{arq_name}", f"~{form_data.target_length} palabras"]
    
    details = []
    if n_products:
        details.append(f"{n_products} producto{'s' if n_products > 1 else ''} ({n_with_json} con JSON)")
    if n_links:
        details.append(f"{n_links} enlace{'s' if n_links > 1 else ''}")
    if n_keywords:
        details.append(f"{n_keywords} keyword{'s' if n_keywords > 1 else ''} secundaria{'s' if n_keywords > 1 else ''}")
    if n_briefing:
        details.append(f"briefing: {n_briefing} respuestas")
    if visuals:
        details.append(f"visual: {', '.join(visuals[:3])}")
    
    summary_line = " | ".join(parts)
    detail_line = " · ".join(details) if details else "Sin datos adicionales"
    
    st.markdown(
        f"""<div style="background:#e8f4f8;border:1px solid #bee5eb;border-radius:6px;padding:10px 14px;margin:8px 0;">
        <div style="font-size:0.95em;">📊 {summary_line}</div>
        <div style="font-size:0.82em;color:#555;margin-top:3px;">{detail_line}</div>
        </div>""",
        unsafe_allow_html=True
    )


# ============================================================================
# UTILIDADES ADICIONALES
# ============================================================================

def get_form_summary(form_data: FormData) -> Dict[str, str]:
    """Genera resumen del formulario para mostrar."""
    return {
        'Keyword': form_data.keyword,
        'URL': form_data.pdp_url or 'No especificada',
        'Longitud': f"{form_data.target_length} palabras",
        'Arquetipo': form_data.arquetipo,
        'Modo': 'Nuevo' if form_data.mode == 'new' else 'Reescritura',
        'Enlaces internos': str(len(form_data.internal_links or [])),
        'Enlaces PDP': str(len(form_data.pdp_links or [])),
    }


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    # Excepciones
    'InputValidationError', 'KeywordValidationError', 'URLValidationError',
    'LengthValidationError', 'LinksValidationError', 'ArquetipoValidationError',
    # Enums y clases
    'InputMode', 'LinkType', 'ProductRole', 'LinkWithAnchor', 'ProductEntry',
    'ValidationResult', 'FormData',
    # Validación
    'validate_keyword', 'validate_url', 'validate_length', 'validate_arquetipo',
    'validate_html_content', 'validate_links_list', 'validate_competitor_urls',
    # Estado
    'get_form_value', 'save_form_data', 'clear_form_data',
    # Componentes UI
    'render_keyword_input', 'render_url_input', 'render_length_slider',
    'render_arquetipo_selector', 'render_mode_selector', 'render_html_input',
    'render_links_with_anchors', 'render_guiding_questions',
    'render_gsc_date_warning', 'render_alternative_product_input',
    'render_competitor_urls_input', 'render_additional_instructions',
    'render_validation_errors', 'render_product_url_with_fetch',
    'render_products_block',
    'get_product_json_data',
    # Formulario principal
    'render_main_form', 'render_content_inputs',
    # Utilidades
    'get_form_summary',
]
