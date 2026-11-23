# GeoResilience-NER 2.0 — Ingestion Verification & Sample Real Observations

**Pilot Study Area:** Dima Hasao District, Assam, India
**Ingestion Pipeline Run:** `2026-11-23T09:00:20Z` – `2026-11-23T09:01:31Z` (aspect raster regenerated `2026-11-23T09:08:19Z` after fixing Horn downhill sign bug caught by unit test)
**Total Verified Artifact Footprint:** `15,127,930 bytes` (`14.43 MB`) across 11 files in `backend/data/pilot/`

---

## 1. Verified Artifact Inventory & Checksums

| File (`backend/data/pilot/`) | Size (bytes) | SHA-256 Prefix | CRS | Description |
|---|---:|---|---|---|
| `dima_hasao_boundary.geojson` | 326,990 | `5991b3e5b0760868` | `EPSG:4326` | Validated OSM `relation/2025931` polygon (`4,880.75 km²`) |
| `haflong_jatinga_copernicus_dem_30m.tif` | 2,587,776 | `181ca5b6265f462d` | `EPSG:4326` | Native 30 m Copernicus DEM GLO-30 over Haflong–Jatinga corridor (`92.85–93.15°E, 25.05–25.30°N`) |
| `dima_hasao_dem_utm46n.tif` | 3,559,318 | `8e04732714be7cd8` | `EPSG:32646` | Reprojected 90 m district Copernicus DEM (`11.64–2,065.81 m`) |
| `dima_hasao_slope_deg_utm46n.tif` | 4,026,049 | `e6308bb830a72ff7` | `EPSG:32646` | Horn (1981) 3×3 terrain slope (`0.0°–66.36°`, mean `11.22°`, p95 `28.03°`) |
| `dima_hasao_aspect_deg_utm46n.tif` | 4,029,922 | `c08ddea91cee791b` | `EPSG:32646` | Horn (1981) downhill aspect (`0.0°–360.0°` clockwise from North) |
| `dima_hasao_worldcover_2021_utm46n.tif` | 548,543 | `602c87146c2bead3` | `EPSG:32646` | ESA WorldCover 2021 v200 land cover (30 m mode/nearest) |
| `dima_hasao_rainfall_imerg.json` | 30,130 | `a243203b63c157ac` | `EPSG:4326` | NASA GPM IMERG Late Run Daily (May–Jun 2024) + NASA POWER reference |
| `copernicus_dem_metadata.json` | 3,122 | `fe65589da9a62ca6` | Metadata | Tile URLs, stats, algorithm, timestamps, attribution |
| `worldcover_metadata.json` | 2,966 | `8b8ebd35de106f20` | Metadata | Tile URLs, class areas/percentages, accuracy & limitations |
| `landslide_inventory_discovery.json` | 4,818 | `ad35f4f82738dbf8` | Metadata | Live probe results for GSI, ISRO/NRSC, NASA COOLR (`0` fabricated records) |
| `ingestion_manifest.json` | 8,296 | `b842299c0a7ec549` | Metadata | Master pipeline run manifest |

---

## 2. District-Wide Physical Sanity Checks

### 2.1 Topography (Copernicus DEM GLO-30)
- **Elevation (`EPSG:32646`, 90 m district raster):** Min `11.64 m`, Max `2,065.81 m` (consistent with Barail Range peaks in Dima Hasao), Mean `528.52 m`, 95th percentile `1,248.92 m`.
- **Slope (Horn 1981 3×3 finite difference on metric UTM grid):** Min `0.00°`, Max `66.36°`, Mean `11.22°`, 95th percentile `28.03°`.
- **Analytical Correctness Check:** During pytest verification, `test_horn_slope_aspect_matches_analytical_tilted_plane` caught a sign inversion in the initial aspect formula (`atan2(dz_dx, -dz_dy)` produced `270°` instead of `90°` for an East-facing slope). Fixed to `atan2(-dz_dx, dz_dy)` (downhill vector `(-dz/dx, -dz/dy)` with `y` increasing southward in image rows), regenerated `dima_hasao_aspect_deg_utm46n.tif`, and verified `< 0.01°` error against analytical planes.

### 2.2 Land Cover Distribution (ESA WorldCover 2021 v200)
| Class Code | Class Label | Area (km², clipped bbox) | Share (%) |
|---:|---|---:|---:|
| 10 | Tree cover | 8,886.96 | 89.47% |
| 30 | Grassland | 653.81 | 6.58% |
| 40 | Cropland | 333.23 | 3.36% |
| 80 | Permanent water bodies | 26.94 | 0.27% |
| 50 | Built-up | 19.50 | 0.20% |
| 60 | Bare / sparse vegetation | 11.23 | 0.11% |
| 90 | Herbaceous wetland | 0.39 | 0.00% |
| 20 | Shrubland | 0.29 | 0.00% |

*Note: Class areas represent the buffered bounding-box raster extent (`92.50°E–93.49°E, 24.95°N–25.85°N`) around Dima Hasao; the dominant ~89.5% forest cover aligns with Barail / North Cachar hill ecology.*

### 2.3 Satellite Rainfall (NASA GPM IMERG Late Run Daily, 2024-05-01 to 2024-06-30)
- **ClimateSERV Job ID:** `8f8d403b-bd9f-4f04-bf87-cfdbca3a0999`
- **Coverage:** `32` valid daily observations (`2024-05-01` through `2024-06-01`), `29` missing days (`2024-06-02` through `2024-06-30`) stored strictly as `null`.
- **Latest Valid Observation (`2024-06-01T23:59:59Z`):** `27.469 mm` (24 h) / `48.665 mm` (72 h rolling).
- **Window Peak (Cyclone Remal Episode):** Max 24-hour `203.259 mm`, Max 72-hour rolling `478.384 mm`.
- **Secondary NASA POWER (MERRA-2) Check:** `61/61` valid days retrieved for independent coarse-grid comparison; never silently merged into IMERG fields.

---

## 3. Sample Real Point Observations (Verified via Both FastAPI & Node CJS Server)

Queried directly from `GET /api/v1/environment/point?lat={lat}&lon={lon}`:

| Location | Coordinates (WGS84) | Inside Pilot Boundary | Elevation (m) | Elevation Res (m) | Slope (°) | Aspect (° / Dir) | ESA WorldCover 2021 | IMERG 24h / 72h (2024-06-01) | ML Probability |
|---|---|---|---:|---:|---:|---|---|---|---|
| **Haflong** | `25.1645, 93.0176` | `true` | `680.23` | `30.0` | `4.00` | `181.88° (S)` | `10: Tree cover` | `27.469 / 48.665 mm` | `null` |
| **Jatinga** | `25.1275, 93.0252` | `true` | `641.28` | `30.0` | `3.41` | `143.76° (SE)` | `50: Built-up` | `27.469 / 48.665 mm` | `null` |
| **Maibang** | `25.3025, 93.1335` | `true` | `302.30` | `90.0` | `19.87` | `44.22° (NE)` | `10: Tree cover` | `27.469 / 48.665 mm` | `null` |
| **Umrangso** | `25.5138, 92.7357` | `true` | `633.76` | `90.0` | `2.22` | `47.26° (NE)` | `10: Tree cover` | `27.469 / 48.665 mm` | `null` |
| **Out-of-Pilot (New Delhi)** | `28.6139, 77.2090` | `false` | `null` | `null` | `null` | `null` | `null` | `null / null` | `null` |

### Cross-Engine Parity Verification
For Haflong (`25.1645, 93.0176`), Python FastAPI (`rasterio` + `pyproj` + `shapely`) and the Node.js production CJS bundle (`dist/server.cjs` via `geotiff` + exact Transverse Mercator WGS84→UTM46N projection) returned **identical values**:
- `elevation_m = 680.23`, `slope_deg = 4.0`, `aspect_deg = 181.88 (S)`, `class_label = "Tree cover"`, `rainfall_24h_mm = 27.469`, `rainfall_72h_mm = 48.665`, `landslide_probability = null`.
