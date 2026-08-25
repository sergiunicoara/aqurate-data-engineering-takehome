from __future__ import annotations

from pathlib import Path
import sqlite3

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def refresh_outputs(connection: sqlite3.Connection) -> tuple[int, int, int]:
    connection.executescript((SQL_DIR / "003_customer_spend_eur.sql").read_text(encoding="utf-8"))
    connection.executescript((SQL_DIR / "004_country_category_revenue.sql").read_text(encoding="utf-8"))
    missing_fx = connection.execute(
        "SELECT COUNT(*) FROM order_values_eur WHERE original_currency <> 'EUR' AND amount_eur IS NULL"
    ).fetchone()[0]
    customers = connection.execute("SELECT COUNT(*) FROM customer_spend_eur").fetchone()[0]
    countries = connection.execute("SELECT COUNT(*) FROM country_category_revenue").fetchone()[0]
    return missing_fx, customers, countries


def validate_outputs(connection: sqlite3.Connection) -> None:
    checks = {
        "raw data is non-empty": "SELECT COUNT(*) > 0 FROM orders_raw",
        "clean data is non-empty": "SELECT COUNT(*) > 0 FROM orders_clean",
        "customer output is non-empty": "SELECT COUNT(*) > 0 FROM customer_spend_eur",
        "customer IDs are complete": "SELECT COUNT(*) = 0 FROM customer_spend_eur WHERE customer_id IS NULL",
        "customer totals are complete": "SELECT COUNT(*) = 0 FROM customer_spend_eur WHERE total_spend_eur IS NULL",
        "country revenue threshold is strict": "SELECT COUNT(*) = 0 FROM country_category_revenue WHERE total_revenue_eur <= 40000",
        "country rankings descend": """SELECT COUNT(*) = 0 FROM (
            SELECT total_revenue_eur, LAG(total_revenue_eur) OVER (ORDER BY revenue_rank) AS previous
            FROM country_category_revenue
        ) WHERE previous IS NOT NULL AND total_revenue_eur > previous""",
    }
    failures = [name for name, query in checks.items() if not connection.execute(query).fetchone()[0]]
    if failures:
        raise ValueError("Validation failed: " + ", ".join(failures))

