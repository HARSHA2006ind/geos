import React from 'react';
import {
  Mountain,
  CloudRain,
  Trees,
  Compass,
  AlertCircle,
  RefreshCw,
  CheckCircle2,
  MapPin,
  Info,
} from 'lucide-react';
import { PointEnvironmentResponse } from '../../services/environmentApi';

export const DIMA_HASAO_PRESETS = [
  { label: 'Haflong Town', lat: 25.1645, lon: 93.0176 },
  { label: 'Jatinga Ridge', lat: 25.1275, lon: 93.0252 },
  { label: 'Maibang Valley', lat: 25.3025, lon: 93.1335 },
  { label: 'Umrangso', lat: 25.5128, lon: 92.7351 },
];

interface PilotEnvironmentPanelProps {
  data: PointEnvironmentResponse | null;
  loading: boolean;
  error: string | null;
  onSelectCoordinate: (lat: number, lon: number) => void;
  onFocusPilot?: () => void;
}

export const PilotEnvironmentPanel: React.FC<PilotEnvironmentPanelProps> = ({
  data,
  loading,
  error,
  onSelectCoordinate,
  onFocusPilot,
}) => {
  return (
    <div className="bg-[#0f172a] border border-cyan-500/40 rounded-xl p-3.5 shadow-xl space-y-3">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-emerald-950/80 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0">
            <CheckCircle2 className="w-4 h-4" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Dima Hasao Pilot — Verified Environmental Inspector
              </h3>
              <span className="px-1.5 py-0.5 rounded bg-emerald-950/90 text-emerald-300 border border-emerald-500/40 text-[9px] font-mono uppercase">
                Real Satellite Data
              </span>
            </div>
            <p className="text-[10px] text-slate-400">
              Click anywhere on the map inside the highlighted Dima Hasao boundary (or pick a reference point) to query real raster & precipitation data
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {DIMA_HASAO_PRESETS.map((pt) => (
            <button
              key={pt.label}
              type="button"
              onClick={() => onSelectCoordinate(pt.lat, pt.lon)}
              className="px-2 py-1 rounded bg-slate-900 hover:bg-cyan-950/70 text-[10px] font-mono text-cyan-300 border border-slate-700 hover:border-cyan-500/50 transition flex items-center gap-1"
            >
              <MapPin className="w-2.5 h-2.5" />
              <span>{pt.label}</span>
            </button>
          ))}
          {onFocusPilot && (
            <button
              type="button"
              onClick={onFocusPilot}
              className="px-2 py-1 rounded bg-emerald-950/70 hover:bg-emerald-900 text-[10px] font-mono text-emerald-300 border border-emerald-500/50 transition flex items-center gap-1"
            >
              <Compass className="w-3 h-3" />
              <span>Zoom to Pilot</span>
            </button>
          )}
        </div>
      </div>

      {/* Loading / Error / Data Body */}
      {loading ? (
        <div className="py-5 flex items-center justify-center gap-2 text-xs text-cyan-300 font-mono">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>Sampling Copernicus DEM, ESA WorldCover & NASA GPM IMERG rasters...</span>
        </div>
      ) : error ? (
        <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-700/40 text-xs text-rose-300 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>Environmental API Error: {error}</span>
        </div>
      ) : !data ? (
        <div className="py-4 text-center text-xs text-slate-400 font-mono">
          Select a point inside Dima Hasao District, Assam to inspect verified environmental observations.
        </div>
      ) : (
        <div className="space-y-2.5">
          {/* Coordinate & Coverage Status Bar */}
          <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] font-mono bg-slate-950/70 px-3 py-1.5 rounded-lg border border-slate-800">
            <div className="flex items-center gap-2 text-slate-300">
              <span className="text-slate-500">Point ({data.crs}):</span>
              <span className="text-cyan-300 font-bold">
                {data.coordinates.lat.toFixed(4)}°N, {data.coordinates.lon.toFixed(4)}°E
              </span>
            </div>
            <div className="flex items-center gap-2">
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold border ${
                  data.within_pilot_boundary
                    ? 'bg-emerald-950/80 text-emerald-300 border-emerald-500/40'
                    : 'bg-amber-950/80 text-amber-300 border-amber-500/40'
                }`}
              >
                {data.within_pilot_boundary ? 'INSIDE DIMA HASAO BOUNDARY' : 'OUTSIDE PILOT BOUNDARY'}
              </span>
              <span className="px-2 py-0.5 rounded bg-slate-900 text-amber-300 border border-slate-700 text-[10px]">
                ML Probability: null (No Model)
              </span>
            </div>
          </div>

          {/* 4-Card Verified Observation Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-2.5 text-xs">
            {/* 1. Elevation & Slope */}
            <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 uppercase">
                <span className="flex items-center gap-1 text-cyan-400 font-bold">
                  <Mountain className="w-3.5 h-3.5" /> Copernicus DEM GLO-30
                </span>
                <span>{data.terrain.elevation_resolution_m ? `${data.terrain.elevation_resolution_m}m` : 'N/A'}</span>
              </div>
              {data.terrain.missing_elevation ? (
                <div className="text-amber-300 font-mono text-xs py-1">Unavailable outside raster bounds</div>
              ) : (
                <div className="grid grid-cols-3 gap-1 pt-0.5 font-mono">
                  <div>
                    <span className="text-[9px] text-slate-500 block">Elevation</span>
                    <span className="text-sm font-bold text-slate-100">
                      {data.terrain.elevation_m?.toFixed(1)} m
                    </span>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 block">Slope (Horn)</span>
                    <span className="text-sm font-bold text-orange-400">
                      {data.terrain.slope_deg !== null ? `${data.terrain.slope_deg.toFixed(1)}°` : 'N/A'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 block">Aspect</span>
                    <span className="text-sm font-bold text-cyan-300">
                      {data.terrain.aspect_deg !== null
                        ? `${Math.round(data.terrain.aspect_deg)}° ${data.terrain.aspect_cardinal || ''}`
                        : 'Flat'}
                    </span>
                  </div>
                </div>
              )}
              <div className="text-[9px] text-slate-500 truncate" title={data.terrain.provenance?.attribution}>
                CRS: {data.terrain.provenance?.crs || 'EPSG:32646'} · {data.terrain.provenance?.product_version || 'COP-DEM'}
              </div>
            </div>

            {/* 2. Land Cover */}
            <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 uppercase">
                <span className="flex items-center gap-1 text-emerald-400 font-bold">
                  <Trees className="w-3.5 h-3.5" /> ESA WorldCover 2021
                </span>
                <span>10m v200</span>
              </div>
              {data.land_cover.missing_land_cover ? (
                <div className="text-amber-300 font-mono text-xs py-1">Unavailable outside raster bounds</div>
              ) : (
                <div className="pt-0.5">
                  <div className="text-sm font-bold text-emerald-300 font-display">
                    {data.land_cover.class_label}
                  </div>
                  <div className="text-[10px] font-mono text-slate-400">
                    ESA Class Code: {data.land_cover.class_code} · Static 2021 epoch
                  </div>
                </div>
              )}
              <div className="text-[9px] text-slate-500 truncate" title={data.land_cover.provenance?.limitations || ''}>
                Note: Static 2021 map (post-2021 clearing not reflected)
              </div>
            </div>

            {/* 3. NASA GPM IMERG Rainfall */}
            <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-1">
              <div className="flex items-center justify-between text-[10px] font-mono text-slate-400 uppercase">
                <span className="flex items-center gap-1 text-sky-400 font-bold">
                  <CloudRain className="w-3.5 h-3.5" /> NASA GPM IMERG
                </span>
                <span>0.1° Daily</span>
              </div>
              {data.rainfall.missing_24h ? (
                <div className="text-amber-300 font-mono text-xs py-1">
                  {data.within_pilot_boundary ? 'Missing observation (null)' : 'Outside pilot AOI'}
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-1 pt-0.5 font-mono">
                  <div>
                    <span className="text-[9px] text-slate-500 block">
                      24h ({data.rainfall.latest_observation_date})
                    </span>
                    <span className="text-sm font-bold text-sky-300">
                      {data.rainfall.rainfall_24h_mm?.toFixed(1)} mm
                    </span>
                  </div>
                  <div>
                    <span className="text-[9px] text-slate-500 block">72h Rolling</span>
                    <span className="text-sm font-bold text-amber-300">
                      {data.rainfall.missing_72h || data.rainfall.rainfall_72h_mm === null
                        ? 'Missing'
                        : `${data.rainfall.rainfall_72h_mm.toFixed(1)} mm`}
                    </span>
                  </div>
                </div>
              )}
              <div className="text-[9px] text-slate-500 font-mono">
                Window Peak: {data.rainfall.max_24h_in_window_mm !== null ? `${data.rainfall.max_24h_in_window_mm.toFixed(1)} mm/24h` : 'N/A'} ·{' '}
                {data.rainfall.valid_days_in_window}d valid / {data.rainfall.missing_days_in_window}d null
              </div>
            </div>

            {/* 4. Provenance & Scientific Guardrail */}
            <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 space-y-1">
              <div className="flex items-center gap-1 text-[10px] font-mono text-amber-300 uppercase font-bold">
                <Info className="w-3.5 h-3.5" /> Provenance & Status
              </div>
              <div className="text-[10px] text-slate-300 leading-snug">
                Verified environmental observations only. Factor of Safety & ML landslide probability are explicitly <strong>unavailable</strong> until supervised training is completed.
              </div>
              <div className="text-[9px] font-mono text-slate-500 truncate">
                Queried: {new Date(data.response_generated_at_utc).toUTCString()}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
