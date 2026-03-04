# -*- coding: utf-8 -*-
"""
Content Translation - PcComponentes Content Generator
Versión 1.0.0 - 2026-02-12

Traducción contextualizada de contenido final a múltiples idiomas.
NO traducción literal: adaptación cultural al país de destino.

Idiomas soportados:
- en: Inglés (UK/Internacional)
- fr: Francés (Francia)
- pt: Portugués (Portugal)
- de: Alemán (Alemania)
- it: Italiano (Italia)

Autor: PcComponentes - Product Discovery & Content
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

__version__ = "1.0.0"


# ============================================================================
# CONFIGURACIÓN DE IDIOMAS
# ============================================================================

@dataclass
class LanguageConfig:
    """Configuración de un idioma de traducción."""
    code: str
    name: str
    flag: str
    country: str
    currency: str
    currency_symbol: str
    locale_notes: str
    tone_notes: str


LANGUAGES: Dict[str, LanguageConfig] = {
    'en': LanguageConfig(
        code='en',
        name='English',
        flag='🇬🇧',
        country='United Kingdom / International',
        currency='GBP / EUR',
        currency_symbol='£ / €',
        locale_notes=(
            'Use British English spelling (colour, favourite, organised). '
            'Prices in GBP or EUR depending on target market. '
            'Measurements in metric but include imperial where common in UK context. '
            'Adapt brand references: PcComponentes operates as an international tech retailer.'
        ),
        tone_notes=(
            'Straightforward, informative tone. Slightly more reserved than Spanish. '
            'Avoid overly enthusiastic language. British consumers appreciate '
            'understatement, factual comparisons, and honest assessments. '
            'Use "you" freely but avoid being patronising.'
        ),
    ),
    'fr': LanguageConfig(
        code='fr',
        name='Français',
        flag='🇫🇷',
        country='France',
        currency='EUR',
        currency_symbol='€',
        locale_notes=(
            'French from France (not Belgian or Canadian). '
            'Prices in EUR with French format (1 299,99 €). '
            'Use "vous" (formal) by default unless the brand tone is casual. '
            'Adapt product names that have French equivalents (e.g. "ordinateur portable" not "laptop"). '
            'French consumers are detail-oriented: include specifications.'
        ),
        tone_notes=(
            'Elegant but accessible. French tech content tends to be more analytical. '
            'Avoid excessive anglicisms unless they are standard in French tech vocabulary '
            '(e.g. "gaming", "streaming" are acceptable, but prefer "disque dur" over "hard drive"). '
            'Use proper French punctuation: thin non-breaking spaces before ; : ! ?'
        ),
    ),
    'pt': LanguageConfig(
        code='pt',
        name='Português',
        flag='🇵🇹',
        country='Portugal',
        currency='EUR',
        currency_symbol='€',
        locale_notes=(
            'European Portuguese from Portugal (NOT Brazilian Portuguese). '
            'Use Portuguese orthography and vocabulary, not Brazilian. '
            'Key differences: "telemóvel" (not "celular"), "ecrã" (not "tela"), '
            '"computador portátil" (not "notebook"), "rato" (not "mouse"). '
            'Prices in EUR. Use tu/você appropriately for PT-PT register.'
        ),
        tone_notes=(
            'Direct and practical. Portuguese consumers appreciate straightforward '
            'recommendations without excessive marketing language. '
            'Slightly more formal than Brazilian Portuguese content. '
            'Technical precision is valued. Avoid Brazilian colloquialisms.'
        ),
    ),
    'de': LanguageConfig(
        code='de',
        name='Deutsch',
        flag='🇩🇪',
        country='Deutschland',
        currency='EUR',
        currency_symbol='€',
        locale_notes=(
            'Standard German (Hochdeutsch) for Germany. '
            'Prices in EUR with German format (1.299,99 €). '
            'Use "Sie" (formal) by default. '
            'German consumers demand thorough technical specifications. '
            'Include exact measurements, certifications, and technical standards. '
            'Compound nouns are natural in German: use them.'
        ),
        tone_notes=(
            'Precise, thorough, and factual. German tech content is highly detail-oriented. '
            'Avoid superlatives and marketing hyperbole — German consumers distrust them. '
            'Focus on Qualität, Zuverlässigkeit (reliability), Preis-Leistung (value for money). '
            'Structure matters: use clear hierarchies and systematic comparisons.'
        ),
    ),
    'it': LanguageConfig(
        code='it',
        name='Italiano',
        flag='🇮🇹',
        country='Italia',
        currency='EUR',
        currency_symbol='€',
        locale_notes=(
            'Standard Italian for Italy. '
            'Prices in EUR with Italian format (1.299,99 €). '
            'Italian tech vocabulary uses many English loanwords (smartphone, laptop, gaming). '
            'Use "tu" for informal or "Lei" for formal depending on brand tone. '
            'Design and aesthetics matter to Italian consumers: highlight design aspects.'
        ),
        tone_notes=(
            'Warm, engaging, and slightly more expressive than German or English. '
            'Italian consumers appreciate a balance of technical detail and lifestyle context. '
            'Highlight design, build quality, and user experience. '
            'Avoid being overly dry or purely technical — weave in practical usage scenarios.'
        ),
    ),
}


def get_supported_languages() -> Dict[str, LanguageConfig]:
    """Devuelve los idiomas soportados."""
    return LANGUAGES


def get_language(code: str) -> Optional[LanguageConfig]:
    """Devuelve la configuración de un idioma."""
    return LANGUAGES.get(code)


# ============================================================================
# PROMPT DE TRADUCCIÓN
# ============================================================================

def build_translation_prompt(
    html_content: str,
    target_lang: str,
    keyword: str = "",
    source_lang: str = "es",
) -> Tuple[str, str]:
    """
    Construye el prompt de traducción contextualizada.

    Args:
        html_content: HTML del contenido final a traducir
        target_lang: Código del idioma destino ('en', 'fr', 'pt', 'de', 'it')
        keyword: Keyword principal (para adaptar SEO)
        source_lang: Idioma de origen (default 'es')

    Returns:
        Tuple de (system_prompt, user_prompt)
    """
    lang = LANGUAGES.get(target_lang)
    if not lang:
        raise ValueError(f"Idioma no soportado: {target_lang}. Disponibles: {list(LANGUAGES.keys())}")

    system_prompt = f"""Eres un traductor profesional especializado en contenido tecnológico y SEO.
Tu tarea es traducir contenido de PcComponentes del español al {lang.name}.

REGLAS CRÍTICAS:
1. NO hagas traducción literal. Adapta el contenido al mercado de {lang.country}.
2. Mantén EXACTAMENTE la misma estructura HTML (tags, clases CSS, IDs, atributos).
3. Traduce solo el texto visible para el usuario, NO toques el código HTML/CSS.
4. Adapta las expresiones idiomáticas al equivalente natural en {lang.name}.
5. Si hay referencias a precios en €, mantén el formato de {lang.country}: {lang.currency_symbol}.
6. Si hay marcas de producto (ASUS, Samsung, etc.), NO las traduzcas.
7. Los nombres de modelos de producto NO se traducen.
8. Las unidades técnicas (GB, TB, MHz, etc.) NO se traducen.

LOCALIZACIÓN — {lang.flag} {lang.country}:
{lang.locale_notes}

TONO Y ESTILO:
{lang.tone_notes}

INSTRUCCIONES HTML:
- El contenido viene envuelto en tags HTML con clases CSS de PcComponentes.
- Traduce SOLO el contenido textual dentro de los tags.
- NO modifiques: <style>, atributos class=, id=, href=, src=.
- SÍ traduce: texto en <p>, <h2>, <h3>, <span>, <li>, <td>, <th>, alt= de imágenes.
- Las anclas de navegación (#seccion1, etc.) NO se traducen.
- Los kickers (<span class="kicker">) SÍ se traducen y adaptan.
- Las FAQs se adaptan a preguntas que haría un usuario de {lang.country}."""

    # Keyword adaptada
    kw_note = ""
    if keyword:
        kw_note = f"""

KEYWORD SEO:
- Keyword original (ES): "{keyword}"
- Adapta la keyword al {lang.name} de forma natural para SEO.
- Usa la keyword adaptada en: título H2, primer párrafo, FAQs, meta-content.
- NO fuerces la keyword si no suena natural en {lang.name}."""

    user_prompt = f"""Traduce el siguiente contenido HTML del español al {lang.name} ({lang.country}).

Recuerda: traducción CONTEXTUALIZADA, no literal. Adapta expresiones, ejemplos y tono al mercado de {lang.country}.
{kw_note}

CONTENIDO A TRADUCIR:
```html
{html_content}
```

Devuelve SOLO el HTML traducido, sin explicaciones ni comentarios. Empieza directamente con <style> o con el primer tag HTML."""

    return system_prompt, user_prompt


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    '__version__',
    'LanguageConfig',
    'LANGUAGES',
    'get_supported_languages',
    'get_language',
    'build_translation_prompt',
]
