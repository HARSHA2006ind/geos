"""
Task 5 Experimental Prototype A — Lightweight CPU-Only NOAA GFS 0.25° Forecast Reader
(Dynamical.org Zarr v3 — Discovered via NVIDIA Earth2Studio `earth2studio/data/dynamical.py`).

Design Rationale:
  - Installing NVIDIA `earth2studio` v1.0.0 on Linux pulls unconditional GPU/CUDA core
    dependencies (`cupy-cuda13x`, `rmm-cu13`, `torch>=2.5.0`, ~4-6 GB), which is unsuitable
    for our 4 vCPU / 8 GB RAM / 20 GB SSD CPU-only server.
  - Following `earth2studio-discover` and `earth2studio-data-fetch` SKILL.md guidance, we
    access the exact same free, unauthenticated, CC-BY-4.0 NOAA GFS 0.25° Zarr v3 archive
    (`https://data.dynamical.org/noaa/gfs/forecast/latest.zarr`) directly over HTTPS Range
    requests using lightweight CPU-only `zarr==3.1.6` + `httpx` (zero GPU dependencies).

Scientific & Operational Isolation:
  - Output is strictly EXPERIMENTAL FORECAST DATA (`data_role = "experimental_nwp_forecast_only"`).
  - Stored ONLY in `backend/data/experimental/dima_hasao_gfs_forecast_eval.json`.
  - NEVER merged into validated historical IMERG observations, NEVER alters `quality_gate.py`,
    and NEVER modifies `landslide_probability: null`.
"""
from __future__ import annotations

import asyncio
import json
import math
import time
import tracemalloc
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
import numpy as np
import zarr
from zarr.abc.store import ByteRequest, OffsetByteRequest, RangeByteRequest, Store, SuffixByteRequest
from zarr.core.buffer import Buffer, BufferPrototype

DYNAMICAL_GFS_ZARR_URL = "https://data.dynamical.org/noaa/gfs/forecast/latest.zarr"
EXPERIMENTAL_DIR = Path(__file__).resolve().parents[2] / "data" / "experimental"
PILOT_DIR = Path(__file__).resolve().parents[2] / "data" / "pilot"

# Dima Hasao bounding grid with 0.25-deg margin: 24.75..26.00 N, 92.50..93.50 E
DIMA_HASAO_LAT_MIN = 24.75
DIMA_HASAO_LAT_MAX = 26.00
DIMA_HASAO_LON_MIN = 92.50
DIMA_HASAO_LON_MAX = 93.50

PHYSICAL_BOUNDS: dict[str, tuple[float, float]] = {
    "precipitation_rate_mm_h": (0.0, 400.0),
    "temperature_2m_c": (-20.0, 55.0),
    "relative_humidity_2m_pct": (0.0, 100.0),
    "precipitable_water_mm": (0.0, 120.0),
}


class ReadOnlyHttpxZarrStore(Store):
    """Minimal read-only Zarr v3 Store over httpx with HTTP Range support & byte telemetry."""

    supports_writes = False
    supports_deletes = False
    supports_listing = False

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        super().__init__(read_only=True)
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.bytes_downloaded = 0
        self.http_requests = 0
        self._client = httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "GeoResilience-NER/2.0-ExperimentalEval"},
        )

    def __eq__(self, other: object) -> bool:
        return isinstance(other, ReadOnlyHttpxZarrStore) and self.base_url == other.base_url

    async def get(
        self,
        key: str,
        prototype: BufferPrototype,
        byte_range: ByteRequest | None = None,
    ) -> Buffer | None:
        url = f"{self.base_url}/{key.lstrip('/')}"
        headers: dict[str, str] = {}
        if isinstance(byte_range, RangeByteRequest):
            headers["Range"] = f"bytes={byte_range.start}-{byte_range.end - 1}"
        elif isinstance(byte_range, OffsetByteRequest):
            headers["Range"] = f"bytes={byte_range.offset}-"
        elif isinstance(byte_range, SuffixByteRequest):
            headers["Range"] = f"bytes=-{byte_range.suffix}"

        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                resp = await self._client.get(url, headers=headers)
                self.http_requests += 1
                if resp.status_code == 404:
                    return None
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                resp.raise_for_status()
                data = resp.content
                self.bytes_downloaded += len(data)
                return prototype.buffer.from_bytes(data)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise
        if last_exc:
            raise last_exc
        return None

    async def get_partial_values(
        self,
        prototype: BufferPrototype,
        key_ranges: Iterable[tuple[str, ByteRequest | None]],
    ) -> list[Buffer | None]:
        out: list[Buffer | None] = []
        for key, br in key_ranges:
            out.append(await self.get(key, prototype, byte_range=br))
        return out

    async def exists(self, key: str) -> bool:
        url = f"{self.base_url}/{key.lstrip('/')}"
        for attempt in range(3):
            try:
                resp = await self._client.head(url)
                if resp.status_code in {429, 500, 502, 503, 504} and attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                return resp.status_code == 200
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt < 2:
                    await asyncio.sleep(0.5 * (2**attempt))
                    continue
                raise
        return False

    async def set(self, key: str, value: Buffer) -> None:
        raise NotImplementedError("Read-only store")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("Read-only store")

    async def list(self):
        raise NotImplementedError("Listing not supported")

    async def list_prefix(self, prefix: str):
        raise NotImplementedError("Listing not supported")

    async def list_dir(self, prefix: str):
        raise NotImplementedError("Listing not supported")

    def close(self) -> None:
        pass


def validate_forecast_series(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate physical ranges and missing-value preservation across all forecast lead times."""
    range_violations: dict[str, int] = {k: 0 for k in PHYSICAL_BOUNDS}
    null_counts: dict[str, int] = {k: 0 for k in PHYSICAL_BOUNDS}
    valid_counts: dict[str, int] = {k: 0 for k in PHYSICAL_BOUNDS}

    for row in records:
        for field, (lo, hi) in PHYSICAL_BOUNDS.items():
            val = row.get(field)
            if val is None:
                null_counts[field] += 1
                continue
            valid_counts[field] += 1
            if not (lo <= float(val) <= hi) or math.isnan(float(val)):
                range_violations[field] += 1

    return {
        "total_lead_steps": len(records),
        "valid_counts": valid_counts,
        "null_counts": null_counts,
        "range_violations": range_violations,
        "all_physical_bounds_valid": all(v == 0 for v in range_violations.values()),
    }


def _safe_mean(arr: np.ndarray) -> float | None:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    return round(float(finite.mean()), 4)


def _safe_max(arr: np.ndarray) -> float | None:
    finite = arr[np.isfinite(arr)]
    if finite.size == 0:
        return None
    return round(float(finite.max()), 4)


def evaluate_dynamical_gfs_dima_hasao(
    forecast_hours: int = 72,
    out_dir: Path = EXPERIMENTAL_DIR,
) -> dict[str, Any]:
    """
    Fetch a real 0..72h NOAA GFS 0.25° forecast slice for Dima Hasao from dynamical.org Zarr v3,
    benchmark RAM/time/disk, validate physical ranges, and compare against IMERG pipeline.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tracemalloc.start()
    t0 = time.perf_counter()

    store = ReadOnlyHttpxZarrStore(DYNAMICAL_GFS_ZARR_URL)
    root = zarr.open_group(store=store, mode="r")
    attrs = dict(root.attrs)

    init_times_sec = np.asarray(root["init_time"][:], dtype=np.int64)
    lead_times_sec = np.asarray(root["lead_time"][:], dtype=np.float64)
    lats = np.asarray(root["latitude"][:], dtype=np.float64)
    lons = np.asarray(root["longitude"][:], dtype=np.float64)

    # Pick latest completed cycle (second-to-last init_time avoids an in-flight GFS upload)
    ingested_len = np.asarray(root["ingested_forecast_length"][:], dtype=np.float64)
    target_sec = forecast_hours * 3600.0
    complete_indices = np.where(ingested_len >= target_sec)[0]
    init_idx = int(complete_indices[-1]) if complete_indices.size > 0 else int(len(init_times_sec) - 2)
    init_dt = datetime.fromtimestamp(int(init_times_sec[init_idx]), tz=timezone.utc)

    # Hourly lead steps 0..forecast_hours
    lead_mask = (lead_times_sec >= 0) & (lead_times_sec <= target_sec)
    lead_indices = np.where(lead_mask)[0]
    lead_start, lead_end = int(lead_indices[0]), int(lead_indices[-1]) + 1
    selected_leads_h = [int(round(float(lead_times_sec[i]) / 3600.0)) for i in range(lead_start, lead_end)]

    # Spatial indices covering Dima Hasao
    lat_indices = np.where((lats >= DIMA_HASAO_LAT_MIN) & (lats <= DIMA_HASAO_LAT_MAX))[0]
    lon_indices = np.where((lons >= DIMA_HASAO_LON_MIN) & (lons <= DIMA_HASAO_LON_MAX))[0]
    lat_s, lat_e = int(lat_indices[0]), int(lat_indices[-1]) + 1
    lon_s, lon_e = int(lon_indices[0]), int(lon_indices[-1]) + 1

    selected_lats = [round(float(x), 4) for x in lats[lat_s:lat_e]]
    selected_lons = [round(float(x), 4) for x in lons[lon_s:lon_e]]

    # Fetch ONLY the tiny Dima Hasao spatial sub-slice (sharded Zarr v3 -> partial range fetches)
    precip_kg_m2_s = np.asarray(
        root["precipitation_surface"][init_idx, lead_start:lead_end, lat_s:lat_e, lon_s:lon_e],
        dtype=np.float32,
    )
    temp_2m_c = np.asarray(
        root["temperature_2m"][init_idx, lead_start:lead_end, lat_s:lat_e, lon_s:lon_e],
        dtype=np.float32,
    )
    rh_2m_pct = np.asarray(
        root["relative_humidity_2m"][init_idx, lead_start:lead_end, lat_s:lat_e, lon_s:lon_e],
        dtype=np.float32,
    )
    pwat_mm = np.asarray(
        root["precipitable_water_atmosphere"][init_idx, lead_start:lead_end, lat_s:lat_e, lon_s:lon_e],
        dtype=np.float32,
    )

    # Convert precipitation rate kg m-2 s-1 (= mm/s) to mm/h cleanly (preserving NaNs!)
    precip_mm_h = np.where(np.isfinite(precip_kg_m2_s), np.maximum(precip_kg_m2_s * 3600.0, 0.0), np.nan)

    hourly_records: list[dict[str, Any]] = []
    for i, lh in enumerate(selected_leads_h):
        valid_dt = init_dt + timedelta(hours=lh)
        hourly_records.append(
            {
                "lead_hours": lh,
                "valid_time_utc": valid_dt.isoformat(),
                "precipitation_rate_mm_h": _safe_mean(precip_mm_h[i]),
                "precipitation_rate_grid_max_mm_h": _safe_max(precip_mm_h[i]),
                "temperature_2m_c": _safe_mean(temp_2m_c[i]),
                "relative_humidity_2m_pct": _safe_mean(rh_2m_pct[i]),
                "precipitable_water_mm": _safe_mean(pwat_mm[i]),
            }
        )

    # Compute 24h & 72h forecast cumulative rainfall (strict null-aware aggregation on hourly steps 1..24 / 1..72)
    def _cum_rain(max_h: int) -> float | None:
        vals = [r["precipitation_rate_mm_h"] for r in hourly_records if 1 <= r["lead_hours"] <= max_h]
        if not vals or any(v is None for v in vals):
            return None
        return round(float(sum(vals)), 3)

    validation = validate_forecast_series(hourly_records)
    elapsed_sec = round(time.perf_counter() - t0, 3)
    _, peak_mem_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Load existing NASA IMERG historical baseline stats for side-by-side comparison
    imerg_baseline: dict[str, Any] = {}
    imerg_path = PILOT_DIR / "dima_hasao_rainfall_multiyear.json"
    if imerg_path.exists():
        my = json.loads(imerg_path.read_text(encoding="utf-8"))
        obs = [o["rainfall_1d_mm"] for o in my.get("observations", []) if o.get("rainfall_1d_mm") is not None]
        imerg_baseline = {
            "dataset": "NASA GPM IMERG Multi-Year Historical Archive",
            "role": "historical_satellite_observation",
            "spatial_resolution_deg": 0.10,
            "valid_days": len(obs),
            "historical_daily_p95_mm": round(float(np.percentile(obs, 95)), 2) if obs else None,
            "historical_daily_max_mm": round(float(max(obs)), 2) if obs else None,
        }

    result: dict[str, Any] = {
        "schema_version": "geos-experimental-gfs-eval-1.0",
        "data_role": "experimental_nwp_forecast_only_NOT_ground_observation",
        "scientific_guardrail": (
            "Coarse 0.25-degree (~25 km) NOAA GFS numerical weather forecasts are experimental "
            "atmospheric guidance ONLY. They are NOT ground-truth rainfall measurements, MUST NOT "
            "substitute for NASA IMERG or IMD/CWC rain gauges, and MUST NOT alter landslide_probability (null)."
        ),
        "discovery_provenance": {
            "discovered_via": "NVIDIA Earth2Studio v1.0.0 (`earth2studio/data/dynamical.py` -> DynamicalGFS_FX)",
            "direct_client_used": "Lightweight CPU-only zarr==3.1.6 + httpx (avoids earth2studio's 4+ GB CUDA/torch/cupy stack)",
            "source_url": DYNAMICAL_GFS_ZARR_URL,
            "dataset_id": attrs.get("dataset_id"),
            "dataset_version": attrs.get("dataset_version"),
            "license": attrs.get("license"),
            "attribution": attrs.get("attribution"),
            "authentication_required": False,
        },
        "spatial_domain": {
            "study_area": "Dima Hasao District, Assam (0.25° NWP grid patch)",
            "crs": "EPSG:4326",
            "resolution_deg": 0.25,
            "grid_points_lat": selected_lats,
            "grid_points_lon": selected_lons,
            "total_grid_cells": len(selected_lats) * len(selected_lons),
        },
        "temporal_domain": {
            "forecast_init_time_utc": init_dt.isoformat(),
            "forecast_horizon_hours": selected_leads_h[-1] if selected_leads_h else 0,
            "lead_steps_count": len(selected_leads_h),
            "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        },
        "summary_metrics": {
            "forecast_24h_mean_rain_mm": _cum_rain(24),
            "forecast_48h_mean_rain_mm": _cum_rain(48),
            "forecast_72h_mean_rain_mm": _cum_rain(72),
            "t2m_min_c": min((r["temperature_2m_c"] for r in hourly_records if r["temperature_2m_c"] is not None), default=None),
            "t2m_max_c": max((r["temperature_2m_c"] for r in hourly_records if r["temperature_2m_c"] is not None), default=None),
            "t2m_mean_c": round(
                float(np.mean([r["temperature_2m_c"] for r in hourly_records if r["temperature_2m_c"] is not None])),
                2,
            ),
            "rh_2m_mean_pct": round(
                float(np.mean([r["relative_humidity_2m_pct"] for r in hourly_records if r["relative_humidity_2m_pct"] is not None])),
                2,
            ),
            "pwat_mean_mm": round(
                float(np.mean([r["precipitable_water_mm"] for r in hourly_records if r["precipitable_water_mm"] is not None])),
                2,
            ),
        },
        "validation": validation,
        "comparison_with_existing_imerg_pipeline": {
            "existing_imerg_baseline": imerg_baseline,
            "spatial_resolution_ratio": "GFS 0.25° (~25 km) is 2.5x coarser linearly (~6.25x larger cell area) than IMERG 0.10° (~11 km).",
            "complementary_value": (
                "Fills a genuine gap: our existing pipeline had ZERO operational weather forecasts "
                "(only historical rainfall). Provides 6-hourly updated forecast precipitation, 2m temperature, "
                "relative humidity, and precipitable water with zero GPU or API keys."
            ),
            "limitations": [
                "0.25° (~25 km) horizontal grid severely smooths Barail Range orographic precipitation extremes.",
                "GFS convective precipitation is a numerical model forecast, NOT measured rainfall.",
                "Lead step 0 (`lead_hours=0`) has NaN/null precipitation rate by GFS convention (accumulated flux starts at hour 1).",
            ],
        },
        "performance_benchmark": {
            "execution_time_sec": elapsed_sec,
            "peak_python_heap_mb": round(peak_mem_bytes / (1024 * 1024), 2),
            "http_requests_count": store.http_requests,
            "http_bytes_transferred_kb": round(store.bytes_downloaded / 1024.0, 2),
            "gpu_required": False,
        },
        "hourly_forecast": hourly_records,
    }

    out_path = out_dir / "dima_hasao_gfs_forecast_eval.json"
    serialized = json.dumps(result, indent=2)
    out_path.write_text(serialized, encoding="utf-8")
    result["performance_benchmark"]["output_disk_kb"] = round(out_path.stat().st_size / 1024.0, 2)
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    res = evaluate_dynamical_gfs_dima_hasao()
    print(
        json.dumps(
            {
                "init_time_utc": res["temporal_domain"]["forecast_init_time_utc"],
                "grid_cells": res["spatial_domain"]["total_grid_cells"],
                "summary_metrics": res["summary_metrics"],
                "validation": res["validation"],
                "performance_benchmark": res["performance_benchmark"],
            },
            indent=2,
        )
    )
