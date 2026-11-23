import React, { useState, useEffect } from 'react';
import { History, Database, AlertCircle } from 'lucide-react';
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
import { historicalLandslides } from '../data/mockData';
import { environmentApi, InventoryDiscoveryResponse } from '../services/environmentApi';

export const HistoricalAnalysisPage: React.FC = () => {
  const [selectedYear, setSelectedYear] = useState<string>('ALL');
  const [discovery, setDiscovery] = useState<InventoryDiscoveryResponse | null>(null);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    environmentApi
      .getInventoryDiscovery()
      .then((res) => {
        if (active) setDiscovery(res);
      })
      .catch((err: unknown) => {
        if (active) setDiscoveryError(err instanceof Error ? err.message : 'Unable to load discovery status');
      });
    return () => {
      active = false;
    };
  }, []);

  // Illustrative prototype seasonality curves (explicitly labeled as simulated demo data)
  const monthlyMonsoonTrend = [
    { month: 'Jan', incidents: 8 },
    { month: 'Feb', incidents: 12 },
    { month: 'Mar', incidents: 25 },
    { month: 'Apr', incidents: 72 },
    { month: 'May', incidents: 195 },
    { month: 'Jun', incidents: 480 },
    { month: 'Jul', incidents: 540 },
    { month: 'Aug', incidents: 460 },
    { month: 'Sep', incidents: 310 },
    { month: 'Oct', incidents: 95 },
    { month: 'Nov', incidents: 18 },
    { month: 'Dec', incidents: 6 },
  ];

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
            <span className="text-[10px] text-cyan-400 uppercase font-mono font-bold tracking-wider">
              Official Inventory Discovery & Prototype Archive
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              NER Landslide Inventory Status
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-2 text-xs font-mono">
          <span className="text-slate-400">Verified ML Labels:</span>
          <span className="px-2.5 py-1 rounded bg-amber-950/90 text-amber-300 font-bold border border-amber-700/50">
            {discovery ? `${discovery.verified_pilot_landslide_records_count} Ingested (0 Fabricated)` : 'Loading...'}
          </span>
        </div>
      </div>

      {/* REAL Official Landslide Inventory Discovery Status (from /api/v1/inventory/discovery) */}
      <div className="bg-[#0f172a] border border-cyan-900/50 rounded-xl p-4 shadow-xl space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2 pb-2 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Database className="w-4 h-4 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-slate-100 font-display">
                Dataset D — Official Landslide Inventory Discovery (Dima Hasao Pilot)
              </h3>
              <p className="text-[11px] text-slate-400">
                Live probe status of official repositories required before supervised RF/XGBoost training
              </p>
            </div>
          </div>
          {discovery?.discovery_timestamp && (
            <span className="text-[10px] font-mono text-slate-400">
              Probed: {new Date(discovery.discovery_timestamp).toUTCString()}
            </span>
          )}
        </div>

        {discoveryError ? (
          <div className="p-3 rounded-lg bg-rose-950/30 border border-rose-700/40 text-xs text-rose-300 flex items-center gap-2">
            <AlertCircle className="w-4 h-4" />
            <span>{discoveryError}</span>
          </div>
        ) : !discovery ? (
          <div className="text-xs text-slate-400 font-mono py-4">Loading inventory discovery probe results...</div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {discovery.providers.map((prov) => (
              <div
                key={prov.provider}
                className="p-3 rounded-lg bg-slate-900/80 border border-slate-800 space-y-2 text-xs"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="font-bold text-slate-100">{prov.provider}</div>
                    <div className="text-[11px] text-slate-400">{prov.dataset}</div>
                  </div>
                  <span
                    className={`px-1.5 py-0.5 rounded text-[9px] font-mono uppercase shrink-0 ${
                      prov.requires_registration
                        ? 'bg-amber-950 text-amber-300 border border-amber-700/50'
                        : 'bg-cyan-950 text-cyan-300 border border-cyan-700/50'
                    }`}
                  >
                    {prov.requires_registration ? 'Registration Req.' : 'Public API'}
                  </span>
                </div>
                <div className="text-[11px] text-amber-200/90 bg-amber-950/20 border border-amber-800/30 rounded p-2">
                  {prov.blocker_note}
                </div>
                <div className="text-[10px] text-slate-400 space-y-1">
                  <div className="font-mono text-slate-500 uppercase">Resolution Steps:</div>
                  <ul className="list-disc list-inside space-y-0.5">
                    {prov.resolution_steps.slice(0, 2).map((step, idx) => (
                      <li key={idx}>{step}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Legacy Prototype Charts (Clearly Labeled as Illustrative Demo Data) */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Monsoon Seasonality Pattern (Illustrative Prototype)
              </h3>
              <p className="text-[10px] text-slate-400">
                Simulated monthly distribution — not derived from ingested GSI/NRSC database
              </p>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-300 border border-amber-700/40 text-[9px] font-mono">
              Demo Chart
            </span>
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
                <Bar dataKey="incidents" name="Illustrative Incidents" fill="#ef4444" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl">
          <div className="flex items-center justify-between mb-3">
            <div>
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Decadal Trend Reference (Illustrative Prototype)
              </h3>
              <p className="text-[10px] text-slate-400">
                Placeholder prototype series awaiting verified GSI Bhukosh multi-year export
              </p>
            </div>
            <span className="px-1.5 py-0.5 rounded bg-amber-950/70 text-amber-300 border border-amber-700/40 text-[9px] font-mono">
              Demo Chart
            </span>
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
                  name="Illustrative Count"
                  stroke="#38bdf8"
                  strokeWidth={2.5}
                  dot={{ r: 4, fill: '#0284c7' }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Prototype Event Samples */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-2 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-slate-100 font-display">
              Sample Reference Events ({filteredIncidents.length} Prototype Entries)
            </h3>
            <p className="text-[11px] text-slate-400">
              Curated demo reference table — NOT used as ML training labels
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
                <th className="py-2 px-3">Year</th>
                <th className="py-2 px-3">Location & District</th>
                <th className="py-2 px-3">State</th>
                <th className="py-2 px-3">Ref. 24h Rain</th>
                <th className="py-2 px-3">Fatalities</th>
                <th className="py-2 px-3">Summary</th>
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
                      {inc.fatalities}
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
