"""Alembic environment: reads DATABASE_URL, or uses local SQLite default."""
from logging.config import fileConfig
from alembic import context
from sqlalchemy import pool
from src.data.database import make_engine
from src.data.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    from src.data.database import get_database_url
    context.configure(
        url=get_database_url(), target_metadata=target_metadata,
        literal_binds=True, compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    engine = make_engine()
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
