# UX Audit — Modo "Nuevo" — Raichu v5.1.0

**Fecha:** 2026-03-23
**Scope:** Simplificacion del formulario de contenido nuevo
**Ficheros analizados:** `ui/inputs.py`, `ui/rewrite.py`, `ui/sidebar.py`, `config/arquetipos.py`

## Resumen ejecutivo

El formulario de modo "Nuevo" expone ~40 widgets interactivos cuando se expande completamente. Solo 2 campos son realmente obligatorios (keyword + arquetipo). Los usuarios reportan que el formulario se siente abrumador antes de ver cualquier resultado. Este audit identifica 9 mejoras priorizadas por esfuerzo. Las 3 primeras (P0) ya estan implementadas.

---

## 1. Mapa del flujo actual

| Paso | Elemento | Tipo widget | Obligatorio | Fichero:Linea |
|------|----------|-------------|-------------|---------------|
| 1 | GSC Date Warning | info banner | N/A | inputs.py:2494 |
| 2 | **Keyword** | text_input | OBLIGATORIO | inputs.py:2499 |
| 3 | **Arquetipo** (37 opciones) | selectbox | OBLIGATORIO | inputs.py:2504 |
| 4 | **Longitud objetivo** | slider | DEFAULT AUTO | inputs.py:2507 |
| 5 | ~~Keywords secundarias~~ *(movido a Avanzado en P0.2)* | text_area | Opcional | inputs.py:2600 |
| 6 | Indicador de briefing | caption | N/A | inputs.py:2510 |
| 7 | Briefing (8-14 textareas) | expander colapsado | Opcional | inputs.py:2518 |
| 8 | Header "Opciones adicionales" | label | N/A | inputs.py:2530 |
| 9 | Productos (checkbox + URL/JSON/rol) | expander colapsado | Opcional | inputs.py:2539 |
| 10 | Enlaces internos (hasta 10) | expander colapsado | Opcional | inputs.py:2555 |
| 11 | Visual + Estructura + Instrucciones | expander colapsado | Opcional | inputs.py:2571 |
| 11a | — Elementos visuales (24 checkboxes + variantes CMS) | checkboxes | Opcional | inputs.py:1549 |
| 11b | — Estructura de encabezados (H2/H3/H4) | number_inputs | Opcional | inputs.py:2591 |
| 11c | — Instrucciones adicionales | text_area | Opcional | inputs.py:2596 |
| 11d | — Keywords secundarias *(nuevo en P0.2)* | text_area | Opcional | inputs.py:2600 |
| 12 | Errores de validacion | error display | Sistema | inputs.py:2617 |
| 13 | Resumen pre-generacion | info box | Sistema | inputs.py:2776 |

**Total widgets interactivos expandidos:** ~40+ (keyword, arquetipo, slider, ~14 briefing textareas, productos, 10 enlaces, 24 checkboxes visuales, encabezados, instrucciones, keywords secundarias).

---

## 2. Hallazgo clave: visual_elements ignoraba datos del arquetipo

Cada arquetipo en `config/arquetipos.py` define `visual_elements` (ej: ARQ-5 Comparativa → `["toc", "table", "verdict"]`). La funcion helper `get_visual_elements()` existe en arquetipos.py:1404. Sin embargo, `render_visual_elements_selector()` (inputs.py:1549) ignoraba estos datos — todos los checkboxes usaban defaults hardcoded (`toc=True`, `verdict=True`, resto `False`).

**Estado:** Corregido en P0.1 — ahora acepta `arquetipo_code` y pre-selecciona los elementos recomendados.

---

## 3. Flujo simplificado propuesto (5 pasos visibles)

| Paso | Contenido | Estado |
|------|-----------|--------|
| 1. Esencial | Keyword + Arquetipo + Longitud (auto-configurada) | Visible siempre |
| 2. Briefing | Preguntas guia del arquetipo (expander colapsado) | Visible, colapsado |
| 3. Productos | URLs + JSON de productos (con hint por arquetipo) | Visible, colapsado |
| 4. Enlaces | Enlaces internos con anchor text | Visible, colapsado |
| 5. Avanzado | Visual elements + Encabezados + Instrucciones + Keywords secundarias | Visible, colapsado |

**Campos eliminados de la vista principal:** Keywords secundarias (movidas al paso 5).

---

## 4. Secciones a ocultar por defecto

| Seccion | Estado actual | Propuesta | Razon |
|---------|--------------|-----------|-------|
| GSC Date Warning | Siempre visible | Solo mostrar si datos >7 dias | Solo relevante cuando los datos estan obsoletos |
| Keywords secundarias | Visible en seccion principal | **Movidas a expander Avanzado** (P0.2 hecho) | Rara vez usadas; reduce decisions en zona esencial |
| Briefing completo | Expander colapsado (8-14 textareas) | Mostrar solo top 3 preguntas + "ver todas" | 14 textareas es abrumador incluso dentro de un expander |
| Checkboxes de visual elements | Dentro de expander colapsado | **Auto-seleccionados desde arquetipo** (P0.1 hecho) + futuro: tag summary + "Personalizar" | 24 checkboxes nunca son necesarios |
| HTML Preview de componentes | Dentro de expander anidado | Eliminar o mover a docs externos | Casi nunca util durante rellenado de formulario |
| Modulos CMS (mod_cards, vcard_cards, etc.) | Dentro de checkboxes visuales | Ocultar tras sub-toggle "Mostrar modulos CMS" | Solo para power users |

---

## 5. Secciones a fusionar

1. **Keywords secundarias + Instrucciones adicionales** — Ambos son texto libre que enriquece el prompt. **P0.2 ya los coloca juntos** en el mismo expander. Futuro: fusionar en una unica seccion "Contexto extra".

2. **Elementos visuales + Estructura de encabezados** — Ambos controlan la estructura del output. Mantener agrupados como "Estructura del output" con auto-seleccion desde arquetipo + toggle "Personalizar".

3. **Base Elements + Table Elements + CMS Modules** — Actualmente 3 sub-secciones con headers separados dentro del selector visual. Futuro: aplanar en una lista unica con toggle "Mostrar modulos CMS avanzados".

---

## 6. Matriz arquetipo-campo (5 arquetipos principales)

| Campo | ARQ-5 Comparativa | ARQ-7 Roundup | ARQ-16 Noticias | ARQ-2 How-to | ARQ-4 Review |
|-------|:-:|:-:|:-:|:-:|:-:|
| Keyword | OBLIGATORIO | OBLIGATORIO | OBLIGATORIO | OBLIGATORIO | OBLIGATORIO |
| Arquetipo | OBLIGATORIO | OBLIGATORIO | OBLIGATORIO | OBLIGATORIO | OBLIGATORIO |
| Longitud | auto:1800 | auto:2200 | auto:1500 | auto:1800 | auto:2000 |
| Keywords sec. | util | util | poco util | util | util |
| Briefing | ALTO valor | ALTO valor | MEDIO valor | ALTO valor | ALTO valor |
| Productos | **CRITICO (2)** | **CRITICO (3-8)** | BAJO (0-1) | BAJO (0-1) | **CRITICO (1)** |
| Enlaces internos | util | util | util | util | util |
| Visual: toc | SI (arquetipo) | SI (arquetipo) | SI (arquetipo) | SI (arquetipo) | SI (arquetipo) |
| Visual: table | SI (arquetipo) | SI (arquetipo) | SI (arquetipo) | NO | SI (arquetipo) |
| Visual: comparison_table | ALTA relevancia | MEDIA | NO | NO | NO |
| Visual: grid | NO | SI (arquetipo) | NO | NO | NO |
| Visual: verdict | SI (arquetipo) | SI (arquetipo) | NO | NO | SI (arquetipo) |
| Visual: callout | NO | NO | SI (arquetipo) | SI (arquetipo) | SI (arquetipo) |
| Visual: check_list | NO | NO | NO | SI (arquetipo) | NO |
| Visual: modulos CMS | MEDIO | MEDIO | BAJO | BAJO | MEDIO |
| Encabezados | rara vez necesario | rara vez necesario | rara vez necesario | rara vez necesario | rara vez necesario |
| Instrucciones | util | util | util | util | util |

**Insight clave:** Para ARQ-16 (Noticias), la seccion de Productos casi nunca se necesita. Para ARQ-5 y ARQ-7, es critica y deberia auto-expandirse o al menos mostrar un hint prominente.

---

## 7. Prioridad de implementacion

### P0 — Quick wins (1-2h, sin cambios de arquitectura) — IMPLEMENTADOS

| ID | Cambio | Fichero | Estado |
|----|--------|---------|--------|
| P0.1 | Auto-seleccionar visual elements desde datos del arquetipo | inputs.py:1549 | Hecho |
| P0.2 | Mover keywords secundarias al expander Avanzado | inputs.py:2507→2600 | Hecho |
| P0.3 | Hint contextual por arquetipo en expander de Productos | inputs.py:2539 | Hecho |

### P1 — Esfuerzo medio (medio dia cada uno) — IMPLEMENTADOS

| ID | Cambio | Fichero | Detalle |
|----|--------|---------|---------|
| P1.1 | Truncar briefing a top 3 preguntas + boton "ver todas" | inputs.py:1084 | Hecho |
| P1.2 | Reemplazar checkboxes visuales con tag summary + toggle "Personalizar" | inputs.py:1549 | Hecho |
| P1.3 | Ocultar modulos CMS tras sub-toggle | inputs.py:1845 | Hecho |

### P2 — Refactors mayores (1-2 dias cada uno)

| ID | Cambio | Fichero | Detalle |
|----|--------|---------|---------|
| P2.1 | Form profiles por arquetipo (recomendado/opcional/oculto) | arquetipos.py + inputs.py | Hecho — _get_form_profile() oculta secciones irrelevantes |
| P2.2 | Wizard mode para primera vez | inputs.py + app.py | 3 pasos cuando `_has_generated_new` es False |
| P2.3 | Selector de arquetipo con busqueda y grupos | inputs.py:725 | Hecho — selector 2 niveles (Categoria -> Arquetipo) |

---

## 8. Riesgos y consideraciones

- **Degradacion graceful:** No romper el patron try/except en imports (app.py L227-326)
- **Compatibilidad de retorno:** `render_content_inputs()` debe mantener su signature `Tuple[bool, Dict]`
- **Session state:** No renombrar keys existentes — afecta `_saved_results_{mode}` al cambiar de modo
- **Override de auto-seleccion:** Los visual elements auto-seleccionados deben ser siempre editables por el usuario
- **Rewrite mode:** `render_visual_elements_selector()` se llama desde `ui/rewrite.py:2158` sin `arquetipo_code` — el parametro es opcional con default `None` para mantener compatibilidad
