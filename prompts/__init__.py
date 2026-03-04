"""
Prompts Module - PcComponentes Content Generator
Versión 4.3.0

Módulo centralizado de prompts y templates para generación de contenido.

USO:
    from prompts import new_content, rewrite
    
    # Uso directo
    prompt = new_content.build_new_content_prompt_stage1(...)
    prompt = rewrite.build_rewrite_prompt_stage1(...)

Autor: PcComponentes - Product Discovery & Content
"""

import logging

logger = logging.getLogger(__name__)

__version__ = "4.3.0"

# ============================================================================
# IMPORTS DE SUBMÓDULOS (usando importaciones RELATIVAS)
# ============================================================================

# IMPORTANTE: Usar "from . import X" (relativo) NO "from prompts import X"
# porque estamos DENTRO del paquete prompts

try:
    from . import new_content
except ImportError as e:
    logger.warning(f"No se pudo importar prompts.new_content: {e}")
    new_content = None  # type: ignore

try:
    from . import rewrite
except ImportError as e:
    logger.warning(f"No se pudo importar prompts.rewrite: {e}")
    rewrite = None  # type: ignore

# ============================================================================
# IMPORTS OPCIONALES DE TEMPLATES (para compatibilidad)
# ============================================================================

try:
    from .templates import (
        SafeTemplate,
        TemplateError,
        MissingVariableError,
        InvalidTemplateError,
        build_system_prompt,
        build_content_prompt,
        build_rewrite_prompt,
        build_analysis_prompt,
        build_links_section,
        build_enhanced_links_section,
        build_competitor_section,
        build_faqs_section,
        build_callout,
        escape_for_json,
        format_list_for_prompt,
        format_dict_for_prompt,
    )
    _templates_available = True
except ImportError as e:
    logger.warning(f"No se pudo importar prompts.templates: {e}")
    _templates_available = False

# ============================================================================
# IMPORTS OPCIONALES DE CONTENT (para compatibilidad)
# ============================================================================

try:
    from .content import (
        build_guide_prompt,
        build_review_prompt,
        build_comparison_prompt,
        build_tutorial_prompt,
        build_ranking_prompt,
        get_content_prompt_by_type,
        CONTENT_TYPE_BUILDERS,
    )
    _content_available = True
except ImportError as e:
    logger.warning(f"No se pudo importar prompts.content: {e}")
    _content_available = False

# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Submódulos principales (los que usa app.py)
    'new_content',
    'rewrite',
]

# Añadir exports de templates si están disponibles
if _templates_available:
    __all__.extend([
        'SafeTemplate',
        'TemplateError',
        'MissingVariableError',
        'InvalidTemplateError',
        'build_system_prompt',
        'build_content_prompt',
        'build_rewrite_prompt',
        'build_analysis_prompt',
        'build_links_section',
        'build_enhanced_links_section',
        'build_competitor_section',
        'build_faqs_section',
        'build_callout',
        'escape_for_json',
        'format_list_for_prompt',
        'format_dict_for_prompt',
    ])

# Añadir exports de content si están disponibles
if _content_available:
    __all__.extend([
        'build_guide_prompt',
        'build_review_prompt',
        'build_comparison_prompt',
        'build_tutorial_prompt',
        'build_ranking_prompt',
        'get_content_prompt_by_type',
        'CONTENT_TYPE_BUILDERS',
    ])
