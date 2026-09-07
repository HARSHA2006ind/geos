import React, { useState } from 'react';
import { X, Send, MapPin, Camera, AlertCircle } from 'lucide-react';
import { FieldReport, RiskLocation } from '../../types/disaster';

interface SubmitReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  locations: RiskLocation[];
  onSubmitReport: (report: FieldReport) => void;
}

export const SubmitReportModal: React.FC<SubmitReportModalProps> = ({
  isOpen,
  onClose,
  locations,
  onSubmitReport,
}) => {
  const [locationId, setLocationId] = useState(locations[0]?.id || '');
  const [reportType, setReportType] = useState<FieldReport['type']>('active_slide');
  const [severity, setSeverity] = useState<FieldReport['severity']>('High');
  const [submittedBy, setSubmittedBy] = useState('Officer T. Jamir');
  const [role, setRole] = useState<FieldReport['role']>('Field Officer');
  const [description, setDescription] = useState(
    'Significant slope displacement observed along cut-section. Slump scarp widening and water seepage active.'
  );
  const [blockedRoads, setBlockedRoads] = useState('NH-13 Kilometer Marker 42+200');

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const loc = locations.find((l) => l.id === locationId) || locations[0];

    const newReport: FieldReport = {
      id: `rep-${Date.now()}`,
      locationId: loc.id,
      locationName: loc.name,
      state: loc.state,
      lat: loc.lat + (Math.random() - 0.5) * 0.04,
      lng: loc.lng + (Math.random() - 0.5) * 0.04,
      type: reportType,
      severity: severity,
      description: `${description} [Impacted Road: ${blockedRoads}]`,
      submittedBy: submittedBy,
      role: role,
      timestamp: 'Just now',
      verificationStatus: 'Verified',
      verified: true,
      imageUrl:
        'https://images.unsplash.com/photo-1544620347-c4fd4a3d5957?auto=format&fit=crop&w=400&q=80',
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
                Submit Ground Hazard Incident Report
              </h3>
              <p className="text-[11px] text-slate-400">Direct Field Crowdsourcing & Officer Ingestion</p>
            </div>
          </div>
          <button
            id="close-submit-report-modal-btn"
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
                onChange={(e) => setReportType(e.target.value as any)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              >
                <option value="active_slide">Active Landslide / Slip</option>
                <option value="road_block">Road Blockage / Debris</option>
                <option value="mudflow">Mudflow / Torrential Wash</option>
                <option value="cracks">Slope Tension Cracks / Seepage</option>
                <option value="retaining_wall_failure">Retaining Wall Failure</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Severity</label>
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value as any)}
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
                required
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              />
            </div>

            <div>
              <label className="block text-[11px] font-semibold text-slate-300 mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as any)}
                className="w-full bg-slate-900 border border-slate-700 rounded-md px-2 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
              >
                <option value="Field Officer">Field Officer</option>
                <option value="Citizen">Local Citizen</option>
                <option value="BRO Engineer">BRO Engineer</option>
                <option value="Disaster Volunteer">Disaster Volunteer</option>
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
              placeholder="e.g. NH-13 KM 42+200 near Sela Pass"
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-1.5 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">
              Visual / Engineering Observations
            </label>
            <textarea
              rows={3}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            />
          </div>

          <div className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 flex items-center justify-between text-[11px] text-slate-400">
            <div className="flex items-center gap-2">
              <Camera className="w-4 h-4 text-cyan-400" />
              <span>Ground Photo Attached (Sela_Pass_slip_01.jpg)</span>
            </div>
            <span className="text-emerald-400 font-mono font-semibold">GPS Geo-tagged</span>
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
              <span>Submit & Ingest to Engine</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
