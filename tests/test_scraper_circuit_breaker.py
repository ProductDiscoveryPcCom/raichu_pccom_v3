"""
Tests for R2.3 — circuit breaker por host en WebScraper.

No live HTTP: tests aislados sobre helpers + un test de integración con
monkeypatch de session.get para simular ConnectionError repetidos.
"""
import threading
import time

import pytest
import requests

from core.scraper import (
    CIRCUIT_BREAKER_COOLDOWN,
    CIRCUIT_BREAKER_THRESHOLD,
    CircuitBreakerError,
    WebScraper,
)


@pytest.fixture
def scraper():
    # Cooldown corto y threshold bajo para tests rápidos.
    return WebScraper(timeout=5, max_retries=1, cb_threshold=3, cb_cooldown=2.0)


def test_check_circuit_closed_initially(scraper):
    assert scraper._check_circuit("example.com") is None


def test_record_failure_opens_after_threshold(scraper):
    host = "broken.example"
    for _ in range(scraper._cb_threshold):
        scraper._record_failure(host)

    remaining = scraper._check_circuit(host)
    assert remaining is not None
    assert 0 < remaining <= scraper._cb_cooldown


def test_record_failure_below_threshold_does_not_open(scraper):
    host = "flaky.example"
    for _ in range(scraper._cb_threshold - 1):
        scraper._record_failure(host)
    assert scraper._check_circuit(host) is None


def test_success_resets_failure_count(scraper):
    host = "ok.example"
    scraper._record_failure(host)
    scraper._record_failure(host)
    scraper._record_success(host)
    # Tras éxito, un fallo más no debe abrir todavía
    scraper._record_failure(host)
    assert scraper._check_circuit(host) is None


def test_circuit_resets_after_cooldown(scraper):
    host = "transient.example"
    for _ in range(scraper._cb_threshold):
        scraper._record_failure(host)
    assert scraper._check_circuit(host) is not None

    # Forzar expiración del cooldown
    state = scraper._host_state[host]
    state.opened_at = time.time() - scraper._cb_cooldown - 1

    assert scraper._check_circuit(host) is None
    # Estado limpio
    assert state.failure_count == 0
    assert state.opened_at is None


def test_threadsafe_increment(scraper):
    host = "concurrent.example"
    threads = []
    for _ in range(100):
        t = threading.Thread(target=scraper._record_failure, args=(host,))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()
    assert scraper._host_state[host].failure_count == 100


def test_host_of_extracts_netloc():
    assert WebScraper._host_of("https://Example.COM/path") == "example.com"
    assert WebScraper._host_of("http://foo.bar:8080/x") == "foo.bar:8080"
    assert WebScraper._host_of("not a url") == ""


def test_make_request_raises_circuit_breaker_when_open(scraper, monkeypatch):
    """Si el circuito está abierto, _make_request debe levantar CircuitBreakerError
    sin tocar la red."""
    host = "down.example"
    for _ in range(scraper._cb_threshold):
        scraper._record_failure(host)

    called = {"flag": False}

    def fail_if_called(*args, **kwargs):
        called["flag"] = True
        raise AssertionError("session.get no debe ejecutarse con circuito abierto")

    monkeypatch.setattr(scraper._session, "get", fail_if_called)

    with pytest.raises(CircuitBreakerError) as exc:
        scraper._make_request("https://down.example/x", (5.0, 5.0))

    assert exc.value.host == "down.example"
    assert exc.value.remaining > 0
    assert called["flag"] is False


def test_scrape_url_returns_result_on_circuit_open(scraper):
    """scrape_url no debe propagar CircuitBreakerError; debe devolver ScrapeResult
    con metadata['circuit_breaker'] = True."""
    host = "cb.example"
    for _ in range(scraper._cb_threshold):
        scraper._record_failure(host)

    result = scraper.scrape_url("https://cb.example/")
    assert result.success is False
    assert "circuit_breaker" in (result.error or "")
    assert result.metadata and result.metadata.get("circuit_breaker") is True
    assert result.metadata.get("host") == "cb.example"


def test_circuit_opens_after_repeated_connection_errors(monkeypatch):
    """Integración: monkeypatch de session.get para forzar ConnectionError
    repetidos. Tras 3 scrape_url, el 4º debe fallar con circuit_breaker sin
    llegar a session.get."""
    scraper = WebScraper(timeout=5, max_retries=1, cb_threshold=3, cb_cooldown=10.0)

    call_count = {"n": 0}

    def always_fail(*args, **kwargs):
        call_count["n"] += 1
        raise requests.exceptions.ConnectionError("simulated")

    monkeypatch.setattr(scraper._session, "get", always_fail)

    url = "https://flaky.example/x"
    for _ in range(scraper._cb_threshold):
        result = scraper.scrape_url(url)
        assert result.success is False

    calls_before = call_count["n"]
    # Siguiente intento: circuit breaker abierto
    result = scraper.scrape_url(url)
    assert result.success is False
    assert "circuit_breaker" in (result.error or "")
    # session.get NO debe haberse llamado de nuevo
    assert call_count["n"] == calls_before
