# GeoResilience-NER 2.0 — Repository Recovery & Preservation Report

**Upstream Repository:** `https://github.com/HARSHA2006ind/geos`
**Upstream `main` Base Commit:** `4fc1e03` (`feat: initialize GeoResilience-NER platform project`)
**Recovery Branch Created:** `feature/geos-v2-foundation` (branched cleanly from `main`; `main` untouched)
**Recovery Workspace:** `/tmp/geos-recovery`
**Verification Date (UTC):** `2026-11-23`

---

## 1. Initial Workspace Diagnosis

- **Active Application Directory:** `/app/applet` (mapped to `/` in workspace).
- **Git Metadata Check:** `git status` inside `/app/applet` returned `fatal: not a git repository (or any of the parent directories): .git`.
- **Upstream Comparison against `origin/main` (`4fc1e03`):**
  - `36` files in upstream `main`.
  - `15` files unchanged, `21` files modified, `0` original files deleted, and `60+` new GEOS 2.0 backend, ingestion, ML pipeline, test, and scientific documentation files added.
- **GitHub Push Authentication Check:**
  - Verified with `GIT_TERMINAL_PROMPT=0 git push --dry-run origin feature/geos-v2-foundation`:
  - Result: **`fatal: could not read Username for 'https://github.com': terminal prompts disabled`**.
  - No GitHub PAT (`GITHUB_TOKEN`/`GH_TOKEN`), `gh` CLI session, or `~/.ssh` deploy key is provisioned inside this isolated container.
  - **Safety Guarantee:** Never force-pushed, never modified `main`, and never bypassed authentication.

---

## 2. Preservation Artifacts Created

To guarantee **zero risk of losing GEOS 2.0 work**, the complete git commit history and clean source tree are preserved in three redundant forms:

1. **Full Recovered Git Clone (Branch `feature/geos-v2-foundation`):** `/tmp/geos-recovery`
   - Clean linear history branched from `origin/main` (`4fc1e03`):
     - Commit 1: `feat(geos-v2): recover Phase 0 & Phase 1 real data foundation and backend`
     - Commit 2: `feat(geos-v2): add NASA COOLR inventory, 10-year IMERG rainfall, 13-check quality gate, and ML readiness reports`
2. **Portable Git Bundle (Verified with `git bundle verify`):** `/tmp/geos-v2-foundation.bundle`
3. **Clean Exportable Source Archive:** `/tmp/geos-v2-foundation-export.tar.gz`

### Files Excluded from Git (`.gitignore` Enforced)
- Secrets & local environment files: `.env*` (keeping `.env.example` and `backend/.env.example` tracked)
- Virtual environments & caches: `backend/.venv/`, `node_modules/`, `__pycache__/`, `*.pyc`, `.pytest_cache/`
- Build outputs: `dist/`, `build/`, `coverage/`
- Large binary rasters & local SQLite verification DB: `backend/data/pilot/*.tif`, `backend/data/pilot/*.db`, `backend/data/raw/`
- Export archives: `*.bundle`, `*.tar.gz`

All dataset manifests (`ingestion_manifest.json`, `copernicus_dem_metadata.json`, `worldcover_metadata.json`, `dima_hasao_boundary.geojson`, `dima_hasao_landslides_coolr.json`, `dima_hasao_rainfall_multiyear.json`, `data_quality_gate_report.json`) and reproducible download scripts (`backend/ingestion/*.py`) ARE tracked in Git.

---

## 3. Exact Commands to Push `feature/geos-v2-foundation` to GitHub

On any developer machine authenticated to `https://github.com/HARSHA2006ind/geos`:

### Option A — Using the Portable Git Bundle (Preserves Exact Commits)
```bash
git clone https://github.com/HARSHA2006ind/geos.git
cd geos
git fetch /path/to/geos-v2-foundation.bundle feature/geos-v2-foundation:feature/geos-v2-foundation
git checkout feature/geos-v2-foundation
git log -n 4 --oneline
git push -u origin feature/geos-v2-foundation
```

### Option B — Regenerating Excluded Pilot Rasters After Cloning
```bash
python3 -m venv backend/.venv
backend/.venv/bin/pip install -r backend/requirements.txt
PYTHONPATH=. backend/.venv/bin/python -m backend.ingestion.run_all
PYTHONPATH=. backend/.venv/bin/python -m backend.ingestion.fetch_coolr_landslides
PYTHONPATH=. backend/.venv/bin/python -m backend.ingestion.fetch_rainfall_multiyear
PYTHONPATH=. backend/.venv/bin/python -m backend.app.quality_gate
```
