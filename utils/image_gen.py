# -*- coding: utf-8 -*-
"""
Image Generation - PcComponentes Content Generator
Version 2.0.0 - 2026-02-12

Generacion de imagenes contextualizadas con Google Gemini 2.5 Flash Image.
Tipos de imagen:
  - Portada (cover): 1024x576 (16:9), max-width 44rem
  - Cuerpo contextual (body_contextual): 1024x1024, ilustra seccion H2/H3
  - Cuerpo caso de uso (body_use_case): 1024x1024, producto en uso real
  - Infografia (infographic): 1024x1792 (vertical), resumen visual
  - Resumen grafico (summary): 1024x1024, overview del post

Las imagenes NO se insertan en el HTML. Se generan y quedan disponibles
para descarga individual o como ZIP.

Autor: PcComponentes - Product Discovery & Content
"""

import base64
import io
import logging
import os
import re
import time
import zipfile
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

__version__ = "2.0.0"

# ============================================================================
# CONSTANTES DE TAMANIO (del CSS de PcComponentes)
# ============================================================================

# Portada: max-width: 44rem, aspect-ratio: 1024/576
COVER_SIZE = "1024x576"
COVER_ASPECT = "16:9"

# Cuerpo: max-width: 100%, height: auto
BODY_SIZE = "1024x1024"
BODY_ASPECT = "1:1"

# Infografia: vertical
INFOGRAPHIC_SIZE = "1024x1792"
INFOGRAPHIC_ASPECT = "9:16"

# Modelos (Gemini 2.5 Flash Image = "nano-banana", SOTA para generación + edición)
DEFAULT_MODEL = "gemini-2.5-flash-image"
FALLBACK_MODEL = "gemini-2.5-flash-preview-image-generation"

# Rate limiting
DELAY_BETWEEN_GENERATIONS = 1.5


# ============================================================================
# ENUMS Y DATACLASSES
# ============================================================================

class ImageType(str, Enum):
    """Tipo de imagen a generar."""
    COVER = "cover"
    BODY_CONTEXTUAL = "body_contextual"
    BODY_USE_CASE = "body_use_case"
    INFOGRAPHIC = "infographic"
    SUMMARY = "summary"


IMAGE_TYPE_LABELS = {
    ImageType.COVER: "Portada",
    ImageType.BODY_CONTEXTUAL: "Cuerpo - Contextual",
    ImageType.BODY_USE_CASE: "Cuerpo - Caso de uso",
    ImageType.INFOGRAPHIC: "Infografia",
    ImageType.SUMMARY: "Resumen grafico",
}


@dataclass
class ImageRequest:
    """Solicitud de generacion de una imagen."""
    image_type: ImageType
    keyword: str = ""
    heading_id: str = ""
    heading_text: str = ""
    heading_content: str = ""
    extra_instructions: str = ""
    seed_images: List[bytes] = field(default_factory=list)
    width: int = 0   # 0 = usar tamaño por defecto del tipo
    height: int = 0   # 0 = usar tamaño por defecto del tipo
    output_formats: List[str] = field(default_factory=lambda: ["jpeg", "webp"])  # formatos de salida


@dataclass
class GeneratedImage:
    """Una imagen generada."""
    image_bytes: bytes
    prompt_used: str
    image_type: ImageType
    alt_text: str = ""
    mime_type: str = "image/png"
    heading_ref: str = ""
    filename: str = ""
    format_variants: List['ImageFormatVariant'] = field(default_factory=list)

    @property
    def base64_data(self) -> str:
        return base64.b64encode(self.image_bytes).decode('utf-8')

    @property
    def data_uri(self) -> str:
        return f"data:{self.mime_type};base64,{self.base64_data}"

    @property
    def size_kb(self) -> float:
        return len(self.image_bytes) / 1024

    def get_filename(self) -> str:
        if self.filename:
            return self.filename
        ext = _mime_to_ext(self.mime_type)
        safe_ref = re.sub(r'[^a-zA-Z0-9_-]', '_', self.heading_ref or 'img')[:30]
        return f"{self.image_type.value}_{safe_ref}.{ext}"


@dataclass
class ImageFormatVariant:
    """Una variante de formato de una imagen generada."""
    image_bytes: bytes
    mime_type: str
    format_label: str  # "jpeg", "webp", "png"
    width: int = 0
    height: int = 0

    @property
    def size_kb(self) -> float:
        return len(self.image_bytes) / 1024

    def get_filename(self, base_name: str) -> str:
        ext = _mime_to_ext(self.mime_type)
        name = base_name.rsplit('.', 1)[0] if '.' in base_name else base_name
        suffix = f"_{self.width}x{self.height}" if self.width and self.height else ""
        return f"{name}{suffix}.{ext}"


@dataclass
class ImageGenResult:
    """Resultado completo de generacion."""
    images: List[GeneratedImage] = field(default_factory=list)
    success: bool = True
    error: str = ""
    model_used: str = ""
    generation_time: float = 0.0


# ============================================================================
# CLIENTE GEMINI
# ============================================================================

def _get_gemini_client():
    """Obtiene cliente Gemini configurado."""
    try:
        from google import genai
        api_key = os.environ.get('GEMINI_API_KEY', '')
        if not api_key:
            try:
                from config.settings import GEMINI_API_KEY
                api_key = GEMINI_API_KEY
            except (ImportError, AttributeError):
                pass
        if not api_key:
            # Fallback: Streamlit secrets
            try:
                import streamlit as st
                api_key = st.secrets.get('gemini_key', '') or st.secrets.get('GEMINI_API_KEY', '')
            except Exception:
                pass
        if not api_key:
            return None, "GEMINI_API_KEY no configurada"
        return genai.Client(api_key=api_key), ""
    except ImportError:
        return None, "google-genai no instalado. pip install google-genai>=1.0.0"


def is_gemini_available() -> Tuple[bool, str]:
    """Verifica disponibilidad de Gemini."""
    client, error = _get_gemini_client()
    return (client is not None), error


# ============================================================================
# CONVERSIÓN DE FORMATO Y REDIMENSIONADO
# ============================================================================

def _mime_to_ext(mime_type: str) -> str:
    """Convierte mime type a extensión de archivo."""
    return {
        "image/png": "png",
        "image/jpeg": "jpg",
        "image/webp": "webp",
    }.get(mime_type, "png")


def _ext_to_mime(ext: str) -> str:
    """Convierte extensión a mime type."""
    return {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
    }.get(ext.lower(), "image/png")


def _resize_and_convert(
    image_bytes: bytes,
    width: int = 0,
    height: int = 0,
    output_format: str = "png",
    jpeg_quality: int = 85,
    webp_quality: int = 82,
) -> Optional[bytes]:
    """
    Redimensiona y/o convierte una imagen a otro formato.

    Args:
        image_bytes: Bytes de la imagen original
        width: Ancho deseado (0 = mantener proporcional o original)
        height: Alto deseado (0 = mantener proporcional o original)
        output_format: "png", "jpeg" o "webp"
        jpeg_quality: Calidad JPEG (1-95)
        webp_quality: Calidad WebP (1-100)

    Returns:
        Bytes de la imagen convertida o None si falla
    """
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))

        # Redimensionar si se especificó tamaño
        if width > 0 and height > 0:
            img = img.resize((width, height), Image.LANCZOS)
        elif width > 0:
            ratio = width / img.width
            img = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
        elif height > 0:
            ratio = height / img.height
            img = img.resize((int(img.width * ratio), height), Image.LANCZOS)

        # Convertir formato
        buf = io.BytesIO()
        fmt = output_format.upper()
        if fmt == "JPEG" or fmt == "JPG":
            # JPEG no soporta alpha — convertir a RGB
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            img.save(buf, format="JPEG", quality=jpeg_quality, optimize=True)
        elif fmt == "WEBP":
            img.save(buf, format="WEBP", quality=webp_quality, method=4)
        else:
            img.save(buf, format="PNG", optimize=True)

        buf.seek(0)
        return buf.getvalue()

    except ImportError:
        logger.warning("Pillow no disponible para conversión de formato. pip install Pillow")
        return None
    except Exception as e:
        logger.error(f"Error redimensionando/convirtiendo imagen: {e}")
        return None


def convert_image_formats(
    image_bytes: bytes,
    width: int = 0,
    height: int = 0,
    formats: Optional[List[str]] = None,
) -> List['ImageFormatVariant']:
    """
    Genera variantes de una imagen en múltiples formatos y tamaño.

    Args:
        image_bytes: Bytes de la imagen original
        width: Ancho deseado
        height: Alto deseado
        formats: Lista de formatos ("jpeg", "webp", "png")

    Returns:
        Lista de ImageFormatVariant
    """
    if formats is None:
        formats = ["jpeg", "webp"]

    variants = []
    for fmt in formats:
        converted = _resize_and_convert(image_bytes, width, height, fmt)
        if converted:
            # Obtener dimensiones reales
            try:
                from PIL import Image
                img = Image.open(io.BytesIO(converted))
                w, h = img.size
            except Exception:
                w, h = width, height

            variants.append(ImageFormatVariant(
                image_bytes=converted,
                mime_type=_ext_to_mime(fmt),
                format_label=fmt.lower(),
                width=w,
                height=h,
            ))
        else:
            logger.warning(f"No se pudo convertir a {fmt}")

    return variants


# ============================================================================
# EXTRACCION DE HEADINGS DEL HTML
# ============================================================================

def extract_headings_from_html(html_content: str) -> List[Dict[str, str]]:
    """
    Extrae H2 y H3 del HTML con su contenido asociado.
    
    Returns:
        Lista de dicts: level, text, id, content, display
    """
    if not html_content:
        return []

    headings = []
    h_pattern = re.compile(
        r'<(h[23])([^>]*)>(.*?)</\1>',
        re.IGNORECASE | re.DOTALL
    )

    matches = list(h_pattern.finditer(html_content))

    for i, match in enumerate(matches):
        level = match.group(1).lower()
        attrs = match.group(2)
        text_raw = match.group(3)

        text = re.sub(r'<[^>]+>', '', text_raw).strip()

        id_match = re.search(r'id=["\']([^"\']+)["\']', attrs)
        heading_id = id_match.group(1) if id_match else f"{level}_{i}"

        start_pos = match.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(html_content)

        content_html = html_content[start_pos:end_pos]
        content_text = re.sub(r'<[^>]+>', ' ', content_html)
        content_text = re.sub(r'\s+', ' ', content_text).strip()[:500]

        headings.append({
            'level': level,
            'text': text,
            'id': heading_id,
            'content': content_text,
            'display': f"[{level.upper()}] {text}",
        })

    return headings


# ============================================================================
# PROMPTS POR TIPO
# ============================================================================

def _build_cover_prompt(keyword: str, extra: str = "") -> str:
    prompt = (
        f"Create a professional hero/cover image for a web article about '{keyword}'. "
        f"Photorealistic, clean, modern editorial look. Horizontal 16:9 format (1024x576). "
        f"CRITICAL: DO NOT include any text, letters, words, or watermarks in the image. "
        f"The image must work at any size from mobile (320px wide) to desktop (1200px wide). "
        f"Center the main subject with some breathing room on edges for responsive cropping. "
        f"Clean background, studio or environmental lighting, tech/lifestyle editorial style."
    )
    if extra:
        prompt += f" Additional notes: {extra}"
    return prompt


def _build_body_contextual_prompt(
    keyword: str, heading_text: str, heading_content: str, extra: str = ""
) -> str:
    prompt = (
        f"Create a professional image that visually illustrates: '{heading_text}'. "
        f"Article topic: '{keyword}'. "
        f"Section context: '{heading_content[:300]}'. "
        f"Photorealistic, square format (1024x1024). "
        f"CRITICAL: DO NOT include any text, letters, or words. "
        f"The image must look good at any width from 300px to 800px (responsive web). "
        f"Keep the main subject centered with clean composition. "
        f"Editorial style, neutral or contextual background, good contrast."
    )
    if extra:
        prompt += f" Additional notes: {extra}"
    return prompt


def _build_use_case_prompt(
    keyword: str, heading_text: str, heading_content: str, extra: str = ""
) -> str:
    prompt = (
        f"Create a photorealistic image showing the product '{keyword}' "
        f"being used in a real scenario related to: '{heading_text}'. "
        f"Context: '{heading_content[:300]}'. "
        f"Show the product in everyday, realistic use. "
        f"Square format (1024x1024). DO NOT include any text or letters. "
        f"Natural lighting, realistic environment, person or space using the product."
    )
    if extra:
        prompt += f" Additional notes: {extra}"
    return prompt


def _build_infographic_prompt(keyword: str, html_content: str, extra: str = "") -> str:
    headings = extract_headings_from_html(html_content)
    key_points = [h['text'] for h in headings[:8]]
    points_text = ", ".join(key_points) if key_points else keyword

    prompt = (
        f"Create a visual vertical infographic about '{keyword}'. "
        f"Key points to represent visually: {points_text}. "
        f"Vertical format (1024x1792). "
        f"Modern, clean style with simple icons and diagrams. "
        f"Accent colors: orange (#FF6000) and dark blue (#170453). "
        f"White or very light gray background. "
        f"DO NOT include any text or letters. Only visual elements, icons and diagrams."
    )
    if extra:
        prompt += f" Additional notes: {extra}"
    return prompt


def _build_summary_prompt(keyword: str, html_content: str, extra: str = "") -> str:
    headings = extract_headings_from_html(html_content)
    sections = [h['text'] for h in headings if h['level'] == 'h2'][:6]
    sections_text = ", ".join(sections) if sections else keyword

    prompt = (
        f"Create a visual summary image for an article about '{keyword}'. "
        f"Main sections: {sections_text}. "
        f"Square format (1024x1024). "
        f"Flat design or isometric style, visually representing the general topic. "
        f"DO NOT include any text or letters. "
        f"Should communicate at a glance what the article is about. "
        f"Clean, professional colors."
    )
    if extra:
        prompt += f" Additional notes: {extra}"
    return prompt


# ============================================================================
# GENERACION CON GEMINI
# ============================================================================

def _generate_single_image(
    client,
    prompt: str,
    model: str = DEFAULT_MODEL,
    seed_images: Optional[List[bytes]] = None,
) -> Tuple[Optional[bytes], str, str]:
    """
    Genera una sola imagen con Gemini 2.5 Flash Image.
    Soporta hasta 5 seed images para multi-image fusion.
    Returns: (image_bytes, mime_type, error)
    """
    try:
        from google.genai import types

        contents = []
        if seed_images:
            for seed in seed_images[:5]:
                # Detectar mime type por magic bytes
                mime = "image/png"
                if seed[:3] == b'\xff\xd8\xff':
                    mime = "image/jpeg"
                elif seed[:4] == b'RIFF' and seed[8:12] == b'WEBP':
                    mime = "image/webp"
                contents.append(types.Part.from_bytes(
                    data=seed, mime_type=mime
                ))
        contents.append(prompt)

        config = types.GenerateContentConfig(
            response_modalities=['Text', 'Image']
        )

        response = client.models.generate_content(
            model=model, contents=contents, config=config,
        )

        if response.candidates and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data is not None:
                    return (
                        part.inline_data.data,
                        part.inline_data.mime_type or "image/png",
                        ""
                    )

        return None, "", "Gemini no devolvio imagen en la respuesta"

    except Exception as e:
        error_msg = str(e)
        if model == DEFAULT_MODEL and FALLBACK_MODEL != model:
            logger.warning(f"Modelo {model} fallo, intentando {FALLBACK_MODEL}: {error_msg}")
            return _generate_single_image(client, prompt, FALLBACK_MODEL, seed_images)
        return None, "", f"Error generando imagen: {error_msg}"


def generate_images(
    requests: List[ImageRequest],
    html_content: str = "",
) -> ImageGenResult:
    """
    Genera multiples imagenes segun las solicitudes.
    """
    start_time = time.time()

    client, error = _get_gemini_client()
    if not client:
        return ImageGenResult(success=False, error=error)

    result = ImageGenResult(model_used=DEFAULT_MODEL)

    for i, req in enumerate(requests):
        if req.image_type == ImageType.COVER:
            prompt = _build_cover_prompt(req.keyword, req.extra_instructions)
        elif req.image_type == ImageType.BODY_CONTEXTUAL:
            prompt = _build_body_contextual_prompt(
                req.keyword, req.heading_text, req.heading_content, req.extra_instructions
            )
        elif req.image_type == ImageType.BODY_USE_CASE:
            prompt = _build_use_case_prompt(
                req.keyword, req.heading_text, req.heading_content, req.extra_instructions
            )
        elif req.image_type == ImageType.INFOGRAPHIC:
            prompt = _build_infographic_prompt(
                req.keyword, html_content, req.extra_instructions
            )
        elif req.image_type == ImageType.SUMMARY:
            prompt = _build_summary_prompt(
                req.keyword, html_content, req.extra_instructions
            )
        else:
            continue

        # Enriquecer prompt con contexto de seed images
        if req.seed_images:
            seed_prefix = (
                "I'm providing reference image(s). Use them as visual inspiration: "
                "maintain a similar style, color palette, and visual language. "
                "Create a NEW image inspired by these references. "
            )
            prompt = seed_prefix + prompt

        img_bytes, mime, gen_error = _generate_single_image(
            client, prompt,
            seed_images=req.seed_images if req.seed_images else None
        )

        if img_bytes:
            # Redimensionar si se pidieron dimensiones custom
            if req.width > 0 or req.height > 0:
                resized = _resize_and_convert(img_bytes, req.width, req.height, "png")
                if resized:
                    img_bytes = resized

            alt = _build_alt_text(req)
            safe_kw = re.sub(r'[^a-zA-Z0-9]', '_', req.keyword)[:20]
            ext = _mime_to_ext(mime or "image/png")
            fname = f"{req.image_type.value}_{safe_kw}_{i+1}.{ext}"

            # Generar variantes de formato (JPEG, WebP, etc.)
            format_variants = []
            if req.output_formats:
                format_variants = convert_image_formats(
                    img_bytes, req.width, req.height, req.output_formats
                )

            gen_img = GeneratedImage(
                image_bytes=img_bytes,
                prompt_used=prompt,
                image_type=req.image_type,
                alt_text=alt,
                mime_type=mime or "image/png",
                heading_ref=req.heading_text or req.keyword,
                filename=fname,
                format_variants=format_variants,
            )
            result.images.append(gen_img)
            logger.info(f"Imagen {i+1}/{len(requests)} generada: {req.image_type.value}")
        else:
            logger.error(f"Fallo imagen {i+1}: {gen_error}")

        if i < len(requests) - 1:
            time.sleep(DELAY_BETWEEN_GENERATIONS)

    result.generation_time = time.time() - start_time
    if not result.images:
        result.success = False
        result.error = "No se pudo generar ninguna imagen"

    return result


def _build_alt_text(req: ImageRequest) -> str:
    type_labels = {
        ImageType.COVER: "Imagen de portada",
        ImageType.BODY_CONTEXTUAL: "Imagen contextual",
        ImageType.BODY_USE_CASE: "Caso de uso",
        ImageType.INFOGRAPHIC: "Infografia",
        ImageType.SUMMARY: "Resumen visual",
    }
    label = type_labels.get(req.image_type, "Imagen")
    if req.heading_text:
        return f"{label}: {req.heading_text} - {req.keyword}"
    return f"{label}: {req.keyword}"


# ============================================================================
# UTILIDADES DE DESCARGA
# ============================================================================

def create_images_zip(images: List[GeneratedImage]) -> bytes:
    """Crea ZIP con todas las imagenes, incluyendo variantes de formato."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for img in images:
            # Imagen original
            zf.writestr(img.get_filename(), img.image_bytes)
            # Variantes de formato (JPEG, WebP, etc.)
            base_name = img.get_filename()
            for variant in img.format_variants:
                vname = variant.get_filename(base_name)
                if vname != base_name:  # evitar duplicar si mismo formato
                    zf.writestr(vname, variant.image_bytes)
    buffer.seek(0)
    return buffer.getvalue()


# ============================================================================
# COMPATIBILIDAD HACIA ATRAS
# ============================================================================

class ImageGenMode(str, Enum):
    """Deprecated: usar ImageType."""
    AUTO = "auto"
    SEED = "seed"
    INSTRUCTIONS = "instructions"


def insert_images_in_html(html: str, images: list) -> str:
    """Deprecated: imagenes solo para descarga."""
    return html


def generate_content_images(*args, **kwargs) -> ImageGenResult:
    """Deprecated: usar generate_images()."""
    return ImageGenResult(success=False, error="Usar generate_images() con ImageRequest")
