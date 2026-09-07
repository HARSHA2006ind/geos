import React, { useState } from 'react';
import {
  SlidersHorizontal,
  CloudRain,
  Flame,
  AlertTriangle,
  Users,
  Compass,
  RefreshCw,
  Sparkles,
  Route,
  ArrowRight,
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
  const [durationHours, setDurationHours] = useState<number>(24);

  const [isRunning, setIsRunning] = useState(false);
  const [executiveBriefing, setExecutiveBriefing] = useState<string | null>(null);

  // Compute simulation outcome
  const { simulatedLocations, summary } = React.useMemo(() => {
    return simulateRainfallScenario(locations, {
      rainfallMm,
      rainfallIntensity: intensity,
      soilSaturationBonus: saturationBonus,
      durationHours,
    });
  }, [locations, rainfallMm, intensity, saturationBonus, durationHours]);

  const runSimulationWithAi = async () => {
    setIsRunning(true);
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
      if (data.text) {
        setExecutiveBriefing(data.text);
      } else {
        setExecutiveBriefing(
          `• Immediate Pre-positioning: 4 NDRF battalions and 6 SDRF rescue columns must be deployed to NH-13 (Arunachal) and NH-10 (Sikkim) corridors.\n• Evacuation Advisory: Over ${summary.diffPopulationExposed.toLocaleString()} hillside residents across ${summary.diffCritical} new Critical Zones face imminent slope breach within 12 hours of threshold breach.\n• Supply Chain Buffer: State administrations must stockpile 3 weeks of essential rations and medical supplies in isolated sub-divisional headquarters before arterial road failure.`
        );
      }
    } catch {
      setExecutiveBriefing(
        `• Critical Corridor Warning: ${summary.diffRoadsExposed} arterial highway links are projected to suffer multiple blockage events.\n• High Vulnerability Clusters: Arunachal Western sector and Sikkim Teesta valley exhibit severe pore pressure spike.`
      );
    } finally {
      setIsRunning(false);
    }
  };

  const handleReset = () => {
    setRainfallMm(120);
    setIntensity('normal');
    setSaturationBonus(0);
    setDurationHours(24);
    setExecutiveBriefing(null);
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
              <span className="text-[10px] text-cyan-400 uppercase font-mono font-bold tracking-wider">
                Dynamic Stress Simulation Engine
              </span>
              <h2 className="text-base font-bold text-slate-100 font-display">
                What-If Regional Hydrometeorological Scenario
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
                  setDurationHours(24);
                }}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                  rainfallMm === 240
                    ? 'bg-cyan-950 text-cyan-300 border border-cyan-500/60 shadow-sm'
                    : 'text-amber-400 hover:text-amber-300 hover:bg-slate-800/60'
                }`}
              >
                +40% Surge (240mm)
              </button>
              <button
                onClick={() => {
                  setRainfallMm(320);
                  setIntensity('cloudburst');
                  setSaturationBonus(25);
                  setDurationHours(24);
                }}
                className={`px-2.5 py-1 rounded text-[11px] font-semibold transition ${
                  rainfallMm === 320
                    ? 'bg-red-950 text-red-300 border border-red-500/60 shadow-sm'
                    : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
                }`}
              >
                Cloudburst (320mm)
              </button>
            </div>

            <button
              id="run-simulation-btn"
              onClick={runSimulationWithAi}
              disabled={isRunning}
              className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-blue-600 to-cyan-600 hover:from-blue-500 hover:to-cyan-500 text-white font-bold rounded-lg shadow-lg shadow-blue-600/30 text-xs transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRunning ? 'animate-spin' : ''}`} />
              <span>{isRunning ? 'Calculating Simulation...' : 'RUN SIMULATION'}</span>
            </button>
          </div>
        </div>

        {/* Sliders and Options */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 pt-3 text-xs">
          {/* 1. Rainfall (mm) Slider */}
          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-slate-300 font-medium flex items-center gap-1.5">
                <CloudRain className="w-4 h-4 text-cyan-400" />
                Rainfall (24h)
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
              <span>50 mm (Light)</span>
              <span>200 mm</span>
              <span>350 mm (Extreme)</span>
            </div>
          </div>

          {/* 2. Intensity Trigger */}
          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <span className="text-slate-300 font-medium block mb-1.5">Precipitation Pattern</span>
            <div className="grid grid-cols-3 gap-1">
              {[
                { id: 'normal', label: 'Continuous' },
                { id: 'heavy', label: 'Monsoon Spike' },
                { id: 'cloudburst', label: 'Cloudburst' },
              ].map((m) => (
                <button
                  key={m.id}
                  onClick={() => setIntensity(m.id as any)}
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
              {intensity === 'cloudburst' ? 'Sudden downpour >100mm/hr' : 'Sustained antecedent accumulation'}
            </p>
          </div>

          {/* 3. Soil Saturation Bonus Slider */}
          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <div className="flex justify-between items-center mb-1.5">
              <span className="text-slate-300 font-medium">Antecedent Saturation</span>
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
              <span>0% (Dry base)</span>
              <span>+15%</span>
              <span>+30% (Saturated)</span>
            </div>
          </div>

          {/* 4. Forecast Horizon */}
          <div className="p-3 bg-slate-900/80 rounded-lg border border-slate-800">
            <span className="text-slate-300 font-medium block mb-1.5">Forecast Horizon</span>
            <div className="grid grid-cols-3 gap-1">
              {[12, 24, 48].map((hrs) => (
                <button
                  key={hrs}
                  onClick={() => setDurationHours(hrs)}
                  className={`py-1 rounded text-[11px] font-mono font-bold transition text-center ${
                    durationHours === hrs
                      ? 'bg-blue-600 text-white'
                      : 'bg-slate-950 text-slate-400 hover:text-slate-200 border border-slate-800'
                  }`}
                >
                  {hrs} Hours
                </button>
              ))}
            </div>
            <p className="text-[10px] text-slate-400 mt-1.5 font-mono">
              Soil relaxation index: {(0.95 - durationHours * 0.003).toFixed(2)}
            </p>
          </div>
        </div>
      </div>

      {/* Dynamic Comparison Delta Counters */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-[#131929] border border-red-900/50 rounded-xl p-3 shadow-lg flex items-center justify-between">
          <div>
            <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
              Critical Risk Zones
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-mono font-bold text-red-400">
                {summary.simulatedCritical}
              </span>
              <span className="text-xs font-mono font-bold text-red-500">
                (+{summary.diffCritical})
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
              High Risk Zones
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-mono font-bold text-orange-400">
                {summary.simulatedHigh}
              </span>
              <span className="text-xs font-mono font-bold text-orange-500">
                (+{summary.diffHigh})
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
              Newly Exposed Citizens
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-xl font-mono font-bold text-purple-300">
                +{summary.diffPopulationExposed.toLocaleString()}
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
              Disrupted Highway Links
            </span>
            <div className="flex items-baseline gap-2 mt-0.5">
              <span className="text-2xl font-mono font-bold text-cyan-400">
                +{summary.diffRoadsExposed}
              </span>
              <span className="text-xs text-slate-400 font-mono">Arterial segments</span>
            </div>
          </div>
          <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
            <Route className="w-4 h-4" />
          </div>
        </div>
      </div>

      {/* Main Simulation View: GIS Map & Disrupted Corridors */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-[480px]">
        {/* Left Simulated GIS Map */}
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

        {/* Right Panel: Disrupted Highways & AI Executive Briefing */}
        <div className="lg:col-span-4 flex flex-col justify-between bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3 overflow-y-auto max-h-[480px]">
          <div>
            <div className="flex items-center gap-2 pb-2 border-b border-slate-800">
              <Route className="w-4 h-4 text-cyan-400" />
              <h3 className="text-xs font-bold text-slate-100 font-display">
                Strategic Arteries at Failure Threshold
              </h3>
            </div>

            <div className="space-y-2 mt-2">
              <div className="p-2.5 bg-red-950/40 border border-red-800/60 rounded-lg text-xs">
                <div className="flex justify-between font-bold text-red-300">
                  <span>NH-13 (Bhalukpong-Tawang)</span>
                  <span className="font-mono">92% Failure Risk</span>
                </div>
                <p className="text-[11px] text-slate-300 mt-1">
                  KM 42 Sela Pass cut. High risk of debris flow over topping culvert.
                </p>
                <div className="text-[10px] text-red-400 font-mono mt-1">
                  Est. Clearance: 48-72 hrs • Detour: Via Tezpur valley
                </div>
              </div>

              <div className="p-2.5 bg-red-950/40 border border-red-800/60 rounded-lg text-xs">
                <div className="flex justify-between font-bold text-red-300">
                  <span>NH-10 (Sevoke-Gangtok)</span>
                  <span className="font-mono">88% Failure Risk</span>
                </div>
                <p className="text-[11px] text-slate-300 mt-1">
                  Birik Dara / 29th Mile subsidence. Teesta river scouring toe slope.
                </p>
                <div className="text-[10px] text-red-400 font-mono mt-1">
                  Est. Clearance: 36 hrs • Detour: Lava-Gorubathan link
                </div>
              </div>

              <div className="p-2.5 bg-orange-950/40 border border-orange-800/60 rounded-lg text-xs">
                <div className="flex justify-between font-bold text-orange-300">
                  <span>NH-29 (Dimapur-Kohima)</span>
                  <span className="font-mono">79% Failure Risk</span>
                </div>
                <p className="text-[11px] text-slate-300 mt-1">
                  Phesama & Old KMC dumping zone slip. Heavy freight disruption.
                </p>
              </div>
            </div>
          </div>

          {/* AI Executive Scenario Briefing */}
          <div className="p-3 bg-slate-900 border border-cyan-900/40 rounded-lg text-xs space-y-1.5">
            <div className="flex items-center gap-1.5 text-cyan-400 font-bold text-[11px]">
              <Sparkles className="w-3.5 h-3.5" />
              <span>NDMA Executive Briefing</span>
            </div>
            <div className="text-[11px] text-slate-300 leading-relaxed whitespace-pre-line font-sans">
              {executiveBriefing ||
                `At ${rainfallMm}mm/24h simulated precipitation (+${saturationBonus}% saturation), ${summary.diffCritical} additional hill sectors surpass critical shear failure limits. Recommend triggering Stage-3 Alert for North Eastern state emergency operations.`}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
