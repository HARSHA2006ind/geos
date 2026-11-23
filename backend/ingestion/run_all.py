"""
Master orchestrator for Phase 3 real data acquisition over Dima Hasao district, Assam.
Executes:
  1. Validated administrative boundary (OSM Nominatim, EPSG:4326)
  2. Dataset A: Copernicus DEM GLO-30 (30 m) + metric UTM46N slope & aspect
  3. Dataset B: NASA GPM IMERG Daily precipitation (via ClimateSERV) + 24h/72h accumulations
  4. Dataset C: ESA WorldCover 10 m v200 (2021) land cover
  5. Dataset D: Landslide inventory discovery probe (GSI, ISRO/NRSC, NASA COOLR)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backend.ingestion.discover_landslide_inventories import probe_landslide_inventories
from backend.ingestion.fetch_boundary import fetch_dima_hasao_boundary
from backend.ingestion.fetch_copernicus_dem import ingest_copernicus_dem
from backend.ingestion.fetch_gpm_imerg import ingest_gpm_imerg_rainfall
from backend.ingestion.fetch_worldcover import ingest_worldcover

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"


def run_all() -> dict:
    started_at = datetime.now(timezone.utc).isoformat()
    print("[1/5] Fetching Dima Hasao administrative boundary (OSM Nominatim)...")
    boundary_meta = fetch_dima_hasao_boundary(PILOT_DIR)

    print("[2/5] Ingesting Copernicus DEM GLO-30 + deriving slope & aspect (EPSG:32646)...")
    dem_meta = ingest_copernicus_dem(PILOT_DIR / "dima_hasao_boundary.geojson", PILOT_DIR)

    print("[3/5] Ingesting NASA GPM IMERG daily rainfall (May–June 2024 monsoon window)...")
    rain_meta = ingest_gpm_imerg_rainfall(PILOT_DIR / "dima_hasao_boundary.geojson", PILOT_DIR)

    print("[4/5] Ingesting ESA WorldCover 10 m v200 (2021) land cover...")
    wc_meta = ingest_worldcover(PILOT_DIR / "dima_hasao_boundary.geojson", PILOT_DIR)

    print("[5/5] Probing official landslide inventories (GSI, ISRO/NRSC, NASA COOLR)...")
    inv_meta = probe_landslide_inventories(PILOT_DIR)

    manifest = {
        "pilot_study_area": "Dima Hasao District, Assam, India",
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "boundary": boundary_meta,
        "copernicus_dem": dem_meta,
        "gpm_imerg_rainfall": rain_meta,
        "esa_worldcover": wc_meta,
        "landslide_inventory_discovery": {
            "verified_records": inv_meta["verified_pilot_landslide_records_count"],
            "fabricated_labels_count": inv_meta["fabricated_labels_count"],
            "providers_probed": len(inv_meta["providers"]),
        },
    }
    (PILOT_DIR / "ingestion_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    res = run_all()
    print(json.dumps(res, indent=2))
