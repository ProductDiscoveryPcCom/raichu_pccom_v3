# Convenciones de Prompts

Aplica a: `prompts/new_content.py` y `prompts/rewrite.py`

## Regla fundamental

Los prompts son **funciones Python que retornan `str`**. No se usan templates Jinja2, YAML ni ficheros externos. PyYAML y Jinja2 en requirements.txt son dependencias legacy sin uso.

## Funciones por etapa

### Contenido nuevo (`prompts/new_content.py`)

| Etapa | Funcion | Parametros clave |
|-------|---------|-----------------|
| Stage 1 (Borrador) | `build_new_content_prompt_stage1()` | keyword, arquetipo, target_length, pdp_data, pdp_json_data, links_data, secondary_keywords, additional_instructions, campos_especificos, visual_elements, headings_config, alternative_product, products, guiding_context |
| Stage 2 (Analisis) | `build_new_content_correction_prompt_stage2()` | draft_content, target_length, keyword, links_to_verify, alternative_product, products, visual_elements |
| Stage 3 (Final) | `build_final_prompt_stage3()` | draft_content, analysis_feedback, keyword, target_length, links_data, alternative_product, products, visual_elements |

### Reescritura (`prompts/rewrite.py`)

| Etapa | Funcion | Parametros clave |
|-------|---------|-----------------|
| Stage 1 | `build_rewrite_prompt_stage1()` | keyword, competitor_analysis, config (dict) |
| Stage 2 | `build_rewrite_correction_prompt_stage2()` | draft_content, target_length, keyword, competitor_analysis, config |
| Stage 3 | `build_rewrite_final_prompt_stage3()` | draft_content, corrections_json, config |

**Nota:** Rewrite usa un unico `config` dict en lugar de parametros individuales.

### Aliases legacy (NO usar en codigo nuevo)

- `build_correction_prompt_stage2` → alias de `build_new_content_correction_prompt_stage2`
- `build_final_generation_prompt_stage3` → alias de `build_final_prompt_stage3`

## Estructura HTML obligatoria (CMS)

Todo contenido generado DEBE contener 3 `<article>`:

```html
<article class="contentGenerator__main">
  <!-- Contenido principal: kicker + H2 + TOC + secciones -->
</article>
<article class="contentGenerator__faqs">
  <!-- Preguntas frecuentes -->
</article>
<article class="contentGenerator__verdict">
  <!-- Veredicto/conclusion -->
</article>
```

## Correccion dual (Stage 2)

1. Claude analiza el draft (via `ContentGenerator.generate()`)
2. Un segundo modelo valida independientemente y `merge_dual_analyses()` fusiona ambos
3. Stage 3 recibe feedback combinado

**Eleccion del analista secundario** (en `core/pipeline.py`, Stage 2):
- **OpenAI** (via `openai_client.generate_dual_analysis()`) si `_openai_client_available and OPENAI_API_KEY` — preferido por ser cross-vendor (mayor independencia).
- **Fallback Claude Haiku** (via `_haiku_secondary_analysis()`, modelo `core.config.DUAL_FALLBACK_MODEL`) cuando NO hay key/SDK de OpenAI, o cuando OpenAI falla en runtime (rate limit / error → backstop secuencial). Garantiza "siempre dos analisis".
- Independencia menor con Haiku (mismo proveedor que el principal) — es red de seguridad, no sustituto equivalente. Usa el mismo system critico que OpenAI (`_DUAL_FALLBACK_SYSTEM`), no el tono de marca.
- `merge_dual_analyses(..., secondary_provider=...)` etiqueta la telemetria con el modelo real usado (`'openai'` / `'haiku'`).

## Como anadir un arquetipo nuevo

1. Agregar entrada al dict `ARQUETIPOS` en `config/arquetipos.py` con keys:
   - `code` (ej: "ARQ-35"), `name`, `description`, `tone`
   - `structure` (lista de secciones H2/H3)
   - `default_length`, `min_length`, `max_length`
   - `preguntas_guia` (lista de preguntas orientadoras)
   - `visual_elements` (ej: ["toc", "table", "callout", "verdict"])
2. Si el arquetipo se beneficia de mini-stories de reviews, anadir su codigo al set `ARQUETIPOS_CON_MINI_STORIES` en `prompts/new_content.py` L57.

## Dependencias internas

Ambos modulos de prompts importan de `prompts/brand_tone.py`:
- `get_tone_instructions()` — instrucciones de tono de marca
- `get_system_prompt_base()` — system prompt base para Claude
- `INSTRUCCIONES_ANTI_IA` — reglas para evitar frases tipicas de IA
- `ANTI_IA_CHECKLIST_STAGE2` — checklist de validacion anti-IA
- `REGLAS_CRITICAS_COMUNES` — reglas compartidas entre new y rewrite

Helpers internos en `new_content.py` que `rewrite.py` tambien importa:
- `_format_products_for_prompt()`, `_format_visual_elements_instructions()`, `_get_css_for_prompt()`, `_build_stage3_visual_instructions()`, `_build_stage3_checklist()`
