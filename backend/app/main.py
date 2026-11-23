"""
GeoResilience-NER 2.0 — FastAPI Backend Application.
Provides verified read-only environmental data, dataset provenance registry,
pilot administrative boundary, observed rainfall history, and landslide inventory
discovery status. Never fabricates landslide probabilities or missing observations.
"""
from __future__ import annotations

import json
import logging
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from backend.app.config import Settings, get_settings
from backend.app.db import check_database_health
from backend.app.logging_config import configure_logging
from backend.app.schemas import (
    DatasetRegistryItem,
    HealthResponse,
    PointEnvironmentResponse,
    RainfallHistoryResponse,
)
from backend.app.services.hazard_engine import get_cached_quality_gate
from backend.app.services.rainfall_service import PilotRainfallService
from backend.app.services.raster_service import PilotRasterService

logger = logging.getLogger("georesilience.api")
_JSON_CACHE_LOCK = threading.RLock()
_JSON_FILE_CACHE: dict[str, tuple[int, Any]] = {}


def _read_cached_json(path: Path) -> Any:
    key = str(path.resolve())
    mtime_ns = path.stat().st_mtime_ns
    with _JSON_CACHE_LOCK:
        hit = _JSON_FILE_CACHE.get(key)
        if hit and hit[0] == mtime_ns:
            return hit[1]
        data = json.loads(path.read_text(encoding="utf-8"))
        _JSON_FILE_CACHE[key] = (mtime_ns, data)
        return data


def create_app(settings_override: Settings | None = None) -> FastAPI:
    settings = settings_override or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Phase 0–4 verified environmental data API for GeoResilience-NER 2.0 "
            "(Dima Hasao, Assam pilot). Serves real Copernicus DEM GLO-30 elevation/slope/aspect, "
            "NASA GPM IMERG daily precipitation, and ESA WorldCover 2021 land cover."
        ),
    )

    app.add_middleware(GZipMiddleware, minimum_size=1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )

    pilot_dir: Path = settings.pilot_data_dir
    raster_service = PilotRasterService(pilot_dir)
    rainfall_service = PilotRainfallService(pilot_dir)

    from backend.app.routers_v2 import build_v2_router

    app.include_router(
        build_v2_router(
            settings=settings,
            raster_service=raster_service,
            rainfall_service=rainfall_service,
        )
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled backend error on %s", request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_server_error",
                "message": "An unexpected server error occurred while processing the environmental query.",
            },
        )

    @app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
    def health_check() -> HealthResponse:
        artifacts = {
            "dima_hasao_boundary": (pilot_dir / "dima_hasao_boundary.geojson").exists(),
            "copernicus_dem_30m_core": (pilot_dir / "haflong_jatinga_copernicus_dem_30m.tif").exists(),
            "copernicus_dem_district": (pilot_dir / "dima_hasao_dem_utm46n.tif").exists(),
            "slope_raster": (pilot_dir / "dima_hasao_slope_deg_utm46n.tif").exists(),
            "aspect_raster": (pilot_dir / "dima_hasao_aspect_deg_utm46n.tif").exists(),
            "worldcover_2021": (pilot_dir / "dima_hasao_worldcover_2021_utm46n.tif").exists(),
            "gpm_imerg_rainfall": (pilot_dir / "dima_hasao_rainfall_imerg.json").exists(),
            "landslide_inventory_discovery": (pilot_dir / "landslide_inventory_discovery.json").exists(),
        }
        all_core_present = all(artifacts.values())
        return HealthResponse(
            status="operational" if all_core_present else "degraded_missing_artifacts",
            service=settings.app_name,
            version=settings.app_version,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
            database=check_database_health(),
            pilot_artifacts=artifacts,
        )

    @app.get("/api/v1/datasets", response_model=list[DatasetRegistryItem], tags=["Datasets"])
    def list_datasets() -> list[DatasetRegistryItem]:
        items: list[DatasetRegistryItem] = []

        boundary = raster_service.get_boundary_geojson()
        if boundary and boundary.get("metadata"):
            bm = boundary["metadata"]
            items.append(
                DatasetRegistryItem(
                    dataset_id="osm-dima-hasao-boundary",
                    name=bm["dataset_name"],
                    category="administrative_boundary",
                    product_version=f"OSM {bm.get('osm_type', 'relation')}/{bm.get('osm_id', 'unknown')}",
                    crs=bm["crs"],
                    resolution_m=None,
                    observation_period="Current OSM snapshot",
                    processing_timestamp=bm.get("processing_timestamp"),
                    available=True,
                    requires_credentials=False,
                    source_url=bm["source_url"],
                    attribution=bm["attribution"],
                    limitations=bm.get("limitations"),
                )
            )

        dem = raster_service.get_dem_metadata()
        if dem:
            items.append(
                DatasetRegistryItem(
                    dataset_id=dem["dataset_id"],
                    name=dem["dataset_name"],
                    category="elevation_and_terrain",
                    product_version=dem["product_version"],
                    crs=dem["derived_metric_crs"],
                    resolution_m=dem["native_resolution_m"],
                    observation_period=dem["observation_period"],
                    processing_timestamp=dem.get("processing_timestamp"),
                    available=(pilot_dir / dem["district_dem_file"]).exists(),
                    requires_credentials=False,
                    source_url=(dem.get("source_tiles") or [{}])[0].get("url", ""),
                    attribution=dem["attribution"],
                    limitations=dem.get("limitations"),
                )
            )

        rain = rainfall_service.get_history()
        if rain:
            items.append(
                DatasetRegistryItem(
                    dataset_id=rain.dataset_id,
                    name=rain.dataset_name,
                    category="precipitation",
                    product_version=rain.product_version,
                    crs="EPSG:4326",
                    resolution_m=round(rain.spatial_resolution_deg * 111_000.0, 1),
                    observation_period=f"{rain.interval_start} to {rain.interval_end}",
                    processing_timestamp=rain.processing_timestamp,
                    available=True,
                    requires_credentials=False,
                    source_url=rain.source_url,
                    attribution=rain.attribution,
                    limitations=rain.missing_data_policy,
                )
            )

        wc = raster_service.get_worldcover_metadata()
        if wc:
            items.append(
                DatasetRegistryItem(
                    dataset_id=wc["dataset_id"],
                    name=wc["dataset_name"],
                    category="land_cover",
                    product_version=wc["product_version"],
                    crs=wc["exported_crs"],
                    resolution_m=wc["native_resolution_m"],
                    observation_period=wc["observation_period"],
                    processing_timestamp=wc.get("processing_timestamp"),
                    available=(pilot_dir / wc["raster_file"]).exists(),
                    requires_credentials=False,
                    source_url=(wc.get("source_tiles") or [{}])[0].get("url", ""),
                    attribution=wc["attribution"],
                    limitations=wc.get("uncertainty_and_limitations"),
                )
            )

        extra_manifests = [
            (
                "soilgrids_metadata.json",
                "isric-soilgrids-2-0",
                "ISRIC SoilGrids 2.0 (Dima Hasao 250m)",
                "soil",
                "EPSG:32646",
                250.0,
                "Static reference (2020)",
                "https://files.isric.org/soilgrids/latest/data/",
                "ISRIC — World Soil Information (SoilGrids 2.0, CC-BY-4.0)",
            ),
            (
                "ndvi_metadata.json",
                "sentinel2-l2a-ndvi-2024",
                "Sentinel-2 L2A Dry-Season NDVI Composite (2024)",
                "vegetation",
                "EPSG:32646",
                90.0,
                "2024-02-01 to 2024-04-30",
                "https://earth-search.aws.element84.com/v1",
                "European Space Agency Copernicus Sentinel-2 L2A (via Element84 Earth Search)",
            ),
            (
                "osm_infrastructure_metadata.json",
                "osm-dima-hasao-transport",
                "OSM Dima Hasao Roads & Railways Network",
                "infrastructure",
                "EPSG:4326",
                90.0,
                "Current OSM snapshot",
                "https://overpass-api.de/api/interpreter",
                "© OpenStreetMap contributors (ODbL 1.0)",
            ),
        ]
        for fname, fallback_id, fallback_name, cat, crs, res_m, period, fallback_url, fallback_attr in extra_manifests:
            mp = pilot_dir / fname
            if mp.exists():
                md = json.loads(mp.read_text(encoding="utf-8"))
                file_ts = datetime.fromtimestamp(mp.stat().st_mtime, tz=timezone.utc).isoformat()
                items.append(
                    DatasetRegistryItem(
                        dataset_id=md.get("dataset_id") or fallback_id,
                        name=md.get("dataset_name") or fallback_name,
                        category=cat,
                        product_version=md.get("product_version") or "v1",
                        crs=md.get("crs") or crs,
                        resolution_m=md.get("native_resolution_m") or res_m,
                        observation_period=md.get("observation_period") or period,
                        processing_timestamp=md.get("processing_timestamp") or md.get("generated_at_utc") or file_ts,
                        available=True,
                        requires_credentials=False,
                        source_url=md.get("source_url") or md.get("endpoint") or fallback_url,
                        attribution=md.get("attribution") or fallback_attr,
                        limitations=md.get("limitations"),
                    )
                )

        fac_path = pilot_dir / "dima_hasao_osm_facilities.geojson"
        if fac_path.exists():
            fmd = (json.loads(fac_path.read_text(encoding="utf-8"))).get("metadata", {})
            fac_ts = datetime.fromtimestamp(fac_path.stat().st_mtime, tz=timezone.utc).isoformat()
            items.append(
                DatasetRegistryItem(
                    dataset_id=fmd.get("dataset_id", "osm-dima-hasao-facilities"),
                    name=fmd.get("dataset_name", "OSM Dima Hasao Facilities, Settlements & Bridges"),
                    category="infrastructure",
                    product_version=fmd.get("product_version", "OSM snapshot"),
                    crs=fmd.get("crs", "EPSG:4326"),
                    resolution_m=None,
                    observation_period="Current OSM snapshot",
                    processing_timestamp=fmd.get("processing_timestamp") or fac_ts,
                    available=True,
                    requires_credentials=False,
                    source_url=fmd.get("source_url", "https://overpass-api.de/api/interpreter"),
                    attribution=fmd.get("attribution", "© OpenStreetMap contributors (ODbL 1.0)"),
                    limitations=fmd.get("limitations"),
                )
            )

        gsi_path = pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json"
        if gsi_path.exists():
            gmd = json.loads(gsi_path.read_text(encoding="utf-8"))
            gsi_ts = datetime.fromtimestamp(gsi_path.stat().st_mtime, tz=timezone.utc).isoformat()
            items.append(
                DatasetRegistryItem(
                    dataset_id="gsi-bhusanket-dima-hasao",
                    name="GSI Bhusanket Public Landslide Inventory (Dima Hasao)",
                    category="landslide_inventory",
                    product_version="GSI Bhusanket Public GetData API",
                    crs="EPSG:4326",
                    resolution_m=None,
                    observation_period="1998–2026 (mixed precision)",
                    processing_timestamp=gmd.get("retrieved_at_utc") or gsi_ts,
                    available=True,
                    requires_credentials=False,
                    source_url=gmd.get("source_url", "https://bhusanket.gsi.gov.in"),
                    attribution=gmd.get("attribution", "Geological Survey of India (GSI)"),
                    limitations="Point centroids without explicit GPS error radius; 77.8% transport-corridor bias; polygon service token-gated.",
                )
            )

        gfs_path = pilot_dir.parent / "experimental" / "dima_hasao_gfs_forecast_eval.json"
        if gfs_path.exists():
            gfs = json.loads(gfs_path.read_text(encoding="utf-8"))
            gfs_ts = datetime.fromtimestamp(gfs_path.stat().st_mtime, tz=timezone.utc).isoformat()
            items.append(
                DatasetRegistryItem(
                    dataset_id="dynamical-noaa-gfs-forecast",
                    name="NOAA GFS 0.25° Experimental Forecast (via Dynamical.org Zarr v3)",
                    category="weather_forecast_experimental",
                    product_version=f"GFS init {gfs.get('init_time_utc', 'latest')}",
                    crs="EPSG:4326",
                    resolution_m=27750.0,
                    observation_period="0–72h forward forecast (NOT measured rainfall)",
                    processing_timestamp=gfs.get("retrieved_at_utc") or gfs_ts,
                    available=True,
                    requires_credentials=False,
                    source_url=gfs.get("source_url", "https://data.dynamical.org/noaa/gfs/forecast/latest.zarr"),
                    attribution="NOAA NCEP GFS redistributed by Dynamical.org (CC-BY-4.0)",
                    limitations="Experimental 0.25 deg global NWP forecast only; smooths steep orographic peaks; never labeled observed rainfall.",
                )
            )

        return items

    @app.get("/api/v1/pilot/boundary", tags=["Pilot GIS"])
    def get_pilot_boundary() -> dict[str, Any]:
        boundary = raster_service.get_boundary_geojson()
        if boundary is None:
            raise HTTPException(
                status_code=503,
                detail="Pilot boundary GeoJSON has not been ingested yet.",
            )
        dem_meta = raster_service.get_dem_metadata()
        wc_meta = raster_service.get_worldcover_metadata()
        return {
            "geojson": boundary,
            "terrain_summary": dem_meta,
            "land_cover_summary": wc_meta,
        }

    @app.get(
        "/api/v1/environment/point",
        response_model=PointEnvironmentResponse,
        tags=["Environmental Data"],
    )
    def get_point_environment(
        lat: float = Query(..., ge=-90.0, le=90.0, description="WGS84 latitude (EPSG:4326)"),
        lon: float = Query(..., ge=-180.0, le=180.0, description="WGS84 longitude (EPSG:4326)"),
    ) -> PointEnvironmentResponse:
        within_boundary = raster_service.is_within_pilot_boundary(lat, lon)
        within_raster, terrain, land_cover = raster_service.sample_point(lat, lon)
        rainfall = rainfall_service.get_snapshot(within_pilot=(within_boundary or within_raster))

        return PointEnvironmentResponse(
            coordinates={"lat": round(lat, 6), "lon": round(lon, 6)},
            within_pilot_boundary=within_boundary,
            within_raster_bounds=within_raster,
            terrain=terrain,
            land_cover=land_cover,
            rainfall=rainfall,
            missing_data_indicators={
                "elevation": terrain.missing_elevation,
                "slope_and_aspect": terrain.missing_slope_aspect,
                "land_cover": land_cover.missing_land_cover,
                "rainfall_24h": rainfall.missing_24h,
                "rainfall_72h": rainfall.missing_72h,
                "landslide_ml_probability": True,
                "factor_of_safety": True,
            },
            response_generated_at_utc=datetime.now(timezone.utc).isoformat(),
        )

    @app.get(
        "/api/v1/environment/rainfall/history",
        response_model=RainfallHistoryResponse,
        tags=["Environmental Data"],
    )
    def get_rainfall_history(
        start_date: str | None = Query(
            default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Optional YYYY-MM-DD start filter"
        ),
        end_date: str | None = Query(
            default=None, pattern=r"^\d{4}-\d{2}-\d{2}$", description="Optional YYYY-MM-DD end filter"
        ),
    ) -> RainfallHistoryResponse:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must not be later than end_date.")
        history = rainfall_service.get_history(start_date=start_date, end_date=end_date)
        if history is None:
            raise HTTPException(
                status_code=503,
                detail="NASA GPM IMERG rainfall observations have not been ingested yet.",
            )
        return history

    @app.get("/api/v1/inventory/discovery", tags=["Landslide Inventory"])
    def get_inventory_discovery() -> dict[str, Any]:
        p = pilot_dir / "landslide_inventory_discovery.json"
        if not p.exists():
            raise HTTPException(
                status_code=503,
                detail="Landslide inventory discovery report has not been generated yet.",
            )
        return _read_cached_json(p)

    @app.get("/api/v1/landslides/coolr", tags=["Landslide Inventory"])
    def get_coolr_landslides(
        pilot_only: bool = Query(
            default=False,
            description="When true, returns only events inside the exact Dima Hasao District polygon.",
        ),
    ) -> dict[str, Any]:
        p = pilot_dir / "dima_hasao_landslides_coolr.json"
        if not p.exists():
            raise HTTPException(
                status_code=503,
                detail="NASA COOLR landslide inventory has not been ingested yet.",
            )
        doc = dict(_read_cached_json(p))
        if pilot_only:
            doc["records"] = [r for r in doc.get("records", []) if r.get("within_pilot_boundary")]
        return doc

    @app.get("/api/v1/environment/rainfall/multiyear", tags=["Environmental Data"])
    def get_multiyear_rainfall(
        start_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        end_date: str | None = Query(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
        include_observations: bool = Query(default=False),
    ) -> dict[str, Any]:
        if start_date and end_date and start_date > end_date:
            raise HTTPException(status_code=400, detail="start_date must not be later than end_date.")
        p = pilot_dir / "dima_hasao_rainfall_multiyear.json"
        if not p.exists():
            raise HTTPException(
                status_code=503,
                detail="Multi-year historical rainfall archive has not been ingested yet.",
            )
        doc = dict(_read_cached_json(p))
        obs = doc.get("observations", [])
        if start_date:
            obs = [o for o in obs if o["date"] >= start_date]
        if end_date:
            obs = [o for o in obs if o["date"] <= end_date]
        if include_observations or start_date or end_date:
            doc["observations"] = obs
        else:
            doc["observations"] = obs[-90:]
            doc["observations_truncated_note"] = (
                "Showing last 90 calendar days by default; pass start_date/end_date or include_observations=true for full 2015–2024 series."
            )
        return doc

    @app.get("/api/v1/quality-gate", tags=["Data Quality & ML Readiness"])
    def get_quality_gate() -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(get_cached_quality_gate(pilot_dir))

    @app.get("/api/v1/features/quality", tags=["Data Quality & ML Readiness"])
    def get_spatial_feature_quality() -> dict[str, Any]:
        p = pilot_dir / "spatial_data_quality_inventory.json"
        if not p.exists():
            raise HTTPException(
                status_code=503,
                detail="Spatial data quality inventory has not been generated yet.",
            )
        return _read_cached_json(p)

    @app.get("/api/v1/rainfall/imerg-v07/catalog", tags=["Environmental Data"])
    def get_imerg_v07_catalog() -> dict[str, Any]:
        p = pilot_dir / "imerg_v07_cmr_catalog.json"
        if not p.exists():
            raise HTTPException(
                status_code=503,
                detail="NASA IMERG V07B/V07C CMR catalog has not been generated yet.",
            )
        return _read_cached_json(p)

    @app.get("/api/v1/landslides/gsi-bhusanket", tags=["Landslide Inventory"])
    def get_gsi_bhusanket_landslides(
        pilot_only: bool = Query(
            default=False,
            description="When true, returns only GSI Bhusanket records inside the exact Dima Hasao polygon.",
        ),
    ) -> dict[str, Any]:
        p = pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json"
        if not p.exists():
            raise HTTPException(
                status_code=503,
                detail="GSI Bhusanket public landslide inventory has not been ingested yet.",
            )
        doc = dict(_read_cached_json(p))
        if pilot_only:
            doc["records"] = [r for r in doc.get("records", []) if r.get("within_pilot_boundary")]
        return doc

    return app


app = create_app()

