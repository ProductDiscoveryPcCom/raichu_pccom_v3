# -*- coding: utf-8 -*-
"""
Presupuesto dinámico de max_tokens por generación.

Calcula cuántos tokens de salida reservar en cada llamada al modelo en función
de `target_length` (palabras objetivo), de modo que los arquetipos largos no
trunquen y los cortos no malgasten un techo innecesariamente alto.

Módulo PURO e independiente de Streamlit / st.secrets → unit-testeable sin API
keys. El techo configurable (`core.config.MAX_TOKENS`, p.ej. el `max_tokens` de
secrets.toml) se pasa como parámetro `ceiling`.

Contexto: sustituye el `max_tokens` global y fijo (parche tras el bug de
truncación que cortaba el HTML de Stage 3 antes del <article> verdict). El guard
de truncación de `core/pipeline.py` queda como red de seguridad (backstop).
"""

import math
from typing import Optional

# Coste fijo de salida: <style> embebido (~1300+ tok) + boilerplate estructural
# (3 <article>, TOC, scaffolding de FAQs/tabla). Conservador.
STYLE_OVERHEAD_TOKENS = 2500

# Español ≈ 2 tok/palabra de prosa; el markup HTML (tags que envuelven cada
# bloque) ~duplica → ~4 tok por palabra de contenido renderizada en HTML.
TOKENS_PER_WORD_HTML = 4.0

SAFETY_FACTOR = 1.30        # margen sobre la estimación central
HTML_FLOOR = 8000           # nunca por debajo: incluso 1400w + CSS lo necesita
STAGE2_BUDGET = 4000        # análisis condensado (texto/JSON), no genera HTML

# Límite duro del modelo (Sonnet 4.x admite ~64k de salida; conservador).
MODEL_OUTPUT_HARD_CAP = 32000


def compute_max_tokens(
    target_length: int,
    stage: int,
    ceiling: Optional[int] = None,
) -> int:
    """Presupuesto de max_tokens para una generación.

    Args:
        target_length: palabras objetivo del contenido.
        stage: etapa del pipeline. 2 → análisis (texto/JSON, presupuesto fijo
            menor); 1 y 3 (y generators secundarios que regeneran HTML completo)
            → fórmula sobre target_length.
        ceiling: techo configurable (p.ej. `core.config.MAX_TOKENS` de
            secrets.toml). Si es None/0, se usa el cap duro del modelo.

    Returns:
        Presupuesto de tokens, acotado a [HTML_FLOOR, hard_cap] para HTML y a
        [_, hard_cap] para análisis. `hard_cap = min(ceiling, MODEL_OUTPUT_HARD_CAP)`.
    """
    hard = MODEL_OUTPUT_HARD_CAP if not ceiling else min(int(ceiling), MODEL_OUTPUT_HARD_CAP)

    if stage == 2:
        return min(STAGE2_BUDGET, hard)

    target = max(1, int(target_length or 1500))
    raw = STYLE_OVERHEAD_TOKENS + target * TOKENS_PER_WORD_HTML * SAFETY_FACTOR
    budget = int(math.ceil(raw / 1000.0) * 1000)          # redondeo a 1000
    return max(HTML_FLOOR, min(budget, hard))
