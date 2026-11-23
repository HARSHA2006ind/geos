import React, { useState, useMemo } from 'react';
import {
  SlidersHorizontal,
  CloudRain,
  Flame,
  AlertTriangle,
  Users,
  RefreshCw,
  Sparkles,
  Route,
} from 'lucide-react';
import { RiskLocation, HistoricalLandslide, FieldReport } from '../types/disaster';
import { simulateRainfallScenario } from '../services/riskEngine';
import { RiskMap } from '../components/map/RiskMap';

interface WhatIfSimulationPageProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  historicalLandslides: HistoricalLandslide[];
  fieldReports: FieldReport[];
}

export const WhatIfSimulationPage: React.FC<WhatIfSimulationPageProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  historicalLandslides,
  fieldReports,
}) => {
  const [rainfallMm, setRainfallMm] = useState<number>(220);
  const [intensity, setIntensity] = useState<'normal' | 'heavy' | 'cloudburst'>('heavy');
  const [saturationBonus, setSaturationBonus] = useState<number>(15);

  const [isRunning, setIsRunning] = useState(false);
  const [executiveBriefing, setExecutiveBriefing] = useState<string | null>(null);
  const [briefingError, setBriefingError] = useState<string | null>(null);

  const { simulatedLocations, summary } = useMemo(() => {
    return simulateRainfallScenario(locations, {
      rainfallMm,
      rainfallIntensity: intensity,
      soilSaturationBonus: saturationBonus,
    });
  }, [locations, rainfallMm, intensity, saturationBonus]);

  // Dynamically derive top elevated corridors from the actual simulatedLocations
  const topStressedSectors = useMemo(() => {
    return [...simulatedLocations]
      .sort((a, b) => b.calculatedScore - a.calculatedScore)
      .slice(0, 3);
  }, [simulatedLocations]);

  const runSimulationWithAi = async () => {
    setIsRunning(true);
    setBriefingError(null);
    try {
      const res = await fetch('/api/gemini/what-if-briefing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          summary,
          params: { rainfallMm, rainfallIntensity: intensity, soilSaturationBonus: saturationBonus },
        }),
      });
      const data = await res.json();
      if (res.ok && data.text) {
        setExecutiveBriefing(data.text);
      } else {
        setExecutiveBriefing(null);
        setBriefingError(data.message || 'Gemini narrative assistant is unavailable.');
      }
    } catch {
      setExecutiveBriefing(null);
      setBriefingError('Unable to reach the server narrative briefing endpoint.');
    } finally {
      setIsRunning(false);
    }
  };

  const handleReset = () => {
    setRainfallMm(120);
    setIntensity('normal');
    setSaturationBonus(0);
    setExecutiveBriefing(null);
    setBriefingError(null);
  };

  return (
    <div className="space-y-3">
      {/* Simulation Control Cockpit */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <SlidersHorizontal className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] text-amber-300 uppercase font-mono font-bold tracking-wider">
                Heuristic Prototype Stress-Test (Not a Calibrated Hydrological Forecast)
              </span>
              <h2 className="text-base font-bold text-slate-100 font-display">
                What-If Rainfall Sensitivity Sandbox
              </h2>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <div className="flex items-center gap-1 bg-slate-900/90 p-1 rounded-lg border border-slate-800">
              <span className="text-[10px] text-slate-500 font-mono px-1.5 uppercase">Presets:</span>
              <button
                onClick={handleReset}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                  rainfallMm === 120
                    ? 'bg-slate-800 text-cyan-400 border border-cyan-500/40'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                Baseline (120mm)
              </button>
              <button
                id="preset-40-percent-surge-btn"
                onClick={() => {
                  setRainfallMm(240);
                  setIntensity('heavy');
                  setSaturationBonus(15);
                }}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                  rainfallMm === 240
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/60 shadow-sm'
                    : 'text-amber-400 hover:text-amber-300 hover:bg-slate-800/60'
                }`}
              >
                Surge (240mm)
              </button>
              <button
                onClick={() => {
                  setRainfallMm(320);
                  setIntensity('cloudburst');
                  setSaturationBonus(25);
                }}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                  rainfallMm === 320
                    ? 'bg-red-950 text-red-300 border border-red-500/60 shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                Extreme (320mm)
              </button>
            </div>

            <button
              id="run-simulation-btn"
              onClick={runSimulationWithAi}
              disabled={isRunning}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold rounded-lg shadow-lg shadow-blue-600/30 text-xs transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
              <span>{isRunning ? 'Generating Briefing...' : 'Generate Narrative Summary'}</span>
            </button>
          </div>
        </div>

        {/* Sliders and Options (only controls wired directly into simulateRainfallScenario) */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-3 text-xs">
          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-slate-300 font-medium flex items-center gap-1.5">
                <CloudRain className="w-4 h-4 text-cyan-400" />
                Scenario Rainfall (24h)
              </span>
              <span className="font-mono text-cyan-400 font-bold text-sm">{rainfallMm} mm</span>
            </div>
            <input
              type="range"
              min={50}
              max={350}
              step={10}
              value={rainfallMm}
              onChange={(e) => setRainfallMm(Number(e.target.value))}
              className="w-full accent-cyan-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
              <span>50 mm</span>
              <span>200 mm</span>
              <span>350 mm</span>
            </div>
          </div>

          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <span className="text-slate-300 font-medium block mb-1.5">Heuristic Intensity Multiplier</span>
            <div className="grid grid-cols-3 gap-1">
              {[
                { id: 'normal', label: '1.0x Normal' },
                { id: 'heavy', label: '1.15x Heavy' },
                { id: 'cloudburst', label: '1.35x Extreme' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setIntensity(m.id as 'normal' | 'heavy' | 'cloudburst')}
                  className={`py-1 px-1.5 rounded text-[10px] font-bold transition text-center ${
                    intensity === m.id
                      ? 'bg-cyan-600 text-white shadow'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 mt-1.5">
              Applies deterministic scaling factor to the prototype rainfall index.
            </p>
          </div>

          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-slate-300 font-medium">Antecedent Saturation Offset</span>
              <span className="font-mono text-amber-400 font-bold text-sm">+{saturationBonus}%</span>
            </div>
            <input
              type="range"
              min={0}
              max={30}
              step={5}
              value={saturationBonus}
              onChange={(e) => setSaturationBonus(Number(e.target.value))}
              className="w-full accent-amber-400 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
              <span>+0%</span>
              <span>+15%</span>
              <span>+30%</span>
            </div>
          </div>
        </div>
      </div>

      {/* Dynamic Comparison Delta Counters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#131929] border border-red-900/50 rounded-xl p-3 shadow-lg flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
              Simulated Critical Zones
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-mono font-bold text-red-400">
                {summary.simulatedCritical}
              </span>
              <span className="text-xs font-mono font-bold text-red-500">
                ({summary.diffCritical >= 0 ? `+${summary.diffCritical}` : summary.diffCritical})
              </span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-lg bg-red-950/80 border border-red-500/40 flex items-center justify-center text-red-400">
            <Flame className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-[#131929] border border-orange-900/50 rounded-xl p-3 shadow-lg flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
              Simulated High Zones
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-mono font-bold text-orange-400">
                {summary.simulatedHigh}
              </span>
              <span className="text-xs font-mono font-bold text-orange-500">
                ({summary.diffHigh >= 0 ? `+${summary.diffHigh}` : summary.diffHigh})
              </span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-lg bg-orange-950/80 border border-orange-500/40 flex items-center justify-center text-orange-400">
            <AlertTriangle className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-[#131929] border border-purple-900/50 rounded-xl p-3 shadow-lg flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
              Delta Exposed Pop. (Demo)
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-xl font-mono font-bold text-purple-300">
                {summary.diffPopulationExposed >= 0 ? '+' : ''}
                {summary.diffPopulationExposed.toLocaleString()}
              </span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-lg bg-purple-950/80 border border-purple-500/40 flex items-center justify-center text-purple-400">
            <Users className="w-4 h-4" />
          </div>
        </div>

        <div className="bg-[#131929] border border-cyan-900/50 rounded-xl p-3 shadow-lg flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
              Delta Road Units (Demo)
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-mono font-bold text-cyan-400">
                {summary.diffRoadsExposed >= 0 ? '+' : ''}
                {summary.diffRoadsExposed}
              </span>
              <span className="text-xs text-slate-400 font-mono">segments</span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
            <Route className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Main Simulation View */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-[480px]">
        <div className="lg:col-span-8 h-[480px]">
          <RiskMap
            locations={simulatedLocations}
            selectedLocation={selectedLocation}
            onSelectLocation={onSelectLocation}
            historicalLandslides={historicalLandslides}
            fieldReports={fieldReports}
            isSimulated={true}
          />
        </div>

        <div className="lg:col-span-4 flex flex-col justify-between bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3 overflow-y-auto max-h-[480px]">
          <div>
            <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
              <Route className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Highest-Scoring Simulated Sectors
              </h3>
            </div>

            <div className="space-y-2 mt-2">
              {topStressedSectors.map((loc) => (
                <div
                  key={loc.id}
                  onClick={() => onSelectLocation(loc)}
                  className={`p-2.5 rounded-lg text-xs cursor-pointer border transition ${
                    loc.calculatedLevel === 'CRITICAL'
                      ? 'bg-red-950/40 border-red-800/60 hover:border-red-500/70'
                      : 'bg-orange-950/40 border-orange-800/60 hover:border-orange-500/70'
                  }`}
                >
                  <div className="flex justify-between font-bold text-slate-100">
                    <span>{loc.name}</span>
                    <span className="font-mono text-red-300">
                      {loc.calculatedScore}/100 ({loc.calculatedLevel})
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-300 mt-1">
                    {loc.district}, {loc.state} · Corridors:{' '}
                    {loc.infrastructure.keyHighways.join(', ') || 'District roads'}
                  </p>
                  <div className="text-[10px] text-slate-400 font-mono mt-1">
                    Scenario Rain: {loc.currentRainfall} mm · Slope: {loc.slope}° · Sat: {loc.soilSaturation}%
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Narrative Briefing Box */}
          <div className="p-3 bg-slate-900 border border-cyan-900/40 rounded-lg text-xs space-y-1.5">
            <div className="flex items-center gap-1.5 text-cyan-400 font-bold text-[11px]">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Scenario Narrative Summary (Optional LLM)</span>
            </div>
            {briefingError ? (
              <div className="text-[11px] text-amber-300 leading-relaxed">{briefingError}</div>
            ) : (
              <div className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-line font-sans">
                {executiveBriefing ||
                  `Heuristic sandbox result: At ${rainfallMm} mm/24h (+${saturationBonus}% saturation offset), ${summary.simulatedCritical} demo sectors classify as CRITICAL (delta ${summary.diffCritical >= 0 ? '+' : ''}${summary.diffCritical}). Click "Generate Narrative Summary" to query the server Gemini assistant.`}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
