"""Bronze lake: one raw API response per file, committed by a meta sidecar written last."""

import http.client
import json
import logging
import os
import time
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

BRONZE_ROOT = Path("data/bronze")
USER_AGENT = "energy-data-platform/0.1 (+https://github.com/AnSloge/energy-data-platform)"

log = logging.getLogger(__name__)


def http_get(url: str, missing_ok: bool = False) -> bytes | None:
    """GET `url`, retrying 5xx, 429, timeouts and connection errors after 1, 2 and 4 s.

    A 404 returns None when `missing_ok`; any other 4xx raises at once.
    """
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for delay in (1, 2, 4, None):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except urllib.error.HTTPError as e:
            if e.code == 404 and missing_ok:
                return None
            if delay is None or (e.code < 500 and e.code != 429):
                raise
        # HTTPException covers a body cut off mid-read (IncompleteRead)
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, ConnectionError):
            if delay is None:
                raise
        log.warning("GET %s failed, retrying in %d s", url, delay)
        time.sleep(delay)


def _paths(root: Path, source: str, name: str, start: date, end: date) -> tuple[Path, Path]:
    partition = root / source / f"year={start:%Y}" / f"month={start:%m}" / f"day={start:%d}"
    stem = f"{name}_{start.isoformat()}_{end.isoformat()}"
    return partition / f"{stem}.json", partition / f"{stem}.meta.json"


def _atomic_write(path: Path, data: bytes) -> None:
    # shortcut: no fsync, so a power cut can lose the last write; add it if this leaves a laptop
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def is_committed(root: Path, source: str, name: str, start: date, end: date) -> bool:
    return _paths(root, source, name, start, end)[1].exists()


def write_bronze(
    root: Path,
    source: str,
    name: str,
    start: date,
    end: date,
    body: bytes,
    run_id: str,
    url: str,
    rows: int,
) -> Path:
    """Store `body` unchanged. A data file without meta is incomplete and gets replaced."""
    if rows <= 0:
        raise ValueError(f"{source} {name} {start}..{end}: empty payload, not written")
    data_path, meta_path = _paths(root, source, name, start, end)
    if meta_path.exists():
        raise FileExistsError(f"Bronze is append-only: {data_path} is already committed")
    data_path.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write(data_path, body)
    meta = {
        "run_id": run_id,
        "ingested_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": source,
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
        "row_count": rows,
        "url": url,
    }
    _atomic_write(meta_path, json.dumps(meta, indent=2).encode())
    return data_path
