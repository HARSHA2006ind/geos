import React from 'react';
import { X, ExternalLink, Sliders, AlertCircle, ArrowUpRight, ShieldAlert, Sparkles } from 'lucide-react';
import { RiskLocation } from '../../types/disaster';
import { getExplainableBreakdown } from '../../services/riskEngine';

interface LocationDetailsPanelProps {
  location: RiskLocation | null;
  onClose: () => void;
  onViewAnalysis: (location: RiskLocation) => void;
  onSimulate: (location: RiskLocation) => void;
  onGenerateAlert: (location: RiskLocation) => void;
}

export const LocationDetailsPanel: React.FC<LocationDetailsPanelProps> = ({
  location,
  onClose,
  onViewAnalysis,
  onSimulate,
  onGenerateAlert,
}) => {
  if (!location) {
    return (
      <div className="h-full flex flex-col items-center justify-center p-6 text-center text-slate-500 bg-[#0f172a] rounded-xl border border-slate-800">
        <AlertCircle className="w-10 h-10 text-slate-600 mb-2" />
        <p className="text-sm font-medium">Select a location on the map</p>
        <p className="text-xs text-slate-600 mt-1">Click any risk zone marker to view telemetry & risk factors</p>
      </div>
    );
  }

  const xai = getExplainableBreakdown(location);

  const levelColor =
    location.calculatedLevel === 'CRITICAL'
      ? 'bg-red-950/80 text-red-400 border-red-500/50'
      : location.calculatedLevel === 'HIGH'
      ? 'bg-orange-950/80 text-orange-400 border-orange-500/50'
      : location.calculatedLevel === 'MODERATE'
      ? 'bg-yellow-950/80 text-yellow-400 border-yellow-500/50'
      : 'bg-emerald-950/80 text-emerald-400 border-emerald-500/50';

  return (
    <div className="h-full flex flex-col justify-between bg-[#0f172a] rounded-xl border border-slate-800 p-4 overflow-y-auto shadow-2xl space-y-4">
      <div className="space-y-3">
        {/* Header */}
        <div className="flex items-start justify-between gap-2 pb-2.5 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-100 tracking-tight font-display">
              {location.name}
            </h3>
            <p className="text-[11px] text-slate-400">
              {location.district}, {location.state}
            </p>
          </div>
          <button
            id="close-location-details-panel-btn"
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Thumbnail Image & Score Header */}
        <div className="flex gap-3 items-center">
          <div className="w-24 h-20 rounded-lg overflow-hidden border border-slate-700 bg-slate-800 shrink-0 relative">
            <img
              src={
                location.imageUrl ||
                'https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=400&q=80'
              }
              alt={location.name}
              className="w-full h-full object-cover"
              referrerPolicy="no-referrer"
            />
          </div>

          <div className="flex-1 space-y-1.5">
            <div className="flex items-center justify-between">
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase border ${levelColor}`}>
                {location.calculatedLevel} RISK
              </span>
              <div className="text-right">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider block font-semibold">CONFIDENCE</span>
                <span className="text-xs font-mono font-bold text-cyan-400">
                  {location.confidence || 89}%
                </span>
              </div>
            </div>
            <div className="pt-0.5 flex items-baseline justify-between">
              <div>
                <span className="text-[9px] text-slate-400 uppercase tracking-wider block font-semibold">Risk Score</span>
                <span className="text-xl font-mono font-bold text-slate-100">
                  <span className={location.calculatedScore >= 75 ? 'text-red-400' : 'text-orange-400'}>
                    {location.calculatedScore}
                  </span>
                  <span className="text-xs text-slate-500 font-normal"> / 100</span>
                </span>
              </div>
              <div className="text-right">
                <span className="text-[9px] text-slate-400 uppercase tracking-wider block">Slope / Rain</span>
                <span className="text-xs font-mono text-slate-300 font-medium">
                  {location.slope}° • {location.currentRainfall}mm
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Concise Explanation */}
        <div className="p-2.5 rounded-lg bg-slate-900/90 border border-slate-800 text-[11px] text-slate-300 leading-relaxed">
          <div className="flex items-center gap-1.5 text-cyan-400 font-bold text-[10px] uppercase tracking-wider mb-1">
            <Sparkles className="w-3 h-3" />
            <span>Diagnosis Summary</span>
          </div>
          {xai.conciseExplanation}
        </div>

        {/* Factor Contribution Visualization: WHY THIS RISK? */}
        <div className="pt-2 border-t border-slate-800 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold uppercase tracking-wider text-slate-300">
              WHY THIS RISK?
            </span>
            <span className="text-[10px] font-mono text-slate-500">Factor Contribution</span>
          </div>

          <div className="space-y-1.5 text-xs">
            {/* Rainfall */}
            <div>
              <div className="flex justify-between text-[11px] mb-0.5">
                <span className="text-slate-300">Rainfall</span>
                <span className="font-mono text-cyan-400 font-bold">{xai.rainfallPct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-cyan-500 rounded-full transition-all duration-500"
                  style={{ width: `${xai.rainfallPct}%` }}
                />
              </div>
            </div>

            {/* Slope */}
            <div>
              <div className="flex justify-between text-[11px] mb-0.5">
                <span className="text-slate-300">Slope</span>
                <span className="font-mono text-orange-400 font-bold">{xai.slopePct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-orange-500 rounded-full transition-all duration-500"
                  style={{ width: `${xai.slopePct}%` }}
                />
              </div>
            </div>

            {/* Soil Saturation */}
            <div>
              <div className="flex justify-between text-[11px] mb-0.5">
                <span className="text-slate-300">Soil Saturation</span>
                <span className="font-mono text-amber-400 font-bold">{xai.soilSaturationPct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-amber-500 rounded-full transition-all duration-500"
                  style={{ width: `${xai.soilSaturationPct}%` }}
                />
              </div>
            </div>

            {/* Historical Activity */}
            <div>
              <div className="flex justify-between text-[11px] mb-0.5">
                <span className="text-slate-300">Historical Activity</span>
                <span className="font-mono text-purple-400 font-bold">{xai.historicalActivityPct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-purple-500 rounded-full transition-all duration-500"
                  style={{ width: `${xai.historicalActivityPct}%` }}
                />
              </div>
            </div>

            {/* Vegetation */}
            <div>
              <div className="flex justify-between text-[11px] mb-0.5">
                <span className="text-slate-300">Vegetation</span>
                <span className="font-mono text-emerald-400 font-bold">{xai.vegetationPct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-emerald-500 rounded-full transition-all duration-500"
                  style={{ width: `${xai.vegetationPct}%` }}
                />
              </div>
            </div>

            {/* Exposure */}
            <div>
              <div className="flex justify-between text-[11px] mb-0.5">
                <span className="text-slate-300">Exposure</span>
                <span className="font-mono text-pink-400 font-bold">{xai.exposurePct}%</span>
              </div>
              <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                <div
                  className="h-full bg-pink-500 rounded-full transition-all duration-500"
                  style={{ width: `${xai.exposurePct}%` }}
                />
              </div>
            </div>
          </div>
        </div>

        {/* Primary Risk Drivers */}
        <div className="pt-2 border-t border-slate-800">
          <div className="text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
            Primary Risk Drivers
          </div>
          <div className="space-y-1">
            {location.primaryRiskDrivers.map((driver, idx) => (
              <div key={idx} className="flex items-center gap-2 text-xs text-slate-300">
                <span className="w-3.5 h-3.5 rounded-full bg-slate-800 text-cyan-400 text-[10px] font-mono font-bold flex items-center justify-center shrink-0 border border-slate-700">
                  {idx + 1}
                </span>
                <span className="truncate text-[11px]">{driver}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="pt-2 border-t border-slate-800 space-y-2">
        <div className="grid grid-cols-2 gap-2">
          <button
            id="panel-btn-view-analysis"
            onClick={() => onViewAnalysis(location)}
            className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg text-xs font-semibold border border-slate-700 transition"
          >
            <ExternalLink className="w-3.5 h-3.5 text-cyan-400" />
            <span>View Analysis</span>
          </button>

          <button
            id="panel-btn-simulate"
            onClick={() => onSimulate(location)}
            className="flex items-center justify-center gap-1.5 px-3 py-2 bg-blue-600/90 hover:bg-blue-600 text-white rounded-lg text-xs font-semibold shadow-md shadow-blue-600/20 transition"
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Simulate</span>
          </button>
        </div>

        <button
          id="panel-btn-generate-alert"
          onClick={() => onGenerateAlert(location)}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-gradient-to-r from-red-600 to-rose-700 hover:from-red-500 hover:to-rose-600 text-white rounded-lg text-xs font-bold tracking-wide shadow-lg shadow-red-900/30 transition"
        >
          <ArrowUpRight className="w-3.5 h-3.5" />
          <span>Generate Alert</span>
        </button>
      </div>
    </div>
  );
};
