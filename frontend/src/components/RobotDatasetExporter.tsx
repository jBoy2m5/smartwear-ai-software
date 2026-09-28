import React from 'react';
import { Database, Download, CheckCircle2, Box, Cpu } from 'lucide-react';

export default function RobotDatasetExporter() {
  return (
    <div className="bg-panelBg rounded-xl p-5 md:p-6 border border-slate-700/50 flex flex-col h-full shadow-lg relative overflow-hidden">
      {/* Decorative background element */}
      <div className="absolute -top-10 -right-10 opacity-[0.03] pointer-events-none">
        <Cpu className="w-64 h-64 text-white" />
      </div>

      <div className="flex items-center gap-3 mb-6 relative z-10 shrink-0">
        <div className="w-1.5 h-6 bg-blue-500 rounded-full"></div>
        <h2 className="text-lg md:text-xl font-bold text-white uppercase tracking-wider font-heading">Robot & Humanoid Dataset Exporter</h2>
      </div>

      <div className="flex-1 flex flex-col gap-5 relative z-10 mb-6 justify-center">
        <div className="bg-[#0B121C] border border-slate-700 p-5 rounded-xl flex flex-col gap-5 shadow-inner">
          <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-2 border-b border-slate-700/50 pb-4">
            <span className="text-xs md:text-sm text-slate-400 font-bold uppercase tracking-wider">Session ID</span>
            <span className="text-white font-mono font-bold bg-slate-800 px-3 py-1 rounded text-sm">SESS_DENSO_2026_01</span>
          </div>
          
          <div className="flex flex-col md:flex-row md:justify-between md:items-center gap-2 border-b border-slate-700/50 pb-4">
            <span className="text-xs md:text-sm text-slate-400 font-bold uppercase tracking-wider">Status</span>
            <div className="flex items-center gap-2 bg-cyberGreen/10 border border-cyberGreen/30 px-3 py-1.5 rounded-full w-max">
              <CheckCircle2 className="w-4 h-4 text-cyberGreen" />
              <span className="text-cyberGreen text-xs font-bold tracking-wide">Ready for Imitation Learning</span>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4 mt-2">
            <div className="bg-slate-800/50 rounded-lg p-4 flex flex-col border border-slate-700/50">
              <span className="text-[10px] md:text-xs text-slate-400 uppercase tracking-widest font-bold mb-1">Total Frames</span>
              <span className="text-2xl md:text-3xl text-white font-mono font-bold">14,250</span>
            </div>
            <div className="bg-slate-800/50 rounded-lg p-4 flex flex-col border border-slate-700/50">
              <span className="text-[10px] md:text-xs text-slate-400 uppercase tracking-widest font-bold mb-1">Est. Size</span>
              <span className="text-2xl md:text-3xl text-white font-mono font-bold">45.2 <span className="text-sm text-slate-400">MB</span></span>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-auto shrink-0 relative z-10">
        <button className="flex items-center justify-between gap-3 bg-densoNavy hover:bg-blue-900 border border-blue-800 text-white py-3 px-4 rounded-lg font-bold transition-colors group shadow-lg">
          <div className="flex items-center gap-3">
            <Box className="w-5 h-5 text-blue-300 group-hover:text-white transition-colors shrink-0" />
            <div className="flex flex-col items-start text-left">
              <span className="text-sm leading-tight">Download ROSbag</span>
              <span className="text-[10px] text-blue-300 font-mono">(.bag format)</span>
            </div>
          </div>
          <Download className="w-4 h-4 opacity-50 group-hover:opacity-100 group-hover:text-cyberGreen shrink-0" />
        </button>
        <button className="flex items-center justify-between gap-3 bg-slate-800 hover:bg-slate-700 border border-slate-600 text-white py-3 px-4 rounded-lg font-bold transition-colors group shadow-lg">
          <div className="flex items-center gap-3">
            <Database className="w-5 h-5 text-gray-400 group-hover:text-white transition-colors shrink-0" />
            <div className="flex flex-col items-start text-left">
              <span className="text-sm leading-tight">Download Dataset</span>
              <span className="text-[10px] text-gray-400 font-mono">(.JSON format)</span>
            </div>
          </div>
          <Download className="w-4 h-4 opacity-50 group-hover:opacity-100 group-hover:text-cyberGreen shrink-0" />
        </button>
      </div>
    </div>
  );
}
