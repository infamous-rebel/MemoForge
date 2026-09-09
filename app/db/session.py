"""Database session management.

Provides engine creation, session factory, and dependency injection
for FastAPI endpoints. Supports both PostgreSQL (production) and
SQLite (testing) via the DATABASE_URL setting.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.models import Base


def get_engine(url: str | None = None):
    """Create a SQLAlchemy engine from settings or override."""
    settings = get_settings()
    db_url = url or settings.database_url
    echo = settings.database_echo

    connect_args = {}
    if db_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(db_url, echo=echo, connect_args=connect_args)


def init_db(engine=None):
    """Create all tables. Used for development/testing."""
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(bind=engine)


_engine = None
_SessionFactory = None


def get_db_session() -> Session:
    """Create a new database session.

    This is the primary way to obtain a session. Callers are responsible
    for committing/closing the session.
    """
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine = get_engine()
        _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    return _SessionFactory()


def get_db():
    """FastAPI dependency that yields a session and auto-closes on exit."""
    session = get_db_session()
    try:
        yield session
    finally:
        session.close()


def reset_db():
    """Drop and recreate all tables. TESTING ONLY."""
    global _engine, _SessionFactory
    if _engine is None:
        _engine = get_engine()
    Base.metadata.drop_all(bind=_engine)
    Base.metadata.create_all(bind=_engine)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
