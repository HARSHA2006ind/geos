# GeoResilience-NER 2.0 — Real Data Sources & Provider Audit

**Pilot Study Area:** Dima Hasao District, Assam, India (`bbox: [92.520515, 24.971076, 93.473486, 25.828943]`, `EPSG:4326`)
**Audit Date (UTC):** 2026-11-23

This registry catalogs every real environmental dataset retrieved in Phase 1, along with authoritative external providers whose data could not be fetched directly due to authentication requirements or container network restrictions. **No synthetic environmental values or fabricated landslide labels were created.**

---

## 1. Successfully Retrieved & Verified Open Datasets

### 1.1 Administrative Study-Area Boundary — OpenStreetMap (Nominatim)
- **Dataset ID:** `osm-dima-hasao-boundary`
- **Source Endpoint:** `https://nominatim.openstreetmap.org/search?q=Dima+Hasao%2C+Assam%2C+India&format=geojson&polygon_geojson=1&addressdetails=1&limit=5`
- **Entity:** `relation/2025931` (`Dima Hasao District, Assam, India`)
- **Credentials Required:** None (public HTTP endpoint with compliant `User-Agent` header)
- **CRS:** Native `EPSG:4326`; area calculated in projected `EPSG:32646` (`4,880.75 km²`)
- **License / Attribution:** `© OpenStreetMap contributors (ODbL 1.0) via Nominatim`
- **Known Limitations:** Community-maintained administrative boundary; official Survey of India (SoI) district boundaries may differ slightly along state borders.

### 1.2 Digital Elevation Model & Derived Terrain — Copernicus DEM GLO-30
- **Dataset ID:** `copernicus-dem-glo30`
- **Product Version:** `COP-DEM_GLO-30-DGED / 2021_1` (AWS Open Data Cloud-Optimized GeoTIFFs)
- **Source Tiles Retrieved (HTTP 200, no credentials):**
  1. `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N24_00_E092_00_DEM/Copernicus_DSM_COG_10_N24_00_E092_00_DEM.tif`
  2. `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N24_00_E093_00_DEM/Copernicus_DSM_COG_10_N24_00_E093_00_DEM.tif`
  3. `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N25_00_E092_00_DEM/Copernicus_DSM_COG_10_N25_00_E092_00_DEM.tif`
  4. `https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N25_00_E093_00_DEM/Copernicus_DSM_COG_10_N25_00_E093_00_DEM.tif`
- **Native Resolution & CRS:** `1 arc-second` (~30 m), `EPSG:4326`, `float32`
- **Derived Products:**
  - Haflong–Jatinga core corridor native 30 m clip (`EPSG:4326`)
  - District-wide reprojected DEM (`EPSG:32646`, 90 m)
  - District-wide Horn (1981) 3×3 slope (`degrees`, `EPSG:32646`, 90 m) and downhill aspect (`0–360°` clockwise from North, `EPSG:32646`, 90 m)
- **Observation Period:** TanDEM-X mission acquisitions (2011–2015), Copernicus DEM 2021 release
- **License / Attribution:** `© DLR e.V. 2010–2014 and © Airbus Defence and Space GmbH 2014–2018 provided under COPERNICUS by the European Union and ESA`
- **Known Limitations:** GLO-30 is a Digital Surface Model (DSM) that includes forest canopy height rather than bare-earth DTM; 90 m district derivatives smooth narrow road-cut escarpments compared to native 30 m pixels.

### 1.3 Satellite Rainfall — NASA GPM IMERG Late Run Daily (via SERVIR ClimateSERV)
- **Dataset ID:** `nasa-gpm-imerg-daily`
- **Product Version:** GPM IMERG Late Run Daily (`datatype=26`) via SERVIR Global ClimateSERV API
- **Source Request URL:** `https://climateserv.servirglobal.net/api/getDataFromRequest/?id=8f8d403b-bd9f-4f04-bf87-cfdbca3a0999`
- **Credentials Required:** None for ClimateSERV API
- **Spatial Resolution & CRS:** `0.1° × 0.1°` (~11.1 km), `EPSG:4326`, areal mean over Dima Hasao bounding box
- **Observation Window:** `2024-05-01` to `2024-06-30` (61 days; covers Cyclone Remal extreme rainfall event in late May 2024)
- **Data Completeness:** **32 valid days**, **29 missing days** explicitly stored as `null` (never imputed to `0.0`). Rolling 72-hour totals require 3 consecutive non-null days.
- **Latency Profile:** IMERG Early Run ~4 h; IMERG Late Run ~14 h; IMERG Final Run (GES DISC) ~3.5 months.
- **Secondary Independent Reference:** NASA LaRC POWER (`MERRA-2`, `PRECTOTCORR`, `0.5° × 0.625°` coarse grid, 61/61 valid days) retained strictly as a separate secondary benchmark and never silently substituted for GPM IMERG.
- **Attribution:** `NASA Goddard Space Flight Center GPM IMERG via SERVIR Global ClimateSERV; secondary reference NASA LaRC POWER (MERRA-2).`
- **Known Limitations:** District-level areal mean at ~11.1 km resolution cannot resolve localized convective cloudbursts on individual hillslopes; missing ClimateSERV days after 2024-06-01 require direct NASA Earthdata GES DISC access for full continuous archives.

### 1.4 Land Cover — ESA WorldCover 10 m 2021 v200
- **Dataset ID:** `esa-worldcover-2021-v200`
- **Product Version:** `v200` (2021 annual composite derived from Sentinel-1 SAR & Sentinel-2 optical imagery)
- **Source Tiles Retrieved (HTTP 200, no credentials):**
  1. `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N24E090_Map.tif`
  2. `https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/ESA_WorldCover_10m_2021_v200_N24E093_Map.tif`
- **Native Resolution & CRS:** `10 m` (`8.3333e-05°`), `EPSG:4326`, `uint8`
- **Exported Pilot Product:** `30 m` `EPSG:32646` (mode aggregation + nearest reprojection)
- **License / Attribution:** `© ESA WorldCover project 2021 / Contains modified Copernicus Sentinel data (2021) processed by ESA WorldCover consortium (CC BY 4.0).`
- **Known Limitations:** Static 2021 snapshot (global overall accuracy ~76.7% in ESA v200 validation report). Does not capture post-2021 deforestation, *jhum* shifting cultivation cycles, new NH-27/railway cut-slopes, or seasonal vegetation stress.

---

## 2. Providers Requiring Credentials, Registration, or External Network Access

| Provider & Dataset | Endpoint Probed | Auth / Registration | Observed Runtime Result | Resolution Path |
|---|---|---|---|---|
| **NASA GES DISC** — Direct GPM IMERG V07B Daily NetCDF4 (`GPM_3IMERGDF.07`) | `https://gpm1.gesdisc.eosdis.nasa.gov/data/GPM_L3/GPM_3IMERGDF.07/` | **Required:** Free NASA Earthdata Login (URS OAuth2) + `.netrc` / bearer token | `HTTP 302` redirect to Earthdata Login | Register at `https://urs.earthdata.nasa.gov`, authorize `NASA GESDISC DATA ARCHIVE`, configure `EARTHDATA_TOKEN` in server `.env`. |
| **Geological Survey of India (GSI)** — Bhukosh National Landslide Inventory & NLSM | `https://bhukosh.gsi.gov.in/Bhukosh/Public` (`bhusanket.gsi.gov.in`) | **Required:** Free Bhukosh portal account + manual AOI shapefile export (no public REST API) | `ConnectTimeout` from sandbox container | Register on GSI Bhukosh, export Assam / Dima Hasao Landslide Inventory shapefile (`.zip`), place in `backend/data/raw/gsi_landslides/`. |
| **ISRO / NRSC** — Landslide Atlas of India (1998–2022) & Bhuvan Disaster Archive | `https://bhuvan-app1.nrsc.gov.in/disaster/disaster.php` | **Required:** Bhuvan account / formal institutional request to NRSC or NESAC Shillong (public Atlas is PDF summary only) | `ConnectError` (DNS resolution failed in container) | Submit institutional data request to NRSC/NESAC for point/polygon inventories; never transcribe PDF charts into synthetic coordinates. |
| **NASA GSFC** — Global Landslide Catalog (GLC) & COOLR | `https://maps.nccs.nasa.gov/arcgis/rest/services/Landslides/COOLR_Events_Points/FeatureServer/0` | **No registration required** (public ArcGIS REST API & CSV/GeoPackage download) | `ReadTimeout` from sandbox container | Query public FeatureServer or download official COOLR GeoPackage from `https://gpm.nasa.gov/landslides/data.html` on an unrestricted host; filter strictly by `location_accuracy <= 5 km`. |
| **IMD** — Gridded Daily Rainfall (`0.25°`) & AWS/ARG Station Feed | N/A (not yet integrated) | Public historical `.grd` via `imdpune.gov.in`; near-real-time AWS API requires institutional MoU/API key | Not queried in Phase 1 | Download IMD `0.25°` historical gridded rainfall via `imdlib` on server and pursue Assam SDMA / IMD Guwahati API access for live gauges. |
| **SoilGrids 2.0 (ISRIC) / GSI Lithology & Fault Maps** | N/A (Phase 2) | SoilGrids WCS is open; GSI 1:50k geology/lineaments require Bhukosh registration | Deferred to Phase 2 | Ingest SoilGrids clay/sand/silt/bulk density + GSI Bhukosh lithology & active fault shapefiles before ML feature engineering. |
