import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from energy_platform.ingestion import __main__ as cli
from energy_platform.ingestion import sources

# 23:30 UTC on 19 Oct is already 20 Oct in Oslo
NOW = datetime(2026, 10, 19, 23, 30, tzinfo=UTC)
TODAY_OSLO = date(2026, 10, 20)
PRICES_NO2 = (Path(__file__).parent / "fixtures" / "prices_NO2_2026-10-19.json").read_bytes()


@pytest.fixture
def run(monkeypatch, tmp_path):
    """Run the CLI with a fake ingest_prices. Returns (exit code, calls)."""
    calls = []
    monkeypatch.setattr(sources, "_now", lambda: NOW)

    def run(*argv, status=None):
        def ingest_prices(day, run_id, root):
            calls.append((day, run_id, root))
            result = status(day) if callable(status) else status
            return result or {"NO1": "skipped"}

        monkeypatch.setattr(sources, "ingest_prices", ingest_prices)
        code = cli.main([*argv, "--root", str(tmp_path)])
        return code, calls

    return run


def test_backfill_loops_days_inclusive_with_one_run_id(run, tmp_path):
    code, calls = run(
        "backfill", "--source", "prices", "--start", "2026-10-01", "--end", "2026-10-03"
    )

    assert code == 0
    assert [day for day, _, _ in calls] == [date(2026, 10, 1), date(2026, 10, 2), date(2026, 10, 3)]
    run_ids = {run_id for _, run_id, _ in calls}
    assert len(run_ids) == 1
    uuid.UUID(run_ids.pop())
    assert {str(root) for _, _, root in calls} == {str(tmp_path)}


def test_backfill_defaults_to_earliest_price_start_through_oslo_today(run):
    _, calls = run("backfill")
    assert calls[0][0] == date(2021, 9, 7)
    assert calls[-1][0] == TODAY_OSLO


def test_incremental_covers_oslo_today_minus_7_through_tomorrow(run):
    _, calls = run("incremental")
    days = [day for day, _, _ in calls]
    assert days == [TODAY_OSLO + timedelta(n) for n in range(-7, 2)]


def test_failures_are_counted_loop_continues_and_exit_is_1(run, capsys):
    def status(day):
        if day == date(2026, 10, 2):
            raise OSError("disk full")
        return {"NO1": "written", "NO2": "failed", "NO3": "missing", "NO4": "skipped"}

    code, calls = run("backfill", "--start", "2026-10-01", "--end", "2026-10-03", status=status)

    assert code == 1
    assert len(calls) == 3
    assert capsys.readouterr().out.strip() == "written=2 skipped=2 missing=2 failed=3"


def test_start_after_end_is_rejected(run):
    with pytest.raises(SystemExit):
        run("backfill", "--start", "2026-10-03", "--end", "2026-10-01")


def test_rerun_makes_no_http_calls(tmp_path, monkeypatch, capsys):
    argv = ["backfill", "--start", "2026-10-19", "--end", "2026-10-19", "--root", str(tmp_path)]

    calls = []
    monkeypatch.setattr(
        sources, "http_get", lambda url, missing_ok: calls.append(url) or PRICES_NO2
    )

    assert cli.main(argv) == 0
    assert len(calls) == 5
    calls.clear()
    assert cli.main(argv) == 0

    assert calls == []
    first, second = capsys.readouterr().out.splitlines()
    assert first == "written=5 skipped=0 missing=0 failed=0"
    assert second == "written=0 skipped=5 missing=0 failed=0"
