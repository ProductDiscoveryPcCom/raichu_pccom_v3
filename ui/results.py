"""
UI de resultados - PcComponentes Content Generator
Versión 4.2.0

Este módulo maneja la visualización de los resultados de generación de contenido.
Incluye tabs para cada etapa del proceso, validación de estructura HTML v4.1.1,
análisis de word count, y preview del contenido generado.

Autor: PcComponentes - Product Discovery & Content
"""

import streamlit as st
import base64
import html as html_module
import json
import logging
import re
import time as time_mod
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

# Importar utilidades
from utils.html_utils import (
    count_words_in_html,
    extract_content_structure,
    validate_html_structure,
    validate_cms_structure,
    analyze_links,
    detect_ai_phrases,
)


def _get_or_create_generator(api_key: str, model: str, max_tokens: int, temperature: float):
    """Obtiene un ContentGenerator cacheado o crea uno nuevo.

    Evita recrear el cliente de Anthropic (y su connection pool) para cada
    operación de refinamiento/traducción.
    """
    from core.generator import ContentGenerator

    cache_key = f"{api_key}:{model}:{max_tokens}:{temperature}"
    cached = st.session_state.get('_results_generator')
    cached_key = st.session_state.get('_results_generator_key')

    if cached is not None and cached_key == cache_key:
        return cached

    generator = ContentGenerator(
        api_key=api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    st.session_state['_results_generator'] = generator
    st.session_state['_results_generator_key'] = cache_key
    return generator


# ============================================================================
# FUNCIÓN PRINCIPAL DE RENDERIZADO
# ============================================================================

def render_results_section(
    draft_html: Optional[str] = None,
    analysis_json: Optional[str] = None,
    final_html: Optional[str] = None,
    target_length: int = 1500,
    mode: str = "new"
) -> None:
    """
    Renderiza los resultados como flujo lineal (sin tabs de etapas).
    
    Flujo v5.0:
      1. Versión Final (resumen SEO + preview/HTML + copiar)
      2. Refinamiento (integrado, antes en app.py)
      3. Traducción
      4. Multimedia (imágenes Gemini + YouTube embed)
      5. Detalles de generación (stages 1-2 en expander debug)
    
    Solo se muestra la versión final al usuario. Las etapas intermedias
    están disponibles en un expander de debug al final.
    """
    # Si no hay nada, mostrar placeholder
    if not any([draft_html, analysis_json, final_html]):
        st.info("👆 Los resultados aparecerán aquí después de iniciar la generación.")
        return
    
    # Si aún no hay final, mostrar estado parcial durante generación
    if not final_html:
        st.markdown("---")
        st.subheader("Generando contenido...")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            if draft_html:
                st.success("✅ Borrador listo")
            else:
                st.info("⏳ Generando borrador...")
        with col_s2:
            if analysis_json:
                st.success("✅ Análisis listo")
            elif draft_html:
                st.info("⏳ Analizando...")
            else:
                st.caption("Pendiente")
        with col_s3:
            st.caption("Pendiente")
        return
    
    # ================================================================
    # 1. VERSIÓN FINAL
    # ================================================================
    st.markdown("---")
    st.subheader("✅ Contenido Generado")
    
    # Resumen SEO compacto
    _render_seo_summary(final_html, target_length)

    # Quality Score (persistido desde pipeline)
    quality_data = st.session_state.get('quality_score')
    if quality_data and isinstance(quality_data, dict):
        composite = quality_data.get('composite_score', 0)
        emoji = "✅" if composite >= 70 else "⚠️"
        st.markdown(f"**{emoji} Quality Score: {composite}/100**")

    # Preview y HTML (tabs internos solo para formato de visualización)
    render_content_tab(
        html_content=final_html,
        target_length=target_length,
        stage_name="Versión Final",
        stage_number=3,
        is_final=True,
    )
    
    # ================================================================
    # 2. REFINAMIENTO
    # ================================================================
    _render_refinement_section()
    
    # ================================================================
    # 3. TRADUCCIÓN
    # ================================================================
    _render_translation_section(final_html, stage_number=3)

    # ================================================================
    # 4. MULTIMEDIA (imágenes + YouTube)
    # ================================================================
    _render_multimedia_section(final_html)

    # ================================================================
    # 5. DETALLES DE GENERACIÓN (debug, colapsado)
    # ================================================================
    _render_debug_stages(draft_html, analysis_json, mode)


# ============================================================================
# RENDERIZADO DE TAB DE CONTENIDO HTML
# ============================================================================

def render_content_tab(
    html_content: str,
    target_length: int,
    stage_name: str,
    stage_number: int,
    is_final: bool = False
) -> None:
    """
    Renderiza el contenido HTML con preview, validación y acciones.
    
    En v5.0 ya no incluye traducción ni multimedia (movidos al flujo principal).
    """
    
    # Validación CMS (colapsada)
    with st.expander("🔍 Validación de Estructura CMS", expanded=False):
        _render_cms_validation(html_content)
    
    # Preview del contenido renderizado
    preview_tab1, preview_tab2, preview_tab3 = st.tabs(
        ["🎨 Renderizado", "📄 HTML", "📑 Estructura"]
    )
    
    with preview_tab1:
        # Limpiar HTML de posibles marcadores markdown antes de renderizar
        clean_html = html_content
        if clean_html.strip().startswith('```'):
            clean_html = re.sub(r'^```html\s*\n?', '', clean_html.strip(), flags=re.IGNORECASE)
            clean_html = re.sub(r'^```\s*\n?', '', clean_html.strip())
            clean_html = re.sub(r'\n?```\s*$', '', clean_html.strip())

        # Defense-in-depth: strip <script> tags from generated content
        clean_html = re.sub(r'<script[^>]*>.*?</script>', '', clean_html, flags=re.IGNORECASE | re.DOTALL)

        if '<style>' not in clean_html.lower():
            clean_html = _get_basic_css() + clean_html
        
        try:
            import streamlit.components.v1 as components
            preview_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{margin:0;padding:16px;font-family:system-ui,-apple-system,sans-serif;}}</style>
</head><body>
{clean_html}
</body></html>"""
            estimated_height = max(600, min(3000, len(clean_html) // 3))
            components.html(preview_html, height=estimated_height, scrolling=True)
        except Exception:
            st.markdown(clean_html, unsafe_allow_html=True)
    
    with preview_tab2:
        st.text_area(
            "HTML completo (solo lectura) — usa el botón 'Copiar HTML' de abajo",
            value=html_content,
            height=400,
            key=f"html_textarea_{stage_number}",
            disabled=True,
        )
    
    with preview_tab3:
        render_structure_analysis(html_content)
    
    # Botones de acción
    action_cols = st.columns(2)
    
    with action_cols[0]:
        # Nombre descriptivo: keyword + fecha
        _dl_keyword = st.session_state.get('last_config', {}).get('keyword', '')
        _dl_keyword_slug = re.sub(r'[^a-zA-Z0-9]+', '-', _dl_keyword)[:40].strip('-') if _dl_keyword else 'contenido'
        _dl_date = st.session_state.get('timestamp', datetime.now().strftime("%Y%m%d"))
        st.download_button(
            label="📥 Descargar HTML",
            data=html_content,
            file_name=f"{_dl_keyword_slug}_{_dl_date}.html",
            mime="text/html",
            use_container_width=True,
        )
    
    with action_cols[1]:
        # Copiar al portapapeles real via JavaScript
        _escaped = html_module.escape(html_content).replace('`', '\\`').replace('$', '\\$')
        _copy_id = f"copy_btn_{stage_number}"
        _copy_html = f"""
        <button id="{_copy_id}" onclick="
            navigator.clipboard.writeText(document.getElementById('{_copy_id}_data').textContent)
            .then(() => {{
                this.innerText = '✅ Copiado!';
                setTimeout(() => {{ this.innerText = '📋 Copiar HTML'; }}, 3000);
            }})
            .catch(() => {{
                const ta = document.createElement('textarea');
                ta.value = document.getElementById('{_copy_id}_data').textContent;
                document.body.appendChild(ta);
                ta.select();
                document.execCommand('copy');
                document.body.removeChild(ta);
                this.innerText = '✅ Copiado!';
                setTimeout(() => {{ this.innerText = '📋 Copiar HTML'; }}, 3000);
            }});
        " style="width:100%;padding:0.5rem 1rem;background:#FF6000;color:white;border:none;
        border-radius:6px;font-weight:700;font-size:14px;cursor:pointer;font-family:inherit;">
        📋 Copiar HTML</button>
        <div id="{_copy_id}_data" style="display:none;">{_escaped}</div>
        """
        st.components.v1.html(_copy_html, height=42)
    
    # Botón de publicación a CMS (si está configurado)
    try:
        import streamlit as _st_cms
        cms_config = dict(_st_cms.secrets.get("cms", {})) if hasattr(_st_cms.secrets, 'get') else {}
        if not cms_config:
            try:
                cms_config = dict(_st_cms.secrets["cms"])
            except (KeyError, TypeError):
                cms_config = {}
        
        cms_url = cms_config.get("url", "")
        if cms_url:
            if st.button("📤 Publicar como borrador en CMS", key=f"cms_publish_{stage_number}",
                        use_container_width=True, type="secondary"):
                try:
                    from core.cms_publisher import get_publisher_for_config
                    publisher = get_publisher_for_config(cms_config)
                    last_config = st.session_state.get('last_config', {})
                    quality_score_data = st.session_state.get('quality_score', {})
                    meta_seo = st.session_state.get('meta_seo', {})
                    metadata = {
                        'title': last_config.get('keyword', 'Sin título'),
                        'keyword': last_config.get('keyword', ''),
                        'slug': re.sub(r'[^a-z0-9]+', '-', last_config.get('keyword', '').lower()).strip('-'),
                        'arquetipo': last_config.get('arquetipo_codigo', ''),
                        'word_count': st.session_state.get('final_word_count', 0),
                        'quality_score': quality_score_data.get('composite_score', 0),
                        'meta_title': meta_seo.get('meta_title', ''),
                        'meta_description': meta_seo.get('meta_description', ''),
                        'tldr_title': meta_seo.get('tldr_title', ''),
                        'tldr_description': meta_seo.get('tldr_description', ''),
                    }
                    result = publisher.publish_draft(html_content, metadata)
                    if result.success:
                        st.success(f"✅ Publicado como borrador. [Editar en CMS]({result.edit_url or result.post_url})")
                    else:
                        st.error(f"❌ Error al publicar: {result.error}")
                except Exception as e:
                    logger.error(f"Error de publicación: {e}")
                    st.error("❌ Error de publicación. Revisa la configuración del CMS.")
    except Exception:
        pass  # No hay config de CMS, no mostrar botón


# ============================================================================
# RESUMEN SEO COMPACTO (nuevo v5.0)
# ============================================================================

def _render_seo_summary(html_content: str, target_length: int) -> None:
    """Resumen rápido: palabras, headings, elementos visuales, enlaces."""
    word_count = count_words_in_html(html_content)
    diff_pct = ((word_count - target_length) / target_length * 100) if target_length > 0 else 0

    # Contar headings
    h2_count = len(re.findall(r'<h2[\s>]', html_content, re.IGNORECASE))
    h3_count = len(re.findall(r'<h3[\s>]', html_content, re.IGNORECASE))
    h4_count = len(re.findall(r'<h4[\s>]', html_content, re.IGNORECASE))
    
    # Detectar elementos visuales
    html_lower = html_content.lower()
    detected_elements = _detect_visual_elements(html_lower)
    
    # Enlaces
    links_analysis = analyze_links(html_content)
    internal_count = links_analysis.get('internal_links_count', 0)
    external_count = links_analysis.get('external_links_count', 0)
    
    # Métricas principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        emoji = "✅" if abs(diff_pct) <= 5 else ("⚠️" if abs(diff_pct) <= 10 else "❌")
        st.metric(f"{emoji} Palabras", f"{word_count:,}", f"{diff_pct:+.0f}% vs objetivo ({target_length})")
    
    with col2:
        heading_str = f"H2×{h2_count} H3×{h3_count}"
        if h4_count:
            heading_str += f" H4×{h4_count}"
        st.metric("📑 Headings", heading_str)
    
    with col3:
        st.metric("🔗 Enlaces", f"{internal_count} int. / {external_count} ext.")
    
    with col4:
        n_detected = len(detected_elements)
        st.metric("🎨 Elementos", f"{n_detected}")
        if detected_elements:
            st.caption(", ".join(detected_elements[:4]) + (f" (+{n_detected - 4} más)" if n_detected > 4 else ""))
    
    # Detección de frases IA
    ai_phrases = detect_ai_phrases(html_content)
    if ai_phrases:
        n_ai = len(ai_phrases)
        phrases_display = " · ".join(f'"{p["phrase"]}"' for p in ai_phrases[:5])
        if n_ai > 5:
            phrases_display += f" (+{n_ai - 5} más)"
        if n_ai > 2:
            st.warning(
                f"**🤖 {n_ai} expresiones IA detectadas:** {phrases_display}"
            )
        else:
            st.info(
                f"**🤖 {n_ai} expresión{'es' if n_ai > 1 else ''} IA detectada{'s' if n_ai > 1 else ''}:** "
                f"{phrases_display}"
            )


def _detect_visual_elements(html_lower: str) -> List[str]:
    """Detecta elementos visuales presentes en el HTML (lowercase)."""
    checks = {
        'TOC': any(x in html_lower for x in ['class="toc"', "class='toc'", 'nav class="toc']),
        'Callout': any(x in html_lower for x in ['class="callout"', "class='callout'", 'class="callout ']),
        'Callout Promo': any(x in html_lower for x in ['callout-bf', 'bf-callout']),
        'Callout Alerta': 'callout-alert' in html_lower,
        'Verdict': any(x in html_lower for x in ['verdict-box', 'verdict_box']),
        'Tabla': '<table' in html_lower and '</table>' in html_lower,
        'Light Table': 'class="lt ' in html_lower,
        'Tabla Comparación': any(x in html_lower for x in ['comparison-table', 'comparison-highlight']),
        'Mod Cards': 'mod-card' in html_lower,
        'VCard Cards': 'vcard' in html_lower,
        'Compact Cards': any(x in html_lower for x in ['compact-cards', 'compact-card']),
        'Casos de Uso': any(x in html_lower for x in ['use-cases', 'use-case']),
        'FAQs': any(x in html_lower for x in ['contentgenerator__faqs', 'class="faqs', 'faqs__item']),
        'Grid': any(x in html_lower for x in ['class="grid', 'cols-2', 'cols-3']),
        'Badges': 'class="badge' in html_lower,
        'Botones CTA': any(x in html_lower for x in ['class="btn', 'class="btns', 'mod-cta']),
        'Intro': any(x in html_lower for x in ['class="intro"', "class='intro'"]),
        'Check List': 'check-list' in html_lower,
        'Specs List': 'specs-list' in html_lower,
        'Product Module': 'product-module' in html_lower,
        'Price Highlight': 'price-highlight' in html_lower,
        'Stats Grid': any(x in html_lower for x in ['font-size:32px', 'font-size: 32px']),
        'Section Divider': 'linear-gradient(135deg,#170453' in html_lower,
        'Video': 'video-container' in html_lower or ('iframe' in html_lower and 'youtube' in html_lower),
    }
    return [name for name, found in checks.items() if found]


# ============================================================================
# VALIDACIÓN CMS (nuevo v5.0 — extraído de render_content_tab)
# ============================================================================

def _render_cms_validation(html_content: str) -> None:
    """Validación completa de estructura CMS, ahora en expander colapsable."""
    is_valid, errors, warnings = validate_cms_structure(html_content)
    
    if is_valid and not warnings:
        st.success("✅ Estructura perfecta: cumple todos los requisitos del CMS")
    elif is_valid and warnings:
        st.warning(f"⚠️ Estructura válida con {len(warnings)} advertencia(s)")
    else:
        st.error(f"❌ Estructura inválida: {len(errors)} error(es) crítico(s)")
    
    if errors:
        for i, error in enumerate(errors, 1):
            st.markdown(f"🔴 **{i}.** {error}")
    
    if warnings:
        with st.expander(f"⚠️ {len(warnings)} advertencias", expanded=False):
            for i, warning in enumerate(warnings, 1):
                st.markdown(f"**{i}.** {warning}")
    
    basic_validation = validate_html_structure(html_content)
    
    validation_cols = st.columns(3)
    
    with validation_cols[0]:
        st.markdown("**Estructura HTML:**")
        render_validation_check("Tiene <article> (wrapper CMS)", basic_validation.get('has_article', False))
        render_validation_check("CSS con :root (variables)", basic_validation.get('css_has_root', False))
        render_validation_check("Sin Markdown (HTML puro)", basic_validation.get('no_markdown', False))
    
    with validation_cols[1]:
        st.markdown("**Elementos clave:**")
        render_validation_check("Kicker con <span> (etiqueta)", basic_validation.get('kicker_uses_span', False))
        render_validation_check("Callout BF (promo)", basic_validation.get('has_bf_callout', False))
        render_validation_check("Verdict Box (conclusión)", basic_validation.get('has_verdict_box', False))
    
    with validation_cols[2]:
        st.markdown("**Enlaces:**")
        links_analysis = analyze_links(html_content)
        internal_count = links_analysis.get('internal_links_count', 0)
        external_count = links_analysis.get('external_links_count', 0)
        render_validation_check(f"Internos ({internal_count})", internal_count >= 1)
        render_validation_check(f"Externos ({external_count})", external_count >= 0)
    
    # Elementos visuales detectados
    html_lower = html_content.lower()
    detected = _detect_visual_elements(html_lower)
    common_check = ['Tabla', 'FAQs', 'Verdict']
    missing_common = [name for name in common_check if name not in detected]
    
    if detected:
        st.markdown("**Elementos visuales detectados:**")
        st.markdown(" · ".join(f"✅ {name}" for name in detected))
    
    if missing_common:
        st.markdown(" · ".join(f"❌ {name}" for name in missing_common))


# ============================================================================
# REFINAMIENTO (movido de app.py a results.py en v5.0)
# ============================================================================

def _render_refinement_section() -> None:
    """Refinamiento con prompt libre + undo, integrado en el flujo de resultados."""
    if not st.session_state.get('final_html'):
        return
    
    st.markdown("---")
    st.markdown("#### ✨ Refinamiento")
    st.caption("Pide cambios puntuales al contenido generado sin regenerarlo desde cero.")

    # Mostrar feedback del último refinamiento (persiste tras rerun)
    feedback = st.session_state.pop('_refinement_feedback', None)
    if feedback and feedback.get('success'):
        st.success("✅ Contenido refinado correctamente")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Antes", f"{feedback['old_words']} palabras")
        with col2:
            st.metric("Después", f"{feedback['new_words']} palabras")
        with col3:
            st.metric("Diferencia", f"{feedback['diff']:+d}")
        
        if feedback.get('changes'):
            with st.expander("📋 Cambios realizados", expanded=True):
                for change in feedback['changes']:
                    if change:
                        st.markdown(f"✅ {change}")
    
    refine_prompt = st.text_area(
        "Instrucciones de mejora",
        placeholder="Ej: Amplía la sección de FAQs, hazlo más técnico, reduce la intro...",
        height=80,
        key="refine_prompt_input",
        label_visibility="collapsed",
    )
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        if st.button("🚀 Aplicar mejora", type="primary", use_container_width=True, key="btn_apply_refinement"):
            if refine_prompt.strip():
                _execute_refinement(refine_prompt)
            else:
                st.warning("⚠️ Escribe instrucciones de refinamiento")
    
    with col2:
        _render_undo_button()


def _execute_refinement(refine_prompt: str) -> None:
    """Ejecuta refinamiento del contenido con Claude."""
    try:
        from core.generator import ContentGenerator
        from core.config import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE
    except ImportError as e:
        logger.error(f"Módulos no disponibles: {e}")
        st.error("❌ Módulos de generación no disponibles. Verifica la instalación.")
        return
    
    try:
        from core.generator import extract_html_content
    except ImportError:
        def extract_html_content(content):
            content = content.strip()
            content = re.sub(r'^```html?\s*\n?', '', content, flags=re.IGNORECASE)
            content = re.sub(r'^```\s*\n?', '', content)
            content = re.sub(r'\n?```\s*$', '', content)
            return content.strip()
    
    current_content = st.session_state.final_html
    current_word_count = count_words_in_html(current_content)
    
    # Enriquecer con contexto de generación si disponible
    gen_meta = st.session_state.get('generation_metadata', {})
    gen_config = gen_meta.get('config', {})
    
    context_section = ""
    ctx_parts = []
    
    keyword = gen_config.get('keyword', '')
    if keyword:
        ctx_parts.append(f"- **Keyword principal:** {keyword}")
    
    arquetipo_code = gen_meta.get('arquetipo', '')
    if arquetipo_code:
        try:
            from config.arquetipos import ARQUETIPOS
            arq = ARQUETIPOS.get(arquetipo_code, {})
            arq_name = arq.get('name', arquetipo_code)
            arq_tone = arq.get('tone', '')
            ctx_parts.append(f"- **Tipo de contenido:** {arq_name}")
            if arq_tone:
                ctx_parts.append(f"- **Tono del arquetipo:** {arq_tone}")
        except ImportError:
            ctx_parts.append(f"- **Arquetipo:** {arquetipo_code}")
    
    visual_elems = gen_config.get('visual_elements', [])
    if visual_elems:
        ctx_parts.append(f"- **Elementos visuales seleccionados:** {', '.join(visual_elems)}")
    
    target_len = gen_config.get('target_length', gen_meta.get('target_length', 0))
    if target_len:
        ctx_parts.append(f"- **Longitud objetivo:** ~{target_len} palabras")
    
    sec_kws = gen_config.get('keywords', [])
    if sec_kws:
        ctx_parts.append(f"- **Keywords secundarias:** {', '.join(sec_kws[:8])}")
    
    if ctx_parts:
        context_section = "\n## CONTEXTO DE GENERACIÓN\n" + "\n".join(ctx_parts) + "\n"
    
    # Importar ejemplos de tono para refinement
    try:
        from prompts.brand_tone import EJEMPLOS_TONO_STAGE3
    except ImportError:
        EJEMPLOS_TONO_STAGE3 = ""
    
    refinement_prompt = f"""Eres un editor experto en contenido SEO para PcComponentes.
Tu tarea es refinar el contenido existente según las instrucciones del usuario.
{context_section}
REGLAS:
1. Mantén el formato HTML válido y las clases CSS
2. Preserva TODOS los enlaces internos existentes
3. Mantén aproximadamente la misma longitud ({current_word_count} palabras ±10%)
4. Mejora según las instrucciones sin perder información valiosa
5. Mantén el tono de marca PcComponentes (experto, cercano, confiable)
6. NO uses frases negativas como "evita este producto" - usa alternativas positivas
7. NO uses marcadores markdown (```html)

{EJEMPLOS_TONO_STAGE3}

---

CONTENIDO ACTUAL:
{current_content}

---

INSTRUCCIONES DE REFINAMIENTO:
{refine_prompt}

---

IMPORTANTE: 
1. Al finalizar, lista los CAMBIOS REALIZADOS en un comentario HTML al final:
<!-- CAMBIOS_REALIZADOS:
- Cambio 1
- Cambio 2
-->

2. Genera el contenido refinado aplicando los cambios solicitados.
3. Responde SOLO con el HTML mejorado (empezando con <style> o <article>)."""

    with st.spinner("🤖 Claude está refinando el contenido..."):
        try:
            generator = _get_or_create_generator(
                CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE,
            )

            # System prompt con personalidad PcComponentes (igual que Stage 3)
            system_prompt = None
            try:
                from prompts.brand_tone import get_system_prompt_base
                system_prompt = get_system_prompt_base()
            except ImportError:
                pass
            
            result = generator.generate(refinement_prompt, system_prompt=system_prompt)
            
            if not result.success:
                st.error(f"❌ Error en refinamiento: {result.error}")
                return
            
            refined_content = result.content
            if not refined_content or len(refined_content) < 100:
                st.error("❌ El contenido refinado está vacío o es muy corto")
                return
            
            # Extraer cambios
            changes_match = re.search(r'<!-- CAMBIOS_REALIZADOS:(.*?)-->', refined_content, re.DOTALL)
            changes_list = []
            if changes_match:
                changes_text = changes_match.group(1).strip()
                changes_list = [line.strip().lstrip('- ') for line in changes_text.split('\n') if line.strip()]
                refined_content = re.sub(r'<!-- CAMBIOS_REALIZADOS:.*?-->', '', refined_content, flags=re.DOTALL)
            
            # Validar que el refinement devolvió HTML COMPLETO (no parcial)
            cleaned_refined = extract_html_content(refined_content)
            original_len = len(current_content)
            refined_len = len(cleaned_refined)
            had_style = '<style' in current_content.lower()
            has_style = '<style' in cleaned_refined.lower()
            
            if refined_len < original_len * 0.4:
                st.error(
                    f"❌ El contenido refinado es demasiado corto ({refined_len} chars vs "
                    f"{original_len} original). Claude puede haber devuelto solo una sección parcial. "
                    f"Tu contenido original no se ha modificado. Inténtalo de nuevo con instrucciones más específicas."
                )
                return
            
            if had_style and not has_style:
                st.warning(
                    "⚠️ El contenido refinado no incluye el bloque `<style>`. "
                    "Se conservará el CSS original."
                )
                # Recuperar <style>...</style> del original y prepend
                style_match = re.search(r'<style[^>]*>.*?</style>', current_content, re.DOTALL | re.IGNORECASE)
                if style_match:
                    cleaned_refined = style_match.group(0) + '\n\n' + cleaned_refined
            
            # Guardar historial
            if 'content_history' not in st.session_state:
                st.session_state.content_history = []

            st.session_state.content_history.append({
                'content': current_content,
                'timestamp': datetime.now().isoformat(),
                'word_count': current_word_count,
            })
            
            # Actualizar contenido
            st.session_state.final_html = cleaned_refined
            new_word_count = count_words_in_html(st.session_state.final_html)
            diff = new_word_count - current_word_count
            
            # Persistir feedback para mostrar tras rerun
            st.session_state['_refinement_feedback'] = {
                'success': True,
                'old_words': current_word_count,
                'new_words': new_word_count,
                'diff': diff,
                'changes': changes_list,
            }
            
            st.rerun()
            
        except Exception as e:
            logger.error(f"Error en refinamiento: {e}")
            st.error("❌ Error durante el refinamiento. Inténtalo de nuevo.")


def _render_undo_button() -> None:
    """Botón de deshacer último refinamiento."""
    history = st.session_state.get('content_history', [])
    
    if not history:
        st.button("↩️ Deshacer", disabled=True, use_container_width=True, key="btn_undo_disabled")
        return

    n_history = len(history)
    if st.button(f"↩️ Deshacer ({n_history})", use_container_width=True, key="btn_undo_active", help=f"{n_history} versión{'es' if n_history > 1 else ''} en historial"):
        last_version = history.pop()
        st.session_state.final_html = last_version['content']
        st.success("✅ Versión anterior restaurada")
        st.rerun()


# ============================================================================
# MULTIMEDIA: IMÁGENES + YOUTUBE (nuevo v5.0)
# ============================================================================

def _render_multimedia_section(html_content: str) -> None:
    """Sección de multimedia: imágenes Gemini + YouTube embed + editor de enlaces."""
    st.markdown("---")
    st.markdown("#### 🎬 Multimedia e Imágenes")
    st.caption("Edita imágenes, genera nuevas con IA o inserta vídeos de YouTube.")

    with st.expander("🔗 Editar imágenes y enlaces", expanded=False):
        _render_image_link_editor(html_content)

    with st.expander("🖼️ Generar imágenes con IA", expanded=False):
        render_image_generation_tab(html_content)

    with st.expander("📹 Insertar vídeo YouTube", expanded=False):
        _render_youtube_embed(html_content)


def _render_image_link_editor(html_content: str) -> None:
    """
    Editor post-generación para imágenes y enlaces CTA del HTML.

    Permite:
    - Cambiar src de imágenes (mod-figure, product-module, etc.)
    - Cambiar href de CTAs y enlaces de producto
    - Preview en tiempo real
    """
    if not html_content:
        st.caption("No hay contenido para editar.")
        return
    
    st.caption(
        "Edita las URLs de imágenes y enlaces de producto generados. "
        "Los cambios se aplican directamente al HTML final."
    )
    
    # Extraer imágenes
    img_pattern = re.compile(
        r'<img[^>]+src=["\']([^"\']+)["\'][^>]*alt=["\']([^"\']*)["\']',
        re.IGNORECASE
    )
    # También capturar alt antes de src
    img_pattern2 = re.compile(
        r'<img[^>]+alt=["\']([^"\']*)["\'][^>]*src=["\']([^"\']+)["\']',
        re.IGNORECASE
    )
    
    images = []
    for m in img_pattern.finditer(html_content):
        images.append({"src": m.group(1), "alt": m.group(2), "full": m.group(0)})
    for m in img_pattern2.finditer(html_content):
        src, alt = m.group(2), m.group(1)
        if not any(i["src"] == src for i in images):
            images.append({"src": src, "alt": alt, "full": m.group(0)})
    
    # Extraer TODOS los enlaces <a href="...">
    # Captura href y texto de cualquier enlace, clasificando por tipo
    all_link_pattern = re.compile(
        r'<a\s[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL
    )
    class_pattern = re.compile(r'class=["\']([^"\']*)["\']', re.IGNORECASE)
    
    # Clasificar enlaces
    cta_classes = {'mod-cta', 'btn', 'primary', 'product-module', 'vcard__cta'}
    ctas = []      # CTAs y botones
    links = []     # Enlaces inline (editoriales, categorías, productos)
    seen_hrefs = set()
    
    for m in all_link_pattern.finditer(html_content):
        href = m.group(1)
        full_tag = m.group(0)
        text = re.sub(r'<[^>]+>', '', m.group(2)).strip()
        
        # Deduplicar por href+text
        dedup_key = f"{href}|{text}"
        if dedup_key in seen_hrefs:
            continue
        seen_hrefs.add(dedup_key)
        
        # Ignorar anchors internos (#seccion) y javascript:
        if href.startswith('#') or href.startswith('javascript:'):
            continue
        
        entry = {"href": href, "text": text, "full": full_tag}
        
        # Clasificar por clase CSS
        cls_match = class_pattern.search(full_tag)
        classes = set(cls_match.group(1).split()) if cls_match else set()
        
        if classes & cta_classes:
            ctas.append(entry)
        else:
            links.append(entry)
    
    if not images and not ctas and not links:
        st.info("No se detectaron imágenes ni enlaces editables en el contenido.")
        return
    
    changes_made = False
    new_html = html_content
    
    # ── Imágenes ──
    if images:
        st.markdown("**🖼️ Imágenes**")
        for i, img in enumerate(images):
            col_alt, col_src = st.columns([1, 3])
            with col_alt:
                st.caption(img["alt"][:40] or f"Imagen {i+1}")
            with col_src:
                new_src = st.text_input(
                    f"URL imagen {i+1}",
                    value=img["src"],
                    key=f"img_edit_src_{i}",
                    label_visibility="collapsed",
                )
                if new_src != img["src"]:
                    # Replace only within src="..." context to avoid collateral matches
                    new_html = new_html.replace(f'src="{img["src"]}"', f'src="{new_src}"', 1)
                    new_html = new_html.replace(f"src='{img['src']}'", f"src='{new_src}'", 1)
                    changes_made = True
    
    # ── CTAs / Botones ──
    if ctas:
        st.markdown("**🔗 CTAs y botones**")
        for i, cta in enumerate(ctas):
            col_text, col_href = st.columns([1, 3])
            with col_text:
                st.caption(cta["text"][:40] or f"CTA {i+1}")
            with col_href:
                new_href = st.text_input(
                    f"URL CTA {i+1}",
                    value=cta["href"],
                    key=f"cta_edit_href_{i}",
                    label_visibility="collapsed",
                )
                if new_href != cta["href"]:
                    new_html = new_html.replace(
                        f'href="{cta["href"]}"',
                        f'href="{new_href}"',
                        1,
                    )
                    changes_made = True

    # ── Enlaces inline (editoriales, categorías, productos) ──
    if links:
        st.markdown("**📝 Enlaces en el contenido**")
        for i, link in enumerate(links):
            col_text, col_href = st.columns([1, 3])
            with col_text:
                st.caption(link["text"][:40] or f"Enlace {i+1}")
            with col_href:
                new_href = st.text_input(
                    f"URL enlace {i+1}",
                    value=link["href"],
                    key=f"link_edit_href_{i}",
                    label_visibility="collapsed",
                )
                if new_href != link["href"]:
                    new_html = new_html.replace(
                        f'href="{link["href"]}"',
                        f'href="{new_href}"',
                        1,
                    )
                    changes_made = True
    
    # ── Aplicar cambios ──
    if changes_made:
        if st.button("✅ Aplicar cambios al HTML", type="primary", use_container_width=True, key="btn_apply_link_edits"):
            st.session_state.final_html = new_html
            st.success("✅ Enlaces actualizados en el HTML final")
            st.rerun()


def _render_youtube_embed(html_content: str) -> None:
    """
    UI para insertar videos de YouTube desde embed code o URL.
    
    Acepta:
    - URLs normales: https://www.youtube.com/watch?v=xxx
    - URLs cortas: https://youtu.be/xxx
    - Código embed completo: <iframe ... src="https://www.youtube.com/embed/xxx" ...>
    """
    
    try:
        from utils.youtube_embed import (
            extract_video_id, parse_youtube_url, generate_embed_html,
            insert_videos_in_html, YouTubeVideo, MAX_VIDEOS,
        )
        from utils.image_gen import extract_headings_from_html
    except ImportError:
        st.warning("⚠️ Módulo de YouTube no disponible.")
        return
    
    headings = extract_headings_from_html(html_content) if html_content else []
    heading_options = ["(No asignar)"] + [h['display'] for h in headings]
    heading_map = {h['display']: h for h in headings}
    
    st.caption(
        "Pega la URL de YouTube o el código embed completo copiado desde YouTube. "
        "El video se insertará en el HTML del contenido."
    )
    
    num_videos = st.number_input(
        "Número de videos",
        min_value=0, max_value=MAX_VIDEOS, value=0,
        key="yt_count_final",
    )
    
    videos_config = []
    for i in range(int(num_videos)):
        st.markdown(f"**Video {i+1}**")
        col_url, col_heading = st.columns([2, 1])
        
        with col_url:
            video_input = st.text_area(
                "URL o código embed de YouTube",
                key=f"yt_input_final_{i}",
                placeholder='https://www.youtube.com/watch?v=... o pega el <iframe ...> completo',
                height=68,
            )
        
        with col_heading:
            heading_choice = st.selectbox(
                "Insertar después de",
                options=heading_options,
                key=f"yt_heading_final_{i}",
            )
        
        if video_input and video_input.strip():
            video_input_clean = video_input.strip()
            video_id = None
            embed_title = None
            
            # 1. Intentar extraer de iframe embed code
            iframe_match = re.search(
                r'src="[^"]*youtube\.com/embed/([a-zA-Z0-9_-]{11})',
                video_input_clean
            )
            if iframe_match:
                video_id = iframe_match.group(1)
                title_match = re.search(r'title="([^"]*)"', video_input_clean)
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
                st.error(f"No se encontró video_id en: {video_input_clean[:60]}...")
        
        st.markdown("---")
    
    if videos_config:
        st.markdown("**Preview:**")
        for v in videos_config:
            embed_html = generate_embed_html(v)
            st.markdown(embed_html, unsafe_allow_html=True)
            if v.heading_text:
                st.caption(f"Se insertará después de: {v.heading_text}")
        
        if st.button(
            f"📹 Insertar {len(videos_config)} video(s) en el HTML",
            key="btn_yt_insert_final",
            type="primary",
            use_container_width=True,
        ):
            modified = insert_videos_in_html(html_content, videos_config)
            st.session_state.final_html = modified
            st.success(f"✅ {len(videos_config)} video(s) insertados en el contenido")
            st.rerun()


# ============================================================================
# DEBUG: STAGES INTERMEDIOS (nuevo v5.0)
# ============================================================================

def _render_debug_stages(
    draft_html: Optional[str],
    analysis_json: Optional[str],
    mode: str,
) -> None:
    """Muestra stages 1-2 en expander colapsado para debug."""
    if not draft_html and not analysis_json:
        return
    
    with st.expander("🔧 Detalles de generación (stages intermedios)", expanded=False):
        if draft_html:
            st.markdown("**📝 Etapa 1 — Borrador:**")
            draft_words = count_words_in_html(draft_html)
            st.caption(f"{draft_words:,} palabras")
            with st.expander("Ver HTML del borrador", expanded=False):
                st.code(draft_html[:2000] + ("..." if len(draft_html) > 2000 else ""),
                         language="html")
        
        if analysis_json:
            st.markdown("**🔍 Etapa 2 — Análisis Crítico:**")
            render_analysis_tab(analysis_json, mode)


# ============================================================================
# SECCIÓN DE TRADUCCIÓN
# ============================================================================

def _render_translation_section(html_content: str, stage_number: int) -> None:
    """
    Renderiza la UI de traducción contextualizada del contenido final.
    Soporta traducción individual, por lotes, y generación de meta SEO en idioma destino.
    """
    try:
        from utils.translation import get_supported_languages, build_translation_prompt
    except ImportError:
        return

    st.markdown("---")
    st.markdown("#### 🌍 Traducción Contextualizada")
    st.caption(
        "Traducción adaptada al país de destino, no literal. "
        "Adapta tono, expresiones, formato de precios y terminología técnica."
    )

    languages = get_supported_languages()

    # Detectar idioma origen del contenido (por defecto es)
    source_lang = st.session_state.get('content_source_lang', 'es')

    # Idiomas destino = todos excepto el origen
    target_languages = {k: v for k, v in languages.items() if k != source_lang}

    # Mostrar badges de traducciones ya realizadas
    existing_translations = []
    for code, cfg in target_languages.items():
        if st.session_state.get(f'translated_html_{code}'):
            existing_translations.append(f"{cfg.flag} {cfg.name}")

    if existing_translations:
        st.info(f"**Traducciones disponibles:** {' · '.join(existing_translations)}")

    # Selector de idioma + botón traducir + botón batch
    lang_options = {f"{cfg.flag} {cfg.name} ({cfg.country})": code for code, cfg in target_languages.items()}

    col_lang, col_btn, col_batch = st.columns([3, 1, 1])

    with col_lang:
        selected_label = st.selectbox(
            "Idioma destino",
            options=list(lang_options.keys()),
            key=f"translate_lang_{stage_number}",
            label_visibility="collapsed",
        )
        selected_code = lang_options[selected_label]

    with col_btn:
        already_translated = bool(st.session_state.get(f'translated_html_{selected_code}'))
        btn_label = "🔄 Re-traducir" if already_translated else "🌐 Traducir"

        translate_clicked = st.button(
            btn_label,
            type="primary",
            use_container_width=True,
            key=f"btn_translate_{stage_number}",
        )

    with col_batch:
        # Contar cuántos faltan por traducir
        pending_count = sum(
            1 for code in target_languages
            if not st.session_state.get(f'translated_html_{code}')
        )
        batch_clicked = st.button(
            f"🌐 Todos ({pending_count})" if pending_count > 0 else "✅ Todos listos",
            type="secondary",
            use_container_width=True,
            key=f"btn_translate_all_{stage_number}",
            disabled=pending_count == 0,
        )

    # Mostrar feedback de traducción reciente
    feedback = st.session_state.pop('_translation_feedback', None)
    if feedback:
        if feedback.get('success'):
            st.success(f"✅ Traducción a {feedback['lang_name']} completada ({feedback['word_count']} palabras)")
        else:
            st.error(f"❌ Error en traducción: {feedback['error']}")

    # Feedback de batch
    batch_feedback = st.session_state.pop('_batch_translation_feedback', None)
    if batch_feedback:
        ok = batch_feedback.get('completed', [])
        fail = batch_feedback.get('failed', [])
        if ok:
            st.success(f"✅ Traducciones completadas: {', '.join(ok)}")
        if fail:
            st.error(f"❌ Errores en: {', '.join(fail)}")

    # Ejecutar traducción individual
    if translate_clicked:
        _execute_translation(html_content, selected_code, stage_number, source_lang=source_lang)

    # Ejecutar traducción por lotes
    if batch_clicked and pending_count > 0:
        _execute_batch_translation(html_content, target_languages, stage_number, source_lang=source_lang)

    # Mostrar traducción si existe para el idioma seleccionado
    translation_key = f'translated_html_{selected_code}'
    if st.session_state.get(translation_key):
        lang_cfg = target_languages[selected_code]
        translated = st.session_state[translation_key]

        with st.expander(f"📄 {lang_cfg.flag} Traducción a {lang_cfg.name}", expanded=True):
            # Mostrar meta SEO traducida si existe
            meta_key = f'translated_meta_{selected_code}'
            translated_meta = st.session_state.get(meta_key)
            if translated_meta:
                st.markdown("##### 🏷️ Meta SEO")
                _tm = translated_meta
                st.markdown(f"**Meta title** ({len(_tm.get('meta_title', ''))} chars)")
                st.code(_tm.get('meta_title', ''), language=None)
                st.markdown(f"**Meta description** ({len(_tm.get('meta_description', ''))} chars)")
                st.code(_tm.get('meta_description', ''), language=None)
                st.markdown(f"**TL;DR title** ({len(_tm.get('tldr_title', ''))} chars)")
                st.code(_tm.get('tldr_title', ''), language=None)
                st.markdown(f"**TL;DR description** ({len(_tm.get('tldr_description', ''))} chars)")
                st.code(_tm.get('tldr_description', ''), language=None)
                st.markdown("---")

            tr_tab1, tr_tab2 = st.tabs(["🎨 Preview", "📄 HTML"])

            with tr_tab1:
                clean = translated
                if '<style>' not in clean.lower():
                    clean = _get_basic_css() + clean
                st.markdown(clean, unsafe_allow_html=True)

            with tr_tab2:
                st.code(translated, language="html", line_numbers=True)

            dl_col1, dl_col2 = st.columns(2)
            with dl_col1:
                tr_words = count_words_in_html(translated)
                st.metric(f"Palabras ({lang_cfg.name})", tr_words)

            with dl_col2:
                st.download_button(
                    label=f"📥 Descargar {lang_cfg.flag} HTML",
                    data=translated,
                    file_name=f"content_{selected_code}_{st.session_state.get('timestamp', 'export')}.html",
                    mime="text/html",
                    use_container_width=True,
                    key=f"dl_translated_{selected_code}_{stage_number}",
                )


def _execute_translation(
    html_content: str, target_lang: str, stage_number: int,
    source_lang: str = "es",
) -> None:
    """Ejecuta la traducción del contenido usando Claude + genera meta SEO en idioma destino."""
    from utils.translation import build_translation_prompt, get_language

    lang = get_language(target_lang)
    if not lang:
        st.session_state['_translation_feedback'] = {
            'success': False, 'error': f"Idioma no soportado: {target_lang}"
        }
        st.rerun()
        return

    keyword = st.session_state.get('generation_metadata', {}).get('keyword', '')

    with st.spinner(f"Traduciendo a {lang.flag} {lang.name}... (adaptación contextualizada)"):
        try:
            from core.generator import extract_html_content
            from core.config import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS

            generator = _get_or_create_generator(
                CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, 0.3,
            )

            system_prompt, user_prompt = build_translation_prompt(
                html_content=html_content,
                target_lang=target_lang,
                keyword=keyword,
                source_lang=source_lang,
            )

            result = generator.generate(user_prompt, system_prompt=system_prompt)

            if result.success and result.content:
                translated = extract_html_content(result.content)

                if not translated or len(translated) < 100:
                    st.session_state['_translation_feedback'] = {
                        'success': False, 'error': "El contenido traducido está vacío o muy corto"
                    }
                    st.rerun()
                    return

                st.session_state[f'translated_html_{target_lang}'] = translated

                # Generar meta SEO en el idioma destino
                _generate_translated_meta(translated, keyword, target_lang)

                tr_words = count_words_in_html(translated)
                st.session_state['_translation_feedback'] = {
                    'success': True,
                    'lang_name': f"{lang.flag} {lang.name}",
                    'word_count': tr_words,
                }
            else:
                st.session_state['_translation_feedback'] = {
                    'success': False, 'error': result.error or "Respuesta vacía de Claude"
                }

        except ImportError as e:
            st.session_state['_translation_feedback'] = {
                'success': False, 'error': f"Módulos no disponibles: {e}"
            }
        except Exception as e:
            logger.error(f"Error en traducción: {e}")
            st.session_state['_translation_feedback'] = {
                'success': False, 'error': str(e)
            }

    st.rerun()


def _execute_batch_translation(
    html_content: str,
    target_languages: dict,
    stage_number: int,
    source_lang: str = "es",
) -> None:
    """Traduce el contenido a todos los idiomas pendientes secuencialmente."""
    from utils.translation import build_translation_prompt, get_language

    keyword = st.session_state.get('generation_metadata', {}).get('keyword', '')
    completed = []
    failed = []

    pending = [code for code in target_languages if not st.session_state.get(f'translated_html_{code}')]
    progress_bar = st.progress(0, text="Iniciando traducciones...")

    for i, target_lang in enumerate(pending):
        lang = get_language(target_lang)
        if not lang:
            failed.append(target_lang)
            continue

        progress_bar.progress(
            (i) / len(pending),
            text=f"Traduciendo a {lang.flag} {lang.name}... ({i+1}/{len(pending)})",
        )

        try:
            from core.generator import extract_html_content
            from core.config import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS

            generator = _get_or_create_generator(
                CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, 0.3,
            )

            system_prompt, user_prompt = build_translation_prompt(
                html_content=html_content,
                target_lang=target_lang,
                keyword=keyword,
                source_lang=source_lang,
            )

            result = generator.generate(user_prompt, system_prompt=system_prompt)

            if result.success and result.content:
                translated = extract_html_content(result.content)
                if translated and len(translated) >= 100:
                    st.session_state[f'translated_html_{target_lang}'] = translated
                    _generate_translated_meta(translated, keyword, target_lang)
                    completed.append(f"{lang.flag} {lang.name}")
                else:
                    failed.append(f"{lang.flag} {lang.name}")
            else:
                failed.append(f"{lang.flag} {lang.name}")

        except Exception as e:
            logger.error(f"Batch translation error ({target_lang}): {e}")
            failed.append(f"{lang.flag} {lang.name}")

    progress_bar.progress(1.0, text="Traducciones completadas")

    st.session_state['_batch_translation_feedback'] = {
        'completed': completed,
        'failed': failed,
    }
    st.rerun()


def _generate_translated_meta(
    translated_html: str, keyword: str, target_lang: str,
) -> None:
    """Genera meta SEO (title, description, TLDR) en el idioma destino."""
    try:
        from utils.meta_generator import generate_meta
        meta = generate_meta(
            html_content=translated_html,
            keyword=keyword,
            target_lang=target_lang,
        )
        if meta:
            st.session_state[f'translated_meta_{target_lang}'] = meta
            logger.info(f"Meta SEO generated for {target_lang}")
    except Exception as e:
        logger.debug(f"Could not generate meta for {target_lang}: {e}")


def _get_basic_css() -> str:
    """CSS básico de PcComponentes para preview de contenido y traducciones."""
    return """<style>
:root{--orange-900:#FF6000;--blue-m-900:#170453;--white:#FFFFFF;--gray-100:#F5F5F5;--gray-200:#E5E5E5;--gray-700:#404040;--gray-900:#171717;}
.contentGenerator__main,.contentGenerator__faqs,.contentGenerator__verdict{font-family:'Inter',sans-serif;line-height:1.7;color:var(--gray-900);}
.kicker{display:inline-block;background:var(--orange-900);color:var(--white);padding:4px 12px;font-size:12px;font-weight:700;text-transform:uppercase;border-radius:4px;margin-bottom:16px;}
.toc{background:var(--gray-100);border-radius:8px;padding:24px;margin:24px 0;}
.toc__title{font-weight:700;margin-bottom:12px;}
.faqs__item{border-bottom:1px solid var(--gray-200);padding:16px 0;}
.faqs__question{font-weight:600;margin-bottom:8px;}
.verdict-box{background:linear-gradient(135deg,var(--blue-m-900),#2E1A7A);color:var(--white);padding:24px;border-radius:8px;}
.callout{background:var(--gray-100);border-left:4px solid var(--orange-900);padding:16px;margin:24px 0;}
.callout-bf{background:var(--blue-m-900);color:var(--white);padding:24px;border-radius:8px;text-align:center;}
table{width:100%;border-collapse:collapse;margin:24px 0;}
th,td{padding:12px;text-align:left;border-bottom:1px solid var(--gray-200);}
th{background:var(--gray-100);font-weight:600;}
</style>
"""


# ============================================================================
# RENDERIZADO DE TAB DE ANÁLISIS JSON
# ============================================================================

def render_analysis_tab(analysis_json: str, mode: str = "new") -> None:
    """
    Renderiza el tab de análisis crítico (Etapa 2).
    
    Muestra el JSON de análisis de forma estructurada y legible,
    incluyendo problemas encontrados, correcciones sugeridas, y
    aspectos positivos del borrador.
    
    Args:
        analysis_json: String JSON con el análisis crítico
        mode: Modo de generación ("new" o "rewrite")
        
    Notes:
        - Parsea el JSON y lo muestra de forma estructurada
        - Colorea problemas por gravedad (crítico/medio/menor)
        - Incluye validación competitiva si mode="rewrite"
        - Maneja errores de parsing JSON
    """
    
    st.markdown("### 🔍 Análisis Crítico del Borrador (Etapa 2/3)")
    
    st.info("""
    Este análisis identifica problemas en el borrador y proporciona
    correcciones específicas que se aplicarán en la Etapa 3.
    """)
    
    # Intentar parsear el JSON
    try:
        analysis = json.loads(analysis_json)
        
        # Métricas principales
        col1, col2, col3 = st.columns(3)
        
        with col1:
            current_length = analysis.get('longitud_actual', 0)
            st.metric("📝 Longitud Actual", f"{current_length:,} palabras")
        
        with col2:
            target_length = analysis.get('longitud_objetivo', 0)
            st.metric("🎯 Longitud Objetivo", f"{target_length:,} palabras")
        
        with col3:
            needs_adjustment = analysis.get('necesita_ajuste_longitud', False)
            if needs_adjustment:
                st.metric("⚠️ Ajuste Necesario", "Sí", delta="Requiere corrección")
            else:
                st.metric("✅ Longitud", "Correcta", delta="En rango")
        
        # Validación de estructura HTML
        st.markdown("---")
        st.markdown("#### 🏗️ Validación de Estructura HTML")
        
        estructura = analysis.get('estructura_html', {})
        
        struct_cols = st.columns(3)
        
        with struct_cols[0]:
            render_validation_check("3 Articles", estructura.get('tiene_3_articles', False))
            render_validation_check("Primer article solo kicker", estructura.get('primer_article_solo_kicker', False))
        
        with struct_cols[1]:
            render_validation_check("Segundo article vacío", estructura.get('segundo_article_vacio', False))
            render_validation_check("Kicker usa <span>", estructura.get('kicker_usa_span', False))
        
        with struct_cols[2]:
            render_validation_check("Título usa H2", estructura.get('titulo_usa_h2', False))
            render_validation_check("CSS tiene :root", estructura.get('css_tiene_root', False))
        
        # Problemas encontrados
        st.markdown("---")
        st.markdown("#### 🚨 Problemas Identificados")
        
        problemas = analysis.get('problemas_encontrados', [])
        
        if not problemas:
            st.success("✅ No se encontraron problemas significativos")
        else:
            # Agrupar por gravedad
            criticos = [p for p in problemas if p.get('gravedad') == 'crítico']
            medios = [p for p in problemas if p.get('gravedad') == 'medio']
            menores = [p for p in problemas if p.get('gravedad') == 'menor']
            
            # Mostrar resumen
            summary_cols = st.columns(3)
            with summary_cols[0]:
                st.metric("🔴 Críticos", len(criticos))
            with summary_cols[1]:
                st.metric("🟡 Medios", len(medios))
            with summary_cols[2]:
                st.metric("🟢 Menores", len(menores))
            
            # Mostrar problemas críticos
            if criticos:
                with st.expander("🔴 Problemas Críticos", expanded=True):
                    for i, problema in enumerate(criticos, 1):
                        render_problem_card(problema, i)
            
            # Mostrar problemas medios
            if medios:
                with st.expander("🟡 Problemas Medios", expanded=False):
                    for i, problema in enumerate(medios, 1):
                        render_problem_card(problema, i)
            
            # Mostrar problemas menores
            if menores:
                with st.expander("🟢 Problemas Menores", expanded=False):
                    for i, problema in enumerate(menores, 1):
                        render_problem_card(problema, i)
        
        # Análisis competitivo (solo en modo rewrite)
        if mode == "rewrite" and 'analisis_competitivo' in analysis:
            st.markdown("---")
            st.markdown("#### 🏆 Análisis Competitivo")
            
            comp_analysis = analysis['analisis_competitivo']
            
            # Métricas competitivas
            comp_cols = st.columns(3)
            
            with comp_cols[0]:
                supera_profundidad = comp_analysis.get('supera_en_profundidad', False)
                st.metric(
                    "📊 Profundidad",
                    "Superior" if supera_profundidad else "Insuficiente",
                    delta="vs Competencia"
                )
            
            with comp_cols[1]:
                tiene_diferenciador = comp_analysis.get('tiene_enfoque_diferenciador', False)
                st.metric(
                    "🎯 Diferenciación",
                    "Presente" if tiene_diferenciador else "Ausente",
                    delta="Enfoque único"
                )
            
            with comp_cols[2]:
                aporta_valor = comp_analysis.get('aporta_valor_unico', False)
                st.metric(
                    "⭐ Valor Único",
                    "Sí" if aporta_valor else "No",
                    delta="PcComponentes"
                )
            
            # Gaps cubiertos
            gaps = comp_analysis.get('gaps_cubiertos', [])
            if gaps:
                with st.expander("🔍 Gaps Competitivos", expanded=True):
                    for gap in gaps:
                        cubierto = gap.get('cubierto', False)
                        icon = "✅" if cubierto else "❌"
                        st.markdown(f"{icon} **{gap.get('gap', 'Gap sin descripción')}**")
                        st.caption(gap.get('comentario', 'Sin comentario'))
                        st.markdown("---")
        
        # Aspectos positivos
        aspectos_positivos = analysis.get('aspectos_positivos', [])
        if aspectos_positivos:
            st.markdown("---")
            st.markdown("#### ✅ Aspectos Positivos del Borrador")
            for aspecto in aspectos_positivos:
                st.success(f"✓ {aspecto}")
        
        # Instrucciones de revisión
        instrucciones = analysis.get('instrucciones_revision', [])
        if instrucciones:
            st.markdown("---")
            st.markdown("#### 📋 Instrucciones para la Revisión Final")
            for i, instruccion in enumerate(instrucciones, 1):
                st.markdown(f"**{i}.** {instruccion}")
        
        # Veredicto
        st.markdown("---")
        necesita_reescritura = analysis.get('necesita_reescritura_completa', False)
        
        if necesita_reescritura:
            st.error("⚠️ **Veredicto**: El borrador necesita reescritura completa")
        else:
            st.success("✅ **Veredicto**: El borrador es aceptable con correcciones menores")
        
        # Mostrar JSON completo colapsado
        with st.expander("📄 Ver JSON Completo del Análisis"):
            st.json(analysis)
    
    except json.JSONDecodeError as e:
        st.error(f"❌ Error al parsear el JSON del análisis: {str(e)}")
        st.markdown("**JSON recibido:**")
        st.code(analysis_json, language="json")
    
    except Exception as e:
        st.error(f"❌ Error inesperado al procesar el análisis: {str(e)}")
        with st.expander("Ver JSON problemático"):
            st.code(analysis_json, language="json")


# ============================================================================
# ANÁLISIS DE ESTRUCTURA HTML
# ============================================================================

def render_structure_analysis(html_content: str) -> None:
    """
    Renderiza un análisis detallado de la estructura del contenido HTML.
    
    Muestra:
    - Jerarquía de headings (H1-H4)
    - Elementos especiales detectados (tablas, FAQs, callouts, etc.)
    - Análisis de enlaces internos y externos
    - Estadísticas de contenido
    
    Args:
        html_content: Contenido HTML a analizar
        
    Notes:
        - Usa extract_content_structure() para obtener la estructura
        - Muestra visualización jerárquica de headings
        - Identifica elementos clave del CMS
    """
    
    st.caption("Análisis detallado de la estructura del contenido generado")
    
    # Extraer estructura
    try:
        structure = extract_content_structure(html_content)
    except Exception as e:
        logger.error(f"Error al extraer estructura: {e}")
        st.error("❌ Error al extraer la estructura del contenido.")
        return
    
    if not structure.get('structure_valid', True):
        st.error(f"❌ Error al analizar estructura: {structure.get('error', 'Error desconocido')}")
        return
    
    # Métricas de estructura
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📝 Palabras", f"{structure.get('word_count', 0):,}")
    
    with col2:
        headings_count = len(structure.get('headings', []))
        st.metric("📑 Secciones", headings_count)
    
    with col3:
        internal_links = structure.get('internal_links_count', 0)
        st.metric("🔗 Enlaces Int.", internal_links)
    
    with col4:
        external_links = structure.get('external_links_count', 0)
        st.metric("🌐 Enlaces Ext.", external_links)
    
    # Título principal
    title = structure.get('title', 'Sin título detectado')
    st.markdown("#### 📌 Título Principal")
    st.markdown(f"**{title}**")
    
    # Jerarquía de headings
    headings = structure.get('headings', [])
    if headings:
        st.markdown("---")
        st.markdown("#### 📑 Estructura de Secciones")
        
        for heading in headings:
            # Obtener level y asegurar que sea un entero válido
            try:
                level = int(heading.get('level', 2))
            except (ValueError, TypeError):
                level = 2  # Valor por defecto si no se puede convertir
            
            text = heading.get('text', '')
            
            # CORRECCIÓN: Usar max(0, level - 2) para evitar valores negativos
            indent = "  " * max(0, level - 2)
            
            if level <= 2:
                st.markdown(f"{indent}**{text}**")
            elif level == 3:
                st.markdown(f"{indent}• {text}")
            else:
                st.markdown(f"{indent}  ◦ {text}")
    
    # Elementos especiales detectados
    st.markdown("---")
    st.markdown("#### 🎨 Elementos Detectados")
    
    elem_cols = st.columns(3)
    
    with elem_cols[0]:
        render_validation_check("Tablas", structure.get('has_table', False))
        render_validation_check("FAQs", structure.get('has_faq', False))
    
    with elem_cols[1]:
        render_validation_check("Callouts", structure.get('has_callout', False))
        render_validation_check("Verdict Box", structure.get('has_verdict', False))
    
    with elem_cols[2]:
        render_validation_check("TOC", structure.get('has_toc', False))
        render_validation_check("Grid Layout", structure.get('has_grid', False))


# ============================================================================
# COMPONENTES DE UI AUXILIARES
# ============================================================================

def render_validation_check(label: str, is_valid: bool) -> None:
    """
    Renderiza un check visual de validación.
    
    Args:
        label: Texto descriptivo del check
        is_valid: Si pasó la validación o no
        
    Notes:
        - Usa emoji de check (✅) o cruz (❌)
        - Aplica color verde o rojo según resultado
    """
    icon = "✅" if is_valid else "❌"
    color = "green" if is_valid else "red"
    st.markdown(f":{color}[{icon}] {label}")


def render_problem_card(problema: Dict, index: int) -> None:
    """
    Renderiza una tarjeta con información de un problema identificado.
    
    Args:
        problema: Dict con información del problema
        index: Número del problema en la lista
        
    Notes:
        - Muestra tipo, descripción, ubicación y corrección sugerida
        - Usa formato markdown para mejor legibilidad
    """
    tipo = problema.get('tipo', 'desconocido')
    descripcion = problema.get('descripcion', 'Sin descripción')
    ubicacion = problema.get('ubicacion', 'Sin ubicación específica')
    correccion = problema.get('correccion_sugerida', 'Sin corrección sugerida')
    
    st.markdown(f"**Problema #{index}**: `{tipo}`")
    st.markdown(f"**Descripción:** {descripcion}")
    st.caption(f"📍 Ubicación: {ubicacion}")
    
    with st.expander("💡 Ver corrección sugerida"):
        st.markdown(correccion)
    
    st.markdown("---")


def render_copy_button(content: str, button_label: str = "📋 Copiar", key: str = None) -> None:
    """
    Renderiza un botón que muestra el contenido en un bloque de código para copiar manualmente.
    
    Nota: Streamlit no soporta copiar al portapapeles nativamente.
    Este botón expande el contenido para que el usuario lo seleccione y copie.
    
    Args:
        content: Contenido a mostrar
        button_label: Texto del botón
        key: Key única para el botón de Streamlit
    """
    if st.button(button_label, key=key):
        st.code(content, language="html")
        st.caption("👆 Selecciona el código y copia con Ctrl+C")


# ============================================================================
# FUNCIONES DE EXPORTACIÓN
# ============================================================================

def export_all_stages(
    draft_html: Optional[str] = None,
    analysis_json: Optional[str] = None,
    final_html: Optional[str] = None
) -> bytes:
    """
    Exporta todas las etapas en un archivo ZIP.
    
    Args:
        draft_html: HTML del borrador (opcional)
        analysis_json: JSON del análisis (opcional)
        final_html: HTML final (opcional)
        
    Returns:
        bytes: Contenido del archivo ZIP
        
    Notes:
        - Crea un archivo ZIP con todas las etapas disponibles
        - Nombres de archivo descriptivos con timestamp
        - Solo incluye etapas que estén disponibles
    """
    import zipfile
    import io

    # Crear buffer en memoria para el ZIP
    zip_buffer = io.BytesIO()
    
    # Timestamp para nombres de archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
        # Agregar borrador si existe
        if draft_html:
            zip_file.writestr(
                f"stage1_draft_{timestamp}.html",
                draft_html
            )
        
        # Agregar análisis si existe
        if analysis_json:
            zip_file.writestr(
                f"stage2_analysis_{timestamp}.json",
                analysis_json
            )
        
        # Agregar versión final si existe
        if final_html:
            zip_file.writestr(
                f"stage3_final_{timestamp}.html",
                final_html
            )
    
    # Retornar contenido del ZIP
    zip_buffer.seek(0)
    return zip_buffer.read()


def render_export_all_button(
    draft_html: Optional[str] = None,
    analysis_json: Optional[str] = None,
    final_html: Optional[str] = None
) -> None:
    """
    Renderiza un botón para exportar todas las etapas en un ZIP.
    
    Args:
        draft_html: HTML del borrador (opcional)
        analysis_json: JSON del análisis (opcional)
        final_html: HTML final (opcional)
        
    Notes:
        - Solo se muestra si hay al menos 2 etapas completadas
        - Genera un archivo ZIP descargable con todas las etapas
    """
    # Contar etapas disponibles
    available_stages = sum([
        draft_html is not None,
        analysis_json is not None,
        final_html is not None
    ])
    
    # Solo mostrar si hay al menos 2 etapas
    if available_stages >= 2:
        st.markdown("---")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        zip_content = export_all_stages(draft_html, analysis_json, final_html)
        
        st.download_button(
            label=f"📦 Descargar Todo ({available_stages} etapas)",
            data=zip_content,
            file_name=f"content_generator_all_stages_{timestamp}.zip",
            mime="application/zip",
            use_container_width=True
        )


# ============================================================================
# INFORMACIÓN Y AYUDA
# ============================================================================

def render_results_help() -> None:
    """
    Renderiza información de ayuda sobre la sección de resultados.
    
    Explica:
    - Qué significa cada etapa
    - Cómo interpretar las validaciones
    - Qué hacer con los errores encontrados
    """
    with st.expander("ℹ️ Ayuda: Interpretando los Resultados"):
        st.markdown("""
        ### 📊 Entendiendo las Etapas
        
        **Etapa 1 - Borrador Inicial:**
        - Primera versión del contenido generada por IA
        - Puede contener errores o imprecisiones
        - Se usa como base para el análisis crítico
        
        **Etapa 2 - Análisis Crítico:**
        - Revisión automatizada del borrador
        - Identifica problemas de estructura, longitud, tono, etc.
        - Proporciona correcciones específicas
        
        **Etapa 3 - Versión Final:**
        - Contenido corregido listo para publicación
        - Aplica todas las correcciones de la Etapa 2
        - Debe pasar todas las validaciones CMS
        
        ---
        
        ### ✅ Validaciones CMS v4.1.1
        
        **Errores Críticos (🔴):**
        - Impiden la publicación en el CMS
        - Deben corregirse antes de usar el contenido
        - Generalmente relacionados con estructura HTML
        
        **Advertencias (🟡):**
        - No impiden publicación pero pueden afectar calidad
        - Recomendable corregir para mejores resultados
        - Relacionadas con SEO, UX o mejores prácticas
        
        ---
        
        ### 📝 Word Count
        
        - **Objetivo**: Longitud especificada en inputs
        - **Diferencia**: Variación respecto al objetivo
        - **Precisión**: Porcentaje de exactitud (ideal >95%)
        - **Rango aceptable**: ±5% del objetivo
        
        ---
        
        ### 🔗 Enlaces
        
        **Recomendaciones:**
        - 2-3 enlaces internos a categorías
        - 1-2 enlaces a PDPs de productos
        - Enlaces bien integrados en el contexto
        - Anchors descriptivos y naturales
        """)


# ============================================================================
# TAB DE GENERACIÓN DE IMÁGENES
# ============================================================================

def render_image_generation_tab(html_content: str) -> None:
    """
    Renderiza la UI de generación de imágenes post-Stage 3.
    
    Opciones:
    - Generar imágenes a partir del contexto del texto final
    - Generar imágenes a partir de imágenes seed del usuario
    - Asociar cada imagen a un bloque H2/H3 específico
    - Descargar imágenes individuales o como ZIP
    
    Args:
        html_content: HTML final de Stage 3
    """
    st.markdown("### 🖼️ Generación de Imágenes")
    
    # Verificar disponibilidad de Gemini
    try:
        from utils.image_gen import (
            is_gemini_available, extract_headings_from_html,
            ImageType, ImageRequest, generate_images, create_images_zip,
            IMAGE_TYPE_LABELS, ImageFormatVariant,
        )
        available, gemini_error = is_gemini_available()
    except ImportError:
        st.warning("⚠️ Módulo de generación de imágenes no disponible. Instalar: `pip install google-genai`")
        return
    
    if not available:
        st.warning(f"⚠️ Gemini no configurado: {gemini_error}")
        st.caption("Configura `GEMINI_API_KEY` en secrets o variables de entorno.")
        return
    
    # Extraer headings del HTML para asociar imágenes
    headings = extract_headings_from_html(html_content)
    keyword = st.session_state.get('last_config', {}).get('keyword', 'contenido')
    
    # Heading options para selectbox
    heading_options = ["(Ninguno — imagen general)"] + [h['display'] for h in headings]
    
    st.caption(
        "Genera imágenes optimizadas para tu artículo con Gemini. "
        "Las imágenes se generan para descarga, no se insertan en el HTML."
    )
    
    # ── Modo de generación ──
    gen_mode = st.radio(
        "Modo de generación",
        options=["context", "seed"],
        format_func=lambda x: {
            "context": "📝 Desde el contexto del texto",
            "seed": "🖼️ Desde imágenes de referencia",
        }[x],
        horizontal=True,
        key="img_gen_mode",
    )
    
    # ── Configuración común: número de imágenes ──
    n_images = st.slider(
        "Número de imágenes a generar",
        min_value=1, max_value=5, value=2,
        key="img_gen_count",
    )
    
    # ── Seed images (si modo seed) ──
    seed_files = []
    if gen_mode == "seed":
        st.markdown("**Sube imágenes de referencia** (máximo 5):")
        uploaded = st.file_uploader(
            "Imágenes seed",
            type=["png", "jpg", "jpeg", "webp"],
            accept_multiple_files=True,
            key="img_seed_upload",
        )
        if uploaded:
            seed_files = uploaded[:5]
            if len(uploaded) > 5:
                st.warning(f"Se usarán solo las primeras 5 de {len(uploaded)} subidas.")
            # Preview thumbnails
            cols = st.columns(min(len(seed_files), 5))
            for i, f in enumerate(seed_files):
                with cols[i]:
                    st.image(f, caption=f.name, width=100)
    
    # ── Configuración por imagen ──
    st.markdown("---")
    st.markdown("**Configuración por imagen:**")
    
    # Tamaños por defecto según tipo
    _DEFAULT_SIZES = {
        ImageType.COVER: (1024, 576),
        ImageType.BODY_CONTEXTUAL: (1024, 1024),
        ImageType.BODY_USE_CASE: (1024, 1024),
        ImageType.INFOGRAPHIC: (1024, 1792),
        ImageType.SUMMARY: (1024, 1024),
    }

    _FORMAT_OPTIONS = {
        "JPEG": "jpeg",
        "WebP": "webp",
        "PNG": "png",
    }

    image_configs = []
    for i in range(n_images):
        with st.expander(f"Imagen {i+1}", expanded=(i == 0)):
            col1, col2 = st.columns([1, 1])

            with col1:
                img_type = st.selectbox(
                    "Tipo",
                    options=[
                        ImageType.BODY_CONTEXTUAL,
                        ImageType.COVER,
                        ImageType.BODY_USE_CASE,
                        ImageType.INFOGRAPHIC,
                        ImageType.SUMMARY,
                    ],
                    format_func=lambda x: IMAGE_TYPE_LABELS.get(x, x.value),
                    key=f"img_type_{i}",
                    index=1 if i == 0 else 0,
                )

            with col2:
                heading_idx = st.selectbox(
                    "Asociar a sección",
                    options=range(len(heading_options)),
                    format_func=lambda x: heading_options[x],
                    key=f"img_heading_{i}",
                    index=min(i + 1, len(heading_options) - 1) if headings else 0,
                )

            # Dimensiones y formatos
            default_w, default_h = _DEFAULT_SIZES.get(img_type, (1024, 1024))

            col_w, col_h, col_fmt = st.columns([1, 1, 2])
            with col_w:
                img_width = st.number_input(
                    "Ancho (px)", min_value=128, max_value=4096,
                    value=default_w, step=64, key=f"img_w_{i}",
                )
            with col_h:
                img_height = st.number_input(
                    "Alto (px)", min_value=128, max_value=4096,
                    value=default_h, step=64, key=f"img_h_{i}",
                )
            with col_fmt:
                img_formats = st.multiselect(
                    "Formatos de salida",
                    options=list(_FORMAT_OPTIONS.keys()),
                    default=["JPEG", "WebP"],
                    key=f"img_fmt_{i}",
                )

            extra = st.text_input(
                "Instrucciones adicionales (opcional)",
                placeholder="Ej: Estilo minimalista, fondo blanco, sin personas",
                key=f"img_extra_{i}",
            )

            # Construir config
            selected_heading = headings[heading_idx - 1] if heading_idx > 0 and heading_idx <= len(headings) else None

            image_configs.append({
                'type': img_type,
                'heading': selected_heading,
                'extra': extra,
                'width': img_width,
                'height': img_height,
                'formats': [_FORMAT_OPTIONS[f] for f in img_formats] if img_formats else ["jpeg", "webp"],
            })
    
    # ── Botón de generación ──
    st.markdown("---")
    
    generate_clicked = st.button(
        f"🚀 Generar {n_images} imagen{'es' if n_images > 1 else ''}",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get('img_generating', False),
        key="btn_generate_images",
    )
    
    if generate_clicked:
        st.session_state.img_generating = True
        
        # Leer seed images si aplica
        seed_bytes = []
        if gen_mode == "seed" and seed_files:
            for f in seed_files:
                f.seek(0)
                seed_bytes.append(f.read())
        
        # Construir requests
        img_requests = []
        for cfg in image_configs:
            heading = cfg['heading']
            req = ImageRequest(
                image_type=cfg['type'],
                keyword=keyword,
                heading_id=heading['id'] if heading else '',
                heading_text=heading['text'] if heading else keyword,
                heading_content=heading['content'] if heading else '',
                extra_instructions=cfg['extra'],
                seed_images=seed_bytes if gen_mode == "seed" else [],
                width=cfg.get('width', 0),
                height=cfg.get('height', 0),
                output_formats=cfg.get('formats', ['jpeg', 'webp']),
            )
            img_requests.append(req)
        
        # Generar
        with st.spinner(f"🎨 Generando {n_images} imagen{'es' if n_images > 1 else ''} con Gemini (puede tardar 10-30s por imagen)..."):
            t0 = time_mod.time()
            result = generate_images(img_requests, html_content=html_content)
            elapsed = time_mod.time() - t0
        
        st.session_state.img_generating = False
        
        if result.success and result.images:
            st.session_state.generated_images = result
            st.success(
                f"✅ {len(result.images)} imagen{'es' if len(result.images) > 1 else ''} "
                f"generada{'s' if len(result.images) > 1 else ''} en {elapsed:.1f}s"
            )
        else:
            st.error(f"❌ Error: {result.error}")
    
    # ── Mostrar imágenes generadas ──
    result = st.session_state.get('generated_images')
    if result and hasattr(result, 'images') and result.images:
        st.markdown("---")
        st.markdown("### Imágenes generadas")
        
        for i, img in enumerate(result.images):
            with st.container():
                col_img, col_info = st.columns([2, 1])

                with col_img:
                    st.image(
                        img.image_bytes,
                        caption=f"{IMAGE_TYPE_LABELS.get(img.image_type, img.image_type.value)} — {img.heading_ref}",
                        use_container_width=True,
                    )

                with col_info:
                    st.markdown(f"**Tipo:** {IMAGE_TYPE_LABELS.get(img.image_type, img.image_type.value)}")
                    st.markdown(f"**Sección:** {img.heading_ref}")

                    # Mostrar dimensiones si hay variantes
                    variants = getattr(img, 'format_variants', [])
                    if variants and variants[0].width:
                        st.markdown(f"**Dimensiones:** {variants[0].width}x{variants[0].height} px")

                    st.markdown(f"**Alt text:** _{img.alt_text}_")

                    # Descargas por formato
                    st.caption("Descargar:")
                    base_name = img.get_filename()

                    # Original
                    orig_ext = base_name.rsplit('.', 1)[-1].upper() if '.' in base_name else 'PNG'
                    st.download_button(
                        f"⬇️ Original ({orig_ext} · {img.size_kb:.0f} KB)",
                        data=img.image_bytes,
                        file_name=base_name,
                        mime=img.mime_type,
                        key=f"dl_img_orig_{i}",
                    )

                    # Variantes de formato (JPEG, WebP, etc.)
                    for vi, variant in enumerate(variants):
                        vname = variant.get_filename(base_name)
                        st.download_button(
                            f"⬇️ {variant.format_label.upper()} ({variant.size_kb:.0f} KB)",
                            data=variant.image_bytes,
                            file_name=vname,
                            mime=variant.mime_type,
                            key=f"dl_img_{i}_v{vi}",
                        )

                    # Prompt usado (colapsable)
                    with st.expander("Ver prompt", expanded=False):
                        st.code(img.prompt_used, language="text")

                st.markdown("---")
        
        # Descarga ZIP de todas
        if len(result.images) > 1:
            zip_data = create_images_zip(result.images)
            st.download_button(
                f"📦 Descargar todas ({len(result.images)} imágenes) como ZIP",
                data=zip_data,
                file_name=f"imagenes_{keyword.replace(' ', '_')[:30]}.zip",
                mime="application/zip",
                key="dl_images_zip",
                use_container_width=True,
            )


# ============================================================================
# CONSTANTES Y CONFIGURACIÓN
# ============================================================================

# Versión del módulo
__version__ = "4.2.0"

# Colores para estados
COLOR_SUCCESS = "green"
COLOR_WARNING = "orange"
COLOR_ERROR = "red"

# Umbrales de validación
WORD_COUNT_TOLERANCE = 0.05  # ±5%
WORD_COUNT_WARNING_THRESHOLD = 0.10  # ±10%

# Configuración de preview
PREVIEW_MAX_LENGTH = 200  # Caracteres en preview de código
