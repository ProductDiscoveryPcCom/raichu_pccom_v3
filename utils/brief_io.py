# -*- coding: utf-8 -*-
"""
Brief I/O - PcComponentes Content Generator

Exporta/importa el "brief" de contenido nuevo como Markdown legible para que un
equipo de expertos lo rellene offline y luego se reimporte para autocompletar el
formulario.

Formato: Markdown amigable. Cada campo es una sección con un código estable entre
corchetes en el título (`## [id] Etiqueta`) que NO debe modificarse; el experto
escribe bajo la línea `Respuesta:`. El parser es tolerante (acepta que falte el
marcador `Respuesta:`).

Campos: keyword, target_length, secondary_keywords, additional_instructions,
authoritative_sources, y las preguntas del briefing del arquetipo
(guiding_spec_N / guiding_univ_N).

Autor: PcComponentes - Product Discovery & Content
"""

import logging
import re
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

BRIEF_VERSION_TAG = "<!-- raichu-brief:v1 -->"

# Campos fijos del brief: id → (etiqueta, ayuda)
_FIELD_LABELS: List[Tuple[str, str, str]] = [
    ("keyword", "Keyword principal", "La keyword objetivo del contenido (2-100 caracteres)."),
    ("target_length", "Longitud objetivo (palabras)", "Número aproximado de palabras (500-5000)."),
    ("secondary_keywords", "Keywords secundarias", "Una por línea."),
    ("additional_instructions", "Instrucciones adicionales", "Indicaciones específicas para la redacción."),
    ("authoritative_sources", "Fuentes autoritativas", "URLs o fuentes que deben primar (una por línea)."),
]

_HEADER_RE = re.compile(r'^#{2,3}\s*\[(?P<id>[A-Za-z0-9_\-]+)\]\s*(?P<label>.*?)\s*$')
_ARQ_RE = re.compile(r'Arquetipo:\s*\[(?P<code>[A-Za-z0-9\-]+)\]', re.IGNORECASE)
_MODE_RE = re.compile(r'Modo:\s*(?P<mode>[A-Za-z_]+)', re.IGNORECASE)


# ============================================================================
# PREGUNTAS DEL BRIEFING (mismo orden que el formulario)
# ============================================================================

def _get_guiding(arquetipo_code: str) -> Tuple[List[str], List[str]]:
    """Devuelve (preguntas_especificas, preguntas_universales) del arquetipo,
    en el MISMO orden que usa el formulario (para que los índices casen)."""
    specific: List[str] = []
    universal: List[str] = []
    try:
        from config.arquetipos import get_guiding_questions
        specific = list(get_guiding_questions(arquetipo_code, include_universal=False) or [])
    except Exception:
        pass
    try:
        from config.arquetipos import PREGUNTAS_UNIVERSALES
        universal = list(PREGUNTAS_UNIVERSALES or [])
    except Exception:
        pass
    return specific, universal


# ============================================================================
# EXPORT — generar Markdown
# ============================================================================

def _section(field_id: str, label: str, help_text: str, value: str = "", level: int = 2) -> str:
    hashes = "#" * level
    parts = [f"{hashes} [{field_id}] {label}"]
    if help_text:
        parts.append(f"_{help_text}_")
    parts.append("Respuesta:")
    parts.append(value.strip() if value else "")
    return "\n".join(parts)


def build_brief_markdown(
    arquetipo_code: str,
    mode: str = "new",
    values: Optional[Dict[str, Any]] = None,
    arquetipo_name: str = "",
) -> str:
    """Genera el brief en Markdown para el arquetipo dado.

    `values` (opcional) precarga campos ya rellenos: keys = ids de campo
    (keyword, target_length, secondary_keywords, additional_instructions,
    authoritative_sources) y 'guiding' = {widget_id: respuesta}.
    """
    values = values or {}
    guiding_vals = values.get("guiding", {}) if isinstance(values.get("guiding"), dict) else {}

    out: List[str] = []
    out.append("# 📋 Brief de contenido — PcComponentes")
    out.append("")
    out.append(
        "Instrucciones: rellena el texto bajo cada `Respuesta:`. NO modifiques los "
        "títulos `##`/`###` ni los códigos entre corchetes `[...]`. Al terminar, "
        "sube este archivo en la app para autocompletar el formulario."
    )
    out.append("")
    out.append(BRIEF_VERSION_TAG)
    out.append(f"Modo: {mode}")
    _arq_label = f"[{arquetipo_code}] {arquetipo_name}".strip()
    out.append(f"Arquetipo: {_arq_label}")
    out.append("")

    # Campos fijos
    for fid, label, help_text in _FIELD_LABELS:
        val = values.get(fid, "")
        if isinstance(val, (list, tuple)):
            val = "\n".join(str(v) for v in val)
        elif val is None:
            val = ""
        else:
            val = str(val)
        out.append(_section(fid, label, help_text, val, level=2))
        out.append("")

    # Briefing del arquetipo
    specific, universal = _get_guiding(arquetipo_code)
    if specific or universal:
        out.append("## Briefing — Preguntas del arquetipo")
        out.append("")
        for i, q in enumerate(specific):
            out.append(_section(f"guiding_spec_{i}", q, "", guiding_vals.get(f"guiding_spec_{i}", ""), level=3))
            out.append("")
        for i, q in enumerate(universal):
            out.append(_section(f"guiding_univ_{i}", q, "", guiding_vals.get(f"guiding_univ_{i}", ""), level=3))
            out.append("")

    return "\n".join(out).rstrip() + "\n"


# ============================================================================
# IMPORT — parsear Markdown
# ============================================================================

def _extract_answer(body_lines: List[str]) -> str:
    """Extrae la respuesta de un bloque de sección de forma tolerante."""
    # Buscar marcador 'Respuesta:'
    resp_idx = None
    for i, line in enumerate(body_lines):
        if line.strip().lower().rstrip(':') == 'respuesta':
            resp_idx = i
            break
    if resp_idx is not None:
        candidate = body_lines[resp_idx + 1:]
    else:
        # Fallback: descartar líneas de ayuda en cursiva (_..._) y citas (>)
        candidate = [
            l for l in body_lines
            if not (l.strip().startswith('_') and l.strip().endswith('_'))
            and not l.strip().startswith('>')
        ]
    return "\n".join(candidate).strip()


def parse_brief_markdown(text: str) -> Dict[str, Any]:
    """Parsea un brief Markdown a un dict estructurado.

    Returns:
        {
          'meta': {'arquetipo': 'ARQ-7'|None, 'mode': 'new'|None},
          'fields': {field_id: valor, ...},   # incluye guiding_spec_N / guiding_univ_N
        }
    """
    result: Dict[str, Any] = {'meta': {'arquetipo': None, 'mode': None}, 'fields': {}}
    if not text:
        return result

    lines = text.splitlines()

    # Meta (arquetipo, modo) — buscar en las primeras líneas (encabezado)
    head = "\n".join(lines[:30])
    m_arq = _ARQ_RE.search(head)
    if m_arq:
        result['meta']['arquetipo'] = m_arq.group('code')
    m_mode = _MODE_RE.search(head)
    if m_mode:
        result['meta']['mode'] = m_mode.group('mode').lower()

    # Secciones por encabezado con [id]
    current_id: Optional[str] = None
    current_body: List[str] = []

    def _flush():
        if current_id is not None:
            val = _extract_answer(current_body)
            result['fields'][current_id] = val

    for line in lines:
        h = _HEADER_RE.match(line)
        if h:
            _flush()
            current_id = h.group('id')
            current_body = []
        elif re.match(r'^#{1,6}\s', line):
            # Encabezado SIN [id] (p.ej. "## Briefing — ...") cierra la sección actual
            _flush()
            current_id = None
            current_body = []
        elif current_id is not None:
            current_body.append(line)
    _flush()

    return result


__all__ = [
    '__version__',
    'BRIEF_VERSION_TAG',
    'build_brief_markdown',
    'parse_brief_markdown',
]
