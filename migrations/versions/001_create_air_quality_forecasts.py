"""Create forecast records.

Revision ID: 001
Revises:
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "air_quality_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("city", sa.String(80), nullable=False),
        sa.Column("forecast_time_utc", sa.String(17), nullable=False),
        sa.Column("pm2_5", sa.Float(), nullable=True),
        sa.Column("pm10", sa.Float(), nullable=True),
        sa.Column("european_aqi", sa.Integer(), nullable=True),
        sa.Column("fetched_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("city", "forecast_time_utc", name="uq_city_forecast_time"),
    )
    op.create_index(
        "ix_air_quality_city_time", "air_quality_forecasts",
        ["city", "forecast_time_utc"],
    )


def downgrade():
    op.drop_index("ix_air_quality_city_time", table_name="air_quality_forecasts")
    op.drop_table("air_quality_forecasts")
