from __future__ import annotations

from src.transforms import refresh_outputs


def insert_clean(connection, source_hash: str, currency: str, reference: str) -> None:
    connection.execute(
        """INSERT INTO orders_clean VALUES (?, 'order', 1, 'x@example.com', '2026-01-01T00:00:00', 'completed',
        'web', 'sku', 'item', 'Books', 1, 100, 100, ?, 'RO', ?, 'clean', '2026-01-01T00:00:00')""",
        (source_hash, currency, reference),
    )


def test_uses_exact_and_latest_prior_rate(database) -> None:
    insert_clean(database, "exact", "RON", "2026-08-25")
    insert_clean(database, "weekend", "RON", "2026-08-30")
    database.executemany(
        "INSERT INTO fx_rates VALUES (?, 'RON', 'EUR', ?, '2026-08-25T00:00:00')",
        [("2026-08-25", 0.2), ("2026-08-28", 0.25)],
    )
    refresh_outputs(database)
    values = {row["source_hash"]: row for row in database.execute("SELECT * FROM order_values_eur")}
    assert values["exact"]["fx_rate_date_used"] == "2026-08-25"
    assert values["exact"]["amount_eur"] == 20
    assert values["weekend"]["fx_rate_date_used"] == "2026-08-28"
    assert values["weekend"]["amount_eur"] == 25


def test_future_reference_does_not_look_ahead(database) -> None:
    insert_clean(database, "future", "RON", "2026-09-10")
    database.execute("INSERT INTO fx_rates VALUES ('2026-08-25', 'RON', 'EUR', 0.2, 'now')")
    refresh_outputs(database)
    value = database.execute("SELECT fx_rate_date_used, amount_eur FROM order_values_eur").fetchone()
    assert tuple(value) == ("2026-08-25", 20)


def test_eur_does_not_require_external_rate(database) -> None:
    insert_clean(database, "eur", "EUR", "2026-09-10")
    refresh_outputs(database)
    value = database.execute("SELECT fx_rate_used, amount_eur FROM order_values_eur").fetchone()
    assert tuple(value) == (1, 100)

