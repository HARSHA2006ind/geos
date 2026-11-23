"""
Stage 9 Priority 3 — NASA GES DISC GPM IMERG V07B/V07C Authenticated Ingestion & CMR Cataloger.

Purpose:
  1. Query NASA Common Metadata Repository (CMR) to discover exact available daily granules for:
     - Historical 2024 gap: 2024-06-02 to 2024-12-31 (213 days) in GPM_3IMERGDF v07 (Final Run V07B)
     - Separate 2025–2026 Current-Monitoring Dataset:
         * GPM_3IMERGDF v07 (Final Run — research grade, ~3.5 month latency)
         * GPM_3IMERGDL v07 (Late Run — ~14 hour latency, V07B/V07C)
         * GPM_3IMERGDE v07 (Early Run — ~4 hour latency, V07C)
  2. When authorized NASA Earthdata credentials are provided via `EARTHDATA_TOKEN` env var
     or `~/.netrc` (`machine urs.earthdata.nasa.gov`), download granules with retry/resume,
     compute SHA-256 checksums, extract Dima Hasao polygon-averaged daily precipitation and
     quality flags (`precipitationQualityIndex` / `randomError`) via HDF5 (`h5py`), and
     preserve missing/fill pixels strictly as `None` (ZERO artificial gap filling).
  3. Never fabricate rainfall values when Earthdata credentials are absent; record exact
     CMR granule URLs, HTTP 302 URS OAuth verification, and missing-gap diagnostics.

IMPORTANT SCIENTIFIC DISTINCTION:
  - Inter-product comparison (e.g., IMERG vs CHIRPS / NASA POWER / ERA5) measures
    inter-product agreement ONLY.
  - True gauge-validated accuracy requires independent IMD / CWC / ASDMA rain-gauge stations
    inside Dima Hasao District, which are NOT yet ingested.
"""
from __future__ import annotations

import hashlib
import json
import netrc
import os
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import h5py
import httpx
import numpy as np
from shapely.geometry import Point, shape

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
RAW_IMERG_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "imerg_v07"

CMR_GRANULES_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"
GES_DISC_HOST = "data.gesdisc.earthdata.nasa.gov"
URS_HOST = "urs.earthdata.nasa.gov"

HISTORICAL_GAP_START = "2024-06-02"
HISTORICAL_GAP_END = "2024-12-31"
SINGLE_MISSING_2019 = "2019-06-30"
CURRENT_MONITORING_START = "2025-01-01"

IMERG_PRODUCTS = {
    "GPM_3IMERGDF": {
        "short_name": "GPM_3IMERGDF",
        "version": "07",
        "run_type": "Final Run (Gauge-Calibrated Research Product)",
        "recommended_role": "historical_training_and_validation",
        "typical_latency": "~3.5 months",
    },
    "GPM_3IMERGDL": {
        "short_name": "GPM_3IMERGDL",
        "version": "07",
        "run_type": "Late Run (Near-Real-Time Monitoring)",
        "recommended_role": "current_monitoring_separate_from_training",
        "typical_latency": "~14 hours",
    },
    "GPM_3IMERGDE": {
        "short_name": "GPM_3IMERGDE",
        "version": "07",
        "run_type": "Early Run (Low-Latency Monitoring)",
        "recommended_role": "current_monitoring_separate_from_training",
        "typical_latency": "~4 hours",
    },
}


@dataclass
class GranuleRecord:
    short_name: str
    version: str
    date: str
    title: str
    data_url: str
    granule_size_mb: float | None
    time_start: str
    time_end: str
    product_revision: str


def has_earthdata_credentials() -> tuple[bool, str]:
    """Check whether NASA Earthdata credentials exist WITHOUT ever returning or logging secrets."""
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if token:
        return True, "env:EARTHDATA_TOKEN"

    netrc_path = Path.home() / ".netrc"
    if netrc_path.exists():
        try:
            auth = netrc.netrc(str(netrc_path)).authenticators(URS_HOST)
            if auth and auth[0] and auth[2]:
                return True, "file:~/.netrc"
        except Exception:
            pass

    return False, "none_configured"


def _build_auth_headers() -> dict[str, str]:
    headers = {"User-Agent": "GeoResilience-NER/2.0 (Scientific Research)"}
    token = os.environ.get("EARTHDATA_TOKEN", "").strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def query_cmr_granules(
    short_name: str,
    start_date: str,
    end_date: str,
    version: str = "07",
    page_size: int = 500,
) -> tuple[int, list[GranuleRecord]]:
    """Query NASA CMR for all daily granules of an IMERG V07 collection in a date window."""
    records: list[GranuleRecord] = []
    total_hits = 0
    page_num = 1

    with httpx.Client(timeout=30.0, follow_redirects=True) as client:
        while True:
            params = {
                "short_name": short_name,
                "version": version,
                "temporal": f"{start_date}T00:00:00Z,{end_date}T23:59:59Z",
                "page_size": page_size,
                "page_num": page_num,
                "sort_key": "start_date",
            }
            resp = client.get(CMR_GRANULES_URL, params=params)
            resp.raise_for_status()
            if page_num == 1:
                total_hits = int(resp.headers.get("CMR-Hits", "0"))
            entries = resp.json().get("feed", {}).get("entry", [])
            if not entries:
                break

            for entry in entries:
                data_url = ""
                for link in entry.get("links", []):
                    href = link.get("href", "")
                    if href.startswith("https://") and href.endswith(".nc4"):
                        data_url = href
                        break
                t_start = entry.get("time_start", "")
                day_str = t_start[:10] if len(t_start) >= 10 else ""
                title = entry.get("title", "")
                revision = "V07C" if ".V07C." in data_url else ("V07B" if ".V07B." in data_url else "V07")
                size_raw = entry.get("granule_size")
                try:
                    size_mb = round(float(size_raw), 3) if size_raw is not None else None
                except ValueError:
                    size_mb = None

                if data_url and day_str:
                    records.append(
                        GranuleRecord(
                            short_name=short_name,
                            version=version,
                            date=day_str,
                            title=title,
                            data_url=data_url,
                            granule_size_mb=size_mb,
                            time_start=t_start,
                            time_end=entry.get("time_end", ""),
                            product_revision=revision,
                        )
                    )

            if len(entries) < page_size or len(records) >= total_hits:
                break
            page_num += 1

    # Deduplicate by date keeping latest title
    by_date: dict[str, GranuleRecord] = {}
    for rec in records:
        by_date[rec.date] = rec
    ordered = [by_date[d] for d in sorted(by_date.keys())]
    return total_hits, ordered


def probe_gesdisc_access(sample_url: str) -> dict[str, Any]:
    """Probe whether GES DISC grants direct download or enforces Earthdata URS OAuth redirect."""
    has_creds, cred_source = has_earthdata_credentials()
    headers = _build_auth_headers()
    headers["Range"] = "bytes=0-63"

    try:
        with httpx.Client(timeout=20.0, follow_redirects=False) as client:
            resp = client.get(sample_url, headers=headers)
            loc = resp.headers.get("location", "")
            return {
                "sample_url": sample_url,
                "http_status": resp.status_code,
                "redirect_host": URS_HOST if URS_HOST in loc else (loc[:80] if loc else None),
                "requires_earthdata_auth": resp.status_code in (302, 401, 403) and URS_HOST in loc,
                "credentials_configured": has_creds,
                "credential_source": cred_source,
                "probed_at_utc": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        return {
            "sample_url": sample_url,
            "http_status": None,
            "error": f"{type(exc).__name__}: {exc}",
            "credentials_configured": has_creds,
            "credential_source": cred_source,
            "probed_at_utc": datetime.now(timezone.utc).isoformat(),
        }


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_granule_with_resume(
    url: str,
    dest_path: Path,
    max_retries: int = 3,
    backoff_sec: float = 2.0,
) -> dict[str, Any]:
    """Download a single IMERG .nc4 granule with HTTP Range resume, retries, and SHA-256 checksum."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    if dest_path.exists() and dest_path.stat().st_size > 1024:
        return {
            "status": "cached",
            "path": str(dest_path),
            "bytes": dest_path.stat().st_size,
            "sha256": sha256_file(dest_path),
        }

    part_path = dest_path.with_suffix(dest_path.suffix + ".part")
    headers = _build_auth_headers()

    for attempt in range(1, max_retries + 1):
        try:
            existing_bytes = part_path.stat().st_size if part_path.exists() else 0
            req_headers = dict(headers)
            if existing_bytes > 0:
                req_headers["Range"] = f"bytes={existing_bytes}-"

            with httpx.Client(timeout=90.0, follow_redirects=True) as client:
                with client.stream("GET", url, headers=req_headers) as resp:
                    if resp.status_code in (401, 403) or URS_HOST in str(resp.url):
                        return {
                            "status": "auth_required",
                            "http_status": resp.status_code,
                            "final_url_host": resp.url.host,
                        }
                    if resp.status_code not in (200, 206):
                        resp.raise_for_status()

                    mode = "ab" if (resp.status_code == 206 and existing_bytes > 0) else "wb"
                    with part_path.open(mode) as fh:
                        for chunk in resp.iter_bytes(chunk_size=131072):
                            fh.write(chunk)

            # Verify valid HDF5 signature before committing atomic rename
            with part_path.open("rb") as fh:
                magic = fh.read(8)
            if magic != b"\x89HDF\r\n\x1a\n":
                part_path.unlink(missing_ok=True)
                return {
                    "status": "invalid_hdf5_payload",
                    "detail": "Downloaded payload did not begin with HDF5/NetCDF4 signature (likely HTML auth wall).",
                }

            part_path.rename(dest_path)
            return {
                "status": "downloaded",
                "path": str(dest_path),
                "bytes": dest_path.stat().st_size,
                "sha256": sha256_file(dest_path),
            }
        except Exception as exc:
            if attempt == max_retries:
                return {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            time.sleep(backoff_sec * attempt)

    return {"status": "failed", "error": "Exhausted retries"}


def extract_dima_hasao_from_imerg_nc4(
    nc4_path: Path,
    boundary_polygon: Any,
) -> dict[str, Any]:
    """
    Extract Dima Hasao area-averaged daily precipitation (mm/day) and quality indicators
    from an official NASA GPM IMERG V07B/V07C daily NetCDF4/HDF5 granule.
    Strictly preserves missing/fill values as None (no artificial gap filling).
    """
    minx, miny, maxx, maxy = boundary_polygon.bounds

    with h5py.File(nc4_path, "r") as hf:
        # GPM IMERG V07 daily files store variables at root or under /Grid depending on endpoint
        root = hf["Grid"] if "Grid" in hf else hf
        lats = np.asarray(root["lat"][:], dtype=np.float64)
        lons = np.asarray(root["lon"][:], dtype=np.float64)

        precip_ds = root["precipitation"]
        fill_val = precip_ds.attrs.get("_FillValue", -9999.9)
        if isinstance(fill_val, np.ndarray):
            fill_val = float(fill_val.flat[0])
        else:
            fill_val = float(fill_val)

        # Shape is typically (time, lon, lat) in GPM_3IMERGDF V07
        raw_p = np.asarray(precip_ds[:], dtype=np.float64)
        if raw_p.ndim == 3:
            raw_p = raw_p[0]

        lat_idx = np.where((lats >= miny - 0.15) & (lats <= maxy + 0.15))[0]
        lon_idx = np.where((lons >= minx - 0.15) & (lons <= maxx + 0.15))[0]

        # Determine axis orientation
        lon_first = raw_p.shape == (lons.size, lats.size)

        # Optional quality dataset (randomError or precipitationQualityIndex)
        qual_ds = None
        qual_name = None
        for candidate in ("precipitationQualityIndex", "randomError", "probabilityLiquidPrecipitation"):
            if candidate in root:
                qual_ds = np.asarray(root[candidate][:], dtype=np.float64)
                if qual_ds.ndim == 3:
                    qual_ds = qual_ds[0]
                qual_name = candidate
                break

        precip_vals: list[float] = []
        qual_vals: list[float] = []
        total_cells_in_poly = 0
        missing_cells_in_poly = 0

        for ix in lon_idx:
            for iy in lat_idx:
                pt = Point(float(lons[ix]), float(lats[iy]))
                if not boundary_polygon.contains(pt):
                    continue
                total_cells_in_poly += 1
                val = float(raw_p[ix, iy] if lon_first else raw_p[iy, ix])
                if np.isnan(val) or val <= -9000.0 or val == fill_val or val < 0.0:
                    missing_cells_in_poly += 1
                    continue
                precip_vals.append(val)
                if qual_ds is not None:
                    q = float(qual_ds[ix, iy] if lon_first else qual_ds[iy, ix])
                    if not np.isnan(q) and q > -9000.0:
                        qual_vals.append(q)

        # Fallback to bbox cells if coarse 0.1-deg grid centroids don't fall strictly inside thin polygon edges
        if total_cells_in_poly == 0:
            for ix in lon_idx:
                for iy in lat_idx:
                    total_cells_in_poly += 1
                    val = float(raw_p[ix, iy] if lon_first else raw_p[iy, ix])
                    if np.isnan(val) or val <= -9000.0 or val == fill_val or val < 0.0:
                        missing_cells_in_poly += 1
                        continue
                    precip_vals.append(val)

        valid_fraction = (
            round(len(precip_vals) / total_cells_in_poly, 4) if total_cells_in_poly > 0 else 0.0
        )

        # Require >= 50% valid grid cells inside district; otherwise preserve strictly as None
        if not precip_vals or valid_fraction < 0.5:
            mean_mm = None
            quality_flag = "MISSING_INSUFFICIENT_VALID_CELLS"
        else:
            mean_mm = round(float(np.mean(precip_vals)), 3)
            quality_flag = "VALID_FULL" if missing_cells_in_poly == 0 else "VALID_PARTIAL"

        return {
            "rainfall_1d_mm": mean_mm,
            "valid_cells": len(precip_vals),
            "total_cells": total_cells_in_poly,
            "valid_cell_fraction": valid_fraction,
            "quality_flag": quality_flag,
            "quality_metric_name": qual_name,
            "quality_metric_mean": round(float(np.mean(qual_vals)), 3) if qual_vals else None,
        }


def _expected_date_count(start_s: str, end_s: str) -> int:
    d0 = date.fromisoformat(start_s)
    d1 = date.fromisoformat(end_s)
    return (d1 - d0).days + 1


def build_imerg_v07_catalog(
    pilot_dir: Path = PILOT_DIR,
    execute_downloads_if_authenticated: bool = True,
) -> dict[str, Any]:
    """
    Discover complete NASA CMR granule catalogs for:
      - Historical missing days (2019-06-30 and 2024-06-02..2024-12-31)
      - Current monitoring dataset (2025-01-01..present) across Final, Late, and Early runs
    If Earthdata credentials exist and execute_downloads_if_authenticated=True, downloads and
    merges verified IMERG V07B granules into the historical archive without fabricating data.
    """
    today_str = date.today().isoformat()

    # 1. Historical 2024 gap in GPM_3IMERGDF v07 (Final Run) + 2019-06-30 single gap
    hits_2019, recs_2019 = query_cmr_granules("GPM_3IMERGDF", SINGLE_MISSING_2019, SINGLE_MISSING_2019)
    hits_gap_final, recs_gap_final = query_cmr_granules(
        "GPM_3IMERGDF", HISTORICAL_GAP_START, HISTORICAL_GAP_END
    )
    hits_gap_late, recs_gap_late = query_cmr_granules(
        "GPM_3IMERGDL", HISTORICAL_GAP_START, HISTORICAL_GAP_END
    )

    # 2. Separate 2025-2026 Current-Monitoring datasets
    hits_2526_final, recs_2526_final = query_cmr_granules(
        "GPM_3IMERGDF", CURRENT_MONITORING_START, today_str
    )
    hits_2526_late, recs_2526_late = query_cmr_granules(
        "GPM_3IMERGDL", CURRENT_MONITORING_START, today_str
    )
    hits_2526_early, recs_2526_early = query_cmr_granules(
        "GPM_3IMERGDE", CURRENT_MONITORING_START, today_str
    )

    sample_url = (
        recs_gap_final[0].data_url
        if recs_gap_final
        else "https://data.gesdisc.earthdata.nasa.gov/data/GPM_L3/GPM_3IMERGDF.07/2024/06/3B-DAY.MS.MRG.3IMERG.20240602-S000000-E235959.V07B.nc4"
    )
    access_probe = probe_gesdisc_access(sample_url)

    expected_gap_days = _expected_date_count(HISTORICAL_GAP_START, HISTORICAL_GAP_END)
    gap_dates_found = {r.date for r in recs_gap_final}
    gap_dates_expected = {
        (date.fromisoformat(HISTORICAL_GAP_START) + timedelta(days=i)).isoformat()
        for i in range(expected_gap_days)
    }
    cmr_missing_gap_dates = sorted(gap_dates_expected - gap_dates_found)

    download_summary: dict[str, Any] = {
        "attempted": False,
        "status": "blocked_earthdata_auth_required",
        "downloaded_granules": 0,
        "failed_granules": 0,
        "reason": (
            "NASA GES DISC returned HTTP 302 redirect to urs.earthdata.nasa.gov. "
            "No EARTHDATA_TOKEN env var or ~/.netrc credentials are configured in this runtime. "
            "Zero rainfall values were fabricated."
        ),
    }

    has_creds, cred_source = has_earthdata_credentials()
    if has_creds and execute_downloads_if_authenticated and recs_gap_final:
        boundary_gj = json.loads((pilot_dir / "dima_hasao_boundary.geojson").read_text(encoding="utf-8"))
        geom = boundary_gj["features"][0]["geometry"] if "features" in boundary_gj else boundary_gj["geometry"]
        poly = shape(geom)

        dl_ok = 0
        dl_fail = 0
        extracted_days: dict[str, dict[str, Any]] = {}
        checksum_manifest: list[dict[str, Any]] = []

        for rec in recs_2019 + recs_gap_final:
            dest = RAW_IMERG_DIR / rec.short_name / f"{rec.date}.nc4"
            res = download_granule_with_resume(rec.data_url, dest)
            if res["status"] in ("downloaded", "cached"):
                dl_ok += 1
                obs = extract_dima_hasao_from_imerg_nc4(dest, poly)
                extracted_days[rec.date] = {
                    **obs,
                    "product": f"{rec.short_name}.07 ({rec.product_revision})",
                    "source_url": rec.data_url,
                    "sha256": res["sha256"],
                }
                checksum_manifest.append(
                    {"date": rec.date, "file": dest.name, "sha256": res["sha256"], "bytes": res["bytes"]}
                )
            else:
                dl_fail += 1
                if res["status"] == "auth_required":
                    break

        download_summary = {
            "attempted": True,
            "credential_source": cred_source,
            "status": "completed" if (dl_ok > 0 and dl_fail == 0) else "partial_or_auth_failed",
            "downloaded_granules": dl_ok,
            "failed_granules": dl_fail,
            "checksum_count": len(checksum_manifest),
        }

    # Check existing multiyear rainfall archive completeness
    multiyear_path = pilot_dir / "dima_hasao_rainfall_multiyear.json"
    archive_status: dict[str, Any] = {}
    if multiyear_path.exists():
        my = json.loads(multiyear_path.read_text(encoding="utf-8"))
        obs = my.get("observations", [])
        valid = sum(1 for o in obs if o.get("rainfall_1d_mm") is not None)
        missing = sum(1 for o in obs if o.get("rainfall_1d_mm") is None)
        archive_status = {
            "archive_file": "dima_hasao_rainfall_multiyear.json",
            "date_range": f"{obs[0]['date']} to {obs[-1]['date']}" if obs else None,
            "total_days": len(obs),
            "valid_days": valid,
            "missing_days_preserved_null": missing,
            "completeness_pct": round(100.0 * valid / len(obs), 2) if obs else 0.0,
            "artificial_gap_filling_applied": False,
        }

    catalog = {
        "schema_version": "geos-imerg-v07-catalog-1.0",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "study_area": "Dima Hasao District, Assam, India",
        "cmr_endpoint": CMR_GRANULES_URL,
        "ges_disc_access_probe": access_probe,
        "download_execution": download_summary,
        "existing_historical_archive_status": archive_status,
        "historical_gap_2019_and_2024": {
            "dataset_role": "historical_training_archive_gap_closure",
            "single_missing_2019_06_30": {
                "short_name": "GPM_3IMERGDF",
                "version": "07",
                "cmr_hits": hits_2019,
                "available_in_cmr": len(recs_2019) == 1,
                "granule": asdict(recs_2019[0]) if recs_2019 else None,
            },
            "gap_2024_06_02_to_2024_12_31_final_run": {
                "short_name": "GPM_3IMERGDF",
                "version": "07",
                "run_type": IMERG_PRODUCTS["GPM_3IMERGDF"]["run_type"],
                "expected_days": expected_gap_days,
                "cmr_granules_available": len(recs_gap_final),
                "cmr_hits_header": hits_gap_final,
                "cmr_coverage_pct": round(100.0 * len(recs_gap_final) / expected_gap_days, 2),
                "cmr_missing_dates": cmr_missing_gap_dates,
                "revisions_observed": sorted({r.product_revision for r in recs_gap_final}),
                "first_granule": asdict(recs_gap_final[0]) if recs_gap_final else None,
                "last_granule": asdict(recs_gap_final[-1]) if recs_gap_final else None,
                "granule_urls_sample_first_5": [r.data_url for r in recs_gap_final[:5]],
            },
            "gap_2024_06_02_to_2024_12_31_late_run_reference": {
                "short_name": "GPM_3IMERGDL",
                "version": "07",
                "cmr_granules_available": len(recs_gap_late),
                "note": "Do NOT mix Late Run into Final Run training series without explicit run-type flag.",
            },
        },
        "current_monitoring_2025_2026_separate_dataset": {
            "dataset_role": "current_monitoring_only_strictly_separate_from_historical_training",
            "query_start_date": CURRENT_MONITORING_START,
            "query_end_date": today_str,
            "GPM_3IMERGDF_v07_final": {
                "run_type": IMERG_PRODUCTS["GPM_3IMERGDF"]["run_type"],
                "cmr_granules_available": len(recs_2526_final),
                "cmr_hits_header": hits_2526_final,
                "earliest_date": recs_2526_final[0].date if recs_2526_final else None,
                "latest_date": recs_2526_final[-1].date if recs_2526_final else None,
                "revisions_observed": sorted({r.product_revision for r in recs_2526_final}),
                "latest_granule_url": recs_2526_final[-1].data_url if recs_2526_final else None,
            },
            "GPM_3IMERGDL_v07_late": {
                "run_type": IMERG_PRODUCTS["GPM_3IMERGDL"]["run_type"],
                "cmr_granules_available": len(recs_2526_late),
                "cmr_hits_header": hits_2526_late,
                "earliest_date": recs_2526_late[0].date if recs_2526_late else None,
                "latest_date": recs_2526_late[-1].date if recs_2526_late else None,
                "revisions_observed": sorted({r.product_revision for r in recs_2526_late}),
                "latest_granule_url": recs_2526_late[-1].data_url if recs_2526_late else None,
            },
            "GPM_3IMERGDE_v07_early": {
                "run_type": IMERG_PRODUCTS["GPM_3IMERGDE"]["run_type"],
                "cmr_granules_available": len(recs_2526_early),
                "cmr_hits_header": hits_2526_early,
                "earliest_date": recs_2526_early[0].date if recs_2526_early else None,
                "latest_date": recs_2526_early[-1].date if recs_2526_early else None,
                "revisions_observed": sorted({r.product_revision for r in recs_2526_early}),
                "latest_granule_url": recs_2526_early[-1].data_url if recs_2526_early else None,
            },
        },
        "validation_distinction_notice": (
            "Previous Stage 4 cross-checks (IMERG vs CHIRPS, NASA POWER, and ERA5) measure "
            "inter-product agreement ONLY, not ground-truth gauge-validated accuracy. "
            "Gauge-validated accuracy for Dima Hasao requires independent IMD / CWC / ASDMA "
            "rain-gauge observations (e.g., Haflong, Maibang, Harangajao, Umrangso stations)."
        ),
        "earthdata_setup_instructions": [
            "1. Create a free NASA Earthdata Login account at https://urs.earthdata.nasa.gov/users/new",
            "2. Authorize 'NASA GESDISC DATA ARCHIVE' under Earthdata Profile -> Applications -> Authorized Apps",
            "3. Generate a Bearer token (Profile -> Generate Token) OR configure ~/.netrc with chmod 600:",
            "   machine urs.earthdata.nasa.gov login <YOUR_USERNAME> password <YOUR_PASSWORD>",
            "4. Run: EARTHDATA_TOKEN=<token> PYTHONPATH=. backend/.venv/bin/python -m backend.ingestion.fetch_imerg_v07_earthdata",
        ],
    }

    out_path = pilot_dir / "imerg_v07_cmr_catalog.json"
    out_path.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    return catalog


if __name__ == "__main__":
    result = build_imerg_v07_catalog()
    print(
        json.dumps(
            {
                "access_probe": result["ges_disc_access_probe"],
                "download_execution": result["download_execution"],
                "gap_2024_final_cmr_count": result["historical_gap_2019_and_2024"][
                    "gap_2024_06_02_to_2024_12_31_final_run"
                ]["cmr_granules_available"],
                "monitoring_2025_2026_final": result["current_monitoring_2025_2026_separate_dataset"][
                    "GPM_3IMERGDF_v07_final"
                ]["cmr_granules_available"],
                "monitoring_2025_2026_late": result["current_monitoring_2025_2026_separate_dataset"][
                    "GPM_3IMERGDL_v07_late"
                ]["cmr_granules_available"],
                "monitoring_2025_2026_early": result["current_monitoring_2025_2026_separate_dataset"][
                    "GPM_3IMERGDE_v07_early"
                ]["cmr_granules_available"],
            },
            indent=2,
        )
    )
