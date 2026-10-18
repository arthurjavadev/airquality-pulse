"""Run schema migrations: python -m src.migrate"""
from pathlib import Path
from alembic import command
from alembic.config import Config


def upgrade_database():
    root = Path(__file__).resolve().parents[1]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("script_location", str(root / "migrations"))
    command.upgrade(cfg, "head")


if __name__ == "__main__":
    upgrade_database()
    print("Database schema is up to date.")
