# Convenciones de Tests

Aplica a: `tests/`

## Stack

- pytest 9.0+, pytest-mock, pytest-asyncio, pytest-cov
- Configurado en `pyproject.toml` (`[tool.pytest.ini_options]`)
- Fixtures globales en `tests/conftest.py`
- Ejecutar con `PYTHONPATH=. pytest tests/` (sin `pythonpath` en config)

## Fixtures de mocks SDK-level (R2.8)

Para tests que ejercitan codigo que llama Anthropic / OpenAI / requests, usar las
fixtures opt-in definidas en `tests/conftest.py`:

| Fixture | Mockea | Uso |
|---------|--------|-----|
| `mock_anthropic_client` | `core.generator.Anthropic` | Tests de `ContentGenerator` |
| `mock_openai_client` | `core.openai_client.OpenAI` (+ resetea singleton) | Tests de `core.openai_client` |
| `mock_requests_session` | `requests.Session` (global) | Tests de scraper / SerpAPI / cms_publisher / semrush |

Cada fixture devuelve un `MagicMock` con un helper para fijar la respuesta:
- `mock_anthropic_client.set_response(text, input_tokens, output_tokens)`
- `mock_openai_client.set_response(text, prompt_tokens, completion_tokens)`
- `mock_requests_session.map_url(url, status_code, body)` — URLs no registradas elevan en `raise_for_status()`

### Regla: parchear por sitio de uso, no por modulo de origen

Cuando un modulo hace `from anthropic import Anthropic`, el binding `Anthropic` se
copia al namespace del modulo consumidor. Parchear `anthropic.Anthropic` directamente
NO afecta a ese consumidor. Hay que parchear `core.generator.Anthropic`.

Excepcion: `import requests` (modulo completo, no `from`). En ese caso parchear
`requests.Session` afecta a todos los consumidores porque el modulo es singleton.

### Como anadir un mock SDK nuevo

1. Verificar como importa el modulo consumidor: `from x import Y` vs `import x`.
2. Anadir fixture `mock_<sdk>_client` a `tests/conftest.py` siguiendo el patron existente.
3. Parchear `core.<consumer>.<Y>` (no `<sdk>.<Y>`).
4. Resetear cualquier singleton interno del modulo consumidor (`monkeypatch.setattr(...)` con `None`) para forzar reconstruccion.
5. Anadir smoke test en `tests/test_mocks_smoke.py`.

## Patrones legacy (NO replicar en tests nuevos)

Los siguientes archivos usan monkeypatch ad-hoc por razones historicas; no migrarlos
salvo que se toquen por otro motivo:

- `tests/test_pipeline_stage2_parallel.py` — usa lambdas como callables sinteticos
- `tests/test_scraper_circuit_breaker.py` — usa `monkeypatch.setattr(scraper._session, "get", ...)` directo

## Scopes de fixtures

Default: `scope="function"`. Solo elevar el scope si:
1. Construccion cara (>=I/O o computo no trivial).
2. Sin estado mutable.
3. Docstring inline justificando el scope.

Ejemplo justificado: las 3 fixtures `scope="class"` en `tests/test_visual_elements_and_serp.py`
leen `core/pipeline.py` desde disco para tests parametrizados (read-only).

## Sin API keys en CI

La suite completa pasa sin variables de entorno de API keys (verificado al cerrar R2.8).
Tests nuevos que invoquen codigo de SDKs deben usar las fixtures de arriba; nunca asumir
que hay key disponible.
