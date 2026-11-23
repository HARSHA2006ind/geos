# GeoResilience-NER 2.0 — Historical Rainfall Completeness & Uncertainty Report

**Pilot Study Area:** Dima Hasao District, Assam, India (`bbox: [92.5205, 24.9711, 93.4735, 25.8289]`, `EPSG:4326`)
**Data Role:** `historical_archive` (strictly separated from operational real-time monitoring)
**Pipeline Script:** `backend/ingestion/fetch_rainfall_multiyear.py`
**Output Artifact:** `backend/data/pilot/dima_hasao_rainfall_multiyear.json` (`1,232 KB`, 3,653 calendar days)

---

## 1. Historical Coverage Summary (2015-01-01 to 2024-12-31)

Replacing the earlier 61-day May–June 2024 snippet (32 valid days), Stage 4 retrieved a **10-year multi-product historical rainfall archive (`3,653` calendar days)** for Dima Hasao:

| Dataset | Role | Spatial Resolution | Interval | Valid Days | Missing Days (`null`) | Completeness | Max 24h (mm) |
|---|---|---|---|---:|---:|---:|---:|
| **NASA GPM IMERG Late Run Daily** (`ClimateSERV dt=26`) | **Primary Satellite** | `0.1°` (~11.1 km) | `2015-01-01` – `2024-12-31` | **3,439** | **214** | **94.14%** (`99.97%` through `2024-06-01`) | `203.340` |
| **UCSB CHIRPS v2.0 Daily** (`ClimateSERV dt=0`) | Independent Gauge-Blended Benchmark | `0.05°` (~5.5 km) | `2020-01-01` – `2024-12-31` | **1,827** | 0 | 100.00% | `145.714` |
| **NASA LaRC POWER (`MERRA-2 PRECTOTCORR`)** | Independent Reanalysis Benchmark | `0.5° × 0.625°` (~55 km) | `2015-01-01` – `2024-12-31` | **3,653** | 0 | 100.00% | `82.010` |
| **ECMWF ERA5 (Open-Meteo Historical Archive)** | Independent Reanalysis Benchmark | `0.25°` (~27 km) | `2015-01-01` – `2024-12-31` | **3,653** | 0 | 100.00% | `140.000` |

### Exact NASA GPM IMERG Missing Intervals (Never Extrapolated or Substituted)
1. **`2019-06-30` (1 day):** Single missing day in SERVIR ClimateSERV archive → stored as `null`; causes 3d/7d/15d rolling sums spanning `2019-06-30` to remain `null`.
2. **`2024-06-02` to `2024-12-31` (213 days):** SERVIR ClimateSERV `datatype=26` served NASA's retired **IMERG V06B** Late Run stream, which terminated on `2024-06-01` when NASA transitioned to **IMERG V07B**. All 213 days are preserved strictly as `null`.

### Free NASA Earthdata Login Integration (Direct IMERG V07B)
- `backend/ingestion/fetch_rainfall_multiyear.py` implements `check_nasa_earthdata_auth()` supporting `EARTHDATA_TOKEN` or `~/.netrc` against `https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDF.07/`.
- Live probe of `3B-DAY.MS.MRG.3IMERG.20240602-S000000-E235959.V07B.nc4` returned **`HTTP 302`** redirecting to `https://urs.earthdata.nasa.gov/oauth/authorize/...` (`authenticated: false` because no `EARTHDATA_TOKEN` is provisioned in this sandbox).
- **To bridge `2024-06-02` to present:** Register free at `https://urs.earthdata.nasa.gov`, authorize `NASA GESDISC DATA ARCHIVE`, generate a bearer token, and set `EARTHDATA_TOKEN` in `backend/.env`.

---

## 2. Units, Aggregation Semantics & Annual IMERG Summary

- **Units:** Daily precipitation in `mm/day` (UTC calendar day `00:00:00Z–23:59:59Z`); antecedent accumulations in `mm`.
- **Strict Window Definitions:**
  - `1-day (24 h)`: Day $t$ rainfall.
  - `3-day (72 h)`: Exact sum of $[t-2, t-1, t]$; **`null`** if any day in window is `null`.
  - `7-day (168 h)`: Exact sum of $[t-6 \dots t]$; **`null`** if any day in window is `null`.
  - `15-day (360 h)`: Exact sum of $[t-14 \dots t]$; **`null`** if any day in window is `null`.
- **Verification:** Independent audit verified **0 aggregation math errors** across all 3,653 days and 4 window lengths.

| Year | Valid Days | Missing (`null`) | Completeness | Annual Total (mm) | Max 1d (mm) | Max 3d (mm) | Max 7d (mm) | Max 15d (mm) |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2015 | 365 | 0 | 100.00% | 1,930.73 | 101.029 | 186.727 | 235.723 | 305.542 |
| 2016 | 366 | 0 | 100.00% | 2,527.77 | 101.728 | 187.420 | 269.881 | 497.320 |
| 2017 | 365 | 0 | 100.00% | **3,408.02** | **203.340** | 450.137 | **692.194** | **732.533** |
| 2018 | 365 | 0 | 100.00% | 2,014.78 | 138.469 | 347.476 | 422.438 | 452.429 |
| 2019 | 364 | 1 | 99.73% | 2,487.09 | 88.272 | 159.191 | 218.841 | 310.094 |
| 2020 | 366 | 0 | 100.00% | 2,027.06 | 108.014 | 170.562 | 179.919 | 280.584 |
| 2021 | 365 | 0 | 100.00% | 1,657.39 | 60.966 | 166.500 | 203.775 | 250.697 |
| 2022 | 365 | 0 | 100.00% | 2,861.85 | 103.199 | 277.718 | 445.099 | 528.077 |
| 2023 | 365 | 0 | 100.00% | 2,321.59 | 99.023 | 192.338 | 327.300 | 542.175 |
| 2024* | 153 | 213 | 41.80% | 1,305.44* | 203.259 | **478.384** | 578.221 | 644.143 |

*\*2024 reflects Jan 1 – Jun 1 only (capturing Cyclone Remal in late May 2024).*

### Sample Antecedent Rainfall Aligned to Verified Dima Hasao Events (Strictly `<= event_date`)
- **`2017-04-04`** (5 NASA COOLR events: Mahur, N. Leikul, Phaiding, Harangajao, NH-54): `1d = 30.688 mm`, **`3d = 360.632 mm`**, **`7d = 692.194 mm`** (10-year archive maximum!), **`15d = 711.469 mm`**.
- **`2017-06-04`** (COOLR #9750): `1d = 0.084 mm`, `3d = 47.049 mm`, `7d = 156.615 mm`, `15d = 225.914 mm`.
- **`2018-12-18`** (COOLR #14086 rock fall between Phaiding & Mahur): `1d = 42.298 mm`, `3d = 61.124 mm`, `7d = 61.126 mm`, `15d = 62.803 mm`.
- **`2024-05-28`** (Cyclone Remal peak window): `1d = 130.594 mm`, `3d = 326.297 mm`, `7d = 342.563 mm`, `15d = 426.132 mm`.

---

## 3. Cross-Product Comparison & Steep-Terrain Satellite Uncertainty

| Product Pair | Overlap Days | Pearson $r$ | Spearman $\rho$ | MAE (mm/d) | RMSE (mm/d) | Rel. Bias (%) | Days $\ge 50$ mm (A vs B) | Heavy-Rain CSI ($\ge 50$ mm) |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| **IMERG vs CHIRPS v2.0** (`2020–2024`) | 1,614 | **0.7529** | 0.6977 | 4.034 | 9.354 | +19.54% | 34 vs 20 | **0.317** |
| **IMERG vs NASA POWER (MERRA-2)** (`2015–2024`) | 3,439 | 0.6575 | **0.8093** | 4.515 | 11.019 | +44.01% | 70 vs 12 | 0.108 |
| **IMERG vs ECMWF ERA5** (`2015–2024`) | 3,439 | 0.5038 | 0.7312 | 5.474 | 13.051 | +35.16% | 70 vs 46 | 0.172 |
| **CHIRPS v2.0 vs ECMWF ERA5** (`2020–2024`) | 1,827 | 0.5314 | 0.5834 | 4.866 | 10.845 | +38.61% | 23 vs 22 | 0.250 |

### Steep-Terrain Uncertainty Conclusions
1. **Substantial Heavy-Rain Disagreement:** Even the two highest-resolution satellite products (IMERG `0.1°` vs gauge-blended CHIRPS `0.05°`) agree on $\ge 50\text{ mm/day}$ storms with a Critical Success Index (CSI) of only **0.317** (`+19.54%` IMERG wet bias relative to CHIRPS).
2. **Severe Coarse-Grid Peak Attenuation:** NASA POWER (`0.5°`, max `82.01 mm`) misses `83%` of IMERG's $\ge 50\text{ mm}$ extremes (`12` vs `70` days), confirming it must never replace IMERG for landslide triggering thresholds.
3. **Ground Gauge Bias Correction Still Needed:** IMD `0.25°` gridded rainfall (via `imdlib`) and **IMD Guwahati / ASDMA Automatic Weather Station (AWS) rain gauges** in Haflong, Maibang, and Umrangso remain necessary to calibrate local orographic bias in the Barail Range.

---

## 4. Separation of Historical Archive vs Operational Monitoring

- `dima_hasao_rainfall_multiyear.json` carries `"data_role": "historical_archive"` and `rainfall_observations.data_role` enforces the same distinction in PostgreSQL/PostGIS (`0002` migration).
- Operational real-time monitoring is NOT active in this archive; it requires a separate scheduled 3–6 hour worker pulling NASA GPM IMERG Early/Late V07B (with `EARTHDATA_TOKEN`) and IMD/ASDMA AWS gauges with explicit latency and staleness alerts.
