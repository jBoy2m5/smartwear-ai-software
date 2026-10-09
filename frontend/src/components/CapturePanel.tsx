import { useEffect, useRef, useState } from 'react';
import { Camera, CircleStop, Play, RotateCw } from 'lucide-react';
import { LearningExperimentPanel } from './LearningExperimentPanel';
import { backendUrl, getCapturePreview, getCaptureStatus, getDeviceHealth, startCapture, stopCapture, listProcedures, listReferences } from '../backendApi';
import type { Procedure, ExpertReference, CaptureContext } from '../backendApi';
import type { CapturePreview, CaptureStatus, DeviceHealth } from '../backendApi';

const ACTIVE = new Set(['starting', 'recording', 'stopping', 'processing', 'publishing']);
const PREVIEW = new Set(['starting', 'recording', 'stopping']);
const FINGERS = [[0, 1, 2, 3, 4], [0, 5, 6, 7, 8], [0, 9, 10, 11, 12],
  [0, 13, 14, 15, 16], [0, 17, 18, 19, 20]];
type DisplayFrame = CapturePreview & { url: string };

export function CapturePanel({ onCompleted }: { onCompleted: (sessionId: string) => void }) {
  const [job, setJob] = useState<CaptureStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [displayFrame, setDisplayFrame] = useState<DisplayFrame | null>(null);
  const [health, setHealth] = useState<DeviceHealth | null>(null);
  const [healthError, setHealthError] = useState('');
  const [clock, setClock] = useState(0);
  const previewSeenAt = useRef(0);
  const notified = useRef<string | null>(null);
  const imageUrls = useRef<string[]>([]);
  const jobId = job?.job_id;
  const stage = job?.stage;
  const [procedures, setProcedures] = useState<Procedure[]>([]);
  const [taskKey, setTaskKey] = useState('LOG_KIT:1');
  const [role, setRole] = useState<'expert' | 'worker' | 'demo'>('expert');
  const [participant, setParticipant] = useState('');
  const [consent, setConsent] = useState(false);
  const [references, setReferences] = useState<ExpertReference[]>([]);
  const [reference, setReference] = useState('');
  const [trialStage, setTrialStage] = useState<'before_learning' | 'after_learning' | 'practice'>('before_learning');
  const task = procedures.find(p => `${p.task_id}:${p.version}` === taskKey);

  useEffect(() => {
    const controller = new AbortController();
    let timer: number | undefined;
    const update = async () => {
      try {
        if (!document.hidden) {
          const current = await getDeviceHealth(controller.signal);
          if (!controller.signal.aborted) { setHealth(current); setHealthError(''); }
        }
      } catch (reason) { if (!controller.signal.aborted) { setHealth(null); setHealthError(String(reason)); } }
      finally { if (!controller.signal.aborted) timer = window.setTimeout(() => void update(), 5000); }
    };
    void update();
    return () => { controller.abort(); if (timer) window.clearTimeout(timer); };
  }, [stage]);

  useEffect(() => {
    if (stage !== 'recording') return;
    const timer = window.setInterval(() => setClock(performance.now()), 500);
    return () => window.clearInterval(timer);
  }, [stage]);

  useEffect(() => { void listProcedures().then(setProcedures).catch(reason => setError(String(reason))); }, []);
  useEffect(() => {
    let active = true;
    setReference(''); setReferences([]);
    if (task) void listReferences(task.task_id, task.version).then(items => { if (active) setReferences(items); }).catch(reason => { if (active) setError(String(reason)); });
    return () => { active = false; };
  }, [task]);

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
    let timer: number | undefined;
    const poll = async () => {
      await update();
      if (!controller.signal.aborted) timer = window.setTimeout(() => void poll(), document.hidden ? 2000 : 700);
    };
    void poll();
    return () => { controller.abort(); if (timer) window.clearTimeout(timer); };
  }, [jobId, stage]);

  useEffect(() => {
    if (!jobId || !stage || !PREVIEW.has(stage)) return;
    const controller = new AbortController();
    let timer: number | undefined;
    let lastFrame = -1;
    const update = async () => {
      try {
        if (document.hidden) return;
        const requested = performance.now();
        const preview = await getCapturePreview(jobId, controller.signal);
        if (preview.frame_index !== lastFrame) {
          const url = backendUrl(`/api/v1/capture/${jobId}/frame?index=${preview.frame_index}`);
          if (!url) return;
          const response = await fetch(url, { signal: controller.signal, cache: 'no-store' });
          if (!response.ok) throw new Error(`Preview HTTP ${response.status}`);
          const imageUrl = URL.createObjectURL(await response.blob());
          if (controller.signal.aborted) { URL.revokeObjectURL(imageUrl); return; }
          lastFrame = preview.frame_index;
          imageUrls.current.push(imageUrl);
          if (imageUrls.current.length > 3) URL.revokeObjectURL(imageUrls.current.shift()!);
          setDisplayFrame({ ...preview, url: imageUrl });
          previewSeenAt.current = requested;
        }
      } catch {
        // No preview exists until the camera has captured its first frame.
      } finally {
        if (!controller.signal.aborted) timer = window.setTimeout(() => void update(), document.hidden ? 1000 : 100);
      }
    };
    void update();
    return () => { controller.abort(); if (timer) window.clearTimeout(timer); };
  }, [jobId, stage]);

  useEffect(() => () => {
    imageUrls.current.forEach(url => URL.revokeObjectURL(url));
    imageUrls.current = [];
  }, []);

  useEffect(() => {
    if (job?.stage === 'completed' && job.session_id && notified.current !== job.job_id) {
      notified.current = job.job_id;
      window.sessionStorage.removeItem('smartwear_capture_job');
      onCompleted(job.session_id);
    }
  }, [job, onCompleted]);

  const begin = async (captureMode: 'hardware' | 'demo') => {
    setBusy(true); setError(null); setDisplayFrame(null);
    try {
      if (captureMode === 'demo' && role !== 'demo') throw new Error('Chọn chế độ thử DEMO để dùng webcam mô phỏng.');
      if (role !== 'demo' && (!task || !participant.trim() || !consent || (role === 'worker' && !reference))) {
        throw new Error('Chọn công đoạn, người thao tác, đồng ý ghi hình và mẫu chuyên gia đã duyệt (nếu quay học viên).');
      }
      const context: CaptureContext = { role, task_id: role === 'demo' ? null : task!.task_id,
        procedure_version: role === 'demo' ? null : task!.version,
        reference_session_id: role === 'worker' ? reference : null,
        participant_id: participant.trim(), consent_confirmed: consent, purpose: 'training_demo',
        trial_stage: role === 'expert' ? 'reference' : role === 'demo' ? 'technical' : trialStage };
      const created = await startCapture(captureMode, context);
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
  const width = displayFrame?.camera.frame_width ?? 640;
  const height = displayFrame?.camera.frame_height ?? 480;
  const frameAge = displayFrame ? (displayFrame.frame_age_ms ?? displayFrame.preview_age_ms ?? 0)
    + Math.max(0, clock-previewSeenAt.current) : null;
  const stale = recording && (frameAge === null || frameAge > 2000);
  const hands = (['left', 'right'] as const).map(side => {
    const landmarks = displayFrame?.[`${side}_landmarks`] ?? [];
    const action = displayFrame?.[`${side}_action`];
    const points = new Map(landmarks.map(point => [point.id, point]));
    return { side, landmarks, points, wrist: points.get(0),
      title: side === 'left' ? 'Tay trái' : 'Tay phải',
      color: side === 'left' ? '#fbbf24' : '#22d3ee',
      label: job?.stage === 'failed' ? 'PHIÊN ĐÃ DỪNG' : stale ? 'CHƯA CÓ ẢNH MỚI'
        : !action ? 'CHƯA CÓ DỮ LIỆU' : action.tracking_status === 'ambiguous' ? 'KHÔNG RÕ'
        : action.tracking_status === 'missing' ? 'KHÔNG THẤY TAY' : action.label };
  });

  return <section className="overflow-hidden rounded-xl border border-cyberGreen/30 bg-panelBg shadow-lg">
    <div className="grid gap-3 border-b border-slate-700 p-4 md:grid-cols-2">
      <label className="text-sm">Mục đích phiên
        <select value={role} disabled={Boolean(working)} onChange={event => setRole(event.target.value as typeof role)} className="mt-1 w-full rounded bg-slate-900 p-2">
          <option value="expert">Ghi mẫu người hướng dẫn / chuyên gia</option><option value="worker">Người học — so với mẫu đã duyệt</option><option value="demo">Thử pipeline với mẫu DEMO (không phải expert thật)</option>
        </select>
      </label>
      <label className="text-sm">Công đoạn / phiên bản
        <select value={taskKey} disabled={Boolean(working)} onChange={event => setTaskKey(event.target.value)} className="mt-1 w-full rounded bg-slate-900 p-2">
          {procedures.map(p => <option key={`${p.task_id}:${p.version}`} value={`${p.task_id}:${p.version}`}>{p.department} · {p.title} · v{p.version}</option>)}
        </select>
      </label>
      {role === 'worker' && <label className="text-sm">Mẫu đã duyệt cùng công đoạn
        <select value={reference} disabled={Boolean(working)} onChange={event => setReference(event.target.value)} className="mt-1 w-full rounded bg-slate-900 p-2">
          <option value="">Chọn mẫu chuyên gia</option>{references.map(item => <option key={item.session_id} value={item.session_id}>{item.context.participant_id} · {item.session_id} · duyệt bởi {item.reviewer}</option>)}
        </select>{references.length === 0 && <span className="text-xs text-amber-200">Chưa có mẫu được duyệt; ghi và duyệt mẫu trước.</span>}
      </label>}
      <label className="text-sm">Mã người thao tác (dùng bí danh)
        <input value={participant} disabled={Boolean(working)} onChange={event => setParticipant(event.target.value)} className="mt-1 w-full rounded bg-slate-900 p-2" />
      </label>
      {role === 'worker' && <label className="text-sm">Lượt thực nghiệm<select value={trialStage} disabled={Boolean(working)} onChange={event => setTrialStage(event.target.value as typeof trialStage)} className="mt-1 w-full rounded bg-slate-900 p-2"><option value="before_learning">Trước khi học SOP</option><option value="after_learning">Sau khi học SOP</option><option value="practice">Luyện tập</option></select></label>}
      <label className="text-sm"><input type="checkbox" checked={consent} disabled={Boolean(working)} onChange={event => setConsent(event.target.checked)} /> Người thao tác đồng ý ghi hình cho bài thực hành này.</label>
      {task && <p className="text-xs text-gray-400">Tiêu chí bài mẫu: {task.success_criteria} · SOP chỉ là nháp trước khi người hướng dẫn duyệt.</p>}
    </div>
    <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-700/60 p-4">
      <div className="flex items-center gap-3"><div className="rounded-lg bg-cyberGreen/10 p-2 text-cyberGreen"><Camera size={22} /></div>
        <div><h2 className="font-heading text-lg font-bold">Quay và phân tích ngay trên trang</h2>
          <p className="text-xs text-gray-400">{job?.capture_mode === 'demo'
            ? 'Nguồn phiên này: webcam máy AI + cảm biến DEMO; không dùng phần cứng'
            : job && !job.capture_mode ? 'Nguồn phiên cũ: chưa xác định'
              : 'Chọn quay ESP32 + SmartWrist hoặc webcam máy AI (DEMO)'} · nhận diện riêng tay trái và tay phải</p></div></div>
      <div className="flex flex-wrap gap-2">
        <button type="button" onClick={() => void begin('hardware')} disabled={busy || Boolean(working) || !health?.can_start}
          className="inline-flex items-center gap-2 rounded-lg bg-cyberGreen px-4 py-2 font-bold text-densoNavy disabled:cursor-not-allowed disabled:opacity-40">
          <Play size={17} />Quay ESP32 + vòng tay</button>
        <button type="button" onClick={() => void begin('demo')} disabled={busy || Boolean(working)}
          className="inline-flex items-center gap-2 rounded-lg border border-cyan-400/60 bg-cyan-400/10 px-4 py-2 font-bold text-cyan-200 disabled:cursor-not-allowed disabled:opacity-40">
          <Camera size={17} />Quay webcam (DEMO)</button>
        <button type="button" onClick={() => void end()} disabled={busy || !job || !['starting', 'recording'].includes(job.stage)}
          className="inline-flex items-center gap-2 rounded-lg border border-alertRed/60 bg-alertRed/15 px-4 py-2 font-bold text-red-200 disabled:cursor-not-allowed disabled:opacity-40">
          <CircleStop size={17} />Kết thúc</button>
      </div>
    </div>
    <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(260px,1fr)]">
      <div className="relative flex aspect-video items-center justify-center overflow-hidden rounded-lg border border-slate-700 bg-slate-950">
        {displayFrame ? <div className="relative shrink-0 overflow-hidden" style={{ height: `min(100%, ${height}px)`, aspectRatio: `${width} / ${height}`, maxWidth: '100%' }}>
          <img src={displayFrame.url} alt="Hình camera tay trái và tay phải" className="h-full w-full object-fill" />
          <svg className="pointer-events-none absolute inset-0 h-full w-full" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
            {hands.map(hand => <g key={hand.side}>
              {FINGERS.map((finger, index) => <polyline key={index} points={finger.map(id => hand.points.get(id)).filter(point => point != null).map(point => `${point!.x * width},${point!.y * height}`).join(' ')}
                fill="none" stroke={hand.color} strokeWidth="2" strokeOpacity="0.85" />)}
              {hand.landmarks.map(point => <circle key={point.id} cx={point.x * width} cy={point.y * height}
                r="3" fill={hand.color} stroke="#082f49" strokeWidth="1" />)}
              {hand.wrist && <text x={Math.max(4, Math.min(width - 64, hand.wrist.x * width))}
                y={Math.max(14, Math.min(height - 4, hand.wrist.y * height - 10))}
                fill={hand.color} stroke="#020617" strokeWidth="2" paintOrder="stroke"
                fontSize="13" fontWeight="bold">{hand.title}</text>}
            </g>)}
          </svg>
        </div> : <div className="px-4 text-center text-sm text-gray-400">{job ? 'Đang nhận hình camera...' : 'Chọn một trong hai nút quay để xem hình và nhãn hành động.'}</div>}
        {recording && !stale && <span className="absolute right-3 top-3 rounded bg-alertRed px-2 py-1 text-xs font-bold text-white">● LIVE</span>}
        {stale && <span className="absolute bottom-3 rounded bg-amber-950 px-3 py-1 text-xs text-amber-100">Chưa có ảnh mới — kiểm tra kết nối camera</span>}
      </div>
      <div className="flex flex-col justify-center rounded-lg border border-slate-700 bg-slate-900/60 p-4">
        <div className="flex items-center gap-2 text-sm font-bold text-cyberGreen">
          {working && <RotateCw className="animate-spin" size={17} />}
          {job ? ({ starting: 'Đang mở camera', recording: 'Đang quay', stopping: 'Đang dừng',
            processing: 'Đang phân tích', publishing: 'Đang lưu kết quả',
            completed: 'Đã hoàn tất', failed: 'Có lỗi' }[job.stage]) : !health ? 'Đang kiểm tra thiết bị'
              : health.can_start ? 'Có thể bắt đầu kết nối camera' : 'Thiết bị chưa sẵn sàng'}</div>
        <p className="mt-2 text-sm text-gray-300">{job?.message ?? health?.camera.message ?? 'Đang kiểm tra camera, broker và đồng hồ.'}</p>
        <div className="mt-3 space-y-1 rounded border border-slate-700 p-2 text-xs">
          <p>SmartCap: {health?.camera.message ?? 'Chưa kiểm tra'}</p>
          <p>MQTT: {health?.mqtt.message ?? 'Chưa kiểm tra'} · NTP: {health ? health.ntp.ok ? 'phản hồi' : 'không phản hồi' : 'chưa kiểm tra'}</p>
          {health?.camera.board && <p>Bo đã chạy {(health.camera.board.uptime_ms/1000).toFixed(0)} s · lần reset: {health.camera.board.reset_reason} · Wi-Fi {health.camera.board.wifi_rssi} dBm</p>}
          {healthError && <p className="text-amber-200">Không đọc được trạng thái thiết bị: {healthError}</p>}
          <button disabled={Boolean(working)} className="underline disabled:opacity-40" onClick={() => {
            void getDeviceHealth(undefined, true).then(value => { setHealth(value); setHealthError(''); }).catch(reason => setHealthError(String(reason)));
          }}>Kiểm tra lại thiết bị</button>
        </div>
        {displayFrame && <div className="mt-3 grid grid-cols-2 gap-2">
          {hands.map(hand => <div key={hand.side} className="rounded border border-slate-700 bg-slate-950/60 p-2">
            <div className="text-sm font-bold" style={{ color: hand.color }}>{hand.title}</div>
            <div className="mt-1 text-xs font-semibold text-gray-200">{hand.label}</div>
            {hand.wrist && <div className="mt-1 font-mono text-xs text-gray-400">X {hand.wrist.x.toFixed(3)} · Y {hand.wrist.y.toFixed(3)}</div>}
          </div>)}
        </div>}
        {displayFrame?.wrist_status && recording && !stale && <p className={`mt-3 text-sm ${displayFrame.wrist_status === 'receiving' ? 'text-cyberGreen' : 'text-amber-300'}`}>
          SmartWrist (tay phải): {displayFrame.wrist_status === 'receiving' ? 'đang nhận dữ liệu' : 'chưa có dữ liệu'}
        </p>}
        {displayFrame?.live_alignment && recording && !stale && <div className="mt-3 text-sm text-gray-300">
          <p>Ghép camera/vòng tay: {displayFrame.live_alignment.sensor_status === 'matched'
            ? `lệch ${displayFrame.live_alignment.delta_ms} ms` : 'thiếu mẫu phù hợp'}</p>
          {displayFrame.wrist_sample && <p className="mt-1 font-mono text-xs">
            FSR ADC: {displayFrame.wrist_sample.force.join(' · ')}
          </p>}
          {displayFrame.wrist_sample && <p className={`mt-1 text-xs ${displayFrame.wrist_sample.acc === null ? 'text-amber-300' : 'text-gray-300'}`}>
            {displayFrame.wrist_sample.acc === null ? 'IMU chưa kết nối — chỉ đang nhận ADC; kiểm tra MPU6050 và dây SDA/SCL.'
              : `IMU: acc ${displayFrame.wrist_sample.acc.map(value => value.toFixed(2)).join(' · ')} / gyro ${displayFrame.wrist_sample.gyro?.map(value => value.toFixed(2)).join(' · ')}`}
          </p>}
        </div>}
        {displayFrame?.performance && recording && !stale && <p className="mt-2 text-xs text-gray-400">AI p95 {displayFrame.performance.stages.inference?.p95_ms.toFixed(1) ?? '—'} ms · tuổi ảnh {frameAge?.toFixed(0)} ms</p>}
        {job?.stage === 'completed' && <p className="mt-3 text-sm text-cyberGreen">Kết quả đã tự mở ở phía dưới.</p>}
        {job?.stage === 'failed' && <p className="mt-3 text-sm text-red-200">Nếu camera đã ghi được dữ liệu, các file vẫn được giữ trên máy. Báo người quản trị kiểm tra lỗi rồi thử lại.</p>}
        {error && <p role="alert" className="mt-3 text-sm text-red-200">{error}</p>}
        <p className="mt-4 text-xs text-gray-500">Quay tối đa 3 phút. Phiên phần cứng lưu bốn kênh ADC đo từ vòng tay; phiên DEMO dùng số mô phỏng.</p>
      </div>
    </div>
    <LearningExperimentPanel />
  </section>;
}
