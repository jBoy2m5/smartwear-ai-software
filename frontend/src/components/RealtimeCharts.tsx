import React, { useEffect, useState } from 'react';
import type { TelemetryData } from '../MockDataEngine';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

export default function RealtimeCharts({ telemetry }: { telemetry: TelemetryData }) {
  const [data, setData] = useState<any[]>([]);

  useEffect(() => {
    setData(prev => {
      const newPoint = {
        time: new Date(telemetry.timestamp).toLocaleTimeString('en-US', { hour12: false, fractionalSecondDigits: 1 }),
        force: telemetry.sensor_telemetry.force_total_N,
        velocity: telemetry.sensor_telemetry.wrist_velocity_mps
      };
      const newData = [...prev, newPoint];
      // Keep last 60 points for 1 second of data if 60fps, let's keep 120 points for 2 seconds
      if (newData.length > 120) return newData.slice(newData.length - 120);
      return newData;
    });
  }, [telemetry]);

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-1.5 h-6 bg-cyberGreen rounded-full"></div>
        <h2 className="text-lg font-bold text-white uppercase tracking-wider">Sensor Telemetry</h2>
      </div>
      
      {/* Force Graph */}
      <div className="flex-1 flex flex-col bg-slate-800/80 rounded-xl p-4 border border-slate-700/50 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
           <svg className="w-16 h-16 text-cyberGreen" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 10V3L4 14h7v7l9-11h-7z"></path></svg>
        </div>
        <div className="flex justify-between items-end mb-4 z-10">
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Force (sEMG/FSR)</h3>
            <p className="text-xs text-gray-500">Muscle effort & grip strength</p>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-cyberGreen font-mono font-bold text-3xl">{telemetry.sensor_telemetry.force_total_N.toFixed(1)}</span>
            <span className="text-cyberGreen/60 text-sm font-mono">N</span>
          </div>
        </div>
        <div className="flex-1 min-h-[80px] z-10">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorForce" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#00E676" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#00E676" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="time" hide />
              <YAxis domain={[0, 25]} stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                itemStyle={{ color: '#00E676' }}
                labelStyle={{ display: 'none' }}
              />
              <Area type="monotone" dataKey="force" stroke="#00E676" strokeWidth={2} fillOpacity={1} fill="url(#colorForce)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
        
        {/* Finger Force Bars */}
        <div className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2 z-10 w-full pt-2 border-t border-slate-700/50 shrink-0">
          {Object.entries(telemetry.sensor_telemetry.force_fingers_N).map(([finger, value]) => {
            const pct = Math.min(100, (value / 10) * 100);
            const isHigh = value > 5;
            return (
              <div key={finger} className="flex flex-col">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-[10px] text-gray-400 font-mono uppercase font-semibold">{finger}</span>
                  <span className="text-[10px] font-bold font-mono text-white">
                    {value.toFixed(1)}<span className="text-gray-500 ml-0.5">N</span>
                  </span>
                </div>
                <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden border border-slate-700/50 shrink-0">
                  <div 
                    className={`h-full rounded-full transition-all duration-[16ms] ease-linear ${isHigh ? 'bg-orange-500 shadow-[0_0_8px_rgba(249,115,22,0.8)]' : 'bg-cyberGreen shadow-[0_0_8px_rgba(0,230,118,0.5)]'}`}
                    style={{ width: `${pct}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Kinematics Graph */}
      <div className="flex-1 flex flex-col bg-slate-800/80 rounded-xl p-4 border border-slate-700/50 relative overflow-hidden">
        <div className="absolute top-0 right-0 p-4 opacity-10 pointer-events-none">
           <svg className="w-16 h-16 text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
        </div>
        <div className="flex justify-between items-end mb-4 z-10">
          <div>
            <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">Kinematics (IMU)</h3>
            <p className="text-xs text-gray-500">Wrist velocity & trajectory</p>
          </div>
          <div className="flex items-baseline gap-1">
            <span className="text-cyan-400 font-mono font-bold text-3xl">{telemetry.sensor_telemetry.wrist_velocity_mps.toFixed(2)}</span>
            <span className="text-cyan-400/60 text-sm font-mono">m/s</span>
          </div>
        </div>
        <div className="flex-1 min-h-[150px] z-10">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 5, right: 0, left: -20, bottom: 0 }}>
              <defs>
                <linearGradient id="colorVelocity" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#22D3EE" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#22D3EE" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
              <XAxis dataKey="time" hide />
              <YAxis domain={[0, 2]} stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px' }}
                itemStyle={{ color: '#22D3EE' }}
                labelStyle={{ display: 'none' }}
              />
              <Area type="monotone" dataKey="velocity" stroke="#22D3EE" strokeWidth={2} fillOpacity={1} fill="url(#colorVelocity)" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
