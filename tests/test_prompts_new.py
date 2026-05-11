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


def test_stage1_omits_engagement_block_when_arquetipo_not_in_set():
    """Si el arquetipo NO está en ARQUETIPOS_CON_MINI_STORIES, se usa el bloque mínimo."""
    # ARQ-2 (Guía Paso a Paso) no está en el set
    arq = _arquetipo_with_code("ARQ-2")
    assert "ARQ-2" not in ARQUETIPOS_CON_MINI_STORIES
    prompt = build_new_content_prompt_stage1(keyword="cómo montar pc", arquetipo=arq)
    assert "PERFILES DE USO" not in prompt
    assert "MINI-HISTORIAS" not in prompt
    assert "ENGAGEMENT: CTAs DISTRIBUIDOS" in prompt
