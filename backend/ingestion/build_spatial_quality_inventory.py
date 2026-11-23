"""
Stage 9 Priority 4E — Spatially Explicit Scientific Data Quality Inventory Builder.

Consolidates all verified Dima Hasao environmental rasters, vectors, time series, and
landslide inventories into `backend/data/pilot/spatial_data_quality_inventory.json`.
Records per-layer provenance, CRS, resolution, nodata %, grid alignment, temporal validity,
known uncertainties, and explicitly catalogs remaining missing covariates.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from pyproj import Transformer
from shapely.geometry import box, shape

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"


def _inspect_raster(path: Path, pilot_utm_box: Any) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "file": path.name}
    with rasterio.open(path) as src:
        arr = src.read(1, masked=True)
        valid = arr.compressed()
        valid_pct = round(100.0 * valid.size / arr.size, 2) if arr.size else 0.0
        crs_str = src.crs.to_string() if src.crs else None
        covers_pilot = bool(box(*src.bounds).covers(pilot_utm_box)) if crs_str == "EPSG:32646" else None
        return {
            "exists": True,
            "file": path.name,
            "file_bytes": path.stat().st_size,
            "crs": crs_str,
            "width": src.width,
            "height": src.height,
            "pixel_size_m": [round(abs(float(src.transform.a)), 3), round(abs(float(src.transform.e)), 3)],
            "nodata": src.nodata,
            "valid_pixel_pct": valid_pct,
            "has_nan_in_valid": bool(np.isnan(valid).any()),
            "covers_dima_hasao_utm46n_bbox": covers_pilot,
            "min": round(float(valid.min()), 4) if valid.size else None,
            "max": round(float(valid.max()), 4) if valid.size else None,
            "mean": round(float(valid.mean()), 4) if valid.size else None,
        }


def build_spatial_quality_inventory(pilot_dir: Path = PILOT_DIR) -> dict[str, Any]:
    boundary_gj = json.loads((pilot_dir / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
    geom = boundary_gj["features"][0]["geometry"] if "features" in boundary_gj else boundary_gj["geometry"]
    poly = shape(geom)
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True)
    bminx, bminy, bmaxx, bmaxy = poly.bounds
    u1x, u1y = to_utm.transform(bminx, bminy)
    u2x, u2y = to_utm.transform(bmaxx, bmaxy)
    pilot_utm_box = box(min(u1x, u2x), min(u1y, u2y), max(u1x, u2x), max(u1y, u2y))

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
    gsi_meta = (
        json.loads((pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json").read_text(encoding="utf-8"))
        if (pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json").exists()
        else None
    )
    coolr_meta = (
        json.loads((pilot_dir / "dima_hasao_landslides_coolr.json").read_text(encoding="utf-8"))
        if (pilot_dir / "dima_hasao_landslides_coolr.json").exists()
        else None
    )
    imerg_catalog = (
        json.loads((pilot_dir / "imerg_v07_cmr_catalog.json").read_text(encoding="utf-8"))
        if (pilot_dir / "imerg_v07_cmr_catalog.json").exists()
        else None
    )

    layers: list[dict[str, Any]] = [
        {
            "layer_id": "copernicus_dem_90m_utm",
            "category": "topography",
            "status": "VERIFIED_INGESTED",
            "provider": "ESA / Copernicus DEM GLO-30 (AWS Public Bucket)",
            "license": "Copernicus DEM Licence (Open, attribution required)",
            "temporal_epoch": dem_meta.get("observation_period"),
            "temporal_validity": "Static topographic baseline (2011–2015); valid pre-event conditioning factor.",
            "uncertainty": "Vertical accuracy < 4 m LE90; 90 m district grid smooths narrow sub-50 m road cuts.",
            "raster_audit": _inspect_raster(pilot_dir / "dima_hasao_dem_utm46n.tif", pilot_utm_box),
        },
        {
            "layer_id": "copernicus_slope_aspect_90m_utm",
            "category": "topography",
            "status": "VERIFIED_INGESTED",
            "provider": "Derived from Copernicus DEM GLO-30",
            "license": "Copernicus DEM Licence",
            "temporal_epoch": dem_meta.get("observation_period"),
            "temporal_validity": "Static topographic baseline.",
            "uncertainty": "Horn 3x3 gradient at 90 m underestimates steep vertical cut-slopes (>55 deg) along NH-27.",
            "raster_audit": {
                "slope_deg": _inspect_raster(pilot_dir / "dima_hasao_slope_deg_utm46n.tif", pilot_utm_box),
                "aspect_deg": _inspect_raster(pilot_dir / "dima_hasao_aspect_deg_utm46n.tif", pilot_utm_box),
            },
        },
        {
            "layer_id": "dem_geomorphometric_hydrological_derivatives",
            "category": "topography_and_hydrology",
            "status": "VERIFIED_INGESTED" if dem_deriv_meta else "MISSING",
            "provider": "Derived from Copernicus DEM GLO-30 (Zevenbergen-Thorne, Riley TRI, D8 TWI/Drainage)",
            "license": "Copernicus DEM Licence",
            "temporal_epoch": dem_meta.get("observation_period"),
            "temporal_validity": "Static topographic/hydrological conditioning factors; aligned identically to DEM UTM46N grid.",
            "uncertainty": (dem_deriv_meta or {}).get("uncertainty_and_limitations"),
            "raster_audit": {
                "profile_curvature": _inspect_raster(pilot_dir / "dima_hasao_profile_curvature_utm46n.tif", pilot_utm_box),
                "plan_curvature": _inspect_raster(pilot_dir / "dima_hasao_plan_curvature_utm46n.tif", pilot_utm_box),
                "tri_m": _inspect_raster(pilot_dir / "dima_hasao_tri_m_utm46n.tif", pilot_utm_box),
                "flow_accumulation_m2": _inspect_raster(pilot_dir / "dima_hasao_flow_acc_m2_utm46n.tif", pilot_utm_box),
                "twi": _inspect_raster(pilot_dir / "dima_hasao_twi_utm46n.tif", pilot_utm_box),
                "distance_to_drainage_m": _inspect_raster(pilot_dir / "dima_hasao_dist_drainage_m_utm46n.tif", pilot_utm_box),
            },
        },
        {
            "layer_id": "isric_soilgrids_2.0_250m",
            "category": "pedology_and_soil",
            "status": "VERIFIED_INGESTED" if soil_meta else "MISSING",
            "provider": "ISRIC — World Soil Information (SoilGrids 2.0 WCS 2.0)",
            "license": (soil_meta or {}).get("license"),
            "temporal_epoch": (soil_meta or {}).get("observation_period"),
            "temporal_validity": (soil_meta or {}).get("temporal_validity"),
            "uncertainty": (soil_meta or {}).get("uncertainty_and_limitations"),
            "raster_audit": {
                l["layer_id"]: _inspect_raster(pilot_dir / l["file"], pilot_utm_box)
                for l in (soil_meta or {}).get("layers", [])
            },
        },
        {
            "layer_id": "esa_worldcover_2021_30m",
            "category": "land_cover",
            "status": "VERIFIED_INGESTED",
            "provider": "ESA WorldCover 2021 v200",
            "license": "CC-BY 4.0",
            "temporal_epoch": wc_meta.get("observation_period"),
            "temporal_validity": (
                "Epoch 2021 ONLY. Valid pre-event covariate for 2022–2026 landslides; "
                "POST-DATES 2007–2020 historical landslides (temporal leakage if applied to pre-2021 events)."
            ),
            "uncertainty": wc_meta.get("uncertainty_and_limitations"),
            "raster_audit": _inspect_raster(pilot_dir / "dima_hasao_worldcover_2021_utm46n.tif", pilot_utm_box),
        },
        {
            "layer_id": "sentinel2_l2a_premonsoon_2024_ndvi",
            "category": "vegetation_dynamic",
            "status": "VERIFIED_INGESTED" if ndvi_meta else "MISSING",
            "provider": "Copernicus Sentinel-2 L2A via Element84 Earth Search STAC",
            "license": (ndvi_meta or {}).get("license"),
            "temporal_epoch": (ndvi_meta or {}).get("observation_period"),
            "temporal_validity": (ndvi_meta or {}).get("temporal_validity"),
            "uncertainty": (
                "Cloud-masked via ESA SCL (classes 4,5,6,7) median composite across "
                f"{(ndvi_meta or {}).get('scenes_composited_count', 0)} scenes; valid ONLY as pre-event NDVI "
                "for post-April 2024 landslides (must fetch matched pre-event years for 2015–2023 events)."
            ),
            "raster_audit": {
                "ndvi_median": _inspect_raster(pilot_dir / "dima_hasao_ndvi_premonsoon_2024_utm46n.tif", pilot_utm_box),
                "qa_clear_obs_count": _inspect_raster(pilot_dir / "dima_hasao_ndvi_qa_clear_obs_count_utm46n.tif", pilot_utm_box),
            },
        },
        {
            "layer_id": "osm_road_railway_proximity",
            "category": "anthropogenic_exposure_and_slope_cuts",
            "status": "VERIFIED_INGESTED" if osm_meta else "MISSING",
            "provider": "OpenStreetMap via Overpass API",
            "license": (osm_meta or {}).get("license"),
            "temporal_epoch": (osm_meta or {}).get("observation_period"),
            "temporal_validity": (osm_meta or {}).get("temporal_validity"),
            "uncertainty": (
                "Community-mapped transport network (2,212 road ways, 392 railway ways). "
                "Minor unpaved village tracks or recent NH-27 realignment detours may have lag; "
                "CAUTION: strong collinearity with GSI road-corridor reporting bias (77.8% of GSI records mention road/rail)."
            ),
            "raster_audit": {
                "distance_to_road_m": _inspect_raster(pilot_dir / "dima_hasao_dist_road_m_utm46n.tif", pilot_utm_box),
                "distance_to_railway_m": _inspect_raster(pilot_dir / "dima_hasao_dist_railway_m_utm46n.tif", pilot_utm_box),
            },
        },
        {
            "layer_id": "nasa_gpm_imerg_multiyear_rainfall",
            "category": "precipitation_trigger",
            "status": "PARTIAL_EARTHDATA_AUTH_REQUIRED_FOR_2024_GAP",
            "provider": "NASA GPM IMERG (ClimateSERV 2015–2024-06-01; GES DISC V07B/V07C CMR cataloged)",
            "license": "NASA Open Data (Earthdata Login required for GES DISC .nc4 granules)",
            "temporal_epoch": "2015-01-01 to 2024-06-01 ingested (3,439/3,653 days = 94.14%); 2024-06-02..2024-12-31 (213 days) & 2025–2026 cataloged in CMR",
            "temporal_validity": "District-averaged 0.1 deg (~11 km) daily precipitation; strict null propagation on missing days.",
            "uncertainty": (
                "Stage 4 CHIRPS/POWER/ERA5 benchmarks measure inter-product agreement ONLY, NOT gauge-validated accuracy. "
                "Independent IMD/CWC rain gauges inside Dima Hasao are required for ground-truth validation."
            ),
            "imerg_v07_cmr_summary": {
                "gap_2024_final_granules_in_cmr": (imerg_catalog or {})
                .get("historical_gap_2019_and_2024", {})
                .get("gap_2024_06_02_to_2024_12_31_final_run", {})
                .get("cmr_granules_available"),
                "monitoring_2025_2026_late_in_cmr": (imerg_catalog or {})
                .get("current_monitoring_2025_2026_separate_dataset", {})
                .get("GPM_3IMERGDL_v07_late", {})
                .get("cmr_granules_available"),
                "ges_disc_auth_status": (imerg_catalog or {}).get("download_execution", {}).get("status"),
            },
        },
        {
            "layer_id": "gsi_bhusanket_public_landslide_inventory",
            "category": "landslide_inventory_ground_truth",
            "status": "VERIFIED_INGESTED_WITH_BIAS_AND_POLYGON_CAVEATS" if gsi_meta else "MISSING",
            "provider": "Geological Survey of India (GSI) — Bhusanket Public Portal",
            "license": (gsi_meta or {}).get("license_and_terms"),
            "temporal_epoch": "1998–2026 (including May 2022 & May 2024 events)",
            "temporal_validity": "Mixed: 95 exact day-level dates, 19 month-only, 103 year-only, 162 undated inside Dima Hasao polygon.",
            "uncertainty": (
                "Point centroids ONLY (GSI/Landslide_Polygon/FeatureServer is HTTP 499 Token Required); "
                "no explicit horizontal GPS error radius column; 81 near-duplicate pairs <= 50 m; "
                "77.8% transport-corridor sampling bias."
            ),
            "inventory_audit": (gsi_meta or {}).get("audit_summary"),
        },
        {
            "layer_id": "nasa_coolr_landslide_inventory",
            "category": "landslide_inventory_contextual",
            "status": "VERIFIED_INGESTED_CONTEXTUAL_ONLY" if coolr_meta else "MISSING",
            "provider": "NASA Cooperative Open Online Landslide Repository (COOLR)",
            "license": "NASA Open Data / Public Domain",
            "temporal_epoch": "2007–2018 inside Dima Hasao (19 records)",
            "temporal_validity": "Contextual historical reference ONLY (0 records <= 100 m positional precision; all 1–50 km or unknown).",
            "uncertainty": "Coarse 1–50 km geocoding uncertainty; unusable for 30 m / 90 m slope-scale labels.",
        },
    ]

    missing_scientific_layers = [
        {
            "layer_id": "gsi_1_50k_lithology_and_structural_faults_gis",
            "status": "MISSING_PORTAL_BLOCKED",
            "impact": "Critical conditioning covariate: Barail/Disang/Surma shale-sandstone contacts and Halflong/Disang thrust fault proximity cannot be sampled wall-to-wall across non-landslide slopes.",
            "access_path": "Requires GSI NGDR (geodataindia.gov.in) / Bhukosh registration or formal institutional request to GSI NER Shillong.",
        },
        {
            "layer_id": "gsi_observed_landslide_polygons_and_nrsc_event_polygons",
            "status": "MISSING_TOKEN_GATED_499",
            "impact": "GSI Bhusanket public GetData gives point centroids only; exact initiation scar vs runout polygons require authorized GSI FeatureServer token or NRSC/NESAC multi-temporal satellite inventory.",
            "access_path": "Formal data request to GSI NLFC / NRSC Bhuvan / NESAC Umiam (draft included in GEOS_GSI_ACCESS_FINDINGS.md).",
        },
        {
            "layer_id": "nasa_imerg_v07b_2024_gap_and_imd_gauge_validation",
            "status": "MISSING_CREDENTIALS_AND_GAUGES",
            "impact": "2024-06-02..2024-12-31 IMERG Final Run requires free NASA Earthdata Login token; ground-truth rainfall error requires IMD/CWC daily station gauges in Dima Hasao.",
            "access_path": "Run fetch_imerg_v07_earthdata.py with EARTHDATA_TOKEN; request IMD Guwahati / CWC Haflong gauge series.",
        },
        {
            "layer_id": "multi_year_pre_event_ndvi_2015_2023",
            "status": "PARTIAL_2024_ONLY",
            "impact": "Pre-monsoon 2024 Sentinel-2 NDVI is ingested for post-April 2024 events, but historical 2015–2023 events require matched pre-event annual dry-season NDVI composites to prevent post-event vegetation leakage.",
            "access_path": "Extend fetch_preevent_ndvi.py over 2016–2023 pre-monsoon Sentinel-2 L2A / Landsat C2 L2 windows once polygon inventory dates are finalized.",
        },
        {
            "layer_id": "dynamic_soil_moisture_smap_l4",
            "status": "MISSING_EARTHDATA_AUTH",
            "impact": "ISRIC SoilGrids provides static soil texture/bulk density ONLY; antecedent pore-water preconditioning requires NASA SMAP L4 (9 km) or ERA5-Land volumetric soil water.",
            "access_path": "NASA Earthdata Login (`SPL4SMGP`) once EARTHDATA_TOKEN is configured.",
        },
    ]

    inventory = {
        "schema_version": "geos-spatial-quality-inventory-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_area": "Dima Hasao District, Assam, India (Pilot)",
        "canonical_metric_crs": "EPSG:32646",
        "ingested_layer_groups_count": len(layers),
        "missing_critical_layer_groups_count": len(missing_scientific_layers),
        "ingested_layers": layers,
        "missing_scientific_layers": missing_scientific_layers,
    }

    out_path = pilot_dir / "spatial_data_quality_inventory.json"
    out_path.write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    return inventory


if __name__ == "__main__":
    inv = build_spatial_quality_inventory()
    print(
        json.dumps(
            {
                "ingested_layer_groups_count": inv["ingested_layer_groups_count"],
                "missing_critical_layer_groups_count": inv["missing_critical_layer_groups_count"],
                "statuses": {l["layer_id"]: l["status"] for l in inv["ingested_layers"]},
            },
            indent=2,
        )
    )
