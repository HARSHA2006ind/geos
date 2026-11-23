"""
Dataset C — ESA WorldCover 10 m v200 (2021) Real Land-Cover Acquisition Pipeline.

Reads official public Cloud-Optimized GeoTIFFs hosted on AWS Open Data
(https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/) via HTTP Range
requests (/vsicurl/), clips tightly to the Dima Hasao pilot bounding box, and writes a
compact DEFLATE-compressed GeoTIFF (uint8) + exact class area distribution and
temporal limitation metadata.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.warp import Resampling, calculate_default_transform, reproject

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
WORLDCOVER_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
WGS84_CRS = "EPSG:4326"
UTM_CRS = "EPSG:32646"

WORLDCOVER_CLASSES: dict[int, str] = {
    10: "Tree cover",
    20: "Shrubland",
    30: "Grassland",
    40: "Cropland",
    50: "Built-up",
    60: "Bare / sparse vegetation",
    70: "Snow and ice",
    80: "Permanent water bodies",
    90: "Herbaceous wetland",
    95: "Mangroves",
    100: "Moss and lichen",
}


def _wc_tile_origin(coord: float) -> int:
    # WorldCover tiles are 3° x 3° aligned to multiples of 3 degrees
    return int(math.floor(coord / 3.0) * 3)


def _wc_tile_url(lat3: int, lon3: int) -> str:
    ns = "N" if lat3 >= 0 else "S"
    ew = "E" if lon3 >= 0 else "W"
    return f"{WORLDCOVER_BASE}/ESA_WorldCover_10m_2021_v200_{ns}{abs(lat3):02d}{ew}{abs(lon3):03d}_Map.tif"


def _required_wc_tiles(bbox: list[float]) -> list[str]:
    minx, miny, maxx, maxy = bbox
    lat_start = _wc_tile_origin(miny)
    lat_end = _wc_tile_origin(maxy)
    lon_start = _wc_tile_origin(minx)
    lon_end = _wc_tile_origin(maxx)
    urls: list[str] = []
    for lat in range(lat_start, lat_end + 1, 3):
        for lon in range(lon_start, lon_end + 1, 3):
            urls.append(_wc_tile_url(lat, lon))
    return urls


def ingest_worldcover(
    boundary_path: Path = PILOT_DIR / "dima_hasao_boundary.geojson",
    output_dir: Path = PILOT_DIR,
    target_resolution_m: float = 30.0,
) -> dict[str, Any]:
    """
    Clips ESA WorldCover 10 m v200 (2021) over Dima Hasao using HTTP range requests and
    exports a compact 30 m modal-resampled UTM GeoTIFF for district-wide fast serving
    (aligned with 30 m Copernicus DEM scale and 20 GB SSD limits) while also verifying
    native 10 m pixel availability.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    bbox = boundary["metadata"]["bbox_wgs84"]
    buf = 0.02
    clip_bounds = [bbox[0] - buf, bbox[1] - buf, bbox[2] + buf, bbox[3] + buf]
    tile_urls = _required_wc_tiles(clip_bounds)

    env_opts = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_TIMEOUT": "30",
        "GDAL_HTTP_MAX_RETRY": "3",
    }

    opened = []
    source_tiles_used: list[dict[str, Any]] = []
    try:
        with rasterio.Env(**env_opts):
            for url in tile_urls:
                ds = rasterio.open(f"/vsicurl/{url}")
                opened.append(ds)
                source_tiles_used.append(
                    {
                        "url": url,
                        "native_crs": str(ds.crs),
                        "native_res_deg": [round(float(ds.res[0]), 9), round(float(ds.res[1]), 9)],
                        "width": ds.width,
                        "height": ds.height,
                        "dtype": ds.dtypes[0],
                    }
                )

            # Read clipped window at ~30 m resolution directly using GDAL overviews / nearest
            # to avoid transferring >50 MB of raw 10 m pixels on tight bandwidth/disk budgets
            res_deg = target_resolution_m / 111_320.0
            mosaic, mosaic_transform = merge(
                opened,
                bounds=tuple(clip_bounds),
                res=(res_deg, res_deg),
                resampling=Resampling.mode,
                nodata=0,
            )
            src_crs = opened[0].crs
    finally:
        for ds in opened:
            ds.close()

    lc_wgs84 = mosaic[0].astype(np.uint8)
    h, w = lc_wgs84.shape
    left, bottom, right, top = rasterio.transform.array_bounds(h, w, mosaic_transform)
    utm_transform, utm_w, utm_h = calculate_default_transform(
        src_crs, UTM_CRS, w, h, left, bottom, right, top, resolution=target_resolution_m
    )

    lc_utm = np.zeros((utm_h, utm_w), dtype=np.uint8)
    reproject(
        source=lc_wgs84,
        destination=lc_utm,
        src_transform=mosaic_transform,
        src_crs=src_crs,
        src_nodata=0,
        dst_transform=utm_transform,
        dst_crs=UTM_CRS,
        dst_nodata=0,
        resampling=Resampling.nearest,
    )

    out_tif = output_dir / "dima_hasao_worldcover_2021_utm46n.tif"
    with rasterio.open(
        out_tif,
        "w",
        driver="GTiff",
        height=utm_h,
        width=utm_w,
        count=1,
        dtype="uint8",
        crs=UTM_CRS,
        transform=utm_transform,
        nodata=0,
        compress="deflate",
        tiled=True,
    ) as dst:
        dst.write(lc_utm, 1)

    # Compute real land-cover class distribution
    vals, counts = np.unique(lc_utm[lc_utm > 0], return_counts=True)
    total_valid = int(np.sum(counts))
    pixel_area_km2 = (target_resolution_m * target_resolution_m) / 1_000_000.0
    class_breakdown = []
    for code, cnt in sorted(zip(vals.tolist(), counts.tolist()), key=lambda x: -x[1]):
        class_breakdown.append(
            {
                "code": int(code),
                "label": WORLDCOVER_CLASSES.get(int(code), f"Unknown ({code})"),
                "pixel_count": int(cnt),
                "area_km2": round(cnt * pixel_area_km2, 2),
                "percentage": round((cnt / total_valid) * 100.0, 2) if total_valid > 0 else 0.0,
            }
        )

    processed_at = datetime.now(timezone.utc).isoformat()
    metadata = {
        "dataset_id": "esa-worldcover-2021-v200",
        "dataset_name": "ESA WorldCover 10 m 2021 v200 (Sentinel-1 & Sentinel-2 Derived)",
        "product_version": "v200 (2021 epoch)",
        "source_tiles": source_tiles_used,
        "native_resolution_m": 10.0,
        "exported_resolution_m": target_resolution_m,
        "resampling_method": "mode (overview/grid aggregation to 30m) + nearest to EPSG:32646",
        "exported_crs": UTM_CRS,
        "raster_file": out_tif.name,
        "file_size_kb": round(out_tif.stat().st_size / 1024, 1),
        "clip_bounds_wgs84": [round(v, 6) for v in clip_bounds],
        "observation_period": "2021-01-01 to 2021-12-31 (annual composite)",
        "class_distribution": class_breakdown,
        "processing_timestamp": processed_at,
        "attribution": "© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium (CC BY 4.0).",
        "uncertainty_and_limitations": (
            "Static 2021 annual map (global overall accuracy ~76.7% in v200 validation report). "
            "Does NOT capture post-2021 deforestation, jhum shifting cultivation cycles, highway cut-slopes, "
            "or seasonal canopy stress; persistent monsoon cloud cover in NER increases optical classification uncertainty."
        ),
    }

    meta_path = output_dir / "worldcover_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    result = ingest_worldcover()
    print(json.dumps(result, indent=2))
