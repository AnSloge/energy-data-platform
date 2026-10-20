# Todo: Bronze ingestion

Spec: `specs/Bronze_ingestion.md` · Plan: `tasks/plan.md`
Verify command for every task: `ruff check . && pytest`

## Phase 1: Foundation + prices

- [ ] **Task 1: Bronze writer with write-safety rules**
  - Adds `write_bronze(root, source, name, start, end, body, run_id, url, rows) -> Path` and `is_committed(...)`.
  - Acceptance:
    - The path is `<root>/<source>/year=/month=/day=<start>/<name>_<start>_<end>.json`, with a byte-identical body and a meta file holding the 7 spec fields (`ingested_at` in UTC)
    - The data file goes through temp + `os.replace` first, then the meta file the same way. An orphan data file (no meta) is overwritten. A committed file raises `FileExistsError`.
    - Two ranges with the same start don't collide
  - Verify: `pytest tests/test_bronze.py`. One test simulates a crash between the data and meta writes and asserts no meta exists and the retry succeeds.
  - Files: `src/energy_platform/ingestion/__init__.py`, `src/energy_platform/ingestion/bronze.py`, `tests/test_bronze.py`
  - Size: S
  Additional checks: 
  - The lake folder should be gitignored
  - Add price resolutoin check
  - an empty non-JSON body should ocunt as "failed", not "missing"

- [ ] **Task 2: `http_get` + `ingest_prices`**
  - Adds `USER_AGENT`, `http_get(url, missing_ok=False) -> bytes | None` and `ingest_prices(day, run_id, root)`. Removes `HTTP_USER_AGENT` from `.env.example`.
  - Acceptance:
    - `http_get` uses a 30 s timeout and sends `USER_AGENT`. It retries 3 times with backoff 1/2/4 s on 5xx, 429, timeouts and connection errors. Any other 4xx raises at once. A 404 with `missing_ok` returns `None`.
    - `ingest_prices` skips areas before `PRICE_START` and areas already committed (no HTTP call). On a 404 or an empty/non-JSON body it writes nothing.
    - The file is stored byte-identical to the fixture, and `row_count` = number of list entries
  - Verify: `pytest tests/test_bronze.py tests/test_sources.py`. `urlopen` and `time.sleep` are monkeypatched, so no network calls.
  - Files: `bronze.py`, `src/energy_platform/ingestion/sources.py`, `tests/test_sources.py`, `tests/fixtures/prices_NO2_2026-10-19.json` (captured by hand), `.env.example`
  - Size: M
  - Depends on: 1

- [ ] **Task 3: CLI for prices + README attribution**
  - Adds `python -m energy_platform.ingestion backfill|incremental --source prices [--start --end]`.
  - Acceptance:
    - Backfill loops over days (default start = earliest `PRICE_START`, end = today Oslo). Incremental covers Oslo today − 7 → tomorrow.
    - One `uuid4` run_id per invocation. 0.5 s sleep only after a real HTTP request.
    - A failing day is logged and the loop continues. The run prints a written/skipped/missing/failed summary and exits 1 if anything failed.
    - The README credits Open-Meteo (CC BY 4.0), hvakosterstrommen.no and NVE
  - Verify: `pytest tests/test_cli.py`. Manual: backfill 3 recent days, then rerun and confirm 0 HTTP calls in the log.
  - Files: `src/energy_platform/ingestion/__main__.py`, `tests/test_cli.py`, `README.md`
  - Size: S
  - Depends on: 2

### Checkpoint A
- [ ] `ruff check . && pytest` green
- [ ] Manual 3-day price backfill + rerun check done
- [ ] Human review before Phase 2

## Phase 2: Remaining sources

- [ ] **Task 4: Weather archive**
  - Adds `ingest_weather_archive(start, end, run_id, root)`. One request per location (5 files).
  - Acceptance:
    - Raises `ValueError` if `end > today(UTC) − 5`
    - The request URL has `start_date`, `end_date`, the 4 spec variables and one location's coordinates. `row_count` = `len(hourly.time)`.
    - CLI backfill splits the range into calendar months, with the last month truncated at today − 5. Incremental makes single-day requests for today − 12 → today − 5.
  - Verify: `pytest`. Month-split edge cases are covered: a start mid-month, a December→January rollover, and a truncated last month.
  - Files: `sources.py`, `__main__.py`, `tests/test_sources.py`, `tests/test_cli.py`, `tests/fixtures/weather_archive_NO2_2026-09-01.json`
  - Size: M
  - Depends on: 3

- [ ] **Task 5: Weather forecast**
  - Adds `ingest_weather_forecast(day, run_id, root)`. One snapshot per location with `start_date=day`, `end_date=day+6`.
  - Acceptance:
    - `day != today(UTC)` raises `ValueError`
    - At or after 12:00 Europe/Oslo it still writes and logs a warning (clock monkeypatched through `_now()`)
    - A second call on the same day makes no HTTP call
  - Verify: `pytest`. Before capturing the fixture, confirm the forecast endpoint accepts `start_date`/`end_date` (see the plan risk).
  - Files: `sources.py`, `__main__.py`, `tests/test_sources.py`, `tests/fixtures/weather_forecast_NO2.json`
  - Size: S
  - Depends on: 3

- [ ] **Task 6: NVE reservoirs**
  - Adds `ingest_reservoirs_latest(run_id, root)` and `ingest_reservoirs_history(run_id, root)`, with name `all`.
  - Acceptance:
    - Weekly: range = Monday of the ISO week of `dato_Id` → `dato_Id`. Mixed `dato_Id`s across EL rows raise. Always 1 HTTP call, and nothing is written if the week is already committed.
    - History: range = first week → last `dato_Id`. It is skipped with no HTTP call if any committed history file exists.
    - CLI: `backfill --source nve_reservoirs` runs history; `incremental` runs latest
  - Verify: `pytest`
  - Files: `sources.py`, `__main__.py`, `tests/test_sources.py`, `tests/fixtures/nve_siste_uke.json`, `tests/fixtures/nve_history_trimmed.json`
  - Size: M
  - Depends on: 3

### Checkpoint B
- [ ] `ruff check . && pytest` green
- [ ] Manual: `incremental` twice. The second run makes 0 HTTP calls except 1 for NVE.
- [ ] Human review

## Phase 3: Live verification

- [ ] **Task 7: Integration tests**
  - Acceptance: one `@pytest.mark.integration` test per source fetches live data into `tmp_path` and asserts a committed file + meta with `row_count > 0`. It is excluded from the default `pytest` run.
  - Verify: `pytest -m integration` passes. Plain `pytest` still runs offline.
  - Files: `tests/test_integration.py`
  - Size: S
  - Depends on: 4, 5, 6

- [ ] **Task 8: Real backfill + success criteria** *(user runs it or approves it first: about 9,700 live requests, ~90 min)*
  - Acceptance: spec success criteria 2–6 are checked against the real lake:
    - per-area file counts per day
    - 5 files per archive month
    - a rerun makes 0 HTTP calls
    - a backfill killed and restarted resumes cleanly
    - every data file has a meta file with a matching `row_count`
  - Verify: a short check script run in the scratchpad, not committed. Results are recorded in the PR description.
  - Files: none committed
  - Depends on: 7

### Checkpoint C: complete
- [ ] Spec success criteria 1–6 all met
- [ ] `/agent-skills:review` and `/ponytail-review` on the diff
