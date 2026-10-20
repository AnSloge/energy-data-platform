# Spec: Bronze ingestion

Status: **approved v3** (2026-10-20)

## Objective

Fetch raw data from the three primary sources in `docs/data-sources.md` and store each API response byte for byte in the local Bronze lake, with ingestion metadata. This is the first pipeline stage. Silver will be rebuilt from these files, so we never need to re-download final data.

Consumers: the Bronze → Silver transformation (next stage) and, later, an Airflow DAG that calls the same functions.

The code must support two modes:
- **Backfill:** a date range, resumable, polite to the APIs.
- **Incremental:** a short lookback window that heals small gaps by itself.

Both modes call the same per-source functions. Idempotency comes from "skip if already committed", so a rerun costs no API calls.

## Bronze file rule: one file = one API request

- Each Bronze data file holds exactly one raw HTTP response body, byte for byte. No splitting, merging, parsing or filtering.
- Path: `data/bronze/<source>/year=YYYY/month=MM/day=DD/<name>_<start>_<end>.json`. The partition is the **start date of the requested range**. `<name>` is the price area or `all` (NVE). `<start>`/`<end>` are ISO dates.
- The range is in the filename, so two requests with different ranges never collide. The idempotency key is `(source, name, start, end)`.
- Every data file has a sidecar `<same stem>.meta.json`:

```json
{
  "run_id": "3f2c…",
  "ingested_at": "2026-10-20T08:00:04+00:00",
  "source": "weather_archive",
  "range_start": "2026-09-01",
  "range_end": "2026-09-30",
  "row_count": 720,
  "url": "https://archive-api.open-meteo.com/v1/archive?latitude=58.15&longitude=8.0&start_date=2026-09-01&end_date=2026-09-30&hourly=…"
}
```

`row_count` is the number of list elements (prices, NVE) or `len(hourly.time)` (Open-Meteo).

### Write safety

1. Write the data file to a temp name in the same directory, then `os.replace` it into its final name.
2. Write the meta file last, the same way (temp name, then `os.replace`).
3. **A data file without a meta file is incomplete.** It gets overwritten when the request is retried.
4. **A data file with a meta file is committed and is never overwritten.** If the writer is asked to overwrite one, it raises `FileExistsError`.
5. If the meta file exists, the request is skipped with no HTTP call. NVE is the one exception (see below).

## Sources

### Partition date semantics

These are explicit so Silver joins don't drift around midnight.

| Source | Partition / range dates mean |
|---|---|
| `prices` | delivery day in **Europe/Oslo** local time (the date in the API URL) |
| `weather_archive` | **UTC** date (Open-Meteo default `timezone=GMT`) |
| `weather_forecast` | **UTC** date. The range starts on the snapshot date. |
| `nve_reservoirs` | **ISO week**: `range_start` = Monday of the ISO week, `range_end` = `dato_Id` (the Sunday that ends it, as NVE publishes it) |

### Per-source behaviour

| Source dir | Function | One request = | Backfill | Incremental |
|---|---|---|---|---|
| `prices` | `ingest_prices(day, run_id)` | 1 area × 1 day (`/prices/YYYY/MM-DD_NOx.json`) | per-area start dates (NO1 2021-09-07, NO2/3/5 2021-10-01, NO4 2021-11-01) → today | Oslo today − 7 → tomorrow |
| `weather_archive` | `ingest_weather_archive(start, end, run_id)` | 1 location × 1 range | 1 request per location per **calendar month**. The last month is truncated at today − 5. | 1 request per location per day, for today − 12 → today − 5 |
| `weather_forecast` | `ingest_weather_forecast(day, run_id)` | 1 location, `start_date=day`, `end_date=day+6` | none in v1 (see Later stages) | 1 snapshot per day at **10:00 Europe/Oslo** |
| `nve_reservoirs` | `ingest_reservoirs_latest(run_id)` | `HentOffentligDataSisteUke` | — | weekly, after Wednesday 13:00 Oslo |
| `nve_reservoirs` | `ingest_reservoirs_history(run_id)` | `HentOffentligData` (full history, ~4 MB) | once; skipped if any committed history file exists | — |

**Weather variables** (archive and forecast): `temperature_2m, precipitation, wind_speed_10m, shortwave_radiation`. Locations: one city per area, as in `docs/data-sources.md`. Requests always use one location each, so the multi-location question in the counting section below doesn't apply.

**Weather archive settle lag = 5 days.** `ingest_weather_archive` raises `ValueError` if `end > today(UTC) − 5`. Source: ERA5 is "Daily with 5 days delay" per [Open-Meteo Historical Weather API docs](https://open-meteo.com/en/docs/historical-weather-api). Monthly backfill files and daily incremental files can overlap. That is allowed, and Silver resolves it (see the contract below).

**Weather forecast timing.** The day-ahead auction closes at 12:00 CET/CEST. The snapshot runs at **10:00 Europe/Oslo**, which is always the same UTC date. `ingest_weather_forecast` raises `ValueError` if `day != today (UTC)`. A run at or after 12:00 Europe/Oslo **still stores the snapshot and logs a warning**. Bronze records what the source returned. The 12:00 cutoff is a feature-availability rule, and it belongs to Gold (see contracts below). A missed day stays missing until the Previous Runs backfill stage.

**NVE.** The requests take no date parameters, so the range comes from the response:
- Weekly: `range_start`/`range_end` = the ISO week of `dato_Id`. Every `omrType == "EL"` row must share one `dato_Id`, otherwise the function raises. Because the range is unknown until the response arrives, the weekly call always makes 1 HTTP request (a small one) and then skips the write if that week is already committed.
- History: the range runs from the first ISO week to the last `dato_Id` in the payload.
- The payload is stored unchanged with all `omrType`s. Silver filters it to `EL` 1–5.

### Price resolution assumption

- hvakosterstrommen serves an **undocumented hourly aggregation** of the 15-minute ENTSO-E day-ahead prices. This was verified on 2026-10-19, when a day had 24 hourly entries. It is **not** the official 15-minute market price.
- **EUR is the primary value** (`EUR_per_kWh`). `NOK_per_kWh` is derived by the provider with its own rate (`EXR`). Silver keeps both and labels NOK as provider-derived.
- **Shape check, in Silver, not Bronze.** Bronze stores whatever the source returns, because if the API switches format, that raw response is exactly what we want to keep. The Bronze → Silver step **fails loudly** (it raises and writes nothing for that day) unless both of these hold:
  - the entry count equals the number of hours in that Oslo day: 23 on the spring DST day, 25 on the autumn DST day, 24 otherwise (computed with `zoneinfo`)
  - every entry has `time_end − time_start == 60 min`, and entries are contiguous

  Bronze only checks that the body is valid JSON with `row_count > 0`.

### Other behaviour rules

- **Expected absence is not an error.** A price 404 for tomorrow before ~13:00 Oslo, or before an area's start date, is logged and nothing is written. Any other 4xx raises.
- **Validate before writing.** The body must parse as JSON and have `row_count > 0`. Otherwise nothing is written, so a later run retries.
- **HTTP.** Uses stdlib `urllib`, a 30 s timeout, and the `User-Agent` from the constant `USER_AGENT = "energy-data-platform/0.1 (+https://github.com/AnSloge/energy-data-platform)"` in `ingestion/bronze.py`. It isn't a secret, so it doesn't go in `.env`. It retries 3 times with backoff (1, 2, 4 s) on 5xx, 429, timeouts and connection errors.
- **run_id.** One `uuid4` per CLI invocation, passed into every function. Airflow passes its own run ID later.
- **Politeness.** Backfill sleeps 0.5 s between HTTP requests. Skipped requests don't sleep.
- **Failures in a range.** Backfill/incremental log the failed request and continue, then print a summary (written / skipped / missing / failed) and exit 1 if anything failed.

### Open-Meteo call counting (checked 2026-10-20)

From [open-meteo.com/en/pricing](https://open-meteo.com/en/pricing) and [open-meteo.com/en/terms](https://open-meteo.com/en/terms):
- Free tier limits: 600/min, 5,000/hour, 10,000/day, 300,000/month. Non-commercial use only, under CC BY 4.0. "Rate limits are applied by IP addresses and application."
- "Typically, one API call corresponds to one HTTP API request." Requests with more than 10 variables or longer than 2 weeks count as multiple calls, using fractional counts. The page's examples: "2 weeks of data with 15 weather variables will be calculated as 1.5 API calls"; "4 weeks of data equals 3.0 API calls".
- **Multi-location requests: unverified.** Neither the pricing, terms nor archive docs say how they are counted. This doesn't matter here, because we send one location per request.

**Estimate.** The archive backfill covers 2021-09 → 2026-10, which is 62 months × 5 locations = **310 requests**. With 4 variables, a 28–31-day request counts as roughly 2–3 calls by the examples above, so about **600–950 weighted calls** in total. That is under 10 % of the daily limit and takes ~3 min at 0.5 s per request. Forecasts are 5 requests/day, each 7 days × 4 variables ≈ 1 call. The exact weighting formula isn't published, so treat the estimate as approximate.

Prices: about 1,870 days × 5 areas ≈ **9,350 requests** (~80 min at 0.5 s). hvakosterstrommen publishes no rate limits (unverified). Because the backfill resumes for free, it can be split across sessions.

## Contracts for later stages

### Silver

- **Overlapping ranges:** for each business key, Silver keeps the record from the file with the latest `ingested_at`. Business keys:
  - prices, weather archive: `price_area + timestamp_utc`
  - weather forecast: `price_area + snapshot_date + timestamp_utc`. Snapshots are history, so Silver never dedups across them.
  - NVE: `omrnr + dato_Id`
- Partition dates follow the semantics table above. Silver converts every timestamp to UTC, and joins on `timestamp_utc`, never on partition dates.
- The price shape check (above) lives in Silver and fails the run loudly.
- EUR is the primary price; NOK is provider-derived.
- NVE values are forward-filled from the publish time (Wednesday 13:00 Oslo), not from `dato_Id` (see `docs/data-sources.md`).

### Gold

- **Forecast cutoff:** a forecast snapshot is a usable feature for delivery day D+1 only if its `ingested_at` is before 12:00 Europe/Oslo on day D, when the day-ahead auction closes. Gold drops later snapshots for that target, using `ingested_at` from the meta file. It doesn't use the partition date.

## Tech Stack

Python 3.12, stdlib only (`urllib.request`, `json`, `argparse`, `logging`, `uuid`, `zoneinfo`, `pathlib`). **No new dependencies.** pytest + ruff are already in `[dev]`. No `.env` is needed for this stage.

## Commands

```bash
pip install -e ".[dev]"

python -m energy_platform.ingestion backfill --source prices --start 2021-09-07 --end 2026-10-20
python -m energy_platform.ingestion backfill --source weather_archive --start 2021-09-01 --end 2026-10-15
python -m energy_platform.ingestion backfill --source nve_reservoirs          # full history, once
python -m energy_platform.ingestion incremental                               # all sources, default windows
python -m energy_platform.ingestion incremental --source weather_forecast     # scheduled 10:00 Europe/Oslo

ruff check .
pytest                                      # unit tests, no network
pytest -m integration                       # live API smoke tests, manual only
```

`--source` values: `prices | weather_archive | weather_forecast | nve_reservoirs`. `--start/--end` are inclusive ISO dates. They default to each source's start date from the table and its latest allowed date.

## Project Structure

```
src/energy_platform/ingestion/
  bronze.py      USER_AGENT, http_get (retries), write_bronze (atomic, append-only), is_committed
  sources.py     the five ingest_* functions, AREAS / POINTS / PRICE_START constants
  __main__.py    argparse CLI: backfill, incremental
.env.example     drop the HTTP_USER_AGENT line (same task that adds USER_AGENT)
tests/
  fixtures/      one small real payload per endpoint, captured once by hand
  test_bronze.py writer + http behaviour
  test_sources.py per-source functions with http_get monkeypatched
  test_cli.py    range loops (monthly / daily), summary, exit code
```

## Code Style

Match ruff (line length 100), type hints on public functions, no classes unless state needs one.

```python
def ingest_prices(day: date, run_id: str, root: Path = BRONZE_ROOT) -> list[Path]:
    """Fetch prices for NO1–NO5 for one Oslo delivery day. Returns written data-file paths."""
    written = []
    for area in AREAS:
        if day < PRICE_START[area] or is_committed(root, "prices", area, day, day):
            continue
        url = f"{PRICES_URL}/{day:%Y}/{day:%m-%d}_{area}.json"
        body = http_get(url, missing_ok=True)  # 404 = not published yet
        if body is None:
            log.info("prices %s %s not published", day, area)
            continue
        rows = len(json.loads(body))
        written.append(write_bronze(root, "prices", area, day, day, body, run_id, url, rows))
    return written
```

## Testing Strategy

- **pytest**, tests in `tests/`, fixtures in `tests/fixtures/`. Unit tests never touch the network: `http_get` is monkeypatched, and every lake write goes to `tmp_path`.
- **Unit (must have):**
  - data file byte-identical to the response; meta has all 7 fields with correct range and row_count
  - partition = range start; filename carries the range; two ranges with the same start don't collide
  - second call is a no-op and makes no HTTP call (all sources except NVE weekly, which makes 1 call and writes nothing)
  - data file without meta is overwritten on retry; data file with meta raises `FileExistsError` on overwrite
  - meta is written after the data file: a simulated crash between the two leaves no meta file
  - price 404 writes nothing; empty list / non-JSON writes nothing
  - retry: 5xx then 200 succeeds, 3× 5xx raises, other 4xx raises immediately
  - archive with `end > today − 5` raises; backfill splits a range into calendar months, truncating the last one
  - forecast with a past day raises; at/after 12:00 Oslo it writes and logs a warning (clock injected)
  - NVE weekly range = Monday → `dato_Id`; mixed `dato_Id`s raise
  - CLI: one failing request doesn't stop the range, exit code 1, summary counts
- **Integration** (`@pytest.mark.integration`, excluded by default as already set up in `pyproject.toml`): one live fetch per source into `tmp_path`.
- The price shape check is tested in the Silver stage, not here.

## Boundaries

- **Always:** one file per request, byte-identical; commit the meta file last; use UTC for `ingested_at`; run `ruff check . && pytest` before committing.
- **Ask first:** adding any dependency (requests, httpx, tenacity); changing the path layout or meta fields after the first backfill; adding sources or endpoints (e.g. `HentOffentligDataMinMaxMedian`, Previous Runs API).
- **Never:** call live APIs in unit tests; overwrite or delete committed Bronze files; parse, convert or filter data in Bronze; commit anything under `data/`; put secrets in code.

## Success Criteria

1. `pytest` passes with no network access. `ruff check .` is clean. CI stays green.
2. Price backfill from 2021-09-07 leaves 5 committed files per day from each area's start date onward. Rerunning makes 0 HTTP calls.
3. Weather archive backfill writes 5 files per calendar month (2021-09 → current month, the last one truncated at today − 5). Rerunning makes 0 HTTP calls.
4. `incremental` run twice in a row: the second run makes 0 HTTP calls for prices, the archive and the forecast. NVE makes 1 call and writes nothing.
5. Killing a backfill mid-run and restarting it resumes with no duplicates or corrupt files.
6. Every data file has a meta sidecar. Its `row_count` and range match the payload.

## Known limitations

- **Weather archive revisions aren't picked up (accepted for v1).** Each archive request is made once and then skipped, so Bronze keeps the first version of each day. Revisions come from the final reanalysis months later, so re-fetching only the last few days wouldn't catch them. If needed, a periodic re-fetch of older months fits the existing latest-wins rule (see Later stages).
- **Prices are an hourly aggregation** of 15-minute market prices by a third party (see Price resolution assumption). They're fine for an hourly model, but they are not the official settlement price.
- One weather point per price area (see `docs/data-sources.md`).

## Later stages (out of scope for v1)

- **Forecast backfill via Open-Meteo [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api)** (most models from January 2024, fixed lead times `previous_day1..7`). The Historical Forecast API covers earlier years. This is planned, because training on archive actuals while predicting with forecasts is train/serve skew. It would also fill missed forecast days.
- **Native 15-minute prices from ENTSO-E** (needs a token, XML).
- **Periodic re-fetch of older weather archive months**, to pick up reanalysis revisions. The rule "Silver keeps the latest `ingested_at`" already handles the overlap.
- Airflow DAG, Silver parsing/validation, `MinMaxMedian` reference data, multiple weather points per area, a run-log table.

## Attribution

The README must credit the data sources: **Open-Meteo** (CC BY 4.0, link to open-meteo.com) and **hvakosterstrommen.no**. NVE Magasinstatistikk should be credited too. Add this when the first Bronze code lands.

## Open Questions

None. Resolved 2026-10-20:
- `.env.example`: the `HTTP_USER_AGENT` line is removed in the same build task that adds `USER_AGENT`.
- Late forecast runs: the snapshot is stored with a warning, and Gold applies the cutoff.
- Archive revisions: fetch once for v1; this is a known limitation.
