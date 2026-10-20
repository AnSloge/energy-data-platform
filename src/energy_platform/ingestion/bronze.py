"""Bronze lake: one raw API response per file, committed by a meta sidecar written last."""

import json
import os
from datetime import UTC, date, datetime
from pathlib import Path

BRONZE_ROOT = Path("data/bronze")


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
