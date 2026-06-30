# Diseño — Raichu Next.js Fase 3 (CSS real + post-proceso de calidad + web research)

**Fecha:** 2026-06-30
**Autor:** Máximo Sánchez (con Claude Code)
**Estado:** Borrador (pendiente de revisión antes de los planes de implementación)
**Proyecto:** `raichu-next` (repo separado, rama `master`). Specs/planes previos:
`docs/superpowers/specs/2026-06-25-raichu-nextjs-migration-design.md` (maestro),
`docs/superpowers/specs/2026-06-29-raichu-nextjs-phase2-inputs-parity-design.md`,
planes Fase 1 / 2A / 2B en `docs/superpowers/plans/`.

---

## 1. Contexto

La **Fase 2** cerró la **paridad de inputs** del modo Nuevo: el formulario completo (37
arquetipos, producto/PDP, enlaces, elementos visuales, headings, briefing guiado, secundarias,
fuentes, brief I/O) construye un `NewContentInput` y lo envía al pipeline de 3 etapas con
streaming SSE. **115 tests verdes, build OK.**

Pero el HTML generado hoy **se entrega sin estilar**: el prompt solo inyecta el placeholder
`<style>/* CSS embebido */</style>` (`src/lib/prompts/new-content.ts`), y el pipeline
(`src/lib/pipeline/run-new-content.ts`) solo hace dos cosas de post-proceso —
`extractHtmlContent` (quita fences) y `validateCmsArticles` (solo **reporta** los 3 `<article>`
que faltan, no repara). No hay CSS del design system, ni normalización de tablas, ni scrub
Unicode, ni quality loop, ni web research.

La **Fase 3** cierra esa brecha: lleva el **output** del modo Nuevo a paridad de calidad con el
Raichu Streamlit, sin cambiar la forma del pipeline (sigue siendo Stage 1/2/3 + corrección
dual + SSE).

### Objetivo

Que el HTML final de `raichu-next` sea **visualmente y estructuralmente equivalente** al del
Raichu actual: estilado con el CSS del design system, con tablas que sobreviven al CSS hostil
del CMS de PcComponentes, sin marcas Unicode ni em-dashes, con los 3 `<article>` garantizados, y
opcionalmente enriquecido con investigación web (opt-in).

### Frontera con la Fase 4 (explícita)

- **En Fase 3:** CSS real del design system + render de elementos visuales, post-proceso de
  calidad (scrub Unicode, fix de tablas + CSS `!important`, validación/refuerzo CMS, quality
  loop, bloque META), y ejecución del **web research opt-in** (Stage 0).
- **En Fase 4 (no aquí):** generación de imágenes (Gemini / gpt-image-1) y **JSON-LD**
  (`utils/jsonld_builder.py`). Se quedan fuera por decisión del spec maestro.

### Fuera de alcance (Fase 3)

- Otros modos (rewrite/verify/opportunities/assistant) y agentes (Repurposer, Audience Tester).
- Reescritura del **tree-shaking de CSS** de `config/design_system.py` (decisión C del spec
  maestro: el CSS se porta **como datos estáticos**, no se reimplementa la selección por
  secciones).
- Port del motor **SERP** completo (`utils/serp_research.py`: SerpAPI + scraping de
  competidores con `ThreadPoolExecutor` + SSRF guard). Ver Decisión 3.

---

## 2. Decisiones de diseño

| # | Decisión | Estado recomendado |
|---|----------|--------------------|
| A | **CSS como dato estático único.** Portar el CSS canónico minificado (`_CANONICAL_CSS` de `config/design_system.py`, fuente de verdad `config/cms_compatible.css`) como un módulo TS `src/lib/design-system/css.ts` e inyectarlo **entero** donde hoy está el stub `/* CSS embebido */`. **Sin tree-shaking** en v1 (decisión C maestro). | Recomendada |
| B | **Render de elementos visuales por plantilla.** Portar, por cada elemento de `VISUAL_ELEMENTS`, su descripción + plantilla HTML de ejemplo + clase, e inyectarlas en el prompt (equivalente a `get_component_instructions`), para que el modelo sepa **cómo** maquetar cada elemento seleccionado. | Recomendada |
| C | **Post-proceso determinista en el pipeline server-side**, en este orden fijo tras Stage 3: `extractHtmlContent` → `sanitizeHtml` → **scrubber** → **fix tablas (estructura)** → **enforce table CSS (`!important`)** → validación/refuerzo CMS → **quality loop**. Réplica del orden de `core/pipeline.py`. | Recomendada |
| D | **Quality loop incluido** (no diferido): score < 70 → una re-revisión "solo texto" vía Claude, aceptada solo si preserva > 80% de palabras y sube el score. Es parte de la paridad de output. | Recomendada (ver Decisión 2) |
| E | **Web research: solo OpenAI web search en v1**, con *graceful skip* si no está disponible. El fallback SERP (SerpAPI+scraping) se difiere. Reusa el cliente OpenAI ya existente. | Recomendada (ver Decisión 3) |
| F | **CMS articles: refuerzo, no fabricación.** Mantener `validateCmsArticles` como gate; si faltan, inyectar el feedback en Stage 2 (como hoy en Python) — **no** fabricar verdict de relleno (lección de la Fase 4 del Python: `max_tokens` correcto + refuerzo en prompt bastan; la fabricación enmascaraba truncación). | Recomendada |

### Decisiones abiertas (a confirmar antes de planificar)

1. **(Decisión A)** ¿CSS **entero** sin tree-shaking, o portar también la selección por
   elementos visuales? — *Recomendación:* entero. El CSS canónico minificado pesa poco, y el
   spec maestro lo excluye explícitamente. Tree-shaking se puede añadir luego si el tamaño del
   prompt molesta.
2. **(Decisión D)** ¿Incluir el **quality loop** (consume 1–2 llamadas LLM extra por generación)
   en Fase 3, o diferirlo a una Fase 3.5? — *Recomendación:* incluirlo; es parte de la calidad
   de output y ya está acotado (solo re-revisa texto, preserva HTML/estilos/enlaces).
3. **(Decisión E)** Web research: ¿**OpenAI web search only** (graceful skip) o portar también
   el motor SERP? — *Recomendación:* OpenAI-only en v1. El motor SERP es ~600 líneas con
   scraping concurrente y guards SSRF; alto coste de port para una ruta de fallback. Si se
   quiere robustez, se aborda como item propio.

---

## 3. Alcance técnico por sub-fase

La Fase 3 se implementa en **tres planes** independientes y verificables por separado (mismo
patrón que Fase 2 = 2A/2B):

### Fase 3A — CSS real del design system + render de elementos visuales

**Qué se porta (desde el Python):**
- `config/design_system.py::_CANONICAL_CSS` (string minificado único, `:root` con
  `--orange-900:#FF6000; --blue-m-900:#170453; …`) → `src/lib/design-system/css.ts`
  (`export const DESIGN_SYSTEM_CSS: string`). Fuente de verdad documentada =
  `config/cms_compatible.css` (690 líneas); en v1 se porta el canónico minificado, no el
  fichero completo con secciones.
- `get_component_instructions()` → `src/lib/design-system/visual-templates.ts`: por cada id de
  `VISUAL_ELEMENTS`, `{ id, description, className, htmlTemplate, variants? }`. Un helper
  `buildVisualInstructions(selectedIds: string[]): string` arma el bloque Markdown del prompt.

**Cómo se cablea:**
- `src/lib/prompts/new-content.ts`: el `<style>/* CSS embebido */</style>` del `CMS_CONTRACT`
  pasa a `<style>${DESIGN_SYSTEM_CSS}</style>`. El modelo recibe la instrucción (ya existente)
  de empezar su HTML con ese `<style>` exacto.
- `formatVisualElementsForPrompt` deja de emitir solo `- toc` y pasa a inyectar las plantillas
  de `buildVisualInstructions(visualElements)` (descripción + ejemplo HTML por elemento
  seleccionado).
- `headingsConfig` (hoy aceptado pero **ignorado**) se inyecta como instrucción de nº de
  H2/H3/H4 en Stage 1/3.

**Resultado:** el HTML sale estilado y con los elementos visuales maquetados con sus clases
reales del design system.

### Fase 3B — Post-proceso de calidad

**Qué se porta:**
- `utils/content_scrubber.py::scrub_html` → `src/lib/postprocess/scrubber.ts`
  (`scrubHtml(html): { html, stats }`): elimina watermarks Unicode (zero-width, etc.),
  normaliza em-dashes `—`→`-`/`,`, quita caracteres de control. Funciones puras.
- `utils/table_fixer.py` → `src/lib/postprocess/tables.ts`:
  - `fixTables(html): { html, stats }` — estructura: envuelve la 1ª fila con `<th>` en
    `<thead>` + resto en `<tbody>`; si ≥4 columnas, envuelve en `<div class="table-responsive">`
    (des-envuelve antes para idempotencia).
  - `enforceTableCss(html): { html, stats }` — override `!important` con marcador idempotente
    `/* PCC-TABLE-FIX */`; 3 overrides **gateados por tipo** detectado
    (`article table:not(.comparison-table)` genérica, `.comparison-table`, `article .lt` light
    table); insertados antes del último `</style>` (o crea `<style>` tras el comentario
    `<!-- META -->` si existe). Valores hex/px literales (sin `var()`), header `#170453`.
- `sanitizeHtml` — ya existe parcialmente en `src/lib/postprocess/html.ts`; verificar paridad
  con `utils/html_utils.py::sanitize_html` (preserva `<style>`, quita script/iframe/`on*`,
  neutraliza `javascript:`/`data:` schemes).
- (Decisión D) `utils/quality_scorer.py::score_content` → `src/lib/postprocess/quality.ts`
  (`scoreContent(html, target): number`); el **quality loop** vive en el pipeline: si
  `score < 70`, una re-revisión Claude "solo texto" (no toca HTML/estilos/enlaces/headings),
  re-score, se acepta solo si `wordPreservation > 0.80` Y el score sube; re-scrub del aceptado.

**Cómo se cablea (`run-new-content.ts`, tras Stage 3):**
```
extractHtmlContent → sanitizeHtml → scrubHtml → fixTables → enforceTableCss
  → validateCmsArticles (gate; si faltan → ya se reforzó en Stage 2) → qualityLoop
```
Cada paso aporta stats al `done` SSE (telemetría, equivalente a `_post_gen_checks`).

**CSS integrity (`utils/css_integrity.py`):** se porta como **test/guard de CI**
(`src/lib/design-system/css-integrity.test.ts`), no como ruta de runtime — en el Python tampoco
tiene caller de producción. Verifica que las variables/selectores críticos y los headers de
tabla `#170453 !important` están presentes en el CSS portado.

### Fase 3C — Web research opt-in (Stage 0)

**Qué se porta:**
- `utils/web_research.py` (cadena) → `src/lib/research/web-research.ts`:
  - `researchEnriched(keyword): Promise<WebResearchResult>` — `{ success, summary, sources[],
    provider }`. v1: solo rama **OpenAI web search** (`client.responses.create` con tool
    `web_search_preview`/`web_search`, probando ambos por compat de versión del SDK); si no hay
    cliente OpenAI o falla → `success:false` (graceful, sin enriquecer). Fallback SERP diferido
    (Decisión 3).
  - `toPromptContext(result): string` — bloque `## INVESTIGACIÓN WEB ACTUALIZADA`; **las fuentes
    son contexto factual, NO se inyectan como enlaces externos** en el HTML (igual que Python).

**Cómo se cablea:**
- `NewContentInput` gana `webResearch?: boolean` (el form ya tiene el checkbox; hoy no viaja al
  pipeline). El builder `build-input.ts` y la route lo pasan.
- `run-new-content.ts`, **Stage 0** (antes de Stage 1, solo si `input.webResearch`): emite un
  evento SSE `stage` "Investigando…", llama `researchEnriched`, y concatena `toPromptContext` al
  `guidingContext` que recibe `buildStage1Prompt`. Errores → warning + continúa sin enriquecer.
- Coste: consume crédito OpenAI por generación (opt-in), requiere acceso a la tool en la cuenta.

---

## 4. Contratos / interfaces nuevas (resumen)

```ts
// src/lib/design-system/css.ts
export const DESIGN_SYSTEM_CSS: string

// src/lib/design-system/visual-templates.ts
export interface VisualTemplate { id: string; description: string; className: string; htmlTemplate: string; variants?: string[] }
export const VISUAL_TEMPLATES: Record<string, VisualTemplate>
export function buildVisualInstructions(selectedIds: string[]): string

// src/lib/postprocess/scrubber.ts
export function scrubHtml(html: string): { html: string; stats: ScrubStats }
// src/lib/postprocess/tables.ts
export function fixTables(html: string): { html: string; stats: TableStructStats }
export function enforceTableCss(html: string): { html: string; stats: TableCssStats }
// src/lib/postprocess/quality.ts
export function scoreContent(html: string, targetLength: number): number

// src/lib/research/web-research.ts
export interface WebResearchResult { success: boolean; summary: string; sources: string[]; provider: 'openai_web' | 'none' }
export function researchEnriched(keyword: string, deps: { openai: OpenAiLike | null; model: string }): Promise<WebResearchResult>
export function toPromptContext(result: WebResearchResult): string
```

`NewContentInput` añade `webResearch?: boolean`. `PipelineEvent.done` añade un `postProcess`
opcional con las stats agregadas (scrub/tables/quality/cms) para telemetría en la UI.

---

## 5. Riesgos y mitigaciones

- **Fidelidad del CSS portado.** El canónico minificado debe coincidir con producción. Mitiga:
  test de integridad (3C-port de `css_integrity`) + checklist de variables/selectores críticos.
- **Tablas en el CMS real.** El override `!important` depende del invariante de 3 `<article>` y
  del prefijo `article`. Mitiga: tests de los 3 tipos de tabla (genérica/comparison/light) con
  un único marcador `/* PCC-TABLE-FIX */`; verificación e2e manual en el CMS antes de cerrar.
- **Quality loop = coste + latencia.** Mitiga: solo se dispara con score < 70; acotado a una
  pasada; preserva HTML. Si molesta, Decisión D lo difiere.
- **Web search tool no disponible en la cuenta.** Mitiga: graceful skip (success:false), la
  generación continúa sin enriquecer; es opt-in.
- **OneDrive / caché tsc.** (Heredado de Fase 2) si `Read` da copia stale usar `git show`; si
  `tsc` falla por caché borrar `*.tsbuildinfo` fuera de `node_modules`.

---

## 6. Criterios de aceptación (Fase 3 completa)

1. El HTML final incluye el `<style>` del design system (no el placeholder) y los elementos
   visuales seleccionados salen con sus clases reales.
2. Post-proceso determinista aplicado en orden: sin watermarks/em-dashes; tablas con
   `<thead>`/`<tbody>` + `table-responsive` cuando aplica; un único `/* PCC-TABLE-FIX */` con los
   overrides de los tipos presentes; los 3 `<article>` presentes (gate).
3. Quality loop operativo (o diferido por Decisión D) sin romper HTML/estilos.
4. Web research opt-in: con `webResearch:true` y OpenAI disponible, el `guidingContext` se
   enriquece y las fuentes NO aparecen como enlaces externos; sin disponibilidad, *graceful*.
5. Suite verde (`npm test`), `tsc --noEmit` limpio, `npm run build` OK.
6. Verificación e2e manual en el CMS de producción de un artículo con tabla (paridad visual).

---

## 7. Plan de implementación

Tres planes TDD, en `docs/superpowers/plans/`:
- **3A** — `…-phase3a-design-system-css.md` (CSS + render visual + headings). Sin nuevas
  llamadas LLM; máxima ganancia de fidelidad.
- **3B** — `…-phase3b-postprocess-quality.md` (scrubber + tablas + sanitize paridad + CMS gate +
  quality loop).
- **3C** — `…-phase3c-web-research.md` (Stage 0 OpenAI web search opt-in).

Recomendación de orden: **3A → 3B → 3C** (cada una mergeable por separado; 3A da el salto visual
mayor, 3C es la más aislada y opt-in).
