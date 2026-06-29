# Raichu Next.js — Fase 1 (Esqueleto + Vertical Slice) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Crear el proyecto Next.js nuevo y separado, y entregar un vertical slice del modo "Nuevo" end-to-end: formulario mínimo (keyword + arquetipo + longitud) → pipeline de 3 etapas con corrección dual (server-side, streaming SSE de progreso) → HTML con la estructura CMS de 3 `<article>` válida + descarga.

**Architecture:** App Router de Next.js (TypeScript). La UI React envía a un Route Handler que ejecuta el pipeline en el servidor Node y emite eventos SSE por etapa. La lógica pura (presupuesto de tokens, prompts, post-proceso, validación CMS, merge de análisis) vive en `lib/` y se testea con Vitest sin red. Las API keys son solo server-side. Sin BD.

**Tech Stack:** Next.js (App Router) · TypeScript · React · Tailwind CSS · Zustand · `@anthropic-ai/sdk` · `openai` · `cheerio` · Vitest · `@testing-library/react`.

## Global Constraints

- **Proyecto separado:** todo este plan se ejecuta en una carpeta hermana nueva `../raichu-next/` con su propio repositorio git. NO se toca el proyecto Python actual.
- **Estructura CMS obligatoria (invariante):** el HTML final DEBE contener exactamente 3 `<article>` con clases `contentGenerator__main`, `contentGenerator__faqs`, `contentGenerator__verdict`, y `__main` DEBE contener ≥1 `<h2>`.
- **Modelos (env-configurables):** `CLAUDE_MODEL` por defecto `claude-sonnet-4-6` (paridad con Raichu actual; Opus 4.8 = `claude-opus-4-8` es la opción más capaz, documentar en README). `DUAL_FALLBACK_MODEL` por defecto `claude-haiku-4-5`. `OPENAI_MODEL` por defecto `gpt-4.1-2025-04-14`.
- **Streaming Anthropic:** si `max_tokens > 21333` (`NONSTREAMING_MAX_TOKENS`), usar `client.messages.stream(...)` + `.finalMessage()`; por debajo, `client.messages.create(...)`.
- **Secrets solo server-side:** `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` en `.env.local`. Nunca importar clientes de IA en componentes cliente (`"use client"`).
- **Sin red en tests:** los tests que ejercitan clientes de IA inyectan un cliente falso; nunca asumir keys.
- **TDD:** test que falla → implementación mínima → test que pasa → commit, por tarea.
- **Tope de tokens duro:** `MODEL_OUTPUT_HARD_CAP = 32000`.

---

### Task 1: Scaffold del proyecto Next.js + tooling

**Files:**
- Create: `../raichu-next/` (proyecto completo vía `create-next-app`)
- Create: `../raichu-next/vitest.config.ts`
- Create: `../raichu-next/vitest.setup.ts`
- Create: `../raichu-next/.env.example`
- Create: `../raichu-next/src/lib/__smoke__/smoke.test.ts`
- Modify: `../raichu-next/next.config.ts` (añadir `output: 'standalone'`)
- Modify: `../raichu-next/package.json` (scripts de test)

**Interfaces:**
- Produces: un proyecto Next.js con App Router en `../raichu-next/`, alias de import `@/*` → `src/*`, `npm run dev`, `npm test`, `npm run build` funcionando.

- [ ] **Step 1: Crear el proyecto Next.js**

Desde el directorio padre del repo Python (NO dentro de él). Ejecutar de forma no interactiva:

```bash
cd "C:/Users/maximo.sanchez/OneDrive - PcComponentes/Escritorio/claude projects"
npx --yes create-next-app@latest raichu-next --typescript --app --tailwind --eslint --src-dir --import-alias "@/*" --use-npm --no-turbopack
```

Expected: crea `raichu-next/` con `src/app/`, `tailwind` configurado, git inicializado.

- [ ] **Step 2: Instalar dependencias de runtime y de test**

```bash
cd "C:/Users/maximo.sanchez/OneDrive - PcComponentes/Escritorio/claude projects/raichu-next"
npm install @anthropic-ai/sdk openai cheerio zustand
npm install -D vitest @testing-library/react @testing-library/jest-dom jsdom @vitejs/plugin-react
```

Expected: instala sin errores; las dependencias aparecen en `package.json`.

- [ ] **Step 3: Configurar Vitest**

Create `vitest.config.ts`:

```ts
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import path from 'node:path'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./vitest.setup.ts'],
  },
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
})
```

Create `vitest.setup.ts`:

```ts
import '@testing-library/jest-dom/vitest'
```

In `package.json`, add to `"scripts"`:

```json
"test": "vitest run",
"test:watch": "vitest"
```

- [ ] **Step 4: Configurar despliegue standalone y env de ejemplo**

In `next.config.ts`, set the config object to include standalone output:

```ts
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
}

export default nextConfig
```

Create `.env.example`:

```
# API keys (solo server-side). Copiar a .env.local y rellenar.
ANTHROPIC_API_KEY=
OPENAI_API_KEY=

# Opcionales (tienen defaults en código)
CLAUDE_MODEL=claude-sonnet-4-6
DUAL_FALLBACK_MODEL=claude-haiku-4-5
OPENAI_MODEL=gpt-4.1-2025-04-14
MAX_TOKENS=32000
```

- [ ] **Step 5: Smoke test**

Create `src/lib/__smoke__/smoke.test.ts`:

```ts
import { describe, it, expect } from 'vitest'

describe('smoke', () => {
  it('runs vitest', () => {
    expect(1 + 1).toBe(2)
  })
})
```

- [ ] **Step 6: Verificar que el toolchain arranca**

Run:

```bash
npm test
npm run build
```

Expected: `npm test` → 1 passed. `npm run build` → compila sin errores.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore: scaffold Next.js project with vitest and standalone output"
```

---

### Task 2: Presupuesto dinámico de tokens (`computeMaxTokens`)

**Files:**
- Create: `src/lib/token-budget.ts`
- Test: `src/lib/token-budget.test.ts`

**Interfaces:**
- Produces: `export function computeMaxTokens(targetLength: number, stage: 1 | 2 | 3, ceiling?: number): number`. Función pura. `ceiling` por defecto lee `MODEL_OUTPUT_HARD_CAP`. Usado por el pipeline (Task 8) en las 3 etapas.

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/token-budget.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { computeMaxTokens, MODEL_OUTPUT_HARD_CAP } from './token-budget'

describe('computeMaxTokens', () => {
  it('stage 1/3 (HTML) escala con target y respeta el piso de 8000', () => {
    // 2500 + 1500*4*1.30 = 10300 → redondeo a 10000
    expect(computeMaxTokens(1500, 1, 32000)).toBe(10000)
    expect(computeMaxTokens(1500, 3, 32000)).toBe(10000)
    // target pequeño cae al piso
    expect(computeMaxTokens(100, 1, 32000)).toBe(8000)
  })

  it('stage 2 (análisis) usa 3.0 tok/palabra con piso 4000', () => {
    // max(4000, 1500*3.0)=4500 → redondeo a 5000 (round half up al millar)
    expect(computeMaxTokens(1500, 2, 32000)).toBe(5000)
    expect(computeMaxTokens(100, 2, 32000)).toBe(4000)
  })

  it('clampa al techo (min(ceiling, hard cap))', () => {
    expect(computeMaxTokens(5000, 1, 12000)).toBe(12000)
    expect(computeMaxTokens(100000, 1, 999999)).toBe(MODEL_OUTPUT_HARD_CAP)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/token-budget.test.ts`
Expected: FAIL — "Cannot find module './token-budget'".

- [ ] **Step 3: Implementación mínima**

Create `src/lib/token-budget.ts`:

```ts
export const MODEL_OUTPUT_HARD_CAP = 32000

const STYLE_OVERHEAD_TOKENS = 2500
const TOKENS_PER_WORD_HTML = 4.0
const SAFETY_FACTOR = 1.3
const HTML_FLOOR = 8000
const STAGE2_FLOOR = 4000
const STAGE2_TOKENS_PER_WORD = 3.0

function roundTo1000(n: number): number {
  return Math.round(n / 1000) * 1000
}

export function computeMaxTokens(
  targetLength: number,
  stage: 1 | 2 | 3,
  ceiling: number = MODEL_OUTPUT_HARD_CAP,
): number {
  const hardCap = Math.min(ceiling, MODEL_OUTPUT_HARD_CAP)

  if (stage === 2) {
    const raw = Math.max(STAGE2_FLOOR, targetLength * STAGE2_TOKENS_PER_WORD)
    return Math.min(roundTo1000(raw), hardCap)
  }

  const raw = STYLE_OVERHEAD_TOKENS + targetLength * TOKENS_PER_WORD_HTML * SAFETY_FACTOR
  return Math.max(HTML_FLOOR, Math.min(roundTo1000(raw), hardCap))
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/token-budget.test.ts`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/token-budget.ts src/lib/token-budget.test.ts
git commit -m "feat: pure computeMaxTokens token budget"
```

---

### Task 3: Post-proceso HTML mínimo (extracción + validación CMS)

**Files:**
- Create: `src/lib/postprocess/html.ts`
- Test: `src/lib/postprocess/html.test.ts`

**Interfaces:**
- Produces:
  - `export function extractHtmlContent(raw: string): string` — quita fences ```` ```html ```` / ```` ``` ````.
  - `export interface CmsValidation { allPresent: boolean; missing: string[] }`
  - `export function validateCmsArticles(html: string): CmsValidation` — verifica las 3 clases `contentGenerator__*` y ≥1 `<h2>` dentro de `__main` (vía `cheerio`).
- Usado por el pipeline (Task 8).

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/postprocess/html.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { extractHtmlContent, validateCmsArticles } from './html'

const VALID = `
<article class="contentGenerator__main"><h2>Título</h2><p>x</p></article>
<article class="contentGenerator__faqs"><h2>FAQ</h2></article>
<article class="contentGenerator__verdict"><div class="verdict-box"><h2>V</h2></div></article>`

describe('extractHtmlContent', () => {
  it('quita los fences de markdown', () => {
    expect(extractHtmlContent('```html\n<p>hi</p>\n```')).toBe('<p>hi</p>')
    expect(extractHtmlContent('<p>plain</p>')).toBe('<p>plain</p>')
  })
})

describe('validateCmsArticles', () => {
  it('acepta los 3 articles con h2 en main', () => {
    const r = validateCmsArticles(VALID)
    expect(r.allPresent).toBe(true)
    expect(r.missing).toEqual([])
  })

  it('reporta los articles que faltan', () => {
    const r = validateCmsArticles('<article class="contentGenerator__main"><h2>x</h2></article>')
    expect(r.allPresent).toBe(false)
    expect(r.missing).toContain('contentGenerator__faqs')
    expect(r.missing).toContain('contentGenerator__verdict')
  })

  it('marca main sin h2 como faltante', () => {
    const html = VALID.replace('<h2>Título</h2>', '')
    const r = validateCmsArticles(html)
    expect(r.allPresent).toBe(false)
    expect(r.missing).toContain('contentGenerator__main h2')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/postprocess/html.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

Create `src/lib/postprocess/html.ts`:

```ts
import * as cheerio from 'cheerio'

export function extractHtmlContent(raw: string): string {
  let s = raw.trim()
  s = s.replace(/^```html\s*\n?/i, '').replace(/^```\s*\n?/, '')
  s = s.replace(/\n?```\s*$/, '')
  return s.trim()
}

export interface CmsValidation {
  allPresent: boolean
  missing: string[]
}

const REQUIRED = [
  'contentGenerator__main',
  'contentGenerator__faqs',
  'contentGenerator__verdict',
] as const

export function validateCmsArticles(html: string): CmsValidation {
  const $ = cheerio.load(html)
  const missing: string[] = []

  for (const cls of REQUIRED) {
    if ($(`article.${cls}`).length === 0) missing.push(cls)
  }

  const $main = $('article.contentGenerator__main')
  if ($main.length > 0 && $main.find('h2').length === 0) {
    missing.push('contentGenerator__main h2')
  }

  return { allPresent: missing.length === 0, missing }
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/postprocess/html.test.ts`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/postprocess/html.ts src/lib/postprocess/html.test.ts
git commit -m "feat: extractHtmlContent + validateCmsArticles"
```

---

### Task 4: Datos y tipos de arquetipos (subconjunto para el slice)

**Files:**
- Create: `src/lib/config/arquetipos.ts`
- Test: `src/lib/config/arquetipos.test.ts`

**Interfaces:**
- Produces:
  - `export interface Arquetipo { code: string; name: string; description: string; tone: string; defaultLength: number; minLength: number; maxLength: number }`
  - `export const ARQUETIPOS: Arquetipo[]` — 3 entradas para el slice (ARQ-1, ARQ-4, ARQ-5).
  - `export function getArquetipo(code: string): Arquetipo | undefined`
  - `export function isValidArquetipo(code: string): boolean`
- Nota de alcance: la Fase 2 portará los 37 completos; aquí 3 bastan para validar la arquitectura.

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/config/arquetipos.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { ARQUETIPOS, getArquetipo, isValidArquetipo } from './arquetipos'

describe('arquetipos', () => {
  it('expone al menos 3 arquetipos con los campos requeridos', () => {
    expect(ARQUETIPOS.length).toBeGreaterThanOrEqual(3)
    for (const a of ARQUETIPOS) {
      expect(a.code).toMatch(/^ARQ-\d+$/)
      expect(a.name.length).toBeGreaterThan(0)
      expect(a.minLength).toBeLessThanOrEqual(a.defaultLength)
      expect(a.defaultLength).toBeLessThanOrEqual(a.maxLength)
    }
  })

  it('getArquetipo / isValidArquetipo resuelven por código', () => {
    expect(getArquetipo('ARQ-1')?.code).toBe('ARQ-1')
    expect(getArquetipo('ARQ-999')).toBeUndefined()
    expect(isValidArquetipo('ARQ-1')).toBe(true)
    expect(isValidArquetipo('nope')).toBe(false)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/config/arquetipos.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

Create `src/lib/config/arquetipos.ts`:

```ts
export interface Arquetipo {
  code: string
  name: string
  description: string
  tone: string
  defaultLength: number
  minLength: number
  maxLength: number
}

export const ARQUETIPOS: Arquetipo[] = [
  {
    code: 'ARQ-1',
    name: 'Artículos SEO con Enlaces Internos',
    description: 'Artículo optimizado para SEO con enlaces internos estratégicos.',
    tone: 'Informativo, profesional y orientado a la conversión',
    defaultLength: 1500,
    minLength: 1000,
    maxLength: 2500,
  },
  {
    code: 'ARQ-4',
    name: 'Review / Análisis de Producto',
    description: 'Análisis honesto de un producto con veredicto claro.',
    tone: 'Cercano, honesto y experto',
    defaultLength: 1800,
    minLength: 1500,
    maxLength: 3500,
  },
  {
    code: 'ARQ-5',
    name: 'Comparativa A vs B',
    description: 'Comparativa entre dos opciones con ganador declarado.',
    tone: 'Directo y resolutivo',
    defaultLength: 1600,
    minLength: 1200,
    maxLength: 2800,
  },
]

const BY_CODE = new Map(ARQUETIPOS.map((a) => [a.code, a]))

export function getArquetipo(code: string): Arquetipo | undefined {
  return BY_CODE.get(code)
}

export function isValidArquetipo(code: string): boolean {
  return BY_CODE.has(code)
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/config/arquetipos.test.ts`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/config/arquetipos.ts src/lib/config/arquetipos.test.ts
git commit -m "feat: arquetipos data subset + lookup helpers"
```

---

### Task 5: Constructores de prompts (etapas 1/2/3) mínimos

**Files:**
- Create: `src/lib/prompts/new-content.ts`
- Test: `src/lib/prompts/new-content.test.ts`

**Interfaces:**
- Consumes: `Arquetipo` (Task 4).
- Produces:
  - `export function getSystemPromptBase(): string`
  - `export function buildStage1Prompt(input: { keyword: string; arquetipo: Arquetipo; targetLength: number }): string`
  - `export function buildStage2Prompt(input: { draftHtml: string; keyword: string; targetLength: number }): string`
  - `export function buildStage3Prompt(input: { draftHtml: string; analysisFeedback: string; keyword: string; targetLength: number }): string`
- Cada prompt impone el contrato CMS y formato HTML sin fences. Usado por el pipeline (Task 8).

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/prompts/new-content.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  getSystemPromptBase,
  buildStage1Prompt,
  buildStage2Prompt,
  buildStage3Prompt,
} from './new-content'
import { getArquetipo } from '@/lib/config/arquetipos'

const arq = getArquetipo('ARQ-1')!

describe('prompts new-content', () => {
  it('el system prompt menciona PcComponentes y HTML sin markdown', () => {
    const s = getSystemPromptBase()
    expect(s).toMatch(/PcComponentes/)
    expect(s).toMatch(/HTML/)
  })

  it('stage 1 incluye keyword, arquetipo y las 3 clases CMS', () => {
    const p = buildStage1Prompt({ keyword: 'monitores gaming', arquetipo: arq, targetLength: 1500 })
    expect(p).toContain('monitores gaming')
    expect(p).toContain(arq.name)
    expect(p).toContain('contentGenerator__main')
    expect(p).toContain('contentGenerator__faqs')
    expect(p).toContain('contentGenerator__verdict')
    expect(p).toMatch(/1500/)
  })

  it('stage 2 pide JSON e incluye el borrador', () => {
    const p = buildStage2Prompt({ draftHtml: '<article>DRAFT</article>', keyword: 'kw', targetLength: 1500 })
    expect(p).toContain('DRAFT')
    expect(p.toUpperCase()).toContain('JSON')
  })

  it('stage 3 incluye borrador y feedback', () => {
    const p = buildStage3Prompt({ draftHtml: '<article>DRAFT</article>', analysisFeedback: 'FIX_THIS', keyword: 'kw', targetLength: 1500 })
    expect(p).toContain('DRAFT')
    expect(p).toContain('FIX_THIS')
    expect(p).toContain('contentGenerator__verdict')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/prompts/new-content.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

Create `src/lib/prompts/new-content.ts`:

```ts
import type { Arquetipo } from '@/lib/config/arquetipos'

const CMS_CONTRACT = `Estructura HTML OBLIGATORIA (no uses \`\`\`html ni markdown, solo HTML puro):
<style>/* CSS embebido */</style>
<article class="contentGenerator__main">
  <h2>Título con la keyword</h2>
  <!-- secciones con H3 y párrafos -->
</article>
<article class="contentGenerator__faqs">
  <h2>Preguntas frecuentes</h2>
</article>
<article class="contentGenerator__verdict">
  <div class="verdict-box"><h2>Nuestro veredicto</h2></div>
</article>`

export function getSystemPromptBase(): string {
  return `Eres un redactor SEO experto de PcComponentes, la tienda líder de tecnología en España.
Tono: experto que ayuda, cercano y honesto. Orienta siempre hacia soluciones.
PROHIBIDO: "en el mundo actual", "sin lugar a dudas", "es importante destacar".
FORMATO: genera HTML puro, NUNCA uses \`\`\`html ni marcadores markdown.`
}

export function buildStage1Prompt(input: {
  keyword: string
  arquetipo: Arquetipo
  targetLength: number
}): string {
  const { keyword, arquetipo, targetLength } = input
  return `# TAREA
Genera un BORRADOR tipo "${arquetipo.name}" para la keyword "${keyword}".
Descripción del arquetipo: ${arquetipo.description}
Tono: ${arquetipo.tone}
Longitud objetivo: ~${targetLength} palabras.

${CMS_CONTRACT}`
}

export function buildStage2Prompt(input: {
  draftHtml: string
  keyword: string
  targetLength: number
}): string {
  const { draftHtml, keyword, targetLength } = input
  return `# ANÁLISIS CRÍTICO
Analiza el siguiente borrador HTML para la keyword "${keyword}" (objetivo ~${targetLength} palabras).
Devuelve SOLO un JSON (sin markdown) con esta forma:
{"problemas": [{"tipo": "...", "severidad": "...", "descripcion": "...", "solucion": "..."}],
 "puntuacion_general": 0,
 "recomendacion_principal": "..."}

Verifica: estructura CMS (3 articles), keyword en H2 y primeras 100 palabras, tono anti-IA.

BORRADOR:
${draftHtml}`
}

export function buildStage3Prompt(input: {
  draftHtml: string
  analysisFeedback: string
  keyword: string
  targetLength: number
}): string {
  const { draftHtml, analysisFeedback, keyword, targetLength } = input
  return `# VERSIÓN FINAL
Reescribe el borrador aplicando TODAS las correcciones del análisis. Keyword: "${keyword}". Objetivo ~${targetLength} palabras.

ANÁLISIS Y CORRECCIONES A APLICAR:
${analysisFeedback}

BORRADOR:
${draftHtml}

${CMS_CONTRACT}`
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/prompts/new-content.test.ts`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/prompts/new-content.ts src/lib/prompts/new-content.test.ts
git commit -m "feat: minimal stage1/2/3 prompt builders with CMS contract"
```

---

### Task 6: Cliente Anthropic con umbral de streaming

**Files:**
- Create: `src/lib/clients/anthropic.ts`
- Test: `src/lib/clients/anthropic.test.ts`

**Interfaces:**
- Produces:
  - `export interface GenerateResult { text: string; stopReason: string | null }`
  - `export interface AnthropicLike { messages: { create: Function; stream: Function } }`
  - `export const NONSTREAMING_MAX_TOKENS = 21333`
  - `export async function generate(client: AnthropicLike, params: { model: string; system: string; prompt: string; maxTokens: number; temperature?: number }): Promise<GenerateResult>` — usa `.create` si `maxTokens <= 21333`, si no `.stream().finalMessage()`. Extrae texto de los bloques `type==='text'`.
- El cliente se inyecta (no se construye dentro) para testear sin red. Una fábrica `createAnthropicClient()` construye el real desde env (no se testea con red).

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/clients/anthropic.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { generate, NONSTREAMING_MAX_TOKENS } from './anthropic'

function fakeMessage(text: string, stopReason = 'end_turn') {
  return { content: [{ type: 'text', text }], stop_reason: stopReason }
}

describe('generate', () => {
  it('usa messages.create por debajo del umbral de streaming', async () => {
    const create = vi.fn().mockResolvedValue(fakeMessage('hola'))
    const stream = vi.fn()
    const client = { messages: { create, stream } }
    const res = await generate(client, { model: 'm', system: 's', prompt: 'p', maxTokens: 8000 })
    expect(res.text).toBe('hola')
    expect(res.stopReason).toBe('end_turn')
    expect(create).toHaveBeenCalledOnce()
    expect(stream).not.toHaveBeenCalled()
  })

  it('usa messages.stream por encima del umbral', async () => {
    const create = vi.fn()
    const stream = vi.fn().mockReturnValue({
      finalMessage: () => Promise.resolve(fakeMessage('largo', 'end_turn')),
    })
    const client = { messages: { create, stream } }
    const res = await generate(client, { model: 'm', system: 's', prompt: 'p', maxTokens: NONSTREAMING_MAX_TOKENS + 1 })
    expect(res.text).toBe('largo')
    expect(stream).toHaveBeenCalledOnce()
    expect(create).not.toHaveBeenCalled()
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/clients/anthropic.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

Create `src/lib/clients/anthropic.ts`:

```ts
import Anthropic from '@anthropic-ai/sdk'

export const NONSTREAMING_MAX_TOKENS = 21333

export interface GenerateResult {
  text: string
  stopReason: string | null
}

// Forma mínima que necesitamos del SDK; permite inyectar un fake en tests.
export interface AnthropicLike {
  messages: {
    create: (...args: unknown[]) => Promise<unknown>
    stream: (...args: unknown[]) => { finalMessage: () => Promise<unknown> }
  }
}

interface RawMessage {
  content?: Array<{ type?: string; text?: string }>
  stop_reason?: string | null
}

function extractText(msg: RawMessage): GenerateResult {
  const text = (msg.content ?? [])
    .filter((b) => b.type === 'text' && typeof b.text === 'string')
    .map((b) => b.text as string)
    .join('')
  return { text, stopReason: msg.stop_reason ?? null }
}

export async function generate(
  client: AnthropicLike,
  params: { model: string; system: string; prompt: string; maxTokens: number; temperature?: number },
): Promise<GenerateResult> {
  const body = {
    model: params.model,
    max_tokens: params.maxTokens,
    temperature: params.temperature ?? 0.7,
    system: params.system,
    messages: [{ role: 'user', content: params.prompt }],
  }

  if (params.maxTokens > NONSTREAMING_MAX_TOKENS) {
    const stream = client.messages.stream(body)
    const msg = (await stream.finalMessage()) as RawMessage
    return extractText(msg)
  }

  const msg = (await client.messages.create(body)) as RawMessage
  return extractText(msg)
}

export function createAnthropicClient(): AnthropicLike {
  const apiKey = process.env.ANTHROPIC_API_KEY
  if (!apiKey) throw new Error('ANTHROPIC_API_KEY no está definida')
  return new Anthropic({ apiKey }) as unknown as AnthropicLike
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/clients/anthropic.test.ts`
Expected: PASS (2 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/clients/anthropic.ts src/lib/clients/anthropic.test.ts
git commit -m "feat: anthropic generate() with streaming threshold + injectable client"
```

---

### Task 7: Análisis secundario OpenAI + merge dual

**Files:**
- Create: `src/lib/clients/dual-analysis.ts`
- Test: `src/lib/clients/dual-analysis.test.ts`

**Interfaces:**
- Produces:
  - `export interface Analysis { raw: string; provider: 'claude' | 'openai' | 'haiku' }`
  - `export function mergeDualAnalyses(primary: string, secondary: string | null, secondaryProvider: 'openai' | 'haiku' | null): string` — concatena ambos análisis etiquetados; si `secondary` es null devuelve solo el primario etiquetado. Función pura.
  - `export interface OpenAiLike { chat: { completions: { create: Function } } }`
  - `export async function generateOpenAiAnalysis(client: OpenAiLike, params: { model: string; prompt: string; maxTokens: number }): Promise<string>`
- Usado por el pipeline (Task 8) en Stage 2.

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/clients/dual-analysis.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { mergeDualAnalyses, generateOpenAiAnalysis } from './dual-analysis'

describe('mergeDualAnalyses', () => {
  it('fusiona ambos análisis etiquetados', () => {
    const merged = mergeDualAnalyses('PRIMARIO', 'SECUNDARIO', 'openai')
    expect(merged).toContain('PRIMARIO')
    expect(merged).toContain('SECUNDARIO')
    expect(merged.toLowerCase()).toContain('openai')
  })

  it('si no hay secundario, devuelve solo el primario', () => {
    const merged = mergeDualAnalyses('PRIMARIO', null, null)
    expect(merged).toContain('PRIMARIO')
    expect(merged).not.toContain('SECUNDARIO')
  })
})

describe('generateOpenAiAnalysis', () => {
  it('extrae el contenido del mensaje', async () => {
    const create = vi.fn().mockResolvedValue({
      choices: [{ message: { content: 'ANALISIS_OPENAI' } }],
    })
    const client = { chat: { completions: { create } } }
    const out = await generateOpenAiAnalysis(client, { model: 'gpt', prompt: 'p', maxTokens: 4000 })
    expect(out).toBe('ANALISIS_OPENAI')
    expect(create).toHaveBeenCalledOnce()
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/clients/dual-analysis.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

Create `src/lib/clients/dual-analysis.ts`:

```ts
import OpenAI from 'openai'

export interface OpenAiLike {
  chat: {
    completions: {
      create: (...args: unknown[]) => Promise<unknown>
    }
  }
}

interface ChatCompletion {
  choices?: Array<{ message?: { content?: string | null } }>
}

const SECONDARY_SYSTEM = 'Eres un editor SEO experto. Analiza el borrador y devuelve un JSON con problemas y puntuación.'

export async function generateOpenAiAnalysis(
  client: OpenAiLike,
  params: { model: string; prompt: string; maxTokens: number },
): Promise<string> {
  const res = (await client.chat.completions.create({
    model: params.model,
    max_tokens: params.maxTokens,
    temperature: 0.4,
    messages: [
      { role: 'system', content: SECONDARY_SYSTEM },
      { role: 'user', content: params.prompt },
    ],
  })) as ChatCompletion
  return res.choices?.[0]?.message?.content ?? ''
}

export function mergeDualAnalyses(
  primary: string,
  secondary: string | null,
  secondaryProvider: 'openai' | 'haiku' | null,
): string {
  const parts = [`## Análisis principal (Claude)\n${primary}`]
  if (secondary && secondaryProvider) {
    parts.push(`## Análisis secundario (${secondaryProvider})\n${secondary}`)
  }
  return parts.join('\n\n')
}

export function createOpenAiClient(): OpenAiLike | null {
  const apiKey = process.env.OPENAI_API_KEY
  if (!apiKey) return null
  return new OpenAI({ apiKey }) as unknown as OpenAiLike
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/clients/dual-analysis.test.ts`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/clients/dual-analysis.ts src/lib/clients/dual-analysis.test.ts
git commit -m "feat: openai secondary analysis + pure mergeDualAnalyses"
```

---

### Task 8: Orquestador del pipeline (3 etapas + dual + post-proceso)

**Files:**
- Create: `src/lib/pipeline/run-new-content.ts`
- Test: `src/lib/pipeline/run-new-content.test.ts`

**Interfaces:**
- Consumes: `generate` + `AnthropicLike` (Task 6), `generateOpenAiAnalysis` + `mergeDualAnalyses` + `OpenAiLike` (Task 7), prompts (Task 5), `computeMaxTokens` (Task 2), `extractHtmlContent` + `validateCmsArticles` (Task 3), `getArquetipo` (Task 4).
- Produces:
  - `export type PipelineEvent = { type: 'stage'; stage: number; label: string } | { type: 'done'; html: string; analysis: string; cms: import('@/lib/postprocess/html').CmsValidation } | { type: 'error'; message: string }`
  - `export interface PipelineDeps { anthropic: AnthropicLike; openai: OpenAiLike | null; claudeModel: string; fallbackModel: string; openaiModel: string; ceiling: number }`
  - `export async function runNewContentPipeline(input: { keyword: string; arquetipoCode: string; targetLength: number }, deps: PipelineDeps, emit: (e: PipelineEvent) => void): Promise<void>`
- Orquesta: Stage 1 (genera draft, extrae HTML) → Stage 2 (análisis Claude + secundario OpenAI si hay, merge) → Stage 3 (final, extrae HTML) → valida CMS → emite `done`. Emite un `stage` antes de cada etapa. Captura errores → emite `error`.

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/pipeline/run-new-content.test.ts`:

```ts
import { describe, it, expect, vi } from 'vitest'
import { runNewContentPipeline, type PipelineEvent } from './run-new-content'
import type { AnthropicLike } from '@/lib/clients/anthropic'
import type { OpenAiLike } from '@/lib/clients/dual-analysis'

const VALID_HTML = `<article class="contentGenerator__main"><h2>T</h2></article>
<article class="contentGenerator__faqs"><h2>F</h2></article>
<article class="contentGenerator__verdict"><h2>V</h2></article>`

function anthropicReturning(...texts: string[]): AnthropicLike {
  let i = 0
  const msg = (text: string) => ({ content: [{ type: 'text', text }], stop_reason: 'end_turn' })
  const create = vi.fn().mockImplementation(() => Promise.resolve(msg(texts[i++] ?? '')))
  return { messages: { create, stream: vi.fn() } }
}

const deps = (anthropic: AnthropicLike, openai: OpenAiLike | null) => ({
  anthropic, openai,
  claudeModel: 'claude-sonnet-4-6', fallbackModel: 'claude-haiku-4-5',
  openaiModel: 'gpt-4.1-2025-04-14', ceiling: 32000,
})

describe('runNewContentPipeline', () => {
  it('emite stages y un done con HTML CMS válido (sin OpenAI → fallback Haiku)', async () => {
    // Stage1 draft, Stage2 análisis Claude, Stage2 fallback Haiku, Stage3 final
    const anthropic = anthropicReturning('```html\n' + VALID_HTML + '\n```', '{"puntuacion_general":80}', 'ANALISIS_HAIKU', VALID_HTML)
    const events: PipelineEvent[] = []
    await runNewContentPipeline(
      { keyword: 'kw', arquetipoCode: 'ARQ-1', targetLength: 1500 },
      deps(anthropic, null),
      (e) => events.push(e),
    )
    const done = events.find((e) => e.type === 'done')
    expect(done).toBeDefined()
    if (done && done.type === 'done') {
      expect(done.cms.allPresent).toBe(true)
      expect(done.html).toContain('contentGenerator__main')
    }
    expect(events.filter((e) => e.type === 'stage').length).toBe(3)
  })

  it('usa OpenAI como secundario cuando está presente', async () => {
    const anthropic = anthropicReturning(VALID_HTML, '{"puntuacion_general":70}', VALID_HTML)
    const oaCreate = vi.fn().mockResolvedValue({ choices: [{ message: { content: 'ANALISIS_OPENAI' } }] })
    const openai = { chat: { completions: { create: oaCreate } } }
    const events: PipelineEvent[] = []
    await runNewContentPipeline(
      { keyword: 'kw', arquetipoCode: 'ARQ-1', targetLength: 1500 },
      deps(anthropic, openai),
      (e) => events.push(e),
    )
    expect(oaCreate).toHaveBeenCalledOnce()
    expect(events.some((e) => e.type === 'done')).toBe(true)
  })

  it('emite error si el arquetipo no existe', async () => {
    const anthropic = anthropicReturning(VALID_HTML)
    const events: PipelineEvent[] = []
    await runNewContentPipeline(
      { keyword: 'kw', arquetipoCode: 'ARQ-999', targetLength: 1500 },
      deps(anthropic, null),
      (e) => events.push(e),
    )
    expect(events.some((e) => e.type === 'error')).toBe(true)
    expect(events.some((e) => e.type === 'done')).toBe(false)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/pipeline/run-new-content.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación mínima**

Create `src/lib/pipeline/run-new-content.ts`:

```ts
import { generate, type AnthropicLike } from '@/lib/clients/anthropic'
import {
  generateOpenAiAnalysis,
  mergeDualAnalyses,
  type OpenAiLike,
} from '@/lib/clients/dual-analysis'
import {
  getSystemPromptBase,
  buildStage1Prompt,
  buildStage2Prompt,
  buildStage3Prompt,
} from '@/lib/prompts/new-content'
import { computeMaxTokens } from '@/lib/token-budget'
import { extractHtmlContent, validateCmsArticles, type CmsValidation } from '@/lib/postprocess/html'
import { getArquetipo } from '@/lib/config/arquetipos'

export type PipelineEvent =
  | { type: 'stage'; stage: number; label: string }
  | { type: 'done'; html: string; analysis: string; cms: CmsValidation }
  | { type: 'error'; message: string }

export interface PipelineDeps {
  anthropic: AnthropicLike
  openai: OpenAiLike | null
  claudeModel: string
  fallbackModel: string
  openaiModel: string
  ceiling: number
}

export async function runNewContentPipeline(
  input: { keyword: string; arquetipoCode: string; targetLength: number },
  deps: PipelineDeps,
  emit: (e: PipelineEvent) => void,
): Promise<void> {
  try {
    const arquetipo = getArquetipo(input.arquetipoCode)
    if (!arquetipo) throw new Error(`Arquetipo desconocido: ${input.arquetipoCode}`)

    const system = getSystemPromptBase()
    const { keyword, targetLength } = input

    // Stage 1 — borrador
    emit({ type: 'stage', stage: 1, label: 'Generando borrador' })
    const s1 = await generate(deps.anthropic, {
      model: deps.claudeModel,
      system,
      prompt: buildStage1Prompt({ keyword, arquetipo, targetLength }),
      maxTokens: computeMaxTokens(targetLength, 1, deps.ceiling),
    })
    const draftHtml = extractHtmlContent(s1.text)

    // Stage 2 — análisis dual
    emit({ type: 'stage', stage: 2, label: 'Análisis dual' })
    const stage2Prompt = buildStage2Prompt({ draftHtml, keyword, targetLength })
    const stage2Budget = computeMaxTokens(targetLength, 2, deps.ceiling)
    const primary = await generate(deps.anthropic, {
      model: deps.claudeModel,
      system,
      prompt: stage2Prompt,
      maxTokens: stage2Budget,
      temperature: 0.4,
    })

    let secondary: string | null = null
    let secondaryProvider: 'openai' | 'haiku' | null = null
    if (deps.openai) {
      secondary = await generateOpenAiAnalysis(deps.openai, {
        model: deps.openaiModel,
        prompt: stage2Prompt,
        maxTokens: stage2Budget,
      })
      secondaryProvider = 'openai'
    } else {
      const fb = await generate(deps.anthropic, {
        model: deps.fallbackModel,
        system,
        prompt: stage2Prompt,
        maxTokens: stage2Budget,
        temperature: 0.4,
      })
      secondary = fb.text
      secondaryProvider = 'haiku'
    }
    const analysis = mergeDualAnalyses(primary.text, secondary, secondaryProvider)

    // Stage 3 — final
    emit({ type: 'stage', stage: 3, label: 'Versión final' })
    const s3 = await generate(deps.anthropic, {
      model: deps.claudeModel,
      system,
      prompt: buildStage3Prompt({ draftHtml, analysisFeedback: analysis, keyword, targetLength }),
      maxTokens: computeMaxTokens(targetLength, 3, deps.ceiling),
    })
    const finalHtml = extractHtmlContent(s3.text)
    const cms = validateCmsArticles(finalHtml)

    emit({ type: 'done', html: finalHtml, analysis, cms })
  } catch (err) {
    emit({ type: 'error', message: err instanceof Error ? err.message : String(err) })
  }
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/pipeline/run-new-content.test.ts`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/pipeline/run-new-content.ts src/lib/pipeline/run-new-content.test.ts
git commit -m "feat: new-content pipeline orchestrator with dual analysis + CMS validation"
```

---

### Task 9: Route Handler con streaming SSE

**Files:**
- Create: `src/lib/sse.ts`
- Test: `src/lib/sse.test.ts`
- Create: `src/app/api/generate/route.ts`

**Interfaces:**
- Consumes: `runNewContentPipeline` + `PipelineEvent` (Task 8), `createAnthropicClient` (Task 6), `createOpenAiClient` (Task 7).
- Produces:
  - `export function encodeSseEvent(event: unknown): string` — formato `data: <json>\n\n`.
  - `POST /api/generate` — recibe `{ keyword, arquetipoCode, targetLength }`, devuelve un `ReadableStream` de SSE emitiendo los `PipelineEvent`. `runtime = 'nodejs'`, `dynamic = 'force-dynamic'`.

- [ ] **Step 1: Escribir el test que falla (encoder SSE)**

Create `src/lib/sse.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { encodeSseEvent } from './sse'

describe('encodeSseEvent', () => {
  it('serializa a formato SSE data: <json>\\n\\n', () => {
    const out = encodeSseEvent({ type: 'stage', stage: 1 })
    expect(out).toBe('data: {"type":"stage","stage":1}\n\n')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/sse.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementación del encoder**

Create `src/lib/sse.ts`:

```ts
export function encodeSseEvent(event: unknown): string {
  return `data: ${JSON.stringify(event)}\n\n`
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/sse.test.ts`
Expected: PASS (1 passed).

- [ ] **Step 5: Implementar el Route Handler**

Create `src/app/api/generate/route.ts`:

```ts
import { runNewContentPipeline, type PipelineEvent } from '@/lib/pipeline/run-new-content'
import { createAnthropicClient } from '@/lib/clients/anthropic'
import { createOpenAiClient } from '@/lib/clients/dual-analysis'
import { encodeSseEvent } from '@/lib/sse'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function POST(req: Request) {
  const body = await req.json()
  const keyword = String(body.keyword ?? '').trim()
  const arquetipoCode = String(body.arquetipoCode ?? '')
  const targetLength = Number(body.targetLength ?? 1500)

  const encoder = new TextEncoder()
  const stream = new ReadableStream({
    async start(controller) {
      const emit = (e: PipelineEvent) => {
        controller.enqueue(encoder.encode(encodeSseEvent(e)))
      }
      try {
        if (keyword.length < 2) {
          emit({ type: 'error', message: 'La keyword debe tener al menos 2 caracteres.' })
          return
        }
        const deps = {
          anthropic: createAnthropicClient(),
          openai: createOpenAiClient(),
          claudeModel: process.env.CLAUDE_MODEL ?? 'claude-sonnet-4-6',
          fallbackModel: process.env.DUAL_FALLBACK_MODEL ?? 'claude-haiku-4-5',
          openaiModel: process.env.OPENAI_MODEL ?? 'gpt-4.1-2025-04-14',
          ceiling: Number(process.env.MAX_TOKENS ?? 32000),
        }
        await runNewContentPipeline({ keyword, arquetipoCode, targetLength }, deps, emit)
      } catch (err) {
        emit({ type: 'error', message: err instanceof Error ? err.message : String(err) })
      } finally {
        controller.close()
      }
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
    },
  })
}
```

- [ ] **Step 6: Verificar compilación de tipos**

Run: `npx tsc --noEmit`
Expected: sin errores de tipo.

- [ ] **Step 7: Commit**

```bash
git add src/lib/sse.ts src/lib/sse.test.ts src/app/api/generate/route.ts
git commit -m "feat: SSE encoder + /api/generate streaming route handler"
```

---

### Task 10: Store Zustand + formulario mínimo

**Files:**
- Create: `src/store/generation.ts`
- Test: `src/store/generation.test.ts`
- Create: `src/components/GenerationForm.tsx`
- Test: `src/components/GenerationForm.test.tsx`

**Interfaces:**
- Consumes: `ARQUETIPOS` + `getArquetipo` (Task 4).
- Produces:
  - `src/store/generation.ts`: `export interface GenerationState { keyword: string; arquetipoCode: string; targetLength: number; status: 'idle'|'running'|'done'|'error'; stageLabel: string; html: string; analysis: string; error: string; setField; reset; }` (Zustand).
  - `src/components/GenerationForm.tsx`: componente cliente con inputs de keyword, select de arquetipo, slider/number de longitud y un botón "Generar" (deshabilitado si keyword < 2 chars o `status==='running'`). Llama a una prop `onSubmit`.

- [ ] **Step 1: Escribir el test del store que falla**

Create `src/store/generation.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { useGenerationStore } from './generation'

describe('generation store', () => {
  it('setField actualiza y reset limpia el resultado', () => {
    const s = useGenerationStore.getState()
    s.setField('keyword', 'monitores')
    expect(useGenerationStore.getState().keyword).toBe('monitores')
    useGenerationStore.getState().setField('html', '<p>x</p>')
    useGenerationStore.getState().reset()
    expect(useGenerationStore.getState().html).toBe('')
    expect(useGenerationStore.getState().status).toBe('idle')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/store/generation.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar el store**

Create `src/store/generation.ts`:

```ts
import { create } from 'zustand'

export type GenStatus = 'idle' | 'running' | 'done' | 'error'

export interface GenerationState {
  keyword: string
  arquetipoCode: string
  targetLength: number
  status: GenStatus
  stageLabel: string
  html: string
  analysis: string
  error: string
  setField: <K extends keyof GenerationState>(key: K, value: GenerationState[K]) => void
  reset: () => void
}

const RESULT_DEFAULTS = {
  status: 'idle' as GenStatus,
  stageLabel: '',
  html: '',
  analysis: '',
  error: '',
}

export const useGenerationStore = create<GenerationState>((set) => ({
  keyword: '',
  arquetipoCode: 'ARQ-1',
  targetLength: 1500,
  ...RESULT_DEFAULTS,
  setField: (key, value) => set({ [key]: value } as Partial<GenerationState>),
  reset: () => set({ ...RESULT_DEFAULTS }),
}))
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/store/generation.test.ts`
Expected: PASS (1 passed).

- [ ] **Step 5: Escribir el test del formulario que falla**

Create `src/components/GenerationForm.test.tsx`:

```tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { GenerationForm } from './GenerationForm'

describe('GenerationForm', () => {
  it('deshabilita Generar con keyword corta y lo habilita al escribir', () => {
    render(<GenerationForm onSubmit={vi.fn()} status="idle" />)
    const btn = screen.getByRole('button', { name: /generar/i })
    expect(btn).toBeDisabled()
    fireEvent.change(screen.getByLabelText(/keyword/i), { target: { value: 'monitores gaming' } })
    expect(btn).toBeEnabled()
  })

  it('invoca onSubmit con los valores del formulario', () => {
    const onSubmit = vi.fn()
    render(<GenerationForm onSubmit={onSubmit} status="idle" />)
    fireEvent.change(screen.getByLabelText(/keyword/i), { target: { value: 'monitores' } })
    fireEvent.click(screen.getByRole('button', { name: /generar/i }))
    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ keyword: 'monitores', arquetipoCode: expect.any(String), targetLength: expect.any(Number) }),
    )
  })
})
```

- [ ] **Step 6: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/components/GenerationForm.test.tsx`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 7: Implementar el formulario**

Create `src/components/GenerationForm.tsx`:

```tsx
'use client'

import { useState } from 'react'
import { ARQUETIPOS } from '@/lib/config/arquetipos'

export interface GenerationInput {
  keyword: string
  arquetipoCode: string
  targetLength: number
}

export function GenerationForm(props: {
  onSubmit: (input: GenerationInput) => void
  status: 'idle' | 'running' | 'done' | 'error'
}) {
  const [keyword, setKeyword] = useState('')
  const [arquetipoCode, setArquetipoCode] = useState(ARQUETIPOS[0].code)
  const [targetLength, setTargetLength] = useState(1500)

  const disabled = keyword.trim().length < 2 || props.status === 'running'

  return (
    <form
      className="flex flex-col gap-4 max-w-xl"
      onSubmit={(e) => {
        e.preventDefault()
        props.onSubmit({ keyword: keyword.trim(), arquetipoCode, targetLength })
      }}
    >
      <label className="flex flex-col gap-1">
        <span>Keyword</span>
        <input
          className="border rounded px-3 py-2"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="p.ej. mejores monitores gaming"
        />
      </label>

      <label className="flex flex-col gap-1">
        <span>Arquetipo</span>
        <select
          className="border rounded px-3 py-2"
          value={arquetipoCode}
          onChange={(e) => setArquetipoCode(e.target.value)}
        >
          {ARQUETIPOS.map((a) => (
            <option key={a.code} value={a.code}>
              {a.code} — {a.name}
            </option>
          ))}
        </select>
      </label>

      <label className="flex flex-col gap-1">
        <span>Longitud objetivo: {targetLength} palabras</span>
        <input
          type="range"
          min={500}
          max={5000}
          step={100}
          value={targetLength}
          onChange={(e) => setTargetLength(Number(e.target.value))}
        />
      </label>

      <button
        type="submit"
        disabled={disabled}
        className="bg-black text-white rounded px-4 py-2 disabled:opacity-40"
      >
        {props.status === 'running' ? 'Generando…' : 'Generar'}
      </button>
    </form>
  )
}
```

- [ ] **Step 8: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/components/GenerationForm.test.tsx`
Expected: PASS (2 passed).

- [ ] **Step 9: Commit**

```bash
git add src/store/generation.ts src/store/generation.test.ts src/components/GenerationForm.tsx src/components/GenerationForm.test.tsx
git commit -m "feat: zustand store + minimal generation form"
```

---

### Task 11: Consumo del stream SSE + vista de resultados + descarga

**Files:**
- Create: `src/lib/sse-parse.ts`
- Test: `src/lib/sse-parse.test.ts`
- Create: `src/components/ResultView.tsx`
- Create: `src/app/page.tsx` (reemplaza el placeholder de create-next-app)

**Interfaces:**
- Consumes: store (Task 10), `GenerationForm` (Task 10), `PipelineEvent` (Task 8).
- Produces:
  - `export function parseSseChunk(buffer: string): { events: unknown[]; rest: string }` — separa eventos `data: ...\n\n` de un buffer parcial, devolviendo el remanente sin terminar. Función pura.
  - `src/components/ResultView.tsx`: muestra stage actual, error, render del HTML (vía `iframe srcDoc`), bloque de análisis y botón de descarga `.html`.
  - `src/app/page.tsx`: página cliente que cablea el formulario → fetch a `/api/generate` → consume el stream → actualiza el store → renderiza `ResultView`.

- [ ] **Step 1: Escribir el test del parser SSE que falla**

Create `src/lib/sse-parse.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { parseSseChunk } from './sse-parse'

describe('parseSseChunk', () => {
  it('extrae eventos completos y conserva el remanente parcial', () => {
    const buf = 'data: {"type":"stage","stage":1}\n\ndata: {"type":"done"}\n\ndata: {"type":"par'
    const { events, rest } = parseSseChunk(buf)
    expect(events).toEqual([{ type: 'stage', stage: 1 }, { type: 'done' }])
    expect(rest).toBe('data: {"type":"par')
  })

  it('sin eventos completos devuelve todo como remanente', () => {
    const { events, rest } = parseSseChunk('data: {"ty')
    expect(events).toEqual([])
    expect(rest).toBe('data: {"ty')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/sse-parse.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar el parser**

Create `src/lib/sse-parse.ts`:

```ts
export function parseSseChunk(buffer: string): { events: unknown[]; rest: string } {
  const parts = buffer.split('\n\n')
  const rest = parts.pop() ?? ''
  const events: unknown[] = []
  for (const part of parts) {
    const line = part.trim()
    if (!line.startsWith('data:')) continue
    const json = line.slice('data:'.length).trim()
    if (json) events.push(JSON.parse(json))
  }
  return { events, rest }
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/sse-parse.test.ts`
Expected: PASS (2 passed).

- [ ] **Step 5: Implementar la vista de resultados**

Create `src/components/ResultView.tsx`:

```tsx
'use client'

import { useGenerationStore } from '@/store/generation'

export function ResultView() {
  const { status, stageLabel, html, analysis, error } = useGenerationStore()

  if (status === 'idle') return null

  if (status === 'error') {
    return <p className="text-red-600">Error: {error}</p>
  }

  return (
    <div className="flex flex-col gap-4">
      {status === 'running' && <p className="animate-pulse">⏳ {stageLabel}…</p>}

      {status === 'done' && html && (
        <>
          <div className="flex gap-3 items-center">
            <button
              className="bg-black text-white rounded px-4 py-2"
              onClick={() => {
                const blob = new Blob([html], { type: 'text/html' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = 'contenido.html'
                a.click()
                URL.revokeObjectURL(url)
              }}
            >
              Descargar HTML
            </button>
          </div>
          <iframe title="preview" className="w-full h-[600px] border rounded" srcDoc={html} />
          <details>
            <summary className="cursor-pointer">Ver análisis</summary>
            <pre className="whitespace-pre-wrap text-sm bg-gray-50 p-3 rounded">{analysis}</pre>
          </details>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 6: Implementar la página que cablea todo**

Replace `src/app/page.tsx` with:

```tsx
'use client'

import { GenerationForm, type GenerationInput } from '@/components/GenerationForm'
import { ResultView } from '@/components/ResultView'
import { useGenerationStore } from '@/store/generation'
import { parseSseChunk } from '@/lib/sse-parse'

export default function Home() {
  const store = useGenerationStore()

  async function handleSubmit(input: GenerationInput) {
    store.reset()
    store.setField('status', 'running')
    store.setField('stageLabel', 'Iniciando')

    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(input),
    })
    if (!res.body) {
      store.setField('status', 'error')
      store.setField('error', 'Sin respuesta del servidor')
      return
    }

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const { events, rest } = parseSseChunk(buffer)
      buffer = rest
      for (const e of events as Array<Record<string, unknown>>) {
        if (e.type === 'stage') store.setField('stageLabel', String(e.label))
        else if (e.type === 'error') {
          store.setField('status', 'error')
          store.setField('error', String(e.message))
        } else if (e.type === 'done') {
          store.setField('html', String(e.html))
          store.setField('analysis', String(e.analysis))
          store.setField('status', 'done')
        }
      }
    }
  }

  return (
    <main className="max-w-4xl mx-auto p-8 flex flex-col gap-8">
      <h1 className="text-2xl font-bold">Raichu — Modo Nuevo (Next.js)</h1>
      <GenerationForm onSubmit={handleSubmit} status={store.status} />
      <ResultView />
    </main>
  )
}
```

- [ ] **Step 7: Verificar tests, tipos y build**

Run:

```bash
npm test
npx tsc --noEmit
npm run build
```

Expected: todos los tests pasan; sin errores de tipo; build OK.

- [ ] **Step 8: Commit**

```bash
git add src/lib/sse-parse.ts src/lib/sse-parse.test.ts src/components/ResultView.tsx src/app/page.tsx
git commit -m "feat: SSE stream consumption, result view with download, wired page"
```

---

### Task 12: README, env y verificación manual end-to-end

**Files:**
- Create: `../raichu-next/README.md`
- Verify: `.env.local` (no se commitea; ya en `.gitignore` de create-next-app)

**Interfaces:**
- Produces: documentación de handoff para Labs (setup, env, dev, build, despliegue como contenedor Node).

- [ ] **Step 1: Escribir el README**

Create `README.md`:

```markdown
# Raichu Next — Modo Nuevo (piloto de migración a Next.js)

Reescritura del modo "Nuevo" de Raichu (originalmente Streamlit/Python) a Next.js/TypeScript.
Fase 1: vertical slice (keyword + arquetipo + longitud → pipeline 3 etapas con corrección dual → HTML CMS + descarga).

## Requisitos
- Node.js 20+
- Claves de API: Anthropic (obligatoria) y OpenAI (opcional; sin ella, el análisis secundario usa Claude Haiku).

## Setup
```bash
npm install
cp .env.example .env.local   # rellenar ANTHROPIC_API_KEY (y OPENAI_API_KEY si se quiere)
npm run dev                  # http://localhost:3000
```

## Variables de entorno
| Var | Obligatoria | Default | Descripción |
|-----|-------------|---------|-------------|
| `ANTHROPIC_API_KEY` | Sí | — | Clave de Anthropic (solo server-side) |
| `OPENAI_API_KEY` | No | — | Habilita el análisis secundario cross-vendor en Stage 2 |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` | Modelo principal. Opción más capaz: `claude-opus-4-8` |
| `DUAL_FALLBACK_MODEL` | No | `claude-haiku-4-5` | Secundario cuando no hay OpenAI |
| `OPENAI_MODEL` | No | `gpt-4.1-2025-04-14` | Modelo del análisis secundario |
| `MAX_TOKENS` | No | `32000` | Techo de tokens de salida (clamp) |

## Comandos
```bash
npm run dev      # desarrollo
npm test         # tests (Vitest)
npm run build    # build de producción (output: standalone)
npm start        # servir el build
```

## Despliegue (entorno privado de Labs)
El proyecto usa `output: 'standalone'`. Desplegar como **servidor Node de larga duración** (contenedor), NO como función serverless (el pipeline puede tardar minutos y usa streaming):
```bash
npm run build
node .next/standalone/server.js   # servir; copiar .next/static y public junto al standalone
```
Definir las variables de entorno en el contenedor. El endpoint `/api/generate` corre en runtime Node y emite SSE.

## Alcance
Fase 1 = solo modo Nuevo, vertical slice. Fases siguientes (su propio plan): paridad de inputs (37 arquetipos, visuales, brief I/O, productos), post-proceso completo (scrub, tablas, CSS, quality loop, meta), imágenes y JSON-LD.
```

- [ ] **Step 2: Verificación manual end-to-end (con keys reales)**

Con `.env.local` relleno:

```bash
npm run dev
```

En el navegador (http://localhost:3000): escribir una keyword (≥2 chars), elegir arquetipo, pulsar "Generar". Verificar:
1. Aparece el progreso por etapa (Generando borrador → Análisis dual → Versión final).
2. Al terminar, el `iframe` muestra el HTML y existe el botón "Descargar HTML".
3. El HTML descargado contiene los 3 `<article>` `contentGenerator__*`.

Si no hay keys disponibles en el momento de implementar, dejar constancia explícita de que la verificación de red queda pendiente (los tests unitarios sí pasan sin keys).

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, env, and container deployment notes"
```

---

## Notas de cierre de fase

Al terminar las 12 tareas, la Fase 1 entrega un proyecto Next.js autocontenido que valida toda la arquitectura (UI → SSE → pipeline server-side 3 etapas con corrección dual → CMS válido → descarga), con tests de la lógica pura que pasan sin red. Las Fases 2–4 del spec (`docs/superpowers/specs/2026-06-25-raichu-nextjs-migration-design.md` §9) tendrán cada una su propio plan, partiendo de esta base.
