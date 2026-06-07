from __future__ import annotations

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_db_engine(database_url: str) -> Engine:
    return create_engine(normalize_database_url(database_url), future=True, pool_pre_ping=True)


def check_database(database_url: str | None) -> str:
    if not database_url:
        return "not_configured"

    try:
        engine = create_db_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return "offline"

    return "online"
