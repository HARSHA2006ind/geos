"""
Phase E & F5/F6 — Server-Side Dynamic Hazard, Spatial Exposure & What-If Scenario Engine.

Separates strictly:
  1. Static susceptibility (explicitly UNAVAILABLE / null until ML Quality Gate passes)
  2. Observed rainfall conditions (NASA GPM IMERG historical/latest + staleness indicator)
  3. Forecast rainfall conditions (NOAA GFS 24h/48h/72h experimental outlook — never labeled measured)
  4. Data & model uncertainty
  5. Infrastructure spatial exposure (real OpenStreetMap roads, railways, bridges, settlements, hospitals, schools)
  6. Research inspection priority (documented experimental reference — NEVER a failure probability or Factor of Safety)
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import threading
import time
from collections import OrderedDict

from backend.app.quality_gate import evaluate_data_quality_gate
from backend.app.services.rainfall_service import PilotRainfallService
from backend.app.services.raster_service import PilotRasterService
from backend.ingestion.fetch_coolr_landslides import haversine_m

EXPERIMENTAL_DIR = Path(__file__).resolve().parents[2] / "data" / "experimental"

_QG_LOCK = threading.RLock()
_QG_CACHE: dict[str, tuple[float, int, Any]] = {}
_GFS_LOCK = threading.RLock()
_GFS_CACHE: dict[str, tuple[int, dict[str, Any]]] = {}


def _pilot_manifest_mtime_ns(pilot_dir: Path) -> int:
    candidates = [
        "dima_hasao_boundary.geojson",
        "dima_hasao_rainfall_multiyear.json",
        "dima_hasao_rainfall_imerg.json",
        "dima_hasao_landslides_gsi_bhusanket.json",
        "dima_hasao_landslides_coolr.json",
        "copernicus_dem_metadata.json",
        "worldcover_metadata.json",
        "soilgrids_metadata.json",
        "ndvi_metadata.json",
    ]
    latest = 0
    for name in candidates:
        p = pilot_dir / name
        if p.exists():
            latest = max(latest, p.stat().st_mtime_ns)
    return latest


def get_cached_quality_gate(pilot_dir: Path, ttl_seconds: float = 120.0) -> Any:
    key = str(pilot_dir.resolve())
    now = time.monotonic()
    mtime_ns = _pilot_manifest_mtime_ns(pilot_dir)
    with _QG_LOCK:
        cached = _QG_CACHE.get(key)
        if cached and (now - cached[0]) < ttl_seconds and cached[1] == mtime_ns:
            return cached[2]
        report = evaluate_data_quality_gate(pilot_dir)
        _QG_CACHE[key] = (now, mtime_ns, report)
        return report


class InfrastructureExposureIndex:
    """Loads authentic OpenStreetMap transport & facility GeoJSONs for fast proximity queries."""

    def __init__(self, pilot_dir: Path) -> None:
        self.pilot_dir = pilot_dir
        self._lock = threading.RLock()
        self._facilities: list[dict[str, Any]] | None = None
        self._facilities_meta: dict[str, Any] = {}
        self._road_anchors: list[dict[str, Any]] | None = None
        self._prox_cache: OrderedDict[tuple[float, float, float], dict[str, Any]] = OrderedDict()

    def _ensure_loaded(self) -> None:
        with self._lock:
            if self._facilities is None:
                fac_path = self.pilot_dir / "dima_hasao_osm_facilities.geojson"
                if fac_path.exists():
                    doc = json.loads(fac_path.read_text(encoding="utf-8"))
                    self._facilities_meta = doc.get("metadata") or {}
                    self._facilities = []
                    for feat in doc.get("features", []):
                        coords = (feat.get("geometry") or {}).get("coordinates")
                        props = feat.get("properties") or {}
                        if isinstance(coords, list) and len(coords) >= 2:
                            self._facilities.append(
                                {
                                    "external_id": props.get("external_id"),
                                    "category": props.get("category"),
                                    "subtype": props.get("subtype"),
                                    "name": props.get("name"),
                                    "named": bool(props.get("named")),
                                    "population_osm_tag": props.get("population_osm_tag"),
                                    "lon": float(coords[0]),
                                    "lat": float(coords[1]),
                                }
                            )
                else:
                    self._facilities = []

            if self._road_anchors is None:
                tr_path = self.pilot_dir / "dima_hasao_osm_transport.geojson"
                self._road_anchors = []
                if tr_path.exists():
                    doc = json.loads(tr_path.read_text(encoding="utf-8"))
                    for feat in doc.get("features", []):
                        geom = feat.get("geometry") or {}
                        props = feat.get("properties") or {}
                        gtype = geom.get("type")
                        coords = geom.get("coordinates") or []
                        sample_pt = None
                        if gtype == "LineString" and coords:
                            sample_pt = coords[len(coords) // 2]
                        elif gtype == "MultiLineString" and coords and coords[0]:
                            sample_pt = coords[0][len(coords[0]) // 2]
                        if sample_pt and len(sample_pt) >= 2:
                            self._road_anchors.append(
                                {
                                    "name": props.get("name") or props.get("ref") or (
                                        f"Railway ({props.get('railway')})" if props.get("railway") else f"Road ({props.get('highway')})"
                                    ),
                                    "ref": props.get("ref"),
                                    "kind": "railway" if props.get("railway") else "road",
                                    "highway_class": props.get("highway") or props.get("railway"),
                                    "lon": float(sample_pt[0]),
                                    "lat": float(sample_pt[1]),
                                }
                            )

    def query_proximity(self, lat: float, lon: float, radius_km: float = 5.0) -> dict[str, Any]:
        cache_key = (round(lat, 5), round(lon, 5), round(radius_km, 2))
        with self._lock:
            hit = self._prox_cache.get(cache_key)
            if hit is not None:
                self._prox_cache.move_to_end(cache_key)
                return hit

        self._ensure_loaded()
        radius_m = radius_km * 1000.0
        dlat_deg = (radius_km / 110.57) * 1.03
        dlon_deg = (radius_km / (111.32 * max(0.2, abs(math.cos(math.radians(lat)))))) * 1.03

        counts = {
            "hospitals_health": 0,
            "schools": 0,
            "settlements": 0,
            "bridges": 0,
            "road_segments": 0,
            "railway_segments": 0,
        }
        nearest_facilities: list[dict[str, Any]] = []
        named_corridors: set[str] = set()
        mapped_osm_population_sum = 0
        settlements_with_pop_tag = 0

        for fac in self._facilities or []:
            if abs(fac["lat"] - lat) > dlat_deg or abs(fac["lon"] - lon) > dlon_deg:
                continue
            d_m = haversine_m(lat, lon, fac["lat"], fac["lon"])
            if d_m <= radius_m:
                cat = fac["category"]
                if cat == "hospital_health":
                    counts["hospitals_health"] += 1
                elif cat == "school":
                    counts["schools"] += 1
                elif cat == "settlement":
                    counts["settlements"] += 1
                    if fac.get("population_osm_tag") is not None:
                        mapped_osm_population_sum += int(fac["population_osm_tag"])
                        settlements_with_pop_tag += 1
                elif cat == "bridge":
                    counts["bridges"] += 1
                nearest_facilities.append({**fac, "distance_km": round(d_m / 1000.0, 2)})

        for seg in self._road_anchors or []:
            if abs(seg["lat"] - lat) > dlat_deg or abs(seg["lon"] - lon) > dlon_deg:
                continue
            d_m = haversine_m(lat, lon, seg["lat"], seg["lon"])
            if d_m <= radius_m:
                if seg["kind"] == "railway":
                    counts["railway_segments"] += 1
                else:
                    counts["road_segments"] += 1
                if seg.get("ref") or (seg.get("name") and not str(seg["name"]).startswith("Road (")):
                    named_corridors.add(str(seg.get("ref") or seg.get("name")))

        nearest_facilities.sort(key=lambda x: x["distance_km"])
        result = {
            "query_radius_km": radius_km,
            "exposure_nature": "estimated_spatial_proximity_not_observed_damage",
            "counts": counts,
            "named_transport_corridors": sorted(named_corridors)[:12],
            "nearest_assets": nearest_facilities[:15],
            "population_exposure_note": (
                f"Only {settlements_with_pop_tag} nearby OSM settlement nodes carry an explicit population tag "
                f"(tagged sum = {mapped_osm_population_sum}). Gridded census/WorldPop exposure is NOT available; "
                "population figures are never fabricated."
            ),
            "source_attribution": self._facilities_meta.get(
                "attribution", "© OpenStreetMap contributors (ODbL 1.0)"
            ),
            "completeness_limitations": self._facilities_meta.get(
                "limitations",
                "OpenStreetMap coverage in rural Northeast India is incomplete; counts represent mapped minimum assets only.",
            ),
        }
        with self._lock:
            self._prox_cache[cache_key] = result
            if len(self._prox_cache) > 512:
                self._prox_cache.popitem(last=False)
        return result

    def district_summary(self) -> dict[str, Any]:
        self._ensure_loaded()
        return {
            "metadata": self._facilities_meta,
            "total_point_assets": len(self._facilities or []),
            "total_transport_segments": len(self._road_anchors or []),
        }


def load_latest_gfs_forecast(experimental_dir: Path = EXPERIMENTAL_DIR) -> dict[str, Any] | None:
    p = experimental_dir / "dima_hasao_gfs_forecast_eval.json"
    if not p.exists():
        return None
    mtime_ns = p.stat().st_mtime_ns
    key = str(p.resolve())
    with _GFS_LOCK:
        cached = _GFS_CACHE.get(key)
        if cached and cached[0] == mtime_ns:
            doc = cached[1]
        else:
            doc = json.loads(p.read_text(encoding="utf-8"))
            _GFS_CACHE[key] = (mtime_ns, doc)
    prov = doc.get("discovery_provenance") or {}
    temp = doc.get("temporal_domain") or {}
    summary = doc.get("summary_metrics") or doc.get("district_summary") or {}
    hourly = doc.get("hourly_forecast") or doc.get("lead_steps") or doc.get("hourly_series") or []

    def _accum_at_lead(max_lead: int) -> float | None:
        vals = []
        for step in hourly:
            raw_lh = step.get("lead_hours") if "lead_hours" in step else step.get("lead_hour", 0)
            lh = int(raw_lh)
            val = step.get("precipitation_rate_mm_h") if "precipitation_rate_mm_h" in step else step.get("rain_1h_mm")
            if 1 <= lh <= max_lead and val is not None:
                vals.append(float(val))
        return round(sum(vals), 3) if vals else None

    init_time = temp.get("forecast_init_time_utc") or doc.get("init_time_utc")
    retrieved_at = temp.get("retrieved_at_utc") or doc.get("retrieved_at_utc")
    age_hours = None
    stale = True
    if init_time:
        try:
            dt = datetime.fromisoformat(str(init_time).replace("Z", "+00:00"))
            age_hours = round((datetime.now(timezone.utc) - dt).total_seconds() / 3600.0, 2)
            stale = age_hours > 24.0
        except ValueError:
            stale = True

    rain_24h = summary.get("forecast_24h_mean_rain_mm")
    if rain_24h is None:
        rain_24h = summary.get("rain_24h_mm") if summary.get("rain_24h_mm") is not None else _accum_at_lead(24)
    rain_48h = summary.get("forecast_48h_mean_rain_mm")
    if rain_48h is None:
        rain_48h = _accum_at_lead(48)
    rain_72h = summary.get("forecast_72h_mean_rain_mm")
    if rain_72h is None:
        rain_72h = summary.get("rain_72h_mm") if summary.get("rain_72h_mm") is not None else _accum_at_lead(72)

    t2m_vals = [float(s["temperature_2m_c"]) for s in hourly if s.get("temperature_2m_c") is not None]
    t2m_mean = summary.get("t2m_mean_c")
    if t2m_mean is None and t2m_vals:
        t2m_mean = round(sum(t2m_vals) / len(t2m_vals), 2)

    return {
        "data_role": "experimental_forecast_only_never_measured_rainfall",
        "provider": doc.get("provider") or prov.get("attribution") or "NOAA NCEP GFS 0.25 deg via Dynamical.org Zarr v3",
        "source_url": prov.get("source_url") or doc.get("source_url"),
        "init_time_utc": init_time,
        "retrieved_at_utc": retrieved_at,
        "spatial_resolution_deg": (doc.get("spatial_domain") or {}).get("resolution_deg", 0.25),
        "rain_24h_outlook_mm": rain_24h,
        "rain_48h_outlook_mm": rain_48h,
        "rain_72h_outlook_mm": rain_72h,
        "temp_2m_min_c": summary.get("t2m_min_c") if summary.get("t2m_min_c") is not None else summary.get("temp_2m_min_c"),
        "temp_2m_max_c": summary.get("t2m_max_c") if summary.get("t2m_max_c") is not None else summary.get("temp_2m_max_c"),
        "temp_2m_mean_c": t2m_mean,
        "rh_2m_mean_pct": summary.get("rh_2m_mean_pct"),
        "pwat_mean_mm": summary.get("pwat_mean_mm"),
        "forecast_age_hours": age_hours,
        "is_stale": stale,
        "limitations": (
            "0.25 deg (~25 km) global NWP forecast smooths steep Barail Range orographic rainfall maxima. "
            "Must never be labeled as observed precipitation."
        ),
    }


def _classify_experimental_rainfall_envelope(
    rain_24h: float | None,
    rain_72h: float | None,
    rain_7d: float | None,
    slope_deg: float | None,
) -> dict[str, Any]:
    """
    Transparent, documented experimental inspection-priority envelope based on IMD
    24-hour heavy rainfall classes + terrain slope steepness.
    Explicitly NOT a calibrated landslide probability or Factor of Safety.
    """
    r24 = rain_24h or 0.0
    r72 = rain_72h or 0.0
    r7 = rain_7d or 0.0
    slope = slope_deg if slope_deg is not None else 0.0

    # IMD standard rainfall categories (mm/24h):
    #   <15.6 Light | 15.6–64.4 Moderate | 64.5–115.5 Heavy | 115.6–204.4 Very Heavy | >=204.5 Extremely Heavy
    if r24 >= 204.5 or r72 >= 300.0:
        rain_tier = "EXTREMELY_HEAVY_ENVELOPE"
    elif r24 >= 115.6 or r72 >= 200.0 or r7 >= 350.0:
        rain_tier = "VERY_HEAVY_ENVELOPE"
    elif r24 >= 64.5 or r72 >= 120.0 or r7 >= 250.0:
        rain_tier = "HEAVY_RAIN_ENVELOPE"
    elif r24 >= 15.6 or r72 >= 45.0:
        rain_tier = "MODERATE_RAIN_ENVELOPE"
    else:
        rain_tier = "LOW_RAIN_ENVELOPE"

    steep_terrain = slope >= 25.0
    moderate_slope = 15.0 <= slope < 25.0

    if rain_tier in {"EXTREMELY_HEAVY_ENVELOPE", "VERY_HEAVY_ENVELOPE"} and steep_terrain:
        priority = "PRIORITY_1_IMMEDIATE_FIELD_REVIEW"
    elif rain_tier in {"EXTREMELY_HEAVY_ENVELOPE", "VERY_HEAVY_ENVELOPE"} or (
        rain_tier == "HEAVY_RAIN_ENVELOPE" and steep_terrain
    ):
        priority = "PRIORITY_2_HEIGHTENED_MONITORING"
    elif rain_tier == "HEAVY_RAIN_ENVELOPE" or (rain_tier == "MODERATE_RAIN_ENVELOPE" and (steep_terrain or moderate_slope)):
        priority = "PRIORITY_3_ROUTINE_WATCH"
    else:
        priority = "BASELINE_MONITORING"

    return {
        "inspection_priority_tier": priority,
        "imd_rainfall_envelope": rain_tier,
        "slope_context_deg": round(slope, 2) if slope_deg is not None else None,
        "steep_slope_flag_ge_25deg": steep_terrain,
        "calibration_status": "EXPERIMENTAL_UNVALIDATED_ENVELOPE",
        "probability_interpretation_warning": (
            "This inspection priority is a transparent meteorological + slope screening rule "
            "(IMD 24h rainfall categories + Copernicus DEM slope >= 25 deg). It is NOT a calibrated "
            "landslide probability, annual recurrence rate, or geotechnical Factor of Safety."
        ),
    }


def compute_dynamic_hazard_assessment(
    lat: float,
    lon: float,
    pilot_dir: Path,
    raster_service: PilotRasterService,
    rainfall_service: PilotRainfallService,
    exposure_index: InfrastructureExposureIndex,
    radius_km: float = 5.0,
) -> dict[str, Any]:
    within_boundary = raster_service.is_within_pilot_boundary(lat, lon)
    within_raster, terrain, land_cover = raster_service.sample_point(lat, lon)
    extended = raster_service.sample_extended_features(lat, lon)
    rainfall = rainfall_service.get_snapshot(within_pilot=(within_boundary or within_raster))
    forecast = load_latest_gfs_forecast()
    gate_report = get_cached_quality_gate(pilot_dir)

    exposure = (
        exposure_index.query_proximity(lat, lon, radius_km=radius_km)
        if (within_boundary or within_raster)
        else {
            "query_radius_km": radius_km,
            "exposure_nature": "outside_pilot_coverage",
            "counts": {},
            "named_transport_corridors": [],
            "nearest_assets": [],
            "population_exposure_note": "Point lies outside the Dima Hasao pilot study area.",
        }
    )

    obs_stale = True
    obs_age_days = None
    if rainfall.latest_observation_date:
        try:
            obs_dt = datetime.fromisoformat(f"{rainfall.latest_observation_date}T00:00:00+00:00")
            obs_age_days = max(0, int((datetime.now(timezone.utc) - obs_dt).days))
            obs_stale = obs_age_days > 3
        except ValueError:
            obs_stale = True

    priority_eval = _classify_experimental_rainfall_envelope(
        rain_24h=forecast.get("rain_24h_outlook_mm") if forecast else rainfall.rainfall_24h_mm,
        rain_72h=forecast.get("rain_72h_outlook_mm") if forecast else rainfall.rainfall_72h_mm,
        rain_7d=None,
        slope_deg=terrain.slope_deg,
    )

    return {
        "coordinates": {"lat": round(lat, 6), "lon": round(lon, 6)},
        "study_area": "Dima Hasao District, Assam (Pilot)",
        "within_pilot_boundary": within_boundary,
        "assessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "landslide_probability": None,
        "factor_of_safety": None,
        "static_susceptibility": {
            "status": "unavailable_model_not_validated",
            "landslide_probability": None,
            "model_version": None,
            "quality_gate_passed": gate_report.overall_ml_ready,
            "blocking_reasons": gate_report.blocking_failures,
        },
        "observed_rainfall": {
            "latest_observation_date": rainfall.latest_observation_date,
            "rainfall_24h_mm": rainfall.rainfall_24h_mm,
            "rainfall_72h_mm": rainfall.rainfall_72h_mm,
            "observation_age_days": obs_age_days,
            "is_stale": obs_stale,
            "missing_telemetry_alert": obs_stale or rainfall.missing_24h,
            "latency_info": rainfall.latency_info,
        },
        "forecast_rainfall": forecast,
        "terrain_and_soil_context": {
            "elevation_m": terrain.elevation_m,
            "slope_deg": terrain.slope_deg,
            "aspect_cardinal": terrain.aspect_cardinal,
            "land_cover_2021": land_cover.class_label,
            "geomorphometry": extended.get("geomorphometry"),
            "soilgrids_2_0": extended.get("soilgrids_2_0"),
            "vegetation_ndvi": extended.get("vegetation_ndvi"),
            "transport_proximity": extended.get("transport_proximity"),
            "geology": extended.get("geology"),
        },
        "infrastructure_exposure": exposure,
        "response_priority": priority_eval,
        "uncertainty_and_limitations": [
            "No spatially & temporally validated landslide ML model is deployed (landslide_probability = null).",
            "Factor of Safety is never computed without site-specific geotechnical borehole/shear-strength testing.",
            "Observed NASA IMERG historical archive has a 2024–2026 gap pending NASA Earthdata Login authentication.",
            "NOAA GFS forecast (0.25 deg) is experimental meteorological outlook and smooths local ridge maxima.",
            "OpenStreetMap exposure counts represent mapped proximity only, not observed damage or complete rural census.",
        ],
    }


def simulate_what_if_scenario(
    lat: float,
    lon: float,
    hypothetical_rain_24h_mm: float,
    hypothetical_rain_72h_mm: float,
    hypothetical_antecedent_7d_mm: float,
    raster_service: PilotRasterService,
    exposure_index: InfrastructureExposureIndex,
    radius_km: float = 5.0,
) -> dict[str, Any]:
    """
    Phase F5 — Server-side hypothetical rainfall stress-test scenario.
    Never fabricates a numerical landslide probability from arbitrary formulas.
    """
    within_boundary = raster_service.is_within_pilot_boundary(lat, lon)
    within_raster, terrain, land_cover = raster_service.sample_point(lat, lon)
    exposure = (
        exposure_index.query_proximity(lat, lon, radius_km=radius_km)
        if (within_boundary or within_raster)
        else {"counts": {}, "named_transport_corridors": [], "nearest_assets": []}
    )
    envelope = _classify_experimental_rainfall_envelope(
        rain_24h=hypothetical_rain_24h_mm,
        rain_72h=hypothetical_rain_72h_mm,
        rain_7d=hypothetical_antecedent_7d_mm,
        slope_deg=terrain.slope_deg,
    )

    return {
        "hypothetical_scenario": True,
        "scenario_label": "HYPOTHETICAL_STRESS_TEST_NOT_A_FORECAST",
        "coordinates": {"lat": round(lat, 6), "lon": round(lon, 6)},
        "within_pilot_boundary": within_boundary,
        "simulated_at_utc": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "hypothetical_rain_24h_mm": round(hypothetical_rain_24h_mm, 2),
            "hypothetical_rain_72h_mm": round(hypothetical_rain_72h_mm, 2),
            "hypothetical_antecedent_7d_mm": round(hypothetical_antecedent_7d_mm, 2),
        },
        "terrain_context": {
            "elevation_m": terrain.elevation_m,
            "slope_deg": terrain.slope_deg,
            "aspect_cardinal": terrain.aspect_cardinal,
            "land_cover_2021": land_cover.class_label,
        },
        "validated_ml_probability": None,
        "factor_of_safety": None,
        "threshold_envelope_response": envelope,
        "potentially_exposed_mapped_infrastructure": exposure,
        "scientific_disclaimer": (
            "Hypothetical scenario output evaluates user-supplied rainfall against documented IMD "
            "heavy-rainfall categories and observed Copernicus DEM slope steepness. Validated "
            "ML failure probability remains null until all 13 Data Quality Gate checks pass."
        ),
    }
