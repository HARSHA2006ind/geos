"""Add landslide_events table and 7d/15d antecedent rainfall columns

Revision ID: 0002_landslide_events_rainfall
Revises: 0001_initial_schema
Create Date: 2026-11-23 09:50:00.000000+00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from geoalchemy2 import Geometry

revision = "0002_landslide_events_rainfall"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    point_col = (
        Geometry(geometry_type="POINT", srid=4326, spatial_index=True)
        if _is_postgres()
        else sa.Text()
    )

    with op.batch_alter_table("rainfall_observations") as batch_op:
        batch_op.add_column(sa.Column("rainfall_7d_mm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("rainfall_15d_mm", sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column("missing_7d", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column("missing_15d", sa.Boolean(), nullable=False, server_default=sa.true())
        )
        batch_op.add_column(
            sa.Column(
                "data_role",
                sa.String(length=32),
                nullable=False,
                server_default="historical_archive",
            )
        )

    op.create_table(
        "landslide_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_provider", sa.String(length=80), nullable=False),
        sa.Column("external_event_id", sa.String(length=120), nullable=False),
        sa.Column("dedup_key", sa.String(length=160), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column(
            "event_date_precision",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("event_title", sa.Text(), nullable=True),
        sa.Column("location_description", sa.Text(), nullable=True),
        sa.Column("admin_division_name", sa.String(length=160), nullable=True),
        sa.Column("country_name", sa.String(length=80), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("geom", point_col, nullable=True),
        sa.Column("location_accuracy_raw", sa.String(length=64), nullable=True),
        sa.Column("location_accuracy_m", sa.Float(), nullable=True),
        sa.Column("spatial_zone", sa.String(length=32), nullable=False),
        sa.Column(
            "within_pilot_boundary",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("landslide_category", sa.String(length=80), nullable=True),
        sa.Column("landslide_trigger", sa.String(length=80), nullable=True),
        sa.Column("landslide_size", sa.String(length=64), nullable=True),
        sa.Column("landslide_setting", sa.String(length=80), nullable=True),
        sa.Column("fatality_count", sa.Integer(), nullable=True),
        sa.Column("injury_count", sa.Integer(), nullable=True),
        sa.Column("source_name", sa.Text(), nullable=True),
        sa.Column("source_link", sa.Text(), nullable=True),
        sa.Column("training_usability", sa.String(length=48), nullable=False),
        sa.Column("usability_reason", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", sa.JSON(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "source_provider",
            "external_event_id",
            name="uq_landslide_provider_event_id",
        ),
        sa.UniqueConstraint("dedup_key", name="uq_landslide_dedup_key"),
    )
    op.create_index("ix_landslide_events_source_provider", "landslide_events", ["source_provider"])
    op.create_index("ix_landslide_events_external_event_id", "landslide_events", ["external_event_id"])
    op.create_index("ix_landslide_events_event_date", "landslide_events", ["event_date"])
    op.create_index("ix_landslide_events_spatial_zone", "landslide_events", ["spatial_zone"])
    op.create_index(
        "ix_landslide_events_within_pilot_boundary",
        "landslide_events",
        ["within_pilot_boundary"],
    )
    op.create_index("ix_landslide_events_training_usability", "landslide_events", ["training_usability"])


def downgrade() -> None:
    op.drop_index("ix_landslide_events_training_usability", table_name="landslide_events")
    op.drop_index("ix_landslide_events_within_pilot_boundary", table_name="landslide_events")
    op.drop_index("ix_landslide_events_spatial_zone", table_name="landslide_events")
    op.drop_index("ix_landslide_events_event_date", table_name="landslide_events")
    op.drop_index("ix_landslide_events_external_event_id", table_name="landslide_events")
    op.drop_index("ix_landslide_events_source_provider", table_name="landslide_events")
    op.drop_table("landslide_events")

    with op.batch_alter_table("rainfall_observations") as batch_op:
        batch_op.drop_column("data_role")
        batch_op.drop_column("missing_15d")
        batch_op.drop_column("missing_7d")
        batch_op.drop_column("rainfall_15d_mm")
        batch_op.drop_column("rainfall_7d_mm")
