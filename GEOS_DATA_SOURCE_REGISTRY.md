# GeoResilience-NER 2.0 — Authentic Data Source Registry

All locally ingested datasets carry verified source URLs, CRS definitions, processing timestamps, and explicit scientific limitations. Zero synthetic geospatial rasters, zero fabricated landslide labels, and zero fabricated population estimates exist in the pipeline.

---

## 1. Verified Ingested Datasets (Dima Hasao Pilot)

| Dataset ID | Provider & Product | CRS & Resolution | Coverage / Period | License / Auth | Local Status & Limitations |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `osm-dima-hasao-boundary` | OpenStreetMap Nominatim/Overpass (Relation `2025210`) | `EPSG:4326` vector | `4,880.75 km²` | ODbL-1.0 / Open | **Verified.** Official district polygon for clipping & boundary checks. |
| `copernicus-dem-glo30` | ESA Copernicus DEM GLO-30 & GLO-90 | `EPSG:4326` (30 m core) & `EPSG:32646` (90 m district) | TanDEM-X 2011–2015 (2021 release) | Copernicus Open / Open | **Verified.** Elevation `11.64–2065.81 m`, slope `0.00–66.36°`, 6 aligned geomorphometric/hydrological derivatives. |
| `esa-worldcover-2021-v200` | ESA WorldCover 2021 v200 | `EPSG:32646` (30 m resampled from 10 m) | 2021 annual composite | CC-BY-4.0 / Open | **Verified.** Static 2021 snapshot — post-dates 65 pre-2021 landslide events (excluded from historical ML training). |
| `isric-soilgrids-2-0` | ISRIC SoilGrids 2.0 (`clay 0-5/15-30`, `sand`, `silt`, `bdod`, `cfvo`, `soc`) | `EPSG:32646` (`250 m` native) | Static reference (2020) | CC-BY-4.0 / Open | **Verified (7 layers).** Urban/water pixels masked as `nodata` (honest `null`). Texture only — never used to invent cohesion or friction angle. |
| `sentinel2-l2a-ndvi-2024` | ESA Sentinel-2 L2A via Element84 Earth Search STAC | `EPSG:32646` (`90 m` grid + clear-obs QA) | `2024-02-01` to `2024-04-30` | Copernicus Open / Open | **Verified.** Pre-monsoon 2024 baseline (`-0.599` to `0.931`); post-dates pre-May-2024 historical events (excluded from ML training). |
| `nasa-gpm-imerg-daily` | NASA GPM IMERG Late Daily via SERVIR ClimateSERV | `EPSG:4326` (`0.1°` / ~11.1 km) | `2015-01-01` to `2024-12-31` | NASA Open / Open (archive) | **Verified (94.14% complete).** `3,439` valid days, `214` missing days (`2024-06-02`–`2024-12-31`) preserved strictly as `null`. `213/213` IMERG V07B granules confirmed in NASA CMR awaiting Earthdata Login token. |
| `dynamical-noaa-gfs-forecast` | NOAA NCEP GFS `0.25°` via Dynamical.org Zarr v3 | `EPSG:4326` (`0.25°` / ~27.8 km) | Experimental 0–72h forward forecast (`init 2026-11-22T18:00Z`) | CC-BY-4.0 / Open | **Verified (Experimental Forecast Only).** `2.521 mm` (24h) / `6.061 mm` (72h) outlook. Smooths local orographic peaks; never labeled measured rainfall. |
| `gsi-bhusanket-dima-hasao` | Geological Survey of India (GSI) Bhusanket Public API | `EPSG:4326` point centroids | `1998–2026` (mixed precision) | GSI Public Portal / Open | **Verified (379 in-district / 418 total).** Point centroids without GPS error radius, 81 near-duplicate pairs (`<= 50 m`), 77.8% transport-corridor bias, only 95 day-dated records. |
| `nasa-coolr-dima-hasao` | NASA Cooperative Open Online Landslide Repository | `EPSG:4326` points | Multi-year historical | NASA Public Domain / Open | **Verified (19 in-district / 104 buffer).** Coarse 1–50 km accuracy; contextual visualization only (0 slope-scale usable). |
| `osm-dima-hasao-transport` | OpenStreetMap Overpass API | `EPSG:4326` lines + `EPSG:32646` distance rasters | Live OSM snapshot | ODbL-1.0 / Open | **Verified.** `2,212` road segments, `392` railway segments (Lumding–Badarpur hill rail). |
| `osm-dima-hasao-facilities` | OpenStreetMap Overpass API (`fetch_osm_facilities.py`) | `EPSG:4326` points | `2026-11-23` snapshot | ODbL-1.0 / Open | **Verified.** `15` hospitals/health, `21` schools, `376` settlements, `207` bridges (`619` assets). Volunteer-mapped rural coverage incomplete; zero fabricated population counts. |

---

## 2. Blocked / Restricted Upstream Sources (Explicitly Unfabricated)

| Dataset | Upstream Authority | Access Barrier | Scientific Impact |
| :--- | :--- | :--- | :--- |
| **GSI 1:50k Lithology & Thrust-Fault GIS** | GSI NGDR / Bhukosh | Portal login & authenticated GIS token required | Missing bedrock/structural conditioning covariates (`geology.lithology_class = null`). |
| **GSI Landslide Polygon FeatureServer** | GSI Bhusanket (`Landslide_Polygon/FeatureServer`) | HTTP 499 Token Required | Prevents certified polygon/headscarp geometry validation (`<= 100 m` accuracy gate fails). |
| **NASA GPM IMERG V07B/V07C HDF5 (2024–2026)** | NASA GES DISC | Free NASA Earthdata Login (`NASA_EARTHDATA_TOKEN`) required | Leaves `2024-06-02`–present rainfall gap as `null`. |
| **NASA SMAP L4 Dynamic Soil Moisture** | NSIDC / NASA Earthdata | NASA Earthdata Login required | Dynamic root-zone soil moisture remains `null` (SoilGrids is static texture only). |
| **IMD / CWC District Rain Gauges** | India Meteorological Dept / CWC | Institutional portal / non-public station feed | Prevents ground-gauge bias calibration of IMERG & GFS in Barail Range terrain. |
| **Gridded Population (WorldPop / Census)** | WorldPop / Census of India | Not ingested locally | Population impact figures remain unfabricated (`null` / explicit OSM tag note). |
