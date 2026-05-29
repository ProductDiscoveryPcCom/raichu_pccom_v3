# Validación — Blindaje integral de tablas (todos los tipos)

**Fecha:** 2026-05-28
**Branch:** `fix/cms-comparison-table-css`
**Predecesor:** PR #19 (commit `c07fdb0`) — solo `.comparison-table`.

## Qué se ha cambiado

Extender el patrón de PR #19 a los **3 tipos de tabla** que emite Raichu:

1. `<table>` genérico — **roto hoy en CMS** por `.chunkPostView table{display:block}`.
2. `<table class="comparison-table">` — ya blindado (PR #19), intacto.
3. `<div class="lt">` — defensa proactiva (CMS actual no lo rompe).

### Ficheros tocados

- [utils/table_fixer.py](../../utils/table_fixer.py) — refactor: 3 constantes
  (`_GENERIC_TABLE_OVERRIDE`, `_COMPARISON_TABLE_OVERRIDE_BODY`,
  `_LIGHT_TABLE_OVERRIDE`). Marcador único `/* PCC-TABLE-FIX */`. Función pública
  renombrada a `enforce_table_css`; alias `enforce_comparison_table_css =
  enforce_table_css` mantenido (no rompe imports en [core/pipeline.py:1057](../../core/pipeline.py#L1057)).
  Stats ampliados con `generic_tables_found` y `light_tables_found`.
- [config/cms_compatible.css](../../config/cms_compatible.css) — `table thead th`
  y `.lt .r:first-child` pasan a `#170453 / #fff` (paridad editor↔CMS).
- [config/design_system.py](../../config/design_system.py) — `_CANONICAL_CSS`:
  `thead th{background:#170453;color:#fff;...}`.
- [static/biblioteca_visual.html](../../static/biblioteca_visual.html) — replica
  ambos cambios en `<style id="cms-base">`.
- [utils/css_integrity.py](../../utils/css_integrity.py) — Check 4-bis
  (`table thead th` con #170453 en fuentes literales) + Check 5 (`.lt
  .r:first-child` con #170453 en `cms_compatible.css`).
- [tests/test_tables.py](../../tests/test_tables.py) — 8 tests nuevos en
  `TestTableEnforcerMultiType` + 1 reescrito (legacy
  `test_no_op_without_comparison_table` → split en 2 tests acordes a la
  nueva conducta multi-tipo).
- [tests/test_ux_ui_functionality.py](../../tests/test_ux_ui_functionality.py) —
  3 tests nuevos en `TestCSSIntegrity` (Check 4-bis + Check 5 + smoke
  `integrity_check_passes`).

## Selectores y especificidades (CSS L4)

| Selector inyectado | Especificidad | CMS rival típico | Margen |
|---|---|---|---|
| `article table:not(.comparison-table)` | (0,1,2) | `.chunkPostView table` (0,1,1) | +1 |
| `article table:not(.comparison-table) thead th` | (0,1,4) | `.chunkPostView th` (0,1,1) | +3 |
| `article .lt .r:first-child` | (0,3,1) | `.chunkPostView .r:first-child` (0,3,0) | +1 |
| `.comparison-table th` (PR#19) | (0,1,1) | `.chunkPostView th` (0,1,1) | empate → último gana |

`:not(.comparison-table)` aporta la especificidad del argumento (no suma extra
por la pseudo-clase). El `!important` en `display`, `background`, `color` y
`thead/tbody{display:*-group}` no es red de seguridad: es necesario porque el
margen es de un solo escalón y, si el CMS añadiera mañana una clase contenedora
adicional (p.ej. `.chunkPostView.article-body table` = (0,2,1)), perderíamos.

## Cómo verificar manualmente

### 1. Render generado por la pipeline

```bash
streamlit run app.py
```

- Generar un artículo con ARQ-7 (fuerza `comparison-table`) o ARQ-4/13 con specs
  (fuerza `<table>`), y un arquetipo con `light_table` en `visual_elements`
  (fuerza `.lt`).
- En "Resultado", abrir el HTML y buscar `<style>`. Confirmar:
  - **Un único** marcador `/* PCC-TABLE-FIX */`.
  - Los **3 bloques** presentes (uno por tipo detectado):
    - `article table:not(.comparison-table){display:table !important;...}`
    - `.comparison-table{display:table !important;...}`
    - `article .lt{display:block !important;...}`

### 2. Inspección en CMS de producción (no preview)

Publicar el HTML en el CMS real (dentro de `.chunkPostView`). Inspector del
navegador:

| Selector | Valor esperado |
|---|---|
| `<table>` (sin class) | `display: table` |
| `<table> thead th` | `background-color: rgb(23, 4, 83)`, `color: rgb(255, 255, 255)` |
| `.comparison-table th` | `background-color: rgb(23, 4, 83)`, `color: rgb(255, 255, 255)` |
| `.lt .r` | `display: grid` |
| `.lt .r:first-child` | `background-color: rgb(23, 4, 83)`, `color: rgb(255, 255, 255)` |

### 3. Contraste WCAG

- `#fff` (texto) sobre `#170453` (fondo) → ratio ≈ **16.4:1** (AAA, holgado).
- `#141822` (td) sobre `#fff` → AAA.
- `#141822` sobre `#F4F4F4` (zebra par) → AAA.

### 4. Tests

```bash
PYTHONPATH=. python -m pytest tests/ -q
```

Esperado: **1105 verdes** (1093 originales + 12 nuevos).

### 5. Reproducción sintética (opcional)

`tmp/test_tables_all_types.py` sigue funcionando como fuente externa de
inspección visual:

```bash
PYTHONPATH=. python tmp/test_tables_all_types.py
```

Genera `tmp/tables_clean.html` (editor) y `tmp/tables_cms.html` (CMS hostil
simulado). El segundo debe mostrar ahora los 3 tipos con `display:table` /
`display:grid` y headers azules (antes la `<table>` genérica colapsaba a
`display:block` y el header era `#ebebeb`).

## Riesgos vivos

| Riesgo | Estado |
|---|---|
| CMS añade contenedor extra y eleva especificidad → `!important` lo neutraliza | mitigado |
| Modelo emite `style=""` inline en `<table>` → ganaría sobre el override | no observado en prompts revisados ([prompts/new_content.py:780](../../prompts/new_content.py#L780)); contingencia: añadir scrubber inline en `fix_tables`. |
| Editor cambia visualmente (th gris → azul) | aceptado (Opción A). Capturas before/after en este doc cuando se publique en `htmls/`. |

## Rollback parcial

Si el override genérico provoca regresión en algún arquetipo, comentar la línea:

```python
# utils/table_fixer.py — enforce_table_css()
if stats['generic_tables_found'] > 0:
    blocks.append(_GENERIC_TABLE_OVERRIDE)   # ← comentar esta línea
```

Y revertir las dos líneas del `<table thead th>` en las 3 fuentes CSS. La
protección de `.comparison-table` (PR#19) queda intacta.
