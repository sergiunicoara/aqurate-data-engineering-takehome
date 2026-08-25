from __future__ import annotations

from collections import Counter
from datetime import date
from typing import Any

from .clean_orders import clean_row
from .ingest_orders import canonical_hash


def build_report(rows: list[dict[str, Any]], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    columns = sorted({key for row in rows for key in row})
    null_counts = {column: sum(row.get(column) is None for row in rows) for column in columns}
    hashes = [canonical_hash(row) for row in rows]
    order_ids = [str(row.get("order_id")) for row in rows if row.get("order_id") is not None]
    reasons: Counter[str] = Counter()
    future_fx = 0
    for row in rows:
        try:
            clean_row(canonical_hash(row), row)
        except ValueError as error:
            reasons[str(error)] += 1
        raw_date = row.get("fx_reference_date")
        try:
            if date.fromisoformat(str(raw_date).strip()) > today:
                future_fx += 1
        except (TypeError, ValueError):
            pass
    return {
        "rows": len(rows), "columns": columns, "null_counts": null_counts,
        "exact_duplicate_rows": len(rows) - len(set(hashes)),
        "duplicate_order_id_rows": len(order_ids) - len(set(item.strip() for item in order_ids)),
        "currencies": sorted({str(row.get("currency")) for row in rows}),
        "categories": sorted({str(row.get("category")) for row in rows}),
        "countries": sorted({str(row.get("country")) for row in rows}),
        "future_fx_reference_dates": future_fx,
        "cleaning_rejections": dict(sorted(reasons.items())),
    }

