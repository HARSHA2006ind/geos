import React, { useEffect, useState, useCallback } from 'react';
import { StatCards } from '../components/dashboard/StatCards';
import { RiskMap } from '../components/map/RiskMap';
import { LocationDetailsPanel } from '../components/dashboard/LocationDetailsPanel';
import { RecentAlertsPanel } from '../components/dashboard/RecentAlertsPanel';
import { BottomAnalyticsRow } from '../components/dashboard/BottomAnalyticsRow';
import { PilotEnvironmentPanel } from '../components/pilot/PilotEnvironmentPanel';
import { RiskLocation, AlertItem, HistoricalLandslide, FieldReport } from '../types/disaster';
import { environmentApi, PointEnvironmentResponse } from '../services/environmentApi';

interface CommandCenterProps {
  locations: RiskLocation[];
  selectedLocation: RiskLocation | null;
  onSelectLocation: (loc: RiskLocation | null) => void;
  alerts: AlertItem[];
  historicalLandslides: HistoricalLandslide[];
  fieldReports: FieldReport[];
  onViewAnalysis: (loc: RiskLocation) => void;
  onSimulate: (loc: RiskLocation) => void;
  onGenerateAlert: (loc: RiskLocation) => void;
  onViewAllAlerts: () => void;
  onSelectAlert: (alert: AlertItem) => void;
  onFilterByLevel: (level: string) => void;
}

export const CommandCenter: React.FC<CommandCenterProps> = ({
  locations,
  selectedLocation,
  onSelectLocation,
  alerts,
  historicalLandslides,
  fieldReports,
  onViewAnalysis,
  onSimulate,
  onGenerateAlert,
  onViewAllAlerts,
  onSelectAlert,
  onFilterByLevel,
}) => {
  const [pilotBoundary, setPilotBoundary] = useState<GeoJSON.FeatureCollection | null>(null);
  const [inspectedPoint, setInspectedPoint] = useState<{ lat: number; lon: number }>({
    lat: 25.1645,
    lon: 93.0176,
  });
  const [pointEnv, setPointEnv] = useState<PointEnvironmentResponse | null>(null);
  const [loadingEnv, setLoadingEnv] = useState(false);
  const [envError, setEnvError] = useState<string | null>(null);
  const [focusPilotTrigger, setFocusPilotTrigger] = useState(0);

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
      .catch(() => {
        // Boundary unavailable handled gracefully
      });
    inspectCoordinate(25.1645, 93.0176);
    return () => {
      active = false;
    };
  }, [inspectCoordinate]);

  return (
    <div className="space-y-3">
      {/* 1. Real Verified Dima Hasao Pilot Environmental Inspector */}
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

      {/* 2. Prototype Heuristic KPI Summary Row */}
      <StatCards
        locations={locations}
        alerts={alerts}
        onFilterByLevel={onFilterByLevel}
      />

      {/* 3. Main Geospatial Command Center Middle Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-[500px]">
        <div className="lg:col-span-6 xl:col-span-7 h-[500px]">
          <RiskMap
            locations={locations}
            selectedLocation={selectedLocation}
            onSelectLocation={onSelectLocation}
            historicalLandslides={historicalLandslides}
            fieldReports={fieldReports}
            pilotBoundaryGeoJson={pilotBoundary}
            inspectedPoint={inspectedPoint}
            onInspectCoordinate={inspectCoordinate}
            focusPilotTrigger={focusPilotTrigger}
          />
        </div>

        <div className="lg:col-span-3 xl:col-span-3 h-[500px]">
          <LocationDetailsPanel
            location={selectedLocation || locations[0]}
            onClose={() => onSelectLocation(null)}
            onViewAnalysis={onViewAnalysis}
            onSimulate={onSimulate}
            onGenerateAlert={onGenerateAlert}
          />
        </div>

        <div className="lg:col-span-3 xl:col-span-2 h-[500px]">
          <RecentAlertsPanel
            alerts={alerts}
            locations={locations}
            onSelectAlert={onSelectAlert}
            onViewAllAlerts={onViewAllAlerts}
          />
        </div>
      </div>

      {/* 4. Bottom Analytics Row (Real NASA GPM IMERG Chart + Dynamic Risk Donut) */}
      <BottomAnalyticsRow locations={locations} />
    </div>
  );
};
