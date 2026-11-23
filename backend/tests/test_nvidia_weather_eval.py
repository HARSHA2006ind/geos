"""
Task 5 & Task 6 Automated Verification Tests — NVIDIA Build / Earth2Studio Experimental Evaluation.

Verifies:
  1. Forecast validation catches out-of-range physical values and preserves None/null strictly.
  2. Experimental Dynamical.org NOAA GFS 0.25° Zarr v3 evaluation artifact contains real
     Dima Hasao forecast values, provenance, coordinates, units, and CPU-only benchmarks.
  3. Experimental NOAA GHCN-Daily verification audit preserves in-district 1955–1970 end-year
     reality and Silchar synoptic comparison caveats.
  4. Strict scientific isolation: experimental weather outputs NEVER alter the 13-check
     Data Quality Gate (`overall_ml_ready: false`) or `landslide_probability: null`.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.quality_gate import evaluate_data_quality_gate
from backend.experimental.nvidia_weather_eval.dynamical_gfs_eval import validate_forecast_series

EXPERIMENTAL_DIR = Path(__file__).resolve().parents[1] / "data" / "experimental"
PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"


def test_forecast_validator_preserves_nulls_and_flags_violations():
    sample = [
        {
            "lead_hours": 0,
            "precipitation_rate_mm_h": None,
            "temperature_2m_c": 21.5,
            "relative_humidity_2m_pct": 84.0,
            "precipitable_water_mm": 38.2,
        },
        {
            "lead_hours": 1,
            "precipitation_rate_mm_h": 2.4,
            "temperature_2m_c": 21.0,
            "relative_humidity_2m_pct": 88.0,
            "precipitable_water_mm": 40.1,
        },
    ]
    res = validate_forecast_series(sample)
    assert res["all_physical_bounds_valid"] is True
    assert res["null_counts"]["precipitation_rate_mm_h"] == 1
    assert res["valid_counts"]["precipitation_rate_mm_h"] == 1

    bad = [
        {
            "lead_hours": 1,
            "precipitation_rate_mm_h": -5.0,
            "temperature_2m_c": 99.0,
            "relative_humidity_2m_pct": 120.0,
            "precipitable_water_mm": 30.0,
        }
    ]
    res_bad = validate_forecast_series(bad)
    assert res_bad["all_physical_bounds_valid"] is False
    assert res_bad["range_violations"]["precipitation_rate_mm_h"] == 1
    assert res_bad["range_violations"]["temperature_2m_c"] == 1
    assert res_bad["range_violations"]["relative_humidity_2m_pct"] == 1


def test_experimental_dynamical_gfs_forecast_artifact_valid_and_isolated():
    gfs_path = EXPERIMENTAL_DIR / "dima_hasao_gfs_forecast_eval.json"
    assert gfs_path.exists(), "Run dynamical_gfs_eval.py before running tests"
    doc = json.loads(gfs_path.read_text(encoding="utf-8"))

    assert doc["data_role"] == "experimental_nwp_forecast_only_NOT_ground_observation"
    assert doc["discovery_provenance"]["authentication_required"] is False
    assert doc["performance_benchmark"]["gpu_required"] is False
    assert doc["validation"]["all_physical_bounds_valid"] is True
    assert doc["spatial_domain"]["resolution_deg"] == 0.25
    assert doc["spatial_domain"]["total_grid_cells"] >= 15
    assert doc["temporal_domain"]["forecast_horizon_hours"] == 72
    assert len(doc["hourly_forecast"]) >= 72
    # GFS convention: lead_hours == 0 has null accumulated flux
    lead0 = doc["hourly_forecast"][0]
    assert lead0["lead_hours"] == 0
    assert lead0["precipitation_rate_mm_h"] is None


def test_experimental_ghcn_verification_artifact_honest_caveats():
    ghcn_path = EXPERIMENTAL_DIR / "ghcn_silchar_verification_eval.json"
    assert ghcn_path.exists(), "Run ghcn_station_eval.py before running tests"
    doc = json.loads(ghcn_path.read_text(encoding="utf-8"))

    assert doc["data_role"] == "experimental_off_district_synoptic_verification_only"
    assert doc["in_district_dima_hasao_ghcn_audit"]["stations_found_inside_polygon"] == 4
    assert doc["in_district_dima_hasao_ghcn_audit"]["active_post_1970_stations_inside_polygon"] == 0
    assert doc["nearest_active_synoptic_station"]["station_id"] == "IN003010600"
    assert doc["comparison_with_dima_hasao_imerg_2015_2024"]["overlapping_valid_days"] >= 900
    assert doc["performance_benchmark"]["gpu_required"] is False


def test_scientific_integrity_preserved_quality_gate_and_null_probability():
    rep = evaluate_data_quality_gate(PILOT_DIR)
    assert rep.overall_ml_ready is False
    assert len(rep.blocking_failures) >= 6

    client = TestClient(create_app())
    r_pt = client.get("/api/v1/environment/point?lat=25.1645&lon=93.0176")
    assert r_pt.status_code == 200
    body = r_pt.json()
    assert body["missing_data_indicators"]["landslide_ml_probability"] is True
    assert body["within_pilot_boundary"] is True
