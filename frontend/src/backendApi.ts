import type { SessionDetail, SessionListResponse, SessionSummary } from './sessionTypes';

const base = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '');

export function backendUrl(path: string | null | undefined): string | null {
  if (!path) return null;
  if (/^https?:\/\//i.test(path)) return path;
  return `${base}${path.startsWith('/') ? path : `/${path}`}`;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return requestJson<T>(path, 'GET', signal);
}

async function requestJson<T>(path: string, method: 'GET' | 'POST', signal?: AbortSignal): Promise<T> {
  const response = await fetch(backendUrl(path)!, {
    method, signal, headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    let detail = '';
    try {
      const body: { detail?: string } = await response.json();
      detail = body.detail ?? '';
    } catch {
      // The status is enough to diagnose an unavailable route.
    }
    throw new Error(`Backend HTTP ${response.status}${detail ? `: ${detail}` : ''}`);
  }
  return response.json() as Promise<T>;
}

export async function listSessions(signal?: AbortSignal): Promise<SessionSummary[]> {
  const items: SessionSummary[] = [];
  let offset = 0;
  const limit = 25;
  let hasMore = true;
  while (hasMore) {
    const page = await getJson<SessionListResponse>(
      `/api/v1/sessions/?limit=${limit}&offset=${offset}`, signal,
    );
    items.push(...page.items);
    offset += page.items.length;
    hasMore = page.items.length > 0 && offset < page.total;
  }
  return items;
}

export function getSession(sessionId: string, signal?: AbortSignal): Promise<SessionDetail> {
  return getJson<SessionDetail>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, signal);
}

export interface CaptureStatus {
  job_id: string;
  stage: 'starting' | 'recording' | 'stopping' | 'processing' | 'publishing' | 'completed' | 'failed';
  message: string;
  session_id: string | null;
  updated_at?: string;
  capture_mode?: 'hardware' | 'demo';
}

export interface CapturePreview {
  frame_index: number;
  timestamp_ms: number;
  camera: { frame_width: number; frame_height: number };
  right_action: { label: string; tracking_status: string };
  right_landmarks: Array<{ id: number; x: number; y: number; z: number }>;
  left_action?: { label: string; tracking_status: string };
  left_landmarks?: Array<{ id: number; x: number; y: number; z: number }>;
  wrist_status?: 'receiving' | 'missing';
  live_alignment?: { sensor_status: 'matched' | 'missing'; delta_ms: number | null };
  wrist_sample?: { seq: number; acc: number[] | null; gyro: number[] | null; force: number[];
    imu_status?: 'ok' | 'unavailable'; imu_address?: number | null } | null;
}

export function startCapture(captureMode: 'hardware' | 'demo' = 'hardware'): Promise<CaptureStatus> {
  return requestJson<CaptureStatus>(`/api/v1/capture/?capture_mode=${captureMode}`, 'POST');
}

export function getCaptureStatus(jobId: string, signal?: AbortSignal): Promise<CaptureStatus> {
  return getJson<CaptureStatus>(`/api/v1/capture/${encodeURIComponent(jobId)}`, signal);
}

export function getCapturePreview(jobId: string, signal?: AbortSignal): Promise<CapturePreview> {
  return getJson<CapturePreview>(`/api/v1/capture/${encodeURIComponent(jobId)}/preview`, signal);
}

export function stopCapture(jobId: string): Promise<CaptureStatus> {
  return requestJson<CaptureStatus>(`/api/v1/capture/${encodeURIComponent(jobId)}/stop`, 'POST');
}
