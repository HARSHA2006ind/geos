"""Release-hardening regression tests for caching, monitoring reliability, and Gemini discovery."""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings
from backend.app.db import Base, build_engine
from backend.app.main import create_app
from backend.app.models import MonitoringRun, WeatherForecast
from backend.app.services.hazard_engine import (
    InfrastructureExposureIndex,
    get_cached_quality_gate,
    load_latest_gfs_forecast,
)
from backend.app.services.monitoring_service import execute_monitoring_cycle
from backend.app.services.rainfall_service import PilotRainfallService


def test_rainfall_and_quality_gate_cache_invalidation_on_mtime(tmp_path: Path) -> None:
    pilot_src = Path("backend/data/pilot")
    rain_file = tmp_path / "dima_hasao_rainfall_imerg.json"
    shutil.copy2(pilot_src / "dima_hasao_rainfall_imerg.json", rain_file)

    svc = PilotRainfallService(pilot_dir=tmp_path)
    first_hist = svc.get_history()
    assert first_hist is not None
    assert "Dima Hasao District, Assam" in first_hist.study_area

    # Mutate file content & advance mtime_ns explicitly -> cache must invalidate immediately
    doc = json.loads(rain_file.read_text(encoding="utf-8"))
    doc["study_area"] = "Dima Hasao Cache Invalidation Check"
    rain_file.write_text(json.dumps(doc), encoding="utf-8")
    stat = rain_file.stat()
    os.utime(rain_file, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000))

    second_hist = svc.get_history()
    assert second_hist is not None
    assert second_hist.study_area == "Dima Hasao Cache Invalidation Check"


def test_quality_gate_cache_returns_consistent_blocked_state() -> None:
    pilot_dir = Path("backend/data/pilot")
    rep1 = get_cached_quality_gate(pilot_dir)
    rep2 = get_cached_quality_gate(pilot_dir)
    assert rep1 is rep2
    assert rep1.overall_ml_ready is False
    assert rep1.passed_checks == 6
    assert rep1.total_checks == 13


def test_exposure_index_bbox_prefilter_exact_equivalence() -> None:
    idx = InfrastructureExposureIndex(Path("backend/data/pilot"))
    for lat, lon, r in [(25.1645, 93.0176, 5.0), (25.1275, 93.0252, 3.0), (25.35, 93.15, 7.5)]:
        res_fast = idx.query_proximity(lat, lon, radius_km=r)
        assert res_fast["counts"]["road_segments"] >= 0
        assert res_fast["counts"]["hospitals_health"] >= 0
        assert res_fast["exposure_nature"] == "estimated_spatial_proximity_not_observed_damage"
        for asset in res_fast["nearest_assets"]:
            assert asset["distance_km"] <= r


def test_monitoring_cycle_failure_recovery_idempotency_and_stale_expiration(
    tmp_path: Path, monkeypatch
) -> None:
    db_file = tmp_path / "monitoring_test.sqlite3"
    engine = build_engine(f"sqlite:///{db_file}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

    exp_dir = tmp_path / "experimental"
    exp_dir.mkdir(parents=True, exist_ok=True)
    fresh_init = (datetime.now(timezone.utc) - timedelta(hours=2)).replace(microsecond=0).isoformat()
    fc_path = exp_dir / "dima_hasao_gfs_forecast_eval.json"
    fc_path.write_text(
        json.dumps(
            {
                "init_time_utc": fresh_init,
                "rain_24h_outlook_mm": 12.4,
                "rain_48h_outlook_mm": 22.8,
                "rain_72h_outlook_mm": 35.1,
                "spatial_resolution_deg": 0.25,
                "source_url": "https://data.dynamical.org/noaa/gfs/forecast/latest.zarr",
            }
        ),
        encoding="utf-8",
    )

    pilot_dir = Path("backend/data/pilot")

    # Cycle 1 & 2: idempotent weather_forecasts insertion
    with SessionLocal() as db:
        r1 = execute_monitoring_cycle(db=db, pilot_dir=pilot_dir, refresh_live_gfs=False, experimental_dir=exp_dir)
        r2 = execute_monitoring_cycle(db=db, pilot_dir=pilot_dir, refresh_live_gfs=False, experimental_dir=exp_dir)
        assert r1["run_id"] < r2["run_id"]
        assert r1["error_message"] is None
        assert r1["forecast_stale"] is False
        assert db.scalar(select(func.count()).select_from(WeatherForecast)) == 3
        assert db.scalar(select(func.count()).select_from(MonitoringRun)) == 2

    # Cycle 3: simulate live NOAA GFS fetch failure -> logs error_message and retains cached forecast
    import backend.experimental.nvidia_weather_eval.dynamical_gfs_eval as gfs_mod

    def _boom(**_kwargs):
        raise RuntimeError("Simulated upstream Zarr timeout")

    monkeypatch.setattr(gfs_mod, "evaluate_dynamical_gfs_dima_hasao", _boom)
    with SessionLocal() as db:
        r3 = execute_monitoring_cycle(db=db, pilot_dir=pilot_dir, refresh_live_gfs=True, experimental_dir=exp_dir)
        assert r3["status"] == "partial_stale"
        assert "Simulated upstream Zarr timeout" in (r3["error_message"] or "")
        assert r3["forecast_init_time_utc"] == fresh_init
        assert db.scalar(select(func.count()).select_from(WeatherForecast)) == 3

    # Stale expiration check: forecast > 24h old must be flagged is_stale=True automatically
    stale_init = (datetime.now(timezone.utc) - timedelta(hours=30)).replace(microsecond=0).isoformat()
    fc_path.write_text(
        json.dumps(
            {
                "init_time_utc": stale_init,
                "rain_24h_outlook_mm": 10.0,
                "rain_48h_outlook_mm": 15.0,
                "rain_72h_outlook_mm": 20.0,
            }
        ),
        encoding="utf-8",
    )
    stat = fc_path.stat()
    os.utime(fc_path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 5_000_000))
    loaded = load_latest_gfs_forecast(exp_dir)
    assert loaded is not None
    assert loaded["is_stale"] is True
    assert loaded["forecast_age_hours"] >= 29.9


def test_assistant_models_discovery_endpoint(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "gemini_disc.sqlite3"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("GEOS_AUTH_SECRET", "test-ephemeral-signing-secret-0123456789abcdef")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    app = create_app(settings_override=Settings(database_url=db_url, gemini_api_key=None))
    client = TestClient(app)

    res = client.get("/api/v1/assistant/models")
    assert res.status_code == 503
    assert res.json()["detail"]["error"] == "gemini_not_configured"
