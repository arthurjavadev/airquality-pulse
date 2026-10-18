"""Read persisted records back from the database (database proof)."""
import argparse
from src.data.database import make_engine
from src.data.gateway import ForecastGateway


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--city", default="Berlin")
    args = parser.parse_args(argv)
    engine = make_engine()
    try:
        rows = ForecastGateway(engine).list_by_city(args.city)
        print(f"Saved forecast records for {args.city}: {len(rows)}")
        for row in rows[:10]:
            print(f"{row['forecast_time_utc']} | PM2.5={row['pm2_5']} | PM10={row['pm10']} | European AQI={row['european_aqi']}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
