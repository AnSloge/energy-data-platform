import json
from datetime import date
from pathlib import Path

import pytest

from energy_platform.ingestion import sources
from energy_platform.ingestion.bronze import is_committed

FIXTURES = Path(__file__).parent / "fixtures"
PRICES_NO2 = (FIXTURES / "prices_NO2_2026-10-19.json").read_bytes()
OCT19 = date(2026, 10, 19)


def fake_http(monkeypatch, responses):
    """`responses` maps URL suffix → body (None = 404). Returns the list of requested URLs."""
    calls = []

    def http_get(url, missing_ok=False):
        calls.append(url)
        return next(body for suffix, body in responses.items() if url.endswith(suffix))

    monkeypatch.setattr(sources, "http_get", http_get)
    return calls


def test_ingest_prices_writes_each_area_byte_identical(tmp_path, monkeypatch):
    calls = fake_http(monkeypatch, {".json": PRICES_NO2})

    assert sources.ingest_prices(OCT19, "run-1", tmp_path) == dict.fromkeys(
        sources.AREAS, "written"
    )

    assert calls[1] == f"{sources.PRICES_URL}/2026/10-19_NO2.json"
    partition = tmp_path / "prices" / "year=2026" / "month=10" / "day=19"
    assert (partition / "NO2_2026-10-19_2026-10-19.json").read_bytes() == PRICES_NO2
    meta = json.loads((partition / "NO2_2026-10-19_2026-10-19.meta.json").read_text())
    assert meta["row_count"] == len(json.loads(PRICES_NO2)) == 24
    assert meta["url"] == calls[1]


def test_ingest_prices_rerun_makes_no_http_call(tmp_path, monkeypatch):
    fake_http(monkeypatch, {".json": PRICES_NO2})
    sources.ingest_prices(OCT19, "run-1", tmp_path)

    calls = fake_http(monkeypatch, {})
    assert sources.ingest_prices(OCT19, "run-2", tmp_path) == dict.fromkeys(
        sources.AREAS, "skipped"
    )
    assert calls == []


def test_ingest_prices_skips_areas_before_start(tmp_path, monkeypatch):
    calls = fake_http(monkeypatch, {".json": PRICES_NO2})
    assert sources.ingest_prices(date(2021, 9, 30), "run-1", tmp_path) == {"NO1": "written"}
    assert calls == [f"{sources.PRICES_URL}/2021/09-30_NO1.json"]


def test_ingest_prices_404_is_missing(tmp_path, monkeypatch):
    fake_http(monkeypatch, {"_NO2.json": None, ".json": PRICES_NO2})
    status = sources.ingest_prices(OCT19, "run-1", tmp_path)
    assert status["NO2"] == "missing"
    assert not is_committed(tmp_path, "prices", "NO2", OCT19, OCT19)
    assert not any(tmp_path.rglob("NO2_*"))


@pytest.mark.parametrize("body", [b"", b"<html>oops</html>", b"[]", b'{"error": "x"}'])
def test_ingest_prices_bad_body_fails_only_that_area(tmp_path, monkeypatch, body):
    fake_http(monkeypatch, {"_NO3.json": body, ".json": PRICES_NO2})

    status = sources.ingest_prices(OCT19, "run-1", tmp_path)

    assert status == {**dict.fromkeys(sources.AREAS, "written"), "NO3": "failed"}
    assert not any(tmp_path.rglob("NO3_*"))
