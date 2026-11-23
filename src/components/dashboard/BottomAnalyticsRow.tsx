import React, { useEffect, useState } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  BarChart,
  PieChart,
  Pie,
  Cell,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
} from 'recharts';
import { landslideIncidentsByState } from '../../data/mockData';
import { RiskLocation } from '../../types/disaster';
import { environmentApi, RainfallHistoryResponse } from '../../services/environmentApi';

interface BottomAnalyticsRowProps {
  locations: RiskLocation[];
}

export const BottomAnalyticsRow: React.FC<BottomAnalyticsRowProps> = ({ locations }) => {
  const [rainHistory, setRainHistory] = useState<RainfallHistoryResponse | null>(null);
  const [rainError, setRainError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    environmentApi
      .getRainfallHistory()
      .then((res) => {
        if (active) setRainHistory(res);
      })
      .catch((err: unknown) => {
        if (active) setRainError(err instanceof Error ? err.message : 'Rainfall history unavailable');
      });
    return () => {
      active = false;
    };
  }, []);

  // Compute exact distribution from active locations (never hardcoded)
  const totalLocations = locations.length;
  const counts = {
    CRITICAL: locations.filter((l) => l.calculatedLevel === 'CRITICAL').length,
    HIGH: locations.filter((l) => l.calculatedLevel === 'HIGH').length,
    MODERATE: locations.filter((l) => l.calculatedLevel === 'MODERATE').length,
    LOW: locations.filter((l) => l.calculatedLevel === 'LOW').length,
  };
  const pct = (n: number) => (totalLocations > 0 ? `${Math.round((n / totalLocations) * 100)}%` : '0%');

  const distributionData = [
    { name: 'Critical', value: counts.CRITICAL, percent: pct(counts.CRITICAL), color: '#ef4444' },
    { name: 'High', value: counts.HIGH, percent: pct(counts.HIGH), color: '#f97316' },
    { name: 'Moderate', value: counts.MODERATE, percent: pct(counts.MODERATE), color: '#eab308' },
    { name: 'Low', value: counts.LOW, percent: pct(counts.LOW), color: '#22c55e' },
  ];

  const imergChartData = (rainHistory?.observations || []).map((obs) => ({
    date: obs.date.slice(5), // MM-DD
    rain24h: obs.rainfall_24h_mm,
    rain72h: obs.rainfall_72h_mm,
    missing: obs.missing_24h,
  }));

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mt-3">
      {/* 1. REAL Observed NASA GPM IMERG Rainfall (Dima Hasao Pilot) */}
      <div className="lg:col-span-5 bg-[#0f172a] rounded-xl border border-cyan-900/50 p-3.5 flex flex-col justify-between shadow-xl">
        <div className="flex items-center justify-between mb-1.5 gap-2">
          <div>
            <div className="flex items-center gap-2">
              <h4 className="text-xs font-bold text-slate-100 font-display">
                Observed NASA GPM IMERG Rainfall — Dima Hasao
              </h4>
              <span className="px-1.5 py-0.5 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-500/40 text-[9px] font-mono uppercase">
                Verified Data
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">
              {rainHistory
                ? `${rainHistory.interval_start} to ${rainHistory.interval_end} · ${rainHistory.valid_observation_days} valid / ${rainHistory.missing_observation_days} missing (null)`
                : 'Loading NASA GPM IMERG daily series...'}
            </p>
          </div>
          <div className="flex items-center gap-2.5 text-[10px] font-medium shrink-0">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-cyan-500"></span>
              <span className="text-slate-400">24h</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-1 bg-amber-400 rounded"></span>
              <span className="text-slate-400">72h</span>
            </div>
          </div>
        </div>

        <div className="h-44 w-full">
          {rainError ? (
            <div className="h-full flex items-center justify-center text-xs text-rose-400 font-mono">
              Observed rainfall unavailable: {rainError}
            </div>
          ) : imergChartData.length === 0 ? (
            <div className="h-full flex items-center justify-center text-xs text-slate-500 font-mono">
              Fetching NASA GPM IMERG series...
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={imergChartData} margin={{ top: 10, right: 10, left: -18, bottom: 0 }}>
                <XAxis dataKey="date" stroke="#64748b" fontSize={9} tickLine={false} minTickGap={16} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  formatter={(value: unknown, name: string) => [
                    value === null || value === undefined ? 'Missing (null)' : `${Number(value).toFixed(1)} mm`,
                    name === 'rain24h' ? '24h IMERG' : '72h Cumulative',
                  ]}
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '11px',
                    color: '#f8fafc',
                  }}
                />
                <Bar dataKey="rain24h" fill="#06b6d4" radius={[2, 2, 0, 0]} barSize={7} />
                <Line
                  type="monotone"
                  dataKey="rain72h"
                  stroke="#fbbf24"
                  strokeWidth={1.8}
                  dot={false}
                  connectNulls={false}
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      {/* 2. Legacy Prototype Regional Reference Chart (Explicitly Labeled) */}
      <div className="lg:col-span-4 bg-[#0f172a] rounded-xl border border-slate-800 p-3.5 flex flex-col justify-between shadow-xl">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-bold text-slate-100 font-display">
            NER State Incidents (Demo Dataset)
          </h4>
          <span className="px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-300 border border-amber-600/40 text-[9px] font-mono">
            Simulated Demo
          </span>
        </div>

        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={landslideIncidentsByState}
              margin={{ top: 18, right: 10, left: -25, bottom: 15 }}
            >
              <XAxis
                dataKey="state"
                stroke="#64748b"
                fontSize={9}
                tickLine={false}
                interval={0}
                tickFormatter={(val) => {
                  if (val === 'Arunachal Pradesh') return 'Arunachal';
                  return val;
                }}
              />
              <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '11px',
                  color: '#f8fafc',
                }}
              />
              <Bar
                dataKey="incidents"
                radius={[4, 4, 0, 0]}
                label={{
                  position: 'top',
                  fill: '#e2e8f0',
                  fontSize: 10,
                  fontFamily: 'monospace',
                }}
              >
                {landslideIncidentsByState.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 3. Dynamic Risk Distribution (Computed Strictly from Active Locations) */}
      <div className="lg:col-span-3 bg-[#0f172a] rounded-xl border border-slate-800 p-3.5 flex flex-col justify-between shadow-xl">
        <div className="flex items-center justify-between mb-1">
          <h4 className="text-xs font-bold text-slate-100 font-display">
            Heuristic Risk Distribution
          </h4>
          <span className="text-[9px] font-mono text-amber-300">Prototype</span>
        </div>

        <div className="flex items-center justify-between h-44">
          <div className="relative w-32 h-32">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distributionData.filter((d) => d.value > 0)}
                  cx="50%"
                  cy="50%"
                  innerRadius={32}
                  outerRadius={50}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {distributionData
                    .filter((d) => d.value > 0)
                    .map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} stroke="#0f172a" strokeWidth={2} />
                    ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-lg font-bold font-mono text-slate-100 leading-none">
                {totalLocations}
              </span>
              <span className="text-[9px] text-slate-400 mt-0.5 uppercase tracking-wider text-center">
                Nodes
              </span>
            </div>
          </div>

          <div className="space-y-1.5 text-xs flex-1 pl-2">
            {distributionData.map((item) => (
              <div key={item.name} className="flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-1.5">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: item.color }} />
                  <span className="text-slate-300">{item.name}</span>
                </div>
                <div className="font-mono text-slate-400 text-right">
                  <span className="font-bold text-slate-200 mr-1">{item.value}</span>
                  <span className="text-[10px]">({item.percent})</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
