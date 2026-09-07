import React, { useState } from 'react';
import {
  History,
  Calendar,
  AlertTriangle,
  TrendingUp,
  BarChart3,
  MapPin,
  Flame,
  FileSpreadsheet,
} from 'lucide-react';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  CartesianGrid,
} from 'recharts';
import { historicalLandslides, landslideIncidentsByState } from '../data/mockData';

export const HistoricalAnalysisPage: React.FC = () => {
  const [selectedYear, setSelectedYear] = useState<string>('ALL');

  // Monsoon seasonal monthly trend data
  const monthlyMonsoonTrend = [
    { month: 'Jan', incidents: 8, avgRainfall: 18 },
    { month: 'Feb', incidents: 12, avgRainfall: 26 },
    { month: 'Mar', incidents: 25, avgRainfall: 64 },
    { month: 'Apr', incidents: 72, avgRainfall: 140 },
    { month: 'May', incidents: 195, avgRainfall: 280 },
    { month: 'Jun', incidents: 480, avgRainfall: 520 },
    { month: 'Jul', incidents: 540, avgRainfall: 590 },
    { month: 'Aug', incidents: 460, avgRainfall: 490 },
    { month: 'Sep', incidents: 310, avgRainfall: 360 },
    { month: 'Oct', incidents: 95, avgRainfall: 110 },
    { month: 'Nov', incidents: 18, avgRainfall: 24 },
    { month: 'Dec', incidents: 6, avgRainfall: 12 },
  ];

  // 10-Year historical frequency trend
  const tenYearTrend = [
    { year: '2015', count: 210 },
    { year: '2016', count: 245 },
    { year: '2017', count: 312 },
    { year: '2018', count: 285 },
    { year: '2019', count: 340 },
    { year: '2020', count: 380 },
    { year: '2021', count: 410 },
    { year: '2022', count: 475 },
    { year: '2023', count: 520 },
    { year: '2024', count: 468 },
  ];

  const filteredIncidents = historicalLandslides.filter((item) => {
    if (selectedYear === 'ALL') return true;
    return item.year.toString() === selectedYear;
  });

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-indigo-950/80 border border-indigo-500/40 flex items-center justify-center text-indigo-400">
            <History className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-indigo-400 uppercase font-mono font-bold tracking-wider">
              Geological Survey & Historical Baseline (GSI Archive)
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              NER Landslide Historical Intelligence
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400">Archived Incidents:</span>
          <span className="px-2.5 py-1 rounded bg-indigo-950/90 text-indigo-300 font-bold border border-indigo-700/50">
            2,148 Records (1998–2024)
          </span>
        </div>
      </div>

      {/* Analytics Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* 1. Monsoon Vulnerability Curve (Monthly Breakdown) */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Monsoon Vulnerability Distribution (Monthly Aggregation)
              </h3>
              <p className="text-[10px] text-slate-400">
                Peak slope instability aligns with Southwest Monsoon peak (June–August)
              </p>
            </div>
            <div className="flex items-center gap-3 text-[10px] font-mono">
              <span className="text-cyan-400">■ Rainfall</span>
              <span className="text-red-400">● Landslides</span>
            </div>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={monthlyMonsoonTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <XAxis dataKey="month" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Bar dataKey="incidents" fill="#ef4444" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* 2. 10-Year Escalation Curve */}
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Decadal Frequency Trajectory (2015–2024)
              </h3>
              <p className="text-[10px] text-slate-400">
                Annual frequency increasing +120% due to highway construction & extreme rain bursts
              </p>
            </div>
          </div>

          <div className="h-56 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={tenYearTrend} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="year" stroke="#64748b" fontSize={10} tickLine={false} />
                <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '8px',
                    fontSize: '11px',
                  }}
                />
                <Line
                  type="monotone"
                  dataKey="count"
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#0284c7' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Catalog of Major Historical Catastrophes */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-100 font-display">
              Major Historical Landslide Events Catalog
            </h3>
            <p className="text-[11px] text-slate-400">
              Verified ground ground-truth events used to calibrate AI susceptibility weights
            </p>
          </div>

          <div className="flex items-center gap-2 text-xs">
            <span className="text-slate-400">Filter Year:</span>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(e.target.value)}
              className="bg-slate-900 border border-slate-700 rounded-md px-2 py-1 text-slate-200 text-xs font-mono outline-none"
            >
              <option value="ALL">All Years</option>
              <option value="2024">2024</option>
              <option value="2023">2023</option>
              <option value="2022">2022</option>
              <option value="2020">2020</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 text-[10px] uppercase font-mono tracking-wider">
                <th className="py-2 px-3">Year / Date</th>
                <th className="py-2 px-3">Location & District</th>
                <th className="py-2 px-3">State</th>
                <th className="py-2 px-3">24h Rainfall</th>
                <th className="py-2 px-3">Fatalities</th>
                <th className="py-2 px-3">Damage & Highway Disruption</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 font-sans">
              {filteredIncidents.map((inc) => (
                <tr key={inc.id} className="hover:bg-slate-800/40 transition">
                  <td className="py-2.5 px-3 font-mono font-bold text-cyan-400">{inc.year}</td>
                  <td className="py-2.5 px-3 font-semibold text-slate-200">{inc.locationName}</td>
                  <td className="py-2.5 px-3 text-slate-400">{inc.state}</td>
                  <td className="py-2.5 px-3 font-mono text-cyan-300">{inc.rainfallRecorded} mm</td>
                  <td className="py-2.5 px-3">
                    <span className="px-1.5 py-0.5 rounded text-[10px] font-bold font-mono bg-red-950 text-red-400 border border-red-800/50">
                      {inc.fatalities} Lives
                    </span>
                  </td>
                  <td className="py-2.5 px-3 text-slate-300 max-w-md">{inc.damageDescription}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
