# Validación Fase 4 — A/B (2026-05-20)

> ⚠️ **SUPERADO (2026-05-20).** Este informe concluyó MERGE-READY=NO atribuyendo la
> pérdida del `<article>` verdict a debilidad del prompt / estructura. Investigación
> posterior el mismo día encontró la **causa raíz real: truncación por `max_tokens=8000`**
> (la respuesta de Stage 3 se cortaba antes de emitir el verdict). Con `max_tokens=16000+`
> los 3 articles salen de forma natural (re-validación 10/10). El determinismo de Fase 4
> se revirtió parcialmente (commit `0f9b929`) y el fix real fue `max_tokens=20000` en
> producción. Conservar como registro histórico del proceso de diagnóstico.

**Baseline:** main @ `18326ea`
**Modificado:** phase4-prompts @ `983e379`
**Keywords:** 5 · **Gens por keyword:** 2 · **Pares totales:** 10

> Nota de ejecución: este reporte se generó vía el agente `prompt-ab-validator`. La
> recursión Agent→Agent (invocar `content-quality-auditor` como subagente) no está
> disponible en el harness desde un subagente, por lo que se aplicó el **fallback
> documentado**: inlinear los criterios C1–C6 delegando en las mismas funciones de
> `utils/html_utils.py` (`validate_word_count_target`, `validate_cms_articles`,
> `detect_ai_phrases`) y `prompts.new_content.ARQUETIPOS_CON_MINI_STORIES`. No se
> reinventó ninguna métrica — single source of truth conservado.

## Criterios (protocolo Fase 4)

| # | Criterio | Tipo | Fuente |
|---|----------|------|--------|
| C1 | Word count ±15% del target | binario | `validate_word_count_target(html, target, 0.15)` |
| C2 | Estructura CMS 3-article (`main`/`faqs`/`verdict`) | binario | `validate_cms_articles` |
| C3 | TOC + FAQs ≥ baseline | comparativo | conteo TOC y items FAQ en `contentGenerator__faqs` |
| C4 | Mini-stories sintéticas en arquetipos ∈ miniset sin reviews | binario | `ARQUETIPOS_CON_MINI_STORIES` + grep "Perfil de uso" |
| C5 | Frases anti-IA ≤ baseline | comparativo | `detect_ai_phrases` |
| C6 | Lectura humana ≥ baseline−0.3 | manual | requiere revisión cualitativa (⚪) |

Targets por arquetipo (de `config/arquetipos.py`): ARQ-3=1600 · ARQ-4=2000 · ARQ-7=2200 · ARQ-13=1800 · ARQ-20=2000.
`has_reviews=False` en todas las keywords (objetivo: validar mini-stories sintéticas R3.3).
Notación celdas: `baseline → modificado`. ✅ pasa · ❌ falla · = sin cambio · ⚪ manual · n/a no aplica.

## Resumen A/B

| Keyword | Arq | C1 word (b→m) | C2 CMS (b→m) | C3 TOC/FAQ (b→m) | C4 mini-stories | C5 anti-IA (b→m) | C6 | Veredicto |
|---------|-----|---------------|--------------|------------------|-----------------|------------------|----|-----------|
| que es un ssd (g1) | ARQ-3 | ❌→❌ (+26.9%→+44.7%) | ✅→❌ (pierde verdict) | TOC=/= · FAQ 5→6 | n/a | 0→0 = | ⚪ | ❌ REGRESIÓN |
| que es un ssd (g2) | ARQ-3 | ❌→❌ (+44.8%→+39.9%) | ✅→✅ | TOC=/= · FAQ 6→6 | n/a | 0→0 = | ⚪ | ❌ FAIL (C1) |
| review producto (g1) | ARQ-4 | ✅→✅ (+12%→−12.7%) | ✅→❌ (pierde faqs+verdict) | TOC=/= · FAQ 5→0 | ✅ presente (modif) | 0→0 = | ⚪ | ❌ REGRESIÓN |
| review producto (g2) | ARQ-4 | ✅→✅ (+4.2%→−3%) | ✅→❌ (pierde faqs+verdict) | TOC=/= · FAQ 6→0 | ✅ presente (modif) | 0→0 = | ⚪ | ❌ REGRESIÓN |
| mejores portatiles (g1) | ARQ-7 | ❌→✅ (−19.4%→−3.7%) | ❌→❌ (faltan faqs+verdict ambos) | TOC=/= · FAQ 0→0 | ❌ ausente | 0→0 = | ⚪ | ❌ FAIL (C2) |
| mejores portatiles (g2) | ARQ-7 | ❌→✅ (−16.6%→+3.2%) | ❌→❌ (faltan faqs+verdict ambos) | TOC=/= · FAQ 0→0 | ❌ ausente | 0→0 = | ⚪ | ❌ FAIL (C2) |
| configurar router (g1) | ARQ-13 | ❌→✅ (+58.1%→+11.4%) | ❌→❌ (pierde faqs además de verdict) | TOC=/= · FAQ 6→0 | n/a | 0→0 = | ⚪ | ❌ REGRESIÓN |
| configurar router (g2) | ARQ-13 | ❌→❌ (+37.2%→+50.4%) | ❌→❌ (gana faqs, falta verdict) | TOC=/= · FAQ 0→6 | n/a | 0→0 = | ⚪ | ❌ FAIL (C1, C2) |
| ofertas black friday (g1) | ARQ-20 | ❌→❌ (−16.9%→+17.1%) | ❌→❌ (gana faqs, falta verdict) | TOC=/= · FAQ 0→6 | ❌ ausente | 0→0 = | ⚪ | ❌ FAIL (C1, C2) |
| ofertas black friday (g2) | ARQ-20 | ✅→✅ (+3.5%→+12.4%) | ❌→❌ (falta verdict ambos) | TOC=/= · FAQ 6→7 | ❌ ausente | 0→0 = | ⚪ | ❌ FAIL (C2) |

### Lectura agregada por criterio

- **C1 (word count ±15%):** mejora neta en regresión de longitud — ARQ-7 y ARQ-13/g1 pasan de fuera-de-rango a dentro. Pero ARQ-3 sigue muy por encima (+40-45%) en ambas ramas y ARQ-13/g2 empeora (+37%→+50%). C1 no es regresión global pero **tampoco pasa en todos los modificados** (4/10 modificados siguen ❌).
- **C2 (CMS 3-article):** **regresión grave y sistémica.** El artículo `contentGenerator__verdict` falta en **9/10 HTMLs modificados** (solo arq03/g2 lo conserva). Además ARQ-4 (ambos gens) y ARQ-13/g1 pierden también `contentGenerator__faqs`, que sí estaba en baseline. Esto viola el requisito "NO TOCAR / Estructura CMS 3-article" de `CLAUDE.md`.
- **C3 (TOC/FAQ):** TOC presente en todos (sin cambio). FAQs mixto: mejora donde el modificado añade el bloque (ARQ-7 no, ARQ-13/g2 0→6, ARQ-20/g1 0→6) pero **empeora donde se pierde el artículo faqs** (ARQ-4 5→0 y 6→0; ARQ-13/g1 6→0). C3 empeora en 3 pares.
- **C4 (mini-stories):** **funciona y es la mejora esperada (R3.3)** para ARQ-4: ambos gens modificados contienen bloques sintéticos reales ("Perfil de uso: el profesional creativo", "...el usuario que viene de un iPhone 12 o 13") ausentes en baseline. Sin embargo ARQ-7 y ARQ-20 (también ∈ miniset, sin reviews) **no** muestran mini-stories en el modificado.
- **C5 (anti-IA):** 0 hits en todas las ramas. Sin cambio, no empeora. ✅ comparativo.
- **C6 (lectura humana):** ⚪ MANUAL en todos — no automatizable, requiere revisión cualitativa de un editor.

## Reportes detallados

### que es un ssd — ARQ-3 (target 1600w)

**gen1** — baseline `+26.9%` (2031w) → modificado `+44.7%` (2315w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ +26.9% | ❌ +44.7% | empeora |
| C2 | CMS 3-art | ✅ main+faqs+verdict | ❌ falta `verdict` | **REGRESIÓN** |
| C3 | TOC/FAQ | TOC ✅ · FAQ 5 | TOC ✅ · FAQ 6 | FAQ mejora |
| C4 | mini-stories | n/a (ARQ-3 ∉ miniset) | n/a | — |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **REGRESIÓN** (C2 pierde verdict).

**gen2** — baseline `+44.8%` (2316w) → modificado `+39.9%` (2238w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ +44.8% | ❌ +39.9% | sigue fuera |
| C2 | CMS 3-art | ✅ completo | ✅ completo | = |
| C3 | TOC/FAQ | TOC ✅ · FAQ 6 | TOC ✅ · FAQ 6 | = |
| C4 | mini-stories | n/a | n/a | — |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **FAIL** (C1 ambas ramas fuera de rango; sin regresión vs baseline).

### review producto — ARQ-4 (target 2000w, has_reviews=False)

**gen1** — baseline `+12%` (2240w) → modificado `−12.7%` (1746w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ✅ +12% | ✅ −12.7% | = (ambos en rango) |
| C2 | CMS 3-art | ✅ completo | ❌ faltan `faqs`+`verdict` | **REGRESIÓN** |
| C3 | TOC/FAQ | TOC ✅ · FAQ 5 | TOC ✅ · FAQ 0 | **empeora** |
| C4 | mini-stories | ausente | ✅ "Perfil de uso" sintético | **MEJORA (R3.3)** |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **REGRESIÓN** (C2/C3 pese a la mejora C4).

**gen2** — baseline `+4.2%` (2085w) → modificado `−3%` (1939w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ✅ +4.2% | ✅ −3% | = |
| C2 | CMS 3-art | ✅ completo | ❌ faltan `faqs`+`verdict` | **REGRESIÓN** |
| C3 | TOC/FAQ | TOC ✅ · FAQ 6 | TOC ✅ · FAQ 0 | **empeora** |
| C4 | mini-stories | ausente | ✅ "Perfil de uso" sintético | **MEJORA (R3.3)** |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **REGRESIÓN** (C2/C3).

### mejores portatiles — ARQ-7 (target 2200w)

**gen1** — baseline `−19.4%` (1774w) → modificado `−3.7%` (2119w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ −19.4% | ✅ −3.7% | **mejora** |
| C2 | CMS 3-art | ❌ faltan `faqs`+`verdict` | ❌ faltan `faqs`+`verdict` | = (ambos rotos) |
| C3 | TOC/FAQ | TOC ✅ · FAQ 0 | TOC ✅ · FAQ 0 | = |
| C4 | mini-stories | ausente | ausente | sin mejora (ARQ-7 ∈ miniset pero no genera) |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **FAIL** (C2 binario falla en modificado).

**gen2** — baseline `−16.6%` (1835w) → modificado `+3.2%` (2270w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ −16.6% | ✅ +3.2% | **mejora** |
| C2 | CMS 3-art | ❌ faltan `faqs`+`verdict` | ❌ faltan `faqs`+`verdict` | = |
| C3 | TOC/FAQ | TOC ✅ · FAQ 0 | TOC ✅ · FAQ 0 | = |
| C4 | mini-stories | ausente | ausente | sin mejora |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **FAIL** (C2).

### configurar router — ARQ-13 (target 1800w)

**gen1** — baseline `+58.1%` (2845w) → modificado `+11.4%` (2005w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ +58.1% | ✅ +11.4% | **mejora** |
| C2 | CMS 3-art | ❌ falta `verdict` | ❌ faltan `faqs`+`verdict` | **empeora** |
| C3 | TOC/FAQ | TOC ✅ · FAQ 6 | TOC ✅ · FAQ 0 | **empeora** |
| C4 | mini-stories | n/a (ARQ-13 ∉ miniset) | n/a | — |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **REGRESIÓN** (C2/C3 pese a mejora C1).

**gen2** — baseline `+37.2%` (2469w) → modificado `+50.4%` (2708w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ +37.2% | ❌ +50.4% | empeora |
| C2 | CMS 3-art | ❌ faltan `faqs`+`verdict` | ❌ falta `verdict` (recupera faqs) | parcial |
| C3 | TOC/FAQ | TOC ✅ · FAQ 0 | TOC ✅ · FAQ 6 | FAQ mejora |
| C4 | mini-stories | n/a | n/a | — |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **FAIL** (C1 y C2 fallan en modificado).

### ofertas black friday — ARQ-20 (target 2000w)

**gen1** — baseline `−16.9%` (1663w) → modificado `+17.1%` (2343w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ❌ −16.9% | ❌ +17.1% | sigue fuera (pasa de bajo a alto) |
| C2 | CMS 3-art | ❌ faltan `faqs`+`verdict` | ❌ falta `verdict` (recupera faqs) | parcial |
| C3 | TOC/FAQ | TOC ✅ · FAQ 0 | TOC ✅ · FAQ 6 | FAQ mejora |
| C4 | mini-stories | ausente | ausente | sin mejora (ARQ-20 ∈ miniset) |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **FAIL** (C1 y C2).

**gen2** — baseline `+3.5%` (2070w) → modificado `+12.4%` (2249w)
| # | Criterio | baseline | modificado | Δ |
|---|----------|----------|------------|---|
| C1 | word ±15% | ✅ +3.5% | ✅ +12.4% | = (ambos en rango) |
| C2 | CMS 3-art | ❌ falta `verdict` | ❌ falta `verdict` | = (ambos rotos) |
| C3 | TOC/FAQ | TOC ✅ · FAQ 6 | TOC ✅ · FAQ 7 | FAQ mejora |
| C4 | mini-stories | ausente | ausente | sin mejora |
| C5 | anti-IA | 0 | 0 | = |
| C6 | lectura | ⚪ | ⚪ | manual |
Veredicto par: **FAIL** (C2 binario).

## Veredicto agregado

**MERGE-READY: NO**

**Justificación:**

El criterio MERGE-READY exige que (a) todos los criterios binarios (C1, C2, C4) pasen
en el modificado y (b) ningún criterio comparativo (C3, C5) empeore vs baseline. Ninguna
de las dos condiciones se cumple:

1. **C2 (binario) falla en 9/10 HTMLs modificados** — el artículo
   `contentGenerator__verdict` desaparece en todos salvo arq03/g2, y `contentGenerator__faqs`
   se pierde adicionalmente en ARQ-4 (ambos gens) y ARQ-13/g1. La estructura CMS 3-article
   está marcada como **"NO TOCAR"** en `CLAUDE.md` y es un requisito del CMS de PcComponentes.
   Esto es un bloqueante absoluto de merge.

2. **C1 (binario) sigue fuera de rango en 4/10 modificados** (ARQ-3 g1/g2, ARQ-13/g2,
   ARQ-20/g1). La condensación de Stage 2 (R2.4) sí mejoró la longitud en ARQ-7 y ARQ-13/g1,
   pero ARQ-3 sigue ~40% por encima del target y ARQ-13/g2 empeoró.

3. **C3 (comparativo) empeora en 3 pares** (ARQ-4 g1/g2, ARQ-13/g1) como efecto colateral
   directo de la pérdida del artículo `faqs` en C2.

**Lo que sí funciona (mérito de la rama):**

- **C4 / mini-stories sintéticas (R3.3) confirmado para ARQ-4 sin reviews:** ambos gens
  modificados contienen bloques "Perfil de uso" reales ausentes en baseline. La feature
  objetivo de R3.3 está operativa para su arquetipo diana.
- **C1 mejora la regresión de longitud baja** en ARQ-7 (ambos gens pasan de fuera a dentro
  de rango), efecto esperado de la condensación de Stage 2.
- **C5 anti-IA:** 0 hits en todas las ramas; sin regresión.

**Acción recomendada antes de re-validar:**

1. **Bloqueante:** corregir la generación para que Stage 3 vuelva a emitir SIEMPRE los 3
   `<article>` (`main`, `faqs`, `verdict`). Investigar si la condensación de Stage 2 (R2.4)
   o el cacheo de CSS al import truncó las instrucciones de estructura en el prompt de
   Stage 3. Revisar `prompts/new_content.py` (`build_final_prompt_stage3` y
   `_build_stage3_checklist`).
2. Ajustar control de longitud para ARQ-3 (consistentemente +40%) y ARQ-13.
3. Verificar por qué las mini-stories no se disparan en ARQ-7/ARQ-20 (ambos ∈
   `ARQUETIPOS_CON_MINI_STORIES`) cuando `has_reviews=False`.
4. Regenerar HTMLs en ambas ramas y re-ejecutar este protocolo. Mantener `min_pairs=5`.

**Observación de método:** C6 (lectura humana) quedó ⚪ MANUAL en los 10 pares; un editor
debe completarlo antes de cualquier merge aunque C1/C2 se resuelvan.
