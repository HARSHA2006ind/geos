"""Add GEOS 2.0 full platform tables (forecasts, infrastructure, ML registry, auth/RBAC, field reports, experimental alerts, monitoring, regional coverage, audit logs).

Revision ID: 0003_geos_v2_full_platform
Revises: 0002_landslide_events_rainfall
Create Date: 2026-11-23 11:15:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0003_geos_v2_full_platform"
down_revision = "0002_landslide_events_rainfall"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _geom_col(geom_type: str = "POINT") -> sa.types.TypeEngine:
    return (
        Geometry(geometry_type=geom_type, srid=4326, spatial_index=True)
        if _is_postgres()
        else sa.Text()
    )


def upgrade() -> None:
    op.create_table(
        "dataset_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.String(length=80), sa.ForeignKey("dataset_registry.id"), nullable=False),
        sa.Column("version_tag", sa.String(length=120), nullable=False),
        sa.Column("release_timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("dataset_id", "version_tag", name="uq_dataset_version_tag"),
    )
    op.create_index("ix_dataset_versions_dataset_id", "dataset_versions", ["dataset_id"])

    op.create_table(
        "weather_forecasts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False),
        sa.Column("provider", sa.String(length=120), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("init_time_utc", sa.String(length=48), nullable=False),
        sa.Column("valid_time_utc", sa.String(length=48), nullable=False),
        sa.Column("horizon_hours", sa.Integer(), nullable=False),
        sa.Column("spatial_resolution_deg", sa.Float(), nullable=False),
        sa.Column("rain_accum_mm", sa.Float(), nullable=True),
        sa.Column("temp_2m_mean_c", sa.Float(), nullable=True),
        sa.Column("rh_2m_mean_pct", sa.Float(), nullable=True),
        sa.Column("pwat_mean_mm", sa.Float(), nullable=True),
        sa.Column("missing_values_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("data_role", sa.String(length=48), nullable=False, server_default="experimental_forecast_only"),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "study_area_slug", "provider", "init_time_utc", "horizon_hours",
            name="uq_weather_forecast_init_horizon",
        ),
    )
    op.create_index("ix_weather_forecasts_study_area_slug", "weather_forecasts", ["study_area_slug"])
    op.create_index("ix_weather_forecasts_init_time_utc", "weather_forecasts", ["init_time_utc"])

    op.create_table(
        "landslide_event_evidence",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("landslide_event_id", sa.Integer(), sa.ForeignKey("landslide_events.id"), nullable=False),
        sa.Column("evidence_type", sa.String(length=64), nullable=False),
        sa.Column("source_reference", sa.Text(), nullable=False),
        sa.Column("positional_error_m", sa.Float(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_landslide_event_evidence_event_id", "landslide_event_evidence", ["landslide_event_id"])

    op.create_table(
        "infrastructure_assets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False),
        sa.Column("source_provider", sa.String(length=80), nullable=False),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=48), nullable=False),
        sa.Column("subtype", sa.String(length=64), nullable=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geom", _geom_col("GEOMETRY"), nullable=True),
        sa.Column("population_tag", sa.Integer(), nullable=True),
        sa.Column("attributes_json", sa.JSON(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_provider", "external_id", name="uq_infra_provider_ext_id"),
    )
    op.create_index("ix_infrastructure_assets_study_area_slug", "infrastructure_assets", ["study_area_slug"])
    op.create_index("ix_infrastructure_assets_category", "infrastructure_assets", ["category"])

    op.create_table(
        "model_registry",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("algorithm", sa.String(length=64), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("problem_type", sa.String(length=64), nullable=False),
        sa.Column("track", sa.String(length=48), nullable=False),
        sa.Column("validated_for_production", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("promoted_to_inference", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False),
        sa.Column("artifact_path", sa.Text(), nullable=True),
        sa.Column("feature_list_json", sa.JSON(), nullable=True),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("model_name", "version", name="uq_model_name_version"),
    )
    op.create_index("ix_model_registry_model_name", "model_registry", ["model_name"])

    op.create_table(
        "validation_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("model_registry.id"), nullable=False),
        sa.Column("validation_scheme", sa.String(length=120), nullable=False),
        sa.Column("metrics_json", sa.JSON(), nullable=False),
        sa.Column("shap_summary_json", sa.JSON(), nullable=True),
        sa.Column("passed_production_gate", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_validation_results_model_id", "validation_results", ["model_id"])

    op.create_table(
        "model_predictions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("model_registry.id"), nullable=True),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geom", _geom_col("POINT"), nullable=True),
        sa.Column("landslide_probability", sa.Float(), nullable=True),
        sa.Column("validation_status", sa.String(length=64), nullable=False, server_default="unavailable_model_not_validated"),
        sa.Column("uncertainty_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_model_predictions_study_area_slug", "model_predictions", ["study_area_slug"])

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=64), nullable=False, unique=True),
        sa.Column("email", sa.String(length=160), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="public_viewer"),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_role", "users", ["role"])

    op.create_table(
        "field_reports",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False, server_default="dima-hasao"),
        sa.Column("location_name", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("geom", _geom_col("POINT"), nullable=True),
        sa.Column("within_pilot_boundary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("observed_at_utc", sa.String(length=48), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("severity_observation", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("road_obstruction", sa.String(length=64), nullable=False, server_default="unknown"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("photo_filename", sa.String(length=160), nullable=True),
        sa.Column("photo_mime", sa.String(length=64), nullable=True),
        sa.Column("photo_size_bytes", sa.Integer(), nullable=True),
        sa.Column("photo_sha256", sa.String(length=64), nullable=True),
        sa.Column("verification_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("submitted_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_field_reports_study_area_slug", "field_reports", ["study_area_slug"])
    op.create_index("ix_field_reports_verification_status", "field_reports", ["verification_status"])

    op.create_table(
        "experimental_alerts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("classification", sa.String(length=48), nullable=False, server_default="EXPERIMENTAL_RESEARCH_DRAFT"),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False, server_default="dima-hasao"),
        sa.Column("title", sa.String(length=220), nullable=False),
        sa.Column("geographic_area", sa.String(length=200), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("severity_tier", sa.String(length=32), nullable=False),
        sa.Column("severity_rationale", sa.Text(), nullable=False),
        sa.Column("hazard_evidence_json", sa.JSON(), nullable=False),
        sa.Column("source_timestamps_json", sa.JSON(), nullable=False),
        sa.Column("affected_infrastructure_json", sa.JSON(), nullable=False),
        sa.Column("inspection_priorities_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="draft"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("dry_run_notifications_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_experimental_alerts_study_area_slug", "experimental_alerts", ["study_area_slug"])
    op.create_index("ix_experimental_alerts_status", "experimental_alerts", ["status"])

    op.create_table(
        "monitoring_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_name", sa.String(length=80), nullable=False),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False, server_default="dima-hasao"),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observed_rainfall_latest_date", sa.String(length=32), nullable=True),
        sa.Column("observed_rainfall_stale", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("forecast_init_time_utc", sa.String(length=48), nullable=True),
        sa.Column("forecast_stale", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("summary_json", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
    )
    op.create_index("ix_monitoring_runs_job_name", "monitoring_runs", ["job_name"])

    op.create_table(
        "regional_coverage",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("state_code", sa.String(length=16), nullable=False, unique=True),
        sa.Column("state_name", sa.String(length=80), nullable=False, unique=True),
        sa.Column("pilot_district", sa.String(length=120), nullable=True),
        sa.Column("region_configured", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("environmental_data_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("landslide_inventory_available", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("model_validated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("experimental_monitoring_active", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("center_lat", sa.Float(), nullable=False),
        sa.Column("center_lon", sa.Float(), nullable=False),
        sa.Column("coverage_notes", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("actor_username", sa.String(length=64), nullable=True),
        sa.Column("actor_role", sa.String(length=32), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=80), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    for tbl in (
        "audit_logs",
        "regional_coverage",
        "monitoring_runs",
        "experimental_alerts",
        "field_reports",
        "users",
        "model_predictions",
        "validation_results",
        "model_registry",
        "infrastructure_assets",
        "landslide_event_evidence",
        "weather_forecasts",
        "dataset_versions",
    ):
        op.drop_table(tbl)
