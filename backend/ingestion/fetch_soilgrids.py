"""
Stage 9 Priority 4A — Authentic ISRIC SoilGrids 2.0 WCS 2.0 Ingestion for Dima Hasao District.

Fetches real 250 m SoilGrids 2.0 global soil property GeoTIFF layers directly from the
official ISRIC WCS 2.0 service (`https://maps.isric.org/mapserv`) with zero synthetic fallback:
  - clay   (0-5cm & 15-30cm, g/kg -> % mass)
  - sand   (0-5cm & 15-30cm, g/kg -> % mass)
  - silt   (0-5cm & 15-30cm, g/kg -> % mass)
  - bdod   (0-5cm, cg/cm3 -> g/cm3 bulk density)
  - cfvo   (0-5cm, cm3/dm3 -> % volumetric coarse fragments)
  - soc    (0-5cm, dg/kg -> g/kg soil organic carbon)

Reprojects and aligns each raster onto the canonical Dima Hasao UTM Zone 46N (EPSG:32646)
analysis extent (250 m metric pixel grid) and records explicit nodata handling, valid pixel %,
unit conversion factors, ISRIC Homolosine -> EPSG:32646 provenance, and uncertainty notes.
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
from rasterio.warp import Resampling, calculate_default_transform, reproject
from shapely.geometry import shape

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
RAW_SOIL_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "soilgrids"

ISRIC_WCS_BASE = "https://maps.isric.org/mapserv"
ISRIC_HOMOLOSINE_PROJ = "+proj=igh +lat_0=0 +lon_0=0 +datum=WGS84 +units=m +no_defs"
TARGET_CRS = "EPSG:32646"
TARGET_RES_M = 250.0
NODATA_FLOAT = -9999.0

# Each layer spec: (map_name, coverage_id, scale_to_si, si_units, description)
SOILGRIDS_LAYERS: list[dict[str, Any]] = [
    {
        "layer_id": "clay_0_5cm",
        "map_file": "/map/clay.map",
        "coverage_id": "clay_0-5cm_mean",
        "scale_factor": 0.1,  # g/kg -> % (g/100g)
        "raw_units": "g/kg",
        "units": "% (mass)",
        "valid_min": 0.0,
        "valid_max": 100.0,
        "description": "Clay content (<2 um) at 0-5 cm depth (mean prediction)",
    },
    {
        "layer_id": "clay_15_30cm",
        "map_file": "/map/clay.map",
        "coverage_id": "clay_15-30cm_mean",
        "scale_factor": 0.1,
        "raw_units": "g/kg",
        "units": "% (mass)",
        "valid_min": 0.0,
        "valid_max": 100.0,
        "description": "Clay content (<2 um) at 15-30 cm depth (mean prediction)",
    },
    {
        "layer_id": "sand_0_5cm",
        "map_file": "/map/sand.map",
        "coverage_id": "sand_0-5cm_mean",
        "scale_factor": 0.1,
        "raw_units": "g/kg",
        "units": "% (mass)",
        "valid_min": 0.0,
        "valid_max": 100.0,
        "description": "Sand content (50-2000 um) at 0-5 cm depth (mean prediction)",
    },
    {
        "layer_id": "silt_0_5cm",
        "map_file": "/map/silt.map",
        "coverage_id": "silt_0-5cm_mean",
        "scale_factor": 0.1,
        "raw_units": "g/kg",
        "units": "% (mass)",
        "valid_min": 0.0,
        "valid_max": 100.0,
        "description": "Silt content (2-50 um) at 0-5 cm depth (mean prediction)",
    },
    {
        "layer_id": "bdod_0_5cm",
        "map_file": "/map/bdod.map",
        "coverage_id": "bdod_0-5cm_mean",
        "scale_factor": 0.01,  # cg/cm3 -> g/cm3
        "raw_units": "cg/cm3",
        "units": "g/cm3",
        "valid_min": 0.1,
        "valid_max": 2.6,
        "description": "Bulk density of the fine earth fraction at 0-5 cm depth (mean prediction)",
    },
    {
        "layer_id": "cfvo_0_5cm",
        "map_file": "/map/cfvo.map",
        "coverage_id": "cfvo_0-5cm_mean",
        "scale_factor": 0.1,  # cm3/dm3 -> % vol
        "raw_units": "cm3/dm3",
        "units": "% (volumetric)",
        "valid_min": 0.0,
        "valid_max": 100.0,
        "description": "Volumetric fraction of coarse fragments (>2 mm) at 0-5 cm depth (mean prediction)",
    },
    {
        "layer_id": "soc_0_5cm",
        "map_file": "/map/soc.map",
        "coverage_id": "soc_0-5cm_mean",
        "scale_factor": 0.1,  # dg/kg -> g/kg
        "raw_units": "dg/kg",
        "units": "g/kg",
        "valid_min": 0.0,
        "valid_max": 500.0,
        "description": "Soil organic carbon content in the fine earth fraction at 0-5 cm depth (mean prediction)",
    },
]


def _compute_homolosine_subset_bounds(boundary_polygon: Any, buffer_m: float = 5000.0) -> tuple[float, float, float, float]:
    """Transform Dima Hasao WGS84 boundary corners into ISRIC Interrupted Goode Homolosine meters."""
    minx, miny, maxx, maxy = boundary_polygon.bounds
    # Sample boundary perimeter densely to avoid projection distortion misses
    transformer = Transformer.from_crs("EPSG:4326", ISRIC_HOMOLOSINE_PROJ, always_xy=True)
    xs_wgs = np.linspace(minx, maxx, 25)
    ys_wgs = np.linspace(miny, maxy, 25)
    pts_x, pts_y = [], []
    for x in xs_wgs:
        for y in (miny, maxy):
            hx, hy = transformer.transform(float(x), float(y))
            pts_x.append(hx)
            pts_y.append(hy)
    for y in ys_wgs:
        for x in (minx, maxx):
            hx, hy = transformer.transform(float(x), float(y))
            pts_x.append(hx)
            pts_y.append(hy)
    return (
        min(pts_x) - buffer_m,
        min(pts_y) - buffer_m,
        max(pts_x) + buffer_m,
        max(pts_y) + buffer_m,
    )


def _fetch_wcs_geotiff(
    map_file: str,
    coverage_id: str,
    igh_bounds: tuple[float, float, float, float],
    raw_dest: Path,
    max_retries: int = 3,
) -> tuple[str, int]:
    """Download a GeoTIFF subset from ISRIC SoilGrids WCS 2.0.1."""
    raw_dest.parent.mkdir(parents=True, exist_ok=True)
    minx, miny, maxx, maxy = igh_bounds
    query_params = [
        ("map", map_file),
        ("SERVICE", "WCS"),
        ("VERSION", "2.0.1"),
        ("REQUEST", "GetCoverage"),
        ("COVERAGEID", coverage_id),
        ("FORMAT", "GEOTIFF_INT16"),
        ("SUBSET", f"X({minx:.2f},{maxx:.2f})"),
        ("SUBSET", f"Y({miny:.2f},{maxy:.2f})"),
        ("SUBSETTINGCRS", "http://www.opengis.net/def/crs/EPSG/0/152160"),
        ("OUTPUTCRS", "http://www.opengis.net/def/crs/EPSG/0/152160"),
    ]

    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=60.0, follow_redirects=True) as client:
                resp = client.get(
                    ISRIC_WCS_BASE,
                    params=query_params,
                    headers={"User-Agent": "GeoResilience-NER/2.0 (Scientific Research)"},
                )
                resp.raise_for_status()
                ctype = resp.headers.get("content-type", "").lower()
                if "tiff" not in ctype and resp.content[:2] not in (b"II", b"MM"):
                    raise RuntimeError(
                        f"ISRIC WCS returned non-GeoTIFF content-type={ctype!r}: {resp.text[:200]}"
                    )
                raw_dest.write_bytes(resp.content)
                return str(resp.url), len(resp.content)
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                time.sleep(2.0 * attempt)

    raise RuntimeError(f"Failed to download {coverage_id} from ISRIC WCS: {last_err}")


def _warp_and_scale_to_utm46n(
    raw_path: Path,
    out_path: Path,
    scale_factor: float,
    utm_bounds: tuple[float, float, float, float],
) -> dict[str, Any]:
    """Reproject ISRIC Homolosine INT16 GeoTIFF to EPSG:32646 float32 in physical units."""
    with rasterio.open(raw_path) as src:
        src_crs = src.crs if src.crs else rasterio.crs.CRS.from_proj4(ISRIC_HOMOLOSINE_PROJ)
        src_nodata = src.nodata if src.nodata is not None else -32768

        dst_transform, dst_width, dst_height = calculate_default_transform(
            src_crs,
            TARGET_CRS,
            src.width,
            src.height,
            *src.bounds,
            resolution=TARGET_RES_M,
        )

        # Ensure output raster strictly covers utm_bounds by using explicit padded target grid
        uminx, uminy, umaxx, umaxy = utm_bounds
        pad = 1000.0
        left = np.floor((uminx - pad) / TARGET_RES_M) * TARGET_RES_M
        bottom = np.floor((uminy - pad) / TARGET_RES_M) * TARGET_RES_M
        right = np.ceil((umaxx + pad) / TARGET_RES_M) * TARGET_RES_M
        top = np.ceil((umaxy + pad) / TARGET_RES_M) * TARGET_RES_M
        dst_width = int(round((right - left) / TARGET_RES_M))
        dst_height = int(round((top - bottom) / TARGET_RES_M))
        dst_transform = rasterio.transform.from_bounds(left, bottom, right, top, dst_width, dst_height)

        raw_arr = src.read(1).astype(np.float32)
        # ISRIC SoilGrids 2.0 encodes open-water / urban non-soil mask pixels as 0 in INT16 WCS coverages
        is_nodata = (raw_arr == src_nodata) | (raw_arr <= -32767) | (raw_arr <= 0)
        scaled_src = np.where(
            is_nodata,
            NODATA_FLOAT,
            raw_arr * scale_factor,
        ).astype(np.float32)

        dst_arr = np.full((dst_height, dst_width), NODATA_FLOAT, dtype=np.float32)
        reproject(
            source=scaled_src,
            destination=dst_arr,
            src_transform=src.transform,
            src_crs=src_crs,
            src_nodata=NODATA_FLOAT,
            dst_transform=dst_transform,
            dst_crs=TARGET_CRS,
            dst_nodata=NODATA_FLOAT,
            resampling=Resampling.bilinear,
        )

        profile = {
            "driver": "GTiff",
            "dtype": "float32",
            "count": 1,
            "width": dst_width,
            "height": dst_height,
            "crs": TARGET_CRS,
            "transform": dst_transform,
            "nodata": NODATA_FLOAT,
            "compress": "deflate",
        }
        with rasterio.open(out_path, "w", **profile) as dst:
            dst.write(dst_arr, 1)

    valid = dst_arr[(dst_arr != NODATA_FLOAT) & (~np.isnan(dst_arr))]
    valid_pct = round(100.0 * valid.size / dst_arr.size, 2) if dst_arr.size else 0.0
    return {
        "file": out_path.name,
        "crs": TARGET_CRS,
        "resolution_m": TARGET_RES_M,
        "width": dst_width,
        "height": dst_height,
        "bounds_utm46n": [round(float(x), 2) for x in (left, bottom, right, top)],
        "nodata": NODATA_FLOAT,
        "valid_pixel_pct": valid_pct,
        "min": round(float(valid.min()), 3) if valid.size else None,
        "max": round(float(valid.max()), 3) if valid.size else None,
        "mean": round(float(valid.mean()), 3) if valid.size else None,
        "std": round(float(valid.std()), 3) if valid.size else None,
        "file_bytes": out_path.stat().st_size,
    }


def fetch_soilgrids_dima_hasao(pilot_dir: Path = PILOT_DIR) -> dict[str, Any]:
    boundary_gj = json.loads((pilot_dir / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
    geom = boundary_gj["features"][0]["geometry"] if "features" in boundary_gj else boundary_gj["geometry"]
    poly = shape(geom)

    igh_bounds = _compute_homolosine_subset_bounds(poly, buffer_m=8000.0)
    to_utm = Transformer.from_crs("EPSG:4326", TARGET_CRS, always_xy=True)
    bminx, bminy, bmaxx, bmaxy = poly.bounds
    u1x, u1y = to_utm.transform(bminx, bminy)
    u2x, u2y = to_utm.transform(bmaxx, bmaxy)
    utm_bounds = (min(u1x, u2x), min(u1y, u2y), max(u1x, u2x), max(u1y, u2y))

    layer_results: list[dict[str, Any]] = []
    for spec in SOILGRIDS_LAYERS:
        raw_tif = RAW_SOIL_DIR / f"{spec['coverage_id']}_igh.tif"
        out_tif = pilot_dir / f"dima_hasao_soilgrids_{spec['layer_id']}_utm46n.tif"
        req_url, raw_bytes = _fetch_wcs_geotiff(
            spec["map_file"], spec["coverage_id"], igh_bounds, raw_tif
        )
        stats = _warp_and_scale_to_utm46n(raw_tif, out_tif, spec["scale_factor"], utm_bounds)
        in_range = (
            stats["min"] is not None
            and stats["max"] is not None
            and spec["valid_min"] <= stats["min"]
            and stats["max"] <= spec["valid_max"]
        )
        layer_results.append(
            {
                "layer_id": spec["layer_id"],
                "coverage_id": spec["coverage_id"],
                "description": spec["description"],
                "units": spec["units"],
                "raw_units": spec["raw_units"],
                "scale_factor": spec["scale_factor"],
                "source_url": req_url,
                "raw_download_bytes": raw_bytes,
                "physical_range_valid": in_range,
                **stats,
            }
        )

    metadata = {
        "dataset_id": "isric-soilgrids-2.0-dima-hasao",
        "dataset_name": "ISRIC SoilGrids 2.0 (250 m) — Dima Hasao Soil Properties",
        "product_version": "SoilGrids 2.0 (v2020)",
        "provider": "ISRIC — World Soil Information",
        "source_service": ISRIC_WCS_BASE,
        "license": "CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/)",
        "attribution": "Poggio, L., de Sousa, L. M., Batjes, N. H., et al. (2021). SoilGrids 2.0: producing soil information for the globe with quantified spatial uncertainty. SOIL, 7, 217-240.",
        "observation_period": "Static global digital soil mapping (WoSIS profiles through 2019; 2020 release)",
        "temporal_validity": "Static pedological baseline; valid as pre-event geotechnical conditioning covariate for post-2015 landslides, NOT dynamic soil moisture.",
        "native_crs": "EPSG:152160 / Interrupted Goode Homolosine",
        "exported_crs": TARGET_CRS,
        "native_resolution_m": 250.0,
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "uncertainty_and_limitations": (
            "SoilGrids 2.0 predictions are machine-learning interpolations from sparse WoSIS profiles "
            "at 250 m resolution. Steep Himalayan/Barail hillslopes in Dima Hasao have limited local "
            "profile density; these layers represent regional soil texture/bulk-density priors and "
            "do NOT replace site-specific geotechnical shear-strength tests or dynamic soil moisture (SMAP)."
        ),
        "layers": layer_results,
    }

    meta_path = pilot_dir / "soilgrids_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    meta = fetch_soilgrids_dima_hasao()
    print(
        json.dumps(
            {
                "dataset_id": meta["dataset_id"],
                "layers_ingested": len(meta["layers"]),
                "summary": [
                    {
                        "id": l["layer_id"],
                        "valid_pct": l["valid_pixel_pct"],
                        "min": l["min"],
                        "max": l["max"],
                        "mean": l["mean"],
                        "units": l["units"],
                    }
                    for l in meta["layers"]
                ],
            },
            indent=2,
        )
    )
