import React from 'react';
import { FileText, FileCode, CheckCircle, Clock, Zap } from 'lucide-react';

export default function AutoSopGenerator() {
  const mockSteps = [
    {
      id: 1,
      image: "https://images.unsplash.com/photo-1581092580497-e0d23cbdf1dc?auto=format&fit=crop&w=300&q=80",
      name: "Lắp ráp & Cố định vỏ bảo vệ",
      time: "14.2s",
      force: "18.5 N",
      kankotsu: "Giữ tay góc 45 độ, nhấn lực đều tay xuống vỏ để khớp lẫy trước khi vặn ốc."
    },
    {
      id: 2,
      image: "https://images.unsplash.com/photo-1581092160562-40aa08e78837?auto=format&fit=crop&w=300&q=80",
      name: "Siết ốc cụm van tiết lưu",
      time: "6.8s",
      force: "12.0 N",
      kankotsu: "Mô-men xoắn vừa đủ, nhả ngón cái ngay khi súng bắn vít dừng."
    }
  ];

  return (
    <div className="bg-panelBg rounded-xl p-5 md:p-6 border border-slate-700/50 flex flex-col h-full shadow-lg">
      <div className="flex items-center gap-3 mb-6 shrink-0">
        <div className="w-1.5 h-6 bg-cyberGreen rounded-full"></div>
        <h2 className="text-lg md:text-xl font-bold text-white uppercase tracking-wider font-heading">Auto Digital SOP Studio</h2>
      </div>

      <div className="flex-1 overflow-y-auto pr-2 space-y-4 mb-6">
        {mockSteps.map((step) => (
          <div key={step.id} className="flex flex-col md:flex-row gap-4 bg-slate-800/50 p-4 rounded-lg border border-slate-700 hover:border-cyberGreen/30 transition-colors group">
            <div className="w-full md:w-32 h-32 md:h-24 rounded-md overflow-hidden shrink-0 border border-slate-600">
              <img src={step.image} alt={step.name} className="w-full h-full object-cover grayscale group-hover:grayscale-0 transition-all duration-500" />
            </div>
            <div className="flex flex-col flex-1 justify-center">
              <h3 className="text-white font-bold font-heading text-base md:text-lg flex items-center gap-2">
                <span className="text-cyberGreen text-sm">#{step.id}</span> {step.name}
              </h3>
              <div className="flex items-center gap-4 mt-2">
                <div className="flex items-center gap-1.5 text-slate-400">
                  <Clock className="w-4 h-4" />
                  <span className="text-xs md:text-sm font-mono">{step.time}</span>
                </div>
                <div className="flex items-center gap-1.5 text-slate-400">
                  <Zap className="w-4 h-4 text-amber-400" />
                  <span className="text-xs md:text-sm font-mono">{step.force}</span>
                </div>
              </div>
              <div className="mt-3 bg-densoNavy/20 border border-densoNavy/50 p-2.5 rounded-md">
                <p className="text-xs text-slate-300 flex items-start gap-2">
                  <CheckCircle className="w-4 h-4 text-cyberGreen shrink-0 mt-0.5" />
                  <span className="font-body leading-relaxed"><strong>Kankotsu:</strong> {step.kankotsu}</span>
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-auto shrink-0">
        <button className="flex items-center justify-center gap-2 bg-slate-800 border border-slate-600 text-white py-3 px-4 rounded-lg font-bold hover:border-cyberGreen hover:text-cyberGreen hover:shadow-[0_0_15px_rgba(0,230,118,0.2)] transition-all group">
          <FileText className="w-5 h-5 text-gray-400 group-hover:text-cyberGreen transition-colors" />
          <span className="text-sm">Xuất file SOP (PDF)</span>
        </button>
        <button className="flex items-center justify-center gap-2 bg-slate-800 border border-slate-600 text-white py-3 px-4 rounded-lg font-bold hover:border-cyberGreen hover:text-cyberGreen hover:shadow-[0_0_15px_rgba(0,230,118,0.2)] transition-all group">
          <FileCode className="w-5 h-5 text-gray-400 group-hover:text-cyberGreen transition-colors" />
          <span className="text-sm">Xuất HTML Tương tác</span>
        </button>
      </div>
    </div>
  );
}
