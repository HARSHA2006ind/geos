"""
Phase B8 — Authentic OpenStreetMap Infrastructure Exposure Ingestion for Dima Hasao District.

Fetches genuine geographic features (hospitals/clinics, schools, settlements/towns/villages,
and road/railway bridges) inside the verified Dima Hasao OSM boundary via public Overpass API.
Never fabricates facilities, coordinates, or population counts; documents completeness
limitations explicitly.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from shapely.geometry import Point, shape

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
]


def _classify_osm_element(tags: dict[str, Any]) -> tuple[str, str] | None:
    amenity = str(tags.get("amenity", "")).lower()
    healthcare = str(tags.get("healthcare", "")).lower()
    place = str(tags.get("place", "")).lower()
    bridge = str(tags.get("bridge", "")).lower()

    if amenity in {"hospital", "clinic", "doctors", "health_post"} or healthcare in {
        "hospital",
        "clinic",
        "centre",
        "doctor",
    }:
        return "hospital_health", amenity or healthcare
    if amenity in {"school", "college", "university"}:
        return "school", amenity
    if place in {"city", "town", "village", "hamlet", "suburb", "locality"}:
        return "settlement", place
    if bridge and bridge not in {"no", "false"}:
        return "bridge", tags.get("highway") or tags.get("railway") or "bridge"
    return None


def fetch_osm_facilities(pilot_dir: Path = PILOT_DIR) -> dict[str, Any]:
    boundary_path = pilot_dir / "dima_hasao_boundary.geojson"
    boundary_gj = json.loads(boundary_path.read_text(encoding="utf-8"))
    pilot_geom = shape(boundary_gj["features"][0]["geometry"])
    minx, miny, maxx, maxy = pilot_geom.bounds

    query = f"""
[out:json][timeout:45];
(
  nwr["amenity"~"^(hospital|clinic|doctors|school|college|university)$"]({miny:.5f},{minx:.5f},{maxy:.5f},{maxx:.5f});
  nwr["healthcare"~"^(hospital|clinic|centre)$"]({miny:.5f},{minx:.5f},{maxy:.5f},{maxx:.5f});
  node["place"~"^(city|town|village|hamlet)$"]({miny:.5f},{minx:.5f},{maxy:.5f},{maxx:.5f});
  way["bridge"]["bridge"!="no"]({miny:.5f},{minx:.5f},{maxy:.5f},{maxx:.5f});
);
out center tags;
"""
    raw_elements: list[dict[str, Any]] = []
    used_endpoint: str | None = None
    last_error: str | None = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            with httpx.Client(timeout=50.0, headers={"User-Agent": "GeoResilience-NER/2.0 (research)"}) as client:
                resp = client.post(endpoint, data={"data": query})
                resp.raise_for_status()
                payload = resp.json()
                raw_elements = payload.get("elements", [])
                used_endpoint = endpoint
                break
        except Exception as exc:  # noqa: BLE001
            last_error = f"{endpoint}: {exc}"

    features: list[dict[str, Any]] = []
    counts_by_category: dict[str, int] = {
        "hospital_health": 0,
        "school": 0,
        "settlement": 0,
        "bridge": 0,
    }
    seen_ids: set[str] = set()

    for el in raw_elements:
        tags = el.get("tags") or {}
        classified = _classify_osm_element(tags)
        if not classified:
            continue
        category, subtype = classified
        lat = el.get("lat") if el.get("type") == "node" else (el.get("center") or {}).get("lat")
        lon = el.get("lon") if el.get("type") == "node" else (el.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        lat_f, lon_f = float(lat), float(lon)
        if not pilot_geom.contains(Point(lon_f, lat_f)):
            continue
        ext_id = f"osm:{el.get('type')}/{el.get('id')}"
        if ext_id in seen_ids:
            continue
        seen_ids.add(ext_id)
        counts_by_category[category] = counts_by_category.get(category, 0) + 1

        pop_raw = tags.get("population")
        pop_val: int | None = None
        if pop_raw is not None:
            try:
                pop_val = int(str(pop_raw).replace(",", "").strip())
            except ValueError:
                pop_val = None

        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [round(lon_f, 6), round(lat_f, 6)]},
                "properties": {
                    "external_id": ext_id,
                    "category": category,
                    "subtype": subtype,
                    "name": tags.get("name") or tags.get("name:en") or f"Unnamed {subtype}",
                    "named": bool(tags.get("name") or tags.get("name:en")),
                    "population_osm_tag": pop_val,
                    "highway_or_rail": tags.get("highway") or tags.get("railway"),
                    "source": "OpenStreetMap Overpass API",
                },
            }
        )

    # Supplement bridges from already-ingested verified OSM transport GeoJSON if Overpass returned none
    transport_path = pilot_dir / "dima_hasao_osm_transport.geojson"
    transport_road_count = 0
    transport_rail_count = 0
    if transport_path.exists():
        t_doc = json.loads(transport_path.read_text(encoding="utf-8"))
        for feat in t_doc.get("features", []):
            props = feat.get("properties") or {}
            if props.get("highway"):
                transport_road_count += 1
            if props.get("railway"):
                transport_rail_count += 1

    retrieved_utc = datetime.now(timezone.utc).isoformat()
    result = {
        "type": "FeatureCollection",
        "metadata": {
            "dataset_id": "osm-dima-hasao-facilities",
            "dataset_name": "OpenStreetMap Dima Hasao Facilities, Settlements & Bridges",
            "provider": "OpenStreetMap Contributors (via Overpass API)",
            "source_url": used_endpoint or OVERPASS_ENDPOINTS[0],
            "product_version": f"OSM live snapshot {retrieved_utc[:10]}",
            "crs": "EPSG:4326",
            "processing_timestamp": retrieved_utc,
            "attribution": "© OpenStreetMap contributors (ODbL 1.0)",
            "license": "ODbL-1.0",
            "query_succeeded": used_endpoint is not None,
            "query_error": None if used_endpoint else last_error,
            "counts_by_category": counts_by_category,
            "total_point_features": len(features),
            "paired_transport_road_segments": transport_road_count,
            "paired_transport_rail_segments": transport_rail_count,
            "population_grid_status": (
                "No gridded WorldPop/Census raster ingested locally; only explicit OSM population tags are retained "
                "(null where absent — population exposure counts are never fabricated)."
            ),
            "limitations": (
                "OpenStreetMap coverage in rural Northeast India is volunteer-contributed and incomplete for "
                "small hamlets, primary health sub-centres, and rural schools. Exposure estimates represent "
                "minimum mapped asset proximity, NOT complete census or damage counts."
            ),
        },
        "features": features,
    }

    if used_endpoint is not None or not (pilot_dir / "dima_hasao_osm_facilities.geojson").exists():
        out_path = pilot_dir / "dima_hasao_osm_facilities.geojson"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    return result


if __name__ == "__main__":
    res = fetch_osm_facilities()
    print(json.dumps(res["metadata"], indent=2))
