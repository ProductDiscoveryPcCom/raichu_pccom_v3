# Raichu Next.js — Fase 2 Plan B (Formulario shadcn + brief I/O + cableado) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Llevar el formulario del modo Nuevo a paridad: UI con shadcn/ui en secciones plegables (accordion) que recoge todos los inputs (producto/PDP, enlaces, elementos visuales, headings, briefing guiado, secundarias, fuentes), brief Markdown descargable/subible, y cablear ese `NewContentInput` completo al endpoint `/api/generate` (que pasa a enviarlo al pipeline ya enriquecido en el Plan A).

**Architecture:** Componentes cliente React (`'use client'`) con shadcn/ui sobre Tailwind. El estado vive en el store Zustand ampliado. Al generar, el cliente construye un `NewContentInput` (parseando el JSON de producto con `parseProductJson` para feedback inmediato) y lo envía al Route Handler, que lo reenvía a `runNewContentPipeline`. Sin BD.

**Tech Stack:** Next.js (App Router) · TypeScript · React · Tailwind · **shadcn/ui** · Zustand · Vitest · @testing-library/react.

## Global Constraints

- **Proyecto de trabajo:** `C:\Users\maximo.sanchez\OneDrive - PcComponentes\Escritorio\claude projects\raichu-next` (rama `master`). Trabaja SIEMPRE dentro de esa carpeta. (Repo en OneDrive: si `Read` devuelve copia stale, usa `git show HEAD:<ruta>` como verdad; si `tsc` falla por caché, borra `*.tsbuildinfo` fuera de node_modules y reintenta.)
- **Secrets solo server-side:** los componentes cliente NO importan `@/lib/clients/*` ni SDKs de IA. El parseo de producto (`parseProductJson`) y validadores SÍ pueden usarse en cliente (son lógica pura, sin red).
- **Compatibilidad:** el endpoint sigue emitiendo los mismos eventos SSE (`stage`/`done`/`error`); solo cambia el *cuerpo de entrada* que acepta. El consumo SSE del cliente (Fase 1) no cambia.
- **Interfaces existentes del Plan A** (consumir, no redefinir):
  - `NewContentInput` y `LinkWithAnchor` desde `@/lib/pipeline/run-new-content` (Link re-exportado desde `@/lib/prompts/new-content`).
  - `ARQUETIPOS`, `PREGUNTAS_UNIVERSALES`, `getArquetipo`, `listArquetipos` desde `@/lib/config/arquetipos`.
  - `VISUAL_ELEMENTS`, `defaultVisualElementsForArquetipo` desde `@/lib/config/visual-elements`.
  - `parseProductJson`, `validateProductJson`, `ProductData` desde `@/lib/product/product-json`.
  - `buildBriefMarkdown`, `parseBriefMarkdown`, `BriefData` desde `@/lib/brief/brief-io`.
  - `validateKeyword`, `validateTargetLength`, `validateUrl`, `validateArquetipoCode`, `MAX_COMPETITORS`, `MAX_LINKS_PER_TYPE` desde `@/lib/validation/inputs`.
  - Store actual `useGenerationStore` (`@/store/generation`): `keyword`, `arquetipoCode`, `targetLength`, `status`, `stageLabel`, `html`, `analysis`, `error`, `cmsAllPresent`, `cmsMissing`, `setField`, `reset`.
- **TDD:** test que falla → implementación mínima → test que pasa → commit, por tarea.

---

### Task 1: Inicializar shadcn/ui + componentes base

**Files:**
- Create/Modify: configuración de shadcn (`components.json`, `src/lib/utils.ts`, estilos), y componentes en `src/components/ui/*`.
- Modify: `src/app/globals.css` (variables de shadcn) según genere el CLI.

**Interfaces:**
- Produces: componentes shadcn disponibles bajo `@/components/ui/*`: `accordion`, `input`, `textarea`, `select`, `slider`, `checkbox`, `tabs`, `button`, `label`, `card`.

- [ ] **Step 1: Inicializar shadcn**

```bash
cd "C:/Users/maximo.sanchez/OneDrive - PcComponentes/Escritorio/claude projects/raichu-next"
npx --yes shadcn@latest init -d
```

`-d` usa los defaults (estilo, base color, CSS variables). Si el CLI pide confirmación interactiva que bloquee, reintenta con las flags no interactivas equivalentes que indique su `--help`. Si detecta Tailwind v4 vs v3, acepta la configuración que proponga.

- [ ] **Step 2: Añadir los componentes necesarios**

```bash
npx --yes shadcn@latest add accordion input textarea select slider checkbox tabs button label card
```

Expected: crea `src/components/ui/{accordion,input,textarea,select,slider,checkbox,tabs,button,label,card}.tsx` y `src/lib/utils.ts` (helper `cn`).

- [ ] **Step 3: Verificar que el proyecto sigue compilando**

Run:
```bash
npm run build && npx tsc --noEmit
```
Expected: build OK; sin errores de tipo. (Si `tsc` falla por caché incremental, borra `*.tsbuildinfo` fuera de node_modules y reintenta.)

- [ ] **Step 4: Smoke test de un componente shadcn**

Create `src/components/ui/__smoke__/button.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Button } from '@/components/ui/button'

describe('shadcn button', () => {
  it('renderiza su contenido', () => {
    render(<Button>Generar</Button>)
    expect(screen.getByRole('button', { name: 'Generar' })).toBeInTheDocument()
  })
})
```

Run: `npx vitest run src/components/ui/__smoke__/button.test.tsx`
Expected: PASS (1 passed). Si el import de `@/components/ui/button` falla, ajusta la ruta al nombre real que generó el CLI.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "chore: init shadcn/ui + base components"
```

---

### Task 2: Ampliar el store con todos los campos del modo Nuevo

**Files:**
- Modify: `src/store/generation.ts`
- Modify: `src/store/generation.test.ts`

**Interfaces:**
- Consumes: `LinkWithAnchor` (`@/lib/prompts/new-content`).
- Produces: el store `useGenerationStore` con estos campos de formulario añadidos (además de los de resultado ya existentes):
  - `additionalInstructions: string`
  - `secondaryKeywords: string` (textarea, una por línea — se split al construir el input)
  - `authoritativeSources: string` (textarea, una por línea)
  - `pdpUrl: string`
  - `productJson: string` (texto pegado/subido)
  - `altProductUrl: string`, `altProductName: string`, `altProductJson: string`
  - `internalLinks: LinkDraft[]`, `pdpLinks: LinkDraft[]` (listas dinámicas)
  - `competitorUrls: string` (textarea, una por línea, máx `MAX_COMPETITORS`)
  - `visualElements: string[]` (ids seleccionados)
  - `headingsH2: number | null`, `headingsH3: number | null`, `headingsH4: number | null`
  - `guidingAnswers: Record<string, string>`
  - `webResearch: boolean`
  - donde `interface LinkDraft { url: string; anchor: string; json: string }`
  - Acciones nuevas: `addLink(kind: 'internal' | 'pdp')`, `removeLink(kind, index)`, `updateLink(kind, index, patch)`, `toggleVisualElement(id)`, `setGuidingAnswer(key, value)`. `reset()` sigue limpiando SOLO los campos de resultado (no el formulario), como hasta ahora.

- [ ] **Step 1: Escribir los tests nuevos (sin romper los existentes)**

Añade a `src/store/generation.test.ts` un `describe` nuevo (deja intactos los tests de Fase 1):

```ts
import { useGenerationStore } from './generation'

describe('store ampliado (Fase 2)', () => {
  it('listas de enlaces: add/update/remove', () => {
    const s = () => useGenerationStore.getState()
    s().reset()
    // limpiar listas manualmente para test determinista
    useGenerationStore.setState({ internalLinks: [], pdpLinks: [] })
    s().addLink('internal')
    expect(s().internalLinks.length).toBe(1)
    s().updateLink('internal', 0, { url: 'https://x.com', anchor: 'ancla' })
    expect(s().internalLinks[0].url).toBe('https://x.com')
    expect(s().internalLinks[0].anchor).toBe('ancla')
    s().removeLink('internal', 0)
    expect(s().internalLinks.length).toBe(0)
  })

  it('toggle de elementos visuales', () => {
    useGenerationStore.setState({ visualElements: [] })
    useGenerationStore.getState().toggleVisualElement('toc')
    expect(useGenerationStore.getState().visualElements).toContain('toc')
    useGenerationStore.getState().toggleVisualElement('toc')
    expect(useGenerationStore.getState().visualElements).not.toContain('toc')
  })

  it('respuestas de briefing por clave', () => {
    useGenerationStore.getState().setGuidingAnswer('guiding_univ_0', 'Gamers')
    expect(useGenerationStore.getState().guidingAnswers['guiding_univ_0']).toBe('Gamers')
  })
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/store/generation.test.ts`
Expected: FAIL — `addLink`/`toggleVisualElement`/`setGuidingAnswer` no existen.

- [ ] **Step 3: Ampliar el store**

En `src/store/generation.ts`: añade los campos nuevos al estado y a sus valores iniciales (strings `''`, arrays `[]`, headings `null`, `webResearch: false`, `guidingAnswers: {}`); define `interface LinkDraft { url: string; anchor: string; json: string }`; implementa las acciones:

```ts
import type { } from '@/lib/prompts/new-content' // (LinkWithAnchor solo se usa al construir el input, no en el store)

export interface LinkDraft { url: string; anchor: string; json: string }
const emptyLink = (): LinkDraft => ({ url: '', anchor: '', json: '' })

// dentro del create(...):
addLink: (kind) =>
  set((st) => ({ [kind === 'internal' ? 'internalLinks' : 'pdpLinks']:
    [...(kind === 'internal' ? st.internalLinks : st.pdpLinks), emptyLink()] } as Partial<GenerationState>)),
removeLink: (kind, index) =>
  set((st) => {
    const key = kind === 'internal' ? 'internalLinks' : 'pdpLinks'
    const arr = (kind === 'internal' ? st.internalLinks : st.pdpLinks).filter((_, i) => i !== index)
    return { [key]: arr } as Partial<GenerationState>
  }),
updateLink: (kind, index, patch) =>
  set((st) => {
    const key = kind === 'internal' ? 'internalLinks' : 'pdpLinks'
    const arr = (kind === 'internal' ? st.internalLinks : st.pdpLinks).map((l, i) => i === index ? { ...l, ...patch } : l)
    return { [key]: arr } as Partial<GenerationState>
  }),
toggleVisualElement: (id) =>
  set((st) => ({ visualElements: st.visualElements.includes(id)
    ? st.visualElements.filter((x) => x !== id)
    : [...st.visualElements, id] })),
setGuidingAnswer: (key, value) =>
  set((st) => ({ guidingAnswers: { ...st.guidingAnswers, [key]: value } })),
```

Mantén `reset()` limpiando solo los campos de resultado (no toca el formulario).

- [ ] **Step 4: Ejecutar para verificar que pasa (y no rompe Fase 1)**

Run: `npx vitest run src/store/generation.test.ts && npx tsc --noEmit`
Expected: PASS (todos); sin errores de tipo.

- [ ] **Step 5: Commit**

```bash
git add src/store/generation.ts src/store/generation.test.ts
git commit -m "feat: extend store with full new-mode form state + dynamic lists"
```

---

### Task 3: Construcción de `NewContentInput` desde el store (helper puro)

**Files:**
- Create: `src/lib/form/build-input.ts`
- Test: `src/lib/form/build-input.test.ts`

**Interfaces:**
- Consumes: `NewContentInput`, `LinkWithAnchor` (`@/lib/pipeline/run-new-content`), `parseProductJson` (`@/lib/product/product-json`), `LinkDraft` (`@/store/generation`).
- Produces: `export function buildNewContentInput(form: FormSnapshot): NewContentInput` — función pura que toma un snapshot plano del formulario (los campos del store) y produce el `NewContentInput`: parsea JSONs de producto a `ProductData`, mapea `LinkDraft[]` → `LinkWithAnchor[]` (parseando su `json` si lo hay), split de textareas (`secondaryKeywords`/`authoritativeSources`/`competitorUrls`) en arrays por línea no vacía, headings a `{h2,h3,h4}` omitiendo nulos, y `guidingAnswers` tal cual. `FormSnapshot` se define en este módulo con los campos del store.

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/form/build-input.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { buildNewContentInput, type FormSnapshot } from './build-input'

const base: FormSnapshot = {
  keyword: 'monitores gaming', arquetipoCode: 'ARQ-1', targetLength: 1500,
  additionalInstructions: 'Instr', secondaryKeywords: 'kw2\nkw3', authoritativeSources: 'https://a.com\n',
  pdpUrl: '', productJson: '', altProductUrl: '', altProductName: '', altProductJson: '',
  internalLinks: [{ url: 'https://x.com', anchor: 'ancla', json: '' }],
  pdpLinks: [], competitorUrls: 'https://comp.com',
  visualElements: ['toc', 'table'], headingsH2: 3, headingsH3: null, headingsH4: null,
  guidingAnswers: { guiding_univ_0: 'Gamers' }, webResearch: false,
}

describe('buildNewContentInput', () => {
  it('mapea campos base y arrays de textarea', () => {
    const input = buildNewContentInput(base)
    expect(input.keyword).toBe('monitores gaming')
    expect(input.arquetipoCode).toBe('ARQ-1')
    expect(input.secondaryKeywords).toEqual(['kw2', 'kw3'])
    expect(input.authoritativeSources).toEqual(['https://a.com'])
    expect(input.competitorUrls).toEqual(['https://comp.com'])
    expect(input.additionalInstructions).toBe('Instr')
  })
  it('mapea enlaces internos a LinkWithAnchor', () => {
    const input = buildNewContentInput(base)
    expect(input.internalLinks?.[0]).toMatchObject({ url: 'https://x.com', anchor: 'ancla' })
  })
  it('headings omite nulos', () => {
    const input = buildNewContentInput(base)
    expect(input.headingsConfig).toEqual({ h2: 3 })
  })
  it('parsea JSON de producto cuando está presente', () => {
    const productJson = JSON.stringify({ product_id: '1', title: 'Monitor', brand_name: 'ASUS' })
    const input = buildNewContentInput({ ...base, productJson })
    expect(input.product?.productId).toBe('1')
    expect(input.product?.brandName).toBe('ASUS')
  })
  it('producto null si el JSON está vacío o es inválido', () => {
    expect(buildNewContentInput({ ...base, productJson: '' }).product ?? null).toBeNull()
    expect(buildNewContentInput({ ...base, productJson: 'nope' }).product ?? null).toBeNull()
  })
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/lib/form/build-input.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar el builder**

Create `src/lib/form/build-input.ts`:

```ts
import type { NewContentInput, LinkWithAnchor } from '@/lib/pipeline/run-new-content'
import { parseProductJson } from '@/lib/product/product-json'
import type { LinkDraft } from '@/store/generation'

export interface FormSnapshot {
  keyword: string
  arquetipoCode: string
  targetLength: number
  additionalInstructions: string
  secondaryKeywords: string
  authoritativeSources: string
  pdpUrl: string
  productJson: string
  altProductUrl: string
  altProductName: string
  altProductJson: string
  internalLinks: LinkDraft[]
  pdpLinks: LinkDraft[]
  competitorUrls: string
  visualElements: string[]
  headingsH2: number | null
  headingsH3: number | null
  headingsH4: number | null
  guidingAnswers: Record<string, string>
  webResearch: boolean
}

const lines = (s: string): string[] =>
  (s ?? '').split('\n').map((l) => l.trim()).filter((l) => l.length > 0)

const parseMaybe = (json: string) => {
  const t = (json ?? '').trim()
  return t ? parseProductJson(t) : null
}

const toLinks = (drafts: LinkDraft[]): LinkWithAnchor[] =>
  (drafts ?? [])
    .filter((d) => d.url.trim().length > 0)
    .map((d) => ({ url: d.url.trim(), anchor: d.anchor.trim(), data: parseMaybe(d.json) }))

export function buildNewContentInput(form: FormSnapshot): NewContentInput {
  const headingsConfig: { h2?: number; h3?: number; h4?: number } = {}
  if (form.headingsH2 != null) headingsConfig.h2 = form.headingsH2
  if (form.headingsH3 != null) headingsConfig.h3 = form.headingsH3
  if (form.headingsH4 != null) headingsConfig.h4 = form.headingsH4

  return {
    keyword: form.keyword.trim(),
    arquetipoCode: form.arquetipoCode,
    targetLength: form.targetLength,
    additionalInstructions: form.additionalInstructions || undefined,
    secondaryKeywords: lines(form.secondaryKeywords),
    authoritativeSources: lines(form.authoritativeSources),
    product: parseMaybe(form.productJson),
    alternativeProduct:
      form.altProductUrl || form.altProductName || form.altProductJson
        ? { url: form.altProductUrl || undefined, name: form.altProductName || undefined, data: parseMaybe(form.altProductJson) }
        : undefined,
    internalLinks: toLinks(form.internalLinks),
    pdpLinks: toLinks(form.pdpLinks),
    competitorUrls: lines(form.competitorUrls),
    visualElements: form.visualElements,
    headingsConfig: Object.keys(headingsConfig).length ? headingsConfig : undefined,
    guidingAnswers: form.guidingAnswers,
  }
}
```

- [ ] **Step 4: Ejecutar para verificar que pasa**

Run: `npx vitest run src/lib/form/build-input.test.ts && npx tsc --noEmit`
Expected: PASS (5 passed); sin errores de tipo.

- [ ] **Step 5: Commit**

```bash
git add src/lib/form/build-input.ts src/lib/form/build-input.test.ts
git commit -m "feat: pure buildNewContentInput from form snapshot"
```

---

### Task 4: Secciones del formulario (accordion shadcn)

**Files:**
- Create: `src/components/form/NewContentForm.tsx` (orquesta el accordion y lee/escribe el store)
- Create: `src/components/form/sections/*` si conviene separar (Básicos, Producto, Enlaces, Visuales, Headings, Briefing, Investigación) — el implementador decide la granularidad de archivos manteniendo cada uno enfocado.
- Test: `src/components/form/NewContentForm.test.tsx`

**Interfaces:**
- Consumes: store ampliado (Task 2), `listArquetipos`/`getArquetipo`/`PREGUNTAS_UNIVERSALES` (`@/lib/config/arquetipos`), `VISUAL_ELEMENTS`/`defaultVisualElementsForArquetipo` (`@/lib/config/visual-elements`), componentes shadcn (Task 1), validadores (`@/lib/validation/inputs`).
- Produces: `export function NewContentForm(props: { onGenerate: () => void })` — componente cliente que renderiza el accordion con todas las secciones, enlazado al store, y un botón "Generar" (deshabilitado si `validateKeyword(keyword).ok === false` o `status === 'running'`) que llama a `props.onGenerate`. Al cambiar el arquetipo, preselecciona sus elementos visuales (`defaultVisualElementsForArquetipo`) y ajusta `targetLength` por defecto si el usuario no lo tocó.

- [ ] **Step 1: Escribir el test que falla**

Create `src/components/form/NewContentForm.test.tsx`:

```tsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { NewContentForm } from './NewContentForm'
import { useGenerationStore } from '@/store/generation'

beforeEach(() => {
  useGenerationStore.setState({
    keyword: '', arquetipoCode: 'ARQ-1', status: 'idle', visualElements: [],
    internalLinks: [], pdpLinks: [],
  } as never)
})

describe('NewContentForm', () => {
  it('Generar deshabilitado con keyword corta, habilitado al escribir', () => {
    render(<NewContentForm onGenerate={vi.fn()} />)
    const btn = screen.getByRole('button', { name: /generar/i })
    expect(btn).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/keyword/i), { target: { value: 'monitores gaming' } })
    expect(btn).toBeEnabled()
  })

  it('al pulsar Generar invoca onGenerate', () => {
    const onGenerate = vi.fn()
    render(<NewContentForm onGenerate={onGenerate} />)
    fireEvent.change(screen.getByLabelText(/keyword/i), { target: { value: 'monitores' } })
    fireEvent.click(screen.getByRole('button', { name: /generar/i }))
    expect(onGenerate).toHaveBeenCalled()
  })

  it('añade un enlace interno con el botón de añadir', () => {
    render(<NewContentForm onGenerate={vi.fn()} />)
    // abre la sección Enlaces y pulsa "Añadir enlace interno"
    fireEvent.click(screen.getByText(/enlaces/i))
    fireEvent.click(screen.getByRole('button', { name: /añadir enlace interno/i }))
    expect(useGenerationStore.getState().internalLinks.length).toBe(1)
  })
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/components/form/NewContentForm.test.tsx`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar el formulario**

Crea `NewContentForm.tsx` (y, si lo separas, las secciones). Usa el `Accordion` de shadcn con `type="multiple"` y la sección **Básicos** con `defaultValue` abierto. Conecta cada campo al store vía `useGenerationStore` (`setField`/acciones). Reglas:
- **Básicos:** `Input` keyword (con `<Label htmlFor>` que diga "Keyword"), `Select` de arquetipos (`listArquetipos()`), `Slider` 500–5000, `Textarea` instrucciones.
- **Producto/PDP:** `Input` pdpUrl, `Tabs` (Pegar `Textarea` / Subir `input[type=file]`) para `productJson`; producto alternativo (url/nombre/json).
- **Enlaces:** listas dinámicas de `internalLinks`/`pdpLinks` (cada fila url+anchor+json opcional, con botón eliminar) y un botón "Añadir enlace interno"/"Añadir enlace PDP" (deshabilitado al llegar a `MAX_LINKS_PER_TYPE`); `Textarea` competidores.
- **Elementos visuales:** `Checkbox` por cada `VISUAL_ELEMENTS`, marcado según `visualElements` del store; al cambiar arquetipo, preselecciona `defaultVisualElementsForArquetipo(code)`.
- **Headings:** 3 `Input type=number` (h2 1–15, h3 0–30, h4 0–20), opcionales.
- **Briefing guiado:** un `Textarea` por cada pregunta del arquetipo activo (`getArquetipo(code)?.guidingQuestions`, claves `guiding_spec_{i}`) y por cada universal (`PREGUNTAS_UNIVERSALES`, claves `guiding_univ_{i}`), enlazados a `guidingAnswers` vía `setGuidingAnswer`.
- **Investigación:** `Textarea` fuentes + `Checkbox` web research.
- Botón "Generar": `disabled={!validateKeyword(keyword).ok || status==='running'}`; al click → `props.onGenerate()`.

- [ ] **Step 4: Ejecutar para verificar que pasa**

Run: `npx vitest run src/components/form/NewContentForm.test.tsx && npx tsc --noEmit`
Expected: PASS (3 passed); sin errores de tipo. (Ajusta selectores del test si los textos accesibles difieren, manteniendo el comportamiento verificado.)

- [ ] **Step 5: Commit**

```bash
git add src/components/form/
git commit -m "feat: full new-mode form with shadcn accordion sections"
```

---

### Task 5: Barra de Brief I/O (descargar + subir que autocompleta)

**Files:**
- Create: `src/components/form/BriefBar.tsx`
- Test: `src/components/form/BriefBar.test.tsx`

**Interfaces:**
- Consumes: `buildBriefMarkdown`/`parseBriefMarkdown`/`BriefData` (`@/lib/brief/brief-io`), store ampliado.
- Produces: `export function BriefBar()` — componente cliente con: botón "Descargar brief" (genera Markdown con `buildBriefMarkdown` desde el estado y dispara descarga de `brief.md`) y un `input[type=file]` "Subir brief" que lee el `.md`, lo parsea con `parseBriefMarkdown` y vuelca los campos al store (`setField` de keyword/targetLength/arquetipo/instrucciones, `setField` de secundarias/fuentes como texto multilínea, y `setGuidingAnswer` por cada clave `guiding_*`).

- [ ] **Step 1: Escribir el test que falla**

Create `src/components/form/BriefBar.test.tsx`:

```tsx
import { describe, it, expect, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BriefBar } from './BriefBar'
import { useGenerationStore } from '@/store/generation'
import { buildBriefMarkdown } from '@/lib/brief/brief-io'

beforeEach(() => {
  useGenerationStore.setState({
    keyword: '', arquetipoCode: 'ARQ-1', targetLength: 1500,
    secondaryKeywords: '', additionalInstructions: '', authoritativeSources: '', guidingAnswers: {},
  } as never)
})

describe('BriefBar', () => {
  it('subir un brief autocompleta el store', async () => {
    render(<BriefBar />)
    const md = buildBriefMarkdown({
      arquetipo: 'ARQ-7', keyword: 'monitores gaming', targetLength: 2200,
      secondaryKeywords: ['kw2'], additionalInstructions: 'Instr',
      authoritativeSources: ['https://a.com'], guiding: { guiding_univ_0: 'Gamers' },
    })
    const file = new File([md], 'brief.md', { type: 'text/markdown' })
    const input = screen.getByLabelText(/subir brief/i) as HTMLInputElement
    fireEvent.change(input, { target: { files: [file] } })
    await waitFor(() => {
      expect(useGenerationStore.getState().keyword).toBe('monitores gaming')
    })
    expect(useGenerationStore.getState().arquetipoCode).toBe('ARQ-7')
    expect(useGenerationStore.getState().targetLength).toBe(2200)
    expect(useGenerationStore.getState().guidingAnswers['guiding_univ_0']).toBe('Gamers')
  })

  it('el botón de descargar brief está presente', () => {
    render(<BriefBar />)
    expect(screen.getByRole('button', { name: /descargar brief/i })).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/components/form/BriefBar.test.tsx`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar BriefBar**

Crea `BriefBar.tsx`. Descargar: construye un `BriefData` desde el store (secundarias/fuentes split por líneas; `guiding` = `guidingAnswers`), llama `buildBriefMarkdown`, crea un `Blob` `text/markdown` y dispara descarga (`a.download='brief.md'`, revoca el objectURL). Subir: `input[type=file]` con `<Label htmlFor>` "Subir brief"; en `onChange`, `await file.text()`, `parseBriefMarkdown`, y vuelca: `setField('keyword', ...)`, `setField('targetLength', Number(...))`, `setField('arquetipoCode', parsed.arquetipo)`, `setField('additionalInstructions', ...)`, `setField('secondaryKeywords', parsed.secondaryKeywords.join('\n'))`, `setField('authoritativeSources', parsed.authoritativeSources.join('\n'))`, y por cada clave de `parsed.guiding` → `setGuidingAnswer(key, value)`.

- [ ] **Step 4: Ejecutar para verificar que pasa**

Run: `npx vitest run src/components/form/BriefBar.test.tsx && npx tsc --noEmit`
Expected: PASS (2 passed); sin errores de tipo.

- [ ] **Step 5: Commit**

```bash
git add src/components/form/BriefBar.tsx src/components/form/BriefBar.test.tsx
git commit -m "feat: brief I/O bar (download + upload autofills form)"
```

---

### Task 6: Extender el Route Handler para aceptar el `NewContentInput` completo

**Files:**
- Modify: `src/app/api/generate/route.ts`

**Interfaces:**
- Consumes: `runNewContentPipeline`, `NewContentInput` (`@/lib/pipeline/run-new-content`).
- Produces: el `POST /api/generate` acepta en el cuerpo un `NewContentInput` completo (no solo los 3 campos base) y lo reenvía a `runNewContentPipeline`. Mantiene la validación mínima de keyword (≥2) y los mismos eventos SSE. Los campos opcionales ausentes se pasan tal cual (el pipeline ya los trata como opcionales).

- [ ] **Step 1: Ajustar el parseo del cuerpo**

Modifica `route.ts`: en lugar de leer solo `keyword`/`arquetipoCode`/`targetLength`, construye el `NewContentInput` desde el body de forma defensiva:

```ts
const body = await req.json()
const tl = Number(body.targetLength)
const input = {
  keyword: String(body.keyword ?? '').trim(),
  arquetipoCode: String(body.arquetipoCode ?? ''),
  targetLength: Number.isFinite(tl) ? tl : 1500,
  additionalInstructions: body.additionalInstructions,
  secondaryKeywords: Array.isArray(body.secondaryKeywords) ? body.secondaryKeywords : undefined,
  authoritativeSources: Array.isArray(body.authoritativeSources) ? body.authoritativeSources : undefined,
  product: body.product ?? null,
  alternativeProduct: body.alternativeProduct,
  internalLinks: Array.isArray(body.internalLinks) ? body.internalLinks : undefined,
  pdpLinks: Array.isArray(body.pdpLinks) ? body.pdpLinks : undefined,
  competitorUrls: Array.isArray(body.competitorUrls) ? body.competitorUrls : undefined,
  visualElements: Array.isArray(body.visualElements) ? body.visualElements : undefined,
  headingsConfig: body.headingsConfig,
  guidingAnswers: body.guidingAnswers,
} satisfies import('@/lib/pipeline/run-new-content').NewContentInput
```

Dentro del `start(controller)`, mantén el guard `if (input.keyword.length < 2) { emit error; return }` y luego `await runNewContentPipeline(input, deps, emit)`. El resto (deps, SSE, close en finally) no cambia.

- [ ] **Step 2: Verificar tipos y build**

Run: `npx tsc --noEmit && npm run build`
Expected: sin errores de tipo; build OK.

- [ ] **Step 3: Commit**

```bash
git add src/app/api/generate/route.ts
git commit -m "feat: /api/generate accepts full NewContentInput body"
```

---

### Task 7: Cablear la página (form enriquecido → input → /api/generate)

**Files:**
- Modify: `src/app/page.tsx` (usa `NewContentForm` + `BriefBar`; construye el input con `buildNewContentInput` y lo envía)
- Modify: `src/components/GenerationForm.tsx` y su test → **eliminar** (lo reemplaza `NewContentForm`); o dejar de usarlos. Si los eliminas, borra también `GenerationForm.test.tsx`.

**Interfaces:**
- Consumes: `NewContentForm` (Task 4), `BriefBar` (Task 5), `buildNewContentInput` (Task 3), `useGenerationStore`, `parseSseChunk` (`@/lib/sse-parse`), `ResultView`.
- Produces: la página del modo Nuevo cableada de extremo a extremo con el formulario completo.

- [ ] **Step 1: Reescribir page.tsx**

Reemplaza `src/app/page.tsx` para: renderizar `<BriefBar/>`, `<NewContentForm onGenerate={handleGenerate}/>` y `<ResultView/>`. `handleGenerate` lee el snapshot del store (los campos de formulario), llama `buildNewContentInput(snapshot)`, hace `store.reset()` + `setField('status','running')`, y hace el `fetch('/api/generate', { method:'POST', body: JSON.stringify(input) })` consumiendo el stream con `parseSseChunk` EXACTAMENTE como en la versión de Fase 1 (mapeo de eventos `stage`/`error`/`done` → store). No cambies la lógica de consumo SSE; solo cambia QUÉ se envía (el `NewContentInput` completo) y de dónde sale el formulario.

Para el snapshot: extrae del store los campos que `FormSnapshot` necesita (keyword, arquetipoCode, targetLength, additionalInstructions, secondaryKeywords, authoritativeSources, pdpUrl, productJson, altProduct*, internalLinks, pdpLinks, competitorUrls, visualElements, headingsH2/H3/H4, guidingAnswers, webResearch).

- [ ] **Step 2: Eliminar el formulario mínimo de Fase 1**

```bash
git rm src/components/GenerationForm.tsx src/components/GenerationForm.test.tsx
```

(Si algún otro archivo lo importaba además de page.tsx, actualízalo.)

- [ ] **Step 3: Verificar suite completa, tipos y build**

Run:
```bash
npm test && npx tsc --noEmit && npm run build
```
Expected: toda la suite verde; sin errores de tipo; build OK.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: wire full new-mode form + brief I/O to /api/generate"
```

---

### Task 8: README — actualizar alcance a Fase 2

**Files:**
- Modify: `README.md`

**Interfaces:**
- Produces: README con el alcance actualizado (modo Nuevo a paridad de inputs).

- [ ] **Step 1: Actualizar la sección de alcance**

En `README.md`, sustituye la nota de "Fase 1 = vertical slice" por una que refleje el estado tras la Fase 2: el modo Nuevo recoge todos los inputs (37 arquetipos, producto/PDP, enlaces, elementos visuales, headings, briefing guiado, secundarias, fuentes, brief I/O) y los pasa al pipeline. Indica que **queda pendiente Fase 3** (CSS real del design system, post-proceso de calidad, web research opt-in) y **Fase 4** (imágenes, JSON-LD).

- [ ] **Step 2: Verificación final**

Run: `npm test && npm run build`
Expected: verde.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update README scope to Phase 2 (inputs parity)"
```

---

## Notas de cierre del Plan B

Al terminar, el modo Nuevo de `raichu-next` tiene el formulario completo (shadcn + accordion), brief I/O, y el `NewContentInput` enriquecido viajando de extremo a extremo hasta el pipeline. Con esto la **Fase 2 (paridad de inputs) queda completa**. Las Fases 3 (calidad/CSS/post-proceso/web research) y 4 (imágenes/JSON-LD) tendrán su propio ciclo spec→plan→implementación.
