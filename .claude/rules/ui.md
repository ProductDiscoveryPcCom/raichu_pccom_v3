# Convenciones UI (Streamlit)

Aplica a: `app.py` y `ui/*.py`

## Session state — keys core

Inicializadas en `initialize_app()` (app.py L365-386):

| Key | Tipo | Descripcion |
|-----|------|-------------|
| `initialized` | bool | Flag de primera inicializacion |
| `mode` | str | Modo activo: `new`, `rewrite`, `verify`, `opportunities`, `assistant` |
| `generation_in_progress` | bool | True durante generacion |
| `current_stage` | int | 0=borrador, 1=analisis, 2=final |
| `draft_html` | str/None | HTML del borrador (Stage 1) |
| `analysis_json` | dict/None | JSON de analisis (Stage 2) |
| `final_html` | str/None | HTML final (Stage 3) |
| `rewrite_analysis` | str/None | Analisis de reescritura |
| `content_history` | list | Historial de generaciones |
| `last_config` | dict/None | Ultima configuracion usada |
| `timestamp` | str | Timestamp de la sesion |

## Session state — keys dinamicas

| Key | Descripcion |
|-----|-------------|
| `_saved_results_{mode}` | Snapshot de resultados al cambiar de modo |
| `_cached_generator` | Singleton de ContentGenerator |
| `_cached_generator_key` | Key para invalidar cache del generator |
| `translated_html_{lang}` | Traducciones por idioma |
| `_has_generated_{mode}` | Oculta guia de uso tras primera generacion |
| `_confirm_clear` | Dialog de confirmacion de limpieza |

## Aislamiento de modos

Al cambiar de modo (app.py L485-498):

1. `_save_mode_results(previous_mode)` — guarda las keys de `_MODE_RESULT_KEYS` en `_saved_results_{mode}`
2. `_restore_mode_results(new_mode)` — restaura resultados previos del modo entrante

**`_MODE_RESULT_KEYS`** (app.py L503-507):
```python
['draft_html', 'analysis_json', 'final_html',
 'rewrite_analysis', 'content_history', 'generation_metadata',
 'last_config', 'timestamp']
```

Las keys `translated_html_*` se guardan/restauran por separado (L518-530).

## Como anadir un modo nuevo

1. Anadir el string del modo a `options` en `st.radio()` (app.py L454)
2. Anadir nombre display al dict `format_func` (app.py L455-461)
3. Crear funcion `render_X_mode()` (en app.py o en `ui/x_mode.py`)
4. Anadir branch `elif mode == 'x':` en el routing de `main()` (app.py L1562-1577)
5. Si el modo genera contenido, anadirlo al check `if mode in [...]` (app.py L1581)

## Patron de validacion

Las funciones `validate_*` en `ui/inputs.py` validan entrada antes de lanzar el pipeline:
- `validate_keyword()` — 2-100 caracteres
- `validate_url()` — formato valido, opcionalmente requiere pccomponentes.com
- `validate_length()` — 500-5000 palabras
- `validate_arquetipo()` — codigo existe en ARQUETIPOS
- `validate_html_content()` — para modo rewrite
- `validate_links_list()` — URLs separadas por espacio/coma
- `validate_competitor_urls()` — multiples URLs

## Imports con degradacion graceful

Todos los modulos UI se importan en app.py con try/except y flag `_X_available`:

```python
try:
    from ui.inputs import render_content_inputs
    _inputs_available = True
except ImportError:
    _inputs_available = False
    render_content_inputs = None
```

Al usar: `if not _inputs_available or render_content_inputs is None: st.error(...); return`

No eliminar este patron — permite que la app funcione parcialmente si un modulo falla.
