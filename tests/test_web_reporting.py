"""Flask integration tests for SQL-backed reporting endpoint and city page."""
from datetime import datetime, timezone

import pytest
from src.app import app


@pytest.fixture
def client():
    app.config.update(TESTING=True)
    with app.test_client() as test_client:
        yield test_client


def test_report_api_returns_400_for_unsupported_city(client):
    result = client.get("/api/air-quality?city=Nowhere")
    assert result.status_code == 400
    assert result.is_json


def test_report_api_returns_404_before_database_is_populated(client, monkeypatch):
    monkeypatch.setattr("src.app.city_report", lambda city: None)
    result = client.get("/api/air-quality?city=Berlin")
    assert result.status_code == 404
    assert result.is_json


def test_report_api_renders_saved_results_in_json_and_ui(client, monkeypatch):
    demo = {
        "city": "Berlin", "mean_pm2_5": 7.43, "mean_pm10": 13.15,
        "max_european_aqi": 32, "forecast_hours": 3,
        "pm2_5_trend": "rising", "analyzed_at_utc": datetime(2026, 10, 18, tzinfo=timezone.utc),
    }
    monkeypatch.setattr("src.app.city_report", lambda city: demo)
    api = client.get("/api/air-quality?city=Berlin")
    assert api.status_code == 200
    assert api.get_json()["max_european_aqi"] == 32
    assert api.get_json()["analyzed_at_utc"].startswith("2026-10-18T")

    form = client.post("/", data={"city": "Berlin"})
    assert form.status_code == 200
    assert b"You searched for: Berlin" in form.data
    assert b"Latest forecast analysis" in form.data
    assert b"7.43" in form.data


def test_report_api_handles_database_failure(client, monkeypatch):
    def failure(city):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr("src.app.city_report", failure)
    result = client.get("/api/air-quality?city=Berlin")
    assert result.status_code == 503
    assert "error" in result.get_json()
