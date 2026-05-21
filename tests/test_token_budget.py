# -*- coding: utf-8 -*-
"""
Tests de la fórmula pura de presupuesto de tokens (`core/token_budget.py`).

Fórmula pura → unit-testeable sin API keys ni Streamlit (ver .claude/rules/tests.md).
"""

import pytest

from core.token_budget import (
    compute_max_tokens,
    HTML_FLOOR,
    MODEL_OUTPUT_HARD_CAP,
    STAGE2_BUDGET,
)


class TestComputeMaxTokens:
    def test_monotonia_no_decrece_con_target(self):
        """A mayor target_length, el presupuesto HTML no decrece."""
        prev = 0
        for t in (500, 1000, 1400, 1800, 2500, 3000, 4000, 5000):
            budget = compute_max_tokens(t, stage=1)
            assert budget >= prev, f"presupuesto bajó en target={t}"
            prev = budget

    def test_cortos_no_malgastan(self):
        """Un arquetipo corto (1400w) usa bastante menos que el techo de 20000."""
        assert compute_max_tokens(1400, stage=1) < 20000

    def test_largos_suben(self):
        """Un arquetipo largo (4000w) sin techo llega a 24000 (> uno de 1800w)."""
        largo = compute_max_tokens(4000, stage=1)
        assert largo == 24000
        assert largo > compute_max_tokens(1800, stage=1)

    def test_zona_segura_medida(self):
        """1800w cae entre 8000 (truncaba) y 16000 (funcionaba) — evidencia A/B."""
        budget = compute_max_tokens(1800, stage=1)
        assert 8000 < budget <= 16000

    def test_stage2_menor_que_html(self):
        """Stage 2 (análisis) usa menos que Stage 1/3 para el mismo target."""
        for t in (1400, 1800, 4000):
            assert compute_max_tokens(t, stage=2) < compute_max_tokens(t, stage=1)
            assert compute_max_tokens(t, stage=2) < compute_max_tokens(t, stage=3)

    def test_stage2_es_fijo(self):
        """Stage 2 no depende de target_length (presupuesto fijo)."""
        assert compute_max_tokens(1400, stage=2) == STAGE2_BUDGET
        assert compute_max_tokens(5000, stage=2) == STAGE2_BUDGET

    def test_clamp_inferior_html_floor(self):
        """Targets diminutos nunca bajan del suelo HTML."""
        assert compute_max_tokens(100, stage=1) == HTML_FLOOR
        assert compute_max_tokens(1, stage=3) == HTML_FLOOR
        assert compute_max_tokens(0, stage=1) >= HTML_FLOOR  # 0 → default 1500 interno

    def test_clamp_superior_hard_cap(self):
        """Nunca se excede el límite duro del modelo, ni con targets enormes."""
        assert compute_max_tokens(99999, stage=1) == MODEL_OUTPUT_HARD_CAP
        assert compute_max_tokens(99999, stage=3) <= MODEL_OUTPUT_HARD_CAP

    def test_ceiling_clampa(self):
        """Con ceiling=20000, un 4000w (que pediría 24000) se clampa a 20000."""
        assert compute_max_tokens(4000, stage=1, ceiling=20000) == 20000

    def test_ceiling_none_usa_cap_modelo(self):
        """Sin techo configurado, el límite es el cap del modelo."""
        assert compute_max_tokens(99999, stage=1, ceiling=None) == MODEL_OUTPUT_HARD_CAP

    def test_ceiling_no_supera_cap_modelo(self):
        """Un ceiling absurdo se acota al cap duro del modelo."""
        assert compute_max_tokens(4000, stage=1, ceiling=999999) == 24000
        assert compute_max_tokens(99999, stage=1, ceiling=999999) == MODEL_OUTPUT_HARD_CAP

    def test_redondeo_a_mil(self):
        """El presupuesto HTML se redondea hacia arriba al millar."""
        for t in (1400, 1800, 2500, 3000, 4000):
            assert compute_max_tokens(t, stage=1) % 1000 == 0
