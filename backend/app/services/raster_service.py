"""
Real raster sampling service for Dima Hasao pilot study area.
Samples:
  - Copernicus DEM GLO-30 (native 30 m Haflong-Jatinga corridor + district UTM46N DEM/slope/aspect)
  - ESA WorldCover 10 m v200 (2021) land cover
Validates WGS84 coordinates, checks polygon containment against the real OSM boundary,
transforms coordinates accurately to EPSG:32646 via pyproj, and strictly respects nodata.
"""
from __future__ import annotations

import json
import math
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any

import rasterio
from pyproj import Transformer
from shapely.geometry import Point, shape

from backend.app.schemas import DatasetProvenance, LandCoverObservation, TerrainObservation
from backend.ingestion.fetch_worldcover import WORLDCOVER_CLASSES

_TO_UTM46N = Transformer.from_crs("EPSG:4326", "EPSG:32646", always_xy=True)


def aspect_to_cardinal(aspect_deg: float | None) -> str | None:
    if aspect_deg is None or aspect_deg < 0:
        return "Flat" if aspect_deg == -1.0 else None
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    idx = int(((aspect_deg + 22.5) % 360.0) // 45.0)
    return dirs[idx]


def _extract_valid_pixel(ds: rasterio.DatasetReader, x: float, y: float) -> float | None:
    b = ds.bounds
    if not (b.left <= x <= b.right and b.bottom <= y <= b.top):
        return None
    val = next(ds.sample([(x, y)]))[0]
    fval = float(val)
    nodata = ds.nodata
    if math.isnan(fval) or math.isinf(fval):
        return None
    if nodata is not None and abs(fval - float(nodata)) < 1e-3:
        return None
    if fval <= -9000.0:
        return None
    return fval


def _sample_single_band(tif_path: Path, x: float, y: float) -> float | None:
    if not tif_path.exists():
        return None
    with rasterio.open(tif_path) as ds:
        return _extract_valid_pixel(ds, x, y)


class PilotRasterService:
    def __init__(self, pilot_dir: Path) -> None:
        self.pilot_dir = pilot_dir
        self._lock = threading.RLock()
        self._boundary_geom = None
        self._boundary_meta: dict[str, Any] | None = None
        self._dem_meta: dict[str, Any] | None = None
        self._wc_meta: dict[str, Any] | None = None
        self._json_cache: dict[str, tuple[int, Any]] = {}
        self._datasets: dict[Path, tuple[int, rasterio.DatasetReader]] = {}
        self._point_cache: OrderedDict[tuple[float, float], tuple[bool, TerrainObservation, LandCoverObservation]] = OrderedDict()
        self._ext_cache: OrderedDict[tuple[float, float], dict[str, Any]] = OrderedDict()
        self._cache_generation_mtime: int = 0

    def close(self) -> None:
        with self._lock:
            for _, ds in self._datasets.values():
                try:
                    ds.close()
                except Exception:
                    pass
            self._datasets.clear()

    def _sample_cached(self, tif_path: Path, x: float, y: float) -> float | None:
        if not tif_path.exists():
            return None
        mtime_ns = tif_path.stat().st_mtime_ns
        with self._lock:
            cached = self._datasets.get(tif_path)
            if cached is None or cached[0] != mtime_ns:
                if cached is not None:
                    self._point_cache.clear()
                    self._ext_cache.clear()
                    try:
                        cached[1].close()
                    except Exception:
                        pass
                ds = rasterio.open(tif_path)
                self._datasets[tif_path] = (mtime_ns, ds)
            else:
                ds = cached[1]
            return _extract_valid_pixel(ds, x, y)

    def _load_json(self, filename: str) -> dict[str, Any] | None:
        p = self.pilot_dir / filename
        if not p.exists():
            return None
        mtime_ns = p.stat().st_mtime_ns
        with self._lock:
            cached = self._json_cache.get(filename)
            if cached is not None and cached[0] == mtime_ns:
                return cached[1]
            data = json.loads(p.read_text(encoding="utf-8"))
            self._json_cache[filename] = (mtime_ns, data)
            return data

    def get_boundary_geojson(self) -> dict[str, Any] | None:
        return self._load_json("dima_hasao_boundary.geojson")

    def is_within_pilot_boundary(self, lat: float, lon: float) -> bool:
        with self._lock:
            if self._boundary_geom is None:
                gj = self.get_boundary_geojson()
                if gj and gj.get("features"):
                    self._boundary_geom = shape(gj["features"][0]["geometry"])
                    self._boundary_meta = gj.get("metadata")
            if self._boundary_geom is None:
                return False
            return bool(self._boundary_geom.contains(Point(lon, lat)))

    def get_dem_metadata(self) -> dict[str, Any] | None:
        if self._dem_meta is None:
            self._dem_meta = self._load_json("copernicus_dem_metadata.json")
        return self._dem_meta

    def get_worldcover_metadata(self) -> dict[str, Any] | None:
        if self._wc_meta is None:
            self._wc_meta = self._load_json("worldcover_metadata.json")
        return self._wc_meta

    def sample_point(self, lat: float, lon: float) -> tuple[bool, TerrainObservation, LandCoverObservation]:
        cache_key = (round(lat, 6), round(lon, 6))
        with self._lock:
            hit = self._point_cache.get(cache_key)
            if hit is not None:
                self._point_cache.move_to_end(cache_key)
                return hit

        x_utm, y_utm = _TO_UTM46N.transform(lon, lat)
        dem_meta = self.get_dem_metadata()
        wc_meta = self.get_worldcover_metadata()

        # 1. Elevation: prefer native 30 m Haflong-Jatinga corridor DEM if inside core bounds
        core_30m = self.pilot_dir / "haflong_jatinga_copernicus_dem_30m.tif"
        dist_dem = self.pilot_dir / "dima_hasao_dem_utm46n.tif"
        slope_tif = self.pilot_dir / "dima_hasao_slope_deg_utm46n.tif"
        aspect_tif = self.pilot_dir / "dima_hasao_aspect_deg_utm46n.tif"
        wc_tif = self.pilot_dir / "dima_hasao_worldcover_2021_utm46n.tif"

        elev_val = self._sample_cached(core_30m, lon, lat)
        elev_res: float | None = 30.0 if elev_val is not None else None
        if elev_val is None:
            elev_val = self._sample_cached(dist_dem, x_utm, y_utm)
            if elev_val is not None:
                elev_res = float(dem_meta.get("district_raster_resolution_m", 90.0)) if dem_meta else 90.0

        slope_val = self._sample_cached(slope_tif, x_utm, y_utm)
        aspect_val = self._sample_cached(aspect_tif, x_utm, y_utm)

        dem_prov = None
        if dem_meta:
            first_tile = (dem_meta.get("source_tiles") or [{}])[0].get(
                "url", "https://copernicus-dem-30m.s3.amazonaws.com"
            )
            dem_prov = DatasetProvenance(
                dataset_id=dem_meta.get("dataset_id", "copernicus-dem-glo30"),
                dataset_name=dem_meta.get("dataset_name", "Copernicus DEM GLO-30"),
                product_version=dem_meta.get("product_version", "GLO-30"),
                source_url=first_tile,
                crs=dem_meta.get("derived_metric_crs", "EPSG:32646"),
                resolution_m=elev_res or dem_meta.get("native_resolution_m", 30.0),
                observation_period=dem_meta.get("observation_period", "2011–2015"),
                processing_timestamp=dem_meta.get("processing_timestamp"),
                attribution=dem_meta.get("attribution", "Copernicus / ESA"),
                limitations=dem_meta.get("limitations"),
            )

        terrain = TerrainObservation(
            elevation_m=round(elev_val, 2) if elev_val is not None else None,
            elevation_resolution_m=elev_res,
            slope_deg=round(slope_val, 2) if slope_val is not None else None,
            aspect_deg=round(aspect_val, 2) if aspect_val is not None else None,
            aspect_cardinal=aspect_to_cardinal(aspect_val),
            slope_aspect_resolution_m=(
                float(dem_meta.get("district_raster_resolution_m", 90.0))
                if (slope_val is not None and dem_meta)
                else None
            ),
            missing_elevation=elev_val is None,
            missing_slope_aspect=(slope_val is None or aspect_val is None),
            provenance=dem_prov,
        )

        # 2. Land Cover: ESA WorldCover 2021 v200
        lc_raw = self._sample_cached(wc_tif, x_utm, y_utm)
        lc_code = int(round(lc_raw)) if (lc_raw is not None and lc_raw > 0) else None
        lc_label = WORLDCOVER_CLASSES.get(lc_code) if lc_code is not None else None

        wc_prov = None
        if wc_meta:
            first_wc = (wc_meta.get("source_tiles") or [{}])[0].get(
                "url", "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
            )
            wc_prov = DatasetProvenance(
                dataset_id=wc_meta.get("dataset_id", "esa-worldcover-2021-v200"),
                dataset_name=wc_meta.get("dataset_name", "ESA WorldCover 10 m 2021 v200"),
                product_version=wc_meta.get("product_version", "v200"),
                source_url=first_wc,
                crs=wc_meta.get("exported_crs", "EPSG:32646"),
                resolution_m=float(wc_meta.get("exported_resolution_m", 30.0)),
                observation_period=wc_meta.get("observation_period", "2021-01-01 to 2021-12-31"),
                processing_timestamp=wc_meta.get("processing_timestamp"),
                attribution=wc_meta.get("attribution", "ESA WorldCover 2021"),
                limitations=wc_meta.get("uncertainty_and_limitations"),
            )

        land_cover = LandCoverObservation(
            class_code=lc_code,
            class_label=lc_label,
            missing_land_cover=lc_code is None,
            provenance=wc_prov,
        )

        within_raster = (elev_val is not None) or (slope_val is not None) or (lc_code is not None)
        res = (within_raster, terrain, land_cover)
        with self._lock:
            self._point_cache[cache_key] = res
            if len(self._point_cache) > 512:
                self._point_cache.popitem(last=False)
        return res

    def sample_extended_features(self, lat: float, lon: float) -> dict[str, Any]:
        """Samples all verified Stage 9 EPSG:32646 geomorphometry, SoilGrids 2.0, NDVI, and OSM distance rasters."""
        cache_key = (round(lat, 6), round(lon, 6))
        with self._lock:
            hit = self._ext_cache.get(cache_key)
            if hit is not None:
                self._ext_cache.move_to_end(cache_key)
                return hit

        x_utm, y_utm = _TO_UTM46N.transform(lon, lat)

        def _s(fname: str, ndigits: int = 3) -> float | None:
            v = self._sample_cached(self.pilot_dir / fname, x_utm, y_utm)
            return round(v, ndigits) if v is not None else None

        res = {
            "geomorphometry": {
                "profile_curvature_per_100m": _s("dima_hasao_profile_curvature_utm46n.tif", 5),
                "plan_curvature_per_100m": _s("dima_hasao_plan_curvature_utm46n.tif", 5),
                "tri_m": _s("dima_hasao_tri_m_utm46n.tif", 2),
                "twi": _s("dima_hasao_twi_utm46n.tif", 3),
                "flow_accumulation_m2": _s("dima_hasao_flow_acc_m2_utm46n.tif", 1),
                "distance_to_drainage_m": _s("dima_hasao_dist_drainage_m_utm46n.tif", 1),
                "crs": "EPSG:32646",
                "resolution_m": 90.0,
            },
            "soilgrids_2_0": {
                "clay_0_5cm_pct": _s("dima_hasao_soilgrids_clay_0_5cm_utm46n.tif", 2),
                "clay_15_30cm_pct": _s("dima_hasao_soilgrids_clay_15_30cm_utm46n.tif", 2),
                "sand_0_5cm_pct": _s("dima_hasao_soilgrids_sand_0_5cm_utm46n.tif", 2),
                "silt_0_5cm_pct": _s("dima_hasao_soilgrids_silt_0_5cm_utm46n.tif", 2),
                "bulk_density_0_5cm_g_cm3": _s("dima_hasao_soilgrids_bdod_0_5cm_utm46n.tif", 3),
                "coarse_fragments_0_5cm_vol_pct": _s("dima_hasao_soilgrids_cfvo_0_5cm_utm46n.tif", 2),
                "soc_0_5cm_g_kg": _s("dima_hasao_soilgrids_soc_0_5cm_utm46n.tif", 2),
                "cohesion_kpa": None,
                "friction_angle_deg": None,
                "soil_moisture_dynamic": None,
                "provider": "ISRIC SoilGrids 2.0 (250 m native, resampled to EPSG:32646)",
                "scientific_note": (
                    "Texture/density only. Geotechnical cohesion and friction angle are NEVER inferred "
                    "from texture alone; dynamic soil moisture (SMAP L4) requires Earthdata auth."
                ),
            },
            "vegetation_ndvi": {
                "ndvi_premonsoon_2024": _s("dima_hasao_ndvi_premonsoon_2024_utm46n.tif", 4),
                "clear_obs_count": _s("dima_hasao_ndvi_qa_clear_obs_count_utm46n.tif", 0),
                "reference_epoch": "2024-02-01 to 2024-04-30 (Sentinel-2 L2A static reference)",
                "temporal_leakage_warning": "Static 2024 pre-monsoon reference; must NOT be applied to pre-2024 historical landslide events.",
            },
            "transport_proximity": {
                "distance_to_road_m": _s("dima_hasao_dist_road_m_utm46n.tif", 1),
                "distance_to_railway_m": _s("dima_hasao_dist_railway_m_utm46n.tif", 1),
                "provider": "OpenStreetMap Overpass API (ODbL 1.0)",
            },
            "geology": {
                "lithology_class": None,
                "rock_formation": None,
                "distance_to_fault_m": None,
                "status": "access_blocked_gsi_ngdr_bhukosh",
                "limitations": (
                    "GSI 1:50k lithology and thrust-fault GIS layers are restricted behind NGDR/Bhukosh "
                    "portal authentication. No geological polygons are fabricated."
                ),
            },
        }
        with self._lock:
            self._ext_cache[cache_key] = res
            if len(self._ext_cache) > 512:
                self._ext_cache.popitem(last=False)
        return res

