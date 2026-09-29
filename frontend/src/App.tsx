import React, { useEffect, useState } from 'react';
import { mockEngine } from './MockDataEngine';
import type { TelemetryData } from './MockDataEngine';
import TelemetryHeader from './components/TelemetryHeader';
import FPVOverlay from './components/FPVOverlay';
import RealtimeCharts from './components/RealtimeCharts';
import CycleTimeAlert from './components/CycleTimeAlert';

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
      <TelemetryHeader telemetry={telemetry} />
      
      <div className="flex-1 flex flex-row gap-4 mt-4 overflow-hidden">
        {/* Left column - FPV Video & Canvas Overlay */}
        <div className="flex-[2] bg-panelBg rounded-xl overflow-hidden relative shadow-lg border border-slate-700/50">
          <FPVOverlay landmarks={telemetry.hand_landmarks_3d} />
        </div>

        {/* Right column - Real-time Charts */}
        <div className="flex-1 bg-panelBg rounded-xl p-4 shadow-lg overflow-hidden flex flex-col border border-slate-700/50">
          <RealtimeCharts telemetry={telemetry} />
        </div>
      </div>

      {/* Bottom Bar - Cycle Time & Muda Alert */}
      <div className="mt-4">
        <CycleTimeAlert step={telemetry.step_analysis} />
      </div>
    </div>
  );
}

export default App;
