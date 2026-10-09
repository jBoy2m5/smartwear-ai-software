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

async function requestJson<T>(path: string, method: 'GET' | 'POST' | 'PUT', signal?: AbortSignal, body?: unknown): Promise<T> {
  const response = await fetch(backendUrl(path)!, {
    method, signal, headers: { Accept: 'application/json', ...(body ? { 'Content-Type': 'application/json' } : {}) },
    ...(body ? { body: JSON.stringify(body) } : {}),
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

export async function deleteSession(sessionId: string): Promise<void> {
  const response = await fetch(backendUrl(`/api/v1/sessions/${encodeURIComponent(sessionId)}`)!, {
    method: 'DELETE', headers: { Accept: 'application/json' },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string };
    throw new Error(body.detail ?? `Backend HTTP ${response.status}`);
  }
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
  preview_age_ms?: number | null;
  frame_age_ms?: number | null;
  preview_encode_ms?: number | null;
  performance?: { stages: Record<string, { mean_ms: number; p95_ms: number }>; events_ms: Record<string, number> } | null;
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

export interface DeviceHealth {
  checked_epoch_ms: number; can_start: boolean; capture_active: boolean;
  camera: { state: 'ready' | 'starting' | 'in_use' | 'tcp_only' | 'unreachable'; message: string;
    board: { boot_id: string; reset_reason: string; uptime_ms: number; wifi_rssi: number } | null };
  mqtt: { ok: boolean; message: string }; ntp: { ok: boolean };
}
export function getDeviceHealth(signal?: AbortSignal, refresh = false) {
  return getJson<DeviceHealth>(`/api/v1/capture/devices?refresh=${refresh}`, signal);
}

export function startCapture(captureMode: 'hardware' | 'demo' = 'hardware', context?: CaptureContext): Promise<CaptureStatus> {
  return requestJson<CaptureStatus>(`/api/v1/capture/?capture_mode=${captureMode}`, 'POST', undefined, context);
}

export interface TaskStep {
  step_id: string; title: string; instruction: string; why: string; tips: string;
  common_errors: string; safety: string; acceptable_variation: string;
  start_s: number | null; end_s: number | null; keyframe: string | null;
}
export interface Procedure {
  task_id: string; version: string; title: string; department: string;
  tools: string; success_criteria: string; steps: TaskStep[];
}
export interface CaptureContext {
  role: 'expert' | 'worker' | 'demo'; task_id: string | null; procedure_version: string | null;
  reference_session_id: string | null; participant_id: string; consent_confirmed: boolean; purpose: string;
  trial_stage: 'reference' | 'before_learning' | 'after_learning' | 'practice' | 'technical';
}
export interface SessionKnowledge {
  revision: number; context: CaptureContext; source_session_name: string; reference_revision: number | null;
  steps: TaskStep[]; review_status: 'draft' | 'approved' | 'retired'; reviewer: string;
  review_rationale: string; clarity_confirmed: boolean; outcome: 'unknown' | 'passed' | 'failed';
  prompt_count: number | null; confirmed_errors: string; retention_policy: string;
  confirmed_error_count?: number | null; conditions_note?: string; sop_viewed_confirmed?: boolean;
  source_archive_sha256?: string | null;
  license_status: 'unknown' | 'project_internal' | 'approved_for_training'; updated_at?: string;
}
export interface ExpertReference extends SessionKnowledge { session_id: string }
export function listLearningTrials() { return getJson<ExpertReference[]>('/api/v1/knowledge/learning-trials'); }
export interface LearningReport {
  evidence_ready: boolean; reasons: string[]; participant_id: string; limitations: string[];
  before: { session_id: string; duration_s: number | null; outcome: string; prompt_count: number | null; confirmed_error_count: number | null };
  after: LearningReport['before'];
  deltas: { duration_delta_s: number; duration_reduction_pct: number; prompt_delta: number; error_delta: number } | null;
  source_evidence: Array<{ session_id: string; archive_sha256: string; source_url: string }>;
}
export function getLearningReport(before: string, after: string) {
  return getJson<LearningReport>(`/api/v1/knowledge/learning-experiment?before_session_id=${encodeURIComponent(before)}&after_session_id=${encodeURIComponent(after)}`);
}
export function listProcedures() { return getJson<Procedure[]>('/api/v1/knowledge/procedures'); }
export function listReferences(task: string, version: string) {
  return getJson<ExpertReference[]>(`/api/v1/knowledge/references?task_id=${encodeURIComponent(task)}&version=${encodeURIComponent(version)}`);
}
export function getKnowledge(id: string) { return getJson<SessionKnowledge>(`/api/v1/knowledge/sessions/${encodeURIComponent(id)}`); }
export function saveKnowledge(id: string, value: SessionKnowledge) {
  const { updated_at: _updated, ...body } = value;
  return requestJson<SessionKnowledge>(`/api/v1/knowledge/sessions/${encodeURIComponent(id)}`, 'PUT', undefined, body);
}
export interface QualityReport {
  warnings: string[]; clock_accuracy_status: string; robot_ready: boolean;
  camera: { frame_width: number; frame_height: number; fps_measured: number | null };
  alignment: { coverage: number }; wrist: { device_rate_hz: number | null; imu_available_samples: number };
}
export function getQuality(id: string) { return getJson<QualityReport>(`/api/v1/knowledge/sessions/${encodeURIComponent(id)}/quality`); }
export function generateProducts(id: string) {
  return requestJson<ProductManifest>(`/api/v1/knowledge/sessions/${encodeURIComponent(id)}/products`, 'POST');
}
export interface ProductManifest {
  episode_id: string; generation_elapsed_ms: number;
  video_timebase: { source_start_s: number; reference_source_start_s: number | null };
  quality_state: { learner_ready: boolean; learner_reasons: string[] };
  artifacts: Array<{ path: string; sha256: string; size_bytes: number }>;
  learner_steps: TaskStep[]; worker_steps: TaskStep[];
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
