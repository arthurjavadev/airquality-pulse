"""Independent scheduled Data Collector with RabbitMQ event publishing."""
from __future__ import annotations

import argparse
import logging
import time

from src.collector import CITIES, collect
from src.messaging import publish_collected_event

LOGGER = logging.getLogger(__name__)


def collect_and_publish(cities: list[str], *, collect_fn=collect, publish_fn=publish_collected_event):
    """Save one city in SQL, then publish a message for its analysis."""
    succeeded = []
    failed = []
    for city in cities:
        try:
            count = collect_fn(city)
            event = publish_fn(CITIES[city.strip().casefold()][0], count)
            succeeded.append(event)
            LOGGER.info("Saved and published %s: %d forecasts", city, count)
        except Exception:
            LOGGER.exception("Collection/publishing failed for %s", city)
            failed.append(city)
    return succeeded, failed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Collect and publish RabbitMQ events")
    parser.add_argument("--cities", default="Berlin,Frankfurt,London,Paris")
    parser.add_argument("--interval-seconds", type=int, default=0,
                        help="0 for one-shot cron mode; positive for continuous worker")
    args = parser.parse_args(argv)
    if args.interval_seconds < 0:
        parser.error("--interval-seconds must be zero or positive")
    cities = [city.strip() for city in args.cities.split(",") if city.strip()]
    if not cities or any(city.casefold() not in CITIES for city in cities):
        parser.error("Unsupported or missing city")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        _, failed = collect_and_publish(cities)
        if args.interval_seconds == 0:
            return 1 if failed else 0
        time.sleep(args.interval_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
