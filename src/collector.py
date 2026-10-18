"""Independent AirQuality Pulse Data Collector process.

Run AFTER migration: python -m src.collector --city Berlin
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import logging

import requests

from src.data.database import make_engine
from src.data.gateway import ForecastGateway

API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
# Named locations avoid requiring a geocoding API for the assignment.
CITIES = {
    "berlin": ("Berlin", 52.5200, 13.4050),
    "frankfurt": ("Frankfurt", 50.1109, 8.6821),
    "london": ("London", 51.5074, -0.1278),
    "paris": ("Paris", 48.8566, 2.3522),
}


def fetch_air_quality(city: str, *, http_client=requests) -> dict:
    """Make an ACTUAL HTTP GET call to Open-Meteo (mocked only in tests)."""
    key = city.strip().casefold()
    if key not in CITIES:
        raise ValueError(f"Unknown city: {city}. Choose one of: {', '.join(c[0] for c in CITIES.values())}")
    _, lat, lon = CITIES[key]
    response = http_client.get(
        API_URL,
        params={
            "latitude": lat,
            "longitude": lon,
            "hourly": "pm2_5,pm10,european_aqi",
            "forecast_hours": 24,
            "timezone": "GMT",  # All returned timestamps represent UTC.
        },
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("error"):
        raise ValueError(f"Invalid Open-Meteo response: {payload}")
    return payload


def normalize_forecasts(city: str, payload: dict, *, fetched_at=None) -> list[dict]:
    """Validate hourly data and convert UTC timestamps into SQL records."""
    key = city.strip().casefold()
    if key not in CITIES:
        raise ValueError(f"Unknown city: {city}")
    city_name = CITIES[key][0]
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise ValueError("Response does not contain the expected hourly object")
    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise ValueError("Response contains no hourly timestamps")
    fields = ("pm2_5", "pm10", "european_aqi")
    for field in fields:
        if not isinstance(hourly.get(field), list) or len(hourly[field]) != len(times):
            raise ValueError(f"Missing or mismatched hourly array: {field}")
    stamp = fetched_at or datetime.now(timezone.utc)
    rows = []
    for index, value in enumerate(times):
        # API is called with timezone=GMT, so naive API timestamps are UTC.
        forecast_time = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if forecast_time.tzinfo is None:
            forecast_time = forecast_time.replace(tzinfo=timezone.utc)
        forecast_time = forecast_time.astimezone(timezone.utc)
        if forecast_time.minute or forecast_time.second:
            raise ValueError("Expected hourly timestamps on an exact hour")
        rows.append({
            "city": city_name,
            "forecast_time_utc": forecast_time.strftime("%Y-%m-%dT%H:%MZ"),
            "pm2_5": hourly["pm2_5"][index],
            "pm10": hourly["pm10"][index],
            "european_aqi": hourly["european_aqi"][index],
            "fetched_at_utc": stamp,
        })
    return rows


def collect(city: str, *, http_client=requests, database_url=None) -> int:
    """Fetch external data and persist it through the gateway."""
    payload = fetch_air_quality(city, http_client=http_client)
    records = normalize_forecasts(city, payload)
    engine = make_engine(database_url)
    try:
        return ForecastGateway(engine).upsert(records)
    finally:
        engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Fetch real Open-Meteo forecasts into SQL")
    parser.add_argument("--city", default="Berlin", help="Berlin, Frankfurt, London or Paris")
    args = parser.parse_args(argv)
    try:
        total = collect(args.city)
    except (ValueError, requests.RequestException) as exc:
        logging.error("Collection failed: %s", exc)
        return 1
    print(f"Saved/updated {total} hourly air-quality records for {args.city}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
