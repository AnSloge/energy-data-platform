# Data sources

Shortlist picked from [public-apis](https://github.com/public-apis/public-apis) (Environment and Weather sections), plus a few Nordic sources that list doesn't include. Every endpoint below returned live data on 2026-10-20.

public-apis is a directory, not a dependency. Use it to find new sources, then add them here.

## Primary (start here)

| Purpose | Source | Auth | Example endpoint | Notes |
|---|---|---|---|---|
| Electricity prices (NO1–NO5), history + day-ahead | [hvakosterstrommen.no](https://www.hvakosterstrommen.no/strompris-api) | none | `https://www.hvakosterstrommen.no/api/v1/prices/2026/10-20_NO2.json` | One file per day and area. NOK and EUR per kWh, hourly, history from autumn 2021 (see findings). Not in public-apis. |
| Weather history (backfill) | [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) | none | `https://archive-api.open-meteo.com/v1/archive?latitude=58.15&longitude=8.0&start_date=2026-10-01&end_date=2026-10-01&hourly=temperature_2m,precipitation,wind_speed_10m` | Hourly, UTC by default. Free for non-commercial use. |
| Weather forecast | [Open-Meteo Forecast](https://open-meteo.com/en/docs) | none | `https://api.open-meteo.com/v1/forecast?latitude=58.15&longitude=8.0&hourly=temperature_2m&forecast_days=7` | Same schema as the archive, so one parser covers both. |
| Hydrology: reservoir filling per price area | [NVE Magasinstatistikk](https://biapi.nve.no/magasinstatistikk/swagger/index.html) | none | `https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke` | Weekly. `omrType=EL`, `omrnr` = price area. Not in public-apis. |

## Exploration findings (2026-10-20)

From the notebooks in `notebooks/`. Gap checks cover samples only (last 30 days); the full history is checked during the Bronze backfill.

### Prices: hvakosterstrommen (`01_explore_prices.ipynb`)

- **Resolution:** hourly, 24 rows per day, 23 on spring DST days and 25 on autumn DST days. Still hourly after the market moved to 15 minutes on 2025-10-01, so the API returns hourly values.
- **History starts:** NO1 2021-09-07, NO2/NO3/NO5 2021-10-01, NO4 2021-11-01. Earlier days return 404. The NO1 date is worth a spot check for gaps.
- **Tomorrow's prices:** 404 until the day-ahead auction result is out (~13:00 Oslo time). These are final market prices, not forecasts.
- **Quality (last 30 days):** no nulls, no duplicates, no missing hours (720 rows per area).
- **Negative prices are real:** 8 hours, the lowest −0.019 NOK/kWh (NO2 2026-09-27, NO4 2026-10-06). Validation must allow prices below 0.
- **Fields:** `NOK_per_kWh`, `EUR_per_kWh`, `EXR` (EUR→NOK rate), `time_start`, `time_end` (local time with offset).

### Weather: Open-Meteo (`02_explore_weather.ipynb`)

- **Archive starts:** 1940-01-01. Precipitation and shortwave radiation are null until 07:00 UTC that day (likely because they are accumulated values), complete after that.
- **Archive is not delayed:** it already had values up to 23:00 today, ~14 h into the future. Recent days are therefore model-filled and may be revised later. Not yet verified by re-fetching a day.
- **Forecast:** `forecast_days` max 16. About 15 full days; the last day has ~21–23 nulls per variable. `past_days` adds earlier days.
- **Schema:** archive and forecast have the same columns and units. Times are UTC without offset, coordinates are snapped to the model grid, wind is km/h.
- **Quality (30-day archive sample, 5 points):** no nulls, no duplicates, 24 rows per day.
- **Points per area (one city each, a shortcut):**

| Area | City | Latitude | Longitude |
|---|---|---|---|
| NO1 | Oslo | 59.91 | 10.75 |
| NO2 | Kristiansand | 58.15 | 8.00 |
| NO3 | Trondheim | 63.43 | 10.39 |
| NO4 | Tromsø | 69.65 | 18.96 |
| NO5 | Bergen | 60.39 | 5.32 |

Open question: is one coastal city representative of each area's demand and hydro inflow? Revisit with several weighted points later.

### Hydrology: NVE Magasinstatistikk (`03_explore_hydrology.ipynb`)

- **Areas:** `omrType == "EL"` with `omrnr` 1–5 = NO1–NO5. Ignore `NO` (whole country, `omrnr` 0) and `VASS` (river systems).
- **Frequency:** weekly, one row per area per ISO week. `dato_Id` = the Sunday that ends the week.
- **Published:** Wednesdays at 13:00 (`neste_Publiseringsdato`), about 3 days after `dato_Id`.
- **History:** 1995-01-08 onward, 1658 weeks per area, no gaps, no duplicates. The full history is one ~4 MB call (`HentOffentligData`).
- **Fields:** `fyllingsgrad` (fraction 0–1), `kapasitet_TWh`, `fylling_TWh`, `fyllingsgrad_forrige_uke`, `endring_fyllingsgrad`.
- **Seasonal reference:** `HentOffentligDataMinMaxMedian` gives min/median/max per ISO week. Deviation from the median is a candidate feature.

## Alternatives / later

| Purpose | Source | Auth | Notes |
|---|---|---|---|
| Weather (Norwegian official) | [MET Norway](https://api.met.no/weatherapi/documentation) | `User-Agent` header with contact info | Locationforecast. Observations come through [Frost](https://frost.met.no) (free client ID). |
| Nordic/DE day-ahead prices, 15-min | [Energi Data Service](https://www.energidataservice.dk/) | none | Use dataset `DayAheadPrices`. `Elspotprices` stopped on 2025-09-30 when the market moved to 15-minute resolution. |
| Nordic day-ahead, 15-min | [Sähkön hinta nyt](https://xn--shknhintanyt-gcb8w.org/integraatiot/) | none | Finnish site. Listed in public-apis. |
| European prices, load, generation | [ENTSO-E Transparency](https://transparency.entsoe.eu/) | free token (email request) | The most authoritative source, but XML and slower to get started with. Good later "source of truth" comparison. Not in public-apis. |
| Solar / energy-oriented weather | [NASA POWER](https://power.larc.nasa.gov/docs/) | none | Daily/hourly, global. |

## Ingestion notes

- Time zones: hvakosterstrommen returns local time with an offset (`+01:00`/`+02:00`). Open-Meteo returns UTC. Normalize to UTC in Silver.
- DST days have 23 or 25 hourly rows. Don't assert exactly 24.
- Units: prices come per **kWh**, but the context doc uses MWh. Convert in Silver (`× 1000`).
- Weather is per coordinate, so you need a reference table that maps each price area to one or more representative points (`silver.price_area_reference`).
- Prices: allow negative values. Fetch tomorrow's file only after ~13:00 Oslo time; a 404 before then is expected, not an error.
- Weather: recent archive days may be revised, so re-fetching the last few days needs a decision (new Bronze version vs. skip). Fetch history only as far back as it is useful (prices start in 2021).
- Hydrology: weekly → hourly by forward-fill from the **publish time** (Wednesday 13:00), not from `dato_Id`, to avoid leakage in the model.
- Be polite to free APIs: cache in Bronze, don't re-download final data you already have (past prices, NVE weeks), and send an identifying `User-Agent`.
