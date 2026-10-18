"""Data Gateway pattern: writes forecasts and reads them back from a real SQL DB."""
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.data.models import AirQualityForecast


class ForecastGateway:
    def __init__(self, engine):
        self.engine = engine

    def upsert(self, records: list[dict]) -> int:
        if not records:
            return 0
        with self.engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "postgresql":
                statement = pg_insert(AirQualityForecast)
            elif dialect == "sqlite":
                statement = sqlite_insert(AirQualityForecast)
            else:
                raise ValueError(f"Unsupported database dialect: {dialect}")

            # Re-running the collector updates existing forecasts, not duplicates.
            statement = statement.values(records).on_conflict_do_update(
                index_elements=["city", "forecast_time_utc"],
                set_={
                    "pm2_5": statement.excluded.pm2_5,
                    "pm10": statement.excluded.pm10,
                    "european_aqi": statement.excluded.european_aqi,
                    "fetched_at_utc": statement.excluded.fetched_at_utc,
                },
            )
            connection.execute(statement)
        return len(records)

    def list_by_city(self, city: str) -> list[dict]:
        with self.engine.connect() as connection:
            results = connection.execute(
                select(
                    AirQualityForecast.forecast_time_utc,
                    AirQualityForecast.pm2_5,
                    AirQualityForecast.pm10,
                    AirQualityForecast.european_aqi,
                )
                .where(AirQualityForecast.city == city)
                .order_by(AirQualityForecast.forecast_time_utc)
            )
            return [dict(row._mapping) for row in results]

    def count(self) -> int:
        with self.engine.connect() as connection:
            return connection.scalar(select(func.count()).select_from(AirQualityForecast)) or 0
