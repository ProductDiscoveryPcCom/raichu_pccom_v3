# Agente de Refactoring — app.py

Agente especializado en extraer logica del monolito `app.py` (1592 lineas, 29 funciones) a modulos dedicados sin romper el flujo actual.

## Inventario de funciones en app.py

### Config/Init
- `_load_config()` (L72-138) — carga cascada st.secrets → config.settings → os.getenv
- `initialize_app()` (L365-386) — inicializa session state
- `check_configuration()` (L389-429) — valida API key y modulos

### Auth
- `check_auth()` (L1471-1521) — autenticacion con hmac contra st.secrets

### Header/Estado
- `render_app_header()` (L436-499) — selector de modo, boton limpiar
- `_save_mode_results()` (L510-530) — guarda state al cambiar modo
- `_restore_mode_results()` (L533-537) — restaura state
- `clear_session_state()` — limpia todo el session state

### Mode renderers
- `render_new_content_mode()` — modo contenido nuevo
- `render_rewrite_mode()` — modo reescritura
- `render_verify_mode()` — modo verificacion
- `render_assistant_mode()` — modo asistente

### Usage guides
- `_render_usage_guide()`, `_render_rewrite_guide()`, `_render_verify_guide()`, `_render_assistant_guide()`

### Pipeline
- `execute_generation_pipeline()` — delega a core/pipeline.py
- `_check_visual_elements_presence()`, `_check_ai_phrases()`, `_check_engagement_elements()`
- `save_generation_to_state()` — guarda resultados en session state

### Results/Footer
- `render_results()` — renderiza resultados segun modo
- `render_footer()`, `render_debug_panel()`

### Generator cache
- `_get_cached_generator()` — singleton de ContentGenerator

### Fallbacks
- `get_arquetipo()`, `get_arquetipo_names()`, `count_words_in_html()`, `extract_html_content()`, `get_system_prompt_base()` — definiciones fallback si los imports fallan

## Plan de extraccion (por orden de riesgo) — COMPLETADO

### 1. `core/auth.py` — HECHO
Extraido: `check_auth()` — autenticacion con hmac contra st.secrets.

### 2. `core/config.py` — HECHO
Extraido: bridge de API keys (st.secrets → os.environ para downstream). ANTHROPIC_API_KEY NO se copia a os.environ — se inyecta directamente via parametro `api_key` de ContentGenerator.

### 3. `core/session.py` — HECHO
Extraido: `initialize_app()`, `_save_mode_results()`, `_restore_mode_results()`, `clear_session_state()`, `_MODE_RESULT_KEYS`.

### 4. `ui/verify.py` — HECHO
Extraido: `render_verify_mode()` y guia de verificacion.

### 5. `ui/router.py` — HECHO (adicional)
Extraido: routing de modos.

## Constraints

- **Mantener degradacion graceful:** cada import nuevo debe usar try/except con flag `_X_available`
- **Session state intacto:** `_save_mode_results` / `_restore_mode_results` deben ser importables por `render_app_header`
- **Routing en main():** el bloque if/elif de modos debe permanecer en app.py como orquestador central
- **Fallbacks colocados:** las definiciones fallback (get_arquetipo, count_words_in_html, etc.) deben quedar junto a sus try/except de import

## Protocolo de testing

Despues de CADA extraccion:

1. `pytest tests/test_modular.py` — verifica imports basicos
2. `streamlit run app.py` — test manual del modo afectado
3. Verificar debug panel — confirmar que todos los modulos aparecen como disponibles
4. Hacer commit individual por extraccion

## Estado actual

app.py reducido a ~836 lineas. Contiene: imports, routing en `main()`, `render_app_header()`, fallbacks, y delegacion de pipeline. Futuras extracciones podrian reducirlo mas (~400 lineas objetivo original).
