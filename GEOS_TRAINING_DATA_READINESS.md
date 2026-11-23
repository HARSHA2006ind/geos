# GeoResilience-NER 2.0 — Training Data Readiness & Scientific Quality Gate Report (Stage 9)

**Evaluation Date (UTC):** 2026-11-23  
**Study Area:** Dima Hasao District, Assam, India (Pilot)  
**Machine Learning Readiness Verdict:** **`overall_ml_ready: false`**  
**ML Training Executed:** **`false`** (`DataQualityGateBlockedError` raised automatically)  
**Operational Probability Output:** **`landslide_probability: null`** (strictly preserved; zero fabricated predictions)

---

## 1. Stage 9 Scientific Feature Acquisition Summary (100% Authentic Datasets)

All newly ingested rasters were derived directly from verified remote-sensing/geospatial sources and audited in `backend/data/pilot/spatial_data_quality_inventory.json`:

| Feature Group | Source & License | CRS & Grid | Valid Pixels | Verified Physical Range (Dima Hasao) | Temporal Validity |
| :--- | :--- | :--- | :---: | :--- | :--- |
| **Base Topography** | Copernicus DEM GLO-30 (ESA/Airbus) | `EPSG:32646` (1114x1106, 90 m) + 30 m core | 99.43% | Elev `25–1868 m`, Slope `0–61.5°`, Aspect `-1–360°` | Static (2011–2015) — pre-event valid |
| **Geomorphometry & Hydrology (Stage 9)** | Derived from Copernicus DEM (`derive_full_district_dem_features.py`) | `EPSG:32646` (1114x1106 exact DEM grid) | 99.11% | Profile curv `-5.14..+15.84`, Plan curv `-7.67..+5.08` (1/100m), TRI `0–2239.9 m` (mean `54.55 m`), TWI `3.91–17.91` (mean `7.46`), Drainage dist `0–3444.8 m` (mean `495.9 m`) | Static — pre-event valid |
| **Soil Properties (Stage 9)** | ISRIC SoilGrids 2.0 WCS 2.0 (`CC-BY 4.0`) | `EPSG:32646` (250 m metric) | 99.57% | Clay 0–5 cm `24.5–40.3%` (mean `31.48%`), Clay 15–30 cm `26.2–42.5%` (mean `34.57%`), Sand `23.8–45.0%` (`32.97%`), Silt `27.1–43.3%` (`35.56%`; texture sum `= 100.00%`), Bulk density `0.93–1.31 g/cm³` (`1.152`), Coarse fragments `6.9–27.2%`, SOC `18.0–92.4 g/kg` | Static pedological prior (NOT dynamic soil moisture) |
| **Pre-Event Vegetation NDVI (Stage 9)** | Copernicus Sentinel-2 L2A via Element84 Earth Search STAC (8 low-cloud scenes Jan–Apr 2024, ESA SCL cloud mask) | `EPSG:32646` (1114x1106 exact DEM grid) | 99.58% | Calibrated BOA NDVI `-0.599..+0.931` (mean `0.657`, `p10=0.450`, `p90=0.841`; mean `1.98` clear obs/pixel) | Pre-monsoon 2024 ONLY — valid pre-event for post-Apr 2024 events; NOT valid for 2014–2022 events |
| **Land Cover** | ESA WorldCover 2021 v200 (`CC-BY 4.0`) | `EPSG:32646` (30 m) | 99.43% | Valid ESA classes `[10, 20, 30, 40, 50, 60, 80, 90]` | Epoch 2021 ONLY — post-dates 2007–2020 events |
| **Transport Corridor Cuts (Stage 9)** | OpenStreetMap Overpass API (`ODbL 1.0`) — **2,212 road ways & 392 railway ways** | `EPSG:32646` (1114x1106 exact DEM grid) | 99.43% | Road dist `0–17,573 m` (median `1,800 m`); Railway dist `0–58,648 m` (median `15,965 m`) | Current OSM snapshot — CAUTION: strong collinearity with GSI corridor bias |
| **Precipitation Archive** | NASA GPM IMERG (`2015–2024-06-01` ingested; `2024-06-02..2026-11-22` CMR cataloged) | District daily `0.1°` | 94.14% (`3,439/3,653`) | `0.0–254.9 mm/day`; 214 missing days preserved strictly as `null` | Needs Earthdata token for 2024 gap + IMD/CWC gauges for validation |
| **Landslide Inventories** | NASA COOLR (`19` in-polygon) + **GSI Bhusanket Public API (`379` in-polygon, Stage 9)** | WGS84 points (`EPSG:4326`) | 100% valid coords | COOLR: `0 <= 100 m`; GSI: `95` day-dated, `19` month, `103` year, `162` undated; `81` near-dup pairs `<=50 m`; `77.8%` road/rail bias | Point centroids only; `GSI/Landslide_Polygon` token-gated HTTP 499 |

---

## 2. Re-Evaluated 13-Check Scientific Data Quality Gate (No Check Weakened)

Result: **6 PASS, 1 WARN, 6 BLOCKING FAILURES -> `overall_ml_ready: false`**

| # | Check ID | Status | Blocking? | Stage 9 Verified Finding |
| :-: | :--- | :---: | :---: | :--- |
| 1 | `coordinate_validity` | **PASS** | Yes | Boundary + all `522` records (`104` COOLR + `418` GSI) have valid WGS84 coordinates. |
| 2 | `geographic_coverage` | **PASS** | Yes | All 15 district `EPSG:32646` rasters completely cover Dima Hasao District bounds. |
| 3 | `crs_alignment` | **PASS** | Yes | All 12 district 90 m terrain/hydrology/NDVI/OSM grids share identical `(1106, 1114)` shape & affine transform. |
| 4 | `raster_nodata_handling` | **PASS** | Yes | All 16 verified rasters declare explicit nodata, 0 NaN leakage, and `>= 99.11%` valid pixels. |
| 5 | `rainfall_continuity` | **WARN** | No | `94.14%` completeness, 0 aggregation errors, 214 missing days strictly `null`; 213/213 2024 gap granules verified in NASA CMR awaiting Earthdata Login; IMD/CWC gauge validation = `false`. |
| 6 | `units_and_physical_ranges` | **PASS** | Yes | Elevation, slope, aspect, curvature, TRI, TWI, drainage/road/rail distances, SoilGrids 2.0, calibrated NDVI, WorldCover, and rainfall all pass physical checks. |
| 7 | `duplicate_landslide_events` | **FAIL** | **Yes** | COOLR has 0 remaining duplicates, but raw GSI Bhusanket contains **81 spatial near-duplicate pairs within 50 m** across overlapping `Macro-Scale`/`PDLS`/`LEWS`/`Mobile app` surveys requiring polygon consolidation. |
| 8 | `landslide_location_uncertainty` | **FAIL** | **Yes** | **0 certified error-bounded polygon/GPS labels** (`<=100 m`). COOLR is 1–50 km coarse; GSI Bhusanket public `GetData` returns point centroids only without an explicit horizontal error radius (`47` records at `<= 2 dp > 1 km`), while `GSI/Landslide_Polygon/FeatureServer` is HTTP 499 Token Required. |
| 9 | `event_date_precision` | **FAIL** | **Yes** | Although GSI Bhusanket adds `95` day-dated records (`85` overlapping `2015–2024-06-01` IMERG), **all 45 post-2021 IMERG-overlapping day-dated events occur in ONLY 1 year (`2022`, 7 dates)** — failing multi-year storm independence (`>= 3` monsoon years). 2024 GSI entries lack exact day dates, and 2025–2026 entries fall in the unauthenticated IMERG gap. |
| 10 | `feature_timestamps` | **FAIL** | **Yes** | WorldCover 2021 post-dates pre-2021 events; Pre-Monsoon 2024 NDVI post-dates pre-May-2024 events; wall-to-wall 1:50k lithology/thrust faults, SMAP L4 dynamic soil moisture, and 2015–2023 matched pre-event NDVI remain missing. |
| 11 | `dataset_licensing_and_provenance` | **PASS** | Yes | All 10 ingested dataset groups record source URLs, licenses, CRS, attribution, and timestamps. |
| 12 | `data_leakage_prevention` | **FAIL** | **Yes** | Strict pre-event rainfall windowing verified (0 synthetic labels), but **77.8% GSI transport-corridor bias** creates severe proxy-leakage risk into OSM road/railway proximity if paired with naive district background negatives, alongside temporal epoch mismatches. |
| 13 | `train_test_geographic_separation` | **FAIL** | **Yes** | 0 certified spatial blocks; even unverified post-2021 GSI daily points cluster in only 7 5-km corridor blocks from one 2022 storm episode — inadequate for out-of-corridor & cross-year generalization. |

---

## 3. Sample-Size Sufficiency Policy (`30` and `150` Events Are Provisional Only)

> **Explicit Scientific Policy:** Numeric event thresholds such as **30 events** (provisional pilot minimum) or **150 events** (provisional multi-year research milestone) are **NEVER scientifically sufficient by themselves** to authorize ML training or early-warning deployment.

In fact, Stage 9 provides a textbook empirical proof of why raw counts can mislead:
- Dima Hasao now has **379 official GSI point records** (well above 150!) and **45 post-2021 IMERG-overlapping day-dated records** (above 30!).
- Yet training a Random Forest or XGBoost model on those raw points today would still produce a **scientifically invalid model** because:
  1. **Representativeness & Sampling Bias:** `77.8%` of GSI points lie along NH-27/NH-54E and the Lumding–Badarpur railway; a naive binary classifier would learn *"closeness to road = landslide"* rather than true forested hillslope instability.
  2. **Temporal Independence & Event Timing:** All `45` post-2021 valid IMERG-overlapping day-dated events originate from **one single monsoon season (2022, 7 dates)** — providing zero temporal holdout generalization across independent storm years (e.g., 2017 vs 2022 vs 2024 Cyclone Remal).
  3. **Geometry & Positional Uncertainty:** Point centroids without certified GPS error bounds conflate head-scarp initiation zones (steep upper slope) with debris deposition zones (flat road/valley floor) and leave `81` near-duplicate pairs `<= 50 m`.
  4. **Missing Physical Conditioning Factors:** Wall-to-wall 1:50k lithology (Barail/Disang/Surma shale-sandstone contacts), thrust faults (Haflong/Disang thrusts), dynamic antecedent soil moisture (SMAP L4), and event-year-matched pre-event NDVI are still required.

---

## 4. Remaining Actions Required to Unblock ML Research Training

1. **Close the IMERG V07B 2024 Gap & Add SMAP L4:** Run `fetch_imerg_v07_earthdata.py` with a free NASA Earthdata Login token (`EARTHDATA_TOKEN`) and ingest SMAP L4 volumetric soil moisture.
2. **Acquire Unbiased Event Polygons & 1:50k Geology:** Execute the formal GSI / NRSC / NESAC data request (`GEOS_GSI_ACCESS_FINDINGS.md`) for `GSI/Landslide_Polygon`, multi-temporal satellite-mapped forested-slope polygons (2017, 2022, 2024), and 1:50k lithology/fault shapefiles.
3. **Generate Event-Matched Pre-Event Annual NDVI (2016–2023):** Extend `fetch_preevent_ndvi.py` across each target monsoon year's pre-monsoon dry window so every event uses strictly pre-event vegetation state.
4. **Apply Bias-Aware Positive-Unlabeled / Corridor-Stratified Sampling & Spatial-Temporal Block CV:** Deduplicate event clusters, separate train/validation/test both geographically (`>= 5` independent 5 km watershed blocks) and temporally (leave-one-monsoon-year-out), and validate rainfall thresholds against IMD/CWC Dima Hasao gauges.
