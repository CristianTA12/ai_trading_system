"""Conexiones a base de datos y servicios externos."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import redis
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import settings
from src.utils.logging import get_logger

logger = get_logger(__name__)

# === Database (TimescaleDB) ===

_engine = None
_SessionFactory = None


def get_engine():
    """Obtener engine de SQLAlchemy (singleton)."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            settings.database.url,
            pool_size=settings.database.pool_size,
            max_overflow=settings.database.max_overflow,
            pool_pre_ping=True,
        )
        logger.info("database_engine_created", url=settings.database.url.split("@")[-1])
    return _engine


def get_session_factory() -> sessionmaker:
    """Obtener factory de sesiones (singleton)."""
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """Context manager para sesiones de base de datos.

    Uso:
        with get_db_session() as session:
            session.execute(...)
    """
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# === Redis ===

_redis_client = None


def get_redis() -> redis.Redis:
    """Obtener cliente de Redis (singleton)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.redis.url,
            decode_responses=True,
        )
        logger.info("redis_client_created", url=settings.redis.url)
    return _redis_client
