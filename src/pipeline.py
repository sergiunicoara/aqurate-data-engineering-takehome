from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
import sys
import time
import uuid

from .clean_orders import rebuild_clean_orders
from .config import Settings
from .db import connect, initialise, transaction
from .fx import fetch_and_upsert_fx
from .ingest_orders import fetch_orders, ingest_orders
from .quality_report import build_report
from .transforms import refresh_outputs, validate_outputs


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def run(settings: Settings, report_only: bool = False) -> dict[str, int]:
    started = time.monotonic()
    rows = fetch_orders(settings)
    if report_only:
        print(json.dumps(build_report(rows), indent=2))
        return {"raw_rows": len(rows)}
    settings.validate_database_configuration()
    connection = connect(settings.database_path, settings.database_url)
    initialise(connection)
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    connection.execute("INSERT INTO pipeline_runs(run_id, started_at, status) VALUES (?, ?, 'running')", (run_id, now))
    connection.commit()
    try:
        with transaction(connection):
            raw_rows, _ = ingest_orders(connection, rows)
            clean_rows, rejected_rows = rebuild_clean_orders(connection)
        with transaction(connection):
            fx_added = fetch_and_upsert_fx(connection, settings)
        with transaction(connection):
            missing_fx, customer_rows, country_rows = refresh_outputs(connection)
            validate_outputs(connection)
            connection.execute(
                """UPDATE pipeline_runs SET completed_at = ?, status = 'succeeded', raw_rows = ?, clean_rows = ?,
                   rejected_rows = ?, fx_rows_added = ?, missing_fx_orders = ? WHERE run_id = ?""",
                (datetime.now(timezone.utc).isoformat(timespec="seconds"), raw_rows, clean_rows, rejected_rows, fx_added, missing_fx, run_id),
            )
        result = {"raw_rows": raw_rows, "clean_rows": clean_rows, "rejected_rows": rejected_rows,
                  "fx_rows_added": fx_added, "missing_fx_orders": missing_fx, "customer_rows": customer_rows,
                  "country_rows": country_rows}
        logging.getLogger(__name__).info("pipeline succeeded in %.2fs: %s", time.monotonic() - started, result)
        return result
    except Exception as error:
        connection.execute(
            "UPDATE pipeline_runs SET completed_at = ?, status = 'failed', error_message = ? WHERE run_id = ?",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"), str(error), run_id),
        )
        connection.commit()
        logging.exception("pipeline failed after %.2fs", time.monotonic() - started)
        raise
    finally:
        connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Aqurate orders pipeline")
    parser.add_argument("--data-quality-report", action="store_true", help="Fetch source and print a compact report")
    args = parser.parse_args()
    configure_logging()
    try:
        run(Settings.from_environment(), report_only=args.data_quality_report)
    except Exception as error:
        logging.getLogger(__name__).error("Pipeline failed: %s", error)
        return 1
    return 0
