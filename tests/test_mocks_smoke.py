"""
Smoke tests para fixtures SDK-level de R2.8.

Verifican que cada fixture (mock_anthropic_client, mock_openai_client,
mock_requests_session) inyecta el mock correctamente en el sitio de uso
y que set_response() / map_url() modifican el comportamiento esperado.

Estos tests NO requieren API keys y pueden correr en CI sin credenciales.
"""
import pytest


# ============================================================================
# mock_anthropic_client
# ============================================================================

class TestAnthropicMock:
    def test_constructor_returns_mock(self, mock_anthropic_client):
        from core.generator import Anthropic
        client = Anthropic(api_key="dummy")
        assert client is mock_anthropic_client

    def test_default_response(self, mock_anthropic_client):
        from core.generator import Anthropic
        client = Anthropic(api_key="dummy")
        resp = client.messages.create()
        assert resp.content[0].text == "default response"
        assert resp.usage.input_tokens == 100
        assert resp.usage.output_tokens == 200

    def test_set_response_changes_output(self, mock_anthropic_client):
        from core.generator import Anthropic
        mock_anthropic_client.set_response("custom text", input_tokens=50, output_tokens=80)
        client = Anthropic(api_key="dummy")
        resp = client.messages.create()
        assert resp.content[0].text == "custom text"
        assert resp.usage.input_tokens == 50
        assert resp.usage.output_tokens == 80

    def test_content_generator_uses_mock(self, mock_anthropic_client):
        from core.generator import ContentGenerator
        gen = ContentGenerator(api_key="dummy")
        assert gen._client is mock_anthropic_client


# ============================================================================
# mock_openai_client
# ============================================================================

class TestOpenAIMock:
    def test_constructor_returns_mock(self, mock_openai_client):
        from core.openai_client import OpenAI
        client = OpenAI(api_key="dummy")
        assert client is mock_openai_client

    def test_get_client_returns_mock(self, mock_openai_client):
        from core.openai_client import get_client
        client = get_client()
        assert client is mock_openai_client

    def test_set_response_changes_output(self, mock_openai_client):
        from core.openai_client import get_client
        mock_openai_client.set_response("openai custom", prompt_tokens=42, completion_tokens=99)
        client = get_client()
        resp = client.chat.completions.create()
        assert resp.choices[0].message.content == "openai custom"
        assert resp.usage.prompt_tokens == 42
        assert resp.usage.completion_tokens == 99
        assert resp.usage.total_tokens == 141


# ============================================================================
# mock_requests_session
# ============================================================================

class TestRequestsMock:
    def test_unmocked_url_raises(self, mock_requests_session):
        import requests
        session = requests.Session()
        resp = session.get("https://unregistered.example/x")
        assert resp.status_code == 404
        with pytest.raises(Exception, match="unmocked URL"):
            resp.raise_for_status()

    def test_mapped_url_returns_body(self, mock_requests_session):
        import requests
        mock_requests_session.map_url("https://x.example", 200, "<html>ok</html>")
        session = requests.Session()
        resp = session.get("https://x.example")
        assert resp.status_code == 200
        assert resp.text == "<html>ok</html>"
        resp.raise_for_status()  # no debe elevar

    def test_consumer_module_uses_mock(self, mock_requests_session):
        # core.scraper hace `import requests` top-level. Patchear requests.Session
        # afecta a todos los consumidores porque el modulo es singleton.
        import core.scraper
        import requests
        assert core.scraper.requests is requests
        session = core.scraper.requests.Session()
        assert session is mock_requests_session
