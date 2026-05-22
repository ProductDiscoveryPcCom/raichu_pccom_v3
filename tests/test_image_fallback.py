"""
Tests del fallback de generación de imágenes a OpenAI gpt-image-1.

Cubre:
  - _fit_to_size: recorte centrado + resize al tamaño objetivo (Pillow real).
  - _generate_single_image_openai: parseo de b64, ajuste de tamaño, args al SDK.
  - generate_images: orquestación Gemini → OpenAI (sin keys; mocks por monkeypatch).

No se hacen llamadas reales a ninguna API.
"""
import base64
import io

import pytest

from utils import image_gen
from utils.image_gen import (
    ImageType,
    ImageRequest,
    OPENAI_IMAGE_MODEL,
    DEFAULT_MODEL,
    _fit_to_size,
    _generate_single_image_openai,
    generate_images,
)


def _png_bytes(w: int, h: int) -> bytes:
    """PNG sólido de w×h vía Pillow."""
    from PIL import Image
    img = Image.new("RGB", (w, h), (120, 120, 120))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _dims(image_bytes: bytes):
    from PIL import Image
    return Image.open(io.BytesIO(image_bytes)).size


class _FakeImageData:
    def __init__(self, b64):
        self.b64_json = b64


class _FakeImagesResponse:
    def __init__(self, b64):
        self.data = [_FakeImageData(b64)] if b64 is not None else []


def _mock_openai_client(b64=None, raises=None):
    from unittest.mock import MagicMock
    client = MagicMock()
    if raises is not None:
        client.images.generate.side_effect = raises
    else:
        client.images.generate.return_value = _FakeImagesResponse(b64)
    return client


# ── _fit_to_size ─────────────────────────────────────────────────────────

class TestFitToSize:
    def test_landscape_to_cover_16_9(self):
        # gpt-image-1 landscape 1536x1024 → portada 1024x576
        out = _fit_to_size(_png_bytes(1536, 1024), 1024, 576)
        assert out is not None
        assert _dims(out) == (1024, 576)

    def test_portrait_to_infographic_9_16(self):
        out = _fit_to_size(_png_bytes(1024, 1536), 1024, 1792)
        assert out is not None
        assert _dims(out) == (1024, 1792)

    def test_square_passthrough_dims(self):
        out = _fit_to_size(_png_bytes(1024, 1024), 1024, 1024)
        assert _dims(out) == (1024, 1024)

    def test_invalid_bytes_returns_none(self):
        assert _fit_to_size(b"not-an-image", 1024, 576) is None


# ── _generate_single_image_openai ────────────────────────────────────────

class TestGenerateSingleImageOpenAI:
    def test_returns_fitted_cover(self):
        b64 = base64.b64encode(_png_bytes(1536, 1024)).decode()
        client = _mock_openai_client(b64=b64)

        raw, mime, err = _generate_single_image_openai(
            "un prompt", ImageType.COVER, client=client,
        )

        assert err == ""
        assert mime == "image/png"
        assert _dims(raw) == (1024, 576)  # ajustado al objetivo del tipo

    def test_requests_correct_model_and_size(self):
        b64 = base64.b64encode(_png_bytes(1024, 1536)).decode()
        client = _mock_openai_client(b64=b64)

        _generate_single_image_openai("p", ImageType.INFOGRAPHIC, client=client)

        _, kwargs = client.images.generate.call_args
        assert kwargs["model"] == OPENAI_IMAGE_MODEL
        assert kwargs["size"] == "1024x1536"  # portrait para infografía
        assert kwargs["n"] == 1

    def test_empty_data_returns_error(self):
        client = _mock_openai_client(b64=None)
        raw, mime, err = _generate_single_image_openai("p", ImageType.SUMMARY, client=client)
        assert raw is None
        assert "no devolvio imagen" in err.lower()

    def test_exception_is_captured(self):
        client = _mock_openai_client(raises=RuntimeError("403 org not verified"))
        raw, mime, err = _generate_single_image_openai("p", ImageType.COVER, client=client)
        assert raw is None
        assert "403 org not verified" in err


# ── generate_images: orquestación con fallback ─────────────────────────────

class TestGenerateImagesFallback:
    @pytest.fixture(autouse=True)
    def _no_sleep(self, monkeypatch):
        monkeypatch.setattr(image_gen.time, "sleep", lambda *_: None)

    def _req(self, t=ImageType.COVER):
        return ImageRequest(image_type=t, keyword="kw", output_formats=[])

    def test_gemini_unavailable_uses_openai(self, monkeypatch):
        monkeypatch.setattr(image_gen, "_get_gemini_client", lambda: (None, "no gemini"))
        monkeypatch.setattr(image_gen, "_get_openai_image_client", lambda: (object(), ""))
        monkeypatch.setattr(
            image_gen, "_generate_single_image_openai",
            lambda prompt, itype, client=None: (b"img", "image/png", ""),
        )

        result = generate_images([self._req()])

        assert result.success is True
        assert len(result.images) == 1
        assert result.model_used == OPENAI_IMAGE_MODEL

    def test_gemini_runtime_failure_falls_back_per_image(self, monkeypatch):
        monkeypatch.setattr(image_gen, "_get_gemini_client", lambda: (object(), ""))
        monkeypatch.setattr(image_gen, "_get_openai_image_client", lambda: (object(), ""))
        # Gemini falla en runtime para esta imagen
        monkeypatch.setattr(
            image_gen, "_generate_single_image",
            lambda *a, **kw: (None, "", "gemini boom"),
        )
        called = {"oai": False}

        def _fake_oai(prompt, itype, client=None):
            called["oai"] = True
            return (b"img", "image/png", "")

        monkeypatch.setattr(image_gen, "_generate_single_image_openai", _fake_oai)

        result = generate_images([self._req()])

        assert called["oai"] is True
        assert result.success is True
        assert result.model_used == OPENAI_IMAGE_MODEL

    def test_gemini_success_does_not_call_openai(self, monkeypatch):
        monkeypatch.setattr(image_gen, "_get_gemini_client", lambda: (object(), ""))
        monkeypatch.setattr(image_gen, "_get_openai_image_client", lambda: (object(), ""))
        monkeypatch.setattr(
            image_gen, "_generate_single_image",
            lambda *a, **kw: (b"gem", "image/png", ""),
        )

        def _boom(*a, **kw):
            raise AssertionError("OpenAI no debe usarse si Gemini funciona")

        monkeypatch.setattr(image_gen, "_generate_single_image_openai", _boom)

        result = generate_images([self._req()])

        assert result.success is True
        assert result.model_used == DEFAULT_MODEL

    def test_no_provider_available_fails(self, monkeypatch):
        monkeypatch.setattr(image_gen, "_get_gemini_client", lambda: (None, "no gemini"))
        monkeypatch.setattr(image_gen, "_get_openai_image_client", lambda: (None, "no openai"))

        result = generate_images([self._req()])

        assert result.success is False
        assert result.error
