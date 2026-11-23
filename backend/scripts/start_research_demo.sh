#!/usr/bin/env bash
# GeoResilience-NER 2.0 — Reproducible Research-Demo Launch Script
# Starts PostgreSQL/PostGIS (if configured), runs Alembic migrations, executes an initial
# monitoring freshness cycle, and launches the unified Express + FastAPI server on :3000.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

export PYTHONPATH="."
export PORT="${PORT:-3000}"

if [[ ! -d "backend/.venv" ]]; then
  echo "ERROR: Python virtual environment missing at backend/.venv" >&2
  echo "Create it with: python3 -m venv backend/.venv && backend/.venv/bin/pip install -r backend/requirements.txt" >&2
  exit 1
fi

if [[ -f "backend/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "backend/.env"
  set +a
fi

if command -v pg_isready >/dev/null 2>&1 && [[ "${DATABASE_URL:-}" == postgresql* ]]; then
  echo "[1/4] Verifying PostgreSQL/PostGIS connectivity..."
  pg_isready -h 127.0.0.1 -p 5432 || {
    echo "PostgreSQL not accepting connections on 127.0.0.1:5432; start via docker compose or pg_ctlcluster." >&2
    exit 1
  }
fi

echo "[2/4] Running Alembic database migrations (head)..."
backend/.venv/bin/alembic -c backend/alembic.ini upgrade head

echo "[3/4] Running initial environmental monitoring freshness cycle (cached NOAA GFS check)..."
backend/.venv/bin/python backend/ingestion/run_monitoring_cycle.py >/dev/null

echo "[4/4] Starting GeoResilience-NER 2.0 server on port ${PORT}..."
exec npm run dev
