from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.storage.models import Base


@dataclass(frozen=True)
class DatabaseConfig:
    sqlite_path: Path


def build_engine(cfg: DatabaseConfig) -> Engine:
    cfg.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite+pysqlite:///{cfg.sqlite_path.as_posix()}"
    engine = create_engine(url, future=True)
    _configure_sqlite(engine)
    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def build_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def session_scope(factory: sessionmaker[Session]) -> Iterator[Session]:
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _configure_sqlite(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.execute("PRAGMA journal_mode=WAL;")
        cursor.execute("PRAGMA synchronous=NORMAL;")
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn) -> None:  # type: ignore[no-untyped-def]
        conn.execute(text("PRAGMA busy_timeout=5000;"))

