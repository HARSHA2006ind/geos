# GeoResilience-NER 2.0 — Automated Test & Benchmark Results

**Execution Date (UTC):** 2026-11-23  
**Summary:** **43 / 43 Automated Tests PASSED** (`34/34` Backend `pytest` + `9/9` Frontend `vitest`) · **Backup/Restore PASSED** · **0 TypeScript / Lint / Build Errors**

---

## 1. Backend Pytest Suite (`34 / 34 PASSED`)

Command: `PYTHONPATH=. backend/.venv/bin/pytest -v backend/tests`

| Test Module | Tests | Result | Verified Coverage |
| :--- | :---: | :---: | :--- |
| `backend/tests/test_api.py` | 8 | **PASS** | `/health`, `/datasets` provenance, `/pilot/boundary`, `/environment/point` inside/outside/invalid coords, IMERG rainfall null preservation, inventory discovery. |
| `backend/tests/test_geos_v2_platform.py` | 5 | **PASS** | Alembic `0003` upgrade/downgrade (all 19 tables); Auth/RBAC first-run admin claim lock (409), least-privilege self-register, 401/403 enforcement, admin role promotion; Extended terrain/SoilGrids/OSM/hazard/What-If & gated `/ml/infer` (`landslide_probability: null`); Multipart PNG upload + SHA-256 + spoofed binary rejection (422) + path traversal block (404) + analyst verification + experimental alerts + dry-run audit; Monitoring + 8-state `/regions` + prompt-injection block (400) + honest 503 Gemini evidence fallback. |
| `backend/tests/test_geospatial_and_provenance.py` | 4 | **PASS** | Horn 3×3 analytical tilted plane slope/aspect verification, missing rainfall null preservation, raster CRS/physical ranges, boundary geometry & provenance manifest. |
| `backend/tests/test_migrations.py` | 1 | **PASS** | Alembic `0001`–`0003` upgrade, SQLAlchemy ORM roundtrip, clean downgrade to `base`. |
| `backend/tests/test_nvidia_weather_eval.py` | 4 | **PASS** | Forecast validator null preservation, Dynamical GFS artifact isolation, GHCN verification caveats, quality gate scientific integrity. |
| `backend/tests/test_stage3_to_7_pipeline.py` | 7 | **PASS** | COOLR deduplication & uncertainty classification, idempotent DB persistence, antecedent 1d/3d/7d/15d strict null propagation, curvature/TRI math, quality gate blocking, pre-event feature extraction, Stage 3–5 endpoints. |
| `backend/tests/test_stage9_scientific_features.py` | 5 | **PASS** | GSI Bhusanket date parser, NLSM map segregation, IMERG V07B CMR catalog & HDF5 null handling, Stage 9 raster alignment, strict quality gate enforcement. |

---

## 2. Frontend Vitest Suite (`9 / 9 PASSED`)

Command: `npm test` (`vitest run`)

- `src/__tests__/regression.test.ts` (**9/9 PASS**, `95 ms`): Leaflet tooltip XSS escaping, `SubmitReportModal` valid enum types, `AlertsPage` null-safe directive rendering, `riskEngine` threshold & XAI sum invariants, WGS84->UTM46N projection accuracy, pilot artifacts health, Haflong real raster sampling (`landslide_probability: null`), out-of-bounds strict null safety, and missing IMERG day null preservation.

---

## 3. Measured Warm API Latency & Resource Benchmarks

Measured via FastAPI `TestClient` after quality-gate cache warmup on CPU-only host:

| Endpoint | HTTP Status | Measured Latency |
| :--- | :---: | :---: |
| `GET /api/v1/health` | `200` | `5.0 ms` |
| `GET /api/v1/datasets` | `200` | `12.1 ms` |
| `GET /api/v1/environment/point?lat=25.125&lon=93.025` | `200` | `30.1 ms` |
| `GET /api/v1/environment/soil?lat=25.125&lon=93.025` | `200` | `52.3 ms` |
| `GET /api/v1/environment/rainfall/forecast` | `200` | `3.4 ms` |
| `GET /api/v1/hazard/assess?lat=25.125&lon=93.025` | `200` | `75.4 ms` |
| `POST /api/v1/hazard/simulate` | `200` | `45.2 ms` |
| `GET /api/v1/ml/models` | `200` | `5.0 ms` |
| `POST /api/v1/ml/infer` | `200` | `72.6 ms` |
| `GET /api/v1/regions` | `200` | `5.6 ms` |

- **Peak Python Process RSS:** `347.1 MB` (well within `1.5 GB` container cap and `8 GB` host RAM).
- **Exploratory ML 5-Fold Spatial CV CPU Runtime:** Random Forest `2.404 s`, XGBoost CPU `0.903 s`.
- **Database Backup & Restore Check:** `backup_db.sh` -> SHA-256 verified (`OK`) -> `restore_db.sh` -> `SQLite restore verified OK (19 tables): ok`.
