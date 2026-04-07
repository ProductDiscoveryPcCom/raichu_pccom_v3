"""
Content Generator - PcComponentes Content Generator
Versión 1.2.0 - 2026-02-10

Módulo de generación de contenido usando la API de Claude (Anthropic).
Incluye manejo robusto de errores, reintentos con backoff exponencial,
y validación exhaustiva de respuestas.

CAMBIOS v1.2.0:
- FIX: Import de config.settings usa nombres reales (CLAUDE_MODEL, TEMPERATURE,
  MAX_RETRIES, RETRY_DELAY) en vez de aliases inexistentes que caían al fallback
- Versión sincronizada a 1.2.0

Este módulo proporciona:
- ContentGenerator: Clase principal para generación
- generate_content(): Función de generación simple
- generate_with_stages(): Generación en 3 etapas
- call_claude_api(): Llamada directa a la API con reintentos

Autor: PcComponentes - Product Discovery & Content
"""

import re
import time
import logging
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# ============================================================================
# VERSIÓN
# ============================================================================

__version__ = "1.2.0"

# ============================================================================
# IMPORTS DE ANTHROPIC CON MANEJO DE ERRORES
# ============================================================================

try:
    import anthropic
    from anthropic import (
        Anthropic,
        APIError,
        APIConnectionError,
        RateLimitError,
        APIStatusError,
        AuthenticationError,
        BadRequestError,
        PermissionDeniedError,
        NotFoundError,
        UnprocessableEntityError,
        InternalServerError,
    )
    _anthropic_available = True
except ImportError as e:
    logger.error(f"No se pudo importar anthropic: {e}")
    _anthropic_available = False
    
    # Definir clases placeholder
    class APIError(Exception):
        pass
    class APIConnectionError(Exception):
        pass
    class RateLimitError(Exception):
        pass
    class APIStatusError(Exception):
        pass
    class AuthenticationError(Exception):
        pass
    class BadRequestError(Exception):
        pass
    class PermissionDeniedError(Exception):
        pass
    class NotFoundError(Exception):
        pass
    class UnprocessableEntityError(Exception):
        pass
    class InternalServerError(Exception):
        pass

# ============================================================================
# IMPORTS DE CONFIGURACIÓN
# ============================================================================

try:
    from core.config import (
        CLAUDE_API_KEY,
        CLAUDE_MODEL,
        MAX_TOKENS,
        TEMPERATURE,
    )
    from config.settings import (
        MAX_RETRIES,
        RETRY_DELAY,
    )
    # Aliases internos para mantener compatibilidad en este módulo
    DEFAULT_MODEL = CLAUDE_MODEL
    DEFAULT_TEMPERATURE = TEMPERATURE
    DEFAULT_MAX_RETRIES = MAX_RETRIES
    DEFAULT_RETRY_DELAY = RETRY_DELAY
except ImportError:
    # Fallback si no está core.config (legacy/standalone)
    import os
    CLAUDE_API_KEY = os.getenv('ANTHROPIC_API_KEY', os.getenv('CLAUDE_API_KEY', ''))
    DEFAULT_MODEL = 'claude-sonnet-4-20250514'
    MAX_TOKENS = 16000
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0


# ============================================================================
# CONSTANTES
# ============================================================================

AVAILABLE_MODELS = {
    'claude-sonnet-4-20250514': 'Claude Sonnet 4',
    'claude-opus-4-20250514': 'Claude Opus 4',
    'claude-3-5-sonnet-20241022': 'Claude 3.5 Sonnet',
    'claude-3-opus-20240229': 'Claude 3 Opus',
    'claude-3-haiku-20240307': 'Claude 3 Haiku',
}

MAX_RETRY_DELAY = 60.0
BACKOFF_MULTIPLIER = 2.0
OVERLOADED_INITIAL_DELAY = 5.0  # Delay más largo para 529 (API overloaded)

MODEL_TOKEN_LIMITS = {
    'claude-sonnet-4-20250514': 200000,
    'claude-opus-4-20250514': 200000,
    'claude-3-5-sonnet-20241022': 200000,
    'claude-3-opus-20240229': 200000,
    'claude-3-haiku-20240307': 200000,
}


# ============================================================================
# EXCEPCIONES PERSONALIZADAS
# ============================================================================

class GenerationError(Exception):
    """Excepción base para errores de generación."""
    
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
    
    def __str__(self):
        if self.details:
            return f"{self.message} | Detalles: {self.details}"
        return self.message


class TokenLimitError(GenerationError):
    """Error cuando se excede el límite de tokens."""
    pass


class APIKeyError(GenerationError):
    """Error relacionado con la API key."""
    pass


class ContentValidationError(GenerationError):
    """Error en la validación del contenido generado."""
    pass


class RetryExhaustedError(GenerationError):
    """Error cuando se agotan los reintentos."""
    pass


# ============================================================================
# ENUMS Y DATA CLASSES
# ============================================================================

class GenerationStage(Enum):
    """Etapas del proceso de generación."""
    DRAFT = 1
    ANALYSIS = 2
    FINAL = 3


@dataclass
class GenerationResult:
    """Resultado de una generación."""
    success: bool
    content: str
    stage: int
    model: str
    tokens_used: int
    generation_time: float
    error: Optional[str] = None
    metadata: Optional[Dict] = field(default_factory=dict)


@dataclass
class APIResponse:
    """Respuesta parseada de la API."""
    content: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    model: str
    stop_reason: str


# ============================================================================
# CLIENTE DE ANTHROPIC (SINGLETON)
# ============================================================================

_client: Optional[Any] = None


def get_client() -> Any:
    """
    Obtiene el cliente de Anthropic (patrón singleton).
    """
    global _client
    
    if not _anthropic_available:
        raise ImportError(
            "El módulo 'anthropic' no está instalado. "
            "Instálalo con: pip install anthropic"
        )
    
    if _client is None:
        api_key = CLAUDE_API_KEY
        
        if not api_key:
            raise APIKeyError(
                "CLAUDE_API_KEY no está configurada",
                {"hint": "Añade CLAUDE_API_KEY o ANTHROPIC_API_KEY al archivo .env o secrets"}
            )
        
        if not api_key.startswith('sk-ant-'):
            raise APIKeyError(
                "CLAUDE_API_KEY tiene formato inválido",
                {"hint": "La API key debe empezar con 'sk-ant-'"}
            )
        
        _client = Anthropic(api_key=api_key)
        logger.info("Cliente de Anthropic inicializado correctamente")
    
    return _client


def reset_client() -> None:
    """Resetea el cliente."""
    global _client
    _client = None


# ============================================================================
# FUNCIÓN PRINCIPAL: LLAMADA A LA API CON REINTENTOS
# ============================================================================

def call_claude_api(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    system_prompt: Optional[str] = None,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY,
    client: Optional[Any] = None,
) -> APIResponse:
    """
    Llama a la API de Claude con manejo robusto de errores y reintentos.
    """
    client = client or get_client()
    
    messages = [{"role": "user", "content": prompt}]
    
    current_delay = retry_delay
    last_error = None
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Llamando a Claude API (intento {attempt + 1}/{max_retries})")
            
            kwargs = {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = client.messages.create(**kwargs)
            
            content = ""
            if response.content:
                for block in response.content:
                    if hasattr(block, 'text'):
                        content += block.text
            
            return APIResponse(
                content=content,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                total_tokens=response.usage.input_tokens + response.usage.output_tokens,
                model=response.model,
                stop_reason=response.stop_reason or "unknown",
            )
        
        except AuthenticationError as e:
            raise APIKeyError("API key inválida o expirada", {"original_error": str(e)})
        
        except RateLimitError as e:
            last_error = e
            logger.warning(f"Rate limit alcanzado, esperando {current_delay}s...")
            time.sleep(current_delay)
            current_delay = min(current_delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
        
        except APIConnectionError as e:
            last_error = e
            logger.warning(f"Error de conexión, reintentando en {current_delay}s...")
            time.sleep(current_delay)
            current_delay = min(current_delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
        
        except BadRequestError as e:
            error_msg = str(e)
            if "token" in error_msg.lower():
                raise TokenLimitError("El prompt excede el límite de tokens", {"original_error": error_msg})
            raise GenerationError(f"Error en la solicitud: {error_msg}", {"original_error": error_msg})
        
        except APIStatusError as e:
            if e.status_code == 529:
                last_error = e
                overload_delay = max(current_delay, OVERLOADED_INITIAL_DELAY)
                logger.warning(f"API sobrecargada (529), esperando {overload_delay}s...")
                time.sleep(overload_delay)
                current_delay = min(overload_delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
            elif e.status_code >= 500:
                last_error = e
                logger.warning(f"Error del servidor ({e.status_code}), reintentando en {current_delay}s...")
                time.sleep(current_delay)
                current_delay = min(current_delay * BACKOFF_MULTIPLIER, MAX_RETRY_DELAY)
            else:
                raise GenerationError(f"Error de API ({e.status_code}): {str(e)}", {"status_code": e.status_code})
        
        except Exception as e:
            raise GenerationError(f"Error inesperado: {str(e)}", {"type": type(e).__name__})
    
    raise RetryExhaustedError(
        f"Se agotaron los {max_retries} reintentos",
        {"last_error": str(last_error) if last_error else "Unknown"}
    )


# ============================================================================
# FUNCIONES DE GENERACIÓN
# ============================================================================

def generate_content(
    prompt: str,
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    system_prompt: Optional[str] = None,
    client: Optional[Any] = None,
) -> GenerationResult:
    """Genera contenido usando Claude API."""
    start_time = time.time()

    try:
        response = call_claude_api(
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system_prompt=system_prompt,
            client=client,
        )
        
        generation_time = time.time() - start_time
        
        return GenerationResult(
            success=True,
            content=response.content,
            stage=1,
            model=response.model,
            tokens_used=response.total_tokens,
            generation_time=generation_time,
            metadata={
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "stop_reason": response.stop_reason,
            }
        )
    
    except GenerationError as e:
        generation_time = time.time() - start_time
        logger.error(f"Error de generación: {e}")
        
        return GenerationResult(
            success=False,
            content="",
            stage=1,
            model=model,
            tokens_used=0,
            generation_time=generation_time,
            error=str(e),
            metadata=e.details if hasattr(e, 'details') else {}
        )
    
    except Exception as e:
        generation_time = time.time() - start_time
        logger.error(f"Error inesperado: {e}")
        
        return GenerationResult(
            success=False,
            content="",
            stage=1,
            model=model,
            tokens_used=0,
            generation_time=generation_time,
            error=f"Error inesperado: {str(e)}",
        )


def generate_with_stages(
    stage1_prompt: str,
    stage2_prompt_builder: Callable[[str], str],
    stage3_prompt_builder: Callable[[str, str], str],
    model: str = DEFAULT_MODEL,
    max_tokens: int = MAX_TOKENS,
    temperature: float = DEFAULT_TEMPERATURE,
    system_prompt: Optional[str] = None,
    on_stage_complete: Optional[Callable[[int, GenerationResult], None]] = None,
    client: Optional[Any] = None,
) -> Tuple[GenerationResult, GenerationResult, GenerationResult]:
    """Genera contenido en 3 etapas (borrador, análisis, final)."""

    # ============== ETAPA 1: BORRADOR ==============
    logger.info("=== ETAPA 1: Generando borrador ===")

    result1 = generate_content(
        prompt=stage1_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
        client=client,
    )
    result1.stage = 1
    
    if on_stage_complete:
        on_stage_complete(1, result1)
    
    if not result1.success:
        logger.error("Etapa 1 falló, abortando")
        empty2 = GenerationResult(success=False, content="", stage=2, model=model, tokens_used=0, generation_time=0, error="Etapa previa falló")
        empty3 = GenerationResult(success=False, content="", stage=3, model=model, tokens_used=0, generation_time=0, error="Etapa previa falló")
        return result1, empty2, empty3
    
    # ============== ETAPA 2: ANÁLISIS ==============
    logger.info("=== ETAPA 2: Analizando borrador ===")
    
    stage2_prompt = stage2_prompt_builder(result1.content)
    
    result2 = generate_content(
        prompt=stage2_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=0.3,
        system_prompt=system_prompt,
        client=client,
    )
    result2.stage = 2
    
    if on_stage_complete:
        on_stage_complete(2, result2)
    
    if not result2.success:
        logger.error("Etapa 2 falló, abortando")
        empty3 = GenerationResult(success=False, content="", stage=3, model=model, tokens_used=0, generation_time=0, error="Etapa previa falló")
        return result1, result2, empty3
    
    # ============== ETAPA 3: VERSIÓN FINAL ==============
    logger.info("=== ETAPA 3: Generando versión final ===")
    
    stage3_prompt = stage3_prompt_builder(result1.content, result2.content)
    
    result3 = generate_content(
        prompt=stage3_prompt,
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
        client=client,
    )
    result3.stage = 3
    
    if on_stage_complete:
        on_stage_complete(3, result3)
    
    return result1, result2, result3


# ============================================================================
# FUNCIONES DE VALIDACIÓN Y EXTRACCIÓN
# ============================================================================

def validate_response(content: str) -> Dict[str, Any]:
    """Valida el contenido de la respuesta."""
    validation = {
        "is_valid": True,
        "has_html": bool(re.search(r'<[^>]+>', content)),
        "has_article": '<article' in content.lower(),
        "has_headings": bool(re.search(r'<h[1-6]', content, re.I)),
        "word_count": len(re.sub(r'<[^>]+>', '', content).split()),
        "errors": [],
        "warnings": [],
    }
    
    if not validation["has_html"]:
        validation["warnings"].append("No se detectó contenido HTML")
    
    if validation["word_count"] < 100:
        validation["warnings"].append(f"Contenido muy corto: {validation['word_count']} palabras")
    
    return validation


def extract_html_content(content: str) -> str:
    """
    Extrae el contenido HTML limpio de la respuesta.
    
    SIEMPRE limpia marcadores markdown como ```html, ``` etc.
    
    Args:
        content: Contenido que puede contener HTML envuelto en markdown
        
    Returns:
        HTML limpio sin marcadores markdown
    """
    if not content:
        return ""
    
    # Paso 1: Limpiar espacios al inicio/final
    content = content.strip()
    
    # Paso 2: Eliminar marcadores markdown al inicio
    # Patrones comunes: ```html, ```HTML, ```xml, ```
    markdown_start_patterns = [
        r'^```html\s*\n?',
        r'^```HTML\s*\n?',
        r'^```xml\s*\n?',
        r'^```\s*\n?',
    ]
    for pattern in markdown_start_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # Paso 3: Eliminar marcadores markdown al final
    markdown_end_patterns = [
        r'\n?```\s*$',
        r'\n?```html\s*$',
    ]
    for pattern in markdown_end_patterns:
        content = re.sub(pattern, '', content, flags=re.IGNORECASE)
    
    # Paso 4: Limpiar de nuevo espacios
    content = content.strip()
    
    # Paso 5: Si todavía hay marcadores en medio, extraer el contenido
    html_match = re.search(r'```(?:html)?\s*(.*?)\s*```', content, re.DOTALL | re.IGNORECASE)
    if html_match:
        content = html_match.group(1).strip()
    
    # Paso 6: Verificar que empieza con tag HTML válido
    # Si no empieza con <, buscar el primer <
    if not content.startswith('<'):
        first_tag = content.find('<')
        if first_tag > 0:
            # Hay texto antes del HTML, lo eliminamos
            content = content[first_tag:]
    
    # Paso 7: Verificar que termina con tag HTML
    if content and not content.rstrip().endswith('>'):
        last_tag = content.rfind('>')
        if last_tag > 0:
            content = content[:last_tag + 1]
    
    return content.strip()


def count_tokens(text: str) -> int:
    """Estima el número de tokens en un texto (~4 caracteres por token)."""
    return len(text) // 4


def estimate_prompt_tokens(prompt: str, system_prompt: Optional[str] = None) -> int:
    """Estima tokens totales del prompt incluyendo system."""
    total = count_tokens(prompt)
    if system_prompt:
        total += count_tokens(system_prompt)
    return total


# ============================================================================
# CLASE CONTENTGENERATOR
# ============================================================================

class ContentGenerator:
    """
    Clase principal para generación de contenido SEO.
    
    Encapsula la lógica de generación en 3 etapas:
    1. Borrador inicial
    2. Análisis crítico
    3. Versión final
    
    Example:
        >>> generator = ContentGenerator(api_key="sk-ant-...")
        >>> result = generator.generate(prompt="Escribe sobre...")
        >>> if result.success:
        ...     print(result.content)
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        """
        Inicializa el generador de contenido.
        
        Args:
            api_key: API key de Anthropic (opcional, usa env si no se provee)
            model: Modelo de Claude a usar
            max_tokens: Máximo de tokens por respuesta
            temperature: Temperatura de generación
        """
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = None

        # Instance-level client when a custom api_key is provided,
        # avoids mutating module-level state in multi-user Streamlit
        if api_key and _anthropic_available:
            self._client = Anthropic(api_key=api_key)

        if not _anthropic_available:
            logger.warning("Anthropic SDK no disponible")

        # P3.9 (TEMPORAL — restaurar tras verificar invalidación de cache):
        # log de instanciación con todos los params para confirmar que
        # @st.cache_resource invalida correctamente en app.py.
        logger.info(
            "ContentGenerator inicializado: model=%s, max_tokens=%d, temperature=%.2f",
            model,
            max_tokens,
            temperature,
        )
    
    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> GenerationResult:
        """
        Genera contenido con un prompt simple.
        
        Args:
            prompt: Prompt para generar
            system_prompt: Prompt de sistema opcional
            temperature: Override de temperatura
            max_tokens: Override de max_tokens
            
        Returns:
            GenerationResult con el contenido generado
        """
        return generate_content(
            prompt=prompt,
            model=self.model,
            max_tokens=max_tokens if max_tokens is not None else self.max_tokens,
            temperature=temperature if temperature is not None else self.temperature,
            system_prompt=system_prompt,
            client=self._client,
        )
    
    def generate_with_stages(
        self,
        stage1_prompt: str,
        stage2_prompt_builder: Callable[[str], str],
        stage3_prompt_builder: Callable[[str, str], str],
        system_prompt: Optional[str] = None,
        on_stage_complete: Optional[Callable[[int, GenerationResult], None]] = None,
    ) -> Tuple[GenerationResult, GenerationResult, GenerationResult]:
        """
        Genera contenido en 3 etapas.
        
        Args:
            stage1_prompt: Prompt para el borrador
            stage2_prompt_builder: Función para construir prompt de análisis
            stage3_prompt_builder: Función para construir prompt final
            system_prompt: Prompt de sistema opcional
            on_stage_complete: Callback al completar cada etapa
            
        Returns:
            Tuple de 3 GenerationResult
        """
        return generate_with_stages(
            stage1_prompt=stage1_prompt,
            stage2_prompt_builder=stage2_prompt_builder,
            stage3_prompt_builder=stage3_prompt_builder,
            model=self.model,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            system_prompt=system_prompt,
            on_stage_complete=on_stage_complete,
            client=self._client,
        )
    
    def validate_content(self, content: str) -> Dict[str, Any]:
        """Valida el contenido generado."""
        return validate_response(content)
    
    def extract_html(self, content: str) -> str:
        """Extrae HTML limpio del contenido."""
        return extract_html_content(content)
    
    def is_available(self) -> bool:
        """Verifica si el generador está listo para usar."""
        return is_api_available()


# ============================================================================
# FUNCIONES DE UTILIDAD
# ============================================================================

def is_api_available() -> bool:
    """Verifica si la API de Anthropic está disponible."""
    if not _anthropic_available:
        return False
    
    if not CLAUDE_API_KEY:
        return False
    
    if not CLAUDE_API_KEY.startswith('sk-ant-'):
        return False
    
    return True


def get_model_info(model: str) -> Dict[str, Any]:
    """Obtiene información sobre un modelo."""
    return {
        'id': model,
        'name': AVAILABLE_MODELS.get(model, model),
        'max_tokens': MODEL_TOKEN_LIMITS.get(model, 200000),
        'available': model in AVAILABLE_MODELS,
    }


def list_available_models() -> List[Dict[str, str]]:
    """Lista todos los modelos disponibles."""
    return [
        {'id': model_id, 'name': name}
        for model_id, name in AVAILABLE_MODELS.items()
    ]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Versión
    '__version__',
    
    # Clase principal
    'ContentGenerator',
    
    # Excepciones
    'GenerationError',
    'TokenLimitError',
    'APIKeyError',
    'ContentValidationError',
    'RetryExhaustedError',
    
    # Clases de datos
    'GenerationStage',
    'GenerationResult',
    'APIResponse',
    
    # Re-exports de errores de Anthropic
    'APIError',
    'APIConnectionError',
    'RateLimitError',
    'APIStatusError',
    'AuthenticationError',
    'BadRequestError',
    
    # Funciones principales
    'call_claude_api',
    'generate_content',
    'generate_with_stages',
    
    # Cliente
    'get_client',
    'reset_client',
    
    # Validación y extracción
    'validate_response',
    'extract_html_content',
    'count_tokens',
    'estimate_prompt_tokens',
    
    # Utilidades
    'is_api_available',
    'get_model_info',
    'list_available_models',
    
    # Constantes
    'AVAILABLE_MODELS',
    'MODEL_TOKEN_LIMITS',
    'DEFAULT_MAX_RETRIES',
]
