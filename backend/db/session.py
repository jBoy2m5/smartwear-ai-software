"""Database engine, sessions, and transaction boundaries."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.core.config import Settings, get_settings
from backend.db.base import Base


class Database:
    """Own the SQLAlchemy engine and provide transactional sessions."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self._prepare_sqlite_directory(database_url)
        engine_options: dict[str, object] = {"pool_pre_ping": True}
        if database_url.startswith("sqlite"):
            engine_options["connect_args"] = {"check_same_thread": False}
        if database_url in {"sqlite://", "sqlite:///:memory:"}:
            engine_options["poolclass"] = StaticPool

        self.engine = create_engine(database_url, **engine_options)
        self.session_factory = sessionmaker(
            bind=self.engine,
            class_=Session,
            autoflush=False,
            expire_on_commit=False,
        )
        if database_url.startswith("sqlite"):
            event.listen(self.engine, "connect", self._configure_sqlite)

    @staticmethod
    def _prepare_sqlite_directory(database_url: str) -> None:
        """Create the parent directory for a file-backed SQLite database."""
        url = make_url(database_url)
        if url.drivername != "sqlite" or not url.database or url.database == ":memory:":
            return
        Path(url.database).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _configure_sqlite(dbapi_connection: object, _: object) -> None:
        """Enable integrity and concurrency pragmas on SQLite connections."""
        cursor = dbapi_connection.cursor()  # type: ignore[attr-defined]
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    @contextmanager
    def transaction(self) -> Iterator[Session]:
        """Yield a session and commit or roll back it atomically."""
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def create_schema(self) -> None:
        """Create all model tables registered on the declarative base."""
        Base.metadata.create_all(self.engine)

    def dispose(self) -> None:
        """Release pooled database connections."""
        self.engine.dispose()


def build_database(settings: Settings) -> Database:
    """Construct a database from explicit settings."""
    return Database(settings.database_url)


@lru_cache(maxsize=1)
def get_database() -> Database:
    """Return the process-wide database instance."""
    return build_database(get_settings())


def get_db_session() -> Generator[Session, None, None]:
    """FastAPI dependency that owns one transaction per request."""
    with get_database().transaction() as session:
        yield session

