# Energy Data Platform – Project & Workflow Summary

As of 2026-10-20.

## Project overview

A portfolio project, "Energy Market Analytics & Forecasting Platform", built to prepare for Capgemini Ignite. It ingests Norwegian electricity prices and weather, cleans and combines them, trains a simple forecasting model, and serves the results to a dashboard.

It follows one stable architecture pattern:

1. **Source**: electricity prices, weather, hydrology (reservoir levels)
2. **Ingestion**: scheduled Python jobs with retries, logging and incremental loads
3. **Storage (Bronze)**: raw payloads, append-only, partitioned by date
4. **Transformation (Silver)**: UTC timestamps, units, schemas, deduplication, quality checks
5. **Gold**: use-case tables, e.g. one forecasting row per `price_area + timestamp`
6. **Serving and consumer**: ML predictions, DuckDB queries, a Streamlit or Power BI dashboard

Cross-cutting concerns: data quality, testing, security, logging and monitoring, CI/CD, governance.

The project should prove end-to-end data engineering: ML is a downstream consumer of reliable data, not the whole project. Planned tools: Python, Airflow, Databricks Free Edition (PySpark and Delta Lake), scikit-learn, MLflow, DuckDB, pytest, GitHub Actions.

## Repo structure

The folder structure is in place, but the folders are still empty (only `.gitkeep` placeholders). Local path: `~/projects/energy-data-platform` (WSL, branch `main`).

| Path | Purpose |
| --- | --- |
| `src/energy_platform/` | Python package: `ingestion/`, `transformation/`, `quality/`, `ml/`, `serving/` |
| `dags/` | Airflow DAGs |
| `notebooks/` | Databricks notebooks (PySpark, Delta Lake) |
| `dashboard/` | Streamlit app |
| `tests/` | pytest |
| `data/` | Local lake: `bronze/`, `silver/`, `gold/`, `quarantine/`. Contents gitignored. |
| `.github/workflows/` | GitHub Actions CI |
| `docs/` | `project-idea-&-context.md` (architecture), `tools.md` (tool per layer), `data-sources.md` (APIs), this file |
| `CLAUDE.md` | Instructions Claude Code reads at the start of every session |
| `.claude/settings.json` | Enables the ponytail and agent-skills plugins for this project |
| `.gitignore` | Ignores secrets, data, Python, notebook, DuckDB, MLflow and Airflow artifacts |
| `.env.example` / `.env` | Environment variables: the template is committed, `.env` is gitignored |

Files that `/agent-skills:spec` and `/agent-skills:plan` will create: `SPEC.md`, `tasks/plan.md`, `tasks/todo.md`. `pyproject.toml` (dependencies, pytest) comes in the first build task.

## Tooling

ponytail and agent-skills are Claude Code plugins installed for this project only. public-apis is a reference list and needs no installing.

| Tool | What it is | Automatic | Manual |
| --- | --- | --- | --- |
| [ponytail](https://github.com/DietrichGebert/ponytail) v5.3.2 | Rules for minimal code: reuse what exists, standard library first, no unrequested abstractions, never cut validation or tests | Loads its rules at every session start, also for helper agents | `/ponytail-review` (current changes), `/ponytail-audit` (whole repo), `/ponytail lite\|full\|ultra\|off` |
| [agent-skills](https://github.com/addyosmani/agent-skills) v0.6.13 | 25 engineering skills plus a spec → plan → build → test → review → ship workflow | Claude loads a matching skill when a task fits (its judgment, not guaranteed) | `/agent-skills:spec`, `:plan`, `:build`, `:test`, `:review`, `:ship` |
| [public-apis](https://github.com/public-apis/public-apis) | A curated README of free web APIs, by category | n/a | Pick a source from it and record it in `docs/data-sources.md` |

Cost: the bar under each reply ("full $1.01 last $0.09") is ponytail's estimate at API prices. On a claude.ai subscription it counts against plan limits, not money, unless "extra usage" is switched on. `/ponytail band off` hides the bar.

## Data sources

Four free, keyless APIs cover the first stage. All returned live data on 2026-10-20. Full details are in `docs/data-sources.md`.

| Need | Source | In public-apis | Notes |
| --- | --- | --- | --- |
| Electricity prices NO1–NO5 | [hvakosterstrommen.no](https://www.hvakosterstrommen.no/strompris-api) | no | One JSON file per day and area, hourly, NOK and EUR per kWh, history back to 2022 |
| Weather history | [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) | yes | Hourly, UTC |
| Weather forecast | [Open-Meteo Forecast](https://open-meteo.com/en/docs) | yes | Same format as the archive |
| Reservoir levels per price area | [NVE Magasinstatistikk](https://biapi.nve.no/magasinstatistikk/swagger/index.html) | no | Weekly |

Alternatives for later: MET Norway (needs a `User-Agent` header), Energi Data Service (15-minute `DayAheadPrices`), ENTSO-E (free token by email).

Quirks to handle in Silver:

- Prices come in local time with an offset, Open-Meteo in UTC. Normalize everything to UTC.
- Daylight-saving days have 23 or 25 hourly rows.
- Prices are per kWh. Convert to MWh (× 1000).
- Weather is per coordinate, so a reference table must map each price area to representative points.

## Development workflow

Use the full agent-skills flow for larger work, such as a new pipeline stage. For small changes, just describe what you want; ponytail still applies.

1. `/agent-skills:spec`: answer a few questions, approve `SPEC.md` (goal, scope, acceptance criteria, testing strategy, boundaries).
2. `/agent-skills:plan`: enters plan mode itself (read-only) and splits the spec into small tasks, saved in `tasks/plan.md` and `tasks/todo.md`. No separate plan mode needed.
3. `/agent-skills:build`: per task, writes a failing test, then the code, runs all tests, **commits**, and stops. Repeat once per task, or use `/agent-skills:build auto` to approve once and run every task.
4. `/agent-skills:review`: once the feature is done, before merging. Not before every commit.
5. `/ponytail-review` (optional): checks for unnecessary code.

How tests get created:

- **New features**: automatically, inside `/agent-skills:build` (test first, then code).
- **Existing code without tests**: `/agent-skills:test`, or ask "write tests for X".
- **Bugs**: `/agent-skills:test`, which writes a test that reproduces the bug before fixing it.
- What to test is decided in the spec's testing strategy, e.g. UTC conversion, kWh → MWh, 23/25-hour days, duplicates, API failures.
- Tests use pytest and run with `pytest`. It gets installed in the first build task.

## How to start a session

Start Claude Code from the project folder. `CLAUDE.md` and both plugins then load automatically, so you don't need to re-explain the project.

1. In WSL: `cd ~/projects/energy-data-platform && claude`
2. Check that "PONYTAIL MODE ACTIVE" appears, and that typing `/` lists `/ponytail` and `/agent-skills:spec`.
3. Check where you left off: `git status`, `git log --oneline -5` and, once it exists, `tasks/todo.md`.
4. Choose the mode:
    - **New stage**: `/agent-skills:spec` with a one-line goal.
    - **Continuing a plan**: `/agent-skills:build` picks the next open task in `tasks/todo.md`.
    - **Small change or question**: just ask in plain words.
5. End a feature with `/agent-skills:review`, then commit or merge.

Example first prompt for the next session:

```
/agent-skills:spec Bronze ingestion: fetch daily prices for NO1–NO5 from hvakosterstrommen.no and hourly weather from Open-Meteo, store raw JSON under bronze/<source>/year=/month=/day= with ingestion metadata (run_id, ingested_at, source, row_count). Support a historical backfill and an incremental daily run. See docs/data-sources.md.
```

To resume a previous conversation instead of starting fresh, use `claude --continue` (latest) or `claude --resume` (pick from a list).

## Status and next steps

Setup is done and no pipeline code exists yet. Next comes the spec for Bronze ingestion.

- [x] Plugins installed and enabled for the project (ponytail 5.3.2, agent-skills 0.6.13)
- [x] Data sources chosen and tested
- [x] `CLAUDE.md` and `docs/data-sources.md` written
- [x] Repo structure, `.gitignore`, `.env.example`
- [ ] Commit the structure and this file
- [ ] `/agent-skills:spec` for Bronze ingestion (implementation steps 1–4)
- [ ] `/agent-skills:plan`, then `/agent-skills:build` per task
- [ ] Later stages: Airflow, Databricks Bronze → Silver → Gold, quality tests, baseline model, MLflow, dashboard, CI
