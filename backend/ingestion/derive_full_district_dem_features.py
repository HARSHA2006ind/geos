"""
Stage 9 Priority 4B — Full-District DEM Geomorphometric & Hydrological Feature Derivation.

Computes scientifically standard terrain & hydrological conditioning factors directly from the
verified full-district Copernicus DEM GLO-30 (EPSG:32646, aligned exact grid with existing
`dima_hasao_dem_utm46n.tif`, `dima_hasao_slope_deg_utm46n.tif`, `dima_hasao_aspect_deg_utm46n.tif`):
  1. Profile curvature (1/100m, Zevenbergen & Thorne 1987) — controls downslope acceleration/deceleration
  2. Planform (contour) curvature (1/100m, Zevenbergen & Thorne 1987) — controls flow convergence/divergence
  3. Terrain Ruggedness Index (TRI, meters, Riley et al. 1999) — local relief heterogeneity
  4. D8 Flow Accumulation (contributing upslope area in m2 via topographic sort over elevation)
  5. Topographic Wetness Index (TWI = ln(a / tan(beta)), Beven & Kirkby 1979)
  6. Synthetic-free DEM-derived drainage network (contributing area >= 0.5 km2) and
     Euclidean distance to drainage channel (meters, via scipy.ndimage.distance_transform_edt)

All output rasters share the EXACT shape, pixel size, nodata (-9999.0), and affine transform
of `dima_hasao_dem_utm46n.tif` (EPSG:32646).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
NODATA = -9999.0
CHANNEL_AREA_THRESHOLD_M2 = 500_000.0  # 0.5 km2 contributing area threshold for valley/stream initiation


def _compute_curvatures_zt(z: np.ndarray, dx: float, dy: float, valid_mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Zevenbergen & Thorne (1987) 3x3 polynomial profile & planform curvature (scaled per 100 m).
    Returns (profile_curvature, plan_curvature).
    """
    L = 0.5 * (dx + dy)
    # Pad edges by replicating boundary pixels so interior 3x3 stencils stay finite
    zp = np.pad(z, 1, mode="edge")
    z1 = zp[:-2, :-2]
    z2 = zp[:-2, 1:-1]
    z3 = zp[:-2, 2:]
    z4 = zp[1:-1, :-2]
    z5 = zp[1:-1, 1:-1]
    z6 = zp[1:-1, 2:]
    z7 = zp[2:, :-2]
    z8 = zp[2:, 1:-1]
    z9 = zp[2:, 2:]

    D = ((z4 + z6) / 2.0 - z5) / (L * L)
    E = ((z2 + z8) / 2.0 - z5) / (L * L)
    F = (-z1 + z3 + z7 - z9) / (4.0 * L * L)
    G = (-z4 + z6) / (2.0 * L)
    H = (z2 - z8) / (2.0 * L)

    g2_h2 = G * G + H * H
    eps = 1e-10
    safe_denom = np.where(g2_h2 > eps, g2_h2, 1.0)

    # Profile curvature (rate of change of slope along flow line); multiply by 100 for standard 1/100m units
    prof = np.where(
        g2_h2 > eps,
        -2.0 * (D * G * G + E * H * H + F * G * H) / safe_denom * 100.0,
        0.0,
    )
    # Planform curvature (curvature perpendicular to slope direction); positive = convex, negative = concave/convergent
    plan = np.where(
        g2_h2 > eps,
        2.0 * (D * H * H + E * G * G - F * G * H) / safe_denom * 100.0,
        0.0,
    )

    # Clip extreme single-pixel DEM artifacts to physically plausible [-25, 25] (1/100m)
    prof = np.clip(prof, -25.0, 25.0).astype(np.float32)
    plan = np.clip(plan, -25.0, 25.0).astype(np.float32)

    prof[~valid_mask] = NODATA
    plan[~valid_mask] = NODATA
    return prof, plan


def _compute_tri(z: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    """Riley et al. (1999) Terrain Ruggedness Index: sqrt(sum((z_neighbor - z_center)^2))."""
    zp = np.pad(z, 1, mode="edge")
    zc = zp[1:-1, 1:-1]
    sq_sum = np.zeros_like(z, dtype=np.float64)
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue
            nb = zp[1 + dr : 1 + dr + z.shape[0], 1 + dc : 1 + dc + z.shape[1]]
            diff = nb - zc
            sq_sum += diff * diff
    tri = np.sqrt(sq_sum).astype(np.float32)
    tri[~valid_mask] = NODATA
    return tri


def _compute_d8_flow_accumulation_and_twi(
    z: np.ndarray,
    slope_deg: np.ndarray,
    dx: float,
    dy: float,
    valid_mask: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Fast vectorized D8 steepest-descent receiver computation + exact elevation-sorted
    accumulation (O(N log N)) to derive:
      - specific contributing area & total contributing area (m2)
      - Topographic Wetness Index TWI = ln(a / tan(beta))
      - Euclidean distance to drainage network (m) where contributing area >= 0.5 km2
    """
    rows, cols = z.shape
    n = rows * cols
    cell_area = dx * dy
    cell_width = 0.5 * (dx + dy)

    # Find steepest downslope neighbor among 8 directions
    offsets = [
        (-1, -1, np.hypot(dx, dy)),
        (-1, 0, dy),
        (-1, 1, np.hypot(dx, dy)),
        (0, -1, dx),
        (0, 1, dx),
        (1, -1, np.hypot(dx, dy)),
        (1, 0, dy),
        (1, 1, np.hypot(dx, dy)),
    ]

    max_drop = np.zeros((rows, cols), dtype=np.float32)
    recv_r = np.full((rows, cols), -1, dtype=np.int32)
    recv_c = np.full((rows, cols), -1, dtype=np.int32)

    r_grid, c_grid = np.indices((rows, cols), dtype=np.int32)

    for dr, dc, dist in offsets:
        # Source slice and neighbor slice
        r0_s = max(0, -dr)
        r1_s = rows - max(0, dr)
        c0_s = max(0, -dc)
        c1_s = cols - max(0, dc)

        r0_n = max(0, dr)
        r1_n = rows - max(0, -dr)
        c0_n = max(0, dc)
        c1_n = cols - max(0, -dc)

        z_src = z[r0_s:r1_s, c0_s:c1_s]
        z_nb = z[r0_n:r1_n, c0_n:c1_n]
        v_nb = valid_mask[r0_n:r1_n, c0_n:c1_n]

        grad = np.where(v_nb, (z_src - z_nb) / dist, -1.0)
        better = grad > max_drop[r0_s:r1_s, c0_s:c1_s]

        max_drop[r0_s:r1_s, c0_s:c1_s] = np.where(better, grad, max_drop[r0_s:r1_s, c0_s:c1_s])
        recv_r[r0_s:r1_s, c0_s:c1_s] = np.where(
            better, r_grid[r0_n:r1_n, c0_n:c1_n], recv_r[r0_s:r1_s, c0_s:c1_s]
        )
        recv_c[r0_s:r1_s, c0_s:c1_s] = np.where(
            better, c_grid[r0_n:r1_n, c0_n:c1_n], recv_c[r0_s:r1_s, c0_s:c1_s]
        )

    # Flatten receiver index (-1 for sinks / boundary outlets)
    recv_flat = np.where(recv_r >= 0, recv_r * cols + recv_c, -1).ravel()
    z_flat = np.where(valid_mask, z, -1e9).ravel()

    # Traverse cells from highest elevation to lowest so every donor finishes before receiver
    order = np.argsort(z_flat)[::-1]
    acc_cells = np.ones(n, dtype=np.float64)
    acc_cells[~valid_mask.ravel()] = 0.0

    # Pure Python tight loop over ~1M cells takes ~0.35s in CPython 3.11
    acc_list = acc_cells.tolist()
    recv_list = recv_flat.tolist()
    for idx in order.tolist():
        rec = recv_list[idx]
        if rec >= 0:
            acc_list[rec] += acc_list[idx]

    acc_area_m2 = (np.asarray(acc_list, dtype=np.float32).reshape(rows, cols)) * float(cell_area)

    # Specific contributing area a = A / cell_width (m2 / m = m)
    spec_area = np.maximum(acc_area_m2 / cell_width, cell_width)
    # Prevent tan(0) singularity with standard 0.005 rad (~0.29 deg) floor
    slope_rad = np.radians(np.clip(slope_deg, 0.29, 89.0))
    twi = np.log(spec_area / np.tan(slope_rad)).astype(np.float32)

    # Drainage channel mask & Euclidean distance to nearest drainage channel (meters)
    channel_mask = (acc_area_m2 >= CHANNEL_AREA_THRESHOLD_M2) & valid_mask
    # distance_transform_edt measures distance from non-zero cells to nearest zero cell
    dist_drainage_m = distance_transform_edt(~channel_mask, sampling=(dy, dx)).astype(np.float32)

    acc_area_m2[~valid_mask] = NODATA
    twi[~valid_mask] = NODATA
    dist_drainage_m[~valid_mask] = NODATA

    return acc_area_m2, twi, dist_drainage_m


def _write_raster(path: Path, arr: np.ndarray, profile: dict[str, Any]) -> dict[str, Any]:
    out_prof = dict(profile)
    out_prof.update(dtype="float32", count=1, nodata=NODATA, compress="deflate")
    with rasterio.open(path, "w", **out_prof) as dst:
        dst.write(arr.astype(np.float32), 1)
    valid = arr[(arr != NODATA) & (~np.isnan(arr))]
    return {
        "file": path.name,
        "crs": str(profile["crs"]),
        "width": int(profile["width"]),
        "height": int(profile["height"]),
        "nodata": NODATA,
        "valid_pixel_pct": round(100.0 * valid.size / arr.size, 2) if arr.size else 0.0,
        "min": round(float(valid.min()), 4) if valid.size else None,
        "max": round(float(valid.max()), 4) if valid.size else None,
        "mean": round(float(valid.mean()), 4) if valid.size else None,
        "std": round(float(valid.std()), 4) if valid.size else None,
        "p95": round(float(np.percentile(valid, 95)), 4) if valid.size else None,
        "file_bytes": path.stat().st_size,
    }


def derive_full_district_dem_features(pilot_dir: Path = PILOT_DIR) -> dict[str, Any]:
    dem_path = pilot_dir / "dima_hasao_dem_utm46n.tif"
    slope_path = pilot_dir / "dima_hasao_slope_deg_utm46n.tif"
    if not dem_path.exists() or not slope_path.exists():
        raise FileNotFoundError("Base Copernicus DEM UTM46N and slope rasters must exist first.")

    with rasterio.open(dem_path) as src_dem, rasterio.open(slope_path) as src_slope:
        profile = src_dem.profile.copy()
        dem_arr = src_dem.read(1).astype(np.float64)
        slope_arr = src_slope.read(1).astype(np.float64)
        dem_nodata = src_dem.nodata
        dx = abs(float(src_dem.transform.a))
        dy = abs(float(src_dem.transform.e))

    valid_mask = (~np.isnan(dem_arr)) & (dem_arr != dem_nodata) & (slope_arr >= 0.0)
    z_clean = np.where(valid_mask, dem_arr, np.nanmedian(dem_arr[valid_mask]))

    prof_curv, plan_curv = _compute_curvatures_zt(z_clean, dx, dy, valid_mask)
    tri = _compute_tri(z_clean, valid_mask)
    flow_acc_m2, twi, dist_drainage_m = _compute_d8_flow_accumulation_and_twi(
        z_clean, np.where(valid_mask, slope_arr, 1.0), dx, dy, valid_mask
    )

    outputs = {
        "profile_curvature": _write_raster(
            pilot_dir / "dima_hasao_profile_curvature_utm46n.tif", prof_curv, profile
        ),
        "plan_curvature": _write_raster(
            pilot_dir / "dima_hasao_plan_curvature_utm46n.tif", plan_curv, profile
        ),
        "tri": _write_raster(pilot_dir / "dima_hasao_tri_m_utm46n.tif", tri, profile),
        "flow_accumulation_m2": _write_raster(
            pilot_dir / "dima_hasao_flow_acc_m2_utm46n.tif", flow_acc_m2, profile
        ),
        "twi": _write_raster(pilot_dir / "dima_hasao_twi_utm46n.tif", twi, profile),
        "distance_to_drainage_m": _write_raster(
            pilot_dir / "dima_hasao_dist_drainage_m_utm46n.tif", dist_drainage_m, profile
        ),
    }

    metadata = {
        "dataset_id": "copernicus-dem-geomorphometric-hydrological-derivatives",
        "dataset_name": "Full-District DEM Geomorphometric & Hydrological Features (Dima Hasao)",
        "source_dem": dem_path.name,
        "source_slope": slope_path.name,
        "crs": str(profile["crs"]),
        "pixel_size_m": [round(dx, 3), round(dy, 3)],
        "grid_shape": [int(profile["height"]), int(profile["width"])],
        "processing_timestamp": datetime.now(timezone.utc).isoformat(),
        "methods": {
            "curvature": "Zevenbergen & Thorne (1987) 3x3 polynomial profile & planform curvature (1/100 m)",
            "tri": "Riley et al. (1999) Terrain Ruggedness Index (m)",
            "flow_accumulation": "D8 steepest-descent topographic-sort upslope area (m2)",
            "twi": "Beven & Kirkby (1979) Topographic Wetness Index ln(a / tan(beta))",
            "distance_to_drainage": f"Euclidean distance (m) to D8 channels with upslope area >= {CHANNEL_AREA_THRESHOLD_M2/1e6:.2f} km2",
        },
        "attribution": "Derived from Copernicus DEM GLO-30 (ESA / Airbus, © DLR e.V. 2010-2014 & Airbus Defence and Space GmbH 2014-2018)",
        "temporal_validity": "Static topographic baseline (2011-2015 TanDEM-X epoch); valid pre-event conditioning factor.",
        "uncertainty_and_limitations": (
            "Derived on the 90 m district UTM grid (aligned with dima_hasao_dem_utm46n.tif) without "
            "pit-filling breach carve; micro-scale gullies (< 90 m) and artificial road culverts are unresolved."
        ),
        "layers": outputs,
    }

    meta_path = pilot_dir / "dem_derivatives_metadata.json"
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return metadata


if __name__ == "__main__":
    meta = derive_full_district_dem_features()
    print(json.dumps(meta["layers"], indent=2))
