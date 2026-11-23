/**
 * Typed frontend API client for GeoResilience-NER 2.0 verified environmental endpoints (/api/v1/*).
 */

export interface DatasetProvenance {
  dataset_id: string;
  dataset_name: string;
  product_version: string;
  source_url: string;
  crs: string;
  resolution_m: number | null;
  observation_period: string;
  processing_timestamp: string | null;
  attribution: string;
  limitations: string | null;
}

export interface TerrainObservation {
  elevation_m: number | null;
  elevation_resolution_m: number | null;
  slope_deg: number | null;
  aspect_deg: number | null;
  aspect_cardinal: string | null;
  slope_aspect_resolution_m: number | null;
  missing_elevation: boolean;
  missing_slope_aspect: boolean;
  provenance: DatasetProvenance | null;
}

export interface LandCoverObservation {
  class_code: number | null;
  class_label: string | null;
  missing_land_cover: boolean;
  provenance: DatasetProvenance | null;
}

export interface RainfallSnapshot {
  latest_observation_date: string | null;
  latest_observation_timestamp_utc: string | null;
  rainfall_24h_mm: number | null;
  rainfall_72h_mm: number | null;
  max_24h_in_window_mm: number | null;
  max_72h_in_window_mm: number | null;
  window_start: string | null;
  window_end: string | null;
  valid_days_in_window: number;
  missing_days_in_window: number;
  missing_24h: boolean;
  missing_72h: boolean;
  latency_info: string | null;
  provenance: DatasetProvenance | null;
}

export interface PointEnvironmentResponse {
  coordinates: { lat: number; lon: number };
  crs: string;
  study_area: string;
  within_pilot_boundary: boolean;
  within_raster_bounds: boolean;
  scientific_disclaimer: string;
  landslide_probability: null;
  terrain: TerrainObservation;
  land_cover: LandCoverObservation;
  rainfall: RainfallSnapshot;
  missing_data_indicators: Record<string, boolean>;
  response_generated_at_utc: string;
}

export interface DailyRainfallPoint {
  date: string;
  observation_timestamp_utc: string;
  rainfall_24h_mm: number | null;
  rainfall_72h_mm: number | null;
  missing_24h: boolean;
  missing_72h: boolean;
}

export interface RainfallHistoryResponse {
  study_area: string;
  dataset_id: string;
  dataset_name: string;
  product_version: string;
  spatial_resolution_deg: number;
  latency_info: string;
  interval_start: string;
  interval_end: string;
  total_days: number;
  valid_observation_days: number;
  missing_observation_days: number;
  max_24h_mm: number | null;
  max_72h_mm: number | null;
  missing_data_policy: string;
  processing_timestamp: string;
  attribution: string;
  source_url: string;
  observations: DailyRainfallPoint[];
}

export interface PilotBoundaryResponse {
  geojson: {
    type: 'FeatureCollection';
    features: Array<{
      type: 'Feature';
      properties: Record<string, unknown>;
      geometry: {
        type: 'Polygon' | 'MultiPolygon';
        coordinates: unknown;
      };
    }>;
    metadata?: {
      dataset_name: string;
      crs: string;
      area_km2: number;
      bbox_wgs84: [number, number, number, number];
      centroid_wgs84: { lat: number; lon: number };
      processing_timestamp: string;
      attribution: string;
      limitations?: string;
    };
  };
  terrain_summary?: Record<string, unknown> | null;
  land_cover_summary?: Record<string, unknown> | null;
}

export interface DatasetRegistryItem {
  dataset_id: string;
  name: string;
  category: string;
  product_version: string;
  crs: string;
  resolution_m: number | null;
  observation_period: string;
  processing_timestamp: string | null;
  available: boolean;
  requires_credentials: boolean;
  source_url: string;
  attribution: string;
  limitations: string | null;
}

export interface BackendHealthStatus {
  status: string;
  service?: string;
  version?: string;
  timestamp_utc?: string;
  pilot_artifacts?: Record<string, boolean>;
  ml_model_status?: string;
  database?: {
    connected: boolean;
    dialect: string;
    postgis_version: string | null;
  };
}

export interface InventoryProviderProbe {
  provider: string;
  dataset: string;
  portal_url: string;
  secondary_url?: string;
  requires_registration: boolean;
  machine_readable_api_available: boolean;
  resolution_steps: string[];
  http_status: number | null;
  reachable_from_environment: boolean;
  pilot_records_retrieved: number;
  error: string | null;
  blocker_note: string;
}

export interface InventoryDiscoveryResponse {
  study_area: string;
  discovery_timestamp: string;
  fabricated_labels_count: number;
  verified_pilot_landslide_records_count: number;
  verified_pilot_landslide_records: unknown[];
  providers: InventoryProviderProbe[];
  scientific_note: string;
}

export interface AuthUser {
  id: number;
  username: string;
  full_name: string;
  role: 'admin' | 'research_analyst' | 'field_officer' | 'public_viewer';
  is_active: boolean;
  created_at: string | null;
}

export interface AuthBootstrapStatus {
  needs_admin_claim: boolean;
  admin_exists: boolean;
  env_admin_passcode_configured: boolean;
  supported_roles: string[];
  self_register_roles: string[];
}

export interface AuthTokenResponse {
  access_token: string;
  token_type: string;
  user: AuthUser;
}

export interface PersistedFieldReport {
  id: number;
  study_area_slug: string;
  location_name: string;
  latitude: number;
  longitude: number;
  within_pilot_boundary: boolean;
  observed_at_utc: string;
  category: string;
  severity_observation: string;
  description: string;
  road_obstruction: string;
  notes: string | null;
  photo_url: string | null;
  photo_metadata: {
    filename: string;
    mime_type: string;
    size_bytes: number;
    sha256: string;
  } | null;
  verification_status: 'pending' | 'verified' | 'rejected';
  submitted_by_username: string | null;
  reviewed_by_username: string | null;
  review_notes: string | null;
  reviewed_at: string | null;
  created_at: string | null;
  ml_impact_note: string;
}

export interface PersistedExperimentalAlert {
  id: number;
  classification: string;
  official_government_warning: boolean;
  title: string;
  geographic_area: string;
  latitude: number | null;
  longitude: number | null;
  severity_tier: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
  severity_rationale: string;
  hazard_evidence: Record<string, unknown>;
  source_timestamps: Record<string, unknown>;
  affected_infrastructure: Record<string, unknown>;
  inspection_priorities: string[];
  status: 'draft' | 'pending_review' | 'approved_internal' | 'rejected' | 'archived';
  created_by_username: string | null;
  reviewed_by_username: string | null;
  review_comment: string | null;
  dry_run_notifications: Array<Record<string, unknown>>;
  created_at: string | null;
}

export interface RegionalCoverageState {
  state_code: string;
  state_name: string;
  pilot_district: string | null;
  region_configured: boolean;
  environmental_data_available: boolean;
  landslide_inventory_available: boolean;
  model_validated: boolean;
  experimental_monitoring_active: boolean;
  center_lat: number;
  center_lon: number;
  coverage_notes: string | null;
}

async function fetchJson<T>(
  url: string,
  options?: RequestInit & { token?: string | null }
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((options?.headers as Record<string, string>) || {}),
  };
  if (options?.token) {
    headers['Authorization'] = `Bearer ${options.token}`;
  }
  const response = await fetch(url, {
    ...options,
    headers,
  });
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const errBody = await response.json();
      if (typeof errBody?.detail === 'string') detail = errBody.detail;
      else if (typeof errBody?.detail?.message === 'string') detail = errBody.detail.message;
      else if (typeof errBody?.message === 'string') detail = errBody.message;
      else if (typeof errBody?.error === 'string') detail = errBody.error;
    } catch {
      // keep status text
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const environmentApi = {
  getHealth: () => fetchJson<BackendHealthStatus>('/api/v1/health'),
  getDatasets: () => fetchJson<DatasetRegistryItem[]>('/api/v1/datasets'),
  getPilotBoundary: () => fetchJson<PilotBoundaryResponse>('/api/v1/pilot/boundary'),
  getPointEnvironment: (lat: number, lon: number) =>
    fetchJson<PointEnvironmentResponse>(
      `/api/v1/environment/point?lat=${encodeURIComponent(lat.toFixed(6))}&lon=${encodeURIComponent(lon.toFixed(6))}`
    ),
  getRainfallHistory: (startDate?: string, endDate?: string) => {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const qs = params.toString();
    return fetchJson<RainfallHistoryResponse>(
      `/api/v1/environment/rainfall/history${qs ? `?${qs}` : ''}`
    );
  },
  getInventoryDiscovery: () => fetchJson<InventoryDiscoveryResponse>('/api/v1/inventory/discovery'),

  // GEOS 2.0 Extended Research Platform Endpoints
  getQualityGate: () => fetchJson<Record<string, any>>('/api/v1/quality-gate'),
  getMlModels: () => fetchJson<Record<string, any>>('/api/v1/ml/models'),
  inferMl: (lat: number, lon: number) =>
    fetchJson<Record<string, any>>('/api/v1/ml/infer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ lat, lon }),
    }),
  assessHazard: (lat: number, lon: number, radiusKm = 5) =>
    fetchJson<Record<string, any>>(
      `/api/v1/hazard/assess?lat=${encodeURIComponent(lat.toFixed(6))}&lon=${encodeURIComponent(lon.toFixed(6))}&radius_km=${radiusKm}`
    ),
  simulateWhatIf: (payload: {
    lat: number;
    lon: number;
    hypothetical_rain_24h_mm: number;
    hypothetical_rain_72h_mm: number;
    hypothetical_antecedent_7d_mm: number;
    radius_km?: number;
  }) =>
    fetchJson<Record<string, any>>('/api/v1/hazard/simulate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  getMonitoringStatus: () => fetchJson<Record<string, any>>('/api/v1/monitoring/status'),
  triggerMonitoringRun: (token: string, refreshLiveGfs = false) =>
    fetchJson<Record<string, any>>(
      `/api/v1/monitoring/run?refresh_live_gfs=${refreshLiveGfs ? 'true' : 'false'}`,
      { method: 'POST', token }
    ),
  getRegions: () =>
    fetchJson<{
      total_states_configured: number;
      pilot_active_states: number;
      validated_ml_states: number;
      states: RegionalCoverageState[];
    }>('/api/v1/regions'),

  // Auth & RBAC (tokens strictly held in React memory, never localStorage)
  getAuthBootstrapStatus: () => fetchJson<AuthBootstrapStatus>('/api/v1/auth/bootstrap-status'),
  claimAdmin: (payload: { username: string; email: string; full_name: string; password: string }) =>
    fetchJson<AuthTokenResponse>('/api/v1/auth/claim-admin', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  register: (payload: {
    username: string;
    email: string;
    full_name: string;
    password: string;
    requested_role: 'field_officer' | 'public_viewer';
  }) =>
    fetchJson<AuthTokenResponse>('/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  login: (username: string, password: string) =>
    fetchJson<AuthTokenResponse>('/api/v1/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    }),

  // Authenticated Field Reports
  listFieldReports: (status?: string) =>
    fetchJson<{ total: number; items: PersistedFieldReport[] }>(
      `/api/v1/field-reports${status ? `?status=${encodeURIComponent(status)}` : ''}`
    ),
  createFieldReport: (formData: FormData, token: string) =>
    fetchJson<PersistedFieldReport>('/api/v1/field-reports', {
      method: 'POST',
      body: formData,
      token,
    }),
  reviewFieldReport: (
    reportId: number,
    verification_status: 'verified' | 'rejected' | 'pending',
    review_notes: string,
    token: string
  ) =>
    fetchJson<PersistedFieldReport>(`/api/v1/field-reports/${reportId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verification_status, review_notes }),
      token,
    }),

  // Experimental Alerts
  listExperimentalAlerts: () =>
    fetchJson<{ total: number; official_warning_notice: string; items: PersistedExperimentalAlert[] }>(
      '/api/v1/alerts'
    ),
  createExperimentalAlert: (
    payload: {
      title: string;
      geographic_area: string;
      latitude: number;
      longitude: number;
      severity_tier: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';
      severity_rationale: string;
      inspection_priorities: string[];
    },
    token: string
  ) =>
    fetchJson<PersistedExperimentalAlert>('/api/v1/alerts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      token,
    }),
  reviewExperimentalAlert: (
    alertId: number,
    status: 'approved_internal' | 'rejected' | 'archived' | 'pending_review',
    review_comment: string,
    token: string
  ) =>
    fetchJson<PersistedExperimentalAlert>(`/api/v1/alerts/${alertId}/review`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status, review_comment }),
      token,
    }),
  dryRunAlertNotify: (alertId: number, target_group: string, token: string) =>
    fetchJson<Record<string, any>>(`/api/v1/alerts/${alertId}/dry-run-notify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        channels: ['internal_research_log', 'webhook_dry_run'],
        target_group,
      }),
      token,
    }),

  // Grounded Gemini Explanation Assistant
  askAssistant: (question: string, lat: number, lon: number, radius_km = 5) =>
    fetchJson<Record<string, any>>('/api/v1/assistant/explain', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question, lat, lon, radius_km }),
    }),
};
