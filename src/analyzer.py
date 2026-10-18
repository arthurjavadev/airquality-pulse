"""Independent Data Analyzer process for the latest air quality forecast.

Run after migration and collection: python -m src.analyzer --city Berlin
Values are model forecasts, not measured historical pollution readings.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging
from statistics import fmean

from src.collector import CITIES
from src.data.analysis_gateway import AnalysisGateway
from src.data.database import make_engine


def summarize_forecasts(rows: list[dict], *, analyzed_at=None) -> dict:
    """Calculate a reproducible summary from an ordered forecast batch.

    Missing values (None) are omitted from each metric. The trend means
    difference between the first and last available PM2.5 FORECAST.
    """
    if not rows:
        raise ValueError("No forecast rows to analyze")
    ordered = sorted(rows, key=lambda row: row["forecast_time_utc"])
    city = ordered[0]["city"]
    if any(row["city"] != city for row in ordered):
        raise ValueError("Cannot analyze a batch containing several cities")

    pm25 = [row["pm2_5"] for row in ordered if row["pm2_5"] is not None]
    pm10 = [row["pm10"] for row in ordered if row["pm10"] is not None]
    aqi_rows = [row for row in ordered if row["european_aqi"] is not None]
    worst = max(aqi_rows, key=lambda row: row["european_aqi"]) if aqi_rows else None
    delta = round(pm25[-1] - pm25[0], 2) if len(pm25) >= 2 else None

    if delta is None:
        trend = "insufficient data"
    elif delta > 0:
        trend = "rising"
    elif delta < 0:
        trend = "falling"
    else:
        trend = "stable"

    return {
        "city": city,
        "forecast_hours": len(ordered),
        "valid_pm2_5_hours": len(pm25),
        "valid_pm10_hours": len(pm10),
        "valid_aqi_hours": len(aqi_rows),
        "mean_pm2_5": round(fmean(pm25), 2) if pm25 else None,
        "mean_pm10": round(fmean(pm10), 2) if pm10 else None,
        "max_european_aqi": worst["european_aqi"] if worst else None,
        "peak_forecast_time_utc": worst["forecast_time_utc"] if worst else None,
        "pm2_5_delta": delta,
        "pm2_5_trend": trend,
        "source_fetched_at_utc": ordered[0]["fetched_at_utc"],
        "analyzed_at_utc": analyzed_at or datetime.now(timezone.utc),
    }


def analyze(city: str, *, database_url=None) -> dict:
    """Read latest collected data from SQL and persist the derived summary."""
    name = CITIES.get(city.strip().casefold())
    if name is None:
        raise ValueError(f"Unknown city: {city}")
    canonical_city = name[0]
    engine = make_engine(database_url)
    try:
        gateway = AnalysisGateway(engine)
        rows = gateway.latest_forecasts(canonical_city)
        if not rows:
            raise ValueError(
                f"No collected forecasts for {canonical_city}. "
                "Run python -m src.collector first."
            )
        summary = summarize_forecasts(rows)
        gateway.save(summary)
        return summary
    finally:
        engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Analyze stored air quality forecasts")
    parser.add_argument("--city", default="Berlin", help="Berlin, Frankfurt, London or Paris")
    args = parser.parse_args(argv)
    try:
        summary = analyze(args.city)
    except ValueError as exc:
        logging.error("Analysis failed: %s", exc)
        return 1
    print(f"City: {summary['city']}")
    print(f"Forecast hours analyzed: {summary['forecast_hours']}")
    print(f"Average PM2.5: {summary['mean_pm2_5']} ug/m3")
    print(f"Average PM10: {summary['mean_pm10']} ug/m3")
    print(f"Maximum European AQI: {summary['max_european_aqi']}")
    print(f"Peak AQI forecast time (UTC): {summary['peak_forecast_time_utc']}")
    print(f"PM2.5 first-to-last change: {summary['pm2_5_delta']} ug/m3")
    print(f"Forecast PM2.5 trend: {summary['pm2_5_trend']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
