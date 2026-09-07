import React, { useState } from 'react';
import { X, Send, Radio, ShieldAlert } from 'lucide-react';
import { AlertItem, RiskLocation, RiskLevel } from '../../types/disaster';

interface CreateAlertModalProps {
  isOpen: boolean;
  onClose: () => void;
  locations: RiskLocation[];
  preselectedLocation?: RiskLocation | null;
  onBroadcastAlert: (alert: AlertItem) => void;
}

export const CreateAlertModal: React.FC<CreateAlertModalProps> = ({
  isOpen,
  onClose,
  locations,
  preselectedLocation,
  onBroadcastAlert,
}) => {
  const [selectedLocationId, setSelectedLocationId] = useState(
    preselectedLocation?.id || locations[0]?.id || ''
  );
  const [riskLevel, setRiskLevel] = useState<RiskLevel>(
    preselectedLocation?.calculatedLevel || 'CRITICAL'
  );
  const [trigger, setTrigger] = useState(
    preselectedLocation
      ? `Sustained 24h rainfall of ${preselectedLocation.currentRainfall} mm over saturated slope (${preselectedLocation.slope}°).`
      : 'Intense precipitation exceeding critical slope threshold.'
  );
  const [potentialImpact, setPotentialImpact] = useState(
    preselectedLocation
      ? `Risk to ${preselectedLocation.populationExposed.toLocaleString()} residents, NH arterial corridors, and essential civil infrastructure.`
      : 'High probability of debris flow blocking arterial transport route.'
  );
  const [broadcastChannels, setBroadcastChannels] = useState({
    sms: true,
    radio: true,
    siren: false,
    ndmaPortal: true,
  });

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const loc = locations.find((l) => l.id === selectedLocationId) || locations[0];

    const newAlert: AlertItem = {
      id: `alert-${Date.now()}`,
      locationId: loc.id,
      locationName: `${loc.name}, ${loc.state}`,
      state: loc.state,
      lat: loc.lat,
      lng: loc.lng,
      riskLevel: riskLevel,
      riskScore: loc.calculatedScore || 88,
      timestamp: 'Just now',
      trigger: trigger,
      potentialImpact: potentialImpact,
      status: 'ACTIVE',
      recommended: trigger,
      recommendedActions: [
        'Halt heavy vehicular transit on adjoining national highways.',
        'Issue immediate red-zone evacuation advisories to hillside residents.',
        'Pre-position State Disaster Response Force (SDRF) heavy excavators.',
      ],
    };

    onBroadcastAlert(newAlert);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-[#0f172a] border border-slate-700 rounded-xl w-full max-w-lg shadow-2xl overflow-hidden text-slate-200">
        <div className="p-4 bg-slate-900 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-red-950/80 border border-red-500/40 flex items-center justify-center text-red-400">
              <ShieldAlert className="w-4 h-4" />
            </div>
            <div>
              <h3 className="font-bold text-sm text-slate-100 font-display">Generate Disaster Early Warning Alert</h3>
              <p className="text-[11px] text-slate-400">Authorized SEOC / NDMA Transmission Protocol</p>
            </div>
          </div>
          <button
            id="close-create-alert-modal-btn"
            onClick={onClose}
            className="p-1 rounded text-slate-400 hover:text-white hover:bg-slate-800"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-4 space-y-3.5 text-xs">
          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">Target Hazard Location</label>
            <select
              value={selectedLocationId}
              onChange={(e) => setSelectedLocationId(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 rounded-md px-3 py-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            >
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name} ({loc.district}, {loc.state}) — Current: {loc.calculatedLevel} ({loc.calculatedScore}/100)
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">Alert Classification Level</label>
            <div className="grid grid-cols-3 gap-2">
              {(['CRITICAL', 'HIGH', 'MODERATE'] as RiskLevel[]).map((level) => (
                <button
                  key={level}
                  type="button"
                  onClick={() => setRiskLevel(level)}
                  className={`py-2 px-3 rounded-lg border font-bold text-xs transition text-center ${
                    riskLevel === level
                      ? level === 'CRITICAL'
                        ? 'bg-red-950/90 text-red-400 border-red-500 ring-1 ring-red-500'
                        : level === 'HIGH'
                        ? 'bg-orange-950/90 text-orange-400 border-orange-500 ring-1 ring-orange-500'
                        : 'bg-yellow-950/90 text-yellow-400 border-yellow-500 ring-1 ring-yellow-500'
                      : 'bg-slate-900 text-slate-400 border-slate-700 hover:border-slate-600'
                  }`}
                >
                  {level}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">Trigger Rationale</label>
            <textarea
              rows={2}
              value={trigger}
              onChange={(e) => setTrigger(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1">Potential Impacts & Exposed Assets</label>
            <textarea
              rows={2}
              value={potentialImpact}
              onChange={(e) => setPotentialImpact(e.target.value)}
              required
              className="w-full bg-slate-900 border border-slate-700 rounded-md p-2 text-slate-200 text-xs focus:ring-1 focus:ring-cyan-500 outline-none"
            />
          </div>

          <div>
            <label className="block text-[11px] font-semibold text-slate-300 mb-1.5">Emergency Broadcast Channels</label>
            <div className="grid grid-cols-2 gap-2 text-slate-300">
              <label className="flex items-center gap-2 p-2 bg-slate-900/80 border border-slate-800 rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={broadcastChannels.sms}
                  onChange={(e) => setBroadcastChannels({ ...broadcastChannels, sms: e.target.checked })}
                  className="rounded text-red-500 bg-slate-950 border-slate-700"
                />
                <span>SMS Cell Broadcast (DoT)</span>
              </label>
              <label className="flex items-center gap-2 p-2 bg-slate-900/80 border border-slate-800 rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={broadcastChannels.radio}
                  onChange={(e) => setBroadcastChannels({ ...broadcastChannels, radio: e.target.checked })}
                  className="rounded text-red-500 bg-slate-950 border-slate-700"
                />
                <span>Police / BRO VHF Radio</span>
              </label>
              <label className="flex items-center gap-2 p-2 bg-slate-900/80 border border-slate-800 rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={broadcastChannels.siren}
                  onChange={(e) => setBroadcastChannels({ ...broadcastChannels, siren: e.target.checked })}
                  className="rounded text-red-500 bg-slate-950 border-slate-700"
                />
                <span>Acoustic Sirens (Municipal)</span>
              </label>
              <label className="flex items-center gap-2 p-2 bg-slate-900/80 border border-slate-800 rounded cursor-pointer">
                <input
                  type="checkbox"
                  checked={broadcastChannels.ndmaPortal}
                  onChange={(e) => setBroadcastChannels({ ...broadcastChannels, ndmaPortal: e.target.checked })}
                  className="rounded text-red-500 bg-slate-950 border-slate-700"
                />
                <span>NDMA National Portal</span>
              </label>
            </div>
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
              id="submit-broadcast-alert-btn"
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-500 text-white font-bold rounded-lg shadow-lg shadow-red-600/30 transition text-xs"
            >
              <Send className="w-3.5 h-3.5" />
              <span>Broadcast Alert Now</span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
