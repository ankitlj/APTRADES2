from __future__ import annotations

import threading

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgresql://") and "+psycopg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


# Phase 18 Tier 1: build one engine + sessionmaker per database URL instead of a
# brand-new engine (pool + DB handshake) on every call, and run create_all only
# once per URL. Guarded by a lock because gunicorn runs several gthread workers.
_lock = threading.RLock()
_engines: dict[str, Engine] = {}
_session_factories: dict[str, sessionmaker[Session]] = {}
_prepared_urls: set[str] = set()


def _build_engine(normalized_url: str) -> Engine:
    if normalized_url.startswith("sqlite"):
        # SQLite has no real connection pool to size; allow the shared engine to
        # be used across worker threads.
        return create_engine(
            normalized_url,
            future=True,
            pool_pre_ping=True,
            connect_args={"check_same_thread": False},
        )
    return create_engine(
        normalized_url,
        future=True,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_recycle=1800,
    )


def create_db_engine(database_url: str) -> Engine:
    normalized_url = normalize_database_url(database_url)
    engine = _engines.get(normalized_url)
    if engine is not None:
        return engine
    with _lock:
        engine = _engines.get(normalized_url)
        if engine is None:
            engine = _build_engine(normalized_url)
            _engines[normalized_url] = engine
        return engine


def create_session_factory(database_url: str) -> sessionmaker[Session]:
    normalized_url = normalize_database_url(database_url)
    factory = _session_factories.get(normalized_url)
    if factory is not None:
        return factory
    with _lock:
        factory = _session_factories.get(normalized_url)
        if factory is None:
            engine = create_db_engine(database_url)
            factory = sessionmaker(bind=engine, future=True, expire_on_commit=False)
            _session_factories[normalized_url] = factory
        return factory


def ensure_tables(database_url: str) -> None:
    from .models import Base

    normalized_url = normalize_database_url(database_url)
    if normalized_url in _prepared_urls:
        return
    with _lock:
        if normalized_url in _prepared_urls:
            return
        engine = create_db_engine(database_url)
        Base.metadata.create_all(bind=engine)
        _prepared_urls.add(normalized_url)


def check_database(database_url: str | None) -> str:
    if not database_url:
        return "not_configured"

    try:
        engine = create_db_engine(database_url)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return "offline"

    return "online"


def reset_caches() -> None:
    """Dispose and clear the process-wide engine/sessionmaker caches.

    Intended for test isolation; production never calls this."""
    with _lock:
        for engine in _engines.values():
            try:
                engine.dispose()
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
        _engines.clear()
        _session_factories.clear()
        _prepared_urls.clear()
