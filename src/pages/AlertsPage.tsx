import React, { useState } from 'react';
import {
  Bell,
  Plus,
  Clock,
  ShieldAlert,
  CheckCircle,
  Radio,
  Share2,
  AlertTriangle,
  Flame,
  ArrowUpRight,
} from 'lucide-react';
import { AlertItem, RiskLocation } from '../types/disaster';

interface AlertsPageProps {
  alerts: AlertItem[];
  locations: RiskLocation[];
  onOpenCreateAlertModal: () => void;
  onUpdateAlertStatus: (alertId: string, newStatus: AlertItem['status']) => void;
}

export const AlertsPage: React.FC<AlertsPageProps> = ({
  alerts,
  locations,
  onOpenCreateAlertModal,
  onUpdateAlertStatus,
}) => {
  const [statusTab, setStatusTab] = useState<'ALL' | 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED'>('ALL');

  const filteredAlerts = alerts.filter((a) => {
    if (statusTab === 'ALL') return true;
    return a.status === statusTab;
  });

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-rose-950/80 border border-rose-500/40 flex items-center justify-center text-rose-400">
            <Bell className="w-5 h-5 animate-pulse" />
          </div>
          <div>
            <span className="text-[10px] text-rose-400 uppercase font-mono font-bold tracking-wider">
              Early Warning & Emergency Broadcast Registry
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              Regional Disaster Bulletins & Alerts
            </h2>
          </div>
        </div>

        <button
          id="alerts-page-create-alert-btn"
          onClick={onOpenCreateAlertModal}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-red-600 to-rose-600 hover:from-red-500 hover:to-rose-500 text-white font-bold rounded-lg shadow-lg shadow-red-600/30 text-xs transition"
        >
          <Plus className="w-4 h-4" />
          <span>Generate New Disaster Alert</span>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-2 border-b border-slate-800 pb-2 text-xs">
        {[
          { id: 'ALL', label: 'All Alerts', count: alerts.length },
          { id: 'ACTIVE', label: 'Active Sirens', count: alerts.filter((a) => a.status === 'ACTIVE').length },
          {
            id: 'ACKNOWLEDGED',
            label: 'Acknowledged',
            count: alerts.filter((a) => a.status === 'ACKNOWLEDGED').length,
          },
          { id: 'RESOLVED', label: 'Resolved', count: alerts.filter((a) => a.status === 'RESOLVED').length },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setStatusTab(tab.id as any)}
            className={`px-3 py-1.5 rounded-lg font-semibold flex items-center gap-2 transition ${
              statusTab === tab.id
                ? 'bg-blue-600 text-white'
                : 'text-slate-400 hover:text-slate-200 bg-slate-900 border border-slate-800'
            }`}
          >
            <span>{tab.label}</span>
            <span
              className={`px-1.5 py-0.2 rounded-full text-[10px] font-mono ${
                statusTab === tab.id ? 'bg-blue-800 text-white' : 'bg-slate-800 text-slate-400'
              }`}
            >
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* Alerts List */}
      <div className="space-y-3">
        {filteredAlerts.map((alert) => {
          const isCritical = alert.riskLevel === 'CRITICAL';
          const isHigh = alert.riskLevel === 'HIGH';

          return (
            <div
              key={alert.id}
              className={`bg-[#0f172a] border rounded-xl p-4 shadow-xl transition space-y-3 ${
                alert.status === 'ACTIVE'
                  ? isCritical
                    ? 'border-red-600/50 bg-[#160f14]'
                    : 'border-orange-600/50 bg-[#16120f]'
                  : 'border-slate-800 opacity-80'
              }`}
            >
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-2 pb-2 border-b border-slate-800/80">
                <div className="flex items-center gap-2.5">
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${
                      isCritical
                        ? 'bg-red-950 text-red-400 border border-red-500/40'
                        : isHigh
                        ? 'bg-orange-950 text-orange-400 border border-orange-500/40'
                        : 'bg-yellow-950 text-yellow-400 border border-yellow-500/40'
                    }`}
                  >
                    {alert.riskLevel} LEVEL
                  </span>
                  <h3 className="text-sm font-bold text-slate-100 font-display">
                    {alert.locationName}
                  </h3>
                  <span className="text-xs font-mono font-bold text-slate-400">
                    (Score: {alert.riskScore}/100)
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs font-mono text-slate-400">
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-slate-500" />
                    {alert.timestamp}
                  </span>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      alert.status === 'ACTIVE'
                        ? 'bg-red-950/80 text-red-400 border border-red-500/40 animate-pulse'
                        : alert.status === 'ACKNOWLEDGED'
                        ? 'bg-blue-950/80 text-blue-400 border border-blue-500/40'
                        : 'bg-emerald-950/80 text-emerald-400 border border-emerald-500/40'
                    }`}
                  >
                    STATUS: {alert.status}
                  </span>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs">
                <div className="p-2.5 bg-slate-900/80 rounded-lg border border-slate-800">
                  <span className="text-slate-400 text-[10px] uppercase font-bold block mb-0.5">
                    Trigger Condition
                  </span>
                  <p className="text-slate-200">{alert.trigger}</p>
                </div>
                <div className="p-2.5 bg-slate-900/80 rounded-lg border border-slate-800">
                  <span className="text-slate-400 text-[10px] uppercase font-bold block mb-0.5">
                    Potential Impact & Assets
                  </span>
                  <p className="text-slate-200">{alert.potentialImpact}</p>
                </div>
              </div>

              {/* Recommended Directives */}
              <div className="text-xs space-y-1">
                <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">
                  Mandatory SEOC Directives:
                </span>
                <ul className="list-disc list-inside space-y-0.5 text-slate-300 text-[11px]">
                  {alert.recommendedActions.map((rec, i) => (
                    <li key={i}>{rec}</li>
                  ))}
                </ul>
              </div>

              {/* Actions */}
              <div className="pt-2 border-t border-slate-800 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-[11px] text-slate-400 font-mono">
                  <Radio className="w-3.5 h-3.5 text-emerald-400" />
                  <span>Broadcasted via SMS (DoT) & Police VHF</span>
                </div>

                <div className="flex items-center gap-2">
                  {alert.status === 'ACTIVE' && (
                    <button
                      onClick={() => onUpdateAlertStatus(alert.id, 'ACKNOWLEDGED')}
                      className="px-3 py-1.5 rounded-lg bg-blue-950 hover:bg-blue-900 text-blue-300 border border-blue-500/40 text-xs font-semibold transition"
                    >
                      Acknowledge & Confirm
                    </button>
                  )}
                  {alert.status !== 'RESOLVED' && (
                    <button
                      onClick={() => onUpdateAlertStatus(alert.id, 'RESOLVED')}
                      className="px-3 py-1.5 rounded-lg bg-emerald-950 hover:bg-emerald-900 text-emerald-300 border border-emerald-500/40 text-xs font-semibold transition"
                    >
                      Mark Resolved
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
