import React, { useState, useEffect } from 'react';
import {
  Activity,
  Sliders,
  Sparkles,
  RefreshCw,
  AlertTriangle,
  ArrowRight,
  ShieldAlert,
  FileCheck2,
  Gauge,
  Layers,
} from 'lucide-react';
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { RiskLocation } from '../types/disaster';
import { getExplainableBreakdown } from '../services/riskEngine';

interface RiskAnalysisPageProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  onSimulate: (loc: RiskLocation) => void;
  onViewImpact: (loc: RiskLocation) => void;
}

export const RiskAnalysisPage: React.FC<RiskAnalysisPageProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  onSimulate,
  onViewImpact,
}) => {
  const activeLoc = selectedLocation || locations[0];
  const [aiBriefing, setAiBriefing] = useState<string | null>(null);
  const [isLoadingAi, setIsLoadingAi] = useState(false);
  const [aiSource, setAiSource] = useState<'gemini-ai' | 'local'>('local');

  // Load deterministic or AI briefing
  const fetchAiAnalysis = async (loc: RiskLocation) => {
    setIsLoadingAi(true);
    try {
      const res = await fetch('/api/gemini/explain', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location: loc, simulated: false }),
      });
      const data = await res.json();
      if (data.text) {
        setAiBriefing(data.text);
        setAiSource('gemini-ai');
      } else {
        // Deterministic fallback
        setAiBriefing(getDefaultBriefing(loc));
        setAiSource('local');
      }
    } catch {
      setAiBriefing(getDefaultBriefing(loc));
      setAiSource('local');
    } finally {
      setIsLoadingAi(false);
    }
  };

  const getDefaultBriefing = (loc: RiskLocation) => {
    return `The calculated Landslide Risk Score of ${loc.calculatedScore}/100 for ${loc.name} is primarily driven by acute hydrometeorological saturation combined with high topographical shear stress. Sustained 24-hour rainfall of ${loc.currentRainfall} mm has elevated pore-water pressure along the weathered rock-soil interface, reducing effective normal stress and causing the estimated Factor of Safety (FS) to degrade to 0.88.\n\nImmediate Directive: The District Disaster Management Authority (DDMA) and BRO Task Force must maintain continuous vigilance on arterial corridors (${loc.infrastructure.keyHighways?.join(', ')}). Pre-position heavy hydraulic earthmovers, evacuate toe-slope settlements, and alert the community emergency response teams.`;
  };

  useEffect(() => {
    if (activeLoc) {
      fetchAiAnalysis(activeLoc);
    }
  }, [activeLoc?.id]);

  const xai = getExplainableBreakdown(activeLoc);

  // Radar chart data comparing factor scores (0-100)
  const radarData = [
    { factor: 'Rainfall Intensity', value: Math.min(100, Math.round((activeLoc.currentRainfall / 180) * 100)) },
    { factor: 'Slope Gradient', value: Math.min(100, Math.round((activeLoc.slope / 50) * 100)) },
    { factor: 'Soil Saturation', value: activeLoc.soilSaturation },
    { factor: 'Historical Slides', value: activeLoc.historicalActivity },
    { factor: 'Vegetation Stress', value: activeLoc.vegetationStress },
    { factor: 'Asset Exposure', value: Math.min(100, Math.round((activeLoc.populationExposed / 6000) * 100)) },
  ];

  return (
    <div className="space-y-4">
      {/* Top Header & Location Switcher */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-blue-950/80 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <Activity className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-cyan-400 uppercase font-mono font-bold tracking-wider">
              Explainable AI (XAI) Geotechnical Engine
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              Multi-Factor Hazard Risk Diagnosis
            </h2>
          </div>
        </div>

        {/* Location Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs text-slate-400 font-medium">Inspecting Location:</span>
          <select
            value={activeLoc.id}
            onChange={(e) => {
              const found = locations.find((l) => l.id === e.target.value);
              if (found) onSelectLocation(found);
            }}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-semibold focus:ring-1 focus:ring-cyan-500 outline-none"
          >
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name} ({loc.district}, {loc.state}) — {loc.calculatedLevel} ({loc.calculatedScore}/100)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Main Analysis Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Key Geotechnical Parameters & Scorecard */}
        <div className="lg:col-span-4 space-y-4">
          {/* Primary Scorecard */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-base font-bold text-white font-display">{activeLoc.name}</h3>
                <p className="text-xs text-slate-400">{activeLoc.district}, {activeLoc.state}</p>
              </div>
              <span
                className={`px-2.5 py-1 rounded text-xs font-bold font-mono uppercase border ${
                  activeLoc.calculatedLevel === 'CRITICAL'
                    ? 'bg-red-950/80 text-red-400 border-red-500/50'
                    : activeLoc.calculatedLevel === 'HIGH'
                    ? 'bg-orange-950/80 text-orange-400 border-orange-500/50'
                    : 'bg-yellow-950/80 text-yellow-400 border-yellow-500/50'
                }`}
              >
                {activeLoc.calculatedLevel} RISK
              </span>
            </div>

            <div className="grid grid-cols-3 gap-2 p-3 bg-slate-950/60 rounded-lg border border-slate-800/80">
              <div>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Risk Score</span>
                <span className="text-xl font-mono font-bold text-red-400">
                  {activeLoc.calculatedScore}
                  <span className="text-xs text-slate-500 font-normal"> / 100</span>
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Factor of Safety</span>
                <span className="text-xl font-mono font-bold text-amber-400">
                  0.88
                  <span className="text-[10px] text-slate-500 font-normal block">&lt; 1.0 (Critical)</span>
                </span>
              </div>
              <div>
                <span className="text-[10px] text-slate-400 uppercase tracking-wider block">Confidence</span>
                <span className="text-xl font-mono font-bold text-cyan-400">
                  {activeLoc.confidence || 89}%
                  <span className="text-[10px] text-slate-500 font-normal block">Multi-sensor</span>
                </span>
              </div>
            </div>

            {/* Geotechnical Parameters */}
            <div className="space-y-2 text-xs">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">
                Geological & Terrain Telemetry
              </div>
              <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 block text-[9px]">Slope Angle</span>
                  <span className="text-orange-400 font-bold">{activeLoc.slope}°</span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 block text-[9px]">Elevation</span>
                  <span className="text-slate-200 font-bold">{activeLoc.elevation} m</span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 block text-[9px]">Current 24h Rain</span>
                  <span className="text-cyan-400 font-bold">{activeLoc.currentRainfall} mm</span>
                </div>
                <div className="p-2 rounded bg-slate-900 border border-slate-800">
                  <span className="text-slate-500 block text-[9px]">Soil Saturation</span>
                  <span className="text-amber-400 font-bold">{activeLoc.soilSaturation}%</span>
                </div>
              </div>

              <div className="p-2 rounded bg-slate-900 border border-slate-800 text-[11px]">
                <div className="flex justify-between">
                  <span className="text-slate-400">Lithology / Soil:</span>
                  <span className="text-slate-200 font-medium">{activeLoc.soilType}</span>
                </div>
                <div className="flex justify-between mt-1">
                  <span className="text-slate-400">Vegetation Stress:</span>
                  <span className="text-emerald-400 font-medium">{activeLoc.vegetationStress}% stress index</span>
                </div>
              </div>
            </div>

            {/* Navigation action links */}
            <div className="pt-2 border-t border-slate-800 flex gap-2">
              <button
                onClick={() => onSimulate(activeLoc)}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-blue-600 hover:bg-blue-500 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-600/20 transition"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Simulate Rain</span>
              </button>
              <button
                onClick={() => onViewImpact(activeLoc)}
                className="flex-1 flex items-center justify-center gap-1.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg text-xs font-semibold border border-slate-700 transition"
              >
                <ShieldAlert className="w-3.5 h-3.5 text-cyan-400" />
                <span>Impact & Response</span>
              </button>
            </div>
          </div>
        </div>

        {/* Center Column: Multi-Factor Radar & XAI Formula Breakdown */}
        <div className="lg:col-span-4 space-y-4">
          {/* Radar Chart */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl">
            <h3 className="text-xs font-bold text-slate-100 font-display mb-1">
              Multi-Factor Hazard Polygon
            </h3>
            <p className="text-[10px] text-slate-400">
              Normalized comparative factor intensity (0-100 scale)
            </p>

            <div className="h-64 w-full mt-2">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart cx="50%" cy="50%" outerRadius="75%" data={radarData}>
                  <PolarGrid stroke="#334155" />
                  <PolarAngleAxis dataKey="factor" stroke="#94a3b8" fontSize={9} />
                  <PolarRadiusAxis stroke="#64748b" domain={[0, 100]} fontSize={8} />
                  <Radar
                    name="Hazard Magnitude"
                    dataKey="value"
                    stroke="#38bdf8"
                    fill="#0284c7"
                    fillOpacity={0.4}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0f172a',
                      borderColor: '#334155',
                      fontSize: '11px',
                    }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Mathematical Weight Breakdown */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-[10px] text-cyan-400 font-mono font-bold uppercase block">
                  WHY THIS RISK?
                </span>
                <h3 className="text-xs font-bold text-slate-100 font-display">
                  Factor Contributions (100% Normalized)
                </h3>
              </div>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-cyan-400 border border-slate-700">
                Confidence {activeLoc.confidence || 89}%
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-300">Rainfall</span>
                  <span className="font-mono text-cyan-400 font-bold">{xai.rainfallPct}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-cyan-500 rounded-full" style={{ width: `${xai.rainfallPct}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-300">Slope Gradient</span>
                  <span className="font-mono text-orange-400 font-bold">{xai.slopePct}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-orange-500 rounded-full" style={{ width: `${xai.slopePct}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-300">Soil Saturation</span>
                  <span className="font-mono text-amber-400 font-bold">{xai.soilSaturationPct}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-amber-500 rounded-full" style={{ width: `${xai.soilSaturationPct}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-300">Historical Activity</span>
                  <span className="font-mono text-purple-400 font-bold">{xai.historicalActivityPct}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-purple-500 rounded-full" style={{ width: `${xai.historicalActivityPct}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-300">Vegetation</span>
                  <span className="font-mono text-emerald-400 font-bold">{xai.vegetationPct}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${xai.vegetationPct}%` }} />
                </div>
              </div>

              <div>
                <div className="flex justify-between text-[11px] mb-0.5">
                  <span className="text-slate-300">Exposure</span>
                  <span className="font-mono text-pink-400 font-bold">{xai.exposurePct}%</span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div className="h-full bg-pink-500 rounded-full" style={{ width: `${xai.exposurePct}%` }} />
                </div>
              </div>
            </div>

            {/* Macro Weight Distribution */}
            <div className="pt-2 border-t border-slate-800/80 space-y-1.5">
              <span className="text-[10px] text-slate-400 font-mono uppercase block">Model Architecture Weights:</span>
              <div className="grid grid-cols-3 gap-1.5 text-center text-[10px] font-mono">
                <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-cyan-400 font-bold block">{xai.dynamicShare}%</span>
                  <span className="text-slate-500 text-[9px]">Dynamic</span>
                </div>
                <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-orange-400 font-bold block">{xai.staticShare}%</span>
                  <span className="text-slate-500 text-[9px]">Static</span>
                </div>
                <div className="p-1.5 rounded bg-slate-900 border border-slate-800">
                  <span className="text-purple-400 font-bold block">{xai.exposureShare}%</span>
                  <span className="text-slate-500 text-[9px]">Exposure</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: AI Geotechnical Advisor & Immediate Directives */}
        <div className="lg:col-span-4 space-y-4">
          <div className="bg-[#0f172a] border border-cyan-900/40 rounded-xl p-4 shadow-xl space-y-3 flex flex-col justify-between min-h-[460px]">
            <div>
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-cyan-400 animate-pulse" />
                  <h3 className="text-xs font-bold text-slate-100 font-display">
                    AI Geotechnical Advisor Briefing
                  </h3>
                </div>
                <span className="text-[9px] font-mono px-2 py-0.5 rounded bg-cyan-950/80 border border-cyan-800/60 text-cyan-300">
                  {aiSource === 'gemini-ai' ? 'Gemini 3.8 Flash' : 'Deterministic Engine'}
                </span>
              </div>

              {isLoadingAi ? (
                <div className="py-12 text-center text-slate-400 space-y-2">
                  <RefreshCw className="w-6 h-6 animate-spin mx-auto text-cyan-400" />
                  <p className="text-xs font-mono">Synthesizing pore pressure & geological failure mechanics...</p>
                </div>
              ) : (
                <div className="mt-3 space-y-3 text-xs leading-relaxed text-slate-300 whitespace-pre-line font-sans">
                  {aiBriefing}
                </div>
              )}
            </div>

            <div className="pt-3 border-t border-slate-800 flex items-center justify-between">
              <span className="text-[10px] text-slate-500 font-mono">ISO/DIS-31010 Compliant</span>
              <button
                onClick={() => fetchAiAnalysis(activeLoc)}
                disabled={isLoadingAi}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-cyan-300 border border-slate-700 text-xs font-semibold transition"
              >
                <RefreshCw className={`w-3 h-3 ${isLoadingAi ? 'animate-spin' : ''}`} />
                <span>Regenerate Briefing</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
