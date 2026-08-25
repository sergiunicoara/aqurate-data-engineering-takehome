from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from src.db import initialise


@pytest.fixture
def database(tmp_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(tmp_path / "test.db")
    connection.row_factory = sqlite3.Row
    initialise(connection)
    yield connection
    connection.close()

