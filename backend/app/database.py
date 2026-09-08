"""Database setup.

The app runs on a single SQLite file by default (``backend/k12_ai.db``). The
data changes roughly monthly and is read far more than it is written, so a
file that can be copied, diffed, and backed up beats a database server. Set
DATABASE_URL to point elsewhere (any SQLAlchemy URL works).
"""
import os
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = BACKEND_DIR / "k12_ai.db"


class Settings(BaseSettings):
    database_url: str = f"sqlite:///{DEFAULT_DB_PATH}"
    environment: str = "development"
    debug: bool = False
    legiscan_api_key: str = ""

    model_config = SettingsConfigDict(env_file=str(BACKEND_DIR / ".env"), case_sensitive=False, extra="ignore")


settings = Settings()


def make_engine(url: str):
    is_sqlite = url.startswith("sqlite")
    engine = create_engine(
        url,
        echo=settings.debug,
        pool_pre_ping=not is_sqlite,
        connect_args={"check_same_thread": False} if is_sqlite else {},
    )
    if is_sqlite:
        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _record):
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA foreign_keys=ON")
            cur.execute("PRAGMA journal_mode=WAL")
            cur.close()
    return engine


engine = make_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db(bind=None):
    """Create any missing tables. Safe to call repeatedly."""
    from app import models  # noqa: F401  (register models)
    Base.metadata.create_all(bind=bind or engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
