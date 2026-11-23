# GeoResilience-NER 2.0 — REST API Documentation (`/api/v1/*`)

**Base URL (Dev / Proxy):** `http://localhost:3000/api/v1` (Express proxies all methods, `Authorization` headers, JSON, multipart uploads `<= 6 MB`, and binary photos to FastAPI on `127.0.0.1:8000`).  
**OpenAPI Docs (FastAPI direct):** `http://127.0.0.1:8000/docs`  
**Response Headers:** Every response includes `X-Request-ID` and `X-Content-Type-Options: nosniff`.

---

## 1. System, Provenance & Regional Coverage

| Method | Endpoint | Auth | Description & Measured Warm Latency |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/health` | Public | Health check, DB connectivity, and pilot artifact presence (`5.0 ms`). |
| `GET` | `/api/v1/datasets` | Public | Complete dataset provenance registry with source URLs, CRS, attribution, and timestamps (`12.1 ms`). |
| `GET` | `/api/v1/pilot/boundary` | Public | Dima Hasao District GeoJSON polygon + DEM & WorldCover summaries. |
| `GET` | `/api/v1/regions` | Public | 8-state Northeast India regional readiness matrix (`5.6 ms`). |

---

## 2. Environmental Data, Exposure & Dynamic Hazard

| Method | Endpoint | Auth | Description & Key Guarantees |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/environment/point?lat=&lon=` | Public | Elevation, slope, aspect, WorldCover 2021, latest IMERG snapshot (`30.1 ms`). `landslide_probability: null`. |
| `GET` | `/api/v1/environment/terrain?lat=&lon=` | Public | Extended DEM geomorphometry (curvatures, TRI, TWI, flow acc, drainage & road/rail distances). |
| `GET` | `/api/v1/environment/soil?lat=&lon=` | Public | ISRIC SoilGrids 2.0 (7 layers, `cohesion_kpa: null`), Sentinel-2 NDVI 2024, honest GSI geology blocker (`52.3 ms`). |
| `GET` | `/api/v1/environment/rainfall/history` | Public | IMERG daily archive with optional `start_date`/`end_date` filters (`null` preserved for missing days). |
| `GET` | `/api/v1/environment/rainfall/multiyear` | Public | 10-year IMERG daily series (`2015–2024`, `3,439` valid / `214` null days). |
| `GET` | `/api/v1/environment/rainfall/forecast` | Public | Experimental NOAA GFS `0.25°` 0–72h forecast (`3.4 ms`, never labeled measured rainfall). |
| `GET` | `/api/v1/infrastructure/exposure?lat=&lon=&radius_km=` | Public | Real OSM proximity counts (roads, railways, bridges, settlements, hospitals, schools); zero fabricated population. |
| `GET` | `/api/v1/infrastructure/facilities?category=&limit=` | Public | GeoJSON of `619` ingested OSM point facilities (`hospital_health`, `school`, `settlement`, `bridge`). |
| `GET` | `/api/v1/hazard/assess?lat=&lon=&radius_km=` | Public | 6-part separated dynamic hazard report (`75.4 ms`). Strictly `landslide_probability: null`, `factor_of_safety: null`. |
| `POST` | `/api/v1/hazard/simulate` | Public | Server-side hypothetical rainfall stress test (`45.2 ms`). Explicitly `hypothetical_scenario: true`, `validated_ml_probability: null`. |

---

## 3. Landslide Inventory, Quality Gate & Machine Learning

| Method | Endpoint | Auth | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/landslides/gsi-bhusanket?pilot_only=` | Public | Official GSI Bhusanket public records (`379` in-district) with precision & bias audit metadata. |
| `GET` | `/api/v1/landslides/coolr?pilot_only=` | Public | NASA COOLR contextual records (`19` in-district, coarse 1–50 km). |
| `GET` | `/api/v1/quality-gate` & `/api/v1/ml/readiness` | Public | Live 13-check Data Quality Gate report (`overall_ml_ready: false`, 6 blocking failures). |
| `GET` | `/api/v1/ml/models` | Public | Model registry (`production_models_validated: 0`) + full exploratory RF/XGBoost/SHAP benchmark (`5.0 ms`). |
| `POST` | `/api/v1/ml/infer` | Public | Deployment-gated inference probe (`72.6 ms`): returns `status: unavailable_model_not_validated`, `landslide_probability: null`. |

---

## 4. Authentication & RBAC (`/api/v1/auth/*`)

| Method | Endpoint | Auth / Role | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/auth/bootstrap-status` | Public | Reports whether first-run admin claim is open (`needs_admin_claim`). |
| `POST` | `/api/v1/auth/claim-admin` | Public (once) | Claims initial `admin` account; permanently returns `409 Conflict` once an admin exists. |
| `POST` | `/api/v1/auth/register` | Public | Least-privilege self-registration (`field_officer` or `public_viewer` only; elevated roles rejected/downgraded). |
| `POST` | `/api/v1/auth/login` | Public | Verifies `scrypt` password hash and issues HMAC-SHA256 Bearer token (rate-limited `25/min`). |
| `GET` | `/api/v1/auth/me` | Bearer | Returns active authenticated user profile (`401` if invalid/expired). |
| `GET` | `/api/v1/auth/users` | `admin` | Lists registered accounts (`403` for non-admin). |
| `PATCH` | `/api/v1/auth/users/{user_id}/role` | `admin` | Promotes/demotes role across `admin`, `research_analyst`, `field_officer`, `public_viewer` + audit log. |

---

## 5. Field Reporting, Experimental Alerts, Monitoring & Gemini Assistant

| Method | Endpoint | Auth / Role | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/api/v1/field-reports?status=&limit=&offset=` | Public | Paginated field reports with verification status and photo metadata. |
| `POST` | `/api/v1/field-reports` | `field_officer` / `research_analyst` / `admin` | Multipart submission with optional magic-byte validated JPEG/PNG/WebP photo (`<= 5 MB`, SHA-256). |
| `GET` | `/api/v1/field-reports/photos/{filename}` | Public | Confined safe download of verified uploaded photo (`404` on traversal). |
| `PATCH` | `/api/v1/field-reports/{id}/review` | `research_analyst` / `admin` | Verifies or rejects a pending report + writes `audit_logs` record. |
| `GET` | `/api/v1/alerts` | Public | Lists experimental research drafts (`official_government_warning: false`). |
| `POST` | `/api/v1/alerts` | `research_analyst` / `admin` | Creates `EXPERIMENTAL_RESEARCH_DRAFT` pre-populated with real OSM exposure & source timestamps. |
| `PATCH` | `/api/v1/alerts/{id}/review` | `research_analyst` / `admin` | Transitions draft status (`pending_review`, `approved_internal`, `rejected`, `archived`). |
| `POST` | `/api/v1/alerts/{id}/dry-run-notify` | `research_analyst` / `admin` | Logs `DRY_RUN_NO_EXTERNAL_DISPATCH` adapter audit entry (zero external SMS/public alerts sent). |
| `GET` / `POST` | `/api/v1/monitoring/status` & `/run` | Public / Analyst+ | Reads or triggers IMERG/GFS freshness check into `monitoring_runs`. |
| `GET` | `/api/v1/audit-logs` | `research_analyst` / `admin` | Read-only security and workflow audit trail. |
| `POST` | `/api/v1/assistant/explain` | Public (rate-limited `15/min`) | Grounded `gemini-4-hydrogen` explanation (`400` on prompt injection, `503` with grounded evidence if `GEMINI_API_KEY` unset). |
