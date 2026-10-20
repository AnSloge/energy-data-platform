# Implementation Plan: Bronze ingestion

Spec: `specs/Bronze_ingestion.md` (approved v3). Tasks with acceptance criteria: `tasks/todo.md`.

## Overview

Build `src/energy_platform/ingestion/` as three modules:
- `bronze.py`: the HTTP client and the append-only writer.
- `sources.py`: one `ingest_*` function per source.
- `__main__.py`: the CLI for backfill and incremental runs.

Prices go end to end first, because they exercise every write-safety rule and give a runnable CLI early. The other sources then plug into the same writer and CLI.

## Dependency graph

```
bronze.write_bronze / is_committed      (no I/O beyond the local lake)
        │
bronze.http_get                         (urllib, retries, USER_AGENT)
        │
sources.ingest_prices ──────────────┐
sources.ingest_weather_archive ─────┤
sources.ingest_weather_forecast ────┼── __main__ (backfill / incremental, range loops, summary)
sources.ingest_reservoirs_* ────────┘
```

The writer has no dependencies, so it comes first. Every source depends on the writer and `http_get`. The CLI depends on the sources but gets extended one source at a time: the prices task creates it, and each later source task adds its own range rule.

## Architecture decisions

- **Stdlib only**, so no dependency questions come up. `urllib.request`, `json`, `argparse`, `logging`, `uuid`, `zoneinfo`.
- **Commit marker = meta file.** `is_committed(root, source, name, start, end)` only checks whether the `.meta.json` exists. The writer writes the data file through a temp name and `os.replace`, then the meta file the same way.
- **Clock is a module-level `_now()` in `sources.py`**, returning `datetime.now(UTC)`. Tests monkeypatch it. This avoids adding a `now=` parameter to every public function.
- **Tests stay offline.** Tests monkeypatch `sources.http_get` (and, for retry tests, `urllib.request.urlopen` and `time.sleep`). Fixtures are real payloads captured once by hand and trimmed where they are large (NVE history).
- **Range loops live in the CLI.** These are per-day loops (prices, archive incremental) and per-month loops (archive backfill). The `ingest_*` functions take exactly one request's range, which is what an Airflow task will call later.
- **Return value:** each `ingest_*` returns `{name: "written" | "skipped" | "missing"}`. This replaces the `list[Path]` in the spec's style snippet, because the CLI summary needs to tell these three cases apart.
- **CLI error handling:** each `ingest_*` call is wrapped in try/except. Any exception, including `ValueError` for an empty or non-JSON body, counts as "failed". The loop continues and the run exits 1 at the end. A 404 is "missing" and doesn't fail the run. A source function never swallows its own errors.
- **Lake root:** `BRONZE_ROOT = Path("data/bronze")`, overridable with a `root` argument or the CLI's `--root`. Lake contents are already ignored by `.gitignore` (`data/**`).
- **Price resolution check lives in Silver**, as the approved spec says. Bronze commits the DST fixtures (23 and 25 rows) so that stage can reuse them.

## Task list

### Phase 1: Foundation + first vertical slice (prices)
- [x] Task 1: Bronze writer with write-safety rules
- [ ] Task 2: `http_get` + `ingest_prices` (one day, all areas)
- [ ] Task 3: CLI `backfill` / `incremental` for prices + README attribution

### Checkpoint A: after Tasks 1–3
- [ ] `ruff check . && pytest` green
- [ ] Manual: `backfill --source prices` over 3 days writes 15 files + 15 metas; the rerun logs 0 HTTP calls
- [ ] Human review before adding more sources

### Phase 2: Remaining sources
- [ ] Task 4: Weather archive (monthly backfill, daily incremental, 5-day lag)
- [ ] Task 5: Weather forecast (daily snapshot, 12:00 warning)
- [ ] Task 6: NVE reservoirs (weekly latest + one-off history)

### Checkpoint B: after Tasks 4–6
- [ ] `ruff check . && pytest` green
- [ ] Manual: `incremental` (all sources) twice. The second run makes 0 HTTP calls except 1 for NVE.
- [ ] Human review

### Phase 3: Verification against live APIs
- [ ] Task 7: Integration tests (one live fetch per source, `-m integration`)
- [ ] Task 8: Real backfill run + `scripts/check_bronze.py` (committed) to check the success criteria (user-run or user-approved, ~90 min of API traffic)

### Checkpoint C: complete
- [ ] All six spec success criteria checked off
- [ ] `/agent-skills:review` and `/ponytail-review` on the branch diff

## Parallelization

Tasks 4, 5 and 6 depend only on Tasks 1–3 and each touch their own function. They could run in parallel, but they all edit `sources.py`, `__main__.py` and `tests/test_sources.py`, so sequential is simpler and avoids merge conflicts. Keep them sequential.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Open-Meteo forecast endpoint may not accept `start_date`/`end_date` the way the spec assumes | Med | Verify while capturing the fixture in Task 5. If it fails, fall back to `forecast_days=7` and record the range from the response. Update the spec first. |
| hvakosterstrommen has no published rate limit; ~9,350 requests in the backfill | Med | 0.5 s politeness delay, resumable. Task 8 can be split across sessions. Stop on repeated 429s. |
| NVE `SisteUke` response may mix `dato_Id`s across `omrType`s | Low | The spec already says to raise. The Task 6 fixture shows the real shape. |
| `os.replace` atomicity on WSL / `/mnt/c` paths | Low | The lake lives under the repo on the Linux filesystem, and the temp file sits in the same directory as its target. |
| Weighted Open-Meteo call count is higher than estimated | Low | 310 archive requests leave a large margin under 10,000/day, even at 3× the estimate. |
| Fixture capture needs one live call per endpoint | Low | Done by hand once during the build, not in tests (CLAUDE.md boundary). |

## Open questions

None. All spec questions were resolved on 2026-10-20.
