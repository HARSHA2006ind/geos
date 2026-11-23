"""
Real rainfall query service reading verified NASA GPM IMERG observations
for the Dima Hasao pilot study area. Strictly preserves null missing-data flags.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.app.schemas import (
    DailyRainfallPoint,
    DatasetProvenance,
    RainfallHistoryResponse,
    RainfallSnapshot,
)


import threading

class PilotRainfallService:
    def __init__(self, pilot_dir: Path) -> None:
        self.pilot_dir = pilot_dir
        self._lock = threading.RLock()
        self._cached_mtime_ns: int | None = None
        self._cached_payload: dict[str, Any] | None = None

    def _load_payload(self) -> dict[str, Any] | None:
        p = self.pilot_dir / "dima_hasao_rainfall_imerg.json"
        if not p.exists():
            return None
        mtime_ns = p.stat().st_mtime_ns
        with self._lock:
            if self._cached_payload is not None and self._cached_mtime_ns == mtime_ns:
                return self._cached_payload
            data = json.loads(p.read_text(encoding="utf-8"))
            self._cached_mtime_ns = mtime_ns
            self._cached_payload = data
            return data

    def get_snapshot(self, within_pilot: bool) -> RainfallSnapshot:
        payload = self._load_payload()
        if not payload or not within_pilot:
            return RainfallSnapshot(
                missing_24h=True,
                missing_72h=True,
                provenance=None,
            )

        latest = payload.get("latest_valid_observation")
        prov = DatasetProvenance(
            dataset_id=payload["dataset_id"],
            dataset_name=payload["dataset_name"],
            product_version=payload["product_version"],
            source_url=payload["source_url"],
            crs="EPSG:4326",
            resolution_m=round(float(payload.get("spatial_resolution_approx_km", 11.1)) * 1000.0, 1),
            observation_period=f"{payload['interval_start']} to {payload['interval_end']}",
            processing_timestamp=payload.get("processing_timestamp"),
            attribution=payload["attribution"],
            limitations=payload.get("missing_data_policy"),
        )
        return RainfallSnapshot(
            latest_observation_date=latest["date"] if latest else None,
            latest_observation_timestamp_utc=latest["observation_timestamp_utc"] if latest else None,
            rainfall_24h_mm=latest["rainfall_24h_mm"] if latest else None,
            rainfall_72h_mm=latest["rainfall_72h_mm"] if latest else None,
            max_24h_in_window_mm=payload.get("max_24h_mm"),
            max_72h_in_window_mm=payload.get("max_72h_mm"),
            window_start=payload["interval_start"],
            window_end=payload["interval_end"],
            valid_days_in_window=int(payload.get("valid_observation_days", 0)),
            missing_days_in_window=int(payload.get("missing_observation_days", 0)),
            missing_24h=latest["missing_24h"] if latest else True,
            missing_72h=latest["missing_72h"] if latest else True,
            latency_info=payload.get("latency_info"),
            provenance=prov,
        )

    def get_history(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> RainfallHistoryResponse | None:
        payload = self._load_payload()
        if not payload:
            return None

        obs = payload.get("observations", [])
        if start_date:
            obs = [o for o in obs if o["date"] >= start_date]
        if end_date:
            obs = [o for o in obs if o["date"] <= end_date]

        valid_24 = [o["rainfall_24h_mm"] for o in obs if not o["missing_24h"] and o["rainfall_24h_mm"] is not None]
        valid_72 = [o["rainfall_72h_mm"] for o in obs if not o["missing_72h"] and o["rainfall_72h_mm"] is not None]

        return RainfallHistoryResponse(
            study_area=payload["study_area"],
            dataset_id=payload["dataset_id"],
            dataset_name=payload["dataset_name"],
            product_version=payload["product_version"],
            spatial_resolution_deg=float(payload.get("spatial_resolution_deg", 0.1)),
            latency_info=payload["latency_info"],
            interval_start=obs[0]["date"] if obs else payload["interval_start"],
            interval_end=obs[-1]["date"] if obs else payload["interval_end"],
            total_days=len(obs),
            valid_observation_days=len(valid_24),
            missing_observation_days=len(obs) - len(valid_24),
            max_24h_mm=max(valid_24) if valid_24 else None,
            max_72h_mm=max(valid_72) if valid_72 else None,
            missing_data_policy=payload["missing_data_policy"],
            processing_timestamp=payload["processing_timestamp"],
            attribution=payload["attribution"],
            source_url=payload["source_url"],
            observations=[DailyRainfallPoint(**o) for o in obs],
        )
