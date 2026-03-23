# Output Quality Audit — Raichu v5.1.0

**Fecha:** 2026-03-23
**Scope:** Calidad del contenido generado por 5 arquetipos representativos
**Dimensiones evaluadas:** Tono humano, SEO, Elementos visuales, Estructura, Etapa 2 (analisis critico)

**Ficheros analizados:**
- `prompts/new_content.py` — prompt builders Stage 1/2/3 (1885 lineas)
- `prompts/rewrite.py` — prompt builders rewrite Stage 1/2/3 (1374 lineas)
- `prompts/brand_tone.py` — tono de marca, anti-IA, system prompts
- `config/arquetipos.py` — definiciones de los 34 arquetipos

---

## 1. Resumen ejecutivo

El pipeline de 3 etapas tiene controles de calidad genericos solidos: las instrucciones anti-IA (`INSTRUCCIONES_ANTI_IA`, `ANTI_IA_CHECKLIST_STAGE2`) cubren frases prohibidas, patrones a evitar y ejemplos before/after. La personalidad de marca (`PERSONALIDAD_MARCA`, 6 pilares) y el tono PcComponentes se inyectan en las 3 etapas.

**Hallazgo principal:** La Etapa 2 (analisis critico) es completamente ciega al arquetipo. La funcion `build_new_content_correction_prompt_stage2()` (`new_content.py:1437`) no recibe el codigo de arquetipo como parametro. El mismo checklist de 6 secciones se aplica a los 34 arquetipos — no puede verificar requisitos especificos como "la comparativa declara un ganador?" o "el ranking numera los productos?".

Esto significa que el analisis critico detecta problemas genericos (tono IA, densidad de keywords, estructura HTML CMS) pero deja pasar defectos estructurales especificos de cada tipo de contenido.

---

## 2. Matriz de evaluacion por arquetipo

| Arquetipo | Tono humano | SEO | Elementos visuales | Estructura | Etapa 2 |
|-----------|:-----------:|:---:|:------------------:|:----------:|:-------:|
| ARQ-2 Guia Paso a Paso | ✅ | ⚠️ | ⚠️ | ✅ | ❌ |
| ARQ-4 Review / Analisis | ✅ | ⚠️ | ✅ | ✅ | ❌ |
| ARQ-5 Comparativa A vs B | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ |
| ARQ-7 Roundup / Mejores X | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ |
| ARQ-16 Novedades y Lanzamientos | ✅ | ⚠️ | ⚠️ | ⚠️ | ❌ |

**Leyenda:** ✅ Fuerte — ⚠️ Debil — ❌ Ausente

---

### Justificacion por dimension

#### Tono humano — ✅ todos los arquetipos

Cobertura robusta en las 3 etapas:
- `INSTRUCCIONES_ANTI_IA` (`brand_tone.py:59-88`): lista de frases prohibidas ("En el mundo actual...", "Sin lugar a dudas...", etc.) + patrones a evitar (adjetivos vacios, estructuras repetitivas) + instrucciones positivas (tutear, opinar, variar parrafos).
- `ANTI_IA_CHECKLIST_STAGE2` (`brand_tone.py:304-315`): 9 items de verificacion critica incluyendo deteccion de emojis y anos en titulos.
- `EJEMPLOS_TONO_STAGE3` (`brand_tone.py:345-373`): 4 pares before/after mostrando transformacion de tono generico a PcComponentes.
- `PERSONALIDAD_MARCA` (`brand_tone.py:18-53`): 6 pilares de personalidad (expertos sin pedantes, frikis sin verguenza, honestos pero no aburridos...).
- Stage 3 repite las frases prohibidas explicitamente (`new_content.py:1744-1749`) como recordatorio final.

**No hay diferencias por arquetipo** — pero esto es correcto: el tono PcComponentes debe ser consistente independientemente del tipo de contenido. El tono *especifico* del arquetipo (ej: "Didactico, claro" para ARQ-2) se inyecta via `arquetipo['tone']` en Stage 1.

#### SEO — ⚠️ todos los arquetipos

**Lo que funciona:**
- Formula de densidad dinamica: `max(3, target_length // 200)` a `max(6, target_length // 100)` — escala con la longitud objetivo.
- Checklist de keyword en Stage 2 (`new_content.py:1537-1546`): 6 verificaciones (primeras 100 palabras, H2, densidad, distribucion, naturalidad, enlaces).
- FAQs H2 con keyword: `"Preguntas frecuentes sobre {keyword}"`.

**Lo que falta:**
- **Sin meta description:** Ningun stage instruye a Claude a generar una meta description optimizada. El output es HTML puro sin `<meta>` tag ni comentario con la meta description sugerida.
- **Reglas de placement identicas:** Las mismas reglas de "distribuir en inicio/medio/fin" se aplican a un articulo de 1500 palabras (ARQ-16 noticia) y a uno de 2200 (ARQ-7 ranking). No hay adaptacion del patron de placement por tipo de contenido.
- **Rewrite sin secondary keywords:** `new_content.py` acepta y usa `secondary_keywords` en las 3 etapas. `rewrite.py` no tiene referencia alguna a secondary keywords — confirmado por grep. El contenido reescrito pierde riqueza semantica.
- **Sin instrucciones de internal linking pattern:** Mas alla de "incluye todos los enlaces proporcionados", no hay guidance sobre *donde* colocar enlaces internos segun el tipo de contenido (ej: en un ranking, enlazar cada producto en su seccion; en una noticia, enlazar al producto en el primer parrafo).

#### Elementos visuales

**ARQ-4 Review ✅:** Define `toc, table, verdict, callout` — los 4 componentes mas relevantes para un analisis de producto. Las instrucciones de visual elements (`_format_visual_elements_instructions()`, L1019-1126) dan placement hints especificos para cada uno. Stage 3 los refuerza con templates imperativos y checklist de CSS selectors.

**ARQ-2 Guia Paso a Paso ⚠️:** Define `toc, callout, check_list`. El `check_list` tiene template HTML (`<ul class="check-list">`) pero **no diferencia** entre "check_list para requisitos previos" y "check_list para pasos completados". En un how-to, los requisitos previos usan checklist de verificacion, mientras los pasos del proceso usan listas ordenadas (`<ol>`). Esta distincion no se instruye.

**ARQ-5 Comparativa ⚠️:** Define `toc, table, verdict`. Usa la clase generica `<table>` en lugar de `<table class="comparison-table">`, que existe en el design system y esta disenada especificamente para comparaciones lado a lado. El componente `comparison_table` tiene hint "2-3 products side-by-side" pero no esta en los visual_elements por defecto del arquetipo.

**ARQ-7 Ranking ⚠️:** Define `toc, table, grid, verdict`. Incluye `grid` pero las instrucciones de visual elements no explican *como* usarlo para un ranking de productos (ej: una card por producto con posicion, nombre, precio, badges). El hint generico dice "Multiple products/features 2-3 cols" sin contexto de ranking.

**ARQ-16 Noticia ⚠️:** Define `toc, table, callout` pero **no incluye `verdict`**. Sin embargo, su estructura dice "Conclusion" como ultima seccion. Esto crea ambiguedad: la conclusion de una noticia no es un veredicto de producto, pero el CMS exige `<article class="contentGenerator__verdict">`. El arquetipo no explicita como llenar ese tercer article obligatorio.

#### Estructura

**ARQ-2 Guia Paso a Paso ✅:** Estructura bien definida (Intro → Requisitos → Pasos numerados → Tips → Resumen → FAQs → Conclusion). Se inyecta como lista numerada en el prompt (`arquetipo['structure']`). Las `preguntas_guia` cubren nivel de dificultad, errores comunes y variantes del proceso. Los `campos_especificos` incluyen `nivel_dificultad`, `tiempo_estimado`, `herramientas`, `errores_comunes`.

**ARQ-4 Review ✅:** Estructura completa y coherente (Intro → Specs tabla → Diseno → Rendimiento → Caracteristicas → Pros/cons → Comparacion → FAQs → Veredicto con puntuacion). Las `preguntas_guia` fuerzan al usuario a definir fuentes de datos, puntos fuertes/debiles y veredicto antes de generar.

**ARQ-5 Comparativa ⚠️:** La estructura dice "Veredicto: cual recomendamos y por que" pero **no hay instruccion explicita** en el prompt que fuerce a Claude a declarar un ganador claro. El campo `ganador` existe en `campos_especificos` pero no se inyecta como requisito en Stage 1. Claude puede generar un veredicto tibio tipo "depende de tus necesidades" sin que Stage 2 lo detecte como problema.

**ARQ-7 Ranking ⚠️:** La estructura dice "Analisis individual de cada producto" y "Comparativa general" pero:
- **No hay instruccion de numeracion:** No se dice explicitamente "numera los productos del 1 al N en orden de recomendacion". Claude puede presentarlos como lista sin orden claro.
- **No hay instruccion de badges:** Los `campos_especificos` definen `mejor_global` y `mejor_calidad_precio` pero estas etiquetas no se traducen en instrucciones de prompt (ej: "El primer producto debe llevar badge 'Mejor en general'").
- **No hay criterio de ordenacion explicito:** "Criterio principal de ranking" esta en `preguntas_guia` pero no se refuerza como constraint del output.

**ARQ-16 Noticia ⚠️:** La estructura dice "Anuncio del lanzamiento → Caracteristicas → Comparacion con anterior → Precio/disponibilidad → Primeras impresiones → Merece la pena? → FAQs → Conclusion" pero:
- **Sin piramide invertida:** Una noticia debe abrir con lo mas importante (que, quien, cuando, precio). No hay instruccion de periodismo basico. Claude puede empezar con una introduccion generica.
- **Sin instrucciones de temporalidad:** No se indica incluir fechas concretas de disponibilidad, ni se diferencia entre lanzamiento futuro vs ya disponible.
- **Sin atribucion de fuentes:** No hay guidance sobre como citar fuentes de las primeras impresiones o benchmarks.

#### Etapa 2 (analisis critico) — ❌ todos los arquetipos

**Hallazgo critico.** La funcion `build_new_content_correction_prompt_stage2()` (`new_content.py:1437-1445`) tiene esta firma:

```python
def build_new_content_correction_prompt_stage2(
    draft_content: str,
    target_length: int = 1500,
    keyword: str = "",
    links_to_verify: Optional[List[Dict]] = None,
    alternative_product: Optional[Dict] = None,
    products: Optional[List[Dict]] = None,
    visual_elements: Optional[List[str]] = None,
) -> str:
```

**No hay parametro de arquetipo.** El pipeline caller en `pipeline.py:506` llama a la funcion sin pasar informacion del arquetipo:

```python
stage2_prompt = new_content.build_correction_prompt_stage2(**stage2_kwargs)
```

El checklist de Stage 2 contiene 6 secciones identicas para todos los arquetipos:
1. `analisis_tecnico` — estructura HTML CMS (3 articles)
2. `keyword_seo` — densidad, placement, distribucion
3. `tono_marca` — anti-IA, personalidad, emojis
4. `cumplimiento_enlaces` — enlaces presentes/faltantes
5. `datos_producto` — uso de ventajas/desventajas
6. `elementos_visuales` — componentes solicitados presentes/faltantes

**Lo que NO puede verificar por ser generico:**

| Arquetipo | Verificacion ausente |
|-----------|---------------------|
| ARQ-2 | Pasos numerados? Seccion de requisitos previos? Progresion logica? |
| ARQ-4 | Puntuacion/rating en veredicto? Tabla de specs? Benchmarks? |
| ARQ-5 | Ganador declarado? Tabla comparativa lado a lado? Secciones "cuando elegir A/B"? |
| ARQ-7 | Productos numerados en orden? Badges "Mejor global"/"Mejor calidad-precio"? Criterio de ranking explicito? |
| ARQ-16 | Piramide invertida? Fecha de disponibilidad? Info de precio/preventa? Fuentes citadas? |

El mismo problema afecta a `build_rewrite_correction_prompt_stage2()` en `rewrite.py:929`.

---

## 3. Top 3 problemas cross-arquetipo

### P1: Stage 2 es completamente ciego al arquetipo (CRITICO)

**Impacto:** Alto — el analisis critico es la unica oportunidad de corregir el borrador antes del output final. Si no puede detectar defectos estructurales especificos del arquetipo, estos pasan al contenido publicado.

**Evidencia:**
- `build_new_content_correction_prompt_stage2()` en `new_content.py:1437` — sin parametro de arquetipo
- `build_rewrite_correction_prompt_stage2()` en `rewrite.py:929` — idem
- Pipeline caller en `pipeline.py:506` — no pasa arquetipo al builder de Stage 2
- El JSON de output de Stage 2 (`new_content.py:1049-1127`) no tiene seccion de cumplimiento del arquetipo

**Consecuencia:** Un ranking sin numeros, una comparativa sin ganador, o una noticia sin piramide invertida pasan Stage 2 sin ser flagged.

### P2: Elementos visuales son opt-in, no archetype-enforced

**Impacto:** Medio — el usuario puede desactivar componentes criticos para el arquetipo sin advertencia.

**Evidencia:**
- Cada arquetipo define `visual_elements` recomendados en `config/arquetipos.py`
- Pero Stage 2 solo verifica los elementos que el *usuario selecciono* en la UI (`new_content.py:1547-1549`)
- No hay floor de minimos por arquetipo

**Consecuencia:** Si el usuario deselecciona `verdict` para una comparativa, Stage 2 no lo flagea como problema. El contenido se genera sin veredicto — un defecto grave para ese tipo de contenido.

**Nota:** La auditoria UX (P0.1) mejoro la UI para pre-seleccionar los elementos recomendados, pero no hay enforcement server-side.

### P3: Rewrite mode carece de secondary keywords

**Impacto:** Medio — el contenido reescrito pierde riqueza semantica respecto al contenido nuevo.

**Evidencia:**
- `new_content.py` acepta `secondary_keywords` en Stage 1 (L1190) y las inyecta como instrucciones de uso
- `rewrite.py` no tiene referencia a secondary keywords en ninguna etapa — confirmado por grep exhaustivo
- La UI de rewrite (`ui/rewrite.py`) no tiene campo para secondary keywords

**Consecuencia:** Articulos reescritos cubren la keyword principal pero pierden oportunidades de posicionar long-tail variants y keywords semanticamente relacionadas.

---

## 4. Quick wins (benefician a todos los arquetipos)

| ID | Cambio | Fichero(s) | Esfuerzo | Impacto |
|----|--------|------------|----------|---------|
| QW-1 | Pasar `arquetipo_code` y `arquetipo_structure` a Stage 2. Anadir bloque condicional con checklist items especificos por arquetipo. | `prompts/new_content.py` L1437 + `core/pipeline.py` L506 | ~15 lineas | Alto |
| QW-2 | Anadir validacion de visual elements minimos del arquetipo en Stage 2: "Estos elementos son OBLIGATORIOS para este arquetipo, independientemente de la seleccion del usuario: {archetype.visual_elements}" | `prompts/new_content.py` L1493 | ~10 lineas | Medio |
| QW-3 | Anadir soporte `secondary_keywords` en `rewrite.py` — nuevo campo en config dict, inyeccion en Stage 1, verificacion en Stage 2 | `prompts/rewrite.py` + `ui/rewrite.py` | ~20 lineas | Medio |
| QW-4 | Anadir instruccion de meta description (max 155 chars, con keyword) como comentario HTML al inicio del output | `prompts/brand_tone.py` `REGLAS_CRITICAS_COMUNES` | ~5 lineas | Bajo |

---

## 5. Mejoras especificas por arquetipo (ordenadas por esfuerzo)

### ARQ-5 Comparativa A vs B

| # | Mejora | Esfuerzo | Donde |
|---|--------|----------|-------|
| 1 | Anadir instruccion de "winner declaration" en Stage 1: "El veredicto DEBE declarar un ganador claro o explicar concretamente por que es un empate tecnico con perfiles de usuario para cada opcion" | Bajo | `new_content.py` Stage 1, bloque condicional si arquetipo == ARQ-5 |
| 2 | Anadir check en Stage 2: "El veredicto nombra un ganador? Si dice 'depende de tus necesidades' sin perfiles concretos, es un problema CRITICO" | Bajo | `new_content.py` Stage 2 (requiere QW-1) |
| 3 | Cambiar `table` por `comparison_table` en `visual_elements` del arquetipo, o anadir instruccion de usar `<table class="comparison-table">` para la tabla comparativa principal | Medio | `config/arquetipos.py` L180 + hint en `new_content.py` |

### ARQ-7 Roundup / Mejores X

| # | Mejora | Esfuerzo | Donde |
|---|--------|----------|-------|
| 1 | Anadir instruccion de ranking numerado: "Numera los productos del 1 al N en orden de recomendacion. El #1 es tu recomendacion principal." | Bajo | `new_content.py` Stage 1, condicional ARQ-7 |
| 2 | Anadir instruccion de badges: "El producto #1 debe llevar badge 'Mejor en general'. Si hay uno con mejor relacion calidad-precio, anadirle badge 'Mejor calidad-precio'." | Bajo | `new_content.py` Stage 1, condicional ARQ-7 |
| 3 | Anadir check en Stage 2: "Los productos estan explicitamente numerados en orden? Hay badge de 'Mejor en general'?" | Bajo | `new_content.py` Stage 2 (requiere QW-1) |
| 4 | Anadir instruccion de uso de `grid` para fichas de producto: "Usa `<div class='grid cols-2'>` o `cols-3` para mostrar la ficha resumen de cada producto con specs clave, precio y badge." | Medio | `new_content.py` visual elements hint, condicional ARQ-7 |

### ARQ-16 Novedades y Lanzamientos

| # | Mejora | Esfuerzo | Donde |
|---|--------|----------|-------|
| 1 | Anadir instruccion de piramide invertida: "Los primeros 2 parrafos deben responder: que producto, que novedad principal, cuando estara disponible, a que precio. El resto desarrolla los detalles." | Bajo | `new_content.py` Stage 1, condicional ARQ-16 |
| 2 | Anadir instruccion de temporalidad: "Incluye fechas concretas de disponibilidad. Diferencia entre 'ya disponible', 'preventa abierta' y 'proximamente'." | Bajo | `new_content.py` Stage 1, condicional ARQ-16 |
| 3 | Revisar si `verdict` debe anadirse a `visual_elements` del arquetipo o si la "Conclusion" de una noticia tiene formato distinto al verdict-box de un review/comparativa. Posible solucion: renombrar la seccion en la estructura a "Veredicto: merece la pena?" | Medio | `config/arquetipos.py` L542 |

### ARQ-2 Guia Paso a Paso

| # | Mejora | Esfuerzo | Donde |
|---|--------|----------|-------|
| 1 | Anadir diferenciacion de `check_list`: "Usa `<ul class='check-list'>` para los requisitos previos (herramientas, materiales). Usa `<ol>` con pasos numerados para el proceso en si. No mezclar ambos formatos." | Bajo | `new_content.py` visual elements hint, condicional ARQ-2 |
| 2 | Anadir check en Stage 2: "Los pasos estan en una lista ordenada `<ol>`? Hay seccion de requisitos previos separada de los pasos?" | Bajo | `new_content.py` Stage 2 (requiere QW-1) |

### ARQ-4 Review / Analisis de Producto

| # | Mejora | Esfuerzo | Donde |
|---|--------|----------|-------|
| 1 | Anadir check en Stage 2: "El veredicto incluye una puntuacion o rating explicito?" | Bajo | `new_content.py` Stage 2 (requiere QW-1) |
| 2 | Anadir instruccion de tabla de benchmarks: "Si hay datos de rendimiento o specs comparables, presentarlos en una `<table>` con la alternativa como referencia." | Medio | `new_content.py` Stage 1, condicional ARQ-4 |

---

## 6. Observaciones adicionales

### Truncado de draft en Stage 2

`draft_content[:12000]` en `new_content.py:1508` trunca el borrador a 12.000 caracteres para el analisis de Stage 2. Para arquetipos largos como ARQ-7 (2200 palabras objetivo, ~13.000-15.000 caracteres con HTML/CSS), el veredicto y las FAQs pueden quedar fuera del texto analizado. Stage 2 no puede verificar lo que no ve.

**Recomendacion:** Evaluar si 12.000 caracteres es suficiente para los arquetipos mas largos, o si el truncado deberia ser dinamico basado en `target_length`.

### campos_especificos sin enforcement

Los `campos_especificos` definidos por arquetipo (ej: ARQ-7 tiene `mejor_global`, `mejor_calidad_precio`; ARQ-5 tiene `ganador`) estan disponibles como campos de UI pero no se validan en Stage 2. Son informacion que el usuario puede proporcionar, pero Claude no esta obligado a reflejar en el output.

### ARQUETIPOS_CON_MINI_STORIES

El set en `new_content.py:57-78` excluye correctamente ARQ-2 (how-to) y ARQ-16 (noticia). Los tutoriales no necesitan mini-historias de reviews, y las noticias de lanzamiento no deben contenerlas. ARQ-4, ARQ-5 y ARQ-7 estan incluidos, lo cual es coherente con su naturaleza orientada a producto.

### Rewrite Stage 2 igualmente ciego

`build_rewrite_correction_prompt_stage2()` en `rewrite.py:929` tiene el mismo problema que new_content: no recibe arquetipo. El fix QW-1 deberia aplicarse tambien a este fichero para consistencia.

---

## 7. Tabla resumen de acciones

| ID | Accion | Tipo | Arquetipo | Fichero principal | Esfuerzo |
|----|--------|------|-----------|-------------------|----------|
| QW-1 | Pasar arquetipo a Stage 2 + checklist condicional | Cross | Todos | `prompts/new_content.py`, `core/pipeline.py` | Bajo |
| QW-2 | Visual elements minimos por arquetipo en Stage 2 | Cross | Todos | `prompts/new_content.py` | Bajo |
| QW-3 | Secondary keywords en rewrite | Cross | Todos | `prompts/rewrite.py`, `ui/rewrite.py` | Bajo |
| QW-4 | Instruccion de meta description | Cross | Todos | `prompts/brand_tone.py` | Bajo |
| A5-1 | Winner declaration en Stage 1 | Especifico | ARQ-5 | `prompts/new_content.py` | Bajo |
| A5-2 | Winner check en Stage 2 | Especifico | ARQ-5 | `prompts/new_content.py` | Bajo |
| A5-3 | Usar `comparison_table` CSS class | Especifico | ARQ-5 | `config/arquetipos.py`, `prompts/new_content.py` | Medio |
| A7-1 | Numbered ranking instruction | Especifico | ARQ-7 | `prompts/new_content.py` | Bajo |
| A7-2 | Badges "Mejor global" / "Mejor calidad-precio" | Especifico | ARQ-7 | `prompts/new_content.py` | Bajo |
| A7-3 | Ranking check en Stage 2 | Especifico | ARQ-7 | `prompts/new_content.py` | Bajo |
| A7-4 | Grid usage para fichas de producto | Especifico | ARQ-7 | `prompts/new_content.py` | Medio |
| A16-1 | Piramide invertida instruction | Especifico | ARQ-16 | `prompts/new_content.py` | Bajo |
| A16-2 | Temporalidad/fechas instruction | Especifico | ARQ-16 | `prompts/new_content.py` | Bajo |
| A16-3 | Clarificar verdict vs conclusion | Especifico | ARQ-16 | `config/arquetipos.py` | Medio |
| A2-1 | check_list vs pasos diferenciacion | Especifico | ARQ-2 | `prompts/new_content.py` | Bajo |
| A2-2 | Pasos numerados check en Stage 2 | Especifico | ARQ-2 | `prompts/new_content.py` | Bajo |
| A4-1 | Scoring/rating check en Stage 2 | Especifico | ARQ-4 | `prompts/new_content.py` | Bajo |
| A4-2 | Benchmark table instruction | Especifico | ARQ-4 | `prompts/new_content.py` | Medio |

**Orden de implementacion recomendado:** QW-1 → QW-2 → {A5-1, A5-2, A7-1, A7-2, A7-3, A16-1, A16-2, A2-1, A2-2, A4-1} → QW-3 → QW-4 → {A5-3, A7-4, A16-3, A4-2}

QW-1 primero porque es prerequisito para todos los checks de Stage 2 especificos por arquetipo.
