import React from 'react';
import type { TelemetryData } from '../MockDataEngine';
import { AlertTriangle, CheckCircle } from 'lucide-react';
import clsx from 'clsx';

export default function CycleTimeAlert({ step }: { step: TelemetryData['step_analysis'] }) {
  const { elapsed_time_sec, baseline_target_sec, muda_detected, muda_type } = step;
  
  const progressPercent = Math.min(100, (elapsed_time_sec / baseline_target_sec) * 100);
  const overagePercent = Math.max(0, ((elapsed_time_sec - baseline_target_sec) / baseline_target_sec) * 100);
  
  return (
    <div className={clsx(
      "rounded-xl p-5 shadow-lg transition-all duration-300 relative overflow-hidden",
      muda_detected ? "bg-red-950/40 border border-alertRed" : "bg-panelBg border border-slate-700/50"
    )}>
      {muda_detected && (
        <div className="absolute inset-0 bg-alertRed/5 animate-pulse pointer-events-none"></div>
      )}

      <div className="flex justify-between items-end mb-4 relative z-10">
        <div className="flex items-center gap-4">
          <div className={clsx(
            "w-12 h-12 rounded-lg flex items-center justify-center border",
            muda_detected ? "bg-alertRed/20 border-alertRed/50 text-alertRed" : "bg-cyberGreen/20 border-cyberGreen/50 text-cyberGreen"
          )}>
            {muda_detected ? <AlertTriangle className="w-6 h-6 animate-pulse" /> : <CheckCircle className="w-6 h-6" />}
          </div>
          <div>
            <h2 className="text-xl font-bold text-white tracking-wide">Cycle Time & Takt Sync</h2>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm font-semibold bg-slate-800 px-2 py-0.5 rounded text-gray-300 border border-slate-700">Step {step.current_step_id}</span>
              <span className="text-sm text-gray-400">{step.step_name}</span>
            </div>
          </div>
        </div>
        
        <div className="flex flex-col items-end">
          <span className="text-xs text-gray-500 uppercase tracking-wider mb-1">Elapsed / Baseline</span>
          <div className="flex items-baseline gap-2">
            <span className={clsx("text-4xl font-mono font-bold", muda_detected ? "text-alertRed animate-pulse" : "text-white")}>
              {elapsed_time_sec.toFixed(1)}s
            </span>
            <span className="text-xl text-gray-500 font-mono">/ {baseline_target_sec.toFixed(1)}s</span>
          </div>
        </div>
      </div>

      <div className="relative w-full h-6 bg-slate-800 rounded-full overflow-hidden border border-slate-700 shadow-inner z-10">
        <div 
          className={clsx(
            "h-full transition-all duration-[16ms] ease-linear",
            muda_detected ? "bg-alertRed" : "bg-cyberGreen"
          )}
          style={{ width: `${Math.min(100, progressPercent)}%` }}
        />
        {muda_detected && (
          <div 
            className="absolute top-0 bottom-0 left-0 bg-alertRed opacity-50"
            style={{ width: `${progressPercent}%`, left: '100%' }}
          />
        )}
        {/* Baseline Marker */}
        <div 
          className="absolute top-0 bottom-0 w-1 bg-white shadow-[0_0_8px_rgba(255,255,255,0.8)] z-20" 
          style={{ left: '100%', transform: 'translateX(-100%)' }}
        />
      </div>

      <div className="mt-4 flex items-center justify-between relative z-10">
        <div className="flex flex-1">
          {muda_detected ? (
            <div className="flex items-center gap-3 bg-alertRed/10 border border-alertRed/30 px-4 py-2 rounded-lg w-full">
              <span className="text-alertRed font-bold uppercase tracking-wider flex-shrink-0 text-sm">Muda Detected</span>
              <div className="w-px h-4 bg-alertRed/30 mx-1"></div>
              <span className="text-red-200 text-sm truncate">{muda_type}</span>
            </div>
          ) : (
            <div className="flex items-center gap-3 bg-cyberGreen/10 border border-cyberGreen/30 px-4 py-2 rounded-lg">
              <span className="text-cyberGreen font-bold uppercase tracking-wider text-sm">Optimal Pacing</span>
              <div className="w-px h-4 bg-cyberGreen/30 mx-1"></div>
              <span className="text-green-200 text-sm">Action aligned with golden baseline</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
