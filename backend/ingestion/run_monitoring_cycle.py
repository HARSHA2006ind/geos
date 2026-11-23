"""
Phase J — Cron-Ready Environmental Monitoring Cycle CLI.

Usage:
  PYTHONPATH=. backend/.venv/bin/python backend/ingestion/run_monitoring_cycle.py
  PYTHONPATH=. backend/.venv/bin/python backend/ingestion/run_monitoring_cycle.py --refresh-live-gfs
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.db import Base, build_engine
from backend.app.services.monitoring_service import (
    ensure_regional_coverage_seeded,
    execute_monitoring_cycle,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run GeoResilience-NER 2.0 environmental monitoring cycle.")
    parser.add_argument(
        "--refresh-live-gfs",
        action="store_true",
        help="Attempt live CPU-only Dynamical.org NOAA GFS Zarr v3 refresh before recording run.",
    )
    parser.add_argument(
        "--db-url",
        default=None,
        help="Optional SQLAlchemy database URL override (defaults to local SQLite platform DB).",
    )
    args = parser.parse_args()

    settings = get_settings()
    if args.db_url:
        db_url = args.db_url
    elif settings.database_url.startswith("sqlite"):
        db_url = settings.database_url
    else:
        try:
            probe_eng = build_engine(settings.database_url)
            with probe_eng.connect():
                pass
            db_url = settings.database_url
        except Exception:
            db_url = f"sqlite:///{(settings.pilot_data_dir / 'geos_platform.db').resolve()}"

    engine = build_engine(db_url)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    with SessionFactory() as db:
        ensure_regional_coverage_seeded(db)
        result = execute_monitoring_cycle(
            db=db,
            pilot_dir=Path(settings.pilot_data_dir),
            refresh_live_gfs=args.refresh_live_gfs,
        )
    result["database_dialect"] = engine.dialect.name
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
