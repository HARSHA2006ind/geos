# GeoResilience-NER 2.0 — Continuous Monitoring Reliability Report

**Verified Date:** 2026-11-23  
**Database Engine:** PostgreSQL 15.20 + PostGIS 3.3.2 (`monitoring_runs` & `weather_forecasts` tables)

---

## 1. Multi-Cycle Execution Verification

Four consecutive monitoring cycles were executed and verified in PostgreSQL (`monitoring_runs` IDs `1..4`):

| Run ID | Mode | Started (UTC) | Completed (UTC) | Status | IMERG Latest Date | IMERG Stale | NOAA GFS Init (UTC) | GFS Stale | Error Message |
|---:|---|---|---|---|---|---|---|---|---|
| `1` | Live GFS Zarr v3 | `2026-11-23T13:29:09Z` | `2026-11-23T13:29:21Z` | `partial_stale` | `2024-06-01` | `true` | `2026-11-23T00:00:00+00:00` | `false` | `null` |
| `2` | Cached freshness | `2026-11-23T14:01:48Z` | `2026-11-23T14:01:48Z` | `partial_stale` | `2024-06-01` | `true` | `2026-11-23T00:00:00+00:00` | `false` | `null` |
| `3` | Live GFS Zarr v3 (`--refresh-live-gfs`) | `2026-11-23T14:01:49Z` | `2026-11-23T14:02:01Z` | `partial_stale` | `2024-06-01` | `true` | `2026-11-23T00:00:00+00:00` | `false` | `null` |
| `4` | Idempotent cached repeat | `2026-11-23T14:02:03Z` | `2026-11-23T14:02:03Z` | `partial_stale` | `2024-06-01` | `true` | `2026-11-23T00:00:00+00:00` | `false` | `null` |

---

## 2. Scientific & Operational Reliability Invariants Verified

1. **Timestamp Ordering & History Persistence:** Each run records distinct monotonic `id`, `started_at`, and `completed_at` timestamps in `monitoring_runs`.
2. **Weather Forecast Deduplication (Zero Duplicates Across Repeated Runs):**
   - Across all 4 cycles (`run_id` 1–4), `SELECT count(*), count(distinct (provider, init_time_utc, horizon_hours)) FROM weather_forecasts` returned **`total = 3`, `unique_tuples = 3`**:
     - `24h` horizon: `8.36 mm` (`data_role = experimental_forecast_only`)
     - `48h` horizon: `9.978 mm` (`data_role = experimental_forecast_only`)
     - `72h` horizon: `9.978 mm` (`data_role = experimental_forecast_only`)
3. **Observed Rainfall vs Experimental Forecast Separation:**
   - **Observed Precipitation (`NASA GPM IMERG`):** Strictly labeled as archival measured satellite estimates ending `2024-06-01` with `observed_rainfall_stale = true` (awaiting NASA Earthdata Login token for 2024–2026 granules). **214 missing days out of 3,653 total days remain strictly `null` (`None`), never coerced to `0.0`.**
   - **Experimental Forecast (`NOAA GFS 0.25°` via Dynamical.org Zarr v3):** Strictly tagged `experimental_forecast_only` and never mixed into observed rainfall totals or issued as official warnings.
4. **Failure Logging & Cached Forecast Retention (Automated Test `test_monitoring_cycle_failure_recovery_idempotency_and_stale_expiration`):**
   - Simulated upstream NOAA Zarr failure logs the exact error on `MonitoringRun.error_message`, keeps `status = "partial_stale"`, and preserves existing `weather_forecasts` rows without wiping valid cached outlooks.
5. **Stale Forecast Expiration (>24 Hours):**
   - `load_latest_gfs_forecast()` computes `forecast_age_hours` dynamically against current UTC time; when `init_time_utc` is >24 hours old, `is_stale = true` and `forecast_stale = true` are set automatically.
6. **No False Public Warnings:** Monitoring cycles record internal operational freshness only and never emit official public alerts (`official_government_warning: false`).
