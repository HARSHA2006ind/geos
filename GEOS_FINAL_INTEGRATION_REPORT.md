# GeoResilience-NER 2.0 — Final Staging, Integration & Release Validation Report

**Study Area:** Dima Hasao District, Assam (Pilot) & 8-State Northeast India Architecture  
**Validation Date (UTC):** 2026-11-23  
**Runtime Topology Verified:** React/Vite (`:3000`) → Express Gateway → Python FastAPI/Uvicorn (`:8001`) → PostgreSQL 15.20 + PostGIS 3.3.2 (`:5432`)

---

## 1. Defects Discovered & Fixed During Release Validation

| Component | Real Defect Found | Resolution Implemented |
|---|---|---|
| `backend/app/services/monitoring_service.py` | Called non-existent `run_dynamical_gfs_eval(output_path=...)`, causing `--refresh-live-gfs` to fail silently inside `except Exception`; stored `temp_2m_max_c` into `temp_2m_mean_c`; set identical `valid_time_utc` for 24h/48h/72h horizons. | Switched to `evaluate_dynamical_gfs_dima_hasao(forecast_hours=72, out_dir=...)`, computed true hourly mean 2m temperature, and set horizon-offset `valid_time_utc`. |
| `backend/app/services/hazard_engine.py` | `load_latest_gfs_forecast()` looked for `lead_steps`/`lead_hour` instead of `hourly_forecast`/`lead_hours`, leaving `rain_48h_outlook_mm` permanently `null`. | Updated parser to read `hourly_forecast`/`lead_hours` and `t2m_mean_c`, restoring real `rain_48h_outlook_mm` (`9.978 mm`) and `temp_2m_mean_c` (`18.41 °C`). |
| `backend/experimental/nvidia_weather_eval/dynamical_gfs_eval.py` | `ReadOnlyHttpxZarrStore` lacked HTTP retry logic on transient network/5xx/429 responses and omitted `t2m_mean_c` summary output. | Added 3-attempt bounded exponential backoff retry (`0.5s`, `1.0s`) for transport/timeout/429/5xx errors and added `forecast_48h_mean_rain_mm` + `t2m_mean_c`. |
| `backend/ingestion/run_monitoring_cycle.py` | Ignored `DATABASE_URL` (`settings.database_url`) and hardcoded local SQLite unless `--db-url` was passed, breaking Docker Compose `monitor` targeting PostGIS. | Updated CLI to probe and use `settings.database_url` (PostGIS) automatically with graceful SQLite fallback when Postgres is unreachable. |
| `backend/app/config.py` | Default `database_url` pointed to DB name `georesilience` while `docker-compose.yml` and `backend/.env.example` configure `geos_ner`. | Aligned default DB name to `geos_ner`. |
| `backend/ingestion/sync_postgis.py` | No unified loader existed to persist all verified pilot GeoJSONs, datasets, provenance, GSI records, OSM transport/facilities, rainfall, and exploratory benchmarks into PostGIS. | Created idempotent `sync_postgis.py` syncing all 9 datasets, 522 landslides, 3,218 OSM assets, 3,653 IMERG days, 2 exploratory models, and 8 NER states. |
| `backend/app/routers_v2.py` & `server.ts` | Gemini upstream HTTP status codes were masked as `HTTPStatusError`; Express proxy aborted at 15s and dropped upstream `X-Request-ID`. | Added single bounded retry on Gemini 429/503, surfaced safe `upstream_status`/`upstream_message` (zero key/header leakage), extended proxy timeout to 30s, and forwarded `X-Request-ID`. |
| `src/components/layout/Sidebar.tsx`, `Header.tsx`, `App.tsx` | Fixed `w-64` sidebar remained visible on `<640px` mobile viewports, compressing main workspace content horizontally. | Converted mobile sidebar to a slide-over drawer (`md:relative`, fixed `<md`) with Header hamburger toggle and backdrop close button. |

---

## 2. Strict Categorization of System Capabilities

### A. Verified Working (End-to-End Against Live PostGIS & FastAPI)
- **Full Geospatial Stack:** Copernicus DEM GLO-30 (`30m` corridor + `90m` UTM46N district grid), Horn slope/aspect, profile/plan curvature, TRI, TWI, flow accumulation, drainage distance, ISRIC SoilGrids 2.0 (7 layers), ESA WorldCover 2021, Sentinel-2 L2A pre-monsoon 2024 NDVI, OSM 619 facilities + 2,599 transport segments + road/rail distance rasters (`23` GeoTIFFs verified).
- **Real PostgreSQL 15.20 + PostGIS 3.3.2 Integration:** All 19 application tables (+ `alembic_version`, `spatial_ref_sys`), Alembic `0001 -> 0003` upgrade/downgrade roundtrip, 5 GiST spatial indexes, verified `ST_MultiPolygon` (`4,884.61 km²`), `ST_Contains` (`379` GSI Bhusanket records inside Dima Hasao polygon), `ST_DWithin` 5 km facility queries, real `pg_dump`/`psql` backup + SHA-256 restore verification, and `pg_ctl restart` + server restart persistence.
- **Automated NOAA GFS CPU Monitoring Pipeline:** Live HTTPS Range Zarr v3 fetch from `data.dynamical.org` (`init_time_utc: 2026-11-23T00:00:00+00:00`, `24h: 8.36 mm`, `48h: 9.978 mm`, `72h: 9.978 mm`, zero GPU required) persisted to `weather_forecasts` and `monitoring_runs` in PostGIS.
- **Auth, RBAC, Field Reporting & Experimental Alert Workflow:** First-run `claim-admin` lock (`409`), `scrypt` password hashing, in-memory HMAC-SHA256 Bearer tokens, role enforcement (`401`/`403`), real multipart PNG upload with magic-byte + `5 MB` cap (`422` oversize rejection) + SHA-256 confinement, analyst verification, and experimental draft alert dry-run dispatch (`DRY_RUN_NO_EXTERNAL_DISPATCH`).
- **Automated Test Suites:** `38/38` backend `pytest` tests and `9/9` frontend `vitest` tests + `tsc --noEmit` + Vite production build (`npm run build`) passed.

### B. Fixture-Only / Legacy Prototype Views
- Legacy tabs in the pre-existing UI (`CommandCenter`, `RiskMapPage`, `RiskAnalysisPage`, `WhatIfSimulationPage`, `ImpactResponsePage`, `HistoricalAnalysisPage`) retain curated NER regional fixture cards alongside `src/data/mockData.ts` (`calculateLocationRisk`), clearly distinct from the verified **`GEOS 2.0 Research Hub`** (`/api/v1/*`).

### C. Staging-Only (Container Runtime Constraints)
- **Native PostGIS vs. Docker Compose:** Because the `docker` CLI/daemon is absent in this validation sandbox, live PostgreSQL 15.20 + PostGIS 3.3.2 runs natively via `pg_ctl` on `127.0.0.1:5432` rather than `docker compose up`. `backend/docker-compose.yml` and `backend/Caddyfile` were statically audited for Ubuntu Linux 4 vCPU / 8 GB RAM hosts.
- **Sandbox Hardware:** Measured host is `2 vCPU`, `4.0 GiB RAM`, `0 B Swap`, `756 GB` filesystem vs. target `4 vCPU / 8 GB RAM / 20 GB SSD`.
- **Node Fallback Bridge:** When FastAPI `:8001` is stopped in Node-only environments, `server.ts` serves verified GeoTIFF/JSON artifacts for read-only `/api/v1/*` routes (`503` for DB-backed auth/reports/alerts).

### D. Scientifically Unvalidated (Explicitly Gated)
- **Random Forest / XGBoost Exploratory Benchmarks:** Trained strictly under Positive-Unlabeled (PU) assumptions on unverified corridor-biased GSI point centroids (`validated_for_production: false`, `promoted_to_inference: false`). Production endpoints return `landslide_probability: null` and `factor_of_safety: null`.
- **Dynamic Hazard Priority Tiers & What-If Simulator:** Transparent IMD 24h heavy rainfall + DEM slope (`>= 25°`) envelope rules (`EXPERIMENTAL_UNVALIDATED_ENVELOPE`), explicitly NOT landslide probabilities.

### E. External Blockers
1. **NASA Earthdata Login (`NASA_EARTHDATA_TOKEN`):** Required to backfill the `2024-06-02..2024-12-31` IMERG V07B/V07C gap (`214` null days).
2. **GSI Polygon FeatureServer Token (`HTTP 499`):** `GSI/Landslide_Polygon/FeatureServer` remains token-gated, leaving only point centroids without error radii.
3. **Geological Survey 1:50k Lithology/Faults & NASA SMAP L4 Soil Moisture & IMD/CWC Gauges:** Not publicly exposed via unauthenticated APIs.
4. **Live Gemini `gemini-4-hydrogen` Upstream Capacity Spike (`HTTP 503`):** During validation, Google `generativelanguage.googleapis.com` returned transient HTTP `503` ("high demand") for `gemini-4-hydrogen`, cleanly surfaced as HTTP `502` with full grounded backend evidence; bad key (`502`/upstream `400`), unset key (`503`), invalid input (`422`), rate limit (`429`), and prompt injection (`400`) all behaved as designed.
5. **GitHub Remote Push Authentication:** Container lacks authenticated GitHub push credentials (`GITHUB_TOKEN`/SSH key); preserved locally via verified Git branch commit, `.bundle`, and `.tar.gz` exports.

### F. Production Deployment Blockers
- **6 Blocking Failures in 13-Check Scientific Data Quality Gate:** `duplicate_landslide_events` (81 GSI near-duplicates <=50m), `landslide_location_uncertainty` (0 certified <=100m polygon/GPS labels), `event_date_precision` (single 2022 post-2021 year overlapping valid IMERG), `feature_timestamps` (missing 1:50k lithology, SMAP moisture, pre-2021 land cover), `data_leakage_prevention` (77.8% road/rail bias), and `train_test_geographic_separation`.
- **Operational Prerequisites Before Public Launch:** Configure unique `GEOS_AUTH_SECRET`, claim initial admin account (`POST /api/v1/auth/claim-admin`), run behind `Caddyfile` automatic TLS (`backend/docker-compose.yml`), and upgrade or isolate Node `express` dev dependencies (`bun audit`: 11 transitive advisories).
