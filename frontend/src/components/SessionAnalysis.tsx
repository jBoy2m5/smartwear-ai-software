import { AlertTriangle, CheckCircle2, Clock3, FileJson2, FileText, Download } from 'lucide-react';
import { backendUrl } from '../backendApi';
import { candidateList, displayHands, focusFromPair, HANDS, handName, number, seconds } from '../presentation';
import type { Focus } from '../presentation';
import type { SessionDetail } from '../sessionTypes';

const reasonName: Record<string, string> = {
  longer_visible_action: 'Kéo dài hơn mẫu',
  shorter_visible_action: 'Ngắn hơn mẫu',
  inserted_visible_action: 'Hành động chen vào',
  extra_visible_action: 'Hành động làm thêm',
  repeated_visible_action: 'Hành động lặp lại',
  missing_visible_action: 'Thiếu hành động trong mẫu',
  different_visible_label: 'Khác hành động trong mẫu',
};

export function MudaPanel({ detail, setFocus }: {
  detail: SessionDetail; setFocus: (focus: Focus) => void;
}) {
  const items = candidateList(detail);
  const dtwReviews = HANDS.reduce((total, hand) =>
    total + (detail.analysis_result?.hands?.[hand]?.review_candidates?.length ?? 0), 0);
  return <section className={`rounded-xl border p-5 shadow-lg ${items.length ? 'border-alertRed/50 bg-red-950/20' : dtwReviews ? 'border-amber-500/40 bg-panelBg' : 'border-slate-700/60 bg-panelBg'}`}>
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex items-center gap-3">{items.length ? <AlertTriangle className="text-alertRed" size={28} /> : dtwReviews ? <AlertTriangle className="text-amber-300" size={28} /> : <CheckCircle2 className="text-cyberGreen" size={28} />}
        <div><h2 className="font-heading text-lg font-bold">Nghi vấn MUDA</h2>
          <p className="text-sm text-gray-400">{items.length ? `${items.length} nghi vấn MUDA; cần xem ảnh/video trước khi kết luận` : dtwReviews ? `Chưa có nghi vấn MUDA theo quy tắc hiện tại; có ${dtwReviews} đoạn DTW cần xem riêng ở bảng phía dưới.` : 'Chưa có nghi vấn MUDA hoặc đoạn DTW cần xem riêng trong phiên này.'}</p></div></div>
      <span className="rounded-lg bg-slate-900 px-3 py-2 font-mono text-sm text-gray-300">Thời gian tăng thêm DEMO: {number(detail.dtw_metrics.muda_detected_seconds, 3)} s</span>
    </div>
    {items.length > 0 && <div className="mt-4 grid gap-3 md:grid-cols-2">
      {items.map((item, index) => <button key={`${item.hand}-${item.reason}-${item.worker_segment_id ?? index}-${index}`}
        type="button" onClick={() => setFocus({ sessionId: detail.session_id,
          title: `${handName(item.hand)} · ${item.worker_label ?? item.expert_label ?? item.reason}`,
          expertPath: item.expert_image_path, workerPath: item.worker_image_path })}
        className="rounded-lg border border-alertRed/25 bg-slate-900/75 p-3 text-left transition hover:border-alertRed/70">
        <div className="flex flex-wrap items-center justify-between gap-2"><span className="text-sm font-bold text-red-200">{handName(item.hand)} · {reasonName[item.reason] ?? item.reason}</span>
          <span className="font-mono text-xs text-gray-400">{item.start_ms == null ? `gần ${seconds(item.worker_time_hint_ms)}` : `${seconds(item.start_ms)} → ${seconds(item.end_ms)}`}</span></div>
        <p className="mt-2 text-sm leading-5 text-gray-200">{item.comment_vi ?? 'Mở ảnh để xem lại đoạn này.'}</p>
        {item.extra_ms != null && <p className="mt-2 text-xs text-gray-400">{item.reason === 'shorter_visible_action' ? 'Ngắn hơn mẫu' : 'Dài hơn mẫu'}: {seconds(Math.abs(item.extra_ms))}</p>}
      </button>)}
    </div>}
    <p className="mt-3 text-xs text-gray-500">Đoạn ngắn hơn mẫu vẫn cần xem lại nhưng không cộng vào thời gian tăng thêm. Các thời lượng hai tay có thể chồng nhau; đây không phải số giây lãng phí đã xác nhận.</p>
  </section>;
}

export function Phases({ detail }: { detail: SessionDetail }) {
  const hands = displayHands(detail);
  return <section className="rounded-xl border border-slate-700/60 bg-panelBg p-4">
    <div className="mb-3 flex items-center gap-2"><Clock3 size={19} className="text-cyberGreen" />
      <h2 className="font-heading text-lg font-bold">Chuỗi hành động đã ghi</h2></div>
    <p className="mb-3 text-xs text-gray-400">Chỉ hiển thị tay có hành động trong phiên; đoạn không nhìn rõ tay có thể không xuất hiện ở đây.</p>
    <div className="max-h-96 overflow-auto rounded-lg border border-slate-700/70">
      <table className="w-full min-w-[670px] text-left text-sm"><thead className="sticky top-0 bg-slate-800 text-xs uppercase text-gray-400"><tr>
        <th className="p-3">Thời gian</th>{hands.map(hand => <th key={hand} className="p-3">{handName(hand)}</th>)}<th className="p-3">Nhãn gốc</th><th className="p-3">Lực DEMO đỉnh</th>
      </tr></thead><tbody>{detail.action_phases.map((phase, index) => <tr key={`${phase.start_time}-${index}`} className="border-t border-slate-700/50 hover:bg-slate-800/60">
        <td className="whitespace-nowrap p-3 font-mono text-xs text-gray-300">{number(phase.start_time, 3)}–{number(phase.end_time, 3)} s</td>
        {hands.map(hand => <td key={hand} className={`p-3 font-semibold ${hand === 'right' ? 'text-cyberGreen' : 'text-cyan-300'}`}>
          {phase.phase.split('.').find(label => label.startsWith(`${hand.toUpperCase()}_`))?.replace(`${hand.toUpperCase()}_`, '') ?? '—'}</td>)}
        <td className="p-3 font-mono text-xs text-gray-400">{phase.phase}</td>
        <td className="p-3 font-mono text-gray-300">{number(phase.peak_force_N, 2)}</td>
      </tr>)}</tbody></table>
      {!detail.action_phases.length && <div className="p-5 text-sm text-gray-400">Chưa có hành động nhìn thấy rõ.</div>}
    </div>
  </section>;
}

export function DtwPanel({ detail, setFocus }: {
  detail: SessionDetail; setFocus: (focus: Focus) => void;
}) {
  const analysis = detail.analysis_result;
  return <section className="rounded-xl border border-slate-700/60 bg-panelBg p-4">
    <div className="mb-4"><h2 className="font-heading text-lg font-bold">So sánh DTW từng tay</h2>
      <p className="text-xs text-gray-400">Mỗi dòng ghép một đoạn mẫu với đoạn camera ghi được. Số âm nghĩa là đoạn bạn quay ngắn hơn; khi khác nhãn, không hiểu là làm hành động đó nhanh hơn.</p></div>
    {!analysis ? <p className="rounded-lg bg-slate-800 p-4 text-sm text-gray-400">Phiên này chưa có bản phân tích chi tiết từ AI.</p> :
      displayHands(detail).map(hand => { const track = analysis.hands?.[hand]; const pairs = track?.alignment ?? [];
        return <div key={hand} className="mb-5 last:mb-0">
          <div className="mb-2 flex flex-wrap items-center gap-3"><h3 className="font-bold text-cyan-300">{handName(hand)}</h3>
            <span className="text-xs text-gray-400">{track?.status ?? 'Chưa rõ'} · mẫu {track?.expert_segments ?? 0} đoạn · bạn {track?.worker_segments ?? 0} đoạn · DTW cost {number(track?.normalized_dtw_cost, 4)}</span></div>
          {pairs.length ? <div className="max-h-80 overflow-auto rounded-lg border border-slate-700/70">
            <table className="w-full min-w-[620px] text-left text-sm"><thead className="sticky top-0 bg-slate-800 text-xs uppercase text-gray-400"><tr>
              <th className="p-3">Cặp đoạn</th><th className="p-3">Mẫu</th><th className="p-3">Phiên quay</th><th className="p-3">Chênh lệch</th><th className="p-3">Ảnh</th>
            </tr></thead><tbody>{pairs.map((pair, index) => <tr key={`${pair.expert_segment_id}-${pair.worker_segment_id}-${index}`} className="border-t border-slate-700/50 hover:bg-slate-800/60">
              <td className="p-3 font-mono text-xs text-gray-400">#{pair.expert_segment_id} ↔ #{pair.worker_segment_id}</td>
              <td className="p-3"><span className="font-semibold">{pair.expert_label}</span><br /><span className="text-xs text-gray-400">{seconds(pair.expert_duration_ms)}</span></td>
              <td className="p-3"><span className={pair.same_label ? 'font-semibold text-cyberGreen' : 'font-semibold text-amber-300'}>{pair.worker_label}</span><br /><span className="text-xs text-gray-400">{seconds(pair.worker_duration_ms)}</span></td>
              <td className="p-3 font-mono text-xs">{pair.worker_extra_ms > 0 ? '+' : ''}{pair.worker_extra_ms} ms
                {!pair.same_label && <span className="mt-1 block font-sans text-amber-200">Khác nhãn: chỉ là hiệu hai độ dài</span>}</td>
              <td className="p-3"><button type="button" onClick={() => setFocus(focusFromPair(detail.session_id, hand, pair))}
                className="rounded border border-cyberGreen/40 px-2 py-1 text-xs text-cyberGreen hover:bg-cyberGreen/10">Xem ảnh</button></td>
          </tr>)}</tbody></table></div> : <p className="rounded-lg bg-slate-800/70 p-3 text-sm text-gray-400">Không đủ hành động nhìn thấy rõ để ghép tay này.</p>}
          {(track?.review_candidates?.length ?? 0) > 0 && <details className="mt-3 rounded-lg border border-amber-500/25 bg-amber-500/5 p-3 text-sm">
            <summary className="cursor-pointer font-semibold text-amber-200">{track!.review_candidates!.length} đoạn DTW cần xem riêng · {handName(hand)}</summary>
            <p className="mt-2 text-xs text-gray-400">Đây là gợi ý từ bước so cặp; không đồng nghĩa đã được bước MUDA đánh dấu.</p>
            <div className="mt-3 grid gap-2 sm:grid-cols-2">{track!.review_candidates!.map((item, index) => <button
              key={`${item.reason}-${item.worker_segment_id ?? index}-${index}`} type="button"
              onClick={() => setFocus({ sessionId: detail.session_id, title: `${handName(hand)} · ${reasonName[item.reason] ?? item.reason}`,
                expertPath: item.expert_image_path, workerPath: item.worker_image_path })}
              className="rounded border border-slate-700 bg-slate-900/70 p-3 text-left hover:border-amber-300/60">
              <span className="font-semibold text-amber-200">{reasonName[item.reason] ?? item.reason}</span>
              <span className="ml-2 text-xs text-gray-400">#{item.expert_segment_id ?? '—'} ↔ #{item.worker_segment_id ?? '—'}</span>
              <span className="mt-1 block text-xs text-gray-300">{item.expert_label ?? '—'} → {item.worker_label ?? '—'} · chênh {item.worker_extra_ms ?? item.extra_ms ?? '—'} ms</span>
              {item.reason === 'different_visible_label' && <span className="mt-1 block text-xs text-amber-200">Khác nhãn; số chênh không nói bạn làm cùng động tác nhanh hay chậm hơn.</span>}
              {item.start_ms != null && <span className="mt-1 block text-xs text-gray-400">{seconds(item.start_ms)} → {seconds(item.end_ms)}</span>}
            </button>)}</div>
          </details>}
          {(track?.expert_omitted || track?.worker_omitted) && <details className="mt-2 text-xs text-gray-400">
            <summary className="cursor-pointer">Các đoạn camera không đủ dữ liệu để ghép</summary>
            <pre className="mt-2 max-h-48 overflow-auto rounded bg-slate-900 p-3">{JSON.stringify({ expert: track.expert_omitted, worker: track.worker_omitted }, null, 2)}</pre>
          </details>}
        </div>;
      })}
  </section>;
}

export function SensorPanel({ detail }: { detail: SessionDetail }) {
  const sensors = detail.analysis_result?.sensor_comparison;
  return <section className="rounded-xl border border-slate-700/60 bg-panelBg p-4">
    <h2 className="font-heading text-lg font-bold">So sánh cảm biến</h2>
    <p className="mt-1 text-sm text-amber-200">Nguồn: {sensors?.status ?? 'chưa có'} · lực/EMG hiện là số mô phỏng, không phải Newton đo thật.</p>
    {sensors?.difference_note && <p className="mt-2 text-xs text-gray-400">{sensors.difference_note}</p>}
    <div className="mt-4 grid gap-4 xl:grid-cols-2">
      {displayHands(detail).map(hand => { const result = sensors?.hands?.[hand]; return <div key={hand} className="rounded-lg border border-slate-700 bg-slate-900/60 p-3">
        <div className="mb-2 font-semibold text-cyan-300">{handName(hand)} · {result?.status ?? 'chưa có dữ liệu'}</div>
        <div className="max-h-72 overflow-auto">{result?.pairs?.length ? <table className="w-full min-w-[400px] text-left text-xs">
          <thead className="text-gray-400"><tr><th className="py-2">Đoạn</th><th>Trạng thái</th><th>Lực TB mẫu</th><th>Lực TB bạn</th><th>Chênh lệch</th><th>Đủ số</th></tr></thead>
          <tbody>{result.pairs.map((pair, index) => <tr key={`${pair.expert_segment_id}-${pair.worker_segment_id}-${index}`} className="border-t border-slate-700/50">
            <td className="py-2">{pair.expert_label} ↔ {pair.worker_label}</td><td>{pair.comparison_status}</td>
            <td>{number(pair.expert?.force_mean)}</td><td>{number(pair.worker?.force_mean)}</td>
            <td>{number(pair.worker_minus_expert?.force_mean)}</td>
            <td><details className="min-w-24"><summary className="cursor-pointer text-cyberGreen">Xem</summary>
              <pre className="max-h-48 w-72 overflow-auto rounded bg-slate-950 p-2 text-[10px] text-gray-300">{JSON.stringify(pair, null, 2)}</pre>
            </details></td>
          </tr>)}</tbody></table> : <p className="text-sm text-gray-500">Không có cặp cảm biến để so.</p>}</div>
      </div>; })}
    </div>
    {sensors && <details className="mt-4 text-sm"><summary className="cursor-pointer text-cyberGreen">Xem toàn bộ số cảm biến, nguồn và đơn vị</summary>
      <pre className="mt-3 max-h-96 overflow-auto rounded-lg bg-slate-950 p-4 text-xs text-gray-300">{JSON.stringify(sensors, null, 2)}</pre></details>}
  </section>;
}

function ExportLink({ href, children, Icon }: { href: string | null | undefined;
  children: React.ReactNode; Icon: typeof FileText }) {
  if (!href) return null;
  return <a href={backendUrl(href) ?? undefined} target="_blank" rel="noreferrer"
    className="inline-flex items-center gap-2 rounded-lg border border-cyberGreen/35 bg-cyberGreen/10 px-3 py-2 text-sm font-semibold text-cyberGreen hover:bg-cyberGreen/20">
    <Icon size={16} />{children}</a>;
}

export function Exports({ detail }: { detail: SessionDetail }) {
  const analysis = detail.analysis_result;
  return <section className="rounded-xl border border-slate-700/60 bg-panelBg p-4">
    <div className="flex flex-wrap items-center justify-between gap-2"><h2 className="font-heading text-lg font-bold">Báo cáo & dữ liệu đầy đủ</h2>
      <span className="text-xs text-gray-400">Backend: {detail.export_status}{detail.export_error ? ` · ${detail.export_error}` : ''}</span></div>
    <div className="mt-4 flex flex-wrap gap-2">
      <ExportLink href={detail.sop_download_url} Icon={FileText}>SOP PDF</ExportLink>
      <ExportLink href={detail.sop_download_url ? `${detail.sop_download_url}?format=html` : null} Icon={FileText}>SOP HTML</ExportLink>
      <ExportLink href={detail.robot_json_url} Icon={FileJson2}>Robot JSON · DEMO</ExportLink>
      <ExportLink href={detail.robot_export_url} Icon={Download}>ROSbag · DEMO</ExportLink>
      <ExportLink href={detail.recording_url} Icon={Download}>Video gốc AVI</ExportLink>
      <ExportLink href={detail.source_data_url} Icon={Download}>Dữ liệu AI gốc ZIP</ExportLink>
      {detail.analysis_result && <ExportLink href={`/api/v1/sessions/${encodeURIComponent(detail.session_id)}/analysis-result`} Icon={FileJson2}>AI analysis JSON</ExportLink>}
    </div>
    <p className="mt-3 text-xs text-gray-500">Đường đi robot là tọa độ DEMO từ ảnh camera, không thể dùng để điều khiển robot thật. Video AVI có thể cần mở bằng trình phát video trên máy.</p>
    {!detail.recording_url && <p className="mt-2 text-xs text-amber-200">Video gốc của phiên này chưa được gửi lên backend; ảnh và phân tích vẫn xem được.</p>}
    {!detail.source_data_url && <p className="mt-2 text-xs text-amber-200">Bộ file AI gốc của phiên này chưa được gửi lên backend.</p>}
    {analysis && <details className="mt-4 rounded-lg border border-slate-700 bg-slate-900/60 p-3 text-sm">
      <summary className="cursor-pointer font-semibold text-gray-200">Mẫu tham chiếu, ghi chú và nguồn dữ liệu</summary>
      <div className="mt-3 space-y-2 text-xs text-gray-300">
        <p>Mẫu đã chọn: {analysis.selected_reference?.title ?? analysis.expert_session ?? '—'} ({analysis.selected_reference?.sample_id ?? '—'})</p>
        {analysis.selected_reference?.practice_instruction && <p>Thao tác mẫu: {analysis.selected_reference.practice_instruction}</p>}
        {analysis.reference_selection_note && <p>Cách chọn mẫu: {analysis.reference_selection_note}</p>}
        {analysis.score_note && <p>Điểm so sánh: {analysis.score_note}</p>}
        {analysis.review_note && <p>Đoạn cần xem: {analysis.review_note}</p>}
        {analysis.muda_review?.note && <p>MUDA: {analysis.muda_review.note}</p>}
        <p>Đã dùng cảm biến mô phỏng: {analysis.uses_simulated_sensors ? 'Có' : 'Không / chưa rõ'}</p>
        {analysis.available_references?.length ? <p>Các mẫu đã xét: {analysis.available_references.map(item => `${item.sample_id} (${number(item.selection_cost, 4)})`).join(' · ')}</p> : null}
      </div>
    </details>}
    <div className="mt-4 grid gap-3 md:grid-cols-2">
      <details className="rounded-lg border border-slate-700 bg-slate-900/60 p-3"><summary className="cursor-pointer text-sm font-semibold text-gray-200">Toàn bộ JSON backend</summary>
        <pre className="mt-3 max-h-96 overflow-auto text-xs text-gray-300">{JSON.stringify(detail, null, 2)}</pre></details>
      <details className="rounded-lg border border-slate-700 bg-slate-900/60 p-3"><summary className="cursor-pointer text-sm font-semibold text-gray-200">Toàn bộ JSON phân tích AI</summary>
        <pre className="mt-3 max-h-96 overflow-auto text-xs text-gray-300">{detail.analysis_result ? JSON.stringify(detail.analysis_result, null, 2) : 'Chưa có analysis_result cho phiên này.'}</pre></details>
    </div>
  </section>;
}
