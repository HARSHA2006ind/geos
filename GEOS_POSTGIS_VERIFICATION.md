# GeoResilience-NER 2.0 — PostgreSQL & PostGIS Verification Report

**Database Engine:** PostgreSQL `15.20 (Debian 15.20-0+deb12u1)`  
**Spatial Extension:** `POSTGIS="3.3.2 4975da8" GEOS="3.11.1" PROJ="9.1.1"`  
**Execution Mode Disclosure:** `docker` is not installed in this sandbox container, so Docker Compose (`backend/docker-compose.yml`, which targets `postgis/postgis:16-3.4-alpine`) could not be executed live and was audited statically. Instead, real PostgreSQL 15 + PostGIS 3.3.2 was installed, started via `pg_ctl` on `127.0.0.1:5432` (role `geos`, DB `geos_ner`), and exercised end-to-end by Alembic, FastAPI (`uvicorn`), `sync_postgis.py`, `run_monitoring_cycle.py`, `psql`, and `pg_dump`/`restore_db.sh`.

---

## 1. Schema, Alembic Migrations & GiST Spatial Indexes

- **Alembic Full Roundtrip (`0001 -> 0003 -> base -> head`):** Exited `0` on live PostgreSQL + PostGIS.
- **Tables Verified (21 base tables):** 19 application tables (`dataset_registry`, `dataset_versions`, `study_areas`, `ingestion_jobs`, `rainfall_observations`, `landslide_events`, `landslide_event_evidence`, `infrastructure_assets`, `weather_forecasts`, `model_registry`, `validation_results`, `model_predictions`, `users`, `field_reports`, `experimental_alerts`, `monitoring_runs`, `regional_coverage`, `audit_logs`, `provenance_records`) + `alembic_version` + PostGIS `spatial_ref_sys`.
- **GiST Spatial Indexes Verified (5/5):**
  1. `idx_study_areas_geom` (`study_areas`)
  2. `idx_landslide_events_geom` (`landslide_events`)
  3. `idx_infrastructure_assets_geom` (`infrastructure_assets`)
  4. `idx_model_predictions_geom` (`model_predictions`)
  5. `idx_field_reports_geom` (`field_reports`)

---

## 2. Persisted Record Counts (`sync_postgis.py` + `run_monitoring_cycle.py`)

| Table | Verified Live Count | Notes |
|---|---|---|
| `study_areas` | `1` | `dima-hasao`, `ST_MultiPolygon`, `SRID=4326`, computed area `4884.61 km²` |
| `dataset_registry` | `9` | Full provenance metadata & licenses |
| `provenance_records` | `9` | SHA-256 artifact checksums verified |
| `rainfall_observations` | `3,653` | 10-year IMERG archive (`214` null gap days preserved strictly as `NULL`) |
| `landslide_events` | `522` | `418` GSI Bhusanket + `104` NASA COOLR (`POINT` geometries, `SRID=4326`) |
| `infrastructure_assets` | `3,218` | `619` OSM facilities (`POINT`) + `2,599` OSM transport segments (`LineString`) |
| `model_registry` | `2` | Exploratory RF & XGBoost (`validated_for_production=false`, `promoted_to_inference=false`) |
| `validation_results` | `2` | 5-fold Spatial-Block CV + SHAP attribution summaries |
| `weather_forecasts` | `3` | Live NOAA GFS `24h`, `48h`, `72h` horizons with distinct `valid_time_utc` |
| `monitoring_runs` | `1` | Recorded with `observed_rainfall_stale=true`, `forecast_stale=false` |
| `regional_coverage` | `8` | All 8 Northeast India states seeded |

---

## 3. Spatial Query Verification (`psql` Output)

1. **Polygon Geometry & Geodetic Area:**
   ```sql
   SELECT ST_GeometryType(geom), ST_SRID(geom), ROUND((ST_Area(geom::geography)/1000000.0)::numeric, 2) AS area_km2
   FROM study_areas WHERE slug = 'dima-hasao';
   -- Result: ST_MultiPolygon | 4326 | 4884.61
   ```
2. **Spatial Containment (`ST_Contains`) of GSI Landslide Events Inside Dima Hasao Boundary:**
   ```sql
   SELECT COUNT(*) FROM landslide_events le
   JOIN study_areas sa ON sa.slug = 'dima-hasao'
   WHERE le.source_provider = 'GSI_Bhusanket' AND ST_Contains(sa.geom, le.geom);
   -- Result: 379 records inside official district polygon
   ```
3. **5 km Geodetic Radius Buffer (`ST_DWithin`) Around Haflong (`25.1645°N, 93.0176°E`):**
   - `278` road segments, `35` bridges, `23` settlements, `20` railway segments, `17` schools, `7` hospitals/health facilities.
4. **GiST Spatial Index Execution (`EXPLAIN ANALYZE` with `enable_seqscan = off`):**
   - Bounding-box `geom && ST_MakeEnvelope(92.9, 25.0, 93.1, 25.3, 4326)` executed **`Bitmap Index Scan on idx_landslide_events_geom`** (`Execution Time: 0.507 ms`, `196` matching events).

---

## 4. Backup, Restore & Restart Persistence

- **Backup Execution:** `DATABASE_URL=postgresql+psycopg://geos:geos_dev_password@127.0.0.1:5432/geos_ner bash backend/scripts/backup_db.sh backend/data/backups` produced `geos_pg_20261123T133007Z.sql.gz` + `.sha256` checksum (`sha256sum -c`: `OK`).
- **Restore Integrity Check:** Restored dump into clean PostGIS-enabled `geos_ner_restore_test` database via `backend/scripts/restore_db.sh` and verified identical counts (`522` landslides, `3,218` infrastructure assets, `3,653` rainfall observations, `2` model records, `ST_MultiPolygon`) before dropping the temporary restore DB.
- **Restart Persistence:** Restarted PostgreSQL (`pg_ctl restart`) and restarted full Node+FastAPI stack (`restart_dev_server`); persisted spatial tables, monitoring runs, weather forecasts, field reports, and alerts remained intact.
