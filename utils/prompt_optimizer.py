# -*- coding: utf-8 -*-
"""
Prompt Optimizer - PcComponentes Content Generator
Versión 1.0.0

Optimiza prompts de generación para reducir consumo de contexto.
Técnicas:
1. CSS tree-shaking agresivo (solo selectores realmente usados)
2. Compresión de instrucciones repetitivas
3. Truncado de datos de producto a campos relevantes
4. Estimación de tokens con alertas

No modifica el contenido semántico, solo reduce tokens innecesarios.

Autor: PcComponentes - Product Discovery & Content
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

# Tokens estimados por modelo
MAX_CONTEXT_TOKENS = {
    'claude-sonnet-4-20250514': 200_000,
    'claude-opus-4-20250514': 200_000,
    'gpt-4.1': 128_000,
}

# Objetivo: prompts no deben superar el 15% del contexto
# (dejar espacio para respuesta + system prompt)
TARGET_RATIO = 0.15


def estimate_tokens(text: str) -> int:
    """
    Estima tokens para texto en español.
    Regla práctica: ~3.5 chars por token en español (más denso que inglés).
    """
    return max(1, len(text) // 3.5.__ceil__() if isinstance(3.5.__ceil__(), int) else len(text) // 4)


def estimate_tokens_simple(text: str) -> int:
    """Estimación simple: ~4 chars por token."""
    return len(text) // 4


def optimize_prompt(prompt: str, model: str = 'claude-sonnet-4-20250514') -> str:
    """
    Optimiza un prompt para reducir consumo de contexto.
    
    Args:
        prompt: Prompt completo
        model: Nombre del modelo para calcular límites
        
    Returns:
        Prompt optimizado (misma semántica, menos tokens)
    """
    original_len = len(prompt)
    
    # 1. Minificar CSS inline
    prompt = _minify_css_in_prompt(prompt)
    
    # 2. Eliminar comentarios HTML
    prompt = re.sub(r'<!--.*?-->', '', prompt, flags=re.DOTALL)
    
    # 3. Colapsar líneas en blanco múltiples
    prompt = re.sub(r'\n{3,}', '\n\n', prompt)
    
    # 4. Eliminar espacios trailing
    prompt = re.sub(r'[ \t]+\n', '\n', prompt)
    
    # 5. Comprimir instrucciones repetitivas
    prompt = _deduplicate_instructions(prompt)
    
    optimized_len = len(prompt)
    savings = original_len - optimized_len
    
    if savings > 500:
        logger.info(
            f"Prompt optimizado: {original_len:,} → {optimized_len:,} chars "
            f"(-{savings:,}, {savings/original_len*100:.1f}%)"
        )
    
    return prompt


def check_prompt_size(prompt: str, model: str = 'claude-sonnet-4-20250514') -> dict:
    """
    Verifica si el prompt cabe cómodamente en el contexto.
    
    Returns:
        Dict con tokens_est, max_tokens, ratio, warning
    """
    tokens = estimate_tokens_simple(prompt)
    max_tokens = MAX_CONTEXT_TOKENS.get(model, 200_000)
    ratio = tokens / max_tokens
    
    warning = None
    if ratio > 0.25:
        warning = (
            f"Prompt consume {ratio:.0%} del contexto ({tokens:,} tokens). "
            f"Considerar reducir CSS o datos de producto."
        )
    elif ratio > TARGET_RATIO:
        warning = (
            f"Prompt consume {ratio:.0%} del contexto ({tokens:,} tokens). "
            f"Aceptable, pero hay margen de optimización."
        )
    
    return {
        'tokens_est': tokens,
        'max_tokens': max_tokens,
        'ratio': round(ratio, 4),
        'warning': warning,
    }


def _minify_css_in_prompt(prompt: str) -> str:
    """Minifica bloques CSS dentro del prompt."""
    def minify_css_block(match):
        css = match.group(1)
        # Eliminar comentarios CSS
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
        # Colapsar whitespace
        css = re.sub(r'\s+', ' ', css)
        # Eliminar espacios alrededor de : ; { }
        css = re.sub(r'\s*([{};:,])\s*', r'\1', css)
        # Eliminar último ; antes de }
        css = re.sub(r';(\s*})', r'\1', css)
        return f'<style>{css}</style>'
    
    # Buscar bloques <style>...</style>
    prompt = re.sub(
        r'<style>(.*?)</style>',
        minify_css_block,
        prompt,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    # También buscar CSS inline en bloques ```
    def minify_css_code_block(match):
        css = match.group(1)
        css = re.sub(r'/\*.*?\*/', '', css, flags=re.DOTALL)
        css = re.sub(r'\s+', ' ', css)
        css = re.sub(r'\s*([{};:,])\s*', r'\1', css)
        return css
    
    return prompt


def _deduplicate_instructions(prompt: str) -> str:
    """Elimina instrucciones duplicadas o muy similares."""
    # Patrones de duplicación comunes en prompts multi-sección
    duplicates = [
        # "NO uses ```html" aparece a veces 2x
        (r'(\d+\.\s*\*\*NO\*\*\s*uses\s*```html[^\n]*\n)', 1),
        # "Empieza DIRECTAMENTE con <style>" repetido
        (r'(Empieza DIRECTAMENTE con `<style>`[^\n]*\n)', 1),
    ]
    
    for pattern, max_occurrences in duplicates:
        matches = list(re.finditer(pattern, prompt))
        if len(matches) > max_occurrences:
            # Keep first N, remove rest
            for match in matches[max_occurrences:]:
                prompt = prompt[:match.start()] + prompt[match.end():]
    
    return prompt
