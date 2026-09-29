import React, { useEffect, useRef } from 'react';
import type { HandLandmark } from '../MockDataEngine';

export default function FPVOverlay({ landmarks }: { landmarks: HandLandmark[] }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear previous drawing
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Set styles
    ctx.fillStyle = '#00E676';
    ctx.strokeStyle = '#00E676';
    ctx.lineWidth = 2;

    // Draw nodes
    landmarks.forEach(lm => {
      const x = lm.x * canvas.width;
      const y = lm.y * canvas.height;
      ctx.beginPath();
      ctx.arc(x, y, 4, 0, 2 * Math.PI);
      ctx.fill();
    });

    // Draw edges (mocking connections for a hand skeleton)
    // Connecting some points to simulate a basic hand structure
    const connections = [
      [0,1], [1,2], [2,3], [3,4], // Thumb
      [0,5], [5,6], [6,7], [7,8], // Index
      [0,9], [9,10], [10,11], [11,12], // Middle
      [0,13], [13,14], [14,15], [15,16], // Ring
      [0,17], [17,18], [18,19], [19,20], // Pinky
      [5,9], [9,13], [13,17] // Palm connections
    ];

    ctx.beginPath();
    connections.forEach(([i, j]) => {
      if (landmarks[i] && landmarks[j]) {
        const x1 = landmarks[i].x * canvas.width;
        const y1 = landmarks[i].y * canvas.height;
        const x2 = landmarks[j].x * canvas.width;
        const y2 = landmarks[j].y * canvas.height;
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2, y2);
      }
    });
    ctx.stroke();
  }, [landmarks]);

  return (
    <div className="w-full h-full relative bg-slate-900 flex items-center justify-center overflow-hidden">
      {/* Top Overlay Gradient */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/40 z-10 pointer-events-none flex flex-col justify-between p-6">
        <div className="flex justify-between items-start">
          <div className="flex items-center gap-2 bg-black/50 px-3 py-1.5 rounded text-white font-mono text-sm border border-slate-700">
            <div className="w-2 h-2 rounded-full bg-red-500 animate-pulse"></div>
            REC FPV
          </div>
          <div className="text-white font-mono text-xs opacity-50 bg-black/50 px-2 py-1 rounded">
            ESP32-CAM 640x480 @ 30FPS
          </div>
        </div>
        
        <div className="flex justify-between items-end">
          <div className="text-cyberGreen font-mono text-xs bg-black/50 px-2 py-1 rounded border border-cyberGreen/30">
            [AI TRACKING ACTIVE] MediaPipe 3D
          </div>
        </div>
      </div>
      
      {/* Dummy Video Background Pattern */}
      <div className="absolute inset-0 opacity-20 pointer-events-none" 
           style={{ backgroundImage: 'radial-gradient(circle, #334155 1px, transparent 1px)', backgroundSize: '20px 20px' }}>
      </div>

      <div className="w-full h-full bg-slate-800 flex items-center justify-center relative">
         <div className="absolute inset-0 bg-gradient-to-br from-slate-800 to-slate-900 mix-blend-overlay"></div>
         <span className="text-slate-600 font-bold text-2xl tracking-widest z-0 opacity-50 select-none">CAMERA FEED</span>
      </div>

      <canvas
        ref={canvasRef}
        width={800}
        height={600}
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-[800px] h-auto object-contain pointer-events-none z-20"
        style={{ filter: 'drop-shadow(0 0 4px rgba(0,230,118,0.5))' }}
      />
    </div>
  );
}
