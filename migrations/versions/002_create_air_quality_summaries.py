"""Create a table for analyzed forecast summaries.

Revision ID: 002
Revises: 001
"""
from alembic import op
import sqlalchemy as sa

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "air_quality_summaries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("city", sa.String(80), nullable=False, unique=True),
        sa.Column("forecast_hours", sa.Integer(), nullable=False),
        sa.Column("valid_pm2_5_hours", sa.Integer(), nullable=False),
        sa.Column("valid_pm10_hours", sa.Integer(), nullable=False),
        sa.Column("valid_aqi_hours", sa.Integer(), nullable=False),
        sa.Column("mean_pm2_5", sa.Float(), nullable=True),
        sa.Column("mean_pm10", sa.Float(), nullable=True),
        sa.Column("max_european_aqi", sa.Integer(), nullable=True),
        sa.Column("peak_forecast_time_utc", sa.String(17), nullable=True),
        sa.Column("pm2_5_delta", sa.Float(), nullable=True),
        sa.Column("pm2_5_trend", sa.String(20), nullable=False),
        sa.Column("source_fetched_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("analyzed_at_utc", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("air_quality_summaries")
