import React from 'react';
import { AlertTriangle, ChevronRight, ShieldAlert, Clock } from 'lucide-react';
import { AlertItem, RiskLocation } from '../../types/disaster';

interface RecentAlertsPanelProps {
  alerts: AlertItem[];
  locations: RiskLocation[];
  onSelectAlert: (alert: AlertItem) => void;
  onViewAllAlerts: () => void;
}

export const RecentAlertsPanel: React.FC<RecentAlertsPanelProps> = ({
  alerts,
  locations,
  onSelectAlert,
  onViewAllAlerts,
}) => {
  const recentAlerts = alerts.slice(0, 3);

  return (
    <div className="h-full flex flex-col bg-[#0f172a] rounded-xl border border-slate-800 p-4 overflow-hidden shadow-2xl">
      <div className="flex items-center justify-between pb-2.5 border-b border-slate-800">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4 text-red-400" />
          <h3 className="text-sm font-bold text-slate-100 font-display">Recent Alerts</h3>
        </div>
        <button
          id="recent-alerts-view-all-btn"
          onClick={onViewAllAlerts}
          className="text-xs font-semibold text-cyan-400 hover:text-cyan-300 flex items-center gap-0.5 transition"
        >
          <span>View All</span>
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="mt-3 space-y-2.5 flex-1 overflow-y-auto pr-0.5">
        {recentAlerts.map((alert) => {
          const isCritical = alert.riskLevel === 'CRITICAL';
          const badgeStyle = isCritical
            ? 'bg-red-950/80 text-red-400 border border-red-500/40'
            : 'bg-orange-950/80 text-orange-400 border border-orange-500/40';

          return (
            <div
              key={alert.id}
              className="bg-[#131929] hover:bg-[#182137] border border-slate-800 rounded-lg p-3 transition flex flex-col justify-between space-y-2 shadow-md"
            >
              <div>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase ${badgeStyle}`}>
                      {alert.riskLevel}
                    </span>
                  </div>
                  <span className="text-[10px] text-slate-400 font-mono flex items-center gap-1">
                    <Clock className="w-2.5 h-2.5" />
                    {alert.timestamp}
                  </span>
                </div>

                <div className="mt-1.5">
                  <div className="text-xs font-bold text-slate-200">{alert.locationName}</div>
                  <div className="text-[11px] font-mono font-semibold mt-0.5">
                    <span className="text-slate-400">Risk Score: </span>
                    <span className={isCritical ? 'text-red-400' : 'text-orange-400'}>
                      {alert.riskScore}/100
                    </span>
                  </div>
                </div>

                <div className="text-[11px] text-slate-400 mt-1 line-clamp-1">
                  {alert.trigger}
                </div>
                <div className="text-[10px] text-slate-500 mt-0.5 line-clamp-1">
                  {alert.potentialImpact}
                </div>
              </div>

              <button
                id={`alert-view-details-btn-${alert.id}`}
                onClick={() => onSelectAlert(alert)}
                className="w-full py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 rounded text-[11px] font-semibold transition border border-slate-700/80 text-center"
              >
                View Details
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
};
