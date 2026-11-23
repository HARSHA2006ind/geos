# GeoResilience-NER 2.0 — Earth2Studio Weather Data & Experimental Prototype Evaluation

**Audit Date (UTC):** 2026-11-23  
**Study Area:** Dima Hasao District, Assam, India (`24.97°N–25.83°N, 92.52°E–93.47°E`, `4,880.75 km²`)

---

## 1. Task 3 — Verified Earth2Studio Weather Data-Source Matrix (Northeast India)

All datasets below were verified directly against `NVIDIA/earth2studio` `main` (`earth2studio/data/*.py` and `earth2studio/lexicon/*.py`):

> **Direct IMERG Check:** Verified in `earth2studio/data/__init__.py` and `earth2studio/data/`: **NVIDIA Earth2Studio v1.0.0 does NOT include a NASA GPM IMERG data source.** Its high-resolution precipitation sources (`MRMS`, `nClimGrid`, `OPERA`) cover CONUS or Europe only — **zero coverage over Northeast India**.

| Earth2Studio Class / Store | Exact Dataset | Verified Lexicon Variables (Precip / Temp / Moisture) | Spatial Res. | Temporal Res. | NER Coverage | Data Role | Auth Required? | License | Latency & Update Freq. |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- | :---: | :--- | :--- |
| **`DynamicalGFS_FX`** (`dynamical.org` Zarr v3) | NOAA GFS Operational Forecast (`noaa-gfs-forecast` v0.2.7) | `precipitation_surface` (`tpf`), `temperature_2m` (`t2m`), `relative_humidity_2m` (`r2m`), `precipitable_water_atmosphere` (`tcwv`), `msl`, `sp`, winds | `0.25°` (~25 km) | 1h (`0–120h`), 3h (`123–384h`) | Global (**Full NER**) | **Forecast** (`2021-05`–Present) | **No (Free)** | `CC-BY-4.0` | ~3–5 h; 4x/day (`00/06/12/18 UTC`) |
| **`DynamicalIFS_ENS_FX`** (`dynamical.org` Zarr v3) | ECMWF IFS Ensemble 15-Day (`ecmwf-ifs-ens-forecast-15-day-0-25-degree`) | `tp`, `t2m`, `d2m`, `tcwv`, `msl`, `sp`, winds | `0.25°` (~25 km) | 3h (`0–144h`), 6h (`144–360h`) | Global (**Full NER**) | **Ensemble Forecast** (`2024-04`–Present) | **No (Free)** | `CC-BY-4.0` | ~8 h; daily (`00 UTC`) |
| **`DynamicalAIFS_FX`** (`dynamical.org` Zarr v3) | ECMWF AI Forecasting System (`ecmwf-aifs-single-forecast`) | `tp`, `t2m`, `d2m`, `tcwv`, `msl`, `sp`, winds | `0.25°` (~25 km) | 6h (`0–360h`) | Global (**Full NER**) | **AI Forecast** (`2024-04`–Present) | **No (Free)** | `CC-BY-4.0` | ~6 h; 4x/day |
| **`GFS` / `GFS_FX`** (NOAA AWS S3 GRIB2) | NOAA NCEP GFS Analysis & Forecast | `tp`, `tp06`, `t2m`, `d2m`, `r2m`, `q850`, `r850`, `tcwv`, `sp`, `msl` (247 vars) | `0.25°` (~25 km) | 6h analysis / 1–3h forecast | Global (**Full NER**) | Analysis & **Forecast** | **No (Free)** | Public Domain | ~3.5–5 h; 4x/day (needs `pygrib`/`eccodes`) |
| **`IFS` / `IFS_FX`** (`ecmwf-opendata` GRIB2) | ECMWF IFS HRES Open Data | `tp`, `tp06`, `tprate`, `t2m`, `d2m`, `swvl1`, `swvl2`, `tcwv` (80 vars) | `0.25°` (~25 km) | 3–6h (rolling 4-day window only) | Global (**Full NER**) | Analysis & **Forecast** | **No (Free)** | `CC-BY-4.0` | ~7–8 h; 4x/day (needs `pygrib`/`eccodes`) |
| **`ARCO_ERA5`** (Google Cloud Zarr v3) | ECMWF ERA5 Reanalysis (ARCO-ERA5) | `tp`, `tp06`, `t2m`, `d2m`, `skt`, `swvl1`, `swvl2`, `stl1`, `tcwv` (44 vars) | `0.25°` (~25 km) | 1h (`1940`–near-present) | Global (**Full NER**) | **Historical Reanalysis** | **No (Free)** | `CC-BY-4.0` (C3S) | ~5–10 days (ERA5T) / 2–3 months |
| **`CDS_ERA5`** (Copernicus CDS API) | ECMWF ERA5 Reanalysis (CDS) | `tp`, `tp06`, `t2m`, `d2m`, `r850`, `q850`, `swvl1`, `swvl2`, `tcwv` (117 vars) | `0.25°` (~25 km) | 1h (`1940`–present) | Global (**Full NER**) | **Historical Reanalysis** | **Yes** (free `~/.cdsapirc`) | Copernicus License | ~5 days; high queue latency |
| **`NCAR_ERA5`** (AWS Open Data NetCDF4) | NSF NCAR ERA5 | `t2m`, `d2m`, `swvl1`, `tcwv` (31 vars) — **NO precipitation (`precip=[]`)** | `0.25°` (~25 km) | 1h (`1940`–present) | Global (**Full NER**) | **Historical Reanalysis** | **No (Free)** | `CC-BY-4.0` | Monthly batch updates |
| **`GHCNDaily` / `ISD`** (NOAA NCEI) | Global Historical Climatology Network Daily / ISD | `tp` (`PRCP`), `t2m` (`TAVG`), `t2m_max`, `t2m_min`, `d2m`, `r2m` | Point stations | Daily / Hourly | **4 pre-1970 stations in Dima Hasao; 1 active station 35 km south (Silchar)** | **Ground Verification** | **No (Free)** | Public Domain | 1–3 days; daily updates |

### Comparison with Existing NASA GPM IMERG Ingestion Pipeline
- **Historical Precipitation (`NASA IMERG V07B` vs `ARCO_ERA5` / `GFS`):** Our existing NASA IMERG pipeline (`0.10°` ≈ 11 km, 6.25× finer cell area than `0.25°` ERA5/GFS) remains **strictly superior** as the satellite precipitation benchmark for historical landslide triggering. Coarse `0.25°` reanalysis or forecast fields must **never** substitute for measured landslide-triggering rainfall.
- **Genuine Complementary Gap Identified:** Our existing pipeline had **zero operational weather forecasts** and **zero atmospheric temperature/humidity/precipitable-water layers**. Earth2Studio's discovery of `dynamical.org`'s free Zarr v3 NOAA GFS / ECMWF IFS-ENS / AIFS archives AND NOAA GHCN-Daily provides two genuinely complementary research capabilities — accessible directly over lightweight HTTP/Zarr without installing Earth2Studio's GPU stack!

---

## 2. Task 5 — Isolated Experimental Evaluation Prototype Results (CPU-Only)

Both isolated prototypes live strictly under `backend/experimental/nvidia_weather_eval/` and write strictly to `backend/data/experimental/`, completely separated from `backend/data/pilot/`, `quality_gate.py`, and production risk outputs.

### Prototype A: Live 72-Hour NOAA GFS `0.25°` Forecast Slice for Dima Hasao (`dynamical_gfs_eval.py`)
- **Direct Access Method:** Pure-CPU `zarr==3.1.6` + custom 40-line `ReadOnlyHttpxZarrStore` against `https://data.dynamical.org/noaa/gfs/forecast/latest.zarr` (zero `torch`, zero `cupy`, zero `eccodes`, zero auth).
- **Live Forecast Cycle Retrieved:** `2026-11-22T18:00:00+00:00` (`73` hourly lead steps, `0..72h`, `30` grid points covering `24.75°N–26.00°N, 92.50°E–93.50°E`).
- **Real Dima Hasao Values Retrieved:**
  - `forecast_24h_mean_rain_mm`: **`2.521 mm`** | `forecast_72h_mean_rain_mm`: **`6.061 mm`**
  - `temperature_2m`: **`14.67°C – 25.37°C`** | `relative_humidity_2m` mean: **`87.21%`** | `precipitable_water` mean: **`26.21 mm`**
- **Validation & Missing-Data Behavior:** `all_physical_bounds_valid: true` (`0` physical range violations across all 4 variables × 73 lead steps); `lead_hours = 0` precipitation flux (`NaN` by GFS convention) preserved strictly as `null` (`null_counts.precipitation_rate_mm_h = 1`).
- **Measured CPU-Only Performance:**
  - Execution time: **`6.176 s`**
  - Peak Python heap RAM (`tracemalloc`): **`11.80 MB`** (0.15% of 8 GB server RAM)
  - Network transfer: **`4.50 MB`** across `17` HTTP Range requests
  - Output disk footprint: **`24.62 KB`** (`backend/data/experimental/dima_hasao_gfs_forecast_eval.json`)
  - GPU required: **`false`**

### Prototype B: NOAA GHCN-Daily Ground-Station Verification Audit (`ghcn_station_eval.py`)
- **Direct Access Method:** Zero new dependencies (plain `httpx` + stdlib `csv`) against `https://www.ncei.noaa.gov/data/global-historical-climatology-network-daily/access/`.
- **In-District Dima Hasao Audit:** Confirmed **4 historical stations physically inside Dima Hasao** (`IN003060200` Haflong Obsy `1901–1970`, `IN003060600` Harangajao `1921–1955`, `IN003060300` Jaitanga Valley `1901–1955`, `IN003060400` Maibong `1901–1968`) — **0 active post-1970 in-district gauges in GHCN-Daily**.
- **Nearest Active IMD Synoptic Station (`IN003010600` Silchar, 29 m MSL, ~35 km south, active through `2026-11-09`):**
  - `1,060` valid PRCP days (`2015–2024`), `933` days overlapping our valid Dima Hasao IMERG archive (`127` valid days in the `2024-06-02..2024-12-31` IMERG gap).
  - Daily Pearson `r = 0.3062`, `MAE = 15.68 mm/day`, bias (`IMERG - Silchar`) = `-4.39 mm/day` (`11.36` vs `15.76 mm/day`).
  - **Scientific Lesson:** Low daily correlation (`r = 0.31`) across just 35 km from Barak Valley (29 m) to the Barail Range (682 m) proves empirically why **in-district IMD/CWC mountain gauges** are irreplaceable for true rainfall validation.
- **Measured Performance:** **`2.885 s`**, **`19.09 MB` peak RAM**, **`2.90 KB` disk**, **`0` added dependencies**.

---

## 3. Documented Limitations

1. **Spatial Coarseness:** `0.25°` (~25 km) GFS/IFS/ERA5 cells severely smooth steep Barail Range terrain-forced rainfall spikes; they provide regional synoptic context ONLY, never slope-scale precipitation truth.
2. **Forecast vs Observation Role:** Numerical weather predictions (`GFS_FX`, `IFS_ENS_FX`, `AIFS_FX`) carry forecast uncertainty and must remain strictly segregated from historical IMERG/gauge training inputs.
3. **Soil Moisture Alternative:** `ARCO_ERA5` (`swvl1`, `swvl2` at `0.25°`) can be evaluated later as a free historical soil-moisture baseline alongside SMAP L4 (`9 km`), still subject to coarse-scale caveats.
