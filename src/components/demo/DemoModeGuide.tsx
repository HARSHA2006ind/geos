import React from 'react';
import {
  Sparkles,
  ChevronRight,
  ChevronLeft,
  X,
  Play,
  CheckCircle2,
  Sliders,
  MapPin,
  FileText,
  ShieldAlert,
  Flame,
  Users,
  Compass,
} from 'lucide-react';
import { RiskLocation } from '../../types/disaster';

export interface DemoStepInfo {
  number: number;
  title: string;
  subtitle: string;
  description: string;
  actionLabel: string;
  icon: React.ReactNode;
}

interface DemoModeGuideProps {
  currentStep: number;
  totalSteps: number;
  onNextStep: () => void;
  onPrevStep: () => void;
  onSelectStep: (step: number) => void;
  onExitDemo: () => void;
  onExecuteStepAction: (step: number) => void;
  selectedLocation: RiskLocation | null;
}

export const DEMO_STEPS: DemoStepInfo[] = [
  {
    number: 1,
    title: 'Select High-Risk Area',
    subtitle: 'Where is the risk?',
    description:
      'Evaluate critical landslide hotspots in NER. Selecting Haflong & Jatinga (Dima Hasao, Assam) or Papum Pare (Arunachal Pradesh) activates real-time GIS telemetry and hazard scoring.',
    actionLabel: 'Focus on Dima Hasao, Assam',
    icon: <MapPin className="w-4 h-4 text-cyan-400" />,
  },
  {
    number: 2,
    title: 'Explain Why It Is Risky',
    subtitle: 'Why is this location risky?',
    description:
      'Review the Explainable AI (XAI) multi-factor breakdown: Rainfall (34%), Slope (27%), Soil Saturation (16%), and History (13%) along with the Gemini-powered geotechnical briefing.',
    actionLabel: 'Open XAI Risk Diagnosis',
    icon: <FileText className="w-4 h-4 text-cyan-400" />,
  },
  {
    number: 3,
    title: 'Run What-If Simulation (+40% Rain)',
    subtitle: 'What happens if conditions worsen?',
    description:
      'Subject the terrain model to a +40% monsoon precipitation surge (240 mm / 24h cloudburst) and observe recalculation across all dynamic hydrometeorological triggers.',
    actionLabel: 'Apply +40% Rainfall Surge',
    icon: <Sliders className="w-4 h-4 text-blue-400" />,
  },
  {
    number: 4,
    title: 'Show Expanded Heuristic Zone',
    subtitle: 'Simulated expansion of stress corridors',
    description:
      'Observe how the prototype heuristic circles expand under higher rainfall inputs (unvalidated demonstration mode — Factor of Safety is not physically modeled yet).',
    actionLabel: 'Inspect Expanded Demo Map',
    icon: <Flame className="w-4 h-4 text-red-400" />,
  },
  {
    number: 5,
    title: 'Review Demo Exposure & Lifelines',
    subtitle: 'Prototype impact layout',
    description:
      'Examine the prototype exposure and lifeline checklist layout. Real WorldPop and OpenStreetMap infrastructure intersections are scheduled for Phase 2.',
    actionLabel: 'View Impact Layout',
    icon: <Users className="w-4 h-4 text-purple-400" />,
  },
  {
    number: 6,
    title: 'Review Response Checklist',
    subtitle: 'Operational workflow prototype',
    description:
      'Inspect dynamically generated location directives grouped by priority level with session-only alert drafting.',
    actionLabel: 'Open Response Checklist',
    icon: <ShieldAlert className="w-4 h-4 text-rose-400" />,
  },
  {
    number: 7,
    title: 'Record Session Field Report',
    subtitle: 'Simulated ground observation loop',
    description:
      'Record a simulated ground observation in the browser session to test recalculation of the prototype heuristic index.',
    actionLabel: 'Trigger Simulated Report Loop',
    icon: <Sparkles className="w-4 h-4 text-amber-400" />,
  },
];

export const DemoModeGuide: React.FC<DemoModeGuideProps> = ({
  currentStep,
  totalSteps,
  onNextStep,
  onPrevStep,
  onSelectStep,
  onExitDemo,
  onExecuteStepAction,
}) => {
  const stepInfo = DEMO_STEPS[currentStep - 1] || DEMO_STEPS[0];

  return (
    <div className="fixed bottom-4 left-1/2 -translate-x-1/2 z-50 w-full max-w-4xl px-4 animate-in slide-in-from-bottom-6 duration-300">
      <div className="bg-[#0b1322]/95 backdrop-blur-md border-2 border-amber-500/70 rounded-2xl shadow-[0_10px_40px_rgba(0,0,0,0.8)] p-4 text-slate-100 space-y-3">
        {/* Header Strip */}
        <div className="flex items-center justify-between gap-2 pb-2 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded-md bg-amber-950 border border-amber-500/50 flex items-center justify-center text-amber-400">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <div>
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-amber-300">
                Simulated Presentation Mode (Demo Walkthrough)
              </span>
              <span className="text-xs font-bold text-slate-200 ml-2 hidden sm:inline font-display">
                GeoResilience-NER 2.0 UI Tour
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            {/* Step badges */}
            <div className="flex items-center gap-1">
              {DEMO_STEPS.map((s) => (
                <button
                  key={s.number}
                  onClick={() => onSelectStep(s.number)}
                  className={`w-6 h-6 rounded-md text-[11px] font-mono font-bold transition flex items-center justify-center ${
                    currentStep === s.number
                      ? 'bg-cyan-500 text-slate-950 shadow-md shadow-cyan-500/40 scale-105'
                      : currentStep > s.number
                      ? 'bg-slate-800 text-emerald-400 border border-emerald-500/40'
                      : 'bg-slate-900 text-slate-500 hover:text-slate-300 border border-slate-800'
                  }`}
                  title={`Step ${s.number}: ${s.title}`}
                >
                  {currentStep > s.number ? '✓' : s.number}
                </button>
              ))}
            </div>

            <button
              onClick={onExitDemo}
              className="p-1 rounded-md text-slate-400 hover:text-white hover:bg-slate-800 transition ml-2"
              title="Exit Demo Mode"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1 flex-1">
            <div className="flex items-center gap-2">
              <span className="px-2 py-0.5 rounded bg-cyan-950/80 text-cyan-300 border border-cyan-500/40 text-[10px] font-mono font-bold uppercase">
                Step {stepInfo.number} of {totalSteps}
              </span>
              <span className="text-[11px] text-slate-400 italic">
                "{stepInfo.subtitle}"
              </span>
            </div>

            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
              {stepInfo.icon}
              <span>{stepInfo.title}</span>
            </h3>

            <p className="text-xs text-slate-300 leading-relaxed max-w-2xl">
              {stepInfo.description}
            </p>
          </div>

          {/* Action & Nav Buttons */}
          <div className="flex flex-wrap items-center gap-2 shrink-0">
            <button
              id="demo-action-execute-btn"
              onClick={() => onExecuteStepAction(currentStep)}
              className="px-3.5 py-1.5 bg-cyan-600 hover:bg-cyan-500 text-slate-950 font-bold rounded-lg text-xs flex items-center gap-1.5 shadow-md shadow-cyan-600/30 transition"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>{stepInfo.actionLabel}</span>
            </button>

            <div className="flex items-center gap-1.5">
              <button
                id="demo-prev-step-btn"
                onClick={onPrevStep}
                disabled={currentStep <= 1}
                className="px-2.5 py-1.5 bg-slate-800 hover:bg-slate-700 disabled:opacity-30 text-slate-200 rounded-lg text-xs font-semibold border border-slate-700 transition flex items-center gap-1"
              >
                <ChevronLeft className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Prev</span>
              </button>

              <button
                id="demo-next-step-btn"
                onClick={onNextStep}
                disabled={currentStep >= totalSteps}
                className="px-3 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:opacity-30 text-white rounded-lg text-xs font-bold border border-blue-500/50 shadow transition flex items-center gap-1"
              >
                <span>{currentStep === totalSteps ? 'Complete' : 'Next'}</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
