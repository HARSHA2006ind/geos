import React from 'react';
import { ShieldAlert, ArrowRight, CheckCircle2, TrendingUp, X } from 'lucide-react';

export interface RiskFeedbackModalData {
  show: boolean;
  locationName: string;
  previousScore: number;
  newScore: number;
  reason: string;
}

interface RiskUpdatedModalProps {
  data: RiskFeedbackModalData | null;
  onClose: () => void;
}

export const RiskUpdatedModal: React.FC<RiskUpdatedModalProps> = ({ data, onClose }) => {
  if (!data || !data.show) return null;

  const prevScore = data.previousScore;
  const newScore = data.newScore;
  const scoreDelta = newScore - prevScore;

  const newLevel =
    newScore >= 75
      ? 'CRITICAL'
      : newScore >= 55
      ? 'HIGH'
      : newScore >= 35
      ? 'MODERATE'
      : 'LOW';

  const badgeColor =
    newLevel === 'CRITICAL'
      ? 'bg-red-950 text-red-400 border-red-500/60'
      : newLevel === 'HIGH'
      ? 'bg-orange-950 text-orange-400 border-orange-500/60'
      : newLevel === 'MODERATE'
      ? 'bg-yellow-950 text-yellow-400 border-yellow-500/60'
      : 'bg-emerald-950 text-emerald-400 border-emerald-500/60';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="w-full max-w-md bg-[#0f172a] border-2 border-cyan-500/60 rounded-2xl shadow-2xl overflow-hidden p-6 space-y-4">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-lg bg-cyan-950 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <TrendingUp className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] text-cyan-400 uppercase font-mono font-bold tracking-widest block">
                Continuous Intelligence Feedback Loop
              </span>
              <h2 className="text-lg font-bold text-slate-100 font-display tracking-tight">
                RISK UPDATED
              </h2>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Location Target */}
        <div className="px-3.5 py-2 rounded-lg bg-slate-900 border border-slate-800 text-xs flex items-center justify-between">
          <span className="text-slate-400 font-medium">Target Zone:</span>
          <span className="font-bold text-slate-100">{data.locationName}</span>
        </div>

        {/* Score Shift Demonstration: Previous -> New */}
        <div className="p-4 bg-slate-950/80 rounded-xl border border-slate-800 space-y-2">
          <div className="flex items-center justify-between text-xs text-slate-400 font-mono">
            <span>PREVIOUS SCORE</span>
            <span>UPDATED SCORE</span>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-baseline gap-1">
              <span className="text-2xl font-mono font-bold text-slate-400">
                {prevScore}
              </span>
              <span className="text-xs text-slate-500">/ 100</span>
            </div>

            <div className="flex items-center gap-1.5 text-cyan-400 font-bold">
              <ArrowRight className="w-5 h-5 animate-pulse" />
              <span className="text-xs font-mono">+{scoreDelta}</span>
            </div>

            <div className="flex items-baseline gap-1">
              <span className="text-3xl font-mono font-extrabold text-red-400">
                {newScore}
              </span>
              <span className="text-xs text-slate-500">/ 100</span>
            </div>
          </div>

          {/* Level Transition Badge */}
          <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between">
            <span className="text-[11px] text-slate-400 font-medium">Escalated Classification:</span>
            <span className={`px-2.5 py-0.5 rounded text-[11px] font-bold uppercase font-mono border ${badgeColor}`}>
              {newLevel} RISK
            </span>
          </div>
        </div>

        {/* Structured Reason */}
        <div className="p-3 bg-red-950/20 border border-red-900/40 rounded-xl space-y-1 text-xs">
          <span className="text-[10px] uppercase font-mono text-red-400 font-bold block">
            Update Driver & Evidence:
          </span>
          <p className="text-slate-200 font-medium leading-relaxed">
            "{data.reason}"
          </p>
        </div>

        {/* System Impact Checklist */}
        <div className="space-y-1.5 text-[11px] text-slate-300">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>Telemetry recalculation completed across all hydrologic models</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>GIS spatial risk heat ring expanded on regional command map</span>
          </div>
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>Local SDMA emergency alert logged in master regional registry</span>
          </div>
        </div>

        {/* Dismiss Button */}
        <button
          onClick={onClose}
          className="w-full py-2.5 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold rounded-lg text-xs shadow-lg shadow-cyan-900/40 transition"
        >
          Acknowledge Risk Escalation
        </button>
      </div>
    </div>
  );
};
