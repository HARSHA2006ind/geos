"""
Stage 10 / Release Validation — Idempotent PostGIS Data Loader & Sync Utility.

Populates PostgreSQL 15+ / PostGIS (or SQLite test DB) with verified pilot artifacts:
  - study_areas (Dima Hasao MultiPolygon geometry, EPSG:4326)
  - dataset_registry, dataset_versions, provenance_records
  - landslide_events (GSI Bhusanket + NASA COOLR POINT geometries, EPSG:4326)
  - infrastructure_assets (OSM 619 facilities POINT + 2,599 transport LineString geometries, EPSG:4326)
  - rainfall_observations (10-year IMERG archive preserving missing days as NULL)
  - model_registry & validation_results (strictly validated_for_production=False, promoted_to_inference=False)
  - regional_coverage (all 8 Northeast India states)

Usage:
  PYTHONPATH=. DATABASE_URL=postgresql+psycopg://geos:geos_dev_password@127.0.0.1:5432/geos_ner \
    backend/.venv/bin/python backend/ingestion/sync_postgis.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from shapely.geometry import MultiPolygon, Polygon, shape
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.db import Base, build_engine
from backend.app.models import (
    DatasetRegistry,
    DatasetVersion,
    InfrastructureAsset,
    LandslideEvent,
    ModelRegistry,
    ProvenanceRecord,
    RainfallObservation,
    StudyArea,
    ValidationResult,
)
from backend.app.services.monitoring_service import ensure_regional_coverage_seeded

EXPERIMENTAL_DIR = Path(__file__).resolve().parents[1] / "data" / "experimental"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_exact_date(val: Any) -> date | None:
    if not val or not isinstance(val, str):
        return None
    txt = val.strip()[:10]
    if len(txt) != 10:
        return None
    try:
        return date.fromisoformat(txt)
    except ValueError:
        return None


def sync_all_artifacts_to_db(
    db: Session,
    pilot_dir: Path,
    experimental_dir: Path = EXPERIMENTAL_DIR,
) -> dict[str, Any]:
    counts: dict[str, int] = {}

    # 1. Seed 8-state NER regional matrix
    regions = ensure_regional_coverage_seeded(db)
    counts["regional_coverage_states"] = len(regions)

    # 2. Study Area MultiPolygon (Dima Hasao)
    boundary_path = pilot_dir / "dima_hasao_boundary.geojson"
    if boundary_path.exists():
        b_doc = json.loads(boundary_path.read_text(encoding="utf-8"))
        b_meta = b_doc.get("metadata") or {}
        geom_dict = b_doc["features"][0]["geometry"] if "features" in b_doc else b_doc["geometry"]
        poly = shape(geom_dict)
        if isinstance(poly, Polygon):
            poly = MultiPolygon([poly])
        bounds = list(poly.bounds)
        area_km2 = float(b_meta.get("area_km2") or 4890.0)
        existing_sa = db.scalar(select(StudyArea).where(StudyArea.slug == "dima-hasao"))
        if existing_sa is None:
            db.add(
                StudyArea(
                    slug="dima-hasao",
                    name="Dima Hasao District",
                    state="Assam",
                    country="India",
                    crs="EPSG:4326",
                    area_km2=area_km2,
                    bbox_wgs84=[round(x, 6) for x in bounds],
                    geom=poly.wkt,
                    source_attribution=str(b_meta.get("attribution", "© OpenStreetMap contributors (ODbL 1.0)")),
                )
            )
            db.commit()
    counts["study_areas"] = db.scalar(select(func.count()).select_from(StudyArea)) or 0

    # 3. Dataset Registry + Provenance Records
    dataset_specs: list[tuple[str, str, str, str, str, str, float | None, str, str, str | None, str | None]] = [
        (
            "osm-dima-hasao-boundary",
            "dima_hasao_boundary.geojson",
            "Dima Hasao Administrative Boundary (OSM)",
            "administrative_boundary",
            "OpenStreetMap",
            "OSM relation/2027398",
            None,
            "https://www.openstreetmap.org/relation/2027398",
            "© OpenStreetMap contributors (ODbL 1.0)",
            "Current OSM snapshot",
            "Boundary accuracy subject to OSM administrative polygon precision.",
        ),
        (
            "copernicus-dem-glo30",
            "dima_hasao_dem_utm46n.tif",
            "Copernicus DEM GLO-30 + Terrain Derivatives",
            "elevation_and_terrain",
            "ESA / Copernicus",
            "GLO-30 (90m district UTM46N / 30m core)",
            30.0,
            "https://copernicus-dem-30m.s3.amazonaws.com/",
            "© DLR e.V. 2010–2014 and Airbus Defence and Space GmbH 2014–2018",
            "2011–2015",
            "30m/90m DEM smooths vertical road-cut scarps under dense forest canopy.",
        ),
        (
            "esa-worldcover-2021",
            "dima_hasao_worldcover_2021_utm46n.tif",
            "ESA WorldCover 2021 10m Land Cover (v200)",
            "land_cover",
            "ESA WorldCover",
            "v200 (2021)",
            10.0,
            "https://esa-worldcover.s3.eu-central-1.amazonaws.com/",
            "© ESA WorldCover project 2021 (CC-BY-4.0)",
            "2021",
            "2021 epoch post-dates pre-2021 historical landslide records.",
        ),
        (
            "nasa-gpm-imerg-multiyear",
            "dima_hasao_rainfall_multiyear.json",
            "NASA GPM IMERG Multi-Year Daily Rainfall",
            "precipitation",
            "NASA GES DISC / POWER",
            "IMERG V07B / Multi-year daily",
            11100.0,
            "https://cmr.earthdata.nasa.gov/search/granules.json",
            "NASA GPM / Earthdata (Public Domain)",
            "2015-01-01 to 2024-06-01 (valid), 2024-06-02..2024-12-31 null gap",
            "Not calibrated against IMD/CWC surface rain gauges; missing days preserved as NULL.",
        ),
        (
            "isric-soilgrids-2-0",
            "dima_hasao_soilgrids_clay_0_5cm_utm46n.tif",
            "ISRIC SoilGrids 2.0 (7 Layers)",
            "soil",
            "ISRIC",
            "v2.0 (250m)",
            250.0,
            "https://files.isric.org/soilgrids/latest/data/",
            "ISRIC World Soil Information (CC-BY-4.0)",
            "Static reference",
            "250m global topsoil/subsoil model; not a replacement for borehole shear-strength tests.",
        ),
        (
            "sentinel2-l2a-ndvi-2024",
            "dima_hasao_ndvi_premonsoon_2024_utm46n.tif",
            "Sentinel-2 L2A Pre-Monsoon 2024 NDVI Composite",
            "vegetation",
            "ESA Copernicus / Element84",
            "S2-L2A 2024 dry-season median",
            90.0,
            "https://earth-search.aws.element84.com/v1",
            "ESA Copernicus Sentinel-2",
            "2024-02-01 to 2024-04-30",
            "Post-dates pre-May-2024 landslide events.",
        ),
        (
            "nasa-coolr-landslides",
            "dima_hasao_landslides_coolr.json",
            "NASA COOLR Landslide Inventory (50km Buffer)",
            "landslide_inventory",
            "NASA Earthdata ArcGIS",
            "COOLR Points",
            None,
            "https://gis.earthdata.nasa.gov/portal/rest/services/Landslides",
            "NASA Cooperative Open Online Landslide Repository",
            "2010–2023",
            "Coarse 1–50 km positional uncertainty inside Dima Hasao.",
        ),
        (
            "gsi-bhusanket-dima-hasao",
            "dima_hasao_landslides_gsi_bhusanket.json",
            "GSI Bhusanket Public Landslide Inventory (Dima Hasao)",
            "landslide_inventory",
            "Geological Survey of India",
            "Bhusanket Public GetData API",
            None,
            "https://bhusanket.gsi.gov.in",
            "Geological Survey of India (GSI)",
            "1998–2026 (mixed precision)",
            "Point centroids without GPS error bounds; 77.8% road/rail bias; polygons token-gated.",
        ),
        (
            "osm-dima-hasao-infrastructure",
            "dima_hasao_osm_facilities.geojson",
            "OSM Dima Hasao Facilities & Transport Network",
            "infrastructure",
            "OpenStreetMap Overpass API",
            "OSM Snapshot",
            90.0,
            "https://overpass-api.de/api/interpreter",
            "© OpenStreetMap contributors (ODbL 1.0)",
            "Current OSM snapshot",
            "Rural OSM coverage is incomplete; counts reflect mapped minimum assets only.",
        ),
    ]

    for ds_id, fname, name, cat, prov, ver, res_m, url, attr, period, lim in dataset_specs:
        fpath = pilot_dir / fname
        ds = db.get(DatasetRegistry, ds_id)
        crs = "EPSG:32646" if fname.endswith(".tif") else "EPSG:4326"
        if ds is None:
            ds = DatasetRegistry(
                id=ds_id,
                name=name,
                category=cat,
                provider=prov,
                product_version=ver,
                crs=crs,
                native_resolution_m=res_m,
                source_url=url,
                attribution=attr,
                requires_credentials=False,
                observation_period=period,
                status="available" if fpath.exists() else "missing",
                limitations=lim,
                metadata_json={"artifact_file": fname},
            )
            db.add(ds)
            db.flush()

        existing_ver = db.scalar(
            select(DatasetVersion).where(
                DatasetVersion.dataset_id == ds_id,
                DatasetVersion.version_tag == ver,
            )
        )
        checksum = _sha256_file(fpath) if fpath.exists() else None
        if existing_ver is None:
            db.add(
                DatasetVersion(
                    dataset_id=ds_id,
                    version_tag=ver,
                    checksum_sha256=checksum,
                    notes=lim,
                )
            )

        if fpath.exists() and checksum:
            existing_prov = db.scalar(
                select(ProvenanceRecord).where(
                    ProvenanceRecord.dataset_id == ds_id,
                    ProvenanceRecord.checksum_sha256 == checksum,
                )
            )
            if existing_prov is None:
                db.add(
                    ProvenanceRecord(
                        dataset_id=ds_id,
                        artifact_filename=fname,
                        checksum_sha256=checksum,
                        source_url=url,
                        observation_period=period or "Unknown",
                        attribution=attr,
                        limitations=lim,
                    )
                )
    db.commit()
    counts["dataset_registry"] = db.scalar(select(func.count()).select_from(DatasetRegistry)) or 0
    counts["provenance_records"] = db.scalar(select(func.count()).select_from(ProvenanceRecord)) or 0

    # 4. Rainfall Observations (multiyear IMERG)
    rain_path = pilot_dir / "dima_hasao_rainfall_multiyear.json"
    if rain_path.exists():
        rdoc = json.loads(rain_path.read_text(encoding="utf-8"))
        existing_dates = set(
            db.scalars(
                select(RainfallObservation.observation_date).where(
                    RainfallObservation.dataset_id == "nasa-gpm-imerg-multiyear"
                )
            ).all()
        )
        new_rain: list[RainfallObservation] = []
        for obs in rdoc.get("observations", []):
            obs_dt = _parse_exact_date(obs.get("date"))
            if obs_dt is None or obs_dt in existing_dates:
                continue
            ts_raw = obs.get("observation_timestamp_utc") or f"{obs_dt.isoformat()}T00:00:00+00:00"
            ts_dt = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
            new_rain.append(
                RainfallObservation(
                    study_area_slug="dima-hasao",
                    dataset_id="nasa-gpm-imerg-multiyear",
                    observation_date=obs_dt,
                    observation_timestamp_utc=ts_dt,
                    rainfall_24h_mm=obs.get("rainfall_1d_mm"),
                    rainfall_72h_mm=obs.get("rainfall_3d_mm"),
                    rainfall_7d_mm=obs.get("rainfall_7d_mm"),
                    rainfall_15d_mm=obs.get("rainfall_15d_mm"),
                    missing_24h=bool(obs.get("missing_1d", obs.get("rainfall_1d_mm") is None)),
                    missing_72h=bool(obs.get("missing_3d", obs.get("rainfall_3d_mm") is None)),
                    missing_7d=bool(obs.get("missing_7d", obs.get("rainfall_7d_mm") is None)),
                    missing_15d=bool(obs.get("missing_15d", obs.get("rainfall_15d_mm") is None)),
                    data_role=str(rdoc.get("data_role", "historical_archive"))[:32],
                    product_version=str(rdoc.get("product_version", "IMERG"))[:160],
                    latency_info="Satellite archive (gap 2024-06-02..2024-12-31 preserved as NULL)",
                )
            )
            existing_dates.add(obs_dt)
        if new_rain:
            db.add_all(new_rain)
            db.commit()
    counts["rainfall_observations"] = db.scalar(select(func.count()).select_from(RainfallObservation)) or 0

    # 5. Landslide Events (GSI Bhusanket + NASA COOLR)
    existing_dedup = set(db.scalars(select(LandslideEvent.dedup_key)).all())
    new_events: list[LandslideEvent] = []

    coolr_path = pilot_dir / "dima_hasao_landslides_coolr.json"
    if coolr_path.exists():
        cdoc = json.loads(coolr_path.read_text(encoding="utf-8"))
        for r in cdoc.get("records", []):
            dkey = str(r.get("dedup_key") or f"coolr:{r.get('source_provider')}:{r.get('external_event_id')}")[:160]
            if dkey in existing_dedup:
                continue
            lat, lon = r.get("latitude"), r.get("longitude")
            wkt = f"POINT({float(lon):.6f} {float(lat):.6f})" if (lat is not None and lon is not None) else None
            new_events.append(
                LandslideEvent(
                    source_provider=str(r.get("source_provider") or "NASA_COOLR")[:80],
                    external_event_id=str(r.get("external_event_id"))[:120],
                    dedup_key=dkey,
                    event_date=_parse_exact_date(r.get("event_date")),
                    event_date_precision=str(r.get("event_date_precision") or "unknown")[:32],
                    event_title=r.get("event_title"),
                    location_description=r.get("location_description"),
                    admin_division_name=str(r.get("admin_division_name") or "")[:160] or None,
                    country_name=str(r.get("country_name") or "India")[:80],
                    latitude=float(lat) if lat is not None else None,
                    longitude=float(lon) if lon is not None else None,
                    geom=wkt,
                    location_accuracy_raw=str(r.get("location_accuracy_raw") or "")[:64] or None,
                    location_accuracy_m=float(r["location_accuracy_m"]) if r.get("location_accuracy_m") is not None else None,
                    spatial_zone=str(r.get("spatial_zone") or "buffer_50km")[:32],
                    within_pilot_boundary=bool(r.get("within_pilot_boundary")),
                    landslide_category=str(r.get("landslide_category") or "")[:80] or None,
                    landslide_trigger=str(r.get("landslide_trigger") or "")[:80] or None,
                    landslide_size=str(r.get("landslide_size") or "")[:64] or None,
                    landslide_setting=str(r.get("landslide_setting") or "")[:80] or None,
                    fatality_count=r.get("fatality_count"),
                    injury_count=r.get("injury_count"),
                    source_name=r.get("source_name"),
                    source_link=r.get("source_link"),
                    training_usability=str(r.get("training_usability") or "contextual_visualization_only")[:48],
                    usability_reason=r.get("usability_reason"),
                    raw_payload_json={k: v for k, v in r.items() if k != "raw_payload_json"},
                )
            )
            existing_dedup.add(dkey)

    gsi_path = pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json"
    if gsi_path.exists():
        gdoc = json.loads(gsi_path.read_text(encoding="utf-8"))
        for r in gdoc.get("records", []):
            ext_id = str(r.get("object_id") or r.get("slide_no") or "")
            if not ext_id:
                continue
            dkey = f"gsi_bhusanket:{ext_id}"[:160]
            if dkey in existing_dedup:
                continue
            lat, lon = r.get("latitude"), r.get("longitude")
            valid_pt = bool(r.get("valid_coordinate")) and lat is not None and lon is not None
            wkt = f"POINT({float(lon):.6f} {float(lat):.6f})" if valid_pt else None
            in_poly = bool(r.get("within_pilot_boundary"))
            new_events.append(
                LandslideEvent(
                    source_provider="GSI_Bhusanket",
                    external_event_id=ext_id[:120],
                    dedup_key=dkey,
                    event_date=_parse_exact_date(r.get("event_date")),
                    event_date_precision=str(r.get("event_date_precision") or "unknown")[:32],
                    event_title=r.get("slide_name") or f"GSI Slide {r.get('slide_no')}",
                    location_description=r.get("nh_sh_location") or r.get("slide_name"),
                    admin_division_name=str(r.get("district") or "Dima Hasao")[:160],
                    country_name="India",
                    latitude=float(lat) if valid_pt else None,
                    longitude=float(lon) if valid_pt else None,
                    geom=wkt,
                    location_accuracy_raw=str(r.get("coord_precision_tier") or "unverified")[:64],
                    location_accuracy_m=None,
                    spatial_zone="pilot_polygon" if in_poly else "district_envelope",
                    within_pilot_boundary=in_poly,
                    landslide_category=str(r.get("movement_type") or "")[:80] or None,
                    landslide_trigger=str(r.get("triggering") or "")[:80] or None,
                    landslide_size=str(r.get("material_involved") or "")[:64] or None,
                    landslide_setting=str(r.get("landuse_or_landcover") or "")[:80] or None,
                    source_name=str(r.get("source_type") or "GSI Bhusanket"),
                    source_link="https://bhusanket.gsi.gov.in",
                    training_usability="exploratory_only_point_centroid",
                    usability_reason=(
                        "Point centroid without explicit GPS error radius; polygons token-gated HTTP 499; "
                        "77.8% transport-corridor bias."
                    ),
                    raw_payload_json=r,
                )
            )
            existing_dedup.add(dkey)

    if new_events:
        db.add_all(new_events)
        db.commit()
    counts["landslide_events"] = db.scalar(select(func.count()).select_from(LandslideEvent)) or 0
    counts["landslide_events_gsi"] = (
        db.scalar(select(func.count()).select_from(LandslideEvent).where(LandslideEvent.source_provider == "GSI_Bhusanket"))
        or 0
    )

    # 6. Infrastructure Assets (OSM 619 Point Facilities + 2,599 Transport Lines)
    existing_infra = set(
        db.execute(select(InfrastructureAsset.source_provider, InfrastructureAsset.external_id)).all()
    )
    new_infra: list[InfrastructureAsset] = []

    fac_path = pilot_dir / "dima_hasao_osm_facilities.geojson"
    if fac_path.exists():
        fdoc = json.loads(fac_path.read_text(encoding="utf-8"))
        for idx, feat in enumerate(fdoc.get("features", [])):
            props = feat.get("properties") or {}
            geom_d = feat.get("geometry") or {}
            coords = geom_d.get("coordinates") or []
            ext_id = str(props.get("external_id") or f"osm:fac:{idx}")[:120]
            if ("OSM_Overpass", ext_id) in existing_infra or len(coords) < 2:
                continue
            lon, lat = float(coords[0]), float(coords[1])
            pop_raw = props.get("population_osm_tag")
            try:
                pop_int = int(pop_raw) if pop_raw is not None else None
            except (TypeError, ValueError):
                pop_int = None
            new_infra.append(
                InfrastructureAsset(
                    study_area_slug="dima-hasao",
                    source_provider="OSM_Overpass",
                    external_id=ext_id,
                    category=str(props.get("category") or "facility")[:48],
                    subtype=str(props.get("subtype") or "")[:64] or None,
                    name=str(props.get("name") or props.get("subtype") or ext_id)[:255],
                    latitude=lat,
                    longitude=lon,
                    geom=f"POINT({lon:.6f} {lat:.6f})",
                    population_tag=pop_int,
                    attributes_json=props,
                )
            )
            existing_infra.add(("OSM_Overpass", ext_id))

    tr_path = pilot_dir / "dima_hasao_osm_transport.geojson"
    if tr_path.exists():
        tdoc = json.loads(tr_path.read_text(encoding="utf-8"))
        for idx, feat in enumerate(tdoc.get("features", [])):
            props = feat.get("properties") or {}
            geom_d = feat.get("geometry") or {}
            ext_id = str(props.get("external_id") or props.get("osm_id") or f"osm:transport:{idx}")[:120]
            if ("OSM_Overpass_Transport", ext_id) in existing_infra or not geom_d.get("coordinates"):
                continue
            gobj = shape(geom_d)
            rep = gobj.representative_point()
            cat = "railway" if props.get("railway") else "road"
            sub = str(props.get("railway") or props.get("highway") or "")[:64] or None
            nm = props.get("name") or props.get("ref") or f"{cat}:{sub or idx}"
            new_infra.append(
                InfrastructureAsset(
                    study_area_slug="dima-hasao",
                    source_provider="OSM_Overpass_Transport",
                    external_id=ext_id,
                    category=cat,
                    subtype=sub,
                    name=str(nm)[:255],
                    latitude=float(rep.y),
                    longitude=float(rep.x),
                    geom=gobj.wkt,
                    population_tag=None,
                    attributes_json=props,
                )
            )
            existing_infra.add(("OSM_Overpass_Transport", ext_id))

    if new_infra:
        db.add_all(new_infra)
        db.commit()
    counts["infrastructure_assets"] = db.scalar(select(func.count()).select_from(InfrastructureAsset)) or 0
    counts["infrastructure_facilities"] = (
        db.scalar(select(func.count()).select_from(InfrastructureAsset).where(InfrastructureAsset.source_provider == "OSM_Overpass"))
        or 0
    )

    # 7. Exploratory Model Registry & Spatial-Block CV Results (strictly unpromoted!)
    bench_path = experimental_dir / "exploratory_ml_benchmark.json"
    if bench_path.exists():
        bdoc = json.loads(bench_path.read_text(encoding="utf-8"))
        ma = bdoc.get("model_a_static_susceptibility") or {}
        clean = ma.get("clean_terrain_soil_ablation") or {}
        features = clean.get("features") or []
        val_scheme = str(ma.get("validation_scheme") or "5-fold Geographic Spatial-Block GroupKFold")[:120]
        models_dict = clean.get("models") or clean
        for model_key, model_name, alg in (
            ("random_forest", "DimaHasao-RF-Exploratory-PU", "RandomForestClassifier"),
            ("xgboost", "DimaHasao-XGBoost-Exploratory-PU", "XGBClassifier"),
        ):
            m_entry = models_dict.get(model_key)
            if not m_entry:
                continue
            m_metrics = m_entry.get("oof_metrics") or m_entry
            reg = db.scalar(
                select(ModelRegistry).where(
                    ModelRegistry.model_name == model_name,
                    ModelRegistry.version == "0.1.0-exploratory-pu",
                )
            )
            if reg is None:
                reg = ModelRegistry(
                    model_name=model_name,
                    algorithm=alg,
                    version="0.1.0-exploratory-pu",
                    problem_type="static_susceptibility",
                    track="exploratory_research",
                    validated_for_production=False,
                    promoted_to_inference=False,
                    study_area_slug="dima-hasao",
                    artifact_path=str(bench_path),
                    feature_list_json=features,
                    limitations=(
                        "Trained under Positive-Unlabeled sampling on corridor-biased point centroids; "
                        "6 blocking Quality Gate failures prohibit production inference."
                    ),
                )
                db.add(reg)
                db.flush()
                db.add(
                    ValidationResult(
                        model_id=reg.id,
                        validation_scheme=val_scheme,
                        metrics_json={
                            "oof_metrics": m_metrics,
                            "spatial_block_generalization": m_entry.get("spatial_block_generalization"),
                        },
                        shap_summary_json=m_entry.get("shap_top_features") or clean.get("shap_top_features"),
                        passed_production_gate=False,
                    )
                )
        db.commit()
    counts["model_registry"] = db.scalar(select(func.count()).select_from(ModelRegistry)) or 0
    counts["validation_results"] = db.scalar(select(func.count()).select_from(ValidationResult)) or 0

    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync verified GEOS 2.0 pilot datasets into PostGIS/SQLAlchemy.")
    parser.add_argument("--db-url", default=None, help="Optional database URL override")
    args = parser.parse_args()

    settings = get_settings()
    db_url = args.db_url or settings.database_url
    engine = build_engine(db_url)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)
    with SessionFactory() as db:
        summary = sync_all_artifacts_to_db(db=db, pilot_dir=Path(settings.pilot_data_dir))
    print(json.dumps({"dialect": engine.dialect.name, "synced_counts": summary}, indent=2))


if __name__ == "__main__":
    main()
