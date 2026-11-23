"""Alembic migration upgrade/downgrade and SQLAlchemy ORM roundtrip tests."""
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from backend.app.db import build_engine
from backend.app.models import (
    DatasetRegistry,
    IngestionJob,
    LandslideEvent,
    ProvenanceRecord,
    RainfallObservation,
    StudyArea,
)


def test_alembic_upgrade_orm_roundtrip_and_downgrade(tmp_path: Path, monkeypatch) -> None:
    db_file = tmp_path / "test_geos_migrations.sqlite3"
    db_url = f"sqlite:///{db_file}"
    monkeypatch.setenv("DATABASE_URL", db_url)

    alembic_cfg = Config("backend/alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", db_url)

    # 1. Upgrade to head (runs 0001 + 0002)
    command.upgrade(alembic_cfg, "head")

    engine = build_engine(db_url)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    expected_tables = {
        "dataset_registry",
        "study_areas",
        "ingestion_jobs",
        "rainfall_observations",
        "landslide_events",
        "provenance_records",
    }
    assert expected_tables.issubset(tables)

    # 2. ORM roundtrip covering all 6 core tables (including null rainfall & landslide_events)
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        ds = DatasetRegistry(
            id="nasa-gpm-imerg-daily",
            name="NASA GPM IMERG Late Run Daily",
            category="precipitation",
            provider="NASA GSFC / SERVIR ClimateSERV",
            product_version="GPM IMERG Late Daily",
            crs="EPSG:4326",
            native_resolution_m=11100.0,
            source_url="https://climateserv.servirglobal.net/api/submitDataRequest/",
            attribution="NASA GPM IMERG",
            requires_credentials=False,
            observation_period="2015-01-01 to 2024-12-31",
            status="available",
        )
        area = StudyArea(
            slug="dima-hasao",
            name="Dima Hasao District",
            state="Assam",
            crs="EPSG:4326",
            area_km2=4880.75,
            bbox_wgs84=[92.52, 24.97, 93.47, 25.83],
            geom="MULTIPOLYGON(((92.52 24.97, 93.47 24.97, 93.47 25.83, 92.52 25.83, 92.52 24.97)))",
            source_attribution="OpenStreetMap contributors",
        )
        job = IngestionJob(
            dataset_id="nasa-gpm-imerg-daily",
            study_area_slug="dima-hasao",
            status="succeeded",
            started_at=now,
            completed_at=now,
            records_ingested=3440,
            missing_records=213,
        )
        rain_missing = RainfallObservation(
            study_area_slug="dima-hasao",
            dataset_id="nasa-gpm-imerg-daily",
            observation_date=date(2024, 6, 15),
            observation_timestamp_utc=now,
            rainfall_24h_mm=None,
            rainfall_72h_mm=None,
            rainfall_7d_mm=None,
            rainfall_15d_mm=None,
            missing_24h=True,
            missing_72h=True,
            missing_7d=True,
            missing_15d=True,
            data_role="historical_archive",
            product_version="GPM IMERG Late Daily",
        )
        ev = LandslideEvent(
            source_provider="NASA_COOLR_Reports_Points",
            external_event_id="10980",
            dedup_key="test-dedup-10980",
            event_date=date(2017, 4, 4),
            event_date_precision="day",
            event_title="Landslide in Mahur",
            latitude=25.1815,
            longitude=93.1181,
            geom="POINT(93.1181 25.1815)",
            location_accuracy_raw="1km",
            location_accuracy_m=1000.0,
            spatial_zone="pilot_polygon",
            within_pilot_boundary=True,
            training_usability="contextual_visualization_only",
            usability_reason="1 km positional uncertainty exceeds 100 m threshold.",
        )
        prov = ProvenanceRecord(
            dataset_id="nasa-gpm-imerg-daily",
            artifact_filename="dima_hasao_rainfall_multiyear.json",
            checksum_sha256="0" * 64,
            source_url="https://climateserv.servirglobal.net/api/submitDataRequest/",
            observation_period="2015-01-01 to 2024-12-31",
            attribution="NASA GPM IMERG",
        )
        session.add_all([ds, area, job, rain_missing, ev, prov])
        session.commit()

        stored_rain = session.query(RainfallObservation).first()
        assert stored_rain is not None
        assert stored_rain.rainfall_24h_mm is None
        assert stored_rain.rainfall_15d_mm is None
        assert stored_rain.missing_24h is True
        stored_ev = session.query(LandslideEvent).first()
        assert stored_ev is not None
        assert stored_ev.within_pilot_boundary is True

    engine.dispose()

    # 3. Downgrade cleanly to base
    command.downgrade(alembic_cfg, "base")
    engine_after = build_engine(db_url)
    tables_after = set(inspect(engine_after).get_table_names())
    assert expected_tables.isdisjoint(tables_after)
    engine_after.dispose()
