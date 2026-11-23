# GeoResilience-NER 2.0 — Geospatial & GIS Verification Report

**Pilot Study Area:** Dima Hasao District, Assam (`4,880.75 km²`)  
**Geographic CRS:** `EPSG:4326` (WGS84)  
**Metric Projected CRS:** `EPSG:32646` (WGS84 / UTM Zone 46N)

---

## 1. Raster Grid Alignment & Physical Range Verification

All `12` district-wide `90 m` terrain, hydrology, NDVI, and OSM transport distance GeoTIFFs share identical array dimensions, `EPSG:32646` CRS, and affine transforms (`terrain_utm_grid_aligned: true`), with explicit `nodata = -9999.0` (or `0` for WorldCover), zero NaN leaks, and `99.11%–100.0%` valid coverage:

| Raster Layer | CRS | Valid Coverage | Verified Physical Range |
| :--- | :---: | :---: | :--- |
| Copernicus DEM (30 m Haflong–Jatinga Core) | `EPSG:4326` | `100.00%` | `127.06` to `1746.09 m` |
| Copernicus DEM (90 m Full District) | `EPSG:32646` | `99.43%` | `11.64` to `2065.81 m` |
| Slope (Horn 3×3 analytical verified) | `EPSG:32646` | `99.11%` | `0.00°` to `66.36°` |
| Aspect | `EPSG:32646` | `99.11%` | `-1.0°` (flat) to `360.0°` |
| Profile Curvature | `EPSG:32646` | `99.11%` | `-5.143` to `15.836` |
| Plan Curvature | `EPSG:32646` | `99.11%` | `-7.673` to `5.083` |
| Terrain Ruggedness Index (TRI) | `EPSG:32646` | `99.11%` | `0.00` to `2239.87 m` |
| D8 Flow Accumulation | `EPSG:32646` | `99.11%` | `8,100` to `27,207,900 m²` |
| Topographic Wetness Index (TWI) | `EPSG:32646` | `99.11%` | `3.906` to `17.905` |
| Distance to Drainage | `EPSG:32646` | `99.11%` | `0.0` to `3,444.8 m` |
| ISRIC SoilGrids 2.0 Clay (`0–5 cm` + 6 layers) | `EPSG:32646` | `99.57%` | `24.55%` to `40.31%` (urban/water masked as `null`) |
| ISRIC SoilGrids 2.0 Bulk Density (`0–5 cm`) | `EPSG:32646` | `99.57%` | `0.932` to `1.314 g/cm³` |
| Sentinel-2 L2A Pre-Monsoon 2024 NDVI | `EPSG:32646` | `99.58%` | `-0.599` to `0.931` (+ clear-obs QA layer) |
| ESA WorldCover 2021 (`30 m`) | `EPSG:32646` | `99.52%` | Classes `{10, 20, 30, 40, 50, 60, 80, 90}` |
| OSM Distance to Road / Railway | `EPSG:32646` | `99.43%` | Road `0–17,573 m`; Rail `0–58,648 m` |

---

## 2. Vector & Infrastructure Exposure Verification

- **District Boundary (`dima_hasao_boundary.geojson`):** Validated Shapely polygon bounds `[92.520515, 24.971076, 93.473486, 25.828943]`.
- **OSM Transport Network (`dima_hasao_osm_transport.geojson`):** `2,212` road segments (including NH-27 / NH-54E) + `392` railway segments (Lumding–Badarpur hill railway).
- **OSM Facilities, Settlements & Bridges (`dima_hasao_osm_facilities.geojson`):** Live Overpass ingestion on `2026-11-23` inside Dima Hasao verified **`619` point features**: `15` hospitals/health facilities, `21` schools, `376` settlements, and `207` bridges.
- **Outside-Boundary Safety:** Verified via automated tests (`28.6139, 77.2090` New Delhi) that queries outside the pilot polygon return `within_pilot_boundary: false` and explicit `null` environmental values (never fabricated defaults).
- **Urban Nodata Safety:** Verified that ISRIC SoilGrids 2.0 urban/water masked pixels (e.g., Haflong town center `25.1645, 93.0176`) honestly return `null`, whereas adjacent natural hillslopes (e.g., Jatinga `25.1250, 93.0250`) return measured soil texture percentages.
