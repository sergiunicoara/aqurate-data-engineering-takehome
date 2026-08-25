from __future__ import annotations

from typing import Any

from src.db import PostgresConnection


class FakeCursor:
    def __init__(self) -> None:
        self.executed: tuple[str, list[tuple[Any, ...]]] | None = None

    def executemany(self, query: str, parameters: list[tuple[Any, ...]]) -> None:
        self.executed = (query, parameters)


class FakePsycopgConnection:
    def __init__(self) -> None:
        self.executed: tuple[str, tuple[Any, ...], bool] | None = None
        self.cursor_instance = FakeCursor()

    def execute(self, query: str, parameters: tuple[Any, ...], *, prepare: bool) -> str:
        self.executed = (query, parameters, prepare)
        return "cursor"

    def cursor(self) -> FakeCursor:
        return self.cursor_instance

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass

    def close(self) -> None:
        pass


def test_postgres_adapter_translates_project_placeholders() -> None:
    raw_connection = FakePsycopgConnection()
    connection = PostgresConnection(raw_connection)

    assert connection.execute("SELECT * FROM fx_rates WHERE rate_date = ?", ("2026-08-25",)) == "cursor"
    assert raw_connection.executed == (
        "SELECT * FROM fx_rates WHERE rate_date = %s", ("2026-08-25",), False
    )

    connection.executemany("INSERT INTO fx_rates VALUES (?, ?)", [("a", "b")])
    assert raw_connection.cursor_instance.executed == (
        "INSERT INTO fx_rates VALUES (%s, %s)", [("a", "b")]
    )
