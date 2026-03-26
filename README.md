# PcComponentes Content Generator

**Version 5.1.0** | Generador de contenido SEO optimizado con IA

Aplicacion Streamlit que genera contenido de alta calidad para PcComponentes usando Claude AI, con analisis competitivo, validacion CMS y flujo de 3 etapas.

---

## Caracteristicas

- **34 arquetipos SEO**: Reviews, guias, comparativas, noticias, rankings, etc.
- **Flujo de 3 etapas**: Borrador -> Analisis Critico (Claude + OpenAI dual) -> Version Final
- **Validacion CMS**: Estructura HTML compatible (3 articles obligatorios)
- **5 modos**: Nuevo, Reescritura competitiva, Verificacion GSC, Oportunidades, Asistente
- **Tono de marca**: Anti-IA, personalidad PcComponentes, 6 pilares de tono
- **Integraciones**: Google Search Console, SEMrush, SerpAPI, Google Gemini (imagenes)

---

## Requisitos

- **Python 3.11+**
- **API Key de Anthropic** (Claude)
- **(Opcional)** OpenAI API key (correccion dual Stage 2), Google Gemini, SEMrush, SerpAPI, Google Search Console

---

## Instalacion

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt        # produccion
pip install -r requirements-dev.txt    # desarrollo (incluye pytest, black, flake8)
```

### Configuracion

API keys via `.env` o `.streamlit/secrets.toml` (para Streamlit Cloud):

```bash
# .env
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
```

Cascada de prioridad: `st.secrets` -> `config.settings` -> `os.getenv()`

---

## Uso

```bash
streamlit run app.py          # Ejecutar la app
pytest tests/                 # Ejecutar tests
```

---

## Estructura del Proyecto

```
app.py                  # Entrypoint: routing, header, fallbacks (~836 lineas)
VERSION                 # Source of truth para version ("5.1.0")
version.py              # Lee VERSION, exporta __version__

config/
  settings.py           # Variables de configuracion (API keys, modelos, timeouts)
  arquetipos.py         # 34 arquetipos SEO (ARQ-1 a ARQ-34)
  design_system.py      # CSS components y sistema de diseno visual

core/
  config.py             # Bridge: copia params a os.environ para downstream
  generator.py          # ContentGenerator class, GenerationResult, retry logic
  pipeline.py           # Orquestacion del pipeline de 3 etapas
  auth.py               # Autenticacion (hmac contra st.secrets)
  session.py            # Gestion de session state (init, save/restore modos)
  scraper.py            # Scraping de competidores y productos
  openai_client.py      # Wrapper OpenAI para correccion dual (Stage 2)
  semrush.py            # Integracion API SEMrush
  cms_publisher.py      # Publicacion a CMS
  n8n_integration.py    # Webhooks n8n para datos de producto

prompts/
  new_content.py        # Prompts para contenido nuevo (Stage 1/2/3)
  rewrite.py            # Prompts para reescritura competitiva (Stage 1/2/3)
  brand_tone.py         # Tono de marca, instrucciones anti-IA, system prompts base
  templates.py          # Templates HTML/CSS

ui/
  inputs.py             # Formularios de entrada y validacion
  rewrite.py            # UI modo reescritura
  results.py            # Visualizacion de resultados
  opportunities.py      # Modo oportunidades GSC/SEMrush
  assistant.py          # Chat asistente con comandos internos
  verify.py             # Modo verificacion de canibalizacion
  router.py             # Routing de modos
  sidebar.py            # Barra lateral
  gsc_section.py        # Seccion GSC en UI

utils/                  # 19 modulos de utilidades
  html_utils.py         # Conteo de palabras, validacion HTML, deteccion frases IA
  gsc_utils.py          # Google Search Console (cache, canibalizacion, CSV fallback)
  gsc_api.py            # API GSC directa
  serp_research.py      # Investigacion SERP (DuckDuckGo/SerpAPI)
  image_gen.py          # Generacion de imagenes con Gemini
  + 14 modulos mas (translation, meta_generator, quality_scorer, etc.)

tests/                  # 13 archivos de test, 462 tests
  conftest.py           # Fixtures de pytest
  test_modular.py       # Tests basicos de imports y arquetipos
  + 12 archivos de test adicionales
```

---

## Arquitectura

### Pipeline de 3 etapas

```
Stage 1 (Borrador)  -->  Stage 2 (Analisis dual)  -->  Stage 3 (Final)
   Claude genera           Claude + OpenAI             Claude incorpora
   HTML draft              validan en paralelo         feedback y genera
                                                       version final
```

### Stack

- **Frontend**: Streamlit 1.28+
- **IA**: Claude Sonnet 4 (Anthropic), GPT-4.1 (OpenAI, correccion dual), Gemini 2.5 Flash (imagenes)
- **Scraping/Research**: BeautifulSoup4 + lxml, SerpAPI, SEMrush API, Google Search Console API
- **Deploy**: Streamlit Cloud
- **CI**: GitHub Actions (pytest, black, flake8)

---

## Desarrollo

```bash
pytest tests/             # Tests
black . && isort .        # Formateo
flake8 .                  # Linting
```

Pre-commit hooks configurados en `.pre-commit-config.yaml`.

---

## Documentacion

- [CLAUDE.md](CLAUDE.md) — Arquitectura y convenciones del proyecto
- [CHANGELOG.md](CHANGELOG.md) — Historial de versiones
- [docs/audit-2026-03.md](docs/audit-2026-03.md) — Auditoria de salud del proyecto
- [docs/ux-audit-2026-03.md](docs/ux-audit-2026-03.md) — Auditoria UX del formulario
- [docs/output-quality-audit-2026-03.md](docs/output-quality-audit-2026-03.md) — Auditoria de calidad del output

---

**Equipo Product Discovery & Content — PcComponentes**
