"""
Stage 9 Priority 2 — Official GSI Bhusanket Public Landslide Inventory Ingestion (Dima Hasao, Assam).

Ingests authentic, authorized public landslide inventory records published by the
Geological Survey of India (GSI) National Landslide Forecasting Centre (NLFC) on the
official public Bhusanket Portal (`https://bhusanket.gsi.gov.in/`):
  - Public Inventory Table API:
      `GET https://bhusanket.gsi.gov.in/ArcGis_Api_Integration/LandslideControllerA/GetData`
      filtered for `state=Assam` and `district in ("Dima Hasao", "Dima Hasao (N.C. Hills)")`.
  - Public GSI State-Wise Report Index:
      `GET https://bhusanket.gsi.gov.in/json/LandslideReport/LandslideReport.json`
  - Public 1:10,000 Meso-Scale NLSM Susceptibility Map Index (strictly segregated as
    susceptibility map references — NEVER conflated with observed landslide event labels):
      `GET https://bhusanket.gsi.gov.in/json/NLSM_10K_Map.json`

Scientific Integrity & Audit Rules:
  1. Preserves raw GSI fields unmodified in `backend/data/pilot/gsi_bhusanket_dima_hasao_raw.json`.
  2. Parses event dates strictly from `History` / `Date` without fabricating day/month values
     when only a year or qualitative text (e.g., "Old", "Pre-monsoon", "NULL") is present.
  3. Explicitly tracks coordinate validity, exact Dima Hasao polygon containment, `Source`
     provenance (`PDLS`, `NLSM`, `Mobile app`, etc.), geometry type (point centroid + reported
     dimensions; polygons on `GSI/Landslide_Polygon/FeatureServer` remain token-gated HTTP 499),
     and road/railway sampling bias (`Landuse_Or_Landcover`, `NH_SH_Location`).
  4. Never bypasses token-gated ArcGIS FeatureServers (HTTP 499).
"""
from __future__ import annotations

import json
import math
import re
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point, shape

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
BHUSANKET_BASE = "https://bhusanket.gsi.gov.in"
INVENTORY_API = f"{BHUSANKET_BASE}/ArcGis_Api_Integration/LandslideControllerA/GetData"
REPORTS_JSON_URL = f"{BHUSANKET_BASE}/json/LandslideReport/LandslideReport.json"
NLSM_10K_URL = f"{BHUSANKET_BASE}/json/NLSM_10K_Map.json"

TARGET_DISTRICTS = ["Dima Hasao", "Dima Hasao (N.C. Hills)"]

MONTH_MAP = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r * math.asin(min(1.0, math.sqrt(a)))


def parse_gsi_event_date(history_raw: Any, date_raw: Any) -> tuple[str | None, str]:
    """
    Strictly parse event date from GSI `History` or `Date` text without inventing missing components.
    Returns (iso_date_or_partial, precision) where precision in {'day', 'month', 'year', 'unknown'}.
    """
    for raw in (date_raw, history_raw):
        if raw is None:
            continue
        txt = str(raw).strip()
        if not txt or txt.upper() in ("NULL", "NIL", "NA", "N/A", "NONE", "-"):
            continue

        # Pattern 1: YYYY-MM-DD or YYYY/MM/DD
        m = re.search(r"\b((?:19|20)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})\b", txt)
        if m:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}", "day"

        # Pattern 2: DD-MM-YYYY or DD/MM/YYYY or DD.MM.YYYY
        m = re.search(r"\b(\d{1,2})[-/.](\d{1,2})[-/.]((?:19|20)\d{2})\b", txt)
        if m:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}", "day"

        # Pattern 3: 31st May 2025 / 03 June 2017 / 14 May, 2022
        m = re.search(
            r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3,9})[.,]?\s+((?:19|20)\d{2})\b",
            txt,
            re.IGNORECASE,
        )
        if m:
            d = int(m.group(1))
            mo = MONTH_MAP.get(m.group(2).lower())
            y = int(m.group(3))
            if mo and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}", "day"

        # Pattern 4: May 14, 2022
        m = re.search(
            r"\b([A-Za-z]{3,9})\s+(\d{1,2})(?:st|nd|rd|th)?[,\s]+((?:19|20)\d{2})\b",
            txt,
            re.IGNORECASE,
        )
        if m:
            mo = MONTH_MAP.get(m.group(1).lower())
            d = int(m.group(2))
            y = int(m.group(3))
            if mo and 1 <= d <= 31:
                return f"{y:04d}-{mo:02d}-{d:02d}", "day"

        # Pattern 5: Month Year (e.g., May 2022, June 2017)
        m = re.search(r"\b([A-Za-z]{3,9})[.,]?\s+((?:19|20)\d{2})\b", txt, re.IGNORECASE)
        if m:
            mo = MONTH_MAP.get(m.group(1).lower())
            y = int(m.group(2))
            if mo:
                return f"{y:04d}-{mo:02d}", "month"

        # Pattern 6: Standalone 4-digit year (e.g., 2015, 2022)
        m = re.search(r"\b((?:19|20)\d{2})\b", txt)
        if m:
            return m.group(1), "year"

    return None, "unknown"


def _clean_str(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.upper() in ("NULL", "NIL", "NONE", "N/A", "NA"):
        return None
    return s


def _clean_float(val: Any) -> float | None:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _count_decimal_places(val: Any) -> int:
    if val is None:
        return 0
    s = str(val).strip()
    if "." not in s:
        return 0
    return len(s.split(".", 1)[1].rstrip("0"))


def fetch_gsi_bhusanket_dima_hasao(pilot_dir: Path = PILOT_DIR) -> dict[str, Any]:
    boundary_gj = json.loads((pilot_dir / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
    geom = boundary_gj["features"][0]["geometry"] if "features" in boundary_gj else boundary_gj["geometry"]
    pilot_poly = shape(geom)

    raw_records: list[dict[str, Any]] = []
    district_totals: dict[str, int] = {}

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        for dist in TARGET_DISTRICTS:
            page = 1
            page_size = 100
            while True:
                resp = client.get(
                    INVENTORY_API,
                    params={
                        "pageNumber": page,
                        "pageSize": page_size,
                        "state": "Assam",
                        "district": dist,
                    },
                    headers={"User-Agent": "GeoResilience-NER/2.0 (Scientific Research)"},
                )
                resp.raise_for_status()
                payload = resp.json()
                if page == 1:
                    district_totals[dist] = int(payload.get("totalRecords") or 0)
                rows = payload.get("data") or []
                if not rows:
                    break
                for row in rows:
                    row_copy = dict(row)
                    row_copy["_queried_district"] = dist
                    raw_records.append(row_copy)
                total_pages = int(payload.get("totalPages") or 1)
                if page >= total_pages:
                    break
                page += 1
                time.sleep(0.25)

        # Fetch public GSI state-wise landslide report index & filter for Dima Hasao / NC Hills
        dima_hasao_reports: list[dict[str, Any]] = []
        try:
            r_rep = client.get(REPORTS_JSON_URL)
            if r_rep.status_code == 200:
                txt = r_rep.text.strip()
                if "=" in txt[:40]:
                    txt = txt.split("=", 1)[1].strip().rstrip(";")
                all_reps = json.loads(txt)
                for rep in all_reps:
                    blob = json.dumps(rep).lower()
                    if "dima hasao" in blob or "north cachar" in blob or "n.c. hills" in blob or "haflong" in blob:
                        dima_hasao_reports.append(rep)
        except Exception:
            pass

        # Fetch public 1:10,000 Meso-scale NLSM Susceptibility Map index (strictly separate from inventory!)
        dima_hasao_nlsm_10k_maps: list[dict[str, Any]] = []
        try:
            r_nlsm = client.get(NLSM_10K_URL)
            if r_nlsm.status_code == 200:
                for entry in r_nlsm.json():
                    blob = json.dumps(entry).lower()
                    if "dima hasao" in blob or "north cachar" in blob or "haflong" in blob:
                        dima_hasao_nlsm_10k_maps.append(entry)
        except Exception:
            pass

    # Save exact raw unmodified GSI payload
    raw_path = pilot_dir / "gsi_bhusanket_dima_hasao_raw.json"
    raw_path.write_text(
        json.dumps(
            {
                "source_url": INVENTORY_API,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                "district_query_totals": district_totals,
                "raw_record_count": len(raw_records),
                "records": raw_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Deduplicate by OBJECTID & standardize
    seen_oids: set[Any] = set()
    curated: list[dict[str, Any]] = []
    exact_oid_dups = 0
    invalid_coord_count = 0

    for row in raw_records:
        oid = row.get("OBJECTID")
        if oid is not None and oid in seen_oids:
            exact_oid_dups += 1
            continue
        if oid is not None:
            seen_oids.add(oid)

        lat = _clean_float(row.get("Latitude"))
        lon = _clean_float(row.get("Longitude"))
        valid_coord = (
            lat is not None
            and lon is not None
            and -90.0 <= lat <= 90.0
            and -180.0 <= lon <= 180.0
            and not (lat == 0.0 and lon == 0.0)
        )
        if not valid_coord:
            invalid_coord_count += 1
            within_poly = False
        else:
            within_poly = bool(pilot_poly.contains(Point(lon, lat)))

        parsed_date, date_precision = parse_gsi_event_date(row.get("History"), row.get("Date"))
        lat_dec = _count_decimal_places(row.get("Latitude"))
        lon_dec = _count_decimal_places(row.get("Longitude"))
        min_dec = min(lat_dec, lon_dec)

        # Conservative positional precision estimate from coordinate decimal precision & source type
        # Note: decimal places indicate quantization floor, NOT guaranteed GPS survey error;
        # GSI does NOT expose an explicit horizontal error radius column in GetData.
        source_tag = _clean_str(row.get("Source")) or _clean_str(row.get("CITATION")) or "Unknown"
        if not valid_coord:
            coord_precision_tier = "invalid_or_missing"
        elif min_dec >= 4:
            coord_precision_tier = "high_decimal_ge_4dp_unverified_error_radius"
        elif min_dec == 3:
            coord_precision_tier = "moderate_decimal_3dp_approx_110m"
        else:
            coord_precision_tier = "coarse_decimal_le_2dp_gt_1km"

        # Check road/rail corridor sampling bias
        loc_blob = " ".join(
            filter(
                None,
                [
                    _clean_str(row.get("NH_SH_Location")),
                    _clean_str(row.get("Landuse_Or_Landcover")),
                    _clean_str(row.get("Slide_Name")),
                    _clean_str(row.get("Communication_Affected")),
                    _clean_str(row.get("Infrastructure_Affected")),
                ],
            )
        ).lower()
        corridor_bias_flag = any(
            kw in loc_blob for kw in ("road", "nh", "sh", "highway", "rail", "track", "bridge", "tunnel", "station")
        )

        curated.append(
            {
                "object_id": oid,
                "slide_no": _clean_str(row.get("Slide_No")),
                "state": _clean_str(row.get("State")),
                "district": _clean_str(row.get("District")),
                "toposheet_no": _clean_str(row.get("Toposheet_No")),
                "slide_name": _clean_str(row.get("Slide_Name")),
                "nh_sh_location": _clean_str(row.get("NH_SH_Location")),
                "latitude": lat,
                "longitude": lon,
                "valid_coordinate": valid_coord,
                "within_pilot_boundary": within_poly,
                "coord_decimal_places_min": min_dec,
                "coord_precision_tier": coord_precision_tier,
                "explicit_error_radius_reported": False,
                "geometry_type": "point_only_polygons_token_gated",
                "event_date": parsed_date,
                "event_date_precision": date_precision,
                "history_raw": _clean_str(row.get("History")),
                "area_sq_m": _clean_float(row.get("Area_In_Sq_Meters")),
                "length_m": _clean_float(row.get("Length_in_meters")),
                "width_m": _clean_float(row.get("Width_in_meters")),
                "depth_m": _clean_float(row.get("Depth_In_meters")),
                "volume_m3": _clean_float(row.get("Volume_In_Cubic_Meters")),
                "material_involved": _clean_str(row.get("Material_Involved")),
                "movement_type": _clean_str(row.get("Movement_Type")),
                "activity": _clean_str(row.get("Activity")),
                "failure_mechanism": _clean_str(row.get("Failure_Mechanism")),
                "geology": _clean_str(row.get("Geology")),
                "geomorphology": _clean_str(row.get("Geomorphology")),
                "hydrological_condition": _clean_str(row.get("Hydrological_Condition")),
                "triggering": _clean_str(row.get("Triggering")),
                "landuse_or_landcover": _clean_str(row.get("Landuse_Or_Landcover")),
                "source_type": source_tag,
                "citation": _clean_str(row.get("CITATION")),
                "near_transport_corridor_text_flag": corridor_bias_flag,
            }
        )

    # Audit summary statistics
    in_poly = [r for r in curated if r["within_pilot_boundary"]]
    out_poly_valid = [r for r in curated if r["valid_coordinate"] and not r["within_pilot_boundary"]]
    date_prec_counts = dict(Counter(r["event_date_precision"] for r in in_poly))
    source_counts = dict(Counter(r["source_type"] for r in in_poly))
    precision_counts = dict(Counter(r["coord_precision_tier"] for r in in_poly))
    years_counts = dict(
        sorted(
            Counter(
                r["event_date"][:4] for r in in_poly if r["event_date"] and len(r["event_date"]) >= 4
            ).items()
        )
    )
    corridor_biased_count = sum(1 for r in in_poly if r["near_transport_corridor_text_flag"])
    with_day_date = [r for r in in_poly if r["event_date_precision"] == "day"]
    with_day_date_2015_2024 = [
        r for r in with_day_date if "2015-01-01" <= (r["event_date"] or "") <= "2024-12-31"
    ]
    with_day_date_2022_2025 = [
        r for r in with_day_date if (r["event_date"] or "") >= "2022-01-01"
    ]
    with_geology = sum(1 for r in in_poly if r["geology"])
    with_area = sum(1 for r in in_poly if r["area_sq_m"] is not None and r["area_sq_m"] > 0)

    # Spatial proximity duplicate audit (within 50m)
    near_dup_pairs = 0
    for i in range(len(in_poly)):
        for j in range(i + 1, len(in_poly)):
            if haversine_m(
                in_poly[i]["latitude"],
                in_poly[i]["longitude"],
                in_poly[j]["latitude"],
                in_poly[j]["longitude"],
            ) <= 50.0:
                near_dup_pairs += 1

    summary_doc = {
        "dataset_id": "gsi-bhusanket-public-inventory-dima-hasao",
        "dataset_name": "GSI Bhusanket Official Public Landslide Inventory (Dima Hasao, Assam)",
        "provider": "Geological Survey of India (GSI) — National Landslide Forecasting Centre (NLFC)",
        "source_url": INVENTORY_API,
        "portal_url": f"{BHUSANKET_BASE}/",
        "license_and_terms": (
            "Published by Geological Survey of India (Ministry of Mines, Govt. of India) on the public "
            "Bhusanket portal for public viewing and tabular export; redistribution/operational use "
            "subject to GSI/MoM data sharing terms and formal institutional acknowledgement."
        ),
        "attribution": "Geological Survey of India (GSI), Ministry of Mines, Government of India — Bhusanket Public Portal",
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "district_query_totals": district_totals,
        "audit_summary": {
            "total_raw_records": len(raw_records),
            "exact_objectid_duplicates_removed": exact_oid_dups,
            "curated_unique_records": len(curated),
            "invalid_coordinates": invalid_coord_count,
            "within_dima_hasao_polygon": len(in_poly),
            "valid_coord_outside_osm_polygon": len(out_poly_valid),
            "date_precision_in_polygon": date_prec_counts,
            "day_level_dates_in_polygon": len(with_day_date),
            "day_level_dates_2015_2024_overlap": len(with_day_date_2015_2024),
            "day_level_dates_2022_2025": len(with_day_date_2022_2025),
            "years_distribution_in_polygon": years_counts,
            "source_type_distribution_in_polygon": source_counts,
            "coord_precision_tier_in_polygon": precision_counts,
            "records_with_geology_description": with_geology,
            "records_with_reported_area_m2": with_area,
            "near_duplicate_pairs_within_50m": near_dup_pairs,
            "transport_corridor_text_bias_count": corridor_biased_count,
            "transport_corridor_text_bias_pct": round(100.0 * corridor_biased_count / len(in_poly), 1)
            if in_poly
            else 0.0,
        },
        "scientific_caveats": [
            "GSI Bhusanket public GetData returns POINT centroids and tabular dimensions only; observed landslide polygons (GSI/Landslide_Polygon/FeatureServer) and national point GIS layer (India_All_Landslided/FeatureServer/0) return ArcGIS Error 499 (Token Required).",
            "Many GSI NLSM legacy inventory records lack an exact failure date ('unknown' or 'year' only), making them usable ONLY for static spatial susceptibility analysis and NOT for dynamic rainfall-triggered temporal early-warning modeling without exact failure dates.",
            "No explicit GPS horizontal uncertainty column (meters) is exposed in the public tabular API; high decimal places reflect coordinate storage precision rather than certified survey error.",
            "Field-mapped inventories (especially PDLS and Bhooskhalan mobile reports) exhibit strong accessibility/reporting bias along NH-27/NH-54E roads and the Lumding–Badarpur railway corridor; unmapped forested interior slopes cannot be assumed landslide-free.",
            "1:10,000 Meso-scale NLSM Susceptibility Maps listed below are derived susceptibility products, strictly separate from observed landslide event records.",
        ],
        "gsi_dima_hasao_reports_count": len(dima_hasao_reports),
        "gsi_dima_hasao_reports_sample": dima_hasao_reports[:15],
        "gsi_dima_hasao_nlsm_10k_susceptibility_maps_separate_from_events": dima_hasao_nlsm_10k_maps,
        "records": curated,
    }

    out_path = pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json"
    out_path.write_text(json.dumps(summary_doc, indent=2), encoding="utf-8")
    return summary_doc


if __name__ == "__main__":
    doc = fetch_gsi_bhusanket_dima_hasao()
    print(json.dumps(doc["audit_summary"], indent=2))
    print("GSI reports for Dima Hasao:", doc["gsi_dima_hasao_reports_count"])
    print("NLSM 10K susceptibility maps for Dima Hasao:", len(doc["gsi_dima_hasao_nlsm_10k_susceptibility_maps_separate_from_events"]))
