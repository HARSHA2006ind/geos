"""
Stage 10 / Release Validation — Automated Tests for GFS Fixes, Monitoring, Retry Logic & PostGIS Integration.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from zarr.core.buffer import default_buffer_prototype

from backend.app.db import Base, build_engine
from backend.app.models import MonitoringRun, WeatherForecast
from backend.app.services.hazard_engine import load_latest_gfs_forecast
from backend.app.services.monitoring_service import execute_monitoring_cycle
from backend.experimental.nvidia_weather_eval.dynamical_gfs_eval import ReadOnlyHttpxZarrStore
from backend.ingestion.sync_postgis import sync_all_artifacts_to_db

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
EXPERIMENTAL_DIR = Path(__file__).resolve().parents[1] / "data" / "experimental"
DEFAULT_PG_URL = "postgresql+psycopg://geos:geos_dev_password@127.0.0.1:5432/geos_ner"


def test_gfs_forecast_loader_reads_48h_and_mean_temp():
    fc = load_latest_gfs_forecast(EXPERIMENTAL_DIR)
    assert fc is not None
    assert fc["data_role"] == "experimental_forecast_only_never_measured_rainfall"
    assert fc["rain_24h_outlook_mm"] is not None
    assert fc["rain_48h_outlook_mm"] is not None
    assert fc["rain_72h_outlook_mm"] is not None
    assert fc["temp_2m_mean_c"] is not None


def test_zarr_http_store_retries_transient_errors_then_succeeds():
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 3:
            return httpx.Response(503, text="Upstream busy")
        return httpx.Response(200, content=b'{"ok":true}')

    async def _run():
        store = ReadOnlyHttpxZarrStore("https://data.dynamical.org/noaa/gfs/forecast/latest.zarr")
        store._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        buf = await store.get("zarr.json", default_buffer_prototype())
        await store._client.aclose()
        return buf

    with patch("asyncio.sleep", return_value=None):
        buf = asyncio.run(_run())
    assert buf is not None
    assert attempts["count"] == 3
    assert json.loads(buf.to_bytes().decode("utf-8")) == {"ok": True}


def test_monitoring_cycle_persists_3_horizons_and_distinct_valid_times(tmp_path: Path):
    db_url = f"sqlite:///{tmp_path / 'mon_test.db'}"
    engine = build_engine(db_url)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    with SessionFactory() as db:
        res = execute_monitoring_cycle(db=db, pilot_dir=PILOT_DIR, refresh_live_gfs=False)
        assert res["error_message"] is None
        assert res["observed_rainfall_stale"] is True
        assert res["summary"]["forecast_horizons_inserted"] == 3
        forecasts = db.query(WeatherForecast).order_by(WeatherForecast.horizon_hours).all()
        assert [f.horizon_hours for f in forecasts] == [24, 48, 72]
        assert len({f.valid_time_utc for f in forecasts}) == 3
        assert db.query(MonitoringRun).count() == 1


def _postgres_reachable() -> bool:
    try:
        eng = build_engine(DEFAULT_PG_URL)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_reachable(), reason="PostgreSQL+PostGIS daemon not reachable on 127.0.0.1:5432")
def test_real_postgis_spatial_queries_and_synced_data():
    engine = build_engine(DEFAULT_PG_URL)
    with engine.connect() as conn:
        ver = conn.execute(text("SELECT PostGIS_Version()")).scalar()
        assert ver is not None
        sa_type = conn.execute(
            text("SELECT ST_GeometryType(geom), ST_SRID(geom) FROM study_areas WHERE slug = 'dima-hasao'")
        ).first()
        assert sa_type is not None
        assert sa_type[0] == "ST_MultiPolygon"
        assert sa_type[1] == 4326

        within_count = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM landslide_events le
                JOIN study_areas sa ON sa.slug = 'dima-hasao'
                WHERE le.geom IS NOT NULL AND ST_Contains(sa.geom, le.geom)
                """
            )
        ).scalar()
        assert within_count >= 300

        near_facilities = conn.execute(
            text(
                """
                SELECT COUNT(*) FROM infrastructure_assets
                WHERE source_provider = 'OSM_Overpass'
                  AND ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(93.0176, 25.1645), 4326)::geography, 5000)
                """
            )
        ).scalar()
        assert near_facilities >= 5
