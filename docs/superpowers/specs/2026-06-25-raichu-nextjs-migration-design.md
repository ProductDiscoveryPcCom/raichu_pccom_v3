# Diseño — Migración de Raichu (modo Nuevo) a Next.js

**Fecha:** 2026-06-25
**Autor:** Máximo Sánchez (con Claude Code)
**Estado:** Aprobado (pendiente de revisión final del spec antes de plan de implementación)

---

## 1. Contexto y objetivo

Producto (PD&C) quiere centralizar las herramientas del equipo en una plataforma única.
Como piloto de ese movimiento, se reescribe **Raichu** (hoy app Streamlit/Python, ~38k líneas)
a **Next.js/TypeScript 100%**, sin Python en el resultado final.

Esta migración:

- **No toca el proyecto Python actual.** Se monta en un **proyecto nuevo y separado** (carpeta
  hermana, repositorio git independiente) que sigue desarrollándose en paralelo mientras el
  Raichu Python permanece operativo.
- **Se entrega para handoff:** repo autocontenido con README, listo para que la persona
  designada lo suba al entorno privado de Labs.

### Alcance de la v1

- **Solo el modo "Nuevo"** (generación de contenido SEO desde cero). Los otros modos
  (`rewrite`, `verify`, `opportunities`, `assistant`) y los agentes (Repurposer, Audience
  Tester) quedan fuera de esta v1.
- **Paridad funcional completa** del modo Nuevo: brief I/O, 37 arquetipos, keywords
  secundarias, elementos visuales, headings, datos PDP/producto, corrección dual, post-proceso
  y estructura CMS de 3 `<article>`.

### Fuera de alcance (v1)

- Gestión de acceso centralizado / SSO / permisos (capa portal, se aborda aparte).
- Migración de los demás modos y agentes.
- Reescritura del tree-shaking de CSS (`design_system.py`) — se porta el CSS como datos
  estáticos.

---

## 2. Decisiones de arquitectura

| # | Decisión | Estado |
|---|----------|--------|
| A | Generación vía **Route Handlers + streaming SSE**, backend sin sesión ni BD | Aprobada |
| B | UI con **Tailwind + shadcn/ui** | Aprobada |
| C | CSS del design system **portado como datos estáticos** en v1 | Aprobada |
| D | Despliegue como **servidor Node de larga duración** (Next.js `output: standalone`, contenedor) — NO serverless | Aprobada (confirmar infra con Labs) |
| E | Stack: **Next.js App Router + TypeScript + React**, sin BD en v1 | Aprobada |
| F | Secrets solo server-side vía `.env.local` (cascada Streamlit → env vars) | Aprobada |

### Por qué streaming + servidor Node (A/D)

El pipeline tarda minutos y a veces usa streaming del SDK Anthropic (cuando
`max_tokens > 21.333`). La UI debe mostrar progreso por etapa, como hoy en Streamlit. Un
Route Handler que emite eventos SSE (borrador listo → análisis listo → final listo) replica
esa UX sin montar cola/almacén. Requiere correr como servidor Node persistente (no función
serverless con timeout). **Restricción de despliegue a confirmar con quien gestione el
entorno privado de Labs.**

---

## 3. Arquitectura del sistema

```
┌─────────────────────────────────────────────┐
│  Cliente (React, App Router)                  │
│  - Formulario modo Nuevo (Zustand+localStorage)│
│  - Vista de resultados (HTML, análisis, meta) │
│  - Brief I/O (descarga/subida Markdown)       │
└───────────────┬───────────────────────────────┘
                │  POST /api/generate  (stream SSE)
                ▼
┌─────────────────────────────────────────────┐
│  Servidor Next.js (Node)                      │
│  /app/api/generate/route.ts  → orquesta       │
│  /lib/pipeline/*   (Stage 0..3 + post-proceso)│
│  /lib/prompts/*    (prompts portados 1:1)     │
│  /lib/clients/*    (anthropic, openai, gemini,│
│                     serp)                     │
│  /lib/postprocess/*(scrub, tables, css, score,│
│                     meta, cms-validate)       │
│  /lib/config/*     (arquetipos, brand-tone,   │
│                     css-data, visual-registry)│
└───────────────┬───────────────────────────────┘
                │  SDKs / REST
                ▼
   Anthropic · OpenAI · Gemini · SerpAPI
```

### Flujo de generación (modo Nuevo)

1. **Stage 0 — Web research (opt-in):** si el usuario lo activa, OpenAI Responses API
   (`web_search`) → fallback SERP (SerpAPI/scraping con `cheerio`) → enriquece el contexto.
   Graceful: si falla, se sigue sin enriquecer.
2. **Stage 1 — Borrador:** Claude genera HTML draft con CSS embebido y estructura CMS.
   `max_tokens` dinámico (`computeMaxTokens(targetLength, stage)`).
3. **Stage 2 — Análisis dual:** Claude analiza (JSON) + analista secundario en paralelo
   (OpenAI si hay key; si no o falla, fallback Claude Haiku). `mergeDualAnalyses()` fusiona.
4. **Stage 3 — Final:** Claude reescribe incorporando feedback. Guard de truncación
   (`stop_reason == 'max_tokens'` → reintento acotado).
5. **Post-proceso determinista (sin LLM salvo quality loop/meta):**
   extracción/sanitización → scrub Unicode/em-dashes → fix de tablas → CSS override
   `!important` anti-CMS → quality score (auto-loop si `< 70`) → meta/TL;DR → validación CMS.

Cada paso relevante emite un evento SSE de progreso al cliente.

### Streaming (paridad con el guard del SDK)

Si `max_tokens > 21.333`, el cliente Anthropic usa `messages.stream()` y recupera el mensaje
final (equivalente a `get_final_message()` en Python). Por debajo, `messages.create()`.

### Presupuesto dinámico de tokens (función pura portada)

`computeMaxTokens(targetLength, stage, ceiling)`:
- Stage 2 (análisis): `max(4000, targetLength * 3.0)`, redondeo a 1000, clamp a `hard_cap`.
- Stages 1/3 (HTML): `max(8000, round1000(2500 + targetLength * 4.0 * 1.30))`, clamp.
- `hard_cap = min(ceiling, 32000)`; `ceiling` = `MAX_TOKENS` de entorno o 32000.

---

## 4. Modelo de datos del formulario (paridad)

Inputs del modo Nuevo a reproducir (origen: `ui/inputs.py`, `config/arquetipos.py`,
`utils/brief_io.py`, `utils/product_json_utils.py`):

**Core:** `keyword` (2–100 chars, obligatorio), `target_length` (500–5000, default por
arquetipo), `arquetipo` (ARQ-1..ARQ-37, obligatorio), `additional_instructions`.

**Producto/PDP:** `pdp_url`, `pdp_json` (formato n8n wrapper + legacy plano, vía
`parseProductJson`), producto alternativo (url/nombre/json), bloque unificado `products[]`
(v5.0) con `role`.

**Enlaces:** internos (hasta 10, url+anchor+json opcional), PDP (hasta 10), competidores
(hasta 5, filtra dominio PcC).

**Estructura/contenido:** `visual_elements` (27 componentes; preselección por arquetipo),
`headings_config` ({h2:1–15, h3:0–30, h4:0–20}), `faq_questions` (PAA + custom).

**Investigación:** `web_research` (checkbox), `authoritative_sources`.

**Briefing guiado:** respuestas `guiding_spec_{i}` (específicas del arquetipo) +
`guiding_univ_{i}` (6 universales).

**Secundarias:** `secondary_keywords[]`.

### Arquetipo (estructura del objeto)

`{ code, name, description, tone, keywords[], structure[], guiding_questions[],
default_length, min_length, max_length, visual_elements[], campos_especificos[] }`.
Los 37 se portan como datos estáticos (TS/JSON). *Nota: confirmar el número exacto contra el
código (37 según `config/arquetipos.py`; `CLAUDE.md` dice 34, desactualizado).*

### Brief Markdown (bidireccional)

`buildBriefMarkdown()` / `parseBriefMarkdown()` portados a TS. Formato con marcador
`<!-- raichu-brief:v1 -->`, secciones `## [id] Etiqueta` + `Respuesta:`, tolerante a
ausencia del marcador. Campos: keyword, target_length, secondary_keywords,
additional_instructions, authoritative_sources, `guiding_spec_{i}`, `guiding_univ_{i}`.

### Validaciones

`keyword` 2–100; `target_length` 500–5000; URL válida (≤2000, opcional dominio PcC);
arquetipo existe; ≤5 competidores; ≤10 enlaces/tipo; JSON producto parseable con `product_id`.

---

## 5. Prompts y configuración (porting)

- **Prompts (3 etapas):** `buildNewContentPromptStage1`, `buildCorrectionPromptStage2`
  (salida **JSON estructurado**), `buildFinalPromptStage3`. ~70% texto estático (template
  literals), ~30% lógica condicional simple (merge de datos de producto, formato de visuales,
  instrucciones por arquetipo). Helpers: `formatProductsForPrompt`,
  `formatVisualElementsInstructions`, `getCssForPrompt`, `buildStage3VisualInstructions`,
  `buildStage3Checklist`.
- **Brand tone:** `getSystemPromptBase`, `getToneInstructions(hasProductData)`,
  `INSTRUCCIONES_ANTI_IA`, `ANTI_IA_CHECKLIST_STAGE2`, `REGLAS_CRITICAS_COMUNES`,
  `ARCHETYPE_STAGE1_INSTRUCTIONS` (por arquetipo), `EJEMPLOS_TONO_STAGE3`. Constantes →
  módulos TS.
- **CSS / design system:** CSS canónico portado como **string/JSON estático** (no se
  reimplementa el tree-shaking). Incluye los overrides de tabla `!important` anti-CMS.
- **Registro de elementos visuales:** 27 componentes con `{label, description, help, default,
  icon}` + plantillas HTML → módulo TS.

---

## 6. Integraciones externas (modo Nuevo)

| Servicio | Uso en modo Nuevo | SDK JS | Riesgo |
|----------|-------------------|--------|--------|
| Anthropic | Núcleo (etapas 1/2/3), streaming | `@anthropic-ai/sdk` | Bajo |
| OpenAI | Análisis dual (gpt-4.1); web research | `openai` | Bajo |
| Gemini | Imágenes (primario, 2.5 Flash Image) | `@google/genai` | Medio |
| OpenAI gpt-image-1 | Fallback imágenes (resize → `sharp`) | `openai` | Medio |
| Web research | OpenAI Responses API (`web_search`) opt-in | `openai` | Alto (beta) |
| SERP | Fallback research (SerpAPI + scraping `cheerio`) | REST / `cheerio` | Alto |

**Excluidas del modo Nuevo:** SEMrush, GSC, n8n webhook (pertenecen a otros modos / helpers
de UI). No se portan en v1.

**Auth:** todas las keys solo server-side vía `.env.local`
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`, `SERPAPI_API_KEY`). Nunca expuestas
al cliente.

---

## 7. Estructura del proyecto (propuesta)

```
raichu-next/
  app/
    page.tsx                 # Formulario modo Nuevo
    results/                 # Vista de resultados
    api/
      generate/route.ts      # Orquestación + stream SSE
      images/route.ts        # Generación de imágenes (fase 4)
  components/                # UI (shadcn) form, results, brief I/O
  lib/
    pipeline/                # stage0..3, postprocess orchestration
    prompts/                 # new-content, brand-tone, helpers
    clients/                 # anthropic, openai, gemini, serp
    postprocess/             # scrub, tables, css, quality, meta, cms-validate
    config/                  # arquetipos, brand-tone, css-data, visual-registry
    brief/                   # build/parse brief markdown
    validation/              # validators
    token-budget.ts          # computeMaxTokens (puro)
  store/                     # Zustand (form + generación)
  __tests__/                 # Vitest
  README.md                  # setup, env, dev, deploy contenedor
```

---

## 8. Estructura HTML obligatoria (contrato CMS — invariante)

```html
<article class="contentGenerator__main">...</article>
<article class="contentGenerator__faqs">...</article>
<article class="contentGenerator__verdict">...</article>
```

`validateCmsArticles(html)` verifica las 3 clases + ≥1 `<h2>` en `__main`. Se valida tras
Stage 1 (feedback a Stage 2) y tras Stage 3 (warning visible si falta algo).

---

## 9. Secuenciación de implementación (paridad completa, ordenada)

1. **Esqueleto + vertical slice:** proyecto Next.js, endpoint streaming, formulario mínimo
   (keyword/arquetipo/longitud) → pipeline 3 etapas con corrección dual → HTML CMS válido +
   descarga. Valida toda la arquitectura.
2. **Paridad de inputs:** 37 arquetipos, visuales, headings, productos/PDP, enlaces,
   secundarias, briefing guiado, brief I/O.
3. **Paridad de calidad:** post-proceso completo (scrub, tablas, CSS, quality loop, meta),
   validación CMS, web research opt-in.
4. **Extras:** generación de imágenes, JSON-LD.

---

## 10. Testing y entrega

- **Vitest** sobre lógica pura portada: `token-budget`, prompt builders, brief parser,
  validaciones, post-proceso (scrub, tablas, CSS, cms-validate). No se migran los 462 tests
  Python; se escriben los equivalentes de lo reimplementado.
- (Opcional) Playwright para 1 E2E del flujo completo.
- **README** con: requisitos, variables de entorno, `npm run dev`, build y despliegue como
  contenedor Node (`output: standalone`).

---

## 11. Riesgos y cuestiones abiertas

- **Infra del entorno privado (D):** confirmar que admite servidor Node persistente (no solo
  serverless). Bloqueante de despliegue, no de desarrollo.
- **Web research (Responses API beta):** schema puede cambiar; es opt-in y tiene fallback
  SERP, así que no bloquea el núcleo.
- **Scraping SERP:** `cheerio` vs `lxml`/BeautifulSoup; selectores a adaptar. Secundario.
- **Imágenes Gemini:** SDK JS difiere del Python; validar tipos/tamaños.
- **Recuento de arquetipos:** confirmar 37 vs 34 contra el código antes de portar los datos.
- **Paridad "completa" es amplia:** aun acotada a un modo, es un build sustancial; la
  secuenciación de §9 mitiga el riesgo entregando valor verificable por fases.
```
