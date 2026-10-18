"""SQL gateways for reading a forecast batch and writing an analysis."""
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from src.data.models import AirQualityForecast, AirQualitySummary


class AnalysisGateway:
    def __init__(self, engine):
        self.engine = engine

    def latest_forecasts(self, city: str) -> list[dict]:
        """Read just the most recent complete collection run for a city.

        Old forecasts can remain in the table after repeated collection.
        The collector stamps all rows in one request with the same time.
        """
        latest_stamp = (
            select(func.max(AirQualityForecast.fetched_at_utc))
            .where(AirQualityForecast.city == city)
            .scalar_subquery()
        )
        statement = (
            select(
                AirQualityForecast.city,
                AirQualityForecast.forecast_time_utc,
                AirQualityForecast.pm2_5,
                AirQualityForecast.pm10,
                AirQualityForecast.european_aqi,
                AirQualityForecast.fetched_at_utc,
            )
            .where(
                AirQualityForecast.city == city,
                AirQualityForecast.fetched_at_utc == latest_stamp,
            )
            .order_by(AirQualityForecast.forecast_time_utc)
        )
        with self.engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(statement)]

    def save(self, summary: dict):
        """Insert or replace the stored summary for this city."""
        with self.engine.begin() as connection:
            dialect = connection.dialect.name
            if dialect == "postgresql":
                statement = pg_insert(AirQualitySummary)
            elif dialect == "sqlite":
                statement = sqlite_insert(AirQualitySummary)
            else:
                raise ValueError(f"Unsupported database dialect: {dialect}")
            statement = statement.values(summary)
            statement = statement.on_conflict_do_update(
                index_elements=["city"],
                set_={key: getattr(statement.excluded, key)
                      for key in summary if key != "city"},
            )
            connection.execute(statement)

    def find_by_city(self, city: str) -> dict | None:
        statement = (
            select(
                AirQualitySummary.city,
                AirQualitySummary.forecast_hours,
                AirQualitySummary.valid_pm2_5_hours,
                AirQualitySummary.valid_pm10_hours,
                AirQualitySummary.valid_aqi_hours,
                AirQualitySummary.mean_pm2_5,
                AirQualitySummary.mean_pm10,
                AirQualitySummary.max_european_aqi,
                AirQualitySummary.peak_forecast_time_utc,
                AirQualitySummary.pm2_5_delta,
                AirQualitySummary.pm2_5_trend,
                AirQualitySummary.source_fetched_at_utc,
                AirQualitySummary.analyzed_at_utc,
            )
            .where(AirQualitySummary.city == city)
        )
        with self.engine.connect() as connection:
            row = connection.execute(statement).mappings().first()
            return dict(row) if row is not None else None
