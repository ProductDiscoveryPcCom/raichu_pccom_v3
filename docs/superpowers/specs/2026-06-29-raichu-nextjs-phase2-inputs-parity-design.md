# Diseño — Raichu Next.js Fase 2 (Paridad de inputs del modo Nuevo)

**Fecha:** 2026-06-29
**Autor:** Máximo Sánchez (con Claude Code)
**Estado:** Aprobado (pendiente de revisión final del spec antes de los planes de implementación)
**Proyecto:** `raichu-next` (repo separado; ver el plan de Fase 1 en `docs/superpowers/plans/2026-06-25-raichu-nextjs-phase1-vertical-slice.md` y el spec maestro `docs/superpowers/specs/2026-06-25-raichu-nextjs-migration-design.md`)

---

## 1. Contexto

La Fase 1 entregó el vertical slice del modo Nuevo: formulario mínimo (keyword + arquetipo +
longitud) → pipeline server-side de 3 etapas con corrección dual y streaming SSE → HTML con
estructura CMS válida + descarga. Toda la arquitectura está validada y testeada.

La **Fase 2** lleva el **formulario del modo Nuevo a paridad funcional** con el Raichu
Streamlit actual y **alimenta esos inputs al pipeline ya existente**. No cambia la forma del
pipeline (sigue siendo Stage 1/2/3 + corrección dual); enriquece sus *entradas*.

### Objetivo

Que un redactor SEO pueda configurar una generación con el mismo nivel de detalle que en el
Raichu actual: arquetipo real (de 37), datos de producto/PDP, enlaces, elementos visuales,
headings, briefing guiado, keywords secundarias, fuentes, y el brief Markdown
descargable/subible.

### Frontera con la Fase 3 (explícita)

- **En Fase 2:** recoger todos los inputs, validarlos, e **inyectar las selecciones de
  elementos visuales como instrucciones en el prompt**.
- **En Fase 3 (no aquí):** el CSS real del design system, el render/corrección visual de esos
  elementos, y el post-proceso de calidad (scrub Unicode, fix de tablas, CSS `!important`,
  quality loop, meta/TL;DR). El `web_research` opt-in se **recoge** en Fase 2 pero su ejecución
  (Stage 0) es Fase 3.

### Fuera de alcance (Fase 2)

- Otros modos (rewrite/verify/opportunities/assistant) y agentes.
- Generación de imágenes y JSON-LD (Fase 4).
- Webhook n8n para *traer* producto (en Fase 2 el JSON se pega/sube; el fetch automático es
  posterior).

---

## 2. Decisiones de diseño

| # | Decisión | Estado |
|---|----------|--------|
| A | UI con **shadcn/ui** (sobre Tailwind ya instalado) | Aprobada |
| B | Layout del formulario en **secciones plegables (accordion)** | Aprobada |
| C | El pipeline **no cambia de forma**; se amplían su tipo de entrada y los prompts | Aprobada |
| D | Implementación en **dos planes**: (A) datos/config + pipeline; (B) formulario + brief I/O + cableado | Aprobada |
| E | Datos estáticos (arquetipos, registro visual) portados como **módulos TS/JSON** | Aprobada |

---

## 3. Capa de datos y configuración (lógica pura)

### 3.1 Arquetipos completos (reemplaza el subconjunto de Fase 1)

Portar los **37 arquetipos** (`ARQ-1`..`ARQ-37`) desde `config/arquetipos.py`. Estructura por
arquetipo:

```ts
interface Arquetipo {
  code: string            // "ARQ-1"
  name: string
  description: string
  tone: string
  structure: string[]     // secciones recomendadas
  guidingQuestions: string[]   // preguntas específicas del arquetipo
  defaultLength: number
  minLength: number
  maxLength: number
  visualElements: string[]     // ids preseleccionados (toc, table, ...)
}
```

Más las **6 preguntas universales** (`PREGUNTAS_UNIVERSALES`) que aplican a todos.

Helpers: `getArquetipo(code)`, `isValidArquetipo(code)`, `listArquetipos()`. El subconjunto
de 3 de la Fase 1 se sustituye por los 37; `getArquetipo`/`isValidArquetipo` mantienen su
firma (los consumidores existentes no cambian).

*Nota de verificación:* confirmar el número exacto (37 según el código Python; el `CLAUDE.md`
dice 34, desactualizado). El recuento real lo fija `config/arquetipos.py`.

### 3.2 Registro de elementos visuales (27 componentes)

Portar el catálogo de `ui/inputs.py` como módulo TS:

```ts
interface VisualElement {
  id: string              // "toc", "table", "comparison_table", "callout", ...
  label: string
  description: string
  help: string
  default: boolean
}
export const VISUAL_ELEMENTS: VisualElement[]
```

La preselección efectiva por arquetipo se calcula con `arquetipo.visualElements`. En Fase 2 el
registro alimenta los checkboxes del formulario y la lista de ids seleccionados que viaja al
prompt; las plantillas HTML/CSS de cada componente son Fase 3.

### 3.3 Parser de JSON de producto

Portar `utils/product_json_utils.py` a `parseProductJson(jsonStr): ProductData | null` y
`validateProductJson(jsonStr): { ok: boolean; error?: string }`. Soporta **dos formatos**:

1. **n8n wrapper** (primario): array con `meta`/`data[]`, donde el contenido vive en un campo
   `markdown` con secciones (`## CARACTERISTICAS`, `## ESPECIFICACIONES`, `## DESCRIPCION`,
   `## ES PARA TI SI`, `## NO ES PARA TI SI`, `## FAQS`). Se parsean a campos estructurados.
2. **legacy plano** (compatibilidad): objeto con `product_id`, `title`, `brand_name`,
   `attributes`, `advantages`, `disadvantages`, etc.

`ProductData` tipado: `productId`, `title`, `brandName`, `familyName`, `description`,
`attributes`, `images`, `advantagesList`, `disadvantagesList`, `comments`/`topComments`,
`totalComments`, `price`, `productUrl`, `rating`, `category`, `faqs`. Detección automática de
formato; `null` si no parsea.

### 3.4 Brief Markdown bidireccional

`buildBriefMarkdown(formData): string` y `parseBriefMarkdown(md): { meta, fields }`.

- Marcador `<!-- raichu-brief:v1 -->`; cabecera con `Modo:` y `Arquetipo:`.
- Secciones `## [id] Etiqueta` + línea `Respuesta:` con el valor debajo; listas
  (secundarias, fuentes) una por línea; preguntas `### [guiding_spec_i]` / `### [guiding_univ_i]`.
- Parser tolerante: acepta ausencia del marcador `Respuesta:`, ignora líneas de ayuda en
  cursiva, cierra sección al encontrar nuevo encabezado.
- Campos: `keyword`, `target_length`, `secondary_keywords`, `additional_instructions`,
  `authoritative_sources`, `guiding_spec_{i}`, `guiding_univ_{i}`.

---

## 4. Enriquecer el pipeline (consumir los nuevos inputs)

Ampliar el tipo de entrada de `runNewContentPipeline` y los 3 constructores de prompts
(`buildStage1Prompt`, `buildStage2Prompt`, `buildStage3Prompt`) para consumir:

```ts
interface NewContentInput {
  keyword: string
  arquetipoCode: string
  targetLength: number
  // nuevos en Fase 2:
  additionalInstructions?: string
  secondaryKeywords?: string[]
  authoritativeSources?: string[]
  product?: ProductData | null
  alternativeProduct?: { url?: string; name?: string; data?: ProductData | null }
  internalLinks?: LinkWithAnchor[]
  pdpLinks?: LinkWithAnchor[]
  competitorUrls?: string[]
  visualElements?: string[]        // ids seleccionados
  headingsConfig?: { h2?: number; h3?: number; h4?: number }
  guidingAnswers?: Record<string, string>  // guiding_spec_*/guiding_univ_*
}
interface LinkWithAnchor { url: string; anchor: string; data?: ProductData | null }
```

Helpers de formateo portados (equivalentes a `_format_products_for_prompt`,
`_format_visual_elements_instructions`): convierten `ProductData`, enlaces, visuales,
headings y briefing en bloques de texto que se insertan en los prompts. Reglas de marca
(anti-IA, tono) se mantienen del módulo de Fase 1; en Fase 2 se enriquece su contenido pero
no su estructura.

**Compatibilidad:** todos los campos nuevos son opcionales. El vertical slice de Fase 1 sigue
funcionando con solo `keyword`/`arquetipoCode`/`targetLength`.

---

## 5. Formulario (shadcn/ui + accordion)

`Accordion` de shadcn con estas secciones (la primera abierta por defecto):

| Sección | Campos |
|---------|--------|
| **Básicos** (abierta) | keyword (2–100), arquetipo (select de 37), longitud (slider 500–5000, default del arquetipo), instrucciones adicionales |
| **Producto / PDP** | url PDP, JSON de producto (tabs Pegar/Subir, n8n+legacy), producto alternativo (url/nombre/JSON) |
| **Enlaces** | internos (lista dinámica url+anchor+JSON opcional, máx 10), PDP (máx 10), competidores (máx 5) |
| **Elementos visuales** | checkboxes de los 27 componentes, preseleccionados según arquetipo, personalizables |
| **Headings** | h2 (1–15), h3 (0–30), h4 (0–20) opcionales |
| **Briefing guiado** | preguntas del arquetipo (`guiding_spec_*`) + 6 universales (`guiding_univ_*`) |
| **Investigación** | fuentes autoritativas (multilínea), checkbox web research (solo se recoge) |

Más, arriba, la barra **Brief I/O**: botón "Descargar brief" (`buildBriefMarkdown`) y subida de
`.md` que autocompleta el formulario (`parseBriefMarkdown` → set de estado).

**Estado:** se extiende el store Zustand de Fase 1 con los nuevos campos. Las listas dinámicas
(enlaces) gestionan add/remove. Persistencia en `localStorage` (opcional, mejora UX).

**Componentes shadcn a usar:** `accordion`, `input`, `textarea`, `select`, `slider`,
`checkbox`, `tabs`, `button`, `label`, `card`. Setup inicial de shadcn (CLI) en el primer plan
de UI.

### Validaciones (portadas)

`keyword` 2–100; `target_length` 500–5000; URL válida (≤2000, opción dominio PcC); arquetipo
existe; ≤5 competidores; ≤10 enlaces/tipo; JSON de producto parseable con `product_id`.

---

## 6. Estructura de archivos (nueva/ampliada en `raichu-next`)

```
src/lib/config/arquetipos.ts        # ampliar a 37 + preguntas universales
src/lib/config/visual-elements.ts   # nuevo: registro de 27
src/lib/product/product-json.ts     # nuevo: parseProductJson/validate/ProductData
src/lib/brief/brief-io.ts           # nuevo: build/parseBriefMarkdown
src/lib/prompts/new-content.ts      # ampliar builders + helpers de formateo
src/lib/pipeline/run-new-content.ts # ampliar NewContentInput
src/lib/validation/inputs.ts        # nuevo: validators
src/store/generation.ts             # ampliar con nuevos campos + listas dinámicas
src/components/form/*                # nuevo: secciones del accordion + brief I/O
+ sus *.test.ts(x)
```

---

## 7. Descomposición en dos planes

**Plan A — Datos/config + pipeline (sin UI):**
arquetipos (37 + universales), registro visual (27), `parseProductJson`, `brief-io`,
validators, y enriquecimiento de `NewContentInput` + los 3 builders con helpers de formateo.
Entregable testeable: la lógica que el formulario necesitará, verificada con Vitest sin red.

**Plan B — Formulario shadcn + brief I/O + cableado:**
setup de shadcn, store ampliado, secciones del accordion, listas dinámicas, tabs de JSON,
brief I/O (descarga/subida), y cableado del formulario enriquecido al `POST /api/generate`
(que pasa a enviar el `NewContentInput` completo). Tests de componentes clave + E2E ligero.

Cada plano se brainstormea/planifica como su propio ciclo writing-plans → ejecución por
subagentes, igual que la Fase 1.

---

## 8. Testing

- **Vitest (lógica pura):** arquetipos (conteo, lookup, preguntas), `parseProductJson` (n8n +
  legacy + inválido), `brief-io` (round-trip build→parse), validators, builders enriquecidos
  (que el prompt incluye producto/enlaces/visuales/briefing cuando se pasan).
- **@testing-library/react (componentes):** listas dinámicas (add/remove), tabs de JSON,
  subida de brief que autocompleta, accordion. Sin red ni keys.
- **Build/tsc** verdes como gate.

---

## 9. Riesgos y cuestiones abiertas

- **Volumen de datos portados:** 37 arquetipos con sus preguntas + 27 visuales es bastante
  transcripción fiel desde Python; riesgo de error de copia → tests de conteo y de campos
  obligatorios lo acotan.
- **Parser n8n:** el `markdown` embebido del formato n8n tiene secciones en español con
  variaciones; portar las heurísticas de `product_json_utils.py` con fixtures reales.
- **Frontera visual/CSS:** los elementos visuales se seleccionan e inyectan como texto en el
  prompt, pero sin el CSS de Fase 3 el HTML saldrá poco estilizado — es esperado y se comunica;
  la corrección visual llega en Fase 3.
- **Recuento de arquetipos (37 vs 34):** confirmar contra el código antes de portar.
