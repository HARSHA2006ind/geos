"""
Dataset B — NASA GPM IMERG Real Precipitation Acquisition Pipeline.

Primary Access Route (No Credentials Required):
  SERVIR ClimateSERV Public REST API (https://climateserv.servirglobal.net/api/)
  - datatype=26: NASA GPM IMERG Late Run Daily (0.1° x 0.1°, ~14h latency)
  - datatype=91: NASA GPM IMERG Early Run Daily (0.1° x 0.1°, ~4h latency)

Direct GES DISC Access Note:
  Direct NetCDF4/HDF5 downloads from https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDF.07/
  redirect (HTTP 302) to NASA Earthdata Login (https://urs.earthdata.nasa.gov/oauth/authorize).
  This pipeline therefore retrieves official NASA GPM IMERG via ClimateSERV AND records
  the exact GES DISC credential requirement for V07B gridded sub-daily NetCDF4 workflows.

Scientific Data Integrity Rules:
  - Missing / NaN / negative fill values are NEVER converted to 0.0 mm.
  - 24h accumulation equals that day's valid observed daily total (or null if missing).
  - 72h accumulation requires ALL 3 consecutive days (t-2, t-1, t) to be non-null;
    otherwise rainfall_72h_mm is strictly null with missing_data_flag = True.
"""
from __future__ import annotations

import json
import math
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

PILOT_DIR = Path(__file__).resolve().parents[1] / "data" / "pilot"
CLIMATESERV_BASE = "https://climateserv.servirglobal.net/api"
NASA_POWER_DAILY_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"


def _submit_and_poll_climateserv(
    client: httpx.Client,
    datatype: int,
    start_date: date,
    end_date: date,
    polygon_geojson: dict[str, Any],
    max_polls: int = 30,
) -> tuple[str, list[dict[str, Any]]]:
    params = {
        "datatype": datatype,
        "begintime": start_date.strftime("%m/%d/%Y"),
        "endtime": end_date.strftime("%m/%d/%Y"),
        "intervaltype": 0,  # Daily
        "operationtype": 5,  # Area average
        "geometry": json.dumps(polygon_geojson),
    }
    sub_resp = client.get(f"{CLIMATESERV_BASE}/submitDataRequest/", params=params)
    sub_resp.raise_for_status()
    job_payload = sub_resp.json()
    if not isinstance(job_payload, list) or not job_payload:
        raise RuntimeError(f"Unexpected ClimateSERV submit response: {job_payload}")
    job_id = str(job_payload[0])

    for _ in range(max_polls):
        prog_resp = client.get(
            f"{CLIMATESERV_BASE}/getDataRequestProgress/", params={"id": job_id}
        )
        prog_resp.raise_for_status()
        prog = prog_resp.json()
        pct = float(prog[0]) if isinstance(prog, list) and prog else 0.0
        if pct >= 100.0:
            break
        if pct < 0:
            raise RuntimeError(f"ClimateSERV job {job_id} failed with progress {pct}")
        time.sleep(1.0)
    else:
        raise TimeoutError(f"ClimateSERV job {job_id} did not finish within {max_polls}s")

    data_resp = client.get(f"{CLIMATESERV_BASE}/getDataFromRequest/", params={"id": job_id})
    data_resp.raise_for_status()
    payload = data_resp.json()
    return job_id, payload.get("data", [])


def compute_rolling_accumulations(
    daily_map: dict[str, float | None],
    start_date: date,
    end_date: date,
) -> list[dict[str, Any]]:
    """
    Build a complete daily timeline between start_date and end_date (inclusive).
    Missing dates or invalid values remain None (never zero-filled).
    72h accumulation is computed ONLY when all 3 consecutive daily observations exist.
    """
    records: list[dict[str, Any]] = []
    cur = start_date
    ordered_vals: list[float | None] = []

    while cur <= end_date:
        iso = cur.isoformat()
        val = daily_map.get(iso, None)
        if val is not None and (math.isnan(val) or math.isinf(val) or val < 0):
            val = None
        ordered_vals.append(val)

        idx = len(ordered_vals) - 1
        rain_24h = round(val, 3) if val is not None else None
        if idx >= 2 and all(ordered_vals[j] is not None for j in (idx - 2, idx - 1, idx)):
            rain_72h = round(
                float(ordered_vals[idx - 2]) + float(ordered_vals[idx - 1]) + float(ordered_vals[idx]),
                3,
            )
            missing_72h = False
        else:
            rain_72h = None
            missing_72h = True

        records.append(
            {
                "date": iso,
                "observation_timestamp_utc": f"{iso}T23:59:59Z",
                "rainfall_24h_mm": rain_24h,
                "rainfall_72h_mm": rain_72h,
                "missing_24h": rain_24h is None,
                "missing_72h": missing_72h,
            }
        )
        cur += timedelta(days=1)

    return records


def ingest_gpm_imerg_rainfall(
    boundary_path: Path = PILOT_DIR / "dima_hasao_boundary.geojson",
    output_dir: Path = PILOT_DIR,
    start_date: date = date(2024, 5, 1),
    end_date: date = date(2024, 6, 30),
    datatype: int = 26,
) -> dict[str, Any]:
    """
    Retrieves actual NASA GPM IMERG daily observations for Dima Hasao (May–June 2024
    pre-monsoon & monsoon onset window, when Cyclone Remal & monsoon rains struck NER).
    Also retrieves NASA POWER MERRA-2 daily precipitation at Haflong centroid as an
    independent cross-reference series (clearly separated, never blended).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    boundary = json.loads(boundary_path.read_text(encoding="utf-8"))
    bbox = boundary["metadata"]["bbox_wgs84"]
    centroid = boundary["metadata"]["centroid_wgs84"]

    # Use bounding-box polygon for ClimateSERV (compact 5-vertex polygon within Dima Hasao)
    minx, miny, maxx, maxy = bbox
    pilot_poly = {
        "type": "Polygon",
        "coordinates": [
            [
                [round(minx, 4), round(miny, 4)],
                [round(maxx, 4), round(miny, 4)],
                [round(maxx, 4), round(maxy, 4)],
                [round(minx, 4), round(maxy, 4)],
                [round(minx, 4), round(miny, 4)],
            ]
        ],
    }

    with httpx.Client(timeout=30.0) as client:
        job_id, raw_rows = _submit_and_poll_climateserv(
            client=client,
            datatype=datatype,
            start_date=start_date,
            end_date=end_date,
            polygon_geojson=pilot_poly,
        )

        # Parse IMERG daily values strictly (never turn NaN / missing into 0)
        imerg_daily: dict[str, float | None] = {}
        for row in raw_rows:
            y, m, d = row.get("year"), row.get("month"), row.get("day")
            if not (y and m and d):
                continue
            iso = f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
            val_obj = row.get("value")
            raw_val = val_obj.get("avg") if isinstance(val_obj, dict) else row.get("raw_value")
            if raw_val is None:
                imerg_daily[iso] = None
            else:
                try:
                    num = float(raw_val)
                    imerg_daily[iso] = None if (math.isnan(num) or num < 0) else num
                except (TypeError, ValueError):
                    imerg_daily[iso] = None

        # Also fetch NASA POWER daily precipitation at Dima Hasao centroid as a documented secondary cross-check
        power_resp = client.get(
            NASA_POWER_DAILY_URL,
            params={
                "parameters": "PRECTOTCORR",
                "community": "AG",
                "longitude": centroid["lon"],
                "latitude": centroid["lat"],
                "start": start_date.strftime("%Y%m%d"),
                "end": end_date.strftime("%Y%m%d"),
                "format": "JSON",
            },
        )
        power_resp.raise_for_status()
        power_json = power_resp.json()

    imerg_series = compute_rolling_accumulations(imerg_daily, start_date, end_date)
    valid_imerg = [r for r in imerg_series if not r["missing_24h"]]
    missing_imerg_count = sum(1 for r in imerg_series if r["missing_24h"])

    # Parse NASA POWER MERRA-2 series strictly honoring fill_value (-999.0)
    fill_value = float(power_json.get("header", {}).get("fill_value", -999.0))
    power_raw = power_json.get("properties", {}).get("parameter", {}).get("PRECTOTCORR", {})
    power_daily: dict[str, float | None] = {}
    for ymd, val in power_raw.items():
        if len(ymd) == 8:
            iso = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:8]}"
            num = float(val)
            power_daily[iso] = None if (num <= fill_value + 1.0 or num < 0) else num
    power_series = compute_rolling_accumulations(power_daily, start_date, end_date)

    processed_at = datetime.now(timezone.utc).isoformat()
    product_label = (
        "NASA GPM IMERG Late Run Daily (ClimateSERV datatype=26)"
        if datatype == 26
        else f"NASA GPM IMERG Early Run Daily (ClimateSERV datatype={datatype})"
    )

    output_payload = {
        "dataset_id": "nasa-gpm-imerg-daily",
        "dataset_name": product_label,
        "product_version": "GPM IMERG Late Run Daily via SERVIR ClimateSERV API",
        "spatial_resolution_deg": 0.1,
        "spatial_resolution_approx_km": 11.1,
        "latency_info": "IMERG Late Run: ~14 hours; IMERG Early Run: ~4 hours; IMERG Final Run (GES DISC): ~3.5 months",
        "source_url": f"{CLIMATESERV_BASE}/getDataFromRequest/?id={job_id}",
        "climateserv_job_id": job_id,
        "direct_ges_disc_status": {
            "url": "https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDF.07/",
            "requires_credentials": True,
            "auth_mechanism": "NASA Earthdata Login (URS OAuth2 redirect HTTP 302)",
        },
        "study_area": "Dima Hasao District, Assam (Pilot Bounding Box)",
        "query_geometry_wgs84": pilot_poly,
        "interval_start": start_date.isoformat(),
        "interval_end": end_date.isoformat(),
        "total_days_in_interval": len(imerg_series),
        "valid_observation_days": len(valid_imerg),
        "missing_observation_days": missing_imerg_count,
        "latest_valid_observation": valid_imerg[-1] if valid_imerg else None,
        "max_24h_mm": max((r["rainfall_24h_mm"] for r in valid_imerg), default=None),
        "max_72h_mm": max(
            (r["rainfall_72h_mm"] for r in imerg_series if not r["missing_72h"]),
            default=None,
        ),
        "observations": imerg_series,
        "secondary_reference": {
            "dataset_id": "nasa-power-merra2-daily",
            "dataset_name": "NASA POWER Daily Precipitation (MERRA-2 PRECTOTCORR)",
            "api_version": power_json.get("header", {}).get("api", {}).get("version"),
            "point_wgs84": centroid,
            "spatial_resolution_deg": 0.5,
            "valid_observation_days": sum(1 for r in power_series if not r["missing_24h"]),
            "missing_observation_days": sum(1 for r in power_series if r["missing_24h"]),
            "observations": power_series,
            "note": "Retained strictly as an independent coarse-resolution (0.5°) reference; never substituted silently for GPM IMERG.",
        },
        "processing_timestamp": processed_at,
        "attribution": "NASA Goddard Space Flight Center GPM IMERG via SERVIR Global ClimateSERV; secondary reference NASA LaRC POWER (MERRA-2).",
        "missing_data_policy": "Missing observations are stored strictly as null; 72-hour rolling totals require 3 consecutive non-null days.",
    }

    out_path = output_dir / "dima_hasao_rainfall_imerg.json"
    out_path.write_text(json.dumps(output_payload, indent=2), encoding="utf-8")
    return {
        "dataset_id": output_payload["dataset_id"],
        "climateserv_job_id": job_id,
        "interval": f"{start_date.isoformat()} to {end_date.isoformat()}",
        "total_days": len(imerg_series),
        "valid_imerg_days": len(valid_imerg),
        "missing_imerg_days": missing_imerg_count,
        "max_24h_mm": output_payload["max_24h_mm"],
        "max_72h_mm": output_payload["max_72h_mm"],
        "latest_valid": output_payload["latest_valid_observation"],
        "power_valid_days": output_payload["secondary_reference"]["valid_observation_days"],
    }


if __name__ == "__main__":
    summary = ingest_gpm_imerg_rainfall()
    print(json.dumps(summary, indent=2))
