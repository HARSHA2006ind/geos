"""
SQLAlchemy + GeoAlchemy2 ORM models for GeoResilience-NER 2.0.
Uses PostGIS Geometry columns on PostgreSQL and gracefully supports SQLite WKT
during isolated local unit tests via TypeDecorator.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from geoalchemy2 import Geometry
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from backend.app.db import Base


class PostGISOrTextGeometry(TypeDecorator):
    """Stores PostGIS GEOMETRY(geometry_type, srid) on PostgreSQL and WKT text on SQLite."""

    impl = Text
    cache_ok = True

    def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326) -> None:
        super().__init__()
        self.geometry_type = geometry_type
        self.srid = srid

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(
                Geometry(geometry_type=self.geometry_type, srid=self.srid, spatial_index=True)
            )
        return dialect.type_descriptor(Text())


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DatasetRegistry(Base):
    __tablename__ = "dataset_registry"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(160), nullable=False)
    product_version: Mapped[str] = mapped_column(String(160), nullable=False)
    crs: Mapped[str] = mapped_column(String(64), nullable=False)
    native_resolution_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    requires_credentials: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observation_period: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="available", nullable=False)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    ingestion_jobs: Mapped[list["IngestionJob"]] = relationship(back_populates="dataset")
    provenance_records: Mapped[list["ProvenanceRecord"]] = relationship(back_populates="dataset")


class StudyArea(Base):
    __tablename__ = "study_areas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    country: Mapped[str] = mapped_column(String(100), default="India", nullable=False)
    crs: Mapped[str] = mapped_column(String(32), default="EPSG:4326", nullable=False)
    area_km2: Mapped[float] = mapped_column(Float, nullable=False)
    bbox_wgs84: Mapped[list[float]] = mapped_column(JSON, nullable=False)
    geom: Mapped[Any] = mapped_column(PostGISOrTextGeometry("MULTIPOLYGON", 4326), nullable=True)
    source_attribution: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_registry.id"), nullable=False, index=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # running, succeeded, failed, blocked
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    records_ingested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    missing_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    dataset: Mapped["DatasetRegistry"] = relationship(back_populates="ingestion_jobs")


class RainfallObservation(Base):
    __tablename__ = "rainfall_observations"
    __table_args__ = (
        UniqueConstraint("study_area_slug", "dataset_id", "observation_date", name="uq_rainfall_area_ds_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_registry.id"), nullable=False, index=True)
    observation_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    observation_timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rainfall_24h_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_72h_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_7d_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    rainfall_15d_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_24h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    missing_72h: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    missing_7d: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    missing_15d: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    data_role: Mapped[str] = mapped_column(String(32), default="historical_archive", nullable=False)
    product_version: Mapped[str] = mapped_column(String(160), nullable=False)
    latency_info: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class LandslideEvent(Base):
    __tablename__ = "landslide_events"
    __table_args__ = (
        UniqueConstraint("source_provider", "external_event_id", name="uq_landslide_provider_event_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_provider: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    event_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    event_date_precision: Mapped[str] = mapped_column(String(32), default="unknown", nullable=False)
    event_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    location_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_division_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    country_name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geom: Mapped[Any] = mapped_column(PostGISOrTextGeometry("POINT", 4326), nullable=True)
    location_accuracy_raw: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location_accuracy_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    spatial_zone: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    within_pilot_boundary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    landslide_category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    landslide_trigger: Mapped[str | None] = mapped_column(String(80), nullable=True)
    landslide_size: Mapped[str | None] = mapped_column(String(64), nullable=True)
    landslide_setting: Mapped[str | None] = mapped_column(String(80), nullable=True)
    fatality_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    injury_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    training_usability: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    usability_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_registry.id"), nullable=False, index=True)
    artifact_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    observation_period: Mapped[str] = mapped_column(String(160), nullable=False)
    processing_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset: Mapped["DatasetRegistry"] = relationship(back_populates="provenance_records")


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    __table_args__ = (
        UniqueConstraint("dataset_id", "version_tag", name="uq_dataset_version_tag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("dataset_registry.id"), nullable=False, index=True)
    version_tag: Mapped[str] = mapped_column(String(120), nullable=False)
    release_timestamp_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class WeatherForecast(Base):
    """Strictly segregated forward meteorological forecast table (never mixed with historical observations)."""

    __tablename__ = "weather_forecasts"
    __table_args__ = (
        UniqueConstraint(
            "study_area_slug",
            "provider",
            "init_time_utc",
            "horizon_hours",
            name="uq_weather_forecast_init_horizon",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(120), nullable=False)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False)
    init_time_utc: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    valid_time_utc: Mapped[str] = mapped_column(String(48), nullable=False)
    horizon_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    spatial_resolution_deg: Mapped[float] = mapped_column(Float, nullable=False)
    rain_accum_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    temp_2m_mean_c: Mapped[float | None] = mapped_column(Float, nullable=True)
    rh_2m_mean_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    pwat_mean_mm: Mapped[float | None] = mapped_column(Float, nullable=True)
    missing_values_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    data_role: Mapped[str] = mapped_column(String(48), default="experimental_forecast_only", nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class LandslideEventEvidence(Base):
    __tablename__ = "landslide_event_evidence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    landslide_event_id: Mapped[int] = mapped_column(ForeignKey("landslide_events.id"), nullable=False, index=True)
    evidence_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_reference: Mapped[str] = mapped_column(Text, nullable=False)
    positional_error_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class InfrastructureAsset(Base):
    __tablename__ = "infrastructure_assets"
    __table_args__ = (
        UniqueConstraint("source_provider", "external_id", name="uq_infra_provider_ext_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    source_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    subtype: Mapped[str | None] = mapped_column(String(64), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geom: Mapped[Any] = mapped_column(PostGISOrTextGeometry("GEOMETRY", 4326), nullable=True)
    population_tag: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attributes_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ModelRegistry(Base):
    __tablename__ = "model_registry"
    __table_args__ = (
        UniqueConstraint("model_name", "version", name="uq_model_name_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    algorithm: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    problem_type: Mapped[str] = mapped_column(String(64), nullable=False)  # static_susceptibility | dynamic_threshold
    track: Mapped[str] = mapped_column(String(48), nullable=False)  # production_candidate | exploratory_research
    validated_for_production: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    promoted_to_inference: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    study_area_slug: Mapped[str] = mapped_column(String(80), nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    feature_list_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    limitations: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ValidationResult(Base):
    __tablename__ = "validation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("model_registry.id"), nullable=False, index=True)
    validation_scheme: Mapped[str] = mapped_column(String(120), nullable=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    shap_summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    passed_production_gate: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ModelPrediction(Base):
    __tablename__ = "model_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_id: Mapped[int | None] = mapped_column(ForeignKey("model_registry.id"), nullable=True, index=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(PostGISOrTextGeometry("POINT", 4326), nullable=True)
    landslide_probability: Mapped[float | None] = mapped_column(Float, nullable=True)
    validation_status: Mapped[str] = mapped_column(String(64), default="unavailable_model_not_validated", nullable=False)
    uncertainty_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(160), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    role: Mapped[str] = mapped_column(String(32), default="public_viewer", nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class FieldReport(Base):
    __tablename__ = "field_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), default="dima-hasao", nullable=False, index=True)
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom: Mapped[Any] = mapped_column(PostGISOrTextGeometry("POINT", 4326), nullable=True)
    within_pilot_boundary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    observed_at_utc: Mapped[str] = mapped_column(String(48), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity_observation: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    road_obstruction: Mapped[str] = mapped_column(String(64), default="unknown", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_filename: Mapped[str | None] = mapped_column(String(160), nullable=True)
    photo_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    photo_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    photo_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False, index=True)
    submitted_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)


class ExperimentalAlert(Base):
    """Strictly segregated research/draft alerts — NEVER official government emergency warnings."""

    __tablename__ = "experimental_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    classification: Mapped[str] = mapped_column(
        String(48), default="EXPERIMENTAL_RESEARCH_DRAFT", nullable=False
    )
    study_area_slug: Mapped[str] = mapped_column(String(80), default="dima-hasao", nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    geographic_area: Mapped[str] = mapped_column(String(200), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    severity_tier: Mapped[str] = mapped_column(String(32), nullable=False)  # LOW | MODERATE | HIGH | CRITICAL
    severity_rationale: Mapped[str] = mapped_column(Text, nullable=False)
    hazard_evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source_timestamps_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    affected_infrastructure_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    inspection_priorities_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False, index=True)
    created_by_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    reviewed_by_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    dry_run_notifications_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class MonitoringRun(Base):
    __tablename__ = "monitoring_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_name: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    study_area_slug: Mapped[str] = mapped_column(String(80), default="dima-hasao", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # succeeded | partial_stale | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_rainfall_latest_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    observed_rainfall_stale: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    forecast_init_time_utc: Mapped[str | None] = mapped_column(String(48), nullable=True)
    forecast_stale: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class RegionalCoverage(Base):
    __tablename__ = "regional_coverage"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    state_code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False, index=True)
    state_name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    pilot_district: Mapped[str | None] = mapped_column(String(120), nullable=True)
    region_configured: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    environmental_data_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    landslide_inventory_available: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    experimental_monitoring_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    center_lat: Mapped[float] = mapped_column(Float, nullable=False)
    center_lon: Mapped[float] = mapped_column(Float, nullable=False)
    coverage_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    actor_username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    actor_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)


