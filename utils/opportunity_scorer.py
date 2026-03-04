# -*- coding: utf-8 -*-
"""
Opportunity Scorer - PcComponentes Content Generator
Versión 1.0.0

Sistema de puntuación multi-factor para priorizar oportunidades SEO.
Combina datos de GSC y SEMrush para detectar:
- Quick wins (posiciones 11-20)
- Gaps de contenido
- Contenido en declive
- Oportunidades de mejora

Inspirado en SEO Machine (opportunity_scorer.py + research_quick_wins.py).
Adaptado para las fuentes de datos de Raichu (GSC + SEMrush).

PESOS:
- Impresiones/Volumen: 25%
- Posición actual: 20%
- Intención comercial: 20%
- Dificultad: 15%
- CTR gap: 10%
- Tendencia: 10%

Autor: PcComponentes - Product Discovery & Content
"""

import re
import logging
from typing import Dict, List, Optional, Any
from enum import Enum

__version__ = "1.0.0"

logger = logging.getLogger(__name__)


class OpportunityType(Enum):
    """Tipos de oportunidad SEO."""
    QUICK_WIN = "quick_win"           # Posición 11-20, cerca de página 1
    IMPROVEMENT = "improvement"        # Posición 1-10, puede subir a top 3
    NEW_CONTENT = "new_content"        # No rankea, gap de competidores
    DECLINING = "declining"            # Estaba bien, ahora cayendo
    UNDERPERFORMER = "underperformer"  # Buen ranking, CTR bajo


# CTR esperado por posición (promedios del sector)
EXPECTED_CTR = {
    1: 0.316, 2: 0.157, 3: 0.105, 4: 0.075, 5: 0.059,
    6: 0.048, 7: 0.041, 8: 0.035, 9: 0.031, 10: 0.027,
    11: 0.018, 12: 0.015, 13: 0.013, 14: 0.012, 15: 0.011,
    16: 0.010, 17: 0.009, 18: 0.008, 19: 0.008, 20: 0.007,
}

# Keywords con intención comercial alta en tech/e-commerce
COMMERCIAL_INTENT_PATTERNS = [
    r'\b(comprar|precio|mejor|comparativa|vs|versus|review|análisis)\b',
    r'\b(barato|oferta|descuento|rebaja|black friday|prime day)\b',
    r'\b(merece la pena|vale la pena|recomendación|top \d+)\b',
    r'\b(alternativa|sustituto|reemplazo)\b',
    r'\b(guía de compra|qué .+ comprar|cuál .+ elegir)\b',
]

# Keywords informacionales (menor valor comercial directo)
INFORMATIONAL_PATTERNS = [
    r'\b(qué es|cómo funciona|para qué sirve|diferencia entre)\b',
    r'\b(tutorial|guía|paso a paso|configurar|instalar)\b',
    r'\b(significado|definición|historia)\b',
]


class OpportunityScorer:
    """Calcula scores de oportunidad para keywords/páginas."""

    def score_keyword(
        self,
        keyword: str,
        position: float = 0,
        impressions: int = 0,
        clicks: int = 0,
        ctr: float = 0,
        url: str = "",
        search_volume: Optional[int] = None,
        difficulty: Optional[int] = None,
        previous_position: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calcula score de oportunidad para una keyword.

        Args:
            keyword: La keyword
            position: Posición media actual
            impressions: Impresiones en período
            clicks: Clics en período
            ctr: CTR actual
            url: URL que rankea
            search_volume: Volumen de búsqueda mensual (SEMrush)
            difficulty: Dificultad SEO 0-100 (SEMrush)
            previous_position: Posición anterior (para detectar declive)

        Returns:
            Dict con score, type, factors, recommendation
        """
        # Detectar tipo de oportunidad
        opp_type = self._classify_opportunity(position, ctr, previous_position)

        # Calcular cada factor
        volume_score = self._score_volume(impressions, search_volume)
        position_score = self._score_position(position, opp_type)
        intent_score = self._score_intent(keyword)
        difficulty_score = self._score_difficulty(difficulty)
        ctr_score = self._score_ctr_gap(position, ctr)
        trend_score = self._score_trend(position, previous_position)

        # Score ponderado
        composite = round(
            volume_score * 0.25
            + position_score * 0.20
            + intent_score * 0.20
            + difficulty_score * 0.15
            + ctr_score * 0.10
            + trend_score * 0.10,
            1,
        )

        # Potencial de clics si subimos a página 1
        potential_clicks = self._estimate_potential_clicks(
            position, impressions, search_volume
        )

        # Recomendación
        recommendation = self._get_recommendation(opp_type, composite, url)

        return {
            'keyword': keyword,
            'score': composite,
            'type': opp_type.value,
            'type_label': self._type_label(opp_type),
            'current': {
                'position': round(position, 1),
                'impressions': impressions,
                'clicks': clicks,
                'ctr': round(ctr, 4),
                'url': url,
            },
            'factors': {
                'volume': round(volume_score, 1),
                'position': round(position_score, 1),
                'intent': round(intent_score, 1),
                'difficulty': round(difficulty_score, 1),
                'ctr_gap': round(ctr_score, 1),
                'trend': round(trend_score, 1),
            },
            'potential_clicks': potential_clicks,
            'recommendation': recommendation,
        }

    def score_batch(self, keywords_data: List[Dict]) -> List[Dict]:
        """
        Puntúa un batch de keywords y las ordena por score.

        Args:
            keywords_data: Lista de dicts con campos de score_keyword()

        Returns:
            Lista ordenada por score descendente
        """
        results = []
        for kw_data in keywords_data:
            result = self.score_keyword(**kw_data)
            results.append(result)

        return sorted(results, key=lambda x: -x['score'])

    def find_quick_wins(self, gsc_data: List[Dict], min_impressions: int = 50) -> List[Dict]:
        """
        Identifica quick wins: keywords en posiciones 11-20 con impresiones.

        Args:
            gsc_data: Datos de GSC [{keyword, position, impressions, clicks, ctr, url}]
            min_impressions: Mínimo de impresiones

        Returns:
            Lista de oportunidades ordenadas por score
        """
        quick_wins = []
        for item in gsc_data:
            pos = item.get('position', 0)
            imps = item.get('impressions', 0)

            if 11 <= pos <= 20 and imps >= min_impressions:
                result = self.score_keyword(
                    keyword=item.get('keyword', item.get('query', '')),
                    position=pos,
                    impressions=imps,
                    clicks=item.get('clicks', 0),
                    ctr=item.get('ctr', 0),
                    url=item.get('url', item.get('page', '')),
                )
                quick_wins.append(result)

        return sorted(quick_wins, key=lambda x: -x['score'])

    # ====================================================================
    # FACTORES DE PUNTUACIÓN
    # ====================================================================

    def _score_volume(self, impressions: int, search_volume: Optional[int]) -> float:
        """Score basado en volumen (impresiones o search volume)."""
        volume = search_volume if search_volume else impressions
        if volume >= 10000:
            return 100
        elif volume >= 5000:
            return 85
        elif volume >= 1000:
            return 70
        elif volume >= 500:
            return 55
        elif volume >= 100:
            return 40
        elif volume >= 50:
            return 25
        return 10

    def _score_position(self, position: float, opp_type: OpportunityType) -> float:
        """Score basado en posición actual y proximidad al objetivo."""
        if opp_type == OpportunityType.QUICK_WIN:
            # Cuanto más cerca de posición 10, mejor
            if position <= 12:
                return 100
            elif position <= 15:
                return 80
            elif position <= 18:
                return 60
            return 40
        elif opp_type == OpportunityType.IMPROVEMENT:
            if position <= 3:
                return 50  # Ya está bien, menos urgente
            elif position <= 5:
                return 80
            elif position <= 7:
                return 90
            return 70
        return 50  # Otros tipos

    def _score_intent(self, keyword: str) -> float:
        """Score basado en intención comercial de la keyword."""
        kw_lower = keyword.lower()

        # Comercial
        commercial_matches = sum(
            1 for p in COMMERCIAL_INTENT_PATTERNS
            if re.search(p, kw_lower)
        )
        if commercial_matches >= 2:
            return 100
        elif commercial_matches == 1:
            return 80

        # Informacional
        info_matches = sum(
            1 for p in INFORMATIONAL_PATTERNS
            if re.search(p, kw_lower)
        )
        if info_matches >= 2:
            return 30
        elif info_matches == 1:
            return 50

        return 60  # Mixta/neutra

    def _score_difficulty(self, difficulty: Optional[int]) -> float:
        """Score basado en dificultad (invertido: menor dificultad = más oportunidad)."""
        if difficulty is None:
            return 50  # Sin datos → neutro
        if difficulty <= 20:
            return 100
        elif difficulty <= 40:
            return 80
        elif difficulty <= 60:
            return 60
        elif difficulty <= 80:
            return 40
        return 20

    def _score_ctr_gap(self, position: float, ctr: float) -> float:
        """Score basado en gap entre CTR actual y CTR esperado."""
        pos_int = min(20, max(1, int(round(position))))
        expected = EXPECTED_CTR.get(pos_int, 0.007)

        if expected <= 0 or ctr <= 0:
            return 50

        ratio = ctr / expected
        if ratio < 0.5:
            return 100  # Gran gap → oportunidad de mejora de titles/descriptions
        elif ratio < 0.8:
            return 70
        elif ratio < 1.0:
            return 50
        return 30  # CTR ya es bueno

    def _score_trend(self, position: float, previous_position: Optional[float]) -> float:
        """Score basado en tendencia (subiendo o bajando)."""
        if previous_position is None:
            return 50  # Sin datos → neutro

        change = previous_position - position  # Positivo = mejoró
        if change > 5:
            return 90  # Subiendo mucho → momentum
        elif change > 2:
            return 75
        elif change > 0:
            return 60
        elif change > -2:
            return 40
        elif change > -5:
            return 25  # Bajando
        return 10  # Cayendo fuerte → urgente

    # ====================================================================
    # CLASIFICACIÓN Y RECOMENDACIONES
    # ====================================================================

    def _classify_opportunity(
        self, position: float, ctr: float, previous_position: Optional[float]
    ) -> OpportunityType:
        """Clasifica el tipo de oportunidad."""
        if position == 0:
            return OpportunityType.NEW_CONTENT
        if previous_position and (position - previous_position) > 5:
            return OpportunityType.DECLINING
        if 11 <= position <= 20:
            return OpportunityType.QUICK_WIN
        if 1 <= position <= 10:
            pos_int = int(round(position))
            expected = EXPECTED_CTR.get(pos_int, 0.027)
            if ctr < expected * 0.5:
                return OpportunityType.UNDERPERFORMER
            return OpportunityType.IMPROVEMENT
        return OpportunityType.NEW_CONTENT

    def _type_label(self, opp_type: OpportunityType) -> str:
        """Label legible para el tipo de oportunidad."""
        labels = {
            OpportunityType.QUICK_WIN: "⚡ Quick Win",
            OpportunityType.IMPROVEMENT: "📈 Mejora",
            OpportunityType.NEW_CONTENT: "🆕 Contenido nuevo",
            OpportunityType.DECLINING: "📉 En declive",
            OpportunityType.UNDERPERFORMER: "🔧 Bajo rendimiento",
        }
        return labels.get(opp_type, "")

    def _estimate_potential_clicks(
        self, position: float, impressions: int, search_volume: Optional[int]
    ) -> int:
        """Estima clics potenciales si movemos a posiciones 5-7."""
        base_volume = search_volume if search_volume else impressions
        # CTR medio de posiciones 5-7
        target_ctr = (EXPECTED_CTR[5] + EXPECTED_CTR[6] + EXPECTED_CTR[7]) / 3
        return int(base_volume * target_ctr)

    def _get_recommendation(self, opp_type: OpportunityType, score: float, url: str) -> str:
        """Genera recomendación accionable."""
        has_url = bool(url)

        if opp_type == OpportunityType.QUICK_WIN:
            if has_url:
                return "Actualizar contenido existente: mejorar keyword density, añadir secciones, actualizar datos."
            return "Crear contenido nuevo optimizado para esta keyword."

        if opp_type == OpportunityType.IMPROVEMENT:
            return "Optimizar título y meta description para mejorar CTR. Añadir schema markup."

        if opp_type == OpportunityType.NEW_CONTENT:
            return "No hay contenido rankeando. Crear artículo completo con Raichu."

        if opp_type == OpportunityType.DECLINING:
            return "Contenido perdiendo posiciones. Reescritura urgente con datos actualizados."

        if opp_type == OpportunityType.UNDERPERFORMER:
            return "Buen ranking pero CTR bajo. Revisar title tag y meta description."

        return "Evaluar manualmente."
