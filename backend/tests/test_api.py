"""API integration tests for GeoResilience-NER 2.0 FastAPI backend."""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app.main import create_app

client = TestClient(create_app())


def test_health_endpoint_reports_all_pilot_artifacts() -> None:
    res = client.get("/api/v1/health")
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "operational"
    assert "X-Request-ID" in res.headers
    assert res.headers.get("X-Content-Type-Options") == "nosniff"
    artifacts = body["pilot_artifacts"]
    assert artifacts["dima_hasao_boundary"] is True
    assert artifacts["copernicus_dem_30m_core"] is True
    assert artifacts["copernicus_dem_district"] is True
    assert artifacts["slope_raster"] is True
    assert artifacts["aspect_raster"] is True
    assert artifacts["worldcover_2021"] is True
    assert artifacts["gpm_imerg_rainfall"] is True
    assert artifacts["landslide_inventory_discovery"] is True


def test_datasets_registry_returns_verified_provenance() -> None:
    res = client.get("/api/v1/datasets")
    assert res.status_code == 200
    items = res.json()
    ids = {item["dataset_id"] for item in items}
    assert "osm-dima-hasao-boundary" in ids
    assert "copernicus-dem-glo30" in ids
    assert "nasa-gpm-imerg-daily" in ids
    assert "esa-worldcover-2021-v200" in ids
    for item in items:
        assert item["attribution"]
        assert item["source_url"]
        assert item["processing_timestamp"]


def test_pilot_boundary_returns_valid_geojson_and_summaries() -> None:
    res = client.get("/api/v1/pilot/boundary")
    assert res.status_code == 200
    body = res.json()
    assert body["geojson"]["type"] == "FeatureCollection"
    assert len(body["geojson"]["features"]) == 1
    meta = body["geojson"]["metadata"]
    assert meta["crs"] == "EPSG:4326"
    assert meta["geometry_valid"] is True
    assert 4000.0 <= meta["area_km2"] <= 5500.0


def test_environment_point_inside_haflong_returns_real_observations_and_null_ml() -> None:
    # Haflong, Dima Hasao District, Assam
    res = client.get("/api/v1/environment/point", params={"lat": 25.1645, "lon": 93.0176})
    assert res.status_code == 200
    body = res.json()
    assert body["within_pilot_boundary"] is True
    assert body["within_raster_bounds"] is True
    assert body["landslide_probability"] is None
    assert "No landslide susceptibility" in body["scientific_disclaimer"]

    terrain = body["terrain"]
    assert terrain["missing_elevation"] is False
    assert 100.0 <= terrain["elevation_m"] <= 2200.0
    assert terrain["missing_slope_aspect"] is False
    assert 0.0 <= terrain["slope_deg"] <= 90.0
    assert 0.0 <= terrain["aspect_deg"] <= 360.0
    assert terrain["provenance"]["crs"] == "EPSG:32646"
    assert terrain["provenance"]["processing_timestamp"]

    lc = body["land_cover"]
    assert lc["missing_land_cover"] is False
    assert lc["class_code"] in {10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100}
    assert lc["class_label"]

    rain = body["rainfall"]
    assert rain["provenance"]["dataset_id"] == "nasa-gpm-imerg-daily"
    assert rain["latest_observation_timestamp_utc"] is not None
    assert body["missing_data_indicators"]["landslide_ml_probability"] is True
    assert body["missing_data_indicators"]["factor_of_safety"] is True


def test_environment_point_outside_pilot_returns_nulls_never_fabricated() -> None:
    # New Delhi (far outside Dima Hasao)
    res = client.get("/api/v1/environment/point", params={"lat": 28.6139, "lon": 77.2090})
    assert res.status_code == 200
    body = res.json()
    assert body["within_pilot_boundary"] is False
    assert body["within_raster_bounds"] is False
    assert body["terrain"]["elevation_m"] is None
    assert body["terrain"]["slope_deg"] is None
    assert body["terrain"]["missing_elevation"] is True
    assert body["land_cover"]["class_code"] is None
    assert body["land_cover"]["missing_land_cover"] is True
    assert body["rainfall"]["rainfall_24h_mm"] is None
    assert body["rainfall"]["rainfall_72h_mm"] is None
    assert body["rainfall"]["missing_24h"] is True
    assert body["rainfall"]["missing_72h"] is True
    assert body["landslide_probability"] is None


def test_environment_point_rejects_invalid_coordinates() -> None:
    res_lat = client.get("/api/v1/environment/point", params={"lat": 95.0, "lon": 93.0})
    assert res_lat.status_code == 422
    res_lon = client.get("/api/v1/environment/point", params={"lat": 25.1, "lon": 200.0})
    assert res_lon.status_code == 422


def test_rainfall_history_preserves_missing_days_and_supports_date_filters() -> None:
    res = client.get("/api/v1/environment/rainfall/history")
    assert res.status_code == 200
    body = res.json()
    assert body["dataset_id"] == "nasa-gpm-imerg-daily"
    assert body["total_days"] == len(body["observations"])
    assert body["valid_observation_days"] > 0
    assert body["missing_observation_days"] >= 0
    # Verify missing records explicitly carry null rainfall_24h_mm (never coerced to 0.0)
    for rec in body["observations"]:
        if rec["missing_24h"]:
            assert rec["rainfall_24h_mm"] is None
        else:
            assert rec["rainfall_24h_mm"] is not None
            assert rec["rainfall_24h_mm"] >= 0.0

    # Date filter
    filtered = client.get(
        "/api/v1/environment/rainfall/history",
        params={"start_date": "2024-05-25", "end_date": "2024-06-01"},
    )
    assert filtered.status_code == 200
    f_body = filtered.json()
    assert len(f_body["observations"]) == 8
    assert f_body["observations"][0]["date"] == "2024-05-25"
    assert f_body["observations"][-1]["date"] == "2024-06-01"

    # Invalid date range
    bad = client.get(
        "/api/v1/environment/rainfall/history",
        params={"start_date": "2024-06-10", "end_date": "2024-05-01"},
    )
    assert bad.status_code == 400


def test_inventory_discovery_never_fabricates_landslide_labels() -> None:
    res = client.get("/api/v1/inventory/discovery")
    assert res.status_code == 200
    body = res.json()
    assert body["fabricated_labels_count"] == 0
    assert len(body["providers"]) >= 3
