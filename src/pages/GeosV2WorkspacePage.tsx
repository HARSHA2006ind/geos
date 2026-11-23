import React, { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import {
  AlertTriangle,
  CheckCircle2,
  ClipboardCheck,
  CloudRain,
  Database,
  Globe2,
  Lock,
  MessageSquareText,
  RefreshCw,
  Send,
  Shield,
  SlidersHorizontal,
  Upload,
  XCircle,
} from 'lucide-react';
import {
  AuthBootstrapStatus,
  AuthUser,
  PersistedExperimentalAlert,
  PersistedFieldReport,
  RegionalCoverageState,
  environmentApi,
} from '../services/environmentApi';
import { DIMA_HASAO_PRESETS } from '../components/pilot/PilotEnvironmentPanel';

type HubTab =
  | 'hazard-inspector'
  | 'ml-validation'
  | 'what-if'
  | 'field-reports'
  | 'alerts-workflow'
  | 'monitoring-regions';

export const GeosV2WorkspacePage: React.FC = () => {
  const [tab, setTab] = useState<HubTab>('hazard-inspector');

  // Auth state strictly held in React memory (never persisted to localStorage)
  const [authToken, setAuthToken] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(null);
  const [bootstrap, setBootstrap] = useState<AuthBootstrapStatus | null>(null);
  const [authMode, setAuthMode] = useState<'login' | 'claim' | 'register'>('login');
  const [authForm, setAuthForm] = useState({
    username: '',
    email: '',
    full_name: '',
    password: '',
    requested_role: 'field_officer' as 'field_officer' | 'public_viewer',
  });
  const [authError, setAuthError] = useState<string | null>(null);

  // Coordinate & Hazard Assessment state
  const [lat, setLat] = useState(25.1645);
  const [lon, setLon] = useState(93.0176);
  const [hazard, setHazard] = useState<Record<string, any> | null>(null);
  const [hazardLoading, setHazardLoading] = useState(false);
  const [hazardError, setHazardError] = useState<string | null>(null);

  // Grounded Gemini Assistant state
  const [question, setQuestion] = useState(
    'What observed terrain, soil, rainfall, and infrastructure exposure evidence exists at Haflong, and what data is currently missing?'
  );
  const [assistantResult, setAssistantResult] = useState<Record<string, any> | null>(null);
  const [assistantLoading, setAssistantLoading] = useState(false);
  const [assistantError, setAssistantError] = useState<string | null>(null);

  // ML Validation & Quality Gate state
  const [mlModels, setMlModels] = useState<Record<string, any> | null>(null);
  const [qualityGate, setQualityGate] = useState<Record<string, any> | null>(null);
  const [inferProbe, setInferProbe] = useState<Record<string, any> | null>(null);

  // Server-side What-If simulation
  const [simRain24, setSimRain24] = useState(145);
  const [simRain72, setSimRain72] = useState(240);
  const [simRain7d, setSimRain7d] = useState(320);
  const [simResult, setSimResult] = useState<Record<string, any> | null>(null);
  const [simLoading, setSimLoading] = useState(false);

  // Field Reports & Experimental Alerts
  const [reports, setReports] = useState<PersistedFieldReport[]>([]);
  const [alerts, setAlerts] = useState<PersistedExperimentalAlert[]>([]);
  const [reportForm, setReportForm] = useState({
    location_name: 'Jatinga–Haflong NH-27 Slope Cut',
    latitude: '25.1275',
    longitude: '93.0252',
    category: 'Slope Tension Crack / Seepage',
    severity_observation: 'Moderate',
    road_obstruction: 'partial_lane',
    description: '',
    notes: '',
  });
  const [photoFile, setPhotoFile] = useState<File | null>(null);
  const [workflowMsg, setWorkflowMsg] = useState<string | null>(null);

  const [alertForm, setAlertForm] = useState({
    title: 'Experimental Research Watch — Haflong–Jatinga Corridor',
    geographic_area: 'Haflong–Jatinga Slope Corridor, Dima Hasao',
    latitude: '25.1275',
    longitude: '93.0252',
    severity_tier: 'MODERATE' as 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL',
    severity_rationale:
      'Steep slope (>25 deg) with active monsoon seepage observations; experimental review draft only.',
  });

  // Monitoring & Regional Expansion
  const [monitoring, setMonitoring] = useState<Record<string, any> | null>(null);
  const [regions, setRegions] = useState<RegionalCoverageState[]>([]);
  const [opsLoading, setOpsLoading] = useState(false);
  const [opsError, setOpsError] = useState<string | null>(null);

  const loadHazard = async (targetLat: number, targetLon: number) => {
    setHazardLoading(true);
    setHazardError(null);
    try {
      const res = await environmentApi.assessHazard(targetLat, targetLon, 5);
      setHazard(res);
    } catch (err) {
      setHazardError(err instanceof Error ? err.message : 'Unable to reach /api/v1/hazard/assess');
    } finally {
      setHazardLoading(false);
    }
  };

  const refreshOperationalData = async () => {
    setOpsLoading(true);
    setOpsError(null);
    try {
      const [bs, qg, ml, mon, reg, rpts, alts] = await Promise.allSettled([
        environmentApi.getAuthBootstrapStatus(),
        environmentApi.getQualityGate(),
        environmentApi.getMlModels(),
        environmentApi.getMonitoringStatus(),
        environmentApi.getRegions(),
        environmentApi.listFieldReports(),
        environmentApi.listExperimentalAlerts(),
      ]);
      const failures: string[] = [];
      if (bs.status === 'fulfilled') {
        setBootstrap(bs.value);
        if (bs.value.needs_admin_claim) {
          setAuthMode('claim');
        } else {
          setAuthMode((m) => (m === 'claim' ? 'login' : m));
        }
      } else {
        failures.push('auth bootstrap');
      }
      if (qg.status === 'fulfilled') setQualityGate(qg.value);
      else failures.push('quality gate');
      if (ml.status === 'fulfilled') setMlModels(ml.value);
      else failures.push('ML registry');
      if (mon.status === 'fulfilled') setMonitoring(mon.value);
      else failures.push('monitoring status');
      if (reg.status === 'fulfilled') setRegions(reg.value.states || []);
      else failures.push('regional coverage');
      if (rpts.status === 'fulfilled') setReports(rpts.value.items || []);
      else failures.push('field reports');
      if (alts.status === 'fulfilled') setAlerts(alts.value.items || []);
      else failures.push('experimental alerts');

      if (failures.length > 0) {
        setOpsError(`Partial backend data load failure (${failures.join(', ')}).`);
      }
    } catch (err) {
      setOpsError(err instanceof Error ? err.message : 'Unable to refresh backend operational datasets.');
    } finally {
      setOpsLoading(false);
    }
  };

  useEffect(() => {
    loadHazard(lat, lon);
    refreshOperationalData();
  }, []);

  const handleAuthSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAuthError(null);
    try {
      let res;
      if (authMode === 'claim') {
        res = await environmentApi.claimAdmin({
          username: authForm.username,
          email: authForm.email,
          full_name: authForm.full_name,
          password: authForm.password,
        });
      } else if (authMode === 'register') {
        res = await environmentApi.register(authForm);
      } else {
        res = await environmentApi.login(authForm.username, authForm.password);
      }
      setAuthToken(res.access_token);
      setCurrentUser(res.user);
      setAuthForm((f) => ({ ...f, password: '' }));
      refreshOperationalData();
    } catch (err) {
      setAuthError(err instanceof Error ? err.message : 'Authentication failed');
    }
  };

  const handleAskAssistant = async (e: React.FormEvent) => {
    e.preventDefault();
    setAssistantLoading(true);
    setAssistantError(null);
    try {
      const res = await environmentApi.askAssistant(question, lat, lon, 5);
      setAssistantResult(res);
    } catch (err) {
      setAssistantError(err instanceof Error ? err.message : 'Assistant request failed');
    } finally {
      setAssistantLoading(false);
    }
  };

  const handleRunSimulation = async (e: React.FormEvent) => {
    e.preventDefault();
    setSimLoading(true);
    try {
      const res = await environmentApi.simulateWhatIf({
        lat,
        lon,
        hypothetical_rain_24h_mm: simRain24,
        hypothetical_rain_72h_mm: simRain72,
        hypothetical_antecedent_7d_mm: simRain7d,
        radius_km: 5,
      });
      setSimResult(res);
    } catch (err) {
      setWorkflowMsg(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      setSimLoading(false);
    }
  };

  const handleSubmitFieldReport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authToken) {
      setWorkflowMsg('Sign in as a Field Officer, Research Analyst, or Admin to submit field reports.');
      return;
    }
    setWorkflowMsg(null);
    try {
      const fd = new FormData();
      fd.append('location_name', reportForm.location_name);
      fd.append('latitude', reportForm.latitude);
      fd.append('longitude', reportForm.longitude);
      fd.append('observed_at_utc', new Date().toISOString());
      fd.append('category', reportForm.category);
      fd.append('severity_observation', reportForm.severity_observation);
      fd.append('road_obstruction', reportForm.road_obstruction);
      fd.append('description', reportForm.description);
      if (reportForm.notes) fd.append('notes', reportForm.notes);
      if (photoFile) fd.append('photo', photoFile);

      await environmentApi.createFieldReport(fd, authToken);
      setReportForm((f) => ({ ...f, description: '', notes: '' }));
      setPhotoFile(null);
      await refreshOperationalData();
      setWorkflowMsg('Field report persisted to database with status: pending review.');
    } catch (err) {
      setWorkflowMsg(err instanceof Error ? err.message : 'Failed to persist field report');
    }
  };

  const handleReviewReport = async (reportId: number, status: 'verified' | 'rejected') => {
    if (!authToken) return;
    try {
      await environmentApi.reviewFieldReport(reportId, status, `Reviewed via GEOS 2.0 Hub (${status})`, authToken);
      await refreshOperationalData();
      setWorkflowMsg(`Field report #${reportId} marked as ${status}.`);
    } catch (err) {
      setWorkflowMsg(err instanceof Error ? err.message : 'Review failed');
    }
  };

  const handleCreateAlert = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!authToken) {
      setWorkflowMsg('Sign in as Research Analyst or Admin to draft experimental alerts.');
      return;
    }
    try {
      await environmentApi.createExperimentalAlert(
        {
          title: alertForm.title,
          geographic_area: alertForm.geographic_area,
          latitude: parseFloat(alertForm.latitude),
          longitude: parseFloat(alertForm.longitude),
          severity_tier: alertForm.severity_tier,
          severity_rationale: alertForm.severity_rationale,
          inspection_priorities: [
            'Inspect slope cut drainage along mapped OSM road corridor',
            'Verify antecedent rainfall & pending field observations',
          ],
        },
        authToken
      );
      await refreshOperationalData();
      setWorkflowMsg('Experimental research draft alert created (not an official public warning).');
    } catch (err) {
      setWorkflowMsg(err instanceof Error ? err.message : 'Alert creation failed');
    }
  };

  const handleReviewAlert = async (
    alertId: number,
    status: 'approved_internal' | 'rejected' | 'archived'
  ) => {
    if (!authToken) return;
    try {
      await environmentApi.reviewExperimentalAlert(alertId, status, `Updated to ${status}`, authToken);
      await refreshOperationalData();
      setWorkflowMsg(`Experimental alert #${alertId} status updated to ${status}.`);
    } catch (err) {
      setWorkflowMsg(err instanceof Error ? err.message : 'Alert review failed');
    }
  };

  const handleDryRunNotify = async (alertId: number) => {
    if (!authToken) return;
    try {
      await environmentApi.dryRunAlertNotify(alertId, 'Dima Hasao Research Review Team', authToken);
      await refreshOperationalData();
      setWorkflowMsg(`Dry-run notification logged for alert #${alertId} (zero public dispatch).`);
    } catch (err) {
      setWorkflowMsg(err instanceof Error ? err.message : 'Dry-run failed');
    }
  };

  const shapChartData =
    mlModels?.exploratory_research_benchmark?.model_a_static_susceptibility
      ?.clean_terrain_soil_ablation?.models?.xgboost?.shap_top_features || [];

  const rfClean =
    mlModels?.exploratory_research_benchmark?.model_a_static_susceptibility
      ?.clean_terrain_soil_ablation?.models?.random_forest?.oof_metrics;
  const xgbClean =
    mlModels?.exploratory_research_benchmark?.model_a_static_susceptibility
      ?.clean_terrain_soil_ablation?.models?.xgboost?.oof_metrics;
  const biasDelta =
    mlModels?.exploratory_research_benchmark?.model_a_static_susceptibility
      ?.corridor_proxy_leakage_diagnostic?.measured_corridor_bias_inflation;

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-8 select-text">
      {/* Page Heading & Scientific Status Bar */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-4 border-b border-slate-800 pb-4">
        <div>
          <p className="text-xs text-slate-400 font-mono">
            Dima Hasao Pilot · Assam, India · Research & Decision-Support Platform
          </p>
          <h2 className="text-2xl font-bold text-slate-100 tracking-tight mt-1">
            GeoResilience-NER 2.0 Verified Research Hub
          </h2>
          <p className="text-sm text-slate-400 mt-1 max-w-3xl">
            Live backend environmental sampling, spatial-block ML validation gate, server-side What-If stress testing,
            authenticated field reporting, experimental alert governance, and 8-state Northeast India expansion status.
          </p>
        </div>

        <div className="flex items-center gap-3 text-xs font-mono tabular-nums text-slate-300 shrink-0">
          <span>
            ML Gate:{' '}
            <strong className="text-amber-400">
              {qualityGate?.overall_ml_ready ? 'READY' : `BLOCKED (${qualityGate?.passed_checks ?? 6}/${qualityGate?.total_checks ?? 13})`}
            </strong>
          </span>
          <span aria-hidden="true" className="text-slate-600">·</span>
          <span>
            Probability: <strong className="text-slate-200">null</strong>
          </span>
          <span aria-hidden="true" className="text-slate-600">·</span>
          <span>
            Session:{' '}
            <strong className={currentUser ? 'text-emerald-400' : 'text-slate-400'}>
              {currentUser ? `${currentUser.username} (${currentUser.role})` : 'Read-Only Viewer'}
            </strong>
          </span>
        </div>
      </div>

      {/* Segmented Workspace Navigation */}
      <div className="flex flex-wrap items-center gap-1.5 p-1 bg-slate-900/90 border border-slate-800 rounded-lg">
        {(
          [
            ['hazard-inspector', 'Hazard, Soil & Gemini', CloudRain],
            ['ml-validation', 'ML Gate & SHAP Benchmark', Database],
            ['what-if', 'Server What-If Stress Test', SlidersHorizontal],
            ['field-reports', 'Auth & Field Reports', Upload],
            ['alerts-workflow', 'Experimental Alerts', ClipboardCheck],
            ['monitoring-regions', 'Monitoring & 8-State NER', Globe2],
          ] as const
        ).map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-3 py-2 rounded-md text-xs font-medium whitespace-nowrap transition-colors ${
              tab === id
                ? 'bg-cyan-600 text-white'
                : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/80'
            }`}
          >
            <Icon className="w-3.5 h-3.5" />
            <span>{label}</span>
          </button>
        ))}
      </div>

      {opsError && (
        <div className="px-4 py-2.5 rounded-lg bg-rose-950/30 border border-rose-700/50 text-xs text-rose-200 flex items-center justify-between gap-3">
          <span>{opsError}</span>
          <button
            type="button"
            disabled={opsLoading}
            onClick={refreshOperationalData}
            className="px-2.5 py-1 rounded bg-rose-900/60 hover:bg-rose-800 text-rose-100 font-semibold whitespace-nowrap"
          >
            {opsLoading ? 'Retrying...' : 'Retry Sync'}
          </button>
        </div>
      )}

      {workflowMsg && (
        <div className="px-4 py-2.5 rounded-lg bg-slate-900 border border-cyan-500/40 text-xs text-cyan-200 flex items-center justify-between gap-3">
          <span>{workflowMsg}</span>
          <button
            type="button"
            onClick={() => setWorkflowMsg(null)}
            className="text-slate-400 hover:text-slate-200 text-xs"
          >
            Dismiss
          </button>
        </div>
      )}

      {/* TAB 1: LIVE HAZARD, SOIL, EXPOSURE & GROUNDED GEMINI ASSISTANT */}
      {tab === 'hazard-inspector' && (
        <div className="space-y-6">
          <div className="p-4 rounded-xl bg-slate-900/70 border border-slate-800 flex flex-wrap items-end justify-between gap-4">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <label className="block text-xs text-slate-400 mb-1">Latitude (WGS84)</label>
                <input
                  type="number"
                  step="0.0001"
                  value={lat}
                  onChange={(e) => setLat(parseFloat(e.target.value) || 0)}
                  className="w-36 px-3 py-2 rounded-md bg-slate-950 border border-slate-700 text-xs font-mono tabular-nums text-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs text-slate-400 mb-1">Longitude (WGS84)</label>
                <input
                  type="number"
                  step="0.0001"
                  value={lon}
                  onChange={(e) => setLon(parseFloat(e.target.value) || 0)}
                  className="w-36 px-3 py-2 rounded-md bg-slate-950 border border-slate-700 text-xs font-mono tabular-nums text-slate-100"
                />
              </div>
              <button
                type="button"
                onClick={() => loadHazard(lat, lon)}
                disabled={hazardLoading}
                className="px-4 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center gap-2 transition"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${hazardLoading ? 'animate-spin' : ''}`} />
                <span>Query Live Rasters</span>
              </button>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              {DIMA_HASAO_PRESETS.map((pt) => (
                <button
                  key={pt.label}
                  type="button"
                  onClick={() => {
                    setLat(pt.lat);
                    setLon(pt.lon);
                    loadHazard(pt.lat, pt.lon);
                  }}
                  className="px-2.5 py-1.5 rounded-md bg-slate-950 border border-slate-700 hover:border-cyan-500 text-xs text-slate-300 transition"
                >
                  {pt.label}
                </button>
              ))}
            </div>
          </div>

          {hazardError && (
            <div className="p-4 rounded-xl bg-rose-950/30 border border-rose-700/50 text-sm text-rose-200">
              {hazardError}
            </div>
          )}

          {hazard && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              {/* Column 1: Terrain, Geomorphometry & SoilGrids 2.0 */}
              <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-100">Terrain & SoilGrids 2.0</h3>
                  <span className="text-xs font-mono text-slate-400">EPSG:32646</span>
                </div>

                <dl className="grid grid-cols-2 gap-y-2.5 gap-x-3 text-xs font-mono tabular-nums">
                  <div>
                    <dt className="text-slate-500">Elevation</dt>
                    <dd className="text-slate-100 font-semibold">{hazard.terrain_and_soil_context?.elevation_m ?? 'null'} m</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Slope (Horn)</dt>
                    <dd className="text-amber-300 font-semibold">{hazard.terrain_and_soil_context?.slope_deg ?? 'null'}°</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">TRI / TWI</dt>
                    <dd className="text-slate-200">
                      {hazard.terrain_and_soil_context?.geomorphometry?.tri_m ?? '—'} m / {hazard.terrain_and_soil_context?.geomorphometry?.twi ?? '—'}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Drainage Dist.</dt>
                    <dd className="text-slate-200">{hazard.terrain_and_soil_context?.geomorphometry?.distance_to_drainage_m ?? '—'} m</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Clay (0–5 cm)</dt>
                    <dd className="text-slate-200">{hazard.terrain_and_soil_context?.soilgrids_2_0?.clay_0_5cm_pct ?? '—'}%</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Bulk Density</dt>
                    <dd className="text-slate-200">{hazard.terrain_and_soil_context?.soilgrids_2_0?.bulk_density_0_5cm_g_cm3 ?? '—'} g/cm³</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">NDVI (2024 Ref)</dt>
                    <dd className="text-emerald-300">{hazard.terrain_and_soil_context?.vegetation_ndvi?.ndvi_premonsoon_2024 ?? '—'}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">WorldCover 2021</dt>
                    <dd className="text-slate-200 truncate">{hazard.terrain_and_soil_context?.land_cover_2021 ?? '—'}</dd>
                  </div>
                </dl>

                <p className="text-xs text-slate-400 border-t border-slate-800 pt-3 leading-relaxed">
                  Geology 1:50k lithology/faults: <strong className="text-amber-300">Unavailable (GSI NGDR/Bhukosh restricted)</strong>.
                  Geotechnical cohesion, friction angle, and Factor of Safety remain <span className="font-mono">null</span>.
                </p>
              </div>

              {/* Column 2: Observed Rainfall vs Forecast Rainfall & Priority */}
              <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
                <h3 className="text-sm font-semibold text-slate-100">Rainfall Observations vs Forecast</h3>

                <div className="space-y-3 text-xs">
                  <div className="pb-3 border-b border-slate-800">
                    <div className="text-slate-400 font-medium">Observed Rainfall (NASA GPM IMERG)</div>
                    <div className="mt-1 font-mono tabular-nums text-slate-100">
                      Latest date: {hazard.observed_rainfall?.latest_observation_date ?? 'N/A'} · 24h:{' '}
                      {hazard.observed_rainfall?.rainfall_24h_mm ?? 'null'} mm · 72h:{' '}
                      {hazard.observed_rainfall?.rainfall_72h_mm ?? 'null'} mm
                    </div>
                    {hazard.observed_rainfall?.is_stale && (
                      <div className="mt-1 text-amber-400">
                        Stale archive warning ({hazard.observed_rainfall?.observation_age_days} days old — NASA Earthdata Login required for 2024–2026 HDF5 updates).
                      </div>
                    )}
                  </div>

                  <div className="pb-3 border-b border-slate-800">
                    <div className="text-slate-400 font-medium">
                      Experimental Forecast (NOAA GFS 0.25° — NOT Measured)
                    </div>
                    <div className="mt-1 font-mono tabular-nums text-sky-300">
                      24h: {hazard.forecast_rainfall?.rain_24h_outlook_mm ?? 'null'} mm · 48h:{' '}
                      {hazard.forecast_rainfall?.rain_48h_outlook_mm ?? 'null'} mm · 72h:{' '}
                      {hazard.forecast_rainfall?.rain_72h_outlook_mm ?? 'null'} mm
                    </div>
                    <div className="mt-1 text-slate-500 font-mono text-[11px]">
                      Init: {hazard.forecast_rainfall?.init_time_utc ?? 'N/A'} · RH:{' '}
                      {hazard.forecast_rainfall?.rh_2m_mean_pct ?? '—'}%
                    </div>
                  </div>

                  <div>
                    <div className="text-slate-400 font-medium">Experimental Screening Tier</div>
                    <div className="mt-1 font-mono text-amber-300 font-semibold">
                      {hazard.response_priority?.inspection_priority_tier}
                    </div>
                    <div className="mt-1 text-slate-400">
                      Static ML Probability: <strong className="font-mono text-slate-200">null</strong> (model not validated).
                    </div>
                  </div>
                </div>
              </div>

              {/* Column 3: Real OSM Spatial Infrastructure Exposure */}
              <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-100">OSM Infrastructure Proximity (5 km)</h3>
                  <span className="text-xs font-mono text-slate-400">ODbL 1.0</span>
                </div>

                <dl className="grid grid-cols-3 gap-2.5 text-xs font-mono tabular-nums">
                  <div>
                    <dt className="text-slate-500">Roads</dt>
                    <dd className="text-slate-100 font-semibold text-base">{hazard.infrastructure_exposure?.counts?.road_segments ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Railways</dt>
                    <dd className="text-slate-100 font-semibold text-base">{hazard.infrastructure_exposure?.counts?.railway_segments ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Bridges</dt>
                    <dd className="text-slate-100 font-semibold text-base">{hazard.infrastructure_exposure?.counts?.bridges ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Settlements</dt>
                    <dd className="text-slate-100 font-semibold text-base">{hazard.infrastructure_exposure?.counts?.settlements ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Hospitals</dt>
                    <dd className="text-slate-100 font-semibold text-base">{hazard.infrastructure_exposure?.counts?.hospitals_health ?? 0}</dd>
                  </div>
                  <div>
                    <dt className="text-slate-500">Schools</dt>
                    <dd className="text-slate-100 font-semibold text-base">{hazard.infrastructure_exposure?.counts?.schools ?? 0}</dd>
                  </div>
                </dl>

                {hazard.infrastructure_exposure?.nearest_assets?.length > 0 && (
                  <div className="border-t border-slate-800 pt-3 space-y-1">
                    <div className="text-[11px] text-slate-400 font-medium">Nearest Mapped OSM Assets</div>
                    {hazard.infrastructure_exposure.nearest_assets.slice(0, 4).map((a: any) => (
                      <div key={a.external_id} className="flex justify-between text-xs text-slate-300 font-mono">
                        <span className="truncate pr-2">{a.name} ({a.category})</span>
                        <span className="text-slate-400 shrink-0">{a.distance_km} km</span>
                      </div>
                    ))}
                  </div>
                )}

                <p className="text-[11px] text-slate-400 leading-relaxed">
                  Estimated spatial proximity only — not observed damage or complete rural census.
                </p>
              </div>
            </div>
          )}

          {/* Grounded Gemini Assistant Panel */}
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <MessageSquareText className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-100">
                  Grounded Gemini Geospatial Explanation Assistant
                </h3>
              </div>
              <span className="text-xs font-mono text-slate-400">
                Server-side proxy · Evidence-linked · Prompt-injection guarded
              </span>
            </div>

            <form onSubmit={handleAskAssistant} className="flex flex-col sm:flex-row gap-2">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask about observed terrain, soil, rainfall, nearby roads, or missing datasets..."
                className="flex-1 px-3 py-2 rounded-md bg-slate-950 border border-slate-700 text-xs text-slate-100 focus:outline-none focus:border-cyan-500"
              />
              <button
                type="submit"
                disabled={assistantLoading}
                className="px-4 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold flex items-center justify-center gap-2 whitespace-nowrap transition"
              >
                <Send className="w-3.5 h-3.5" />
                <span>{assistantLoading ? 'Querying...' : 'Explain Evidence'}</span>
              </button>
            </form>

            {assistantError && (
              <div className="p-3 rounded-lg bg-amber-950/30 border border-amber-700/40 text-xs text-amber-200">
                {assistantError}
              </div>
            )}

            {assistantResult && (
              <div className="p-4 rounded-lg bg-slate-950 border border-slate-800 space-y-2 text-xs">
                <div className="text-slate-400 font-mono">
                  Model: {assistantResult.model} · Source: {assistantResult.source} · Landslide Probability: null
                </div>
                <div className="text-slate-200 whitespace-pre-wrap leading-relaxed">
                  {assistantResult.answer}
                </div>
                <div className="text-[11px] text-amber-300 pt-2 border-t border-slate-800">
                  {assistantResult.disclaimer}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: ML QUALITY GATE & EXPLORATORY BENCHMARK */}
      {tab === 'ml-validation' && (
        <div className="space-y-6">
          <div className="p-5 rounded-xl bg-slate-900/70 border border-amber-600/40 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-400" />
                <h3 className="text-sm font-semibold text-slate-100">
                  Production ML Deployment Gate — STRICTLY BLOCKED
                </h3>
              </div>
              <button
                type="button"
                onClick={async () => {
                  const res = await environmentApi.inferMl(lat, lon);
                  setInferProbe(res);
                }}
                className="px-3 py-1.5 rounded-md bg-slate-800 hover:bg-slate-700 text-xs font-mono text-cyan-300 border border-slate-700"
              >
                Test POST /api/v1/ml/infer
              </button>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              {qualityGate?.decision ||
                'Production model training is blocked until certified polygon/GPS positional accuracy, multi-year storm independence, deduplication, lithology/SMAP covariates, and corridor bias controls pass.'}
            </p>
            {inferProbe && (
              <pre className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-[11px] font-mono text-slate-300 overflow-x-auto">
                {JSON.stringify(
                  {
                    status: inferProbe.status,
                    model_validated: inferProbe.model_validated,
                    landslide_probability: inferProbe.landslide_probability,
                    blocking_failures: inferProbe.blocking_failures,
                  },
                  null,
                  2
                )}
              </pre>
            )}
          </div>

          {/* Exploratory RF vs XGBoost + Corridor Bias Diagnostic */}
          {rfClean && xgbClean && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
                <div>
                  <p className="text-[11px] font-mono text-amber-400">
                    EXPLORATORY RESEARCH TRACK · NOT VALIDATED FOR PRODUCTION
                  </p>
                  <h3 className="text-sm font-semibold text-slate-100 mt-1">
                    5-Fold Geographic Spatial-Block CV (Clean Terrain + SoilGrids)
                  </h3>
                </div>

                <table className="w-full text-xs font-mono tabular-nums border-collapse">
                  <thead>
                    <tr className="border-b border-slate-800 text-slate-400 text-left">
                      <th className="py-2">Metric (5 km UTM Blocks)</th>
                      <th className="py-2 text-right">Random Forest</th>
                      <th className="py-2 text-right">XGBoost (CPU)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/70 text-slate-200">
                    <tr>
                      <td className="py-2 text-slate-400">ROC-AUC</td>
                      <td className="py-2 text-right">{rfClean.roc_auc}</td>
                      <td className="py-2 text-right">{xgbClean.roc_auc}</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-400">PR-AUC</td>
                      <td className="py-2 text-right">{rfClean.pr_auc}</td>
                      <td className="py-2 text-right">{xgbClean.pr_auc}</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-400">Precision / Recall (@0.5)</td>
                      <td className="py-2 text-right">
                        {rfClean.precision_at_0_5} / {rfClean.recall_at_0_5}
                      </td>
                      <td className="py-2 text-right">
                        {xgbClean.precision_at_0_5} / {xgbClean.recall_at_0_5}
                      </td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-400">Brier Score</td>
                      <td className="py-2 text-right">{rfClean.brier_score}</td>
                      <td className="py-2 text-right">{xgbClean.brier_score}</td>
                    </tr>
                    <tr>
                      <td className="py-2 text-slate-400">Expected Calibration Error</td>
                      <td className="py-2 text-right">{rfClean.expected_calibration_error}</td>
                      <td className="py-2 text-right">{xgbClean.expected_calibration_error}</td>
                    </tr>
                  </tbody>
                </table>

                {biasDelta && (
                  <div className="p-3 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-300 space-y-1">
                    <div className="font-semibold text-amber-300">
                      Measured Corridor-Bias Leakage Inflation
                    </div>
                    <div className="font-mono tabular-nums">
                      Adding OSM road/rail distance inflates ROC-AUC by +{biasDelta.random_forest_roc_auc_delta} (RF) and +{biasDelta.xgboost_roc_auc_delta} (XGB).
                    </div>
                    <p className="text-[11px] text-slate-400">{biasDelta.scientific_interpretation}</p>
                  </div>
                )}
              </div>

              <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3">
                <div>
                  <p className="text-[11px] font-mono text-cyan-400">EXPLAINABLE AI (SHAP TREEEXPLAINER)</p>
                  <h3 className="text-sm font-semibold text-slate-100 mt-1">
                    Top Exploratory Feature Attributions (Mean |SHAP|)
                  </h3>
                </div>
                <div className="h-64 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart
                      data={shapChartData}
                      layout="vertical"
                      margin={{ top: 4, right: 16, left: 40, bottom: 4 }}
                    >
                      <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                      <XAxis type="number" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                      <YAxis dataKey="feature" type="category" width={110} tick={{ fill: '#cbd5e1', fontSize: 10 }} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', fontSize: 12 }}
                      />
                      <Bar dataKey="mean_abs_shap" fill="#06b6d4" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
                <p className="text-[11px] text-slate-400">
                  SHAP values reflect statistical association in the exploratory Positive-Unlabeled benchmark only—never physically causal geotechnical shear-strength parameters.
                </p>
              </div>
            </div>
          )}

          {/* 13-Check Quality Gate Table */}
          {qualityGate?.checks && (
            <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 overflow-x-auto">
              <h3 className="text-sm font-semibold text-slate-100 mb-3">
                13-Check Scientific Data Quality Gate Audit
              </h3>
              <table className="w-full text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 text-left">
                    <th className="py-2 pr-4">Check</th>
                    <th className="py-2 pr-4">Status</th>
                    <th className="py-2">Verified Evidence Summary</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {qualityGate.checks.map((c: any) => (
                    <tr key={c.check_id}>
                      <td className="py-2.5 pr-4 font-mono text-slate-200 whitespace-nowrap">{c.check_id}</td>
                      <td className="py-2.5 pr-4 font-mono font-semibold whitespace-nowrap">
                        <span
                          className={
                            c.status === 'PASS'
                              ? 'text-emerald-400'
                              : c.status === 'WARN'
                              ? 'text-amber-400'
                              : 'text-rose-400'
                          }
                        >
                          {c.status}
                        </span>
                      </td>
                      <td className="py-2.5 text-slate-300 leading-relaxed">{c.summary}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* TAB 3: SERVER-SIDE WHAT-IF STRESS TEST */}
      {tab === 'what-if' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <form
            onSubmit={handleRunSimulation}
            className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4"
          >
            <div>
              <p className="text-[11px] font-mono text-amber-400">HYPOTHETICAL SCENARIO · NOT A FORECAST</p>
              <h3 className="text-sm font-semibold text-slate-100 mt-1">
                Server-Side Rainfall Envelope Stress Test (/api/v1/hazard/simulate)
              </h3>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <div className="flex justify-between font-mono tabular-nums">
                  <label className="text-slate-300">Hypothetical 24h Rainfall</label>
                  <span className="text-cyan-300">{simRain24} mm</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={350}
                  value={simRain24}
                  onChange={(e) => setSimRain24(Number(e.target.value))}
                  className="w-full mt-1"
                />
              </div>

              <div>
                <div className="flex justify-between font-mono tabular-nums">
                  <label className="text-slate-300">Hypothetical 72h Cumulative</label>
                  <span className="text-cyan-300">{simRain72} mm</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={600}
                  value={simRain72}
                  onChange={(e) => setSimRain72(Number(e.target.value))}
                  className="w-full mt-1"
                />
              </div>

              <div>
                <div className="flex justify-between font-mono tabular-nums">
                  <label className="text-slate-300">Hypothetical 7-Day Antecedent</label>
                  <span className="text-cyan-300">{simRain7d} mm</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={900}
                  value={simRain7d}
                  onChange={(e) => setSimRain7d(Number(e.target.value))}
                  className="w-full mt-1"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={simLoading}
              className="px-4 py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white text-xs font-semibold transition"
            >
              {simLoading ? 'Computing on Server...' : 'Run Server-Side Hypothetical Scenario'}
            </button>
          </form>

          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 text-xs">
            <h3 className="text-sm font-semibold text-slate-100">Scenario Output & Scientific Guardrails</h3>
            {!simResult ? (
              <p className="text-slate-400">
                Adjust hypothetical rainfall inputs and execute the server-side evaluator to compare against documented IMD rainfall classes, Copernicus DEM slope steepness, and nearby real OSM assets.
              </p>
            ) : (
              <div className="space-y-3 font-mono tabular-nums">
                <div className="text-amber-300 font-semibold">{simResult.scenario_label}</div>
                <div>
                  Priority Tier:{' '}
                  <strong className="text-cyan-300">
                    {simResult.threshold_envelope_response?.inspection_priority_tier}
                  </strong>
                </div>
                <div>
                  IMD Envelope: {simResult.threshold_envelope_response?.imd_rainfall_envelope} · Slope:{' '}
                  {simResult.terrain_context?.slope_deg ?? 'N/A'}°
                </div>
                <div>
                  Validated ML Probability: <strong>null</strong> · Factor of Safety: <strong>null</strong>
                </div>
                <div className="text-slate-300">
                  Nearby Mapped OSM Assets (5 km):{' '}
                  {simResult.potentially_exposed_mapped_infrastructure?.counts?.road_segments ?? 0} roads,{' '}
                  {simResult.potentially_exposed_mapped_infrastructure?.counts?.bridges ?? 0} bridges,{' '}
                  {simResult.potentially_exposed_mapped_infrastructure?.counts?.settlements ?? 0} settlements,{' '}
                  {simResult.potentially_exposed_mapped_infrastructure?.counts?.hospitals_health ?? 0} hospitals
                </div>
                <p className="font-sans text-slate-400 border-t border-slate-800 pt-2">
                  {simResult.scientific_disclaimer}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: AUTHENTICATION & FIELD OFFICER REPORTING */}
      {tab === 'field-reports' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Auth / RBAC Panel */}
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Lock className="w-4 h-4 text-cyan-400" />
                <h3 className="text-sm font-semibold text-slate-100">Role-Based Access Control</h3>
              </div>
              {currentUser && (
                <button
                  type="button"
                  onClick={() => {
                    setAuthToken(null);
                    setCurrentUser(null);
                    setAuthError(null);
                    setAuthMode('login');
                  }}
                  className="text-xs text-rose-400 hover:underline"
                >
                  Sign Out
                </button>
              )}
            </div>

            {currentUser ? (
              <div className="space-y-2 text-xs font-mono">
                <div className="text-emerald-400 font-semibold">Authenticated (In-Memory Bearer Session)</div>
                <div>User: {currentUser.username} ({currentUser.full_name})</div>
                <div>Role: {currentUser.role}</div>
                <p className="font-sans text-slate-400 pt-2">
                  Bearer tokens are held strictly in React state memory (never stored in browser localStorage).
                </p>
              </div>
            ) : (
              <form onSubmit={handleAuthSubmit} className="space-y-3 text-xs">
                <div className="flex gap-1.5">
                  {bootstrap?.needs_admin_claim && (
                    <button
                      type="button"
                      onClick={() => setAuthMode('claim')}
                      className={`px-2.5 py-1 rounded text-xs ${authMode === 'claim' ? 'bg-amber-600 text-white' : 'bg-slate-800 text-slate-300'}`}
                    >
                      Claim First Admin
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setAuthMode('login')}
                    className={`px-2.5 py-1 rounded text-xs ${authMode === 'login' ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-300'}`}
                  >
                    Sign In
                  </button>
                  <button
                    type="button"
                    onClick={() => setAuthMode('register')}
                    className={`px-2.5 py-1 rounded text-xs ${authMode === 'register' ? 'bg-cyan-600 text-white' : 'bg-slate-800 text-slate-300'}`}
                  >
                    Register
                  </button>
                </div>

                {authMode === 'claim' && (
                  <p className="text-[11px] text-amber-300">
                    First-run setup: claim the initial Administrator account (locks permanently once claimed).
                  </p>
                )}

                <input
                  type="text"
                  required
                  placeholder="Username"
                  value={authForm.username}
                  onChange={(e) => setAuthForm({ ...authForm, username: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
                />
                {authMode !== 'login' && (
                  <>
                    <input
                      type="email"
                      required
                      placeholder="Email"
                      value={authForm.email}
                      onChange={(e) => setAuthForm({ ...authForm, email: e.target.value })}
                      className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
                    />
                    <input
                      type="text"
                      required
                      placeholder="Full Name"
                      value={authForm.full_name}
                      onChange={(e) => setAuthForm({ ...authForm, full_name: e.target.value })}
                      className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
                    />
                  </>
                )}
                {authMode === 'register' && (
                  <select
                    value={authForm.requested_role}
                    onChange={(e) =>
                      setAuthForm({
                        ...authForm,
                        requested_role: e.target.value as 'field_officer' | 'public_viewer',
                      })
                    }
                    className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
                  >
                    <option value="field_officer">Field Officer</option>
                    <option value="public_viewer">Public Read-Only Viewer</option>
                  </select>
                )}
                <input
                  type="password"
                  required
                  placeholder="Password (min 8 chars)"
                  value={authForm.password}
                  onChange={(e) => setAuthForm({ ...authForm, password: e.target.value })}
                  className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
                />

                {authError && <div className="text-rose-400">{authError}</div>}

                <button
                  type="submit"
                  className="w-full py-2 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white font-semibold transition"
                >
                  {authMode === 'claim' ? 'Create Initial Admin' : authMode === 'register' ? 'Create Account' : 'Sign In'}
                </button>
              </form>
            )}
          </div>

          {/* Field Report Submission Form (Real Multipart Photo Upload) */}
          <form
            onSubmit={handleSubmitFieldReport}
            className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 text-xs"
          >
            <h3 className="text-sm font-semibold text-slate-100">Submit Authenticated Field Report</h3>
            <input
              type="text"
              required
              placeholder="Location Name"
              value={reportForm.location_name}
              onChange={(e) => setReportForm({ ...reportForm, location_name: e.target.value })}
              className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
            />
            <div className="grid grid-cols-2 gap-2">
              <input
                type="number"
                step="0.0001"
                required
                placeholder="Latitude"
                value={reportForm.latitude}
                onChange={(e) => setReportForm({ ...reportForm, latitude: e.target.value })}
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 font-mono text-slate-100"
              />
              <input
                type="number"
                step="0.0001"
                required
                placeholder="Longitude"
                value={reportForm.longitude}
                onChange={(e) => setReportForm({ ...reportForm, longitude: e.target.value })}
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 font-mono text-slate-100"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select
                value={reportForm.severity_observation}
                onChange={(e) => setReportForm({ ...reportForm, severity_observation: e.target.value })}
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
              >
                <option value="Low">Low</option>
                <option value="Moderate">Moderate</option>
                <option value="High">High</option>
                <option value="Critical">Critical</option>
              </select>
              <select
                value={reportForm.road_obstruction}
                onChange={(e) => setReportForm({ ...reportForm, road_obstruction: e.target.value })}
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
              >
                <option value="none">No Road Obstruction</option>
                <option value="partial_lane">Partial Lane Blocked</option>
                <option value="full_closure">Full Road Closure</option>
              </select>
            </div>
            <textarea
              required
              rows={3}
              placeholder="Field observation details (slope cracks, seepage, debris volume, culvert status)..."
              value={reportForm.description}
              onChange={(e) => setReportForm({ ...reportForm, description: e.target.value })}
              className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
            />
            <div>
              <label className="block text-slate-400 mb-1">Optional Photo Evidence (JPEG/PNG/WebP, max 5 MB)</label>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(e) => setPhotoFile(e.target.files?.[0] || null)}
                className="w-full text-slate-300"
              />
            </div>
            <button
              type="submit"
              disabled={!authToken}
              className="w-full py-2 rounded-md bg-cyan-600 disabled:bg-slate-800 disabled:text-slate-500 hover:bg-cyan-500 text-white font-semibold transition"
            >
              {authToken ? 'Persist Field Report' : 'Sign In to Submit Report'}
            </button>
          </form>

          {/* Persisted Reports Registry */}
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 text-xs">
            <h3 className="text-sm font-semibold text-slate-100">
              Database Field Reports ({reports.length})
            </h3>
            {reports.length === 0 ? (
              <p className="text-slate-400">
                No persisted field reports yet. Authenticated Field Officers can log geotagged observations here.
              </p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {reports.map((r) => (
                  <div key={r.id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-100">{r.location_name}</span>
                      <span className="font-mono text-[11px] text-amber-300">{r.verification_status}</span>
                    </div>
                    <div className="font-mono text-[11px] text-slate-400 tabular-nums">
                      {r.latitude.toFixed(4)}°N, {r.longitude.toFixed(4)}°E · {r.severity_observation} · by {r.submitted_by_username}
                    </div>
                    <p className="text-slate-300">{r.description}</p>
                    {r.photo_url && (
                      <a
                        href={r.photo_url}
                        target="_blank"
                        rel="noreferrer"
                        className="inline-block text-cyan-400 hover:underline font-mono text-[11px]"
                      >
                        View Uploaded Photo ({r.photo_metadata?.mime_type})
                      </a>
                    )}
                    {currentUser && (currentUser.role === 'admin' || currentUser.role === 'research_analyst') && (
                      <div className="flex gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => handleReviewReport(r.id, 'verified')}
                          className="px-2 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-[11px]"
                        >
                          Verify
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReviewReport(r.id, 'rejected')}
                          className="px-2 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white text-[11px]"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 5: EXPERIMENTAL ALERT & RESPONSE WORKFLOW */}
      {tab === 'alerts-workflow' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <form
            onSubmit={handleCreateAlert}
            className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 text-xs"
          >
            <div>
              <p className="text-[11px] font-mono text-amber-400">
                EXPERIMENTAL RESEARCH DRAFTS · NEVER OFFICIAL GOVERNMENT WARNINGS
              </p>
              <h3 className="text-sm font-semibold text-slate-100 mt-1">
                Create Evidence-Linked Research Alert Draft
              </h3>
            </div>

            <input
              type="text"
              required
              value={alertForm.title}
              onChange={(e) => setAlertForm({ ...alertForm, title: e.target.value })}
              className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
            />
            <input
              type="text"
              required
              value={alertForm.geographic_area}
              onChange={(e) => setAlertForm({ ...alertForm, geographic_area: e.target.value })}
              className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
            />
            <div className="grid grid-cols-3 gap-2">
              <input
                type="number"
                step="0.0001"
                value={alertForm.latitude}
                onChange={(e) => setAlertForm({ ...alertForm, latitude: e.target.value })}
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 font-mono text-slate-100"
              />
              <input
                type="number"
                step="0.0001"
                value={alertForm.longitude}
                onChange={(e) => setAlertForm({ ...alertForm, longitude: e.target.value })}
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 font-mono text-slate-100"
              />
              <select
                value={alertForm.severity_tier}
                onChange={(e) =>
                  setAlertForm({
                    ...alertForm,
                    severity_tier: e.target.value as 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL',
                  })
                }
                className="px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
              >
                <option value="LOW">LOW</option>
                <option value="MODERATE">MODERATE</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <textarea
              required
              rows={3}
              value={alertForm.severity_rationale}
              onChange={(e) => setAlertForm({ ...alertForm, severity_rationale: e.target.value })}
              className="w-full px-3 py-2 rounded bg-slate-950 border border-slate-700 text-slate-100"
            />
            <button
              type="submit"
              disabled={!currentUser || !['admin', 'research_analyst'].includes(currentUser.role)}
              className="w-full py-2 rounded-md bg-cyan-600 disabled:bg-slate-800 disabled:text-slate-500 hover:bg-cyan-500 text-white font-semibold"
            >
              {currentUser && ['admin', 'research_analyst'].includes(currentUser.role)
                ? 'Save Experimental Draft Alert'
                : 'Sign In as Analyst/Admin (Tab 4) to Draft Alerts'}
            </button>
          </form>

          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 text-xs">
            <h3 className="text-sm font-semibold text-slate-100">
              Experimental Alert Review Queue ({alerts.length})
            </h3>
            {alerts.length === 0 ? (
              <p className="text-slate-400">No experimental research alerts created yet.</p>
            ) : (
              <div className="space-y-3 max-h-96 overflow-y-auto pr-1">
                {alerts.map((a) => (
                  <div key={a.id} className="p-3 rounded-lg bg-slate-950 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-100">{a.title}</span>
                      <span className="font-mono text-amber-300">{a.status}</span>
                    </div>
                    <div className="font-mono text-[11px] text-slate-400">
                      {a.classification} · {a.severity_tier} · {a.geographic_area}
                    </div>
                    <p className="text-slate-300">{a.severity_rationale}</p>
                    <div className="text-[11px] text-slate-400 font-mono">
                      Dry-run audit entries: {a.dry_run_notifications.length}
                    </div>
                    {currentUser && ['admin', 'research_analyst'].includes(currentUser.role) && (
                      <div className="flex flex-wrap gap-2 pt-1">
                        <button
                          type="button"
                          onClick={() => handleReviewAlert(a.id, 'approved_internal')}
                          className="px-2 py-1 rounded bg-emerald-700 hover:bg-emerald-600 text-white text-[11px]"
                        >
                          Approve Internal
                        </button>
                        <button
                          type="button"
                          onClick={() => handleReviewAlert(a.id, 'rejected')}
                          className="px-2 py-1 rounded bg-rose-700 hover:bg-rose-600 text-white text-[11px]"
                        >
                          Reject
                        </button>
                        <button
                          type="button"
                          onClick={() => handleDryRunNotify(a.id)}
                          className="px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 text-[11px]"
                        >
                          Log Dry-Run Notification
                        </button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 6: AUTOMATED MONITORING & 8-STATE REGIONAL EXPANSION */}
      {tab === 'monitoring-regions' && (
        <div className="space-y-6">
          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 space-y-3 text-xs">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Automated Environmental Monitoring & Freshness
                </h3>
                <p className="text-slate-400 mt-0.5">
                  Tracks IMERG observation staleness and NOAA GFS CPU-only forecast updates. Never claims zero-latency real-time telemetry.
                </p>
              </div>
              {currentUser && ['admin', 'research_analyst'].includes(currentUser.role) && (
                <button
                  type="button"
                  onClick={async () => {
                    if (!authToken) return;
                    await environmentApi.triggerMonitoringRun(authToken, false);
                    setWorkflowMsg('Monitoring freshness cycle recorded.');
                    refreshOperationalData();
                  }}
                  className="px-3 py-1.5 rounded-md bg-cyan-600 hover:bg-cyan-500 text-white font-semibold"
                >
                  Run Freshness Check
                </button>
              )}
            </div>

            {monitoring?.latest_run && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-3 pt-2 font-mono tabular-nums">
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-slate-500 text-[11px]">Latest Cycle Status</div>
                  <div className="text-amber-300 font-semibold mt-1">{monitoring.latest_run.status}</div>
                </div>
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-slate-500 text-[11px]">IMERG Latest Observed</div>
                  <div className="text-slate-100 font-semibold mt-1">
                    {monitoring.latest_run.observed_rainfall_latest_date ?? 'N/A'}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-slate-500 text-[11px]">NOAA GFS Forecast Init</div>
                  <div className="text-sky-300 font-semibold mt-1 truncate">
                    {monitoring.latest_run.forecast_init_time_utc ?? 'N/A'}
                  </div>
                </div>
                <div className="p-3 rounded-lg bg-slate-950 border border-slate-800">
                  <div className="text-slate-500 text-[11px]">Recorded Runs</div>
                  <div className="text-slate-100 font-semibold mt-1">{monitoring.recent_runs?.length ?? 1}</div>
                </div>
              </div>
            )}
          </div>

          <div className="p-5 rounded-xl bg-slate-900/70 border border-slate-800 overflow-x-auto">
            <div className="flex items-center justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-slate-100">
                  Phase O — Eight-State Northeast India Regional Expansion Readiness
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Regions are listed transparently even where predictive models or environmental data are not yet available.
                </p>
              </div>
              <Shield className="w-4 h-4 text-cyan-400 shrink-0" />
            </div>

            <table className="w-full text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 text-left">
                  <th className="py-2 pr-4">State</th>
                  <th className="py-2 pr-4">Pilot Focus</th>
                  <th className="py-2 pr-4">Configured</th>
                  <th className="py-2 pr-4">Env Data</th>
                  <th className="py-2 pr-4">Inventory</th>
                  <th className="py-2 pr-4">Model Validated</th>
                  <th className="py-2">Monitoring</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70 font-mono">
                {regions.map((s) => (
                  <tr key={s.state_code}>
                    <td className="py-2.5 pr-4 font-sans font-semibold text-slate-100">{s.state_name}</td>
                    <td className="py-2.5 pr-4 font-sans text-slate-300">{s.pilot_district || 'Pending selection'}</td>
                    <td className="py-2.5 pr-4">
                      {s.region_configured ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-slate-600" />}
                    </td>
                    <td className="py-2.5 pr-4">
                      {s.environmental_data_available ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-slate-600" />}
                    </td>
                    <td className="py-2.5 pr-4">
                      {s.landslide_inventory_available ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <XCircle className="w-4 h-4 text-slate-600" />}
                    </td>
                    <td className="py-2.5 pr-4">
                      {s.model_validated ? (
                        <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                      ) : (
                        <span className="text-amber-400">Blocked</span>
                      )}
                    </td>
                    <td className="py-2.5">
                      {s.experimental_monitoring_active ? (
                        <span className="text-cyan-300">Experimental</span>
                      ) : (
                        <span className="text-slate-500">Inactive</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
