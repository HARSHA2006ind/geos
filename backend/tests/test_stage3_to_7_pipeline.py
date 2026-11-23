"""
Automated tests for GEOS 2.0 Stages 3–7:
  - Stage 3: NASA COOLR deduplication, polygon filtering, uncertainty classification, DB persistence
  - Stage 4: Multi-year rainfall 1d/3d/7d/15d antecedent math & strict null preservation
  - Stage 5: 13-check automated Scientific Data Quality Gate
  - Stage 6 & 7: Feature extraction (curvature, TRI, sin/cos aspect) & hard ML gate blocking
  - FastAPI endpoints: /api/v1/landslides/coolr, /api/v1/environment/rainfall/multiyear, /api/v1/quality-gate
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from backend.app.main import app
from backend.app.quality_gate import evaluate_data_quality_gate
from backend.ingestion.fetch_coolr_landslides import (
    deduplicate_and_classify_records,
    parse_accuracy_m,
    store_landslides_to_db,
)
from backend.ingestion.fetch_rainfall_multiyear import (
    compare_precipitation_series,
    compute_antecedent_series,
)
from backend.ml.pipeline import (
    DataQualityGateBlockedError,
    compute_curvature_and_tri,
    extract_point_features,
    run_ml_training_pipeline,
)

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
client = TestClient(app)


def test_coolr_deduplication_and_uncertainty_classification():
    pilot_poly = box(92.5, 25.0, 93.5, 25.8)
    ts_2017 = 1491264000000  # 2017-04-04T00:00:00Z
    raw = [
        (
            "NASA_COOLR_Reports_Points",
            {
                "attributes": {
                    "event_id": 1001,
                    "event_date": ts_2017,
                    "latitude": 25.1645,
                    "longitude": 93.0176,
                    "location_accuracy": "1km",
                    "event_title": "Haflong slide",
                }
            },
        ),
        # Exact ID duplicate
        (
            "NASA_COOLR_Reports_Points",
            {
                "attributes": {
                    "event_id": 1001,
                    "event_date": ts_2017,
                    "latitude": 25.1645,
                    "longitude": 93.0176,
                    "location_accuracy": "1km",
                    "event_title": "Haflong slide duplicate",
                }
            },
        ),
        # Spatiotemporal near-duplicate (same date, ~110 m away)
        (
            "NASA_COOLR_Reports_Points",
            {
                "attributes": {
                    "event_id": 1002,
                    "event_date": ts_2017,
                    "latitude": 25.1655,
                    "longitude": 93.0176,
                    "location_accuracy": "5km",
                    "event_title": "Haflong slide near dup",
                }
            },
        ),
        # Exact high-precision record inside pilot
        (
            "NASA_COOLR_Reports_Points",
            {
                "attributes": {
                    "event_id": 1003,
                    "event_date": ts_2017,
                    "latitude": 25.3025,
                    "longitude": 93.1335,
                    "location_accuracy": "exact",
                    "event_title": "Maibang exact GPS",
                }
            },
        ),
    ]
    curated, removed = deduplicate_and_classify_records(raw, pilot_poly)
    assert len(curated) == 2
    assert len(removed) == 2
    by_id = {r["external_event_id"]: r for r in curated}
    assert by_id["1001"]["training_usability"] == "contextual_visualization_only"
    assert by_id["1003"]["training_usability"] == "usable_slope_scale"
    assert parse_accuracy_m("exact") == 50.0
    assert parse_accuracy_m("5km") == 5000.0
    assert parse_accuracy_m("unknown") is None


def test_coolr_db_persistence_is_idempotent(tmp_path: Path):
    pilot_poly = box(92.5, 25.0, 93.5, 25.8)
    raw = [
        (
            "NASA_COOLR_Reports_Points",
            {
                "attributes": {
                    "event_id": 5001,
                    "event_date": 1491264000000,
                    "latitude": 25.1645,
                    "longitude": 93.0176,
                    "location_accuracy": "5km",
                    "event_title": "Test DB Persistence",
                }
            },
        )
    ]
    curated, _ = deduplicate_and_classify_records(raw, pilot_poly)
    db_url = f"sqlite:///{tmp_path / 'test_coolr.db'}"
    assert store_landslides_to_db(curated, db_url) == 1
    assert store_landslides_to_db(curated, db_url) == 0


def test_antecedent_rainfall_1d_3d_7d_15d_strict_null_propagation():
    # 16 days with day 5 missing -> days 5..7 have null 3d, days 5..11 have null 7d, day 15 has null 15d
    daily = {f"2024-05-{d:02d}": 10.0 for d in range(1, 17)}
    daily["2024-05-05"] = None
    series = compute_antecedent_series(daily, date(2024, 5, 1), date(2024, 5, 16))
    assert len(series) == 16
    # Day 3 (index 2): 3d = 30.0, 7d = None, 15d = None
    assert series[2]["rainfall_3d_mm"] == 30.0
    assert series[2]["rainfall_7d_mm"] is None
    # Day 5 (index 4): missing -> all rolling sums None
    assert series[4]["rainfall_1d_mm"] is None
    assert series[4]["rainfall_3d_mm"] is None
    assert series[4]["rainfall_7d_mm"] is None
    assert series[4]["missing_1d"] is True
    # Day 8 (index 7): days 6,7,8 valid -> 3d = 30.0, but 7d spans day 5 -> None
    assert series[7]["rainfall_3d_mm"] == 30.0
    assert series[7]["rainfall_7d_mm"] is None
    # Day 12 (index 11): days 6..12 valid -> 7d = 70.0, but 15d still None
    assert series[11]["rainfall_7d_mm"] == 70.0
    assert series[11]["rainfall_15d_mm"] is None

    # Clean 15 consecutive days -> exact 150.0 mm
    clean = {f"2024-04-{d:02d}": 10.0 for d in range(1, 16)}
    clean_series = compute_antecedent_series(clean, date(2024, 4, 1), date(2024, 4, 15))
    assert clean_series[14]["rainfall_15d_mm"] == 150.0
    assert clean_series[14]["missing_15d"] is False

    # Cross-product comparison sanity
    comp = compare_precipitation_series(clean, clean)
    assert comp["overlapping_valid_days"] == 15
    assert comp["mae_mm_per_day"] == 0.0
    assert comp["relative_bias_pct"] == 0.0


def test_curvature_and_tri_on_flat_and_curved_surfaces():
    flat = np.full((3, 3), 500.0, dtype=float)
    res_flat = compute_curvature_and_tri(flat, 90.0)
    assert res_flat["tri_m"] == 0.0
    assert res_flat["profile_curvature"] == 0.0
    assert res_flat["plan_curvature"] == 0.0

    # Bowl z = x^2 + y^2 should have positive TRI and non-zero curvature
    bowl = np.array([[20.0, 10.0, 20.0], [10.0, 0.0, 10.0], [20.0, 10.0, 20.0]], dtype=float)
    res_bowl = compute_curvature_and_tri(bowl, 90.0)
    assert res_bowl["tri_m"] is not None and res_bowl["tri_m"] > 0.0


def test_data_quality_gate_blocks_ml_training_on_coarse_coolr_labels():
    report = evaluate_data_quality_gate(PILOT_DIR)
    assert report.total_checks == 13
    assert report.overall_ml_ready is False
    assert "landslide_location_uncertainty" in report.blocking_failures
    assert "train_test_geographic_separation" in report.blocking_failures

    with pytest.raises(DataQualityGateBlockedError):
        run_ml_training_pipeline(PILOT_DIR)


def test_feature_extraction_returns_real_terrain_and_pre_event_rainfall():
    feats = extract_point_features(25.1645, 93.0176, event_date_iso="2017-04-04", pilot_dir=PILOT_DIR)
    assert feats["elevation_m"] is not None and 500.0 < feats["elevation_m"] < 900.0
    assert feats["slope_deg"] is not None and 0.0 <= feats["slope_deg"] <= 90.0
    assert feats["aspect_sin"] is not None and -1.0 <= feats["aspect_sin"] <= 1.0
    assert feats["aspect_cos"] is not None and -1.0 <= feats["aspect_cos"] <= 1.0
    assert feats["tri_m"] is not None and feats["tri_m"] >= 0.0
    assert feats["worldcover_2021_code"] == 10
    assert feats["spatial_block_5km"].startswith("utm46n_")


def test_stage3_4_5_fastapi_endpoints():
    r_coolr = client.get("/api/v1/landslides/coolr?pilot_only=true")
    assert r_coolr.status_code == 200
    coolr_body = r_coolr.json()
    assert coolr_body["summary"]["within_dima_hasao_polygon"] == 19
    assert coolr_body["summary"]["usable_for_30m_90m_slope_training_pilot"] == 0
    assert coolr_body["summary"]["fabricated_labels_count"] == 0
    assert len(coolr_body["records"]) == 19

    r_gate = client.get("/api/v1/quality-gate")
    assert r_gate.status_code == 200
    gate_body = r_gate.json()
    assert gate_body["total_checks"] == 13
    assert gate_body["overall_ml_ready"] is False
    assert "landslide_location_uncertainty" in gate_body["blocking_failures"]

    # Multi-year rainfall endpoint (if ingestion completed)
    if (PILOT_DIR / "dima_hasao_rainfall_multiyear.json").exists():
        r_rain = client.get("/api/v1/environment/rainfall/multiyear?start_date=2024-05-01&end_date=2024-06-30")
        assert r_rain.status_code == 200
        rb = r_rain.json()
        assert rb["data_role"] == "historical_archive"
        assert rb["total_calendar_days"] == 3653
        assert len(rb["observations"]) == 61
