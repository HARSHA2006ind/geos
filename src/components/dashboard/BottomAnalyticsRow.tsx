import React from 'react';
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
import { rainfallTrendNER, landslideIncidentsByState } from '../../data/mockData';
import { RiskLocation } from '../../types/disaster';

interface BottomAnalyticsRowProps {
  locations: RiskLocation[];
}

export const BottomAnalyticsRow: React.FC<BottomAnalyticsRowProps> = ({ locations }) => {
  // Compute distribution from locations (or standard base distribution matching 144)
  const distributionData = [
    { name: 'Critical', value: 12, percent: '8%', color: '#ef4444' },
    { name: 'High', value: 38, percent: '26%', color: '#f97316' },
    { name: 'Moderate', value: 94, percent: '59%', color: '#eab308' },
    { name: 'Low', value: 20, percent: '14%', color: '#22c55e' },
  ];

  return (
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 mt-3">
      {/* 1. Rainfall Trend (NER) */}
      <div className="lg:col-span-4 bg-[#0f172a] rounded-xl border border-slate-800 p-3.5 flex flex-col justify-between shadow-xl">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-bold text-slate-100 font-display">Rainfall Trend (NER)</h4>
          <div className="flex items-center gap-3 text-[10px] font-medium">
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-2.5 rounded-sm bg-cyan-500"></span>
              <span className="text-slate-400">Rainfall (mm)</span>
            </div>
            <div className="flex items-center gap-1">
              <span className="w-2.5 h-1 bg-red-500 rounded"></span>
              <span className="text-slate-400">Landslides</span>
            </div>
          </div>
        </div>

        <div className="h-44 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={rainfallTrendNER} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
              <XAxis dataKey="date" stroke="#64748b" fontSize={10} tickLine={false} />
              <YAxis yAxisId="left" stroke="#64748b" fontSize={10} tickLine={false} domain={[0, 200]} />
              <YAxis yAxisId="right" orientation="right" hide domain={[0, 15]} />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#0f172a',
                  borderColor: '#334155',
                  borderRadius: '8px',
                  fontSize: '11px',
                  color: '#f8fafc',
                }}
              />
              <Bar yAxisId="left" dataKey="rainfall" fill="#0284c7" radius={[3, 3, 0, 0]} barSize={18} />
              <Line
                yAxisId="right"
                type="monotone"
                dataKey="landslides"
                stroke="#ef4444"
                strokeWidth={2}
                dot={{ r: 3, fill: '#ef4444' }}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* 2. Landslide Incidents by State (2020-2024) */}
      <div className="lg:col-span-5 bg-[#0f172a] rounded-xl border border-slate-800 p-3.5 flex flex-col justify-between shadow-xl">
        <div className="flex items-center justify-between mb-2">
          <h4 className="text-xs font-bold text-slate-100 font-display">
            Landslide Incidents by State (2020-2024)
          </h4>
          <span className="text-[10px] text-slate-500 font-mono">Total: 1,870 Records</span>
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
                  if (val === 'Meghalaya') return 'Meghalaya';
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

      {/* 3. Risk Distribution (Current) */}
      <div className="lg:col-span-3 bg-[#0f172a] rounded-xl border border-slate-800 p-3.5 flex flex-col justify-between shadow-xl">
        <div className="flex items-center justify-between mb-1">
          <h4 className="text-xs font-bold text-slate-100 font-display">
            Risk Distribution (Current)
          </h4>
        </div>

        <div className="flex items-center justify-between h-44">
          {/* Donut Chart with center label */}
          <div className="relative w-36 h-36">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={distributionData}
                  cx="50%"
                  cy="50%"
                  innerRadius={36}
                  outerRadius={56}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {distributionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} stroke="#0f172a" strokeWidth={2} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <span className="text-lg font-bold font-mono text-slate-100 leading-none">144</span>
              <span className="text-[9px] text-slate-400 mt-0.5 uppercase tracking-wider text-center">
                Total Locations
              </span>
            </div>
          </div>

          {/* Legend Table */}
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
