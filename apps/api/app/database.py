"""SQLAlchemy database setup."""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_sighting_student_nullable() -> None:
    """Keep existing local databases compatible with anonymous recognition events."""
    if engine.dialect.name != "postgresql":
        return
    columns = {column["name"]: column for column in inspect(engine).get_columns("sightings")}
    if columns.get("student_id", {}).get("nullable") is False:
        with engine.begin() as connection:
            connection.execute(text("ALTER TABLE sightings ALTER COLUMN student_id DROP NOT NULL"))


def get_db() -> Generator[Session, None, None]:
    """Provide one transaction-scoped database session per request."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
