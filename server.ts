import express from 'express';
import fs from 'fs';
import http from 'http';
import https from 'https';
import path from 'path';
import { GoogleGenAI } from '@google/genai';
import dotenv from 'dotenv';
import { z } from 'zod';
import {
  getPilotBoundary,
  getPilotDatasets,
  getPilotHealth,
  getPilotInventoryDiscovery,
  getPilotPointEnvironment,
  getPilotRainfallHistory,
} from './src/server/pilotReader';

dotenv.config();

const fastApiHttpAgent = new http.Agent({ keepAlive: true, maxSockets: 64, keepAliveMsecs: 30_000 });
const fastApiHttpsAgent = new https.Agent({ keepAlive: true, maxSockets: 64, keepAliveMsecs: 30_000 });

// Valid, currently supported default Gemini model alias (configurable via GEMINI_MODEL)
const DEFAULT_GEMINI_MODEL = 'gemini-4-hydrogen';

// Zod request validation schemas
const ExplainLocationSchema = z.object({
  location: z.object({
    name: z.string().min(1).max(160),
    state: z.string().min(1).max(80),
    district: z.string().min(1).max(120),
    calculatedScore: z.number().min(0).max(100),
    calculatedLevel: z.enum(['LOW', 'MODERATE', 'HIGH', 'CRITICAL']),
    currentRainfall: z.number().min(0).max(2000),
    slope: z.number().min(0).max(90),
    elevation: z.number().min(-500).max(9000),
    soilType: z.string().max(160).optional().default('Unspecified'),
    soilSaturation: z.number().min(0).max(100),
    historicalActivity: z.number().min(0).max(100),
    populationExposed: z.number().min(0).max(10_000_000),
    infrastructure: z.object({
      roads: z.number().min(0),
      bridges: z.number().min(0),
      hospitals: z.number().min(0),
      schools: z.number().min(0),
      keyHighways: z.array(z.string().max(120)).max(20).optional().default([]),
    }),
  }),
  simulated: z.boolean().optional().default(false),
});

const WhatIfBriefingSchema = z.object({
  summary: z.object({
    currentCritical: z.number().int().min(0),
    simulatedCritical: z.number().int().min(0),
    diffCritical: z.number().int(),
    currentHigh: z.number().int().min(0),
    simulatedHigh: z.number().int().min(0),
    diffHigh: z.number().int(),
    diffPopulationExposed: z.number().int(),
    diffRoadsExposed: z.number().int(),
  }),
  params: z
    .object({
      rainfallMm: z.number().min(0).max(2000).optional(),
      rainfallIntensity: z.string().max(40).optional(),
      soilSaturationBonus: z.number().min(-50).max(100).optional(),
    })
    .optional(),
});

const PointQuerySchema = z.object({
  lat: z.coerce.number().min(-90).max(90),
  lon: z.coerce.number().min(-180).max(180),
});

const DateRangeSchema = z.object({
  start_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .optional(),
  end_date: z
    .string()
    .regex(/^\d{4}-\d{2}-\d{2}$/)
    .optional(),
});

// Lightweight in-memory sliding-window rate limiter for AI endpoints
export function createRateLimiter(maxRequests: number, windowMs: number) {
  const hits = new Map<string, number[]>();
  return (req: express.Request, res: express.Response, next: express.NextFunction) => {
    const key = req.ip || req.socket.remoteAddress || 'unknown';
    const now = Date.now();
    const recent = (hits.get(key) || []).filter((ts) => now - ts < windowMs);
    if (recent.length >= maxRequests) {
      res.setHeader('Retry-After', String(Math.ceil(windowMs / 1000)));
      return res.status(429).json({
        error: 'rate_limit_exceeded',
        message: 'Too many AI briefing requests. Please wait a moment before retrying.',
      });
    }
    recent.push(now);
    hits.set(key, recent);
    next();
  };
}

let activeFastApiUrl = process.env.FASTAPI_BACKEND_URL || '';

async function tryProxyToFastApi(
  req: express.Request,
  res: express.Response,
  rawBody?: Buffer
): Promise<boolean> {
  const fastApiBase = process.env.FASTAPI_BACKEND_URL || activeFastApiUrl;
  if (!fastApiBase) return false;

  const targetUrl = new URL(`${fastApiBase.replace(/\/$/, '')}${req.originalUrl}`);
  const isHttps = targetUrl.protocol === 'https:';
  const transport = isHttps ? https : http;
  const agent = isHttps ? fastApiHttpsAgent : fastApiHttpAgent;

  const headers: Record<string, string> = {};
  if (req.headers.accept) headers['Accept'] = String(req.headers.accept);
  if (req.headers['accept-encoding']) headers['Accept-Encoding'] = String(req.headers['accept-encoding']);
  if (req.headers['content-type']) headers['Content-Type'] = String(req.headers['content-type']);
  if (req.headers.authorization) headers['Authorization'] = String(req.headers.authorization);
  if (req.headers['x-request-id']) headers['X-Request-ID'] = String(req.headers['x-request-id']);

  let bodyBuf: Buffer | undefined;
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    if (rawBody !== undefined) {
      bodyBuf = rawBody;
    } else if (req.body && Object.keys(req.body).length > 0) {
      headers['Content-Type'] = 'application/json';
      bodyBuf = Buffer.from(JSON.stringify(req.body), 'utf-8');
    }
  }
  if (bodyBuf) {
    headers['Content-Length'] = String(bodyBuf.length);
  }

  return new Promise<boolean>((resolve) => {
    const proxyReq = transport.request(
      targetUrl,
      {
        method: req.method,
        headers,
        agent,
        timeout: 30_000,
      },
      (upstream) => {
        const chunks: Buffer[] = [];
        upstream.on('data', (chunk: Buffer) => chunks.push(chunk));
        upstream.on('end', () => {
          const buf = Buffer.concat(chunks);
          res.status(upstream.statusCode || 502);
          const ct = upstream.headers['content-type'];
          if (ct) res.setHeader('Content-Type', ct);
          const ce = upstream.headers['content-encoding'];
          if (ce) res.setHeader('Content-Encoding', ce);
          const reqId = upstream.headers['x-request-id'];
          if (reqId) res.setHeader('X-Request-ID', reqId);
          res.setHeader('X-Geos-Data-Backend', 'fastapi');
          res.send(buf);
          resolve(true);
        });
        upstream.on('error', () => resolve(false));
      }
    );

    proxyReq.on('timeout', () => {
      proxyReq.destroy(new Error('FastAPI proxy timeout'));
      resolve(false);
    });
    proxyReq.on('error', () => resolve(false));

    if (bodyBuf) proxyReq.write(bodyBuf);
    proxyReq.end();
  });
}

export function createApp() {
  const app = express();
  const geminiModel = process.env.GEMINI_MODEL || DEFAULT_GEMINI_MODEL;

  app.disable('x-powered-by');
  app.use((_req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    res.setHeader('Permissions-Policy', 'geolocation=(self), camera=()');
    next();
  });

  // Forward multipart/form-data uploads directly to FastAPI before express.json parses body
  app.post('/api/v1/field-reports', async (req, res, next) => {
    const ct = String(req.headers['content-type'] || '');
    if (ct.includes('multipart/form-data')) {
      const chunks: Buffer[] = [];
      let total = 0;
      const MAX_BYTES = 6 * 1024 * 1024;
      req.on('data', (chunk: Buffer) => {
        total += chunk.length;
        if (total <= MAX_BYTES) chunks.push(chunk);
      });
      req.on('end', async () => {
        if (total > MAX_BYTES) {
          return res.status(413).json({ detail: 'Upload exceeds 6 MB request limit.' });
        }
        const ok = await tryProxyToFastApi(req, res, Buffer.concat(chunks));
        if (!ok) {
          res.status(503).json({ detail: 'FastAPI geospatial backend is unavailable for field report uploads.' });
        }
      });
      return;
    }
    next();
  });

  app.use(express.json({ limit: '128kb' }));

  const aiRateLimiter = createRateLimiter(15, 60_000);

  const getGeminiClient = () => {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey || apiKey === 'MY_GEMINI_API_KEY') return null;
    return new GoogleGenAI({
      apiKey,
      httpOptions: {
        headers: {
          'User-Agent': 'aistudio-build',
        },
      },
    });
  };

  // Legacy health check (extended with accurate model & FastAPI configuration metadata)
  app.get('/api/health', (_req, res) => {
    res.json({
      status: 'operational',
      engine: 'GeoResilience-NER 2.0 Web Gateway',
      geminiConfigured: Boolean(
        process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY !== 'MY_GEMINI_API_KEY'
      ),
      geminiModel,
      fastApiConfigured: Boolean(process.env.FASTAPI_BACKEND_URL),
      pilotArtifacts: getPilotHealth().pilot_artifacts,
      timestamp: new Date().toISOString(),
    });
  });

  // =========================================================================
  // GeoResilience-NER 2.0 Verified Environmental API (/api/v1/*)
  // Proxies to Python FastAPI when reachable, else reads the exact same
  // verified pilot GeoTIFF/JSON artifacts directly with zero fabrication.
  // =========================================================================
  app.get('/api/v1/health', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(getPilotHealth());
  });

  app.get('/api/v1/datasets', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(getPilotDatasets());
  });

  app.get('/api/v1/pilot/boundary', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const data = getPilotBoundary();
    if (!data) {
      return res.status(503).json({
        detail: 'Pilot boundary GeoJSON has not been ingested yet.',
      });
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(data);
  });

  app.get('/api/v1/environment/point', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const parsed = PointQuerySchema.safeParse(req.query);
    if (!parsed.success) {
      return res.status(422).json({
        detail: 'Invalid coordinates. lat must be in [-90, 90] and lon in [-180, 180].',
      });
    }
    try {
      const result = await getPilotPointEnvironment(parsed.data.lat, parsed.data.lon);
      res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
      res.json(result);
    } catch (err) {
      console.error('Error sampling pilot rasters:', err);
      res.status(500).json({ detail: 'Failed to sample pilot environmental rasters.' });
    }
  });

  app.get('/api/v1/environment/rainfall/history', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const parsed = DateRangeSchema.safeParse(req.query);
    if (!parsed.success) {
      return res.status(422).json({ detail: 'Dates must follow YYYY-MM-DD format.' });
    }
    const { start_date, end_date } = parsed.data;
    if (start_date && end_date && start_date > end_date) {
      return res.status(400).json({ detail: 'start_date must not be later than end_date.' });
    }
    const history = getPilotRainfallHistory(start_date, end_date);
    if (!history) {
      return res.status(503).json({
        detail: 'NASA GPM IMERG rainfall observations have not been ingested yet.',
      });
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(history);
  });

  app.get('/api/v1/inventory/discovery', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const discovery = getPilotInventoryDiscovery();
    if (!discovery) {
      return res.status(503).json({
        detail: 'Landslide inventory discovery report has not been generated yet.',
      });
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(discovery);
  });

  app.get('/api/v1/landslides/coolr', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const p = path.resolve(process.cwd(), 'backend/data/pilot/dima_hasao_landslides_coolr.json');
    if (!fs.existsSync(p)) {
      return res.status(503).json({ detail: 'NASA COOLR landslide inventory has not been ingested yet.' });
    }
    const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
    if (req.query.pilot_only === 'true') {
      doc.records = (doc.records || []).filter((r: { within_pilot_boundary?: boolean }) => r.within_pilot_boundary);
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(doc);
  });

  app.get('/api/v1/environment/rainfall/multiyear', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const parsed = DateRangeSchema.safeParse(req.query);
    if (!parsed.success) {
      return res.status(422).json({ detail: 'Dates must follow YYYY-MM-DD format.' });
    }
    const { start_date, end_date } = parsed.data;
    if (start_date && end_date && start_date > end_date) {
      return res.status(400).json({ detail: 'start_date must not be later than end_date.' });
    }
    const p = path.resolve(process.cwd(), 'backend/data/pilot/dima_hasao_rainfall_multiyear.json');
    if (!fs.existsSync(p)) {
      return res.status(503).json({ detail: 'Multi-year historical rainfall archive has not been ingested yet.' });
    }
    const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
    let obs = doc.observations || [];
    if (start_date) obs = obs.filter((o: { date: string }) => o.date >= start_date);
    if (end_date) obs = obs.filter((o: { date: string }) => o.date <= end_date);
    doc.observations =
      req.query.include_observations === 'true' || start_date || end_date ? obs : obs.slice(-90);
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(doc);
  });

  app.get('/api/v1/quality-gate', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const p = path.resolve(process.cwd(), 'backend/data/pilot/data_quality_gate_report.json');
    if (!fs.existsSync(p)) {
      return res.status(503).json({ detail: 'Data quality gate report has not been generated yet.' });
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(JSON.parse(fs.readFileSync(p, 'utf-8')));
  });

  app.get('/api/v1/features/quality', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const p = path.resolve(process.cwd(), 'backend/data/pilot/spatial_data_quality_inventory.json');
    if (!fs.existsSync(p)) {
      return res.status(503).json({ detail: 'Spatial data quality inventory has not been generated yet.' });
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(JSON.parse(fs.readFileSync(p, 'utf-8')));
  });

  app.get('/api/v1/rainfall/imerg-v07/catalog', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const p = path.resolve(process.cwd(), 'backend/data/pilot/imerg_v07_cmr_catalog.json');
    if (!fs.existsSync(p)) {
      return res.status(503).json({ detail: 'NASA IMERG V07B/V07C CMR catalog has not been generated yet.' });
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(JSON.parse(fs.readFileSync(p, 'utf-8')));
  });

  app.get('/api/v1/landslides/gsi-bhusanket', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const p = path.resolve(process.cwd(), 'backend/data/pilot/dima_hasao_landslides_gsi_bhusanket.json');
    if (!fs.existsSync(p)) {
      return res.status(503).json({ detail: 'GSI Bhusanket public landslide inventory has not been ingested yet.' });
    }
    const doc = JSON.parse(fs.readFileSync(p, 'utf-8'));
    if (req.query.pilot_only === 'true') {
      doc.records = (doc.records || []).filter((r: { within_pilot_boundary?: boolean }) => r.within_pilot_boundary);
    }
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(doc);
  });

  // =========================================================================
  // Optional Gemini Narrative Briefing Endpoints (NOT a prediction engine)
  // =========================================================================
  app.post('/api/gemini/explain', aiRateLimiter, async (req, res) => {
    const parsed = ExplainLocationSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        error: 'validation_error',
        message: 'Invalid location payload provided for narrative briefing.',
      });
    }

    const { location, simulated } = parsed.data;
    const ai = getGeminiClient();
    if (!ai) {
      return res.status(503).json({
        source: 'unavailable',
        model: geminiModel,
        error: 'gemini_not_configured',
        message: 'Gemini narrative assistant is not configured on this server.',
      });
    }

    try {
      const prompt = `You are a disaster-communications narrative assistant helping summarize prototype landslide decision-support scenarios for Northeast India.
IMPORTANT SCIENTIFIC GUARDRAIL: You are NOT a predictive ML model and must NOT fabricate Factor of Safety numbers, landslide probabilities, or unverified sensor readings. Clearly state that the input risk index below is from an unvalidated prototype heuristic.

Scenario context:
- Location: ${location.name} (${location.state}, District: ${location.district})
- Prototype Heuristic Index: ${location.calculatedScore}/100 (${location.calculatedLevel})
- Input 24h Rainfall: ${location.currentRainfall} mm
- Input Slope Angle: ${location.slope}°
- Input Elevation: ${location.elevation} m
- Soil Description: ${location.soilType}
- Input Soil Saturation Index: ${location.soilSaturation}%
- Input Historical Activity Index: ${location.historicalActivity}%
- Estimated Exposed Population (Demo Scenario): ${location.populationExposed}
- Infrastructure Count (Demo Scenario): ${location.infrastructure.roads} roads (${location.infrastructure.keyHighways.join(', ') || 'Local corridors'}), ${location.infrastructure.bridges} bridges, ${location.infrastructure.hospitals} hospitals, ${location.infrastructure.schools} schools.
- Context: ${simulated ? 'Hypothetical stress-test rainfall scenario.' : 'Prototype baseline scenario.'}

Write a concise 2-paragraph operational summary:
Paragraph 1: Explain qualitatively why the combination of slope gradient, antecedent moisture, and intense precipitation is relevant to slope stability in Northeast India without inventing numerical Factor of Safety or failure probabilities.
Paragraph 2: List pragmatic preparedness checks for DDMA, PWD/BRO road maintenance teams, and local field observers.`;

      const response = await ai.models.generateContent({
        model: geminiModel,
        contents: prompt,
      });

      return res.json({
        source: 'gemini-ai',
        model: geminiModel,
        text: response.text || '',
        disclaimer: 'AI-generated narrative summary only — not a trained landslide prediction model.',
      });
    } catch (err) {
      console.error('Gemini explain error:', err);
      return res.status(502).json({
        source: 'error',
        model: geminiModel,
        error: 'upstream_ai_unavailable',
        message: 'Unable to retrieve narrative briefing from the Gemini API at this time.',
      });
    }
  });

  app.post('/api/gemini/what-if-briefing', aiRateLimiter, async (req, res) => {
    const parsed = WhatIfBriefingSchema.safeParse(req.body);
    if (!parsed.success) {
      return res.status(400).json({
        error: 'validation_error',
        message: 'Invalid simulation summary payload.',
      });
    }

    const { summary, params } = parsed.data;
    const ai = getGeminiClient();
    if (!ai) {
      return res.status(503).json({
        source: 'unavailable',
        model: geminiModel,
        error: 'gemini_not_configured',
        message: 'Gemini narrative assistant is not configured on this server.',
      });
    }

    try {
      const prompt = `You are a disaster-preparedness communications assistant. Summarize this HYPOTHETICAL prototype stress-test scenario in 3 concise bullet points without claiming scientific forecast accuracy or inventing unprovided statistics.
Scenario inputs: Simulated rainfall ${params?.rainfallMm ?? 180} mm/24h (pattern: ${params?.rainfallIntensity ?? 'Normal'}, saturation offset: ${params?.soilSaturationBonus ?? 0}%).
Heuristic prototype deltas:
- Critical zones: ${summary.currentCritical} -> ${summary.simulatedCritical} (delta ${summary.diffCritical})
- High zones: ${summary.currentHigh} -> ${summary.simulatedHigh} (delta ${summary.diffHigh})
- Delta exposed population: ${summary.diffPopulationExposed}
- Delta disrupted road segments: ${summary.diffRoadsExposed}`;

      const response = await ai.models.generateContent({
        model: geminiModel,
        contents: prompt,
      });

      return res.json({
        source: 'gemini-ai',
        model: geminiModel,
        text: response.text || '',
        disclaimer: 'AI-generated narrative summary of a heuristic stress test — not a validated forecast.',
      });
    } catch (err) {
      console.error('Gemini what-if error:', err);
      return res.status(502).json({
        source: 'error',
        model: geminiModel,
        error: 'upstream_ai_unavailable',
        message: 'Unable to retrieve scenario briefing from the Gemini API at this time.',
      });
    }
  });

  // =========================================================================
  // Verified Artifact Fallbacks for GEOS 2.0 Hub when Python FastAPI is absent
  // =========================================================================
  const readJsonIfExists = (relPath: string): any | null => {
    const abs = path.resolve(process.cwd(), relPath);
    if (!fs.existsSync(abs)) return null;
    return JSON.parse(fs.readFileSync(abs, 'utf-8'));
  };

  const loadGfsForecastSummary = () => {
    const doc = readJsonIfExists('backend/data/experimental/dima_hasao_gfs_forecast_eval.json');
    if (!doc) return null;
    const prov = doc.discovery_provenance || {};
    const temp = doc.temporal_domain || {};
    const summary = doc.summary_metrics || {};
    const initTime = temp.forecast_init_time_utc || null;
    let ageHours: number | null = null;
    if (initTime) {
      const ms = Date.now() - Date.parse(initTime);
      if (Number.isFinite(ms)) ageHours = Math.round((ms / 3_600_000) * 100) / 100;
    }
    return {
      data_role: 'experimental_forecast_only_never_measured_rainfall',
      provider: prov.attribution || 'NOAA NCEP GFS 0.25 deg via Dynamical.org Zarr v3',
      source_url: prov.source_url || 'https://data.dynamical.org/noaa/gfs/forecast/latest.zarr',
      init_time_utc: initTime,
      retrieved_at_utc: temp.retrieved_at_utc || null,
      spatial_resolution_deg: doc.spatial_domain?.resolution_deg ?? 0.25,
      rain_24h_outlook_mm: summary.forecast_24h_mean_rain_mm ?? null,
      rain_48h_outlook_mm: null,
      rain_72h_outlook_mm: summary.forecast_72h_mean_rain_mm ?? null,
      temp_2m_min_c: summary.t2m_min_c ?? null,
      temp_2m_max_c: summary.t2m_max_c ?? null,
      rh_2m_mean_pct: summary.rh_2m_mean_pct ?? null,
      pwat_mean_mm: summary.pwat_mean_mm ?? null,
      forecast_age_hours: ageHours,
      is_stale: ageHours === null ? true : ageHours > 24,
      limitations:
        '0.25 deg (~25 km) global NWP forecast smooths steep Barail Range orographic rainfall maxima. Must never be labeled as observed precipitation.',
    };
  };

  const haversineKm = (lat1: number, lon1: number, lat2: number, lon2: number) => {
    const R = 6371;
    const dLat = ((lat2 - lat1) * Math.PI) / 180;
    const dLon = ((lon2 - lon1) * Math.PI) / 180;
    const a =
      Math.sin(dLat / 2) ** 2 +
      Math.cos((lat1 * Math.PI) / 180) * Math.cos((lat2 * Math.PI) / 180) * Math.sin(dLon / 2) ** 2;
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  };

  const computeOsmExposure = (lat: number, lon: number, radiusKm: number) => {
    const facDoc = readJsonIfExists('backend/data/pilot/dima_hasao_osm_facilities.geojson');
    const counts = {
      hospitals_health: 0,
      schools: 0,
      settlements: 0,
      bridges: 0,
      road_segments: 0,
      railway_segments: 0,
    };
    const nearest: Array<Record<string, unknown>> = [];
    for (const feat of facDoc?.features || []) {
      const coords = feat?.geometry?.coordinates;
      const props = feat?.properties || {};
      if (!Array.isArray(coords) || coords.length < 2) continue;
      const d = haversineKm(lat, lon, Number(coords[1]), Number(coords[0]));
      if (d <= radiusKm) {
        if (props.category === 'hospital_health') counts.hospitals_health += 1;
        else if (props.category === 'school') counts.schools += 1;
        else if (props.category === 'settlement') counts.settlements += 1;
        else if (props.category === 'bridge') counts.bridges += 1;
        nearest.push({ ...props, distance_km: Math.round(d * 100) / 100 });
      }
    }
    nearest.sort((a, b) => Number(a.distance_km) - Number(b.distance_km));
    return {
      query_radius_km: radiusKm,
      exposure_nature: 'estimated_spatial_proximity_not_observed_damage',
      counts,
      named_transport_corridors: [],
      nearest_assets: nearest.slice(0, 15),
      population_exposure_note:
        'Gridded census/WorldPop exposure is NOT available; population figures are never fabricated.',
      source_attribution: facDoc?.metadata?.attribution || '© OpenStreetMap contributors (ODbL 1.0)',
    };
  };

  app.get('/api/v1/ml/readiness', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const gate = readJsonIfExists('backend/data/pilot/data_quality_gate_report.json');
    if (!gate) return res.status(503).json({ detail: 'Quality gate report unavailable.' });
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(gate);
  });

  app.get('/api/v1/ml/models', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const gate = readJsonIfExists('backend/data/pilot/data_quality_gate_report.json');
    const benchmark = readJsonIfExists('backend/data/experimental/exploratory_ml_benchmark.json');
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({
      production_models_validated: 0,
      production_inference_available: false,
      landslide_probability_policy: 'STRICTLY_NULL_UNTIL_QUALITY_GATE_PASSES',
      quality_gate_passed: Boolean(gate?.overall_ml_ready),
      blocking_failures: gate?.blocking_failures || [],
      exploratory_research_benchmark: benchmark,
    });
  });

  app.post('/api/v1/ml/infer', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const gate = readJsonIfExists('backend/data/pilot/data_quality_gate_report.json');
    const lat = Number(req.body?.lat ?? 25.1645);
    const lon = Number(req.body?.lon ?? 93.0176);
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({
      status: 'unavailable_model_not_validated',
      model_validated: false,
      landslide_probability: null,
      factor_of_safety: null,
      coordinates: { lat, lon },
      message:
        'No scientifically validated landslide prediction model is deployed for Dima Hasao. Production inference remains disabled until all 13 Data Quality Gate checks pass.',
      blocking_failures: gate?.blocking_failures || [],
    });
  });

  app.get('/api/v1/environment/rainfall/forecast', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const fc = loadGfsForecastSummary();
    if (!fc) return res.status(503).json({ detail: 'Experimental NOAA GFS forecast artifact unavailable.' });
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json(fc);
  });

  app.get('/api/v1/infrastructure/facilities', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const doc = readJsonIfExists('backend/data/pilot/dima_hasao_osm_facilities.geojson');
    if (!doc) return res.status(503).json({ detail: 'OSM facilities GeoJSON unavailable.' });
    const category = typeof req.query.category === 'string' ? req.query.category : null;
    const limit = Math.min(700, Math.max(1, Number(req.query.limit || 200)));
    const feats = category
      ? (doc.features || []).filter((f: any) => f?.properties?.category === category)
      : doc.features || [];
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({ type: 'FeatureCollection', metadata: doc.metadata, features: feats.slice(0, limit) });
  });

  app.get('/api/v1/infrastructure/exposure', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const lat = Number(req.query.lat ?? 25.1645);
    const lon = Number(req.query.lon ?? 93.0176);
    const radiusKm = Math.min(25, Math.max(0.5, Number(req.query.radius_km ?? 5)));
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({
      coordinates: { lat, lon },
      exposure: computeOsmExposure(lat, lon, radiusKm),
    });
  });

  app.get('/api/v1/hazard/assess', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const lat = Number(req.query.lat ?? 25.1645);
    const lon = Number(req.query.lon ?? 93.0176);
    const radiusKm = Math.min(25, Math.max(0.5, Number(req.query.radius_km ?? 5)));
    const point = await getPilotPointEnvironment(lat, lon);
    const gate = readJsonIfExists('backend/data/pilot/data_quality_gate_report.json');
    const forecast = loadGfsForecastSummary();
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({
      coordinates: { lat, lon },
      study_area: 'Dima Hasao District, Assam (Pilot)',
      within_pilot_boundary: point.within_pilot_boundary,
      assessed_at_utc: new Date().toISOString(),
      landslide_probability: null,
      factor_of_safety: null,
      static_susceptibility: {
        status: 'unavailable_model_not_validated',
        landslide_probability: null,
        model_version: null,
        quality_gate_passed: Boolean(gate?.overall_ml_ready),
        blocking_reasons: gate?.blocking_failures || [],
      },
      observed_rainfall: {
        latest_observation_date: point.rainfall.latest_observation_date,
        rainfall_24h_mm: point.rainfall.rainfall_24h_mm,
        rainfall_72h_mm: point.rainfall.rainfall_72h_mm,
        is_stale: true,
        missing_telemetry_alert: true,
        latency_info: point.rainfall.latency_info,
      },
      forecast_rainfall: forecast,
      terrain_and_soil_context: {
        elevation_m: point.terrain.elevation_m,
        slope_deg: point.terrain.slope_deg,
        aspect_cardinal: point.terrain.aspect_cardinal,
        land_cover_2021: point.land_cover.class_label,
        geomorphometry: null,
        soilgrids_2_0: { clay_0_5cm_pct: null, cohesion_kpa: null, friction_angle_deg: null },
        geology: { lithology_class: null, status: 'access_blocked_gsi_ngdr_bhukosh' },
      },
      infrastructure_exposure: computeOsmExposure(lat, lon, radiusKm),
      response_priority: {
        inspection_priority_tier: 'BASELINE_MONITORING',
        imd_rainfall_envelope: 'LOW_RAIN_ENVELOPE',
        official_government_warning: false,
        calibration_status: 'EXPERIMENTAL_UNVALIDATED_ENVELOPE',
      },
      uncertainty_and_limitations: [
        'No scientifically validated landslide ML model is deployed (landslide_probability = null).',
        'Factor of Safety is never computed without site-specific geotechnical testing.',
      ],
    });
  });

  app.post('/api/v1/hazard/simulate', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const lat = Number(req.body?.lat ?? 25.1645);
    const lon = Number(req.body?.lon ?? 93.0176);
    const r24 = Math.max(0, Number(req.body?.hypothetical_rain_24h_mm ?? 0));
    const r72 = Math.max(0, Number(req.body?.hypothetical_rain_72h_mm ?? 0));
    const r7 = Math.max(0, Number(req.body?.hypothetical_antecedent_7d_mm ?? 0));
    const radiusKm = Math.min(25, Math.max(0.5, Number(req.body?.radius_km ?? 5)));
    const rainTier =
      r24 >= 204.5 || r72 >= 300
        ? 'EXTREMELY_HEAVY_ENVELOPE'
        : r24 >= 115.6 || r72 >= 200 || r7 >= 350
        ? 'VERY_HEAVY_ENVELOPE'
        : r24 >= 64.5 || r72 >= 120 || r7 >= 250
        ? 'HEAVY_RAIN_ENVELOPE'
        : r24 >= 15.6 || r72 >= 45
        ? 'MODERATE_RAIN_ENVELOPE'
        : 'LOW_RAIN_ENVELOPE';
    const tier =
      rainTier === 'EXTREMELY_HEAVY_ENVELOPE' || rainTier === 'VERY_HEAVY_ENVELOPE'
        ? 'PRIORITY_2_HEIGHTENED_MONITORING'
        : rainTier === 'HEAVY_RAIN_ENVELOPE'
        ? 'PRIORITY_3_ROUTINE_WATCH'
        : 'BASELINE_MONITORING';
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({
      hypothetical_scenario: true,
      scenario_label: 'HYPOTHETICAL_STRESS_TEST_NOT_A_FORECAST',
      coordinates: { lat, lon },
      simulated_at_utc: new Date().toISOString(),
      inputs: { hypothetical_rain_24h_mm: r24, hypothetical_rain_72h_mm: r72, hypothetical_antecedent_7d_mm: r7 },
      validated_ml_probability: null,
      factor_of_safety: null,
      threshold_envelope_response: {
        inspection_priority_tier: tier,
        imd_rainfall_envelope: rainTier,
        calibration_status: 'EXPERIMENTAL_UNVALIDATED_ENVELOPE',
      },
      potentially_exposed_mapped_infrastructure: computeOsmExposure(lat, lon, radiusKm),
    });
  });

  app.get('/api/v1/monitoring/status', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const fc = loadGfsForecastSummary();
    const history = getPilotRainfallHistory();
    const run = {
      run_id: 0,
      job_name: 'dima_hasao_environmental_monitoring',
      status: 'partial_stale',
      started_at: new Date().toISOString(),
      completed_at: new Date().toISOString(),
      observed_rainfall_latest_date: history?.interval_end || '2024-06-01',
      observed_rainfall_stale: true,
      forecast_init_time_utc: fc?.init_time_utc || null,
      forecast_stale: fc ? fc.is_stale : true,
      summary: { forecast_outlook: fc },
    };
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({ latest_run: run, recent_runs: [run] });
  });

  app.get('/api/v1/regions', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    const states = [
      { state_name: 'Assam', state_code: 'AS', pilot_district: 'Dima Hasao', status: 'pilot_active', environmental_data_available: true, landslide_inventory_status: 'partial_public_gsi_379_unverified_points', model_validated: false },
      { state_name: 'Arunachal Pradesh', state_code: 'AR', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
      { state_name: 'Meghalaya', state_code: 'ML', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
      { state_name: 'Manipur', state_code: 'MN', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
      { state_name: 'Mizoram', state_code: 'MZ', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
      { state_name: 'Nagaland', state_code: 'NL', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
      { state_name: 'Tripura', state_code: 'TR', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
      { state_name: 'Sikkim', state_code: 'SK', pilot_district: null, status: 'planned', environmental_data_available: false, landslide_inventory_status: 'not_ingested', model_validated: false },
    ];
    res.setHeader('X-Geos-Data-Backend', 'verified-pilot-bridge');
    res.json({ total_states_configured: 8, pilot_active_states: 1, validated_ml_states: 0, states });
  });

  // Catch-all forwarder for remaining GEOS 2.0 /api/v1/* routes (auth, field reports, alerts, assistant)
  app.all('/api/v1/*', async (req, res) => {
    if (await tryProxyToFastApi(req, res)) return;
    res.status(503).json({
      error: 'fastapi_backend_unavailable',
      detail: 'The Python FastAPI geospatial backend is not running in this Node-only environment.',
    });
  });

  return app;
}

async function startServer() {
  // Outside unit tests, auto-start the local Python FastAPI backend on port 8001 (never 8000) if venv exists
  let fastApiProc: import('child_process').ChildProcess | null = null;
  const fastApiPort = Number(process.env.FASTAPI_PORT || 8001);
  if (process.env.NODE_ENV !== 'test' && !process.env.FASTAPI_BACKEND_URL) {
    const venvPython = path.resolve(process.cwd(), 'backend/.venv/bin/python');
    if (fs.existsSync(venvPython)) {
      const { spawn } = await import('child_process');
      fastApiProc = spawn(
        venvPython,
        ['-m', 'uvicorn', 'backend.app.main:app', '--host', '127.0.0.1', '--port', String(fastApiPort), '--workers', '1'],
        {
          cwd: process.cwd(),
          env: { ...process.env, PYTHONPATH: '.' },
          stdio: 'inherit',
        }
      );
      activeFastApiUrl = `http://127.0.0.1:${fastApiPort}`;
      fastApiProc.on('error', (err) => {
        console.warn('FastAPI backend failed to start; falling back to verified pilot bridge:', err.message);
        activeFastApiUrl = '';
      });
      fastApiProc.on('exit', () => {
        activeFastApiUrl = '';
      });
      const cleanup = () => {
        if (fastApiProc && !fastApiProc.killed) fastApiProc.kill('SIGTERM');
      };
      process.on('SIGINT', cleanup);
      process.on('SIGTERM', cleanup);
      process.on('exit', cleanup);
    }
  }

  const app = createApp();

  // Strictly bind port 3000 in development (or explicit --port CLI arg) so container ENV_PORT=8080 never collides with nginx
  const portArgIdx = process.argv.indexOf('--port');
  const cliPort = portArgIdx !== -1 ? Number(process.argv[portArgIdx + 1]) : NaN;
  const PORT =
    Number.isFinite(cliPort) && cliPort > 0
      ? cliPort
      : process.env.NODE_ENV === 'production'
      ? Number(process.env.PORT || 3000)
      : 3000;

  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.resolve(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`GeoResilience-NER 2.0 Server running on http://0.0.0.0:${PORT}`);
  });
}

// Guard auto-start when imported in unit tests
if (process.env.NODE_ENV !== 'test') {
  startServer().catch((err) => {
    console.error('Fatal server startup error:', err);
    process.exit(1);
  });
}
