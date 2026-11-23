/**
 * Read-only Node.js reader for the verified real pilot geospatial artifacts
 * stored in backend/data/pilot/ (Copernicus DEM GLO-30, Horn slope/aspect,
 * ESA WorldCover 2021 v200, NASA GPM IMERG rainfall, OSM Dima Hasao boundary).
 *
 * Used by server.ts only when FASTAPI_BACKEND_URL is not running separately,
 * guaranteeing that /api/v1/* returns identical verified observations from
 * the exact same GeoTIFF and JSON files with zero fabricated data.
 */
import fs from 'fs';
import path from 'path';
import { fromFile, GeoTIFFImage } from 'geotiff';

const WORLDCOVER_CLASSES: Record<number, string> = {
  10: 'Tree cover',
  20: 'Shrubland',
  30: 'Grassland',
  40: 'Cropland',
  50: 'Built-up',
  60: 'Bare / sparse vegetation',
  70: 'Snow and ice',
  80: 'Permanent water bodies',
  90: 'Herbaceous wetland',
  95: 'Mangroves',
  100: 'Moss and lichen',
};

const PILOT_DIR = path.resolve(process.cwd(), 'backend', 'data', 'pilot');

function readJsonIfExists(filename: string): any | null {
  const fullPath = path.join(PILOT_DIR, filename);
  if (!fs.existsSync(fullPath)) return null;
  return JSON.parse(fs.readFileSync(fullPath, 'utf-8'));
}

/**
 * Exact WGS84 (EPSG:4326) -> UTM Zone 46N (EPSG:32646, central meridian 93°E) forward projection.
 */
export function wgs84ToUtm46N(latDeg: number, lonDeg: number): [number, number] {
  const a = 6378137.0;
  const f = 1 / 298.257223563;
  const e2 = f * (2 - f);
  const ePrime2 = e2 / (1 - e2);
  const k0 = 0.9996;
  const lon0 = (93.0 * Math.PI) / 180.0;

  const lat = (latDeg * Math.PI) / 180.0;
  const lon = (lonDeg * Math.PI) / 180.0;

  const sinLat = Math.sin(lat);
  const cosLat = Math.cos(lat);
  const tanLat = Math.tan(lat);

  const N = a / Math.sqrt(1 - e2 * sinLat * sinLat);
  const T = tanLat * tanLat;
  const C = ePrime2 * cosLat * cosLat;
  const A = cosLat * (lon - lon0);

  const M =
    a *
    ((1 - e2 / 4 - (3 * e2 * e2) / 64 - (5 * e2 * e2 * e2) / 256) * lat -
      ((3 * e2) / 8 + (3 * e2 * e2) / 32 + (45 * e2 * e2 * e2) / 1024) * Math.sin(2 * lat) +
      ((15 * e2 * e2) / 256 + (45 * e2 * e2 * e2) / 1024) * Math.sin(4 * lat) -
      ((35 * e2 * e2 * e2) / 3072) * Math.sin(6 * lat));

  const easting =
    k0 *
      N *
      (A +
        ((1 - T + C) * Math.pow(A, 3)) / 6 +
        ((5 - 18 * T + T * T + 72 * C - 58 * ePrime2) * Math.pow(A, 5)) / 120) +
    500000.0;

  const northing =
    k0 *
    (M +
      N *
        tanLat *
        ((A * A) / 2 +
          ((5 - T + 9 * C + 4 * C * C) * Math.pow(A, 4)) / 24 +
          ((61 - 58 * T + T * T + 600 * C - 330 * ePrime2) * Math.pow(A, 6)) / 720));

  return [easting, northing];
}

function pointInRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersect = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi) + xi;
    if (intersect) inside = !inside;
  }
  return inside;
}

function pointInPolygon(lon: number, lat: number, rings: number[][][]): boolean {
  if (!rings.length || !pointInRing(lon, lat, rings[0])) return false;
  for (let i = 1; i < rings.length; i++) {
    if (pointInRing(lon, lat, rings[i])) return false;
  }
  return true;
}

function isPointInsideBoundary(lat: number, lon: number, boundaryDoc: any): boolean {
  const geom = boundaryDoc?.features?.[0]?.geometry;
  if (!geom) return false;
  if (geom.type === 'Polygon') {
    return pointInPolygon(lon, lat, geom.coordinates);
  }
  if (geom.type === 'MultiPolygon') {
    return geom.coordinates.some((poly: number[][][]) => pointInPolygon(lon, lat, poly));
  }
  return false;
}

function aspectToCardinal(deg: number | null): string | null {
  if (deg === null || deg < 0) return null;
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.floor(((deg + 22.5) % 360) / 45)];
}

const imageCache = new Map<string, GeoTIFFImage>();

async function sampleGeoTiff(filename: string, x: number, y: number): Promise<number | null> {
  const fullPath = path.join(PILOT_DIR, filename);
  if (!fs.existsSync(fullPath)) return null;

  let image = imageCache.get(fullPath);
  if (!image) {
    const tiff = await fromFile(fullPath);
    image = await tiff.getImage();
    imageCache.set(fullPath, image);
  }

  const bbox = image.getBoundingBox(); // [minX, minY, maxX, maxY]
  if (x < bbox[0] || x > bbox[2] || y < bbox[1] || y > bbox[3]) {
    return null;
  }

  const width = image.getWidth();
  const height = image.getHeight();
  const col = Math.floor(((x - bbox[0]) / (bbox[2] - bbox[0])) * width);
  const row = Math.floor(((bbox[3] - y) / (bbox[3] - bbox[1])) * height);

  if (col < 0 || col >= width || row < 0 || row >= height) return null;

  const rasters = await image.readRasters({ window: [col, row, col + 1, row + 1] });
  const band = rasters[0] as ArrayLike<number>;
  const val = Number(band[0]);
  const nodata = image.getGDALNoData();

  if (!Number.isFinite(val)) return null;
  if (nodata !== null && Math.abs(val - nodata) < 1e-5) return null;
  return val;
}

export function getPilotHealth() {
  const artifacts = {
    dima_hasao_boundary: fs.existsSync(path.join(PILOT_DIR, 'dima_hasao_boundary.geojson')),
    copernicus_dem_30m_core: fs.existsSync(path.join(PILOT_DIR, 'haflong_jatinga_copernicus_dem_30m.tif')),
    copernicus_dem_district: fs.existsSync(path.join(PILOT_DIR, 'dima_hasao_dem_utm46n.tif')),
    slope_raster: fs.existsSync(path.join(PILOT_DIR, 'dima_hasao_slope_deg_utm46n.tif')),
    aspect_raster: fs.existsSync(path.join(PILOT_DIR, 'dima_hasao_aspect_deg_utm46n.tif')),
    worldcover_2021: fs.existsSync(path.join(PILOT_DIR, 'dima_hasao_worldcover_2021_utm46n.tif')),
    gpm_imerg_rainfall: fs.existsSync(path.join(PILOT_DIR, 'dima_hasao_rainfall_imerg.json')),
    landslide_inventory_discovery: fs.existsSync(path.join(PILOT_DIR, 'landslide_inventory_discovery.json')),
  };
  const allPresent = Object.values(artifacts).every(Boolean);
  return {
    status: allPresent ? 'operational' : 'degraded_missing_artifacts',
    service: 'GeoResilience-NER 2.0 Verified Artifact Bridge',
    version: '2.0.0-alpha.1',
    timestamp_utc: new Date().toISOString(),
    database: {
      connected: false,
      dialect: 'file-artifact-bridge',
      postgis_version: null,
    },
    pilot_artifacts: artifacts,
    ml_model_status: 'not_trained_phase_1_data_foundation',
  };
}

export function getPilotDatasets() {
  const items: any[] = [];
  const boundary = readJsonIfExists('dima_hasao_boundary.geojson');
  if (boundary?.metadata) {
    const bm = boundary.metadata;
    items.push({
      dataset_id: 'osm-dima-hasao-boundary',
      name: bm.dataset_name,
      category: 'administrative_boundary',
      product_version: `OSM ${bm.osm_type || 'relation'}/${bm.osm_id || 'unknown'}`,
      crs: bm.crs,
      resolution_m: null,
      observation_period: 'Current OSM snapshot',
      processing_timestamp: bm.processing_timestamp || null,
      available: true,
      requires_credentials: false,
      source_url: bm.source_url,
      attribution: bm.attribution,
      limitations: bm.limitations || null,
    });
  }

  const dem = readJsonIfExists('copernicus_dem_metadata.json');
  if (dem) {
    items.push({
      dataset_id: dem.dataset_id,
      name: dem.dataset_name,
      category: 'elevation_and_terrain',
      product_version: dem.product_version,
      crs: dem.derived_metric_crs,
      resolution_m: dem.native_resolution_m,
      observation_period: dem.observation_period,
      processing_timestamp: dem.processing_timestamp || null,
      available: fs.existsSync(path.join(PILOT_DIR, dem.district_dem_file)),
      requires_credentials: false,
      source_url: dem.source_tiles?.[0]?.url || '',
      attribution: dem.attribution,
      limitations: dem.limitations || null,
    });
  }

  const rain = readJsonIfExists('dima_hasao_rainfall_imerg.json');
  if (rain?.dataset_id) {
    items.push({
      dataset_id: rain.dataset_id,
      name: rain.dataset_name,
      category: 'precipitation',
      product_version: rain.product_version,
      crs: 'EPSG:4326',
      resolution_m: Math.round((rain.spatial_resolution_deg || 0.1) * 111000 * 10) / 10,
      observation_period: `${rain.interval_start} to ${rain.interval_end}`,
      processing_timestamp: rain.processing_timestamp || null,
      available: true,
      requires_credentials: false,
      source_url: rain.source_url,
      attribution: rain.attribution,
      limitations: rain.missing_data_policy || null,
    });
  }

  const wc = readJsonIfExists('worldcover_metadata.json');
  if (wc) {
    items.push({
      dataset_id: wc.dataset_id,
      name: wc.dataset_name,
      category: 'land_cover',
      product_version: wc.product_version,
      crs: wc.exported_crs,
      resolution_m: wc.native_resolution_m,
      observation_period: wc.observation_period,
      processing_timestamp: wc.processing_timestamp || null,
      available: fs.existsSync(path.join(PILOT_DIR, wc.raster_file)),
      requires_credentials: false,
      source_url: wc.source_tiles?.[0]?.url || '',
      attribution: wc.attribution,
      limitations: wc.uncertainty_and_limitations || null,
    });
  }
  return items;
}

export function getPilotBoundary() {
  const geojson = readJsonIfExists('dima_hasao_boundary.geojson');
  if (!geojson) return null;
  return {
    geojson,
    terrain_summary: readJsonIfExists('copernicus_dem_metadata.json'),
    land_cover_summary: readJsonIfExists('worldcover_metadata.json'),
  };
}

export function getPilotRainfallHistory(startDate?: string, endDate?: string) {
  const doc = readJsonIfExists('dima_hasao_rainfall_imerg.json');
  if (!doc?.dataset_id) return null;
  let records: any[] = doc.observations || [];
  if (startDate) records = records.filter((r) => r.date >= startDate);
  if (endDate) records = records.filter((r) => r.date <= endDate);

  const valid24 = records.filter((r) => r.rainfall_24h_mm !== null).map((r) => r.rainfall_24h_mm);
  const valid72 = records.filter((r) => r.rainfall_72h_mm !== null).map((r) => r.rainfall_72h_mm);

  return {
    study_area: doc.study_area,
    dataset_id: doc.dataset_id,
    dataset_name: doc.dataset_name,
    product_version: doc.product_version,
    spatial_resolution_deg: doc.spatial_resolution_deg,
    latency_info: doc.latency_info,
    interval_start: records[0]?.date || doc.interval_start,
    interval_end: records[records.length - 1]?.date || doc.interval_end,
    total_days: records.length,
    valid_observation_days: valid24.length,
    missing_observation_days: records.length - valid24.length,
    max_24h_mm: valid24.length ? Math.max(...valid24) : null,
    max_72h_mm: valid72.length ? Math.max(...valid72) : null,
    missing_data_policy: doc.missing_data_policy,
    processing_timestamp: doc.processing_timestamp,
    attribution: doc.attribution,
    source_url: doc.source_url,
    observations: records,
  };
}

export function getPilotInventoryDiscovery() {
  return readJsonIfExists('landslide_inventory_discovery.json');
}

export async function getPilotPointEnvironment(lat: number, lon: number) {
  const boundaryDoc = readJsonIfExists('dima_hasao_boundary.geojson');
  const demMeta = readJsonIfExists('copernicus_dem_metadata.json');
  const wcMeta = readJsonIfExists('worldcover_metadata.json');
  const rainDoc = readJsonIfExists('dima_hasao_rainfall_imerg.json');

  const withinBoundary = boundaryDoc ? isPointInsideBoundary(lat, lon, boundaryDoc) : false;
  const [utmX, utmY] = wgs84ToUtm46N(lat, lon);

  // Sample elevation: prefer native 30m Haflong-Jatinga corridor (EPSG:4326), fallback to district UTM46N
  let elev = await sampleGeoTiff('haflong_jatinga_copernicus_dem_30m.tif', lon, lat);
  let elevRes: number | null = elev !== null ? 30.0 : null;
  if (elev === null) {
    elev = await sampleGeoTiff('dima_hasao_dem_utm46n.tif', utmX, utmY);
    if (elev !== null) elevRes = demMeta?.district_raster_resolution_m ?? 90.0;
  }

  const slope = await sampleGeoTiff('dima_hasao_slope_deg_utm46n.tif', utmX, utmY);
  const aspectRaw = await sampleGeoTiff('dima_hasao_aspect_deg_utm46n.tif', utmX, utmY);
  const aspect = aspectRaw !== null && aspectRaw >= 0 ? Math.round(aspectRaw * 100) / 100 : null;

  const wcRaw = await sampleGeoTiff('dima_hasao_worldcover_2021_utm46n.tif', utmX, utmY);
  const wcCode = wcRaw !== null && wcRaw > 0 ? Math.round(wcRaw) : null;
  const wcLabel = wcCode !== null ? WORLDCOVER_CLASSES[wcCode] || `Unknown (${wcCode})` : null;

  const withinRaster = elev !== null || slope !== null || wcCode !== null;

  const demProv = demMeta
    ? {
        dataset_id: demMeta.dataset_id,
        dataset_name: demMeta.dataset_name,
        product_version: demMeta.product_version,
        source_url: demMeta.source_tiles?.[0]?.url || '',
        crs: demMeta.derived_metric_crs,
        resolution_m: elevRes ?? demMeta.native_resolution_m,
        observation_period: demMeta.observation_period,
        processing_timestamp: demMeta.processing_timestamp || null,
        attribution: demMeta.attribution,
        limitations: demMeta.limitations || null,
      }
    : null;

  const wcProv = wcMeta
    ? {
        dataset_id: wcMeta.dataset_id,
        dataset_name: wcMeta.dataset_name,
        product_version: wcMeta.product_version,
        source_url: wcMeta.source_tiles?.[0]?.url || '',
        crs: wcMeta.exported_crs,
        resolution_m: wcMeta.native_resolution_m,
        observation_period: wcMeta.observation_period,
        processing_timestamp: wcMeta.processing_timestamp || null,
        attribution: wcMeta.attribution,
        limitations: wcMeta.uncertainty_and_limitations || null,
      }
    : null;

  const rainProv = rainDoc?.dataset_id
    ? {
        dataset_id: rainDoc.dataset_id,
        dataset_name: rainDoc.dataset_name,
        product_version: rainDoc.product_version,
        source_url: rainDoc.source_url,
        crs: 'EPSG:4326',
        resolution_m: Math.round((rainDoc.spatial_resolution_deg || 0.1) * 111000 * 10) / 10,
        observation_period: `${rainDoc.interval_start} to ${rainDoc.interval_end}`,
        processing_timestamp: rainDoc.processing_timestamp || null,
        attribution: rainDoc.attribution,
        limitations: rainDoc.missing_data_policy || null,
      }
    : null;

  let rainfall: any = {
    latest_observation_date: null,
    latest_observation_timestamp_utc: null,
    rainfall_24h_mm: null,
    rainfall_72h_mm: null,
    max_24h_in_window_mm: null,
    max_72h_in_window_mm: null,
    window_start: rainDoc?.interval_start || null,
    window_end: rainDoc?.interval_end || null,
    valid_days_in_window: 0,
    missing_days_in_window: 0,
    missing_24h: true,
    missing_72h: true,
    latency_info: rainDoc?.latency_info || null,
    provenance: rainProv,
  };

  if ((withinBoundary || withinRaster) && rainDoc?.dataset_id) {
    const latest = rainDoc.latest_valid_observation;
    rainfall = {
      latest_observation_date: latest?.date ?? null,
      latest_observation_timestamp_utc: latest?.observation_timestamp_utc ?? null,
      rainfall_24h_mm: latest?.rainfall_24h_mm ?? null,
      rainfall_72h_mm: latest?.rainfall_72h_mm ?? null,
      max_24h_in_window_mm: rainDoc.max_24h_mm ?? null,
      max_72h_in_window_mm: rainDoc.max_72h_mm ?? null,
      window_start: rainDoc.interval_start,
      window_end: rainDoc.interval_end,
      valid_days_in_window: rainDoc.valid_observation_days,
      missing_days_in_window: rainDoc.missing_observation_days,
      missing_24h: latest ? Boolean(latest.missing_24h) : true,
      missing_72h: latest ? Boolean(latest.missing_72h) : true,
      latency_info: rainDoc.latency_info,
      provenance: rainProv,
    };
  }

  const missingElevation = elev === null;
  const missingSlopeAspect = slope === null;
  const missingLandCover = wcCode === null;

  return {
    coordinates: {
      lat: Math.round(lat * 1e6) / 1e6,
      lon: Math.round(lon * 1e6) / 1e6,
    },
    crs: 'EPSG:4326',
    study_area: 'Dima Hasao District, Assam (Pilot)',
    within_pilot_boundary: withinBoundary,
    within_raster_bounds: withinRaster,
    scientific_disclaimer:
      'Verified environmental observations only. No landslide susceptibility or failure probability is generated because no spatially validated ML model is deployed yet.',
    landslide_probability: null,
    terrain: {
      elevation_m: elev !== null ? Math.round(elev * 100) / 100 : null,
      elevation_resolution_m: elevRes,
      slope_deg: slope !== null ? Math.round(slope * 100) / 100 : null,
      aspect_deg: aspect,
      aspect_cardinal: aspectToCardinal(aspect),
      slope_aspect_resolution_m: slope !== null ? (demMeta?.district_raster_resolution_m ?? 90.0) : null,
      missing_elevation: missingElevation,
      missing_slope_aspect: missingSlopeAspect,
      provenance: demProv,
    },
    land_cover: {
      class_code: wcCode,
      class_label: wcLabel,
      missing_land_cover: missingLandCover,
      provenance: wcProv,
    },
    rainfall,
    missing_data_indicators: {
      elevation: missingElevation,
      slope_and_aspect: missingSlopeAspect,
      land_cover: missingLandCover,
      rainfall_24h: rainfall.missing_24h,
      rainfall_72h: rainfall.missing_72h,
      landslide_ml_probability: true,
      factor_of_safety: true,
    },
    response_generated_at_utc: new Date().toISOString(),
  };
}
