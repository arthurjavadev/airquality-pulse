"""Record model for individual hourly forecast estimates."""
from sqlalchemy import DateTime, Float, Integer, String, UniqueConstraint, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime


class Base(DeclarativeBase):
    pass


class AirQualityForecast(Base):
    __tablename__ = "air_quality_forecasts"
    __table_args__ = (
        UniqueConstraint("city", "forecast_time_utc", name="uq_city_forecast_time"),
        Index("ix_air_quality_city_time", "city", "forecast_time_utc"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    forecast_time_utc: Mapped[str] = mapped_column(String(17), nullable=False)
    pm2_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm10: Mapped[float | None] = mapped_column(Float, nullable=True)
    european_aqi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fetched_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)



class AirQualitySummary(Base):
    """One analysis of the latest forecast batch for a city."""
    __tablename__ = "air_quality_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    city: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    forecast_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_pm2_5_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_pm10_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    valid_aqi_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    mean_pm2_5: Mapped[float | None] = mapped_column(Float, nullable=True)
    mean_pm10: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_european_aqi: Mapped[int | None] = mapped_column(Integer, nullable=True)
    peak_forecast_time_utc: Mapped[str | None] = mapped_column(String(17), nullable=True)
    pm2_5_delta: Mapped[float | None] = mapped_column(Float, nullable=True)
    pm2_5_trend: Mapped[str] = mapped_column(String(20), nullable=False)
    source_fetched_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    analyzed_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
