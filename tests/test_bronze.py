import json
from datetime import UTC, date, datetime

import pytest

from energy_platform.ingestion import bronze
from energy_platform.ingestion.bronze import is_committed, write_bronze

SEP1, SEP30 = date(2026, 9, 1), date(2026, 9, 30)
BODY = b'{"hourly": {"time": ["2026-09-01T00:00"]}}'
URL = "https://example.test/archive?start_date=2026-09-01"


def write(root, body=BODY, start=SEP1, end=SEP30, rows=720):
    return write_bronze(root, "weather_archive", "NO2", start, end, body, "run-1", URL, rows)


def test_layout_body_and_meta(tmp_path):
    path = write(tmp_path)

    partition = tmp_path / "weather_archive" / "year=2026" / "month=09" / "day=01"
    assert path == partition / "NO2_2026-09-01_2026-09-30.json"
    assert path.read_bytes() == BODY
    meta = json.loads((partition / "NO2_2026-09-01_2026-09-30.meta.json").read_text())
    ingested_at = datetime.fromisoformat(meta.pop("ingested_at"))
    assert ingested_at.utcoffset() == UTC.utcoffset(None)
    assert meta == {
        "run_id": "run-1",
        "source": "weather_archive",
        "range_start": "2026-09-01",
        "range_end": "2026-09-30",
        "row_count": 720,
        "url": URL,
    }
    assert is_committed(tmp_path, "weather_archive", "NO2", SEP1, SEP30)


def test_ranges_with_same_start_dont_collide(tmp_path):
    month = write(tmp_path, b"[1]", end=SEP30)
    day = write(tmp_path, b"[2]", end=SEP1)
    assert month.parent == day.parent
    assert (month.read_bytes(), day.read_bytes()) == (b"[1]", b"[2]")


def test_committed_file_is_never_overwritten(tmp_path):
    path = write(tmp_path)
    with pytest.raises(FileExistsError):
        write(tmp_path, b"[]")
    assert path.read_bytes() == BODY


def test_crash_before_meta_leaves_uncommitted_file_that_retry_replaces(tmp_path, monkeypatch):
    real_replace = bronze.os.replace

    def crash_on_meta(src, dst):
        if str(dst).endswith(".meta.json"):
            raise OSError("simulated crash")
        real_replace(src, dst)

    monkeypatch.setattr(bronze.os, "replace", crash_on_meta)
    with pytest.raises(OSError):
        write(tmp_path, b"old")
    assert not is_committed(tmp_path, "weather_archive", "NO2", SEP1, SEP30)

    monkeypatch.setattr(bronze.os, "replace", real_replace)
    path = write(tmp_path, b"new")
    assert path.read_bytes() == b"new"
    assert is_committed(tmp_path, "weather_archive", "NO2", SEP1, SEP30)


def test_empty_payload_is_not_written(tmp_path):
    with pytest.raises(ValueError):
        write(tmp_path, rows=0)
    assert not any(tmp_path.rglob("*.json"))
