"""Unit and Flask integration tests for operational endpoints."""

import pytest

from src.monitoring import RequestMetrics


@pytest.fixture
def client():
    # Lazy import allows running pure metrics unit tests without Flask installed.
    from src.app import app
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_request_rate_unit():
    now = [100.0]
    metrics = RequestMetrics(window_seconds=10, clock=lambda: now[0])
    metrics.record_request()
    metrics.record_request()

    snapshot = metrics.snapshot()
    assert snapshot["requests_total"] == 2
    assert snapshot["requests_per_second"] == pytest.approx(0.2)

    # After the rolling window expires the current rate is zero.
    now[0] += 11
    snapshot = metrics.snapshot()
    assert snapshot["requests_total"] == 2
    assert snapshot["requests_per_second"] == 0.0


def test_health_returns_200_and_ok_json(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_metrics_returns_200_and_json_after_application_request(client):
    before = client.get("/metrics").get_json()["requests_total"]
    assert client.get("/api/echo?city=Berlin").status_code == 200
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.is_json
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["requests_total"] == before + 1
    assert payload["requests_per_second"] > 0
    assert payload["window_seconds"] == 60


def test_metrics_scrapes_do_not_inflate_request_count(client):
    before = client.get("/metrics").get_json()["requests_total"]
    client.get("/metrics")
    client.get("/metrics/prometheus")
    after = client.get("/metrics").get_json()["requests_total"]
    assert after == before


def test_prometheus_exposition_format(client):
    response = client.get("/metrics/prometheus")
    assert response.status_code == 200
    assert b"airquality_http_requests_total" in response.data
    assert b"airquality_http_requests_per_second" in response.data
