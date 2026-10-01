import type { TelemetryData } from '../MockDataEngine';
import { Battery, BatteryCharging, Wifi, WifiOff } from 'lucide-react';
import clsx from 'clsx';

export default function TelemetryHeader({ telemetry }: { telemetry: TelemetryData }) {
  const { worker, sensor_telemetry } = telemetry;
  
  return (
    <div className="bg-panelBg rounded-xl p-4 flex flex-row justify-between items-center shadow-md border border-slate-700/50">
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 bg-densoNavy rounded flex items-center justify-center border border-cyberGreen/30">
          <span className="text-cyberGreen font-bold text-xl">AI</span>
        </div>
        <h1 className="text-xl md:text-2xl font-bold text-white tracking-wide">
          SmartWear AI <span className="text-gray-500 font-normal">| Live Gemba Monitor</span>
        </h1>
      </div>

      <div className="flex items-center gap-6 md:gap-8">
        <div className="flex flex-col items-end">
          <span className="text-xs text-gray-400 uppercase tracking-wider">Worker ID: {worker.id}</span>
          <div className="flex items-center mt-1">
            <span className="font-semibold text-white">{worker.name}</span>
            <span className="text-xs text-cyberGreen ml-2 py-0.5 px-2 bg-cyberGreen/10 border border-cyberGreen/30 rounded-full">{worker.level}</span>
          </div>
        </div>
        
        <div className="h-10 w-px bg-slate-700 mx-2 hidden md:block"></div>
        
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-3">
            <Battery className="w-6 h-6 text-gray-400" />
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-400 uppercase">Cap Battery</span>
              <span className="text-sm font-bold text-white">{sensor_telemetry.battery_cap}%</span>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
            <BatteryCharging className="w-6 h-6 text-gray-400" />
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-400 uppercase">Wrist Battery</span>
              <span className="text-sm font-bold text-white">{sensor_telemetry.battery_wrist}%</span>
            </div>
          </div>

          <div className="flex items-center gap-3 bg-slate-800 p-2 rounded-lg border border-slate-700">
            {sensor_telemetry.ping_ms < 50 ? <Wifi className="w-5 h-5 text-cyberGreen" /> : <WifiOff className="w-5 h-5 text-alertRed" />}
            <div className="flex flex-col">
              <span className="text-[10px] text-gray-400 uppercase">MQTT Ping</span>
              <span className={clsx("text-sm font-bold", sensor_telemetry.ping_ms < 15 ? "text-cyberGreen" : "text-white")}>{sensor_telemetry.ping_ms}ms</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
