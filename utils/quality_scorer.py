# -*- coding: utf-8 -*-
"""
Quality Scorer - PcComponentes Content Generator
Versión 1.0.0

Sistema de puntuación multi-dimensional para evaluar calidad del contenido
generado ANTES de publicar. Inspirado en SEO Machine (content_scorer.py),
adaptado al español y al contexto de PcComponentes.

5 DIMENSIONES (total = 100 puntos ponderados):
- Humanidad/Voz (30%): Ausencia de patrones IA, recursos conversacionales
- Especificidad (25%): Cifras concretas, nombres de producto, datos reales
- Balance estructural (20%): Ratio prosa vs listas, distribución de headings
- SEO (15%): Keyword density, placements críticos, enlaces
- Legibilidad (10%): Longitud de frases, párrafos, variedad rítmica

THRESHOLD: Score >= 70 → publicable. < 70 → necesita revisión.

Autor: PcComponentes - Product Discovery & Content
"""

import re
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

__version__ = "1.0.0"

# ============================================================================
# CONSTANTES
# ============================================================================

PASS_THRESHOLD = 70

WEIGHTS = {
    'humanidad': 0.30,
    'especificidad': 0.25,
    'balance_estructural': 0.20,
    'seo': 0.15,
    'legibilidad': 0.10,
}

# Frases IA en español (alta precisión)
AI_PHRASES_ES = [
    r'en el mundo actual',
    r'en la era digital',
    r'sin lugar a dudas',
    r'es importante destacar',
    r'cabe mencionar que',
    r'es fundamental',
    r'a la hora de',
    r'en lo que respecta',
    r'ofrece una experiencia',
    r'brinda la posibilidad',
    r'esto se traduce en',
    r'lo que permite',
    r'no es de extra[ñn]ar',
    r'en definitiva',
    r'cabe destacar',
    r'resulta especialmente',
    r'en este sentido',
    r'hoy en día',
    r'en el panorama actual',
    r'juega un papel (crucial|fundamental|clave)',
    r'en última instancia',
    r'a lo largo de este artículo',
    r'como hemos (visto|mencionado)',
    r'es importante tener en cuenta',
    r'se ha convertido en',
    r'desempeña un papel',
]

# Palabras vagas en español que reducen especificidad
VAGUE_WORDS_ES = [
    r'\bmuchos?\b', r'\bvarios?\b', r'\bnumerosos?\b',
    r'\balgunos?\b', r'\bbastante\b', r'\bsignificativ[ao]s?\b',
    r'\bconsiderable\b', r'\bimportante\b', r'\besencial\b',
    r'\bfundamental\b', r'\bclave\b', r'\bcrucial\b',
    r'\bgeneralmente\b', r'\bnormalmente\b', r'\btípicamente\b',
    r'\bhabitual\b', r'\bfrecuente\b', r'\brelativamente\b',
    r'\bbastante\b', r'\bmuy\b', r'\brealmente\b',
]

# Patrones de especificidad (cifras, nombres, datos concretos)
SPECIFICITY_PATTERNS = [
    r'\b\d{1,3}[.,]?\d*\s*%',           # Porcentajes: 45%, 12,5%
    r'\b\d{1,3}[.,]\d{2}\s*€',           # Precios: 499,99€
    r'\b\d+\s*(?:GB|TB|MHz|GHz|MP|mAh|W|pulgadas|")\b',  # Specs técnicas
    r'\b(?:20[12]\d)\b',                   # Años: 2024, 2025
    r'\b\d+(?:\.\d{3})*\s*(?:usuarios?|unidades?|ventas|descargas)\b',  # Cantidades
    r'(?:[A-Z][a-záéíóú]+(?:\s+[A-Z][a-záéíóú]+)?)\s+(?:dijo|afirmó|explicó|señaló)',  # Citas
    r'\"[^\"]{10,}\"',                     # Texto entrecomillado
]

# Recursos conversacionales
CONVERSATIONAL_PATTERNS_ES = [
    r'\([^)]{5,60}\)',       # Paréntesis incidentales
    r'\?(?:\s|$)',           # Preguntas
    r'\b¿',                  # Apertura de pregunta
    r'\bno te pierdas\b',
    r'\bojo\b',
    r'\bvamos a\b',
    r'\bla verdad es\b',
    r'\blo cierto es\b',
    r'\beso sí\b',
    r'\bpor cierto\b',
    r'\bahora bien\b',
]


# ============================================================================
# FUNCIONES AUXILIARES
# ============================================================================

def _strip_html(html: str) -> str:
    """Extrae texto visible de HTML, decodificando entidades."""
    if not html or not isinstance(html, str):
        return ''
    import html as html_module
    # Eliminar style y script
    text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Eliminar tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decodificar entidades HTML (&#37; → %, &aacute; → á, &euro; → €, etc.)
    text = html_module.unescape(text)
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _count_syllables_es(word: str) -> int:
    """Cuenta sílabas en español (aproximación)."""
    word = word.lower()
    vowels = 'aeiouáéíóú'
    count = 0
    prev_vowel = False
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_vowel:
            count += 1
        prev_vowel = is_vowel
    return max(count, 1)


def _flesch_fernandez_huerta(text: str) -> float:
    """
    Calcula legibilidad Flesch adaptada al español (Fernández-Huerta).
    Fórmula: 206.84 - 60*(sílabas/palabras) - 1.02*(palabras/frases)
    """
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    words = text.split()

    if not words or not sentences:
        return 60.0  # Default neutro

    total_syllables = sum(_count_syllables_es(w) for w in words)
    syllables_per_word = total_syllables / len(words)
    words_per_sentence = len(words) / len(sentences)

    score = 206.84 - 60 * syllables_per_word - 1.02 * words_per_sentence
    return max(0, min(100, score))


# ============================================================================
# SCORER PRINCIPAL
# ============================================================================

class QualityScorer:
    """Evaluador multi-dimensional de calidad de contenido."""

    def score(
        self,
        html_content: str,
        keyword: str = "",
        secondary_keywords: Optional[List[str]] = None,
        target_length: int = 1500,
    ) -> Dict[str, Any]:
        """
        Evalúa calidad del contenido en 5 dimensiones.

        Args:
            html_content: HTML del contenido generado
            keyword: Keyword principal
            secondary_keywords: Keywords secundarias
            target_length: Longitud objetivo en palabras

        Returns:
            Dict con composite_score, passed, dimensions, priority_fixes
        """
        if not html_content:
            return {
                'composite_score': 0, 'passed': False,
                'dimensions': {d: {'score': 0, 'issues': []} for d in WEIGHTS},
                'priority_fixes': [],
            }

        text = _strip_html(html_content)
        secondary_keywords = secondary_keywords or []

        # Evaluar cada dimensión
        humanidad = self._score_humanidad(text)
        especificidad = self._score_especificidad(text)
        balance = self._score_balance_estructural(html_content, text)
        seo = self._score_seo(html_content, text, keyword, secondary_keywords)
        legibilidad = self._score_legibilidad(text)

        # Score compuesto ponderado
        composite = round(
            humanidad['score'] * WEIGHTS['humanidad']
            + especificidad['score'] * WEIGHTS['especificidad']
            + balance['score'] * WEIGHTS['balance_estructural']
            + seo['score'] * WEIGHTS['seo']
            + legibilidad['score'] * WEIGHTS['legibilidad'],
            1,
        )

        passed = composite >= PASS_THRESHOLD

        # Recoger issues y priorizar por impacto
        all_issues = []
        for dim_name, dim_data in [
            ('humanidad', humanidad),
            ('especificidad', especificidad),
            ('balance_estructural', balance),
            ('seo', seo),
            ('legibilidad', legibilidad),
        ]:
            for issue in dim_data.get('issues', []):
                weight = WEIGHTS[dim_name]
                deficit = 100 - dim_data['score']
                issue['dimension'] = dim_name
                issue['impact'] = round(weight * deficit, 1)
                all_issues.append(issue)

        priority_fixes = sorted(all_issues, key=lambda x: -x['impact'])[:5]

        return {
            'composite_score': composite,
            'passed': passed,
            'threshold': PASS_THRESHOLD,
            'dimensions': {
                'humanidad': {
                    'score': humanidad['score'],
                    'weight': WEIGHTS['humanidad'],
                    'label': 'Humanidad / Voz',
                    'issues': humanidad.get('issues', []),
                },
                'especificidad': {
                    'score': especificidad['score'],
                    'weight': WEIGHTS['especificidad'],
                    'label': 'Especificidad',
                    'issues': especificidad.get('issues', []),
                },
                'balance_estructural': {
                    'score': balance['score'],
                    'weight': WEIGHTS['balance_estructural'],
                    'label': 'Balance estructural',
                    'issues': balance.get('issues', []),
                },
                'seo': {
                    'score': seo['score'],
                    'weight': WEIGHTS['seo'],
                    'label': 'SEO',
                    'issues': seo.get('issues', []),
                },
                'legibilidad': {
                    'score': legibilidad['score'],
                    'weight': WEIGHTS['legibilidad'],
                    'label': 'Legibilidad',
                    'issues': legibilidad.get('issues', []),
                },
            },
            'priority_fixes': priority_fixes,
        }

    # ========================================================================
    # DIMENSIÓN 1: HUMANIDAD (30%)
    # ========================================================================

    def _score_humanidad(self, text: str) -> Dict[str, Any]:
        """Evalúa ausencia de patrones IA y presencia de recursos conversacionales."""
        score = 100
        issues = []
        text_lower = text.lower()

        # Penalizar frases IA encontradas
        ai_count = 0
        for pattern in AI_PHRASES_ES:
            matches = re.findall(pattern, text_lower)
            ai_count += len(matches)

        if ai_count > 0:
            penalty = min(40, ai_count * 8)  # Máx -40 puntos
            score -= penalty
            issues.append({
                'description': f'{ai_count} frases típicas de IA detectadas. Reescribir con lenguaje más natural.',
                'severity': 'high' if ai_count >= 3 else 'medium',
            })

        # Bonus por recursos conversacionales
        conv_count = 0
        for pattern in CONVERSATIONAL_PATTERNS_ES:
            conv_count += len(re.findall(pattern, text_lower))

        words = text.split()
        word_count = len(words)
        conv_ratio = conv_count / max(1, word_count / 200)  # Por cada 200 palabras

        if conv_ratio < 1.0:
            penalty = min(20, int((1.0 - conv_ratio) * 20))
            score -= penalty
            issues.append({
                'description': 'Añadir preguntas retóricas, paréntesis incidentales o expresiones coloquiales.',
                'severity': 'medium',
            })

        # Penalizar palabras vagas excesivas
        vague_count = 0
        for pattern in VAGUE_WORDS_ES:
            vague_count += len(re.findall(pattern, text_lower))

        vague_ratio = vague_count / max(1, word_count) * 100
        if vague_ratio > 3.0:
            penalty = min(15, int((vague_ratio - 3.0) * 5))
            score -= penalty
            issues.append({
                'description': f'{vague_count} palabras vagas ({vague_ratio:.1f}%). Reemplazar por cifras o datos concretos.',
                'severity': 'low',
            })

        return {'score': max(0, score), 'issues': issues}

    # ========================================================================
    # DIMENSIÓN 2: ESPECIFICIDAD (25%)
    # ========================================================================

    def _score_especificidad(self, text: str) -> Dict[str, Any]:
        """Evalúa presencia de datos concretos, cifras y nombres."""
        score = 100
        issues = []
        words = text.split()
        word_count = len(words)

        # Contar patrones de especificidad
        spec_count = 0
        for pattern in SPECIFICITY_PATTERNS:
            spec_count += len(re.findall(pattern, text))

        # Target: ~1 dato concreto por cada 150 palabras
        target_specs = max(3, word_count // 150)
        spec_ratio = spec_count / max(1, target_specs)

        if spec_ratio < 0.5:
            penalty = min(40, int((1.0 - spec_ratio) * 40))
            score -= penalty
            issues.append({
                'description': f'Solo {spec_count} datos concretos (objetivo: {target_specs}+). Añadir cifras, precios, specs técnicas.',
                'severity': 'high',
            })
        elif spec_ratio < 1.0:
            penalty = min(15, int((1.0 - spec_ratio) * 15))
            score -= penalty
            issues.append({
                'description': f'{spec_count} datos concretos, se pueden añadir {target_specs - spec_count} más.',
                'severity': 'low',
            })

        # Detectar nombres propios (marcas, productos) - incluye all-caps
        # Pattern 1: CamelCase/TitleCase (Asus, Strix, Katana)
        titlecase_brands = re.findall(r'\b[A-Z][a-z]{2,}(?:\s+[A-Z][a-z]+)*\b', text)
        # Pattern 2: All-caps brands (ASUS, MSI, NVIDIA, AMD, RTX, GPU, SSD)
        allcaps_brands = re.findall(r'\b[A-Z]{2,}(?:\s+[A-Z]{2,})*\b', text)
        # Filtrar siglas comunes que no son marcas
        noise = {'HTML', 'CSS', 'FAQ', 'URL', 'SEO', 'CTA', 'RAM', 'SSD', 'HDD', 'USB', 'LED', 'LCD', 'IPS'}
        allcaps_brands = [b for b in allcaps_brands if b not in noise]
        unique_brands = set(titlecase_brands + allcaps_brands)
        if len(unique_brands) < 2:
            score -= 10
            issues.append({
                'description': 'Mencionar marcas o productos específicos para mayor credibilidad.',
                'severity': 'medium',
            })

        return {'score': max(0, score), 'issues': issues}

    # ========================================================================
    # DIMENSIÓN 3: BALANCE ESTRUCTURAL (20%)
    # ========================================================================

    def _score_balance_estructural(self, html: str, text: str) -> Dict[str, Any]:
        """Evalúa ratio prosa vs listas y distribución de headings."""
        score = 100
        issues = []

        # Contar elementos de lista en el HTML raw (más fiable que texto plano)
        list_items = len(re.findall(r'<li[\s>]', html, re.IGNORECASE))
        # Contar párrafos
        paragraphs = len(re.findall(r'<p[\s>]', html, re.IGNORECASE))

        total_blocks = max(1, list_items + paragraphs)
        prose_ratio = paragraphs / total_blocks

        # Target: 40-70% prosa
        if prose_ratio < 0.40:
            penalty = min(30, int((0.40 - prose_ratio) * 75))
            score -= penalty
            issues.append({
                'description': f'Demasiadas listas ({list_items} items vs {paragraphs} párrafos). Convertir algunas en párrafos narrativos.',
                'severity': 'high',
            })
        elif prose_ratio > 0.90 and paragraphs > 5:
            penalty = min(15, int((prose_ratio - 0.90) * 150))
            score -= penalty
            issues.append({
                'description': f'Contenido muy denso en texto ({paragraphs} párrafos, {list_items} items de lista). Añadir listas o tablas para mejorar escaneo.',
                'severity': 'low',
            })

        # Verificar distribución de headings
        headings = re.findall(r'<h[23][^>]*>', html, re.IGNORECASE)
        words = text.split()
        word_count = len(words)

        if word_count > 500:
            expected_headings = max(3, word_count // 350)
            if len(headings) < expected_headings:
                score -= 15
                issues.append({
                    'description': f'Solo {len(headings)} subtítulos para {word_count} palabras. Añadir subheadings cada ~300-400 palabras.',
                    'severity': 'medium',
                })

        return {'score': max(0, score), 'issues': issues, 'prose_ratio': round(prose_ratio, 2)}

    # ========================================================================
    # DIMENSIÓN 4: SEO (15%)
    # ========================================================================

    def _score_seo(self, html: str, text: str, keyword: str, secondary_keywords: List[str]) -> Dict[str, Any]:
        """Evalúa keyword density, placements y enlaces."""
        score = 100
        issues = []

        if not keyword:
            return {'score': 50, 'issues': [{'description': 'No se proporcionó keyword para análisis SEO.', 'severity': 'low'}]}

        text_lower = text.lower()
        kw_lower = keyword.lower()
        words = text.split()
        word_count = len(words)

        # Keyword density
        kw_count = text_lower.count(kw_lower)
        density = (kw_count / max(1, word_count)) * 100

        if density < 0.5:
            score -= 25
            issues.append({
                'description': f'Keyword density muy baja ({density:.1f}%). Objetivo: 1-2%. Añadir keyword de forma natural.',
                'severity': 'high',
            })
        elif density > 2.5:
            score -= 20
            issues.append({
                'description': f'Keyword density alta ({density:.1f}%). Riesgo de stuffing. Reducir repeticiones.',
                'severity': 'high',
            })
        elif density < 1.0:
            score -= 10
            issues.append({
                'description': f'Keyword density algo baja ({density:.1f}%). Ideal: 1-2%.',
                'severity': 'low',
            })

        # Keyword en H2
        h2_texts = re.findall(r'<h2[^>]*>(.*?)</h2>', html, re.IGNORECASE | re.DOTALL)
        h2_with_kw = sum(1 for h in h2_texts if kw_lower in re.sub(r'<[^>]+>', '', h).lower())
        if h2_with_kw == 0:
            score -= 15
            issues.append({
                'description': 'Keyword no aparece en ningún H2. Incluir en el título principal.',
                'severity': 'high',
            })

        # Keyword en primeras 100 palabras
        first_100 = ' '.join(words[:100]).lower()
        if kw_lower not in first_100:
            score -= 10
            issues.append({
                'description': 'Keyword no aparece en las primeras 100 palabras.',
                'severity': 'medium',
            })

        # Enlaces internos (pccomponentes.com)
        internal_links = re.findall(r'href=["\'][^"\']*pccomponentes\.com[^"\']*["\']', html, re.IGNORECASE)
        if len(internal_links) < 2:
            score -= 10
            issues.append({
                'description': f'Solo {len(internal_links)} enlaces internos. Objetivo: 3-5.',
                'severity': 'medium',
            })

        return {'score': max(0, score), 'issues': issues, 'density': round(density, 2)}

    # ========================================================================
    # DIMENSIÓN 5: LEGIBILIDAD (10%)
    # ========================================================================

    def _score_legibilidad(self, text: str) -> Dict[str, Any]:
        """Evalúa legibilidad: Flesch, longitud de frases, párrafos."""
        score = 100
        issues = []

        # Flesch-Fernández Huerta
        flesch = _flesch_fernandez_huerta(text)

        if flesch < 40:
            score -= 30
            issues.append({
                'description': f'Legibilidad muy baja (Flesch: {flesch:.0f}). Simplificar frases y vocabulario.',
                'severity': 'high',
            })
        elif flesch < 55:
            score -= 15
            issues.append({
                'description': f'Legibilidad mejorable (Flesch: {flesch:.0f}). Acortar frases complejas.',
                'severity': 'medium',
            })

        # Longitud media de frases
        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 5]

        if sentences:
            avg_sentence_len = sum(len(s.split()) for s in sentences) / len(sentences)
            if avg_sentence_len > 25:
                score -= 20
                issues.append({
                    'description': f'Frases muy largas (media: {avg_sentence_len:.0f} palabras). Objetivo: <20.',
                    'severity': 'medium',
                })
            elif avg_sentence_len > 20:
                score -= 10
                issues.append({
                    'description': f'Frases algo largas (media: {avg_sentence_len:.0f} palabras).',
                    'severity': 'low',
                })

            # Variedad rítmica (penalizar monotonía)
            lengths = [len(s.split()) for s in sentences]
            if len(lengths) > 5:
                # Calcular desviación estándar
                mean_len = sum(lengths) / len(lengths)
                variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
                std_dev = math.sqrt(variance)

                if std_dev < 3:
                    score -= 10
                    issues.append({
                        'description': 'Frases con longitud muy uniforme. Variar entre frases cortas (5-10) y largas (15-25).',
                        'severity': 'low',
                    })

        return {'score': max(0, score), 'issues': issues, 'flesch': round(flesch, 1)}


# ============================================================================
# FUNCIÓN DE CONVENIENCIA
# ============================================================================

def score_content(
    html_content: str,
    keyword: str = "",
    secondary_keywords: Optional[List[str]] = None,
    target_length: int = 1500,
) -> Dict[str, Any]:
    """
    Función de conveniencia para evaluar calidad de contenido.

    Returns:
        Dict con composite_score, passed, dimensions, priority_fixes
    """
    scorer = QualityScorer()
    return scorer.score(html_content, keyword, secondary_keywords, target_length)
