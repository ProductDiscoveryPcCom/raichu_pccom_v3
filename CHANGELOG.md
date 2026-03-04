# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/),
y este proyecto adhiere a [Semantic Versioning](https://semver.org/lang/es/).

## [1.2.0] - 2026-02-10

### 🐛 Corregido
- **app.py:** Import de `count_words_in_html` separado de `extract_html_content` (html_utils no exportaba `extract_html_content`, arrastrando ambas funciones al fallback simplificado)
- **app.py:** Modo rewrite stages 1, 2 y 3 ahora pasan `config` dict correctamente a las funciones de `prompts/rewrite.py` (antes pasaban kwargs sueltos que causaban TypeError en runtime)
- **app.py:** `rewrite_config` se construye una sola vez antes de las 3 etapas para garantizar consistencia y scope
- **utils/html_utils.py:** Añadida función `extract_html_content()` que faltaba (limpia marcadores markdown de respuestas de Claude)
- **prompts/new_content.py:** Font-family corregido de `'Inter'` a `'Open Sans'` en `CSS_INLINE_MINIFIED` para coincidir con el design system real de PcComponentes
- **prompts/new_content.py:** Callout-bf con padding reducido, sin espacio extra abajo
- **prompts/new_content.py:** Responsive en callouts para móvil
- **prompts/new_content.py:** Solo emojis permitidos en contenido: ⚡ 💡 ✅
- **config/brand.py:** Font-family corregido de `'Inter'` a `'Open Sans'` en `CSS_CMS_COMPATIBLE` y `CSS_FALLBACK`

### ✨ Añadido
- **prompts/new_content.py:** Parámetro `pdp_json_data` en `build_new_content_prompt_stage1()` para fusión de datos n8n + JSON subido
- **prompts/new_content.py:** Procesamiento de `product_data` en enlaces PDP, soporte `alternative_product.json_data`, implementación de `visual_elements`
- **prompts/new_content.py:** Variable CSS `--space-xl:32px`, enlaces visibles en fondos oscuros (verdict-box, callout-bf)
- **prompts/new_content.py:** Tablas con `table-layout:fixed`, mayor espaciado entre headings y cajas
- **prompts/rewrite.py:** Formateo de productos alternativos con JSON y enlaces editoriales con HTML contextual
- **ui/rewrite.py:** Productos Alternativos como paso opcional con N productos + JSON cada uno, selector tipo Post/PLP
- **ui/inputs.py:** Opción de pegar JSON además de subir archivo, descripción del arquetipo bajo selector, soporte JSON en producto alternativo y producto principal
- **config/arquetipos.py:** Preguntas guía revisadas con preguntas universales (público, intención, productos PcComponentes)
- **config/brand.py:** Sección `INSTRUCCIONES_ORIENTACION_POSITIVA`, clases CSS `.card.destacado`, `.product-module`, `.price-tag`

### 🔧 Modificado
- **app.py:** Nombres de funciones y parámetros alineados con módulos de prompts, validaciones de entrada en pipeline
- **ui/rewrite.py:** Paso 2 ahora es "HTML a Reescribir" con instrucciones detalladas de reescritura
- **config/brand.py:** Tono rebalanceado: orientado a soluciones, no disuasorio
- Sincronización de versiones en todos los módulos
- CHANGELOG.md reescrito como versión única 1.2.0

## [1.1.0] - 2024-11-XX

### ✨ Añadido
- Refactorización completa a arquitectura modular (config, core, prompts, ui, utils)
- Modo reescritura con análisis competitivo automático
- Sistema de validación CMS completo
- 18 arquetipos predefinidos con campos específicos
- Exportación ZIP de todas las etapas
- Panel de debug para desarrollo
- Configuración centralizada con múltiples fuentes (secrets, env, defaults)
- `ContentGenerator` con reintentos y backoff exponencial

### 🐛 Corregido
- Validación de estructura HTML CMS-compatible
- Uso correcto de `<span>` en kicker (no `<div>`)
- Estructura de 3 articles obligatoria
- Título principal con H2 (no H1)

### 🗑️ Eliminado
- Código monolítico de `app_backup.py` (3000+ líneas)
- CSS duplicado (4 instancias → 1)
- Prompts embebidos en código Python

## [1.0.0] - 2025-11-XX

### ✨ Añadido
- Versión inicial del Content Generator
- Flujo de 3 etapas (borrador, análisis, final)
- Arquetipos básicos
- Integración con Claude API
