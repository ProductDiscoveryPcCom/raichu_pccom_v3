"""
Tests del parámetro `prefill` en core.generator.call_claude_api.

Prefill añade un mensaje assistant final antes de llamar al SDK, forzando que
la respuesta del modelo arranque desde ese texto. El parser de call_claude_api
prepende el prefill al `content` retornado, de modo que el consumidor recibe
la respuesta completa (ej. JSON parseable directamente con json.loads).

Cobertura:
- Comportamiento por defecto (sin prefill) sigue siendo idéntico (retrocompat).
- Con prefill='{' el content empieza por '{' y json.loads OK.
- El payload `messages` enviado al SDK contiene el turno assistant con el prefill.
- Streaming path (max_tokens > NONSTREAMING_MAX_TOKENS) también respeta prefill.
"""
import json


def test_call_claude_api_sin_prefill_es_retrocompatible(mock_anthropic_client):
    """Sin prefill: messages tiene solo el turno user; content no se modifica."""
    mock_anthropic_client.set_response("respuesta normal")

    from core.generator import call_claude_api

    response = call_claude_api(
        prompt="hola",
        client=mock_anthropic_client,
        max_tokens=1000,
    )

    assert response.content == "respuesta normal"

    kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert kwargs["messages"] == [{"role": "user", "content": "hola"}]


def test_call_claude_api_prefill_inyecta_assistant_en_messages(mock_anthropic_client):
    """Con prefill: se añade un turno assistant al final de messages."""
    mock_anthropic_client.set_response('"key":"value"}')

    from core.generator import call_claude_api

    call_claude_api(
        prompt="dame JSON",
        client=mock_anthropic_client,
        max_tokens=1000,
        prefill="{",
    )

    kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert kwargs["messages"] == [
        {"role": "user", "content": "dame JSON"},
        {"role": "assistant", "content": "{"},
    ]


def test_call_claude_api_prefill_se_prepende_al_content(mock_anthropic_client):
    """El content retornado incluye el prefill al inicio, ergo parseable como JSON."""
    mock_anthropic_client.set_response('"titles":["a","b"],"descriptions":["x"]}')

    from core.generator import call_claude_api

    response = call_claude_api(
        prompt="genera RSA",
        client=mock_anthropic_client,
        max_tokens=1000,
        prefill="{",
    )

    assert response.content.startswith("{")
    parsed = json.loads(response.content)
    assert parsed == {"titles": ["a", "b"], "descriptions": ["x"]}


def test_call_claude_api_prefill_funciona_en_streaming(mock_anthropic_client):
    """Sobre el umbral de streaming, prefill también se prepende al content."""
    from core.generator import NONSTREAMING_MAX_TOKENS

    mock_anthropic_client.set_response('"data":42}')

    from core.generator import call_claude_api

    response = call_claude_api(
        prompt="json grande",
        client=mock_anthropic_client,
        max_tokens=NONSTREAMING_MAX_TOKENS + 1,
        prefill="{",
    )

    assert response.content == '{"data":42}'
    # Confirmamos que efectivamente fue por el camino de streaming
    mock_anthropic_client.messages.stream.assert_called_once()
    mock_anthropic_client.messages.create.assert_not_called()


def test_content_generator_pasa_prefill(mock_anthropic_client):
    """ContentGenerator.generate propaga prefill hasta el SDK."""
    mock_anthropic_client.set_response('"ok":true}')

    from core.generator import ContentGenerator

    gen = ContentGenerator(api_key="sk-ant-dummy", max_tokens=1000)
    result = gen.generate(prompt="dame JSON", prefill="{")

    assert result.success
    assert result.content == '{"ok":true}'

    kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    assert {"role": "assistant", "content": "{"} in kwargs["messages"]


def test_content_generator_sin_prefill_no_inyecta_assistant(mock_anthropic_client):
    """Default sin prefill: no aparece turno assistant en messages."""
    mock_anthropic_client.set_response("texto")

    from core.generator import ContentGenerator

    gen = ContentGenerator(api_key="sk-ant-dummy", max_tokens=1000)
    result = gen.generate(prompt="hola")

    assert result.success
    kwargs = mock_anthropic_client.messages.create.call_args.kwargs
    roles = [m["role"] for m in kwargs["messages"]]
    assert roles == ["user"]
