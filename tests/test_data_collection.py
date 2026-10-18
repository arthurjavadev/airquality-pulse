"""Offline deterministic tests; SQL statements use a real SQLite DB, not mocks."""
import json
from pathlib import Path

import pytest
from sqlalchemy import inspect

from src.collector import API_URL, collect, fetch_air_quality, normalize_forecasts
from src.data.database import make_engine
from src.data.gateway import ForecastGateway
from src.migrate import upgrade_database


@pytest.fixture
def fixture_payload():
    path = Path(__file__).parent / "fixtures" / "open_meteo_sample.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def test_database(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'test_air_quality.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    upgrade_database()  # Real Alembic migration creates schema for test.
    yield url


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self.payload


class FakeHttp:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get(self, url, *, params, timeout):
        self.calls.append((url, params, timeout))
        return FakeResponse(self.payload)


def test_fetches_external_api_with_expected_query(fixture_payload):
    http = FakeHttp(fixture_payload)
    result = fetch_air_quality("Berlin", http_client=http)
    assert result["hourly"]["pm2_5"][0] == 6.4
    url, params, timeout = http.calls[0]
    assert url == API_URL
    assert params["hourly"] == "pm2_5,pm10,european_aqi"
    assert params["timezone"] == "GMT"
    assert timeout == 20


def test_normalization_has_utc_and_handles_missing_value(fixture_payload):
    rows = normalize_forecasts("Berlin", fixture_payload)
    assert len(rows) == 3
    assert rows[0]["forecast_time_utc"] == "2026-10-18T09:00Z"
    assert rows[2]["pm10"] is None


def test_migration_creates_real_sql_table(test_database):
    engine = make_engine(test_database)
    try:
        assert "air_quality_forecasts" in inspect(engine).get_table_names()
        assert "alembic_version" in inspect(engine).get_table_names()
    finally:
        engine.dispose()


def test_collector_persists_real_records_and_reads_them(test_database, fixture_payload):
    http = FakeHttp(fixture_payload)
    assert collect("Berlin", http_client=http, database_url=test_database) == 3
    engine = make_engine(test_database)
    try:
        db = ForecastGateway(engine)
        assert db.count() == 3
        rows = db.list_by_city("Berlin")
        assert [x["european_aqi"] for x in rows] == [23, 27, 32]
        assert rows[2]["pm10"] is None
    finally:
        engine.dispose()


def test_recollection_upserts_instead_of_duplicating(test_database, fixture_payload):
    http = FakeHttp(fixture_payload)
    collect("Berlin", http_client=http, database_url=test_database)
    modified = json.loads(json.dumps(fixture_payload))
    modified["hourly"]["pm2_5"][0] = 99.0
    collect("Berlin", http_client=FakeHttp(modified), database_url=test_database)
    engine = make_engine(test_database)
    try:
        db = ForecastGateway(engine)
        assert db.count() == 3
        assert db.list_by_city("Berlin")[0]["pm2_5"] == 99.0
    finally:
        engine.dispose()


def test_invalid_payload_is_not_persisted(test_database):
    with pytest.raises(ValueError, match="hourly"):
        collect("Berlin", http_client=FakeHttp({"hourly": {}}), database_url=test_database)
    engine = make_engine(test_database)
    try:
        assert ForecastGateway(engine).count() == 0
    finally:
        engine.dispose()
