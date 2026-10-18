"""Read an SQL analysis without using a fake database."""
from src.data.analysis_gateway import AnalysisGateway
from src.data.database import make_engine
from src.reporting import city_report, serialize_report
from src.migrate import upgrade_database
from src.collector import collect
from src.analyzer import analyze
from pathlib import Path
import json
from types import SimpleNamespace


def test_report_reads_saved_analysis(monkeypatch, tmp_path):
    url = f"sqlite:///{tmp_path / 'reports.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    upgrade_database()
    fixture = Path(__file__).parent / "fixtures" / "open_meteo_sample.json"
    payload = json.loads(fixture.read_text())

    class StubHttp:
        def get(self, url, *, params, timeout):
            return SimpleNamespace(raise_for_status=lambda: None,
                                   json=lambda: payload)

    collect("Berlin", http_client=StubHttp(), database_url=url)
    analyze("Berlin", database_url=url)
    assert city_report("Berlin")["max_european_aqi"] == 32
    assert "T" in serialize_report(city_report("Berlin"))["analyzed_at_utc"]
    assert city_report("Not a city") is None
