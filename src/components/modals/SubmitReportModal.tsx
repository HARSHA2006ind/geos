import React, { useState, useEffect } from 'react';
import { X, Send, MapPin, AlertCircle } from 'lucide-react';
import { FieldReport, ReportSeverity, ReportType, RiskLocation } from '../../types/disaster';

interface SubmitReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  locations: RiskLocation[];
  onSubmitReport: (report: FieldReport) => void;
}

export const VALID_REPORT_TYPES: ReportType[] = [
  'Landslide',
  'Road Blockage',
  'Ground Crack',
  'Rockfall',
  'Flooding',
  'Infrastructure Damage',
];

export const VALID_REPORTER_ROLES: FieldReport['role'][] = [
  'Field Officer',
  'Citizen',
  'NDRF Scout',
  'PWD Inspector',
];

export const SubmitReportModal: React.FC<SubmitReportModalProps> = ({
  isOpen,
  onClose,
  locations,
  onSubmitReport,
}) => {
  const [locationId, setLocationId] = useState(locations[0]?.id || '');
  const [reportType, setReportType] = useState<ReportType>('Landslide');
  const [severity, setSeverity] = useState<ReportSeverity>('High');
  const [submittedBy, setSubmittedBy] = useState('Officer T. Jamir');
  const [role, setRole] = useState<FieldReport['role']>('Field Officer');
  const [description, setDescription] = useState(
    'Slope displacement observed along road cut-section; tension fissures and seepage noted.'
  );
  const [blockedRoads, setBlockedRoads] = useState('NH-27 / Haflong-Jatinga corridor');

  useEffect(() => {
    if (isOpen && locations.length > 0 && !locations.some((l) => l.id === locationId)) {
      setLocationId(locations[0].id);
    }
  }, [isOpen, locations, locationId]);

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const loc = locations.find((l) => l.id === locationId) || locations[0];
    if (!loc) return;

    const cleanRoad = blockedRoads.trim();
    const newReport: FieldReport = {
      id: `rep-${Date.now()}`,
      locationId: loc.id,
      locationName: loc.name,
      state: loc.state,
      lat: loc.lat,
      lng: loc.lng,
      type: reportType,
      severity,
      description: cleanRoad ? `${description.trim()} [Landmark: ${cleanRoad}]` : description.trim(),
      submittedBy: submittedBy.trim() || 'Anonymous Reporter',
      role,
      timestamp: new Date().toISOString(),
      verificationStatus: 'Pending',
      verified: false,
    };

    onSubmitReport(newReport);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[#0f172a] border border-slate-700 rounded-xl w-full max-w-lg shadow-2xl overflow-hidden text-slate-200">
        <div className="p-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-cyan-950/80 border border-cyan-500/40 flex items-center justify-center text-cyan-400">
              <MapPin className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-100 font-display">
                Submit Ground Observation (Session Prototype)
              </h3>
              <p className="text-[11px] text-slate-400">
                Stored in local browser session only — marked Pending until verified
              </p>
            </div>
          </div>
          <button
            id="close-submit-report-modal-btn"
            type="button"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-3.5 text-xs">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Affected Sector
              </label>
              <select
                value={locationId}
                onChange={(e) => setLocationId(e.target.value)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              >
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} ({loc.district}, {loc.state})
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                Incident Phenomenon
              </label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value as ReportType)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              >
                {VALID_REPORT_TYPES.map((typeOption) => (
                  <option key={typeOption} value={typeOption}>
                    {typeOption}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Severity</label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as ReportSeverity)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              >
                <option value="Critical">Critical</option>
                <option value="High">High</option>
                <option value="Moderate">Moderate</option>
                <option value="Low">Low</option>
              </select>
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Reporter Name</label>
              <input
                type="text"
                value={submittedBy}
                onChange={(e) => setSubmittedBy(e.target.value)}
                maxLength={80}
                required
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as FieldReport['role'])}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              >
                {VALID_REPORTER_ROLES.map((roleOption) => (
                  <option key={roleOption} value={roleOption}>
                    {roleOption}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">
              Impacted Road / Highway Landmark
            </label>
            <input
              type="text"
              value={blockedRoads}
              onChange={(e) => setBlockedRoads(e.target.value)}
              maxLength={120}
              placeholder="e.g. NH-27 KM 38 near Jatinga"
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">
              Visual / Field Observations
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={500}
              required
              className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            />
          </div>

          <div className="p-2.5 bg-amber-950/30 rounded-lg border border-amber-700/40 flex items-start gap-2 text-[11px] text-amber-200/90">
            <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
            <span>
              Photo upload and live GPS capture are not enabled yet. Coordinates use the selected sector center, and submissions persist in this browser session only.
            </span>
          </div>

          <div className="pt-2 flex justify-end gap-2 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition"
            >
              Cancel
            </button>
            <button
              type="submit"
              id="submit-field-report-action-btn"
              className="flex items-center gap-2 px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white font-bold rounded-lg shadow-lg shadow-cyan-600/30 transition text-xs"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Record Session Observation</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
