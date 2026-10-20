"""CLI: python -m energy_platform.ingestion backfill|incremental --source prices [--start --end]."""

import argparse
import logging
import sys
import uuid
from collections import Counter
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from energy_platform.ingestion import sources
from energy_platform.ingestion.bronze import BRONZE_ROOT

log = logging.getLogger(__name__)

OSLO = ZoneInfo("Europe/Oslo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m energy_platform.ingestion")
    parser.add_argument("mode", choices=["backfill", "incremental"])
    parser.add_argument("--source", choices=["prices"], default="prices")
    parser.add_argument("--start", type=date.fromisoformat, help="inclusive ISO date")
    parser.add_argument("--end", type=date.fromisoformat, help="inclusive ISO date")
    parser.add_argument("--root", type=Path, default=BRONZE_ROOT)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    today = sources._now().astimezone(OSLO).date()  # price days are Oslo delivery days
    if args.mode == "backfill":
        start, end = min(sources.PRICE_START.values()), today
    else:
        start, end = today - timedelta(days=7), today + timedelta(days=1)
    start, end = args.start or start, args.end or end
    if start > end:
        parser.error(f"--start {start} is after --end {end}")

    run_id = str(uuid.uuid4())
    log.info("%s %s %s..%s run_id=%s", args.mode, args.source, start, end, run_id)
    counts = Counter()
    for n in range((end - start).days + 1):
        day = start + timedelta(days=n)
        try:
            status = sources.ingest_prices(day, run_id, args.root)
        except Exception:
            log.exception("prices %s failed", day)
            counts["failed"] += 1
            continue
        log.info("prices %s %s", day, status)
        counts.update(status.values())

    print(" ".join(f"{k}={counts[k]}" for k in ("written", "skipped", "missing", "failed")))
    return 1 if counts["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
