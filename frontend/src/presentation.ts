import { backendUrl } from './backendApi';
import type { AlignmentPair, Hand, ReviewCandidate, SessionDetail } from './sessionTypes';

export type Focus = {
  sessionId: string;
  title: string;
  expertPath?: string | null;
  workerPath?: string | null;
};

export const HANDS: Hand[] = ['left', 'right'];
export const handName = (hand: Hand) => hand === 'left' ? 'Tay trái' : 'Tay phải';
export const seconds = (ms?: number | null) => ms == null ? '—' : `${(ms / 1000).toFixed(3)} s`;
export const number = (value?: number | null, decimals = 2) =>
  value == null || !Number.isFinite(value) ? '—' : value.toFixed(decimals);
export const dateTime = (value?: string) => {
  if (!value) return '—';
  // SQLite strips the UTC timezone marker from backend timestamps.
  const timestamp = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Date(timestamp).toLocaleString('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh' });
};

export function candidateList(detail: SessionDetail): Array<ReviewCandidate & { hand: Hand }> {
  return HANDS.flatMap(hand =>
    (detail.analysis_result?.muda_review?.hands?.[hand]?.candidates ?? []).map(candidate => ({
      ...candidate, hand,
    })),
  ).sort((a, b) => (a.start_ms ?? a.worker_time_hint_ms ?? 0)
    - (b.start_ms ?? b.worker_time_hint_ms ?? 0));
}

export function focusFromPair(sessionId: string, hand: Hand, pair: AlignmentPair): Focus {
  return { sessionId, title: `${handName(hand)} · mẫu ${pair.expert_label} / bạn ${pair.worker_label}`,
    expertPath: pair.expert_image_path, workerPath: pair.worker_image_path };
}

export function defaultFocus(detail: SessionDetail): Focus {
  const candidate = candidateList(detail).find(item => item.worker_image_path || item.expert_image_path);
  if (candidate) return { sessionId: detail.session_id,
    title: `${handName(candidate.hand)} · ${candidate.worker_label ?? candidate.reason}`,
    expertPath: candidate.expert_image_path, workerPath: candidate.worker_image_path };
  for (const hand of HANDS) {
    const pair = detail.analysis_result?.hands?.[hand]?.alignment?.find(item =>
      item.worker_image_path || item.expert_image_path);
    if (pair) return focusFromPair(detail.session_id, hand, pair);
  }
  return { sessionId: detail.session_id, title: 'Ảnh đầu tiên của phiên',
    workerPath: detail.key_frames[0] ? `keyframes/${detail.key_frames[0]}` : null };
}

export function imageUrl(detail: SessionDetail, role: 'expert' | 'worker', path?: string | null): string | null {
  if (!path) return null;
  const declared = detail.analysis_image_urls?.[role]?.[path];
  if (declared) return backendUrl(declared);
  if (role === 'worker') {
    const filename = path.replace(/^keyframes\//, '');
    if (detail.key_frames.includes(filename)) {
      return backendUrl(`/api/v1/sessions/${encodeURIComponent(detail.session_id)}/keyframes/${encodeURIComponent(filename)}`);
    }
  }
  return null;
}
