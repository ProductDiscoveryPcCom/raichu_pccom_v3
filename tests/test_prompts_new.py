"""
Tests for prompts/new_content.py — prompt builder signature and output.
"""
import copy

from config.arquetipos import ARQUETIPOS
from prompts.new_content import (
    ARQUETIPOS_CON_MINI_STORIES,
    build_new_content_prompt_stage1,
    build_new_content_correction_prompt_stage2,
    build_final_prompt_stage3,
    _build_real_mini_stories_block,
    _build_synthetic_mini_stories_block,
    _build_stage3_checklist,
    _cms_article_skeletons,
)


def test_stage1_returns_string_with_keyword(sample_arquetipo):
    result = build_new_content_prompt_stage1(
        keyword="tarjeta grafica",
        arquetipo=sample_arquetipo,
    )
    assert isinstance(result, str)
    assert len(result) > 500
    assert "tarjeta grafica" in result.lower()


def test_stage1_includes_arquetipo(sample_arquetipo):
    result = build_new_content_prompt_stage1(
        keyword="monitor gaming",
        arquetipo=sample_arquetipo,
    )
    # The arquetipo name should appear in the prompt
    assert sample_arquetipo["name"].lower() in result.lower()


def test_stage1_with_optional_params(sample_arquetipo):
    result = build_new_content_prompt_stage1(
        keyword="portatil gaming",
        arquetipo=sample_arquetipo,
        secondary_keywords=["gpu", "nvidia rtx"],
        additional_instructions="Incluir tabla comparativa de precios",
        visual_elements=["toc", "table"],
    )
    assert "gpu" in result.lower()
    assert "tabla comparativa" in result.lower()


def test_stage2_includes_draft():
    draft = "<article><h2>Borrador</h2><p>Contenido de prueba.</p></article>"
    result = build_new_content_correction_prompt_stage2(
        draft_content=draft,
        target_length=1500,
        keyword="portatil gaming",
    )
    assert isinstance(result, str)
    assert len(result) > 200
    assert "portatil gaming" in result.lower()


def test_stage3_includes_feedback():
    draft = "<article><h2>Borrador</h2><p>Contenido de prueba.</p></article>"
    feedback = '{"issues": ["contenido demasiado corto", "faltan FAQs"]}'
    result = build_final_prompt_stage3(
        draft_content=draft,
        analysis_feedback=feedback,
        keyword="monitor 4k",
        target_length=2000,
    )
    assert isinstance(result, str)
    assert len(result) > 200
    assert "monitor 4k" in result.lower()


# ============================================================================
# R3.3: Mini-stories sintéticas como fallback sin reviews
# ============================================================================

def _arquetipo_with_code(code: str) -> dict:
    return copy.deepcopy(ARQUETIPOS[code])


def test_synthetic_mini_stories_block_constraints():
    """R3.3: bloque sintético cumple los 5 constraints anti-fake."""
    block = _build_synthetic_mini_stories_block()
    # Encabezado de perfiles (no se permite encabezarlo como Testimonios)
    assert "Perfiles de uso" in block
    assert "PERFILES DE USO" in block  # encabezado del bloque
    # Testimonios/Reviews sólo deben aparecer como prohibición explícita
    assert 'no "Testimonios"' in block
    # Tono hipotético explícito
    assert "puede encajar" in block.lower() or "buena opción si" in block.lower()
    # Prohibiciones explícitas
    assert "NUNCA inventes nombres propios" in block
    assert "no son testimonios" in block.lower() or "Perfiles, no testimonios" in block
    # Ancla en specs reales
    assert "specs reales" in block


def test_real_and_synthetic_blocks_are_distinct():
    """R3.3: los dos bloques deben ser claramente diferentes en encabezado."""
    real = _build_real_mini_stories_block()
    synth = _build_synthetic_mini_stories_block()
    assert real != synth
    assert "MINI-HISTORIAS" in real
    assert "PERFILES DE USO" in synth


def test_stage1_uses_synthetic_when_no_feedback_for_arq4():
    """R3.3: si arquetipo en ARQUETIPOS_CON_MINI_STORIES y NO hay feedback,
    el prompt incluye el bloque sintético, no el de mini-historias reales."""
    arq = _arquetipo_with_code("ARQ-4")
    assert "ARQ-4" in ARQUETIPOS_CON_MINI_STORIES
    # Sin pdp_data → has_feedback queda en False
    prompt = build_new_content_prompt_stage1(keyword="review iphone 17", arquetipo=arq)
    assert "PERFILES DE USO" in prompt
    assert "Perfiles de uso" in prompt
    # No debe activar el bloque de mini-historias reales
    assert "BASADOS EN LAS REVIEWS REALES" not in prompt
    # Sí debe contener constraints anti-fake clave
    assert "NUNCA inventes nombres propios" in prompt


def test_stage1_uses_real_when_feedback_present():
    """R3.3: si hay feedback de usuario, se usa el bloque de mini-historias reales."""
    arq = _arquetipo_with_code("ARQ-4")
    pdp_data = {
        "title": "Producto Demo",
        "advantages_list": ["Pantalla brillante", "Batería duradera"],
        "disadvantages_list": ["Algo pesado"],
        "top_comments": ["Funciona muy bien"],
        "has_user_feedback": True,
    }
    prompt = build_new_content_prompt_stage1(
        keyword="review iphone 17", arquetipo=arq, pdp_data=pdp_data,
    )
    assert "BASADOS EN LAS REVIEWS REALES" in prompt
    assert "PERFILES DE USO" not in prompt


# ============================================================================
# R2.4: Stage 2 condensado y validaciones críticas preservadas
# ============================================================================

_STAGE2_CRITICAL_MARKERS = [
    # Estructura CMS (R1.3 follow-up — no debe perderse)
    "contentGenerator__main",
    "contentGenerator__faqs",
    "contentGenerator__verdict",
    # Anti-IA referenciado vía constante canónica
    "ANTI-IA",
    # Excepciones por arquetipo R1.4 (provienen de ANTI_IA_CHECKLIST_STAGE2)
    "ARQ-16",
    "ARQ-19",
    "ARQ-20",
    # Keyword/SEO
    "primeras 100 palabras",
    "densidad",
    # Output JSON estructurado
    "json",
]


def test_stage2_preserves_critical_validations(sample_arquetipo):
    """R2.4: Stage 2 condensado debe seguir mencionando los markers críticos."""
    draft = "<article class='contentGenerator__main'><p>Demo.</p></article>"
    prompt = build_new_content_correction_prompt_stage2(
        draft_content=draft,
        target_length=1500,
        keyword="portatil gaming",
        visual_elements=["toc", "table"],
        arquetipo_code=sample_arquetipo["code"],
        arquetipo_structure=sample_arquetipo["structure"],
    )
    missing = [m for m in _STAGE2_CRITICAL_MARKERS if m.lower() not in prompt.lower()]
    assert not missing, f"Stage 2 perdió markers críticos: {missing}"


def test_stage2_prompt_under_token_budget():
    """R2.4: Stage 2 condensado debe estar bajo presupuesto razonable.

    Aproximación: len // 4 ≈ tokens. Threshold conservador (5000) que detecta
    regresiones grandes pero permite inputs grandes (draft hasta 12000 chars).
    """
    draft = "<article>" + ("Texto de relleno. " * 200) + "</article>"
    prompt = build_new_content_correction_prompt_stage2(
        draft_content=draft,
        target_length=1500,
        keyword="monitor gaming",
        links_to_verify=[{"anchor": "review", "url": "https://x"}],
        visual_elements=["toc", "table", "callout"],
    )
    approx_tokens = len(prompt) // 4
    assert approx_tokens < 5000, f"Stage 2 demasiado grande: ~{approx_tokens} tokens"


def test_stage2_uses_canonical_anti_ia_checklist():
    """R2.4: Stage 2 inyecta el checklist anti-IA canónico de brand_tone.py."""
    from prompts.brand_tone import ANTI_IA_CHECKLIST_STAGE2
    prompt = build_new_content_correction_prompt_stage2(
        draft_content="<article>x</article>", keyword="test",
    )
    # Una frase específica que sólo aparece en el checklist canónico
    assert "Cabe mencionar" in prompt
    # Debe contener el bloque (puede estar normalizado por f-string, comprueba subset)
    assert "Excepciones permitidas" in prompt


def test_get_css_styles_uses_module_constant():
    """R2.4: get_css_styles() retorna la constante cacheada al import."""
    from prompts.new_content import get_css_styles, _CACHED_CSS_FOR_PROMPT_NO_ARGS
    assert get_css_styles() is _CACHED_CSS_FOR_PROMPT_NO_ARGS


def test_stage1_omits_engagement_block_when_arquetipo_not_in_set():
    """Si el arquetipo NO está en ARQUETIPOS_CON_MINI_STORIES, se usa el bloque mínimo."""
    # ARQ-2 (Guía Paso a Paso) no está en el set
    arq = _arquetipo_with_code("ARQ-2")
    assert "ARQ-2" not in ARQUETIPOS_CON_MINI_STORIES
    prompt = build_new_content_prompt_stage1(keyword="cómo montar pc", arquetipo=arq)
    assert "PERFILES DE USO" not in prompt
    assert "MINI-HISTORIAS" not in prompt
    assert "ENGAGEMENT: CTAs DISTRIBUIDOS" in prompt


# ============================================================================
# Garantía estructura CMS — Capa A (prompt hardening) + C4 (mini-stories Stage 3)
# ============================================================================

def test_stage3_has_non_negotiable_cms_mandate():
    """A1: el requisito de los 3 articles aparece como bloque NO-NEGOCIABLE antes del draft."""
    out = build_final_prompt_stage3(
        draft_content="<article>x</article>", analysis_feedback="{}", keyword="ssd",
    )
    assert "NO NEGOCIABLE" in out
    assert "ERROR CRÍTICO" in out
    assert all(c in out for c in [
        "contentGenerator__main", "contentGenerator__faqs", "contentGenerator__verdict",
    ])
    # el mandato va antes del borrador (máxima atención del modelo)
    assert out.index("NO NEGOCIABLE") < out.index("# BORRADOR ORIGINAL")


def test_stage3_checklist_lists_three_articles_always():
    """A2: los 3 articles encabezan el checklist tanto vacío como con elementos visuales."""
    for ve in ([], ["toc", "table"]):
        chk = _build_stage3_checklist(ve)
        assert "contentGenerator__main" in chk
        assert "contentGenerator__faqs" in chk
        assert "contentGenerator__verdict" in chk


def test_stage2_reports_missing_articles_as_critical():
    """A3: Stage 2 §3 instruye a reportar articles faltantes como problema crítico."""
    out = build_new_content_correction_prompt_stage2(
        draft_content="<article>x</article>", target_length=1500, keyword="ssd",
    )
    assert "estructura" in out
    assert "critico" in out


def test_stage3_mini_stories_directive_only_for_miniset():
    """C4: arquetipo del miniset (ARQ-7) recibe directiva de preservación; ARQ-3 no."""
    in_set = build_final_prompt_stage3(
        draft_content="d", analysis_feedback="{}", keyword="portatiles", arquetipo_code="ARQ-7",
    )
    not_in_set = build_final_prompt_stage3(
        draft_content="d", analysis_feedback="{}", keyword="ssd", arquetipo_code="ARQ-3",
    )
    assert "ARQ-7" in ARQUETIPOS_CON_MINI_STORIES
    assert "ARQ-3" not in ARQUETIPOS_CON_MINI_STORIES
    assert "MINI-HISTORIAS" in in_set
    assert "MINI-HISTORIAS" not in not_in_set


def test_cms_article_skeletons_only_missing():
    """_cms_article_skeletons devuelve solo los articles pedidos, con marcadores."""
    sk = _cms_article_skeletons(
        ["contentGenerator__faqs", "contentGenerator__verdict"], keyword="ssd",
    )
    assert "contentGenerator__faqs" in sk
    assert "contentGenerator__verdict" in sk
    assert "contentGenerator__main" not in sk
    assert "#MODULE_START:VERDICT#" in sk
