# energy-data-platform

Portfolio project: Energy Market Analytics & Forecasting Platform. It ingests Norwegian electricity prices and weather, moves them through Bronze → Silver → Gold, trains a forecasting model on Gold, and serves the output to a dashboard.

- Architecture, layer responsibilities and implementation order: `docs/project-idea-&-context.md`
- Chosen APIs, endpoints and their quirks: `docs/data-sources.md`

## Layout

```
src/energy_platform/   ingestion/ transformation/ quality/ ml/ serving/
dags/                  Airflow DAGs
notebooks/             Databricks notebooks
dashboard/             Streamlit app
tests/                 pytest
data/                  local lake: bronze/ silver/ gold/ quarantine/ (contents gitignored)
.github/workflows/     CI
```

## Tooling (project-scoped plugins, see `.claude/settings.json`)

- **agent-skills** (addyosmani): the development workflow. Work through `/spec` → `/plan` → `/build` → `/test` → `/agent-skills:review` → `/ship`. Write a spec before starting a new pipeline stage.
- **ponytail** (DietrichGebert): keeps code minimal. Use stdlib or existing libraries first, and add no abstractions nobody asked for. It never cuts validation, error handling or tests. Run `/ponytail-review` on a diff before merging and `/ponytail-audit` for the whole repo.
- **public-apis**: a reference list, not installed. New data sources are picked from it and recorded in `docs/data-sources.md`.

## Conventions

- Bronze is append-only raw payloads plus ingestion metadata (run ID, ingested_at, source, row count). Never rewrite it.
- Business key: `price_area + timestamp_utc`. Store all timestamps in UTC from Silver onward.
- Secrets go in environment variables (`.env`, gitignored) and never in code.
- Split time series chronologically. No random shuffles.
