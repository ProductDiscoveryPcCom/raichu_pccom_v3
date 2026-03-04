# -*- coding: utf-8 -*-
"""
Content Scrubber - PcComponentes Content Generator
Versión 1.0.0

Limpia watermarks Unicode invisibles y patrones de IA del HTML generado.
Inspirado en SEO Machine (content_scrubber.py), adaptado para HTML en español.

Elimina:
- Zero-width spaces, BOMs, format-control chars
- Em-dashes (reemplaza por puntuación contextual en español)
- Espacios dobles y saltos de línea excesivos

Es idempotente: ejecutarlo múltiples veces no altera contenido ya limpio.

Autor: PcComponentes - Product Discovery & Content
"""

import re
import unicodedata
from typing import Tuple, Dict

__version__ = "1.0.0"


class ContentScrubber:
    """Limpia contenido HTML de watermarks Unicode y patrones de IA."""

    # Caracteres Unicode invisibles usados como watermarks por LLMs
    WATERMARK_CHARS = [
        '\u200B',  # Zero-width space
        '\uFEFF',  # Byte Order Mark (BOM)
        '\u200C',  # Zero-width non-joiner
        '\u200D',  # Zero-width joiner
        '\u2060',  # Word joiner
        '\u00AD',  # Soft hyphen
        '\u202F',  # Narrow no-break space
        '\u180E',  # Mongolian vowel separator
        '\u200E',  # Left-to-right mark
        '\u200F',  # Right-to-left mark
    ]

    # Adverbios y conectores españoles que preceden un em-dash → punto y coma
    _CONJUNCTIVE_PATTERN = (
        r'sin embargo|no obstante|además|por tanto|por ello|'
        r'en cambio|de hecho|por ejemplo|en realidad|'
        r'es decir|o sea|ahora bien|eso sí|con todo'
    )

    def scrub(self, content: str) -> Tuple[str, Dict[str, int]]:
        """
        Limpia contenido de watermarks Unicode y patrones de IA.

        Args:
            content: HTML o texto a limpiar

        Returns:
            Tuple de (contenido_limpio, estadísticas)
        """
        if not content:
            return content, {'unicode_removed': 0, 'emdashes_replaced': 0, 'format_control_removed': 0}

        stats = {
            'unicode_removed': 0,
            'emdashes_replaced': 0,
            'format_control_removed': 0,
        }

        # Paso 1: Eliminar watermark chars específicos
        content = self._remove_watermark_chars(content, stats)

        # Paso 2: Eliminar todos los chars Unicode de categoría Cf (format-control)
        content = self._remove_format_control_chars(content, stats)

        # Paso 3: Reemplazar em-dashes por puntuación contextual española
        content = self._replace_emdashes(content, stats)

        # Paso 4: Limpiar espacios y saltos de línea
        content = self._clean_whitespace(content)

        return content, stats

    def _remove_watermark_chars(self, content: str, stats: Dict) -> str:
        """Elimina caracteres Unicode invisibles específicos."""
        for char in self.WATERMARK_CHARS:
            count = content.count(char)
            if count > 0:
                stats['unicode_removed'] += count
                if char == '\u200B':
                    # Zero-width space entre palabras → espacio normal
                    content = re.sub(r'(\w)\u200B(\w)', r'\1 \2', content)
                content = content.replace(char, '')
        return content

    def _remove_format_control_chars(self, content: str, stats: Dict) -> str:
        """Elimina todos los caracteres Unicode de categoría Cf no capturados antes."""
        cleaned = []
        for c in content:
            if unicodedata.category(c) == 'Cf':
                stats['format_control_removed'] += 1
            else:
                cleaned.append(c)
        return ''.join(cleaned)

    def _replace_emdashes(self, content: str, stats: Dict) -> str:
        """
        Reemplaza em-dashes (—) por puntuación contextual en español.

        Reglas:
        1. Antes de adverbios conjuntivos → punto y coma
        2. Entre frases (mayúscula después) → punto
        3. Resto → coma
        """
        # No tocar em-dashes dentro de tags HTML o atributos
        # Procesamos solo el texto fuera de tags
        parts = re.split(r'(<[^>]+>)', content)
        result = []

        for part in parts:
            if part.startswith('<'):
                # Es un tag HTML, no tocar
                result.append(part)
                continue

            # Antes de conectores/adverbios → punto y coma
            part, n = re.subn(
                rf'\s+—\s+({self._CONJUNCTIVE_PATTERN})',
                r'; \1', part, flags=re.IGNORECASE
            )
            stats['emdashes_replaced'] += n

            # Entre frases (mayúscula después) → punto
            part, n = re.subn(r'\s+—\s+([A-ZÁÉÍÓÚÑ])', r'. \1', part)
            stats['emdashes_replaced'] += n

            # Resto de em-dashes con espacios alrededor → coma
            part, n = re.subn(r'\s+—\s+', ', ', part)
            stats['emdashes_replaced'] += n

            result.append(part)

        return ''.join(result)

    def _clean_whitespace(self, content: str) -> str:
        """Normaliza espacios y saltos de línea."""
        # Espacios dobles → simple (pero no dentro de tags)
        content = re.sub(r'(?<=>)\s{2,}(?=<)', ' ', content)
        # Espacios múltiples en texto
        content = re.sub(r'([^<\s])  +([^>])', r'\1 \2', content)
        # Espacio antes de puntuación
        content = re.sub(r'\s+([.,;:!?])', r'\1', content)
        # Saltos de línea excesivos
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content


def scrub_html(content: str) -> Tuple[str, Dict[str, int]]:
    """
    Función de conveniencia para limpiar HTML.

    Args:
        content: HTML a limpiar

    Returns:
        Tuple de (html_limpio, estadísticas)
    """
    scrubber = ContentScrubber()
    return scrubber.scrub(content)
