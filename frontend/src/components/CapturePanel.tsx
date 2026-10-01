import { useEffect, useRef, useState } from 'react';
import { Camera, CircleStop, Play, RotateCw } from 'lucide-react';
import { backendUrl, getCaptureStatus, startCapture, stopCapture } from '../backendApi';
import type { CaptureStatus } from '../backendApi';

const ACTIVE = new Set(['starting', 'recording', 'stopping', 'processing', 'publishing']);

export function CapturePanel({ onCompleted }: { onCompleted: (sessionId: string) => void }) {
  const [job, setJob] = useState<CaptureStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [frameTick, setFrameTick] = useState(0);
  const [frameReady, setFrameReady] = useState(false);
  const notified = useRef<string | null>(null);
  const jobId = job?.job_id;
  const stage = job?.stage;

  useEffect(() => {
    const saved = window.sessionStorage.getItem('smartwear_capture_job');
    if (saved && /^[0-9a-f]{32}$/.test(saved)) {
      void getCaptureStatus(saved).then(setJob).catch(() => {
        window.sessionStorage.removeItem('smartwear_capture_job');
      });
    }
  }, []);

  useEffect(() => {
    if (!jobId || !stage || !ACTIVE.has(stage)) return;
    const controller = new AbortController();
    const update = async () => {
      try {
        const current = await getCaptureStatus(jobId, controller.signal);
        if (!controller.signal.aborted) setJob(current);
      } catch (reason) {
        if (!controller.signal.aborted) setError(reason instanceof Error ? reason.message : 'Không đọc được trạng thái camera');
      }
    };
    const timer = window.setInterval(() => void update(), 700);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [jobId, stage]);

  useEffect(() => {
    if (stage !== 'recording') return;
    const timer = window.setInterval(() => setFrameTick(value => value + 1), 100);
    return () => window.clearInterval(timer);
  }, [jobId, stage]);

  useEffect(() => {
    if (job?.stage === 'completed' && job.session_id && notified.current !== job.job_id) {
      notified.current = job.job_id;
      window.sessionStorage.removeItem('smartwear_capture_job');
      onCompleted(job.session_id);
    }
  }, [job, onCompleted]);

  const begin = async () => {
    setBusy(true); setError(null); setFrameReady(false);
    try {
      const created = await startCapture();
      notified.current = null;
      window.sessionStorage.setItem('smartwear_capture_job', created.job_id);
      setJob(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không mở được camera');
    } finally { setBusy(false); }
  };

  const end = async () => {
    if (!job) return;
    setBusy(true); setError(null);
    try {
      await stopCapture(job.job_id);
      setJob(current => current ? { ...current, stage: 'stopping', message: 'Đang kết thúc quay...' } : current);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'Không dừng được camera');
    } finally { setBusy(false); }
  };

  const recording = job?.stage === 'recording';
  const working = job && ACTIVE.has(job.stage);
  const frameUrl = job ? backendUrl(`/api/v1/capture/${job.job_id}/frame?t=${frameTick}`) ?? undefined : undefined;

  return <section className="overflow-hidden rounded-xl border border-cyberGreen/30 bg-panelBg shadow-lg">
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-700/60 p-4">
      <div className="flex items-center gap-3"><div className="rounded-lg bg-cyberGreen/10 p-2 text-cyberGreen"><Camera size={22} /></div>
        <div><h2 className="font-heading text-lg font-bold">Quay và phân tích ngay trên trang</h2>
          <p className="text-xs text-gray-400">Camera trên máy chạy AI · nhận diện hai tay · tự lưu sau khi kết thúc</p></div></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void begin()} disabled={busy || Boolean(working)}
          className="inline-flex items-center gap-2 rounded-lg bg-cyberGreen px-4 py-2 font-bold text-densoNavy disabled:cursor-not-allowed disabled:opacity-40">
          <Play size={17} />Bắt đầu quay</button>
        <button type="button" onClick={() => void end()} disabled={busy || !job || !['starting', 'recording'].includes(job.stage)}
          className="inline-flex items-center gap-2 rounded-lg border border-alertRed/60 bg-alertRed/15 px-4 py-2 font-bold text-red-200 disabled:cursor-not-allowed disabled:opacity-40">
          <CircleStop size={17} />Kết thúc</button>
      </div>
    </div>
    <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,1fr)]">
      <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
        {job && ['starting', 'recording', 'stopping', 'processing', 'publishing', 'completed'].includes(job.stage) &&
          <img src={frameUrl} alt="Hình camera với nhãn tay trái và tay phải"
            onLoad={() => setFrameReady(true)} onError={() => setFrameReady(false)}
            className={`h-full w-full object-contain ${frameReady ? '' : 'hidden'}`} />}
        {!frameReady && <div className="px-4 text-center text-sm text-gray-400">{job ? 'Đang nhận hình camera...' : 'Bấm “Bắt đầu quay” để xem camera và nhãn hành động.'}</div>}
        {recording && <span className="absolute left-3 top-3 rounded bg-alertRed px-2 py-1 text-xs font-bold text-white">● LIVE</span>}
      </div>
      <div className="flex flex-col justify-center rounded-lg border border-slate-700 bg-slate-900/60 p-4">
        <div className="flex items-center gap-2 text-sm font-bold text-cyberGreen">
          {working && <RotateCw className="animate-spin" size={17} />}
          {job ? ({ starting: 'Đang mở camera', recording: 'Đang quay', stopping: 'Đang dừng',
            processing: 'Đang phân tích', publishing: 'Đang lưu kết quả',
            completed: 'Đã hoàn tất', failed: 'Có lỗi' }[job.stage]) : 'Sẵn sàng'}</div>
        <p className="mt-2 text-sm text-gray-300">{job?.message ?? 'Đưa tay vào vùng camera rồi bấm Bắt đầu quay.'}</p>
        {job?.stage === 'completed' && <p className="mt-3 text-sm text-cyberGreen">Kết quả đã tự mở ở phía dưới.</p>}
        {job?.stage === 'failed' && <p className="mt-3 text-sm text-red-200">Nếu camera đã ghi được dữ liệu, các file vẫn được giữ trên máy. Báo người quản trị kiểm tra lỗi rồi thử lại.</p>}
        {error && <p role="alert" className="mt-3 text-sm text-red-200">{error}</p>}
        <p className="mt-4 text-xs text-gray-500">Quay tối đa 3 phút. Số lực và đường đi trong kết quả vẫn là dữ liệu DEMO.</p>
      </div>
    </div>
  </section>;
}
