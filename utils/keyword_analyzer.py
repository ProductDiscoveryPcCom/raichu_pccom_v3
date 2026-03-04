# -*- coding: utf-8 -*-
"""
Keyword Analyzer - PcComponentes Content Generator
Versión 1.0.0

Análisis de densidad, distribución y placements de keywords en HTML.
Inspirado en SEO Machine (keyword_analyzer.py), adaptado para HTML español.

Sin dependencia de sklearn/numpy — funciona sin librerías ML.

Autor: PcComponentes - Product Discovery & Content
"""

import re
from typing import Dict, List, Optional, Any
from collections import Counter

__version__ = "1.0.0"


def _strip_html(html: str) -> str:
    """Extrae texto visible de HTML, decodificando entidades."""
    import html as html_module
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decodificar entidades HTML (&#37; → %, &aacute; → á, &euro; → €, etc.)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class KeywordAnalyzer:
    """Analiza densidad, distribución y placements de keywords en HTML."""

    def analyze(
        self,
        html_content: str,
        primary_keyword: str,
        secondary_keywords: Optional[List[str]] = None,
        target_density: float = 1.5,
    ) -> Dict[str, Any]:
        """
        Análisis completo de keywords.

        Args:
            html_content: HTML del contenido
            primary_keyword: Keyword principal
            secondary_keywords: Keywords secundarias
            target_density: Densidad objetivo (%)

        Returns:
            Dict con primary_keyword, secondary_keywords, placements,
                 distribution, related_terms
        """
        secondary_keywords = secondary_keywords or []
        text = _strip_html(html_content)
        words = text.split()
        word_count = len(words)
        text_lower = text.lower()
        kw_lower = primary_keyword.lower()

        # ===== Primary keyword analysis =====
        kw_count = text_lower.count(kw_lower)
        density = (kw_count / max(1, word_count)) * 100

        # Status
        if density < 0.5:
            status = 'muy_baja'
        elif density < 1.0:
            status = 'baja'
        elif density <= 2.0:
            status = 'óptima'
        elif density <= 2.5:
            status = 'alta'
        else:
            status = 'excesiva'

        # Stuffing risk
        stuffing_risk = 'ninguno'
        if density > 3.0:
            stuffing_risk = 'alto'
        elif density > 2.5:
            stuffing_risk = 'medio'
        elif density > 2.0:
            stuffing_risk = 'bajo'

        # ===== Placements críticos =====
        headings = re.findall(r'<(h[23])[^>]*>(.*?)</\1>', html_content, re.IGNORECASE | re.DOTALL)
        h2_texts = [re.sub(r'<[^>]+>', '', h[1]).lower() for h in headings if h[0].lower() == 'h2']
        h3_texts = [re.sub(r'<[^>]+>', '', h[1]).lower() for h in headings if h[0].lower() == 'h3']

        first_100_words = ' '.join(words[:100]).lower()
        last_150_words = ' '.join(words[-150:]).lower()

        placements = {
            'in_h2': any(kw_lower in h for h in h2_texts),
            'h2_count': sum(1 for h in h2_texts if kw_lower in h),
            'in_h3': any(kw_lower in h for h in h3_texts),
            'in_first_100_words': kw_lower in first_100_words,
            'in_conclusion': kw_lower in last_150_words,
            'total_headings_with_kw': sum(1 for h in h2_texts + h3_texts if kw_lower in h),
        }

        # ===== Distribución por tercios =====
        third = max(1, word_count // 3)
        sections_text = [
            ' '.join(words[:third]).lower(),
            ' '.join(words[third:2*third]).lower(),
            ' '.join(words[2*third:]).lower(),
        ]
        distribution = {
            'inicio': sections_text[0].count(kw_lower),
            'medio': sections_text[1].count(kw_lower),
            'final': sections_text[2].count(kw_lower),
        }

        # Flag de distribución desigual
        dist_values = list(distribution.values())
        total_dist = sum(dist_values)
        distribution_balanced = True
        if total_dist > 0:
            max_concentration = max(dist_values) / total_dist
            if max_concentration > 0.6:
                distribution_balanced = False

        # ===== Secondary keywords =====
        secondary_analysis = []
        for sec_kw in secondary_keywords:
            sec_lower = sec_kw.lower()
            sec_count = text_lower.count(sec_lower)
            sec_density = (sec_count / max(1, word_count)) * 100
            sec_status = 'óptima' if 0.3 <= sec_density <= 1.5 else ('baja' if sec_density < 0.3 else 'alta')
            secondary_analysis.append({
                'keyword': sec_kw,
                'count': sec_count,
                'density': round(sec_density, 2),
                'status': sec_status,
            })

        # ===== Related terms (frecuencia de bigramas relevantes) =====
        related_terms = self._extract_related_terms(text_lower, kw_lower)

        return {
            'primary_keyword': {
                'keyword': primary_keyword,
                'count': kw_count,
                'density': round(density, 2),
                'target_density': target_density,
                'status': status,
                'stuffing_risk': stuffing_risk,
            },
            'secondary_keywords': secondary_analysis,
            'placements': placements,
            'distribution': distribution,
            'distribution_balanced': distribution_balanced,
            'related_terms': related_terms,
            'word_count': word_count,
        }

    def _extract_related_terms(self, text: str, keyword: str, top_n: int = 10) -> List[Dict[str, Any]]:
        """Extrae bigramas frecuentes relacionados con el tema."""
        # Stopwords español
        stopwords = {
            'de', 'la', 'el', 'en', 'y', 'a', 'los', 'del', 'las', 'un',
            'por', 'con', 'una', 'su', 'para', 'es', 'al', 'lo', 'que',
            'se', 'más', 'no', 'como', 'pero', 'o', 'este', 'ya', 'te',
            'si', 'ha', 'son', 'muy', 'ser', 'le', 'tan', 'todo', 'hay',
            'nos', 'ni', 'sin', 'sobre', 'ese', 'esta', 'tiene', 'fue',
        }

        words = re.findall(r'\b[a-záéíóúñü]{3,}\b', text)
        words = [w for w in words if w not in stopwords and w not in keyword.split()]

        # Bigramas
        bigrams = []
        for i in range(len(words) - 1):
            bigrams.append(f"{words[i]} {words[i+1]}")

        counter = Counter(bigrams)
        top = counter.most_common(top_n)

        return [{'term': t, 'count': c} for t, c in top]

    def get_seo_score(self, analysis: Dict[str, Any]) -> int:
        """Calcula un score SEO 0-100 basado en el análisis de keywords."""
        score = 100
        primary = analysis['primary_keyword']
        placements = analysis['placements']

        # Density
        d = primary['density']
        if d < 0.5:
            score -= 30
        elif d < 1.0:
            score -= 15
        elif d > 2.5:
            score -= 25
        elif d > 2.0:
            score -= 10

        # Placements
        if not placements['in_h2']:
            score -= 20
        if not placements['in_first_100_words']:
            score -= 15
        if not placements['in_conclusion']:
            score -= 5

        # Distribution
        if not analysis['distribution_balanced']:
            score -= 10

        return max(0, score)


def analyze_keywords(
    html_content: str,
    primary_keyword: str,
    secondary_keywords: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Función de conveniencia para análisis de keywords."""
    analyzer = KeywordAnalyzer()
    return analyzer.analyze(html_content, primary_keyword, secondary_keywords)
