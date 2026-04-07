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
    def test_dict_without_known_keys_min_is_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"seo": 8, "contenido": 7}),
            _base_analysis(puntuacion_general=5),
        ))
        # claude_score → 0 (shape inesperado), openai_score → 5
        # P3.1: el min real es 0, no se ignora la señal crítica
        assert merged["puntuacion_general"] == 0

    def test_both_dicts_without_known_keys(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general={"seo": 8}),
            _base_analysis(puntuacion_general={"contenido": 7}),
        ))
        assert merged["puntuacion_general"] == 0


# ── puntuacion_general: string ───────────────────────────────────────────

class TestPuntuacionGeneralString:
    def test_string_one_side_min_is_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general="alto"),
            _base_analysis(puntuacion_general=6),
        ))
        # claude_score → 0 (string normalizado), openai_score → 6
        # P3.1: el min real es 0
        assert merged["puntuacion_general"] == 0

    def test_both_strings_fall_back_to_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general="alto"),
            _base_analysis(puntuacion_general="medio"),
        ))
        assert merged["puntuacion_general"] == 0


# ── puntuacion_general: None ────────────────────────────────────────────

class TestPuntuacionGeneralNone:
    def test_none_one_side_min_is_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=None),
            _base_analysis(puntuacion_general=4),
        ))
        # claude_score → 0 (None normalizado), openai_score → 4
        # P3.1: el min real es 0
        assert merged["puntuacion_general"] == 0

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


# ── P3.1: min_score must respect 0 as a valid critical signal ────────────

class TestMinScoreRespectsZero:
    def test_claude_zero_openai_seventy_returns_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=0),
            _base_analysis(puntuacion_general=70),
        ))
        # P3.1: 0 es señal crítica válida — el min real es 0, no 70
        assert merged["puntuacion_general"] == 0

    def test_claude_seventy_openai_zero_returns_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=70),
            _base_analysis(puntuacion_general=0),
        ))
        assert merged["puntuacion_general"] == 0

    def test_both_zero_returns_zero(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(puntuacion_general=0),
            _base_analysis(puntuacion_general=0),
        ))
        assert merged["puntuacion_general"] == 0


# ── P3.3: dedup of frases_ia / enlaces_faltantes preserves order ─────────

class TestDedupPreservesOrder:
    def test_frases_ia_order_preserved(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(tono={"frases_ia_detectadas": ["en resumen", "en conclusión", "es importante destacar"]}),
            _base_analysis(tono={"frases_ia_detectadas": ["en conclusión", "cabe mencionar"]}),
        ))
        phrases = merged.get("tono", {}).get("frases_ia_detectadas", [])
        # Orden esperado: claude primero, luego nuevos de openai. Sin duplicados.
        assert phrases == ["en resumen", "en conclusión", "es importante destacar", "cabe mencionar"]

    def test_enlaces_faltantes_order_preserved(self):
        merged = _parse(_merge_json_analyses(
            _base_analysis(enlaces={"faltantes": ["url-a", "url-b", "url-c"]}),
            _base_analysis(enlaces={"faltantes": ["url-b", "url-d"]}),
        ))
        missing = merged.get("enlaces", {}).get("faltantes", [])
        assert missing == ["url-a", "url-b", "url-c", "url-d"]


# ── P3.7: log warning when puntuacion_general dict has unexpected shape ──

class TestPuntuacionGeneralUnexpectedShapeLog:
    def test_logs_warning_for_claude_unknown_shape(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="core.openai_client"):
            _merge_json_analyses(
                _base_analysis(puntuacion_general={"seo": 8, "contenido": 7}),
                _base_analysis(puntuacion_general=5),
            )
        assert any(
            "puntuacion_general dict shape inesperado (claude)" in rec.message
            for rec in caplog.records
        )

    def test_logs_warning_for_openai_unknown_shape(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="core.openai_client"):
            _merge_json_analyses(
                _base_analysis(puntuacion_general=5),
                _base_analysis(puntuacion_general={"seo": 8}),
            )
        assert any(
            "puntuacion_general dict shape inesperado (openai)" in rec.message
            for rec in caplog.records
        )

    def test_no_warning_when_dict_has_general(self, caplog):
        import logging
        with caplog.at_level(logging.WARNING, logger="core.openai_client"):
            _merge_json_analyses(
                _base_analysis(puntuacion_general={"general": 6}),
                _base_analysis(puntuacion_general={"general": 4}),
            )
        assert not any(
            "puntuacion_general dict shape inesperado" in rec.message
            for rec in caplog.records
        )
