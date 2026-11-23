# GeoResilience-NER 2.0 — System Architecture

**Target Hardware Profile:** Ubuntu Linux Server — 4 vCPU, 8 GB RAM, 20 GB SSD, CPU-only (zero GPU/CUDA dependencies).

---

## 1. High-Level Architecture

```
                     ┌──────────────────────────────────────┐
                     │        Caddy 2 TLS Reverse Proxy      │
                     │     (256 MB cap · Auto-HTTPS / HSTS)  │
                     └──────────────────┬───────────────────┘
                                        │
          ┌─────────────────────────────┴─────────────────────────────┐
          ▼                                                           ▼
┌──────────────────────────────┐                     ┌────────────────────────────────┐
│ React 19 + Vite + TypeScript │                     │   Express Proxy (server.ts)    │
│  + Leaflet GIS + Recharts    │ ── /api/v1/* ────▶  │  + FastAPI Backend (Uvicorn)   │
│  (In-memory Bearer session)  │                     │  1 worker · 1.5 GB RAM cap     │
└──────────────────────────────┘                     └───────────────┬────────────────┘
                                                                     │
          ┌──────────────────────────┬───────────────────────────────┼───────────────────────┐
          ▼                          ▼                               ▼                       ▼
┌────────────────────┐   ┌───────────────────────┐   ┌──────────────────────────┐  ┌────────────────────┐
│ PostgreSQL 16 +    │   │ Raster & Vector Store │   │ CPU-Only ML & Quality    │  │ Server-Side Gemini │
│ PostGIS 3.4        │   │ (EPSG:32646 GeoTIFFs, │   │ Gate Engine              │  │ API Proxy          │
│ (SQLite fallback   │   │  OSM GeoJSON, IMERG,  │   │ (13-Check Gate, RF/XGB,  │  │ (gemini-4-hydrogen │
│  for local dev)    │   │  GSI, GFS Zarr JSON)  │   │  SHAP TreeExplainer)     │  │  prompt-guarded)   │
│ 1.5 GB RAM cap     │   │  ~54 MB disk total    │   │  Production Gate: BLOCKED│  │  Key server-only   │
└────────────────────┘   └───────────────────────┘   └──────────────────────────┘  └────────────────────┘
```

---

## 2. Backend Service Layers (`/backend/`)

1. **API & Middleware (`backend/app/main.py`, `backend/app/routers_v2.py`):**
   - Versioned `/api/v1/*` REST API with strict Pydantic v2 validation, explicit CORS (`GET/POST/PATCH/DELETE/OPTIONS`), `X-Request-ID`, `X-Content-Type-Options: nosniff`, and structured error responses without stack trace leakage.
2. **Security & Governance (`backend/app/security.py`):**
   - `hashlib.scrypt` password hashing (`N=16384, r=8, p=1`) with per-user random salt and constant-time comparison (`hmac.compare_digest`).
   - HMAC-SHA256 signed Bearer tokens (`GEOS_AUTH_SECRET`, ephemeral fallback in dev).
   - 4-role RBAC (`admin`, `research_analyst`, `field_officer`, `public_viewer`) with locked first-run admin claim and least-privilege self-registration.
   - Magic-byte JPEG/PNG/WebP upload verification (`<= 5 MB`), SHA-256 digesting, and canonical path confinement (`resolve_confined_upload`).
   - Sliding-window per-IP rate limiting on auth, writes, and Gemini endpoints.
   - Regex-based prompt-injection guardrail before any LLM request.
3. **Geospatial Sampling & Exposure (`backend/app/services/raster_service.py`, `hazard_engine.py`, `rainfall_service.py`):**
   - Projects incoming WGS84 `(lat, lon)` to UTM Zone 46N (`EPSG:32646`) via `pyproj.Transformer` and samples 16 aligned GeoTIFF rasters via `rasterio` preserving nodata as `null`.
   - Computes real OpenStreetMap spatial proximity (`InfrastructureExposureIndex`) across `619` point assets (`15` hospitals/health, `21` schools, `376` settlements, `207` bridges) and `2,604` transport segments (`2,212` roads, `392` railways).
   - Separates static susceptibility (`null`), observed IMERG rainfall, experimental NOAA GFS forecast, uncertainty, spatial exposure, and transparent IMD rainfall-envelope inspection priority.
4. **Scientific Quality Gate & Exploratory ML (`backend/app/quality_gate.py`, `backend/ml/research_benchmark.py`):**
   - 13-check gate with 60-second TTL cache (`get_cached_quality_gate`) maintaining sub-80 ms warm API latencies.
   - Exploratory RF + XGBoost (CPU `hist`) + SHAP spatial-block CV benchmark isolated strictly in `backend/data/experimental/exploratory_ml_benchmark.json` (`promoted_to_inference: false`).
5. **Automated Monitoring & Regional Coverage (`backend/app/services/monitoring_service.py`, `backend/ingestion/run_monitoring_cycle.py`):**
   - Periodic cron-compatible freshness audit logging IMERG/GFS staleness into `monitoring_runs` and `weather_forecasts`.
   - Idempotent 8-state Northeast India coverage registry (`regional_coverage`).

---

## 3. Database Schema (19 Tables — Alembic `0001` through `0003`)

- **Core Provenance & Telemetry (Migrations `0001`–`0002`):** `dataset_registry`, `study_areas`, `ingestion_jobs`, `rainfall_observations`, `landslide_events`, `provenance_records`.
- **GEOS 2.0 Platform Tables (Migration `0003_geos_v2_full_platform.py`):**
  - `dataset_versions`, `weather_forecasts`, `landslide_event_evidence`, `infrastructure_assets`
  - `model_registry`, `validation_results`, `model_predictions`
  - `users`, `field_reports`, `experimental_alerts`, `monitoring_runs`, `regional_coverage`, `audit_logs`

---

## 4. Frontend & Dev/Prod Proxy (`src/`, `server.ts`)

- Preserves all legacy pages (`CommandCenter`, `RiskMapPage`, `RiskAnalysisPage`, `WhatIfSimulationPage`, `ImpactResponsePage`, `FieldReportsPage`, `AlertsPage`, `HistoricalAnalysisPage`) while adding `GEOS 2.0 Research Hub` (`src/pages/GeosV2WorkspacePage.tsx`).
- `server.ts` proxies all `/api/v1/*` requests (JSON, multipart photo uploads up to `6 MB`, binary image responses, `Authorization` headers) to FastAPI (`127.0.0.1:8000`) and spawns the single-worker Uvicorn server automatically in development.
- Authentication tokens live strictly in React component state memory (never `localStorage` or `sessionStorage`).
