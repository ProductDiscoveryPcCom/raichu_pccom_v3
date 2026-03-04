# -*- coding: utf-8 -*-
"""
CSS Integrity Checker - PcComponentes Content Generator
Versión 1.0.0

Detecta desincronización entre las 3 fuentes de CSS:
1. config/design_system.py (fuente principal, tree-shaking)
2. config/cms_compatible.css (CSS base)
3. prompts/new_content.py _CSS_FALLBACK (inline fallback)

Ejecutar como test o al inicio de la app para detectar drift.

USO:
    from utils.css_integrity import check_css_integrity
    issues = check_css_integrity()
    if issues:
        for issue in issues:
            print(f"⚠️ {issue}")

Autor: PcComponentes - Product Discovery & Content
"""

import re
import logging
from pathlib import Path
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

# Variables CSS críticas que DEBEN coincidir entre fuentes
CRITICAL_VARS = [
    '--orange-900',
    '--blue-m-900',
    '--gray-100',
    '--gray-200',
    '--gray-700',
    '--gray-900',
    '--space-md',
    '--space-lg',
    '--radius-md',
]

# Selectores que DEBEN existir en todas las fuentes
CRITICAL_SELECTORS = [
    '.contentGenerator__main',
    '.contentGenerator__faqs',
    '.contentGenerator__verdict',
    '.kicker',
    '.toc',
    '.faqs__item',
    '.verdict-box',
    '.callout',
]


def check_css_integrity(verbose: bool = False) -> List[str]:
    """
    Verifica consistencia entre fuentes CSS.
    
    Returns:
        Lista de issues encontrados (vacía si todo OK)
    """
    issues = []
    
    # Cargar fuentes
    fallback_css = _load_fallback_css()
    design_system_css = _load_design_system_css()
    file_css = _load_file_css()
    
    sources = {}
    if fallback_css:
        sources['fallback (new_content.py)'] = fallback_css
    if design_system_css:
        sources['design_system.py'] = design_system_css
    if file_css:
        sources['cms_compatible.css'] = file_css
    
    if len(sources) < 2:
        if verbose:
            logger.info(f"CSS integrity: solo {len(sources)} fuente(s) disponibles, no se puede comparar")
        return issues
    
    # Check 1: Variables CSS críticas
    for var in CRITICAL_VARS:
        values = {}
        for name, css in sources.items():
            match = re.search(re.escape(var) + r'\s*:\s*([^;}\s]+)', css)
            if match:
                values[name] = match.group(1).strip()
        
        unique_values = set(values.values())
        if len(unique_values) > 1:
            issues.append(
                f"Variable {var} tiene valores diferentes: "
                + ", ".join(f"{k}={v}" for k, v in values.items())
            )
    
    # Check 2: Selectores críticos presentes en todas las fuentes
    for selector in CRITICAL_SELECTORS:
        for name, css in sources.items():
            if selector not in css:
                issues.append(f"Selector '{selector}' no encontrado en {name}")
    
    # Check 3: Font-family consistency
    fonts = {}
    for name, css in sources.items():
        font_match = re.search(r"font-family\s*:\s*'([^']+)'", css)
        if font_match:
            fonts[name] = font_match.group(1)
    
    unique_fonts = set(fonts.values())
    if len(unique_fonts) > 1:
        issues.append(
            f"Font-family inconsistente: "
            + ", ".join(f"{k}='{v}'" for k, v in fonts.items())
        )
    
    if verbose:
        if issues:
            logger.warning(f"CSS integrity: {len(issues)} issues encontrados")
        else:
            logger.info(f"CSS integrity: OK ({len(sources)} fuentes verificadas)")
    
    return issues


def _load_fallback_css() -> Optional[str]:
    """Carga el CSS fallback de new_content.py."""
    try:
        from prompts.new_content import _CSS_FALLBACK
        return _CSS_FALLBACK
    except ImportError:
        return None


def _load_design_system_css() -> Optional[str]:
    """Carga CSS generado por design_system.py."""
    try:
        from config.design_system import get_css_for_prompt
        return get_css_for_prompt(selected_components=[], minify=False)
    except ImportError:
        return None


def _load_file_css() -> Optional[str]:
    """Carga CSS desde cms_compatible.css."""
    css_path = Path(__file__).parent.parent / "config" / "cms_compatible.css"
    try:
        return css_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        return None
