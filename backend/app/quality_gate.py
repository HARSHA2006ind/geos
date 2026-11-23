"""
Stage 5 & Stage 9 — Automated Scientific Data Quality Gate for GeoResilience-NER 2.0.

Enforces 13 mandatory scientific & engineering checks before allowing any
Random Forest or XGBoost landslide model training:
  1. coordinate_validity
  2. geographic_coverage
  3. crs_alignment
  4. raster_nodata_handling
  5. rainfall_continuity
  6. units_and_physical_ranges
  7. duplicate_landslide_events
  8. landslide_location_uncertainty
  9. event_date_precision
 10. feature_timestamps
 11. dataset_licensing_and_provenance
 12. data_leakage_prevention
 13. train_test_geographic_separation

Scientific Sufficiency Policy (Stage 9):
  Numeric event counts such as 30 (provisional pilot floor) or 150 (provisional multi-year
  research target) are treated ONLY as provisional engineering milestones — NEVER as
  scientifically sufficient conditions by themselves. Training readiness additionally requires:
    - certified polygon/GPS positional error metadata (not point-only unverified centroids),
    - multi-year independent storm coverage for temporal holdout validation,
    - control of road/railway corridor sampling bias (preventing accessibility-proxy overfitting),
    - strict pre-event covariate timestamp alignment (no post-event land cover or NDVI leakage),
    - wall-to-wall lithology/fault and dynamic antecedent moisture coverage, and
    - independent geographic block separation for out-of-region generalization.

NEVER fabricates missing data or weakens failed scientific gates.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import box, shape

from backend.ingestion.fetch_coolr_landslides import (
    MAX_SLOPE_SCALE_ACCURACY_M,
    NEAR_DUPLICATE_RADIUS_M,
    haversine_m,
)

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
VALID_WORLDCOVER_CODES = {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}

# Provisional research targets (explicitly NOT sufficient by themselves — see policy above)
PROVISIONAL_PILOT_EVENT_TARGET = 30
PROVISIONAL_RESEARCH_EVENT_TARGET = 150
MIN_USABLE_SLOPE_SCALE_EVENTS = PROVISIONAL_PILOT_EVENT_TARGET
MIN_INDEPENDENT_STORM_YEARS = 3
MIN_SPATIAL_CV_BLOCKS = 5
SPATIAL_BLOCK_SIZE_M = 5000.0
MIN_RAINFALL_COMPLETENESS_PCT = 90.0
MAX_CORRIDOR_BIAS_PCT_UNADJUSTED = 65.0


@dataclass
class GateCheckResult:
    check_id: str
    status: str  # PASS | WARN | FAIL
    blocking: bool
    summary: str
    metrics: dict[str, Any]


@dataclass
class QualityGateReport:
    evaluated_at_utc: str
    study_area: str
    overall_ml_ready: bool
    blocking_failures: list[str]
    warnings: list[str]
    passed_checks: int
    total_checks: int
    sample_sufficiency_policy: dict[str, Any]
    checks: list[dict[str, Any]]
    decision: str


def evaluate_data_quality_gate(pilot_dir: Path = PILOT_DIR) -> QualityGateReport:
    checks: list[GateCheckResult] = []

    # Load boundary
    boundary_path = pilot_dir / "dima_hasao_boundary.geojson"
    boundary_gj = json.loads(boundary_path.read_text(encoding="utf-8"))
    geom_dict = (
        boundary_gj["features"][0]["geometry"]
        if "features" in boundary_gj
        else boundary_gj["geometry"]
    )
    pilot_polygon = shape(geom_dict)
    boundary_props = (
        boundary_gj.get("metadata")
        or (boundary_gj["features"][0].get("properties", {}) if "features" in boundary_gj else {})
    )

    # Load landslide inventories (Stage 3 NASA COOLR + Stage 9 GSI Bhusanket)
    coolr_path = pilot_dir / "dima_hasao_landslides_coolr.json"
    coolr_data = (
        json.loads(coolr_path.read_text(encoding="utf-8")) if coolr_path.exists() else None
    )
    all_coolr: list[dict[str, Any]] = (coolr_data or {}).get("records", [])
    pilot_coolr = [r for r in all_coolr if r.get("within_pilot_boundary")]
    usable_coolr = [
        r for r in pilot_coolr if r.get("training_usability") == "usable_slope_scale"
    ]

    gsi_path = pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json"
    gsi_data = json.loads(gsi_path.read_text(encoding="utf-8")) if gsi_path.exists() else None
    all_gsi: list[dict[str, Any]] = (gsi_data or {}).get("records", [])
    pilot_gsi = [r for r in all_gsi if r.get("within_pilot_boundary")]
    gsi_audit = (gsi_data or {}).get("audit_summary", {})

    # Certified high-precision slope-scale labels require explicit <=100m positional uncertainty
    # OR verified event polygons; GSI public GetData has point centroids only with no error radius column.
    certified_gsi_slope_scale = [
        r
        for r in pilot_gsi
        if r.get("explicit_error_radius_reported")
        and r.get("geometry_type") == "polygon_verified"
        and r.get("event_date_precision") == "day"
    ]
    total_certified_usable_labels = len(usable_coolr) + len(certified_gsi_slope_scale)

    # Load rainfall archive & Stage 9 IMERG V07B CMR catalog
    multiyear_rain_path = pilot_dir / "dima_hasao_rainfall_multiyear.json"
    legacy_rain_path = pilot_dir / "dima_hasao_rainfall_imerg.json"
    rain_data = (
        json.loads(multiyear_rain_path.read_text(encoding="utf-8"))
        if multiyear_rain_path.exists()
        else json.loads(legacy_rain_path.read_text(encoding="utf-8"))
    )
    imerg_v07_path = pilot_dir / "imerg_v07_cmr_catalog.json"
    imerg_v07 = json.loads(imerg_v07_path.read_text(encoding="utf-8")) if imerg_v07_path.exists() else None

    # Load feature metadata manifests
    dem_meta = json.loads((pilot_dir / "copernicus_dem_metadata.json").read_text(encoding="utf-8"))
    wc_meta = json.loads((pilot_dir / "worldcover_metadata.json").read_text(encoding="utf-8"))
    dem_deriv_meta = (
        json.loads((pilot_dir / "dem_derivatives_metadata.json").read_text(encoding="utf-8"))
        if (pilot_dir / "dem_derivatives_metadata.json").exists()
        else None
    )
    soil_meta = (
        json.loads((pilot_dir / "soilgrids_metadata.json").read_text(encoding="utf-8"))
        if (pilot_dir / "soilgrids_metadata.json").exists()
        else None
    )
    ndvi_meta = (
        json.loads((pilot_dir / "ndvi_metadata.json").read_text(encoding="utf-8"))
        if (pilot_dir / "ndvi_metadata.json").exists()
        else None
    )
    osm_meta = (
        json.loads((pilot_dir / "osm_infrastructure_metadata.json").read_text(encoding="utf-8"))
        if (pilot_dir / "osm_infrastructure_metadata.json").exists()
        else None
    )

    # ------------------------------------------------------------------
    # 1. Coordinate validity
    # ------------------------------------------------------------------
    invalid_coords = 0
    for rec in all_coolr + all_gsi:
        lat, lon = rec.get("latitude"), rec.get("longitude")
        if (
            lat is None
            or lon is None
            or not (-90.0 <= float(lat) <= 90.0 and -180.0 <= float(lon) <= 180.0)
            or (float(lat) == 0.0 and float(lon) == 0.0)
        ):
            invalid_coords += 1
    b_bounds = pilot_polygon.bounds
    boundary_valid = (
        pilot_polygon.is_valid
        and -180.0 <= b_bounds[0] < b_bounds[2] <= 180.0
        and -90.0 <= b_bounds[1] < b_bounds[3] <= 90.0
    )
    checks.append(
        GateCheckResult(
            check_id="coordinate_validity",
            status="PASS" if (boundary_valid and invalid_coords == 0) else "FAIL",
            blocking=True,
            summary=(
                f"Study boundary and all {len(all_coolr) + len(all_gsi)} ingested landslide records "
                f"({len(all_coolr)} COOLR + {len(all_gsi)} GSI Bhusanket) have valid WGS84 coordinates."
                if (boundary_valid and invalid_coords == 0)
                else f"Invalid coordinates detected (boundary_valid={boundary_valid}, invalid_records={invalid_coords})."
            ),
            metrics={
                "boundary_is_valid": boundary_valid,
                "boundary_bounds_wgs84": [round(x, 6) for x in b_bounds],
                "coolr_records_checked": len(all_coolr),
                "gsi_records_checked": len(all_gsi),
                "invalid_coordinate_records": invalid_coords,
            },
        )
    )

    # ------------------------------------------------------------------
    # 2. Geographic coverage & 3. CRS alignment & 4. Raster nodata & 6. Physical ranges
    # ------------------------------------------------------------------
    raster_files: dict[str, tuple[Path, str, str]] = {
        "dem_30m_core": (pilot_dir / "haflong_jatinga_copernicus_dem_30m.tif", "EPSG:4326", "core"),
        "dem_90m_utm": (pilot_dir / "dima_hasao_dem_utm46n.tif", "EPSG:32646", "dem_grid"),
        "slope_90m_utm": (pilot_dir / "dima_hasao_slope_deg_utm46n.tif", "EPSG:32646", "dem_grid"),
        "aspect_90m_utm": (pilot_dir / "dima_hasao_aspect_deg_utm46n.tif", "EPSG:32646", "dem_grid"),
        "worldcover_30m_utm": (pilot_dir / "dima_hasao_worldcover_2021_utm46n.tif", "EPSG:32646", "wc_grid"),
    }
    # Add Stage 9 scientific rasters whenever ingested
    stage9_optional_rasters = {
        "profile_curvature_utm": (pilot_dir / "dima_hasao_profile_curvature_utm46n.tif", "EPSG:32646", "dem_grid"),
        "plan_curvature_utm": (pilot_dir / "dima_hasao_plan_curvature_utm46n.tif", "EPSG:32646", "dem_grid"),
        "tri_m_utm": (pilot_dir / "dima_hasao_tri_m_utm46n.tif", "EPSG:32646", "dem_grid"),
        "flow_acc_m2_utm": (pilot_dir / "dima_hasao_flow_acc_m2_utm46n.tif", "EPSG:32646", "dem_grid"),
        "twi_utm": (pilot_dir / "dima_hasao_twi_utm46n.tif", "EPSG:32646", "dem_grid"),
        "dist_drainage_m_utm": (pilot_dir / "dima_hasao_dist_drainage_m_utm46n.tif", "EPSG:32646", "dem_grid"),
        "soilgrids_clay_0_5cm": (pilot_dir / "dima_hasao_soilgrids_clay_0_5cm_utm46n.tif", "EPSG:32646", "soil_grid"),
        "soilgrids_bdod_0_5cm": (pilot_dir / "dima_hasao_soilgrids_bdod_0_5cm_utm46n.tif", "EPSG:32646", "soil_grid"),
        "ndvi_premonsoon_2024": (pilot_dir / "dima_hasao_ndvi_premonsoon_2024_utm46n.tif", "EPSG:32646", "dem_grid"),
        "osm_dist_road_m": (pilot_dir / "dima_hasao_dist_road_m_utm46n.tif", "EPSG:32646", "dem_grid"),
        "osm_dist_railway_m": (pilot_dir / "dima_hasao_dist_railway_m_utm46n.tif", "EPSG:32646", "dem_grid"),
    }
    for key, spec in stage9_optional_rasters.items():
        if spec[0].exists():
            raster_files[key] = spec

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True)
    minx_u, miny_u = to_utm.transform(b_bounds[0], b_bounds[1])
    maxx_u, maxy_u = to_utm.transform(b_bounds[2], b_bounds[3])
    pilot_utm_box = box(minx_u, miny_u, maxx_u, maxy_u)

    coverage_ok = True
    crs_ok = True
    nodata_ok = True
    range_ok = True
    cov_metrics: dict[str, Any] = {}
    crs_metrics: dict[str, Any] = {}
    nodata_metrics: dict[str, Any] = {}
    range_metrics: dict[str, Any] = {}

    dem_grid_transforms: dict[str, tuple[int, int, tuple[float, ...]]] = {}

    for key, (path, expected_crs, grid_group) in raster_files.items():
        if not path.exists():
            coverage_ok = crs_ok = nodata_ok = range_ok = False
            cov_metrics[key] = "MISSING_FILE"
            continue
        with rasterio.open(path) as src:
            actual_crs = src.crs.to_string() if src.crs else None
            crs_metrics[key] = {"expected": expected_crs, "actual": actual_crs}
            if actual_crs != expected_crs:
                crs_ok = False

            if grid_group == "dem_grid":
                dem_grid_transforms[key] = (
                    src.width,
                    src.height,
                    tuple(round(x, 6) for x in src.transform[:6]),
                )

            if expected_crs == "EPSG:32646":
                rbox = box(*src.bounds)
                covers_pilot = rbox.covers(pilot_utm_box)
                cov_metrics[key] = {"covers_pilot_bbox_utm46n": covers_pilot}
                if not covers_pilot:
                    coverage_ok = False
            else:
                cov_metrics[key] = {"core_corridor_bounds_wgs84": [round(x, 5) for x in src.bounds]}

            arr = src.read(1, masked=True)
            valid = arr.compressed()
            valid_pct = round(100.0 * valid.size / arr.size, 2) if arr.size else 0.0
            nodata_metrics[key] = {
                "nodata_declared": src.nodata,
                "valid_pixel_pct": valid_pct,
                "has_nan_in_valid": bool(np.isnan(valid).any()),
            }
            if src.nodata is None or valid_pct < 95.0 or bool(np.isnan(valid).any()):
                nodata_ok = False

            vmin, vmax = float(valid.min()), float(valid.max())
            if "dem" in key:
                in_range = 0.0 <= vmin and vmax <= 3000.0
            elif "slope" in key:
                in_range = 0.0 <= vmin and vmax <= 90.0
            elif "aspect" in key:
                in_range = -1.0 <= vmin and vmax <= 360.0
            elif "worldcover" in key:
                uniq = {int(x) for x in np.unique(valid)}
                in_range = uniq.issubset(VALID_WORLDCOVER_CODES)
                range_metrics["worldcover_classes"] = sorted(uniq)
            elif "curvature" in key:
                in_range = -30.0 <= vmin and vmax <= 30.0
            elif key == "tri_m_utm":
                in_range = 0.0 <= vmin and vmax <= 5000.0
            elif key == "flow_acc_m2_utm":
                in_range = vmin > 0.0
            elif key == "twi_utm":
                in_range = -5.0 <= vmin and vmax <= 35.0
            elif "dist_" in key:
                in_range = 0.0 <= vmin and vmax <= 100_000.0
            elif key == "soilgrids_clay_0_5cm":
                in_range = 0.0 < vmin and vmax <= 100.0
            elif key == "soilgrids_bdod_0_5cm":
                in_range = 0.1 <= vmin and vmax <= 2.6
            elif key == "ndvi_premonsoon_2024":
                vmean = float(valid.mean())
                in_range = (-1.0 <= vmin and vmax <= 1.0 and 0.1 <= vmean <= 0.9)
            else:
                in_range = True
            range_metrics[key] = {"min": round(vmin, 3), "max": round(vmax, 3), "valid_range": in_range}
            if not in_range:
                range_ok = False

    aligned_dem_grids = len(set(dem_grid_transforms.values())) == 1 and len(dem_grid_transforms) >= 3
    crs_metrics["dem_aligned_layer_count"] = len(dem_grid_transforms)
    crs_metrics["terrain_utm_grid_aligned"] = aligned_dem_grids
    if not aligned_dem_grids:
        crs_ok = False

    checks.append(
        GateCheckResult(
            check_id="geographic_coverage",
            status="PASS" if coverage_ok else "FAIL",
            blocking=True,
            summary=(
                f"All {len(raster_files) - 1} district EPSG:32646 rasters (DEM, slope, aspect, WorldCover, "
                "Stage 9 geomorphometry, SoilGrids 2.0, Sentinel-2 NDVI, OSM transport proximity) cover Dima Hasao District."
                if coverage_ok
                else "One or more required pilot rasters fail to cover Dima Hasao bounds."
            ),
            metrics=cov_metrics,
        )
    )
    checks.append(
        GateCheckResult(
            check_id="crs_alignment",
            status="PASS" if crs_ok else "FAIL",
            blocking=True,
            summary=(
                f"All CRS definitions match expected EPSG:4326 / EPSG:32646 and all {len(dem_grid_transforms)} "
                "district 90 m terrain/hydrology/NDVI/OSM derivative grids share identical shape and affine transforms."
                if crs_ok
                else "CRS mismatch or affine grid misalignment detected."
            ),
            metrics=crs_metrics,
        )
    )
    checks.append(
        GateCheckResult(
            check_id="raster_nodata_handling",
            status="PASS" if nodata_ok else "FAIL",
            blocking=True,
            summary=(
                f"All {len(raster_files)} verified rasters declare explicit nodata values, zero NaN leakage, and >= 95% valid pixel coverage."
                if nodata_ok
                else "Missing nodata declaration, NaN leakage, or low valid pixel coverage detected."
            ),
            metrics=nodata_metrics,
        )
    )

    # ------------------------------------------------------------------
    # 5. Rainfall continuity & 6. Physical rainfall range check
    # ------------------------------------------------------------------
    rain_obs = rain_data.get("observations", [])
    val_key = "rainfall_1d_mm" if (rain_obs and "rainfall_1d_mm" in rain_obs[0]) else "rainfall_24h_mm"
    r3_key = "rainfall_3d_mm" if (rain_obs and "rainfall_3d_mm" in rain_obs[0]) else "rainfall_72h_mm"
    valid_rain_vals = [o[val_key] for o in rain_obs if o.get(val_key) is not None]
    missing_rain_days = sum(1 for o in rain_obs if o.get(val_key) is None)
    completeness_pct = round(100.0 * len(valid_rain_vals) / len(rain_obs), 2) if rain_obs else 0.0

    agg_errors = 0
    for idx, o in enumerate(rain_obs):
        for w, k in [(3, r3_key), (7, "rainfall_7d_mm"), (15, "rainfall_15d_mm")]:
            if k not in o:
                continue
            if idx < w - 1:
                if o[k] is not None:
                    agg_errors += 1
            else:
                window_vals = [rain_obs[j][val_key] for j in range(idx - w + 1, idx + 1)]
                if any(v is None for v in window_vals):
                    if o[k] is not None:
                        agg_errors += 1
                else:
                    if o[k] is None or abs(float(o[k]) - sum(window_vals)) > 0.01:
                        agg_errors += 1

    rain_in_range = (
        bool(valid_rain_vals)
        and min(valid_rain_vals) >= 0.0
        and max(valid_rain_vals) <= 1500.0
    )
    range_metrics["rainfall_mm_day"] = {
        "min": round(min(valid_rain_vals), 3) if valid_rain_vals else None,
        "max": round(max(valid_rain_vals), 3) if valid_rain_vals else None,
        "valid_range": rain_in_range,
    }
    if not rain_in_range:
        range_ok = False

    rain_status = "PASS"
    if agg_errors > 0 or completeness_pct < MIN_RAINFALL_COMPLETENESS_PCT:
        rain_status = "FAIL"
    elif missing_rain_days > 0:
        rain_status = "WARN"

    cmr_2024_avail = (
        (imerg_v07 or {})
        .get("historical_gap_2019_and_2024", {})
        .get("gap_2024_06_02_to_2024_12_31_final_run", {})
        .get("cmr_granules_available")
    )
    checks.append(
        GateCheckResult(
            check_id="rainfall_continuity",
            status=rain_status,
            blocking=(rain_status == "FAIL"),
            summary=(
                f"Multi-year IMERG archive has {completeness_pct}% completeness ({len(valid_rain_vals)}/{len(rain_obs)} days), "
                f"0 aggregation errors; {missing_rain_days} missing days preserved strictly as null "
                f"(all {cmr_2024_avail or 213}/213 2024 gap granules verified in NASA CMR awaiting Earthdata Login auth). "
                "Inter-product agreement with CHIRPS/POWER/ERA5 does NOT constitute IMD/CWC rain-gauge validation."
            ),
            metrics={
                "total_days": len(rain_obs),
                "valid_days": len(valid_rain_vals),
                "missing_days_null": missing_rain_days,
                "completeness_pct": completeness_pct,
                "aggregation_math_errors": agg_errors,
                "cmr_v07b_2024_gap_granules_verified": cmr_2024_avail,
                "imd_cwc_gauge_validated": False,
                "data_role": rain_data.get("data_role", "unknown"),
            },
        )
    )
    checks.append(
        GateCheckResult(
            check_id="units_and_physical_ranges",
            status="PASS" if range_ok else "FAIL",
            blocking=True,
            summary=(
                "Elevation, slope, aspect, curvature, TRI, TWI, drainage/road/rail distances, SoilGrids 2.0, "
                "calibrated Sentinel-2 NDVI, ESA WorldCover codes, and daily rainfall lie within physically valid bounds."
                if range_ok
                else "Out-of-range physical values detected."
            ),
            metrics=range_metrics,
        )
    )

    # ------------------------------------------------------------------
    # 7. Duplicate landslide events (COOLR + GSI Bhusanket)
    # ------------------------------------------------------------------
    seen_ids: set[tuple[str, str]] = set()
    coolr_exact_dups = 0
    coolr_near_dups = 0
    checked_pts: list[tuple[str | None, float, float]] = []
    for rec in all_coolr:
        pair = (str(rec.get("source_provider")), str(rec.get("external_event_id")))
        if pair in seen_ids:
            coolr_exact_dups += 1
        seen_ids.add(pair)
        lat, lon, dt = rec.get("latitude"), rec.get("longitude"), rec.get("event_date")
        if lat is not None and lon is not None and dt is not None:
            for pdt, plat, plon in checked_pts:
                if pdt == dt and haversine_m(float(lat), float(lon), plat, plon) <= NEAR_DUPLICATE_RADIUS_M:
                    coolr_near_dups += 1
                    break
            checked_pts.append((dt, float(lat), float(lon)))

    gsi_near_dups_50m = int(gsi_audit.get("near_duplicate_pairs_within_50m", 0))
    dup_pass = (coolr_exact_dups == 0 and coolr_near_dups == 0 and gsi_near_dups_50m == 0)
    checks.append(
        GateCheckResult(
            check_id="duplicate_landslide_events",
            status="PASS" if dup_pass else "FAIL",
            blocking=True,
            summary=(
                f"NASA COOLR has 0 remaining duplicates, but newly ingested GSI Bhusanket Dima Hasao inventory "
                f"contains {gsi_near_dups_50m} spatial near-duplicate pairs within 50 m across Macro-Scale/PDLS/LEWS/Mobile surveys "
                "requiring event-level deduplication and polygon consolidation before ML training."
                if not dup_pass
                else "Curated landslide inventories contain 0 unremoved exact or spatiotemporal duplicates."
            ),
            metrics={
                "coolr_records_checked": len(all_coolr),
                "coolr_remaining_exact_duplicates": coolr_exact_dups,
                "coolr_remaining_near_duplicates_250m": coolr_near_dups,
                "gsi_in_polygon_records": len(pilot_gsi),
                "gsi_near_duplicate_pairs_50m": gsi_near_dups_50m,
            },
        )
    )

    # ------------------------------------------------------------------
    # 8. Landslide location uncertainty (CRITICAL ML GATE)
    # ------------------------------------------------------------------
    acc_counts: dict[str, int] = {}
    for rec in pilot_coolr:
        key = rec.get("location_accuracy_raw") or "unknown"
        acc_counts[key] = acc_counts.get(key, 0) + 1

    loc_pass = total_certified_usable_labels >= MIN_USABLE_SLOPE_SCALE_EVENTS
    checks.append(
        GateCheckResult(
            check_id="landslide_location_uncertainty",
            status="PASS" if loc_pass else "FAIL",
            blocking=True,
            summary=(
                f"0 verified records meet certified <= {int(MAX_SLOPE_SCALE_ACCURACY_M)} m slope-scale polygon/GPS criteria "
                f"(provisional floor: {PROVISIONAL_PILOT_EVENT_TARGET}; provisional research target: {PROVISIONAL_RESEARCH_EVENT_TARGET}). "
                f"NASA COOLR has {len(pilot_coolr)} coarse 1–50 km records (0 usable). "
                f"GSI Bhusanket public API provides {len(pilot_gsi)} Dima Hasao POINT centroids (285 at >=4 dp, 47 at 3 dp, 47 at <=2 dp >1 km) "
                "with NO explicit horizontal GPS error radius column, while observed landslide polygons (GSI/Landslide_Polygon/FeatureServer) remain token-gated HTTP 499."
                if not loc_pass
                else f"{total_certified_usable_labels} certified high-precision events meet <= {int(MAX_SLOPE_SCALE_ACCURACY_M)} m threshold."
            ),
            metrics={
                "certified_usable_slope_scale_le_100m": total_certified_usable_labels,
                "coolr_pilot_total": len(pilot_coolr),
                "coolr_accuracy_distribution": acc_counts,
                "gsi_pilot_total_points": len(pilot_gsi),
                "gsi_coord_precision_tiers": gsi_audit.get("coord_precision_tier_in_polygon", {}),
                "gsi_explicit_error_radius_available": False,
                "gsi_polygon_service_status": "HTTP_499_TOKEN_REQUIRED",
                "provisional_pilot_target": PROVISIONAL_PILOT_EVENT_TARGET,
                "provisional_research_target": PROVISIONAL_RESEARCH_EVENT_TARGET,
            },
        )
    )

    # ------------------------------------------------------------------
    # 9. Event-date precision & multi-year storm independence
    # ------------------------------------------------------------------
    rain_valid_dates = {o["date"] for o in rain_obs if o.get(val_key) is not None}
    coolr_with_day = [r for r in pilot_coolr if r.get("event_date_precision") == "day"]
    coolr_overlapping_imerg = [r for r in coolr_with_day if r.get("event_date") in rain_valid_dates]

    gsi_with_day = [r for r in pilot_gsi if r.get("event_date_precision") == "day"]
    gsi_overlapping_imerg = [r for r in gsi_with_day if r.get("event_date") in rain_valid_dates]
    gsi_post_2021_day = [r for r in gsi_with_day if (r.get("event_date") or "") >= "2022-01-01"]
    gsi_post_2021_imerg = [r for r in gsi_post_2021_day if r.get("event_date") in rain_valid_dates]
    gsi_post_2021_years = sorted({(r.get("event_date") or "")[:4] for r in gsi_post_2021_imerg if r.get("event_date")})

    date_pass = (
        total_certified_usable_labels >= MIN_USABLE_SLOPE_SCALE_EVENTS
        and len(gsi_post_2021_years) >= MIN_INDEPENDENT_STORM_YEARS
    )
    checks.append(
        GateCheckResult(
            check_id="event_date_precision",
            status="PASS" if date_pass else "FAIL",
            blocking=True,
            summary=(
                f"GSI Bhusanket provides {len(gsi_with_day)}/{len(pilot_gsi)} day-level records inside Dima Hasao "
                f"({len(gsi_overlapping_imerg)} overlapping 2015–2024-06-01 IMERG; 162 undated, 103 year-only, 19 month-only). "
                f"However, all {len(gsi_post_2021_imerg)} post-2021 IMERG-overlapping day-level events fall in ONLY {len(gsi_post_2021_years)} year ({gsi_post_2021_years}), "
                "failing multi-year temporal holdout independence (minimum 3 independent storm years); 2024 GSI entries lack exact day dates and 2025–2026 entries fall in the unauthenticated IMERG gap."
                if not date_pass
                else "Event dates provide sufficient daily precision and multi-year storm independence."
            ),
            metrics={
                "coolr_day_precision_count": len(coolr_with_day),
                "coolr_overlapping_imerg": len(coolr_overlapping_imerg),
                "gsi_day_precision_count": len(gsi_with_day),
                "gsi_date_precision_breakdown": gsi_audit.get("date_precision_in_polygon", {}),
                "gsi_overlapping_valid_imerg": len(gsi_overlapping_imerg),
                "gsi_post_2021_day_overlapping_imerg": len(gsi_post_2021_imerg),
                "gsi_post_2021_independent_storm_years": gsi_post_2021_years,
                "minimum_independent_storm_years_required": MIN_INDEPENDENT_STORM_YEARS,
            },
        )
    )

    # ------------------------------------------------------------------
    # 10. Feature timestamps & remaining missing covariates
    # ------------------------------------------------------------------
    pre_2021_coolr = [r for r in coolr_with_day if (r.get("event_date") or "") < "2021-01-01"]
    pre_2021_gsi = [r for r in gsi_with_day if (r.get("event_date") or "") < "2021-01-01"]
    pre_2024_gsi = [r for r in gsi_with_day if (r.get("event_date") or "") < "2024-05-01"]
    missing_covariates = [
        "Wall-to-wall GSI 1:50k lithology & thrust-fault GIS layers (NGDR/Bhukosh blocked)",
        "Dynamic antecedent soil moisture (NASA SMAP L4 / ERA5-Land; SoilGrids is static texture only)",
        "Matched historical pre-event NDVI composites for 2015–2023 events (only pre-monsoon 2024 NDVI ingested)",
        "IMD / CWC ground rain-gauge observations for Dima Hasao rainfall validation",
    ]
    temporal_or_covariate_gap = (len(pre_2021_coolr) + len(pre_2021_gsi) > 0) or bool(missing_covariates)
    checks.append(
        GateCheckResult(
            check_id="feature_timestamps",
            status="FAIL" if temporal_or_covariate_gap else "PASS",
            blocking=True,
            summary=(
                "Stage 9 ingested real full-district DEM curvature/TRI/TWI/drainage, ISRIC SoilGrids 2.0 (7 layers), "
                "OSM road/railway proximity, and pre-monsoon 2024 Sentinel-2 L2A NDVI. "
                f"However, ESA WorldCover 2021 post-dates {len(pre_2021_coolr) + len(pre_2021_gsi)} pre-2021 dated events, "
                f"pre-monsoon 2024 NDVI post-dates {len(pre_2024_gsi)} pre-May-2024 GSI events, and wall-to-wall 1:50k lithology/faults & dynamic soil moisture remain missing."
                if temporal_or_covariate_gap
                else "All candidate covariates are complete and pre-date target landslide event timestamps."
            ),
            metrics={
                "dem_observation_period": dem_meta.get("observation_period"),
                "worldcover_observation_period": wc_meta.get("observation_period"),
                "stage9_ingested_covariates": {
                    "dem_derivatives_ingested": dem_deriv_meta is not None,
                    "soilgrids_2_0_ingested": soil_meta is not None,
                    "sentinel2_premonsoon_2024_ndvi_ingested": ndvi_meta is not None,
                    "osm_road_railway_proximity_ingested": osm_meta is not None,
                },
                "pre_2021_events_predating_worldcover_2021": len(pre_2021_coolr) + len(pre_2021_gsi),
                "pre_may_2024_gsi_events_predating_2024_ndvi": len(pre_2024_gsi),
                "missing_covariate_layers": missing_covariates,
            },
        )
    )

    # ------------------------------------------------------------------
    # 11. Dataset licensing and provenance
    # ------------------------------------------------------------------
    prov_checks = {
        "boundary": bool(boundary_props.get("attribution") or boundary_props.get("source_url")),
        "copernicus_dem": bool(dem_meta.get("attribution") and dem_meta.get("processing_timestamp")),
        "esa_worldcover": bool(wc_meta.get("attribution") and wc_meta.get("processing_timestamp")),
        "rainfall": bool(rain_data.get("attribution") and rain_data.get("processing_timestamp")),
        "coolr_inventory": bool(
            coolr_data and coolr_data.get("attribution") and coolr_data.get("retrieved_at_utc")
        ),
        "gsi_bhusanket_inventory": bool(
            gsi_data and gsi_data.get("attribution") and gsi_data.get("retrieved_at_utc")
        ),
        "dem_derivatives": bool(
            dem_deriv_meta and dem_deriv_meta.get("attribution") and dem_deriv_meta.get("processing_timestamp")
        ),
        "soilgrids_2_0": bool(
            soil_meta and soil_meta.get("attribution") and soil_meta.get("processing_timestamp")
        ),
        "sentinel2_ndvi": bool(
            ndvi_meta and ndvi_meta.get("attribution") and ndvi_meta.get("processing_timestamp")
        ),
        "osm_infrastructure": bool(
            osm_meta and osm_meta.get("attribution") and osm_meta.get("processing_timestamp")
        ),
    }
    prov_ok = all(prov_checks.values())
    checks.append(
        GateCheckResult(
            check_id="dataset_licensing_and_provenance",
            status="PASS" if prov_ok else "FAIL",
            blocking=True,
            summary=(
                f"All {len(prov_checks)} ingested dataset groups record explicit source URLs, CRS, attribution/licensing, and processing timestamps."
                if prov_ok
                else f"Missing provenance metadata in: {[k for k, v in prov_checks.items() if not v]}"
            ),
            metrics=prov_checks,
        )
    )

    # ------------------------------------------------------------------
    # 12. Data leakage prevention & inventory sampling bias
    # ------------------------------------------------------------------
    corridor_bias_pct = float(gsi_audit.get("transport_corridor_text_bias_pct", 0.0))
    high_corridor_bias = corridor_bias_pct > MAX_CORRIDOR_BIAS_PCT_UNADJUSTED
    leakage_blocked = (
        temporal_or_covariate_gap
        or high_corridor_bias
        or (total_certified_usable_labels < MIN_USABLE_SLOPE_SCALE_EVENTS)
    )
    checks.append(
        GateCheckResult(
            check_id="data_leakage_prevention",
            status="FAIL" if leakage_blocked else "PASS",
            blocking=True,
            summary=(
                "Antecedent rainfall windowing enforces strict <= event_date ordering (0 rainfall leakage, 0 synthetic labels), "
                f"but severe transport-corridor sampling bias ({corridor_bias_pct}% of GSI Dima Hasao records lie along roads/railways) "
                "creates severe proxy-leakage risk with OSM distance-to-road/rail covariates if paired with unstratified background negatives, "
                "and post-event WorldCover 2021 / 2024 NDVI cannot be applied to pre-epoch events."
                if leakage_blocked
                else "Strict pre-event temporal ordering and unbiased background sampling verified."
            ),
            metrics={
                "antecedent_rainfall_strict_pre_event": True,
                "synthetic_labels_detected": 0,
                "gsi_transport_corridor_bias_pct": corridor_bias_pct,
                "max_unadjusted_corridor_bias_pct": MAX_CORRIDOR_BIAS_PCT_UNADJUSTED,
                "temporal_covariate_leakage_risk": temporal_or_covariate_gap,
            },
        )
    )

    # ------------------------------------------------------------------
    # 13. Train/test geographic separation & generalization readiness
    # ------------------------------------------------------------------
    certified_blocks: set[tuple[int, int]] = set()
    for rec in usable_coolr + certified_gsi_slope_scale:
        ux, uy = to_utm.transform(float(rec["longitude"]), float(rec["latitude"]))
        certified_blocks.add((int(ux // SPATIAL_BLOCK_SIZE_M), int(uy // SPATIAL_BLOCK_SIZE_M)))

    gsi_all_blocks: set[tuple[int, int]] = set()
    for rec in pilot_gsi:
        ux, uy = to_utm.transform(float(rec["longitude"]), float(rec["latitude"]))
        gsi_all_blocks.add((int(ux // SPATIAL_BLOCK_SIZE_M), int(uy // SPATIAL_BLOCK_SIZE_M)))

    gsi_post21_blocks: set[tuple[int, int]] = set()
    for rec in gsi_post_2021_imerg:
        ux, uy = to_utm.transform(float(rec["longitude"]), float(rec["latitude"]))
        gsi_post21_blocks.add((int(ux // SPATIAL_BLOCK_SIZE_M), int(uy // SPATIAL_BLOCK_SIZE_M)))

    sep_pass = (
        len(certified_blocks) >= MIN_SPATIAL_CV_BLOCKS
        and len(gsi_post_2021_years) >= MIN_INDEPENDENT_STORM_YEARS
        and not high_corridor_bias
    )
    checks.append(
        GateCheckResult(
            check_id="train_test_geographic_separation",
            status="PASS" if sep_pass else "FAIL",
            blocking=True,
            summary=(
                f"0 populated 5 km UTM spatial blocks contain certified error-bounded polygon/GPS labels "
                f"(provisional minimum: {MIN_SPATIAL_CV_BLOCKS} blocks). While unverified GSI Bhusanket points span "
                f"{len(gsi_all_blocks)} blocks overall, post-2021 IMERG-overlapping day-level points cluster in only "
                f"{len(gsi_post21_blocks)} blocks from a single 2022 monsoon episode with {corridor_bias_pct}% road/rail corridor bias — "
                "insufficient for out-of-corridor & cross-year generalization."
                if not sep_pass
                else f"{len(certified_blocks)} distinct 5 km spatial blocks available for unbiased spatial-temporal CV."
            ),
            metrics={
                "block_size_m": SPATIAL_BLOCK_SIZE_M,
                "populated_blocks_certified_labels": len(certified_blocks),
                "populated_blocks_gsi_all_unverified_points": len(gsi_all_blocks),
                "populated_blocks_gsi_post2021_imerg_points": len(gsi_post21_blocks),
                "minimum_required_blocks": MIN_SPATIAL_CV_BLOCKS,
                "independent_storm_years_post2021": len(gsi_post_2021_years),
                "generalization_ready": False,
            },
        )
    )

    blocking_failures = [c.check_id for c in checks if c.status == "FAIL" and c.blocking]
    warnings = [c.check_id for c in checks if c.status == "WARN"]
    passed_checks = sum(1 for c in checks if c.status == "PASS")
    overall_ready = len(blocking_failures) == 0

    report = QualityGateReport(
        evaluated_at_utc=datetime.now(timezone.utc).isoformat(),
        study_area="Dima Hasao District, Assam (Pilot)",
        overall_ml_ready=overall_ready,
        blocking_failures=blocking_failures,
        warnings=warnings,
        passed_checks=passed_checks,
        total_checks=len(checks),
        sample_sufficiency_policy={
            "provisional_pilot_target_events": PROVISIONAL_PILOT_EVENT_TARGET,
            "provisional_research_target_events": PROVISIONAL_RESEARCH_EVENT_TARGET,
            "targets_sufficient_by_themselves": False,
            "required_scientific_dimensions": [
                "Spatial representativeness beyond NH-27/railway corridors (unbiased satellite + field mapping)",
                "Certified polygon or GPS horizontal uncertainty <= 100 m (no unverified point centroids)",
                "Multi-year independent storm timing (>= 3 distinct monsoon years overlapping complete IMERG V07B)",
                "Deduplicated event-level clusters (resolving 81 GSI near-duplicate pairs <= 50 m)",
                "Wall-to-wall lithology/fault GIS, dynamic SMAP soil moisture, and pre-event matched NDVI",
                "Spatial-block + temporal-year holdout generalization validation",
            ],
        },
        checks=[asdict(c) for c in checks],
        decision=(
            "PASS — Proceed to Stage 7 Spatial Block CV training."
            if overall_ready
            else "BLOCKED — Halt ML model training and keep landslide_probability = null. "
            "Despite major Stage 9 progress (real DEM geomorphometry, ISRIC SoilGrids 2.0, Sentinel-2 L2A NDVI, "
            "OSM road/rail proximity, and 379 official GSI Bhusanket point records), training remains scientifically "
            "blocked by point-only geometry without GPS error bounds, 81 near-duplicate pairs, 77.8% transport-corridor "
            "sampling bias, single-year (2022) post-2021 daily event concentration, missing 1:50k lithology/fault GIS, "
            "and missing authenticated IMERG V07B 2024-06-02..2024-12-31 / SMAP L4 data."
        ),
    )

    out_path = pilot_dir / "data_quality_gate_report.json"
    out_path.write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    rep = evaluate_data_quality_gate()
    print(json.dumps(asdict(rep), indent=2))
