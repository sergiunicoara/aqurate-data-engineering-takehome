from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import logging
import sqlite3

import requests

from .config import Settings
from .ingest_orders import http_session, utc_now

LOGGER = logging.getLogger(__name__)


def required_fx_currencies(connection: sqlite3.Connection) -> list[str]:
    return [row[0] for row in connection.execute("SELECT DISTINCT currency FROM orders_clean WHERE currency <> 'EUR' ORDER BY currency")]


def required_fx_date_bounds(connection: sqlite3.Connection) -> tuple[date, date] | None:
    row = connection.execute("SELECT MIN(fx_reference_date), MAX(fx_reference_date) FROM orders_clean WHERE currency <> 'EUR'").fetchone()
    return None if row[0] is None else (date.fromisoformat(row[0]), date.fromisoformat(row[1]))


def fetch_and_upsert_fx(connection: sqlite3.Connection, settings: Settings, session: requests.Session | None = None, today: date | None = None) -> int:
    bounds = required_fx_date_bounds(connection)
    currencies = required_fx_currencies(connection)
    if not bounds or not currencies:
        return 0
    earliest_reference, latest_reference = bounds
    available_through = min(latest_reference, today or date.today())
    if available_through < earliest_reference:
        return 0
    requester = session or http_session()
    added = 0
    for currency in currencies:
        cached = connection.execute(
            "SELECT MAX(rate_date) FROM fx_rates WHERE base_currency = ? AND quote_currency = 'EUR'", (currency,)
        ).fetchone()[0]
        # Re-request the last observed date so a previously unavailable current-date rate can appear.
        start = earliest_reference if cached is None else max(earliest_reference, date.fromisoformat(cached))
        if start > available_through:
            continue
        url = f"{settings.fx_api_url}/{start.isoformat()}..{available_through.isoformat()}"
        try:
            response = requester.get(url, params={"base": currency, "symbols": "EUR"}, timeout=settings.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as error:
            raise RuntimeError(f"FX request failed for {currency}: {error}") from error
        rates = payload.get("rates", {})
        if not isinstance(rates, dict):
            raise ValueError(f"Unexpected FX response for {currency}")
        now = utc_now()
        for rate_date, values in rates.items():
            if "EUR" not in values:
                continue
            existed = connection.execute(
                "SELECT 1 FROM fx_rates WHERE rate_date = ? AND base_currency = ? AND quote_currency = 'EUR'",
                (rate_date, currency),
            ).fetchone()
            cursor = connection.execute(
                """INSERT INTO fx_rates(rate_date, base_currency, quote_currency, rate, fetched_at)
                   VALUES (?, ?, 'EUR', ?, ?)
                   ON CONFLICT(rate_date, base_currency, quote_currency) DO UPDATE SET rate = excluded.rate, fetched_at = excluded.fetched_at""",
                (rate_date, currency, str(values["EUR"]), now),
            )
            if existed is None:
                added += 1
        LOGGER.info("fx fetched", extra={"currency": currency, "from": str(start), "to": str(available_through)})
    return added
