import React, { useEffect, useState } from 'react';
import { mockEngine } from './MockDataEngine';
import type { TelemetryData } from './MockDataEngine';
import TelemetryHeader from './components/TelemetryHeader';
import FPVOverlay from './components/FPVOverlay';
import RealtimeCharts from './components/RealtimeCharts';
import CycleTimeAlert from './components/CycleTimeAlert';
import AutoSopGenerator from './components/AutoSopGenerator';
import RobotDatasetExporter from './components/RobotDatasetExporter';

function App() {
  const [telemetry, setTelemetry] = useState<TelemetryData | null>(null);

  useEffect(() => {
    mockEngine.start();
    const unsubscribe = mockEngine.subscribe((data) => {
      setTelemetry(data);
    });

    return () => {
      unsubscribe();
      mockEngine.stop();
    };
  }, []);

  if (!telemetry) return <div className="flex h-screen items-center justify-center bg-background text-cyberGreen">Loading telemetry...</div>;

  const isMuda = telemetry.step_analysis.muda_detected;

  return (
    <div className={`min-h-screen bg-background flex flex-col p-4 transition-colors duration-300 ${isMuda ? 'border-4 border-alertRed' : 'border-4 border-transparent'}`}>
      <div className="shrink-0">
        <TelemetryHeader telemetry={telemetry} />
      </div>
      
      <div className="flex-1 flex flex-col lg:flex-row gap-4 mt-4 min-h-[450px]">
        {/* Left column - FPV Video & Canvas Overlay */}
        <div className="flex-[2] bg-panelBg rounded-xl overflow-hidden relative shadow-lg border border-slate-700/50 min-h-[300px]">
          <FPVOverlay landmarks={telemetry.hand_landmarks_3d} />
        </div>

        {/* Right column - Real-time Charts */}
        <div className="flex-[1] bg-panelBg rounded-xl p-4 shadow-lg flex flex-col border border-slate-700/50 min-h-[300px]">
          <RealtimeCharts telemetry={telemetry} />
        </div>
      </div>

      {/* Bottom Bar - Cycle Time & Muda Alert */}
      <div className="mt-4 shrink-0">
        <CycleTimeAlert step={telemetry.step_analysis} />
      </div>

      {/* Layer 4: Export Tools */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mt-8 pt-6 border-t border-slate-800 shrink-0 min-h-[450px]">
        <AutoSopGenerator />
        <RobotDatasetExporter />
      </div>
    </div>
  );
}

export default App;
