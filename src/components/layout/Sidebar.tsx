import React from 'react';
import {
  LayoutDashboard,
  Map as MapIcon,
  Activity,
  SlidersHorizontal,
  ShieldAlert,
  FileText,
  Bell,
  History,
  Mountain,
  ChevronLeft,
  ChevronRight,
  UserCheck,
} from 'lucide-react';

export type NavPage =
  | 'command-center'
  | 'risk-map'
  | 'risk-analysis'
  | 'what-if-simulation'
  | 'impact-response'
  | 'field-reports'
  | 'alerts'
  | 'historical-analysis';

interface SidebarProps {
  activePage: NavPage;
  onNavigate: (page: NavPage) => void;
  activeAlertsCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activePage,
  onNavigate,
  activeAlertsCount,
}) => {
  const [collapsed, setCollapsed] = React.useState(false);

  const navItems = [
    { id: 'command-center', label: 'Command Center', icon: LayoutDashboard },
    { id: 'risk-map', label: 'Risk Map', icon: MapIcon },
    { id: 'risk-analysis', label: 'Risk Analysis', icon: Activity },
    { id: 'what-if-simulation', label: 'What-If Simulation', icon: SlidersHorizontal },
    { id: 'impact-response', label: 'Impact & Response', icon: ShieldAlert },
    { id: 'field-reports', label: 'Field Reports', icon: FileText },
    { id: 'alerts', label: 'Alerts', icon: Bell, badge: activeAlertsCount },
    { id: 'historical-analysis', label: 'Historical Analysis', icon: History },
  ];

  return (
    <aside
      className={`bg-[#0d1424] border-r border-slate-800/80 flex flex-col justify-between transition-all duration-300 relative z-40 select-none ${
        collapsed ? 'w-20' : 'w-64'
      }`}
    >
      {/* Top Branding Section */}
      <div>
        <div className="p-4 border-b border-slate-800/70 flex items-center justify-between">
          {!collapsed ? (
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 p-0.5 shadow-lg shadow-cyan-500/20 flex items-center justify-center shrink-0">
                <div className="w-full h-full bg-[#0b101b] rounded-[7px] flex items-center justify-center">
                  <Mountain className="w-5 h-5 text-cyan-400" />
                </div>
              </div>
              <div className="overflow-hidden">
                <h1 className="font-bold text-slate-100 text-base tracking-tight leading-none font-display">
                  GeoResilience-NER
                </h1>
                <p className="text-[11px] font-semibold text-cyan-400 mt-1 leading-tight">
                  AI-Powered Landslide Intelligence
                </p>
                <p className="text-[10px] text-slate-500 tracking-wide mt-0.5">
                  Safer Hills, Stronger Communities
                </p>
              </div>
            </div>
          ) : (
            <div className="mx-auto w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-500 to-blue-600 p-0.5 flex items-center justify-center">
              <div className="w-full h-full bg-[#0b101b] rounded-[7px] flex items-center justify-center">
                <Mountain className="w-5 h-5 text-cyan-400" />
              </div>
            </div>
          )}

          <button
            id="sidebar-collapse-toggle-btn"
            onClick={() => setCollapsed(!collapsed)}
            className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition"
            title={collapsed ? 'Expand Sidebar' : 'Collapse Sidebar'}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        {/* Navigation items */}
        <nav className="p-3 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = activePage === item.id;
            return (
              <button
                key={item.id}
                id={`sidebar-nav-btn-${item.id}`}
                onClick={() => onNavigate(item.id as NavPage)}
                className={`w-full flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-blue-600/90 text-white shadow-md shadow-blue-600/30 font-semibold'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`}
                title={collapsed ? item.label : undefined}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-white' : 'text-slate-400'}`} />
                {!collapsed && (
                  <span className="flex-1 text-left truncate">{item.label}</span>
                )}
                {!collapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-red-500 text-white animate-pulse">
                    {item.badge}
                  </span>
                )}
                {collapsed && item.badge !== undefined && item.badge > 0 && (
                  <span className="absolute top-2 right-2 w-2 h-2 rounded-full bg-red-500" />
                )}
              </button>
            );
          })}
        </nav>
      </div>

      {/* Bottom System Health & Authority Profile */}
      <div className="p-3 space-y-3 border-t border-slate-800/70">
        {!collapsed ? (
          <div className="bg-[#090d16] p-3 rounded-lg border border-slate-800 text-[11px] space-y-2">
            <div className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">
              System Status
            </div>
            <div className="flex items-center gap-2 text-emerald-400 font-semibold font-mono text-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
              <span>SYSTEM OPERATIONAL</span>
            </div>
            <div className="space-y-1 text-slate-400 text-[10px] pt-1">
              <div className="flex justify-between items-center">
                <span>Rainfall Data</span>
                <span className="text-emerald-400 font-mono">Online</span>
              </div>
              <div className="flex justify-between items-center">
                <span>Terrain Data</span>
                <span className="text-emerald-400 font-mono">Available</span>
              </div>
              <div className="flex justify-between items-center">
                <span>Historical Data</span>
                <span className="text-emerald-400 font-mono">Available</span>
              </div>
              <div className="flex justify-between items-center">
                <span>Field Reports</span>
                <span className="text-emerald-400 font-mono">Active</span>
              </div>
              <div className="flex justify-between items-center">
                <span>AI Risk Engine</span>
                <span className="text-emerald-400 font-mono">Operational</span>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex justify-center" title="System Operational">
            <div className="w-3 h-3 rounded-full bg-emerald-400 animate-pulse"></div>
          </div>
        )}

        {/* User profile */}
        <div className="flex items-center gap-2.5 px-2 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800/80">
          <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 flex items-center justify-center text-slate-300 shrink-0">
            <UserCheck className="w-4 h-4 text-cyan-400" />
          </div>
          {!collapsed && (
            <div className="overflow-hidden leading-tight">
              <div className="text-xs font-semibold text-slate-200 truncate">
                Disaster Management
              </div>
              <div className="text-[10px] text-slate-400 truncate">
                NER Authority
              </div>
            </div>
          )}
        </div>
      </div>
    </aside>
  );
};
