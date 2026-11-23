"""
Dataset D — Landslide Inventory Discovery Probe.

Probes official machine-readable access endpoints for:
  1. Geological Survey of India (GSI) Bhukosh / Bhusanket
  2. ISRO / NRSC Landslide Atlas of India & Bhuvan Disaster Portal
  3. NASA Global Landslide Catalog (GLC) / COOLR (ArcGIS FeatureServer & Open Data)

NEVER fabricates landslide labels. Records exact HTTP status, accessibility,
credential/registration requirements, and step-by-step resolution instructions.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"

CANDIDATE_ENDPOINTS = [
    {
        "provider": "Geological Survey of India (GSI)",
        "dataset": "GSI Bhusanket (NLSM 1:50k/1:10k, Statewise Reports) & Bhukosh Landslide Inventory",
        "portal_url": "https://bhusanket.gsi.gov.in/",
        "secondary_url": "https://bhukosh.gsi.gov.in/Bhukosh/Public",
        "probe_url": "https://bhusanket.gsi.gov.in/statewiseLandslideReport.html",
        "machine_readable_api_available": False,
        "requires_registration": True,
        "resolution_steps": [
            "Public Bhusanket portal (https://bhusanket.gsi.gov.in/) provides 1,044 statewise PDF reports and NLSM 1:10k map viewer, not bulk GeoJSON/Shapefile downloads.",
            "For GIS point/polygon landslide inventories and 1:50,000 lithology/fault layers, register a free user account on GSI Bhukosh (https://bhukosh.gsi.gov.in/Bhukosh/Public) or submit a formal data request via https://www.gsi.gov.in/.",
            "Export Assam / Dima Hasao Landslide Inventory Shapefile (.zip) and place into backend/data/raw/gsi_landslides/.",
        ],
    },
    {
        "provider": "ISRO / NRSC",
        "dataset": "Landslide Atlas of India (1998–2022) & Bhuvan Disaster Services",
        "portal_url": "https://www.isro.gov.in/Landslide_Atlas_India.html",
        "secondary_url": "https://bhuvan-app1.nrsc.gov.in/disaster/disaster.php",
        "probe_url": "https://www.isro.gov.in/Landslide_Atlas_India.html",
        "machine_readable_api_available": False,
        "requires_registration": True,
        "resolution_steps": [
            "The public ISRO Landslide Atlas page distributes a summary PDF (/media_isro/pdf/LandslideAtlas_new_2023.pdf) containing district rankings and aggregate statistics, NOT machine-readable event coordinates.",
            "For georeferenced point/polygon inventories in Dima Hasao, register on ISRO Bhuvan or submit an institutional research request to NRSC Hyderabad / NESAC Shillong.",
            "Do NOT transcribe aggregate PDF charts into synthetic point coordinates.",
        ],
    },
    {
        "provider": "NASA GSFC",
        "dataset": "NASA Cooperative Open Online Landslide Repository (COOLR — Reports & Events FeatureServers)",
        "portal_url": "https://gpm.nasa.gov/applications/landslides/coolr",
        "secondary_url": "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Events_Points/FeatureServer/0",
        "probe_url": "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides/COOLR_Reports_Points/FeatureServer/0/query?where=1%3D1&geometry=92.0,24.5,94.0,26.3&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&returnCountOnly=true&f=json",
        "machine_readable_api_available": True,
        "requires_registration": False,
        "resolution_steps": [
            "Retrieved automatically via backend/ingestion/fetch_coolr_landslides.py (104 verified records in 50 km buffer; 19 inside Dima Hasao polygon; 0 in COOLR_Events_Points).",
            "All 19 Dima Hasao COOLR records have 1 km–50 km or 'unknown' location_accuracy (0 exact <= 100 m), so they are suitable ONLY for contextual visualization, NOT 30 m/90 m slope-scale ML training.",
        ],
    },
]


def probe_landslide_inventories(output_dir: Path = PILOT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    coolr_count = 0

    with httpx.Client(
        timeout=15.0,
        follow_redirects=True,
        headers={"User-Agent": "GeoResilience-NER-Research/2.0"},
    ) as client:
        for item in CANDIDATE_ENDPOINTS:
            probe_status: dict[str, Any] = {
                "provider": item["provider"],
                "dataset": item["dataset"],
                "portal_url": item["portal_url"],
                "secondary_url": item["secondary_url"],
                "probe_url": item["probe_url"],
                "requires_registration": item["requires_registration"],
                "machine_readable_api_available": item["machine_readable_api_available"],
                "resolution_steps": item["resolution_steps"],
            }
            try:
                resp = client.get(item["probe_url"])
                probe_status["http_status"] = resp.status_code
                probe_status["reachable_from_environment"] = 200 <= resp.status_code < 400
                probe_status["content_type"] = resp.headers.get("content-type", "")
                if "COOLR_Reports_Points" in item["probe_url"] and resp.status_code == 200:
                    data = resp.json()
                    coolr_count = int(data.get("count", 0))
                    probe_status["pilot_records_retrieved"] = coolr_count
                else:
                    probe_status["pilot_records_retrieved"] = 0
                probe_status["blocker_note"] = (
                    "Public portal reachable, but machine-readable GIS inventory requires account registration or formal institutional data request."
                    if item["requires_registration"]
                    else "Public ArcGIS FeatureServer reachable; retrieved records are coarse (1 km–50 km) media reports unsuitable for 30 m ML training."
                )
            except Exception as exc:
                probe_status["http_status"] = None
                probe_status["reachable_from_environment"] = False
                probe_status["pilot_records_retrieved"] = 0
                probe_status["error"] = f"{type(exc).__name__}: {exc}"
                probe_status["blocker_note"] = (
                    f"Endpoint unreachable or timed out from this runtime environment ({type(exc).__name__}). "
                    "Follow resolution_steps to obtain official data."
                )
            results.append(probe_status)

    # Check if Stage 3 curated COOLR file exists to report exact polygon count
    coolr_curated_path = output_dir / "dima_hasao_landslides_coolr.json"
    pilot_polygon_count = 0
    slope_usable_count = 0
    if coolr_curated_path.exists():
        c_doc = json.loads(coolr_curated_path.read_text(encoding="utf-8"))
        pilot_polygon_count = int(c_doc.get("summary", {}).get("within_dima_hasao_polygon", 0))
        slope_usable_count = int(
            c_doc.get("summary", {}).get("usable_for_30m_90m_slope_training_pilot", 0)
        )

    processed_at = datetime.now(timezone.utc).isoformat()
    report = {
        "study_area": "Dima Hasao District, Assam (Pilot)",
        "discovery_timestamp": processed_at,
        "fabricated_labels_count": 0,
        "verified_pilot_landslide_records_count": slope_usable_count,
        "verified_contextual_pilot_records_count": pilot_polygon_count,
        "verified_buffer_50km_records_count": coolr_count,
        "verified_pilot_landslide_records": [],
        "providers": results,
        "scientific_note": (
            f"NASA COOLR returned {coolr_count} verified records in the 50 km buffer ({pilot_polygon_count} inside Dima Hasao polygon), "
            f"of which {slope_usable_count} meet <= 100 m positional accuracy required for 30 m/90 m slope-scale ML training. "
            "No synthetic or hardcoded landslide labels are generated. Field-validated GSI Bhukosh / ISRO NRSC polygons remain required."
        ),
    }

    out_path = output_dir / "landslide_inventory_discovery.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    rep = probe_landslide_inventories()
    print(json.dumps({k: v for k, v in rep.items() if k != "verified_pilot_landslide_records"}, indent=2))
