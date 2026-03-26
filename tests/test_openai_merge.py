"""Tests for _merge_json_analyses in core/openai_client.py.

Covers defensive handling of puntuacion_general (dict/str/None) and
aspectos_positivos dedup when items are dicts (unhashable).
"""

import json
import pytest

from core.openai_client import _merge_json_analyses


def _base_analysis(**overrides):
    """Minimal valid analysis dict with optional overrides."""
    base = {
        "problemas": [],
        "puntuacion_general": 7,
        "aspectos_positivos": [],
        "recomendacion_principal": "ok",
    }
    base.update(overrides)
    return base


def _parse(result: str) -> dict:
    return json.loads(result)


# ── puntuacion_general: plain numbers ────────────────────────────────────

class TestPuntuacionGeneralNumeric:
    def test_int_scores_take_min(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=8),
            _base_analysis(puntuacion_general=5),
        ))
        assert merged["puntuacion_general"] == 5

    def test_float_scores_take_min(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=6.5),
            _base_analysis(puntuacion_general=7.2),
        ))
        assert merged["puntuacion_general"] == 6.5


# ── puntuacion_general: dict with "general" key ─────────────────────────

class TestPuntuacionGeneralDictGeneral:
    def test_both_dicts_with_general(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"general": 6, "seo": 8}),
            _base_analysis(puntuacion_general={"general": 4, "seo": 9}),
        ))
        assert merged["puntuacion_general"] == 4

    def test_one_dict_one_int(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"general": 3}),
            _base_analysis(puntuacion_general=7),
        ))
        assert merged["puntuacion_general"] == 3


# ── puntuacion_general: dict with "total" key ───────────────────────────

class TestPuntuacionGeneralDictTotal:
    def test_both_dicts_with_total(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"total": 9}),
            _base_analysis(puntuacion_general={"total": 5}),
        ))
        assert merged["puntuacion_general"] == 5

    def test_general_takes_precedence_over_total(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"general": 3, "total": 8}),
            _base_analysis(puntuacion_general=6),
        ))
        assert merged["puntuacion_general"] == 3


# ── puntuacion_general: dict without general/total ───────────────────────

class TestPuntuacionGeneralDictNoKey:
    def test_dict_without_known_keys_falls_back_to_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"seo": 8, "contenido": 7}),
            _base_analysis(puntuacion_general=5),
        ))
        # claude_score → 0, openai_score → 5; one is falsy → fallback branch
        assert merged["puntuacion_general"] == 5

    def test_both_dicts_without_known_keys(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"seo": 8}),
            _base_analysis(puntuacion_general={"contenido": 7}),
        ))
        assert merged["puntuacion_general"] == 0


# ── puntuacion_general: string ───────────────────────────────────────────

class TestPuntuacionGeneralString:
    def test_string_falls_back_to_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general="alto"),
            _base_analysis(puntuacion_general=6),
        ))
        assert merged["puntuacion_general"] == 6

    def test_both_strings_fall_back_to_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general="alto"),
            _base_analysis(puntuacion_general="medio"),
        ))
        assert merged["puntuacion_general"] == 0


# ── puntuacion_general: None ────────────────────────────────────────────

class TestPuntuacionGeneralNone:
    def test_none_falls_back_to_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=None),
            _base_analysis(puntuacion_general=4),
        ))
        assert merged["puntuacion_general"] == 4

    def test_both_none(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=None),
            _base_analysis(puntuacion_general=None),
        ))
        assert merged["puntuacion_general"] == 0


# ── aspectos_positivos: dicts (unhashable) ───────────────────────────────

class TestAspectosPositivosDicts:
    def test_dicts_do_not_crash(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(aspectos_positivos=[{"area": "seo", "detalle": "buen H1"}]),
            _base_analysis(aspectos_positivos=[{"area": "tono", "detalle": "natural"}]),
        ))
        assert len(merged["aspectos_positivos"]) == 2

    def test_duplicate_dicts_are_removed(self):
        dup = {"area": "seo", "detalle": "buen H1"}
        merged = _parse(_merge_json_analyses(
            _base_analysis(aspectos_positivos=[dup, {"area": "tono"}]),
            _base_analysis(aspectos_positivos=[dup]),
        ))
        assert len(merged["aspectos_positivos"]) == 2
        assert merged["aspectos_positivos"][0] == dup

    def test_mixed_strings_and_dicts(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(aspectos_positivos=["buen SEO", {"area": "tono"}]),
            _base_analysis(aspectos_positivos=["buen SEO", "buena estructura"]),
        ))
        assert len(merged["aspectos_positivos"]) == 3
        assert "buen SEO" in merged["aspectos_positivos"]
        assert "buena estructura" in merged["aspectos_positivos"]
        assert {"area": "tono"} in merged["aspectos_positivos"]
