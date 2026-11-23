# GeoResilience-NER 2.0 — NVIDIA Build & Earth2Studio Agent Skills Research

**Audit Date (UTC):** 2026-11-23  
**Official Sources Inspected:**
- `https://github.com/NVIDIA/earth2studio` (Release `v1.0.0`, published `2026-11-18`, Apache-2.0, `1,254` stars)
- `https://build.nvidia.com/skills` / `https://nvidia.github.io/earth2studio/main/`
- Direct raw inspection of `NVIDIA/earth2studio/main/skills/*/SKILL.md` and `pyproject.toml`

---

## 1. Nature & Authenticity of NVIDIA Earth2Studio Skills

All four target skills live inside the official NVIDIA-maintained GitHub repository `NVIDIA/earth2studio` under `/skills/` (mirrored to `.agents/skills/`), authored by **NVIDIA Earth-2 Team**, versioned **`1.0.0`**, licensed **Apache-2.0**, and cryptographically signed (`skill.oms.sig`).

**Critical Architectural Distinction:**  
These skills are **AI coding-agent Markdown instruction files (`SKILL.md`)** designed for developer code assistants (Claude Code, Cursor, Codex, OpenCode). They are **NOT** Python runtime libraries, API SDKs, or meteorological data services. Inspecting each skill directory (`BENCHMARK.md`, `SKILL.md`, `skill-card.md`, `skill.oms.sig`, `evals/`, `references/`) confirmed **zero executable installation scripts** inside the skill directories.

---

## 2. Detailed Evaluation of the Four Target NVIDIA Skills

| Attribute | `earth2studio-discover` | `earth2studio-data-fetch` | `earth2studio-create-datasource` | `earth2studio-deterministic-forecast` |
| :--- | :--- | :--- | :--- | :--- |
| **Official Source & Version** | `NVIDIA/earth2studio/skills/earth2studio-discover` (`v1.0.0`, Apache-2.0) | `NVIDIA/earth2studio/skills/earth2studio-data-fetch` (`v1.0.0`, Apache-2.0) | `NVIDIA/earth2studio/skills/earth2studio-create-datasource` (`v1.0.0`, Apache-2.0) | `NVIDIA/earth2studio/skills/earth2studio-deterministic-forecast` (`v1.0.0`, Apache-2.0) |
| **Exact Purpose** | Guides agents to discover Earth2Studio models, data sources, lexicons, and examples from live repo docs (`docs/modules/models_*.md`, `datasources_*.md`) without memorizing stale lists. | Guides agents to select an Earth2Studio data source, check its lexicon (`earth2studio/lexicon/`), and author Python data-fetch scripts returning `xarray.DataArray` or `pandas.DataFrame`. | End-to-end workflow for building protocol-compatible custom `DataSource` / `ForecastSource` async wrappers connecting S3/GCS/Azure/HTTP stores into Earth2Studio. | Guides agents to write deterministic single-member weather forecast inference scripts using `earth2studio.run.deterministic` and diagnostic `Pipeline` postprocessing. |
| **Installation Requirements** | Skill itself: Markdown guidance only (installed via `npx skills add` in Claude Code/Cursor). Executing discovered code requires `earth2studio` Python package. | Skill itself: Markdown guidance only. Running generated scripts requires `earth2studio[data]` (`cupy-cuda13x`, `rmm-cu13`, `torch`, `pygrib`, `eccodes`, `xarray`, `zarr`). | Skill itself: Markdown guidance only. Custom wrappers conform to `earth2studio.data.base` contracts (requiring `earth2studio` runtime if integrated directly). | Requires `earth2studio` + model extras (e.g., `sfno`, `fcn3`, `torch-harmonics` with `FORCE_CUDA_EXTENSION=1`, `flash-attn`, or `onnxruntime-gpu`). |
| **Hardware Requirements** | None for reading docs; target models discovered typically require 16–80 GB GPU VRAM. | CPU possible for data fetch **only if** CUDA core deps are bypassed, but Linux `earth2studio` v1.0.0 unconditionally pulls `cupy-cuda13x`, `rmm-cu13`, and `torch>=2.5.0` (~4–6 GB). | Same heavy Linux dependency stack if importing `earth2studio` directly; lightweight standalone Python wrappers do not need Earth2Studio. | **NVIDIA CUDA GPU required** (`SKILL.md` explicitly warns: *"A CUDA-capable GPU for nearly all models (`deterministic` falls back to CPU when CUDA is unavailable, which is rarely practical)"*). |
| **Requires GPU?** | No (discovery only) | Runtime package pulls CUDA 13 libraries on Linux even for non-GPU data fetching | Only if using Earth2Studio runtime directly | **Yes (mandatory in practice)** |
| **Auth or Payment** | Free / Apache-2.0 (no auth) | Free / Apache-2.0; underlying stores vary (Dynamical/ARCO/GFS/GHCN = free no-auth; CDS = free API key) | Free / Apache-2.0 | Free code; weights on NGC/HuggingFace may require free NGC account; cloud GPU compute costs money |
| **Compatibility with Our Python 3.11 CPU Server** | **Guidance compatible** (Markdown methodology useful); runtime package **NOT compatible** with 8 GB RAM / 20 GB SSD CPU-only server. | **Guidance compatible** (led us directly to `dynamical.org` GFS Zarr v3 & NOAA GHCN-Daily); full `earth2studio[data]` package **NOT suitable** due to CUDA bloat. | **Not needed** — our pipeline already uses lean, modular `backend/ingestion/*.py` modules (20x smaller footprint). | **Incompatible** — CPU-only server (4 vCPU, 8 GB RAM, 20 GB SSD, `nvidia-smi: None`). |
| **Improvement to NER Data Acquisition** | **High indirect value:** Immediately identified free cloud-native `dynamical.org` NOAA GFS / ECMWF IFS-ENS / AIFS Zarr v3 archives and NOAA GHCN-Daily station catalog. | **Moderate indirect value:** Confirmed exact lexicon variable mappings (`precipitation_surface`, `temperature_2m`, `relative_humidity_2m`, `precipitable_water_atmosphere`) and confirmed **Earth2Studio has NO IMERG source**. | **Low:** Wrapping NASA IMERG or GSI Bhusanket in Earth2Studio's async tensor protocol adds overhead without improving landslide modeling. | **None:** Global `0.25°` (~25 km) AI weather models cannot run locally on CPU and do not resolve Barail Range hillslope rainfall. |

*(Note: We also inspected `skills/earth2studio-install/SKILL.md` v1.0.0, which explicitly forbids automated package installation and documents `docs/userguide/about/install_options.yml`.)*

---

## 3. Task 2 Installation Verification & Decision

We checked our coding runtime before running any skill installer:
- **Environment check:** Linux x86_64 (`Python 3.11.2`), `nvidia-smi: None`, container RAM `4 GB` (production server `4 vCPU, 8 GB RAM, 20 GB SSD, no GPU`).
- **Agent-skill runtime check:** This AI Studio Build coding environment reads platform skills strictly from read-only `/skills/system_skills/` and does **not** dynamically load repository-local `.agents/skills/` or `.claude/skills/`.
- **Decision (Strict Compliance with Task 2):**
  - **Installed via `npx skills add`:** **None (`0`).** Running `npx skills add` would download and execute an external npm CLI package (`skills`) solely to copy Markdown files into a directory our agent runtime does not load.
  - **Installed `earth2studio` Python package:** **No.** Installing `earth2studio` v1.0.0 on Linux pulls `cupy-cuda13x`, `rmm-cu13`, and `torch>=2.5.0` (~4–6 GB GPU stack) onto a CPU-only 20 GB SSD server.
  - **Methodology Applied:** Following Task 2's explicit fallback rule (*"If direct skill installation is unsupported, use the official `SKILL.md` instructions as documented guidance instead"*), we executed the exact `earth2studio-discover` and `earth2studio-data-fetch` workflows directly against live `NVIDIA/earth2studio` `main` docs and lexicons, and built an isolated CPU-only prototype (`zarr==3.1.6`, 36 MB total, zero GPU packages) to test the best discovered data sources.
