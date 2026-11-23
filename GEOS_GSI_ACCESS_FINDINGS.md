# GeoResilience-NER 2.0 — GSI, NGDR, Bhukosh, Bhusanket & Regional Agency Access Findings (Stage 9)

**Investigation Date (UTC):** 2026-11-23  
**Study Area:** Dima Hasao District (formerly North Cachar Hills), Assam, India

---

## 1. Live Portal & API Access Audit Matrix

All portals were investigated using standard, authorized read-only HTTP requests (zero authentication bypasses, zero token scraping, zero unauthorized extraction):

| Portal / Agency | Probed Endpoints | Observed Result | Publicly Accessible Data | Access Barrier / Restriction |
| :--- | :--- | :--- | :--- | :--- |
| **GSI Bhusanket (NLFC Public Portal)** | `https://bhusanket.gsi.gov.in/`<br>`/ArcGis_Api_Integration/LandslideControllerA/GetData`<br>`/json/NLSM_10K_Map.json`<br>`/json/LandslideReport/LandslideReport.json`<br>`/json/config.json` | **HTTP 200 (Authorized Public Portal)** | **418 official GSI landslide point records** for `Assam` (`Dima Hasao` + `Dima Hasao (N.C. Hills)`), **379 inside exact Dima Hasao OSM polygon**, **5 Meso-scale 1:10,000 NLSM Susceptibility Map PDFs**, and state-wise GSI field report citations. | Public table returns **point centroids & tabular dimensions only**. Daily forecasting bulletins (`filterdistrict`) currently cover only 4 NLFC pilot districts (Darjeeling, Kalimpong, The Nilgiris, Rudraprayag) — **not yet Dima Hasao**. |
| **GSI Bhusanket ArcGIS GIS Layers** | `.../gisserver/rest/services/GSI/Landslide_Polygon/FeatureServer`<br>`.../Hosted/India_All_Landslided/FeatureServer/0`<br>`.../GSI/Susceptibility/ImageServer` | **HTTP 200 with ArcGIS JSON Error 499 (`Token Required`)** | Only `Bulletin_NDEM/MapServer` metadata is public. | **Observed landslide polygons** (`GSI/Landslide_Polygon`) and national GIS vector/raster layers require an authorized GSI ArcGIS Enterprise token. |
| **NGDR (National Geoscience Data Repository)** | `https://ngdr.gsi.gov.in/`<br>`https://ngdr.gov.in/`<br>`https://geodataindia.gov.in/` | `ngdr.gsi.gov.in` / `ngdr.gov.in`: DNS `Name or service not known`;<br>`geodataindia.gov.in`: `Connection refused` from non-India cloud container | Official Ministry of Mines portal hosting 1:50k lithology, structural faults, and NLSM baseline layers. | Requires browser access from Indian network / institutional registration & login on `https://geodataindia.gov.in/`. |
| **GSI Bhukosh** | `https://bhukosh.gsi.gov.in/` | `ConnectTimeout` from cloud container | Interactive GSI map viewer for geology, lineaments/faults, and NLSM susceptibility maps. | Geo-restricted / interactive portal session + user registration required to export shapefiles/GeoJSON. |
| **NESAC (NESDR / NERDRR)** | `https://nesdr.gov.in/`<br>`https://nerdrr.gov.in/` | **HTTP 403 Forbidden** | Regional Northeast India seasonal landslide maps & Lumding–Badarpur corridor archives. | WAF/geo-restriction and institutional stakeholder registration required. |
| **NRSC Bhoonidhi / Bhuvan** | `https://bhoonidhi.nrsc.gov.in/` | DNS failure from cloud container | Multi-temporal Resourcesat/Cartosat event landslide inventories (incl. May 2022 & May 2024). | Requires Bhoonidhi / Bhuvan registered researcher credentials & formal request. |
| **Data.gov.in (OGD India)** | `https://data.gov.in/`<br>`https://www.data.gov.in/` | `Connection refused` / `HTTP 503` (Akamai WAF) | Open government tabular datasets. | WAF blocks automated cloud container egress; requires browser access & registered API key. |

---

## 2. Authentic GSI Bhusanket Public Inventory Ingested for Dima Hasao

Using the official public Bhusanket portal API (`backend/ingestion/fetch_gsi_bhusanket_inventory.py`), we ingested and audited the complete public GSI Dima Hasao dataset into:
- Verbatim raw archive: `backend/data/pilot/gsi_bhusanket_dima_hasao_raw.json`
- Curated & audited dataset: `backend/data/pilot/dima_hasao_landslides_gsi_bhusanket.json`

### Quantitative Audit Summary (Dima Hasao District)

| Metric | Verified Count | Scientific Interpretation |
| :--- | :---: | :--- |
| Total raw GSI records (`Dima Hasao` + `Dima Hasao (N.C. Hills)`) | **418** | Zero exact `OBJECTID` duplicates; zero invalid WGS84 coordinates. |
| Records inside exact OSM Dima Hasao polygon | **379** | 39 valid coordinates fall just outside the OSM border (likely Survey of India vs OSM district boundary offset). |
| Source breakdown (in-polygon) | **185 Macro-Scale**, **152 PDLS**, **36 LEWS**, **6 Mobile app** | Combines 1:50k NLSM mapping (`Macro-Scale`), GSI geologist Post-Disaster Landslide Studies (`PDLS`), LEWS archive, and Bhooskhalan mobile submissions. |
| Temporal coverage (years represented) | **1998–2026** (incl. **51 in 2022**, **15 in 2024**, **3 in 2025**, **1 in 2026**) | Captures catastrophic May 2022 & 2024 episodes — a major leap beyond NASA COOLR (which ended in 2018). |
| Exact day-level dates (in-polygon) | **95 / 379 (25.1%)** | Remaining records: `19` month-only, `103` year-only, `162` undated (`unknown`). Undated records cannot be paired with antecedent daily rainfall! |
| Day-level dates overlapping valid 2015–2024-06-01 IMERG | **85** (across 17 5-km blocks) | Post-2021 (after WorldCover 2021) IMERG-overlapping day-level events = **45**, ALL concentrated in **7 dates of a single year (2022)** across only **7 5-km blocks**. |
| Records with field geology & area (`Area_In_Sq_Meters`) | **365 / 379 (96.3%)** | Rich site-level geological notes (e.g., weathered Barail/Renji sandstone & carbonaceous shale), but NOT wall-to-wall district lithology polygons. |
| **Spatial near-duplicate pairs (`<= 50 m`)** | **81 pairs** | Chronic recurring slides along NH-27 & Lumding–Badarpur railway appear across multiple surveys (`Macro-Scale` + `PDLS` + `LEWS`). |
| **Transport-corridor sampling bias** | **295 / 379 (77.8%)** | Text/attribute audit confirms 77.8% of records explicitly reference NH/SH highways, roads, bridges, tunnels, or railway tracks. |
| **Coordinate precision tiers** | **285 (`>= 4 dp`)**, **47 (`3 dp` ~110 m)**, **47 (`<= 2 dp` >1 km)** | **Zero records** include an explicit horizontal GPS error radius column (`explicit_error_radius_reported: false`). |

---

## 3. Strict Separation: Susceptibility Maps vs Observed Event Polygons

Per strict geospatial ML methodology, **NLSM susceptibility maps are NEVER used as ground-truth landslide labels** (using a susceptibility map to train a susceptibility model is circular target leakage).

The 5 official GSI Meso-Scale (1:10,000) NLSM Susceptibility Maps discovered for Dima Hasao on Bhusanket (`NLSM_10K_Map.json`) are stored strictly as **reference susceptibility documents**, separate from observed event records:
1. *Meso-scale (1:10,000) Landslide susceptibility mapping along NH 54E, from Retzawl to Doliyadisa in Dima Hasao of Assam.*
2. *Meso-scale (1:10,000) landslide susceptibility mapping from Phaiding to Jorai Batan in Dima Hasao of Assam.*
3. *Meso-scale (1:10,000) landslide susceptibility mapping from Jorai Batan to Retzawl in Dima Hasao of Assam.*
4. *Meso-scale (1:10,000) Landslide susceptibility mapping in northern part of Haflong, Dima Hasao of Assam.*
5. *Meso-scale (1:10,000) Landslide susceptibility mapping in southern part of Haflong, Dima Hasao of Assam.*

---

## 4. Exact Portal Registration & Download Steps (From an Authorized Machine in India)

### A. National Geoscience Data Repository (NGDR — `https://geodataindia.gov.in/`)
1. Open `https://geodataindia.gov.in/` in a browser from an Indian institutional/research network.
2. Click **Sign Up / Register** using an institutional email address and complete mobile/email OTP verification.
3. Navigate to **Data Explorer -> Baseline Geoscience Data -> Geology (1:50,000)** and **Geohazards -> Landslide Inventory / NLSM**.
4. Apply spatial filter: **State = Assam**, **District = Dima Hasao** (and Toposheets `83C`, `83G`: specifically `83C/13–16`, `83G/01–04`, `83G/05–08`).
5. Download in Shapefile/GeoJSON format:
   - 1:50,000 Lithology polygons (Disang, Barail/Laisong/Jenam/Renji, Surma, Tipam formations)
   - 1:50,000 Structural lineaments & thrust faults (Haflong Thrust, Disang Thrust, Dauki/Kopili fault zone)
   - Verified observed landslide initiation/depletion polygons (`GSI_Landslide_Polygons`) — strictly distinct from NLSM susceptibility zone polygons.

### B. GSI Bhukosh (`https://bhukosh.gsi.gov.in/`)
1. Register/Sign in at `https://bhukosh.gsi.gov.in/`.
2. Open **Map Viewer -> Layer Catalogue -> Geohazard -> Landslide Inventory** and **Geology -> Lithology (50K) / Faults (50K)**.
3. Draw/select **Dima Hasao District** bounding extent and submit an authorized **Data Download Request** for Shapefile/GeoPackage export.

---

## 5. Formal Institutional Data Request Letter Draft (GSI / NRSC / NESAC)

> **Subject:** Academic & Disaster-Management Research Data Request — Field-Validated Landslide Polygons, 1:50k Lithology/Faults & Event Inventories for Dima Hasao District, Assam (SIH26001 / GeoResilience-NER 2.0)
>
> **To:**  
> 1. The Deputy Director General / Head of Mission-IV (Geohazards), **Geological Survey of India (GSI), North Eastern Region (NER), Shillong** & **National Landslide Forecasting Centre (NLFC), Kolkata**  
> 2. The Group Director (Geosciences / Disaster Management Support), **National Remote Sensing Centre (NRSC), ISRO, Hyderabad**  
> 3. The Director, **North Eastern Space Applications Centre (NESAC), Umiam, Meghalaya**
>
> **Respected Sir / Madam,**
>
> We are developing an open, reproducible scientific landslide susceptibility and early-warning research platform (**GeoResilience-NER 2.0**) focused initially on a pilot study of **Dima Hasao District, Assam** (Haflong–Jatinga–Maibang–Harangajao hill corridor and surrounding Barail Range watersheds), under Smart India Hackathon Problem Statement **SIH26001**.
>
> Using publicly accessible datasets (Copernicus DEM GLO-30, ESA WorldCover 2021, ISRIC SoilGrids 2.0, Copernicus Sentinel-2 L2A, NASA GPM IMERG, and the public tabular records on the GSI Bhusanket Portal), we have established a fully audited geospatial baseline. However, our automated Scientific Data Quality Gate has intentionally **blocked ML model training** because publicly available point tables lack verified scar/runout polygons, certified horizontal GPS uncertainty, complete event-date coverage across multiple monsoon seasons (especially May 2022 and May 2024 Cyclone Remal events), and wall-to-wall 1:50,000 geological/structural vector layers.
>
> We respectfully request authorized academic/research access to the following datasets for **Dima Hasao District, Assam** (bounding box `92.52°E–93.47°E, 24.97°N–25.83°N`):
> 1. **From GSI (NER Shillong / NLFC Kolkata):**
>    - Observed landslide event polygons (`GSI/Landslide_Polygon`) with field-verified event dates (2015–2025, specifically including May 2022 and May 2024 post-disaster inventories), initiation point vs runout delineation, and positional accuracy metadata.
>    - 1:50,000 Geological (Lithology) polygons and Structural Fault / Thrust lineaments (Haflong Thrust, Disang Thrust, and Barail/Disang/Surma formation contacts) in Shapefile/GeoPackage format.
>    - Access to the Meso-scale (1:10,000) NLSM susceptibility maps strictly as an **independent validation benchmark** (never as ML training labels).
> 2. **From NRSC (ISRO Bhuvan / Bhoonidhi) & NESAC (NESDR / NERDRR):**
>    - Multi-temporal satellite-mapped landslide event polygons (Cartosat / Resourcesat / Sentinel-2 pre- and post-event mapping) covering forested interior slopes beyond road/railway corridors for the 2017, 2022, and 2024 monsoon seasons, to mitigate transport-corridor sampling bias.
> 3. **Data Governance Commitment:** All datasets will be used strictly for non-commercial scientific research and disaster-resilience engineering, stored securely with full institutional attribution, never redistributed without written permission, and no unvalidated operational warning will be issued to the public.
>
> Thank you for your guidance and support toward evidence-based disaster risk reduction in Northeast India.
>
> **Sincerely,**  
> *[Research Team Name / Institution / Faculty Supervisor / Contact Email & Phone]*
