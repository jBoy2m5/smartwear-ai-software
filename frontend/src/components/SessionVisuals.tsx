import { Activity, ArrowUpRight, Camera } from 'lucide-react';
import { Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis } from 'recharts';
import { imageUrl, number } from '../presentation';
import type { Focus } from '../presentation';
import type { SessionDetail } from '../sessionTypes';

function ImageFrame({ url, label }: { url: string | null; label: string }) {
  return <div className="min-w-0 flex-1 overflow-hidden rounded-xl border border-slate-700 bg-slate-900/80">
    <div className="flex items-center justify-between border-b border-slate-700 px-3 py-2 text-xs font-bold uppercase tracking-widest text-gray-300">
      <span>{label}</span>
      {url && <a href={url} target="_blank" rel="noreferrer" aria-label={`Mở ảnh ${label}`} className="text-cyberGreen"><ArrowUpRight size={16} /></a>}
    </div>
    <div className="flex aspect-video items-center justify-center bg-[#101923]">
      {url ? <img src={url} alt={`Ảnh ${label}`} className="h-full w-full object-contain" />
        : <span className="px-4 text-center text-sm text-gray-500">Chưa có ảnh cho đoạn này</span>}
    </div>
  </div>;
}

export function ImageViewer({ detail, focus, setFocus }: {
  detail: SessionDetail; focus: Focus; setFocus: (focus: Focus) => void;
}) {
  return <section className="overflow-hidden rounded-xl border border-slate-700/60 bg-panelBg shadow-lg">
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-700/60 p-4">
      <div className="flex items-center gap-3"><div className="rounded-lg bg-cyberGreen/10 p-2 text-cyberGreen"><Camera size={21} /></div>
        <div><h2 className="font-heading text-lg font-bold">Hình ảnh đối chiếu</h2>
          <p className="text-xs text-gray-400">Ảnh từ phiên đã quay · {focus.title}</p></div></div>
      <span className="rounded border border-slate-600 px-2 py-1 text-xs text-gray-400">KEYFRAME · KHÔNG PHẢI CAMERA LIVE</span>
    </div>
    <div className="flex flex-col gap-3 p-4 sm:flex-row">
      <ImageFrame url={imageUrl(detail, 'expert', focus.expertPath)} label="Mẫu" />
      <ImageFrame url={imageUrl(detail, 'worker', focus.workerPath)} label="Phiên của bạn" />
    </div>
    <details className="border-t border-slate-700/60 px-4 py-3 text-sm">
      <summary className="cursor-pointer text-gray-300">Xem tất cả {detail.key_frames.length} ảnh của phiên quay</summary>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {detail.key_frames.map(filename => {
          const relative = `keyframes/${filename}`;
          const url = imageUrl(detail, 'worker', relative);
          return <button key={filename} type="button"
            onClick={() => setFocus({ sessionId: detail.session_id, title: filename, workerPath: relative })}
            className="rounded-lg border border-slate-700 bg-slate-900 p-1 text-left hover:border-cyberGreen/60">
            {url && <img src={url} alt={filename} loading="lazy" className="aspect-video w-full rounded object-cover" />}
            <span className="block truncate px-1 py-1 text-[10px] text-gray-400" title={filename}>{filename}</span>
          </button>;
        })}
      </div>
    </details>
  </section>;
}

export function SessionCharts({ detail }: { detail: SessionDetail }) {
  const points = detail.robot_trajectory_points.map(item => ({
    time: number(item.t, 1), force: item.force, x: item.pos[0], y: item.pos[1],
  }));
  return <section className="rounded-xl border border-slate-700/60 bg-panelBg p-4 shadow-lg">
    <div className="mb-4 flex items-center gap-2"><Activity className="text-cyberGreen" size={20} />
      <div><h2 className="font-heading text-lg font-bold">Tín hiệu của phiên</h2>
        <p className="text-xs text-gray-400">Dữ liệu đã lưu, không phải cảm biến truyền trực tiếp</p></div></div>
    {points.length ? <div className="space-y-5">
      <div><div className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">Lực DEMO · không phải Newton đo thật</div>
        <div className="h-44 rounded-lg bg-slate-800/70 p-2"><ResponsiveContainer width="100%" height="100%">
          <AreaChart data={points}><defs><linearGradient id="forceFill" x1="0" x2="0" y1="0" y2="1"><stop offset="5%" stopColor="#00E676" stopOpacity={0.35} /><stop offset="95%" stopColor="#00E676" stopOpacity={0} /></linearGradient></defs>
            <CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" stroke="#94a3b8" tick={{ fontSize: 10 }} />
            <YAxis stroke="#94a3b8" tick={{ fontSize: 10 }} width={28} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
            <Area type="monotone" dataKey="force" stroke="#00E676" fill="url(#forceFill)" isAnimationActive={false} />
          </AreaChart></ResponsiveContainer></div></div>
      <div><div className="mb-2 text-xs font-semibold uppercase tracking-wider text-gray-400">Vị trí cổ tay DEMO · X / Y</div>
        <div className="h-40 rounded-lg bg-slate-800/70 p-2"><ResponsiveContainer width="100%" height="100%">
          <LineChart data={points}><CartesianGrid stroke="#334155" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="time" stroke="#94a3b8" tick={{ fontSize: 10 }} />
            <YAxis stroke="#94a3b8" tick={{ fontSize: 10 }} width={35} />
            <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155' }} />
            <Line type="monotone" dataKey="x" stroke="#22D3EE" dot={false} isAnimationActive={false} />
            <Line type="monotone" dataKey="y" stroke="#fbbf24" dot={false} isAnimationActive={false} />
          </LineChart></ResponsiveContainer></div></div>
    </div> : <p className="rounded-lg bg-slate-800 p-5 text-sm text-gray-400">Phiên này chưa có điểm đường đi để vẽ.</p>}
  </section>;
}
