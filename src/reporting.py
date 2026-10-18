"""Read prepared SQL summaries for web UI and REST API."""
import os

from src.collector import CITIES
from src.data.analysis_gateway import AnalysisGateway
from src.data.database import make_engine


def city_report(city: str) -> dict | None:
    """Read the latest report or return None if no DB is configured."""
    if not os.environ.get("DATABASE_URL"):
        return None
    canonical = CITIES.get(city.strip().casefold())
    if canonical is None:
        return None
    engine = make_engine()
    try:
        return AnalysisGateway(engine).find_by_city(canonical[0])
    finally:
        engine.dispose()


def serialize_report(report: dict) -> dict:
    """Turn SQL types such as datetime into JSON-friendly strings."""
    return {key: value.isoformat() if hasattr(value, "isoformat") else value
            for key, value in report.items()}
