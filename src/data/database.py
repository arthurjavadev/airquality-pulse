"""A configurable SQLAlchemy database connection."""
import os

from sqlalchemy import create_engine


def get_database_url() -> str:
    """Local default is durable on disk; set DATABASE_URL for PostgreSQL."""
    url = os.environ.get("DATABASE_URL", "sqlite:///./airquality.db")
    # Some platforms still supply this legacy prefix.
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def make_engine(database_url: str | None = None):
    return create_engine(database_url or get_database_url(), pool_pre_ping=True)
