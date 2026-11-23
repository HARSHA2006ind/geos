#!/usr/bin/env bash
# Phase L & M — GeoResilience-NER 2.0 Database Restore & Integrity Verification Script
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <backup_file.gz> [target_sqlite_path]" >&2
  exit 1
fi

BACKUP_FILE="$1"
TARGET_SQLITE="${2:-backend/data/pilot/geos_platform_restored.db}"

if [[ -f "${BACKUP_FILE}.sha256" ]]; then
  sha256sum -c "${BACKUP_FILE}.sha256"
fi

if [[ "$BACKUP_FILE" == *.sql.gz ]]; then
  : "${DATABASE_URL:?DATABASE_URL must be set for PostgreSQL restore}"
  gunzip -c "$BACKUP_FILE" | psql "${DATABASE_URL/postgresql+psycopg:/postgresql:}"
  echo "PostgreSQL restore completed."
else
  gunzip -c "$BACKUP_FILE" > "$TARGET_SQLITE"
  backend/.venv/bin/python -c '
import sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
res = conn.execute("PRAGMA integrity_check;").fetchone()[0]
tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type=\"table\"").fetchall()]
conn.close()
assert res == "ok", f"Integrity check failed: {res}"
print(f"SQLite restore verified OK ({len(tables)} tables): {res}")
' "$TARGET_SQLITE"
fi
