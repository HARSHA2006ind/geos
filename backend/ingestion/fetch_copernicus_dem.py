"""
Dataset A — Copernicus DEM GLO-30 (30 m) Real Acquisition & Terrain Derivative Pipeline.

Reads official public Cloud-Optimized GeoTIFFs (COGs) hosted on AWS Open Data
(s3://copernicus-dem-30m / https://copernicus-dem-30m.s3.amazonaws.com) via HTTP Range
requests (/vsicurl/), clips tightly to the Dima Hasao pilot bounding box (+small buffer),
reprojects to UTM Zone 46N (EPSG:32646) to compute physically accurate Horn's 3x3 slope
(degrees) and aspect (degrees clockwise from north), and writes compact LZW-compressed
GeoTIFFs in EPSG:4326 + complete provenance metadata.
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
from rasterio.windows import from_bounds

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
COPERNICUS_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
UTM_CRS = "EPSG:32646"
WGS84_CRS = "EPSG:4326"
NODATA_VAL = -9999.0


def _tile_url(lat_floor: int, lon_floor: int) -> str:
    ns = "N" if lat_floor >= 0 else "S"
    ew = "E" if lon_floor >= 0 else "W"
    name = f"Copernicus_DSM_COG_10_{ns}{abs(lat_floor):02d}_00_{ew}{abs(lon_floor):03d}_00_DEM"
    return f"{COPERNICUS_BASE}/{name}/{name}.tif"


def _required_tiles(bbox: list[float]) -> list[str]:
    minx, miny, maxx, maxy = bbox
    urls: list[str] = []
    for lat in range(math.floor(miny), math.floor(maxy) + 1):
        for lon in range(math.floor(minx), math.floor(maxx) + 1):
            urls.append(_tile_url(lat, lon))
    return urls


def compute_slope_aspect_horn(
    elevation_m: np.ndarray,
    pixel_size_x: float,
    pixel_size_y: float,
    nodata_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Compute Horn's (1981) 3x3 finite-difference slope (degrees) and aspect
    (degrees clockwise from North, 0..360; -1 for flat slopes).
    Expects elevation in meters on a metric projected grid (e.g., EPSG:32646).
    """
    z = elevation_m.astype(np.float64)
    z_pad = np.pad(z, 1, mode="edge")

    z1 = z_pad[:-2, :-2]
    z2 = z_pad[:-2, 1:-1]
    z3 = z_pad[:-2, 2:]
    z4 = z_pad[1:-1, :-2]
    z6 = z_pad[1:-1, 2:]
    z7 = z_pad[2:, :-2]
    z8 = z_pad[2:, 1:-1]
    z9 = z_pad[2:, 2:]

    dz_dx = ((z3 + 2.0 * z6 + z9) - (z1 + 2.0 * z4 + z7)) / (8.0 * abs(pixel_size_x))
    dz_dy = ((z7 + 2.0 * z8 + z9) - (z1 + 2.0 * z2 + z3)) / (8.0 * abs(pixel_size_y))

    slope_rad = np.arctan(np.hypot(dz_dx, dz_dy))
    slope_deg = np.degrees(slope_rad).astype(np.float32)

    # Aspect (downhill direction clockwise from North): 0 = North, 90 = East, 180 = South, 270 = West
    # In north-up raster coordinates, +x is East and +y (row) is South, so downhill is (-dz_dx, +dz_dy).
    aspect_rad = np.arctan2(-dz_dx, dz_dy)
    aspect_deg = (np.degrees(aspect_rad) + 360.0) % 360.0
    aspect_deg = np.where((dz_dx == 0) & (dz_dy == 0), -1.0, aspect_deg).astype(np.float32)

    # Propagate nodata across 3x3 neighborhood
    mask_pad = np.pad(nodata_mask, 1, mode="edge")
    any_nodata = (
        mask_pad[:-2, :-2]
        | mask_pad[:-2, 1:-1]
        | mask_pad[:-2, 2:]
        | mask_pad[1:-1, :-2]
        | mask_pad[1:-1, 1:-1]
        | mask_pad[1:-1, 2:]
        | mask_pad[2:, :-2]
        | mask_pad[2:, 1:-1]
        | mask_pad[2:, 2:]
    )
    slope_deg[any_nodata] = NODATA_VAL
    aspect_deg[any_nodata] = NODATA_VAL
    return slope_deg, aspect_deg


def ingest_copernicus_dem(
    boundary_path: Path = PILOT_DIR / "dima_hasao_boundary.geojson",
    output_dir: Path = PILOT_DIR,
    target_resolution_m: float = 90.0,
) -> dict[str, Any]:
    """
    Reads real Copernicus DEM GLO-30 COG windows for Dima Hasao using HTTP range requests.
    Note: Exports full native ~30 m DEM for the Haflong/Jatinga core corridor AND a compact
    90 m district-wide DEM + slope + aspect raster (derived directly from GLO-30) to respect
    the 20 GB SSD / 8 GB RAM server constraint while preserving real 30 m native sampling.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    bbox = boundary["metadata"]["bbox_wgs84"]
    buf = 0.02
    clip_bounds = [bbox[0] - buf, bbox[1] - buf, bbox[2] + buf, bbox[3] + buf]
    tile_urls = _required_tiles(clip_bounds)

    env_opts = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_TIMEOUT": "30",
        "GDAL_HTTP_MAX_RETRY": "3",
    }

    opened_datasets = []
    source_tiles_used: list[dict[str, Any]] = []
    try:
        with rasterio.Env(**env_opts):
            for url in tile_urls:
                vsi_url = f"/vsicurl/{url}"
                ds = rasterio.open(vsi_url)
                opened_datasets.append(ds)
                source_tiles_used.append(
                    {
                        "url": url,
                        "native_crs": str(ds.crs),
                        "native_res_deg": [round(float(ds.res[0]), 8), round(float(ds.res[1]), 8)],
                        "width": ds.width,
                        "height": ds.height,
                        "dtype": ds.dtypes[0],
                    }
                )

            # Merge only the clipped Dima Hasao bounding box window (HTTP range reads)
            mosaic, mosaic_transform = merge(
                opened_datasets,
                bounds=tuple(clip_bounds),
                nodata=NODATA_VAL,
            )
            src_crs = opened_datasets[0].crs
    finally:
        for ds in opened_datasets:
            ds.close()

    dem_native = mosaic[0].astype(np.float32)
    native_h, native_w = dem_native.shape

    # Reproject native 30m DEM to UTM Zone 46N at target_resolution_m for accurate metric slope/aspect
    left, bottom, right, top = rasterio.transform.array_bounds(native_h, native_w, mosaic_transform)
    utm_transform, utm_w, utm_h = calculate_default_transform(
        src_crs, UTM_CRS, native_w, native_h, left, bottom, right, top, resolution=target_resolution_m
    )

    dem_utm = np.full((utm_h, utm_w), NODATA_VAL, dtype=np.float32)
    reproject(
        source=dem_native,
        destination=dem_utm,
        src_transform=mosaic_transform,
        src_crs=src_crs,
        src_nodata=NODATA_VAL,
        dst_transform=utm_transform,
        dst_crs=UTM_CRS,
        dst_nodata=NODATA_VAL,
        resampling=Resampling.bilinear,
    )

    nodata_mask = np.isnan(dem_utm) | (dem_utm <= -9000.0)
    slope_utm, aspect_utm = compute_slope_aspect_horn(
        dem_utm, utm_transform.a, utm_transform.e, nodata_mask
    )

    # Also save native 30m Haflong-Jatinga core corridor clip (approx 25.05-25.30N, 92.85-93.15E)
    core_bounds = (92.85, 25.05, 93.15, 25.30)
    core_win = from_bounds(*core_bounds, transform=mosaic_transform).round_offsets().round_lengths()
    r0 = max(0, int(core_win.row_off))
    c0 = max(0, int(core_win.col_off))
    r1 = min(native_h, r0 + int(core_win.height))
    c1 = min(native_w, c0 + int(core_win.width))
    dem_core_30m = dem_native[r0:r1, c0:c1]
    core_transform = rasterio.windows.transform(
        rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0), mosaic_transform
    )

    core_path = output_dir / "haflong_jatinga_copernicus_dem_30m.tif"
    with rasterio.open(
        core_path,
        "w",
        driver="GTiff",
        height=dem_core_30m.shape[0],
        width=dem_core_30m.shape[1],
        count=1,
        dtype="float32",
        crs=WGS84_CRS,
        transform=core_transform,
        nodata=NODATA_VAL,
        compress="deflate",
        predictor=3,
        tiled=True,
    ) as dst:
        dst.write(dem_core_30m, 1)

    # Write district-wide UTM 46N DEM, Slope, Aspect GeoTIFFs (compact, metric CRS)
    utm_profile = {
        "driver": "GTiff",
        "height": utm_h,
        "width": utm_w,
        "count": 1,
        "dtype": "float32",
        "crs": UTM_CRS,
        "transform": utm_transform,
        "nodata": NODATA_VAL,
        "compress": "deflate",
        "predictor": 3,
        "tiled": True,
    }
    dem_path = output_dir / "dima_hasao_dem_utm46n.tif"
    slope_path = output_dir / "dima_hasao_slope_deg_utm46n.tif"
    aspect_path = output_dir / "dima_hasao_aspect_deg_utm46n.tif"

    for out_p, arr in [(dem_path, dem_utm), (slope_path, slope_utm), (aspect_path, aspect_utm)]:
        with rasterio.open(out_p, "w", **utm_profile) as dst:
            dst.write(arr, 1)

    valid_dem = dem_utm[~nodata_mask]
    valid_slope = slope_utm[slope_utm != NODATA_VAL]
    processed_at = datetime.now(timezone.utc).isoformat()

    metadata = {
        "dataset_id": "copernicus-dem-glo30",
        "dataset_name": "Copernicus DEM GLO-30 (Global 30 m Digital Surface Model)",
        "product_version": "COP-DEM_GLO-30-DGED / 2021_1 (AWS Open Data COG)",
        "source_tiles": source_tiles_used,
        "native_crs": WGS84_CRS,
        "derived_metric_crs": UTM_CRS,
        "native_resolution_m": 30.0,
        "district_raster_resolution_m": target_resolution_m,
        "core_corridor_native_30m_file": core_path.name,
        "district_dem_file": dem_path.name,
        "district_slope_file": slope_path.name,
        "district_aspect_file": aspect_path.name,
        "clip_bounds_wgs84": [round(v, 6) for v in clip_bounds],
        "core_corridor_bounds_wgs84": list(core_bounds),
        "elevation_stats_m": {
            "min": round(float(np.min(valid_dem)), 2),
            "max": round(float(np.max(valid_dem)), 2),
            "mean": round(float(np.mean(valid_dem)), 2),
            "p95": round(float(np.percentile(valid_dem, 95)), 2),
        },
        "slope_stats_deg": {
            "min": round(float(np.min(valid_slope)), 2),
            "max": round(float(np.max(valid_slope)), 2),
            "mean": round(float(np.mean(valid_slope)), 2),
            "p95": round(float(np.percentile(valid_slope, 95)), 2),
        },
        "file_sizes_kb": {
            core_path.name: round(core_path.stat().st_size / 1024, 1),
            dem_path.name: round(dem_path.stat().st_size / 1024, 1),
            slope_path.name: round(slope_path.stat().st_size / 1024, 1),
            aspect_path.name: round(aspect_path.stat().st_size / 1024, 1),
        },
        "slope_algorithm": "Horn (1981) 3x3 finite difference on EPSG:32646 projected meters",
        "observation_period": "TanDEM-X mission acquisitions (2011–2015), Copernicus DEM release 2021",
        "processing_timestamp": processed_at,
        "attribution": "© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA",
        "limitations": "GLO-30 is a Digital Surface Model (DSM) including forest canopy height; 90 m district derivatives smooth micro-cliff gradients compared to native 30 m.",
    }
    meta_path = output_dir / "copernicus_dem_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    result = ingest_copernicus_dem()
    print(json.dumps(result, indent=2))
