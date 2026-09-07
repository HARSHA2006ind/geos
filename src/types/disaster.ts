export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'CRITICAL';

export type NERState =
  | 'All NER'
  | 'Arunachal Pradesh'
  | 'Assam'
  | 'Manipur'
  | 'Meghalaya'
  | 'Mizoram'
  | 'Nagaland'
  | 'Sikkim'
  | 'Tripura';

export type ReportType =
  | 'Landslide'
  | 'Road Blockage'
  | 'Ground Crack'
  | 'Rockfall'
  | 'Flooding'
  | 'Infrastructure Damage';

export type ReportSeverity = 'Low' | 'Moderate' | 'High' | 'Critical';

export type VerificationStatus = 'Pending' | 'Verified' | 'Investigating' | 'Resolved';

export type AlertStatus = 'ACTIVE' | 'ACKNOWLEDGED' | 'RESOLVED';

export interface LocationInfrastructure {
  roads: number;
  bridges: number;
  hospitals: number;
  schools: number;
  powerAssets: number;
  keyHighways: string[];
}

export interface RiskLocation {
  id: string;
  name: string;
  state: NERState;
  district: string;
  lat: number;
  lng: number;
  elevation: number; // in meters
  slope: number; // in degrees (0 - 90)
  soilType: string;
  landCover: string;
  currentRainfall: number; // in mm/24h
  soilSaturation: number; // 0 - 100
  historicalActivity: number; // 0 - 100
  vegetationStress: number; // 0 - 100
  populationExposed: number;
  infrastructure: LocationInfrastructure;
  primaryRiskDrivers: string[];
  confidence: number; // percentage
  imageUrl?: string;
  // Computed fields
  calculatedScore: number; // 0 - 100
  calculatedLevel: RiskLevel;
}

export interface HistoricalLandslide {
  id: string;
  locationName: string;
  state: NERState;
  lat: number;
  lng: number;
  date: string;
  year: number;
  fatalities: number;
  rainfallRecorded: number; // mm in 24h
  trigger: string;
  damageDescription: string;
}

export interface FieldReport {
  id: string;
  locationId?: string;
  locationName: string;
  state: NERState;
  lat: number;
  lng: number;
  type: ReportType;
  severity: ReportSeverity;
  submittedBy: string;
  role: 'Citizen' | 'Field Officer' | 'NDRF Scout' | 'PWD Inspector';
  timestamp: string;
  verificationStatus: VerificationStatus;
  description: string;
  photoUrl?: string;
  imageUrl?: string;
  verified?: boolean;
}

export interface AlertItem {
  id: string;
  locationId: string;
  locationName: string;
  state: NERState;
  lat: number;
  lng: number;
  riskScore: number;
  riskLevel: RiskLevel;
  timestamp: string;
  status: AlertStatus;
  trigger: string;
  potentialImpact: string;
  recommended: string;
  recommendedActions?: string[];
  dispatchedTeams?: string[];
}

export interface MapLayerSettings {
  riskZones: boolean;
  historicalLandslides: boolean;
  rainfall: boolean;
  roads: boolean;
  settlements: boolean;
  hospitals: boolean;
  schools: boolean;
  infrastructure: boolean;
  fieldReports: boolean;
}

export interface SimulationParams {
  rainfallMm: number; // 50 to 300 mm
  soilSaturationBonus: number; // -20 to +40
  rainfallIntensity: 'Normal' | 'High' | 'Extreme';
  vegetationStressModifier: number; // -20 to +20
}

export interface SimulationResultSummary {
  currentCritical: number;
  simulatedCritical: number;
  diffCritical: number;
  currentHigh: number;
  simulatedHigh: number;
  diffHigh: number;
  currentModerate: number;
  simulatedModerate: number;
  currentLow: number;
  simulatedLow: number;
  currentPopulationExposed: number;
  simulatedPopulationExposed: number;
  diffPopulationExposed: number;
  currentRoadsExposed: number;
  simulatedRoadsExposed: number;
  diffRoadsExposed: number;
}

export interface ResponseAction {
  id: string;
  title: string;
  description: string;
  priority: 'IMMEDIATE' | 'HIGH' | 'MONITOR';
  assignedAgency: string;
  status: 'Pending' | 'In Progress' | 'Completed';
}
