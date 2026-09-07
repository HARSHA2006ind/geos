import {
  RiskLocation,
  RiskLevel,
  SimulationParams,
  SimulationResultSummary,
  ResponseAction,
  FieldReport,
} from '../types/disaster';

/**
 * Calculates a deterministic, scientifically grounded Landslide Risk Score (0 - 100)
 * based on Static Susceptibility, Dynamic Hydrometeorological factors, and Vulnerability/Exposure.
 */
export function calculateLocationRisk(
  loc: Omit<RiskLocation, 'calculatedScore' | 'calculatedLevel'>,
  additionalRainfall: number = 0,
  soilSatBonus: number = 0,
  intensityMultiplier: number = 1.0,
  recentReportsCount: number = 0
): { score: number; level: RiskLevel; drivers: string[] } {
  // 1. Static Susceptibility (Weight: ~35%)
  // Slope: 0-20° (gentle), 20-35° (moderate), 35-55° (steep/critical), >55° (sheer rock)
  const slopeFactor = Math.min(100, (loc.slope / 45) * 100);
  const elevationFactor = Math.min(100, (loc.elevation / 3500) * 100);
  const historyFactor = loc.historicalActivity; // 0-100

  const staticScore =
    slopeFactor * 0.45 +
    historyFactor * 0.35 +
    elevationFactor * 0.20;

  // 2. Dynamic Hydrometeorological Factors (Weight: ~45%)
  const effectiveRainfall = Math.max(0, (loc.currentRainfall + additionalRainfall) * intensityMultiplier);
  // Rainfall threshold: in NER, >100mm/24h is dangerous, >200mm is extreme cloudburst
  const rainfallFactor = Math.min(100, (effectiveRainfall / 220) * 100);
  const effectiveSoilSat = Math.min(100, Math.max(0, loc.soilSaturation + soilSatBonus));

  const dynamicScore =
    rainfallFactor * 0.55 +
    effectiveSoilSat * 0.35 +
    loc.vegetationStress * 0.10;

  // 3. Exposure & Ground Observations (Weight: ~20%)
  const popFactor = Math.min(100, (loc.populationExposed / 15000) * 100);
  const infraFactor = Math.min(
    100,
    loc.infrastructure.roads * 3 +
      loc.infrastructure.bridges * 10 +
      loc.infrastructure.hospitals * 12 +
      loc.infrastructure.schools * 5
  );
  const reportFactor = Math.min(100, recentReportsCount * 25);

  const exposureScore = popFactor * 0.45 + infraFactor * 0.40 + reportFactor * 0.15;

  // Final Weighted Fusion:
  // Base Susceptibility (35%) + Dynamic Trigger (50%) + Exposure / Field Reports (15%)
  const rawScore = staticScore * 0.35 + dynamicScore * 0.50 + exposureScore * 0.15;

  // Clamp 0 - 100
  const finalScore = Math.round(Math.max(0, Math.min(100, rawScore)));

  // Classification:
  // 0–24: LOW, 25–49: MODERATE, 50–74: HIGH, 75–100: CRITICAL
  let level: RiskLevel = 'LOW';
  if (finalScore >= 75) {
    level = 'CRITICAL';
  } else if (finalScore >= 50) {
    level = 'HIGH';
  } else if (finalScore >= 25) {
    level = 'MODERATE';
  } else {
    level = 'LOW';
  }

  // Derive top drivers based on factor magnitudes
  const drivers: string[] = [];
  if (rainfallFactor > 60) drivers.push(`Heavy rainfall (${Math.round(effectiveRainfall)} mm/24h)`);
  if (slopeFactor > 65) drivers.push(`Steep slope gradient (${loc.slope}°)`);
  if (effectiveSoilSat > 65) drivers.push(`Elevated pore-water & soil saturation (${Math.round(effectiveSoilSat)}%)`);
  if (historyFactor > 60) drivers.push(`High historical landslide frequency in sector`);
  if (loc.vegetationStress > 60) drivers.push(`Degraded slope vegetation cover`);
  if (recentReportsCount > 0) drivers.push(`${recentReportsCount} recent field incident observation(s)`);

  if (drivers.length === 0) {
    drivers.push('Stable geological conditions', 'Moderate ambient precipitation', 'Low immediate slope stress');
  }

  return {
    score: finalScore,
    level,
    drivers: drivers.slice(0, 4),
  };
}

/**
 * Recalculate simulation state across all locations given user simulation parameters
 */
export function runSimulation(
  locations: RiskLocation[],
  params: SimulationParams,
  fieldReports: FieldReport[]
): {
  simulatedLocations: RiskLocation[];
  summary: SimulationResultSummary;
} {
  const intensityMult =
    params.rainfallIntensity === 'Extreme' ? 1.35 : params.rainfallIntensity === 'High' ? 1.15 : 1.0;

  // Compute baseline counts
  let currentCritical = 0;
  let currentHigh = 0;
  let currentModerate = 0;
  let currentLow = 0;
  let currentPop = 0;
  let currentRoads = 0;

  locations.forEach((l) => {
    if (l.calculatedLevel === 'CRITICAL') {
      currentCritical++;
      currentPop += l.populationExposed;
      currentRoads += l.infrastructure.roads;
    } else if (l.calculatedLevel === 'HIGH') {
      currentHigh++;
      currentPop += Math.round(l.populationExposed * 0.7);
      currentRoads += Math.round(l.infrastructure.roads * 0.7);
    } else if (l.calculatedLevel === 'MODERATE') {
      currentModerate++;
    } else {
      currentLow++;
    }
  });

  let simulatedCritical = 0;
  let simulatedHigh = 0;
  let simulatedModerate = 0;
  let simulatedLow = 0;
  let simulatedPop = 0;
  let simulatedRoads = 0;

  const simulatedLocations: RiskLocation[] = locations.map((loc) => {
    // Count active field reports near this location (within ~0.3 degrees or matching id)
    const activeReports = fieldReports.filter(
      (r) =>
        r.locationName.toLowerCase().includes(loc.name.toLowerCase()) ||
        (Math.abs(r.lat - loc.lat) < 0.25 && Math.abs(r.lng - loc.lng) < 0.25)
    ).length;

    // Difference from base 120mm baseline
    const rainfallDiff = params.rainfallMm - 120;

    const { score, level, drivers } = calculateLocationRisk(
      loc,
      rainfallDiff,
      params.soilSaturationBonus,
      intensityMult,
      activeReports
    );

    if (level === 'CRITICAL') {
      simulatedCritical++;
      simulatedPop += loc.populationExposed;
      simulatedRoads += loc.infrastructure.roads;
    } else if (level === 'HIGH') {
      simulatedHigh++;
      simulatedPop += Math.round(loc.populationExposed * 0.7);
      simulatedRoads += Math.round(loc.infrastructure.roads * 0.7);
    } else if (level === 'MODERATE') {
      simulatedModerate++;
    } else {
      simulatedLow++;
    }

    return {
      ...loc,
      calculatedScore: score,
      calculatedLevel: level,
      primaryRiskDrivers: drivers,
      currentRainfall: Math.max(0, Math.round(loc.currentRainfall + rainfallDiff)),
      soilSaturation: Math.min(100, Math.max(0, loc.soilSaturation + params.soilSaturationBonus)),
    };
  });

  const summary: SimulationResultSummary = {
    currentCritical,
    simulatedCritical,
    diffCritical: simulatedCritical - currentCritical,
    currentHigh,
    simulatedHigh,
    diffHigh: simulatedHigh - currentHigh,
    currentModerate,
    simulatedModerate,
    currentLow,
    simulatedLow,
    currentPopulationExposed: currentPop,
    simulatedPopulationExposed: simulatedPop,
    diffPopulationExposed: simulatedPop - currentPop,
    currentRoadsExposed: currentRoads,
    simulatedRoadsExposed: simulatedRoads,
    diffRoadsExposed: simulatedRoads - currentRoads,
  };

  return { simulatedLocations, summary };
}

/**
 * Generates local deterministic Explainable AI (XAI) analysis matching the mock data
 */
export function generateExplainableExplanation(loc: RiskLocation): {
  overview: string;
  geotechnicalFactors: string[];
  hydrologicalAssessment: string;
  exposureSummary: string;
} {
  const level = loc.calculatedLevel;
  const score = loc.calculatedScore;

  let overview = '';
  if (level === 'CRITICAL') {
    overview = `The location ${loc.name} (${loc.state}) is currently classified as CRITICAL risk (${score}/100). The convergence of intense cumulative precipitation (${loc.currentRainfall} mm/24h), extreme terrain gradient (${loc.slope}° slope), and saturated sub-surface pore-water pressure creates acute shear failure susceptibility along vulnerable colluvial strata.`;
  } else if (level === 'HIGH') {
    overview = `The location ${loc.name} (${loc.state}) is classified as HIGH risk (${score}/100) primarily due to persistent monsoonal rainfall, steep Himalayan terrain, elevated soil moisture index (${loc.soilSaturation}%), and historical reactivation patterns.`;
  } else if (level === 'MODERATE') {
    overview = `The location ${loc.name} (${loc.state}) exhibits MODERATE risk (${score}/100). Baseline geological susceptibility is buffered by existing forest cover, but elevated rainfall may prompt localized slope wash or rockfall.`;
  } else {
    overview = `The location ${loc.name} (${loc.state}) maintains a LOW risk level (${score}/100). Drainage gradients remain stable under current precipitation levels with no anomalous pore-water buildup observed.`;
  }

  const geotechnicalFactors: string[] = [
    `Terrain Gradient: ${loc.slope}° slope angle exceeds critical friction angle of ${loc.soilType}.`,
    `Lithology: Prevalent ${loc.soilType} with elevated weathering index and shallow bedrock interface.`,
    `Vegetation Anchor: Canopy integrity factor is ${100 - loc.vegetationStress}%, showing ${loc.vegetationStress > 50 ? 'marked root anchorage weakening' : 'adequate vegetative cohesion'}.`,
    `Historical Seismicity & Landslide Index: Historical recurrence rating evaluated at ${loc.historicalActivity}%.`,
  ];

  const hydrologicalAssessment = `24-Hour Rainfall is measured at ${loc.currentRainfall} mm. Soil saturation is at ${loc.soilSaturation}%. Hydrostatic pore-pressure modeling indicates that infiltration exceeds lateral subsurface discharge capacity, escalating sliding friction failure probability.`;

  const exposureSummary = `Direct human exposure encompasses ${loc.populationExposed.toLocaleString()} residents across proximal habitations. Strategic infrastructure includes ${loc.infrastructure.roads} arterial road links (${loc.infrastructure.keyHighways.join(', ') || 'District corridors'}), ${loc.infrastructure.bridges} bridges, ${loc.infrastructure.hospitals} healthcare facilities, and ${loc.infrastructure.schools} schools.`;

  return {
    overview,
    geotechnicalFactors,
    hydrologicalAssessment,
    exposureSummary,
  };
}

/**
 * Generates prioritized Disaster Management Response Recommendations
 */
export function generateResponseRecommendations(loc: RiskLocation): ResponseAction[] {
  const actions: ResponseAction[] = [];
  const level = loc.calculatedLevel;

  if (level === 'CRITICAL') {
    actions.push({
      id: 'act-1',
      title: 'Dispatch Emergency Field Inspection & Geotechnical Team',
      description: `Mobilize SDMA/DDMA emergency reconnaissance unit to inspect crown cracks and toe erosion around ${loc.name}.`,
      priority: 'IMMEDIATE',
      assignedAgency: 'SDMA / PWD Highway Wing',
      status: 'In Progress',
    });
    actions.push({
      id: 'act-2',
      title: 'Issue Red Evacuation & Habitation Advisory',
      description: `Broadcast sirens and SMS cell broadcasts to ${loc.populationExposed.toLocaleString()} residents across downhill habitations to move to designated relief shelters.`,
      priority: 'IMMEDIATE',
      assignedAgency: 'District Administration / Police',
      status: 'Pending',
    });
    actions.push({
      id: 'act-3',
      title: `Pre-position Earthmovers & Heavy Machinery along ${loc.infrastructure.keyHighways[0] || 'State Corridors'}`,
      description: `Deploy JCBs, wheel loaders, and emergency recovery vehicles at strategic choke points to guarantee rapid clearance upon debris slip.`,
      priority: 'IMMEDIATE',
      assignedAgency: 'Border Roads Organisation (BRO) / NHIDCL',
      status: 'Pending',
    });
    actions.push({
      id: 'act-4',
      title: 'Emergency Medical & Trauma Preparedness',
      description: `Place ${loc.infrastructure.hospitals} local primary health center(s) and district hospital on high alert with trauma response kits and backup diesel generators.`,
      priority: 'HIGH',
      assignedAgency: 'Health & Family Welfare Dept',
      status: 'Pending',
    });
    actions.push({
      id: 'act-5',
      title: 'Automated Telemetry Frequency Boost',
      description: 'Shift rain gauge telemetry and piezometer logging intervals from 60 minutes to 5-minute continuous streaming.',
      priority: 'MONITOR',
      assignedAgency: 'IMD / State Disaster Operations Center',
      status: 'Completed',
    });
  } else if (level === 'HIGH') {
    actions.push({
      id: 'act-1',
      title: 'Issue High-Risk Travel & Commuter Warning',
      description: `Restrict night-time vehicular traffic on ${loc.infrastructure.keyHighways.join(' and ') || 'vulnerable routes'} between 19:00 - 06:00.`,
      priority: 'IMMEDIATE',
      assignedAgency: 'Traffic Police / District Transport Office',
      status: 'In Progress',
    });
    actions.push({
      id: 'act-2',
      title: 'Inspect Slope Drainage Catchment and Culverts',
      description: 'Clear debris-choked roadside drainage channels and culverts to prevent concentrated surface water infiltration.',
      priority: 'HIGH',
      assignedAgency: 'Municipal Corporation / PWD',
      status: 'Pending',
    });
    actions.push({
      id: 'act-3',
      title: 'School Closure and Community Sensitization',
      description: `Alert administration of ${loc.infrastructure.schools} vulnerable schools in downslope zones to suspend classes or shift to safe elevations.`,
      priority: 'HIGH',
      assignedAgency: 'District Education Officer',
      status: 'Pending',
    });
    actions.push({
      id: 'act-4',
      title: 'Continuous Rain Gauge & Slope Piezometer Monitoring',
      description: 'Track cumulative 3-day antecedent rainfall index against historical empirical threshold curves.',
      priority: 'MONITOR',
      assignedAgency: 'State Emergency Operation Centre (SEOC)',
      status: 'In Progress',
    });
  } else if (level === 'MODERATE') {
    actions.push({
      id: 'act-1',
      title: 'Routine Slope Patrol & Visual Inspection',
      description: 'Assign beat patrol officers to inspect road cuts along hillsides for fresh tension cracks or mudflows.',
      priority: 'HIGH',
      assignedAgency: 'Local Forest Guard / PWD Beats',
      status: 'In Progress',
    });
    actions.push({
      id: 'act-2',
      title: 'Communicate Advisory to Village Disaster Management Committees (VDMC)',
      description: 'Brief local Gaon Burahs / Village heads on emergency contact numbers and evacuation muster points.',
      priority: 'MONITOR',
      assignedAgency: 'DDMA Community Liaison',
      status: 'Pending',
    });
    actions.push({
      id: 'act-3',
      title: 'Standard Weather Radar Surveillance',
      description: 'Monitor IMD Doppler weather radar feeds for incoming convective precipitation bands.',
      priority: 'MONITOR',
      assignedAgency: 'SEOC Duty Officer',
      status: 'Completed',
    });
  } else {
    actions.push({
      id: 'act-1',
      title: 'Standard Baseline Environmental Monitoring',
      description: 'Maintain automated remote-sensing and ground telemetry under nominal operational status.',
      priority: 'MONITOR',
      assignedAgency: 'State GIS & Remote Sensing Centre',
      status: 'Completed',
    });
  }

  return actions;
}

/**
 * Computes factor contributions for XAI visual radar and bar breakdown
 */
export interface ExplainableFactorBreakdown {
  rainfallPct: number;
  slopePct: number;
  soilSaturationPct: number;
  historicalActivityPct: number;
  vegetationPct: number;
  exposurePct: number;
  dynamicShare: number;
  staticShare: number;
  exposureShare: number;
  conciseExplanation: string;
  drivers: string[];
}

export function getExplainableBreakdown(loc: RiskLocation): ExplainableFactorBreakdown {
  // Static Susceptibility (~35%)
  const slopeVal = Math.min(100, (loc.slope / 45) * 100);
  const staticScore = slopeVal * 0.45 + loc.historicalActivity * 0.35 + (loc.elevation / 3500) * 20;

  // Dynamic Trigger (~50%)
  const rainVal = Math.min(100, (loc.currentRainfall / 220) * 100);
  const dynamicScore = rainVal * 0.55 + loc.soilSaturation * 0.35 + loc.vegetationStress * 0.10;

  // Exposure (~15%)
  const popVal = Math.min(100, (loc.populationExposed / 15000) * 100);
  const infraVal = Math.min(100, loc.infrastructure.roads * 3 + loc.infrastructure.bridges * 10 + loc.infrastructure.hospitals * 12 + loc.infrastructure.schools * 5);
  const exposureScore = popVal * 0.5 + infraVal * 0.5;

  const total = staticScore * 0.35 + dynamicScore * 0.50 + exposureScore * 0.15;
  const safeTotal = total > 0 ? total : 1;

  const dynamicShare = Math.round(((dynamicScore * 0.50) / safeTotal) * 100);
  const staticShare = Math.round(((staticScore * 0.35) / safeTotal) * 100);
  const exposureShare = Math.max(0, 100 - dynamicShare - staticShare);

  // Individual factor weights for granular XAI contribution display (e.g. Rainfall 34%, Slope 27%, etc.)
  const rainfallWeight = (rainVal * 0.55) * 0.50;
  const slopeWeight = (slopeVal * 0.45) * 0.35;
  const soilSaturationWeight = (loc.soilSaturation * 0.35) * 0.50;
  const historicalWeight = (loc.historicalActivity * 0.35) * 0.35;
  const vegetationWeight = (loc.vegetationStress * 0.10) * 0.50;
  const exposureWeight = exposureScore * 0.15;

  const factorSum = rainfallWeight + slopeWeight + soilSaturationWeight + historicalWeight + vegetationWeight + exposureWeight || 1;

  const rainfallPct = Math.round((rainfallWeight / factorSum) * 100);
  const slopePct = Math.round((slopeWeight / factorSum) * 100);
  const soilSaturationPct = Math.round((soilSaturationWeight / factorSum) * 100);
  const historicalActivityPct = Math.round((historicalWeight / factorSum) * 100);
  const vegetationPct = Math.round((vegetationWeight / factorSum) * 100);
  // Ensure sum equals exactly 100%
  const exposurePct = Math.max(0, 100 - (rainfallPct + slopePct + soilSaturationPct + historicalActivityPct + vegetationPct));

  const conciseExplanation = `The location is currently classified as ${loc.calculatedLevel} risk (${loc.calculatedScore}/100) primarily due to ${
    loc.currentRainfall > 150 ? 'intense precipitation (' + loc.currentRainfall + ' mm/24h)' : 'persistent antecedent rainfall'
  }, steep terrain (${loc.slope}° slope gradient), elevated sub-surface saturation (${loc.soilSaturation}%) and historical slope instability records.`;

  return {
    rainfallPct,
    slopePct,
    soilSaturationPct,
    historicalActivityPct,
    vegetationPct,
    exposurePct,
    dynamicShare,
    staticShare,
    exposureShare,
    conciseExplanation,
    drivers: loc.primaryRiskDrivers || [],
  };
}

/**
 * Convenience wrapper for What-If simulation page
 */
export function simulateRainfallScenario(
  locations: RiskLocation[],
  params: {
    rainfallMm: number;
    rainfallIntensity: 'normal' | 'heavy' | 'cloudburst';
    soilSaturationBonus: number;
    durationHours?: number;
  }
): {
  simulatedLocations: RiskLocation[];
  summary: SimulationResultSummary;
} {
  const intensityMap: Record<string, 'Normal' | 'High' | 'Extreme'> = {
    normal: 'Normal',
    heavy: 'High',
    cloudburst: 'Extreme',
  };

  const simulationParams: SimulationParams = {
    rainfallMm: params.rainfallMm,
    soilSaturationBonus: params.soilSaturationBonus,
    rainfallIntensity: intensityMap[params.rainfallIntensity] || 'High',
    vegetationStressModifier: 0,
  };

  return runSimulation(locations, simulationParams, []);
}

