import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { Search, MapPin, Eye, Sliders } from 'lucide-react';
import { RiskMap } from '../components/map/RiskMap';
import { PilotEnvironmentPanel } from '../components/pilot/PilotEnvironmentPanel';
import { RiskLocation, HistoricalLandslide, FieldReport } from '../types/disaster';
import { environmentApi, PointEnvironmentResponse } from '../services/environmentApi';

interface RiskMapPageProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  historicalLandslides: HistoricalLandslide[];
  fieldReports: FieldReport[];
  onViewAnalysis: (loc: RiskLocation) => void;
  onSimulate: (loc: RiskLocation) => void;
  initialLevelFilter?: string;
}

export const RiskMapPage: React.FC<RiskMapPageProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  historicalLandslides,
  fieldReports,
  onViewAnalysis,
  onSimulate,
  initialLevelFilter = 'ALL',
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [levelFilter, setLevelFilter] = useState<string>(initialLevelFilter);
  const [minSlope, setMinSlope] = useState<number>(0);
  const [minRainfall, setMinRainfall] = useState<number>(0);

  const [pilotBoundary, setPilotBoundary] = useState<GeoJSON.FeatureCollection | null>(null);
  const [inspectedPoint, setInspectedPoint] = useState<{ lat: number; lon: number }>({
    lat: 25.1645,
    lon: 93.0176,
  });
  const [pointEnv, setPointEnv] = useState<PointEnvironmentResponse | null>(null);
  const [loadingEnv, setLoadingEnv] = useState(false);
  const [envError, setEnvError] = useState<string | null>(null);
  const [focusPilotTrigger, setFocusPilotTrigger] = useState(0);

  useEffect(() => {
    setLevelFilter(initialLevelFilter);
  }, [initialLevelFilter]);

  const inspectCoordinate = useCallback(async (lat: number, lon: number) => {
    setInspectedPoint({ lat, lon });
    setLoadingEnv(true);
    setEnvError(null);
    try {
      const res = await environmentApi.getPointEnvironment(lat, lon);
      setPointEnv(res);
    } catch (err: unknown) {
      setEnvError(err instanceof Error ? err.message : 'Failed to query pilot environment');
    } finally {
      setLoadingEnv(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    environmentApi
      .getPilotBoundary()
      .then((res) => {
        if (active) setPilotBoundary(res.geojson as unknown as GeoJSON.FeatureCollection);
      })
      .catch(() => {});
    inspectCoordinate(25.1645, 93.0176);
    return () => {
      active = false;
    };
  }, [inspectCoordinate]);

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
    <div className="space-y-3">
      {/* Verified Pilot Environmental Inspector */}
      <PilotEnvironmentPanel
        data={pointEnv}
        loading={loadingEnv}
        error={envError}
        onSelectCoordinate={(lat, lon) => {
          inspectCoordinate(lat, lon);
          setFocusPilotTrigger((n) => n + 1);
        }}
        onFocusPilot={() => setFocusPilotTrigger((n) => n + 1)}
      />

      {/* Top Filter Bar */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 shadow-lg">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <MapPin className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-100 font-display">
                Geospatial Risk Map (Dima Hasao Pilot + NER Demo Layer)
              </h2>
              <p className="text-[10px] text-slate-400 font-mono">
                Showing {filteredLocations.length} of {locations.length} demo nodes · Click inside green boundary for real data
              </p>
            </div>
          </div>

          <div className="hidden md:flex items-center gap-2 pl-4 border-l border-slate-800 text-xs font-mono">
            <span className="px-2 py-0.5 rounded bg-red-950/80 text-red-400 border border-red-500/40">
              {criticalCount} Critical
            </span>
            <span className="px-2 py-0.5 rounded bg-orange-950/80 text-orange-400 border border-orange-500/40">
              {highCount} High
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <div className="relative w-44">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search demo sector..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-md pl-8 pr-3 py-1 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />
          </div>

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

      {/* Main Map */}
      <div className="relative h-[540px] rounded-xl overflow-hidden border border-slate-800">
        <RiskMap
          locations={filteredLocations}
          selectedLocation={selectedLocation}
          onSelectLocation={onSelectLocation}
          historicalLandslides={historicalLandslides}
          fieldReports={fieldReports}
          pilotBoundaryGeoJson={pilotBoundary}
          inspectedPoint={inspectedPoint}
          onInspectCoordinate={inspectCoordinate}
          focusPilotTrigger={focusPilotTrigger}
        />

        {selectedLocation && (
          <div className="absolute right-4 bottom-8 z-20 w-80 bg-slate-900/95 backdrop-blur-md border border-slate-700 rounded-xl p-4 shadow-2xl space-y-3">
            <div className="flex items-start justify-between">
              <div>
                <span className="text-[10px] text-amber-300 font-mono uppercase tracking-wider block">
                  Demo Sector Selection
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
                <span className="text-slate-500 block text-[9px]">Demo Slope:</span>
                <span className="text-slate-200 font-semibold">{selectedLocation.slope}°</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[9px]">Demo 24h Rain:</span>
                <span className="text-cyan-400 font-semibold">{selectedLocation.currentRainfall} mm</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[9px]">Demo Saturation:</span>
                <span className="text-amber-400 font-semibold">{selectedLocation.soilSaturation}%</span>
              </div>
              <div>
                <span className="text-slate-500 block text-[9px]">Demo Pop Est:</span>
                <span className="text-purple-300 font-semibold">{selectedLocation.populationExposed.toLocaleString()}</span>
              </div>
            </div>

            <div className="flex gap-2 pt-1">
              <button
                onClick={() => onViewAnalysis(selectedLocation)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded text-xs font-semibold border border-slate-700 transition"
              >
                <Eye className="w-3.5 h-3.5 text-cyan-400" />
                <span>Diagnosis</span>
              </button>
              <button
                onClick={() => onSimulate(selectedLocation)}
                className="flex-1 flex items-center justify-center gap-1.5 py-1.5 bg-blue-600 hover:bg-blue-500 text-white rounded text-xs font-semibold shadow-md shadow-blue-600/20 transition"
              >
                <Sliders className="w-3.5 h-3.5" />
                <span>Stress Test</span>
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
