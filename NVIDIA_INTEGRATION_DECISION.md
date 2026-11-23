# GeoResilience-NER 2.0 — Final NVIDIA Build & Earth2Studio Integration Decision

**Decision Date (UTC):** 2026-11-23  
**Architecture Status:** Approved GeoResilience-NER 2.0 stack preserved (`React/TS/Leaflet` + `FastAPI` + `PostGIS` + `NASA IMERG` + `Copernicus DEM` + `Sentinel-2 NDVI` + `SoilGrids 2.0` + `GSI Bhusanket` + quality-gated `RF/XGBoost`, currently **`overall_ml_ready: false`**, **`landslide_probability: null`**).

---

## Executive Decision: **SELECTIVE PATTERN ADOPTION — DO NOT INSTALL `earth2studio` OR INTEGRATE FOURCASTNET**

> **Guiding Principle:** Use NVIDIA only where it demonstrably improves GeoResilience-NER — never for branding or appearance.

| Component Evaluated | Decision | Concise Technical Rationale |
| :--- | :---: | :--- |
| **NVIDIA Earth2Studio Agent Skills (`SKILL.md`)** | **USE AS DOCUMENTATION ONLY (Do Not Run `npx skills add`)** | Verified authentic NVIDIA Apache-2.0 guidance (`v1.0.0`), but our AI Studio environment does not load repo-local `.agents/skills/`. Applying `earth2studio-discover` & `earth2studio-data-fetch` guidance directly gave 100% of the discovery value with zero installer clutter. |
| **NVIDIA `earth2studio` v1.0.0 Python Package** | **REJECT** | `pyproject.toml` unconditionally pulls `cupy-cuda13x`, `rmm-cu13`, and `torch>=2.5.0` (~4–6 GB GPU stack) on Linux + `icechunk` requires Python `>=3.12`. Incompatible with our `4 vCPU, 8 GB RAM, 20 GB SSD, Python 3.11.2` CPU-only server. |
| **NVIDIA FourCastNet (Local or Hosted NIM API)** | **REJECT** | Source-verified `sfno.py` (73 vars) & `fcn3.py` (72 vars) output **ZERO precipitation (`precip_vars = []`)**; `0.25°` (~25 km) grid is far too coarse for Dima Hasao hillslopes; hosted `/v1/infer` requires uploading `303 MB` global float32 tensors per call + NGC API key / rate-limited trial / paid AI Enterprise for production. |
| **Earth2Studio-Discovered `dynamical.org` NOAA GFS `0.25°` Zarr v3 (via lightweight CPU-only `zarr==3.1.6`)** | **ADOPT AS ISOLATED EXPERIMENTAL FORECAST LAYER** | Free, unauthenticated, `CC-BY-4.0`, fills a real missing capability (72h hourly forecast precipitation, 2m temp, RH, precipitable water) in **`6.18 s`**, **`11.8 MB` RAM**, **`36 MB` disk footprint**, zero GPU, zero API keys. Strictly isolated from validated observations and ML quality gates. |
| **Earth2Studio-Discovered NOAA GHCN-Daily Audit (`httpx`)** | **KEEP AS VERIFICATION DIAGNOSTIC (0 Extra Deps)** | Zero added dependencies; empirically proved `0` active post-1970 GHCN gauges inside Dima Hasao and quantified Silchar valley-to-ridge decorrelation (`r = 0.3062`), strengthening the case for acquiring in-district IMD/CWC gauges. |

---

## Direct Answers to the 10 Required Evaluation Questions

1. **Which NVIDIA skills were examined?**  
   All four requested official `NVIDIA/earth2studio` (`v1.0.0`, Apache-2.0) skills — `earth2studio-discover`, `earth2studio-data-fetch`, `earth2studio-create-datasource`, and `earth2studio-deterministic-forecast` — plus `earth2studio-install` (for dependency rules).

2. **Which were installed successfully?**  
   **Zero** skills were installed via `npx skills add` and **`earth2studio` Python package was NOT installed**, by deliberate engineering choice per Task 2: our runtime does not load repo-local `.agents/skills/`, we do not run unreviewed npm installers, and `earth2studio` v1.0.0 forces CUDA 13 (`cupy-cuda13x`, `rmm-cu13`, `torch`) on Linux. Instead, we applied `earth2studio-discover` and `earth2studio-data-fetch` `SKILL.md` instructions directly and installed only lightweight CPU-only `zarr==3.1.6` (36 MB total, 0 GPU libs) for the isolated evaluation prototype.

3. **Which were not suitable?**  
   - `earth2studio-deterministic-forecast`: requires an NVIDIA CUDA GPU in practice (`SKILL.md` explicitly warns CPU fallback is impractical).
   - `earth2studio-create-datasource`: unnecessary overhead compared to our lean standalone `backend/ingestion/*.py` architecture.
   - Full `earth2studio` Python library: unsuitable for our 8 GB RAM / 20 GB SSD CPU-only production server.
   - NVIDIA FourCastNet (local & hosted NIM): unsuitable due to missing precipitation output (`sfno.py` / `fcn3.py` have `0` precipitation channels), `0.25°` coarseness, 303 MB per-call upload overhead, and NGC trial/enterprise licensing limits.

4. **Can Earth2Studio improve our weather data access?**  
   **Indirectly yes — via its open-data catalog, NOT via installing its Python runtime.** Earth2Studio does **not** support NASA GPM IMERG, and its high-resolution precipitation sources (`MRMS`, `nClimGrid`, `OPERA`) do not cover India. However, following its data-source catalog revealed **free, unauthenticated, CC-BY-4.0 cloud-native Zarr v3 global forecasts** (`dynamical.org` NOAA GFS `0.25°`, ECMWF IFS-ENS `0.25°`, ECMWF AIFS `0.25°`), `ARCO_ERA5` (soil moisture `swvl1`/`swvl2`), and NOAA `GHCN-Daily` — which we can consume directly on CPU with minimal footprint.

5. **Does NVIDIA provide a usable free hosted forecasting endpoint?**  
   **No, not for rainfall-triggered landslide early warning in Dima Hasao.** `build.nvidia.com/nvidia/fourcastnet` provides a rate-limited free prototyping trial (requiring `NVIDIA_API_KEY`; production requires NVIDIA AI Enterprise), but FourCastNet SFNO does **not** output precipitation (`tp`/`tp06`), runs at `0.25°` (~25 km), and requires uploading a `303 MB` global 73-variable float32 tensor per inference request. Meanwhile, NOAA GFS and ECMWF AIFS/IFS-ENS are already served free, unauthenticated, **with precipitation**, on `dynamical.org`.

6. **What are the hardware and API limitations?**  
   - **Hardware:** Production server is `4 vCPU, 8 GB RAM, 20 GB SSD, no NVIDIA GPU`; cannot run CUDA/PyTorch weather foundation models or afford 4–6 GB of unused CUDA wheels.
   - **API / Data:** FourCastNet NIM has trial rate limits, enterprise production licensing, 303 MB input uploads, and no precipitation output. `dynamical.org` GFS/IFS/AIFS forecasts are `0.25°` (~25 km) — useful for synoptic context, never slope-scale ground truth.

7. **Were real experimental observations or forecasts retrieved?**  
   **Yes — two real, live, unfabricated experimental datasets were retrieved and validated:**
   - **Real 72-hour NOAA GFS `0.25°` forecast** (`init_time = 2026-11-22T18:00:00Z`, `30` Dima Hasao grid cells, `73` hourly lead steps: `24h rain = 2.521 mm`, `72h rain = 6.061 mm`, `t2m = 14.67–25.37°C`, `RH = 87.21%`, `PWAT = 26.21 mm`, `0` physical violations, `lead=0` null preserved) in `6.18 s` and `11.8 MB` RAM (`backend/data/experimental/dima_hasao_gfs_forecast_eval.json`).
   - **Real NOAA GHCN-Daily ground-station verification audit** confirming `0` active post-1970 stations inside Dima Hasao and comparing `933` overlapping days (`2015–2024`) at nearby Silchar IMD (`IN003010600`, `r = 0.3062`) in `2.89 s` and `19.1 MB` RAM (`backend/data/experimental/ghcn_silchar_verification_eval.json`).

8. **Did tests pass?**  
   **Yes — 100% passing (`38/38` automated tests: `29/29` Python Pytest including 4 new experimental evaluation & scientific-isolation tests + `9/9` TypeScript Vitest), plus clean `tsc --noEmit` and production build.**

9. **Were existing GEOS features preserved?**  
   **Yes — 100% preserved.** Zero changes to the React/Leaflet UI, FastAPI/Express production routes, PostGIS/Alembic schema, Stage 1–9 verified pilot datasets, 13-check Data Quality Gate (`overall_ml_ready: false`, 6 blocking failures), or `landslide_probability: null`.

10. **Is the integration worth maintaining?**  
    - **NVIDIA `earth2studio` runtime / FourCastNet NIM:** **No — do not maintain or adopt.**
    - **Lightweight CPU-only `dynamical.org` NOAA GFS / ECMWF AIFS Zarr v3 experimental forecast reader (`backend/experimental/nvidia_weather_eval/dynamical_gfs_eval.py`):** **Yes — worth maintaining strictly as an isolated experimental forecast module** (~12 MB RAM, 6 s latency, zero auth, zero GPU) to supply future lead-time synoptic forecast context *only after* verified landslide polygons, 1:50k lithology/faults, complete IMERG V07B, and IMD/CWC gauge validation unblock scientific ML model training.
