# GeoResilience-NER 2.0 — Production Deployment Guide (Ubuntu 8 GB RAM / 4 vCPU / 20 GB SSD)

---

## 1. Hardware Resource Budget & Measured Footprint

Designed explicitly for a CPU-only **4 vCPU, 8 GB RAM, 20 GB SSD** Ubuntu Linux host (zero GPU/CUDA packages installed):

| Component | Configured Memory Ceiling (`docker-compose.yml`) | Measured Local Footprint |
| :--- | :---: | :--- |
| PostgreSQL 16 + PostGIS 3.4 | `1.5 GB` (`shared_buffers=256MB`, `work_mem=8MB`) | Lightweight relational + spatial tables |
| FastAPI Backend (Uvicorn, **1 worker**) | `1.5 GB` | **`347.1 MB` peak RSS** under full raster + ML + API load |
| Automated Environmental Monitor | `512 MB` | Periodic `run_monitoring_cycle.py` check |
| Caddy 2 TLS Reverse Proxy + Static SPA | `256 MB` | Serves compiled `dist/` + TLS termination |
| **Total Container Ceiling** | **`3.75 GB` / `8.0 GB` RAM (47%)** | Leaves `> 4 GB` headroom for OS & file cache |
| **Disk Footprint** | **Target `< 20 GB` SSD** | `pilot=52 MB`, `raw=1.7 MB`, `experimental=46 KB`, `.venv=825 MB` (`~0.88 GB` total backend) |

---

## 2. Environment Variables (`.env`)

Copy `.env.example` to `.env` on the server (never commit `.env`):

```bash
DATABASE_URL=postgresql+psycopg://geos:<STRONG_DB_PASSWORD>@db:5432/georesilience
POSTGRES_PASSWORD=<STRONG_DB_PASSWORD>
GEOS_AUTH_SECRET=<32_PLUS_BYTE_RANDOM_HEX>
GEMINI_API_KEY=<OPTIONAL_SERVER_SIDE_GEMINI_KEY>
GEMINI_MODEL=gemini-4-hydrogen
NASA_EARTHDATA_TOKEN=<OPTIONAL_EARTHDATA_BEARER_TOKEN_FOR_IMERG_V07B>
CORS_ORIGINS=https://your-domain.example.org
```

---

## 3. Deployment Steps (Ubuntu 22.04 / 24.04 LTS)

```bash
# 1. Build frontend production static bundle
npm ci && npm run build

# 2. Launch PostGIS + FastAPI + Monitor + Caddy TLS stack
docker compose -f backend/docker-compose.yml up -d --build

# 3. Apply all Alembic database migrations (0001 -> 0003)
docker compose -f backend/docker-compose.yml exec api alembic -c backend/alembic.ini upgrade head

# 4. Verify health and quality gate status
curl -fsS http://127.0.0.1:8000/api/v1/health
curl -fsS http://127.0.0.1:8000/api/v1/ml/readiness
```

### First-Run Administrator Bootstrap
Immediately after launch, open the **GEOS 2.0 Research Hub** (or call `POST /api/v1/auth/claim-admin`) to claim the initial administrator account with a strong password. Subsequent calls to `/claim-admin` are permanently locked (`409 Conflict`).

---

## 4. Automated Monitoring & Verified Backup / Restore

### Cron Schedule (Host or Monitor Container)
```cron
# Refresh environmental freshness & NOAA GFS outlook every 6 hours
0 */6 * * * cd /opt/geos && PYTHONPATH=. backend/.venv/bin/python backend/ingestion/run_monitoring_cycle.py --refresh-gfs >> /var/log/geos_monitor.log 2>&1

# Daily compressed database backup with SHA-256 checksum at 02:30 UTC
30 2 * * * cd /opt/geos && bash backend/scripts/backup_db.sh /var/backups/geos >> /var/log/geos_backup.log 2>&1
```

### Backup & Restore Verification (Tested End-to-End)
```bash
# Create compressed backup + .sha256 manifest (auto-detects PostgreSQL vs SQLite)
bash backend/scripts/backup_db.sh /var/backups/geos

# Restore & run automated checksum + SQLite/PostgreSQL integrity check
bash backend/scripts/restore_db.sh /var/backups/geos/geos_sqlite_<TIMESTAMP>.db.gz /tmp/restore_verify.db
```
Verified locally on `2026-11-23`: checksum passed (`OK`) and restored SQLite passed `PRAGMA integrity_check` across all `19` tables (`ok`).
