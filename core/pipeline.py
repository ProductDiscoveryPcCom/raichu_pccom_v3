# -*- coding: utf-8 -*-
"""
Pipeline de Generación - PcComponentes Content Generator
Versión 5.1.0

Pipeline principal de generación de contenido en 3 etapas,
extraído de app.py para mantener la modularidad.

Incluye:
- execute_generation_pipeline(): Pipeline completo new/rewrite
- _check_visual_elements_presence(): Verificación de elementos visuales
- _check_ai_phrases(): Detección de frases IA
- _check_engagement_elements(): Verificación de engagement con auto-retry

Autor: PcComponentes - Product Discovery & Content
"""

import re
import time
import logging
import traceback
from typing import Dict, List, Any, Optional

import streamlit as st

logger = logging.getLogger(__name__)

# ============================================================================
# IMPORTS LAZY (se cargan al ejecutar, no al importar el módulo)
# ============================================================================

# Flags de disponibilidad — se evalúan en tiempo de ejecución
def _get_module_flags():
    """Obtiene flags de disponibilidad de módulos."""
    flags = {}
    
    try:
        from core.generator import ContentGenerator
        flags['ContentGenerator'] = ContentGenerator
    except ImportError:
        flags['ContentGenerator'] = None
    
    try:
        from prompts import new_content
        flags['new_content'] = new_content
        flags['_new_content_available'] = True
    except ImportError:
        flags['new_content'] = None
        flags['_new_content_available'] = False
    
    try:
        from prompts import rewrite
        flags['rewrite'] = rewrite
        flags['_rewrite_available'] = True
    except ImportError:
        flags['rewrite'] = None
        flags['_rewrite_available'] = False
    
    try:
        from prompts.brand_tone import get_system_prompt_base
        flags['get_system_prompt_base'] = get_system_prompt_base
        flags['_brand_tone_available'] = True
    except ImportError:
        flags['get_system_prompt_base'] = lambda: None
        flags['_brand_tone_available'] = False
    
    try:
        from config.settings import DEBUG_MODE, CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE
        flags['DEBUG_MODE'] = DEBUG_MODE
        flags['CLAUDE_API_KEY'] = CLAUDE_API_KEY
        flags['CLAUDE_MODEL'] = CLAUDE_MODEL
        flags['MAX_TOKENS'] = MAX_TOKENS
        flags['TEMPERATURE'] = TEMPERATURE
    except ImportError:
        flags['DEBUG_MODE'] = False
        flags['CLAUDE_API_KEY'] = ''
        flags['CLAUDE_MODEL'] = 'claude-sonnet-4-20250514'
        flags['MAX_TOKENS'] = 8192
        flags['TEMPERATURE'] = 0.7
    
    try:
        from config.arquetipos import get_arquetipo
        flags['get_arquetipo'] = get_arquetipo
    except ImportError:
        flags['get_arquetipo'] = lambda x: None
    
    try:
        from utils.html_utils import count_words_in_html
        flags['count_words_in_html'] = count_words_in_html
    except ImportError:
        flags['count_words_in_html'] = lambda x: 0

    try:
        from utils.content_scrubber import scrub_html
        flags['scrub_html'] = scrub_html
    except ImportError:
        flags['scrub_html'] = None

    try:
        from core import openai_client
        flags['openai_client'] = openai_client
        flags['_openai_client_available'] = True
    except ImportError:
        flags['openai_client'] = None
        flags['_openai_client_available'] = False

    # OpenAI model: leer de st.secrets o app.py global
    try:
        flags['OPENAI_MODEL'] = st.secrets.get('openai_model', 'gpt-4.1-2025-04-14')
    except Exception:
        import os
        flags['OPENAI_MODEL'] = os.getenv('OPENAI_MODEL', 'gpt-4.1-2025-04-14')

    return flags


def _extract_html_content(text: str) -> str:
    """Extrae HTML limpio de la respuesta del modelo."""
    if not text:
        return ""
    # Eliminar marcadores markdown
    import re as _re
    text = _re.sub(r'^```html?\s*', '', text, flags=_re.MULTILINE)
    text = _re.sub(r'^```\s*$', '', text, flags=_re.MULTILINE)
    text = text.strip()
    return text


# ============================================================================
# PIPELINE Y FUNCIONES AUXILIARES
# ============================================================================

def execute_generation_pipeline(config: Dict[str, Any], mode: str = 'new') -> None:
    """
    Ejecuta el pipeline completo de generación en 3 etapas.
    
    Args:
        config: Configuración de generación
        mode: 'new' para nuevo contenido, 'rewrite' para reescritura
    
    Raises:
        TypeError: Si config no es dict o mode no es string
        ValueError: Si mode no es 'new' o 'rewrite'
        ValueError: Si faltan keys requeridas en config
    """
    # Cargar dependencias de módulos
    _flags = _get_module_flags()
    ContentGenerator = _flags['ContentGenerator']
    new_content = _flags['new_content']
    rewrite = _flags['rewrite']
    _new_content_available = _flags['_new_content_available']
    _rewrite_available = _flags['_rewrite_available']
    _brand_tone_available = _flags['_brand_tone_available']
    get_system_prompt_base = _flags['get_system_prompt_base']
    DEBUG_MODE = _flags['DEBUG_MODE']
    get_arquetipo = _flags['get_arquetipo']
    count_words_in_html = _flags['count_words_in_html']
    scrub_html = _flags['scrub_html']
    extract_html_content = _extract_html_content
    openai_client = _flags['openai_client']
    _openai_client_available = _flags['_openai_client_available']
    OPENAI_MODEL = _flags['OPENAI_MODEL']
    CLAUDE_API_KEY = _flags['CLAUDE_API_KEY']
    CLAUDE_MODEL = _flags['CLAUDE_MODEL']
    MAX_TOKENS = _flags['MAX_TOKENS']
    TEMPERATURE = _flags['TEMPERATURE']
    
    # ========================================================================
    # VALIDACIONES DE ENTRADA
    # ========================================================================
    # Validar tipos
    if not isinstance(config, dict):
        raise TypeError(f"config debe ser dict, recibido: {type(config).__name__}")
    
    if not isinstance(mode, str):
        raise TypeError(f"mode debe ser string, recibido: {type(mode).__name__}")
    
    # Validar mode
    if mode not in ['new', 'rewrite']:
        raise ValueError(f"mode debe ser 'new' o 'rewrite', recibido: '{mode}'")
    
    # Validar keys requeridas
    required_keys = ['keyword', 'target_length', 'arquetipo_codigo']
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValueError(f"Config incompleto. Faltan keys: {missing}")
    
    # ========================================================================
    # DEBUG: Verificar datos JSON (v4.9.0)
    # ========================================================================
    if DEBUG_MODE:
        logger.info("=" * 60)
        logger.info("DEBUG: Verificando datos JSON en config")
        logger.info(f"  pdp_json_data: {'✅ Presente' if config.get('pdp_json_data') else '❌ Ausente'}")
        links = config.get('links', config.get('internal_links', []))
        links_with_data = sum(1 for l in links if l.get('product_data'))
        logger.info(f"  links con product_data: {links_with_data}/{len(links)}")
        alt = config.get('producto_alternativo', config.get('alternative_product', {}))
        if alt:
            logger.info(f"  alternative_product.json_data: {'✅ Presente' if alt.get('json_data') else '❌ Ausente'}")
        logger.info("=" * 60)
    # ========================================================================
    
    if ContentGenerator is None:
        st.error("❌ ContentGenerator no está disponible")
        return
    
    # Validar módulos según modo
    if mode == 'new' and not _new_content_available:
        st.error("❌ Módulo prompts.new_content no disponible")
        return
    
    if mode == 'rewrite' and not _rewrite_available:
        st.error("❌ Módulo prompts.rewrite no disponible")
        return
    
    # Marcar generación en progreso
    st.session_state.generation_in_progress = True
    st.session_state.last_config = config
    
    # Crear generador
    try:
        generator = ContentGenerator(
            api_key=CLAUDE_API_KEY,
            model=CLAUDE_MODEL,
            max_tokens=MAX_TOKENS,
            temperature=TEMPERATURE
        )
    except Exception as e:
        st.error(f"❌ Error al crear generador: {e}")
        st.session_state.generation_in_progress = False
        return
    
    # Contenedor de progreso
    progress_container = st.container()
    
    try:
        # ====================================================================
        # PREPARAR CONFIG DE REWRITE (usado en las 3 etapas)
        # ====================================================================
        
        rewrite_config = {}
        if mode == 'rewrite':
            # Preparar contexto con HTML a reescribir si existe
            context_with_html = config.get('context', '')
            if config.get('html_to_rewrite'):
                context_with_html += f"""

CONTENIDO ACTUAL A MEJORAR/REESCRIBIR:
{config.get('html_to_rewrite')}

Usa este contenido como base, mejóralo y amplíalo según el análisis competitivo.
"""
            
            # Construir config dict para rewrite (las funciones de rewrite
            # esperan un dict 'config' del que extraen los parámetros internamente)
            rewrite_config = {
                'target_length': config.get('target_length', 1500),
                'keywords': config.get('keywords', [config.get('keyword', '')]),
                'context': context_with_html,
                'editorial_links': config.get('links', config.get('editorial_links', [])),
                'product_links': config.get('product_links', []),
                'objetivo': config.get('objetivo', ''),
                'producto_alternativo': config.get('producto_alternativo', {}),
                'alternative_products': config.get('alternative_products', []),
                'arquetipo_codigo': config.get('arquetipo_codigo', ''),
                'rewrite_mode': config.get('rewrite_mode', 'single'),
                'rewrite_instructions': config.get('rewrite_instructions', {}),
                'html_contents': config.get('html_contents', []),
                'disambiguation': config.get('disambiguation'),
                'main_product': config.get('main_product'),
            }
        
        # ====================================================================
        # ETAPA 0 (new): INVESTIGACIÓN SERP (opcional)
        # ====================================================================
        
        serp_context = ""
        if mode == 'new' and config.get('serp_research', False):
            with progress_container:
                st.markdown("### 🔍 Etapa 0/3: Investigación SERP")
                
                with st.spinner("Analizando qué posiciona en las SERPs..."):
                    try:
                        from utils.serp_research import research_serp, format_for_prompt, _get_serpapi_key
                        
                        research = research_serp(config.get('keyword', ''))
                        
                        if research.success:
                            serp_context = format_for_prompt(research)
                            
                            # Mostrar resumen al usuario
                            n_results = len(research.serp_results)
                            n_scraped = sum(1 for c in research.competitors if c.success)
                            avg_words = research.avg_word_count
                            n_related = len(research.related_searches)
                            
                            summary_parts = [
                                f"✅ {n_results} resultados encontrados",
                                f"{n_scraped} competidores analizados",
                            ]
                            if avg_words:
                                summary_parts.append(f"~{avg_words} palabras de media")
                            if n_related:
                                summary_parts.append(f"{n_related} búsquedas relacionadas")
                            
                            st.success(", ".join(summary_parts))
                            
                            # Expander con detalle
                            with st.expander("📊 Ver detalle del análisis", expanded=False):
                                from utils.serp_research import format_for_display
                                st.markdown(format_for_display(research))
                        else:
                            st.warning(f"⚠️ SERP: {research.error}")
                    except ImportError:
                        st.warning("⚠️ Módulo serp_research no disponible")
                    except Exception as e:
                        logger.warning(f"Error en investigación SERP: {e}")
                        st.warning(f"⚠️ Investigación SERP fallida: {str(e)[:100]}")
                    
                    time.sleep(0.3)
        
        # ====================================================================
        # ETAPA 0 (solo rewrite): ANÁLISIS COMPETITIVO
        # ====================================================================
        
        if mode == 'rewrite':
            # Inyectar contexto enriquecido de Oportunidades si existe
            _prefill_ctx = st.session_state.pop('prefill_analysis_context', None)
            if _prefill_ctx:
                existing = st.session_state.get('rewrite_analysis') or ''
                st.session_state.rewrite_analysis = (
                    f"{existing}\n\n{_prefill_ctx}" if existing else _prefill_ctx
                )
                logger.info("Contexto enriquecido de Oportunidades inyectado en rewrite_analysis")

            if not st.session_state.get('rewrite_analysis'):
                with progress_container:
                    st.markdown("### 🔍 Análisis Competitivo")
                    
                    with st.spinner("Analizando contenido de competidores..."):
                        # Verificar que tenemos los datos necesarios
                        competitors_data = config.get('competitors_data', [])
                        html_to_rewrite = config.get('html_to_rewrite', '')
                        
                        if not competitors_data and not html_to_rewrite:
                            st.warning("⚠️ No hay competidores ni contenido HTML para analizar.")
                        
                        # Formatear competidores
                        competitor_contents = rewrite.format_competitors_for_prompt(competitors_data)
                        
                        # Si hay HTML a reescribir, añadirlo
                        if html_to_rewrite:
                            competitor_contents += f"""

---
CONTENIDO ACTUAL A MEJORAR:
{html_to_rewrite}
---
"""
                        
                        # NOTA: build_competitor_analysis_prompt() NO EXISTE
                        # Construimos el prompt de análisis inline
                        analysis_prompt = f"""Analiza el siguiente contenido de competidores para la keyword "{config['keyword']}".

{competitor_contents}

Proporciona un análisis estructurado que incluya:
1. Fortalezas comunes de los competidores
2. Debilidades y gaps de contenido
3. Oportunidades de diferenciación
4. Longitud promedio y estructura
5. Keywords secundarias detectadas
6. Recomendaciones para superar a la competencia

Formato tu respuesta de manera clara y accionable."""
                        
                        # Ejecutar análisis
                        result = generator.generate(analysis_prompt)
                        
                        if result.success:
                            st.session_state.rewrite_analysis = result.content
                            st.success("✅ Análisis competitivo completado")
                        else:
                            st.warning(f"⚠️ Análisis parcial: {result.error}")
                            st.session_state.rewrite_analysis = "Análisis no disponible"
                        
                        time.sleep(0.5)
        
        # ====================================================================
        # ETAPA 1: BORRADOR INICIAL
        # ====================================================================
        
        with progress_container:
            st.markdown("### 📝 Etapa 1/3: Generando Borrador Inicial")
            st.session_state.current_stage = 1
            
            with st.spinner("Claude está escribiendo el borrador inicial..."):
                # Construir prompt según el modo
                if mode == 'new':
                    # Obtener arquetipo
                    arquetipo = get_arquetipo(config.get('arquetipo_codigo', 'ARQ-1'))
                    
                    if arquetipo is None:
                        logger.warning(f"Arquetipo no encontrado: {config.get('arquetipo_codigo')}")
                        arquetipo = {'code': 'ARQ-1', 'name': 'Review', 'tone': 'experto'}
                    
                    # ================================================================
                    # CAMBIO v4.9.0: Añadido pdp_json_data
                    # ================================================================
                    
                    # Enriquecer guiding_context con SERP research si disponible
                    guiding = config.get('context', config.get('guiding_context', ''))
                    if serp_context:
                        guiding = f"{guiding}\n\n{serp_context}" if guiding else serp_context
                    
                    stage1_prompt = new_content.build_new_content_prompt_stage1(
                        keyword=config.get('keyword', ''),
                        arquetipo=arquetipo,
                        target_length=config.get('target_length', 1500),
                        pdp_data=config.get('pdp_data'),
                        pdp_json_data=config.get('pdp_json_data'),
                        links_data=config.get('links', config.get('internal_links', [])),
                        secondary_keywords=config.get('keywords', []),
                        additional_instructions=config.get('objetivo', config.get('additional_instructions', '')),
                        campos_especificos=config.get('campos_arquetipo', {}),
                        visual_elements=config.get('visual_elements', []),
                        guiding_context=guiding,
                        alternative_product=config.get('producto_alternativo', config.get('alternative_product')),
                        products=config.get('products', []),
                        headings_config=config.get('headings_config'),
                    )
                else:  # mode == 'rewrite'
                    stage1_prompt = rewrite.build_rewrite_prompt_stage1(
                        keyword=config.get('keyword', ''),
                        competitor_analysis=st.session_state.get('rewrite_analysis', ''),
                        config=rewrite_config,
                    )
                
                # Generar borrador (con system prompt de tono de marca)
                # Optimizar prompt para reducir consumo de contexto
                try:
                    from utils.prompt_optimizer import optimize_prompt, check_prompt_size
                    stage1_prompt = optimize_prompt(stage1_prompt)
                    size_info = check_prompt_size(stage1_prompt)
                    if size_info['warning']:
                        logger.info(f"Prompt size: {size_info['warning']}")
                except ImportError:
                    pass
                
                system_prompt = get_system_prompt_base() if _brand_tone_available else None
                result = generator.generate(stage1_prompt, system_prompt=system_prompt)
                
                if not result.success:
                    st.error(f"❌ Error en Etapa 1: {result.error}")
                    st.session_state.generation_in_progress = False
                    return
                
                draft_html = result.content
                
                # Validar que obtuvimos contenido
                if not draft_html or len(draft_html) < 100:
                    st.error("❌ El borrador generado está vacío o es muy corto")
                    st.session_state.generation_in_progress = False
                    return
                
                # Extraer HTML limpio
                st.session_state.draft_html = extract_html_content(draft_html)
                
                # Mostrar métricas
                word_count = count_words_in_html(st.session_state.draft_html)
                st.success(f"✅ Borrador completado: {word_count} palabras")
                time.sleep(0.5)
        
        # ====================================================================
        # ETAPA 2: ANÁLISIS CRÍTICO (con corrección dual si OpenAI disponible)
        # ====================================================================
        
        with progress_container:
            # Determinar si hay corrección dual
            dual_enabled = _openai_client_available and openai_client.is_available()
            stage2_label = "Análisis Crítico Dual" if dual_enabled else "Análisis Crítico"
            st.markdown(f"### 🔍 Etapa 2/3: {stage2_label}")
            st.session_state.current_stage = 2
            
            # Construir prompt de análisis según modo
            if mode == 'new':
                # Construir kwargs para stage2
                stage2_kwargs = dict(
                    draft_content=st.session_state.draft_html,
                    target_length=config.get('target_length', 1500),
                    keyword=config.get('keyword', ''),
                    links_to_verify=config.get('links', config.get('internal_links', [])),
                    alternative_product=config.get('producto_alternativo', config.get('alternative_product')),
                    products=config.get('products', []),  # v5.0
                )
                # visual_elements: pasar solo si la función lo soporta
                try:
                    import inspect
                    _s2_sig = inspect.signature(new_content.build_new_content_correction_prompt_stage2)
                    if 'visual_elements' in _s2_sig.parameters:
                        stage2_kwargs['visual_elements'] = config.get('visual_elements', [])
                except Exception:
                    pass
                stage2_prompt = new_content.build_correction_prompt_stage2(**stage2_kwargs)
            else:  # mode == 'rewrite'
                stage2_prompt = rewrite.build_rewrite_correction_prompt_stage2(
                    draft_content=st.session_state.draft_html,
                    target_length=config.get('target_length', 1500),
                    keyword=config.get('keyword', ''),
                    competitor_analysis=st.session_state.get('rewrite_analysis', ''),
                    config=rewrite_config,
                )
            
            # --- Análisis de Claude ---
            with st.spinner("Claude está analizando el borrador..."):
                system_prompt = get_system_prompt_base() if _brand_tone_available else None
                result = generator.generate(stage2_prompt, system_prompt=system_prompt)
                
                if not result.success:
                    st.warning(f"⚠️ Análisis Claude parcial: {result.error}")
                    claude_analysis = "{}"
                else:
                    claude_analysis = result.content
                    st.success("✅ Análisis Claude completado")
            
            # --- Análisis de OpenAI (corrección dual) ---
            if dual_enabled:
                with st.spinner(f"OpenAI ({OPENAI_MODEL}) está revisando el borrador..."):
                    ok, openai_analysis, openai_meta = openai_client.generate_dual_analysis(
                        prompt=stage2_prompt,
                        model=OPENAI_MODEL,
                    )
                    
                    if ok:
                        st.success(
                            f"✅ Análisis OpenAI completado "
                            f"({openai_meta.get('tokens', 0)} tokens, "
                            f"{openai_meta.get('time', 0)}s)"
                        )
                        # Fusionar ambos análisis
                        st.session_state.analysis_json = openai_client.merge_dual_analyses(
                            claude_analysis=claude_analysis,
                            openai_analysis=openai_analysis,
                        )
                        logger.info("Corrección dual completada: análisis fusionados")
                    else:
                        st.warning(
                            f"⚠️ OpenAI no disponible: {openai_meta.get('error', 'desconocido')}. "
                            "Continuando solo con análisis de Claude."
                        )
                        st.session_state.analysis_json = claude_analysis
            else:
                st.session_state.analysis_json = claude_analysis
            
            time.sleep(0.5)
        
        # ====================================================================
        # ETAPA 3: VERSIÓN FINAL
        # ====================================================================
        
        with progress_container:
            st.markdown("### ✅ Etapa 3/3: Generando Versión Final")
            st.session_state.current_stage = 3
            
            with st.spinner("Claude está generando la versión final..."):
                # Construir prompt final según modo
                if mode == 'new':
                    # ================================================================
                    # CAMBIO v4.9.0: Añadidos links_data y alternative_product
                    # ================================================================
                    # Construir kwargs para stage3
                    stage3_kwargs = dict(
                        draft_content=st.session_state.draft_html,
                        analysis_feedback=st.session_state.analysis_json,
                        keyword=config.get('keyword', ''),
                        target_length=config.get('target_length', 1500),
                        links_data=config.get('links', config.get('internal_links', [])),
                        alternative_product=config.get('producto_alternativo', config.get('alternative_product')),
                        products=config.get('products', []),  # v5.0
                    )
                    # visual_elements: pasar solo si la función lo soporta
                    try:
                        import inspect
                        _s3_sig = inspect.signature(new_content.build_final_prompt_stage3)
                        if 'visual_elements' in _s3_sig.parameters:
                            stage3_kwargs['visual_elements'] = config.get('visual_elements', [])
                    except Exception:
                        pass
                    stage3_prompt = new_content.build_final_prompt_stage3(**stage3_kwargs)
                else:  # mode == 'rewrite'
                    stage3_prompt = rewrite.build_rewrite_final_prompt_stage3(
                        draft_content=st.session_state.draft_html,
                        corrections_json=st.session_state.analysis_json,
                        config=rewrite_config,
                    )
                
                # Generar versión final (con system prompt de tono de marca)
                system_prompt = get_system_prompt_base() if _brand_tone_available else None
                result = generator.generate(stage3_prompt, system_prompt=system_prompt)
                
                if not result.success:
                    st.error(f"❌ Error en Etapa 3: {result.error}")
                    st.session_state.generation_in_progress = False
                    return
                
                final_html = result.content
                
                # Validar contenido final
                if not final_html or len(final_html) < 100:
                    st.error("❌ El contenido final está vacío o es muy corto")
                    st.session_state.generation_in_progress = False
                    return
                
                # Extraer HTML limpio
                st.session_state.final_html = extract_html_content(final_html)
                
                # Post-generation PASO 1: Content Scrubber (limpiar watermarks Unicode)
                if scrub_html:
                    try:
                        cleaned_html, scrub_stats = scrub_html(st.session_state.final_html)
                        st.session_state.final_html = cleaned_html
                        total_scrubbed = sum(scrub_stats.values())
                        if total_scrubbed > 0:
                            st.caption(
                                f"🧹 Limpieza automática: {scrub_stats['unicode_removed']} watermarks, "
                                f"{scrub_stats['emdashes_replaced']} em-dashes, "
                                f"{scrub_stats['format_control_removed']} chars de control"
                            )
                    except Exception as e:
                        logger.warning(f"Content scrubber error: {e}")
                
                # Mostrar métricas finales
                final_word_count = count_words_in_html(st.session_state.final_html)
                target = config.get('target_length', 1500)
                diff_pct = ((final_word_count - target) / target) * 100 if target > 0 else 0
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Palabras Finales", final_word_count)
                with col2:
                    st.metric("Objetivo", target)
                with col3:
                    st.metric("Precisión", f"{100 - abs(diff_pct):.1f}%")
                
                # Post-generation PASO 1.5: Fix tablas (thead/tbody + responsive)
                try:
                    from utils.table_fixer import fix_tables
                    fixed_html, table_stats = fix_tables(st.session_state.final_html)
                    if table_stats['tables_found'] > 0:
                        st.session_state.final_html = fixed_html
                        fixes = []
                        if table_stats['thead_added'] > 0:
                            fixes.append(f"{table_stats['thead_added']} thead añadidos")
                        if table_stats['responsive_wrapped'] > 0:
                            fixes.append(f"{table_stats['responsive_wrapped']} tablas con scroll mobile")
                        if fixes:
                            st.caption(f"📊 Tablas: {table_stats['tables_found']} encontradas, {', '.join(fixes)}")
                except ImportError:
                    pass
                except Exception as e:
                    logger.warning(f"Table fixer error: {e}")
                
                st.success("✅ ¡Generación completada!")
                
                # Post-generation PASO 2: Quality Score multi-dimensional
                quality_result = None
                try:
                    from utils.quality_scorer import score_content
                    quality_result = score_content(
                        html_content=st.session_state.final_html,
                        keyword=config.get('keyword', ''),
                        secondary_keywords=config.get('keywords', []),
                        target_length=target,
                    )
                    st.session_state.quality_score = quality_result
                    composite = quality_result['composite_score']
                    
                    if composite >= 70:
                        st.success(f"✅ Quality Score: **{composite}/100** — Publicable")
                    else:
                        st.warning(f"⚠️ Quality Score: **{composite}/100** — Lanzando auto-revisión...")
                    
                    # Mostrar dimensiones en expander
                    with st.expander("📊 Desglose de calidad", expanded=composite < 70):
                        dim_cols = st.columns(5)
                        for i, (dim_key, dim_data) in enumerate(quality_result['dimensions'].items()):
                            with dim_cols[i]:
                                st.metric(
                                    dim_data['label'],
                                    f"{dim_data['score']}/100",
                                    f"×{dim_data['weight']:.0%}",
                                )
                        
                        # Mostrar fixes prioritarios
                        if quality_result['priority_fixes']:
                            st.markdown("**🔧 Correcciones prioritarias:**")
                            for fix in quality_result['priority_fixes'][:3]:
                                st.markdown(f"- {fix['description']}")
                    
                    # ============================================================
                    # QUALITY LOOP: auto-revisión si score < 70
                    # Máximo 1 iteración para no acumular costes API
                    # ============================================================
                    if composite < 70 and quality_result['priority_fixes']:
                        try:
                            from core.generator import ContentGenerator
                            from config.settings import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE
                            
                            fixes_text = "\n".join(
                                f"- {fix['description']}" for fix in quality_result['priority_fixes'][:5]
                            )
                            
                            revision_prompt = f"""Eres un editor SEO de PcComponentes. El siguiente HTML necesita correcciones de calidad.

PUNTUACIÓN ACTUAL: {composite}/100 (mínimo para publicar: 70)

CORRECCIONES OBLIGATORIAS (aplica TODAS):
{fixes_text}

REGLAS ESTRICTAS:
1. NO cambies la estructura HTML (articles, clases CSS, IDs, nav, style)
2. NO elimines ni modifiques enlaces (<a href>)
3. NO alteres headings (h2, h3) ni su contenido
4. NO cambies el <style> ni los elementos visuales (tablas, callouts, grids, etc.)
5. SOLO mejora el TEXTO de los párrafos (<p>) aplicando las correcciones
6. Mantén la longitud similar (±10%)
7. Responde con el HTML completo (empezando por <style>)
8. NO uses ```html ni marcadores markdown

HTML A CORREGIR:
{st.session_state.final_html}

Genera el HTML corregido:"""
                            
                            with st.spinner(f"🔄 Auto-revisando calidad ({composite}/100 → objetivo ≥70)..."):
                                qloop_generator = ContentGenerator(
                                    api_key=CLAUDE_API_KEY,
                                    model=CLAUDE_MODEL,
                                    max_tokens=MAX_TOKENS,
                                    temperature=max(0.3, TEMPERATURE - 0.1),  # Algo menos creativo para preservar
                                )
                                system_prompt_ql = get_system_prompt_base() if _brand_tone_available else None
                                qloop_result = qloop_generator.generate(revision_prompt, system_prompt=system_prompt_ql)
                                
                                if qloop_result.success and qloop_result.content and len(qloop_result.content) > 200:
                                    revised_html = extract_html_content(qloop_result.content)
                                    
                                    if revised_html and len(revised_html) > len(st.session_state.final_html) * 0.85:
                                        # Verificar que el contenido original se preserva (>85% palabras)
                                        original_words = set(
                                            w.lower() for w in re.sub(r'<[^>]+>', ' ', st.session_state.final_html).split()
                                            if len(w) > 3
                                        )
                                        new_words = set(
                                            w.lower() for w in re.sub(r'<[^>]+>', ' ', revised_html).split()
                                            if len(w) > 3
                                        )
                                        preservation = len(original_words & new_words) / max(1, len(original_words))
                                        
                                        if preservation > 0.80:
                                            # Re-score el contenido revisado
                                            new_quality = score_content(
                                                html_content=revised_html,
                                                keyword=config.get('keyword', ''),
                                                secondary_keywords=config.get('keywords', []),
                                                target_length=target,
                                            )
                                            new_composite = new_quality['composite_score']
                                            
                                            if new_composite > composite:
                                                # Aplicar scrubber al contenido revisado también
                                                if scrub_html:
                                                    try:
                                                        revised_html, _ = scrub_html(revised_html)
                                                    except Exception:
                                                        pass
                                                
                                                st.session_state.final_html = revised_html
                                                st.session_state.quality_score = new_quality
                                                
                                                # Actualizar word count
                                                final_word_count = count_words_in_html(revised_html)
                                                
                                                if new_composite >= 70:
                                                    st.success(
                                                        f"✅ Quality Loop: **{composite} → {new_composite}/100** — Publicable "
                                                        f"(preservación: {preservation:.0%})"
                                                    )
                                                else:
                                                    st.info(
                                                        f"📈 Quality Loop: **{composite} → {new_composite}/100** — Mejorado pero aún bajo 70. "
                                                        f"Usa el refinamiento para ajustar manualmente."
                                                    )
                                            else:
                                                st.info(
                                                    f"📊 Quality Loop: revisión no mejoró el score ({composite} → {new_composite}). "
                                                    f"Contenido original preservado."
                                                )
                                        else:
                                            logger.warning(f"Quality loop: preservación insuficiente ({preservation:.0%}), descartando")
                                            st.info("📊 Quality Loop: revisión alteró demasiado el contenido. Original preservado.")
                                    else:
                                        logger.warning("Quality loop: output demasiado corto, descartando")
                                else:
                                    logger.warning(f"Quality loop: generación fallida: {qloop_result.error}")
                        except ImportError:
                            logger.info("Quality loop: imports no disponibles, saltando")
                        except Exception as e:
                            logger.warning(f"Quality loop error: {e}")
                            
                except ImportError:
                    pass
                except Exception as e:
                    logger.warning(f"Quality scorer error: {e}")
                
                # Post-generation PASO 3: Keyword analysis
                try:
                    from utils.keyword_analyzer import analyze_keywords
                    kw = config.get('keyword', '')
                    if kw:
                        kw_result = analyze_keywords(
                            html_content=st.session_state.final_html,
                            primary_keyword=kw,
                            secondary_keywords=config.get('keywords', []),
                        )
                        st.session_state.keyword_analysis = kw_result
                        primary = kw_result['primary_keyword']
                        
                        with st.expander("🔑 Análisis de keyword"):
                            kw_cols = st.columns(4)
                            with kw_cols[0]:
                                st.metric("Densidad", f"{primary['density']}%",
                                         "✓" if primary['status'] == 'óptima' else primary['status'])
                            with kw_cols[1]:
                                st.metric("Apariciones", primary['count'])
                            with kw_cols[2]:
                                st.metric("Stuffing", primary['stuffing_risk'])
                            with kw_cols[3]:
                                p = kw_result['placements']
                                checks = sum([p['in_h2'], p['in_first_100_words'], p['in_conclusion']])
                                st.metric("Placements", f"{checks}/3")
                            
                            # Distribución
                            dist = kw_result['distribution']
                            st.markdown(f"**Distribución:** Inicio: {dist['inicio']} | "
                                       f"Medio: {dist['medio']} | Final: {dist['final']}")
                            if not kw_result['distribution_balanced']:
                                st.info("💡 Keyword concentrada en una zona. Distribuir más uniformemente.")
                except ImportError:
                    pass
                except Exception as e:
                    logger.warning(f"Keyword analyzer error: {e}")
                
                # Post-generation PASO 4: verificar elementos visuales seleccionados
                _check_visual_elements_presence(
                    st.session_state.final_html,
                    config.get('visual_elements', [])
                )
                
                # Post-generation PASO 5: detectar frases IA en el contenido final
                _check_ai_phrases(st.session_state.final_html)
                
                # Post-generation PASO 6: verificar engagement (mini-stories + CTAs)
                # Mini-stories solo se verifican si el arquetipo lo requiere Y hay reviews
                _arq_code = config.get('arquetipo_codigo', 'ARQ-1')
                _products = config.get('products', [])
                _has_reviews = False
                if _products:
                    _has_reviews = any(
                        (p.get('json_data') or {}).get('advantages_list')
                        or (p.get('json_data') or {}).get('disadvantages_list')
                        or (p.get('json_data') or {}).get('top_comments')
                        for p in _products
                    )
                else:
                    from prompts.new_content import _merge_product_data
                    _merged = _merge_product_data(config.get('pdp_data'), config.get('pdp_json_data'))
                    _has_reviews = bool(_merged and _merged.get('has_user_feedback'))

                from prompts.new_content import ARQUETIPOS_CON_MINI_STORIES
                _check_mini_stories = (_arq_code in ARQUETIPOS_CON_MINI_STORIES and _has_reviews)
                _check_engagement_elements(st.session_state.final_html, check_mini_stories=_check_mini_stories)
                
                # Post-generation PASO 7: generar meta title, meta description, TL;DR
                try:
                    from utils.meta_generator import generate_meta, validate_meta
                    
                    with st.spinner("📝 Generando meta SEO y TL;DR..."):
                        meta_result = generate_meta(
                            html_content=st.session_state.final_html,
                            keyword=config.get('keyword', ''),
                            pdp_data=config.get('pdp_data') or config.get('pdp_json_data'),
                            secondary_keywords=config.get('keywords', []),
                            arquetipo_name=get_arquetipo(config.get('arquetipo_codigo', '')).get('name', '') if get_arquetipo(config.get('arquetipo_codigo', '')) else '',
                        )
                    
                    if meta_result:
                        st.session_state.meta_seo = meta_result
                        
                        # Validar
                        meta_issues = validate_meta(meta_result, config.get('keyword', ''))
                        
                        with st.expander("📋 Meta SEO & TL;DR", expanded=True):
                            # Meta title
                            mt = meta_result.get('meta_title', '')
                            mt_len = len(mt)
                            mt_color = "green" if mt_len <= 60 else "red"
                            st.markdown(f"**Meta Title** ({mt_len}/60)")
                            st.code(mt, language=None)
                            
                            # Meta description
                            md = meta_result.get('meta_description', '')
                            md_len = len(md)
                            st.markdown(f"**Meta Description** ({md_len}/155)")
                            st.code(md, language=None)
                            
                            st.markdown("---")
                            
                            # TL;DR
                            tt = meta_result.get('tldr_title', '')
                            st.markdown(f"**TL;DR Título** ({len(tt)}/80)")
                            st.code(tt, language=None)
                            
                            td = meta_result.get('tldr_description', '')
                            st.markdown(f"**TL;DR Descripción** ({len(td)}/200)")
                            st.code(td, language=None)
                            
                            # Issues si los hay
                            if meta_issues:
                                st.warning("⚠️ " + " | ".join(meta_issues))
                except ImportError:
                    pass
                except Exception as e:
                    logger.warning(f"Meta generation error: {e}")
        
        # Guardar metadata
        try:
            from utils.state_manager import save_generation_to_state
            save_generation_to_state(config, mode)
        except ImportError:
            pass
        
    except Exception as e:
        logger.error(f"Error en pipeline: {e}\n{traceback.format_exc()}")
        st.error(f"❌ Error durante la generación: {str(e)}")
        
        with st.expander("Ver detalles del error"):
            st.code(traceback.format_exc())
    
    finally:
        st.session_state.generation_in_progress = False
        st.session_state.current_stage = 0


def _check_visual_elements_presence(html_content: str, selected_elements: List[str]) -> None:
    """
    Verifica que los elementos visuales seleccionados estén presentes en el HTML.
    
    Si faltan ≤3 elementos, intenta auto-retry con refinamiento targeted.
    Si faltan >3 o el retry falla, muestra warning al usuario.
    """
    if not selected_elements or not html_content:
        return
    
    missing_ids = _detect_missing_visual_elements(html_content, selected_elements)
    
    if not missing_ids:
        return
    
    _NAMES = _get_visual_element_names()
    missing_names = [_NAMES.get(eid, eid) for eid in missing_ids]
    
    # Auto-retry si ≤3 elementos faltantes
    if len(missing_ids) <= 3:
        retry_success = _auto_retry_missing_elements(html_content, missing_ids)
        if retry_success:
            # Verificar de nuevo tras retry
            still_missing = _detect_missing_visual_elements(
                st.session_state.final_html, selected_elements
            )
            if not still_missing:
                st.success(f"✅ Elementos insertados automáticamente: {', '.join(missing_names)}")
                return
            else:
                still_names = [_NAMES.get(eid, eid) for eid in still_missing]
                st.warning(
                    f"⚠️ **Auto-retry parcial:** Se intentó insertar {', '.join(missing_names)}, "
                    f"pero aún faltan: {', '.join(still_names)}. "
                    f"Puedes usar el refinamiento manual para añadirlos."
                )
                return
    
    # Fallback: warning (>3 faltantes o retry no intentado)
    st.warning(
        f"⚠️ **Elementos visuales no detectados en el HTML final:** {', '.join(missing_names)}. "
        f"El modelo puede no haber incluido todos los componentes solicitados. "
        f"Puedes regenerar o editar manualmente el HTML."
    )


def _detect_missing_visual_elements(html_content: str, selected_elements: List[str]) -> List[str]:
    """
    Detecta qué elementos visuales seleccionados NO están en el HTML.
    
    Returns:
        Lista de element_ids faltantes
    """
    html_lower = html_content.lower()
    
    _DETECT = {
        'toc': ['class="toc"', "class='toc'", 'nav class="toc'],
        'callout': ['class="callout"', "class='callout'"],
        'callout_promo': ['callout-bf', 'bf-callout'],
        'callout_alert': ['callout-alert'],
        'verdict': ['verdict-box', 'verdict_box'],
        'grid': ['class="grid', 'grid-layout', 'mod-grid', 'cols-2', 'cols-3'],
        'badges': ['class="badge'],
        'buttons': ['class="btn', 'class="btns', 'mod-cta'],
        'table': ['<table'],
        'light_table': ['class="lt '],
        'comparison_table': ['comparison-table', 'comparison-highlight'],
        'faqs': ['contentgenerator__faqs', 'class="faqs', 'faqs__item'],
        'intro_box': ['class="intro"', "class='intro'"],
        'check_list': ['check-list'],
        'specs_list': ['specs-list'],
        'product_module': ['product-module'],
        'price_highlight': ['price-highlight'],
        'stats_grid': ['font-size:32px', 'font-size: 32px'],
        'section_divider': ['linear-gradient(135deg,#170453'],
        'mod_cards': ['mod-card'],
        'vcard_cards': ['vcard'],
        'compact_cards': ['compact-cards', 'compact-card'],
        'use_cases': ['use-cases', 'use-case'],
    }
    
    missing = []
    for elem_id in selected_elements:
        patterns = _DETECT.get(elem_id, [])
        if patterns:
            found = any(p in html_lower for p in patterns)
            if not found:
                missing.append(elem_id)
    return missing


def _get_visual_element_names() -> Dict[str, str]:
    """Mapeo element_id → nombre legible."""
    return {
        'toc': 'Tabla de Contenidos',
        'callout': 'Callout',
        'callout_promo': 'Callout Promo',
        'callout_alert': 'Callout Alerta',
        'verdict': 'Verdict Box',
        'grid': 'Grid Layout',
        'badges': 'Badges',
        'buttons': 'Botones CTA',
        'table': 'Tabla HTML',
        'light_table': 'Light Table',
        'comparison_table': 'Tabla Comparación',
        'faqs': 'FAQs',
        'intro_box': 'Intro',
        'check_list': 'Check List',
        'specs_list': 'Specs List',
        'product_module': 'Product Module',
        'price_highlight': 'Price Highlight',
        'stats_grid': 'Stats Grid',
        'section_divider': 'Section Divider',
        'mod_cards': 'Mod Cards',
        'vcard_cards': 'VCard Cards',
        'compact_cards': 'Compact Cards (Naranja)',
        'use_cases': 'Cards Casos de Uso (Azul)',
    }


def _auto_retry_missing_elements(html_content: str, missing_ids: List[str]) -> bool:
    """
    Intenta insertar elementos visuales faltantes via refinamiento targeted.
    
    Solo se ejecuta si faltan ≤3 elementos. Usa un prompt enfocado exclusivamente
    en insertar los componentes faltantes sin alterar el resto del contenido.
    
    Args:
        html_content: HTML actual
        missing_ids: Lista de element_ids faltantes
        
    Returns:
        True si se completó el retry (aunque no garantiza éxito)
    """
    try:
        from core.generator import ContentGenerator
        from config.settings import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE
        extract_html_content = _extract_html_content
    except ImportError as e:
        logger.warning(f"Auto-retry: imports no disponibles: {e}")
        return False
    
    # Obtener templates de los elementos faltantes
    try:
        from prompts.new_content import _build_stage3_visual_instructions
        element_instructions = _build_stage3_visual_instructions(missing_ids)
    except ImportError:
        logger.warning("Auto-retry: no se puede importar _build_stage3_visual_instructions")
        return False
    
    _NAMES = _get_visual_element_names()
    missing_names = [_NAMES.get(eid, eid) for eid in missing_ids]
    
    retry_prompt = f"""Eres un editor SEO de PcComponentes. El siguiente HTML fue generado pero le FALTAN {len(missing_ids)} elementos visuales que el usuario solicitó.

Tu ÚNICA tarea es INSERTAR los elementos faltantes en las ubicaciones correctas del HTML.

REGLAS ESTRICTAS:
1. NO modifiques el texto, enlaces, headings o estructura existente
2. NO elimines ni reescribas nada del contenido actual
3. SOLO inserta los elementos nuevos donde correspondan
4. Mantén el <style> existente (ya incluye los estilos necesarios)
5. Responde con el HTML completo (con <style> y todo)
6. NO uses ```html ni marcadores markdown

ELEMENTOS QUE FALTAN ({len(missing_ids)}): {', '.join(missing_names)}

{element_instructions}

---

HTML ACTUAL (insertar los elementos faltantes):
{html_content}

---

Genera el HTML completo con los {len(missing_ids)} elementos insertados:"""

    logger.info(f"Auto-retry: insertando {len(missing_ids)} elementos faltantes: {missing_ids}")
    
    with st.spinner(f"🔄 Insertando elementos faltantes: {', '.join(missing_names)}..."):
        try:
            generator = ContentGenerator(
                api_key=CLAUDE_API_KEY,
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            result = generator.generate(retry_prompt)
            
            if result.success and result.content and len(result.content) > 200:
                cleaned = extract_html_content(result.content)
                # Validar que el output no es demasiado corto NI demasiado diferente
                # del original (protege contra reescrituras accidentales)
                if cleaned and len(cleaned) > len(html_content) * 0.9:
                    # Verificar que el contenido original se preserva (>90% del texto)
                    import re as _re
                    original_text = _re.sub(r'<[^>]+>', ' ', html_content).split()
                    new_text = _re.sub(r'<[^>]+>', ' ', cleaned).split()
                    # Comprobar que la mayoría de las palabras originales siguen presentes
                    original_set = set(w.lower() for w in original_text if len(w) > 3)
                    new_set = set(w.lower() for w in new_text if len(w) > 3)
                    if original_set and len(original_set & new_set) / len(original_set) > 0.85:
                        st.session_state.final_html = cleaned
                        logger.info(f"Auto-retry completado: {len(cleaned)} chars")
                        return True
                    else:
                        logger.warning("Auto-retry: contenido original no preservado, descartando")
                else:
                    logger.warning(f"Auto-retry: output demasiado corto ({len(cleaned) if cleaned else 0} chars)")
            else:
                logger.warning(f"Auto-retry fallido: {result.error}")
        except Exception as e:
            logger.warning(f"Auto-retry error: {e}")
    
    return False


def _check_ai_phrases(html_content: str) -> None:
    """
    Detecta frases típicas de IA en el contenido final y muestra feedback.
    
    Usa detección programática (regex) — 100% fiable, zero coste API.
    Muestra las frases encontradas con contexto para que el usuario
    pueda corregirlas vía refinamiento.
    """
    if not html_content:
        return
    
    try:
        from utils.html_utils import detect_ai_phrases
    except ImportError:
        return
    
    ai_phrases = detect_ai_phrases(html_content)
    
    if not ai_phrases:
        return
    
    n = len(ai_phrases)
    phrase_list = ", ".join(f'"{p["phrase"]}"' for p in ai_phrases[:5])
    
    if n <= 2:
        st.info(
            f"💡 **Tono:** Se detectaron {n} expresiones que suenan a IA: {phrase_list}. "
            f"Puedes corregirlas con el refinamiento."
        )
    else:
        st.warning(
            f"⚠️ **Tono IA detectado:** {n} expresiones típicas de escritura con IA: {phrase_list}. "
            f"Usa el refinamiento con instrucciones como 'reescribe las frases que suenan a IA' "
            f"para mejorar el tono."
        )


def _check_engagement_elements(html_content: str, check_mini_stories: bool = True) -> None:
    """
    Verifica presencia de mini-stories y CTAs distribuidos.
    Si faltan, intenta auto-retry (1 iteración) para insertarlos.

    Args:
        html_content: HTML generado
        check_mini_stories: Si False, no verifica ni inserta mini-stories.
            Solo se activa cuando el arquetipo lo requiere Y hay reviews disponibles.

    Detección:
    - Mini-stories: nombres propios + cifras en proximidad (solo si check_mini_stories=True)
    - CTAs distribuidos: enlaces con texto accionable en el HTML
    """
    if not html_content:
        return

    try:
        from utils.html_utils import strip_html_tags as _strip
        text = _strip(html_content)
    except ImportError:
        text = re.sub(r'<[^>]+>', ' ', html_content)

    text_lower = text.lower()

    # Detectar mini-stories solo si el arquetipo lo requiere y hay reviews
    nombres_pattern = r'\b(María|Carlos|Laura|Ana|Pedro|Miguel|Sara|Pablo|Lucía|Javier|Elena|David|Marta|Alberto|Carmen|Sofía|Diego|Andrea|Raúl|Cristina|Jorge)\b'
    if check_mini_stories:
        nombres = re.findall(nombres_pattern, html_content, re.IGNORECASE)
        nombres_unicos = len(set(n.lower() for n in nombres))
        missing_stories = nombres_unicos < 2
    else:
        missing_stories = False

    # Detectar CTAs (enlaces con texto accionable en español)
    cta_patterns = [
        'ver precio', 'comprar', 'ver en', 'echa un vistazo',
        'disponibilidad', 'comparar', 'explorar', 'descubrir',
        'ver oferta', 'ir a', 'conocer', 'probar',
    ]
    ctas_found = sum(1 for p in cta_patterns if p in text_lower)

    # También contar enlaces con → que suelen ser CTAs
    arrow_ctas = len(re.findall(r'<a[^>]+>[^<]*→[^<]*</a>', html_content))
    ctas_found += arrow_ctas

    missing_ctas = ctas_found < 2
    
    if not missing_stories and not missing_ctas:
        return  # Todo OK
    
    # ================================================================
    # AUTO-RETRY: insertar engagement elements faltantes
    # ================================================================
    fixes_needed = []
    if missing_stories:
        fixes_needed.append(
            "AÑADIR 2 mini-historias con nombres españoles concretos (ej: Carlos, Laura), "
            "cifras específicas (presupuestos, porcentajes, tiempos) y resultados claros. "
            "Una en la primera mitad del artículo y otra en la segunda mitad. "
            "Cada mini-historia: 50-100 palabras dentro de un <p> existente o nuevo."
        )
    if missing_ctas:
        fixes_needed.append(
            "AÑADIR 2 CTAs distribuidos: uno tras la primera sección de valor "
            "(texto como 'Echa un vistazo a...' o 'Mira el...') y otro antes del veredicto. "
            "Usar enlaces <a href> a URLs de PcComponentes que ya estén en el artículo."
        )
    
    try:
        from core.generator import ContentGenerator
        from config.settings import CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE
        extract_html_content = _extract_html_content
        
        fixes_text = "\n".join(f"- {f}" for f in fixes_needed)
        
        engagement_prompt = f"""Eres un editor de PcComponentes. El HTML siguiente necesita mejoras de engagement.

CORRECCIONES OBLIGATORIAS:
{fixes_text}

REGLAS ESTRICTAS:
1. NO cambies la estructura HTML (articles, clases CSS, IDs, nav, style)
2. NO elimines ni modifiques enlaces (<a href>) existentes
3. NO alteres headings (h2, h3)
4. NO cambies el <style> ni elimines elementos visuales
5. SOLO inserta o modifica texto dentro de párrafos <p>
6. Mantén la longitud similar (±15%)
7. Las mini-historias deben sonar naturales, no forzadas
8. Los CTAs deben ser contextuales (relacionados con la sección donde aparecen)
9. Responde con el HTML completo (empezando por <style>)
10. NO uses ```html ni marcadores markdown

HTML A MEJORAR:
{html_content}

Genera el HTML con las mejoras de engagement:"""
        
        with st.spinner("🔄 Insertando elementos de engagement (mini-historias + CTAs)..."):
            eng_generator = ContentGenerator(
                api_key=CLAUDE_API_KEY,
                model=CLAUDE_MODEL,
                max_tokens=MAX_TOKENS,
                temperature=TEMPERATURE,
            )
            eng_result = eng_generator.generate(engagement_prompt)
            
            if eng_result.success and eng_result.content and len(eng_result.content) > 200:
                revised = extract_html_content(eng_result.content)
                
                if revised and len(revised) > len(html_content) * 0.85:
                    # Verificar preservación
                    original_words = set(
                        w.lower() for w in re.sub(r'<[^>]+>', ' ', html_content).split()
                        if len(w) > 3
                    )
                    new_words = set(
                        w.lower() for w in re.sub(r'<[^>]+>', ' ', revised).split()
                        if len(w) > 3
                    )
                    preservation = len(original_words & new_words) / max(1, len(original_words))
                    
                    if preservation > 0.75:
                        # Verificar que se añadió algo
                        new_text_lower = re.sub(r'<[^>]+>', ' ', revised).lower()
                        new_nombres = re.findall(nombres_pattern, revised, re.IGNORECASE)
                        new_ctas = sum(1 for p in cta_patterns if p in new_text_lower)
                        new_ctas += len(re.findall(r'<a[^>]+>[^<]*→[^<]*</a>', revised))
                        
                        improved_stories = len(set(n.lower() for n in new_nombres)) >= 2
                        improved_ctas = new_ctas >= 2
                        
                        if (improved_stories or not missing_stories) and (improved_ctas or not missing_ctas):
                            # Aplicar scrubber
                            try:
                                from utils.content_scrubber import scrub_html
                                revised, _ = scrub_html(revised)
                            except Exception:
                                pass
                            
                            st.session_state.final_html = revised
                            improvements = []
                            if missing_stories and improved_stories:
                                improvements.append("mini-historias")
                            if missing_ctas and improved_ctas:
                                improvements.append("CTAs distribuidos")
                            
                            st.success(
                                f"✅ Engagement mejorado: se añadieron {', '.join(improvements)} "
                                f"(preservación: {preservation:.0%})"
                            )
                            return
                        else:
                            logger.info("Engagement retry: no se detectaron mejoras suficientes")
                    else:
                        logger.warning(f"Engagement retry: preservación insuficiente ({preservation:.0%})")
            else:
                logger.warning(f"Engagement retry fallido: {eng_result.error if eng_result else 'sin resultado'}")
    except ImportError:
        pass
    except Exception as e:
        logger.warning(f"Engagement retry error: {e}")
    
    # Fallback: mostrar tips informativos
    tips = []
    if missing_stories:
        tips.append("Incluir 2-3 mini-historias con nombres y situaciones concretas")
    if missing_ctas:
        tips.append("Distribuir 2-3 CTAs a lo largo del artículo (no solo al final)")
    
    if tips:
        st.info("💡 **Engagement:** " + ". ".join(tips) + ". Usa el refinamiento para añadirlos.")
