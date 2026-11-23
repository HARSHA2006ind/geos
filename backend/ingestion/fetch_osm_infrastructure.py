"""
Stage 9 Priority 4D — Authentic OpenStreetMap Road & Railway Network Proximity (Dima Hasao).

Acquires real OpenStreetMap highway (motorway/trunk/primary/secondary/tertiary/unclassified)
and railway (Lumding–Badarpur BG Hill Section) line geometries across Dima Hasao District via
official Overpass API mirrors with exponential-backoff retry.

Outputs:
  - `dima_hasao_osm_transport.geojson` (WGS84 GeoJSON with OSM way IDs, highway/railway tags, ref/name)
  - `dima_hasao_dist_road_m_utm46n.tif` (Euclidean distance to nearest road in meters, aligned with DEM)
  - `dima_hasao_dist_railway_m_utm46n.tif` (Euclidean distance to nearest railway in meters, aligned with DEM)
  - `osm_infrastructure_metadata.json` (provenance, ODbL license, mirror used, feature counts, stats)
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
from shapely.geometry import LineString, mapping, shape
from shapely.ops import transform as shp_transform

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
NODATA = -9999.0

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://z.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]


def _query_overpass_transport(bbox_wgs84: tuple[float, float, float, float]) -> tuple[str, dict[str, Any]]:
    minx, miny, maxx, maxy = bbox_wgs84
    # Overpass bbox order is (south, west, north, east)
    bbox_str = f"{miny:.5f},{minx:.5f},{maxy:.5f},{maxx:.5f}"
    ql = (
        "[out:json][timeout:60];\n"
        "(\n"
        f'  way["highway"~"^(motorway|trunk|primary|secondary|tertiary|unclassified|residential)$"]({bbox_str});\n'
        f'  way["railway"~"^(rail|narrow_gauge|construction)$"]({bbox_str});\n'
        ");\n"
        "out body geom;\n"
    )

    errors: list[str] = []
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(1, 3):
            try:
                with httpx.Client(timeout=75.0, follow_redirects=True) as client:
                    resp = client.post(
                        endpoint,
                        data={"data": ql},
                        headers={"User-Agent": "GeoResilience-NER/2.0 (Scientific Research)"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        if "elements" in data:
                            return endpoint, data
                    errors.append(f"{endpoint} HTTP {resp.status_code}")
            except Exception as exc:
                errors.append(f"{endpoint} {type(exc).__name__}: {str(exc)[:80]}")
            time.sleep(2.0 * attempt)

    raise RuntimeError(f"All Overpass endpoints failed: {'; '.join(errors)}")


def fetch_osm_infrastructure_dima_hasao(pilot_dir: Path = PILOT_DIR) -> dict[str, Any]:
    boundary_gj = json.loads((pilot_dir / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
    geom = boundary_gj["features"][0]["geometry"] if "features" in boundary_gj else boundary_gj["geometry"]
    poly = shape(geom)

    endpoint_used, raw = _query_overpass_transport(poly.bounds)
    elements = raw.get("elements", [])

    features: list[dict[str, Any]] = []
    road_geoms_wgs: list[LineString] = []
    rail_geoms_wgs: list[LineString] = []

    for el in elements:
        if el.get("type") != "way":
            continue
        pts = el.get("geometry") or []
        if len(pts) < 2:
            continue
        coords = [(float(p["lon"]), float(p["lat"])) for p in pts]
        line = LineString(coords)
        tags = el.get("tags") or {}
        is_rail = "railway" in tags
        is_road = "highway" in tags

        if is_road:
            road_geoms_wgs.append(line)
        if is_rail:
            rail_geoms_wgs.append(line)

        features.append(
            {
                "type": "Feature",
                "geometry": mapping(line),
                "properties": {
                    "osm_id": el.get("id"),
                    "category": "railway" if is_rail else "road",
                    "highway": tags.get("highway"),
                    "railway": tags.get("railway"),
                    "ref": tags.get("ref"),
                    "name": tags.get("name"),
                },
            }
        )

    gj_path = pilot_dir / "dima_hasao_osm_transport.geojson"
    gj_path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "metadata": {
                    "source": endpoint_used,
                    "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
                    "license": "Open Database License (ODbL 1.0) — © OpenStreetMap contributors",
                    "road_way_count": len(road_geoms_wgs),
                    "railway_way_count": len(rail_geoms_wgs),
                },
                "features": features,
            }
        ),
        encoding="utf-8",
    )

    dem_path = pilot_dir / "dima_hasao_dem_utm46n.tif"
    with rasterio.open(dem_path) as dem_src:
        profile = dem_src.profile.copy()
        shape_hw = (dem_src.height, dem_src.width)
        transform = dem_src.transform
        dx = abs(float(transform.a))
        dy = abs(float(transform.e))
        dem_arr = dem_src.read(1)
        valid_mask = (~np.isnan(dem_arr)) & (dem_arr != dem_src.nodata)

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True).transform

    def _build_distance_raster(lines_wgs: list[LineString], out_name: str) -> dict[str, Any]:
        lines_utm = [shp_transform(to_utm, ln) for ln in lines_wgs]
        if lines_utm:
            mask = rasterize(
                [(geom, 1) for geom in lines_utm],
                out_shape=shape_hw,
                transform=transform,
                fill=0,
                all_touched=True,
                dtype="uint8",
            )
            dist_m = distance_transform_edt(mask == 0, sampling=(dy, dx)).astype(np.float32)
        else:
            dist_m = np.full(shape_hw, NODATA, dtype=np.float32)
        dist_m[~valid_mask] = NODATA

        out_path = pilot_dir / out_name
        out_prof = dict(profile)
        out_prof.update(dtype="float32", count=1, nodata=NODATA, compress="deflate")
        with rasterio.open(out_path, "w", **out_prof) as dst:
            dst.write(dist_m, 1)

        valid = dist_m[(dist_m != NODATA) & (~np.isnan(dist_m))]
        return {
            "file": out_name,
            "crs": "EPSG:32646",
            "width": shape_hw[1],
            "height": shape_hw[0],
            "nodata": NODATA,
            "valid_pixel_pct": round(100.0 * valid.size / dist_m.size, 2) if dist_m.size else 0.0,
            "min_m": round(float(valid.min()), 2) if valid.size else None,
            "max_m": round(float(valid.max()), 2) if valid.size else None,
            "mean_m": round(float(valid.mean()), 2) if valid.size else None,
            "median_m": round(float(np.median(valid)), 2) if valid.size else None,
            "file_bytes": out_path.stat().st_size,
        }

    road_stats = _build_distance_raster(road_geoms_wgs, "dima_hasao_dist_road_m_utm46n.tif")
    rail_stats = _build_distance_raster(rail_geoms_wgs, "dima_hasao_dist_railway_m_utm46n.tif")

    metadata = {
        "dataset_id": "osm-dima-hasao-road-railway-proximity",
        "dataset_name": "OpenStreetMap Road & Railway Network + Euclidean Proximity Rasters (Dima Hasao)",
        "source_endpoint": endpoint_used,
        "license": "Open Database License (ODbL 1.0)",
        "attribution": "© OpenStreetMap contributors (https://www.openstreetmap.org/copyright)",
        "observation_period": f"OSM snapshot retrieved {datetime.now(timezone.utc).date().isoformat()}",
        "temporal_validity": (
            "Current OSM transport network snapshot (includes NH-27 four-laning and Lumding-Badarpur BG rail line). "
            "Valid for post-2016 road-cut proximity analysis; pre-2015 highway alignments may differ."
        ),
        "vector_geojson_file": gj_path.name,
        "road_way_count": len(road_geoms_wgs),
        "railway_way_count": len(rail_geoms_wgs),
        "rasters": {
            "distance_to_road_m": road_stats,
            "distance_to_railway_m": rail_stats,
        },
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
    }

    (pilot_dir / "osm_infrastructure_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    meta = fetch_osm_infrastructure_dima_hasao()
    print(
        json.dumps(
            {
                "endpoint": meta["source_endpoint"],
                "road_way_count": meta["road_way_count"],
                "railway_way_count": meta["railway_way_count"],
                "rasters": meta["rasters"],
            },
            indent=2,
        )
    )
