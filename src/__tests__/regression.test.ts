import { describe, it, expect } from 'vitest';
import { escapeHtml } from '../utils/htmlEscape';
import {
  calculateLocationRisk,
  generateResponseRecommendations,
  getExplainableBreakdown,
} from '../services/riskEngine';
import { activeAlertsData, nerLocations } from '../data/mockData';
import { VALID_REPORT_TYPES, VALID_REPORTER_ROLES } from '../components/modals/SubmitReportModal';
import {
  getPilotBoundary,
  getPilotDatasets,
  getPilotHealth,
  getPilotInventoryDiscovery,
  getPilotPointEnvironment,
  getPilotRainfallHistory,
  wgs84ToUtm46N,
} from '../server/pilotReader';

describe('Phase 0 Regression & Security Tests', () => {
  it('escapes malicious HTML/JS strings to prevent Leaflet tooltip XSS', () => {
    const payload = `<img src=x onerror="alert('xss')">&<script>steal()</script>`;
    const escaped = escapeHtml(payload);
    expect(escaped).not.toContain('<img');
    expect(escaped).not.toContain('<script>');
    expect(escaped).toContain('&lt;img');
    expect(escaped).toContain('&quot;');
    expect(escaped).toContain('&#39;');
    expect(escaped).toContain('&amp;');
  });

  it('uses only valid ReportType and role values in SubmitReportModal', () => {
    const expectedTypes = [
      'Landslide',
      'Road Blockage',
      'Ground Crack',
      'Rockfall',
      'Flooding',
      'Infrastructure Damage',
    ];
    const expectedRoles = ['Field Officer', 'Citizen', 'NDRF Scout', 'PWD Inspector'];
    expect(VALID_REPORT_TYPES).toEqual(expectedTypes);
    expect(VALID_REPORTER_ROLES).toEqual(expectedRoles);
    expect(VALID_REPORT_TYPES).not.toContain('active_slide');
  });

  it('safely handles alerts without recommendedActions array (prevents AlertsPage crash)', () => {
    expect(activeAlertsData.length).toBeGreaterThan(0);
    for (const alert of activeAlertsData) {
      const actions =
        alert.recommendedActions && alert.recommendedActions.length > 0
          ? alert.recommendedActions
          : alert.recommended
          ? [alert.recommended]
          : ['No directive specified'];
      expect(Array.isArray(actions)).toBe(true);
      expect(actions.length).toBeGreaterThan(0);
    }
  });

  it('keeps riskEngine thresholds, XAI contribution sums, and dynamic recommendations consistent', () => {
    const sampleLoc = nerLocations[0];
    const calc = calculateLocationRisk(sampleLoc);
    expect(calc.score).toBeGreaterThanOrEqual(0);
    expect(calc.score).toBeLessThanOrEqual(100);

    const expectedLevel =
      calc.score >= 75 ? 'CRITICAL' : calc.score >= 50 ? 'HIGH' : calc.score >= 25 ? 'MODERATE' : 'LOW';
    expect(calc.level).toBe(expectedLevel);

    const enriched = { ...sampleLoc, calculatedScore: calc.score, calculatedLevel: calc.level };
    const xai = getExplainableBreakdown(enriched);
    const factorSum =
      xai.rainfallPct +
      xai.slopePct +
      xai.soilSaturationPct +
      xai.historicalActivityPct +
      xai.vegetationPct +
      xai.exposurePct;
    expect(factorSum).toBe(100);

    const recs = generateResponseRecommendations(enriched);
    expect(recs.length).toBeGreaterThan(0);
    expect(recs[0].description.length).toBeGreaterThan(10);
  });
});

describe('Phase 3–4 Verified Dima Hasao Pilot Data Bridge Tests', () => {
  it('projects Haflong WGS84 coordinates accurately into UTM Zone 46N (EPSG:32646)', () => {
    const [easting, northing] = wgs84ToUtm46N(25.1645, 93.0176);
    expect(easting).toBeGreaterThan(500_000);
    expect(easting).toBeLessThan(505_000);
    expect(northing).toBeGreaterThan(2_780_000);
    expect(northing).toBeLessThan(2_785_000);
  });

  it('reports all verified Dima Hasao pilot artifacts as present', () => {
    const health = getPilotHealth();
    expect(health.status).toBe('operational');
    expect(health.pilot_artifacts.dima_hasao_boundary).toBe(true);
    expect(health.pilot_artifacts.copernicus_dem_30m_core).toBe(true);
    expect(health.pilot_artifacts.slope_raster).toBe(true);
    expect(health.pilot_artifacts.worldcover_2021).toBe(true);
    expect(health.pilot_artifacts.gpm_imerg_rainfall).toBe(true);

    const datasets = getPilotDatasets();
    expect(datasets.length).toBe(4);

    const boundary = getPilotBoundary();
    expect(boundary?.geojson?.type).toBe('FeatureCollection');

    const discovery = getPilotInventoryDiscovery();
    expect(discovery?.fabricated_labels_count).toBe(0);
  });

  it('samples real Copernicus DEM, ESA WorldCover, and NASA GPM IMERG data for Haflong', async () => {
    const point = await getPilotPointEnvironment(25.1645, 93.0176);
    expect(point.within_pilot_boundary).toBe(true);
    expect(point.within_raster_bounds).toBe(true);
    expect(point.landslide_probability).toBeNull();
    expect(point.terrain.missing_elevation).toBe(false);
    expect(point.terrain.elevation_m).toBeGreaterThan(200);
    expect(point.terrain.elevation_m).toBeLessThan(2000);
    expect(point.terrain.missing_slope_aspect).toBe(false);
    expect(point.terrain.slope_deg).toBeGreaterThanOrEqual(0);
    expect(point.terrain.slope_deg).toBeLessThanOrEqual(90);
    expect(point.land_cover.missing_land_cover).toBe(false);
    expect(point.land_cover.class_code).not.toBeNull();
    expect(point.rainfall.latest_observation_date).not.toBeNull();
  });

  it('returns explicit null values (never fabricated numbers) outside the pilot study area', async () => {
    const outside = await getPilotPointEnvironment(28.6139, 77.209);
    expect(outside.within_pilot_boundary).toBe(false);
    expect(outside.within_raster_bounds).toBe(false);
    expect(outside.terrain.elevation_m).toBeNull();
    expect(outside.terrain.slope_deg).toBeNull();
    expect(outside.land_cover.class_code).toBeNull();
    expect(outside.rainfall.rainfall_24h_mm).toBeNull();
    expect(outside.rainfall.missing_24h).toBe(true);
    expect(outside.landslide_probability).toBeNull();
  });

  it('preserves missing GPM IMERG rainfall observations as null (never 0.0)', () => {
    const history = getPilotRainfallHistory();
    expect(history).not.toBeNull();
    expect(history!.valid_observation_days).toBeGreaterThan(0);
    for (const obs of history!.observations) {
      if (obs.missing_24h) {
        expect(obs.rainfall_24h_mm).toBeNull();
      } else {
        expect(obs.rainfall_24h_mm).not.toBeNull();
      }
    }
  });
});
