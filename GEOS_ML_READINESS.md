# GeoResilience-NER 2.0 — Machine Learning Readiness Assessment

**Assessment Date (UTC):** `2026-11-23`
**Pilot Study Area:** Dima Hasao District, Assam, India
**Can Random Forest and XGBoost Be Trained Responsibly Now?** **NO — HALTED BY STAGE 5 DATA QUALITY GATE.**
**Trained Models Saved / Deployed:** `0` (`landslide_probability` strictly remains `null` in all API responses).

---

## 1. Why Model Training Was Responsibly Stopped

Despite acquiring **19 real NASA COOLR records inside Dima Hasao** (104 in the 50 km buffer) and a **10-year (3,439 valid days) NASA GPM IMERG rainfall archive**, training a 30 m or 90 m Random Forest or XGBoost landslide susceptibility/hazard model right now would be **scientifically invalid** for five concrete, verified reasons:

1. **Zero Slope-Scale Positional Labels (`0 / 30` minimum):** `100%` of the 19 Dima Hasao COOLR records are media-geocoded reports with `1 km–50 km` or `unknown` positional error (`0` `exact` points; `0` polygon scarps). Sampling 30 m/90 m slope, curvature, and aspect pixels at a `5 km` or `25 km` approximate coordinate pairs the positive label with random surrounding terrain—destroying physical signal.
2. **Severe Sample Scarcity & Single-Storm Collapse:** Only `7` of the 19 events fall within the `2015–2024` IMERG archive, and **`5` of those `7` occurred on a single storm date (`2017-04-04`)**. Zero events exist for `2019–2025` (missing the major May 2022 and May 2024 Cyclone Remal failures).
3. **Post-Event Feature Leakage (`ESA WorldCover 2021`):** All 19 COOLR events occurred in `2007–2018`, **before** the 2021 WorldCover composite. Using 2021 land cover to predict 2007–2018 failures leaks post-landslide bare scars and post-event deforestation into training features.
4. **Spatial Reporting Bias & PU-Learning Ambiguity:** Media-reported COOLR points cluster almost exclusively along the Lumding–Badarpur railway and NH-27/NH-54 corridors. Unreported landslides on remote Barail hillslopes mean non-landslide background points must be modeled as **unlabeled background (Positive-Unlabeled framing)**, not guaranteed stable slopes.
5. **Missing First-Order Physical Conditioning Covariates:** Dima Hasao landslides are strongly controlled by **Barail/Disang shale-sandstone contacts**, **Haflong–Disang thrust fault proximity**, **soil clay/hydraulic properties**, **pre-event NDVI**, and **highway/railway cut-slope geometry** — none of which are ingested yet.

---

## 2. Reproducible Feature Pipeline Already Built (Ready Once Gate Passes)

`backend/ml/pipeline.py` already implements and unit-tests the core Stage 6/7 infrastructure, gated strictly behind `evaluate_data_quality_gate()`:

| Candidate Feature | Status | Implementation / Source | Missing-Data / Leakage Policy |
|---|---|---|---|
| **Elevation (m)** | **Ready** | Copernicus DEM GLO-30 (`30 m` core / `90 m` district UTM) | Explicit nodata `-9999.0`; expand 30 m to full district before training |
| **Slope (°)** | **Ready** | Horn (1981) 3×3 finite difference (`EPSG:32646`) | Verified `< 0.01°` against analytical tilted plane |
| **Aspect ($\sin\theta, \cos\theta$)** | **Ready** | Downhill Horn (1981) circular encoding (`backend/ml/pipeline.py`) | Flat pixels (`-1.0`) handled explicitly without wrap-around discontinuity |
| **Plan & Profile Curvature** | **Ready** | Zevenbergen & Thorne (1987) 3×3 quadratic surface | Verified on flat & curved analytical surfaces |
| **Terrain Ruggedness Index (TRI)** | **Ready** | Riley et al. (1999) 3×3 elevation RMS difference | Verified on flat (`0.0`) & rough surfaces |
| **Antecedent Rainfall (1d, 3d, 7d, 15d)** | **Ready (2015–2024-06-01)** | NASA GPM IMERG Late Run (`dima_hasao_rainfall_multiyear.json`) | Strict `<= event_date` lookup; `null` gaps never imputed; needs Earthdata V07B for post-`2024-06-01` |
| **Land Cover** | **Blocked (Epoch Mismatch)** | ESA WorldCover 2021 v200 (`30 m` UTM) | Usable ONLY for `>= 2022` events; require pre-event Sentinel-2 / Landsat annual land cover for older events |
| **Pre-Event NDVI** | **Missing** | Needed: Sentinel-2 / Landsat 8–9 cloud-free pre-monsoon composites | Must strictly pre-date each landslide event |
| **Geological Lithology & Fault Distance** | **Missing** | Needed: GSI Bhukosh 1:50,000 Geology & Structural Lineaments | Requires free GSI Bhukosh registration |
| **Soil Texture & Moisture** | **Missing** | Needed: ISRIC SoilGrids 2.0 + NASA SMAP / ERA5-Land soil moisture | Open WCS / Earthdata ingestion in Phase 2 |
| **Drainage & Road-Cut Proximity** | **Missing** | Needed: DEM flow-accumulation stream network + OSM/PWD/BRO highway & railway polylines | Compute Euclidean distance rasters in `EPSG:32646` |

---

## 3. Mandatory Acceptance Criteria to Unlock Stage 7 Training

Before running Random Forest and XGBoost in `backend/ml/pipeline.py`, all 5 blocking Data Quality Gate checks must turn **PASS**:
1. **Verified High-Precision Positive Labels:** $\ge 30$ (target $150+$) field-validated or high-resolution satellite-mapped landslide scarps/polygons inside Dima Hasao (`location_accuracy <= 100 m`) spanning multiple monsoon years (including 2022–2024) from **GSI Bhukosh** and/or **ISRO/NRSC/NESAC**.
2. **Temporally Aligned Covariates:** Every dynamic or land-cover/NDVI covariate strictly pre-dates each event's timestamp (`0` temporal leakage), plus full-district 30 m terrain derivatives, GSI lithology/fault distance, SoilGrids 2.0, and OSM/DEM drainage & road proximity.
3. **Continuous Rainfall Alignment:** NASA Earthdata `EARTHDATA_TOKEN` configured for IMERG V07B (`2024-06-02` onward) + IMD `0.25°` / AWS gauge bias check.
4. **Spatial & Temporal Validation Design:**
   - **Spatial Block Cross-Validation:** `5 km × 5 km` `EPSG:32646` blocks (`>= 5` populated blocks; never random pixel k-fold).
   - **Temporal Holdout:** Train on earlier monsoon seasons, evaluate on unseen later monsoon season(s) (e.g., 2024 Cyclone Remal).
   - **Evaluation Metrics:** Precision, Recall, **PR-AUC** (primary for imbalanced hazards), ROC-AUC, Brier Score, Expected Calibration Error (ECE), reliability curves, and **SHAP** attributions on spatially held-out folds.
   - **PU-Learning Framing:** Background samples drawn outside a verified exclusion buffer around scarps and explicitly documented as unlabeled background.
