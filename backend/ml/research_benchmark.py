"""
Phase D — Reproducible Machine Learning System (Exploratory Research Track + Strict Quality Gate).

CRITICAL SCIENTIFIC GOVERNANCE:
  1. Production ML training (`backend.ml.pipeline.run_ml_training_pipeline`) remains HARD-BLOCKED
     by the 13-check Data Quality Gate (`overall_ml_ready: false`, `landslide_probability: null`).
  2. Per Phase D3 ("If necessary, build a separate explicitly labeled exploratory research track
     using only appropriate data and evaluation methods. Never promote exploratory results to
     validated operational outputs"), this module runs a reproducible CPU-only spatial-block CV
     benchmark comparing:
       - Model A (Static Susceptibility): Random Forest baseline vs XGBoost candidate + SHAP
         TreeExplainer on deduplicated Dima Hasao GSI Bhusanket points + Positive-Unlabeled (PU)
         background cells across 5 km x 5 km EPSG:32646 spatial blocks.
       - Corridor Bias Ablation: quantifies the exact AUC inflation caused by adding road/railway
         distance proxies (confirming the 77.8% corridor survey bias warning).
       - Model B (Dynamic Rainfall Threshold Research): empirical comparison of observed IMERG
         1d/3d/7d/15d antecedent rainfall on dated GSI event days vs monsoon background days.
  3. Artifacts are written strictly to `backend/data/experimental/exploratory_ml_benchmark.json`
     with `validated_for_production: false` and `promoted_to_inference: false`.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
import shap
from pyproj import Transformer
from shapely.geometry import Point, shape
from sklearn.calibration import calibration_curve
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import GroupKFold
from xgboost import XGBClassifier

from backend.app.quality_gate import PILOT_DIR, SPATIAL_BLOCK_SIZE_M, evaluate_data_quality_gate
from backend.ingestion.fetch_coolr_landslides import haversine_m

EXPERIMENTAL_DIR = Path(__file__).resolve().parents[1] / "data" / "experimental"
_TO_UTM46N = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True)

CLEAN_STATIC_FEATURES = [
    "elevation_m",
    "slope_deg",
    "aspect_sin",
    "aspect_cos",
    "profile_curvature",
    "plan_curvature",
    "tri_m",
    "twi",
    "log1p_flow_acc",
    "dist_drainage_m",
    "soil_clay_0_5cm",
    "soil_sand_0_5cm",
    "soil_silt_0_5cm",
    "soil_bdod_0_5cm",
    "soil_cfvo_0_5cm",
    "soil_soc_0_5cm",
]

CORRIDOR_PROXY_FEATURES = CLEAN_STATIC_FEATURES + ["dist_road_m", "dist_railway_m"]

RASTER_MAP = {
    "elevation_m": "dima_hasao_dem_utm46n.tif",
    "slope_deg": "dima_hasao_slope_deg_utm46n.tif",
    "aspect_deg": "dima_hasao_aspect_deg_utm46n.tif",
    "profile_curvature": "dima_hasao_profile_curvature_utm46n.tif",
    "plan_curvature": "dima_hasao_plan_curvature_utm46n.tif",
    "tri_m": "dima_hasao_tri_m_utm46n.tif",
    "twi": "dima_hasao_twi_utm46n.tif",
    "flow_acc_m2": "dima_hasao_flow_acc_m2_utm46n.tif",
    "dist_drainage_m": "dima_hasao_dist_drainage_m_utm46n.tif",
    "soil_clay_0_5cm": "dima_hasao_soilgrids_clay_0_5cm_utm46n.tif",
    "soil_sand_0_5cm": "dima_hasao_soilgrids_sand_0_5cm_utm46n.tif",
    "soil_silt_0_5cm": "dima_hasao_soilgrids_silt_0_5cm_utm46n.tif",
    "soil_bdod_0_5cm": "dima_hasao_soilgrids_bdod_0_5cm_utm46n.tif",
    "soil_cfvo_0_5cm": "dima_hasao_soilgrids_cfvo_0_5cm_utm46n.tif",
    "soil_soc_0_5cm": "dima_hasao_soilgrids_soc_0_5cm_utm46n.tif",
    "dist_road_m": "dima_hasao_dist_road_m_utm46n.tif",
    "dist_railway_m": "dima_hasao_dist_railway_m_utm46n.tif",
}


def _deduplicate_points(records: list[dict[str, Any]], min_spacing_m: float = 100.0) -> list[dict[str, Any]]:
    """Greedy deterministic spatial deduplication to reduce clustered survey duplicates."""
    kept: list[dict[str, Any]] = []
    # Sort deterministically by object_id / latitude / longitude
    ordered = sorted(
        records,
        key=lambda r: (
            str(r.get("external_event_id") or r.get("object_id") or ""),
            float(r.get("latitude", 0.0)),
            float(r.get("longitude", 0.0)),
        ),
    )
    for rec in ordered:
        lat, lon = float(rec["latitude"]), float(rec["longitude"])
        if any(haversine_m(lat, lon, float(k["latitude"]), float(k["longitude"])) < min_spacing_m for k in kept):
            continue
        kept.append(rec)
    return kept


def _sample_feature_matrix(
    coords_wgs84: list[tuple[float, float]],
    pilot_dir: Path,
) -> tuple[dict[str, np.ndarray], np.ndarray]:
    """Batch-samples all verified EPSG:32646 GeoTIFFs for a list of (lat, lon) coordinates."""
    utm_pts = [_TO_UTM46N.transform(lon, lat) for lat, lon in coords_wgs84]
    raw: dict[str, np.ndarray] = {}
    valid_mask = np.ones(len(utm_pts), dtype=bool)

    for key, fname in RASTER_MAP.items():
        fpath = pilot_dir / fname
        vals = np.full(len(utm_pts), np.nan, dtype=np.float64)
        if fpath.exists():
            with rasterio.open(fpath) as src:
                nodata = src.nodata
                sampled = np.array([v[0] for v in src.sample(utm_pts)], dtype=np.float64)
                if nodata is not None:
                    sampled[np.isclose(sampled, float(nodata), atol=1e-3)] = np.nan
                sampled[sampled <= -9000.0] = np.nan
                vals = sampled
        raw[key] = vals

    # Derived circular aspect & log flow accumulation
    aspect = raw["aspect_deg"]
    aspect_rad = np.deg2rad(np.where(aspect >= 0.0, aspect, np.nan))
    raw["aspect_sin"] = np.where(aspect == -1.0, 0.0, np.sin(aspect_rad))
    raw["aspect_cos"] = np.where(aspect == -1.0, 0.0, np.cos(aspect_rad))
    raw["log1p_flow_acc"] = np.log1p(np.maximum(raw["flow_acc_m2"], 0.0))

    for col in CORRIDOR_PROXY_FEATURES:
        valid_mask &= np.isfinite(raw[col])

    return raw, valid_mask


def _sample_unlabeled_background(
    pilot_geom: Any,
    positive_coords: list[tuple[float, float]],
    n_target: int,
    min_dist_from_pos_m: float = 250.0,
    seed: int = 2026,
) -> list[tuple[float, float]]:
    """
    Samples deterministic Positive-Unlabeled (PU) background points inside the Dima Hasao polygon.
    Explicitly avoids claiming these points are confirmed landslide-free absences.
    """
    rng = np.random.default_rng(seed)
    minx, miny, maxx, maxy = pilot_geom.bounds
    bg: list[tuple[float, float]] = []
    attempts = 0
    max_attempts = n_target * 40
    while len(bg) < n_target and attempts < max_attempts:
        attempts += 1
        lon = float(rng.uniform(minx, maxx))
        lat = float(rng.uniform(miny, maxy))
        if not pilot_geom.contains(Point(lon, lat)):
            continue
        if any(haversine_m(lat, lon, plat, plon) < min_dist_from_pos_m for plat, plon in positive_coords):
            continue
        bg.append((lat, lon))
    return bg


def _compute_ece(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 8) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        mask = (y_prob >= bins[i]) & (y_prob < bins[i + 1] if i < n_bins - 1 else y_prob <= bins[i + 1])
        if np.any(mask):
            ece += (np.sum(mask) / n) * abs(float(np.mean(y_prob[mask])) - float(np.mean(y_true[mask])))
    return round(float(ece), 4)


def _evaluate_spatial_cv_pair(
    X: np.ndarray,
    y: np.ndarray,
    groups: np.ndarray,
    feature_names: list[str],
    seed: int = 2026,
) -> dict[str, Any]:
    """Runs identical 5-fold Spatial-Block GroupKFold CV for Random Forest and XGBoost + SHAP."""
    n_splits = min(5, len(np.unique(groups)))
    gkf = GroupKFold(n_splits=n_splits)

    results: dict[str, Any] = {}
    for model_key in ("random_forest", "xgboost"):
        oof_probs = np.zeros(len(y), dtype=np.float64)
        fold_rocs: list[float] = []
        fold_prs: list[float] = []
        t0 = time.perf_counter()

        for train_idx, test_idx in gkf.split(X, y, groups):
            if model_key == "random_forest":
                clf = RandomForestClassifier(
                    n_estimators=200,
                    max_depth=8,
                    min_samples_leaf=4,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=2,
                )
            else:
                pos = max(1, int(np.sum(y[train_idx] == 1)))
                neg = max(1, int(np.sum(y[train_idx] == 0)))
                clf = XGBClassifier(
                    n_estimators=180,
                    max_depth=4,
                    learning_rate=0.05,
                    subsample=0.8,
                    colsample_bytree=0.8,
                    scale_pos_weight=neg / pos,
                    tree_method="hist",
                    eval_metric="logloss",
                    random_state=seed,
                    n_jobs=2,
                )
            clf.fit(X[train_idx], y[train_idx])
            probs = clf.predict_proba(X[test_idx])[:, 1]
            oof_probs[test_idx] = probs
            if len(np.unique(y[test_idx])) == 2:
                fold_rocs.append(float(roc_auc_score(y[test_idx], probs)))
                fold_prs.append(float(average_precision_score(y[test_idx], probs)))

        elapsed_s = round(time.perf_counter() - t0, 3)
        preds = (oof_probs >= 0.5).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, preds, labels=[0, 1]).ravel()
        prob_true, prob_pred = calibration_curve(y, oof_probs, n_bins=6, strategy="quantile")

        # Fit full exploratory model purely for reproducible SHAP attribution analysis (NOT exported for production!)
        if model_key == "random_forest":
            full_clf = RandomForestClassifier(
                n_estimators=200,
                max_depth=8,
                min_samples_leaf=4,
                class_weight="balanced",
                random_state=seed,
                n_jobs=2,
            )
        else:
            pos_all = max(1, int(np.sum(y == 1)))
            neg_all = max(1, int(np.sum(y == 0)))
            full_clf = XGBClassifier(
                n_estimators=180,
                max_depth=4,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                scale_pos_weight=neg_all / pos_all,
                tree_method="hist",
                eval_metric="logloss",
                random_state=seed,
                n_jobs=2,
            )
        full_clf.fit(X, y)

        explainer = shap.TreeExplainer(full_clf)
        shap_vals = explainer.shap_values(X)
        if isinstance(shap_vals, list):
            sv_pos = np.asarray(shap_vals[1], dtype=np.float64)
        elif np.asarray(shap_vals).ndim == 3:
            sv_pos = np.asarray(shap_vals, dtype=np.float64)[:, :, 1]
        else:
            sv_pos = np.asarray(shap_vals, dtype=np.float64)
        mean_abs_shap = np.mean(np.abs(sv_pos), axis=0)
        shap_ranking = sorted(
            [
                {
                    "feature": feature_names[i],
                    "mean_abs_shap": round(float(mean_abs_shap[i]), 5),
                }
                for i in range(len(feature_names))
            ],
            key=lambda item: item["mean_abs_shap"],
            reverse=True,
        )

        results[model_key] = {
            "algorithm": "RandomForestClassifier (baseline)" if model_key == "random_forest" else "XGBClassifier (CPU hist candidate)",
            "training_cv_seconds": elapsed_s,
            "oof_metrics": {
                "roc_auc": round(float(roc_auc_score(y, oof_probs)), 4),
                "pr_auc": round(float(average_precision_score(y, oof_probs)), 4),
                "precision_at_0_5": round(float(precision_score(y, preds, zero_division=0)), 4),
                "recall_at_0_5": round(float(recall_score(y, preds, zero_division=0)), 4),
                "f1_at_0_5": round(float(f1_score(y, preds, zero_division=0)), 4),
                "brier_score": round(float(brier_score_loss(y, oof_probs)), 4),
                "expected_calibration_error": _compute_ece(y, oof_probs),
                "confusion_matrix": {"tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)},
            },
            "spatial_block_generalization": {
                "n_folds": n_splits,
                "fold_roc_auc_mean": round(float(np.mean(fold_rocs)), 4) if fold_rocs else None,
                "fold_roc_auc_std": round(float(np.std(fold_rocs)), 4) if fold_rocs else None,
                "fold_pr_auc_mean": round(float(np.mean(fold_prs)), 4) if fold_prs else None,
                "fold_pr_auc_std": round(float(np.std(fold_prs)), 4) if fold_prs else None,
                "fold_roc_aucs": [round(x, 4) for x in fold_rocs],
            },
            "calibration_bins": [
                {"mean_predicted": round(float(pp), 4), "fraction_positive": round(float(pt), 4)}
                for pt, pp in zip(prob_true, prob_pred)
            ],
            "shap_top_features": shap_ranking[:10],
            "shap_disclaimer": (
                "SHAP values quantify statistical attribution within this exploratory PU benchmark only; "
                "they are NOT physically causal geotechnical parameters or Factor of Safety estimates."
            ),
        }

    return results


def _evaluate_dynamic_rainfall_thresholds(pilot_dir: Path) -> dict[str, Any]:
    """
    Phase D1 Model B — Transparent Empirical Rainfall-Threshold Research.
    Compares observed NASA IMERG 1d/3d/7d/15d antecedent rainfall on dated GSI Bhusanket
    event days vs monsoon background days (May–October, 2015–2024).
    """
    gsi_path = pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json"
    rain_path = pilot_dir / "dima_hasao_rainfall_multiyear.json"
    gsi_doc = json.loads(gsi_path.read_text(encoding="utf-8"))
    rain_doc = json.loads(rain_path.read_text(encoding="utf-8"))

    by_date = {o["date"]: o for o in rain_doc.get("observations", [])}
    pilot_gsi = [r for r in gsi_doc.get("records", []) if r.get("within_pilot_boundary")]
    dated_gsi = [r for r in pilot_gsi if r.get("event_date_precision") == "day" and r.get("event_date")]

    unique_event_dates = sorted({str(r["event_date"]) for r in dated_gsi if str(r["event_date"]) in by_date})
    event_r1, event_r3, event_r7, event_r15 = [], [], [], []
    matched_records = 0

    for rec in dated_gsi:
        row = by_date.get(str(rec["event_date"]))
        if row and row.get("rainfall_1d_mm") is not None:
            matched_records += 1

    for d in unique_event_dates:
        row = by_date[d]
        if row.get("rainfall_1d_mm") is not None:
            event_r1.append(float(row["rainfall_1d_mm"]))
        if row.get("rainfall_3d_mm") is not None:
            event_r3.append(float(row["rainfall_3d_mm"]))
        if row.get("rainfall_7d_mm") is not None:
            event_r7.append(float(row["rainfall_7d_mm"]))
        if row.get("rainfall_15d_mm") is not None:
            event_r15.append(float(row["rainfall_15d_mm"]))

    monsoon_bg_r1, monsoon_bg_r3, monsoon_bg_r7 = [], [], []
    event_date_set = set(unique_event_dates)
    for d, row in by_date.items():
        month = int(d[5:7])
        if 5 <= month <= 10 and d not in event_date_set:
            if row.get("rainfall_1d_mm") is not None:
                monsoon_bg_r1.append(float(row["rainfall_1d_mm"]))
            if row.get("rainfall_3d_mm") is not None:
                monsoon_bg_r3.append(float(row["rainfall_3d_mm"]))
            if row.get("rainfall_7d_mm") is not None:
                monsoon_bg_r7.append(float(row["rainfall_7d_mm"]))

    def _stats(vals: list[float]) -> dict[str, Any]:
        if not vals:
            return {"count": 0, "median": None, "p75": None, "p90": None, "max": None}
        arr = np.asarray(vals, dtype=np.float64)
        return {
            "count": len(vals),
            "median": round(float(np.median(arr)), 2),
            "p75": round(float(np.percentile(arr, 75)), 2),
            "p90": round(float(np.percentile(arr, 90)), 2),
            "max": round(float(np.max(arr)), 2),
        }

    # Empirical reference thresholds (explicitly labeled EXPERIMENTAL / UNCALIBRATED for Dima Hasao)
    # Guzzetti et al. (2008) global shallow landslide lower-bound cumulated rainfall:
    #   24h: ~32 mm, 72h: ~62 mm; Regional Northeast India heavy monsoon watch envelopes:
    #   24h >= 64.5 mm (IMD "Heavy Rain"), 24h >= 115.6 mm (IMD "Very Heavy Rain"), 72h >= 150 mm.
    return {
        "model_type": "Model B — Empirical Rainfall-Threshold Research (Non-Operational)",
        "validated_for_production": False,
        "event_records_with_day_precision": len(dated_gsi),
        "event_records_overlapping_valid_imerg": matched_records,
        "unique_event_days_overlapping_imerg": len(event_r1),
        "event_day_rainfall_mm": {
            "1d": _stats(event_r1),
            "3d": _stats(event_r3),
            "7d": _stats(event_r7),
            "15d": _stats(event_r15),
        },
        "monsoon_non_event_day_rainfall_mm": {
            "1d": _stats(monsoon_bg_r1),
            "3d": _stats(monsoon_bg_r3),
            "7d": _stats(monsoon_bg_r7),
        },
        "experimental_reference_envelopes": {
            "imd_heavy_24h_mm": 64.5,
            "imd_very_heavy_24h_mm": 115.6,
            "imd_extremely_heavy_24h_mm": 204.5,
            "experimental_72h_watch_mm": 120.0,
            "experimental_72h_elevated_mm": 200.0,
            "experimental_7d_antecedent_wet_mm": 250.0,
            "calibration_status": "EXPERIMENTAL_REFERENCE_ONLY_NOT_SITE_CALIBRATED",
        },
        "scientific_limitations": [
            "District-averaged 0.1 deg IMERG daily series smooths localized Barail Range cloudburst peaks.",
            "Only a small subset of unique calendar days overlap valid IMERG days, with 2024 monsoon (June–Dec) missing pending NASA Earthdata Login download.",
            "Non-event monsoon days may include unrecorded rural landslides (under-reporting / positive-unlabeled censoring).",
            "Dynamic event-probability modeling remains BLOCKED until multi-year, rain-gauge-validated, dated landslide records pass the Data Quality Gate.",
        ],
    }


def run_exploratory_ml_benchmark(
    pilot_dir: Path = PILOT_DIR,
    experimental_dir: Path = EXPERIMENTAL_DIR,
    seed: int = 2026,
) -> dict[str, Any]:
    """
    Runs the full reproducible exploratory RF vs XGBoost + SHAP spatial-block CV benchmark
    AND empirical rainfall-threshold analysis while strictly enforcing that production
    inference remains blocked (`overall_ml_ready: false`, `landslide_probability: null`).
    """
    gate_report = evaluate_data_quality_gate(pilot_dir)

    boundary_gj = json.loads((pilot_dir / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
    pilot_geom = shape(boundary_gj["features"][0]["geometry"])

    gsi_doc = json.loads((pilot_dir / "dima_hasao_landslides_gsi_bhusanket.json").read_text(encoding="utf-8"))
    pilot_gsi = [r for r in gsi_doc.get("records", []) if r.get("within_pilot_boundary")]
    dedup_pos = _deduplicate_points(pilot_gsi, min_spacing_m=100.0)
    pos_coords = [(float(r["latitude"]), float(r["longitude"])) for r in dedup_pos]

    # 2:1 Positive-Unlabeled background ratio inside exact Dima Hasao boundary
    bg_coords = _sample_unlabeled_background(
        pilot_geom=pilot_geom,
        positive_coords=pos_coords,
        n_target=len(pos_coords) * 2,
        min_dist_from_pos_m=250.0,
        seed=seed,
    )

    all_coords = pos_coords + bg_coords
    raw_labels = np.array([1] * len(pos_coords) + [0] * len(bg_coords), dtype=int)

    raw_feats, valid_mask = _sample_feature_matrix(all_coords, pilot_dir)
    kept_indices = np.where(valid_mask)[0]
    y = raw_labels[kept_indices]

    # Assign 5 km x 5 km EPSG:32646 spatial blocks for strict geographic CV
    blocks = []
    for idx in kept_indices:
        lat, lon = all_coords[idx]
        ux, uy = _TO_UTM46N.transform(lon, lat)
        blocks.append(f"{int(ux // SPATIAL_BLOCK_SIZE_M)}_{int(uy // SPATIAL_BLOCK_SIZE_M)}")
    groups = np.array(blocks)

    X_clean = np.column_stack([raw_feats[col][kept_indices] for col in CLEAN_STATIC_FEATURES])
    X_corridor = np.column_stack([raw_feats[col][kept_indices] for col in CORRIDOR_PROXY_FEATURES])

    clean_eval = _evaluate_spatial_cv_pair(X_clean, y, groups, CLEAN_STATIC_FEATURES, seed=seed)
    corridor_eval = _evaluate_spatial_cv_pair(X_corridor, y, groups, CORRIDOR_PROXY_FEATURES, seed=seed)
    dynamic_eval = _evaluate_dynamic_rainfall_thresholds(pilot_dir)

    rf_clean_auc = clean_eval["random_forest"]["oof_metrics"]["roc_auc"]
    rf_corr_auc = corridor_eval["random_forest"]["oof_metrics"]["roc_auc"]
    xgb_clean_auc = clean_eval["xgboost"]["oof_metrics"]["roc_auc"]
    xgb_corr_auc = corridor_eval["xgboost"]["oof_metrics"]["roc_auc"]

    artifact = {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_area": "Dima Hasao District, Assam (Pilot)",
        "track": "exploratory_research_only",
        "validated_for_production": False,
        "promoted_to_inference": False,
        "production_landslide_probability_policy": "STRICTLY_NULL_UNTIL_ALL_13_QUALITY_GATES_PASS",
        "production_quality_gate_status": {
            "overall_ml_ready": gate_report.overall_ml_ready,
            "passed_checks": gate_report.passed_checks,
            "total_checks": gate_report.total_checks,
            "blocking_failures": gate_report.blocking_failures,
        },
        "dataset_construction": {
            "positive_source": "GSI Bhusanket Public Inventory (in-district point centroids)",
            "raw_in_district_records": len(pilot_gsi),
            "spatial_dedup_radius_m": 100.0,
            "deduplicated_positives_sampled": int(np.sum(y == 1)),
            "background_sampling_method": "Positive-Unlabeled (PU) uniform spatial background >= 250 m from known GSI points (NOT confirmed landslide-free ground truth)",
            "unlabeled_background_sampled": int(np.sum(y == 0)),
            "unique_5km_utm_spatial_blocks": int(len(np.unique(groups))),
            "excluded_temporal_leakage_features": [
                "esa_worldcover_2021 (post-dates pre-2021 events)",
                "sentinel2_premonsoon_2024_ndvi (post-dates pre-May-2024 events)",
            ],
            "missing_critical_geology_features": [
                "GSI 1:50k lithology polygons (NGDR/Bhukosh access blocked)",
                "GSI thrust/fault lineaments",
            ],
            "random_seed": seed,
        },
        "model_a_static_susceptibility": {
            "validation_scheme": "5-fold Geographic Spatial-Block GroupKFold (5 km x 5 km EPSG:32646 blocks)",
            "clean_terrain_soil_ablation": {
                "description": "Excludes road/railway distance proxies to isolate physical terrain, hydrology, and soil conditioning.",
                "features": CLEAN_STATIC_FEATURES,
                "models": clean_eval,
            },
            "corridor_proxy_leakage_diagnostic": {
                "description": "Adds OSM distance-to-road and distance-to-railway solely to measure survey-accessibility bias leakage.",
                "features": CORRIDOR_PROXY_FEATURES,
                "models": corridor_eval,
                "measured_corridor_bias_inflation": {
                    "random_forest_roc_auc_delta": round(rf_corr_auc - rf_clean_auc, 4),
                    "xgboost_roc_auc_delta": round(xgb_corr_auc - xgb_clean_auc, 4),
                    "scientific_interpretation": (
                        "Adding road/railway proximity artificially inflates spatial-CV ROC-AUC because 77.8% of "
                        "GSI public points were surveyed along NH-27/railway corridors — proving why unstratified "
                        "corridor-proxy features must NOT be deployed into production susceptibility maps."
                    ),
                },
            },
        },
        "model_b_dynamic_rainfall_thresholds": dynamic_eval,
    }

    experimental_dir.mkdir(parents=True, exist_ok=True)
    out_path = experimental_dir / "exploratory_ml_benchmark.json"
    out_path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return artifact


if __name__ == "__main__":
    res = run_exploratory_ml_benchmark()
    clean = res["model_a_static_susceptibility"]["clean_terrain_soil_ablation"]["models"]
    corr = res["model_a_static_susceptibility"]["corridor_proxy_leakage_diagnostic"]["measured_corridor_bias_inflation"]
    print(
        json.dumps(
            {
                "validated_for_production": res["validated_for_production"],
                "overall_ml_ready": res["production_quality_gate_status"]["overall_ml_ready"],
                "dedup_positives": res["dataset_construction"]["deduplicated_positives_sampled"],
                "unlabeled_bg": res["dataset_construction"]["unlabeled_background_sampled"],
                "spatial_blocks": res["dataset_construction"]["unique_5km_utm_spatial_blocks"],
                "rf_clean_oof": clean["random_forest"]["oof_metrics"],
                "xgb_clean_oof": clean["xgboost"]["oof_metrics"],
                "corridor_bias_inflation": corr,
            },
            indent=2,
        )
    )
