from __future__ import annotations

import pytest

from src.clean_orders import clean_row


def row(**changes: object) -> dict[str, object]:
    base: dict[str, object] = {
        "order_id": " ORD-1 ", "customer_id": 7, "customer_email": "x@example.com",
        "order_ts": "05/04/2026 07:29", "status": "completed", "channel": "web", "sku": "S-1",
        "product_name": "Item", "category": " electronics ", "qty": "2", "unit_price": "12.50",
        "currency": " lei ", "country": "Romania", "fx_reference_date": "2026-08-25",
    }
    base.update(changes)
    return base


def test_normalises_safe_string_variations() -> None:
    cleaned = clean_row("hash", row())
    assert cleaned.order_id == "ORD-1"
    assert cleaned.category == "Electronics"
    assert cleaned.currency == "RON"
    assert cleaned.country == "RO"
    assert str(cleaned.line_amount) == "25.00"


@pytest.mark.parametrize("changes, reason", [
    ({"unit_price": "broken"}, "invalid_unit_price"),
    ({"unit_price": "-1"}, "negative_unit_price"),
    ({"unit_price": "999999"}, "suspicious_unit_price"),
    ({"category": None}, "unsupported_category"),
    ({"status": "test"}, "excluded_status_test"),
])
def test_rejects_unusable_rows(changes: dict[str, object], reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        clean_row("hash", row(**changes))


def test_missing_customer_is_retained_with_audit_note() -> None:
    cleaned = clean_row("hash", row(customer_id=None))
    assert cleaned.customer_id is None
    assert "excluded_from_customer_spend" in cleaned.notes
