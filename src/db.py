from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Any, Iterator, Protocol


SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


class DatabaseConnection(Protocol):
    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> Any: ...
    def executemany(self, query: str, parameters: list[tuple[Any, ...]]) -> Any: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


def postgres_query(query: str) -> str:
    """Convert this project's DB-API qmark placeholders for psycopg."""
    return query.replace("?", "%s")


class PostgresConnection:
    """Small compatibility adapter around psycopg for the shared pipeline SQL."""

    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def execute(self, query: str, parameters: tuple[Any, ...] = ()) -> Any:
        return self.connection.execute(postgres_query(query), parameters, prepare=False)

    def executemany(self, query: str, parameters: list[tuple[Any, ...]]) -> Any:
        cursor = self.connection.cursor()
        cursor.executemany(postgres_query(query), parameters, prepare=False)
        return cursor

    def commit(self) -> None:
        self.connection.commit()

    def rollback(self) -> None:
        self.connection.rollback()

    def close(self) -> None:
        self.connection.close()


def connect(database_path: Path, database_url: str | None = None) -> DatabaseConnection:
    if database_url:
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as error:
            raise RuntimeError("PostgreSQL support requires psycopg; install requirements.txt") from error
        return PostgresConnection(psycopg.connect(database_url, row_factory=dict_row))

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def execute_script(connection: DatabaseConnection, path: Path) -> None:
    script = path.read_text(encoding="utf-8")
    if isinstance(connection, sqlite3.Connection):
        connection.executescript(script)
    else:
        connection.execute(script)


def initialise(connection: DatabaseConnection) -> None:
    execute_script(connection, SQL_DIR / "001_schema.sql")
    connection.commit()


@contextmanager
def transaction(connection: DatabaseConnection) -> Iterator[DatabaseConnection]:
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
