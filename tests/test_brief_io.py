"""
Tests del brief I/O: exportar (Markdown) e importar (parse tolerante) el brief
de contenido nuevo.
"""
import re
from pathlib import Path

import pytest

from utils.brief_io import (
    build_brief_markdown,
    parse_brief_markdown,
    BRIEF_VERSION_TAG,
)


def _fill(md: str, field_id: str, value: str) -> str:
    """Inserta `value` bajo el 'Respuesta:' de la sección [field_id]."""
    pat = re.compile(
        r'(\[' + re.escape(field_id) + r'\][^\n]*\n(?:_[^\n]*_\n)?Respuesta:\n)',
        re.M,
    )
    return pat.sub(lambda m: m.group(1) + value + "\n", md, count=1)


# ── build_brief_markdown ───────────────────────────────────────────────────

class TestBuildBrief:
    def test_includes_version_tag_and_meta(self):
        md = build_brief_markdown("ARQ-7", mode="new", arquetipo_name="Ranking")
        assert BRIEF_VERSION_TAG in md
        assert "Modo: new" in md
        assert "[ARQ-7]" in md

    def test_includes_fixed_field_headers(self):
        md = build_brief_markdown("ARQ-3")
        for fid in ("keyword", "target_length", "secondary_keywords",
                    "additional_instructions", "authoritative_sources"):
            assert f"[{fid}]" in md

    def test_includes_guiding_questions(self):
        md = build_brief_markdown("ARQ-7")
        assert "[guiding_spec_0]" in md  # el arquetipo tiene preguntas específicas
        assert "Briefing" in md

    def test_prefills_values(self):
        md = build_brief_markdown(
            "ARQ-7", values={"keyword": "kw test", "target_length": 1800}
        )
        assert "kw test" in md
        assert "1800" in md

    def test_prefills_secondary_keywords_list(self):
        md = build_brief_markdown("ARQ-3", values={"secondary_keywords": ["a", "b"]})
        assert "a\nb" in md


# ── parse_brief_markdown ───────────────────────────────────────────────────

class TestParseBrief:
    def test_parses_meta(self):
        md = build_brief_markdown("ARQ-7", mode="new", arquetipo_name="Ranking")
        p = parse_brief_markdown(md)
        assert p["meta"]["arquetipo"] == "ARQ-7"
        assert p["meta"]["mode"] == "new"

    def test_parses_filled_fields(self):
        md = build_brief_markdown("ARQ-7")
        md = _fill(md, "keyword", "mejores portatiles 2026")
        md = _fill(md, "additional_instructions", "Enfoca en autonomia")
        md = _fill(md, "guiding_spec_0", "Cinco modelos")
        p = parse_brief_markdown(md)
        assert p["fields"]["keyword"] == "mejores portatiles 2026"
        assert p["fields"]["additional_instructions"] == "Enfoca en autonomia"
        assert p["fields"]["guiding_spec_0"] == "Cinco modelos"

    def test_empty_fields_are_empty_string(self):
        md = build_brief_markdown("ARQ-3")
        p = parse_brief_markdown(md)
        assert p["fields"].get("keyword") == ""

    def test_round_trip_values(self):
        md = build_brief_markdown(
            "ARQ-7", values={"keyword": "kw", "target_length": 1500}
        )
        p = parse_brief_markdown(md)
        assert p["fields"]["keyword"] == "kw"
        assert p["fields"]["target_length"] == "1500"

    def test_tolerant_without_respuesta_marker(self):
        # Sección con respuesta directa, sin la línea 'Respuesta:'
        md = (
            f"{BRIEF_VERSION_TAG}\nModo: new\nArquetipo: [ARQ-3] Educativo\n\n"
            "## [keyword] Keyword principal\n_ayuda_\nmi keyword directa\n"
        )
        p = parse_brief_markdown(md)
        assert p["fields"]["keyword"] == "mi keyword directa"

    def test_section_without_id_is_ignored(self):
        md = (
            "## Briefing — Preguntas del arquetipo\n"
            "## [keyword] Keyword\nRespuesta:\nvalor\n"
        )
        p = parse_brief_markdown(md)
        assert p["fields"].get("keyword") == "valor"
        # El header sin [id] no genera campo
        assert "Briefing" not in p["fields"]

    def test_empty_input(self):
        p = parse_brief_markdown("")
        assert p["meta"]["arquetipo"] is None
        assert p["fields"] == {}


# ── Wiring UI (source inspection) ──────────────────────────────────────────

class TestBriefWiring:
    def test_form_has_brief_io_section(self):
        src = Path("ui/inputs.py").read_text(encoding="utf-8")
        assert "_render_brief_io_section" in src
        assert "build_brief_markdown" in src
        assert "parse_brief_markdown" in src

    def test_apply_brief_seeds_widget_state(self):
        src = Path("ui/inputs.py").read_text(encoding="utf-8")
        assert "def _apply_brief(" in src
        # Pre-siembra de widgets de solo-key y re-init de los que usan value=
        assert "main_secondary_keywords" in src
        assert "st.session_state.pop('main_keyword'" in src

    def test_brief_only_in_new_mode(self):
        src = Path("ui/inputs.py").read_text(encoding="utf-8")
        # La sección de brief solo se renderiza en modo 'new'
        assert 'if mode == "new":' in src
