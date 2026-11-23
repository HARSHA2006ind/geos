"""SQLAlchemy database engine, session factory, and PostGIS availability check."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.app.config import get_settings


class Base(DeclarativeBase):
    pass


def build_engine(database_url: str | None = None):
    url = database_url or get_settings().database_url
    if url.startswith("sqlite"):
        return create_engine(
            url,
            pool_pre_ping=True,
            future=True,
            connect_args={"check_same_thread": False},
        )
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=1800,
        future=True,
    )


_engine = build_engine()
SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False, class_=Session)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_database_health(engine=None) -> dict[str, object]:
    eng = engine or _engine
    dialect = eng.dialect.name
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
            postgis_version = None
            if dialect == "postgresql":
                try:
                    postgis_version = conn.execute(text("SELECT PostGIS_Version()")).scalar()
                except Exception:
                    postgis_version = None
        return {
            "connected": True,
            "dialect": dialect,
            "postgis_version": postgis_version,
        }
    except Exception as exc:
        return {
            "connected": False,
            "dialect": dialect,
            "postgis_version": None,
            "error": type(exc).__name__,
        }
