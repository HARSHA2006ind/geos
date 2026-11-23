# GeoResilience-NER 2.0 — Model Validation & Calibration Report

**Validation Scheme:** 5-Fold Geographic Spatial-Block `GroupKFold` (`5 km × 5 km` `EPSG:32646` UTM blocks, `199` unique blocks)  
**Production Promotion Decision:** **REJECTED / BLOCKED** (`validated_for_production = false`, `promoted_to_inference = false`)

---

## 1. Fold-by-Fold Spatial Generalization (Clean Terrain + Hydrology + SoilGrids)

| Model | Fold 1 AUC | Fold 2 AUC | Fold 3 AUC | Fold 4 AUC | Fold 5 AUC | Fold Mean ± Std | OOF PR-AUC |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Random Forest Baseline** | `0.8371` | `0.7357` | `0.7449` | `0.7338` | `0.7687` | `0.7640 ± 0.0386` | `0.5415` |
| **XGBoost CPU Candidate** | `0.8417` | `0.7309` | `0.7255` | `0.7192` | `0.7895` | `0.7614 ± 0.0474` | `0.5678` |

### Confusion Matrices (Threshold `0.50`, `n = 842` samples = `279` deduplicated GSI positives + `563` PU background)
- **Random Forest:** `TN = 472`, `FP = 91`, `FN = 135`, `TP = 144` (Recall `51.61%`, Precision `61.28%`, F1 `0.5603`)
- **XGBoost CPU:** `TN = 469`, `FP = 94`, `FN = 134`, `TP = 145` (Recall `51.97%`, Precision `60.67%`, F1 `0.5598`)

---

## 2. Calibration Reliability Assessment

| Quantile Bin | RF Mean Pred | RF Frac Pos | XGB Mean Pred | XGB Frac Pos |
| :-: | :---: | :---: | :---: | :---: |
| Bin 1 | `0.0982` | `0.0496` | `0.0362` | `0.0638` |
| Bin 2 | `0.2191` | `0.1643` | `0.1082` | `0.1429` |
| Bin 3 | `0.3261` | `0.2643` | `0.2127` | `0.2643` |
| Bin 4 | `0.4225` | `0.3429` | `0.3599` | `0.3571` |
| Bin 5 | `0.5249` | `0.5571` | `0.5485` | `0.5357` |
| Bin 6 | `0.6586` | `0.6099` | `0.7875` | `0.6241` |

- **Brier Score:** RF `0.1857` vs. XGBoost `0.1865`
- **Expected Calibration Error (ECE):** RF `0.0696` vs. XGBoost `0.0506`
- **PU Probability Caveat:** Because the `563` background points are *unlabeled* rather than confirmed landslide-free terrain, predicted scores reflect relative PU presence density under a `1:2` sampling ratio — **not** calibrated real-world failure probabilities.

---

## 3. Why Production Deployment Remains Blocked

Even though clean terrain+soil spatial-block ROC-AUC (`0.7623`) exceeds random chance (`0.50`), promotion to production inference is blocked by six unresolved scientific defects:
1. **Unverified Point Positional Accuracy:** `0` certified polygon/headscarp or GPS error-bounded (`<= 100 m`) labels (GSI Polygon FeatureServer returns HTTP 499 Token Required).
2. **Event-Level Duplication:** `81` near-duplicate pairs within `50 m` across GSI survey programs require polygon consolidation.
3. **Severe Transport-Corridor Sampling Bias (`77.8%`):** Proved to inflate ROC-AUC by `+0.185` when road/rail distances are included; remote Barail Range slopes are systematically under-sampled.
4. **Insufficient Temporal Holdout Independence:** Post-2021 IMERG-overlapping day-dated events occur in only **1 year (`2022`)**, preventing genuine multi-year (`>= 3` monsoon years) forward temporal validation.
5. **Missing Critical Conditioning Covariates:** GSI 1:50k lithology, fault/thrust geometry, and dynamic SMAP L4 soil moisture are absent.
6. **Zero Ground Rain-Gauge Validation:** IMERG and NOAA GFS have not been bias-corrected against IMD/CWC gauges in Dima Hasao.
