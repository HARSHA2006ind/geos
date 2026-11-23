import React, { useState, useEffect } from 'react';
import {
  ShieldAlert,
  Users,
  Building2,
  CheckCircle2,
  Truck,
  Hospital,
  School,
  Radio,
  Zap,
  Navigation,
  Filter,
} from 'lucide-react';
import { ResponseAction, RiskLocation } from '../types/disaster';
import { generateResponseRecommendations } from '../services/riskEngine';

interface ImpactResponsePageProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  onOpenCreateAlert: (loc: RiskLocation) => void;
}

export const ImpactResponsePage: React.FC<ImpactResponsePageProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  onOpenCreateAlert,
}) => {
  const activeLoc = selectedLocation || locations[0];
  const [categoryFilter, setCategoryFilter] = useState<'ALL' | 'IMMEDIATE' | 'HIGH' | 'MONITOR'>('ALL');
  const [actions, setActions] = useState<ResponseAction[]>(() =>
    activeLoc ? generateResponseRecommendations(activeLoc) : []
  );

  // Regenerate location-specific directives whenever the selected location changes
  useEffect(() => {
    if (activeLoc) {
      setActions(generateResponseRecommendations(activeLoc));
    }
  }, [activeLoc?.id, activeLoc?.calculatedLevel]);

  if (!activeLoc) return null;

  const toggleActionStatus = (id: string) => {
    setActions((prev) =>
      prev.map((act) => {
        if (act.id !== id) return act;
        const nextStatus: ResponseAction['status'] =
          act.status === 'Pending'
            ? 'In Progress'
            : act.status === 'In Progress'
            ? 'Completed'
            : 'Pending';
        return { ...act, status: nextStatus };
      })
    );
  };

  const filteredActions =
    categoryFilter === 'ALL' ? actions : actions.filter((act) => act.priority === categoryFilter);

  // Align strictly with riskEngine.ts thresholds: 75 / 50 / 25
  const impactSeverity = activeLoc.calculatedLevel;

  const severityBadgeClass =
    impactSeverity === 'CRITICAL'
      ? 'bg-red-950 text-red-400 border-red-500/50'
      : impactSeverity === 'HIGH'
      ? 'bg-orange-950 text-orange-400 border-orange-500/50'
      : impactSeverity === 'MODERATE'
      ? 'bg-yellow-950 text-yellow-400 border-yellow-500/50'
      : 'bg-emerald-950 text-emerald-400 border-emerald-500/50';

  return (
    <div className="space-y-4">
      {/* Top Header & Sector Selector */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-rose-950/80 border border-rose-500/40 flex items-center justify-center text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-amber-300 uppercase font-mono font-bold tracking-wider">
              Prototype Decision-Support Directives (Demo Exposure Estimates)
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              Impact Assessment & Response Checklist
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
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
                {loc.name} ({loc.district}, {loc.state})
              </option>
            ))}
          </select>

          <button
            id="impact-page-generate-alert-btn"
            onClick={() => onOpenCreateAlert(activeLoc)}
            className="px-3.5 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold shadow-md shadow-red-600/30 transition flex items-center gap-1.5"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Draft Prototype Alert</span>
          </button>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Demo Exposure Summary */}
        <div className="lg:col-span-5 space-y-4">
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl flex items-center justify-between">
            <div>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider font-mono font-bold block">
                HEURISTIC CLASSIFICATION ({activeLoc.calculatedScore}/100)
              </span>
              <span className="text-sm font-bold text-slate-100 font-display">
                {activeLoc.name} · {activeLoc.state}
              </span>
            </div>
            <div className={`px-3 py-1 rounded-lg text-xs font-bold uppercase font-mono border ${severityBadgeClass}`}>
              {impactSeverity}
            </div>
          </div>

          {/* People */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase font-display tracking-wider">
                  PEOPLE — Demo Exposure Estimate
                </h3>
              </div>
              <span className="text-xs font-mono font-bold text-purple-300">
                {activeLoc.populationExposed.toLocaleString()}
              </span>
            </div>

            <p className="text-[11px] text-slate-400 leading-relaxed">
              Demographic and household runout exposure is currently populated from prototype scenario data. Integration with WorldPop / Census village shapefiles is planned in Phase 2.
            </p>
          </div>

          {/* Lifelines */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase font-display tracking-wider">
                  LIFELINES — Prototype Asset Inventory
                </h3>
              </div>
              <span className="text-xs font-mono font-bold text-cyan-400">
                {activeLoc.infrastructure.roads + activeLoc.infrastructure.bridges + activeLoc.infrastructure.powerAssets} Units
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Truck className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-slate-300 text-[11px]">Roads</span>
                </div>
                <span className="font-mono text-cyan-400 font-bold">{activeLoc.infrastructure.roads}</span>
              </div>

              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Navigation className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-slate-300 text-[11px]">Bridges</span>
                </div>
                <span className="font-mono text-orange-400 font-bold">{activeLoc.infrastructure.bridges}</span>
              </div>

              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-slate-300 text-[11px]">Power</span>
                </div>
                <span className="font-mono text-amber-400 font-bold">{activeLoc.infrastructure.powerAssets}</span>
              </div>

              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Hospital className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-slate-300 text-[11px]">Hospitals / Schools</span>
                </div>
                <span className="font-mono text-emerald-400 font-bold">
                  {activeLoc.infrastructure.hospitals} / {activeLoc.infrastructure.schools}
                </span>
              </div>
            </div>

            <div className="text-[11px] text-slate-400 font-mono">
              Key Highway Corridors:{' '}
              <span className="text-slate-200">
                {activeLoc.infrastructure.keyHighways.join(', ') || 'District roads'}
              </span>
            </div>
            <div className="text-[10px] text-slate-500">
              Telecom tower counts, shelter capacity, and verified bypass detour routing are not yet ingested (unavailable).
            </div>
          </div>
        </div>

        {/* Right Column: Dynamic Location-Specific Action Directives */}
        <div className="lg:col-span-7 bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-4">
          <div className="flex flex-wrap items-center justify-between pb-3 border-b border-slate-800 gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-100 font-display">
                Recommended Directives for {activeLoc.name}
              </h3>
              <p className="text-[11px] text-slate-400">
                Generated dynamically from location severity ({activeLoc.calculatedLevel}) · Session Checklist Only
              </p>
            </div>
            <span className="text-xs text-slate-400 font-mono">
              {actions.filter((a) => a.status === 'Completed').length} / {actions.length} Completed
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[11px] text-slate-400 font-medium mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Filter:
            </span>
            {(['ALL', 'IMMEDIATE', 'HIGH', 'MONITOR'] as const).map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                  categoryFilter === cat
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/50'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                }`}
              >
                {cat === 'ALL' ? 'All Directives' : cat}
              </button>
            ))}
          </div>

          <div className="space-y-3">
            {filteredActions.map((act) => (
              <div
                key={act.id}
                className={`p-3.5 rounded-xl border transition-all flex flex-col md:flex-row md:items-start justify-between gap-3 ${
                  act.status === 'Completed'
                    ? 'bg-slate-900/40 border-slate-800 opacity-85'
                    : act.priority === 'IMMEDIATE'
                    ? 'bg-[#181119] border-red-900/50 shadow-md'
                    : act.priority === 'HIGH'
                    ? 'bg-[#1a1714] border-orange-900/40 shadow'
                    : 'bg-[#121824] border-slate-800'
                }`}
              >
                <div className="space-y-1.5 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${
                        act.priority === 'IMMEDIATE'
                          ? 'bg-red-950 text-red-400 border border-red-500/40'
                          : act.priority === 'HIGH'
                          ? 'bg-orange-950 text-orange-400 border border-orange-500/40'
                          : 'bg-yellow-950 text-yellow-400 border border-yellow-500/40'
                      }`}
                    >
                      {act.priority}
                    </span>
                    <span className="text-[11px] text-slate-400 font-medium">{act.assignedAgency}</span>
                  </div>

                  <h4 className="text-xs font-bold text-slate-100">{act.title}</h4>
                  <p className="text-[11px] text-slate-300 leading-relaxed">{act.description}</p>
                </div>

                <div className="shrink-0 flex flex-col items-end gap-1">
                  <button
                    id={`action-status-btn-${act.id}`}
                    onClick={() => toggleActionStatus(act.id)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition shadow-sm ${
                      act.status === 'Completed'
                        ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-500/60 hover:bg-emerald-900'
                        : act.status === 'In Progress'
                        ? 'bg-blue-950/90 text-blue-300 border border-blue-500/60 hover:bg-blue-900'
                        : 'bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700'
                    }`}
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>{act.status}</span>
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
