# GeoResilience-NER 2.0 — Remaining External & Scientific Blockers

All software engineering, geospatial processing, database migration, security, UI, deployment, and exploratory ML benchmarking work that is technically feasible without restricted external credentials has been completed. The following **external data, credential, and governance blockers** remain honestly open and prevent production ML deployment:

---

## 1. Scientific & Upstream Data Blockers (Blocking Production ML Gate)

| # | Blocker | Root Cause | Concrete Resolution Path |
| :-: | :--- | :--- | :--- |
| 1 | **GSI Landslide Polygons & GPS Error Bounds** | `GSI/Landslide_Polygon/FeatureServer` returns HTTP `499 Token Required`; public GSI Bhusanket API provides point centroids without horizontal accuracy metadata and `81` near-duplicate pairs (`<= 50 m`). | Obtain institutional GSI NGDR/Bhukosh stakeholder credentials or conduct Sentinel-2/field headscarp polygon digitization + event consolidation (`<= 100 m` accuracy). |
| 2 | **GSI 1:50k Lithology & Thrust-Fault GIS** | NGDR / Bhukosh geological polygons require portal login and authenticated vector download. | Register institutional researcher account on NGDR/Bhukosh, ingest 1:50k lithology & Barail/Disang thrust fault vectors into `EPSG:32646`. |
| 3 | **NASA GPM IMERG V07B/V07C (2024–Present) & SMAP L4** | `213/213` 2024 gap granules are confirmed in NASA CMR, but NASA GES DISC / NSIDC HDF5 downloads require a free **NASA Earthdata Login** bearer token (`NASA_EARTHDATA_TOKEN`). | Set `NASA_EARTHDATA_TOKEN` in server environment and run `backend/ingestion/fetch_imerg_v07_authenticated.py` + SMAP L4 ingestion. |
| 4 | **Transport-Corridor Sampling Bias (`77.8%`)** | Public GSI records heavily cluster along NH-27 and the Lumding–Badarpur railway; proved in Phase D to inflate spatial-CV ROC-AUC by `+0.185` if road/rail distances are used unstratified. | Supplement with unbiased satellite optical/SAR (Sentinel-2 / Sentinel-1) landslide mapping across remote slopes or apply formal survey-effort spatial weighting. |
| 5 | **Multi-Year Storm Independence (`>= 3` Monsoon Years)** | Post-2021 IMERG-overlapping day-dated GSI events currently cluster in a single year (`2022`). | Backfill 2024–2026 IMERG V07B and verify exact trigger dates for 2023–2026 events to achieve `>= 3` independent monsoon seasons for forward temporal validation. |
| 6 | **IMD / CWC District Rain-Gauge Validation** | Ground rain-gauge datasets for Dima Hasao are not publicly accessible via unauthenticated API. | Request historical daily/hourly gauge series from IMD Guwahati / CWC Brahmaputra Board to bias-correct IMERG and NOAA GFS in complex orographic terrain. |

---

## 2. Operational & Synchronization Blockers

| # | Blocker | Root Cause | Resolution Path |
| :-: | :--- | :--- | :--- |
| 7 | **GitHub Push Authentication** | Container has read-only access to `https://github.com/HARSHA2006ind/geos.git` (no SSH key or GitHub token configured). | Use the refreshed `geos-v2-foundation.bundle` and exact push commands in `GEOS_GITHUB_SYNC_STATUS.md` from an authenticated developer workstation (pushing `feature/geos-v2-foundation` only; never touching `main`). |
| 8 | **Live Gemini API Key (`GEMINI_API_KEY`)** | Not configured in container environment (intentionally never hardcoded); `/api/v1/assistant/explain` honestly returns HTTP `503` with grounded evidence until configured. | Add `GEMINI_API_KEY` in Settings / server `.env` to enable live `gemini-4-hydrogen` explanations. |
| 9 | **7 Additional NER States Data Ingestion** | Dima Hasao (Assam) is the active pilot; Arunachal Pradesh, Meghalaya, Manipur, Mizoram, Nagaland, Tripura, and Sikkim are registered in `/api/v1/regions` as `planned` with explicit `0` validated models. | Replicate the `backend/ingestion/` pipeline per district once Dima Hasao clears all 13 Quality Gate checks. |
| 10 | **Transitive Node Dev/Proxy Patch (`express` / `vite`)** | `bun audit` flags transitive `proxy-addr`/`body-parser`/`qs` under `express` and dev-only `vite@6.4.3`. | Deploy FastAPI behind Caddy (`docker-compose.yml`) in production and run `bun update express` before exposing `server.ts` on untrusted networks. |
