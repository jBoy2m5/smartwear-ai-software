import { useState } from 'react';
import { backendUrl, getLearningReport, listLearningTrials } from '../backendApi';
import type { ExpertReference, LearningReport } from '../backendApi';

export function LearningExperimentPanel() {
  const [trials, setTrials] = useState<ExpertReference[]>([]);
  const [before, setBefore] = useState('');
  const [after, setAfter] = useState('');
  const [report, setReport] = useState<LearningReport | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const load = async () => {
    setBusy(true); setError(''); setReport(null);
    try { setTrials(await listLearningTrials()); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  };
  const compare = async () => {
    setBusy(true); setError(''); setReport(null);
    try { setReport(await getLearningReport(before, after)); }
    catch (reason) { setError(String(reason)); }
    finally { setBusy(false); }
  };
  const download = () => {
    if (!report) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = 'learning-evidence.json'; link.click();
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <div className="space-y-3 border-t border-slate-700 p-4">
    <h3 className="font-bold">Thí nghiệm học việc — bằng chứng trước/sau</h3>
    <p className="text-sm text-gray-300">Ghi mẫu và duyệt SOP → ghi người học trước khi xem SOP → cho xem SOP → ghi lượt sau trong cùng điều kiện → người đánh giá duyệt video, đầu ra, lỗi và số gợi ý.</p>
    <button disabled={busy} onClick={() => void load()} className="rounded border p-2 text-sm">Tải / cập nhật các lượt thực nghiệm</button>
    {trials.length === 0 && <p className="text-sm text-amber-200">Chưa tải được lượt trước/sau. Thu và duyệt các phiên người học bằng lựa chọn phía trên.</p>}
    <div className="grid gap-3 md:grid-cols-2">{(['before_learning', 'after_learning'] as const).map((stage, index) => <label key={stage} className="text-sm">{index === 0 ? 'Lượt trước khi học' : 'Lượt sau khi học'}
      <select value={index === 0 ? before : after} onChange={event => { (index === 0 ? setBefore : setAfter)(event.target.value); setReport(null); }} className="mt-1 w-full rounded bg-slate-950 p-2">
        <option value="">Chọn phiên thật</option>{trials.filter(t => t.context.trial_stage === stage).map(t => <option key={t.session_id} value={t.session_id}>{t.context.participant_id} · {t.context.task_id} · {t.review_status} · {t.session_id}</option>)}
      </select>
    </label>)}</div>
    <button disabled={busy || !before || !after} onClick={() => void compare()} className="rounded border border-cyberGreen p-2 text-sm disabled:opacity-40">Kiểm bằng chứng và so sánh</button>
    {report && <div className="space-y-2 rounded bg-slate-900 p-3 text-sm">
      <p className={report.evidence_ready ? 'text-cyberGreen' : 'text-amber-200'}>{report.evidence_ready ? 'Đủ bằng chứng cho cặp thực nghiệm này' : 'Chưa đủ bằng chứng để kết luận'}</p>
      <ul className="list-disc pl-5">{report.reasons.map(reason => <li key={reason}>{reason}</li>)}</ul>
      <div className="overflow-x-auto"><table className="w-full text-left"><thead><tr><th>Chỉ số</th><th>Trước</th><th>Sau</th></tr></thead><tbody>
        <tr><td>Thời gian thao tác (s)</td><td>{report.before.duration_s ?? 'chưa đánh dấu'}</td><td>{report.after.duration_s ?? 'chưa đánh dấu'}</td></tr>
        <tr><td>Đầu ra</td><td>{report.before.outcome}</td><td>{report.after.outcome}</td></tr>
        <tr><td>Số gợi ý</td><td>{report.before.prompt_count ?? 'chưa đo'}</td><td>{report.after.prompt_count ?? 'chưa đo'}</td></tr>
        <tr><td>Số lỗi đã xác nhận</td><td>{report.before.confirmed_error_count ?? 'chưa đánh giá'}</td><td>{report.after.confirmed_error_count ?? 'chưa đánh giá'}</td></tr>
      </tbody></table></div>
      {report.deltas && <p>Sau − trước: thời gian {report.deltas.duration_delta_s} s · gợi ý {report.deltas.prompt_delta} · lỗi {report.deltas.error_delta}. Thời gian giảm {report.deltas.duration_reduction_pct}%.</p>}
      {report.limitations.map(line => <p className="text-xs text-gray-400" key={line}>{line}</p>)}
      <div className="flex flex-wrap gap-3">{report.source_evidence.map(source => <a key={source.session_id} className="text-xs text-cyan-200 underline" href={backendUrl(source.source_url)!}>Nguồn {source.session_id}</a>)}</div>
      <button onClick={download} className="rounded border p-2">Tải báo cáo JSON kèm hash và mốc bằng chứng</button>
    </div>}
    {error && <p role="alert" className="text-sm text-red-200">{error}</p>}
  </div>;
}
