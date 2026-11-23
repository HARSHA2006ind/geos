# GeoResilience-NER 2.0 — Backend & Data Architecture

## 1. System Topology

GeoResilience-NER 2.0 separates the interactive web frontend, the Node/Express BFF + AI proxy, and the Python FastAPI + PostGIS geospatial backend so that real scientific rasters and ML pipelines remain isolated in Python while the React SPA works reliably in both single-node preview and multi-container server deployments.

```text
[ React + Vite + Leaflet SPA ]
        │
        ├── /api/gemini/*  ──► [ Express BFF (server.ts / dist/server.cjs) ]
        │                          • Zod validation, 15 req/min rate limiter
        │                          • 64 KB payload cap, security headers
        │                          • Configurable GEMINI_MODEL (narrative only)
        │
        └── /api/v1/*      ──► [ Express /api/v1 Proxy ]
                                   ├── Primary: FastAPI (FASTAPI_BACKEND_URL, port 8000)
                                   │     • RasterEnvironmentalService (rasterio, pyproj, shapely)
                                   │     • RainfallService (verified GPM IMERG JSON)
                                   │     • SQLAlchemy 2.0 + Alembic + PostgreSQL/PostGIS
                                   └── Fallback (when FastAPI offline in single-runtime preview):
                                         • src/server/pilotReader.ts (geotiff + UTM46N)
                                         • Reads the exact same backend/data/pilot/ artifacts
```

---

## 2. FastAPI Application Layout (`backend/`)

| Path | Responsibility |
|---|---|
| `backend/app/config.py` | Environment-driven `Settings` (`DATABASE_URL`, `PILOT_DATA_DIR`, `CORS_ORIGINS`, `LOG_LEVEL`). |
| `backend/app/logging_config.py` | Structured JSON logging formatter for container/server observability. |
| `backend/app/db.py` | SQLAlchemy 2.0 `Engine`, `SessionLocal`, `Base`, and `get_db()` dependency. |
| `backend/app/models.py` | Relational + spatial schema (`datasets`, `study_areas`, `rainfall_observations`, `landslide_events`, `field_reports`). |
| `backend/app/schemas.py` | Strict Pydantic v2 response contracts enforcing explicit provenance, timestamps, `missing_data_indicators`, and `landslide_probability: None`. |
| `backend/app/services/raster_service.py` | Samples Copernicus DEM (30 m core corridor with 90 m district fallback), Horn slope/aspect rasters, and ESA WorldCover 2021; checks boundary containment using Shapely. |
| `backend/app/services/rainfall_service.py` | Reads verified NASA GPM IMERG Late Run Daily observations with date filtering and strict `null` missing-value preservation. |
| `backend/app/main.py` | FastAPI entrypoint, CORS middleware, lifespan warmup, and `/api/v1/*` routes. |
| `backend/alembic/versions/0001_initial_schema.py` | Forward (`upgrade`) and rollback (`downgrade`) migration enabling PostGIS (`CREATE EXTENSION IF NOT EXISTS postgis` on PostgreSQL) and creating all 5 core tables with indexes. |
| `backend/ingestion/*.py` | Repeatable CLI ingestion scripts for OSM boundary, Copernicus DEM, NASA GPM IMERG, ESA WorldCover, and landslide inventory discovery. |

---

## 3. Working REST API Endpoints (`/api/v1/*`)

| Method & Path | Parameters | Response Guarantees |
|---|---|---|
| `GET /api/v1/health` | None | Reports service status, pilot study area, loaded artifact flags (`boundary`, `dem_30m`, `dem_utm46n`, `slope`, `aspect`, `worldcover`, `rainfall`, `inventory_discovery`), and `ml_model_deployed: false`. |
| `GET /api/v1/datasets` | None | Returns verified provenance metadata for every ingested dataset (URLs, CRS, native/derived resolution, observation period, processing timestamp, attribution, limitations). |
| `GET /api/v1/pilot/boundary` | None | Returns Dima Hasao GeoJSON boundary (`EPSG:4326`), `area_km2` (`4,880.75`), bounding box, elevation/slope summary stats, and ESA WorldCover class distribution. |
| `GET /api/v1/environment/point` | `lat` (`-90..90`), `lon` (`-180..180`) | Samples verified elevation, slope, aspect (degrees + cardinal), ESA WorldCover class, latest valid IMERG 24h/72h + window peak rainfall, per-dataset provenance, `missing_data_indicators`, and `landslide_probability: null`. Returns `null`s outside Dima Hasao (never fabricates). Rejects invalid coordinates with `HTTP 422`. |
| `GET /api/v1/rainfall/history` | Optional `start_date`, `end_date` (`YYYY-MM-DD`) | Returns daily NASA GPM IMERG Late Run series (`2024-05-01` to `2024-06-30`), preserving `29` missing days as `null`, plus summary stats and provenance. |
| `GET /api/v1/inventory/discovery` | None | Returns live probe status, registration/network blockers, and resolution steps for GSI Bhukosh, ISRO/NRSC Bhuvan, and NASA COOLR (`verified_pilot_landslide_records_count: 0`, `fabricated_labels_count: 0`). |

### Express BFF AI Endpoint
- `POST /api/gemini/geotechnical-briefing` — Zod-validated JSON payload, 15 req/min per-IP throttle, configurable `GEMINI_MODEL` (default `gemini-4-hydrogen`), narrative-only prompt guardrail prohibiting fabrication of unverified probabilities or Factor of Safety values, and safe HTTP 503/502 error handling when unconfigured or unreachable.

---

## 4. Database Schema (PostgreSQL + PostGIS)

Defined in `backend/app/models.py` and `backend/alembic/versions/0001_initial_schema.py`:
1. `datasets` — Provenance registry (`dataset_id`, `name`, `provider`, `product_version`, `source_url`, `crs`, `resolution_m`, `observation_period`, `attribution`, `limitations`, `ingested_at`).
2. `study_areas` — Administrative/basin polygons (`code`, `name`, `state`, `crs`, `area_km2`, `bbox_json`, `geometry_geojson` / PostGIS `GEOMETRY`).
3. `rainfall_observations` — Time-series observations (`dataset_id`, `study_area_code`, `observation_date`, `rainfall_24h_mm` nullable, `rainfall_72h_mm` nullable, `is_missing`, `source_job_id`).
4. `landslide_events` — Schema-ready table for verified historical landslide inventories (GSI / NRSC / COOLR) with `external_event_id`, `source_provider`, `event_date`, `location_accuracy_m`, `trigger`, `latitude`, `longitude`, and provenance fields. Currently empty (`0` rows) pending verified inventory import.
5. `field_reports` — Schema-ready table for authenticated officer / citizen ground observations (separate from verified historical training labels).

---

## 5. Server Deployment & Resource Footprint (`backend/docker-compose.yml`)

Designed to run comfortably within a modest single-server footprint (**4 vCPU, 8 GB RAM, 20 GB SSD**):

| Container / Service | Image / Runtime | Memory Limit | CPU Limit | Disk Footprint |
|---|---|---:|---:|---:|
| `postgis` | `postgis/postgis:16-3.4-alpine` | `2.0 GB` | `1.5 vCPU` | ~400 MB base + DB growth |
| `backend` (FastAPI) | Python 3.11-slim (`backend/Dockerfile`, 2 Uvicorn workers) | `2.0 GB` | `1.5 vCPU` | ~550 MB image + 14.4 MB pilot data |
| `frontend` / Express BFF | Node 20 (`dist/` + `dist/server.cjs`) | `512 MB` | `0.5 vCPU` | ~120 MB |
| **Total Allocated** | | **4.5 GB / 8 GB** | **3.5 / 4 vCPU** | **~1.1 GB / 20 GB** |

### Deployment Readiness Status
- **Ready for staging/research deployment:** Dockerfiles, `docker-compose.yml`, Alembic migrations, `.env.example`, structured JSON logging, healthchecks, and automated test suites are complete.
- **Not yet ready for public production alerting:** Requires TLS reverse proxy (Nginx/Caddy), authentication/RBAC for officer field-report writes, automated daily rainfall ingestion cron with Earthdata credentials, and a spatially cross-validated ML model (see `GEOS_REMAINING_BLOCKERS.md`).
