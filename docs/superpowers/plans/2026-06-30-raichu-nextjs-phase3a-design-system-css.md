# Raichu Next.js — Fase 3 Plan A (CSS real del design system + render de elementos visuales) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el HTML del modo Nuevo salga **estilado** con el CSS del design system (hoy llega un stub `/* CSS embebido */`) y que los elementos visuales seleccionados se maqueten con sus **clases reales** + plantilla de ejemplo. También cablear `headingsConfig` (hoy aceptado pero ignorado) al prompt. Sin nuevas llamadas LLM.

**Architecture:** El CSS canónico se porta como **string estático** (`DESIGN_SYSTEM_CSS`) y se inyecta entero donde está el placeholder (decisión A del spec: sin tree-shaking en v1). Las plantillas por elemento visual (`VISUAL_TEMPLATES` + `buildVisualInstructions`) reemplazan la lista de ids pelada en el prompt. Todo es lógica pura server-side; el pipeline no cambia de forma.

**Tech Stack:** Next.js (App Router) · TypeScript · Vitest.

## Global Constraints

- **Proyecto de trabajo:** `C:\Users\maximo.sanchez\OneDrive - PcComponentes\Escritorio\claude projects\raichu-next` (rama `master`). Trabaja SIEMPRE dentro de esa carpeta. (OneDrive: si `Read` da copia stale usa `git show HEAD:<ruta>`; si `tsc` falla por caché borra `*.tsbuildinfo` fuera de `node_modules`.)
- **Fuente de verdad del CSS** (proyecto Python `raichu_pccom_v3`, NO se modifica): `config/design_system.py::_CANONICAL_CSS` (string minificado, empieza en `config/design_system.py:483`) y, para detalle/secciones, `config/cms_compatible.css` (690 líneas). Se porta el **canónico minificado**.
- **Fuente de verdad de las plantillas visuales:** `config/design_system.py::get_component_instructions` y `COMPONENT_REGISTRY` (Python). Los ids deben coincidir con los de `src/lib/config/visual-elements.ts` ya portados en raichu-next (23 elementos).
- **No cambiar la forma del pipeline ni los eventos SSE.** Solo cambia el CONTENIDO de los prompts (CSS real + instrucciones visuales + headings).
- **TDD:** test que falla → implementación mínima → test que pasa → commit, por tarea.
- **Interfaces existentes a consumir (no redefinir):** `VISUAL_ELEMENTS`, `getVisualElement` (`@/lib/config/visual-elements`); `buildStage1Prompt`, `buildStage3Prompt`, `formatVisualElementsForPrompt`, `CMS_CONTRACT` (`@/lib/prompts/new-content`); `NewContentInput` (`@/lib/pipeline/run-new-content`).

---

### Task 1: Portar el CSS canónico como dato estático

**Files:**
- Create: `src/lib/design-system/css.ts`
- Test: `src/lib/design-system/css.test.ts`

**Interfaces:**
- Produces: `export const DESIGN_SYSTEM_CSS: string` — el CSS canónico minificado del design system (un solo string, listo para ir dentro de `<style>…</style>`).

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/design-system/css.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { DESIGN_SYSTEM_CSS } from './css'

describe('DESIGN_SYSTEM_CSS', () => {
  it('contiene las variables de marca críticas', () => {
    expect(DESIGN_SYSTEM_CSS).toContain('--orange-900:#FF6000')
    expect(DESIGN_SYSTEM_CSS).toContain('--blue-m-900:#170453')
  })
  it('contiene los selectores CMS críticos', () => {
    for (const sel of ['.contentGenerator__main', '.contentGenerator__faqs', '.contentGenerator__verdict', '.kicker', '.toc', '.verdict-box']) {
      expect(DESIGN_SYSTEM_CSS).toContain(sel)
    }
  })
  it('no incluye etiquetas <style> (solo reglas)', () => {
    expect(DESIGN_SYSTEM_CSS).not.toContain('<style')
    expect(DESIGN_SYSTEM_CSS.length).toBeGreaterThan(500)
  })
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/lib/design-system/css.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Portar el CSS**

Copia el contenido de `_CANONICAL_CSS` (Python `config/design_system.py`, desde `:root{--orange-900:#FF6000;…` hasta el cierre del string) a una constante TS. Si algún selector crítico del test (p. ej. `.verdict-box`, `.toc`) NO está en el canónico minificado, complétalo desde `config/cms_compatible.css` (su sección equivalente, minificada) — el objetivo es que el CSS portado cubra los selectores del contrato CMS y de los elementos visuales base. Usa un template literal:

```ts
// src/lib/design-system/css.ts
// Portado de raichu_pccom_v3/config/design_system.py::_CANONICAL_CSS (fuente: config/cms_compatible.css).
// NO tree-shaking en v1 (decisión A del spec Fase 3): se inyecta entero.
export const DESIGN_SYSTEM_CSS = `:root{--orange-900:#FF6000;--blue-m-900:#170453;/* …resto del canónico… */}`
```

- [ ] **Step 4: Ejecutar para verificar que pasa**

Run: `npx vitest run src/lib/design-system/css.test.ts && npx tsc --noEmit`
Expected: PASS; sin errores de tipo.

- [ ] **Step 5: Commit**

```bash
git add src/lib/design-system/css.ts src/lib/design-system/css.test.ts
git commit -m "feat: port canonical design-system CSS as static asset"
```

---

### Task 2: Plantillas de elementos visuales + builder de instrucciones

**Files:**
- Create: `src/lib/design-system/visual-templates.ts`
- Test: `src/lib/design-system/visual-templates.test.ts`

**Interfaces:**
- Consumes: `VISUAL_ELEMENTS` / `getVisualElement` (`@/lib/config/visual-elements`).
- Produces:
  - `export interface VisualTemplate { id: string; description: string; className: string; htmlTemplate: string; variants?: string[] }`
  - `export const VISUAL_TEMPLATES: Record<string, VisualTemplate>` — al menos para los elementos base con clase propia (toc, callout/callout_promo, table, comparison_table, light_table, verdict, faqs, cards/grid, badges, kicker, intro_box, check_list, specs_list, product_module, price_highlight). Los ids DEBEN existir en `VISUAL_ELEMENTS`.
  - `export function buildVisualInstructions(selectedIds: string[]): string` — devuelve un bloque Markdown con, por cada id seleccionado que tenga plantilla, su descripción + clase + ejemplo HTML (y variantes si las hay). Ignora ids sin plantilla (degradación suave). String vacío si `selectedIds` vacío.

- [ ] **Step 1: Escribir el test que falla**

Create `src/lib/design-system/visual-templates.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { VISUAL_TEMPLATES, buildVisualInstructions } from './visual-templates'
import { VISUAL_ELEMENTS } from '@/lib/config/visual-elements'

describe('VISUAL_TEMPLATES', () => {
  it('todos los ids de plantilla existen en VISUAL_ELEMENTS', () => {
    const known = new Set(VISUAL_ELEMENTS.map((e) => e.id))
    for (const id of Object.keys(VISUAL_TEMPLATES)) expect(known.has(id)).toBe(true)
  })
  it('cada plantilla trae clase y ejemplo HTML', () => {
    for (const t of Object.values(VISUAL_TEMPLATES)) {
      expect(t.className.length).toBeGreaterThan(0)
      expect(t.htmlTemplate).toContain('<')
    }
  })
})

describe('buildVisualInstructions', () => {
  it('vacío si no hay selección', () => {
    expect(buildVisualInstructions([]).trim()).toBe('')
  })
  it('incluye la plantilla del elemento seleccionado', () => {
    const out = buildVisualInstructions(['toc'])
    expect(out).toContain(VISUAL_TEMPLATES['toc'].className)
  })
  it('ignora ids desconocidos sin romper', () => {
    expect(() => buildVisualInstructions(['no-existe'])).not.toThrow()
  })
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/lib/design-system/visual-templates.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar**

Crea `visual-templates.ts` portando, por cada elemento con clase propia, la descripción + clase + ejemplo HTML desde `get_component_instructions`/`COMPONENT_REGISTRY` (Python). `buildVisualInstructions` itera `selectedIds`, busca en `VISUAL_TEMPLATES`, y compone un bloque `## ELEMENTOS VISUALES A MAQUETAR` con una entrada por elemento (nombre/clase/descr + ` ```html ` ejemplo). Mantén el texto en español, conciso.

- [ ] **Step 4: Ejecutar para verificar que pasa**

Run: `npx vitest run src/lib/design-system/visual-templates.test.ts && npx tsc --noEmit`
Expected: PASS; sin errores de tipo.

- [ ] **Step 5: Commit**

```bash
git add src/lib/design-system/visual-templates.ts src/lib/design-system/visual-templates.test.ts
git commit -m "feat: per-element visual templates + buildVisualInstructions"
```

---

### Task 3: Inyectar CSS real + instrucciones visuales + headings en los prompts

**Files:**
- Modify: `src/lib/prompts/new-content.ts`
- Modify/Add: `src/lib/prompts/new-content.test.ts` (o el test existente de prompts)

**Interfaces:**
- Consumes: `DESIGN_SYSTEM_CSS` (Task 1), `buildVisualInstructions` (Task 2).
- Produces: `buildStage1Prompt`/`buildStage3Prompt` emiten el `<style>` real + el bloque de instrucciones visuales por plantilla + las instrucciones de headings. La firma pública de los builders no cambia (siguen recibiendo el `NewContentInput`/los campos que ya reciben).

- [ ] **Step 1: Escribir los tests que fallan**

Añade a `src/lib/prompts/new-content.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { buildStage1Prompt } from './new-content'
import { DESIGN_SYSTEM_CSS } from '@/lib/design-system/css'

describe('prompt Stage 1 — CSS y visuales reales', () => {
  const base = { keyword: 'monitores gaming', arquetipoCode: 'ARQ-1', targetLength: 1500, visualElements: ['toc'], headingsConfig: { h2: 4 } }
  it('inyecta el CSS del design system, no el placeholder', () => {
    const p = buildStage1Prompt(base as never)
    expect(p).toContain('--orange-900:#FF6000')
    expect(p).not.toContain('/* CSS embebido */')
  })
  it('inyecta la plantilla del elemento visual seleccionado', () => {
    const p = buildStage1Prompt(base as never)
    expect(p).toContain('toc') // clase/instrucción del TOC
  })
  it('inyecta las instrucciones de headings', () => {
    const p = buildStage1Prompt(base as never)
    expect(p).toMatch(/H2/)
  })
})
```

(Ajusta el modo de invocar `buildStage1Prompt` a su firma real — revisa `git show HEAD:src/lib/prompts/new-content.ts` para los parámetros exactos.)

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/lib/prompts/new-content.test.ts`
Expected: FAIL — sigue saliendo el placeholder / no hay headings.

- [ ] **Step 3: Implementar el cableado**

En `src/lib/prompts/new-content.ts`:
1. Reemplaza el literal `<style>/* CSS embebido */</style>` del `CMS_CONTRACT` (o donde se construya el bloque inicial) por `` `<style>${DESIGN_SYSTEM_CSS}</style>` ``.
2. En `formatVisualElementsForPrompt` (o el punto donde se serializan los elementos), sustituye la lista pelada de ids por `buildVisualInstructions(selectedIds)` (deja un fallback a la lista si no hay plantilla para ninguno).
3. Añade un helper `formatHeadingsForPrompt(headingsConfig)` que, si hay `h2/h3/h4`, emita una instrucción tipo "Usa ~N H2, ~M H3…"; cablea su salida en Stage 1 y Stage 3. Si `headingsConfig` es undefined, no emite nada.

- [ ] **Step 4: Ejecutar para verificar que pasa (y no rompe la suite)**

Run: `npx vitest run src/lib/prompts/new-content.test.ts && npm test && npx tsc --noEmit`
Expected: toda la suite verde; sin errores de tipo.

- [ ] **Step 5: Commit**

```bash
git add src/lib/prompts/new-content.ts src/lib/prompts/new-content.test.ts
git commit -m "feat: inject real design-system CSS + visual templates + headings into prompts"
```

---

### Task 4: Verificación de integridad + cierre

**Files:**
- Create: `src/lib/design-system/css-integrity.test.ts` (guard de CI; port ligero de `utils/css_integrity.py`)

**Interfaces:**
- Produces: un test que falla si el CSS portado pierde variables/selectores críticos o el header de tabla `#170453`.

- [ ] **Step 1: Escribir el guard**

Create `src/lib/design-system/css-integrity.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { DESIGN_SYSTEM_CSS } from './css'

const CRITICAL_VARS = ['--orange-900', '--blue-m-900', '--gray-100', '--gray-900', '--space-md', '--radius-md']
const CRITICAL_SELECTORS = ['.contentGenerator__main', '.contentGenerator__faqs', '.contentGenerator__verdict', '.kicker', '.toc', '.faqs__item', '.verdict-box', '.callout']

describe('css integrity guard', () => {
  it('todas las variables críticas están definidas', () => {
    for (const v of CRITICAL_VARS) expect(DESIGN_SYSTEM_CSS).toContain(v)
  })
  it('todos los selectores críticos están presentes', () => {
    for (const s of CRITICAL_SELECTORS) expect(DESIGN_SYSTEM_CSS).toContain(s)
  })
})
```

(Si algún selector crítico falta porque el canónico no lo trae, complétalo en `css.ts` desde `cms_compatible.css` — el guard define el contrato mínimo.)

- [ ] **Step 2: Verificación final (suite + tipos + build)**

Run:
```bash
npm test && npx tsc --noEmit && npm run build
```
Expected: toda la suite verde; sin errores de tipo; build OK.

- [ ] **Step 3: Commit**

```bash
git add src/lib/design-system/css-integrity.test.ts
git commit -m "test: css integrity guard for critical vars/selectors"
```

---

## Notas de cierre del Plan 3A

Al terminar, el HTML del modo Nuevo sale **estilado** con el CSS real del design system y con los elementos visuales maquetados según su plantilla; `headingsConfig` ya influye en el prompt. Queda pendiente la **Fase 3B** (post-proceso: scrubber, fix de tablas + CSS `!important`, sanitize paridad, CMS gate, quality loop) y la **Fase 3C** (web research opt-in, Stage 0). Verificación e2e visual en el CMS de producción: al cerrar 3B (cuando el override de tablas esté), comparar un artículo con tabla.
