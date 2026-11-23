# GeoResilience-NER 2.0 — Dependency Security Report

**Audit Date:** 2026-11-23  
**Scope:** Node.js / TypeScript workspace (`package.json`, `bun.lock`) and Python backend environment (`backend/requirements.txt`, `backend/.venv`)

---

## 1. Node.js Advisory Audit (Before vs After)

### Before Remediation (`bun audit --json`)
A baseline audit identified **11 advisories** (1 Critical, 3 High, 6 Moderate, 1 Low) across transitive and direct build/server packages:

| Package | Vulnerable Version | Severity | Advisory ID | Remediation Target |
|---|---|---|---|---|
| `proxy-addr` | `2.0.7` | Critical | `GHSA-jqcg-44mw-7w3h` | `>= 2.0.8` |
| `body-parser` | `1.20.6` | High | `GHSA-27r3-jxmh-p828` | `>= 1.20.9` |
| `qs` | `6.15.3` | Moderate (3) | `GHSA-x5fp-wj9c-mxmx`, `GHSA-4mjr-xmp4-gh2g`, `GHSA-6pq8-jhm2-2vcw` | `>= 6.16.2` |
| `source-map-js` | `1.2.1` | High | `GHSA-68fv-2mgg-jv7q` | `>= 1.2.2` |
| `vite` | `6.4.3` | High (1), Moderate (3), Low (1) | `GHSA-587h-7wmj-h5pm`, `GHSA-rq7h-c2jc-7f22`, `GHSA-698v-4r3x-3vcv`, `GHSA-r825-w8mm-5pxw`, `GHSA-9jrq-w75r-8gcw` | `>= 6.4.6` |

### Applied Changes (`/package.json` & `/bun.lock`)
Preserving major versions to avoid breaking API changes in Express 4.x and Vite 6.x:
- Updated `express` from `^4.21.2` to `^4.22.3`
- Updated `vite` from `^6.4.3` to `^6.4.6` (removed duplicate `vite` key in `devDependencies`)
- Added targeted `"overrides"` constraints:
  - `"body-parser": "^1.20.9"`
  - `"proxy-addr": "^2.0.8"`
  - `"qs": "^6.16.2"`
  - `"source-map-js": "^1.2.4"`

### After Remediation Verification
- `bun install`: clean resolution (`383` packages installed cleanly, zero warnings).
- `bun audit`: **`No vulnerabilities found (checked 349 packages)`** (`0` Critical, `0` High, `0` Moderate, `0` Low).
- `npm run lint` (`tsc --noEmit`): **PASS** (`0` TypeScript errors).
- `npm run test` (`vitest run`): **PASS** (`9/9` frontend/proxy regression tests).

---

## 2. Python Backend Dependencies (`backend/requirements.txt` & `.venv`)

All Python packages are pinned cleanly to current 2025/2026 releases inside `backend/requirements.txt`:

| Package | Installed Version | Role |
|---|---|---|
| `fastapi` | `0.115.12` | Core ASGI API framework |
| `starlette` | `0.46.2` | ASGI routing, GZipMiddleware, request lifecycle |
| `uvicorn` | `0.34.2` | Production/staging ASGI worker |
| `pydantic` / `pydantic-core` | `2.11.4` / `2.33.2` | Strict schema validation (`ge`/`le` bounds, regex rules) |
| `SQLAlchemy` / `GeoAlchemy2` | `2.0.40` / `0.17.1` | Pooled PostGIS ORM + parameterized queries |
| `psycopg` / `psycopg-binary` | `3.2.6` | PostgreSQL 15/16 wire driver |
| `httpx` | `0.28.1` | Async upstream Gemini HTTP client |
| `python-multipart` | `0.0.20` | Multipart image upload parsing (with magic-byte validation) |
| `rasterio` / `pyproj` / `shapely` / `geopandas` | `1.4.3` / `3.7.2` / `2.1.0` / `1.0.1` | CRS-aware GeoTIFF sampling & spatial geometry checks |
| `scikit-learn` / `xgboost-cpu` / `shap` | `1.6.1` / `2.1.4` / `0.46.0` | Exploratory spatial-block CV research diagnostics (deployment-gated) |

**Audit Boundary Note:** `pip-audit` is not installed in the container's offline `backend/.venv`, so automated online PyPI CVE database lookup was not executed locally. All runtime packages are pinned to current supported releases, and secret/upload/path-confinement/rate-limiting protections remain enforced and regression-tested (`43/43` pytest tests passing).
