import { useCallback, useEffect, useMemo, useState } from 'react';
import { Images, RefreshCw, Wifi, WifiOff } from 'lucide-react';
import { getSession, listSessions } from './backendApi';
import { candidateList, dateTime, defaultFocus, number } from './presentation';
import type { Focus } from './presentation';
import type { SessionDetail, SessionSummary } from './sessionTypes';
import { SessionCharts, ImageViewer } from './components/SessionVisuals';
import { DtwPanel, Exports, MudaPanel, Phases, SensorPanel } from './components/SessionAnalysis';
import { CapturePanel } from './components/CapturePanel';

function MetricCard({ label, value, note, danger = false }: {
  label: string; value: string; note: string; danger?: boolean;
}) {
  return <div className="rounded-xl border border-slate-700/60 bg-panelBg p-4">
    <div className="text-xs font-semibold uppercase tracking-widest text-gray-400">{label}</div>
    <div className={`mt-2 font-mono text-2xl font-bold ${danger ? 'text-alertRed' : 'text-cyberGreen'}`}>{value}</div>
    <p className="mt-1 text-xs leading-5 text-gray-400">{note}</p>
  </div>;
}

export default function SessionDashboard() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(() => new URLSearchParams(window.location.search).get('session'));
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [focus, setFocus] = useState<Focus | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        const items = await listSessions();
        if (!active) return;
        setSessions(items);
        setListError(null);
        setSelectedId(current => current ?? items[0]?.session_id ?? null);
      } catch (error) {
        if (active) setListError(error instanceof Error ? error.message : 'Không kết nối được backend');
      } finally {
        if (active) setLoading(false);
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => { active = false; window.clearInterval(timer); };
  }, [refreshKey]);

  useEffect(() => {
    if (!selectedId) return;
    const controller = new AbortController();
    const refresh = async () => {
      try {
        const result = await getSession(selectedId, controller.signal);
        if (controller.signal.aborted) return;
        setDetail(result);
        setFocus(current => current?.sessionId === result.session_id ? current : defaultFocus(result));
        setDetailError(null);
      } catch (error) {
        if (!controller.signal.aborted) setDetailError(error instanceof Error ? error.message : 'Không tải được phiên');
      }
    };
    void refresh();
    const timer = window.setInterval(() => void refresh(), 10_000);
    return () => { controller.abort(); window.clearInterval(timer); };
  }, [selectedId, refreshKey]);

  const candidates = useMemo(() => detail ? candidateList(detail) : [], [detail]);
  const selected = detail && detail.session_id === selectedId ? detail : null;
  const chooseSession = useCallback((id: string) => {
    setSelectedId(id);
    const url = new URL(window.location.href);
    url.searchParams.set('session', id);
    window.history.replaceState({}, '', url);
  }, []);
  const captureCompleted = useCallback((id: string) => {
    chooseSession(id);
    setRefreshKey(value => value + 1);
  }, [chooseSession]);

  return <div className="min-h-screen bg-background p-4 text-lightGray md:p-6">
    <div className="mx-auto max-w-[1800px] space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-slate-700/60 bg-panelBg p-4 shadow-lg">
        <div className="flex items-center gap-4"><div className="flex h-11 w-11 items-center justify-center rounded-lg border border-cyberGreen/30 bg-densoNavy font-bold text-cyberGreen">AI</div>
          <div><h1 className="font-heading text-xl font-bold tracking-wide md:text-2xl">SmartWear AI <span className="font-normal text-gray-400">| Session Monitor</span></h1>
            <p className="text-xs text-gray-400">Camera → AI → Backend → Dashboard</p></div></div>
        <div className="flex flex-wrap items-center gap-3">
          <span className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold ${listError ? 'border-alertRed/40 bg-alertRed/10 text-red-300' : 'border-cyberGreen/30 bg-cyberGreen/10 text-cyberGreen'}`}>
            {listError ? <WifiOff size={15} /> : <Wifi size={15} />}{listError ? 'Backend chưa kết nối' : 'Backend đã kết nối'}</span>
          <button type="button" onClick={() => setRefreshKey(value => value + 1)} aria-label="Làm mới"
            className="rounded-lg border border-slate-600 p-2 text-gray-300 hover:border-cyberGreen hover:text-cyberGreen"><RefreshCw size={18} /></button>
        </div>
      </header>

      <CapturePanel onCompleted={captureCompleted} />

      {listError && <div className="rounded-xl border border-alertRed/40 bg-red-950/30 p-4 text-sm text-red-100">
        Không lấy được danh sách phiên: {listError}. Hãy chạy backend tại <code>127.0.0.1:8000</code> rồi bấm làm mới.</div>}

      <div className="grid gap-4 xl:grid-cols-[290px_minmax(0,1fr)]">
        <aside className="min-w-0 rounded-xl border border-slate-700/60 bg-panelBg p-4 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:self-start xl:overflow-auto">
          <div className="mb-3 flex items-center justify-between"><h2 className="font-heading font-bold">Các phiên đã lưu</h2><span className="rounded-full bg-slate-800 px-2 py-0.5 text-xs text-gray-400">{sessions.length}</span></div>
          <p className="mb-3 text-xs text-gray-400">Chọn một lần quay để xem kết quả. Không phải chọn công việc cho công nhân.</p>
          <div className="space-y-2">{sessions.map(item => <button key={item.session_id} type="button" onClick={() => chooseSession(item.session_id)}
            className={`w-full rounded-lg border p-3 text-left transition ${selectedId === item.session_id ? 'border-cyberGreen/60 bg-cyberGreen/10' : 'border-slate-700 bg-slate-900/50 hover:border-slate-500'}`}>
            <div className="truncate text-xs font-bold text-gray-200" title={item.session_id}>{item.session_id.replace(/^DEMO_camera_data_/, 'DEMO · ')}</div>
            <div className="mt-2 text-xs text-gray-400">{dateTime(item.created_at)}</div>
            <div className="mt-2 flex gap-2 text-xs"><span className="text-cyberGreen">Điểm {number(item.similarity_score, 1)}</span><span className="text-amber-300">MUDA {number(item.muda_detected_seconds, 2)} s</span></div>
          </button>)}</div>
          {!loading && sessions.length === 0 && !listError && <p className="rounded-lg bg-slate-800 p-4 text-sm text-gray-400">Chưa có phiên. Bấm “Bắt đầu quay” ở phía trên để tạo phiên đầu tiên.</p>}
        </aside>

        <main className="min-w-0 space-y-4">
          {detailError && <div className="rounded-xl border border-alertRed/40 bg-red-950/30 p-4 text-sm text-red-100">Không tải được phiên: {detailError}</div>}
          {!selected && <div className="flex min-h-72 items-center justify-center rounded-xl border border-slate-700 bg-panelBg p-6 text-center text-gray-400">
            {detailError ? 'Không tải được phiên này. Hãy chọn phiên khác hoặc bấm làm mới.' : loading || selectedId ? 'Đang tải kết quả phiên...' : 'Chọn một phiên ở bên trái để xem.'}</div>}
          {selected && <>
            <section className="rounded-xl border border-cyberGreen/25 bg-densoNavy/55 p-4">
              <div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2"><span className="rounded bg-cyberGreen/15 px-2 py-1 text-xs font-bold text-cyberGreen">{selected.session_id.startsWith('DEMO_') ? 'DEMO' : 'SESSION'}</span>
                  <span className="text-xs text-gray-400">{selected.worker_type} · {dateTime(selected.created_at)}</span></div>
                <h2 className="mt-2 break-all font-heading text-lg font-bold">{selected.session_id}</h2>
                <p className="mt-1 text-sm text-gray-300">Mẫu so sánh: <strong>{selected.analysis_result?.selected_reference?.title ?? selected.analysis_result?.expert_session ?? 'Chưa có'}</strong></p>
              </div><span className="rounded border border-slate-600 px-3 py-1 text-xs text-gray-300">Xuất file: {selected.export_status}</span></div>
            </section>
            <div className="grid gap-3 sm:grid-cols-2 2xl:grid-cols-4">
              <MetricCard label="Điểm so khớp DEMO" value={number(selected.dtw_metrics.similarity_score, 1)} note="Điểm hiển thị từ DTW; không phải phần trăm làm đúng." />
              <MetricCard label="Đoạn cần xem lại" value={String(candidates.length)} note="Nghi vấn từ AI; chưa kết luận thao tác sai." danger={candidates.length > 0} />
              <MetricCard label="Tổng thời lượng nghi vấn" value={`${number(selected.dtw_metrics.muda_detected_seconds, 3)} s`} note="Tổng DEMO; hai tay có thể chồng thời gian." danger={candidates.length > 0} />
              <MetricCard label="Đoạn hành động" value={String(selected.action_phases.length)} note={`${selected.key_frames.length} ảnh phiên quay · ${selected.analysis_result ? 'có phân tích AI' : 'chưa có phân tích AI'}`} />
            </div>
            <div className="grid items-start gap-4 2xl:grid-cols-[minmax(0,1.65fr)_minmax(340px,1fr)]">
              <ImageViewer detail={selected} focus={focus?.sessionId === selected.session_id ? focus : defaultFocus(selected)} setFocus={setFocus} />
              <SessionCharts detail={selected} />
            </div>
            <MudaPanel detail={selected} setFocus={setFocus} />
            <div className="grid items-start gap-4 2xl:grid-cols-2"><Phases detail={selected} /><DtwPanel detail={selected} setFocus={setFocus} /></div>
            <SensorPanel detail={selected} />
            <Exports detail={selected} />
          </>}
        </main>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-2 px-1 pb-3 text-xs text-gray-500">
        <span>SmartWear AI · Giao diện đọc kết quả phiên đã lưu</span>
        <span className="inline-flex items-center gap-1"><Images size={13} /> Ảnh & cảm biến DEMO được ghi rõ nguồn</span>
      </footer>
    </div>
  </div>;
}
