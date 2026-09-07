import React, { useState, useMemo } from 'react';
import { Filter, Layers, Search, MapPin, Eye, Compass, ShieldAlert, Sliders } from 'lucide-react';
import { RiskMap } from '../components/map/RiskMap';
import { RiskLocation, HistoricalLandslide, FieldReport, RiskLevel } from '../types/disaster';

interface RiskMapPageProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  historicalLandslides: HistoricalLandslide[];
  fieldReports: FieldReport[];
  onViewAnalysis: (loc: RiskLocation) => void;
  onSimulate: (loc: RiskLocation) => void;
}

export const RiskMapPage: React.FC<RiskMapPageProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  historicalLandslides,
  fieldReports,
  onViewAnalysis,
  onSimulate,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState<string>('ALL');
  const [minSlope, setMinSlope] = useState<number>(0);
  const [minRainfall, setMinRainfall] = useState<number>(0);

  const filteredLocations = useMemo(() => {
    return locations.filter((loc) => {
      const matchesSearch =
        loc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        loc.district.toLowerCase().includes(searchQuery.toLowerCase()) ||
        loc.state.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesLevel = levelFilter === 'ALL' || loc.calculatedLevel === levelFilter;
      const matchesSlope = loc.slope >= minSlope;
      const matchesRainfall = loc.currentRainfall >= minRainfall;
      return matchesSearch && matchesLevel && matchesSlope && matchesRainfall;
    });
  }, [locations, searchQuery, levelFilter, minSlope, minRainfall]);

  const criticalCount = locations.filter((l) => l.calculatedLevel === 'CRITICAL').length;
  const highCount = locations.filter((l) => l.calculatedLevel === 'HIGH').length;

  return (
    <div className="h-[calc(100vh-6rem)] flex flex-col space-y-2">
      {/* Top Telemetry & Filter Bar */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100 font-display">
                Geospatial Hazard Risk Map (NER)
              </h2>
              <p className="text-[10px] text-slate-400 font-mono">
                Showing {filteredLocations.length} of {locations.length} hazard telemetry nodes
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-800 text-xs font-mono">
            <span className="px-2 py-0.5 rounded bg-red-950/80 text-red-400 border border-red-500/40">
              {criticalCount} Critical
            </span>
            <span className="px-2 py-0.5 rounded bg-orange-950/80 text-orange-400 border border-orange-500/40">
              {highCount} High Risk
            </span>
          </div>
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          {/* Search */}
          <div className="relative w-48">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search place..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-md pl-8 pr-3 py-1 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

          {/* Level Filter */}
          <div className="flex items-center rounded-md bg-slate-900 border border-slate-700 p-0.5 text-[11px]">
            {['ALL', 'CRITICAL', 'HIGH', 'MODERATE', 'LOW'].map((lvl) => (
              <button
                key={lvl}
                onClick={() => setLevelFilter(lvl)}
                className={`px-2 py-1 rounded font-medium transition ${
                  levelFilter === lvl
                    ? 'bg-blue-600 text-white font-bold'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {lvl}
              </button>
            ))}
          </div>

          {/* Slope filter pill */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-900 border border-slate-700 rounded-md text-[11px] text-slate-300">
            <span>Slope &gt;</span>
            <select
              value={minSlope}
              onChange={(e) => setMinSlope(Number(e.target.value))}
              className="bg-transparent text-cyan-400 font-mono font-bold outline-none"
            >
              <option value={0}>0°</option>
              <option value={25}>25°</option>
              <option value={35}>35°</option>
              <option value={45}>45°</option>
            </select>
          </div>

          {/* Rainfall filter pill */}
          <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-900 border border-slate-700 rounded-md text-[11px] text-slate-300">
            <span>Rain &gt;</span>
            <select
              value={minRainfall}
              onChange={(e) => setMinRainfall(Number(e.target.value))}
              className="bg-transparent text-cyan-400 font-mono font-bold outline-none"
            >
              <option value={0}>0 mm</option>
              <option value={80}>80 mm</option>
              <option value={120}>120 mm</option>
              <option value={150}>150 mm</option>
            </select>
          </div>
        </div>
      </div>

      {/* Main Map with Floating Detail Drawer on selection */}
      <div className="relative flex-1 rounded-xl overflow-hidden border border-slate-800">
        <RiskMap
          locations={filteredLocations}
          selectedLocation={selectedLocation}
          onSelectLocation={onSelectLocation}
          historicalLandslides={historicalLandslides}
          fieldReports={fieldReports}
        />

        {/* Floating Quick Drawer if location selected */}
        {selectedLocation && (
          <div className="absolute right-4 bottom-4 z-20 w-80 bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-xl p-4 shadow-2xl space-y-3 animate-in slide-in-from-right-4 duration-200">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] text-cyan-400 font-mono uppercase tracking-wider block">
                  Focused Location
                </span>
                <h4 className="text-sm font-bold text-white font-display">
                  {selectedLocation.name}
                </h4>
                <p className="text-[11px] text-slate-400">
                  {selectedLocation.district}, {selectedLocation.state}
                </p>
              </div>
              <span
                className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  selectedLocation.calculatedLevel === 'CRITICAL'
                    ? 'bg-red-950 text-red-400 border border-red-500/50'
                    : 'bg-orange-950 text-orange-400 border border-orange-500/50'
                }`}
              >
                {selectedLocation.calculatedScore}/100
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono p-2 bg-slate-950/60 rounded border border-slate-800">
              <div>
                <span className="text-slate-500 block text-[9px]">Slope:</span>
                <span className="text-slate-200 font-semibold">{selectedLocation.slope}°</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[9px]">24h Rain:</span>
                <span className="text-cyan-400 font-semibold">{selectedLocation.currentRainfall} mm</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[9px]">Soil Saturation:</span>
                <span className="text-amber-400 font-semibold">{selectedLocation.soilSaturation}%</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[9px]">Pop Exposed:</span>
                <span className="text-purple-300 font-semibold">{selectedLocation.populationExposed.toLocaleString()}</span>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => onViewAnalysis(selectedLocation)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded text-xs font-semibold border border-slate-700 transition"
              >
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>Deep Analysis</span>
              </button>
              <button
                onClick={() => onSimulate(selectedLocation)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold shadow-md shadow-blue-600/20 transition"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Simulate</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
