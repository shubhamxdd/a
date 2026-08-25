"""SQLAlchemy database setup."""

from collections.abc import Generator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""


engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_anonymous_sightings_compatible() -> None:
    """Keep existing local databases compatible with anonymous recognition events."""
    if engine.dialect.name != "postgresql":
        return
    columns = {column["name"]: column for column in inspect(engine).get_columns("sightings")}
    nullable_columns = [
        name for name in ("student_id", "face_distance") if columns.get(name, {}).get("nullable") is False
    ]
    if nullable_columns:
        with engine.begin() as connection:
            for column_name in nullable_columns:
                connection.execute(text(f"ALTER TABLE sightings ALTER COLUMN {column_name} DROP NOT NULL"))


def get_db() -> Generator[Session, None, None]:
    """Provide one transaction-scoped database session per request."""
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()
