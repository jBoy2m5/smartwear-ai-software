import { useEffect, useRef, useState } from 'react';
import { backendUrl, getKnowledge, getQuality, saveKnowledge, generateProducts } from '../backendApi';
import type { SessionKnowledge, QualityReport, ProductManifest } from '../backendApi';
import type { SessionDetail } from '../sessionTypes';

export function KnowledgePanel({ detail }: { detail: SessionDetail }) {
  const [knowledge, setKnowledge] = useState<SessionKnowledge | null>(null);
  const [quality, setQuality] = useState<QualityReport | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [tab, setTab] = useState<'learner' | 'machine'>('learner');
  const [product, setProduct] = useState<ProductManifest | null>(null);
  const expertVideo = useRef<HTMLVideoElement>(null);
  const workerVideo = useRef<HTMLVideoElement>(null);
  useEffect(() => {
    let active = true; setKnowledge(null); setQuality(null); setError(''); setMessage(''); setProduct(null);
    void getKnowledge(detail.session_id).then(value => { if (active) setKnowledge(value); }).catch(reason => {
      if (active && String(reason).includes('HTTP 404')) setMessage('Phiên cũ chưa có task/version và SOP được duyệt. Hãy ghi mẫu mới bằng lựa chọn ở trên.');
      else if (active) setError(String(reason));
    });
    void getQuality(detail.session_id).then(value => { if (active) setQuality(value); }).catch(() => {});
    return () => { active = false; };
  }, [detail.session_id]);
  const save = async (status: SessionKnowledge['review_status']) => {
    if (!knowledge) return;
    setBusy(true); setError('');
    try { setKnowledge(await saveKnowledge(detail.session_id, { ...knowledge, review_status: status })); setMessage('Đã lưu phiên bản mới; lịch sử trước vẫn được giữ.'); }
    catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  };
  const generate = async () => {
    setBusy(true); setError('');
    try {
      const result = await generateProducts(detail.session_id);
      setProduct(result);
      setMessage(`${result.quality_state.learner_ready ? 'Gói đã duyệt' : 'Gói nháp'} · tạo trong ${(result.generation_elapsed_ms / 1000).toFixed(1)} s. ${result.quality_state.learner_reasons.join('; ')}`);
    } catch (reason) { setError(String(reason)); } finally { setBusy(false); }
  };
  const base = `/api/v1/knowledge/sessions/${encodeURIComponent(detail.session_id)}/products/`;
  const artifactUrl = (path: string) => product ? backendUrl(`${base}files/${path}?episode_id=${product.episode_id}`)! : '';
  return <section className="space-y-4 rounded-xl border border-slate-700 bg-panelBg p-4">
    <h2 className="font-heading text-lg font-bold">Kinh nghiệm chuyên gia và gói dữ liệu</h2>
    <div className="flex gap-3"><button onClick={() => setTab('learner')} className="rounded border p-2">Học thao tác</button><button onClick={() => setTab('machine')} className="rounded border p-2">Dữ liệu máy</button></div>
    {quality && <div className="rounded bg-slate-900 p-3 text-sm">
      <p>{quality.camera.frame_width}×{quality.camera.frame_height} · {quality.camera.fps_measured?.toFixed(2) ?? 'chưa rõ'} FPS · wrist {quality.wrist.device_rate_hz?.toFixed(2) ?? 'chưa rõ'} Hz · ghép {(quality.alignment.coverage * 100).toFixed(1)}%</p>
      <ul className="mt-2 list-disc pl-5 text-amber-200">{quality.warnings.map(w => <li key={w}>{w}</li>)}</ul>
    </div>}
    {knowledge && <>
      <p className="text-sm">{knowledge.context.role} · {knowledge.context.task_id} / v{knowledge.context.procedure_version} · {knowledge.review_status} · bản ghi chú {knowledge.revision}</p>
      <p className="break-all text-xs text-gray-400">Reference: {knowledge.context.reference_session_id ?? 'Phiên mẫu chưa so sánh'} · review revision {knowledge.reference_revision ?? '—'}</p>
      {tab === 'learner' && <>
        {product && <div className="space-y-2">
          <div className="grid gap-3 md:grid-cols-2">
            {product.artifacts.some(a => a.path === 'video/reference.mp4') && <div><h3>Mẫu chuyên gia đã chọn</h3><video ref={expertVideo} controls src={artifactUrl('video/reference.mp4')} className="w-full" /></div>}
            {product.artifacts.some(a => a.path === 'video/fpv.mp4') && <div><h3>{knowledge.context.role === 'worker' ? 'Phiên người học' : 'Phiên mẫu'}</h3><video ref={workerVideo} controls src={artifactUrl('video/fpv.mp4')} className="w-full" /></div>}
          </div>
          <div className="flex flex-wrap gap-2">{product.learner_steps.map(step => <button key={step.step_id} className="rounded border p-2 text-xs" onClick={() => {
            if (expertVideo.current && step.start_s !== null) expertVideo.current.currentTime = step.start_s - (product.video_timebase.reference_source_start_s ?? 0);
            const workerStep = product.worker_steps.find(s => s.step_id === step.step_id);
            if (workerVideo.current && workerStep?.start_s != null) workerVideo.current.currentTime = workerStep.start_s - product.video_timebase.source_start_s;
          }}>{step.step_id} · {step.title}</button>)}</div>
          <p className="text-xs text-gray-400">Hai video mở đúng mốc bước đã gán; thời lượng có thể khác nhau. Đánh giá lỗi do người hướng dẫn xác nhận.</p>
        </div>}
        {knowledge.steps.map((step, index) => <div key={step.step_id} className="space-y-2 rounded border border-slate-700 p-3">
          <h3 className="font-bold">{step.step_id} · {step.title}</h3>
          {(['instruction','why','tips','common_errors','safety','acceptable_variation'] as const).map((field, i) => <label key={field} className="block text-xs">{['Hướng dẫn','Vì sao / kinh nghiệm','Mẹo','Lỗi cần tránh','Khi nào dừng','Biến thể chấp nhận'][i]}
            <textarea value={step[field]} onChange={event => setKnowledge(current => current ? { ...current, steps: current.steps.map((s, j) => j === index ? { ...s, [field]: event.target.value } : s) } : current)} className="mt-1 w-full rounded bg-slate-950 p-2 text-sm" />
          </label>)}
          <div className="grid grid-cols-2 gap-2">{(['start_s','end_s'] as const).map(field => <label key={field} className="text-xs">{field === 'start_s' ? 'Bắt đầu thao tác (giây)' : 'Kết thúc thao tác (giây)'}
            <input type="number" min="0" step="0.01" value={step[field] ?? ''} onChange={event => setKnowledge(current => current ? { ...current, steps: current.steps.map((s, j) => j === index ? { ...s, [field]: event.target.value === '' ? null : Number(event.target.value) } : s) } : current)} className="mt-1 w-full rounded bg-slate-950 p-2" />
          </label>)}</div>
          <label className="block text-xs">Ảnh bằng chứng
            <select value={step.keyframe ?? ''} onChange={event => setKnowledge(current => current ? { ...current, steps: current.steps.map((s,j) => j === index ? { ...s, keyframe: event.target.value || null } : s) } : current)} className="mt-1 w-full rounded bg-slate-950 p-2"><option value="">Dùng mốc video</option>{detail.key_frames.map(name => <option key={name} value={name}>{name}</option>)}</select>
          </label>
        </div>)}
        <label className="block text-sm">Người duyệt<input value={knowledge.reviewer} onChange={event => setKnowledge({ ...knowledge, reviewer: event.target.value })} className="ml-2 rounded bg-slate-950 p-2" /></label>
        <label className="block text-sm">Lý do duyệt / tiêu chí đầu ra<textarea value={knowledge.review_rationale} onChange={event => setKnowledge({ ...knowledge, review_rationale: event.target.value })} className="w-full rounded bg-slate-950 p-2" /></label>
        <label className="block text-sm"><input type="checkbox" checked={knowledge.clarity_confirmed} onChange={event => setKnowledge({ ...knowledge, clarity_confirmed: event.target.checked })} /> Tôi đã xem video, kiểm tra mốc bước và xác nhận nhìn rõ thao tác.</label>
        <label className="block text-sm">Đầu ra do người đánh giá kiểm <select value={knowledge.outcome} onChange={event => setKnowledge({ ...knowledge, outcome: event.target.value as SessionKnowledge['outcome'] })} className="rounded bg-slate-950 p-2"><option value="unknown">Chưa đánh giá</option><option value="passed">Đạt</option><option value="failed">Chưa đạt</option></select></label>
        <label className="block text-sm">Số lần gợi ý miệng <input type="number" min="0" value={knowledge.prompt_count ?? ''} onChange={event => setKnowledge({ ...knowledge, prompt_count: event.target.value === '' ? null : Number(event.target.value) })} className="rounded bg-slate-950 p-2" /></label>
        <label className="block text-sm">Lỗi đã xác nhận<textarea value={knowledge.confirmed_errors} onChange={event => setKnowledge({ ...knowledge, confirmed_errors: event.target.value })} className="w-full rounded bg-slate-950 p-2" /></label>
        {knowledge.context.role === 'worker' && <div className="space-y-2 rounded border border-slate-700 p-3">
          <label className="block text-sm">Số lỗi người đánh giá đã xác nhận (ghi 0 khi không có)<input type="number" min="0" value={knowledge.confirmed_error_count ?? ''} onChange={event => setKnowledge({ ...knowledge, confirmed_error_count: event.target.value === '' ? null : Number(event.target.value) })} className="ml-2 rounded bg-slate-950 p-2" /></label>
          <label className="block text-sm">Điều kiện thực nghiệm: vật, gá, bố trí, ánh sáng và tiêu chí đầu ra<textarea value={knowledge.conditions_note ?? ''} onChange={event => setKnowledge({ ...knowledge, conditions_note: event.target.value })} className="w-full rounded bg-slate-950 p-2" /></label>
          <p className="text-xs text-gray-400">Dùng cùng mô tả khi người đánh giá xác nhận điều kiện hai lượt tương đương.</p>
          {knowledge.context.trial_stage === 'after_learning' && <label className="block text-sm"><input type="checkbox" checked={knowledge.sop_viewed_confirmed ?? false} onChange={event => setKnowledge({ ...knowledge, sop_viewed_confirmed: event.target.checked })} /> Người đánh giá xác nhận người học đã xem SOP/video mẫu trước lượt này.</label>}
        </div>}
        <div className="flex gap-3"><button disabled={busy} onClick={() => void save('draft')} className="rounded border p-2">Lưu nháp</button><button disabled={busy} onClick={() => void save('approved')} className="rounded border border-cyberGreen p-2 text-cyberGreen">Duyệt SOP và bằng chứng</button><button disabled={busy} onClick={() => void save('retired')} className="rounded border p-2">Ngừng dùng mẫu</button></div>
      </>}
      {tab === 'machine' && <p className="text-sm">Episode HDF5 chứa observations, timestamps và validity masks. ADC giữ đơn vị adc_count, landmark giữ tọa độ ảnh; IMU thiếu là NaN kèm valid=false. Robot action chưa có; chưa cho phép xuất gói điều khiển robot.</p>}
      <label className="block text-xs">Quyền sử dụng dữ liệu <select value={knowledge.license_status} onChange={event => setKnowledge({ ...knowledge, license_status: event.target.value as SessionKnowledge['license_status'] })} className="rounded bg-slate-950 p-2"><option value="unknown">Chưa xác nhận</option><option value="project_internal">Chỉ nội bộ dự án</option><option value="approved_for_training">Đã có quyền dùng để huấn luyện</option></select></label>
      <button disabled={busy} onClick={() => void generate()} className="rounded border p-2">Tạo SOP, clip và episode quan sát</button>
      <div className="flex flex-wrap gap-3 text-sm text-cyberGreen">{(['learner','observation','manifest'] as const).map(kind => <a key={kind} href={backendUrl(base + kind)!}>{kind === 'learner' ? 'Tải gói người học' : kind === 'observation' ? 'Tải episode quan sát HDF5' : 'Xem manifest / checksum'}</a>)}</div>
    </>}
    {!knowledge && <div className="space-y-2"><p className="text-xs text-gray-400">Có thể xuất bản kỹ thuật từ dữ liệu cũ; task, người duyệt và quyền sử dụng vẫn là chưa xác nhận.</p><button disabled={busy} onClick={() => void generate()} className="rounded border p-2">Xuất episode quan sát nháp từ phiên cũ</button>
      {product && <a className="ml-3 text-sm text-cyberGreen" href={backendUrl(base + 'observation')!}>Tải HDF5 / MCAP / video và manifest</a>}</div>}
    {message && <p className="text-sm text-amber-200">{message}</p>}{error && <p role="alert" className="text-sm text-red-200">{error}</p>}
  </section>;
}
