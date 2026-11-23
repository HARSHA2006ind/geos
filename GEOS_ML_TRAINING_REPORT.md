# GeoResilience-NER 2.0 — Machine Learning Training Report

**Execution Script:** `backend/ml/research_benchmark.py`  
**Artifact:** `backend/data/experimental/exploratory_ml_benchmark.json`  
**Run Timestamp (UTC):** `2026-11-23T11:12:20Z`  
**Hardware:** CPU-only (`scikit-learn==1.6.1`, `xgboost-cpu==2.1.4`, `shap==0.46.0`, **0 GPU/CUDA libraries**)  
**Deployment Status:** **`validated_for_production = false` · `promoted_to_inference = false`**

---

## 1. Two-Track Scientific Governance

GeoResilience-NER 2.0 enforces a strict boundary between **production inference** and **exploratory research benchmarking**:

1. **Production Track (BLOCKED):** `evaluate_data_quality_gate()` fails `6/13` blocking checks (`overall_ml_ready: false`). Consequently, `POST /api/v1/ml/infer`, `GET /api/v1/hazard/assess`, and `GET /api/v1/environment/point` strictly return `landslide_probability = null` and `factor_of_safety = null`.
2. **Exploratory Research Track (EXECUTED LIVE):** Benchmarks CPU-only Random Forest (baseline) vs. XGBoost (`hist` tree method) + SHAP (`TreeExplainer`) on the real ingested Dima Hasao rasters and deduplicated GSI Bhusanket point inventory to quantify physical terrain/soil signal, corridor-bias leakage, and empirical antecedent rainfall envelopes.

---

## 2. Dataset Construction & Leakage Controls

- **Positives:** `379` raw in-district GSI Bhusanket points spatially deduplicated at a `100 m` radius -> **`279` deduplicated positives** sampled on valid raster pixels.
- **Unlabeled Background (PU Learning):** **`563` spatially uniform background samples** placed `>= 250 m` from known GSI records (explicitly treated as **Positive-Unlabeled**, never claimed to be confirmed landslide-free ground truth).
- **Spatial Blocks:** **`199` unique `5 km × 5 km` `EPSG:32646` UTM grid blocks** used for 5-fold Geographic `GroupKFold` (`random_seed = 2026`).
- **Temporal Leakage Features Excluded:**
  - `esa_worldcover_2021` (post-dates pre-2021 historical landslides)
  - `sentinel2_premonsoon_2024_ndvi` (post-dates pre-May-2024 landslides)
- **Missing Conditioning Covariates Documented:** GSI 1:50k lithology polygons & thrust-fault lineaments (NGDR/Bhukosh blocked), dynamic SMAP L4 soil moisture.

---

## 3. Model A — Static Susceptibility Exploratory Benchmark (16 Clean Terrain + Hydrology + SoilGrids Features)

Clean feature set: `elevation_m`, `slope_deg`, `aspect_sin`, `aspect_cos`, `profile_curvature`, `plan_curvature`, `tri_m`, `twi`, `log1p_flow_acc`, `dist_drainage_m`, `soil_clay_0_5cm`, `soil_sand_0_5cm`, `soil_silt_0_5cm`, `soil_bdod_0_5cm`, `soil_cfvo_0_5cm`, `soil_soc_0_5cm`.

| Model | CV Runtime (CPU) | OOF ROC-AUC | OOF PR-AUC | Precision @0.5 | Recall @0.5 | F1 @0.5 | Brier Score | ECE |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest (Baseline)** | `2.404 s` | `0.7588` | `0.5415` | `0.6128` | `0.5161` | `0.5603` | `0.1857` | `0.0696` |
| **XGBoost CPU (`hist` Candidate)** | `0.903 s` | `0.7623` | `0.5678` | `0.6067` | `0.5197` | `0.5598` | `0.1865` | `0.0506` |

### Top SHAP TreeExplainer Feature Attributions (Clean Ablation)
- **Random Forest (Mean |SHAP| probability scale):** `tri_m` (`0.07408`), `elevation_m` (`0.05102`), `soil_soc_0_5cm` (`0.04791`), `slope_deg` (`0.04272`), `soil_sand_0_5cm` (`0.03038`), `soil_cfvo_0_5cm` (`0.02430`), `soil_clay_0_5cm` (`0.02316`).
- **XGBoost CPU (Mean |SHAP| log-odds scale):** `soil_soc_0_5cm` (`0.56262`), `tri_m` (`0.54617`), `elevation_m` (`0.54369`), `soil_clay_0_5cm` (`0.30586`), `soil_cfvo_0_5cm` (`0.21973`), `soil_silt_0_5cm` (`0.18571`), `slope_deg` (`0.17097`).
- *Disclaimer:* SHAP values measure statistical attribution inside this exploratory PU benchmark only — they are **not** physically causal geotechnical shear-strength parameters or Factor of Safety inputs.

---

## 4. Corridor-Bias Proxy Leakage Diagnostic (Why Road/Rail Distances Are Blocked)

Adding `dist_road_m` + `dist_railway_m` to the exact same 5-fold geographic CV produced:
- **Random Forest:** ROC-AUC jumped from `0.7588` -> **`0.9444`** (`+0.1856` artificial inflation); `dist_road_m` dominated SHAP (`0.22316`).
- **XGBoost CPU:** ROC-AUC jumped from `0.7623` -> **`0.9468`** (`+0.1845` artificial inflation); `dist_road_m` dominated SHAP (`2.29719`).

**Conclusion:** Because `77.8%` of public GSI Bhusanket records were surveyed along NH-27 and the Lumding–Badarpur railway corridor, unstratified transport-distance features cause massive survey-accessibility leakage. This quantitatively validates why `data_leakage_prevention` MUST remain a blocking failure in the production Quality Gate.

---

## 5. Model B — Empirical Antecedent Rainfall Threshold Analysis (Non-Operational)

Across `95` day-dated GSI records (`85` overlapping valid IMERG, spanning `14` unique calendar event days) vs. `1,675` monsoon non-event days (`2015–2024-06-01`):

| Antecedent Window | Event-Day Median (p75 / p90 / Max) | Monsoon Non-Event Median (p75 / p90 / Max) |
| :--- | :---: | :---: |
| **1-day (24h)** | `49.90 mm` (`70.38` / `78.49` / `83.80 mm`) | `4.37 mm` (`11.14` / `21.78` / `203.26 mm`) |
| **3-day (72h)** | `127.18 mm` (`181.49` / `251.45` / `347.48 mm`) | `19.06 mm` (`33.38` / `58.10` / `478.38 mm`) |
| **7-day** | `212.67 mm` (`253.22` / `331.82` / `407.10 mm`) | `50.16 mm` (`76.87` / `115.94` / `578.22 mm`) |
| **15-day** | `287.31 mm` (`321.11` / `420.01` / `435.51 mm`) | — |

Dynamic rainfall-trigger probability modeling remains **BLOCKED** pending NASA Earthdata Login IMERG V07B 2024–2026 backfill, IMD/CWC rain-gauge calibration, and multi-year dated landslide inventory expansion (`>= 3` independent storm years).
