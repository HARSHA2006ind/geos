# GeoResilience-NER 2.0 — Data Quality & ML Readiness Audit Report

**Evaluated At (UTC):** 2026-11-23 (`backend/app/quality_gate.py`)  
**Study Area:** Dima Hasao District, Assam (Pilot)  
**Overall Production ML Readiness:** **`false` (BLOCKED — 6 Passing, 1 Warning, 6 Blocking Failures across 13 Checks)**

---

## 1. Automated 13-Check Data Quality Gate Summary

| # | Check ID | Status | Blocking? | Verified Measured Evidence |
| :-: | :--- | :---: | :---: | :--- |
| 1 | `coordinate_validity` | **PASS** | Yes | Boundary valid; all `522` landslide records (`104` COOLR + `418` GSI) have valid WGS84 coordinates (`0` invalid). |
| 2 | `geographic_coverage` | **PASS** | Yes | All `15` district `EPSG:32646` rasters cover full Dima Hasao polygon; 30 m core covers Haflong–Jatinga corridor. |
| 3 | `crs_alignment` | **PASS** | Yes | All `12` district 90 m terrain/hydrology/NDVI/OSM grids share identical shape & affine transform in `EPSG:32646`. |
| 4 | `raster_nodata_handling` | **PASS** | Yes | All `16` verified rasters declare explicit nodata (`-9999.0` or `0`), `0` NaN leaks, `99.11%–100.0%` valid coverage. |
| 5 | `rainfall_continuity` | **WARN** | No | Multi-year IMERG `94.14%` complete (`3,439/3,653` days), `0` math errors; `214` missing days strictly `null`; `213/213` 2024 granules confirmed in CMR; not IMD/CWC gauge-validated. |
| 6 | `units_and_physical_ranges` | **PASS** | Yes | DEM `11.64–2065.81 m`, slope `0.0–66.36°`, TWI `3.91–17.91`, clay `24.55–40.31%`, NDVI `-0.599..0.931`, rain `0–203.34 mm/d`. |
| 7 | `duplicate_landslide_events` | **FAIL** | **Yes** | COOLR has `0` duplicates, but GSI Bhusanket Dima Hasao contains **`81` near-duplicate pairs within 50 m** across survey programs requiring event-level polygon consolidation. |
| 8 | `landslide_location_uncertainty` | **FAIL** | **Yes** | **`0` certified slope-scale (`<= 100 m`) polygon/GPS records.** COOLR is 1–50 km coarse; GSI public points (`379`) lack explicit GPS error radius; `GSI/Landslide_Polygon/FeatureServer` returns HTTP 499 Token Required. |
| 9 | `event_date_precision` | **FAIL** | **Yes** | GSI has `95` day-dated records (`85` overlapping IMERG; `162` undated, `103` year-only, `19` month-only). All `45` post-2021 IMERG-overlapping daily records cluster in **only 1 year (`2022`)**, failing the `>= 3` independent storm years requirement. |
| 10 | `feature_timestamps` | **FAIL** | **Yes** | WorldCover 2021 post-dates `65` pre-2021 events; pre-monsoon 2024 NDVI post-dates `91` pre-May-2024 GSI events; 1:50k lithology/faults & dynamic SMAP soil moisture remain missing. |
| 11 | `dataset_licensing_and_provenance` | **PASS** | Yes | All `10` core dataset groups (plus live OSM facilities & experimental GFS) record explicit URLs, CRS, attribution, and timestamps. |
| 12 | `data_leakage_prevention` | **FAIL** | **Yes** | Strict `<= event_date` rainfall windowing (`0` rainfall leakage, `0` synthetic labels), but **`77.8%` transport-corridor sampling bias** causes severe proxy leakage with road/rail covariates (`+0.185` ROC-AUC inflation verified in Phase D). |
| 13 | `train_test_geographic_separation` | **FAIL** | **Yes** | **`0` populated 5 km UTM blocks** with certified error-bounded polygon/GPS labels. Post-2021 IMERG-overlapping unverified GSI points cluster in only `7` blocks from a single 2022 monsoon episode. |

---

## 2. Scientific Enforcement Policy

- Production endpoints (`/api/v1/environment/point`, `/api/v1/hazard/assess`, `/api/v1/ml/infer`, `/api/v1/hazard/simulate`) strictly enforce **`landslide_probability = null`** and **`factor_of_safety = null`**.
- Urban/water nodata pixels in ISRIC SoilGrids 2.0 (such as Haflong town center) return explicit `null` rather than interpolated or invented soil values.
- Missing rainfall observations are preserved as `null` (never coerced to `0.0`).
- Exploratory ML models in `backend/data/experimental/` are permanently segregated from production inference (`validated_for_production: false`, `promoted_to_inference: false`).
