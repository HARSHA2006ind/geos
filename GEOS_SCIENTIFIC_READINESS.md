# GeoResilience-NER 2.0 — Scientific Readiness & Quality Gate Assessment

**Study Area:** Dima Hasao District, Assam  
**Quality Gate Decision:** **`BLOCKED — Halt ML model training and keep landslide_probability = null`**  
**Check Summary:** **`6 / 13 PASS` · `1 WARN` · `6 FAIL (Blocking)` · `overall_ml_ready: false`**

---

## 1. Automated 13-Check Scientific Quality Gate Results

| # | Check ID | Status | Key Evidence |
|---|---|---|---|
| 1 | `coordinate_validity` | **PASS** | `104` NASA COOLR + `418` GSI Bhusanket records + Dima Hasao polygon pass WGS84 bounds |
| 2 | `geographic_coverage` | **PASS** | All `15` district `EPSG:32646` rasters cover Dima Hasao District |
| 3 | `crs_alignment` | **PASS** | All `11` derivative 90 m terrain/hydrology/NDVI/OSM grids share identical affine transforms |
| 4 | `raster_nodata_handling` | **PASS** | All `16` checked pilot rasters declare explicit nodata (`>= 99%` valid coverage, `0` NaN leaks) |
| 5 | `rainfall_continuity` | **WARN** | `94.14%` completeness (`3,439 / 3,653` days), `0` aggregation errors; `214` missing days (`2024-06-02..2024-12-31`) preserved as `null` pending Earthdata auth; NOT IMD/CWC gauge-validated |
| 6 | `units_and_physical_ranges` | **PASS** | Elevation, slope, aspect, curvatures, TRI, TWI, distances, SoilGrids 2.0, NDVI (`[-0.599, 0.931]`), WorldCover, and daily IMERG rainfall verified in bounds |
| 7 | `duplicate_landslide_events` | **FAIL (Blocking)** | COOLR has `0` duplicates, but GSI Bhusanket contains **`81` spatial near-duplicate pairs <= 50 m** across survey tiers |
| 8 | `landslide_location_uncertainty` | **FAIL (Blocking)** | **`0` certified slope-scale (`<= 100 m`) polygon/GPS labels.** COOLR points are `1–50 km`; GSI public points lack GPS error radii while polygons (`FeatureServer`) return HTTP `499 Token Required` |
| 9 | `event_date_precision` | **FAIL (Blocking)** | `95` GSI day-level records inside Dima Hasao (`49` overlapping valid IMERG), but **all `13` post-2021 IMERG-overlapping daily events fall in `1` year (`2022`)**, failing `>= 3` independent storm years |
| 10 | `feature_timestamps` | **FAIL (Blocking)** | WorldCover 2021 post-dates `32` pre-2021 events; 2024 NDVI post-dates `93` pre-May-2024 events; missing 1:50k lithology/fault GIS, dynamic SMAP L4 soil moisture, and IMD/CWC rain gauges |
| 11 | `dataset_licensing_and_provenance` | **PASS** | All `10` dataset groups carry source URLs, CRS, attribution, and timestamps |
| 12 | `data_leakage_prevention` | **FAIL (Blocking)** | **`77.8%` transport-corridor sampling bias** in GSI records creates proxy-leakage risk with OSM road/rail proximity unless paired with unbiased mapping |
| 13 | `train_test_geographic_separation` | **FAIL (Blocking)** | `0` populated 5 km blocks contain certified error-bounded polygon labels (`2022` daily events span only `4` blocks) |

---

## 2. Safeguards Enforced Across API, Database & UI

- **Strict Null Probability Guarantee:** `landslide_probability: null` and `factor_of_safety: null` enforced across `/api/v1/hazard/assess`, `/api/v1/hazard/simulate`, `/api/v1/ml/infer`, `/api/v1/assistant/explain`, and persisted `experimental_alerts`.
- **Exploratory Benchmark Segregation:** Random Forest and XGBoost + SHAP experiments (`DimaHasao-RF-Exploratory-PU`, `DimaHasao-XGBoost-Exploratory-PU`) remain flagged `track = "exploratory_research"`, `validated_for_production = false`, `promoted_to_inference = false` in `exploratory_ml_benchmark.json` and PostgreSQL `model_registry`, explicitly warning against PU sampling & road-bias ROC-AUC inflation.
- **Observed vs. Forecast Meteorological Separation:**
  - *Observed Historical:* NASA GPM IMERG multi-year archive (`latest_valid_date: 2024-06-01`, `observed_rainfall_stale: true`).
  - *Experimental NWP Forecast:* Dynamical.org NOAA GFS `0.25°` Zarr v3 (`rain_24h_outlook_mm: 8.36`, `rain_48h_outlook_mm: 9.978`, `rain_72h_outlook_mm: 9.978`), converting `kg m⁻² s⁻¹ * 3600 = mm/h`, retaining lead-hour `0` as `null`, and isolated in `weather_forecasts` (`data_role = "experimental_forecast_only"`).
