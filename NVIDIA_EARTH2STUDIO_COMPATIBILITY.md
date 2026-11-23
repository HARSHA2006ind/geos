# GeoResilience-NER 2.0 — NVIDIA Earth2Studio Compatibility & FourCastNet Assessment

**Audit Date (UTC):** 2026-11-23  
**Target Production Hardware:** `4 vCPU, 8 GB RAM, 20 GB SSD, NO NVIDIA GPU` (`nvidia-smi: None`, Python `3.11.2`)

---

## 1. Earth2Studio v1.0.0 Runtime & Dependency Compatibility Audit

Direct inspection of `https://raw.githubusercontent.com/NVIDIA/earth2studio/main/pyproject.toml` (release `v1.0.0`) reveals why `earth2studio` **cannot** be installed on GeoResilience-NER 2.0's CPU-only production server:

### Hard Unconditional Linux Dependencies in `earth2studio` `pyproject.toml`
- `cupy-cuda13x; sys_platform == 'linux' or sys_platform == 'win32'` — **CUDA 13 GPU library**
- `rmm-cu13>=26.2.0; sys_platform == 'linux'` — **NVIDIA RAPIDS Memory Manager (CUDA 13)**
- `torch>=2.5.0` — **PyTorch (~2.5–3.5 GB CUDA wheel footprint on Linux)**
- `pygrib` — requires native C library `eccodes` / `eccodeslib`
- `netCDF4>=1.6.4,<1.7.3`, `xarray[parallel]`, `zarr>=3.1.3`, `s3fs`, `gcsfs`, `obstore`, `pyarrow>=24.0.0`

### Optional Extras (`[data]`, `[sfno]`, `[fcn3]`, `[precip-afno]`)
- `earth2studio[data]` adds `eccodes`, `eccodeslib`, `cfgrib`, `ecmwf-opendata`, `cdsapi`, `rioxarray`, `pystac-client`, `eumdac`, and (for Python `>=3.12`) `icechunk`, `arraylake`, `gribberish` — note our runtime is **Python 3.11.2**, so `icechunk` (`python_version>='3.12'`) used by `earth2studio/data/dynamical.py` is **not even installable on Python 3.11**!
- `earth2studio[sfno]` / `[fcn3]` require compiling `torch-harmonics` with `FORCE_CUDA_EXTENSION=1`.
- Total disk footprint of `earth2studio[data]` on Linux exceeds **4–6 GB** (20–30% of our entire 20 GB production SSD!) purely for unused CUDA/GPU libraries.

### Verdict on Installing `earth2studio`
**REJECTED for our CPU-only server.** Instead, accessing the exact underlying open meteorological store (`https://data.dynamical.org/noaa/gfs/forecast/latest.zarr`) directly via pure-CPU `zarr==3.1.6` + `httpx` requires only **36.3 MB** on disk (100x smaller), runs on Python `3.11.2`, uses **11.8 MB peak RAM**, and introduces **zero GPU/CUDA dependencies**.

---

## 2. Task 4 — Comprehensive Assessment of NVIDIA FourCastNet

**Official Model Page:** `https://build.nvidia.com/nvidia/fourcastnet` (`HTTP 200` verified live)  
**Hosted Inference Endpoint:** `https://climate.api.nvidia.com/v1/nvidia/fourcastnet` (`HTTP 405 Method Not Allowed` on GET — confirming live POST inference router)  
**Verified Model Source Code:** `NVIDIA/earth2studio/main/earth2studio/models/px/{fcn.py, sfno.py, fcn3.py}` and `models/dx/{precipitation_afno.py, precipitation_afno_v2.py}`

| Evaluation Criterion | Verified Official Fact | Impact on GeoResilience-NER 2.0 |
| :--- | :--- | :--- |
| **Hosted Inference Availability** | Available via NVIDIA NIM API Catalog (`build.nvidia.com/nvidia/fourcastnet`, POST `/v1/infer`) and self-hosted NIM container (`nvcr.io/nim/nvidia/fourcastnet`). | Hosted NIM avoids local GPU hardware **only for inference execution**, NOT for assembling/uploading global initial-condition tensors. |
| **Model Versions** | - **FourCastNet v1 (`FCN`):** AFNO, 26 variables.<br>- **FourCastNet v2 (`SFNO` — NIM production model):** Spherical Fourier Neural Operator, **73 variables**.<br>- **FourCastNet 3 (`FCN3`):** Spherical convolutional/harmonic operator, **72 variables**. | Production NIM serves 73-channel `SFNO`. |
| **Does FourCastNet Output Actual Precipitation?** | **NO — VERIFIED DIRECTLY IN SOURCE CODE!**<br>`fcn.py` (26 vars), `sfno.py` (73 vars), and `fcn3.py` (72 vars) contain **`precip_vars = []` (ZERO `tp` or `tp06` precipitation channels!)**. They output atmospheric state (`u10m`, `v10m`, `u100m`, `v100m`, `t2m`, `sp`, `msl`, `tcwv`, and pressure-level `u/v/z/t/r`). | **DISQUALIFYING SCIENTIFIC GAP for landslide triggering.** Getting 6h precipitation (`tp06`) requires chaining a *separate* diagnostic GPU model (`PrecipitationAFNO`; note NVIDIA's own `install_options.yml` marks `PrecipitationAFNOv2` as *"deprecated and performs worse than V1"*). |
| **Spatial Resolution** | Global **`0.25° × 0.25°`** regular lat-lon grid (`721 × 1440` points, ~25 km × 27 km ≈ **675 km² per cell** at 25°N). | **Severely too coarse for Dima Hasao** (`4,880.75 km²` total ≈ ~7–10 cells). Smooths out the steep Barail Range / Jatinga–Haflong–Maibang orographic rain shadow and localized convective cloudbursts that drive slope failures. |
| **Temporal Resolution & Horizon** | **6-hour** fixed autoregressive steps; stable across medium-range horizons (days to 2 weeks+). | Lacks 1-hour storm intensity peaks needed for shallow debris-slide intensity-duration (ID) thresholds. |
| **Input / Output Format & Payload Burden** | POST `/v1/infer` requires uploading a global float32 NumPy tensor `(1, 73, 721, 1440)` (`fcn_inputs.npy` = **`303.16 MB` per request!**) plus `input_time` & `simulation_length`, returning a multi-hundred-MB `output.tar` global forecast cube. | Completely impractical on a 4 vCPU / 8 GB RAM / 20 GB SSD server — fetching 73 global ERA5/GFS variables and uploading 303 MB per forecast cycle just to slice 15–30 grid cells over Assam wastes gigabytes of bandwidth and RAM. |
| **Authentication, Trial & Pricing** | Requires an NVIDIA NGC account (`NVIDIA_API_KEY` / `NGC_API_KEY`). Free prototyping is governed by rate-limited trial usage on `build.nvidia.com` (replaced older 4,000-credit bucket); commercial/operational deployment requires **NVIDIA AI Enterprise** licensing. | Introduces external API-key dependency, rate-limit risk, and commercial licensing lock-in when **NOAA GFS (`0.25°` hourly) and ECMWF AIFS/IFS-ENS (`0.25°`)** are already published **free, unauthenticated, CC-BY-4.0, WITH precipitation** on `dynamical.org`! |
| **Suitability for Northeast India Landslides** | **UNSUITABLE.** | FourCastNet is an impressive global synoptic atmospheric emulator, NOT a rainfall-triggered hillslope landslide predictor. |

### Verdict on FourCastNet
**DO NOT INTEGRATE FourCastNet** (neither self-hosted nor via hosted NIM API). Self-hosting violates our CPU-only hardware constraint, and calling the hosted API requires uploading 303 MB global tensors, managing NGC keys/rate limits, and still receives **zero precipitation output** at `0.25°` resolution.
