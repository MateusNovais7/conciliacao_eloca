from __future__ import annotations

from collections.abc import Generator

from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.database.session import make_engine

_engine = None
_SessionLocal: sessionmaker | None = None


def _get_session_factory() -> sessionmaker:
    global _engine, _SessionLocal
    if _SessionLocal is None:
        settings = get_settings()
        _engine = make_engine(settings.database_url)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _SessionLocal


def override_session_factory(factory: sessionmaker) -> None:
    """Usado pelos testes para injetar um SQLite em memória em vez do
    Postgres real."""
    global _SessionLocal
    _SessionLocal = factory


def get_session() -> Generator[Session, None, None]:
    factory = _get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
