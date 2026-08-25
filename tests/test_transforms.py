from __future__ import annotations

from src.transforms import refresh_outputs


def insert_value(connection, source_hash: str, customer_id: int, country: str, category: str, amount: float) -> None:
    connection.execute(
        """INSERT INTO orders_clean VALUES (?, ?, ?, 'x@example.com', '2026-01-01T00:00:00', 'completed',
        'web', 'sku', 'item', ?, 1, ?, ?, 'EUR', ?, '2026-08-25', 'clean', 'now')""",
        (source_hash, source_hash, customer_id, category, amount, amount, country),
    )


def test_customer_totals_threshold_filter_and_rank(database) -> None:
    insert_value(database, "a", 1, "RO", "Books", 25_000)
    insert_value(database, "b", 1, "RO", "Electronics", 20_000)
    insert_value(database, "c", 2, "DE", "Books", 40_000)
    insert_value(database, "d", 3, "HU", "Fashion", 99_999)
    refresh_outputs(database)
    assert tuple(database.execute("SELECT total_spend_eur, order_count FROM customer_spend_eur WHERE customer_id = 1").fetchone()) == (45000, 2)
    countries = database.execute("SELECT revenue_rank, country, total_revenue_eur FROM country_category_revenue").fetchall()
    assert [tuple(item) for item in countries] == [(1, "RO", 45000)]

