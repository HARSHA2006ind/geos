import React from 'react';
import {
  AlertTriangle,
  Flame,
  ShieldAlert,
  Bell,
  Users,
  Building2,
} from 'lucide-react';
import { RiskLocation, AlertItem } from '../../types/disaster';

interface StatCardsProps {
  locations: RiskLocation[];
  alerts: AlertItem[];
  onFilterByLevel?: (level: string) => void;
}

export const StatCards: React.FC<StatCardsProps> = ({ locations, alerts, onFilterByLevel }) => {
  let criticalCount = 0;
  let highCount = 0;
  let moderateCount = 0;
  let totalPopExposed = 0;
  let totalInfraAtRisk = 0;

  locations.forEach((l) => {
    if (l.calculatedLevel === 'CRITICAL') {
      criticalCount++;
      totalPopExposed += l.populationExposed;
      totalInfraAtRisk += l.infrastructure.roads + l.infrastructure.bridges;
    } else if (l.calculatedLevel === 'HIGH') {
      highCount++;
      totalPopExposed += Math.round(l.populationExposed * 0.4);
      totalInfraAtRisk += Math.round((l.infrastructure.roads + l.infrastructure.bridges) * 0.4);
    } else if (l.calculatedLevel === 'MODERATE') {
      moderateCount++;
    }
  });

  const activeAlertsCount = alerts.filter((a) => a.status === 'ACTIVE').length;

  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between px-0.5 text-[10px] font-mono text-slate-400">
        <span>PROTOTYPE HEURISTIC SUMMARY ({locations.length} SIMULATED NER NODES)</span>
        <span className="text-amber-300/90">Simulated Demo Layer — Not Trained ML Output</span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-3">
        {/* 1. Critical Zones */}
        <div
          id="stat-card-critical-zones"
          onClick={() => onFilterByLevel?.('CRITICAL')}
          className="bg-[#131929] hover:bg-[#182137] border border-red-900/40 rounded-xl p-3.5 flex flex-col justify-between transition-all cursor-pointer shadow-lg hover:border-red-600/50 group"
        >
          <div className="flex items-center justify-between">
            <span className="text-2xl lg:text-3xl font-bold font-mono text-red-500 tracking-tight group-hover:scale-105 transition-transform">
              {criticalCount}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-red-950/60 border border-red-800/40 text-[10px] font-mono text-red-300">
              ≥75 idx
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-300">Critical Zones</span>
            <div className="w-6 h-6 rounded-md bg-red-950/80 flex items-center justify-center text-red-400">
              <Flame className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* 2. High Risk Zones */}
        <div
          id="stat-card-high-risk-zones"
          onClick={() => onFilterByLevel?.('HIGH')}
          className="bg-[#131929] hover:bg-[#182137] border border-orange-900/40 rounded-xl p-3.5 flex flex-col justify-between transition-all cursor-pointer shadow-lg hover:border-orange-600/50 group"
        >
          <div className="flex items-center justify-between">
            <span className="text-2xl lg:text-3xl font-bold font-mono text-orange-400 tracking-tight group-hover:scale-105 transition-transform">
              {highCount}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-orange-950/60 border border-orange-800/40 text-[10px] font-mono text-orange-300">
              50–74 idx
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-300">High Risk Zones</span>
            <div className="w-6 h-6 rounded-md bg-orange-950/80 flex items-center justify-center text-orange-400">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* 3. Moderate Risk Zones */}
        <div
          id="stat-card-moderate-risk-zones"
          onClick={() => onFilterByLevel?.('MODERATE')}
          className="bg-[#131929] hover:bg-[#182137] border border-yellow-900/40 rounded-xl p-3.5 flex flex-col justify-between transition-all cursor-pointer shadow-lg hover:border-yellow-600/50 group"
        >
          <div className="flex items-center justify-between">
            <span className="text-2xl lg:text-3xl font-bold font-mono text-yellow-400 tracking-tight group-hover:scale-105 transition-transform">
              {moderateCount}
            </span>
            <span className="px-1.5 py-0.5 rounded bg-yellow-950/60 border border-yellow-800/40 text-[10px] font-mono text-yellow-300">
              25–49 idx
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-300">Moderate Zones</span>
            <div className="w-6 h-6 rounded-md bg-yellow-950/80 flex items-center justify-center text-yellow-400">
              <ShieldAlert className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* 4. Active Alerts */}
        <div
          id="stat-card-active-alerts"
          className="bg-[#131929] hover:bg-[#182137] border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between transition-all shadow-lg hover:border-slate-700 group"
        >
          <div className="flex items-center justify-between">
            <span className="text-2xl lg:text-3xl font-bold font-mono text-rose-400 tracking-tight group-hover:scale-105 transition-transform">
              {activeAlertsCount}
            </span>
            <span className="text-[10px] font-mono text-rose-300 bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-800/40">
              Session
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-300">Active Alerts</span>
            <div className="w-6 h-6 rounded-md bg-rose-950/80 flex items-center justify-center text-rose-400">
              <Bell className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* 5. Population Exposed (Demo) */}
        <div
          id="stat-card-population-exposed"
          className="bg-[#131929] hover:bg-[#182137] border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between transition-all shadow-lg hover:border-purple-600/40 group"
        >
          <div className="flex items-center justify-between">
            <span className="text-xl lg:text-2xl xl:text-3xl font-bold font-mono text-purple-300 tracking-tight group-hover:scale-105 transition-transform">
              {totalPopExposed.toLocaleString()}
            </span>
            <span className="text-[10px] font-mono text-purple-400 bg-purple-950/60 px-1 rounded border border-purple-800/40">
              Demo Est.
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-300">Pop. Exposure</span>
            <div className="w-6 h-6 rounded-md bg-purple-950/80 flex items-center justify-center text-purple-400">
              <Users className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>

        {/* 6. Infrastructure at Risk (Demo) */}
        <div
          id="stat-card-infrastructure-at-risk"
          className="bg-[#131929] hover:bg-[#182137] border border-slate-800 rounded-xl p-3.5 flex flex-col justify-between transition-all shadow-lg hover:border-cyan-600/40 group"
        >
          <div className="flex items-center justify-between">
            <span className="text-2xl lg:text-3xl font-bold font-mono text-cyan-400 tracking-tight group-hover:scale-105 transition-transform">
              {totalInfraAtRisk}
            </span>
            <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 px-1 rounded border border-cyan-800/40">
              Demo Est.
            </span>
          </div>
          <div className="flex items-center justify-between mt-2 pt-1 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-300">Road & Bridge Units</span>
            <div className="w-6 h-6 rounded-md bg-cyan-950/80 flex items-center justify-center text-cyan-400">
              <Building2 className="w-3.5 h-3.5" />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
