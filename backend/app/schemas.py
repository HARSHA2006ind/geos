"""Pydantic v2 API schemas enforcing explicit provenance, timestamps, and missing-data indicators."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DatasetProvenance(BaseModel):
    dataset_id: str
    dataset_name: str
    product_version: str
    source_url: str
    crs: str
    resolution_m: float | None = None
    observation_period: str
    processing_timestamp: str | None = None
    attribution: str
    limitations: str | None = None


class TerrainObservation(BaseModel):
    elevation_m: float | None = None
    elevation_resolution_m: float | None = None
    slope_deg: float | None = None
    aspect_deg: float | None = None
    aspect_cardinal: str | None = None
    slope_aspect_resolution_m: float | None = None
    missing_elevation: bool
    missing_slope_aspect: bool
    provenance: DatasetProvenance | None = None


class LandCoverObservation(BaseModel):
    class_code: int | None = None
    class_label: str | None = None
    missing_land_cover: bool
    provenance: DatasetProvenance | None = None


class RainfallSnapshot(BaseModel):
    latest_observation_date: str | None = None
    latest_observation_timestamp_utc: str | None = None
    rainfall_24h_mm: float | None = None
    rainfall_72h_mm: float | None = None
    max_24h_in_window_mm: float | None = None
    max_72h_in_window_mm: float | None = None
    window_start: str | None = None
    window_end: str | None = None
    valid_days_in_window: int = 0
    missing_days_in_window: int = 0
    missing_24h: bool = True
    missing_72h: bool = True
    latency_info: str | None = None
    provenance: DatasetProvenance | None = None


class PointEnvironmentResponse(BaseModel):
    coordinates: dict[str, float]
    crs: str = "EPSG:4326"
    study_area: str = "Dima Hasao District, Assam (Pilot)"
    within_pilot_boundary: bool
    within_raster_bounds: bool
    scientific_disclaimer: str = (
        "Verified environmental observations only. No landslide susceptibility or failure "
        "probability is generated because no spatially validated ML model is deployed yet."
    )
    landslide_probability: None = Field(
        default=None,
        description="Always null in Phase 0–4; reserved until a spatially cross-validated ML model is trained.",
    )
    terrain: TerrainObservation
    land_cover: LandCoverObservation
    rainfall: RainfallSnapshot
    missing_data_indicators: dict[str, bool]
    response_generated_at_utc: str


class DailyRainfallPoint(BaseModel):
    date: str
    observation_timestamp_utc: str
    rainfall_24h_mm: float | None
    rainfall_72h_mm: float | None
    missing_24h: bool
    missing_72h: bool


class RainfallHistoryResponse(BaseModel):
    study_area: str
    dataset_id: str
    dataset_name: str
    product_version: str
    spatial_resolution_deg: float
    latency_info: str
    interval_start: str
    interval_end: str
    total_days: int
    valid_observation_days: int
    missing_observation_days: int
    max_24h_mm: float | None
    max_72h_mm: float | None
    missing_data_policy: str
    processing_timestamp: str
    attribution: str
    source_url: str
    observations: list[DailyRainfallPoint]


class DatasetRegistryItem(BaseModel):
    dataset_id: str
    name: str
    category: str
    product_version: str
    crs: str
    resolution_m: float | None = None
    observation_period: str
    processing_timestamp: str | None = None
    available: bool
    requires_credentials: bool = False
    source_url: str
    attribution: str
    limitations: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    timestamp_utc: str
    database: dict[str, Any]
    pilot_artifacts: dict[str, bool]
    ml_model_status: str = "not_trained_phase_1_data_foundation"
