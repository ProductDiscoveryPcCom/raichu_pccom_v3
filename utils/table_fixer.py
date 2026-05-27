# -*- coding: utf-8 -*-
"""
Table Fixer - PcComponentes Content Generator
Versión 1.0.0

Corrige problemas estructurales en tablas HTML generadas por Claude:
1. Añade <thead>/<tbody> si faltan
2. Envuelve tablas anchas (≥4 cols) en div.table-responsive para mobile
3. Valida consistencia de columnas

Se ejecuta como paso del pipeline post-generación, después del scrubber
y antes del quality scorer.

Autor: PcComponentes - Product Discovery & Content
"""

import re
import logging
from typing import List, Tuple, Dict

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

# Umbral de columnas para envolver en wrapper responsive
RESPONSIVE_THRESHOLD = 4

# Marcador de idempotencia del refuerzo CSS de tablas comparativas.
PCC_TABLE_FIX_MARKER = "/* PCC-TABLE-FIX */"

# Bloque override (con !important) que gana la cascada frente a lo que el modelo
# haya reescrito y frente al CSS del CMS de producción
# (.chunkPostView-* table{display:block} y th{background:#ebebeb}).
# Valores LITERALES (hex/px, sin var(...)) para ser autosuficiente.
_COMPARISON_TABLE_OVERRIDE = (
    PCC_TABLE_FIX_MARKER
    + ".comparison-table{display:table !important;table-layout:fixed;width:100%;"
    "border-collapse:collapse;font-size:14px;}"
    ".comparison-table thead{display:table-header-group !important;}"
    ".comparison-table tbody{display:table-row-group !important;}"
    ".comparison-table th,.comparison-table td{padding:10px 14px;text-align:left;"
    "vertical-align:top;word-wrap:break-word;overflow-wrap:break-word;}"
    ".comparison-table th{background:#170453 !important;color:#fff !important;"
    "font-weight:700;font-size:15px;border:none !important;}"
    ".comparison-table td{border-bottom:1px solid #E6E6E6;}"
    ".comparison-table tbody tr:nth-child(even) td{background:#F4F4F4;}"
)


def fix_tables(html: str) -> Tuple[str, Dict]:
    """
    Corrige tablas en el HTML generado.
    
    Args:
        html: HTML con tablas potencialmente mal estructuradas
        
    Returns:
        (html_corregido, stats) donde stats tiene:
            - tables_found: int
            - thead_added: int
            - responsive_wrapped: int
    """
    if not html or '<table' not in html.lower():
        return html, {'tables_found': 0, 'thead_added': 0, 'responsive_wrapped': 0}
    
    stats = {'tables_found': 0, 'thead_added': 0, 'responsive_wrapped': 0}
    
    def process_table(match):
        tag_open = match.group(1)
        inner = match.group(2)
        stats['tables_found'] += 1
        
        inner_lower = inner.lower()
        has_thead = '<thead>' in inner_lower
        
        if not has_thead:
            # Buscar filas
            rows = re.findall(r'(<tr[^>]*>.*?</tr>)', inner, re.DOTALL | re.IGNORECASE)
            if rows and re.search(r'<th[\s>]', rows[0], re.IGNORECASE):
                # Primera fila tiene <th> → convertir en <thead>
                thead = f'<thead>{rows[0]}</thead>'
                remaining = ''.join(rows[1:])
                
                has_tbody = '<tbody>' in inner_lower
                if not has_tbody and remaining:
                    remaining = f'<tbody>{remaining}</tbody>'
                
                inner = thead + remaining
                stats['thead_added'] += 1
                logger.info(f"Table fix: añadido <thead> a tabla {stats['tables_found']}")
        
        table_html = f'{tag_open}{inner}</table>'
        
        # Contar columnas de la primera fila
        first_row = re.search(r'<tr[^>]*>(.*?)</tr>', inner, re.DOTALL | re.IGNORECASE)
        if first_row:
            col_count = len(re.findall(r'<t[hd][\s>]', first_row.group(1), re.IGNORECASE))
            if col_count >= RESPONSIVE_THRESHOLD:
                # Solo envolver si no está ya en un wrapper
                stats['responsive_wrapped'] += 1
                return f'<div class="table-responsive">{table_html}</div>'
        
        return table_html
    
    # Verificar que no estamos re-wrapping tablas ya envueltas
    # Primero quitar wrappers existentes para evitar doble-wrap
    html = re.sub(
        r'<div class="table-responsive">\s*(<table)',
        r'\1',
        html,
        flags=re.IGNORECASE
    )
    html = re.sub(
        r'(</table>)\s*</div>(?=\s*(?:<[^t]|$))',  # Cerrar wrapper solo si siguiente no es <table
        r'\1',
        html,
        flags=re.IGNORECASE
    )
    
    result = re.sub(
        r'(<table[^>]*>)(.*?)</table>',
        process_table,
        html,
        flags=re.DOTALL | re.IGNORECASE
    )
    
    return result, stats


def validate_tables(html: str) -> List[str]:
    """
    Valida todas las tablas y devuelve issues.
    
    Returns:
        Lista de strings describiendo problemas encontrados
    """
    issues = []
    tables = re.findall(r'<table[^>]*>(.*?)</table>', html, re.DOTALL | re.IGNORECASE)
    
    for i, content in enumerate(tables, 1):
        content_lower = content.lower()
        
        if '<thead>' not in content_lower:
            issues.append(f"Tabla {i}: falta <thead>")
        
        if '<tbody>' not in content_lower:
            issues.append(f"Tabla {i}: falta <tbody>")
        
        # <th> en tbody
        tbody_match = re.search(r'<tbody>(.*?)</tbody>', content, re.DOTALL | re.IGNORECASE)
        if tbody_match and '<th' in tbody_match.group(1).lower():
            issues.append(f"Tabla {i}: <th> dentro de <tbody>")
        
        # Columnas inconsistentes
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', content, re.DOTALL | re.IGNORECASE)
        col_counts = [len(re.findall(r'<t[hd][\s>]', row, re.IGNORECASE)) for row in rows]
        if len(set(col_counts)) > 1:
            issues.append(f"Tabla {i}: columnas inconsistentes {col_counts}")

    return issues


def enforce_comparison_table_css(html: str) -> Tuple[str, Dict]:
    """Inyecta un override CSS determinista para .comparison-table.

    Estrategia OVERRIDE POR CASCADA: el bloque (_COMPARISON_TABLE_OVERRIDE, con
    !important) se inserta al FINAL del <style> del artículo. Al ir último y ser
    !important, gana sobre lo que el modelo haya reescrito y sobre el CSS del CMS
    de producción, sin parsear ni reemplazar reglas existentes.

    Args:
        html: HTML final del artículo (con o sin <style>).

    Returns:
        (html, stats) donde stats tiene:
            - comparison_tables_found: int  (nº de class="comparison-table")
            - css_injected: bool            (se añadió el override)
            - style_created: bool           (se creó un <style> nuevo)
            - already_present: bool         (marcador ya existía → no-op)
    """
    stats = {
        'comparison_tables_found': 0,
        'css_injected': False,
        'style_created': False,
        'already_present': False,
    }

    if not html:
        return html, stats

    # Guard: solo actuar si hay tablas comparativas (evita CSS muerto).
    stats['comparison_tables_found'] = len(
        re.findall(r'class\s*=\s*["\'][^"\']*\bcomparison-table\b', html, re.IGNORECASE)
    )
    if stats['comparison_tables_found'] == 0:
        return html, stats

    # Idempotencia: si el marcador ya está, no apilar (refinamientos/reruns).
    if PCC_TABLE_FIX_MARKER in html:
        stats['already_present'] = True
        return html, stats

    # Insertar antes del ÚLTIMO </style> (mayor prioridad de cascada local).
    style_closes = list(re.finditer(r'</style\s*>', html, re.IGNORECASE))
    if style_closes:
        last = style_closes[-1]
        result = html[:last.start()] + _COMPARISON_TABLE_OVERRIDE + html[last.start():]
        stats['css_injected'] = True
        logger.info("Comparison-table CSS override inyectado en <style> existente")
        return result, stats

    # No hay <style>: crear uno. Debe ir DESPUÉS del comentario líder <!-- META: ... -->
    # si existe (su extracción exige que vaya primero); si no, al inicio.
    new_style = f'<style>{_COMPARISON_TABLE_OVERRIDE}</style>'
    meta = re.search(r'<!--\s*META:.*?-->', html, re.DOTALL | re.IGNORECASE)
    if meta:
        result = html[:meta.end()] + new_style + html[meta.end():]
    else:
        result = new_style + html
    stats['css_injected'] = True
    stats['style_created'] = True
    logger.info("Comparison-table CSS override inyectado en <style> nuevo")
    return result, stats
