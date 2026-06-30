"""
Prompts del Audience Tester — simulación de reacción por persona.

Cada persona produce un JSON con nivel_conviccion, dudas, fricciones,
sugerencias y veredicto_compra. El merge_directive prepara el texto que se
inyecta como `audience_feedback` en `build_final_prompt_stage3` (parámetro
opcional retrocompatible).

Uso de prefill='{' en la llamada a Claude para forzar JSON desde el primer
carácter (ver `core/audience_test.py`). El prefill ya inyecta el `{` inicial; el
prompt NO debe pedir además "empieza con {" (produciría `{{` → JSON inválido).
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from config.audiencias import Persona


def coerce_conviction(value: Any) -> Optional[float]:
    """
    Coacciona `nivel_conviccion` a float de forma tolerante.

    El modelo a veces devuelve la convicción como string ("7") o la omite; sin
    esta coerción, `sum(...)` o `... < 6` sobre tipos mixtos elevan TypeError y
    descartan TODO el feedback de audiencia (no solo el de la persona afectada).
    Devuelve None si el valor falta o no es numérico, para que el llamador lo
    excluya de los agregados en vez de tratarlo como 0.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _persona_block(persona: Persona) -> str:
    return (
        f"Nombre: {persona.nombre}\n"
        f"Edad: {persona.edad}\n"
        f"Presupuesto: {persona.presupuesto}\n"
        f"Contexto: {persona.contexto}\n"
        f"Dolores actuales: {', '.join(persona.dolores) or 'n/a'}\n"
        f"Lenguaje preferido: {persona.lenguaje or 'n/a'}\n"
        f"Objeciones típicas: {', '.join(persona.objeciones) or 'n/a'}\n"
        f"Criterios de decisión: {', '.join(persona.criterios_decision) or 'n/a'}"
    )


def build_audience_test_prompt(draft_text: str, persona: Persona, keyword: str) -> str:
    """
    Construye el prompt para una persona simulando su lectura del draft.

    `draft_text` ya viene como texto plano (HTML sanitizado + strip).
    """
    return (
        "[ROL]\n"
        "Vas a actuar como una persona REAL leyendo un artículo de e-commerce.\n"
        "NO eres un asistente IA. Tu identidad para esta tarea:\n\n"
        f"{_persona_block(persona)}\n\n"
        "[TAREA]\n"
        f"Lee este artículo sobre \"{keyword}\" y responde como TÚ reaccionarías.\n"
        "NO seas educado por defecto: si algo te confunde o no te convence, dilo claro.\n"
        "Cita fragmentos LITERALES del artículo en las fricciones.\n\n"
        "[ARTÍCULO]\n"
        f"{draft_text}\n\n"
        "[OUTPUT — JSON estricto]\n"
        "{\n"
        "  \"nivel_conviccion\": int 0-10,\n"
        "  \"dudas_no_resueltas\": [\"...\", ...],     # 0-5 items\n"
        "  \"fricciones_copy\": [{\"cita\":\"texto literal\",\"problema\":\"...\"}, ...],\n"
        "  \"sugerencias\": [\"...\", ...],\n"
        "  \"veredicto_compra\": \"si\" | \"no\" | \"talvez\",\n"
        "  \"razon_veredicto\": \"string ≤ 150 chars\"\n"
        "}\n\n"
        "Responde SOLO con JSON válido, sin texto antes ni después.\n"
    )


def _format_fricciones(fricciones: List[Dict[str, str]]) -> str:
    if not fricciones:
        return "(ninguna)"
    parts = []
    for fr in fricciones[:5]:
        cita = fr.get("cita", "").strip()
        problema = fr.get("problema", "").strip()
        if cita and problema:
            parts.append(f"cita \"{cita}\" → {problema}")
    return "; ".join(parts) if parts else "(ninguna relevante)"


def build_audience_merge_directive(
    audience_results: Iterable[Dict[str, Any]],
) -> str:
    """
    Compone el bloque de texto que se inyecta en Stage 3 como `audience_feedback`.

    Cada item de `audience_results` es un dict:
        {"persona_id": str, "persona_nombre": str, "feedback": dict, "ok": bool}

    Sólo los OK contribuyen al merge. Si todos fallaron, retorna "".
    """
    valid = [r for r in audience_results if r.get("ok") and r.get("feedback")]
    if not valid:
        return ""

    convictions = [
        c for c in (coerce_conviction(r["feedback"].get("nivel_conviccion")) for r in valid)
        if c is not None
    ]
    avg = (sum(convictions) / len(convictions)) if convictions else 0.0

    lines = [
        f"[FEEDBACK DE AUDIENCIA SIMULADA — {len(valid)} personas testeadas]",
        f"Nivel medio de convicción: {avg:.1f}/10",
        "",
    ]

    for r in valid:
        fb = r["feedback"]
        conv = fb.get("nivel_conviccion", "?")
        veredicto = fb.get("veredicto_compra", "?")
        razon = fb.get("razon_veredicto", "")
        dudas = fb.get("dudas_no_resueltas", []) or []
        sug = fb.get("sugerencias", []) or []
        fric = fb.get("fricciones_copy", []) or []

        lines.append(f"Persona \"{r['persona_nombre']}\" (convicción {conv}/10, veredicto: {veredicto}):")
        if razon:
            lines.append(f"  Razón: {razon}")
        if dudas:
            lines.append(f"  Dudas: {'; '.join(dudas[:5])}")
        if fric:
            lines.append(f"  Fricciones: {_format_fricciones(fric)}")
        if sug:
            lines.append(f"  Sugerencias: {'; '.join(sug[:5])}")
        lines.append("")

    lines.extend([
        "[INSTRUCCIÓN PARA STAGE 3]",
        "Aborda explícitamente las dudas con convicción <6 y las fricciones citadas literalmente.",
        "Donde haya divergencia entre personas, prioriza la de menor convicción.",
        "NO menciones que se hizo un focus group simulado.",
    ])

    return "\n".join(lines)
