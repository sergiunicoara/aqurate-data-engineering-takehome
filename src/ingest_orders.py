from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import logging
from typing import Any, Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import Settings
from .db import DatabaseConnection

LOGGER = logging.getLogger(__name__)
BATCH_SIZE = 1000
REQUIRED_COLUMNS = frozenset({
    "order_id", "customer_id", "customer_email", "order_ts", "status", "channel", "sku",
    "product_name", "category", "qty", "unit_price", "currency", "country", "fx_reference_date",
})


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_session() -> requests.Session:
    retry = Retry(total=3, backoff_factor=0.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=("GET",))
    session = requests.Session()
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_orders(settings: Settings, session: requests.Session | None = None) -> list[dict[str, Any]]:
    settings.validate_source_credentials()
    requester = session or http_session()
    try:
        response = requester.get(
            settings.orders_source_url,
            headers={"apikey": settings.orders_source_api_key},
            params={"select": "*"},
            timeout=settings.timeout_seconds,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"Orders source request failed: {error}") from error
    payload = response.json()
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise ValueError("Orders source response must be a JSON array of objects")
    if not payload:
        raise ValueError("Orders source returned no rows")
    missing = REQUIRED_COLUMNS.difference(payload[0])
    if missing:
        raise ValueError(f"Orders source schema missing required columns: {sorted(missing)}")
    return payload


def canonical_hash(row: dict[str, Any]) -> str:
    canonical = json.dumps(row, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def as_raw_text(value: Any) -> str | None:
    return None if value is None else str(value)


def ingest_orders(connection: DatabaseConnection, rows: Iterable[dict[str, Any]]) -> tuple[int, int]:
    rows = list(rows)
    now = utc_now()
    inserted = 0
    records: list[tuple[Any, ...]] = []
    for row in rows:
        missing = REQUIRED_COLUMNS.difference(row)
        if missing:
            raise ValueError(f"Orders source row missing required columns: {sorted(missing)}")
        source_hash = canonical_hash(row)
        records.append((source_hash, json.dumps(row, sort_keys=True, ensure_ascii=False), *[as_raw_text(row[key]) for key in (
            "order_id", "customer_id", "customer_email", "order_ts", "status", "channel", "sku",
            "product_name", "category", "qty", "unit_price", "currency", "country", "fx_reference_date",
        )], now))

    statement = """INSERT INTO orders_raw (
                    source_hash, payload_json, order_id_raw, customer_id_raw, customer_email_raw,
                    order_ts_raw, status_raw, channel_raw, sku_raw, product_name_raw, category_raw,
                    qty_raw, unit_price_raw, currency_raw, country_raw, fx_reference_date_raw, source_loaded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(source_hash) DO NOTHING"""
    for start in range(0, len(records), BATCH_SIZE):
        cursor = connection.executemany(statement, records[start:start + BATCH_SIZE])
        inserted += cursor.rowcount
    LOGGER.info("raw ingestion complete", extra={"source_rows": len(rows), "new_rows": inserted})
    return len(rows), inserted
