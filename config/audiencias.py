"""
Personas-tipo de PcComponentes para el Audience Tester (Stage 2.5).

Catálogo extensible de buyer personas para simular reacciones a un draft antes
del Stage 3. Mapeo `PERSONAS_POR_ARQUETIPO` permite auto-pick contextual; los
arquetipos no mapeados caen a "todas las personas" con log informativo.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Persona:
    id: str
    nombre: str
    edad: str           # rango libre: "16-22", "35-55"
    presupuesto: str
    contexto: str
    dolores: List[str] = field(default_factory=list)
    lenguaje: str = ""
    objeciones: List[str] = field(default_factory=list)
    criterios_decision: List[str] = field(default_factory=list)


PERSONAS: Dict[str, Persona] = {
    "gamer_entry": Persona(
        id="gamer_entry",
        nombre="Gamer entry-level",
        edad="16-22",
        presupuesto="<800€",
        contexto="Adolescente o universitario montando su primer setup gaming. Vive con padres o piso compartido. Decisión muchas veces aprobada por adulto.",
        dolores=[
            "Mucha jerga técnica que no entiende",
            "Miedo a equivocarse y desperdiciar dinero",
            "Comparar 20 modelos sin saber qué importa de verdad",
        ],
        lenguaje="Directo, casual, comparativas con jugabilidad real (FPS por juego).",
        objeciones=[
            "¿Esto me dura 3-4 años?",
            "¿Vale la pena pagar más por X?",
            "¿Qué hago si se rompe?",
        ],
        criterios_decision=["Relación calidad-precio", "Reviews de YouTubers", "FPS reales en juegos AAA"],
    ),
    "gamer_enthusiast": Persona(
        id="gamer_enthusiast",
        nombre="Gamer enthusiast",
        edad="25-35",
        presupuesto="1500-3500€",
        contexto="Conoce specs en detalle, sigue tech reviewers, tiene experiencia montando PCs. Quiere high-end pero no malgastar.",
        dolores=[
            "Encontrar el cuello de botella real",
            "Lanzamientos solapados (gen actual vs siguiente)",
            "Garantía y RMA en componentes caros",
        ],
        lenguaje="Técnico, comparativo, espera benchmarks concretos y datos.",
        objeciones=[
            "¿Por qué este y no el modelo Pro?",
            "¿Cuánto perderé si espero 3 meses?",
            "¿La fuente aguanta upgrade futuro?",
        ],
        criterios_decision=["Benchmarks independientes", "Roadmap del fabricante", "Garantía PcComponentes"],
    ),
    "creativo_pro": Persona(
        id="creativo_pro",
        nombre="Creativo profesional",
        edad="28-45",
        presupuesto="2000-5000€",
        contexto="Editor de video, diseñador 3D o fotógrafo profesional. Su PC es herramienta de trabajo, downtime = dinero perdido.",
        dolores=[
            "Soporte de software (Adobe, DaVinci, Blender)",
            "Fiabilidad para sesiones largas",
            "Color accuracy, calibración, periféricos",
        ],
        lenguaje="Profesional, orientado a workflow y tiempos de render.",
        objeciones=[
            "¿Qué soporte tengo si falla en plena entrega?",
            "¿Esto me sirve también para gaming ocasional?",
            "¿Factura para autónomos?",
        ],
        criterios_decision=["Estabilidad", "Soporte y SLA", "ROI sobre tiempo de trabajo"],
    ),
    "it_pro": Persona(
        id="it_pro",
        nombre="IT pro / sysadmin",
        edad="28-50",
        presupuesto="Variable (B2B)",
        contexto="Responsable de compras tecnológicas en pyme o departamento. Decide en función de TCO, soporte y reposición.",
        dolores=[
            "Estandarización de flota",
            "Garantía empresarial y plazos de RMA",
            "Compatibilidad con software corporativo",
        ],
        lenguaje="Conciso, orientado a especificaciones y contratos.",
        objeciones=[
            "¿Tiene cuenta para empresas?",
            "¿Plazo de reposición en caso de avería?",
            "¿Existen alternativas con mejor SLA?",
        ],
        criterios_decision=["TCO a 3 años", "Soporte empresarial", "Volumen / descuentos"],
    ),
    "comprador_familiar": Persona(
        id="comprador_familiar",
        nombre="Comprador familiar",
        edad="35-55",
        presupuesto="500-1200€",
        contexto="Padre o madre que va a regalar un PC a su hijo/a (gaming o estudios). NO es técnico, le abruma la jerga.",
        dolores=[
            "No entender qué necesita el chaval",
            "Miedo a tirar el dinero",
            "Preocupación por seguridad / parental control",
        ],
        lenguaje="Sencillo, evita tecnicismos, agradece comparativas tipo 'el PC X es como un coche Y'.",
        objeciones=[
            "¿Esto es para gaming o para estudiar?",
            "¿Necesita algo más además del PC?",
            "¿Cómo lo devuelvo si no le gusta?",
        ],
        criterios_decision=["Recomendación clara", "Garantía y devolución", "Que el hijo lo apruebe"],
    ),
}


# Mapeo arquetipo → personas recomendadas. Los códigos no listados caen al
# fallback de _pick_personas_for_arquetipo (= todas las personas).
PERSONAS_POR_ARQUETIPO: Dict[str, List[str]] = {
    "ARQ-4": list(PERSONAS.keys()),  # Review: audiencia amplia
    "ARQ-7": ["gamer_entry", "gamer_enthusiast"],  # Ranking gaming
    "ARQ-13": ["creativo_pro"],  # Setup creativo
}


def _pick_personas_for_arquetipo(arquetipo_code: str) -> List[str]:
    """
    Devuelve las personas relevantes para un arquetipo.

    Si el arquetipo no está mapeado, retorna TODAS las personas (la editora
    puede deseleccionar manualmente vía multi-select). Loguea para visibilidad.
    """
    if arquetipo_code in PERSONAS_POR_ARQUETIPO:
        return list(PERSONAS_POR_ARQUETIPO[arquetipo_code])
    logger.info(
        f"Arquetipo {arquetipo_code} sin mapeo de personas, usando todas ({len(PERSONAS)})"
    )
    return list(PERSONAS.keys())
