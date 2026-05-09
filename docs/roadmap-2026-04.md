# Raichu v5.1.0 — Roadmap Consolidado

**Fecha base:** 2026-04-20
**Reemplaza/consolida:** `audit-2026-03.md`, `ux-audit-2026-03.md`, `output-quality-audit-2026-03.md`, `p3-p4-plan-2026-04.md`
**Método:** Auditoría dirigida en 4 ejes (performance/API, prompts, UX/Streamlit, seguridad/tests).

Este es el **documento único de trabajo**. Todos los audits previos quedan archivados como referencia histórica. Iterar sobre este fichero: marcar items como `✅ DONE`, `🟡 IN PROGRESS`, `⬜ OPEN`.

---

## Leyenda

- **Severidad**
  - `S1` Crítico — afecta calidad output, dinero, seguridad, pérdida de datos
  - `S2` Importante — UX rota, robustez, deuda relevante
  - `S3` Mejora — nice-to-have, pulido, limpieza
- **Esfuerzo:** `S` (<2h) · `M` (medio día) · `L` (1-2 días)
- **Estado:** `⬜ OPEN` · `🟡 IN PROGRESS` · `✅ DONE`

---

## 1. Resumen ejecutivo

Raichu v5.1.0 cerró con éxito las olas P0/P1/P2/P3/P4 (ver §5). El proyecto está funcional y desplegado. Esta nueva auditoría (2026-04-20) descubre **24 items abiertos** en 4 ejes:

| Eje | S1 | S2 | S3 | Total abiertos |
|-----|----|----|----|----------------|
| Performance y coste de API | 0 | 1 | 0 | 1 |
| Calidad de output y prompts | 0 | 2 | 2 | 4 |
| UX / Streamlit / session state | 0 | 0 | 1 | 1 |
| Seguridad / tests / deuda técnica | 0 | 0 | 0 | 0 |
| **Total** | **0** | **3** | **3** | **6** |

**Cerrados en Fase 1 (2026-04-29):** R1.2, R1.3, R1.4, R1.5, R1.6, R1.7, R3.5 (7 items).
**Cerrados en Fase 2 (2026-05-08):** R1.1, R2.1, R2.3 (3 items).
**Cerrados en Fase 3 (2026-05-09):** R2.7, R2.8, R2.9 (3 items).
**Cerrados en Fase 5 (2026-05-09):** R2.6, R3.1, R3.4, R3.6, R3.7, R3.8 (6 items).

**Esfuerzo agregado estimado:** ~8-11 días de ingeniería.

**ROI máximo:** `R1.1` (paralelizar Stage 2) + `R1.2` (prompt caching) = ~25-35% reducción en latencia y 20-30% en tokens de entrada.

---

## 2. Items abiertos — S1 (Crítico)

### R1.1 — Stage 2 Claude+OpenAI secuencial ✅ DONE (2026-05-08)
**Cambio:** Nuevo helper `_run_parallel_stage2(claude_callable, openai_callable, dual_enabled)` a nivel módulo en [core/pipeline.py:99-138](../core/pipeline.py#L99-L138) que orquesta un `ThreadPoolExecutor(max_workers=2)`. Cada worker captura sus propias excepciones y devuelve `(ok, result, err, elapsed)`; los `status_widget.write` y la mutación de `st.session_state` se mantienen en el hilo principal. La semántica de fallback (Claude solo cuando OpenAI falla) se preserva byte a byte. Log de Stage 2 reporta `claude=Xs openai=Ys wall=max`. Tests en [tests/test_pipeline_stage2_parallel.py](../tests/test_pipeline_stage2_parallel.py).


**Eje:** Performance · **Esfuerzo:** M · **Archivo:** [core/pipeline.py:660-704](../core/pipeline.py#L660-L704)

Claude y OpenAI se ejecutan en serie en Stage 2. Con prompts ~4-8K tokens cada uno, suma **60-120s de latencia innecesaria** por generación.

**Fix:** `concurrent.futures.ThreadPoolExecutor(max_workers=2)` con `submit()` para lanzar ambos análisis en paralelo. `stage2_time = max(claude, openai)` en lugar de `sum`.

```python
with ThreadPoolExecutor(max_workers=2) as executor:
    claude_future = executor.submit(generator.generate, stage2_prompt, ...)
    openai_future = executor.submit(openai_client.generate_dual_analysis, ...)
    claude_analysis = claude_future.result()
    openai_analysis = openai_future.result()
```

---

### R1.2 — Prompt caching no implementado / incompleto ✅ DONE (2026-04-29)
**Verificación:** [generator.py:294-301](../core/generator.py#L294-L301) ya usa `cache_control: {"type": "ephemeral"}` sobre el system prompt. Confirmado que es el único punto de llamada a `client.messages.create()` y que los 3 stages comparten el mismo `system_prompt` en pipeline.py L570/L659/L751. El finding del audit era inexacto; no requiere cambios. Texto original conservado abajo para trazabilidad.


**Eje:** Performance · **Esfuerzo:** S · **Archivo:** [core/generator.py:295-301](../core/generator.py#L295-L301)

System prompt se pasa 3 veces (Stage 1/2/3) sin `cache_control: {"type": "ephemeral"}`. `brand_tone.py` tiene ~658 líneas → ~1200 tokens × 3 etapas = **3600 tokens redundantes** por generación.

**Fix:** Activar prompt caching de Anthropic sobre bloques de system prompt en [core/generator.py:295-301](../core/generator.py#L295-L301). Verificar en [pipeline.py:571](../core/pipeline.py#L571), [L660](../core/pipeline.py#L660), [L752](../core/pipeline.py#L752) que el mismo system prompt se reutiliza.

---

### R1.3 — Stage 1 hints blandos vs Stage 2/3 mandatos duros ✅ DONE (2026-04-29)
**Cambio:** Header de elementos visuales en Stage 1 ahora declara explícitamente que son "OBLIGATORIOS" y que Stage 2 marcará su ausencia como ERROR CRÍTICO. Hints de `toc` y `faqs` actualizados con el mismo lenguaje imperativo que `verdict` ya tenía. Editado [prompts/new_content.py:1055-1084](../prompts/new_content.py#L1055).


**Eje:** Prompts · **Esfuerzo:** S · **Archivo:** [prompts/new_content.py:1060-1084](../prompts/new_content.py#L1060-L1084)

Stage 1 sugiere visual elements ("Colócala...", "Úsala para...") pero Stage 2 valida con severidad "CRÍTICA" y Stage 3 los marca como "ERROR CRÍTICO" (L870). TOC/verdict/faqs son efectivamente obligatorios pero Stage 1 no lo dice.

**Fix:** Alinear `_USAGE_HINTS` de Stage 1 a lenguaje imperativo ("OBLIGATORIO") para verdict/faqs/toc, coincidiendo con placement rules de Stage 3 en [L820-842](../prompts/new_content.py#L820-L842).

---

### R1.4 — Anti-IA checklist sin excepciones por arquetipo ✅ DONE (2026-04-29)
**Cambio:** `ANTI_IA_CHECKLIST_STAGE2` y `REGLAS_CRITICAS_COMUNES` en [prompts/brand_tone.py:304-330](../prompts/brand_tone.py#L304) ahora explicitan excepciones para ARQ-16 (Lanzamientos), ARQ-19 (Ofertas) y ARQ-20 (Black Friday) sobre años en títulos y lenguaje de urgencia.


**Eje:** Prompts · **Esfuerzo:** S · **Archivo:** [prompts/brand_tone.py:304-330](../prompts/brand_tone.py#L304-L330)

`ANTI_IA_CHECKLIST_STAGE2` prohíbe años/fechas en títulos y "adjetivos vacíos". Pero ARQ-16 (Lanzamientos), ARQ-19 (Ofertas), ARQ-20 (Black Friday) usan fechas/urgencia como parte del contenido legítimo. Falsos positivos en validación.

**Fix:** Añadir excepciones condicionales por grupo de arquetipo. Ejemplo: `"Si la keyword contiene año/fecha, años en títulos son PERMITIDOS"` en L330.

---

### R1.5 — 9+ keys huérfanas sobreviven `clear_session_state()` ✅ DONE (2026-04-29)
**Cambio:** Añadidas listas `gsc_keys` y `feedback_keys` (con `gsc_data_date`, `gsc_analysis`, `gsc_opportunities_data`, `_post_gen_checks`, `_refinement_feedback`, `_translation_feedback`, `_batch_translation_feedback`, `prefill_*`). Añadido `rewrite_original_html` a `rewrite_keys` (también cierra R3.5). Añadidos patterns `translated_html_`, `_pending_delete_`, `_has_generated_` al cleanup dinámico. Editado [core/session.py:84-194](../core/session.py#L84).


**Eje:** UX · **Esfuerzo:** S · **Archivo:** [core/session.py:84-194](../core/session.py#L84-L194)

`clear_session_state()` omite estas keys activamente seteadas:
- `gsc_data_date`, `gsc_analysis`, `gsc_opportunities_data`
- `_post_gen_checks`, `_refinement_feedback`, `_translation_feedback`, `_batch_translation_feedback`
- `prefill_keyword`, `prefill_url`, `prefill_analysis_context`
- `rewrite_original_html`

Usuario hace clic en "Limpiar" → keys persisten → pollution de estado entre modos.

**Fix:** Añadir keys faltantes a las listas de limpieza correspondientes. Considerar enumeración deterministic + pattern matching.

---

### R1.6 — XSS bypass en `sanitize_html` ✅ DONE (2026-04-29)
**Cambio:** Nuevo helper `_has_dangerous_scheme()` en [utils/html_utils.py](../utils/html_utils.py) que decodifica HTML entities, normaliza whitespace/control chars y usa `urllib.parse.urlparse()` para detectar `javascript`, `vbscript`, `data`, `file`, `about`. Aplicado a `href`, `src`, `action`, `xlink:href`, `poster`, `background`. Cubre bypasses por case (`JavaScriPt:`) y encoding (`java&#x0A;script:`).


**Eje:** Seguridad · **Esfuerzo:** S · **Archivo:** [utils/html_utils.py:328-329](../utils/html_utils.py#L328-L329)

Check de `javascript:` usa string comparison tras lowercase. Bypasses posibles:
- Variación de case: `JavaScriPt:`
- Encoded: `java&#x0A;script:`
- Schemes relacionados: `vbscript:`, `data:text/html,...`

**Fix:** Usar `urllib.parse.urlparse()` para extraer scheme, rechazar si está en `['javascript', 'vbscript', 'data']`.

---

### R1.7 — Auth status loggeado en debug ✅ DONE (2026-04-29)
**Cambio:** Eliminada línea `logger.debug(f"CLAUDE_API_KEY presente: {bool(CLAUDE_API_KEY)}")` en [core/config.py:224](../core/config.py#L224).


**Eje:** Seguridad · **Esfuerzo:** S · **Archivo:** [core/config.py:224](../core/config.py#L224)

`logger.debug(f"CLAUDE_API_KEY presente: {bool(CLAUDE_API_KEY)}")` señala estado de auth. No es crítico pero es información innecesaria en logs debug.

**Fix:** Eliminar o reducir a `logger.debug("API key configured")` sin referencia a presencia.

---

## 3. Items abiertos — S2 (Importante)

### R2.1 — Retry sin jitter → thundering herd ✅ DONE (2026-05-08)
**Cambio:** Nuevo helper `_sleep_with_jitter(delay, jitter_ratio=0.1)` en [core/generator.py:128-141](../core/generator.py#L128-L141) que añade hasta un 10% de jitter aleatorio. Sustituye los 4 `time.sleep(current_delay)` en los bloques de RateLimit, ConnectionError, 529 overload y 5xx. Tests en [tests/test_generator.py](../tests/test_generator.py) cubren bounds, delay=0 y ratio personalizado.


**Eje:** Performance · **Esfuerzo:** S · **Archivo:** [core/generator.py:327-352](../core/generator.py#L327-L352)

Backoff exponencial sin jitter. En multi-usuario (Streamlit Cloud) todos los clientes golpean retry al mismo tiempo → más rate limits.

**Fix:**
```python
import random
jitter = random.uniform(0, current_delay * 0.1)
time.sleep(current_delay + jitter)
```

---

### R2.2 — System prompt sin compresión modular ⬜
**Eje:** Performance · **Esfuerzo:** M · **Archivo:** [prompts/brand_tone.py:266-297](../prompts/brand_tone.py#L266-L297)

`get_system_prompt_base()` retorna ~1200 tokens sin diferenciar etapas. Stage 1 ≠ Stage 2 ≠ Stage 3 en necesidades. Instrucciones duplicadas con `ANTI_IA_CHECKLIST_STAGE2` y `REGLAS_CRITICAS_COMUNES`.

**Fix:** Modularizar system prompt por etapa. Consolidar reglas compartidas en 1 bloque cacheable.

---

### R2.3 — Scraper sin circuit breaker por host ✅ DONE (2026-05-08)
**Cambio:** `WebScraper` mantiene estado por host (`_HostState` con `failure_count` y `opened_at`) protegido por `threading.Lock` (necesario porque `scrape_competitors` ya usa ThreadPoolExecutor). Tras `cb_threshold=3` fallos consecutivos de Timeout/ConnectionError, el circuito abre durante `cb_cooldown=300s`. Solo errores de red abren el circuito; HTTP 5xx no (puede ser ruido legítimo). `_make_request` levanta nueva `CircuitBreakerError` antes de tocar la red; `scrape_url` la captura y devuelve `ScrapeResult(success=False, error="circuit_breaker: …", metadata={"circuit_breaker": True, ...})` para no romper el contrato. 10 tests en [tests/test_scraper_circuit_breaker.py](../tests/test_scraper_circuit_breaker.py) cubren helpers, threadsafety (100 hilos) y ruta integración con monkeypatch.


**Eje:** Performance · **Esfuerzo:** M · **Archivo:** [core/scraper.py:326-346](../core/scraper.py#L326-L346)

Si competidor host está caído, cada scrape reintenta 3× individualmente. No hay fail-fast tras N errores consecutivos.

**Fix:**
```python
self._failure_count = 0
if self._failure_count > 5:
    raise CircuitBreakerError(f"Too many failures on {host}")
```

---

### R2.4 — Prompt bloat Stage 1 ⬜
**Eje:** Prompts · **Esfuerzo:** M · **Archivo:** [prompts/new_content.py](../prompts/new_content.py) (2330 líneas)

Stage 1 incluye CSS fallback inline (L113-120), design_system templates (L1098-1122), instrucciones arquetípicas repetidas. ~30-40% de tokens en boilerplate. Stage 2 revalida el mismo checklist redundantemente.

**Fix:** Mover `_CSS_FALLBACK` a `design_system.py`, cachear globalmente. Condensar Stage 2 a validación de JSON schema.

---

### R2.5 — `guiding_questions` pobres en arquetipos trend/news ⬜
**Eje:** Prompts · **Esfuerzo:** S · **Archivo:** [config/arquetipos.py:398-401](../config/arquetipos.py#L398-L401)

Todos los 34 arquetipos tienen `guiding_questions`, pero calidad varía:
- ARQ-7 (Solución de Problemas): solo 4 preguntas
- ARQ-16–ARQ-20 (Trends/News): 5-7 genéricas vs ARQ-1–ARQ-5 con 16+
- Ninguno valida "¿Evergreen o caducidad?" aunque existe en `PREGUNTAS_UNIVERSALES`

**Fix:** Asegurar ≥6 preguntas por arquetipo, incluir subset de universales. Añadir validación pipeline que advierta si <6.

---

### R2.6 — Mode isolation incompleto ✅ DONE (2026-05-09)
**Cambio:** [core/session.py:17-29](../core/session.py#L17-L29) — `_MODE_RESULT_KEYS` ampliado con 6 keys (`gsc_analysis`, `gsc_opportunities_data`, `_post_gen_checks`, `_refinement_feedback`, `_translation_feedback`, `_batch_translation_feedback`). `_save_mode_results` / `_restore_mode_results` ahora aíslan también el contexto de verify/opportunities/feedback. Ninguna de las keys añadidas contiene credenciales (verificado). Nuevo archivo [tests/test_session_mode_isolation.py](../tests/test_session_mode_isolation.py) — primer test del codebase que ejercita `st.session_state` directamente vía un `FakeSessionState` dict-like (4 tests, ~1s). Commit `a3f46cb`.


**Eje:** UX · **Esfuerzo:** S · **Archivo:** [core/session.py:17-21](../core/session.py#L17-L21)

`_MODE_RESULT_KEYS` excluye `gsc_analysis`, `_post_gen_checks` y feedback keys. Contexto de "verify" bleed-ea a "new".

**Fix:** Añadir keys faltantes a `_MODE_RESULT_KEYS` o eliminar explícitamente en `_save_mode_results()`.

---

### R2.7 — Test coverage pobre en html_utils.py ✅ DONE (2026-05-09)
**Cambio:** [tests/test_html_utils.py](../tests/test_html_utils.py) ampliado de 11 a 96 tests (+85). Cobertura de [utils/html_utils.py](../utils/html_utils.py) sube de 37% a 93%. Tests nuevos: `_has_dangerous_scheme` (19 parametrizados, R1.6), `sanitize_html` (17 bypasses XSS — case, encoding, schemes, event handlers, blacklist tags, formaction, svg — más preservación de `<style>` y atributos seguros), `detect_placeholders` (6 patrones + clean + empty), `extract_content_structure`/`extract_content`/`extract_text`/`extract_meta_tags`, `validate_cms_articles` (complete/missing/empty), `validate_cms_structure` (5 ramas), `validate_word_count_target` (within/out/zero), `analyze_links` (clasificación PDP/blog/externo + empty), `get_heading_hierarchy`, HTMLParser custom class, aliases (`get_word_count`, `strip_tags`, `get_parser`, `get_bs4_parser`, `is_bs4_available`), edge cases de `extract_html_content` (text before/after, inner block, unclosed fence, nested backticks documentado como limitación), false positives de `detect_ai_phrases`. Las 23 líneas restantes son fallbacks de excepción sin valor realista. Commit `20ababc`.


**Eje:** Tests · **Esfuerzo:** M · **Archivo:** [tests/test_html_utils.py](../tests/test_html_utils.py)

12 funciones de test para 40+ utility functions. Missing:
- `extract_html_content()` — nested backticks, malformed tags
- `detect_placeholders()`
- `detect_ai_phrases()` — false positive rates

**Fix:** Añadir 8-10 tests parametrizados.

---

### R2.8 — Tests sin mocks de APIs externas ✅ DONE (2026-05-09)
**Cambio:** Añadidas 3 fixtures opt-in SDK-level en [tests/conftest.py:90-189](../tests/conftest.py#L90-L189): `mock_anthropic_client` (parchea `core.generator.Anthropic`), `mock_openai_client` (parchea `core.openai_client.OpenAI` + resetea singleton interno), `mock_requests_session` (parchea `requests.Session` global; el módulo `requests` es singleton, así que un solo patch cubre scraper/semrush/cms_publisher/serp_research). Cada fixture devuelve un `MagicMock` con helpers `set_response()` / `map_url()`. Regla "patch where used, not where defined": para `from x import Y`, parchear el namespace consumidor. Path `core.pipeline.Anthropic` descartado tras verificar que pipeline solo importa clases de error (las llamadas SDK viven en `ContentGenerator`). 10 smoke tests en [tests/test_mocks_smoke.py](../tests/test_mocks_smoke.py) verifican el wiring. Patrón documentado en [.claude/rules/tests.md](../.claude/rules/tests.md). Paso 0 (auditoría sin keys): 827 tests ya pasaban sin keys → 0 tests para sweep ligero. Tests legacy con monkeypatch ad-hoc (test_pipeline_stage2_parallel.py, test_scraper_circuit_breaker.py) intactos por decisión explícita. Suite final: 922 passed in 6.99s sin API keys. Commit `6668980`.


**Eje:** Tests · **Esfuerzo:** M · **Archivo:** `tests/`

Tests importan `core.generator`, `core.scraper`, `utils.serp_research` sin mockear Anthropic/OpenAI/SerpAPI. Si CI no tiene API keys, tests pasan auth validation pero skip real calls silenciosamente.

**Fix:** `@pytest.fixture` con stubs de `anthropic.Anthropic()` y `openai.OpenAI()`.

---

### R2.9 — Fixtures `scope="session"` causan bleed ✅ DONE (2026-05-09)
**Cambio:** Las 3 fixtures `scope="session"` en [tests/conftest.py:16-57](../tests/conftest.py#L16-L57) (`sample_html`, `sample_html_with_ai_phrases`, `markdown_wrapped_html`) migradas a `scope="function"` (default). Eran strings literales inmutables, el scope no aportaba perf y violaba la recomendación pytest. Las 3 fixtures `scope="class"` en [tests/test_visual_elements_and_serp.py:248-260](../tests/test_visual_elements_and_serp.py#L248-L260) (`pipeline_src`, `detect_block`, `names_block`) **se mantienen** con docstring justificando el scope: leen `core/pipeline.py` desde disco y devuelven slices read-only reutilizados por tests parametrizados (perf real, sin estado mutable). Verificación: 827 passed en `pytest tests/ -p no:randomly` y modo normal (mismos resultados, sin dependencia oculta de orden). Commit `eebbc09`.


**Eje:** Tests · **Esfuerzo:** S · **Archivo:** [tests/conftest.py](../tests/conftest.py)

`test_ux_ui_functionality.py` usa session-scoped fixtures. Si orden cambia, fixtures de distintos modos se mezclan.

**Fix:** `scope="function"` con teardown explícito en tests state-dependent.

---

## 4. Items abiertos — S3 (Mejora)

### R3.1 — OpenAI fallback verbose ✅ DONE (2026-05-09)
**Cambio:** Las dos quejas principales del audit ya estaban resueltas tras R1.1 (paralelización Stage 2): `merge_dual_analyses` solo se invoca cuando ambos providers triunfan ([core/pipeline.py:753](../core/pipeline.py#L753)) — sin copia innecesaria; el doble logging desapareció con la nueva orquestación. Único pulido pendiente: el path "OpenAI devolvió ok=False" solo escribía en `status_widget` pero no en `logger`. Añadido `logger.warning` en [core/pipeline.py:763](../core/pipeline.py#L763) para que Streamlit Cloud capture todos los fallback paths consistentemente. Commit `3e14e08`.


**Eje:** Performance · **Esfuerzo:** S · **Archivo:** [core/pipeline.py:695-704](../core/pipeline.py#L695-L704)

Si OpenAI falla, Claude se usa pero 2× logging + JSON merge innecesario (copia).

**Fix:** Cache resultado si es copia. Reducir warnings verbose.

---

### R3.2 — CSS drift entre 3 archivos ⬜
**Eje:** Prompts · **Esfuerzo:** M · **Archivos:** [prompts/new_content.py:113-120](../prompts/new_content.py#L113-L120), [prompts/templates.py:44](../prompts/templates.py#L44), `config/design_system.py`

`_CSS_FALLBACK` en Stage 1 es minificado legacy. `templates.py` define otro fallback. Design system vars (`--orange-900`, `--blue-m-900`) duplicadas en 3 sitios.

**Fix:** Single source of truth en `config/design_system.py`. Importar en ambos.

---

### R3.3 — Mini-stories sin fallback sintético ⬜
**Eje:** Prompts · **Esfuerzo:** S · **Archivo:** [prompts/new_content.py:57-68](../prompts/new_content.py#L57-L68)

`ARQUETIPOS_CON_MINI_STORIES` activa mini-historias solo si `has_feedback=True`. Si producto no tiene reviews, ARQ-4/ARQ-5 pierden personas → contenido más genérico.

**Fix:**
```python
if include_mini_stories and not has_feedback:
    prompt += "Incluir 2-3 mini-historias SINTÉTICAS basadas en perfiles de usuario típicos:"
```

---

### R3.4 — Error messages genéricos sin logging ✅ DONE (2026-05-09)
**Cambio:** 5 bloques `except ImportError:` en [app.py](../app.py) (`ui.inputs`, `ui.rewrite`, `ui.results`, `ui.sidebar`, `ui.assistant`, `ui.verify`) actualizados a `except ImportError as e:` con `logger.error(f"...: {e}")` (warning para los cosméticos como sidebar/results, error para los críticos de modo). Añadido `logger.error` antes del `st.error` en runtime cuando `ContentGenerator` es None en `render_assistant_mode` ([app.py:418](../app.py#L418)) — ese caso no es ImportError local sino fallo de instanciación posterior. `prompts.rewrite` ([app.py:84-87](../app.py#L84-L87)) y `ui.opportunities` ([app.py:816-818](../app.py#L816-L818)) ya tenían el patrón correcto. Commit `ecd6865`.


**Eje:** UX · **Esfuerzo:** S · **Archivos:** [app.py:220,299,414,811](../app.py#L220)

7 locations con `st.error("❌ El módulo X no está disponible")` sin `logger.error(f"Import failed: {e}")`. Difícil debuggear fallos en Streamlit Cloud.

**Fix:** Añadir `logger.error()` antes de cada fallback. Ejemplo correcto ya existe en [app.py:66-69](../app.py#L66-L69).

---

### R3.5 — `rewrite_original_html` nunca se limpia ✅ DONE (2026-04-29, junto con R1.5)

**Eje:** UX · **Esfuerzo:** S · **Archivos:** [app.py:332](../app.py#L332), [core/session.py](../core/session.py)

Seteado al cachear HTML pre-rewrite, pero no en `clear_session_state()`. Al cambiar a modo "new", HTML de rewrite persiste → comparación stale.

**Fix:** Añadir `'rewrite_original_html'` a `rewrite_keys` en `clear_session_state()`.

---

### R3.6 — PyYAML/types-PyYAML en requirements sin uso ✅ DONE (2026-05-09)
**Cambio:** Verificación previa con `grep` confirmó 0 matches de `import yaml`/`from yaml` en *.py (incluido tests/). `requirements.txt` no contenía `pyyaml` (solo `types-PyYAML` en [requirements-dev.txt:33](../requirements-dev.txt#L33)). Eliminada esa línea — `types-PyYAML` es type-stub puro, solo útil para mypy cuando hay imports de yaml. Suite: 922 → 922 verde. Commit `2c91666`.


**Eje:** Deuda · **Esfuerzo:** S · **Archivo:** `requirements.txt:42-43`

Verificado: no hay `import yaml` en codebase. +500KB bundle innecesario.

**Fix:** Eliminar líneas de `requirements.txt` y `requirements-dev.txt`.

---

### R3.7 — HTMLParser stub duplicado ✅ DONE (2026-05-09) — verificación retroactiva
**Cambio:** Verificado que [utils/__init__.py:53](../utils/__init__.py#L53) ya implementaba el fix (`from html.parser import HTMLParser`) desde antes de Fase 5. El audit estaba stale. Sin commit de código.


**Eje:** Deuda · **Esfuerzo:** S · **Archivo:** [utils/__init__.py:53-58](../utils/__init__.py#L53-L58)

Fallback `HTMLParser` custom duplica stdlib. Si `html_utils` import falla, el fallback es un stub incompleto.

**Fix:** `from html.parser import HTMLParser` en fallback.

---

### R3.8 — `sanitize_html` con `except Exception` muy amplio ✅ DONE (2026-05-09)
**Cambio:** [utils/html_utils.py](../utils/html_utils.py) — import de `ParserRejectedMarkup` añadido al bloque bs4 (con sentinel `class ParserRejectedMarkup(Exception)` cuando bs4 no está, para que el `except` sea well-defined en tiempo de import). Nuevo helper `_regex_fallback_sanitize()` usado por los **dos** paths de fallback (bs4 ausente + bs4 falla en runtime). Cubre los mismos tags que el path bs4 (`script, iframe, object, embed, applet, svg, meta, link, base, form, input, button`) + comentarios HTML + event handlers `on*=` en tres variantes de comillas. `except Exception` estrechado a `(ParserRejectedMarkup, AttributeError, ValueError)` para que bugs reales propaguen. Limitación documentada: el regex no neutraliza `javascript:`/`data:` en `href`/`src` — solo bs4 lo hace; defense-in-depth, no defensa primaria. Nuevo archivo [tests/test_html_sanitization_fallback.py](../tests/test_html_sanitization_fallback.py) — 17 tests parametrizados sobre vectores XSS forzando el fallback vía monkeypatch. Cobertura `utils/html_utils.py`: 93% → 95%. Commit `a0dfe81`.


**Eje:** Deuda · **Esfuerzo:** S · **Archivo:** [utils/html_utils.py:341-344](../utils/html_utils.py#L341-L344)

`except Exception` swallows errores. Regex fallback solo remueve `<script>` — miss `<iframe>`, `onerror=`, `onclick=`.

**Fix:** Catch `bs4.ParserRejectedMarkup` explícito. Ampliar regex fallback a event handlers + iframes.

---

## 5. Orden de ejecución sugerido

**Fase 1 — Quick wins S1 (1-2 días):** `R1.2` · `R1.3` · `R1.4` · `R1.5` · `R1.6` · `R1.7`
**Fase 2 — Performance boost (1 día):** `R1.1` · `R2.1` · `R2.3`
**Fase 3 — Robustez tests (2 días):** `R2.7` · `R2.8` · `R2.9`
**Fase 4 — Prompt refinement (2 días):** `R2.2` · `R2.4` · `R2.5` · `R3.2` · `R3.3`
**Fase 5 — UX polish & deuda (1-2 días):** `R2.6` · `R3.1` · `R3.4` · `R3.5` · `R3.6` · `R3.7` · `R3.8`

---

## 6. Histórico de audits previos (CERRADOS)

Todos los hallazgos F1-F8 (audit 2026-03-22), P0/P1/P2 (UX 2026-03-23), QW-1/A5-/A7-/A16-/A2-/A4- (output quality 2026-03-23), y P3.1-P3.10/P4.1-P4.12 (plan 2026-04-07) están **resueltos**. Mantengo aquí el índice para trazabilidad.

### Audit 2026-03-22 — Salud del proyecto
- F1 Versión en 6 ubicaciones — ✅ PARCIAL (source of truth correcto)
- F2 app.py monolito — ✅ DONE (1592 → 836 líneas)
- F3 Suite de tests mínima — ✅ DONE (3 → 462 tests)
- F4 Deps no usadas — ✅ DONE (limpieza en requirements.txt, salvo PyYAML residual → ver R3.6)
- F5 state_manager inexistente — ✅ DONE
- F6 Changelog embebido — ✅ DONE
- F7 API keys en os.environ — ✅ DONE (ANTHROPIC_API_KEY vía parámetro)
- F8 Sin CI pipeline — ✅ DONE (.github/workflows/ci.yml configurado)

### UX Audit 2026-03-23 — Modo Nuevo
- P0.1/P0.2/P0.3 — ✅ DONE (visual elements auto, keywords sec a avanzado, hint productos)
- P1.1/P1.2/P1.3 — ✅ DONE (briefing top 3, tag summary, CMS toggle)
- P2.1/P2.3 — ✅ DONE (form profiles, selector 2 niveles)
- P2.2 — 🟡 PARCIAL (wizard 3 pasos cuando `_has_generated_new=False`)

### Output Quality Audit 2026-03-23
- QW-1 a QW-4, A5-1 a A4-2 — ✅ mayoritariamente DONE en sprints subsiguientes
- **Reabierto parcialmente** en R1.3, R1.4, R2.5 con nuevos matices

### Plan P3/P4 2026-04-07
- P3.1–P3.10 — ✅ todos resueltos
- P4.1–P4.12 — ✅ todos resueltos

---

## 7. Cómo iterar sobre este documento

1. Al cerrar un item, cambiar estado a `✅ DONE` + añadir commit hash y fecha.
2. Si aparece contexto nuevo, **no abras un audit nuevo** — añade item `R4.X` o sub-item a este roadmap.
3. Si un item resulta no aplicable, marcar `❌ DESCARTADO` con razón.
4. Revisión semanal: actualizar la tabla de resumen ejecutivo (§1) con conteo actualizado por severidad.
