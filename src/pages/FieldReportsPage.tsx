import React, { useState } from 'react';
import {
  FileText,
  Plus,
  Search,
  CheckCircle2,
  Clock,
  MapPin,
  Camera,
  AlertTriangle,
  User,
  ShieldCheck,
  ExternalLink,
} from 'lucide-react';
import { FieldReport, RiskLocation } from '../types/disaster';

interface FieldReportsPageProps {
  reports: FieldReport[];
  locations: RiskLocation[];
  onOpenSubmitModal: () => void;
  onSelectLocationOnMap: (loc: RiskLocation) => void;
}

export const FieldReportsPage: React.FC<FieldReportsPageProps> = ({
  reports,
  locations,
  onOpenSubmitModal,
  onSelectLocationOnMap,
}) => {
  const [filterSeverity, setFilterSeverity] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState('');

  const filteredReports = reports.filter((r) => {
    const matchesSeverity = filterSeverity === 'ALL' || r.severity === filterSeverity;
    const matchesSearch =
      r.locationName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      r.submittedBy.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSeverity && matchesSearch;
  });

  return (
    <div className="space-y-4">
      {/* Top Header */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-4 flex flex-wrap items-center justify-between gap-4 shadow-xl">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-teal-950/80 border border-teal-500/40 flex items-center justify-center text-teal-400">
            <FileText className="w-5 h-5" />
          </div>
          <div>
            <span className="text-[10px] text-teal-400 uppercase font-mono font-bold tracking-wider">
              Crowdsourced & Officer Ground Intel
            </span>
            <h2 className="text-lg font-bold text-slate-100 font-display">
              Field Hazard Incident Reports
            </h2>
          </div>
        </div>

        <button
          id="submit-new-field-report-top-btn"
          onClick={onOpenSubmitModal}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white font-bold rounded-lg shadow-lg shadow-teal-600/20 text-xs transition"
        >
          <Plus className="w-4 h-4" />
          <span>Submit Ground Incident Report</span>
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-3 flex flex-wrap items-center justify-between gap-3 text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-400 font-medium">Severity:</span>
          {['ALL', 'Critical', 'High', 'Moderate'].map((sev) => (
            <button
              key={sev}
              onClick={() => setFilterSeverity(sev)}
              className={`px-2.5 py-1 rounded-md transition font-medium ${
                filterSeverity === sev
                  ? 'bg-teal-600 text-white font-bold'
                  : 'text-slate-400 hover:text-white bg-slate-900 border border-slate-700'
              }`}
            >
              {sev}
            </button>
          ))}
        </div>

        <div className="relative w-64">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search report, observer, highway..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-900 border border-slate-700 rounded-md pl-8 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-teal-500"
          />
        </div>
      </div>

      {/* Reports Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredReports.map((report) => {
          const isCritical = report.severity === 'Critical';
          const isHigh = report.severity === 'High';

          const matchingLoc = locations.find((l) => l.id === report.locationId);

          return (
            <div
              key={report.id}
              className="bg-[#0f172a] border border-slate-800 hover:border-slate-700 rounded-xl p-4 shadow-xl flex flex-col justify-between space-y-3 transition group"
            >
              <div className="space-y-2.5">
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <span className="text-[10px] text-cyan-400 font-mono uppercase tracking-wider block">
                      {report.type.replace('_', ' ')}
                    </span>
                    <h4 className="text-sm font-bold text-slate-100 font-display">
                      {report.locationName}
                    </h4>
                  </div>
                  <span
                    className={`px-2 py-0.5 rounded text-[10px] font-bold uppercase font-mono ${
                      isCritical
                        ? 'bg-red-950 text-red-400 border border-red-500/40'
                        : isHigh
                        ? 'bg-orange-950 text-orange-400 border border-orange-500/40'
                        : 'bg-yellow-950 text-yellow-400 border border-yellow-500/40'
                    }`}
                  >
                    {report.severity}
                  </span>
                </div>

                {/* Photo thumbnail */}
                {report.imageUrl && (
                  <div className="w-full h-32 rounded-lg overflow-hidden border border-slate-700 relative bg-slate-900">
                    <img
                      src={report.imageUrl}
                      alt={report.locationName}
                      className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                      referrerPolicy="no-referrer"
                    />
                    <div className="absolute bottom-1.5 left-1.5 bg-slate-950/80 px-2 py-0.5 rounded text-[9px] font-mono text-cyan-300 flex items-center gap-1">
                      <Camera className="w-3 h-3" />
                      <span>GPS Geo-Photo</span>
                    </div>
                  </div>
                )}

                <p className="text-xs text-slate-300 leading-relaxed">
                  {report.description}
                </p>

                {/* Submitter details */}
                <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-[11px] text-slate-400">
                  <div className="flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-slate-500" />
                    <span>{report.submittedBy}</span>
                    <span className="text-[10px] text-slate-500 font-mono">({report.role})</span>
                  </div>
                  {report.verified && (
                    <div className="flex items-center gap-1 text-emerald-400 text-[10px] font-semibold">
                      <ShieldCheck className="w-3.5 h-3.5" />
                      <span>Verified</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Bottom Actions */}
              <div className="pt-2 border-t border-slate-800 flex items-center justify-between">
                <span className="text-[10px] text-slate-500 font-mono flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {report.timestamp}
                </span>

                {matchingLoc && (
                  <button
                    onClick={() => onSelectLocationOnMap(matchingLoc)}
                    className="flex items-center gap-1 px-2.5 py-1 rounded bg-slate-800 hover:bg-slate-700 text-cyan-300 text-xs font-semibold transition"
                  >
                    <MapPin className="w-3 h-3" />
                    <span>Inspect On Map</span>
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
