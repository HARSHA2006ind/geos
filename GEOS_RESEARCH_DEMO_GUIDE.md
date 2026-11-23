# GeoResilience-NER 2.0 — Reproducible Research-Demo Launch Guide

This guide describes how to launch and demonstrate **GeoResilience-NER 2.0** reproducibly on a local developer workstation or an 8 GB RAM / 4 vCPU Ubuntu Linux host (CPU-only, no GPU required).

---

## 1. Prerequisites

- **Node.js** `>= 20` (plus `npm` or `bun`)
- **Python** `3.11+` (`backend/.venv` with `backend/requirements.txt` installed)
- **PostgreSQL 15/16 + PostGIS 3.3/3.4** running locally or via `backend/docker-compose.yml`

---

## 2. Environment Configuration

Copy the template without committing secrets:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
```

Key server-side environment variables:
- `DATABASE_URL`: PostgreSQL/PostGIS DSN (or SQLite fallback when Postgres is stopped)
- `GEMINI_API_KEY`: Optional server-side Google Gemini API key (never exposed to browser)
- `GEMINI_MODEL`: Configured model alias (default: `gemini-4-hydrogen`)
- `GEOS_AUTH_SECRET`: Stable signing secret for in-memory HMAC-SHA256 Bearer tokens
- `NASA_EARTHDATA_TOKEN`: Optional NASA Earthdata Login token for post-2024-06-01 IMERG HDF5 backfill

---

## 3. One-Command Research-Demo Launch

```bash
./backend/scripts/start_research_demo.sh
```

This script verifies:
1. Python `.venv` and PostgreSQL/PostGIS readiness (when `DATABASE_URL` points to PostgreSQL)
2. `alembic -c backend/alembic.ini upgrade head` (all 19 schema tables & spatial indexes)
3. Initial environmental monitoring freshness check (`backend/ingestion/run_monitoring_cycle.py`)
4. Unified Express (`:3000`) + Vite SPA + FastAPI (`:8001` proxied under `/api/v1/*`) startup.

### Docker Compose Option (Linux Host)

```bash
cd backend
docker compose up -d --build
docker compose exec api alembic -c backend/alembic.ini upgrade head
```

---

## 4. Interactive Walkthrough Checklist

1. Open `http://localhost:3000` -> select **GEOS 2.0 Research Hub**.
2. **Tab 1 — Hazard, Soil & Gemini:** Click **Haflong** or **Jatinga** presets to inspect Copernicus DEM slope/aspect/TRI/TWI, ISRIC SoilGrids 2.0 clay & bulk density, Sentinel-2 2024 NDVI, stale IMERG history (`null` missing days), experimental NOAA GFS 0.25° outlook, and real OSM proximity assets. Test the Grounded Gemini Assistant (`GET /api/v1/assistant/models` verifies discovery; prompt injection attempts are blocked with HTTP `400`).
3. **Tab 2 — ML Gate & SHAP Benchmark:** Verify `overall_ml_ready: false` (`6/13` checks passing), test `POST /api/v1/ml/infer` returning `landslide_probability: null`, and review the exploratory 5-fold spatial-block CV benchmark + corridor-bias diagnostic (`+0.123` RF / `+0.172` XGB inflation).
4. **Tab 3 — Server What-If Stress Test:** Adjust hypothetical 24h/72h/7d rainfall sliders and run `/api/v1/hazard/simulate` (strictly labeled hypothetical with `landslide_probability: null` and `factor_of_safety: null`).
5. **Tab 4 — Auth & Field Reports:** On a fresh database, use **Claim First Admin** once (locks permanently afterward), or **Register** a `field_officer` account, upload a geotagged PNG/JPEG/WebP site photo, sign in as `admin`, and verify/reject the pending submission.
6. **Tab 5 — Experimental Alerts:** Draft an evidence-linked research alert (`EXPERIMENTAL_RESEARCH_DRAFT`, `official_government_warning: false`), approve internally, and log a dry-run audit notification.
7. **Tab 6 — Monitoring & 8-State NER:** Inspect recent monitoring cycles and the transparent 8-state Northeast India expansion status table.
