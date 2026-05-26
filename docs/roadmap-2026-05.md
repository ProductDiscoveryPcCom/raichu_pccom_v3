# Roadmap 2026-05 — Resiliencia, fixes de producción y nuevas features

**Periodo:** 2026-05-22 → 2026-05-26
**Origen:** No es una auditoría dirigida. Documenta el trabajo **reactivo a las pruebas
en producción (Streamlit Cloud)** del usuario, más dos features solicitadas. El roadmap
anterior (`roadmap-2026-04.md`) quedó cerrado el 2026-05-11; este recoge lo posterior.
**Método:** detección de bugs en pruebas reales → diagnóstico de causa raíz → fix con
tests → commit en rama → merge `--no-ff` a `main` → push.

> Convención (heredada): marcar items `✅ DONE`, `🟡 IN PROGRESS`, `⬜ OPEN`,
> `❌ DESCARTADO`. Iterar sobre este fichero. La próxima auditoría debe crear
> `roadmap-2026-MM.md` nuevo.

---

## 1. Resumen

| Eje | DONE | OPEN |
|-----|------|------|
| Modelo / API / resiliencia | 4 | 0 |
| Calidad de output (HTML/prompts) | 2 | 0 |
| UX / formulario | 2 | 0 |
| Research / enriquecimiento | 1 | 0 |
| Deploy / dependencias | 1 | 0 |
| **Decisiones pendientes** | — | 0 |

> P1 (Modular Prompt Markers / I3) resuelto el 2026-05-26 → `❌ DESCARTADO` (ver §7).

**10 commits a `main`.** Suite de tests: **963 → 1053 verdes** sin API keys (+90).
Todos los cambios siguen el patrón de degradación graceful y resiliencia
("ningún proveedor es punto único de fallo").

---

## 2. Modelo / API / resiliencia

### M1 — Migración de modelo retirado (404) ✅ DONE (2026-05-22)
**Commit:** `255dacd`
Anthropic retiró `claude-sonnet-4-20250514` → la API devolvía `404 not_found_error`
y la generación fallaba en producción. Migrado a `claude-sonnet-4-6` en los 10
sitios con default hardcodeado (`core/config.py`, `config/settings.py`,
`config/__init__.py`, `core/pipeline.py`, `core/generator.py` DEFAULT_MODEL +
dicts AVAILABLE_MODELS/MODEL_TOKEN_LIMITS, `utils/prompt_optimizer.py` ×3, docs, tests).
**GOTCHA documentado:** si `st.secrets['claude_model']` está definido, gana sobre el
default del código (cascada en `core/config.py`) — hay que actualizar AMBOS sitios.

### M2 — Streaming obligatorio sobre `max_tokens > 21333` ✅ DONE (2026-05-22)
**Commit:** `f719bf5` · **Archivo:** `core/generator.py`
El SDK de Anthropic eleva `ValueError("Streaming is required…")` en llamadas
no-streaming cuya duración estimada supera 10 min (`3600*max_tokens/128000 > 600`
→ `max_tokens > 21333`). Con `max_tokens` alto en secrets, el refinamiento y el
pipeline para arquetipos largos rompían. `call_claude_api` (único punto de llamada al
SDK) usa `client.messages.stream()` + `get_final_message()` por encima del umbral
(`NONSTREAMING_MAX_TOKENS=21333`); por debajo sigue con `.create()`. Cubre todas las
llamadas a Claude. Hace seguro mantener `max_tokens=32000` en secrets.

### M3 — Fallback Claude Haiku para la validación dual (Stage 2) ✅ DONE (2026-05-22)
**Commit:** `12c4daa` · **Archivo:** `core/pipeline.py`, `core/config.py`, `core/openai_client.py`
La corrección dual solo existía con OpenAI; sin key/SDK o ante fallo runtime se
degradaba a un único análisis. Ahora hay SIEMPRE un segundo analista: OpenAI si está
disponible (cross-vendor, preferido), si no Claude Haiku (`DUAL_FALLBACK_MODEL`); si
OpenAI falla en runtime → backstop secuencial a Haiku. `merge_dual_analyses(secondary_provider=)`
etiqueta la telemetría real. Independencia menor con Haiku (mismo proveedor) = red de
seguridad, no equivalente.

### M4 — Fallback de imágenes a OpenAI `gpt-image-1` ✅ DONE (2026-05-22)
**Commit:** `6c015d3` · **Archivo:** `utils/image_gen.py`, `ui/results.py`
Gemini sigue primario (seed images + ratios nativos 16:9/9:16); `gpt-image-1` entra
como fallback cross-vendor cuando Gemini no está configurado o falla una imagen en
runtime. `_fit_to_size` recorta+redimensiona (gpt-image-1 solo da 1024², 1536×1024,
1024×1536). Sin seed images en el fallback. **Requiere organización verificada en
OpenAI** (si no → 403).

---

## 3. Calidad de output (HTML / prompts)

### Q1 — Eliminar marcadores `#MODULE_*#` colados ✅ DONE (2026-05-22)
**Commit:** `48383ee` · **Archivo:** `prompts/new_content.py`, `core/generator.py`, `core/pipeline.py`
Los marcadores `#MODULE_START:ID#`/`#MODULE_END:ID#` (pedidos por la regla 13 del
prompt Stage 3 — item I3 del audit, nunca consumidos) se renderizaban como texto.
Fix doble: quitada la instrucción + marcadores del prompt, y strip defensivo en
`extract_html_content` (generator) y `_extract_html_content` (pipeline). **Esto
revierte de facto el item I3 "Modular Prompt Markers" del audit-2026-03** (ver §6).

### Q2 — Tabla comparativa "cuadrada" (tree-shaking de CSS) ✅ DONE (2026-05-22)
**Commit:** `48383ee` · **Archivo:** `config/design_system.py`, `config/cms_compatible.css`
El tree-shaking de CSS (`_BASE_CSS_SECTION_MAP`) asociaba la sección base de tablas
(`table{table-layout:fixed}` + `.table-responsive`) solo a `table`, no a
`comparison_table` → columnas desiguales y `.table-responsive` sin estilo (lo inyecta
`table_fixer.py`). Fix: `'Tablas HTML': 'table,comparison_table'` + `table-layout:fixed`
directo en `.comparison-table`. **Nota de arquitectura:** el CSS embebido sale de
`cms_compatible.css` vía `design_system.get_css_for_prompt` (tree-shaking por secciones),
NO de `_CANONICAL_CSS` (fallback). El modelo además reescribe parte del CSS.

---

## 4. UX / formulario

### U1 — Campos descubribles (keywords secundarias e instrucciones) ✅ DONE (2026-05-22)
**Commit:** `671c6ce` · **Archivo:** `ui/inputs.py`
Estaban enterradas en el expander "🎨 Visual, estructura e instrucciones". Separado en
dos expanders: "🎨 Elementos visuales y estructura" y "✍️ Keywords secundarias,
instrucciones y fuentes" (dedicado y descubrible). Micro-formatos (ARQ-32..37) siguen
ocultando keywords secundarias.

### U2 — Brief descargable / rellenable / subible ✅ DONE (2026-05-25)
**Commit:** `61b8d16` · **Archivo:** `utils/brief_io.py` (nuevo), `ui/inputs.py`
Descarga el brief de contenido nuevo como Markdown legible para que el equipo de
expertos lo rellene offline, y lo sube completado para autocompletar el formulario.
`build_brief_markdown` (campos fijos + briefing del arquetipo, con códigos `[id]`
estables en los títulos) + `parse_brief_markdown` (parser tolerante). Pre-siembra de
widgets según tipo (pop+save_form_data para `value=`/`index=`; session_state directo
para solo-key; auto-expande "Ver todas" si hay briefing oculto). Solo modo `new`.
Patrón documentado en `.claude/rules/ui.md`.

---

## 5. Research / enriquecimiento

### R1 — Investigación web opt-in (OpenAI web search → fallback SERP) ✅ DONE (2026-05-22)
**Commit:** `292499b` · **Archivo:** `utils/web_research.py` (nuevo), `core/pipeline.py`, `ui/inputs.py`
El usuario pidió "conectar con AI Mode de Google" pero sin depender de Gemini. AI Mode
no tiene API pública → se descartó. Solución: nueva etapa 0 opcional que enriquece
`guiding_context` con info actual. Cadena con fallback que NUNCA depende de Gemini:
**OpenAI web search** (Responses API + tool `web_search`, reutiliza `OPENAI_API_KEY`)
→ **SERP research** (SerpAPI/DuckDuckGo) → graceful. Las fuentes web son solo contexto
factual; NO se inyectan como enlaces externos. Checkbox opt-in (control de coste).
**Requiere acceso a la herramienta `web_search` en la cuenta OpenAI** (si no → cae al SERP).

---

## 6. Deploy / dependencias

### D1 — Blindar mínimos de SDK para Streamlit Cloud ✅ DONE (2026-05-26)
**Commit:** `4ffd0a9` · **Archivo:** `requirements.txt`
Cloud instala desde `requirements.txt`; los floors eran demasiado bajos para garantizar
las features nuevas. `openai>=1.30.0 → >=1.74.0` (Responses API + `web_search` +
`gpt-image-1`); `anthropic>=0.34.0 → >=0.49.0` (streaming). Tras desplegar conviene
**Reboot app** en Cloud para reinstalar.

### M0 — Cierre del presupuesto dinámico de Stage 2 ✅ DONE (2026-05-22)
**Commit:** `884cded` · **Archivo:** `core/token_budget.py`
Cierre de trabajo arrastrado: Stage 2 escalaba con un fijo de 4000 que truncaba el
análisis en borradores largos. Ahora `max(STAGE2_FLOOR=4000, target*STAGE2_TOKENS_PER_WORD=3.0)`,
redondeo a 1000, acotado al techo.

---

## 7. Decisiones pendientes / housekeeping

### P1 — "Modular Prompt Markers" (I3) ❌ DESCARTADO (2026-05-26)
El item **I3** del `audit-2026-03.md` ("soporte para `#MODULE_START#`/`#MODULE_END#`")
estaba marcado `[x]` pero los marcadores nunca se consumían (no había parser ni uso
downstream) y se colaban como texto en el HTML renderizado (ver Q1).
**Decisión (usuario, 2026-05-26): DESCARTADO.** No existe consumidor de los marcadores
ni necesidad confirmada del CMS de trocear el HTML por bloques. La implementación quedó
revertida en `48383ee` (prompt ya no los emite + strip defensivo en la limpieza de HTML).
Si en el futuro el CMS requiriera modularización por bloques, se reabriría como item
nuevo con diseño completo (emitir + parsear + ensamblar). El audit-2026-03 (I3) se anota
en consecuencia.

### P2 — Housekeeping (no bloqueante)
- Rama `origin/claude/review-and-test-TIAuw` puede borrarse (sus fixes únicos ya en main).
- Verificaciones de cuenta OpenAI (lado usuario, no código): organización verificada
  para `gpt-image-1` y acceso a la herramienta `web_search` con `gpt-4.1`.
- Recomendado en secrets: `max_tokens=32000` (ya seguro gracias a M2) y confirmar
  `claude_model=claude-sonnet-4-6` (confirmado por el usuario 2026-05-26).
