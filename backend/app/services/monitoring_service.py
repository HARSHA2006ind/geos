"""
Phase J & Phase O — Automated Environmental Monitoring Service & 8-State NER Regional Coverage.

Handles:
  - Scheduled / on-demand environmental freshness & forecast update cycles.
  - Idempotent recording of monitoring runs and NOAA GFS weather forecasts in the database.
  - Explicit staleness detection for delayed/missing observed rainfall providers (IMERG).
  - Regional expansion registry across all 8 Northeast Indian states cleanly distinguishing:
      region_configured | environmental_data_available | landslide_inventory_available |
      model_validated | experimental_monitoring_active
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import MonitoringRun, RegionalCoverage, WeatherForecast
from backend.app.services.hazard_engine import EXPERIMENTAL_DIR, load_latest_gfs_forecast

NER_STATES_SEED: list[dict[str, Any]] = [
    {
        "state_code": "AS",
        "state_name": "Assam",
        "pilot_district": "Dima Hasao",
        "region_configured": True,
        "environmental_data_available": True,
        "landslide_inventory_available": True,
        "model_validated": False,
        "experimental_monitoring_active": True,
        "center_lat": 25.17,
        "center_lon": 93.02,
        "coverage_notes": (
            "Primary pilot district (Dima Hasao): Copernicus DEM GLO-30 + derivatives, ISRIC SoilGrids 2.0 (7 layers), "
            "ESA WorldCover 2021, Sentinel-2 2024 NDVI, OSM transport & 619 facilities, 379 GSI Bhusanket + NASA COOLR records, "
            "10-year IMERG historical rainfall, and live NOAA GFS CPU forecast. ML model NOT yet validated (6 blocking quality gates)."
        ),
    },
    {
        "state_code": "AR",
        "state_name": "Arunachal Pradesh",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 28.21,
        "center_lon": 94.73,
        "coverage_notes": "Configured in regional architecture; district raster ingestion, GSI inventory curation, and spatial validation pending.",
    },
    {
        "state_code": "ML",
        "state_name": "Meghalaya",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 25.47,
        "center_lon": 91.37,
        "coverage_notes": "Configured in regional architecture (adjacent to Barail/Shillong Plateau); no state-level validated layers ingested yet.",
    },
    {
        "state_code": "MN",
        "state_name": "Manipur",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 24.66,
        "center_lon": 93.91,
        "coverage_notes": "Configured in regional architecture (NH-37/Noney corridor candidate); ingestion and validation pending.",
    },
    {
        "state_code": "MZ",
        "state_name": "Mizoram",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 23.16,
        "center_lon": 92.94,
        "coverage_notes": "Configured in regional architecture (Aizawl/Lunglei hill ranges); ingestion and validation pending.",
    },
    {
        "state_code": "NL",
        "state_name": "Nagaland",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 26.16,
        "center_lon": 94.56,
        "coverage_notes": "Configured in regional architecture (Kohima/NH-29 corridor candidate); ingestion and validation pending.",
    },
    {
        "state_code": "TR",
        "state_name": "Tripura",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 23.94,
        "center_lon": 91.99,
        "coverage_notes": "Configured in regional architecture; ingestion and validation pending.",
    },
    {
        "state_code": "SK",
        "state_name": "Sikkim",
        "pilot_district": None,
        "region_configured": True,
        "environmental_data_available": False,
        "landslide_inventory_available": False,
        "model_validated": False,
        "experimental_monitoring_active": False,
        "center_lat": 27.53,
        "center_lon": 88.51,
        "coverage_notes": "Configured in regional architecture (Teesta valley / Gangtok steep slopes); ingestion and validation pending.",
    },
]


def ensure_regional_coverage_seeded(db: Session) -> list[dict[str, Any]]:
    existing = {r.state_code: r for r in db.scalars(select(RegionalCoverage)).all()}
    changed = False
    for row in NER_STATES_SEED:
        if row["state_code"] not in existing:
            db.add(RegionalCoverage(**row))
            changed = True
    if changed:
        db.commit()
    rows = db.scalars(select(RegionalCoverage).order_by(RegionalCoverage.id)).all()
    return [
        {
            "state_code": r.state_code,
            "state_name": r.state_name,
            "pilot_district": r.pilot_district,
            "region_configured": r.region_configured,
            "environmental_data_available": r.environmental_data_available,
            "landslide_inventory_available": r.landslide_inventory_available,
            "model_validated": r.model_validated,
            "experimental_monitoring_active": r.experimental_monitoring_active,
            "center_lat": r.center_lat,
            "center_lon": r.center_lon,
            "coverage_notes": r.coverage_notes,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in rows
    ]


def execute_monitoring_cycle(
    db: Session,
    pilot_dir: Path,
    refresh_live_gfs: bool = False,
    experimental_dir: Path = EXPERIMENTAL_DIR,
) -> dict[str, Any]:
    """
    Runs an idempotent environmental monitoring & freshness cycle:
      1. Inspects verified NASA GPM IMERG archive freshness & missing days.
      2. Optionally refreshes live NOAA GFS 0.25 deg forecast via CPU-only Dynamical.org Zarr v3.
      3. Upserts 24h / 48h / 72h forecast horizons into `weather_forecasts`.
      4. Persists a `monitoring_runs` execution record with staleness indicators.
    """
    started = datetime.now(timezone.utc)
    error_msg: str | None = None

    # 1. Check observed rainfall freshness
    rain_path = pilot_dir / "dima_hasao_rainfall_multiyear.json"
    latest_obs_date: str | None = None
    valid_days = 0
    missing_days = 0
    if rain_path.exists():
        rdoc = json.loads(rain_path.read_text(encoding="utf-8"))
        obs = rdoc.get("observations") or []
        valid_obs = [o for o in obs if o.get("rainfall_1d_mm") is not None]
        valid_days = len(valid_obs)
        missing_days = len(obs) - valid_days
        if valid_obs:
            latest_obs_date = valid_obs[-1]["date"]

    obs_stale = True
    if latest_obs_date:
        try:
            obs_dt = datetime.fromisoformat(f"{latest_obs_date}T00:00:00+00:00")
            obs_stale = (started - obs_dt).days > 3
        except ValueError:
            obs_stale = True

    # 2. Optionally refresh live NOAA GFS forecast
    if refresh_live_gfs:
        try:
            from backend.experimental.nvidia_weather_eval.dynamical_gfs_eval import (
                evaluate_dynamical_gfs_dima_hasao,
            )

            evaluate_dynamical_gfs_dima_hasao(forecast_hours=72, out_dir=experimental_dir)
        except Exception as exc:  # noqa: BLE001
            error_msg = f"Live NOAA GFS refresh failed (retained cached forecast): {exc}"

    forecast = load_latest_gfs_forecast(experimental_dir)
    forecast_init = forecast.get("init_time_utc") if forecast else None
    forecast_stale = bool(forecast.get("is_stale", True)) if forecast else True

    # 3. Idempotently upsert forecast horizons (24h, 48h, 72h) into weather_forecasts table
    horizons_persisted = 0
    if forecast and forecast_init:
        init_dt_parsed: datetime | None = None
        try:
            init_dt_parsed = datetime.fromisoformat(str(forecast_init).replace("Z", "+00:00"))
        except ValueError:
            init_dt_parsed = None

        for horizon, key in (
            (24, "rain_24h_outlook_mm"),
            (48, "rain_48h_outlook_mm"),
            (72, "rain_72h_outlook_mm"),
        ):
            valid_time_str = (
                (init_dt_parsed + timedelta(hours=horizon)).isoformat()
                if init_dt_parsed is not None
                else str(forecast_init)
            )
            existing_fc = db.scalar(
                select(WeatherForecast).where(
                    WeatherForecast.study_area_slug == "dima-hasao",
                    WeatherForecast.provider == "dynamical_org_noaa_gfs",
                    WeatherForecast.init_time_utc == forecast_init,
                    WeatherForecast.horizon_hours == horizon,
                )
            )
            if existing_fc is None:
                db.add(
                    WeatherForecast(
                        study_area_slug="dima-hasao",
                        provider="dynamical_org_noaa_gfs",
                        model_name="NOAA GFS 0.25 deg",
                        init_time_utc=forecast_init,
                        valid_time_utc=valid_time_str,
                        horizon_hours=horizon,
                        spatial_resolution_deg=float(forecast.get("spatial_resolution_deg") or 0.25),
                        rain_accum_mm=forecast.get(key),
                        temp_2m_mean_c=(
                            forecast.get("temp_2m_mean_c")
                            if forecast.get("temp_2m_mean_c") is not None
                            else forecast.get("temp_2m_max_c")
                        ),
                        rh_2m_mean_pct=forecast.get("rh_2m_mean_pct"),
                        pwat_mean_mm=forecast.get("pwat_mean_mm"),
                        missing_values_count=0,
                        data_role="experimental_forecast_only",
                        source_url=str(
                            forecast.get("source_url") or "https://data.dynamical.org/noaa/gfs/forecast/latest.zarr"
                        ),
                    )
                )
                horizons_persisted += 1

    completed = datetime.now(timezone.utc)
    status = "partial_stale" if (obs_stale or forecast_stale or error_msg) else "succeeded"

    summary = {
        "observed_rainfall": {
            "provider": "NASA GPM IMERG (Multi-Year Archive)",
            "latest_valid_date": latest_obs_date,
            "valid_days": valid_days,
            "missing_days_null": missing_days,
            "is_stale": obs_stale,
            "stale_reason": (
                "NASA Earthdata Login credentials required to download post-2024-06-01 IMERG V07B/V07C daily HDF5 granules."
                if obs_stale
                else None
            ),
        },
        "forecast_outlook": forecast,
        "forecast_horizons_inserted": horizons_persisted,
        "provider_latency_notice": (
            "Satellite precipitation (IMERG Early/Late/Final) has intrinsic 4h–3.5mo latency; "
            "NOAA GFS updates every 6 hours. System does NOT claim continuous real-time telemetry."
        ),
    }

    run_row = MonitoringRun(
        job_name="dima_hasao_environmental_monitoring",
        study_area_slug="dima-hasao",
        status=status,
        started_at=started,
        completed_at=completed,
        observed_rainfall_latest_date=latest_obs_date,
        observed_rainfall_stale=obs_stale,
        forecast_init_time_utc=forecast_init,
        forecast_stale=forecast_stale,
        summary_json=summary,
        error_message=error_msg,
    )
    db.add(run_row)
    db.commit()
    db.refresh(run_row)

    return {
        "run_id": run_row.id,
        "job_name": run_row.job_name,
        "status": run_row.status,
        "started_at": run_row.started_at.isoformat(),
        "completed_at": run_row.completed_at.isoformat() if run_row.completed_at else None,
        "observed_rainfall_latest_date": run_row.observed_rainfall_latest_date,
        "observed_rainfall_stale": run_row.observed_rainfall_stale,
        "forecast_init_time_utc": run_row.forecast_init_time_utc,
        "forecast_stale": run_row.forecast_stale,
        "summary": run_row.summary_json,
        "error_message": run_row.error_message,
    }
