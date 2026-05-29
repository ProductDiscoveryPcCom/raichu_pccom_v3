"""
UI del modo Repurpose — deriva assets desde un artículo HTML existente.

Patrón de degradación graceful: si `_repurpose_available=False` en app.py,
el modo no aparece en el radio. Aquí asumimos imports OK (la guarda está arriba).
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

import streamlit as st

from core.repurpose_pipeline import (
    RepurposeResult,
    execute_repurpose_pipeline,
    regenerate_single_asset,
)
from prompts.repurpose import SUPPORTED_ASSETS

logger = logging.getLogger(__name__)


ASSET_LABELS = {
    "meta_description": "🏷️ Meta description (155 chars)",
    "serp_title": "🔎 Título SERP (60 chars)",
    "rsa": "📣 Google RSA (15 títulos + 4 desc)",
    "newsletter": "✉️ Snippet newsletter",
    "x_thread": "🧵 Hilo X/Twitter (8-12 tweets)",
    "linkedin_carousel": "🎠 Carrusel LinkedIn (5-7 slides)",
    "jsonld": "🧬 JSON-LD (Article + FAQPage + Product)",
    "featured_snippet": "⭐ Featured snippet (Q&A)",
    "whatsapp": "📲 WhatsApp / Telegram",
}

DEFAULT_ASSETS = ["meta_description", "serp_title", "jsonld"]


def _get_generator():
    """Importa ContentGenerator perezosamente para no romper si falla el SDK."""
    try:
        from core.config import CLAUDE_API_KEY, CLAUDE_MODEL
        from core.generator import ContentGenerator
        return ContentGenerator(api_key=CLAUDE_API_KEY, model=CLAUDE_MODEL, max_tokens=2000)
    except Exception as e:
        logger.exception("No se pudo instanciar ContentGenerator")
        st.error(f"❌ No se pudo inicializar el generador: {e}")
        return None


def _render_asset_preview(asset_id: str, payload: Any) -> None:
    if asset_id in ("meta_description", "serp_title", "whatsapp"):
        st.code(payload, language="text")
    elif asset_id == "jsonld":
        st.code(json.dumps(payload, indent=2, ensure_ascii=False), language="json")
    elif asset_id == "newsletter":
        st.markdown(f"**Asunto:** {payload.get('subject')}")
        st.markdown(f"**Preheader:** {payload.get('preheader')}")
        st.markdown(f"**Body:**\n\n{payload.get('body')}")
        st.markdown(f"**CTA:** `{payload.get('cta_text')}`")
    elif asset_id == "x_thread":
        for tw in payload.get("tweets", []):
            st.markdown(f"**{tw.get('n')}.** {tw.get('text')}")
    elif asset_id == "linkedin_carousel":
        for slide in payload.get("slides", []):
            with st.container(border=True):
                st.markdown(f"**Slide {slide.get('n')} — {slide.get('title')}**")
                st.markdown(slide.get("body_markdown", ""))
    elif asset_id == "featured_snippet":
        st.markdown(f"**P:** {payload.get('question')}")
        st.markdown(f"**R:** {payload.get('answer')}")
    elif asset_id == "rsa":
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Títulos (≤30 chars)**")
            for t in payload.get("titles", []):
                st.markdown(f"- {t}")
        with col2:
            st.markdown("**Descripciones (≤90 chars)**")
            for d in payload.get("descriptions", []):
                st.markdown(f"- {d}")
    else:
        st.code(str(payload))


def _render_results(results: Dict[str, RepurposeResult]) -> None:
    if not results:
        return

    st.markdown("### 🎁 Assets generados")

    total_tokens = 0
    for asset_id, res in results.items():
        meta = res.metadata or {}
        if meta.get("input_tokens"):
            total_tokens += meta["input_tokens"] + (meta.get("output_tokens") or 0)

    if total_tokens:
        st.caption(f"Total tokens: {total_tokens:,}")

    for asset_id, res in results.items():
        label = ASSET_LABELS.get(asset_id, asset_id)
        status = "✅" if res.ok else "❌"
        with st.expander(f"{status} {label}", expanded=res.ok):
            if not res.ok:
                if res.error:
                    st.error(f"Error: {res.error}")
                if res.validation_errors:
                    st.warning("Validación:\n- " + "\n- ".join(res.validation_errors))
            else:
                if res.validation_errors:
                    st.info("Avisos:\n- " + "\n- ".join(res.validation_errors))
                _render_asset_preview(asset_id, res.payload)

            meta = res.metadata or {}
            if meta:
                with st.popover("ℹ️ Metadata"):
                    st.json(meta)

            if st.button("♻️ Regenerar este asset", key=f"regen_{asset_id}"):
                gen = _get_generator()
                if gen:
                    with st.spinner(f"Regenerando {label}..."):
                        new_res = regenerate_single_asset(
                            asset_id=asset_id,
                            article_html=st.session_state.get("repurpose_source_html", ""),
                            config={"keyword": st.session_state.get("repurpose_keyword", "")},
                            generator=gen,
                        )
                    results[asset_id] = new_res
                    st.session_state.repurpose_assets = results
                    st.rerun()


def render_repurpose_mode() -> None:
    """Renderiza el modo Repurpose."""
    st.markdown("## 🔁 Repurpose — Deriva assets desde un artículo")
    st.caption(
        "Sube o pega un artículo Raichu (o cualquier HTML con la estructura CMS) y genera "
        "assets para meta, ads, social y CMS. El JSON-LD se construye determinista (sin LLM)."
    )

    final_html = st.session_state.get("final_html")
    last_keyword = (st.session_state.get("last_config") or {}).get("keyword", "")

    # Pre-siembra: si keyword no existe en session_state, inicializamos con el último
    if "repurpose_keyword" not in st.session_state and last_keyword:
        st.session_state.repurpose_keyword = last_keyword

    if final_html and not st.session_state.get("repurpose_source_html"):
        if st.button("📥 Usar último artículo generado"):
            st.session_state.repurpose_source_html = final_html
            if last_keyword:
                st.session_state.repurpose_keyword = last_keyword
            st.rerun()

    article = st.text_area(
        "HTML del artículo fuente",
        height=250,
        key="repurpose_source_html",
        help="Pega el HTML del artículo (estructura CMS 3-article).",
    )

    keyword = st.text_input(
        "Keyword principal",
        key="repurpose_keyword",
    )

    assets = st.multiselect(
        "Assets a generar",
        options=list(SUPPORTED_ASSETS),
        default=st.session_state.get("repurpose_selected_assets", DEFAULT_ASSETS),
        format_func=lambda a: ASSET_LABELS.get(a, a),
        key="repurpose_selected_assets",
    )

    can_run = bool(article and len(article.split()) >= 300 and keyword and assets)
    if article and len(article.split()) < 300:
        st.warning("⚠️ El artículo debe tener al menos 300 palabras.")

    if st.button("🔁 Generar derivados", type="primary", disabled=not can_run):
        gen = _get_generator()
        if gen:
            with st.spinner(f"Generando {len(assets)} assets en paralelo..."):
                results = execute_repurpose_pipeline(
                    article_html=article,
                    assets_requested=assets,
                    config={"keyword": keyword},
                    generator=gen,
                )
            st.session_state.repurpose_assets = results
            st.session_state["_has_generated_repurpose"] = True

    results = st.session_state.get("repurpose_assets")
    if results:
        _render_results(results)
