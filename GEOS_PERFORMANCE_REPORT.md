# GeoResilience-NER 2.0 — Performance & Load Benchmark Report

**Benchmark Environment:** Unified Staging Stack (`:3000` Express Proxy -> `:8001` FastAPI Uvicorn -> `:5432` PostgreSQL 15.20 + PostGIS 3.3.2), `4 GB` container RAM (`804 MB` baseline used).

---

## 1. Root Bottlenecks Identified (Before Optimization)

1. **Uncached 13-Check Scientific Quality Gate Re-Evaluation:** `/api/v1/quality-gate`, `/api/v1/ml/readiness`, and `/api/v1/hazard/assess` called `evaluate_data_quality_gate()` per request, re-opening and computing full-raster statistics over 16+ GeoTIFF rasters and re-parsing multi-hundred-record JSON files (~`1,088 ms` to `1,133 ms` per request!).
2. **Repeated Raster File Opens & Uncached Point Sampling:** Every `/api/v1/environment/point`, `/terrain`, `/soil`, and `/hazard/assess` opened `rasterio` handles from scratch.
3. **Unpooled Express -> FastAPI HTTP Requests:** `tryProxyToFastApi` in `server.ts` created new TCP connections per request (`fetch`) rather than reusing persistent keep-alive sockets.
4. **Full Linear Scan in OSM Proximity Index:** `InfrastructureExposureIndex.query_proximity` ran spherical `haversine_m` over all facilities and transport segments without bounding-box pre-filtering.
5. **Uncompressed Large GeoJSON/JSON Payloads & Missing SQLAlchemy Pool Tuning:** `gsi-bhusanket` (`508.8 KB`) lacked `GZipMiddleware`, and PostgreSQL connections lacked explicit `pool_size` / `pool_pre_ping` sizing.

---

## 2. Optimizations Implemented (Zero Behavioral or Scientific Weakening)

- **`backend/app/db.py`:** Configured PostgreSQL `QueuePool` (`pool_size=10`, `max_overflow=20`, `pool_recycle=1800`, `pool_pre_ping=True`).
- **`backend/app/services/hazard_engine.py`:**
  - Added `mtime_ns`-verified + `120s` TTL cache (`get_cached_quality_gate`) with thread locking.
  - Added bounding-box degree pre-filter (`dlat_deg`, `dlon_deg`) + 512-entry bounded LRU cache on `InfrastructureExposureIndex.query_proximity`.
  - Added `mtime_ns`-validated JSON cache for `dima_hasao_gfs_forecast_eval.json` while computing `forecast_age_hours` and `is_stale` dynamically on every read.
- **`backend/app/services/raster_service.py` & `rainfall_service.py`:** Added `mtime_ns`-validated `rasterio.DatasetReader` cache, JSON read cache, and bounded 512-entry point LRU cache (automatically invalidated if file modification timestamps advance).
- **`backend/app/main.py` & `routers_v2.py`:** Added `GZipMiddleware(minimum_size=1024)` and `mtime_ns`-cached static JSON helper `_read_cached_json()` for public read-only scientific artifacts. **No user-private tables (`field_reports`, `users`, `experimental_alerts`, `audit_logs`) are ever cached across accounts.**
- **`server.ts`:** Replaced per-request `fetch()` in `tryProxyToFastApi` with persistent `http.Agent` / `https.Agent` (`keepAlive: true`, `maxSockets: 64`) forwarding `Accept-Encoding` and `Content-Encoding`.

---

## 3. Single-Endpoint Latency Comparison (Before vs After via `:3000`)

| Endpoint | Before Cold (ms) | Before p50 (ms) | Before p95 (ms) | After Cold (ms) | After p50 (ms) | After p95 (ms) | Warm Speedup (p50) |
|---|---:|---:|---:|---:|---:|---:|---:|
| `GET /api/health` | `7.30` | `1.90` | `2.10` | `4.09` | `1.09` | `1.71` | `1.7x` |
| `GET /api/v1/health` | `84.10` | `10.20` | `12.40` | `6.31` | `4.20` | `4.95` | `2.4x` |
| `GET /api/v1/environment/point` | `79.40` | `24.30` | `25.30` | `3.77` | `3.06` | `4.15` | **`7.9x`** |
| `GET /api/v1/hazard/assess` | `1481.00` | `68.10` | `69.60` | `1138.91` | `3.58` | `4.88` | **`19.0x`** |
| `POST /api/v1/hazard/simulate` | `55.40` | `31.70` | `33.40` | `7.40` | `6.00` | `7.19` | **`5.3x`** |
| `GET /api/v1/quality-gate` | `1117.10` | `1087.90` | `1176.90` | `5.92`* | `4.25` | `4.85` | **`256.0x`** |
| `GET /api/v1/ml/readiness` | `1133.00` | `1133.00` | — | `4.42`* | `3.89` | `4.66` | **`291.3x`** |
| `GET /api/v1/landslides/gsi-bhusanket` (raw) | `26.20` | `25.60` | `34.60` | `20.71` | `14.49` | `24.58` | `1.8x` |
| `GET /api/v1/landslides/gsi-bhusanket` (gzip) | `508.8 KB` | — | — | `32.4 KB` | `26.38` | `31.43` | **`-93.6% payload`** |
| `GET /api/v1/auth/bootstrap-status` | `10.90` | `6.60` | `7.40` | `5.79` | `4.81` | `6.45` | `1.4x` |
| `GET /api/v1/datasets` | `16.30` | `15.20` | `17.00` | `10.65` | `9.18` | `12.58` | `1.7x` |
| Direct PostGIS Spatial Query | `78.98` | `11.53` | `16.73` | `14.04` | `0.36` | `0.56` | **`32.0x`** |

*\*Note: First cold computation of Quality Gate occurred inside `hazard_assess` (`1138.91 ms`); subsequent `quality-gate` and `ml/readiness` reads hit the `mtime_ns`-validated cache in `<6 ms`.*

### Additional Verified Endpoints (Measured After Optimization)

| Endpoint | Cold (ms) | p50 (ms) | p95 (ms) | Max (ms) | Payload (Bytes) |
|---|---:|---:|---:|---:|---:|
| `GET /api/v1/environment/terrain` | `2.45` | `2.63` | `3.50` | `3.68` | `1,478` |
| `GET /api/v1/environment/soil` | `3.82` | `2.57` | `6.46` | `8.11` | `1,165` |
| `GET /api/v1/environment/rainfall/history` | `3.10` | `3.01` | `3.88` | `4.36` | `10,763` |
| `GET /api/v1/environment/rainfall/multiyear` | `3.57` | `3.38` | `3.72` | `3.83` | `30,501` |
| `GET /api/v1/environment/rainfall/forecast` | `2.68` | `2.70` | `3.06` | `3.14` | `773` |
| `GET /api/v1/infrastructure/exposure` | `3.30` | `2.85` | `3.88` | `4.93` | `4,030` |
| `GET /api/v1/ml/models` | `4.28` | `3.36` | `4.45` | `4.46` | `11,186` |
| `GET /api/v1/monitoring/status` | `7.28` | `5.51` | `6.91` | `7.28` | `3,384` |
| `GET /api/v1/regions` | `6.76` | `5.96` | `6.76` | `6.93` | `3,841` |
| `POST /api/v1/auth/login` (scrypt) | `56.75` | `56.46` | `57.34` | `58.35` | `474` |
| `GET /api/v1/auth/me` (Bearer token) | `7.08` | `5.17` | `6.69` | `18.84` | `153` |

---

## 4. Concurrent Mixed Load Tests (64 Requests @ 16 Concurrency)

| Workload Mix | Stage | Requests | Conc. | Errors | Elapsed (s) | Throughput (req/s) | p50 (ms) | p95 (ms) | p99 (ms) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **Mix A** (`health`, `point`, `hazard/assess`, `forecast`) | **BEFORE** | `64` | `16` | `0` | `3.454` | `18.53` | `686.74` | `1,644.59` | `1,854.47` |
| **Mix A** (`health`, `point`, `hazard/assess`, `forecast`) | **AFTER** | `64` | `16` | **`0`** | **`0.158`** | **`404.77`** | **`33.32`** | **`60.09`** | **`70.95`** |
| **Mix B** (incl. `quality-gate`, `ml/readiness`, `auth/bootstrap-status`) | **BEFORE** | `64` | `16` | `0` | `~16.1` | `3.97` | `1,840.00` | `10,790.00` | — |
| **Mix B** (`hazard/assess`, `quality-gate`, `ml/readiness`, `auth/bootstrap-status`) | **AFTER** | `64` | `16` | **`0`** | **`0.230`** | **`278.53`** | **`47.96`** | **`91.28`** | **`102.99`** |

- **Peak Runtime Memory Footprint (during benchmark suite):**
  - FastAPI (`python` / Uvicorn): `~289–301 MB` RSS (`~7.0%` CPU during burst)
  - Express/Vite (`node` + `esbuild`): `~283–361 MB` RSS
  - PostgreSQL + PostGIS backends: `~44.5 MB` RSS per active worker
  - Total container RAM stays comfortably under `<1 GB` used (`4 GB` total / `8 GB` target host).
