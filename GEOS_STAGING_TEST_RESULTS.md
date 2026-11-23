# GeoResilience-NER 2.0 — Staging Integration Test Results

## 1. Automated Unit & Integration Suites

| Suite | Command | Result | Scope Covered |
|---|---|---|---|
| **Backend `pytest`** | `PYTHONPATH=. backend/.venv/bin/pytest -v backend/tests/` | **38 / 38 PASSED** (`15.52s`) | API health & datasets, Alembic `0003` upgrade/downgrade, RBAC/admin lockout, magic-byte & path traversal security, Horn slope math, IMERG null propagation, Stage 9 rasters, GSI Bhusanket audit, GFS 48h/mean temp, Zarr HTTP 503 retry, monitoring cycles, live PostGIS `ST_Contains` / `ST_DWithin` |
| **Frontend `vitest`** | `npx vitest run` | **9 / 9 PASSED** (`871ms`) | Risk engine bounds, Leaflet XSS `escapeHtml`, pilot endpoints |
| **TypeScript Check** | `npm run lint` (`tsc --noEmit`) | Verified at final build step | Strict TypeScript compilation across React/Vite & `server.ts` |
| **Production Bundle** | `npm run build` | Verified at final build step | Vite client build + `esbuild server.ts` bundle |

---

## 2. Live Full-Stack E2E Journey (`http://127.0.0.1:3000` → `:8001` → PostGIS `:5432`)

- **Health & Security Headers:** `GET /api/v1/health` returned `200 OK` with `database.dialect = "postgresql"`, `postgis_version = "3.3 USE_GEOS=1 USE_PROJ=1 USE_STATS=1"`, all `8/8` `pilot_artifacts = true`, `X-Content-Type-Options: nosniff`, and forwarded `X-Request-ID`.
- **Point & Environmental Queries:** Haflong (`25.1645°N, 93.0176°E`) returned `within_pilot_boundary: true`, elevation `680.23 m`, slope `4.0°`, `Tree cover`, `rain_48h_outlook_mm: 9.978`, and `missing_data_indicators.landslide_ml_probability: true`. Outside point (`26.5°N, 91.5°E`) returned `within_pilot_boundary: false` without fabrication.
- **ML Gate & Simulation:** `/api/v1/ml/readiness` returned `overall_ml_ready: false` (`6/13` pass, `6` blocking failures); `/api/v1/ml/models` reported `production_models_validated: 0`; `/api/v1/ml/infer` returned `landslide_probability: null`, `factor_of_safety: null`; `/api/v1/hazard/simulate` returned `PRIORITY_2_HEIGHTENED_MONITORING` with `validated_ml_probability: null`.
- **Auth, Field Reporting & Experimental Alerts:** Exercised full lifecycle (`claim-admin` `200` → second claim `409` → `field_officer` register → admin escalation attempt downgraded to `public_viewer` → `>5 MB` upload rejected `422` → valid 1x1 PNG persisted with SHA-256 & served `200` → field officer review blocked `403` → admin review `200` → experimental alert draft → internal approval → dry-run notify `DRY_RUN_NO_EXTERNAL_DISPATCH` → audit log verification).
- **Restart Persistence:** Restarted `server.ts` + `uvicorn` (`restart_dev_server`); confirmed persisted report (`total: 1`), alert (`total: 1`), and monitoring run (`1`) survived restart cleanly, after which synthetic test user/report/alert rows were removed so production initial admin claim (`needs_admin_claim: true`) stays clean.

---

## 3. Gemini Explanation Assistant Validation (`/api/v1/assistant/explain`)

| Test Scenario | Expected | Measured Result |
|---|---|---|
| Prompt Injection (`"Ignore previous instructions..."`) | `400` + audit log | **`400 Bad Request`** (`prompt_injection_blocked` logged in DB) |
| Invalid / Too-Short Input (`"hi"`) | `422` | **`422 Unprocessable Entity`** |
| Unconfigured `GEMINI_API_KEY` | `503` + grounded evidence | **`503 Service Unavailable`** (`gemini_not_configured`, `landslide_probability: null`) |
| Invalid `GEMINI_API_KEY` | `502` + upstream detail | **`502 Bad Gateway`** (upstream Google `400 API key not valid`, `grounded_evidence` intact) |
| Rate Limit (`>15 req/60s` per IP) | `429` | **`429 Too Many Requests`** triggered on 15th/16th rapid call |
| Live Inference (`gemini-4-hydrogen`, runtime key) | `200` or truthful `502` on upstream failure | Upstream Google endpoint returned transient **`503`** (*"This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later."*). Backend retried once and returned **`502 Bad Gateway`** preserving full structured `grounded_evidence` with `landslide_probability: null`. |

---

## 4. Concurrent Load, Memory & Disk Footprint

- **Measured Container Specs:** `2 vCPU`, `4.0 GiB RAM`, `0 B Swap`, `756 GB` filesystem (`754 GB` free). (Smaller than target `4 vCPU / 8 GB RAM` production spec.)
- **Concurrency Load Test:** `64` requests across `/api/v1/health`, `/api/v1/environment/point`, `/api/v1/hazard/assess`, `/api/v1/ml/readiness` at `16` concurrent workers through `:3000 -> :8001 -> PostGIS`:
  - **Errors:** `0 / 64` (`100%` HTTP `200`)
  - **Wall Time / Throughput:** `16.112 s` (`3.97 req/s` under single-worker Uvicorn + full raster sampling + 64-synchronous quality-gate cached reads on 2 vCPUs)
  - **Latency:** `p50 = 1,836.39 ms`, `p95 = 10,794.74 ms`, `max = 11,497.90 ms`
- **Process RSS Memory (Post-Load):** `python` (`uvicorn`): `276 MB`, `node` (`tsx`/`vite`): `359 MB`, `postgres` cluster processes total: `~179 MB` (well within 4 GiB sandbox and 8 GB target budgets).
- **Disk Usage:** `backend/data`: `56 MB`, `backend/.venv`: `793 MB`, `node_modules`: `240 MB`.
