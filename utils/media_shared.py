# -*- coding: utf-8 -*-
"""
UI Media Shared - PcComponentes Content Generator
Version 2.0.0 - 2026-02-15

Componentes de UI compartidos para YouTube embed.

CAMBIOS v2.0.0:
- render_image_generation_section() ELIMINADA (ahora integrada en ui/results.py
  como render_image_generation_tab con soporte completo de seed mode)
- render_youtube_embed_section() MEJORADA: acepta iframe embed code además de URLs

Autor: PcComponentes - Product Discovery & Content
"""

import re
import streamlit as st
import logging
from typing import Optional

logger = logging.getLogger(__name__)

__version__ = "2.0.0"


# ============================================================================
# IMAGEN: REDIRECT A results.py (legacy compat)
# ============================================================================

def render_image_generation_section(
    html_content: str,
    keyword: str = "",
    section_key: str = "default",
) -> None:
    """
    DEPRECATED v2.0 — La generación de imágenes ahora vive en
    ui/results.py → render_image_generation_tab() con soporte completo
    de seed mode, config por imagen, y flujo integrado.
    
    Este stub redirige para compatibilidad si algún módulo externo lo llama.
    """
    try:
        from ui.results import render_image_generation_tab
        render_image_generation_tab(html_content)
    except ImportError:
        st.warning("⚠️ Generación de imágenes no disponible. Usa la sección integrada en Resultados.")


# ============================================================================
# YOUTUBE EMBED (mejorada v2.0 — acepta iframe embed code)
# ============================================================================

def render_youtube_embed_section(
    html_content: str,
    section_key: str = "default",
) -> Optional[str]:
    """
    Renderiza la sección de embed de videos de YouTube.
    
    v2.0: Acepta tanto URLs como código iframe embed copiado desde YouTube.
    
    Args:
        html_content: HTML del artículo
        section_key: Key única para widgets
        
    Returns:
        HTML con videos insertados, o None si no hay cambios
    """
    from utils.youtube_embed import (
        extract_video_id, parse_youtube_url, generate_embed_html,
        insert_videos_in_html, YouTubeVideo, MAX_VIDEOS,
    )
    from utils.image_gen import extract_headings_from_html
    
    st.markdown("---")
    st.markdown("#### 📹 Videos de YouTube")
    
    headings = extract_headings_from_html(html_content) if html_content else []
    heading_options = ["(No asignar)"] + [h['display'] for h in headings]
    heading_map = {h['display']: h for h in headings}
    
    state_key = f"yt_{section_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {'videos': [], 'modified_html': None}
    
    state = st.session_state[state_key]
    
    with st.expander("Configurar videos de YouTube", expanded=False):
        st.caption(
            "Pega la URL de YouTube o el código embed completo copiado desde YouTube "
            "(botón Compartir → Insertar)."
        )
        
        num_videos = st.number_input(
            "Número de videos",
            min_value=0, max_value=MAX_VIDEOS, value=0,
            key=f"yt_count_{section_key}",
        )
        
        videos_config = []
        for i in range(int(num_videos)):
            st.markdown(f"**Video {i+1}**")
            col_url, col_heading = st.columns([2, 1])
            
            with col_url:
                video_input = st.text_area(
                    "URL o código embed de YouTube",
                    key=f"yt_url_{section_key}_{i}",
                    placeholder='https://www.youtube.com/watch?v=... o pega el <iframe ...> completo',
                    height=68,
                )
            
            with col_heading:
                heading_choice = st.selectbox(
                    "Insertar después de",
                    options=heading_options,
                    key=f"yt_heading_{section_key}_{i}",
                )
            
            if video_input and video_input.strip():
                video_input_clean = video_input.strip()
                video_id = None
                embed_title = None
                
                # 1. Intentar extraer de iframe embed code
                iframe_match = re.search(
                    r'src=["\'][^"\']*youtube\.com/embed/([a-zA-Z0-9_-]{11})',
                    video_input_clean,
                )
                if iframe_match:
                    video_id = iframe_match.group(1)
                    title_match = re.search(r'title=["\']([^"\']*)["\']', video_input_clean)
                    if title_match:
                        embed_title = title_match.group(1)
                
                # 2. Intentar como URL normal
                if not video_id:
                    video_id = extract_video_id(video_input_clean)
                
                if video_id:
                    video = parse_youtube_url(f"https://www.youtube.com/watch?v={video_id}")
                    if video:
                        if embed_title:
                            video.title = embed_title
                        
                        display_title = video.title or video_id
                        st.caption(f"✅ Detectado: **{display_title}** (`{video_id}`)")
                        
                        if heading_choice != "(No asignar)":
                            h_data = heading_map.get(heading_choice, {})
                            video.heading_id = h_data.get('id', '')
                            video.heading_text = h_data.get('text', '')
                        
                        videos_config.append(video)
                    else:
                        st.error(f"No se pudo procesar: {video_input_clean[:60]}...")
                else:
                    st.error(f"No se encontró video en: {video_input_clean[:60]}...")
            
            st.markdown("---")
        
        if videos_config:
            # Preview de embeds
            st.markdown("**Preview:**")
            for v in videos_config:
                embed_html = generate_embed_html(v)
                st.markdown(embed_html, unsafe_allow_html=True)
                if v.heading_text:
                    st.caption(f"Se insertará después de: {v.heading_text}")
            
            # Botón para insertar
            if st.button(
                f"📹 Insertar {len(videos_config)} video(s) en el HTML",
                key=f"btn_yt_insert_{section_key}",
                type="primary",
                use_container_width=True,
            ):
                modified = insert_videos_in_html(html_content, videos_config)
                state['videos'] = videos_config
                state['modified_html'] = modified
                st.success(f"✅ {len(videos_config)} video(s) insertados correctamente")
                
                # Ofrecer descarga del HTML modificado
                st.download_button(
                    label="📥 Descargar HTML con videos",
                    data=modified,
                    file_name="content_with_videos.html",
                    mime="text/html",
                    use_container_width=True,
                    key=f"dl_yt_html_{section_key}",
                )
    
    return state.get('modified_html')
