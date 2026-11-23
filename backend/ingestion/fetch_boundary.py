"""
Fetch and validate the official administrative boundary for Dima Hasao district, Assam
from OpenStreetMap Nominatim (EPSG:4326) and save a compact GeoJSON + metadata artifact.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import httpx
from shapely.geometry import shape

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
UTM_ZONE_46N = "EPSG:32646"  # Metric CRS appropriate for Assam / Dima Hasao (90°E–96°E)


def fetch_dima_hasao_boundary(output_dir: Path = PILOT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    headers = {
        "User-Agent": "GeoResilience-NER-v2-Research/2.0 (geospatial-pilot-ingestion)",
        "Accept": "application/geo+json, application/json",
    }
    params = {
        "q": "Dima Hasao, Assam, India",
        "format": "geojson",
        "polygon_geojson": 1,
        "addressdetails": 1,
        "limit": 5,
    }

    with httpx.Client(timeout=30.0, headers=headers) as client:
        resp = client.get(NOMINATIM_URL, params=params)
        resp.raise_for_status()
        payload = resp.json()

    features = payload.get("features", [])
    selected = None
    for feat in features:
        geom = feat.get("geometry", {})
        if geom.get("type") in ("Polygon", "MultiPolygon"):
            selected = feat
            break

    if selected is None:
        raise RuntimeError(
            "Nominatim did not return a Polygon/MultiPolygon boundary for Dima Hasao, Assam."
        )

    geom = shape(selected["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)

    gdf_wgs84 = gpd.GeoDataFrame(
        [
            {
                "name": "Dima Hasao",
                "state": "Assam",
                "country": "India",
                "osm_type": selected.get("properties", {}).get("osm_type"),
                "osm_id": selected.get("properties", {}).get("osm_id"),
                "display_name": selected.get("properties", {}).get("display_name"),
            }
        ],
        geometry=[geom],
        crs="EPSG:4326",
    )
    gdf_utm = gdf_wgs84.to_crs(UTM_ZONE_46N)
    area_km2 = float(gdf_utm.geometry.area.iloc[0] / 1_000_000.0)
    minx, miny, maxx, maxy = [round(float(v), 6) for v in gdf_wgs84.total_bounds]
    centroid = gdf_wgs84.geometry.centroid.iloc[0]

    processed_at = datetime.now(timezone.utc).isoformat()
    boundary_geojson = {
        "type": "FeatureCollection",
        "name": "dima_hasao_district_boundary",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
        "metadata": {
            "dataset_name": "OpenStreetMap Administrative Boundary (Dima Hasao District, Assam)",
            "source_url": str(resp.url),
            "crs": "EPSG:4326",
            "metric_crs_for_area": UTM_ZONE_46N,
            "area_km2": round(area_km2, 2),
            "bbox_wgs84": [minx, miny, maxx, maxy],
            "centroid_wgs84": {"lat": round(float(centroid.y), 6), "lon": round(float(centroid.x), 6)},
            "osm_type": selected.get("properties", {}).get("osm_type"),
            "osm_id": selected.get("properties", {}).get("osm_id"),
            "geometry_valid": bool(geom.is_valid),
            "processing_timestamp": processed_at,
            "attribution": "© OpenStreetMap contributors (ODbL 1.0) via Nominatim",
            "limitations": "Administrative boundary from OSM; official Survey of India (SoI) district boundaries may differ slightly along state borders.",
        },
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "name": "Dima Hasao",
                    "state": "Assam",
                    "country": "India",
                    "area_km2": round(area_km2, 2),
                    "osm_id": selected.get("properties", {}).get("osm_id"),
                },
                "geometry": json.loads(gpd.GeoSeries([geom]).to_json())["features"][0]["geometry"],
            }
        ],
    }

    out_path = output_dir / "dima_hasao_boundary.geojson"
    out_path.write_text(json.dumps(boundary_geojson, indent=2), encoding="utf-8")
    return boundary_geojson["metadata"]


if __name__ == "__main__":
    meta = fetch_dima_hasao_boundary()
    print(json.dumps(meta, indent=2))
