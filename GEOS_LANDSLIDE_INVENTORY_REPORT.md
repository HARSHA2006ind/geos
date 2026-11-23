# GeoResilience-NER 2.0 — Landslide Inventory Acquisition & Uncertainty Report

**Pilot Study Area:** Dima Hasao District, Assam, India (`4,880.75 km²`, `EPSG:4326` / `EPSG:32646`)
**Surrounding Study Buffer:** `50 km` documented envelope (`[92.0, 24.5, 94.0, 26.3]`, `EPSG:4326`)
**Acquisition Timestamp (UTC):** `2026-11-23T09:50:20Z`
**Reproducible Script:** `backend/ingestion/fetch_coolr_landslides.py` & `backend/ingestion/discover_landslide_inventories.py`
**Fabricated / Synthetic Landslide Labels Created:** `0`

---

## 1. Executive Summary by Source

| Source | Endpoint / Portal | Raw Records (India / NER) | Raw in 50 km Buffer | Duplicates Removed | Within Exact Dima Hasao Polygon | Valid Coords (Pilot) | Exact Day Dates (Pilot) | Usable for 30 m/90 m Slope Training | Suitable Only for Contextual Visualization |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **NASA COOLR (`COOLR_Events_Points`)** | `gis.earthdata.nasa.gov/.../COOLR_Events_Points/FeatureServer/0` | 8,876 / 8,634 | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| **NASA COOLR (`COOLR_Reports_Points`)** | `gis.earthdata.nasa.gov/.../COOLR_Reports_Points/FeatureServer/0` | 3,672 / 879 | **104** | 0 | **19** | 19 | 19 | **0** | **19** (85 more in 50 km buffer) |
| **NASA COOLR (`COOLR_Events_Polygons`)** | `gis.earthdata.nasa.gov/.../COOLR_Events_Polygons/FeatureServer/0` | 796 / 0 | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| **NASA COOLR (`COOLR_Reports_Polygons`)** | `gis.earthdata.nasa.gov/.../COOLR_Reports_Polygons/FeatureServer/0` | 8 / 3 | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| **GSI Bhusanket / Bhukosh** | `https://bhusanket.gsi.gov.in/`, `https://bhukosh.gsi.gov.in/Bhukosh/Public` | Portal HTTP 200 (1,044 PDF reports; GIS behind login) | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| **ISRO / NRSC Landslide Atlas & Bhuvan** | `https://www.isro.gov.in/Landslide_Atlas_India.html` | Portal HTTP 200 (summary PDF only; GIS behind request) | 0 | 0 | 0 | 0 | 0 | **0** | 0 |
| **TOTAL VERIFIED** | | | **104** | **0** | **19** | **19** | **19** | **0** | **19 pilot / 104 buffer** |

---

## 2. Source A — NASA COOLR (Retrieved & Persisted)

### 2.1 Supported API Operations Verified
Queried `https://gis.earthdata.nasa.gov/portal/rest/services/Landslides?f=json` and confirmed four public ArcGIS FeatureServers supporting `Query`, `returnCountOnly`, `spatialRel=esriSpatialRelIntersects`, `outSR=4326`, and pagination (`supportsPagination=True`, `maxRecordCount=2000`):
- `COOLR_Events_Points` (`40,154` global records; satellite-mapped inventories): **0** records inside Dima Hasao or its 50 km buffer.
- `COOLR_Reports_Points` (`14,750` global records; NASA Global Landslide Catalog + citizen reports): **104** records in the 50 km study buffer, of which **19** fall inside the exact OSM Dima Hasao polygon (`dima_hasao_boundary.geojson`) and **85** lie in adjacent districts (Cachar, Karbi Anglong, Meghalaya Jaintia Hills, Tamenglong Manipur, Nagaland).
- `COOLR_Events_Polygons` (`22,421` global): **0** in NER / Dima Hasao.
- `COOLR_Reports_Polygons` (`48` global): **0** in Dima Hasao + 50 km buffer.

### 2.2 Raw Record Preservation, Deduplication & Database Storage
- **Unmodified Raw Archive:** `backend/data/pilot/nasa_coolr_raw_buffer50km.json` (`SHA-256: 5ac2c57774212dc143db5416d3143815dc5d567b5a78bca5cdb4224d8c948736`).
- **Curated & Classified JSON:** `backend/data/pilot/dima_hasao_landslides_coolr.json`.
- **Deduplication Rules Applied:** (1) Exact `(source_provider, external_event_id)` match; (2) Same `event_date` and Haversine distance `<= 250 m`. Result: **0** duplicates detected among the 104 retrieved buffer records (automated unit tests verify both rules).
- **Database Storage:** All **104** verified records stored idempotently in the `landslide_events` PostGIS/SQLAlchemy table (`backend/alembic/versions/0002_landslide_events_and_antecedent_rainfall.py`, verified against `backend/data/pilot/pilot_verification.db`).

### 2.3 Positional Precision, Temporal Coverage & Uncertainty Assessment
All **19** records inside Dima Hasao District come from `COOLR_Reports_Points` (media/report geocoding):

| `location_accuracy` | Conservative Uncertainty Radius | Count in Dima Hasao Polygon | Count in 50 km Buffer | Suitable for 30 m/90 m Slope Training? |
|---|---:|---:|---:|---|
| `exact` | ~50 m (`<= 100 m`) | **0** | 1 | Yes (if dated & verified) |
| `1km` | 1,000 m | **4** (all on `2017-04-04`) | 16 | **No** (11×–33× raster pixel size) |
| `5km` | 5,000 m | **5** | 33 | **No** (55×–167× raster pixel size) |
| `10km` | 10,000 m | **2** | 12 | **No** |
| `25km` | 25,000 m | **3** | 20 | **No** |
| `50km` | 50,000 m | **4** | 17 | **No** |
| `unknown` | Unbounded | **1** | 5 | **No** |

**Key Scientific Findings:**
1. **Severe Coordinate Uncertainty:** `0/19` Dima Hasao records have `exact` (`<= 100 m`) coordinates. Even the 4 best records (`1km`: Mahur, N. Leikul, Phaiding, Harangajao) all occurred on a single storm date (`2017-04-04`) and have ±1 km placement error—meaning sampling a 30 m or 90 m DEM pixel at those coordinates frequently hits a valley floor, road embankment, or opposing slope aspect rather than the actual failure scarp.
2. **Severe Temporal Under-Reporting & Reporting Bias:** All 19 Dima Hasao COOLR records span **`2007–2018`** (`0` records in `2019–2025`), completely omitting the catastrophic **May 2022** Lumding–Badarpur railway/NH-27 washouts and **May 2024 Cyclone Remal** landslides. Furthermore, media reports concentrate along railways and highways (Haflong, Mahur, Phaiding, Harangajao, Maibang), introducing severe **road/rail reporting bias** against unpopulated forested slopes.
3. **Consistent Rainfall Trigger Signal (Contextual Only):** `19/19` (`100%`) of Dima Hasao COOLR events are rainfall-triggered (`downpour`: 11, `rain`: 7, `continuous_rain`: 1). Cross-checking the 5 events on `2017-04-04` against our 10-year NASA GPM IMERG archive confirms an extreme **`692.194 mm` 7-day antecedent rainfall** (`360.632 mm` 3-day, `711.469 mm` 15-day) — the highest 7-day deluge in the entire 2015–2024 IMERG record!

### 2.4 All 19 Verified NASA COOLR Records Inside Dima Hasao District (Contextual Only)

| Event ID | Date (UTC) | Accuracy | Lat, Lon | Category | Trigger | Title (Original) |
|---:|---|---|---|---|---|---|
| `213` | `2007-08-26` | `unknown` | `25.2946, 92.8339` | `landslide` | `rain` | Shillong Road at Kuliang in the Jaintia Hills *(mis-geocoded inside Dima Hasao)* |
| `1109` | `2009-08-20` | `25km` | `25.5215, 93.1645` | `landslide` | `downpour` | Lumding-Badarpur section in North Cachar Hills district |
| `1127` | `2009-08-27` | `10km` | `25.1718, 93.1230` | `landslide` | `downpour` | between Mahur and Phaiding railway stations on Barail hills |
| `1611` | `2010-04-01` | `25km` | `25.1553, 93.0280` | `landslide` | `downpour` | Paglanala village, Dholai Block, near Dwarbandh locality |
| `1987` | `2010-06-15` | `25km` | `25.2269, 93.1658` | `landslide` | `downpour` | rails between Mahur and Wadringdisa(?), Assam |
| `2573` | `2010-10-09` | `5km` | `25.1796, 93.0083` | `mudslide` | `downpour` | Haflong, Assam |
| `2574` | `2010-10-09` | `50km` | `25.4749, 93.1477` | `landslide` | `downpour` | between Mahur and Maigrandisa(?) or Lumding, Assam |
| `2575` | `2010-10-09` | `50km` | `25.5242, 92.9914` | `landslide` | `downpour` | road between Haflong and Lanka, Assam |
| `3532` | `2011-05-24` | `10km` | `25.0888, 92.8551` | `complex` | `downpour` | Silchar-Haflong rd., at Reko(Rekha )(?), near Harangajao |
| `4382` | `2012-06-03` | `5km` | `25.1175, 92.8573` | `landslide` | `downpour` | between Harangajao and Mailongdisa, Assam |
| `4383` | `2012-06-03` | `5km` | `25.3056, 93.1265` | `landslide` | `downpour` | between Maibang and Daotohaja, Assam |
| `4384` | `2012-06-03` | `5km` | `25.1775, 93.0123` | `landslide` | `downpour` | between Haflong and Bagetar, Assam |
| `10976` | `2017-04-04` | `1km` | `25.1184, 92.8539` | `landslide` | `rain` | Landslide in Harangajao |
| `10977` | `2017-04-04` | `50km` | `25.4816, 93.1417` | `landslide` | `rain` | Landslides along National Highway 54 |
| `10978` | `2017-04-04` | `1km` | `25.1322, 93.0468` | `landslide` | `rain` | Landslide in N. Leikul |
| `10979` | `2017-04-04` | `1km` | `25.1954, 93.1728` | `landslide` | `rain` | Landslide in Phaiding |
| `10980` | `2017-04-04` | `1km` | `25.1815, 93.1181` | `landslide` | `rain` | Landslide in Mahur |
| `9750` | `2017-06-04` | `50km` | `25.1525, 92.9467` | `landslide` | `continuous_rain` | Flood, Landslide in Assam |
| `14086` | `2018-12-18` | `5km` | `25.1964, 93.1343` | `rock_fall` | `rain` | Rock fall on Railroad tracks between Phiding and Mahur |

*(Notice Event `213` — title references Jaintia Hills, Meghalaya, yet its `unknown`-accuracy point falls inside Dima Hasao! This concrete real-world example illustrates why unvalidated coarse COOLR points must never be treated blindly as 30 m ground truth.)*

---

## 3. Source B — Geological Survey of India (GSI)

Live probes on `2026-11-23`:
- **`https://bhusanket.gsi.gov.in/` (`HTTP 200`):** Exposes public HTML viewers (`./NLSM_10K_Map.html`, `./impactmap.html`, `statewiseLandslideReport.html` listing **1,044** statewise FSP project PDF reports). **Does not provide an unauthenticated bulk Shapefile/GeoJSON API.**
- **`https://www.gsi.gov.in/` (`HTTP 200`):** Official Ministry of Mines portal hosting publication catalogs and formal data-request guidance.
- **`https://bhukosh.gsi.gov.in/Bhukosh/Public`:** Interactive spatial portal hosting the **National Landslide Inventory**, **National Landslide Susceptibility Mapping (NLSM 1:50,000)**, and **1:50,000 Geological / Lithology / Structural Lineament & Fault GIS layers**.

### Access Classification & Human Action Required
| GSI Dataset | Access Tier | Required Human Action |
|---|---|---|
| Bhusanket Statewise FSP Landslide Reports (PDF) | Freely viewable via browser | Browse `https://bhusanket.gsi.gov.in/statewiseLandslideReport.html` (filter `State = Assam`). Useful for geotechnical context, not machine-readable polygons. |
| Bhukosh National Landslide Inventory (Point/Polygon Shapefiles) | **Free portal registration required** | Register at `https://bhukosh.gsi.gov.in/Bhukosh/Public` → Map Viewer → *Natural Hazards → Landslide Inventory* → Clip to Assam / Dima Hasao → Export Shapefile (`.zip`) → place in `backend/data/raw/gsi_landslides/`. |
| Bhukosh 1:50k Lithology, Structural Faults & NLSM Polygons | **Free portal registration / institutional request** | Same Bhukosh login → *Geology (50K) → Lithology & Lineaments/Faults* + *NLSM 50K*; for 1:10,000 meso-scale landslide maps (`NLSM_10K_Map.html`) submit formal academic/government request to GSI North Eastern Region (Shillong). |

---

## 4. Source C — ISRO / NRSC & NESAC

Live probe on `2026-11-23`:
- **`https://www.isro.gov.in/Landslide_Atlas_India.html` (`HTTP 200`):** Links exclusively to **`/media_isro/pdf/LandslideAtlas_new_2023.pdf`** — a **summary PDF publication** containing district-level susceptibility rankings and aggregate counts (1998–2022), **NOT machine-readable georeferenced event coordinates or landslide polygons**.
- **Bhuvan Disaster Services (`bhuvan-app1.nrsc.gov.in`):** DNS/network blocked from sandbox; externally provides WMS map browsing and requires Bhuvan registration / institutional data-sharing MoU with **NRSC (Hyderabad)** or **NESAC (Umiam, Shillong)** to obtain raw post-event satellite-mapped landslide polygon inventories (e.g., May 2022 and May 2024 Dima Hasao event inventories).
- **Strict Scientific Policy:** Aggregate statistics from the ISRO Landslide Atlas PDF were **NOT** transcribed into synthetic points.

---

## 5. Licensing & Citations

- **NASA COOLR:** Public domain / open NASA Earthdata resource. Cite: Kirschbaum, D., Stanley, T., & Zhou, Y. (2015), *Spatial and temporal analysis of a global landslide catalog*, Geomorphology 249, 4–15; Juang, C. S., Stanley, T. A., & Kirschbaum, D. B. (2019), *Using citizen science to expand the global map of landslides: Introducing the Cooperative Open Online Landslide Repository (COOLR)*, PLoS ONE 14(7).
- **GSI & ISRO/NRSC:** Government of India / National Data Sharing and Accessibility Policy (NDSAP) terms apply upon registration/institutional approval.
