# Raichu Next.js — Fase 2 Plan A (Datos/config + enriquecimiento del pipeline) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Llevar a paridad la capa de datos/lógica del modo Nuevo (37 arquetipos + preguntas universales, registro de 27 elementos visuales, parser de JSON de producto n8n/legacy, brief Markdown bidireccional, validadores) y enriquecer el tipo de entrada del pipeline y los constructores de prompts para que **consuman** esos datos. Sin UI (eso es el Plan B).

**Architecture:** Todo es lógica pura en `src/lib/` del proyecto `raichu-next`, testeada con Vitest sin red. Los datos estáticos (arquetipos, registro visual) y los parsers se portan desde el código Python fuente del repo `raichu_pccom_v3`. Los campos nuevos del pipeline son **opcionales** → compatibilidad total con la Fase 1.

**Tech Stack:** TypeScript · Vitest. (Sin dependencias nuevas en este plan.)

## Global Constraints

- **Proyecto de trabajo:** `C:\Users\maximo.sanchez\OneDrive - PcComponentes\Escritorio\claude projects\raichu-next` (rama `master`). Trabaja SIEMPRE dentro de esa carpeta.
- **Código Python fuente a portar** (repo separado, solo lectura): `C:\Users\maximo.sanchez\OneDrive - PcComponentes\Escritorio\claude projects\raichu_pccom_v3\`. NO lo modifiques.
- **Compatibilidad hacia atrás:** todos los campos nuevos del pipeline son opcionales; el vertical slice de Fase 1 debe seguir pasando sus tests sin cambios.
- **Recuento de arquetipos:** la fuente de verdad es `config/arquetipos.py`. El plan asume **37** (`ARQ-1`..`ARQ-37`); si el código tiene otro número, usa el real y ajusta la aserción de conteo (documenta la discrepancia en el reporte).
- **Sin red en tests:** ningún test usa API keys ni red.
- **TDD:** test que falla → implementación mínima → test que pasa → commit, por tarea.
- **Convención de imports:** alias `@/` → `src/`.

---

### Task 1: Arquetipos completos (37 + preguntas universales)

**Files:**
- Modify: `src/lib/config/arquetipos.ts` (amplía de 3 a 37 + añade campos e universales)
- Modify: `src/lib/config/arquetipos.test.ts`
- Source a portar (lectura): `raichu_pccom_v3\config\arquetipos.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `interface Arquetipo { code; name; description; tone; structure: string[]; guidingQuestions: string[]; defaultLength; minLength; maxLength; visualElements: string[] }`
  - `export const ARQUETIPOS: Arquetipo[]` (37 entradas)
  - `export const PREGUNTAS_UNIVERSALES: string[]` (6)
  - `getArquetipo(code)`, `isValidArquetipo(code)` (firmas sin cambios), `listArquetipos(): Arquetipo[]`
- Nota: añadir campos al interface es aditivo; los consumidores de Fase 1 (pipeline) solo usan `code/name/description/tone/*Length` y siguen compilando.

- [ ] **Step 1: Leer la fuente y actualizar el test**

Lee `raichu_pccom_v3\config\arquetipos.py` para obtener, por cada `ARQ-1..ARQ-37`: `name`, `description`, `tone`, `structure`, `guiding_questions` (o `preguntas_guia`), `default_length`, `min_length`, `max_length`, `visual_elements`; y la lista `PREGUNTAS_UNIVERSALES`.

Reescribe `src/lib/config/arquetipos.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  ARQUETIPOS,
  PREGUNTAS_UNIVERSALES,
  getArquetipo,
  isValidArquetipo,
  listArquetipos,
} from './arquetipos'

describe('arquetipos (paridad Fase 2)', () => {
  it('expone los 37 arquetipos con códigos únicos ARQ-1..ARQ-37', () => {
    expect(ARQUETIPOS.length).toBe(37)
    const codes = ARQUETIPOS.map((a) => a.code)
    expect(new Set(codes).size).toBe(37)
    for (let i = 1; i <= 37; i++) expect(codes).toContain(`ARQ-${i}`)
  })

  it('cada arquetipo tiene los campos requeridos y rangos coherentes', () => {
    for (const a of ARQUETIPOS) {
      expect(a.name.length).toBeGreaterThan(0)
      expect(a.description.length).toBeGreaterThan(0)
      expect(a.tone.length).toBeGreaterThan(0)
      expect(Array.isArray(a.structure)).toBe(true)
      expect(Array.isArray(a.guidingQuestions)).toBe(true)
      expect(a.guidingQuestions.length).toBeGreaterThan(0)
      expect(Array.isArray(a.visualElements)).toBe(true)
      expect(a.minLength).toBeLessThanOrEqual(a.defaultLength)
      expect(a.defaultLength).toBeLessThanOrEqual(a.maxLength)
    }
  })

  it('nombres conocidos coinciden con la fuente', () => {
    expect(getArquetipo('ARQ-1')?.name).toBe('Artículos SEO con Enlaces Internos')
    expect(getArquetipo('ARQ-5')?.name).toBe('Comparativa A vs B')
  })

  it('hay 6 preguntas universales no vacías', () => {
    expect(PREGUNTAS_UNIVERSALES.length).toBe(6)
    for (const q of PREGUNTAS_UNIVERSALES) expect(q.length).toBeGreaterThan(0)
  })

  it('lookup y listado', () => {
    expect(isValidArquetipo('ARQ-37')).toBe(true)
    expect(isValidArquetipo('ARQ-999')).toBe(false)
    expect(listArquetipos().length).toBe(ARQUETIPOS.length)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/config/arquetipos.test.ts`
Expected: FAIL (solo hay 3 arquetipos; faltan `PREGUNTAS_UNIVERSALES`, `listArquetipos`, campos nuevos).

- [ ] **Step 3: Portar los datos**

Reescribe `src/lib/config/arquetipos.ts`: amplía el `interface Arquetipo` con `structure: string[]`, `guidingQuestions: string[]`, `visualElements: string[]`; transcribe los 37 arquetipos desde `arquetipos.py` (mapea `guiding_questions`/`preguntas_guia` → `guidingQuestions`, `default_length` → `defaultLength`, etc.); añade `export const PREGUNTAS_UNIVERSALES: string[]` (las 6 de la fuente) y `export function listArquetipos(): Arquetipo[] { return ARQUETIPOS }`. Mantén `getArquetipo`/`isValidArquetipo` con el `Map` por código.

Transcribe los textos fielmente (descripciones, preguntas, structure) desde la fuente Python; no inventes contenido. La fuente Python es **canónica para los nombres**: si el `name` real de ARQ-1/ARQ-5 difiere del que afirma el test del Step 1, alinea AMBOS (datos y aserción) al valor de la fuente, no al revés.

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/config/arquetipos.test.ts`
Expected: PASS (5 passed).

- [ ] **Step 5: Verificar que no rompe consumidores**

Run: `npx vitest run && npx tsc --noEmit`
Expected: toda la suite verde; sin errores de tipo (el pipeline de Fase 1 sigue compilando).

- [ ] **Step 6: Commit**

```bash
git add src/lib/config/arquetipos.ts src/lib/config/arquetipos.test.ts
git commit -m "feat: full 37 arquetipos + universal questions"
```

---

### Task 2: Registro de elementos visuales (27)

**Files:**
- Create: `src/lib/config/visual-elements.ts`
- Test: `src/lib/config/visual-elements.test.ts`
- Source a portar (lectura): `raichu_pccom_v3\ui\inputs.py` (sección de definición de elementos visuales, aprox. L1645–2226)

**Interfaces:**
- Consumes: `getArquetipo` (Task 1) en el test, para verificar preselección.
- Produces:
  - `interface VisualElement { id: string; label: string; description: string; help: string; default: boolean }`
  - `export const VISUAL_ELEMENTS: VisualElement[]` (27)
  - `export function getVisualElement(id: string): VisualElement | undefined`
  - `export function defaultVisualElementsForArquetipo(code: string): string[]` — devuelve `getArquetipo(code)?.visualElements ?? []`.

- [ ] **Step 1: Leer la fuente y escribir el test**

Lee la definición de elementos visuales en `raichu_pccom_v3\ui\inputs.py` para obtener los 27 ids con su `label`/`description`/`help`/`default`. Crea `src/lib/config/visual-elements.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  VISUAL_ELEMENTS,
  getVisualElement,
  defaultVisualElementsForArquetipo,
} from './visual-elements'

describe('visual elements', () => {
  it('expone 27 componentes con ids únicos y campos requeridos', () => {
    expect(VISUAL_ELEMENTS.length).toBe(27)
    const ids = VISUAL_ELEMENTS.map((v) => v.id)
    expect(new Set(ids).size).toBe(27)
    for (const v of VISUAL_ELEMENTS) {
      expect(v.id.length).toBeGreaterThan(0)
      expect(v.label.length).toBeGreaterThan(0)
      expect(typeof v.default).toBe('boolean')
    }
  })

  it('incluye los ids base esperados', () => {
    const ids = VISUAL_ELEMENTS.map((v) => v.id)
    for (const id of ['toc', 'table', 'comparison_table', 'callout', 'verdict', 'faqs', 'grid']) {
      expect(ids).toContain(id)
    }
  })

  it('getVisualElement resuelve por id', () => {
    expect(getVisualElement('toc')?.id).toBe('toc')
    expect(getVisualElement('nope')).toBeUndefined()
  })

  it('la preselección por arquetipo viene de su lista visualElements', () => {
    const arq1 = defaultVisualElementsForArquetipo('ARQ-1')
    expect(arq1).toContain('toc')
    expect(defaultVisualElementsForArquetipo('ARQ-999')).toEqual([])
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/config/visual-elements.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Portar el registro**

Crea `src/lib/config/visual-elements.ts` con el `interface VisualElement`, el array `VISUAL_ELEMENTS` (27 entradas transcritas de la fuente; si la fuente no define `description`/`help` para alguno, usa cadena vacía), `getVisualElement` (con `Map` por id) y `defaultVisualElementsForArquetipo` que importa `getArquetipo` de `@/lib/config/arquetipos`.

Si la lista de ids base del test (`toc`, `table`, `comparison_table`, `callout`, `verdict`, `faqs`, `grid`) no aparece tal cual en la fuente, ajústate a los ids reales de la fuente y actualiza esa aserción del test para que liste ids que sí existen (no inventes ids).

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/config/visual-elements.test.ts`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/config/visual-elements.ts src/lib/config/visual-elements.test.ts
git commit -m "feat: visual elements registry (27 components)"
```

---

### Task 3: Tipos y parser de JSON de producto (legacy + n8n)

**Files:**
- Create: `src/lib/product/product-json.ts`
- Test: `src/lib/product/product-json.test.ts`
- Source a portar (lectura): `raichu_pccom_v3\utils\product_json_utils.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `interface ProductData { productId: string; title: string; brandName: string; familyName: string; description: string; attributes: Record<string,string>; images: string[]; advantagesList: string[]; disadvantagesList: string[]; totalComments: number; price: string; productUrl: string; rating: string; category: string; faqs: Array<{ question: string; answer: string }> }`
  - `export function validateProductJson(jsonStr: string): { ok: boolean; error?: string }`
  - `export function parseProductJson(jsonStr: string): ProductData | null` (detecta formato; `null` si no parsea).

- [ ] **Step 1: Escribir el test que falla**

Crea `src/lib/product/product-json.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { parseProductJson, validateProductJson } from './product-json'

const LEGACY = JSON.stringify({
  product_id: '6917499',
  title: 'Monitor ASUS ROG 27" 144Hz',
  brand_name: 'ASUS',
  family_name: 'ROG Strix',
  description: 'Monitor gaming premium.',
  attributes: { Pantalla: '27" IPS 144Hz', 'Conexión': 'DP/HDMI' },
  images: ['https://example.com/a.jpg'],
  total_comments: 125,
  advantages: '- Excelente para gaming\n- Panel IPS',
  disadvantages: '- Precio elevado',
})

const N8N = JSON.stringify([
  {
    meta: [],
    data: [
      {
        product_id: '6917499',
        name: 'Monitor ASUS ROG',
        brand: 'ASUS',
        family: 'ROG Strix',
        markdown:
          '## CARACTERISTICAS\n- PRECIO: 599€\n## ESPECIFICACIONES\n| Pantalla | 27" IPS 144Hz |\n## DESCRIPCION\nMonitor gaming premium.\n## ES PARA TI SI\n- Gaming competitivo\n## NO ES PARA TI SI\n- Presupuesto ajustado\n## FAQS\n### ¿Tiene DisplayPort?\nSí, 2x DP 1.4',
      },
    ],
    rows: 1,
  },
])

describe('validateProductJson', () => {
  it('acepta legacy y n8n válidos', () => {
    expect(validateProductJson(LEGACY).ok).toBe(true)
    expect(validateProductJson(N8N).ok).toBe(true)
  })
  it('rechaza JSON inválido o sin product_id', () => {
    expect(validateProductJson('{no json').ok).toBe(false)
    expect(validateProductJson('{"title":"x"}').ok).toBe(false)
  })
})

describe('parseProductJson (legacy)', () => {
  it('extrae los campos base y las listas de ventajas/desventajas', () => {
    const p = parseProductJson(LEGACY)!
    expect(p.productId).toBe('6917499')
    expect(p.brandName).toBe('ASUS')
    expect(p.attributes['Pantalla']).toBe('27" IPS 144Hz')
    expect(p.advantagesList).toContain('Excelente para gaming')
    expect(p.disadvantagesList).toContain('Precio elevado')
    expect(p.totalComments).toBe(125)
  })
})

describe('parseProductJson (n8n)', () => {
  it('detecta el wrapper y parsea las secciones del markdown', () => {
    const p = parseProductJson(N8N)!
    expect(p.productId).toBe('6917499')
    expect(p.brandName).toBe('ASUS')
    expect(p.price).toContain('599')
    expect(p.advantagesList).toContain('Gaming competitivo')
    expect(p.disadvantagesList).toContain('Presupuesto ajustado')
    expect(p.faqs.length).toBeGreaterThanOrEqual(1)
    expect(p.faqs[0].question).toContain('DisplayPort')
  })
  it('devuelve null si no parsea', () => {
    expect(parseProductJson('nope')).toBeNull()
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/product/product-json.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar el parser**

Lee `raichu_pccom_v3\utils\product_json_utils.py` para replicar las heurísticas de parseo. Crea `src/lib/product/product-json.ts` con:

- `ProductData` (interface de arriba). Valores por defecto: strings `''`, arrays `[]`, `totalComments: 0`.
- `validateProductJson(jsonStr)`: intenta `JSON.parse`; si lanza → `{ok:false, error:'JSON inválido'}`. Detecta formato: si es array con `[0].data[0]` o si es objeto con `product_id` → busca `product_id`/`productId`; si no hay → `{ok:false, error:'falta product_id'}`. Si todo OK → `{ok:true}`.
- `parseProductJson(jsonStr)`: `JSON.parse` en try/catch (→ `null`). Detección:
  - **n8n wrapper:** `Array.isArray(raw) && raw[0]?.data?.[0]`. Toma `d = raw[0].data[0]`: `productId = d.product_id`, `title = d.name`, `brandName = d.brand`, `familyName = d.family`. Parsea `d.markdown` por secciones `## TÍTULO` (split por líneas que empiezan con `## `):
    - `## CARACTERISTICAS`: busca línea `- PRECIO: ...` → `price` (el texto tras `PRECIO:`).
    - `## ESPECIFICACIONES`: filas de tabla `| clave | valor |` → `attributes[clave]=valor`.
    - `## DESCRIPCION`: el texto → `description`.
    - `## ES PARA TI SI`: items `- ...` → `advantagesList`.
    - `## NO ES PARA TI SI`: items `- ...` → `disadvantagesList`.
    - `## FAQS`: pares `### pregunta` + línea(s) siguientes → `faqs[{question, answer}]`.
  - **legacy plano:** objeto con `product_id`. Mapea `title`, `brand_name`, `family_name`, `description`, `attributes` (objeto tal cual), `images`, `total_comments`. `advantages`/`disadvantages` son strings markdown con items `- ...`: parsea a `advantagesList`/`disadvantagesList` (quita el `- ` inicial y trim por línea no vacía).
  - Si no encaja ninguno → `null`.

Implementa las heurísticas de forma que el test pase con los fixtures dados; usa la fuente Python como referencia para casos límite (acentos, líneas vacías).

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/product/product-json.test.ts`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/product/product-json.ts src/lib/product/product-json.test.ts
git commit -m "feat: product JSON parser (legacy + n8n wrapper)"
```

---

### Task 4: Brief Markdown bidireccional

**Files:**
- Create: `src/lib/brief/brief-io.ts`
- Test: `src/lib/brief/brief-io.test.ts`
- Source a portar (lectura): `raichu_pccom_v3\utils\brief_io.py`

**Interfaces:**
- Consumes: nada (usa tipos propios).
- Produces:
  - `interface BriefData { arquetipo: string; keyword: string; targetLength: number; secondaryKeywords: string[]; additionalInstructions: string; authoritativeSources: string[]; guiding: Record<string, string> }`
  - `export function buildBriefMarkdown(data: BriefData): string`
  - `export function parseBriefMarkdown(md: string): BriefData`

- [ ] **Step 1: Escribir el test que falla**

Crea `src/lib/brief/brief-io.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import { buildBriefMarkdown, parseBriefMarkdown, type BriefData } from './brief-io'

const DATA: BriefData = {
  arquetipo: 'ARQ-7',
  keyword: 'mejores monitores gaming 2025',
  targetLength: 2200,
  secondaryKeywords: ['monitores 144hz', 'monitor 4k gaming'],
  additionalInstructions: 'Enfócate en relación calidad-precio.',
  authoritativeSources: ['https://www.pccomponentes.com/monitores-gaming'],
  guiding: { guiding_spec_0: 'Monitores IPS 144Hz+', guiding_univ_0: 'Jugadores competitivos' },
}

describe('brief-io', () => {
  it('el markdown generado lleva el marcador de versión y el arquetipo', () => {
    const md = buildBriefMarkdown(DATA)
    expect(md).toContain('<!-- raichu-brief:v1 -->')
    expect(md).toContain('ARQ-7')
    expect(md).toContain('[keyword]')
    expect(md).toContain('mejores monitores gaming 2025')
  })

  it('round-trip: build → parse recupera los campos', () => {
    const parsed = parseBriefMarkdown(buildBriefMarkdown(DATA))
    expect(parsed.arquetipo).toBe('ARQ-7')
    expect(parsed.keyword).toBe('mejores monitores gaming 2025')
    expect(parsed.targetLength).toBe(2200)
    expect(parsed.secondaryKeywords).toEqual(['monitores 144hz', 'monitor 4k gaming'])
    expect(parsed.additionalInstructions).toContain('calidad-precio')
    expect(parsed.authoritativeSources[0]).toContain('pccomponentes.com')
    expect(parsed.guiding.guiding_spec_0).toContain('IPS 144Hz')
  })

  it('el parser tolera ausencia del marcador "Respuesta:"', () => {
    const md = `<!-- raichu-brief:v1 -->\nArquetipo: [ARQ-1]\n\n## [keyword] Keyword principal\nmonitores baratos\n`
    const parsed = parseBriefMarkdown(md)
    expect(parsed.keyword).toBe('monitores baratos')
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/brief/brief-io.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar build + parse**

Lee `raichu_pccom_v3\utils\brief_io.py` para el formato exacto. Crea `src/lib/brief/brief-io.ts`:

- `buildBriefMarkdown(data)`: genera el documento con:
  - Cabecera con `<!-- raichu-brief:v1 -->`, una línea `Modo: new` y `Arquetipo: [${data.arquetipo}]`.
  - Secciones `## [keyword] Keyword principal`, `## [target_length] Longitud objetivo (palabras)`, `## [secondary_keywords] Keywords secundarias` (una por línea), `## [additional_instructions] Instrucciones adicionales`, `## [authoritative_sources] Fuentes autoritativas` (una por línea), cada una con una línea `Respuesta:` y el valor debajo.
  - Sección `## Briefing — Preguntas del arquetipo` con un bloque `### [guiding_xxx] ...` + `Respuesta:` + valor por cada clave en `data.guiding`.
- `parseBriefMarkdown(md)`: recorre líneas; detecta secciones por el patrón `## [<id>]` o `### [<id>]`; el valor son las líneas tras `Respuesta:` (o, si no hay `Respuesta:`, las líneas no-cabecera siguientes) hasta la próxima cabecera. Mapea: `keyword`→string, `target_length`→`Number(...)`, `secondary_keywords`/`authoritative_sources`→split por líneas no vacías, `additional_instructions`→string, `guiding_*`→`guiding[id]`. El `Arquetipo: [ARQ-X]` de la cabecera → `arquetipo`. Ignora líneas de ayuda en cursiva (`_..._`).

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/brief/brief-io.test.ts`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/brief/brief-io.ts src/lib/brief/brief-io.test.ts
git commit -m "feat: brief markdown build/parse round-trip"
```

---

### Task 5: Validadores de inputs

**Files:**
- Create: `src/lib/validation/inputs.ts`
- Test: `src/lib/validation/inputs.test.ts`

**Interfaces:**
- Consumes: `isValidArquetipo` (Task 1). (La validación de JSON de producto ya vive en `validateProductJson` de la Task 3; este módulo no la re-envuelve.)
- Produces:
  - `interface ValidationResult { ok: boolean; error?: string }`
  - `export function validateKeyword(v: string): ValidationResult` (2–100)
  - `export function validateTargetLength(n: number): ValidationResult` (500–5000)
  - `export function validateUrl(v: string, opts?: { requirePcc?: boolean }): ValidationResult` (≤2000, formato URL; si `requirePcc`, dominio pccomponentes.com)
  - `export function validateArquetipoCode(code: string): ValidationResult`
  - Constantes: `MIN_KEYWORD=2, MAX_KEYWORD=100, MIN_LENGTH=500, MAX_LENGTH=5000, MAX_URL=2000, MAX_COMPETITORS=5, MAX_LINKS_PER_TYPE=10`

- [ ] **Step 1: Escribir el test que falla**

Crea `src/lib/validation/inputs.test.ts`:

```ts
import { describe, it, expect } from 'vitest'
import {
  validateKeyword,
  validateTargetLength,
  validateUrl,
  validateArquetipoCode,
  MAX_COMPETITORS,
  MAX_LINKS_PER_TYPE,
} from './inputs'

describe('validators', () => {
  it('keyword 2–100', () => {
    expect(validateKeyword('a').ok).toBe(false)
    expect(validateKeyword('monitores').ok).toBe(true)
    expect(validateKeyword('x'.repeat(101)).ok).toBe(false)
  })
  it('target length 500–5000', () => {
    expect(validateTargetLength(400).ok).toBe(false)
    expect(validateTargetLength(1500).ok).toBe(true)
    expect(validateTargetLength(6000).ok).toBe(false)
  })
  it('url formato y dominio PcC opcional', () => {
    expect(validateUrl('no-es-url').ok).toBe(false)
    expect(validateUrl('https://example.com').ok).toBe(true)
    expect(validateUrl('https://example.com', { requirePcc: true }).ok).toBe(false)
    expect(validateUrl('https://www.pccomponentes.com/x', { requirePcc: true }).ok).toBe(true)
  })
  it('arquetipo existe', () => {
    expect(validateArquetipoCode('ARQ-1').ok).toBe(true)
    expect(validateArquetipoCode('ARQ-999').ok).toBe(false)
  })
  it('constantes de límites', () => {
    expect(MAX_COMPETITORS).toBe(5)
    expect(MAX_LINKS_PER_TYPE).toBe(10)
  })
})
```

- [ ] **Step 2: Ejecutar el test para verificar que falla**

Run: `npx vitest run src/lib/validation/inputs.test.ts`
Expected: FAIL — módulo no encontrado.

- [ ] **Step 3: Implementar los validadores**

Crea `src/lib/validation/inputs.ts`:

```ts
import { isValidArquetipo } from '@/lib/config/arquetipos'

export interface ValidationResult { ok: boolean; error?: string }

export const MIN_KEYWORD = 2
export const MAX_KEYWORD = 100
export const MIN_LENGTH = 500
export const MAX_LENGTH = 5000
export const MAX_URL = 2000
export const MAX_COMPETITORS = 5
export const MAX_LINKS_PER_TYPE = 10

export function validateKeyword(v: string): ValidationResult {
  const t = (v ?? '').trim()
  if (t.length < MIN_KEYWORD) return { ok: false, error: `Mínimo ${MIN_KEYWORD} caracteres` }
  if (t.length > MAX_KEYWORD) return { ok: false, error: `Máximo ${MAX_KEYWORD} caracteres` }
  return { ok: true }
}

export function validateTargetLength(n: number): ValidationResult {
  if (!Number.isFinite(n) || n < MIN_LENGTH || n > MAX_LENGTH) {
    return { ok: false, error: `Entre ${MIN_LENGTH} y ${MAX_LENGTH} palabras` }
  }
  return { ok: true }
}

export function validateUrl(v: string, opts?: { requirePcc?: boolean }): ValidationResult {
  const t = (v ?? '').trim()
  if (t.length === 0 || t.length > MAX_URL) return { ok: false, error: 'URL vacía o demasiado larga' }
  let url: URL
  try {
    url = new URL(t)
  } catch {
    return { ok: false, error: 'Formato de URL no válido' }
  }
  if (url.protocol !== 'http:' && url.protocol !== 'https:') return { ok: false, error: 'Protocolo no válido' }
  if (opts?.requirePcc && !url.hostname.endsWith('pccomponentes.com')) {
    return { ok: false, error: 'Debe ser un dominio pccomponentes.com' }
  }
  return { ok: true }
}

export function validateArquetipoCode(code: string): ValidationResult {
  return isValidArquetipo(code) ? { ok: true } : { ok: false, error: 'Arquetipo desconocido' }
}
```

- [ ] **Step 4: Ejecutar el test para verificar que pasa**

Run: `npx vitest run src/lib/validation/inputs.test.ts`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/lib/validation/inputs.ts src/lib/validation/inputs.test.ts
git commit -m "feat: input validators (keyword, length, url, arquetipo)"
```

---

### Task 6: Enriquecer NewContentInput + builders de prompts + helpers de formateo

**Files:**
- Modify: `src/lib/prompts/new-content.ts` (builders consumen campos nuevos; añade helpers)
- Modify: `src/lib/prompts/new-content.test.ts` (añade casos; no rompas los existentes)
- Modify: `src/lib/pipeline/run-new-content.ts` (extiende el tipo de entrada)
- Modify: `src/lib/pipeline/run-new-content.test.ts` (un caso de compat hacia atrás; no rompas los existentes)

**Interfaces:**
- Consumes: `ProductData` (Task 3), `Arquetipo` (Task 1).
- Produces:
  - `interface LinkWithAnchor { url: string; anchor: string; data?: ProductData | null }`
  - `interface NewContentInput { keyword: string; arquetipoCode: string; targetLength: number; additionalInstructions?: string; secondaryKeywords?: string[]; authoritativeSources?: string[]; product?: ProductData | null; alternativeProduct?: { url?: string; name?: string; data?: ProductData | null }; internalLinks?: LinkWithAnchor[]; pdpLinks?: LinkWithAnchor[]; competitorUrls?: string[]; visualElements?: string[]; headingsConfig?: { h2?: number; h3?: number; h4?: number }; guidingAnswers?: Record<string, string> }` (exportado desde el pipeline)
  - `export function formatProductForPrompt(p: ProductData | null | undefined): string`
  - `export function formatLinksForPrompt(links: LinkWithAnchor[] | undefined, label: string): string`
  - `export function formatVisualElementsForPrompt(ids: string[] | undefined): string`
  - `export function formatBriefingForPrompt(answers: Record<string,string> | undefined): string`
  - Los builders `buildStage1Prompt`/`buildStage3Prompt` aceptan un objeto extendido **opcional** y, cuando se pasa, incluyen esos bloques. Firmas hacia atrás compatibles (todos los campos nuevos opcionales).

- [ ] **Step 1: Escribir los tests que fallan (sin romper los existentes)**

Añade a `src/lib/prompts/new-content.test.ts` un nuevo `describe` (deja intactos los tests de Fase 1):

```ts
import {
  formatProductForPrompt,
  formatLinksForPrompt,
  formatVisualElementsForPrompt,
  formatBriefingForPrompt,
} from './new-content'

describe('prompts enriquecidos (Fase 2)', () => {
  const product = {
    productId: '1', title: 'Monitor X', brandName: 'ASUS', familyName: 'ROG',
    description: 'desc', attributes: { Pantalla: '27"' }, images: [],
    advantagesList: ['Gran imagen'], disadvantagesList: ['Caro'],
    totalComments: 10, price: '599€', productUrl: '', rating: '4.5', category: 'monitores', faqs: [],
  }

  it('formatProductForPrompt incluye marca, ventajas y desventajas', () => {
    const s = formatProductForPrompt(product)
    expect(s).toContain('ASUS')
    expect(s).toContain('Gran imagen')
    expect(s).toContain('Caro')
  })
  it('formatProductForPrompt vacío si no hay producto', () => {
    expect(formatProductForPrompt(null)).toBe('')
  })
  it('formatLinksForPrompt lista url+anchor', () => {
    const s = formatLinksForPrompt([{ url: 'https://x.com', anchor: 'ancla' }], 'Internos')
    expect(s).toContain('https://x.com')
    expect(s).toContain('ancla')
  })
  it('formatVisualElementsForPrompt enumera ids solicitados', () => {
    expect(formatVisualElementsForPrompt(['toc', 'table'])).toContain('toc')
    expect(formatVisualElementsForPrompt([])).toBe('')
  })
  it('formatBriefingForPrompt incluye respuestas', () => {
    expect(formatBriefingForPrompt({ guiding_univ_0: 'Gamers' })).toContain('Gamers')
  })

  it('buildStage1Prompt incluye los bloques cuando se pasan', async () => {
    const { buildStage1Prompt } = await import('./new-content')
    const { getArquetipo } = await import('@/lib/config/arquetipos')
    const p = buildStage1Prompt({
      keyword: 'kw', arquetipo: getArquetipo('ARQ-1')!, targetLength: 1500,
      product, secondaryKeywords: ['kw2'], visualElements: ['toc'],
      internalLinks: [{ url: 'https://x.com', anchor: 'a' }],
      additionalInstructions: 'INSTR', guidingAnswers: { guiding_univ_0: 'Gamers' },
    })
    expect(p).toContain('ASUS')
    expect(p).toContain('kw2')
    expect(p).toContain('toc')
    expect(p).toContain('INSTR')
    expect(p).toContain('Gamers')
  })
})
```

Añade a `src/lib/pipeline/run-new-content.test.ts` un caso de compat (deja intactos los existentes):

```ts
import type { NewContentInput } from './run-new-content'

it('compat: el pipeline acepta solo los 3 campos base (Fase 1)', async () => {
  const { runNewContentPipeline } = await import('./run-new-content')
  // reutiliza los helpers/fakes del archivo; este test solo verifica el tipo + flujo mínimo
  const input: NewContentInput = { keyword: 'kw', arquetipoCode: 'ARQ-1', targetLength: 1500 }
  expect(input.keyword).toBe('kw')
})
```

- [ ] **Step 2: Ejecutar para verificar que falla**

Run: `npx vitest run src/lib/prompts/new-content.test.ts src/lib/pipeline/run-new-content.test.ts`
Expected: FAIL — helpers y `NewContentInput` no existen aún.

- [ ] **Step 3: Implementar helpers y extender builders + tipo**

En `src/lib/prompts/new-content.ts`:
- Importa `ProductData` de `@/lib/product/product-json` y `LinkWithAnchor`/tipos según convenga (puedes definir `LinkWithAnchor` aquí y reexportarlo, o importarlo del pipeline; para evitar ciclos, **define `LinkWithAnchor` en `new-content.ts` y que el pipeline lo importe de aquí**).
- Implementa los 4 helpers de formateo (devuelven `''` cuando el input está vacío/ausente):
  - `formatProductForPrompt(p)`: si `p`, devuelve un bloque markdown con título, marca/familia, precio, atributos clave, `advantagesList` (como "Ventajas:") y `disadvantagesList` (como "Desventajas:").
  - `formatLinksForPrompt(links, label)`: si hay, devuelve `"## Enlaces ${label}\n"` + líneas `- [anchor](url)`.
  - `formatVisualElementsForPrompt(ids)`: si hay, devuelve `"## Elementos visuales solicitados\n"` + lista de ids.
  - `formatBriefingForPrompt(answers)`: si hay, devuelve `"## Contexto del briefing\n"` + líneas `clave: valor`.
- Extiende los parámetros de `buildStage1Prompt` y `buildStage3Prompt` con los campos nuevos **opcionales** (`product`, `secondaryKeywords`, `additionalInstructions`, `authoritativeSources`, `internalLinks`, `pdpLinks`, `competitorUrls`, `visualElements`, `guidingAnswers`, `alternativeProduct`) y, antes del bloque `CMS_CONTRACT`, inserta el resultado de los helpers (cada uno omitido si devuelve `''`). No cambies la firma mínima existente: los tests de Fase 1 pasan `{keyword, arquetipo, targetLength}` y deben seguir funcionando.

En `src/lib/pipeline/run-new-content.ts`:
- Exporta `interface NewContentInput { ... }` (la de arriba) e impórtala/úsala como tipo del primer parámetro de `runNewContentPipeline` (reemplaza el `{ keyword; arquetipoCode; targetLength }` inline). Importa `LinkWithAnchor` y `ProductData` desde sus módulos.
- En la llamada a `buildStage1Prompt`/`buildStage3Prompt`, pasa los campos nuevos desde `input` (todos opcionales). Stage 2 puede seguir igual (no necesita los bloques nuevos para el análisis en esta fase).

- [ ] **Step 4: Ejecutar para verificar que pasa (y no rompe Fase 1)**

Run: `npx vitest run && npx tsc --noEmit`
Expected: toda la suite verde (incluidos los tests de Fase 1 de prompts y pipeline); sin errores de tipo.

- [ ] **Step 5: Build de seguridad**

Run: `npm run build`
Expected: compila sin errores.

- [ ] **Step 6: Commit**

```bash
git add src/lib/prompts/new-content.ts src/lib/prompts/new-content.test.ts src/lib/pipeline/run-new-content.ts src/lib/pipeline/run-new-content.test.ts
git commit -m "feat: enrich NewContentInput + prompt builders consume product/links/visuals/briefing"
```

---

## Notas de cierre del Plan A

Al terminar, `raichu-next` tiene la capa de datos/lógica del modo Nuevo a paridad (37 arquetipos + universales, 27 visuales, parser de producto n8n/legacy, brief I/O, validadores) y el pipeline/prompts ya **consumen** esos inputs, todo verificado con Vitest sin red. El **Plan B** (formulario shadcn + accordion, brief I/O en UI, listas dinámicas, y cableado del `NewContentInput` completo a `/api/generate`) se construye encima de esta base y tendrá su propio documento de plan.
