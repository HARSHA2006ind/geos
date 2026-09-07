import React, { useState, useMemo } from 'react';
import { Header } from './components/layout/Header';
import { Sidebar, NavPage } from './components/layout/Sidebar';
import { CommandCenter } from './pages/CommandCenter';
import { RiskMapPage } from './pages/RiskMapPage';
import { RiskAnalysisPage } from './pages/RiskAnalysisPage';
import { WhatIfSimulationPage } from './pages/WhatIfSimulationPage';
import { ImpactResponsePage } from './pages/ImpactResponsePage';
import { FieldReportsPage } from './pages/FieldReportsPage';
import { AlertsPage } from './pages/AlertsPage';
import { HistoricalAnalysisPage } from './pages/HistoricalAnalysisPage';
import { CreateAlertModal } from './components/modals/CreateAlertModal';
import { SubmitReportModal } from './components/modals/SubmitReportModal';
import { RiskUpdatedModal, RiskFeedbackModalData } from './components/modals/RiskUpdatedModal';
import { DemoModeGuide } from './components/demo/DemoModeGuide';
import { ToastContainer, ToastMessage } from './components/common/Toast';
import {
  nerLocations,
  activeAlertsData,
  mockFieldReports,
  historicalLandslides,
} from './data/mockData';
import { RiskLocation, AlertItem, FieldReport, NERState } from './types/disaster';
import { calculateLocationRisk } from './services/riskEngine';

export default function App() {
  const [activePage, setActivePage] = useState<NavPage>('command-center');
  const [selectedState, setSelectedState] = useState<NERState>('All NER');
  const [locations, setLocations] = useState<RiskLocation[]>(() =>
    nerLocations.map((loc) => {
      const calc = calculateLocationRisk(loc);
      return {
        ...loc,
        calculatedScore: calc.score,
        calculatedLevel: calc.level,
        primaryRiskDrivers: calc.drivers,
        confidence: loc.confidence || 88,
      };
    })
  );

  const [selectedLocation, setSelectedLocation] = useState<RiskLocation | null>(
    () => locations[0] || null
  );
  const [alerts, setAlerts] = useState<AlertItem[]>(activeAlertsData);
  const [fieldReports, setFieldReports] = useState<FieldReport[]>(mockFieldReports);

  // Modals state
  const [isCreateAlertModalOpen, setIsCreateAlertModalOpen] = useState(false);
  const [isSubmitReportModalOpen, setIsSubmitReportModalOpen] = useState(false);
  const [modalPreselectedLoc, setModalPreselectedLoc] = useState<RiskLocation | null>(null);

  // Demo mode state (SIH Presentation Walkthrough)
  const [isDemoMode, setIsDemoMode] = useState(false);
  const [demoStep, setDemoStep] = useState(1);

  // Continuous Intelligence Feedback Loop Modal State
  const [riskUpdatedData, setRiskUpdatedData] = useState<RiskFeedbackModalData | null>(null);

  // Toast notifications state
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  const addToast = (type: 'success' | 'error' | 'info', title: string, message: string) => {
    const newToast: ToastMessage = {
      id: `toast-${Date.now()}-${Math.random()}`,
      type,
      title,
      message,
    };
    setToasts((prev) => [...prev, newToast]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== newToast.id));
    }, 4500);
  };

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  // Filter locations by selected state
  const filteredLocations = useMemo(() => {
    if (selectedState === 'All NER') return locations;
    return locations.filter((loc) => loc.state === selectedState);
  }, [locations, selectedState]);

  // Actions
  const handleSelectLocation = (loc: RiskLocation | null) => {
    setSelectedLocation(loc);
  };

  const handleViewAnalysis = (loc: RiskLocation) => {
    setSelectedLocation(loc);
    setActivePage('risk-analysis');
  };

  const handleSimulate = (loc: RiskLocation) => {
    setSelectedLocation(loc);
    setActivePage('what-if-simulation');
  };

  const handleViewImpact = (loc: RiskLocation) => {
    setSelectedLocation(loc);
    setActivePage('impact-response');
  };

  const handleOpenCreateAlert = (loc?: RiskLocation) => {
    setModalPreselectedLoc(loc || selectedLocation || locations[0]);
    setIsCreateAlertModalOpen(true);
  };

  const handleBroadcastAlert = (newAlert: AlertItem) => {
    setAlerts((prev) => [newAlert, ...prev]);
    addToast(
      'success',
      'Disaster Alert Broadcasted',
      `Emergency notification dispatched to ${newAlert.locationName} authorities and citizen cell broadcasts.`
    );
  };

  const handleSubmitFieldReport = (newReport: FieldReport) => {
    setFieldReports((prev) => [newReport, ...prev]);

    let previousScore = 0;
    let updatedScore = 0;
    let affectedLocationName = newReport.locationName;
    let updatedLocationObj: RiskLocation | null = null;

    // Recalculate and update the corresponding location's score
    setLocations((prev) =>
      prev.map((loc) => {
        if (loc.id === newReport.locationId) {
          previousScore = loc.calculatedScore;
          const satBoost =
            newReport.severity === 'Critical' ? 14 : newReport.severity === 'High' ? 9 : 5;
          const rainBoost =
            newReport.severity === 'Critical' ? 28 : newReport.severity === 'High' ? 16 : 10;
          const histBoost =
            newReport.severity === 'Critical' ? 12 : newReport.severity === 'High' ? 8 : 4;

          const updatedLoc: RiskLocation = {
            ...loc,
            soilSaturation: Math.min(100, loc.soilSaturation + satBoost),
            currentRainfall: loc.currentRainfall + rainBoost,
            historicalActivity: Math.min(100, loc.historicalActivity + histBoost),
          };
          const calc = calculateLocationRisk(updatedLoc);
          updatedScore = calc.score;
          affectedLocationName = updatedLoc.name;

          const finalized: RiskLocation = {
            ...updatedLoc,
            calculatedScore: calc.score,
            calculatedLevel: calc.level,
            primaryRiskDrivers: [
              `Field Observation: ${newReport.type} (${newReport.severity})`,
              ...calc.drivers,
            ].slice(0, 4),
          };
          updatedLocationObj = finalized;
          return finalized;
        }
        return loc;
      })
    );

    // Sync selected location if affected
    if (selectedLocation && selectedLocation.id === newReport.locationId && updatedLocationObj) {
      setSelectedLocation(updatedLocationObj);
    }

    // Auto-generate emergency alert if severity is High or Critical
    if (newReport.severity === 'Critical' || newReport.severity === 'High') {
      const autoAlert: AlertItem = {
        id: `alert-auto-${Date.now()}`,
        locationId: newReport.locationId || 'loc-dima-hasao',
        locationName: newReport.locationName,
        state: newReport.state || 'Assam',
        lat: newReport.lat,
        lng: newReport.lng,
        riskScore: updatedScore || 88,
        riskLevel: newReport.severity === 'Critical' ? 'CRITICAL' : 'HIGH',
        trigger: `Ground Verification: ${newReport.type} reported by ${newReport.role}`,
        potentialImpact: 'Immediate blockage of arterial highway corridor & structural slope threat.',
        recommended: 'Deploy SDRF rescue column and close traffic along affected sector.',
        recommendedActions: [
          'Pre-position earthmovers and clear culverts',
          'Enforce Section 144 traffic diversion',
          'Establish emergency relief satellite communication',
        ],
        timestamp: 'Just now',
        status: 'ACTIVE',
      };
      setAlerts((prev) => [autoAlert, ...prev]);
    }

    // Trigger prominent Continuous Intelligence Feedback Loop banner
    setRiskUpdatedData({
      show: true,
      locationName: affectedLocationName,
      previousScore: previousScore || 63,
      newScore: updatedScore || 78,
      reason: `${newReport.severity} severity ground observation received: ${newReport.type} reported by ${newReport.role}.`,
    });

    addToast(
      'success',
      'Ground Observation Ingested',
      `Hazard score for ${newReport.locationName} recalculated in real time.`
    );
  };

  // Demo Mode Handlers (Smart India Hackathon Walkthrough)
  const handleExecuteDemoStep = (step: number) => {
    const dimaHasao =
      locations.find((l) => l.id === 'loc-dima-hasao') ||
      locations.find((l) => l.name.toLowerCase().includes('dima hasao')) ||
      locations[0];

    if (step === 1) {
      setSelectedLocation(dimaHasao);
      setSelectedState('Assam');
      setActivePage('risk-map');
      addToast(
        'info',
        'Demo Step 1/7: Target Area Focus',
        'Selected Haflong & Jatinga (Dima Hasao, Assam) - Critical Landslide Corridor.'
      );
    } else if (step === 2) {
      setSelectedLocation(dimaHasao);
      setActivePage('risk-analysis');
      addToast(
        'info',
        'Demo Step 2/7: Explainable AI',
        'Inspecting multi-factor diagnostic breakdown and geotechnical risk drivers.'
      );
    } else if (step === 3) {
      setSelectedLocation(dimaHasao);
      setActivePage('what-if-simulation');
      addToast(
        'info',
        'Demo Step 3/7: What-If Stress Testing',
        'Precipitation surge applied (+40% rainfall / 240mm storm).'
      );
    } else if (step === 4) {
      setActivePage('what-if-simulation');
      addToast(
        'info',
        'Demo Step 4/7: Spatial Expansion',
        'Notice +12 regional zones transitioned to CRITICAL status on the GIS map.'
      );
    } else if (step === 5) {
      setActivePage('impact-response');
      setSelectedLocation(dimaHasao);
      addToast(
        'info',
        'Demo Step 5/7: Impact Assessment',
        'Reviewing 14,800 exposed residents and blocked NH-54E / Hill Railway lines.'
      );
    } else if (step === 6) {
      setActivePage('impact-response');
      setSelectedLocation(dimaHasao);
      addToast(
        'info',
        'Demo Step 6/7: Operational Response Plan',
        'Standard Operating Procedures (SOPs) prioritized across 0-2h, 2-6h, and 6-24h timeframes.'
      );
    } else if (step === 7) {
      const verifiedObservation: FieldReport = {
        id: `report-sih-demo-${Date.now()}`,
        locationId: dimaHasao.id,
        locationName: dimaHasao.name,
        state: dimaHasao.state,
        lat: dimaHasao.lat + 0.005,
        lng: dimaHasao.lng - 0.003,
        type: 'Landslide',
        severity: 'Critical',
        description:
          'High pore-pressure seepage and 40-meter rotational slump blocking culvert on NH-54E KM 38 near Jatinga.',
        role: 'Field Officer',
        submittedBy: 'SDRF Patrol Unit 4',
        verificationStatus: 'Verified',
        timestamp: 'Just now',
        verified: true,
        imageUrl:
          'https://images.unsplash.com/photo-1541888946425-d0fbb18086f6?auto=format&fit=crop&w=600&q=80',
      };
      handleSubmitFieldReport(verifiedObservation);
      setSelectedLocation(dimaHasao);
      setActivePage('risk-map');
    }
  };

  const handleToggleDemoMode = () => {
    if (!isDemoMode) {
      setIsDemoMode(true);
      setDemoStep(1);
      handleExecuteDemoStep(1);
    } else {
      setIsDemoMode(false);
    }
  };

  const handleNextDemoStep = () => {
    if (demoStep < 7) {
      const next = demoStep + 1;
      setDemoStep(next);
      handleExecuteDemoStep(next);
    } else {
      setIsDemoMode(false);
      addToast(
        'success',
        'Presentation Tour Complete',
        'GeoResilience-NER end-to-end mission demonstration completed successfully.'
      );
    }
  };

  const handlePrevDemoStep = () => {
    if (demoStep > 1) {
      const prev = demoStep - 1;
      setDemoStep(prev);
      handleExecuteDemoStep(prev);
    }
  };

  const handleSelectDemoStep = (step: number) => {
    setDemoStep(step);
    handleExecuteDemoStep(step);
  };

  const handleUpdateAlertStatus = (alertId: string, newStatus: AlertItem['status']) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, status: newStatus } : a))
    );
    addToast(
      'info',
      'Alert Status Updated',
      `Alert marked as ${newStatus}. Updated in the SEOC regional master log.`
    );
  };

  const handleFilterByLevel = (level: string) => {
    setActivePage('risk-map');
  };

  const unreadAlertsCount = alerts.filter((a) => a.status === 'ACTIVE').length;

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#090d16] text-slate-100 font-sans select-none">
      {/* 1. Main Left Sidebar */}
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        activeAlertsCount={unreadAlertsCount}
      />

      {/* 2. Main Body Container */}
      <div className="flex-1 flex flex-col min-w-0 h-full overflow-hidden">
        {/* Top Header */}
        <Header
          selectedState={selectedState}
          onSelectState={setSelectedState}
          locations={locations}
          onSelectLocation={(loc) => {
            setSelectedLocation(loc);
            if (activePage === 'command-center') {
              // Stay on command center
            } else if (activePage !== 'risk-map') {
              setActivePage('risk-analysis');
            }
          }}
          unreadAlertsCount={unreadAlertsCount}
          onOpenAlerts={() => setActivePage('alerts')}
          isDemoMode={isDemoMode}
          onToggleDemoMode={handleToggleDemoMode}
        />

        {/* Dynamic Page Router */}
        <main className="flex-1 overflow-y-auto p-3 sm:p-4 bg-[#090d16]">
          {activePage === 'command-center' && (
            <CommandCenter
              locations={filteredLocations}
              selectedLocation={selectedLocation}
              onSelectLocation={handleSelectLocation}
              alerts={alerts}
              historicalLandslides={historicalLandslides}
              fieldReports={fieldReports}
              onViewAnalysis={handleViewAnalysis}
              onSimulate={handleSimulate}
              onGenerateAlert={handleOpenCreateAlert}
              onViewAllAlerts={() => setActivePage('alerts')}
              onSelectAlert={(a) => {
                const loc = locations.find((l) => l.id === a.locationId);
                if (loc) setSelectedLocation(loc);
                setActivePage('alerts');
              }}
              onFilterByLevel={handleFilterByLevel}
            />
          )}

          {activePage === 'risk-map' && (
            <RiskMapPage
              locations={filteredLocations}
              selectedLocation={selectedLocation}
              onSelectLocation={handleSelectLocation}
              historicalLandslides={historicalLandslides}
              fieldReports={fieldReports}
              onViewAnalysis={handleViewAnalysis}
              onSimulate={handleSimulate}
            />
          )}

          {activePage === 'risk-analysis' && (
            <RiskAnalysisPage
              locations={locations}
              selectedLocation={selectedLocation}
              onSelectLocation={setSelectedLocation}
              onSimulate={handleSimulate}
              onViewImpact={handleViewImpact}
            />
          )}

          {activePage === 'what-if-simulation' && (
            <WhatIfSimulationPage
              locations={locations}
              selectedLocation={selectedLocation}
              onSelectLocation={setSelectedLocation}
              historicalLandslides={historicalLandslides}
              fieldReports={fieldReports}
            />
          )}

          {activePage === 'impact-response' && (
            <ImpactResponsePage
              locations={locations}
              selectedLocation={selectedLocation}
              onSelectLocation={setSelectedLocation}
              onOpenCreateAlert={handleOpenCreateAlert}
            />
          )}

          {activePage === 'field-reports' && (
            <FieldReportsPage
              reports={fieldReports}
              locations={locations}
              onOpenSubmitModal={() => setIsSubmitReportModalOpen(true)}
              onSelectLocationOnMap={(loc) => {
                setSelectedLocation(loc);
                setActivePage('risk-map');
              }}
            />
          )}

          {activePage === 'alerts' && (
            <AlertsPage
              alerts={alerts}
              locations={locations}
              onOpenCreateAlertModal={() => handleOpenCreateAlert()}
              onUpdateAlertStatus={handleUpdateAlertStatus}
            />
          )}

          {activePage === 'historical-analysis' && <HistoricalAnalysisPage />}
        </main>
      </div>

      {/* Modals & Feedback */}
      <CreateAlertModal
        isOpen={isCreateAlertModalOpen}
        onClose={() => setIsCreateAlertModalOpen(false)}
        locations={locations}
        preselectedLocation={modalPreselectedLoc}
        onBroadcastAlert={handleBroadcastAlert}
      />

      <SubmitReportModal
        isOpen={isSubmitReportModalOpen}
        onClose={() => setIsSubmitReportModalOpen(false)}
        locations={locations}
        onSubmitReport={handleSubmitFieldReport}
      />

      {/* Continuous Intelligence Feedback Banner Modal */}
      <RiskUpdatedModal
        data={riskUpdatedData}
        onClose={() => setRiskUpdatedData(null)}
      />

      {/* Smart India Hackathon Presentation Guide */}
      {isDemoMode && (
        <DemoModeGuide
          currentStep={demoStep}
          totalSteps={7}
          onNextStep={handleNextDemoStep}
          onPrevStep={handlePrevDemoStep}
          onSelectStep={handleSelectDemoStep}
          onExitDemo={() => setIsDemoMode(false)}
          onExecuteStepAction={handleExecuteDemoStep}
          selectedLocation={selectedLocation}
        />
      )}

      <ToastContainer toasts={toasts} onDismiss={removeToast} />
    </div>
  );
}
