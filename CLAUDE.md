# Raichu v5.1.0 — PcComponentes SEO Content Generator

Aplicacion Streamlit para generacion automatizada de contenido SEO para PcComponentes.

## Stack

- **Runtime:** Python 3.11, Streamlit 1.28+
- **IA:** Anthropic API (`claude-sonnet-4-20250514`), OpenAI (`gpt-4.1-2025-04-14` para correccion dual en Stage 2), Google Gemini 2.5 Flash (generacion de imagenes)
- **Scraping/Research:** BeautifulSoup4 + lxml, SerpAPI, SEMrush API, Google Search Console API
- **Deploy:** Streamlit Cloud

## Estructura del proyecto

```
app.py                  # Entrypoint: routing de modos, auth, config, pipeline delegation (1592 lineas)
VERSION                 # Source of truth para version ("5.1.0")
version.py              # Lee VERSION, exporta __version__

config/
  settings.py           # Variables de configuracion (API keys, modelos, timeouts)
  arquetipos.py          # 34 arquetipos SEO (ARQ-1 a ARQ-34) con tone, structure, lengths
  design_system.py       # CSS components y sistema de diseno visual

core/
  generator.py           # ContentGenerator class, GenerationResult, retry logic
  pipeline.py            # Orquestacion del pipeline de 3 etapas (1420 lineas)
  scraper.py             # Scraping de competidores y productos
  openai_client.py       # Wrapper OpenAI para correccion dual (Stage 2)
  semrush.py             # Integracion API SEMrush (keyword research)
  cms_publisher.py       # Publicacion a CMS
  n8n_integration.py     # Webhooks n8n para datos de producto

prompts/
  new_content.py         # Prompts para contenido nuevo (Stage 1/2/3, 1885 lineas)
  rewrite.py             # Prompts para reescritura competitiva (Stage 1/2/3, 1374 lineas)
  brand_tone.py          # Tono de marca, instrucciones anti-IA, system prompts base
  templates.py           # Templates HTML/CSS

ui/
  inputs.py              # Formularios de entrada y validacion (2855 lineas)
  rewrite.py             # UI modo reescritura (2562 lineas)
  results.py             # Visualizacion de resultados (2236 lineas)
  opportunities.py       # Modo oportunidades GSC/SEMrush
  assistant.py           # Chat asistente con comandos internos
  sidebar.py             # Barra lateral
  gsc_section.py         # Seccion GSC en UI

utils/
  html_utils.py          # Conteo de palabras, validacion HTML, deteccion frases IA
  gsc_utils.py           # Google Search Console (cache, canibalizacion, CSV fallback)
  gsc_api.py             # API GSC directa
  serp_research.py       # Investigacion SERP (DuckDuckGo/SerpAPI)
  image_gen.py           # Generacion de imagenes con Gemini
  product_json_utils.py  # Parse/validacion JSON de productos
  translation.py         # Traduccion de contenido
  + 10 modulos mas de utilidades especializadas

tests/
  test_modular.py        # Tests basicos de imports y arquetipos
  + 6 archivos de test adicionales
```

## Cascada de API keys

Prioridad de carga (app.py L72-214):
1. `st.secrets` (Streamlit Cloud) — keys: `claude_key`, `openai_key`, `gemini_key`, `semrush.api_key`, `serpapi_key`
2. `config.settings` — importa `CLAUDE_API_KEY`, `CLAUDE_MODEL`, etc.
3. `os.getenv()` — fallback: `ANTHROPIC_API_KEY`, `CLAUDE_API_KEY`, etc.

**Bridge pattern:** app.py copia valores de `st.secrets` a `os.environ` (L150-214) para que modulos downstream los lean via `os.getenv()`.

## Pipeline de 3 etapas

Orquestado en `core/pipeline.py`:

1. **Stage 1 — Borrador:** Claude genera HTML draft con CSS embebido
2. **Stage 2 — Analisis:** Claude analiza + OpenAI valida (correccion dual, opcional si `openai_key` esta en secrets)
3. **Stage 3 — Final:** Claude genera version final incorporando feedback de ambos analisis

Funciones de prompts por etapa: ver `.claude/rules/prompts.md`

## 5 modos de operacion

| Modo | Key | Descripcion |
|------|-----|-------------|
| Nuevo | `new` | Genera contenido SEO desde cero |
| Reescritura | `rewrite` | Reescribe contenido existente (single/merge/disambiguate) |
| Verificar | `verify` | Comprueba canibalizacion de keywords en GSC |
| Oportunidades | `opportunities` | Busca oportunidades SEO en GSC/SEMrush |
| Asistente | `assistant` | Chat libre con comandos internos ([GSC_CHECK], [SERP_RESEARCH], etc.) |

## Comandos

```bash
streamlit run app.py          # Ejecutar la app
pytest tests/                 # Ejecutar tests
pip install -r requirements-dev.txt  # Instalar dependencias (incluye dev)
```

## Version

**Source of truth:** archivo `VERSION` en la raiz (leido por `version.py`). Actualmente "5.1.0".

Los `__version__` en `config/settings.py` y `config/arquetipos.py` estan desactualizados — ignorarlos.

## NO TOCAR

- **`.streamlit/secrets.toml`** — API keys reales, excluido de git
- **Patron de degradacion graceful** — 12 flags `_X_available` en app.py (L227-326). Cada modulo se importa con try/except y flag booleano. Si un modulo falla, la app sigue funcionando sin esa feature. No eliminar estos bloques.
- **Estructura CMS 3-article** — El HTML generado DEBE contener 3 `<article>` con clases: `contentGenerator__main`, `contentGenerator__faqs`, `contentGenerator__verdict`. Esta estructura es requerida por el CMS de PcComponentes.
- **Aislamiento de session state por modo** — `_save_mode_results()` / `_restore_mode_results()` (app.py L510-537). Al cambiar de modo se guardan/restauran los resultados para no perder trabajo.
