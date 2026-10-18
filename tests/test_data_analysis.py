"""Fast unit tests and real-SQL integration tests for Data Analyzer."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect

from src.analyzer import analyze, summarize_forecasts
from src.collector import collect, normalize_forecasts
from src.data.analysis_gateway import AnalysisGateway
from src.data.database import make_engine
from src.data.gateway import ForecastGateway
from src.migrate import upgrade_database


@pytest.fixture
def sample():
    path = Path(__file__).parent / "fixtures" / "open_meteo_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def database(monkeypatch, tmp_path):
    uri = f"sqlite:///{tmp_path / 'analysis_test.db'}"
    monkeypatch.setenv("DATABASE_URL", uri)
    upgrade_database()
    yield uri


class StubResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class StubHttp:
    def __init__(self, payload):
        self.payload = payload

    def get(self, *args, **kwargs):
        return StubResponse(self.payload)


def test_unit_calculates_means_peak_and_trend(sample):
    rows = normalize_forecasts(
        "Berlin", sample,
        fetched_at=datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    summary = summarize_forecasts(rows)
    assert summary["forecast_hours"] == 3
    assert summary["mean_pm2_5"] == 7.43
    assert summary["valid_pm2_5_hours"] == 3
    assert summary["mean_pm10"] == 13.15
    assert summary["valid_pm10_hours"] == 2
    assert summary["max_european_aqi"] == 32
    assert summary["peak_forecast_time_utc"] == "2026-10-18T11:00Z"
    assert summary["pm2_5_delta"] == 1.7
    assert summary["pm2_5_trend"] == "rising"


def test_unit_handles_missing_values_and_no_trend(sample):
    rows = normalize_forecasts("Berlin", sample)
    for row in rows:
        row["pm2_5"] = None
        row["pm10"] = None
        row["european_aqi"] = None
    summary = summarize_forecasts(rows)
    assert summary["mean_pm2_5"] is None
    assert summary["mean_pm10"] is None
    assert summary["max_european_aqi"] is None
    assert summary["pm2_5_delta"] is None
    assert summary["pm2_5_trend"] == "insufficient data"


def test_integration_collects_analyzes_and_persists(database, sample):
    engine = make_engine(database)
    try:
        assert "air_quality_summaries" in inspect(engine).get_table_names()
        assert collect("Berlin", http_client=StubHttp(sample), database_url=database) == 3
        summary = analyze("Berlin", database_url=database)
        assert summary["mean_pm2_5"] == 7.43
        saved = AnalysisGateway(engine).find_by_city("Berlin")
        assert saved is not None
        assert saved["forecast_hours"] == 3
        assert saved["mean_pm10"] == 13.15
        assert saved["pm2_5_trend"] == "rising"
    finally:
        engine.dispose()


def test_integration_uses_latest_collection_only(database, sample):
    engine = make_engine(database)
    try:
        first_stamp = datetime(2026, 10, 18, 9, tzinfo=timezone.utc)
        first = normalize_forecasts("Berlin", sample, fetched_at=first_stamp)
        ForecastGateway(engine).upsert(first)

        second = normalize_forecasts(
            "Berlin", sample,
            fetched_at=first_stamp + timedelta(hours=1),
        )
        second = second[1:]
        second[0]["pm2_5"] = 50.0
        second[1]["pm2_5"] = 60.0
        ForecastGateway(engine).upsert(second)

        summary = analyze("Berlin", database_url=database)
        assert summary["forecast_hours"] == 2
        assert summary["mean_pm2_5"] == 55.0
        assert summary["pm2_5_delta"] == 10.0
        saved = AnalysisGateway(engine).find_by_city("Berlin")
        assert saved["forecast_hours"] == 2
        assert saved["mean_pm2_5"] == 55.0
        assert ForecastGateway(engine).count() == 3
    finally:
        engine.dispose()


def test_integration_reanalysis_updates_instead_of_duplicating(database, sample):
    collect("Berlin", http_client=StubHttp(sample), database_url=database)
    analyze("Berlin", database_url=database)
    changed = json.loads(json.dumps(sample))
    changed["hourly"]["pm2_5"] = [10.0, 10.0, 10.0]
    collect("Berlin", http_client=StubHttp(changed), database_url=database)
    new = analyze("Berlin", database_url=database)
    engine = make_engine(database)
    try:
        assert new["mean_pm2_5"] == 10.0
        from sqlalchemy import select, func
        from src.data.models import AirQualitySummary
        with engine.connect() as conn:
            assert conn.scalar(select(func.count()).select_from(AirQualitySummary)) == 1
    finally:
        engine.dispose()


def test_integration_empty_city_is_rejected(database):
    with pytest.raises(ValueError, match="No collected forecasts"):
        analyze("Berlin", database_url=database)
