#!/usr/bin/env bash
# Phase L & M — GeoResilience-NER 2.0 Database Backup Script (PostgreSQL or SQLite)
set -euo pipefail

BACKUP_DIR="${1:-backend/data/backups}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$BACKUP_DIR"

if [[ -n "${DATABASE_URL:-}" && "${DATABASE_URL}" == postgresql* ]]; then
  OUT_FILE="${BACKUP_DIR}/geos_pg_${TIMESTAMP}.sql.gz"
  pg_dump "${DATABASE_URL/postgresql+psycopg:/postgresql:}" | gzip > "$OUT_FILE"
  sha256sum "$OUT_FILE" > "${OUT_FILE}.sha256"
  echo "PostgreSQL backup created: ${OUT_FILE}"
else
  SQLITE_DB="${SQLITE_DB_PATH:-backend/data/pilot/geos_platform.db}"
  if [[ ! -f "$SQLITE_DB" ]]; then
    echo "SQLite database not found at ${SQLITE_DB}" >&2
    exit 1
  fi
  OUT_FILE="${BACKUP_DIR}/geos_sqlite_${TIMESTAMP}.db.gz"
  backend/.venv/bin/python -c '
import gzip, pathlib, shutil, sqlite3, sys, tempfile
src_path, out_path = sys.argv[1], sys.argv[2]
src = sqlite3.connect(src_path)
fd, tmp_name = tempfile.mkstemp(suffix=".db")
tmp = pathlib.Path(tmp_name)
dst = sqlite3.connect(str(tmp))
src.backup(dst)
dst.close()
src.close()
with open(tmp, "rb") as fin, gzip.open(out_path, "wb") as fout:
    shutil.copyfileobj(fin, fout)
tmp.unlink()
' "$SQLITE_DB" "$OUT_FILE"
  sha256sum "$OUT_FILE" > "${OUT_FILE}.sha256"
  echo "SQLite backup created: ${OUT_FILE}"
fi
