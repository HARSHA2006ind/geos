import React from 'react';
import {
  Search,
  Clock,
  Bell,
  User,
  Radio,
  ChevronDown,
  Sparkles,
} from 'lucide-react';
import { NERState, RiskLocation } from '../../types/disaster';

interface HeaderProps {
  selectedState: NERState;
  onSelectState: (state: NERState) => void;
  locations: RiskLocation[];
  onSelectLocation: (loc: RiskLocation) => void;
  unreadAlertsCount: number;
  onOpenAlerts: () => void;
  isDemoMode?: boolean;
  onToggleDemoMode?: () => void;
}

const statesList: NERState[] = [
  'All NER',
  'Arunachal Pradesh',
  'Assam',
  'Manipur',
  'Meghalaya',
  'Mizoram',
  'Nagaland',
  'Sikkim',
  'Tripura',
];

export const Header: React.FC<HeaderProps> = ({
  selectedState,
  onSelectState,
  locations,
  onSelectLocation,
  unreadAlertsCount,
  onOpenAlerts,
  isDemoMode = false,
  onToggleDemoMode,
}) => {
  const [searchQuery, setSearchQuery] = React.useState('');
  const [isSearchOpen, setIsSearchOpen] = React.useState(false);
  const [isStateDropdownOpen, setIsStateDropdownOpen] = React.useState(false);

  const filteredLocations = React.useMemo(() => {
    if (!searchQuery.trim()) return [];
    return locations
      .filter(
        (l) =>
          l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          l.state.toLowerCase().includes(searchQuery.toLowerCase()) ||
          l.district.toLowerCase().includes(searchQuery.toLowerCase())
      )
      .slice(0, 6);
  }, [searchQuery, locations]);

  return (
    <header className="h-16 bg-[#0f172a]/95 backdrop-blur border-b border-slate-800/80 px-4 md:px-6 flex items-center justify-between sticky top-0 z-30">
      {/* Left: Region / State Selector */}
      <div className="flex items-center gap-4">
        <div className="relative">
          <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
            <span className="hidden sm:inline">Region:</span>
            <button
              id="header-state-selector-btn"
              onClick={() => setIsStateDropdownOpen(!isStateDropdownOpen)}
              className="flex items-center gap-2 px-3 py-1.5 bg-slate-800/90 hover:bg-slate-700/90 text-slate-100 rounded-md border border-slate-700 text-sm font-semibold transition"
            >
              <span className="truncate max-w-[160px]">{selectedState}</span>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
            </button>
          </div>

          {isStateDropdownOpen && (
            <div
              className="absolute left-0 mt-1 w-52 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl py-1 z-50 animate-in fade-in zoom-in-95 duration-100"
              onMouseLeave={() => setIsStateDropdownOpen(false)}
            >
              {statesList.map((state) => (
                <button
                  key={state}
                  onClick={() => {
                    onSelectState(state);
                    setIsStateDropdownOpen(false);
                  }}
                  className={`w-full text-left px-3 py-2 text-xs flex items-center justify-between hover:bg-slate-800 transition ${
                    selectedState === state
                      ? 'text-cyan-400 font-semibold bg-cyan-950/30'
                      : 'text-slate-300'
                  }`}
                >
                  <span>{state}</span>
                  {selectedState === state && (
                    <span className="w-1.5 h-1.5 rounded-full bg-cyan-400"></span>
                  )}
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Global Location Search */}
        <div className="relative hidden md:block w-72 lg:w-96">
          <div className="relative">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              id="global-location-search-input"
              type="text"
              placeholder="Search location (e.g., Tawang, Shillong, Gangtok...)"
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setIsSearchOpen(true);
              }}
              onFocus={() => setIsSearchOpen(true)}
              className="w-full bg-slate-900/90 border border-slate-700/90 rounded-md pl-9 pr-4 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition"
            />
          </div>

          {/* Autocomplete dropdown */}
          {isSearchOpen && searchQuery && (
            <div
              className="absolute left-0 right-0 mt-1 bg-slate-900 border border-slate-700 rounded-lg shadow-2xl overflow-hidden z-50"
              onMouseLeave={() => setIsSearchOpen(false)}
            >
              {filteredLocations.length > 0 ? (
                filteredLocations.map((loc) => (
                  <button
                    key={loc.id}
                    onClick={() => {
                      onSelectLocation(loc);
                      setSearchQuery('');
                      setIsSearchOpen(false);
                    }}
                    className="w-full px-3 py-2 text-left text-xs hover:bg-slate-800 flex items-center justify-between border-b border-slate-800/50 last:border-0"
                  >
                    <div>
                      <div className="font-medium text-slate-200">{loc.name}</div>
                      <div className="text-[10px] text-slate-400">
                        {loc.district}, {loc.state} • Elev: {loc.elevation}m
                      </div>
                    </div>
                    <span
                      className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        loc.calculatedLevel === 'CRITICAL'
                          ? 'bg-red-500/20 text-red-400 border border-red-500/40'
                          : loc.calculatedLevel === 'HIGH'
                          ? 'bg-orange-500/20 text-orange-400 border border-orange-500/40'
                          : loc.calculatedLevel === 'MODERATE'
                          ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/40'
                          : 'bg-green-500/20 text-green-400 border border-green-500/40'
                      }`}
                    >
                      {loc.calculatedScore}/100
                    </span>
                  </button>
                ))
              ) : (
                <div className="p-3 text-xs text-slate-500 text-center">
                  No matching locations found in NER
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Right side: Telemetry status, timestamp, alerts, profile */}
      <div className="flex items-center gap-3 md:gap-4">
        {/* Prominent DEMO MODE Button (SIH Presentation) */}
        {onToggleDemoMode && (
          <button
            id="header-demo-mode-btn"
            onClick={onToggleDemoMode}
            className={`flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg text-xs font-mono font-bold transition shadow-md ${
              isDemoMode
                ? 'bg-amber-500 hover:bg-amber-400 text-slate-950 border border-amber-400 shadow-amber-500/30 ring-2 ring-amber-400/50'
                : 'bg-cyan-950/80 hover:bg-cyan-900/90 text-cyan-300 border border-cyan-500/50 shadow-cyan-900/20 hover:border-cyan-400'
            }`}
            title="Smart India Hackathon Presentation Guided Walkthrough"
          >
            <Sparkles className={`w-3.5 h-3.5 ${isDemoMode ? 'text-slate-950' : 'text-cyan-400 animate-pulse'}`} />
            <span className="font-extrabold tracking-wide">DEMO MODE</span>
            <span className="text-[10px] px-1 py-0.2 rounded bg-black/30 font-normal hidden lg:inline">SIH26001</span>
          </button>
        )}

        {/* Live telemetry status */}
        <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded bg-emerald-950/40 border border-emerald-500/30 text-emerald-400 text-xs font-mono">
          <Radio className="w-3.5 h-3.5 animate-pulse" />
          <span className="font-semibold tracking-wider text-[11px]">LIVE GIS TELEMETRY</span>
        </div>

        {/* Last Updated */}
        <div className="hidden sm:flex items-center gap-2 text-xs text-slate-400 font-mono">
          <Clock className="w-3.5 h-3.5 text-emerald-400" />
          <div className="leading-tight text-right">
            <span className="block text-[10px] text-slate-500 uppercase tracking-wider">Last Updated</span>
            <span className="text-slate-300 text-xs">14 Nov 2024, 10:30 AM</span>
          </div>
        </div>

        {/* Alerts Bell */}
        <button
          id="header-alerts-bell-btn"
          onClick={onOpenAlerts}
          className="relative p-2 rounded-md hover:bg-slate-800 text-slate-300 hover:text-white transition"
          title="View Active Disaster Alerts"
        >
          <Bell className="w-4 h-4" />
          {unreadAlertsCount > 0 && (
            <span className="absolute -top-0.5 -right-0.5 w-4 h-4 bg-red-500 text-white rounded-full text-[10px] font-bold flex items-center justify-center ring-2 ring-slate-900 animate-pulse">
              {unreadAlertsCount}
            </span>
          )}
        </button>

        {/* User profile */}
        <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
          <div className="w-8 h-8 rounded-full bg-cyan-900/60 border border-cyan-500/40 flex items-center justify-center text-cyan-300 font-semibold text-xs shadow-inner">
            <User className="w-4 h-4" />
          </div>
          <div className="hidden xl:block leading-tight text-xs">
            <div className="font-semibold text-slate-200">Disaster Management</div>
            <div className="text-[10px] text-slate-400">NER Authority (SEOC)</div>
          </div>
        </div>
      </div>
    </header>
  );
};
