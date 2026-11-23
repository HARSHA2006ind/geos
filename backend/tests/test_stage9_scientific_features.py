"""
Stage 9 Automated Scientific & Engineering Verification Tests.

Covers:
  - Priority 2: GSI Bhusanket public inventory integrity, strict date parser, bias audit,
    and strict separation of NLSM 10K susceptibility maps from observed event records.
  - Priority 3: NASA IMERG V07B/V07C CMR catalog completeness, separation of 2024 historical
    gap vs 2025-2026 current monitoring, and HDF5 NetCDF4 extraction with strict null fill-value handling.
  - Priority 4: Real full-district DEM derivatives, ISRIC SoilGrids 2.0, calibrated Sentinel-2 L2A
    pre-monsoon 2024 NDVI, OSM road/railway proximity rasters, and spatially explicit quality inventory.
  - Priority 5: Non-weakened 13-check Data Quality Gate, provisional-target policy, ML training block,
    and Stage 9 FastAPI read-only endpoints.
"""
from __future__ import annotations

import json
from pathlib import Path

import h5py
import numpy as np
import rasterio
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend.app.main import create_app
from backend.app.quality_gate import evaluate_data_quality_gate
from backend.ingestion.fetch_gsi_bhusanket_inventory import parse_gsi_event_date
from backend.ingestion.fetch_imerg_v07_earthdata import extract_dima_hasao_from_imerg_nc4
import pytest
from backend.ml.pipeline import DataQualityGateBlockedError, run_ml_training_pipeline

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"


def test_gsi_bhusanket_date_parser_never_fabricates_precision():
    assert parse_gsi_event_date("31st May 2025", None) == ("2025-05-31", "day")
    assert parse_gsi_event_date("03 June 2017", None) == ("2017-06-03", "day")
    assert parse_gsi_event_date("May 2022", None) == ("2022-05", "month")
    assert parse_gsi_event_date("2016", None) == ("2016", "year")
    assert parse_gsi_event_date("Old reactivated slide", None) == (None, "unknown")
    assert parse_gsi_event_date("NULL", None) == (None, "unknown")


def test_gsi_bhusanket_ingested_inventory_and_segregated_nlsm_maps():
    gsi_path = PILOT_DIR / "dima_hasao_landslides_gsi_bhusanket.json"
    assert gsi_path.exists()
    doc = json.loads(gsi_path.read_text(encoding="utf-8"))
    audit = doc["audit_summary"]

    assert audit["curated_unique_records"] >= 350
    assert audit["within_dima_hasao_polygon"] >= 300
    assert audit["invalid_coordinates"] == 0
    assert audit["day_level_dates_in_polygon"] >= 80
    assert audit["transport_corridor_text_bias_pct"] > 50.0
    assert audit["near_duplicate_pairs_within_50m"] > 0

    # NLSM 10K susceptibility maps are strictly separated from observed event records
    nlsm_maps = doc["gsi_dima_hasao_nlsm_10k_susceptibility_maps_separate_from_events"]
    assert isinstance(nlsm_maps, list) and len(nlsm_maps) >= 3
    for rec in doc["records"]:
        assert rec["explicit_error_radius_reported"] is False
        assert rec["geometry_type"] == "point_only_polygons_token_gated"


def test_imerg_v07_cmr_catalog_and_hdf5_null_handling(tmp_path: Path):
    cat_path = PILOT_DIR / "imerg_v07_cmr_catalog.json"
    assert cat_path.exists()
    cat = json.loads(cat_path.read_text(encoding="utf-8"))

    gap24 = cat["historical_gap_2019_and_2024"]["gap_2024_06_02_to_2024_12_31_final_run"]
    assert gap24["expected_days"] == 213
    assert gap24["cmr_granules_available"] == 213
    assert gap24["cmr_coverage_pct"] == 100.0

    mon = cat["current_monitoring_2025_2026_separate_dataset"]
    assert mon["dataset_role"] == "current_monitoring_only_strictly_separate_from_historical_training"
    assert mon["GPM_3IMERGDF_v07_final"]["cmr_granules_available"] >= 200
    assert mon["GPM_3IMERGDL_v07_late"]["cmr_granules_available"] >= 600
    assert mon["GPM_3IMERGDE_v07_early"]["cmr_granules_available"] >= 600

    # Unit-test HDF5 extraction on a synthetic local NetCDF4/HDF5 fixture verifying strict fill-value masking
    fixture_nc4 = tmp_path / "test_imerg.nc4"
    poly = box(92.6, 25.0, 93.4, 25.8)
    with h5py.File(fixture_nc4, "w") as hf:
        grp = hf.create_group("Grid")
        lats = np.array([25.05, 25.35, 25.65], dtype=np.float64)
        lons = np.array([92.75, 93.05, 93.35], dtype=np.float64)
        grp.create_dataset("lat", data=lats)
        grp.create_dataset("lon", data=lons)
        precip = np.full((1, 3, 3), -9999.9, dtype=np.float32)
        ds = grp.create_dataset("precipitation", data=precip)
        ds.attrs["_FillValue"] = np.float32(-9999.9)
    res_missing = extract_dima_hasao_from_imerg_nc4(fixture_nc4, poly)
    assert res_missing["rainfall_1d_mm"] is None
    assert res_missing["quality_flag"] == "MISSING_INSUFFICIENT_VALID_CELLS"

    # Now test valid positive cells
    fixture_ok = tmp_path / "test_imerg_ok.nc4"
    with h5py.File(fixture_ok, "w") as hf:
        grp = hf.create_group("Grid")
        grp.create_dataset("lat", data=np.array([25.05, 25.35, 25.65], dtype=np.float64))
        grp.create_dataset("lon", data=np.array([92.75, 93.05, 93.35], dtype=np.float64))
        precip = np.full((1, 3, 3), 42.5, dtype=np.float32)
        ds = grp.create_dataset("precipitation", data=precip)
        ds.attrs["_FillValue"] = np.float32(-9999.9)
    res_ok = extract_dima_hasao_from_imerg_nc4(fixture_ok, poly)
    assert res_ok["rainfall_1d_mm"] == 42.5
    assert res_ok["quality_flag"] == "VALID_FULL"


def test_stage9_scientific_rasters_aligned_and_physically_valid():
    dem_path = PILOT_DIR / "dima_hasao_dem_utm46n.tif"
    with rasterio.open(dem_path) as ref:
        ref_shape = (ref.height, ref.width)
        ref_transform = ref.transform
        ref_crs = ref.crs.to_string()

    aligned_layers = [
        "dima_hasao_profile_curvature_utm46n.tif",
        "dima_hasao_plan_curvature_utm46n.tif",
        "dima_hasao_tri_m_utm46n.tif",
        "dima_hasao_flow_acc_m2_utm46n.tif",
        "dima_hasao_twi_utm46n.tif",
        "dima_hasao_dist_drainage_m_utm46n.tif",
        "dima_hasao_ndvi_premonsoon_2024_utm46n.tif",
        "dima_hasao_dist_road_m_utm46n.tif",
        "dima_hasao_dist_railway_m_utm46n.tif",
    ]
    for fname in aligned_layers:
        p = PILOT_DIR / fname
        assert p.exists(), f"Missing Stage 9 raster {fname}"
        with rasterio.open(p) as src:
            assert src.crs.to_string() == ref_crs
            assert (src.height, src.width) == ref_shape
            assert tuple(round(x, 5) for x in src.transform[:6]) == tuple(
                round(x, 5) for x in ref_transform[:6]
            )
            arr = src.read(1, masked=True).compressed()
            assert arr.size > 0 and not np.isnan(arr).any()

    # Verify Sentinel-2 NDVI is calibrated (no Collection-1 double-offset saturation)
    with rasterio.open(PILOT_DIR / "dima_hasao_ndvi_premonsoon_2024_utm46n.tif") as src:
        ndvi = src.read(1, masked=True).compressed()
        assert -1.0 <= float(ndvi.min()) and float(ndvi.max()) <= 1.0
        assert 0.4 <= float(ndvi.mean()) <= 0.85

    # Verify ISRIC SoilGrids texture mass balance (~100%) and valid bulk density
    soil_meta = json.loads((PILOT_DIR / "soilgrids_metadata.json").read_text(encoding="utf-8"))
    means = {l["layer_id"]: l["mean"] for l in soil_meta["layers"]}
    texture_sum = means["clay_0_5cm"] + means["sand_0_5cm"] + means["silt_0_5cm"]
    assert 98.0 <= texture_sum <= 102.0
    bdod_layer = next(l for l in soil_meta["layers"] if l["layer_id"] == "bdod_0_5cm")
    assert 0.5 <= bdod_layer["min"] <= bdod_layer["max"] <= 2.2


def test_stage9_quality_gate_remains_strict_and_api_endpoints_work():
    rep = evaluate_data_quality_gate(PILOT_DIR)
    assert rep.overall_ml_ready is False
    assert rep.sample_sufficiency_policy["targets_sufficient_by_themselves"] is False
    assert "landslide_location_uncertainty" in rep.blocking_failures
    assert "data_leakage_prevention" in rep.blocking_failures
    assert "train_test_geographic_separation" in rep.blocking_failures
    assert "duplicate_landslide_events" in rep.blocking_failures

    with pytest.raises(DataQualityGateBlockedError):
        run_ml_training_pipeline(PILOT_DIR)

    client = TestClient(create_app())
    r_feat = client.get("/api/v1/features/quality")
    assert r_feat.status_code == 200
    assert r_feat.json()["ingested_layer_groups_count"] >= 10

    r_cat = client.get("/api/v1/rainfall/imerg-v07/catalog")
    assert r_cat.status_code == 200
    assert r_cat.json()["historical_gap_2019_and_2024"]["gap_2024_06_02_to_2024_12_31_final_run"]["cmr_granules_available"] == 213

    r_gsi = client.get("/api/v1/landslides/gsi-bhusanket?pilot_only=true")
    assert r_gsi.status_code == 200
    assert len(r_gsi.json()["records"]) >= 300
