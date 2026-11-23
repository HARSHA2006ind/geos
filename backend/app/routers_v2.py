"""
Phase E, G, H, I, J, K, L, O — Complete GEOS 2.0 FastAPI Router (/api/v1/*).

Provides:
  - Authentication & RBAC (/api/v1/auth/*) with first-run admin claim flow, scrypt hashing,
    HMAC-SHA256 Bearer tokens, least-privilege registration, and admin role management.
  - Extended Terrain/Soil/Forecast/Infrastructure/Dynamic Hazard & What-If endpoints.
  - Honest ML Registry, Readiness & Deployment-Gated Inference (/api/v1/ml/*).
  - Authenticated Field Officer Reporting with validated real photo uploads & review workflow.
  - Experimental Research Alert creation, review/approval workflow & dry-run notification audit.
  - Automated Environmental Monitoring freshness status & trigger.
  - 8-State Northeast India Regional Expansion readiness matrix (/api/v1/regions).
  - Grounded Gemini Geospatial Explanation Assistant (/api/v1/assistant/explain).
  - Read-only Audit Logs (/api/v1/audit-logs).
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import Settings
from backend.app.db import Base, build_engine
from backend.app.models import (
    AuditLog,
    ExperimentalAlert,
    FieldReport,
    MonitoringRun,
    User,
)
from backend.app.quality_gate import evaluate_data_quality_gate
from backend.app.security import (
    SELF_REGISTER_ALLOWED_ROLES,
    VALID_ROLES,
    SlidingWindowRateLimiter,
    create_access_token,
    hash_password,
    resolve_confined_upload,
    sanitize_user_question,
    save_validated_photo_upload,
    verify_access_token,
    verify_password,
)
from backend.app.services.hazard_engine import (
    EXPERIMENTAL_DIR,
    InfrastructureExposureIndex,
    compute_dynamic_hazard_assessment,
    get_cached_quality_gate,
    load_latest_gfs_forecast,
    simulate_what_if_scenario,
)
from backend.app.services.monitoring_service import (
    ensure_regional_coverage_seeded,
    execute_monitoring_cycle,
)
from backend.app.services.rainfall_service import PilotRainfallService
from backend.app.services.raster_service import PilotRasterService


# =====================================================================
# Request Schemas
# =====================================================================
class ClaimAdminRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=48, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str = Field(..., min_length=5, max_length=160)
    full_name: str = Field(..., min_length=2, max_length=160)
    password: str = Field(..., min_length=8, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=48, pattern=r"^[a-zA-Z0-9_.-]+$")
    email: str = Field(..., min_length=5, max_length=160)
    full_name: str = Field(..., min_length=2, max_length=160)
    password: str = Field(..., min_length=8, max_length=128)
    requested_role: str = Field(default="field_officer")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=160)
    password: str = Field(..., min_length=1, max_length=128)


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., description="One of admin, research_analyst, field_officer, public_viewer")


class InferRequest(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)


class WhatIfSimulateRequest(BaseModel):
    lat: float = Field(default=25.1645, ge=-90.0, le=90.0)
    lon: float = Field(default=93.0176, ge=-180.0, le=180.0)
    hypothetical_rain_24h_mm: float = Field(..., ge=0.0, le=1500.0)
    hypothetical_rain_72h_mm: float = Field(..., ge=0.0, le=3000.0)
    hypothetical_antecedent_7d_mm: float = Field(default=120.0, ge=0.0, le=4500.0)
    radius_km: float = Field(default=5.0, ge=0.5, le=25.0)


class ReviewFieldReportRequest(BaseModel):
    verification_status: str = Field(..., pattern=r"^(verified|rejected|pending)$")
    review_notes: str = Field(default="", max_length=1000)


class CreateAlertRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=220)
    geographic_area: str = Field(..., min_length=2, max_length=200)
    latitude: float = Field(default=25.1645, ge=-90.0, le=90.0)
    longitude: float = Field(default=93.0176, ge=-180.0, le=180.0)
    severity_tier: str = Field(..., pattern=r"^(LOW|MODERATE|HIGH|CRITICAL)$")
    severity_rationale: str = Field(..., min_length=10, max_length=2000)
    inspection_priorities: list[str] = Field(default_factory=list, max_length=12)
    radius_km: float = Field(default=5.0, ge=0.5, le=25.0)


class ReviewAlertRequest(BaseModel):
    status: str = Field(..., pattern=r"^(pending_review|approved_internal|rejected|archived)$")
    review_comment: str = Field(default="", max_length=1000)


class DryRunNotifyRequest(BaseModel):
    channels: list[str] = Field(default_factory=lambda: ["internal_research_log", "webhook_dry_run"])
    target_group: str = Field(default="Dima Hasao Research Review Team", max_length=160)


class AssistantExplainRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    lat: float = Field(default=25.1645, ge=-90.0, le=90.0)
    lon: float = Field(default=93.0176, ge=-180.0, le=180.0)
    radius_km: float = Field(default=5.0, ge=0.5, le=25.0)


def _record_audit(
    db: Session,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    actor: User | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else None,
            actor_role=actor.role if actor else None,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details_json=details or {},
        )
    )


def _serialize_user(u: User) -> dict[str, Any]:
    return {
        "id": u.id,
        "username": u.username,
        "full_name": u.full_name,
        "role": u.role,
        "is_active": u.is_active,
        "created_at": u.created_at.isoformat() if u.created_at else None,
    }


def _serialize_field_report(r: FieldReport, submitter_name: str | None = None, reviewer_name: str | None = None) -> dict[str, Any]:
    return {
        "id": r.id,
        "study_area_slug": r.study_area_slug,
        "location_name": r.location_name,
        "latitude": r.latitude,
        "longitude": r.longitude,
        "within_pilot_boundary": r.within_pilot_boundary,
        "observed_at_utc": r.observed_at_utc,
        "category": r.category,
        "severity_observation": r.severity_observation,
        "description": r.description,
        "road_obstruction": r.road_obstruction,
        "notes": r.notes,
        "photo_url": f"/api/v1/field-reports/photos/{r.photo_filename}" if r.photo_filename else None,
        "photo_metadata": (
            {
                "filename": r.photo_filename,
                "mime_type": r.photo_mime,
                "size_bytes": r.photo_size_bytes,
                "sha256": r.photo_sha256,
            }
            if r.photo_filename
            else None
        ),
        "verification_status": r.verification_status,
        "submitted_by_user_id": r.submitted_by_user_id,
        "submitted_by_username": submitter_name,
        "reviewed_by_user_id": r.reviewed_by_user_id,
        "reviewed_by_username": reviewer_name,
        "review_notes": r.review_notes,
        "reviewed_at": r.reviewed_at.isoformat() if r.reviewed_at else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "ml_impact_note": "Field reports are persisted for human verification and NEVER silently alter ML outputs.",
    }


def _serialize_alert(a: ExperimentalAlert, creator_name: str | None = None, reviewer_name: str | None = None) -> dict[str, Any]:
    return {
        "id": a.id,
        "classification": a.classification,
        "official_government_warning": False,
        "study_area_slug": a.study_area_slug,
        "title": a.title,
        "geographic_area": a.geographic_area,
        "latitude": a.latitude,
        "longitude": a.longitude,
        "severity_tier": a.severity_tier,
        "severity_rationale": a.severity_rationale,
        "hazard_evidence": a.hazard_evidence_json,
        "source_timestamps": a.source_timestamps_json,
        "affected_infrastructure": a.affected_infrastructure_json,
        "inspection_priorities": a.inspection_priorities_json,
        "status": a.status,
        "created_by_user_id": a.created_by_user_id,
        "created_by_username": creator_name,
        "reviewed_by_user_id": a.reviewed_by_user_id,
        "reviewed_by_username": reviewer_name,
        "review_comment": a.review_comment,
        "dry_run_notifications": a.dry_run_notifications_json or [],
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def build_v2_router(
    settings: Settings,
    raster_service: PilotRasterService,
    rainfall_service: PilotRainfallService,
    platform_db_url: str | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/api/v1")
    pilot_dir = Path(settings.pilot_data_dir)
    uploads_dir = pilot_dir.parent / "uploads"
    exposure_index = InfrastructureExposureIndex(pilot_dir)

    # Resolve operational platform DB (uses configured DATABASE_URL if reachable/sqlite, else local SQLite platform DB)
    db_url = platform_db_url
    if not db_url:
        if settings.database_url.startswith("sqlite"):
            db_url = settings.database_url
        else:
            # Verify PostgreSQL reachability; gracefully fall back to persistent local SQLite if Postgres daemon is absent
            try:
                probe_eng = build_engine(settings.database_url)
                with probe_eng.connect():
                    pass
                db_url = settings.database_url
            except Exception:
                db_url = f"sqlite:///{(pilot_dir / 'geos_platform.db').resolve()}"

    engine = build_engine(db_url)
    Base.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, autocommit=False, autoflush=False, class_=Session)

    # Seed regional coverage on startup idempotently
    with SessionFactory() as seed_db:
        ensure_regional_coverage_seeded(seed_db)

    auth_limiter = SlidingWindowRateLimiter(max_requests=25, window_seconds=60)
    ai_limiter = SlidingWindowRateLimiter(max_requests=15, window_seconds=60)
    write_limiter = SlidingWindowRateLimiter(max_requests=30, window_seconds=60)

    def get_platform_db():
        db = SessionFactory()
        try:
            yield db
        finally:
            db.close()

    def _enforce_rate(limiter: SlidingWindowRateLimiter, request: Request, bucket: str) -> None:
        client_ip = request.client.host if request.client else "unknown"
        ok, retry_after = limiter.allow(f"{bucket}:{client_ip}")
        if not ok:
            raise HTTPException(
                status_code=429,
                detail=f"Rate limit exceeded for {bucket}. Retry after {retry_after} seconds.",
                headers={"Retry-After": str(retry_after)},
            )

    def get_current_user(
        authorization: str | None = Header(default=None),
        db: Session = Depends(get_platform_db),
    ) -> User:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Authentication required (Bearer token missing).")
        token = authorization.split(" ", 1)[1].strip()
        payload = verify_access_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid or expired access token.")
        user = db.get(User, int(payload["sub"]))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User account is inactive or no longer exists.")
        return user

    def require_roles(*allowed_roles: str):
        def _dep(user: User = Depends(get_current_user)) -> User:
            if user.role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Insufficient permissions. Required role in {list(allowed_roles)}; current role is '{user.role}'.",
                )
            return user

        return _dep

    # =====================================================================
    # 1. AUTHENTICATION & RBAC (/api/v1/auth/*)
    # =====================================================================
    @router.get("/auth/bootstrap-status", tags=["Authentication"])
    def auth_bootstrap_status(db: Session = Depends(get_platform_db)) -> dict[str, Any]:
        admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0
        env_passcode_set = bool(os.environ.get("GEOS_ADMIN_PASSCODE", "").strip())
        return {
            "needs_admin_claim": admin_count == 0,
            "admin_exists": admin_count > 0,
            "env_admin_passcode_configured": env_passcode_set,
            "supported_roles": list(VALID_ROLES),
            "self_register_roles": list(SELF_REGISTER_ALLOWED_ROLES),
        }

    @router.post("/auth/claim-admin", tags=["Authentication"])
    def claim_first_admin(
        body: ClaimAdminRequest,
        request: Request,
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        _enforce_rate(auth_limiter, request, "auth_claim")
        admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == "admin")) or 0
        if admin_count > 0:
            raise HTTPException(
                status_code=409,
                detail="Initial administrator has already been claimed. Sign in with an existing admin account.",
            )
        existing = db.scalar(
            select(User).where((User.username == body.username) | (User.email == body.email))
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username or email is already registered.")
        user = User(
            username=body.username,
            email=body.email.lower().strip(),
            full_name=body.full_name.strip(),
            role="admin",
            password_hash=hash_password(body.password),
            is_active=True,
        )
        db.add(user)
        db.flush()
        _record_audit(db, "admin_first_run_claimed", "user", str(user.id), actor=user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id, user.username, user.role)
        return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user)}

    @router.post("/auth/register", tags=["Authentication"])
    def register_user(
        body: RegisterRequest,
        request: Request,
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        _enforce_rate(auth_limiter, request, "auth_register")
        # Never trust client-supplied privileged roles on self-registration
        assigned_role = body.requested_role if body.requested_role in SELF_REGISTER_ALLOWED_ROLES else "public_viewer"
        existing = db.scalar(
            select(User).where((User.username == body.username) | (User.email == body.email.lower().strip()))
        )
        if existing:
            raise HTTPException(status_code=409, detail="Username or email already exists.")
        user = User(
            username=body.username,
            email=body.email.lower().strip(),
            full_name=body.full_name.strip(),
            role=assigned_role,
            password_hash=hash_password(body.password),
            is_active=True,
        )
        db.add(user)
        db.flush()
        _record_audit(
            db,
            "user_registered",
            "user",
            str(user.id),
            actor=user,
            details={"assigned_role": assigned_role},
        )
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id, user.username, user.role)
        return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user)}

    @router.post("/auth/login", tags=["Authentication"])
    def login_user(
        body: LoginRequest,
        request: Request,
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        _enforce_rate(auth_limiter, request, "auth_login")
        user = db.scalar(
            select(User).where((User.username == body.username) | (User.email == body.username.lower().strip()))
        )
        if not user or not user.is_active or not verify_password(body.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password.")
        _record_audit(db, "user_login", "user", str(user.id), actor=user)
        db.commit()
        token = create_access_token(user.id, user.username, user.role)
        return {"access_token": token, "token_type": "bearer", "user": _serialize_user(user)}

    @router.get("/auth/me", tags=["Authentication"])
    def auth_me(user: User = Depends(get_current_user)) -> dict[str, Any]:
        return _serialize_user(user)

    @router.get("/auth/users", tags=["Authentication"])
    def list_users(
        _admin: User = Depends(require_roles("admin")),
        db: Session = Depends(get_platform_db),
    ) -> list[dict[str, Any]]:
        users = db.scalars(select(User).order_by(User.id)).all()
        return [_serialize_user(u) for u in users]

    @router.patch("/auth/users/{user_id}/role", tags=["Authentication"])
    def update_user_role(
        user_id: int,
        body: UpdateRoleRequest,
        admin: User = Depends(require_roles("admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=422, detail=f"Role must be one of {list(VALID_ROLES)}.")
        target = db.get(User, user_id)
        if not target:
            raise HTTPException(status_code=404, detail="User not found.")
        prev_role = target.role
        target.role = body.role
        _record_audit(
            db,
            "user_role_updated",
            "user",
            str(target.id),
            actor=admin,
            details={"previous_role": prev_role, "new_role": body.role},
        )
        db.commit()
        db.refresh(target)
        return _serialize_user(target)

    # =====================================================================
    # 2. EXTENDED TERRAIN, SOIL, FORECAST, INFRASTRUCTURE & DYNAMIC HAZARD
    # =====================================================================
    @router.get("/environment/terrain", tags=["Environmental Data"])
    def get_terrain_features(
        lat: float = Query(..., ge=-90.0, le=90.0),
        lon: float = Query(..., ge=-180.0, le=180.0),
    ) -> dict[str, Any]:
        within = raster_service.is_within_pilot_boundary(lat, lon)
        _, terrain, _ = raster_service.sample_point(lat, lon)
        ext = raster_service.sample_extended_features(lat, lon)
        return {
            "coordinates": {"lat": round(lat, 6), "lon": round(lon, 6)},
            "within_pilot_boundary": within,
            "terrain": terrain.model_dump(),
            "geomorphometry": ext["geomorphometry"],
            "transport_proximity": ext["transport_proximity"],
        }

    @router.get("/environment/soil", tags=["Environmental Data"])
    def get_soil_features(
        lat: float = Query(..., ge=-90.0, le=90.0),
        lon: float = Query(..., ge=-180.0, le=180.0),
    ) -> dict[str, Any]:
        within = raster_service.is_within_pilot_boundary(lat, lon)
        ext = raster_service.sample_extended_features(lat, lon)
        return {
            "coordinates": {"lat": round(lat, 6), "lon": round(lon, 6)},
            "within_pilot_boundary": within,
            "soilgrids_2_0": ext["soilgrids_2_0"],
            "vegetation_ndvi": ext["vegetation_ndvi"],
            "geology": ext["geology"],
        }

    @router.get("/environment/rainfall/forecast", tags=["Environmental Data"])
    def get_rainfall_forecast() -> dict[str, Any]:
        fc = load_latest_gfs_forecast(EXPERIMENTAL_DIR)
        if not fc:
            raise HTTPException(
                status_code=503,
                detail="Experimental NOAA GFS forecast artifact has not been generated yet.",
            )
        return fc

    @router.get("/infrastructure/exposure", tags=["Infrastructure Exposure"])
    def get_infrastructure_exposure(
        lat: float = Query(default=25.1645, ge=-90.0, le=90.0),
        lon: float = Query(default=93.0176, ge=-180.0, le=180.0),
        radius_km: float = Query(default=5.0, ge=0.5, le=25.0),
    ) -> dict[str, Any]:
        return {
            "coordinates": {"lat": round(lat, 6), "lon": round(lon, 6)},
            "within_pilot_boundary": raster_service.is_within_pilot_boundary(lat, lon),
            "exposure": exposure_index.query_proximity(lat, lon, radius_km=radius_km),
        }

    @router.get("/infrastructure/facilities", tags=["Infrastructure Exposure"])
    def get_infrastructure_facilities(
        category: str | None = Query(default=None),
        limit: int = Query(default=200, ge=1, le=700),
    ) -> dict[str, Any]:
        exposure_index._ensure_loaded()
        fac_path = pilot_dir / "dima_hasao_osm_facilities.geojson"
        if not fac_path.exists():
            raise HTTPException(status_code=503, detail="OSM facilities GeoJSON has not been ingested yet.")
        items = exposure_index._facilities or []
        if category:
            items = [f for f in items if f.get("category") == category]
        features = [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [f["lon"], f["lat"]]},
                "properties": {k: v for k, v in f.items() if k not in {"lat", "lon"}},
            }
            for f in items[:limit]
        ]
        return {"type": "FeatureCollection", "metadata": exposure_index._facilities_meta, "features": features}

    @router.get("/hazard/assess", tags=["Dynamic Hazard"])
    def assess_dynamic_hazard(
        lat: float = Query(default=25.1645, ge=-90.0, le=90.0),
        lon: float = Query(default=93.0176, ge=-180.0, le=180.0),
        radius_km: float = Query(default=5.0, ge=0.5, le=25.0),
    ) -> dict[str, Any]:
        return compute_dynamic_hazard_assessment(
            lat=lat,
            lon=lon,
            pilot_dir=pilot_dir,
            raster_service=raster_service,
            rainfall_service=rainfall_service,
            exposure_index=exposure_index,
            radius_km=radius_km,
        )

    @router.post("/hazard/simulate", tags=["Dynamic Hazard"])
    def simulate_what_if(
        body: WhatIfSimulateRequest,
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        result = simulate_what_if_scenario(
            lat=body.lat,
            lon=body.lon,
            hypothetical_rain_24h_mm=body.hypothetical_rain_24h_mm,
            hypothetical_rain_72h_mm=body.hypothetical_rain_72h_mm,
            hypothetical_antecedent_7d_mm=body.hypothetical_antecedent_7d_mm,
            raster_service=raster_service,
            exposure_index=exposure_index,
            radius_km=body.radius_km,
        )
        _record_audit(
            db,
            "what_if_scenario_simulated",
            "hazard_simulation",
            details={
                "lat": body.lat,
                "lon": body.lon,
                "rain_24h_mm": body.hypothetical_rain_24h_mm,
                "rain_72h_mm": body.hypothetical_rain_72h_mm,
                "priority_tier": result["threshold_envelope_response"]["inspection_priority_tier"],
            },
        )
        db.commit()
        return result

    # =====================================================================
    # 3. ML READINESS, MODEL REGISTRY & HONEST INFERENCE GATE (/api/v1/ml/*)
    # =====================================================================
    @router.get("/ml/readiness", tags=["Machine Learning"])
    def get_ml_readiness() -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(get_cached_quality_gate(pilot_dir))

    @router.get("/ml/models", tags=["Machine Learning"])
    def get_ml_models() -> dict[str, Any]:
        bench_path = EXPERIMENTAL_DIR / "exploratory_ml_benchmark.json"
        benchmark = json.loads(bench_path.read_text(encoding="utf-8")) if bench_path.exists() else None
        gate = get_cached_quality_gate(pilot_dir)
        return {
            "production_models_validated": 0,
            "production_inference_available": False,
            "landslide_probability_policy": "STRICTLY_NULL_UNTIL_QUALITY_GATE_PASSES",
            "quality_gate_passed": gate.overall_ml_ready,
            "blocking_failures": gate.blocking_failures,
            "exploratory_research_benchmark": benchmark,
        }

    @router.post("/ml/infer", tags=["Machine Learning"])
    def infer_susceptibility(body: InferRequest) -> dict[str, Any]:
        """Deployment-gated ML inference endpoint: honestly returns null when no validated model exists."""
        gate = get_cached_quality_gate(pilot_dir)
        within = raster_service.is_within_pilot_boundary(body.lat, body.lon)
        _, terrain, land_cover = raster_service.sample_point(body.lat, body.lon)
        ext = raster_service.sample_extended_features(body.lat, body.lon)
        return {
            "status": "unavailable_model_not_validated",
            "model_validated": False,
            "landslide_probability": None,
            "factor_of_safety": None,
            "coordinates": {"lat": round(body.lat, 6), "lon": round(body.lon, 6)},
            "within_pilot_boundary": within,
            "message": (
                "No scientifically validated landslide prediction model is deployed for Dima Hasao. "
                "Production inference remains disabled until all 13 Data Quality Gate checks pass."
            ),
            "blocking_failures": gate.blocking_failures,
            "sampled_conditioning_context": {
                "elevation_m": terrain.elevation_m,
                "slope_deg": terrain.slope_deg,
                "land_cover_2021": land_cover.class_label,
                "twi": ext["geomorphometry"]["twi"],
                "tri_m": ext["geomorphometry"]["tri_m"],
                "clay_0_5cm_pct": ext["soilgrids_2_0"]["clay_0_5cm_pct"],
            },
        }

    # =====================================================================
    # 4. AUTHENTICATED FIELD OFFICER REPORTING (/api/v1/field-reports/*)
    # =====================================================================
    @router.get("/field-reports", tags=["Field Reporting"])
    def list_field_reports(
        status: str | None = Query(default=None, pattern=r"^(pending|verified|rejected)$"),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        q = select(FieldReport).order_by(desc(FieldReport.created_at))
        if status:
            q = q.where(FieldReport.verification_status == status)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.offset(offset).limit(limit)).all()
        user_ids = {r.submitted_by_user_id for r in rows} | {r.reviewed_by_user_id for r in rows if r.reviewed_by_user_id}
        users_map = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()} if user_ids else {}
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "items": [
                _serialize_field_report(
                    r,
                    submitter_name=users_map.get(r.submitted_by_user_id),
                    reviewer_name=users_map.get(r.reviewed_by_user_id) if r.reviewed_by_user_id else None,
                )
                for r in rows
            ],
        }

    @router.post("/field-reports", tags=["Field Reporting"])
    async def create_field_report(
        request: Request,
        location_name: str = Form(..., min_length=2, max_length=200),
        latitude: float = Form(..., ge=-90.0, le=90.0),
        longitude: float = Form(..., ge=-180.0, le=180.0),
        observed_at_utc: str = Form(...),
        category: str = Form(..., min_length=2, max_length=64),
        severity_observation: str = Form(..., pattern=r"^(Low|Moderate|High|Critical)$"),
        description: str = Form(..., min_length=5, max_length=2000),
        road_obstruction: str = Form(default="none"),
        notes: str | None = Form(default=None),
        photo: UploadFile | None = File(default=None),
        user: User = Depends(require_roles("field_officer", "research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        _enforce_rate(write_limiter, request, "field_report_create")
        if latitude == 0.0 and longitude == 0.0:
            raise HTTPException(status_code=422, detail="Zero (0, 0) coordinates are invalid.")

        upload_meta = None
        if photo is not None and photo.filename:
            raw = await photo.read()
            try:
                upload_meta = save_validated_photo_upload(raw, uploads_dir)
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=str(exc)) from exc

        within = raster_service.is_within_pilot_boundary(latitude, longitude)
        report = FieldReport(
            study_area_slug="dima-hasao",
            location_name=location_name.strip(),
            latitude=round(latitude, 6),
            longitude=round(longitude, 6),
            geom=f"POINT({longitude:.6f} {latitude:.6f})",
            within_pilot_boundary=within,
            observed_at_utc=observed_at_utc.strip(),
            category=category.strip(),
            severity_observation=severity_observation,
            description=description.strip(),
            road_obstruction=road_obstruction.strip()[:64],
            notes=notes.strip()[:1000] if notes else None,
            photo_filename=upload_meta.filename if upload_meta else None,
            photo_mime=upload_meta.mime_type if upload_meta else None,
            photo_size_bytes=upload_meta.size_bytes if upload_meta else None,
            photo_sha256=upload_meta.sha256 if upload_meta else None,
            verification_status="pending",
            submitted_by_user_id=user.id,
        )
        db.add(report)
        db.flush()
        _record_audit(
            db,
            "field_report_submitted",
            "field_report",
            str(report.id),
            actor=user,
            details={"within_pilot": within, "has_photo": upload_meta is not None},
        )
        db.commit()
        db.refresh(report)
        return _serialize_field_report(report, submitter_name=user.username)

    @router.get("/field-reports/photos/{filename}", tags=["Field Reporting"])
    def get_field_report_photo(filename: str):
        resolved = resolve_confined_upload(filename, uploads_dir)
        if not resolved:
            raise HTTPException(status_code=404, detail="Photo not found.")
        return FileResponse(resolved)

    @router.patch("/field-reports/{report_id}/review", tags=["Field Reporting"])
    def review_field_report(
        report_id: int,
        body: ReviewFieldReportRequest,
        reviewer: User = Depends(require_roles("research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        report = db.get(FieldReport, report_id)
        if not report:
            raise HTTPException(status_code=404, detail="Field report not found.")
        prev_status = report.verification_status
        report.verification_status = body.verification_status
        report.reviewed_by_user_id = reviewer.id
        report.review_notes = body.review_notes.strip()
        report.reviewed_at = datetime.now(timezone.utc)
        _record_audit(
            db,
            "field_report_reviewed",
            "field_report",
            str(report.id),
            actor=reviewer,
            details={"previous_status": prev_status, "new_status": body.verification_status},
        )
        db.commit()
        db.refresh(report)
        submitter = db.get(User, report.submitted_by_user_id)
        return _serialize_field_report(
            report,
            submitter_name=submitter.username if submitter else None,
            reviewer_name=reviewer.username,
        )

    # =====================================================================
    # 5. EXPERIMENTAL ALERT & RESPONSE WORKFLOW (/api/v1/alerts/*)
    # =====================================================================
    @router.get("/alerts", tags=["Experimental Alerts"])
    def list_experimental_alerts(
        status: str | None = Query(default=None),
        limit: int = Query(default=50, ge=1, le=200),
        offset: int = Query(default=0, ge=0),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        q = select(ExperimentalAlert).order_by(desc(ExperimentalAlert.created_at))
        if status:
            q = q.where(ExperimentalAlert.status == status)
        total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
        rows = db.scalars(q.offset(offset).limit(limit)).all()
        uids = {a.created_by_user_id for a in rows} | {a.reviewed_by_user_id for a in rows if a.reviewed_by_user_id}
        umap = {u.id: u.username for u in db.scalars(select(User).where(User.id.in_(uids))).all()} if uids else {}
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "official_warning_notice": "All items in this registry are EXPERIMENTAL RESEARCH DRAFTS, never official NDMA/SDMA/IMD warnings.",
            "items": [
                _serialize_alert(
                    a,
                    creator_name=umap.get(a.created_by_user_id),
                    reviewer_name=umap.get(a.reviewed_by_user_id) if a.reviewed_by_user_id else None,
                )
                for a in rows
            ],
        }

    @router.post("/alerts", tags=["Experimental Alerts"])
    def create_experimental_alert(
        body: CreateAlertRequest,
        request: Request,
        actor: User = Depends(require_roles("research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        _enforce_rate(write_limiter, request, "alert_create")
        hazard = compute_dynamic_hazard_assessment(
            lat=body.latitude,
            lon=body.longitude,
            pilot_dir=pilot_dir,
            raster_service=raster_service,
            rainfall_service=rainfall_service,
            exposure_index=exposure_index,
            radius_km=body.radius_km,
        )
        alert = ExperimentalAlert(
            classification="EXPERIMENTAL_RESEARCH_DRAFT",
            study_area_slug="dima-hasao",
            title=body.title.strip(),
            geographic_area=body.geographic_area.strip(),
            latitude=round(body.latitude, 6),
            longitude=round(body.longitude, 6),
            severity_tier=body.severity_tier,
            severity_rationale=body.severity_rationale.strip(),
            hazard_evidence_json={
                "landslide_probability": None,
                "observed_rainfall": hazard["observed_rainfall"],
                "forecast_rainfall": hazard["forecast_rainfall"],
                "response_priority": hazard["response_priority"],
            },
            source_timestamps_json={
                "assessed_at_utc": hazard["assessed_at_utc"],
                "imerg_latest_date": hazard["observed_rainfall"]["latest_observation_date"],
                "gfs_init_time_utc": (hazard["forecast_rainfall"] or {}).get("init_time_utc"),
            },
            affected_infrastructure_json=hazard["infrastructure_exposure"],
            inspection_priorities_json=body.inspection_priorities or [
                "Verify slope drainage culverts along mapped transport corridor",
                "Log geotagged field observations via authenticated Field Reports form",
            ],
            status="pending_review",
            created_by_user_id=actor.id,
            dry_run_notifications_json=[],
        )
        db.add(alert)
        db.flush()
        _record_audit(
            db,
            "experimental_alert_created",
            "experimental_alert",
            str(alert.id),
            actor=actor,
            details={"severity_tier": body.severity_tier, "classification": alert.classification},
        )
        db.commit()
        db.refresh(alert)
        return _serialize_alert(alert, creator_name=actor.username)

    @router.patch("/alerts/{alert_id}/review", tags=["Experimental Alerts"])
    def review_experimental_alert(
        alert_id: int,
        body: ReviewAlertRequest,
        reviewer: User = Depends(require_roles("research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        alert = db.get(ExperimentalAlert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Experimental alert not found.")
        prev = alert.status
        alert.status = body.status
        alert.reviewed_by_user_id = reviewer.id
        alert.review_comment = body.review_comment.strip()
        _record_audit(
            db,
            "experimental_alert_reviewed",
            "experimental_alert",
            str(alert.id),
            actor=reviewer,
            details={"previous_status": prev, "new_status": body.status},
        )
        db.commit()
        db.refresh(alert)
        creator = db.get(User, alert.created_by_user_id)
        return _serialize_alert(
            alert,
            creator_name=creator.username if creator else None,
            reviewer_name=reviewer.username,
        )

    @router.post("/alerts/{alert_id}/dry-run-notify", tags=["Experimental Alerts"])
    def dry_run_alert_notification(
        alert_id: int,
        body: DryRunNotifyRequest,
        actor: User = Depends(require_roles("research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        alert = db.get(ExperimentalAlert, alert_id)
        if not alert:
            raise HTTPException(status_code=404, detail="Experimental alert not found.")
        entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "delivery_mode": "DRY_RUN_NO_EXTERNAL_DISPATCH",
            "channels_simulated": body.channels,
            "target_group": body.target_group,
            "triggered_by": actor.username,
            "note": "Dry-run adapter test only. Zero public SMS, cell broadcast, or government portal messages were sent.",
        }
        history = list(alert.dry_run_notifications_json or [])
        history.append(entry)
        alert.dry_run_notifications_json = history
        _record_audit(
            db,
            "experimental_alert_dry_run_notify",
            "experimental_alert",
            str(alert.id),
            actor=actor,
            details=entry,
        )
        db.commit()
        db.refresh(alert)
        return {"alert_id": alert.id, "dry_run_entry": entry, "total_dry_runs": len(history)}

    # =====================================================================
    # 6. MONITORING, REGIONAL EXPANSION & AUDIT LOGS
    # =====================================================================
    @router.get("/monitoring/status", tags=["Automated Monitoring"])
    def get_monitoring_status(db: Session = Depends(get_platform_db)) -> dict[str, Any]:
        runs = db.scalars(select(MonitoringRun).order_by(desc(MonitoringRun.started_at)).limit(10)).all()
        if not runs:
            latest = execute_monitoring_cycle(db, pilot_dir=pilot_dir, refresh_live_gfs=False)
            return {"latest_run": latest, "recent_runs": [latest]}
        serialized = [
            {
                "run_id": r.id,
                "job_name": r.job_name,
                "status": r.status,
                "started_at": r.started_at.isoformat(),
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "observed_rainfall_latest_date": r.observed_rainfall_latest_date,
                "observed_rainfall_stale": r.observed_rainfall_stale,
                "forecast_init_time_utc": r.forecast_init_time_utc,
                "forecast_stale": r.forecast_stale,
                "summary": r.summary_json,
                "error_message": r.error_message,
            }
            for r in runs
        ]
        return {"latest_run": serialized[0], "recent_runs": serialized}

    @router.post("/monitoring/run", tags=["Automated Monitoring"])
    def trigger_monitoring_run(
        refresh_live_gfs: bool = Query(default=False),
        actor: User = Depends(require_roles("research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        result = execute_monitoring_cycle(db, pilot_dir=pilot_dir, refresh_live_gfs=refresh_live_gfs)
        _record_audit(
            db,
            "monitoring_cycle_triggered",
            "monitoring_run",
            str(result["run_id"]),
            actor=actor,
            details={"refresh_live_gfs": refresh_live_gfs, "status": result["status"]},
        )
        db.commit()
        return result

    @router.get("/regions", tags=["Regional Expansion"])
    def list_regional_coverage(db: Session = Depends(get_platform_db)) -> dict[str, Any]:
        states = ensure_regional_coverage_seeded(db)
        return {
            "total_states_configured": len(states),
            "pilot_active_states": sum(1 for s in states if s["environmental_data_available"]),
            "validated_ml_states": sum(1 for s in states if s["model_validated"]),
            "states": states,
        }

    @router.get("/audit-logs", tags=["Security & Audit"])
    def list_audit_logs(
        limit: int = Query(default=50, ge=1, le=200),
        _actor: User = Depends(require_roles("research_analyst", "admin")),
        db: Session = Depends(get_platform_db),
    ) -> list[dict[str, Any]]:
        rows = db.scalars(select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit)).all()
        return [
            {
                "id": r.id,
                "actor_username": r.actor_username,
                "actor_role": r.actor_role,
                "action": r.action,
                "resource_type": r.resource_type,
                "resource_id": r.resource_id,
                "details": r.details_json,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    # =====================================================================
    # 7. GROUNDED GEMINI EXPLANATION ASSISTANT (/api/v1/assistant/*)
    # =====================================================================
    @router.get("/assistant/models", tags=["Gemini Explanation Assistant"])
    async def discover_gemini_models() -> dict[str, Any]:
        api_key = (
            settings.gemini_api_key.get_secret_value()
            if settings.gemini_api_key
            else os.environ.get("GEMINI_API_KEY", "")
        ).strip()
        model_name = settings.gemini_model or os.environ.get("GEMINI_MODEL", "gemini-4-hydrogen")
        if not api_key or api_key == "MY_GEMINI_API_KEY":
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "gemini_not_configured",
                    "configured_model": model_name,
                    "message": "GEMINI_API_KEY is not configured on the backend server.",
                },
            )
        url = "https://generativelanguage.googleapis.com/v1beta/models"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    url,
                    headers={"x-goog-api-key": api_key, "User-Agent": "aistudio-build"},
                )
                resp.raise_for_status()
                models_raw = resp.json().get("models", [])
        except httpx.HTTPStatusError as exc:
            err_msg = None
            try:
                err_msg = exc.response.json().get("error", {}).get("message")
            except Exception:
                err_msg = None
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_gemini_error",
                    "configured_model": model_name,
                    "upstream_status": exc.response.status_code,
                    "upstream_message": err_msg or f"HTTP {exc.response.status_code}",
                },
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_gemini_error",
                    "configured_model": model_name,
                    "message": f"Model discovery failed: {type(exc).__name__}",
                },
            ) from exc

        gen_models = [
            {
                "name": str(m.get("name", "")).removeprefix("models/"),
                "display_name": m.get("displayName"),
                "supported_methods": m.get("supportedGenerationMethods", []),
            }
            for m in models_raw
            if "generateContent" in (m.get("supportedGenerationMethods") or [])
        ]
        names = [m["name"] for m in gen_models]
        return {
            "discovery_source": "https://generativelanguage.googleapis.com/v1beta/models",
            "configured_model": model_name,
            "configured_model_verified": model_name in names,
            "total_generate_content_models": len(gen_models),
            "gemini_models_sample": [m["name"] for m in gen_models if "gemini" in m["name"]][:25],
        }

    @router.post("/assistant/explain", tags=["Gemini Explanation Assistant"])
    async def explain_with_gemini(
        body: AssistantExplainRequest,
        request: Request,
        db: Session = Depends(get_platform_db),
    ) -> dict[str, Any]:
        _enforce_rate(ai_limiter, request, "assistant_explain")
        clean_q, injection_flagged = sanitize_user_question(body.question)
        if injection_flagged:
            _record_audit(
                db,
                "prompt_injection_blocked",
                "assistant",
                details={"lat": body.lat, "lon": body.lon},
            )
            db.commit()
            raise HTTPException(
                status_code=400,
                detail=(
                    "Your query triggered prompt-security guardrails. Ask a factual question about "
                    "observed terrain, soil, rainfall, infrastructure exposure, data gaps, or model readiness."
                ),
            )

        evidence = compute_dynamic_hazard_assessment(
            lat=body.lat,
            lon=body.lon,
            pilot_dir=pilot_dir,
            raster_service=raster_service,
            rainfall_service=rainfall_service,
            exposure_index=exposure_index,
            radius_km=body.radius_km,
        )
        pending_reports = db.scalar(
            select(func.count()).select_from(FieldReport).where(FieldReport.verification_status == "pending")
        ) or 0
        verified_reports = db.scalar(
            select(func.count()).select_from(FieldReport).where(FieldReport.verification_status == "verified")
        ) or 0
        evidence["field_report_summary"] = {
            "verified_count": verified_reports,
            "pending_unverified_count": pending_reports,
            "trust_rule": "Unverified pending field reports are untrusted until reviewed by an analyst or admin.",
        }

        api_key = (
            settings.gemini_api_key.get_secret_value()
            if settings.gemini_api_key
            else os.environ.get("GEMINI_API_KEY", "")
        ).strip()
        model_name = settings.gemini_model or os.environ.get("GEMINI_MODEL", "gemini-4-hydrogen")

        if not api_key or api_key == "MY_GEMINI_API_KEY":
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "gemini_not_configured",
                    "model": model_name,
                    "message": "GEMINI_API_KEY is not configured on the backend server. Returning structured backend evidence only.",
                    "grounded_evidence": evidence,
                },
            )

        system_instruction = (
            "You are the GeoResilience-NER 2.0 scientific explanation assistant for Dima Hasao, Assam.\n"
            "STRICT RULES:\n"
            "1. Ground EVERY statement strictly in the provided JSON evidence bundle.\n"
            "2. Distinguish measured historical rainfall (NASA GPM IMERG) from experimental forecast rainfall (NOAA GFS).\n"
            "3. Explicitly state that no landslide ML model is validated yet (landslide_probability = null) and REFUSE to invent failure probabilities or Factor of Safety.\n"
            "4. Never impersonate NDMA, SDMA, IMD, or GSI or issue official government emergency warnings.\n"
            "5. Explicitly state missing data (GSI 1:50k lithology/faults, SMAP soil moisture, 2024–2026 IMERG gap, rural OSM completeness).\n"
            "6. Treat pending field reports as untrusted until reviewed."
        )
        user_payload = (
            f"STRUCTURED_EVIDENCE_JSON:\n{json.dumps(evidence, indent=2)}\n\n"
            f"UNTRUSTED_USER_QUESTION:\n<<<{clean_q}>>>\n\n"
            "Provide a clear, concise, evidence-linked explanation citing the exact data sources and limitations."
        )

        import asyncio

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resp = None
                for attempt in range(2):
                    resp = await client.post(
                        url,
                        headers={
                            "Content-Type": "application/json",
                            "x-goog-api-key": api_key,
                            "User-Agent": "aistudio-build",
                        },
                        json={
                            "system_instruction": {"parts": [{"text": system_instruction}]},
                            "contents": [{"role": "user", "parts": [{"text": user_payload}]}],
                        },
                    )
                    if resp.status_code in {429, 503} and attempt == 0:
                        await asyncio.sleep(1.5)
                        continue
                    break
                assert resp is not None
                resp.raise_for_status()
                data = resp.json()
                parts = (
                    ((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or []
                )
                answer_text = "\n".join(p.get("text", "") for p in parts if p.get("text")).strip()
        except httpx.HTTPStatusError as exc:
            err_msg = None
            try:
                err_msg = exc.response.json().get("error", {}).get("message")
            except Exception:
                err_msg = None
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_gemini_error",
                    "model": model_name,
                    "upstream_status": exc.response.status_code,
                    "upstream_message": err_msg or f"HTTP {exc.response.status_code}",
                    "message": f"Gemini API request failed (HTTP {exc.response.status_code}).",
                    "grounded_evidence": evidence,
                },
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status_code=502,
                detail={
                    "error": "upstream_gemini_error",
                    "model": model_name,
                    "message": f"Gemini API request failed: {type(exc).__name__}",
                    "grounded_evidence": evidence,
                },
            ) from exc

        return {
            "source": "gemini-ai-grounded",
            "model": model_name,
            "answer": answer_text,
            "landslide_probability": None,
            "grounded_evidence": evidence,
            "disclaimer": "Evidence-linked AI explanation only — not a numerical landslide prediction or official warning.",
        }

    return router
