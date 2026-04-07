"""
PcComponentes Content Generator - App Principal

Aplicación Streamlit para generación de contenido SEO.
Flujo de 3 etapas: Borrador → Análisis → Final

Autor: PcComponentes - Product Discovery & Content
"""

import streamlit as st
import re
import hashlib
import logging
from typing import Dict, Any

# ============================================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============================================================================
# VERSIÓN
# ============================================================================

try:
    from version import __version__
except ImportError:
    __version__ = "5.1.0"
APP_TITLE = "PcComponentes Content Generator"

# ============================================================================
# CONFIGURACIÓN (delegada a core/config.py)
# ============================================================================

from core.config import (
    CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE, DEBUG_MODE,
    OPENAI_API_KEY, OPENAI_MODEL, GEMINI_API_KEY,
    check_configuration,
)

# ============================================================================
# IMPORTS CON MANEJO DE ERRORES
# ============================================================================

# Arquetipos
try:
    from config.arquetipos import get_arquetipo, get_arquetipo_names, ARQUETIPOS
except ImportError:
    logger.warning("No se pudo importar arquetipos")
    ARQUETIPOS = {}
    def get_arquetipo(code):
        return {'code': code, 'name': 'Default', 'tone': 'informativo'}
    def get_arquetipo_names():
        return []

# Generador de contenido
try:
    from core.generator import ContentGenerator, GenerationResult
    _generator_available = True
except ImportError as e:
    logger.error(f"No se pudo importar ContentGenerator: {e}")
    ContentGenerator = None
    GenerationResult = None
    _generator_available = False

# Prompts - new_content
try:
    from prompts import new_content
    _new_content_available = True
except ImportError as e:
    logger.error(f"No se pudo importar prompts.new_content: {e}")
    new_content = None
    _new_content_available = False

# Prompts - rewrite
try:
    from prompts import rewrite
    _rewrite_available = True
except ImportError as e:
    logger.error(f"No se pudo importar prompts.rewrite: {e}")
    rewrite = None
    _rewrite_available = False

# Brand tone (system prompt base) — fuente única: prompts.brand_tone
try:
    from prompts.brand_tone import get_system_prompt_base
    _brand_tone_available = True
except ImportError:
    try:
        from brand_tone import get_system_prompt_base
        _brand_tone_available = True
    except ImportError:
        _brand_tone_available = False
        def get_system_prompt_base():
            return None

# UI Components
try:
    from ui.inputs import render_content_inputs
    _inputs_available = True
except ImportError:
    logger.warning("No se pudo importar ui.inputs")
    _inputs_available = False
    render_content_inputs = None

try:
    from ui.rewrite import render_rewrite_section
    _rewrite_ui_available = True
except ImportError:
    logger.warning("No se pudo importar ui.rewrite")
    _rewrite_ui_available = False
    render_rewrite_section = None

try:
    from ui.results import render_results_section
    _results_available = True
except ImportError:
    logger.warning("No se pudo importar ui.results")
    _results_available = False
    render_results_section = None

try:
    from ui.sidebar import render_sidebar
    _sidebar_available = True
except ImportError:
    logger.warning("No se pudo importar ui.sidebar")
    _sidebar_available = False
    render_sidebar = None

try:
    from ui.assistant import (
        initialize_chat_state,
        render_chat_messages,
        build_messages_for_api,
        get_system_prompt,
        detect_and_execute_commands,
        detect_product_json_in_message,
        parse_generation_params,
    )
    _assistant_available = True
except ImportError:
    logger.warning("No se pudo importar ui.assistant")
    _assistant_available = False

# OpenAI para corrección dual
try:
    from core import openai_client
    _openai_client_available = True
except ImportError:
    try:
        import openai_client
        _openai_client_available = True
    except ImportError:
        _openai_client_available = False
        logger.info("Módulo openai_client no disponible. Corrección dual deshabilitada.")

# Utilidades HTML
try:
    from utils.html_utils import count_words_in_html
except ImportError:
    def count_words_in_html(html: str) -> int:
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        return len(text.split())

# extract_html_content: usar la de core.generator si está disponible, sino fallback local
try:
    from core.generator import extract_html_content
except ImportError:
    def extract_html_content(content: str) -> str:
        """Fallback: Extrae HTML limpio eliminando marcadores markdown."""
        import re
        if not content:
            return ""
        content = content.strip()
        # Eliminar ```html al inicio
        content = re.sub(r'^```html\s*\n?', '', content, flags=re.IGNORECASE)
        content = re.sub(r'^```\s*\n?', '', content)
        # Eliminar ``` al final
        content = re.sub(r'\n?```\s*$', '', content)
        content = content.strip()
        # Verificar que empieza con <
        if not content.startswith('<'):
            first_tag = content.find('<')
            if first_tag > 0:
                content = content[first_tag:]
        return content.strip()


# ============================================================================
# SESSION STATE (delegado a core/session.py)
# ============================================================================

from core.session import initialize_app


# ============================================================================
# HEADER, FOOTER, DEBUG (delegados a ui/router.py)
# ============================================================================

from ui.router import render_app_header, render_footer, render_debug_panel


# ============================================================================
# MODOS DE GENERACIÓN
# ============================================================================

def render_new_content_mode() -> None:
    """Renderiza el modo de nuevo contenido."""
    
    if not _inputs_available or render_content_inputs is None:
        st.error("❌ El módulo de inputs no está disponible")
        return
    
    # Manual de uso — solo visible si el usuario no ha generado antes
    if not st.session_state.get('_has_generated_new'):
        _render_usage_guide()

    # Renderizar inputs y obtener configuración
    is_valid, config = render_content_inputs()
    
    if not is_valid:
        return
    
    # Botón de generación
    st.markdown("---")

    col_serp, col_btn = st.columns([2, 3])

    with col_serp:
        serp_enabled = st.checkbox(
            "🔍 Investigar SERPs",
            value=True,
            help="Analiza la competencia en Google antes de generar. "
                 "Mejora la calidad (~5-8s extra).",
            key="cb_serp_research_new",
        )
        config['serp_research'] = serp_enabled

    with col_btn:
        generate_clicked = st.button(
            "🚀 Generar Contenido",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.get('generation_in_progress', False),
            key="btn_generate_new"
        )

    if generate_clicked:
        execute_generation_pipeline(config, mode='new')


def _render_usage_guide() -> None:
    """Renderiza guía de uso rápida para nuevos usuarios."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**Raichu genera artículos SEO en 3 etapas automáticas:** borrador → análisis → versión final.

**Para empezar solo necesitas 2 campos:**

| Paso | Campo | Ejemplo |
|------|-------|---------|
| **1** | **Keyword** — el término SEO objetivo | `mejores portátiles gaming 2025` |
| **2** | **Arquetipo** — el tipo de artículo | `ARQ-1: Guía de compra` |

**Campos opcionales que mejoran el resultado:**

| Campo | Para qué sirve |
|-------|----------------|
| **URL del producto** | Raichu extrae specs reales del PDP y las integra en el artículo |
| **Longitud** | Ajusta la extensión del artículo al arquetipo (por defecto ya optimizado) |
| **Briefing** | Preguntas contextuales que guían el enfoque del contenido |
| **Enlaces internos** | Links a categorías o artículos relacionados para SEO interno |
| **Enlaces PDP** | Productos a enlazar dentro del artículo con datos JSON enriquecidos |
| **Producto alternativo** | Alternativa a recomendar si el producto principal no encaja |
| **Elementos visuales** | Tablas comparativas, tarjetas de producto, cajas destacadas |
| **Instrucciones adicionales** | Cualquier indicación extra para el generador |
        """)
        
        st.info(
            "💡 **Consejo**: Empieza solo con keyword + arquetipo. "
            "Puedes refinar el resultado después con el panel de refinamiento."
        )


def render_rewrite_mode() -> None:
    """Renderiza el modo de reescritura competitiva."""
    
    if not _rewrite_ui_available or render_rewrite_section is None:
        st.error("❌ El módulo de reescritura no está disponible")
        return
    
    if not _rewrite_available:
        st.error("❌ El módulo prompts.rewrite no está disponible")
        return
    
    # Guía de uso — solo visible si el usuario no ha generado reescritura antes
    if not st.session_state.get('_has_generated_rewrite'):
        _render_rewrite_guide()

    # Renderizar sección de reescritura
    is_valid, config = render_rewrite_section()
    
    if not is_valid:
        return
    
    # Botón de generación
    st.markdown("---")

    generate_clicked = st.button(
        "🚀 Generar Reescritura",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.get('generation_in_progress', False),
        key="btn_generate_rewrite"
    )

    if generate_clicked:
        # Save original HTML for before/after comparison in results
        _orig_html = config.get('html_to_rewrite', '') or ''
        if not _orig_html and config.get('html_contents'):
            _orig_html = config['html_contents'][0].get('html', '')
        st.session_state['rewrite_original_html'] = _orig_html
        execute_generation_pipeline(config, mode='rewrite')


def _render_rewrite_guide() -> None:
    """Guía de uso para el modo reescritura competitiva."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**Reescritura Competitiva analiza tu contenido actual y el de competidores para generar una versión superior.**

**El proceso sigue 8 pasos guiados:**

| Paso | Qué haces | Obligatorio |
|------|-----------|:-----------:|
| **1. Keyword** | Define el término SEO objetivo | ✅ |
| **2. Contenido HTML** | Pega el HTML del artículo a reescribir (o varios para fusionar) | ✅ |
| **3. Instrucciones** | Indica qué mejorar, mantener o eliminar | ✅ |
| **4. Producto principal** | Vincula el producto protagonista con su [JSON (n8n)](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV) | — |
| **5. Competidores** | Se analizan automáticamente (SEMrush) o los introduces a mano | ✅ |
| **6. Configuración** | Arquetipo, longitud, tono | ✅ |
| **7. Enlaces** | Links internos a posts/PLPs y a PDPs con datos enriquecidos | — |
| **8. Alternativos** | Productos alternativos a recomendar | — |

**3 modos disponibles:**
- **Reescritura simple** — mejora un artículo existente
- **Fusión** — combina 2+ artículos en uno superior (ideal contra canibalización)
- **Desambiguación** — separa un artículo genérico en varios específicos
        """)
        
        st.info(
            "💡 **Consejo**: Si GSC detecta múltiples URLs para tu keyword, "
            "usa el modo Fusión para consolidarlas en un único artículo."
        )


# ============================================================================
# MODO VERIFICAR KEYWORD
# ============================================================================

# Verify mode (delegado a ui/verify.py)
try:
    from ui.verify import render_verify_mode
    _verify_ui_available = True
except ImportError:
    _verify_ui_available = False
    render_verify_mode = None


# ============================================================================
# MODO ASISTENTE
# ============================================================================


@st.cache_resource
def _get_cached_generator(_api_key: str, model: str, max_tokens: int = 8192, temperature: float = 0.7) -> 'ContentGenerator':
    """Obtiene o crea un ContentGenerator cacheado.

    Evita recrear el cliente de Anthropic (y su connection pool) en cada
    rerun. Se invalida automáticamente si cambian model, max_tokens o
    temperature.

    P3.9: anteriormente los 4 parámetros tenían prefijo `_`, lo que en
    `@st.cache_resource` significa "no incluir en la cache key". Resultado:
    la cache key era constante y el generator nunca se invalidaba al
    cambiar temperature, max_tokens ni model. Ahora solo `_api_key`
    mantiene el prefijo (no se hashea, evitando exponer la key en
    caches/logs internos de Streamlit); model, max_tokens y temperature
    sí forman parte de la cache key.
    """
    return ContentGenerator(
        api_key=_api_key,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
    )


def render_assistant_mode() -> None:
    """Renderiza el modo asistente (chat con herramientas internas)."""
    
    if not _assistant_available:
        st.error("❌ El módulo de asistente no está disponible")
        return
    
    if not _generator_available or ContentGenerator is None:
        st.error("❌ ContentGenerator no disponible. Se requiere la API de Claude.")
        return
    
    # Guía
    _render_assistant_guide()
    
    # Inicializar estado del chat
    initialize_chat_state()
    
    # Renderizar historial
    render_chat_messages()
    
    # Input del usuario
    user_input = st.chat_input(
        "Pregunta sobre keywords, arquetipos, productos o pide generar contenido..."
    )
    
    if not user_input:
        return
    
    # Detectar si el usuario pegó un JSON de producto
    product_json = detect_product_json_in_message(user_input)
    if product_json:
        user_input = (
            f"El usuario ha pegado un JSON de producto. Analízalo con "
            f"[PRODUCTO_ANALIZAR: {product_json}]\n\n"
            f"Mensaje original del usuario: {user_input[:200]}"
        )
    
    # Añadir mensaje del usuario
    st.session_state.assistant_messages.append({
        'role': 'user',
        'content': user_input if not product_json else user_input.split("Mensaje original del usuario: ")[-1],
    })
    
    # Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(
            user_input if not product_json 
            else user_input.split("Mensaje original del usuario: ")[-1]
        )
    
    # Llamar a Claude
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                generator = _get_cached_generator(CLAUDE_API_KEY, CLAUDE_MODEL, MAX_TOKENS, TEMPERATURE)

                messages = build_messages_for_api()

                # Construir prompt con historial
                # La API de Claude recibe system + messages
                system = get_system_prompt()

                # Usar el último mensaje como prompt, el resto como contexto
                if len(messages) > 1:
                    context_parts = []
                    for m in messages[:-1]:
                        role_label = "Usuario" if m['role'] == 'user' else "Asistente"
                        context_parts.append(f"{role_label}: {m['content']}")
                    context = "\n\n".join(context_parts)
                    full_prompt = (
                        f"Historial de conversación:\n{context}\n\n"
                        f"Usuario: {messages[-1]['content']}"
                    )
                else:
                    full_prompt = messages[-1]['content']

                result = generator.generate(
                    prompt=full_prompt,
                    system_prompt=system,
                    temperature=0.7,
                )
                
                if not result.success:
                    st.error(f"❌ Error: {result.error}")
                    return
                
                # Detectar y ejecutar comandos en la respuesta
                cleaned_response, tool_results = detect_and_execute_commands(
                    result.content
                )
                
                # Mostrar respuesta del asistente
                if cleaned_response:
                    st.markdown(cleaned_response)
                
                # Mostrar resultados de herramientas
                for tr in tool_results:
                    with st.expander(f"🔧 {tr['command']}", expanded=True):
                        st.markdown(tr['result'])
                
                # Guardar en historial
                st.session_state.assistant_messages.append({
                    'role': 'assistant',
                    'content': cleaned_response,
                    'tool_results': tool_results,
                })
                
                # Si hay comando GENERAR, preparar para ejecutar
                gen_commands = [tr for tr in tool_results if tr.get('action') == 'generate']
                if gen_commands:
                    params = parse_generation_params(gen_commands[0].get('params', ''))
                    _handle_assistant_generation(params)
                
            except Exception as e:
                logger.error(f"Error en asistente: {e}")
                st.error("❌ Error del asistente. Por favor, inténtalo de nuevo.")


def _handle_assistant_generation(params: Dict[str, str]) -> None:
    """
    Maneja la generación de contenido lanzada desde el asistente.
    
    Args:
        params: Dict con keyword, arquetipo, longitud, visual (opcional)
    """
    keyword = params.get('keyword', '')
    arquetipo_code = params.get('arquetipo', 'ARQ-1')
    target_length = int(params.get('longitud', '1500'))
    visual_str = params.get('visual', '')
    
    if not keyword:
        st.warning("⚠️ Falta la keyword para generar contenido.")
        return
    
    # Parsear componentes visuales
    visual_elements = []
    if visual_str:
        visual_elements = [v.strip() for v in visual_str.split(',') if v.strip()]
    
    # Default: toc + verdict si no se especificó
    if not visual_elements:
        visual_elements = ['toc', 'verdict']
    
    visual_label = ', '.join(visual_elements) if visual_elements else 'por defecto'
    
    st.info(
        f"🚀 Lanzando generación: **{keyword}** | "
        f"Arquetipo: {arquetipo_code} | Longitud: {target_length} palabras | "
        f"Visual: {visual_label}"
    )
    
    # Construir guiding_context desde la conversación del asistente
    guiding_context = _build_assistant_guiding_context()
    
    config = {
        'keyword': keyword,
        'target_length': target_length,
        'arquetipo_codigo': arquetipo_code,
        'mode': 'new',
        'links': [],
        'additional_instructions': '',
        'guiding_context': guiding_context,
        'visual_elements': visual_elements,
        'visual_config': {
            'selected': visual_elements,
            'variants': {},
            'components_css': [],
        },
    }
    
    execute_generation_pipeline(config, mode='new')


def _build_assistant_guiding_context() -> str:
    """
    Construye guiding_context a partir del historial del asistente.
    
    Extrae contexto relevante de:
    1. Mensajes del usuario en la conversación del asistente
    2. Resultados de herramientas ejecutadas (SERP research, GSC, análisis de producto)
    """
    context_parts = []
    
    assistant_messages = st.session_state.get('assistant_messages', [])
    if not assistant_messages:
        return ""
    
    # 1. Extraer mensajes relevantes del usuario (máx últimos ~3 turnos)
    user_messages = [
        m['content'] for m in assistant_messages[-8:]
        if m.get('role') == 'user' and len(m.get('content', '')) > 10
    ]
    if user_messages:
        context_parts.append(
            "**Contexto de la conversación con el asistente:**\n" + 
            "\n".join(f"- {msg[:500]}" for msg in user_messages[-4:])
        )
    
    # 2. Extraer resultados de herramientas (SERP, GSC, producto, etc.)
    for m in assistant_messages[-6:]:
        tool_results = m.get('tool_results', [])
        for tr in tool_results:
            command = tr.get('command', '')
            result = tr.get('result', '')
            # Solo incluir resultados informativos, no errores ni comandos GENERAR
            if (result and len(result) > 20 
                    and not result.startswith('❌') 
                    and not result.startswith('⚠️')
                    and tr.get('action') != 'generate'):
                context_parts.append(
                    f"**Resultado de {command}:**\n{result[:1500]}"
                )
    
    return "\n\n".join(context_parts) if context_parts else ""


def _render_assistant_guide() -> None:
    """Guía de uso para el modo asistente."""
    
    with st.expander("📖 ¿Cómo funciona? — Guía rápida", expanded=False):
        st.markdown("""
**El asistente es tu copiloto para la creación de contenido.** Pregúntale en lenguaje natural y usará las herramientas internas de Raichu automáticamente.

**Ejemplos de lo que puedes preguntar:**

| Pregunta | Qué hace el asistente |
|----------|----------------------|
| "¿Qué contenido posiciona en Google para mejores portátiles gaming?" | Investiga las SERPs, scrapea competidores y analiza su estructura |
| "¿Tengo contenido para monitor gaming 4K?" | Verifica en GSC si ya posicionas para esa keyword |
| "¿Qué arquetipo me recomiendas para una guía de compra de portátiles?" | Consulta los arquetipos y recomienda el más adecuado |
| "Muéstrame los arquetipos disponibles" | Lista todos los tipos de contenido con su descripción |
| "¿Qué elementos visuales me recomiendas para una comparativa?" | Sugiere componentes del design system según el tipo de artículo |
| "¿Qué componentes visuales hay disponibles?" | Lista todos los componentes CSS del design system |
| *(pegar un [JSON de producto](https://n8n.prod.pccomponentes.com/workflow/jsjhKAdZFBSM5XFV))* | Analiza las specs, reviews y características del producto |
| "Genera un artículo para mejores auriculares gaming con ARQ-1" | Lanza la generación con componentes visuales recomendados |

**El historial se mantiene** durante toda la sesión, incluso si cambias a otro modo y vuelves.
        """)
        
        st.info(
            "💡 **Consejo**: Empieza verificando tu keyword, luego pide una recomendación "
            "de arquetipo, y finalmente lanza la generación — todo desde el chat."
        )


# ============================================================================
# PIPELINE DE GENERACIÓN (delegado a core/pipeline.py)
# ============================================================================

def execute_generation_pipeline(config: Dict[str, Any], mode: str = 'new') -> None:
    """
    Ejecuta el pipeline completo de generación en 3 etapas.
    Delegado a core.pipeline para mantener app.py manejable.
    """
    # Recordar que el usuario ya ha generado en este modo (oculta guía)
    if mode == 'new':
        st.session_state['_has_generated_new'] = True
    elif mode == 'rewrite':
        st.session_state['_has_generated_rewrite'] = True

    from core.pipeline import execute_generation_pipeline as _execute
    _execute(config, mode)


# Helpers de pipeline (delegados a core.pipeline)
def _check_visual_elements_presence(html_content, selected_elements):
    from core.pipeline import _check_visual_elements_presence as _fn
    _fn(html_content, selected_elements)

def _check_ai_phrases(html_content):
    from core.pipeline import _check_ai_phrases as _fn
    _fn(html_content)

def _check_engagement_elements(html_content, check_mini_stories=True):
    from core.pipeline import _check_engagement_elements as _fn
    _fn(html_content, check_mini_stories=check_mini_stories)



# ============================================================================
# RESULTADOS Y FOOTER
# ============================================================================

def render_results() -> None:
    """Renderiza la sección de resultados.
    
    Solo muestra resultados si fueron generados por el modo ACTUAL.
    Esto evita que un artículo generado en 'new' se arrastre a 'rewrite' o 'assistant'.
    """
    current_mode = st.session_state.get('mode', 'new')
    
    if not any([
        st.session_state.get('draft_html'),
        st.session_state.get('analysis_json'),
        st.session_state.get('final_html')
    ]):
        return
    
    # Verificar que los resultados pertenecen al modo actual
    gen_meta = st.session_state.get('generation_metadata', {})
    result_mode = gen_meta.get('mode', '')
    
    # El asistente genera con mode='new' internamente, así que lo aceptamos en assistant
    if result_mode and result_mode != current_mode:
        if not (current_mode == 'assistant' and result_mode == 'new'):
            return
    
    if _results_available and render_results_section:
        render_results_section(
            draft_html=st.session_state.get('draft_html'),
            analysis_json=st.session_state.get('analysis_json'),
            final_html=st.session_state.get('final_html'),
            target_length=st.session_state.get('last_config', {}).get('target_length', 1500),
            mode=st.session_state.get('mode', 'new')
        )
    else:
        # Fallback simple si render_results_section no está disponible
        st.markdown("---")
        st.subheader("📊 Resultados")
        
        if st.session_state.get('final_html'):
            st.markdown("### ✅ Contenido Final")
            with st.expander("Ver HTML"):
                st.code(st.session_state.final_html, language="html")
            
            st.download_button(
                "📥 Descargar HTML",
                st.session_state.final_html,
                file_name=f"content_{st.session_state.get('timestamp', 'export')}.html",
                mime="text/html"
            )




# ============================================================================
# AUTENTICACIÓN (delegado a core/auth.py)
# ============================================================================

try:
    from core.auth import check_auth
    _auth_available = True
except ImportError:
    _auth_available = False
    def check_auth():
        return True


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Función principal de la aplicación."""
    
    # Configuración de página
    st.set_page_config(
        page_title=APP_TITLE,
        page_icon="🚀",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Autenticación
    if not check_auth():
        st.stop()
    
    # Inicializar
    initialize_app(
        openai_client=openai_client if _openai_client_available else None,
        openai_api_key=OPENAI_API_KEY,
        openai_model=OPENAI_MODEL,
    )
    
    # Verificar configuración
    is_valid, errors = check_configuration(
        _generator_available, _new_content_available, _openai_client_available
    )
    
    if not is_valid:
        st.error("❌ Error de Configuración")
        for error in errors:
            st.warning(f"• {error}")
        st.stop()
    
    # Sidebar
    if _sidebar_available and render_sidebar:
        render_sidebar()
    
    # Header con selector de modo
    mode = render_app_header(APP_TITLE, __version__)
    
    # Renderizar según modo
    if mode == 'new':
        render_new_content_mode()
    elif mode == 'rewrite':
        render_rewrite_mode()
    elif mode == 'verify':
        if _verify_ui_available and render_verify_mode:
            render_verify_mode()
        else:
            st.error("Módulo de verificación no disponible")
    elif mode == 'opportunities':
        try:
            from ui.opportunities import render_opportunities_mode
            render_opportunities_mode()
        except ImportError as e:
            logger.error(f"Módulo de oportunidades no disponible: {e}")
            st.error("❌ Módulo de oportunidades no disponible. Verifica la instalación.")
    elif mode == 'assistant':
        render_assistant_mode()
    
    # Resultados (solo para modos de generación)
    # v5.0: results.py ahora incluye refinamiento integrado en el flujo
    if mode in ['new', 'rewrite', 'assistant']:
        render_results()
    
    # Footer
    render_footer(__version__, DEBUG_MODE)

    # Debug panel
    render_debug_panel(DEBUG_MODE, {
        'generator': _generator_available,
        'new_content': _new_content_available,
        'rewrite': _rewrite_available,
        'inputs_ui': _inputs_available,
        'rewrite_ui': _rewrite_ui_available,
        'results_ui': _results_available,
    })


if __name__ == "__main__":
    main()
