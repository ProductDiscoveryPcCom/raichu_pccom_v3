"""
Tests for prompts/new_content.py — prompt builder signature and output.
"""
from prompts.new_content import (
    build_new_content_prompt_stage1,
    build_new_content_correction_prompt_stage2,
    build_final_prompt_stage3,
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
