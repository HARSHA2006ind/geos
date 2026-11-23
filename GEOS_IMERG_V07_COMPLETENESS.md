# GeoResilience-NER 2.0 — NASA GPM IMERG V07B/V07C Rainfall Completeness & Validation Report (Stage 9)

**Audit Date (UTC):** 2026-11-23  
**Study Area:** Dima Hasao District, Assam, India (`92.52°E–93.47°E, 24.97°N–25.83°N`)  
**Ingestion Module:** `backend/ingestion/fetch_imerg_v07_earthdata.py`  
**Verified CMR Catalog Artifact:** `backend/data/pilot/imerg_v07_cmr_catalog.json`

---

## 1. Current Historical Archive Status (`2015-01-01` to `2024-12-31`)

| Metric | Verified Value | Policy |
| :--- | :--- | :--- |
| Existing Historical Archive (`dima_hasao_rainfall_multiyear.json`) | **3,439 / 3,653 valid days (94.14%)** | Acquired via ClimateSERV GPM IMERG (`2015-01-01` to `2024-06-01`). |
| Missing Days Preserved Strictly as `null` | **214 days** (`2019-06-30` + `2024-06-02..2024-12-31`) | **Zero artificial gap filling**; rolling 3d/7d/15d sums propagate `null` strictly. |
| Live NASA GES DISC Access Probe | **HTTP 302 -> `urs.earthdata.nasa.gov`** | Free NASA Earthdata Login (`EARTHDATA_TOKEN` or `~/.netrc`) is required to download `.nc4` granules; no credentials exist in this container, so **0 values were fabricated**. |

---

## 2. Live NASA CMR Granule Discovery (Exact Verified Availability)

Live queries to NASA Common Metadata Repository (`https://cmr.earthdata.nasa.gov/search/granules.json`) confirmed **100% granule availability** for closing the historical gap AND mapped the separate `2025–2026` current-monitoring stream:

### A. Historical Training Archive Gap Closure (`data_role = historical_training_archive_gap_closure`)

| Window | NASA Collection | Run Type | Expected Days | CMR Granules Verified | Revision | Coverage |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| `2019-06-30` (single missing day) | `GPM_3IMERGDF` v07 | Final Run (Gauge-Calibrated) | 1 | **1** | `V07B` | **100.0%** |
| `2024-06-02` to `2024-12-31` | `GPM_3IMERGDF` v07 | Final Run (Gauge-Calibrated) | 213 | **213** | `V07B` | **100.0%** |
| `2024-06-02` to `2024-12-31` (reference only) | `GPM_3IMERGDL` v07 | Late Run (NRT — do NOT silently blend into Final Run) | 213 | **213** | `V07B` | **100.0%** |

### B. Separate `2025–2026` Current-Monitoring Dataset (`data_role = current_monitoring_only_strictly_separate_from_historical_training`)

Kept **strictly separate** from the `2015–2024` historical training archive so near-real-time (Early/Late) latency products are never mixed into research-grade Final Run training features:

| NASA Collection | Run Type & Latency | CMR Granules Verified (`2025-01-01` to `2026-11-23`) | Earliest Granule | Latest Granule | Observed Revisions |
| :--- | :--- | :---: | :---: | :---: | :---: |
| `GPM_3IMERGDF` v07 | Final Run (~3.5 month latency, gauge-calibrated) | **273** | `2025-01-01` | `2025-09-30` | `V07B` |
| `GPM_3IMERGDL` v07 | Late Run (~14 hour latency) | **690** | `2025-01-01` | `2026-11-21` | `V07B`, `V07C` |
| `GPM_3IMERGDE` v07 | Early Run (~4 hour latency) | **691** | `2025-01-01` | `2026-11-22` | `V07B`, `V07C` |

*(Note: NASA CMR confirms that IMERG Late/Early operational processing transitioned from `V07B` to `V07C` during 2026; `fetch_imerg_v07_earthdata.py` records exact per-granule revisions automatically.)*

---

## 3. Authenticated Ingestion Pipeline Architecture (`fetch_imerg_v07_earthdata.py`)

The production-ready ingestion pipeline implements:
1. **Free NASA Earthdata Auth:** Supports `EARTHDATA_TOKEN` environment variable (Bearer token) or `~/.netrc` (`machine urs.earthdata.nasa.gov`), never printing, committing, or logging credentials.
2. **Resilient Download with Resume & Integrity Checks:** Exponential-backoff retry, HTTP `Range` partial-file resume (`*.nc4.part`), HDF5 magic-byte (`\x89HDF\r\n\x1a\n`) validation against HTML auth walls, atomic rename, and SHA-256 checksum logging.
3. **Strict NetCDF4/HDF5 Spatial Subsetting (`h5py`):** Reads `/Grid/precipitation` and quality variables (`precipitationQualityIndex` / `randomError`), clips strictly to Dima Hasao District polygon cells, masks `_FillValue` (`-9999.9`), and returns `rainfall_1d_mm = None` (`MISSING_INSUFFICIENT_VALID_CELLS`) whenever `< 50%` of district grid cells are valid — **verified by automated Pytest unit tests**.

### Exact Commands to Close the 2024 Gap Once Earthdata Login Is Configured

```bash
# 1. Create a free NASA Earthdata account: https://urs.earthdata.nasa.gov/users/new
# 2. Authorize "NASA GESDISC DATA ARCHIVE" in Earthdata Profile -> Applications -> Authorized Apps
# 3. Export your personal Bearer token (never commit or paste in chat) and run:
export EARTHDATA_TOKEN="<your_nasa_earthdata_bearer_token>"
PYTHONPATH=. backend/.venv/bin/python -m backend.ingestion.fetch_imerg_v07_earthdata
```

---

## 4. Critical Scientific Distinction: Inter-Product Agreement vs Gauge-Validated Accuracy

- **What Stage 4 Measured (Inter-Product Agreement ONLY):** Cross-checking NASA GPM IMERG against CHIRPS, NASA POWER, and ERA5 quantifies **inter-product agreement** among gridded satellite/reanalysis estimates. Shared orographic precipitation biases over the steep Barail Range can exist across multiple satellite/reanalysis products simultaneously.
- **What Is Still Required (True Gauge-Validated Accuracy):** Ground-truth rainfall error quantification (RMSE, bias, missed extreme convective cores, and intensity-duration threshold calibration) requires independent daily/hourly **IMD (India Meteorological Department), CWC (Central Water Commission), and ASDMA Automatic Weather Station (AWS)** rain-gauge observations inside Dima Hasao (e.g., Haflong, Maibang, Harangajao, Umrangso). Until those ground gauges are ingested, `imd_cwc_gauge_validated` remains strictly **`false`**.
