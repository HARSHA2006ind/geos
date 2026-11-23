# GeoResilience-NER 2.0 — Full Headless Chromium UI & Mobile Validation

**Test Runner:** Playwright Headless Chromium (`chrome-headless-shell` 1247)  
**Target:** Unified Staging App (`http://127.0.0.1:3000`)  
**Viewports Tested:** Desktop (`1440x900`) and Mobile (`390x844`)

---

## 1. Defects Found & Fixed During Validation

1. **Stale Hardcoded GSI Count in Sidebar (`/src/components/layout/Sidebar.tsx`):**
   - *Finding:* Bottom status card still displayed `337 Recs` from an earlier milestone instead of the Stage 9 ingested polygon-filtered inventory.
   - *Fix:* Updated badge to **`379 In-Poly`** matching `/api/v1/landslides/gsi-bhusanket` (`379` records inside Dima Hasao boundary, `418` total ingested).
2. **Sign Out Auth-Mode Persistence Bug (`/src/pages/GeosV2WorkspacePage.tsx`):**
   - *Finding:* After claiming admin or registering (`authMode = 'claim' | 'register'`), clicking **Sign Out** left `authMode` on `'register'` (or `'claim'`) instead of returning to `'login'`.
   - *Fix:* Updated **Sign Out** and `refreshOperationalData()` to reset `authMode` cleanly to `'login'` once an admin exists.
3. **Silent Operational Fetch Failures & Refresh Race (`/src/pages/GeosV2WorkspacePage.tsx`):**
   - *Finding:* `refreshOperationalData()` swallowed partial network failures silently, and `workflowMsg` updated prior to `refreshOperationalData()` finishing after alert/report mutations.
   - *Fix:* Added explicit `opsError` banner with a **Retry Sync** button, and awaited `refreshOperationalData()` before displaying mutation confirmation messages.

---

## 2. Desktop Verification Matrix (`1440x900`)

| View / Flow | Result | Verified Details |
|---|---|---|
| **Command Center** | **PASS** | Renders cleanly; `scrollWidth <= innerWidth` (`overflow: false`). |
| **Risk Map (Leaflet GIS)** | **PASS** | `.leaflet-container` mounted cleanly; zero horizontal overflow. |
| **What-If, Impact, Field Reports, Alerts** | **PASS** | All legacy navigation routes render cleanly with `overflow: false`. |
| **Historical Analysis (`Dataset D`)** | **PASS** | Live `/api/v1/inventory/discovery` provider cards render; zero overflow. |
| **Sidebar Status Card** | **PASS** | Displays **`379 In-Poly`** for GSI Bhusanket and `Blocked (6)` for Production ML Gate. |
| **Hub Tab 1 — Hazard, Soil & Gemini** | **PASS** | **Jatinga** preset queries real DEM Horn slope, SoilGrids 2.0 clay (`0–5 cm`), IMERG (`2024-06-01`), NOAA GFS outlook, and OSM proximity; prompt-injection test blocked cleanly (`HTTP 400`) in UI. |
| **Hub Tab 2 — ML Gate & SHAP** | **PASS** | Displays `STRICTLY BLOCKED (6/13)`, 5-fold spatial-block RF/XGBoost table, corridor-bias leakage delta, Recharts SHAP chart, all 13 checks; `Test POST /api/v1/ml/infer` returns `unavailable_model_not_validated` (`landslide_probability: null`). |
| **Hub Tab 3 — Server What-If** | **PASS** | Executes `/api/v1/hazard/simulate`; renders IMD envelope + `Validated ML Probability: null` + `Factor of Safety: null`. |
| **Hub Tab 4 — Auth, RBAC & Photo Upload** | **PASS** | Claim Initial Admin (`admin`) -> Sign Out -> Register `field_officer` -> Upload real PNG + persist Field Report (`pending`) -> Uploaded photo returns **`HTTP 200`** -> Confirm `Verify` button hidden for `field_officer` -> Sign Out resets to `Sign In` -> Login `admin` -> `Verify` updates status to `verified`. |
| **Hub Tab 5 — Experimental Alerts** | **PASS** | Draft alert (`EXPERIMENTAL_RESEARCH_DRAFT`) -> `Approve Internal` (`approved_internal`) -> `Log Dry-Run Notification` -> `Dry-run audit entries: 1` verified in DOM & PostGIS. |
| **Hub Tab 6 — Monitoring & 8-State NER** | **PASS** | `Run Freshness Check` logs cycle (`2024-06-01` IMERG + live GFS init) and renders all 8 Northeast Indian states honestly. |

- **Uncaught `pageerror` count:** **`0`**
- **Unintended `console.error` / API failures:** **`0`** *(only intentional prompt-injection `POST /api/v1/assistant/explain -> HTTP 400` test recorded)*

---

## 3. Mobile Responsive Verification (`390x844`)

| Mobile Check (`390x844`) | Result | Horizontal Overflow (`scrollWidth > innerWidth`) |
|---|---|---|
| **Command Center** | **PASS** | `false` |
| **Mobile Navigation Drawer (`#header-mobile-menu-btn`)** | **PASS** | `false` |
| **GEOS 2.0 Hub Tab 1 (Hazard, Soil & Gemini)** | **PASS** | `false` |
| **GEOS 2.0 Hub Tab 2 (ML Gate & SHAP)** | **PASS** | `false` |
| **GEOS 2.0 Hub Tab 6 (Monitoring & 8-State NER)** | **PASS** | `false` |

- **Mobile `pageerror` count:** **`0`** | **`console.error`:** **`0`** | **Failed API requests:** **`0`**
- Temporary verification database rows and test PNG upload were cleaned up after completion so the staging PostGIS database remains clean (`users: 0` ready for first-run Admin Claim).
