"""Geospatial math, CRS validation, missing-data policy, and provenance tests."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
import rasterio
from shapely.geometry import shape

from backend.ingestion.fetch_copernicus_dem import compute_slope_aspect_horn
from backend.ingestion.fetch_gpm_imerg import compute_rolling_accumulations

PILOT_DIR = Path("backend/data/pilot")


def test_horn_slope_aspect_matches_analytical_tilted_plane() -> None:
    """
    Validate Horn (1981) 3x3 finite difference on an exact mathematical plane:
    z(x, y) = 1000 - x * tan(30 deg) on a 30 m metric grid -> slope = 30 deg, aspect = 90 deg (East).
    Note: synthetic unit-test fixture strictly isolated from pilot datasets.
    """
    cell_size = 30.0
    rows, cols = 9, 9
    slope_target_deg = 30.0
    grad = math.tan(math.radians(slope_target_deg))
    x = np.arange(cols, dtype=np.float64) * cell_size
    z = 1000.0 - np.tile(x * grad, (rows, 1))
    nodata_mask = np.zeros_like(z, dtype=bool)

    slope, aspect = compute_slope_aspect_horn(z, pixel_size_x=cell_size, pixel_size_y=cell_size, nodata_mask=nodata_mask)
    center_slope = float(slope[4, 4])
    center_aspect = float(aspect[4, 4])
    assert center_slope == pytest.approx(slope_target_deg, abs=1e-4)
    assert center_aspect == pytest.approx(90.0, abs=1e-4)


def test_missing_rainfall_never_coerced_to_zero() -> None:
    """Missing days must remain None and propagate missingness to 72h rolling sums."""
    from datetime import date

    daily_map = {
        "2024-05-01": 10.0,
        "2024-05-02": 20.0,
        "2024-05-03": 30.0,
        "2024-05-04": None,
        "2024-05-05": 5.0,
        "2024-05-06": 15.0,
        "2024-05-07": 25.0,
    }
    rows = compute_rolling_accumulations(daily_map, date(2024, 5, 1), date(2024, 5, 7))
    assert len(rows) == 7

    # Day 1 & 2 lack full 3-day window -> rainfall_72h_mm must be None
    assert rows[0]["rainfall_72h_mm"] is None and rows[0]["missing_72h"] is True
    assert rows[1]["rainfall_72h_mm"] is None and rows[1]["missing_72h"] is True

    # Day 3 has full 3 valid days -> 10 + 20 + 30 = 60.0
    assert rows[2]["rainfall_72h_mm"] == pytest.approx(60.0, abs=1e-6)
    assert rows[2]["missing_72h"] is False

    # Day 4 is missing -> 24h is None (NOT 0.0), 72h is None
    assert rows[3]["rainfall_24h_mm"] is None
    assert rows[3]["missing_24h"] is True
    assert rows[3]["rainfall_72h_mm"] is None
    assert rows[3]["missing_72h"] is True

    # Days 5 & 6 overlap Day 4 missing -> 72h must stay None
    assert rows[4]["rainfall_72h_mm"] is None and rows[4]["missing_72h"] is True
    assert rows[5]["rainfall_72h_mm"] is None and rows[5]["missing_72h"] is True

    # Day 7 has 3 consecutive valid days again (5 + 15 + 25 = 45.0)
    assert rows[6]["rainfall_72h_mm"] == pytest.approx(45.0, abs=1e-6)
    assert rows[6]["missing_72h"] is False


def test_real_pilot_rasters_have_expected_crs_and_physical_ranges() -> None:
    dem_30m = PILOT_DIR / "haflong_jatinga_copernicus_dem_30m.tif"
    dem_utm = PILOT_DIR / "dima_hasao_dem_utm46n.tif"
    slope_utm = PILOT_DIR / "dima_hasao_slope_deg_utm46n.tif"
    aspect_utm = PILOT_DIR / "dima_hasao_aspect_deg_utm46n.tif"
    wc_utm = PILOT_DIR / "dima_hasao_worldcover_2021_utm46n.tif"

    with rasterio.open(dem_30m) as src:
        assert src.crs.to_string() == "EPSG:4326"
        data = src.read(1, masked=True)
        assert float(data.min()) > 0.0
        assert float(data.max()) < 3000.0

    with rasterio.open(dem_utm) as src:
        assert src.crs.to_string() == "EPSG:32646"

    with rasterio.open(slope_utm) as src:
        assert src.crs.to_string() == "EPSG:32646"
        data = src.read(1, masked=True)
        assert float(data.min()) >= 0.0
        assert float(data.max()) <= 90.0

    with rasterio.open(aspect_utm) as src:
        assert src.crs.to_string() == "EPSG:32646"
        data = src.read(1, masked=True)
        # -1.0 encodes flat pixels (dz/dx == 0 and dz/dy == 0), valid compass aspects are [0, 360]
        assert float(data.min()) >= -1.0
        assert float(data.max()) <= 360.0

    with rasterio.open(wc_utm) as src:
        assert src.crs.to_string() == "EPSG:32646"
        vals = set(np.unique(src.read(1)).tolist()) - {0}
        assert vals.issubset({10, 20, 30, 40, 50, 60, 70, 80, 90, 95, 100})


def test_boundary_geometry_and_provenance_manifest_complete() -> None:
    boundary_doc = json.loads((PILOT_DIR / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
    geom = shape(boundary_doc["features"][0]["geometry"])
    assert geom.is_valid
    assert boundary_doc["metadata"]["crs"] == "EPSG:4326"
    assert boundary_doc["metadata"]["processing_timestamp"]

    manifest = json.loads((PILOT_DIR / "ingestion_manifest.json").read_text(encoding="utf-8"))
    assert manifest["pilot_study_area"] == "Dima Hasao District, Assam, India"
    assert manifest["copernicus_dem"]["processing_timestamp"]
    assert manifest["esa_worldcover"]["processing_timestamp"]
    assert manifest["landslide_inventory_discovery"]["fabricated_labels_count"] == 0
