from __future__ import annotations

from pathlib import Path

from .db import DatabaseConnection, execute_script

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"


def refresh_outputs(connection: DatabaseConnection) -> tuple[int, int, int]:
    execute_script(connection, SQL_DIR / "003_customer_spend_eur.sql")
    execute_script(connection, SQL_DIR / "004_country_category_revenue.sql")
    missing_fx = connection.execute(
        "SELECT COUNT(*) AS missing_fx_orders FROM order_values_eur WHERE original_currency <> 'EUR' AND amount_eur IS NULL"
    ).fetchone()["missing_fx_orders"]
    customers = connection.execute("SELECT COUNT(*) AS customer_count FROM customer_spend_eur").fetchone()["customer_count"]
    countries = connection.execute("SELECT COUNT(*) AS country_count FROM country_category_revenue").fetchone()["country_count"]
    return missing_fx, customers, countries


def validate_outputs(connection: DatabaseConnection) -> None:
    checks = {
        "raw data is non-empty": "SELECT COUNT(*) > 0 AS check_passed FROM orders_raw",
        "clean data is non-empty": "SELECT COUNT(*) > 0 AS check_passed FROM orders_clean",
        "customer output is non-empty": "SELECT COUNT(*) > 0 AS check_passed FROM customer_spend_eur",
        "customer IDs are complete": "SELECT COUNT(*) = 0 AS check_passed FROM customer_spend_eur WHERE customer_id IS NULL",
        "customer totals are complete": "SELECT COUNT(*) = 0 AS check_passed FROM customer_spend_eur WHERE total_spend_eur IS NULL",
        "country revenue threshold is strict": "SELECT COUNT(*) = 0 AS check_passed FROM country_category_revenue WHERE total_revenue_eur <= 40000",
        "country rankings descend": """SELECT COUNT(*) = 0 AS check_passed FROM (
            SELECT total_revenue_eur, LAG(total_revenue_eur) OVER (ORDER BY revenue_rank) AS previous
            FROM country_category_revenue
        ) WHERE previous IS NOT NULL AND total_revenue_eur > previous""",
    }
    failures = [name for name, query in checks.items() if not connection.execute(query).fetchone()["check_passed"]]
    if failures:
        raise ValueError("Validation failed: " + ", ".join(failures))
