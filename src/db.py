from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
from typing import Iterator


SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def connect(database_path: Path) -> sqlite3.Connection:
    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    return connection


def initialise(connection: sqlite3.Connection) -> None:
    connection.executescript((SQL_DIR / "001_schema.sql").read_text(encoding="utf-8"))
    connection.commit()


@contextmanager
def transaction(connection: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    try:
        with connection:
            yield connection
    except sqlite3.Error:
        connection.rollback()
        raise

