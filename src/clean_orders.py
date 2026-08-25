from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import sqlite3
from typing import Any

from .ingest_orders import utc_now

CURRENCY_ALIASES = {"EURO": "EUR", "€": "EUR", "LEI": "RON"}
COUNTRY_ALIASES = {"ROMANIA": "RO", "GERMANY": "DE", "HUNGARY": "HU", "BULGARIA": "BG"}
CATEGORY_ALIASES = {"books": "Books", "electronics": "Electronics", "beauty": "Beauty", "fashion": "Fashion", "sports": "Sports", "home & kitchen": "Home & Kitchen"}
VALID_CURRENCIES = frozenset({"EUR", "RON"})
VALID_CATEGORIES = frozenset(CATEGORY_ALIASES.values())
# The observed legitimate maximum is 207.87; 13 source lines use 999999, a
# sentinel-sized value that would dominate every analytical output.
MAX_REASONABLE_UNIT_PRICE = Decimal("10000")


@dataclass(frozen=True)
class CleanedOrder:
    source_hash: str
    order_id: str
    customer_id: int | None
    customer_email: str | None
    order_ts: str
    status: str
    channel: str | None
    sku: str | None
    product_name: str | None
    category: str
    qty: int
    unit_price: Decimal
    line_amount: Decimal
    currency: str
    country: str
    fx_reference_date: str
    notes: str


def normalise_text(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def parse_decimal(value: Any, field: str) -> Decimal:
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as error:
        raise ValueError(f"invalid_{field}") from error
    if not parsed.is_finite():
        raise ValueError(f"invalid_{field}")
    return parsed


def parse_order_ts(value: Any) -> str:
    raw = normalise_text(value)
    if not raw:
        raise ValueError("missing_order_ts")
    if raw.isdigit():
        try:
            return datetime.fromtimestamp(int(raw), tz=timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
        except (OverflowError, OSError, ValueError) as error:
            raise ValueError("invalid_order_ts") from error
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw, pattern).isoformat(timespec="seconds")
        except ValueError:
            continue
    raise ValueError("invalid_order_ts")


def parse_date(value: Any) -> str:
    raw = normalise_text(value)
    try:
        return date.fromisoformat(raw or "").isoformat()
    except ValueError as error:
        raise ValueError("invalid_fx_reference_date") from error


def clean_row(source_hash: str, row: dict[str, Any]) -> CleanedOrder:
    notes: list[str] = []
    order_id = normalise_text(row["order_id"])
    if not order_id:
        raise ValueError("missing_order_id")
    if str(row["order_id"]) != order_id:
        notes.append("trimmed_order_id")
    status = (normalise_text(row["status"]) or "").lower()
    if status != "completed":
        raise ValueError(f"excluded_status_{status or 'missing'}")
    customer_raw = normalise_text(row["customer_id"])
    try:
        customer_id = int(customer_raw) if customer_raw is not None else None
    except ValueError as error:
        raise ValueError("invalid_customer_id") from error
    if customer_id is not None and customer_id <= 0:
        raise ValueError("invalid_customer_id")
    if customer_id is None:
        notes.append("missing_customer_id_excluded_from_customer_spend")
    qty_decimal = parse_decimal(row["qty"], "qty")
    if qty_decimal != qty_decimal.to_integral_value() or qty_decimal < 0:
        raise ValueError("invalid_qty")
    unit_price = parse_decimal(row["unit_price"], "unit_price")
    if unit_price < 0:
        raise ValueError("negative_unit_price")
    if unit_price >= MAX_REASONABLE_UNIT_PRICE:
        raise ValueError("suspicious_unit_price")
    if qty_decimal == 0 or unit_price == 0:
        notes.append("zero_value_line_retained")
    currency_raw = normalise_text(row["currency"])
    currency = CURRENCY_ALIASES.get((currency_raw or "").upper(), (currency_raw or "").upper())
    if currency not in VALID_CURRENCIES:
        raise ValueError("unsupported_currency")
    if currency != (currency_raw or "").upper():
        notes.append("normalised_currency_alias")
    country_raw = normalise_text(row["country"])
    country = COUNTRY_ALIASES.get((country_raw or "").upper(), (country_raw or "").upper())
    if country not in {"RO", "DE", "HU", "BG"}:
        raise ValueError("unsupported_country")
    if country != (country_raw or "").upper():
        notes.append("normalised_country_alias")
    category_raw = normalise_text(row["category"])
    category = CATEGORY_ALIASES.get((category_raw or "").lower())
    if category is None:
        raise ValueError("unsupported_category")
    if category != category_raw:
        notes.append("normalised_category")
    return CleanedOrder(
        source_hash=source_hash, order_id=order_id, customer_id=customer_id,
        customer_email=normalise_text(row["customer_email"]), order_ts=parse_order_ts(row["order_ts"]),
        status=status, channel=normalise_text(row["channel"]), sku=normalise_text(row["sku"]),
        product_name=normalise_text(row["product_name"]), category=category, qty=int(qty_decimal),
        unit_price=unit_price, line_amount=qty_decimal * unit_price, currency=currency, country=country,
        fx_reference_date=parse_date(row["fx_reference_date"]), notes=";".join(notes) or "clean",
    )


def rebuild_clean_orders(connection: sqlite3.Connection) -> tuple[int, int]:
    raw_rows = connection.execute("SELECT source_hash, payload_json FROM orders_raw ORDER BY source_hash").fetchall()
    now = utc_now()
    clean: list[CleanedOrder] = []
    rejected: list[tuple[str, str, str]] = []
    for raw in raw_rows:
        try:
            clean.append(clean_row(raw["source_hash"], json.loads(raw["payload_json"])))
        except (KeyError, TypeError, ValueError) as error:
            rejected.append((raw["source_hash"], str(error), now))
    # These materialisations reference clean rows. Clear them within the same
    # transaction before rebuilding clean data; transforms repopulate them later.
    connection.execute("DELETE FROM country_category_revenue")
    connection.execute("DELETE FROM customer_spend_eur")
    connection.execute("DELETE FROM order_values_eur")
    connection.execute("DELETE FROM orders_clean")
    connection.execute("DELETE FROM rejected_orders")
    connection.executemany(
        """INSERT INTO orders_clean VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [(item.source_hash, item.order_id, item.customer_id, item.customer_email, item.order_ts, item.status,
          item.channel, item.sku, item.product_name, item.category, item.qty, str(item.unit_price),
          str(item.line_amount), item.currency, item.country, item.fx_reference_date, item.notes, now) for item in clean],
    )
    connection.executemany("INSERT INTO rejected_orders VALUES (?, ?, ?)", rejected)
    return len(clean), len(rejected)
