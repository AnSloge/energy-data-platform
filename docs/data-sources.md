# Data sources

Shortlist picked from [public-apis](https://github.com/public-apis/public-apis) (Environment and Weather sections), plus a few Nordic sources that list doesn't include. Every endpoint below returned live data on 2026-10-20.

public-apis is a directory, not a dependency. Use it to find new sources, then add them here.

## Primary (start here)

| Purpose | Source | Auth | Example endpoint | Notes |
|---|---|---|---|---|
| Electricity prices (NO1–NO5), history + day-ahead | [hvakosterstrommen.no](https://www.hvakosterstrommen.no/strompris-api) | none | `https://www.hvakosterstrommen.no/api/v1/prices/2026/10-20_NO2.json` | One file per day and area. NOK and EUR per kWh, hourly, history back to at least 2022. Not in public-apis. |
| Weather history (backfill) | [Open-Meteo Archive](https://open-meteo.com/en/docs/historical-weather-api) | none | `https://archive-api.open-meteo.com/v1/archive?latitude=58.15&longitude=8.0&start_date=2026-10-01&end_date=2026-10-01&hourly=temperature_2m,precipitation,wind_speed_10m` | Hourly, UTC by default. Free for non-commercial use. |
| Weather forecast | [Open-Meteo Forecast](https://open-meteo.com/en/docs) | none | `https://api.open-meteo.com/v1/forecast?latitude=58.15&longitude=8.0&hourly=temperature_2m&forecast_days=7` | Same schema as the archive, so one parser covers both. |
| Hydrology: reservoir filling per price area | [NVE Magasinstatistikk](https://biapi.nve.no/magasinstatistikk/swagger/index.html) | none | `https://biapi.nve.no/magasinstatistikk/api/Magasinstatistikk/HentOffentligDataSisteUke` | Weekly. `omrType=EL`, `omrnr` = price area. Not in public-apis. |

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
- Be polite to free APIs: cache in Bronze, never re-download a day you already have, and send an identifying `User-Agent`.
