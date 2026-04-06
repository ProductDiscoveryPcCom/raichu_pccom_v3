# -*- coding: utf-8 -*-
"""
Brief Parser - PcComponentes Content Generator

Parses markdown briefs from the cannibalization tool into a dictionary
that can be used to populate the rewrite form.
"""

import re
from typing import Dict, List, Any, Optional

def parse_cannibalization_brief(content: str) -> Dict[str, Any]:
    """
    Parses a markdown brief and extracts key fields.
    
    Fields extracted:
    - keyword (inferred from URL or keywords table)
    - url
    - action
    - summary
    - headings (list)
    - keywords (list of dicts)
    - internal_links (list of dicts)
    - instructions (add, remove, maintain)
    """
    
    data = {
        "url": "",
        "action": "",
        "summary": "",
        "headings": [],
        "keywords": [],
        "internal_links": [],
        "instructions": {
            "add": [],
            "remove": [],
            "maintain": []
        },
        "arquetipo": "ARQ-6", # Default to Guía de Compra if not specified
        "target_length": 1500
    }
    
    # 1. Extract Metadata Table
    meta_table_match = re.search(r'\| Campo \| Valor \|\n\|-+\|-+\|\n(.*?)(?=\n\n|##)', content, re.DOTALL)
    if meta_table_match:
        rows = meta_table_match.group(1).strip().split('\n')
        for row in rows:
            parts = [p.strip().replace('**', '') for p in row.split('|') if p.strip()]
            if len(parts) >= 2:
                key, val = parts[0], parts[1]
                if "URL" in key:
                    data["url"] = val
                elif "Acción" in key:
                    data["action"] = val
    
    # 2. Extract Executive Summary
    summary_match = re.search(r'## Resumen ejecutivo\n+(.*?)(?=\n+---|\n+##)', content, re.DOTALL)
    if summary_match:
        data["summary"] = summary_match.group(1).strip()
        
    # 3. Extract Headings Proposed
    headings_match = re.search(r'## Headings propuestos\n+.*?\n\| # \| H2 propuesto \| Justificación \|\n\|-+\|-+\|-+\|\n(.*?)(?=\n\n|##|---)', content, re.DOTALL)
    if headings_match:
        rows = headings_match.group(1).strip().split('\n')
        for row in rows:
            parts = [p.strip().replace('`', '') for p in row.split('|') if p.strip()]
            if len(parts) >= 2:
                # Part 0 is #, Part 1 is Heading, Part 2 is Justification
                h_text = parts[1]
                data["headings"].append(h_text)
                data["instructions"]["add"].append(f"Incluir sección con H2: {h_text} ({parts[2] if len(parts) > 2 else ''})")

    # 4. Extract Keywords Table
    keywords_match = re.search(r'## Keywords SEMrush\n+.*?\n\| Keyword \| Volumen \| Posición \| Intent \| Prioridad \|\n\|-+\|-+\|-+\|-+\|-+\|\n(.*?)(?=\n\n|##|---)', content, re.DOTALL)
    if keywords_match:
        rows = keywords_match.group(1).strip().split('\n')
        for row in rows:
            parts = [p.strip() for p in row.split('|') if p.strip()]
            if len(parts) >= 5:
                kw = parts[0]
                vol = parts[1]
                pos = parts[2]
                intent = parts[3]
                priority = parts[4]
                
                # Only add as secondary keyword if not marked for redirect or if it's a blog opportunity
                if "Redirigir" not in priority:
                    data["keywords"].append(kw)
                
                # If first time we see a high priority one, use as main keyword if we don't have one
                if not data.get("keyword") and "Oportunidad blog" in priority:
                    data["keyword"] = kw

    # 5. Extract Anchor Texts
    anchor_match = re.search(r'## Anchor texts recomendados\n+.*?Desde el blog → PLP.*?\n\| Anchor text \| Contexto de uso \|\n\|-+\|-+\|\n(.*?)(?=\n\n|##|---)', content, re.DOTALL)
    if anchor_match:
        rows = anchor_match.group(1).strip().split('\n')
        for row in rows:
            parts = [p.strip().replace('`', '') for p in row.split('|') if p.strip()]
            if len(parts) >= 2:
                data["internal_links"].append({
                    "anchor": parts[0],
                    "context": parts[1]
                })

    # 6. Extract "Contenido a mover/keep"
    move_match = re.search(r'## Contenido a mover\n+(.*?)(?=\n+---|\n+##)', content, re.DOTALL)
    if move_match:
        move_section = move_match.group(1)
        
        # Extract items to remove / move to PLP
        remove_items = re.findall(r'- \*\*([^*]+)\*\*(?:: )?(.*?)(?=\n-|\n\n|\Z)', move_section, re.DOTALL)
        for title, desc in remove_items:
            if "trasladarse" in move_section.lower() or "eliminarse" in move_section.lower():
                data["instructions"]["remove"].append(f"{title.strip()}: {desc.strip()}")

        # Extract items to keep and expand
        keep_match = re.search(r'El blog debe \*\*conservar y ampliar\*\*:\n(.*?)(?=\n---|\n##|\Z)', move_section, re.DOTALL)
        if keep_match:
            keep_items = re.findall(r'- (.*?)(?=\n-|\n\n|\Z)', keep_match.group(1), re.DOTALL)
            for item in keep_items:
                data["instructions"]["maintain"].append(item.strip())

    # Infer keyword from URL if still missing
    if not data.get("keyword") and data["url"]:
        # Extract last part of slug and replace hyphens with spaces
        slug = data["url"].split('/')[-1]
        data["keyword"] = slug.replace('-', ' ').title()

    return data
