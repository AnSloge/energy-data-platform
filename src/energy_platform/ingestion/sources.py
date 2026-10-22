"""One ingest_* function per source. Each call covers exactly one request's range per name."""

import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path

from energy_platform.ingestion.bronze import BRONZE_ROOT, http_get, is_committed, write_bronze

log = logging.getLogger(__name__)

AREAS = ("NO1", "NO2", "NO3", "NO4", "NO5")
PRICES_URL = "https://www.hvakosterstrommen.no/api/v1/prices"
PRICE_START = {
    "NO1": date(2021, 9, 7),
    "NO2": date(2021, 10, 1),
    "NO3": date(2021, 10, 1),
    "NO4": date(2021, 11, 1),
    "NO5": date(2021, 10, 1),
}


def _now() -> datetime:
    """The clock, in one place so tests can monkeypatch it."""
    return datetime.now(UTC)


def ingest_prices(day: date, run_id: str, root: Path = BRONZE_ROOT) -> dict[str, str]:
    """Fetch prices for one Oslo delivery day. Returns {area: written | skipped | missing | failed}.

    Areas before their PRICE_START are left out. Any error for an area (HTTP, an empty or
    non-list body) is logged and reported as failed, and the other areas still run.
    """
    status = {}
    for area in AREAS:
        if day < PRICE_START[area]:
            continue
        if is_committed(root, "prices", area, day, day):
            status[area] = "skipped"
            continue
        url = f"{PRICES_URL}/{day:%Y}/{day:%m-%d}_{area}.json"
        try:
            body = http_get(url, missing_ok=True)  # 404 = not published yet
            if body is None:
                log.info("prices %s %s not published", day, area)
                status[area] = "missing"
                continue
            prices = json.loads(body)
            if not isinstance(prices, list):  # bad payload, not a caller bug, hence ValueError
                raise ValueError(f"prices {day} {area}: expected a JSON list")  # noqa: TRY004
            write_bronze(root, "prices", area, day, day, body, run_id, url, len(prices))
            status[area] = "written"
        except Exception:
            log.exception("prices %s %s failed", day, area)
            status[area] = "failed"
    return status
