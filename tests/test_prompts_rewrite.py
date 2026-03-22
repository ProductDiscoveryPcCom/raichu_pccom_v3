"""
Tests for prompts/rewrite.py — rewrite prompt builder signature and output.
"""
from prompts.rewrite import (
    build_rewrite_prompt_stage1,
    build_rewrite_correction_prompt_stage2,
    build_rewrite_final_prompt_stage3,
)


def test_rewrite_stage1_returns_string(rewrite_config):
    result = build_rewrite_prompt_stage1(
        keyword="raton gaming",
        competitor_analysis="La competencia usa tablas comparativas extensas.",
        config=rewrite_config,
    )
    assert isinstance(result, str)
    assert len(result) > 500
    assert "raton gaming" in result.lower()


def test_rewrite_stage1_merge_mode(rewrite_config):
    rewrite_config["rewrite_mode"] = "merge"
    rewrite_config["html_contents"] = [
        {"html": "<article><p>Articulo uno sobre ratones.</p></article>",
         "url": "https://www.pccomponentes.com/ratones", "word_count": 30},
        {"html": "<article><p>Articulo dos sobre teclados.</p></article>",
         "url": "https://www.pccomponentes.com/teclados", "word_count": 25},
    ]
    result = build_rewrite_prompt_stage1(
        keyword="perifericos gaming",
        competitor_analysis="Analisis competencia.",
        config=rewrite_config,
    )
    assert isinstance(result, str)
    # Merge mode should reference fusion or merging
    result_lower = result.lower()
    assert "fusión" in result_lower or "fusión" in result_lower or "merge" in result_lower or "fusionar" in result_lower


def test_rewrite_stage2_returns_string(rewrite_config):
    result = build_rewrite_correction_prompt_stage2(
        draft_content="<article><h2>Borrador reescrito</h2><p>Texto.</p></article>",
        target_length=1500,
        keyword="ssd nvme",
        competitor_analysis="Competencia tiene buena estructura.",
        config=rewrite_config,
    )
    assert isinstance(result, str)
    assert "ssd nvme" in result.lower()


def test_rewrite_stage3_returns_string(rewrite_config):
    result = build_rewrite_final_prompt_stage3(
        draft_content="<article><h2>Borrador</h2><p>Texto.</p></article>",
        corrections_json='{"corrections": ["mejorar intro"]}',
        config=rewrite_config,
    )
    assert isinstance(result, str)
    assert len(result) > 200
