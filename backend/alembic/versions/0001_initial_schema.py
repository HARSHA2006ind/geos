"""Initial PostGIS-ready schema for GeoResilience-NER 2.0.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-11-23 09:00:00+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    if _is_postgres():
        op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "dataset_registry",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=160), nullable=False),
        sa.Column("product_version", sa.String(length=160), nullable=False),
        sa.Column("crs", sa.String(length=64), nullable=False),
        sa.Column("native_resolution_m", sa.Float(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("requires_credentials", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("observation_period", sa.String(length=160), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="available"),
        sa.Column("limitations", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    geom_col_type = (
        Geometry(geometry_type="MULTIPOLYGON", srid=4326, spatial_index=True)
        if _is_postgres()
        else sa.Text()
    )

    op.create_table(
        "study_areas",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=100), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False, server_default="India"),
        sa.Column("crs", sa.String(length=32), nullable=False, server_default="EPSG:4326"),
        sa.Column("area_km2", sa.Float(), nullable=False),
        sa.Column("bbox_wgs84", sa.JSON(), nullable=False),
        sa.Column("geom", geom_col_type, nullable=True),
        sa.Column("source_attribution", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_study_areas_slug", "study_areas", ["slug"], unique=True)

    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.String(length=80), sa.ForeignKey("dataset_registry.id"), nullable=False),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("records_ingested", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("missing_records", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=True),
    )
    op.create_index("ix_ingestion_jobs_dataset_id", "ingestion_jobs", ["dataset_id"])

    op.create_table(
        "rainfall_observations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("study_area_slug", sa.String(length=80), nullable=False),
        sa.Column("dataset_id", sa.String(length=80), sa.ForeignKey("dataset_registry.id"), nullable=False),
        sa.Column("observation_date", sa.Date(), nullable=False),
        sa.Column("observation_timestamp_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rainfall_24h_mm", sa.Float(), nullable=True),
        sa.Column("rainfall_72h_mm", sa.Float(), nullable=True),
        sa.Column("missing_24h", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("missing_72h", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("product_version", sa.String(length=160), nullable=False),
        sa.Column("latency_info", sa.String(length=255), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "study_area_slug",
            "dataset_id",
            "observation_date",
            name="uq_rainfall_area_ds_date",
        ),
    )
    op.create_index("ix_rainfall_observations_study_area_slug", "rainfall_observations", ["study_area_slug"])
    op.create_index("ix_rainfall_observations_dataset_id", "rainfall_observations", ["dataset_id"])
    op.create_index("ix_rainfall_observations_observation_date", "rainfall_observations", ["observation_date"])

    op.create_table(
        "provenance_records",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("dataset_id", sa.String(length=80), sa.ForeignKey("dataset_registry.id"), nullable=False),
        sa.Column("artifact_filename", sa.String(length=255), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("observation_period", sa.String(length=160), nullable=False),
        sa.Column("processing_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=True),
    )
    op.create_index("ix_provenance_records_dataset_id", "provenance_records", ["dataset_id"])


def downgrade() -> None:
    op.drop_index("ix_provenance_records_dataset_id", table_name="provenance_records")
    op.drop_table("provenance_records")
    op.drop_index("ix_rainfall_observations_observation_date", table_name="rainfall_observations")
    op.drop_index("ix_rainfall_observations_dataset_id", table_name="rainfall_observations")
    op.drop_index("ix_rainfall_observations_study_area_slug", table_name="rainfall_observations")
    op.drop_table("rainfall_observations")
    op.drop_index("ix_ingestion_jobs_dataset_id", table_name="ingestion_jobs")
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_study_areas_slug", table_name="study_areas")
    op.drop_table("study_areas")
    op.drop_table("dataset_registry")
