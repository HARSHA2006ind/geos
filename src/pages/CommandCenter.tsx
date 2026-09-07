import React from 'react';
import { StatCards } from '../components/dashboard/StatCards';
import { RiskMap } from '../components/map/RiskMap';
import { LocationDetailsPanel } from '../components/dashboard/LocationDetailsPanel';
import { RecentAlertsPanel } from '../components/dashboard/RecentAlertsPanel';
import { BottomAnalyticsRow } from '../components/dashboard/BottomAnalyticsRow';
import { RiskLocation, AlertItem, HistoricalLandslide, FieldReport } from '../types/disaster';

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
  return (
    <div className="space-y-3">
      {/* 1. Top KPI Summary Cards Row */}
      <StatCards
        locations={locations}
        alerts={alerts}
        onFilterByLevel={onFilterByLevel}
      />

      {/* 2. Main Geospatial Command Center Middle Row */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-3 min-h-[500px]">
        {/* Left / Center GIS Interactive Map */}
        <div className="lg:col-span-6 xl:col-span-7 h-[500px]">
          <RiskMap
            locations={locations}
            selectedLocation={selectedLocation}
            onSelectLocation={onSelectLocation}
            historicalLandslides={historicalLandslides}
            fieldReports={fieldReports}
          />
        </div>

        {/* Selected Location Details Panel */}
        <div className="lg:col-span-3 xl:col-span-3 h-[500px]">
          <LocationDetailsPanel
            location={selectedLocation || locations[0]}
            onClose={() => onSelectLocation(null)}
            onViewAnalysis={onViewAnalysis}
            onSimulate={onSimulate}
            onGenerateAlert={onGenerateAlert}
          />
        </div>

        {/* Right Recent Disaster Alerts Panel */}
        <div className="lg:col-span-3 xl:col-span-2 h-[500px]">
          <RecentAlertsPanel
            alerts={alerts}
            locations={locations}
            onSelectAlert={onSelectAlert}
            onViewAllAlerts={onViewAllAlerts}
          />
        </div>
      </div>

      {/* 3. Bottom Comprehensive Analytics Charts */}
      <BottomAnalyticsRow locations={locations} />
    </div>
  );
};
