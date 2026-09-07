import React, { useState } from 'react';
import {
  ShieldAlert,
  Users,
  Building2,
  PhoneCall,
  CheckCircle2,
  Clock,
  Truck,
  AlertTriangle,
  Hospital,
  School,
  Radio,
  ExternalLink,
  Zap,
  Antenna,
  Navigation,
  Compass,
  Filter,
} from 'lucide-react';
import { RiskLocation } from '../types/disaster';

interface ImpactResponsePageProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation) => void;
  onOpenCreateAlert: (loc: RiskLocation) => void;
}

interface ActionProtocol {
  id: string;
  category: 'IMMEDIATE' | 'HIGH' | 'MONITORING';
  title: string;
  description: string;
  agency: string;
  assignedTo: string;
  status: 'PENDING' | 'DISPATCHED' | 'CONFIRMED';
  timeframe: string;
}

export const ImpactResponsePage: React.FC<ImpactResponsePageProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  onOpenCreateAlert,
}) => {
  const activeLoc = selectedLocation || locations[0];
  const [categoryFilter, setCategoryFilter] = useState<'ALL' | 'IMMEDIATE' | 'HIGH' | 'MONITORING'>('ALL');

  const [actions, setActions] = useState<ActionProtocol[]>([
    // IMMEDIATE — 0-2 HOURS
    {
      id: 'act-imm-1',
      category: 'IMMEDIATE',
      title: 'Dispatch Emergency Field Inspection Team',
      description:
        'Deploy Quick Reaction Ground Inspection squad equipped with inclinometers to verify crown tension cracks and toe seepage.',
      agency: 'Geological Survey / District Disaster Management Authority (DDMA)',
      assignedTo: 'Eng. R. Bordoloi',
      status: 'DISPATCHED',
      timeframe: '0–2 Hours',
    },
    {
      id: 'act-imm-2',
      category: 'IMMEDIATE',
      title: 'Verify Ground Conditions & Slump Displacement',
      description:
        'Physically survey active subsidence zone along kilometer marker 38-42. Measure creep velocity and surface tension fissure apertures.',
      agency: 'State PWD (Roads) / BRO Project Vartak',
      assignedTo: 'Asst. Exec. Engineer K. Sarmah',
      status: 'DISPATCHED',
      timeframe: '0–2 Hours',
    },
    {
      id: 'act-imm-3',
      category: 'IMMEDIATE',
      title: 'Issue Local Flash Warning & Community Sirens',
      description:
        'Broadcast CAP-compliant SMS geo-fenced alert and trigger village public address sirens for immediate toe-slope evacuation.',
      agency: 'State Emergency Operations Center (SEOC)',
      assignedTo: 'Duty Officer A. Lyngdoh',
      status: 'CONFIRMED',
      timeframe: '0–2 Hours',
    },
    {
      id: 'act-imm-4',
      category: 'IMMEDIATE',
      title: 'Monitor Critical Highway & Restrict Heavy Freight',
      description:
        'Establish barricades at entry junctions. Divert non-essential heavy transport and single-lane transit for emergency convoys only.',
      agency: 'District Traffic Police / Highway Patrol',
      assignedTo: 'DSP M. Sonowal',
      status: 'CONFIRMED',
      timeframe: '0–2 Hours',
    },
    {
      id: 'act-imm-5',
      category: 'IMMEDIATE',
      title: 'Prepare Evacuation Teams & SDRF Staging',
      description:
        'Stage 2 platoons of State Disaster Response Force (SDRF) with inflatable boats, stretchers, and chainsaw units at Sector Base.',
      agency: 'State Disaster Response Force (SDRF)',
      assignedTo: 'Cmdt. P. Hazarika',
      status: 'DISPATCHED',
      timeframe: '0–2 Hours',
    },

    // HIGH PRIORITY — 2-6 HOURS
    {
      id: 'act-high-1',
      category: 'HIGH',
      title: 'Pre-position Emergency Debris Clearance Resources',
      description:
        'Position 2 wheeled excavators, 1 rock breaker, and dumpers at strategic laybys near vulnerable pass chokepoints.',
      agency: 'Border Roads Organisation (BRO) / NHIDCL',
      assignedTo: 'Capt. R. K. Nair',
      status: 'PENDING',
      timeframe: '2–6 Hours',
    },
    {
      id: 'act-high-2',
      category: 'HIGH',
      title: 'Coordinate Road Clearance & Debris Disposal Zones',
      description:
        'Survey designated debris dump zones away from river drainage basins to prevent subsequent mudflow damming and flash floods.',
      agency: 'District Administration / Environment Dept',
      assignedTo: 'Divisional Forest Officer',
      status: 'PENDING',
      timeframe: '2–6 Hours',
    },
    {
      id: 'act-high-3',
      category: 'HIGH',
      title: 'Notify District Administration & Block Officers',
      description:
        'Brief Deputy Commissioner and Sub-Divisional Magistrates on escalating rainfall thresholds and activate Incident Response System (IRS).',
      agency: 'DDMA Secretariat',
      assignedTo: 'District Disaster Management Officer',
      status: 'CONFIRMED',
      timeframe: '2–6 Hours',
    },
    {
      id: 'act-high-4',
      category: 'HIGH',
      title: 'Verify Vulnerable Settlements & Relief Camps',
      description:
        'Conduct house-to-house headcounts in hamlets directly down-gradient. Prepare relief shelters with clean water, blankets, and rations.',
      agency: 'Revenue & Disaster Management / Red Cross',
      assignedTo: 'Circle Officer / Tehsildar',
      status: 'PENDING',
      timeframe: '2–6 Hours',
    },

    // MONITORING — 6-24 HOURS
    {
      id: 'act-mon-1',
      category: 'MONITORING',
      title: 'Continue Rainfall & Pore-Water Telemetry Monitoring',
      description:
        'Ingest continuous hourly AWS telemetry and automated piezometer loggers. Track if cumulative 48h precipitation exceeds 220mm.',
      agency: 'IMD Regional Meteorological Centre & NESAC',
      assignedTo: 'Meteorologist Dr. T. Roy',
      status: 'PENDING',
      timeframe: '6–24 Hours',
    },
    {
      id: 'act-mon-2',
      category: 'MONITORING',
      title: 'Track Citizen & Field Officer Ground Reports',
      description:
        'Review incoming crowd-sourced photo observations and automated NLP anomaly detections to spot localized slope movements.',
      agency: 'GeoResilience GIS Operations Cell',
      assignedTo: 'GIS Analyst S. Debbarma',
      status: 'PENDING',
      timeframe: '6–24 Hours',
    },
    {
      id: 'act-mon-3',
      category: 'MONITORING',
      title: 'Reassess Dynamic Risk Score & Thresholds',
      description:
        'Recalculate dynamic multi-factor risk scores every 3 hours as rainfall forecast radar models update over the Eastern Himalayas.',
      agency: 'State Decision Support Engine',
      assignedTo: 'Technical Lead AI Operations',
      status: 'CONFIRMED',
      timeframe: '6–24 Hours',
    },
    {
      id: 'act-mon-4',
      category: 'MONITORING',
      title: 'Review Satellite Optical & SAR Observations',
      description:
        'Analyze ISRO Cartosat and Sentinel-1 Interferometric Synthetic Aperture Radar (InSAR) coherence pairs for millimeter-scale surface subsidence.',
      agency: 'North Eastern Space Applications Centre (NESAC)',
      assignedTo: 'Remote Sensing Scientist Dr. B. Saikia',
      status: 'PENDING',
      timeframe: '6–24 Hours',
    },
  ]);

  const toggleActionStatus = (id: string) => {
    setActions((prev) =>
      prev.map((act) => {
        if (act.id !== id) return act;
        const nextStatus =
          act.status === 'PENDING'
            ? 'DISPATCHED'
            : act.status === 'DISPATCHED'
            ? 'CONFIRMED'
            : 'PENDING';
        return { ...act, status: nextStatus };
      })
    );
  };

  const filteredActions =
    categoryFilter === 'ALL'
      ? actions
      : actions.filter((act) => act.category === categoryFilter);

  // Derive Impact Severity level
  const impactSeverity: 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL' =
    activeLoc.calculatedScore >= 75
      ? 'CRITICAL'
      : activeLoc.calculatedScore >= 55
      ? 'HIGH'
      : activeLoc.calculatedScore >= 35
      ? 'MODERATE'
      : 'LOW';

  const severityBadgeClass =
    impactSeverity === 'CRITICAL'
      ? 'bg-red-950 text-red-400 border-red-500/50'
      : impactSeverity === 'HIGH'
      ? 'bg-orange-950 text-orange-400 border-orange-500/50'
      : impactSeverity === 'MODERATE'
      ? 'bg-yellow-950 text-yellow-400 border-yellow-500/50'
      : 'bg-emerald-950 text-emerald-400 border-emerald-500/50';

  return (
    <div className="space-y-4">
      {/* Top Header & Sector Selector */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-rose-950/80 border border-rose-500/40 flex items-center justify-center text-rose-400">
            <ShieldAlert className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-rose-400 uppercase font-mono font-bold tracking-wider">
              Emergency Decision Support & Directives
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              Impact Assessment & Standard Operating Procedures
            </h2>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={activeLoc.id}
            onChange={(e) => {
              const found = locations.find((l) => l.id === e.target.value);
              if (found) onSelectLocation(found);
            }}
            className="bg-slate-900 border border-slate-700 rounded-lg px-3 py-1.5 text-xs text-slate-100 font-semibold focus:ring-1 focus:ring-cyan-500 outline-none"
          >
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name} ({loc.district}, {loc.state})
              </option>
            ))}
          </select>

          <button
            id="impact-page-generate-alert-btn"
            onClick={() => onOpenCreateAlert(activeLoc)}
            className="px-3.5 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-bold shadow-md shadow-red-600/30 transition flex items-center gap-1.5"
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Broadcast Evacuation Siren</span>
          </button>
        </div>
      </div>

      {/* Grid: Assets Exposed on Left, SOP Action Matrix on Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column: Impact Analysis Structured Hierarchy */}
        <div className="lg:col-span-5 space-y-4">
          {/* Impact Severity Banner */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl flex items-center justify-between">
            <div>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider font-mono font-bold block">
                OVERALL IMPACT SEVERITY
              </span>
              <span className="text-sm font-bold text-slate-100 font-display">
                {activeLoc.name}
              </span>
            </div>
            <div className={`px-3 py-1 rounded-lg text-xs font-bold uppercase font-mono border ${severityBadgeClass}`}>
              {impactSeverity} SEVERITY
            </div>
          </div>

          {/* 1. PEOPLE */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Users className="w-4 h-4 text-purple-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase font-display tracking-wider">
                  PEOPLE — Population Exposed
                </h3>
              </div>
              <span className="text-xs font-mono font-bold text-purple-300">
                {activeLoc.populationExposed.toLocaleString()} Exposed
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800">
                <span className="text-slate-400 text-[10px] block">High Vulnerability Toe-Slope</span>
                <span className="text-lg font-mono font-bold text-red-400">
                  {Math.round(activeLoc.populationExposed * 0.24).toLocaleString()}
                </span>
                <span className="text-[10px] text-slate-500 block">Direct runout path</span>
              </div>

              <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800">
                <span className="text-slate-400 text-[10px] block">Households & Habitations</span>
                <span className="text-lg font-mono font-bold text-slate-200">
                  {Math.round(activeLoc.populationExposed / 4.8).toLocaleString()}
                </span>
                <span className="text-[10px] text-slate-500 block">Residential units</span>
              </div>
            </div>

            <div className="p-2.5 bg-purple-950/30 border border-purple-800/40 rounded-lg text-[11px] text-purple-200 leading-relaxed">
              • ~{Math.round(activeLoc.populationExposed * 0.08).toLocaleString()} elderly and infant residents requiring assisted evacuation.
              <br />• 3 village hamlets situated within 250m of active scar slope.
            </div>
          </div>

          {/* 2. LIFELINES */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Building2 className="w-4 h-4 text-cyan-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase font-display tracking-wider">
                  LIFELINES — Strategic Assets
                </h3>
              </div>
              <span className="text-xs font-mono font-bold text-cyan-400">
                {activeLoc.infrastructure.roads + activeLoc.infrastructure.bridges + activeLoc.infrastructure.powerAssets} Lifeline Units
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Truck className="w-3.5 h-3.5 text-cyan-400" />
                  <span className="text-slate-300 text-[11px]">Roads</span>
                </div>
                <span className="font-mono text-cyan-400 font-bold">{activeLoc.infrastructure.roads} segments</span>
              </div>

              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Navigation className="w-3.5 h-3.5 text-orange-400" />
                  <span className="text-slate-300 text-[11px]">Bridges</span>
                </div>
                <span className="font-mono text-orange-400 font-bold">{activeLoc.infrastructure.bridges} crossings</span>
              </div>

              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Zap className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-slate-300 text-[11px]">Power</span>
                </div>
                <span className="font-mono text-amber-400 font-bold">{activeLoc.infrastructure.powerAssets} substations</span>
              </div>

              <div className="p-2 bg-slate-900 rounded-lg border border-slate-800 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Antenna className="w-3.5 h-3.5 text-purple-400" />
                  <span className="text-slate-300 text-[11px]">Telecom</span>
                </div>
                <span className="font-mono text-purple-400 font-bold">4 BTS Towers</span>
              </div>
            </div>

            <div className="text-[11px] text-slate-400 font-mono">
              Key Highway Corridors: <span className="text-slate-200">{activeLoc.infrastructure.keyHighways.join(', ')}</span>
            </div>
          </div>

          {/* 3. ESSENTIAL SERVICES */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Hospital className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase font-display tracking-wider">
                  ESSENTIAL SERVICES
                </h3>
              </div>
              <span className="text-xs font-mono font-bold text-emerald-400">
                {activeLoc.infrastructure.hospitals} Hospitals • {activeLoc.infrastructure.schools} Schools
              </span>
            </div>

            <div className="space-y-1.5 text-xs">
              <div className="flex items-center justify-between p-2 bg-slate-900 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2">
                  <Hospital className="w-3.5 h-3.5 text-emerald-400" />
                  <span className="text-slate-300">Hospitals & Trauma Centers</span>
                </div>
                <span className="font-mono text-emerald-400 font-bold">{activeLoc.infrastructure.hospitals} Facility</span>
              </div>

              <div className="flex items-center justify-between p-2 bg-slate-900 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2">
                  <School className="w-3.5 h-3.5 text-amber-400" />
                  <span className="text-slate-300">Schools & Educational Facilities</span>
                </div>
                <span className="font-mono text-amber-400 font-bold">{activeLoc.infrastructure.schools} Centers</span>
              </div>

              <div className="flex items-center justify-between p-2 bg-slate-900 rounded-lg border border-slate-800">
                <div className="flex items-center gap-2">
                  <ShieldAlert className="w-3.5 h-3.5 text-rose-400" />
                  <span className="text-slate-300">Emergency Facilities / Staging</span>
                </div>
                <span className="font-mono text-rose-400 font-bold">2 Designated Shelters</span>
              </div>
            </div>
          </div>

          {/* 4. ACCESSIBILITY */}
          <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-slate-800">
              <div className="flex items-center gap-2">
                <Compass className="w-4 h-4 text-amber-400" />
                <h3 className="text-xs font-bold text-slate-100 uppercase font-display tracking-wider">
                  ACCESSIBILITY & ROUTE DISRUPTION
                </h3>
              </div>
              <span className="text-xs font-mono font-bold text-amber-400">
                {activeLoc.calculatedScore >= 70 ? 'HIGH DISRUPTION' : 'MODERATE'}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <div className="flex justify-between">
                  <span className="text-slate-300 font-medium">Road Disruption Probability:</span>
                  <span className="font-mono font-bold text-red-400">
                    {Math.min(96, Math.round(activeLoc.calculatedScore * 0.95))}%
                  </span>
                </div>
                <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-500 rounded-full"
                    style={{ width: `${Math.min(96, Math.round(activeLoc.calculatedScore * 0.95))}%` }}
                  />
                </div>
              </div>

              <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <span className="text-slate-400 text-[10px] uppercase font-mono block">Potential Isolated Settlements:</span>
                <span className="text-slate-200 font-semibold text-[11px] block">
                  3 Down-gradient Hamlets (Est. pop ~2,100 cut off if NH blocked)
                </span>
              </div>

              <div className="p-2.5 bg-slate-900 rounded-lg border border-slate-800 space-y-1">
                <span className="text-slate-400 text-[10px] uppercase font-mono block">Alternative Route Availability:</span>
                <span className="text-cyan-300 font-semibold text-[11px] block">
                  State Highway Bypass Route 4B (Adds 34 km via southern ridge pass)
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column: Prioritized Action Directives Matrix */}
        <div className="lg:col-span-7 bg-[#0f172a] border border-slate-800 rounded-xl p-4 shadow-xl space-y-4">
          <div className="flex flex-wrap items-center justify-between pb-3 border-b border-slate-800 gap-2">
            <div>
              <h3 className="text-sm font-bold text-slate-100 font-display">
                Emergency Response Directives Matrix
              </h3>
              <p className="text-[11px] text-slate-400">
                Grouped by Operational Timeframe (NDMA / SDMA Protocols)
              </p>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-slate-400 font-mono">
                {actions.filter((a) => a.status === 'CONFIRMED').length} / {actions.length} Completed
              </span>
            </div>
          </div>

          {/* Filter Pills */}
          <div className="flex flex-wrap items-center gap-1.5 text-xs">
            <span className="text-[11px] text-slate-400 font-medium mr-1 flex items-center gap-1">
              <Filter className="w-3 h-3" /> Filter:
            </span>
            {(['ALL', 'IMMEDIATE', 'HIGH', 'MONITORING'] as const).map((cat) => (
              <button
                key={cat}
                onClick={() => setCategoryFilter(cat)}
                className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                  categoryFilter === cat
                    ? cat === 'IMMEDIATE'
                      ? 'bg-red-950 text-red-300 border border-red-500/50'
                      : cat === 'HIGH'
                      ? 'bg-orange-950 text-orange-300 border border-orange-500/50'
                      : cat === 'MONITORING'
                      ? 'bg-yellow-950 text-yellow-300 border border-yellow-500/50'
                      : 'bg-cyan-950 text-cyan-300 border border-cyan-500/50'
                    : 'bg-slate-900 text-slate-400 hover:text-slate-200 border border-slate-800'
                }`}
              >
                {cat === 'IMMEDIATE'
                  ? 'IMMEDIATE (0–2h)'
                  : cat === 'HIGH'
                  ? 'HIGH PRIORITY (2–6h)'
                  : cat === 'MONITORING'
                  ? 'MONITORING (6–24h)'
                  : 'All Directives'}
              </button>
            ))}
          </div>

          {/* Directive List */}
          <div className="space-y-3">
            {filteredActions.map((act) => {
              const isImmediate = act.category === 'IMMEDIATE';
              const isHigh = act.category === 'HIGH';

              return (
                <div
                  key={act.id}
                  className={`p-3.5 rounded-xl border transition-all flex flex-col md:flex-row md:items-start justify-between gap-3 ${
                    act.status === 'CONFIRMED'
                      ? 'bg-slate-900/40 border-slate-800 opacity-85'
                      : isImmediate
                      ? 'bg-[#181119] border-red-900/50 shadow-md'
                      : isHigh
                      ? 'bg-[#1a1714] border-orange-900/40 shadow'
                      : 'bg-[#121824] border-slate-800'
                  }`}
                >
                  <div className="space-y-1.5 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${
                          isImmediate
                            ? 'bg-red-950 text-red-400 border border-red-500/40'
                            : isHigh
                            ? 'bg-orange-950 text-orange-400 border border-orange-500/40'
                            : 'bg-yellow-950 text-yellow-400 border border-yellow-500/40'
                        }`}
                      >
                        {act.category === 'IMMEDIATE'
                          ? 'IMMEDIATE — 0–2 HOURS'
                          : act.category === 'HIGH'
                          ? 'HIGH PRIORITY — 2–6 HOURS'
                          : 'MONITORING — 6–24 HOURS'}
                      </span>
                      <span className="text-[11px] text-slate-400 font-medium">
                        {act.agency}
                      </span>
                    </div>

                    <h4 className="text-xs font-bold text-slate-100">{act.title}</h4>
                    <p className="text-[11px] text-slate-300 leading-relaxed">
                      {act.description}
                    </p>
                    <div className="text-[10px] text-slate-500 font-mono">
                      Assigned Lead: <span className="text-slate-400">{act.assignedTo}</span>
                    </div>
                  </div>

                  {/* Status Toggle Button: PENDING / DISPATCHED / CONFIRMED */}
                  <div className="shrink-0 flex flex-col items-end gap-1">
                    <button
                      id={`action-status-btn-${act.id}`}
                      onClick={() => toggleActionStatus(act.id)}
                      title="Click to advance status: PENDING → DISPATCHED → CONFIRMED"
                      className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition shadow-sm ${
                        act.status === 'CONFIRMED'
                          ? 'bg-emerald-950/90 text-emerald-300 border border-emerald-500/60 hover:bg-emerald-900'
                          : act.status === 'DISPATCHED'
                          ? 'bg-blue-950/90 text-blue-300 border border-blue-500/60 hover:bg-blue-900'
                          : 'bg-slate-800 text-slate-300 border border-slate-700 hover:bg-slate-700'
                      }`}
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>{act.status}</span>
                    </button>
                    <span className="text-[9px] text-slate-500 font-mono">Click to toggle status</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
