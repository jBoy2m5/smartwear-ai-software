export type Hand = 'left' | 'right';

export interface SessionSummary {
  session_id: string;
  worker_type: 'EXPERT' | 'TRAINEE';
  similarity_score: number;
  muda_detected_seconds: number;
  export_status: string;
  created_at: string;
  updated_at: string;
}

export interface ActionPhase {
  phase: string;
  start_time: number;
  end_time: number;
  peak_force_N: number | null;
}

export interface TrajectoryPoint {
  t: number;
  pos: [number, number, number];
  force: number;
}

export interface AlignmentPair {
  expert_segment_id: number;
  worker_segment_id: number;
  expert_label: string;
  worker_label: string;
  same_label: boolean;
  expert_duration_ms: number;
  worker_duration_ms: number;
  worker_extra_ms: number;
  expert_image_path?: string | null;
  worker_image_path?: string | null;
}

export interface ReviewCandidate {
  hand?: Hand;
  reason: string;
  comment_vi?: string;
  worker_segment_id?: number;
  expert_segment_id?: number;
  worker_label?: string;
  expert_label?: string;
  start_ms?: number;
  end_ms?: number;
  duration_ms?: number;
  extra_ms?: number;
  worker_extra_ms?: number;
  worker_time_hint_ms?: number;
  expert_image_path?: string | null;
  worker_image_path?: string | null;
}

export interface HandComparison {
  status: string;
  expert_segments?: number;
  worker_segments?: number;
  normalized_dtw_cost?: number;
  alignment?: AlignmentPair[];
  review_candidates?: ReviewCandidate[];
  expert_omitted?: Record<string, unknown>;
  worker_omitted?: Record<string, unknown>;
}

export interface SensorPair {
  expert_segment_id: number;
  worker_segment_id: number;
  expert_label: string;
  worker_label: string;
  comparison_status: string;
  expert?: { force_mean?: number | null; force_adc_mean?: number[] | null; [key: string]: unknown };
  worker?: { force_mean?: number | null; force_adc_mean?: number[] | null; [key: string]: unknown };
  worker_minus_expert?: Record<string, number | null> | null;
  worker_minus_expert_adc?: number[] | null;
}

export interface SensorHand {
  status: string;
  pairs?: SensorPair[];
}

export interface AnalysisResult {
  schema_version: string;
  expert_session?: string;
  worker_session: string;
  selected_reference?: {
    sample_id: string;
    title?: string;
    practice_instruction?: string;
    demo_only?: boolean;
    selection_cost?: number;
  };
  reference_selection_note?: string;
  score_note?: string;
  review_note?: string;
  hands: Record<Hand, HandComparison>;
  muda_review?: {
    status?: string;
    method?: string;
    note?: string;
    hands?: Record<Hand, { status: string; candidate_count?: number; candidates: ReviewCandidate[] }>;
  };
  sensor_comparison?: {
    status?: string;
    difference_note?: string;
    force_note?: string;
    expert_source?: Record<string, unknown>;
    worker_source?: Record<string, unknown>;
    hands?: Record<Hand, SensorHand>;
  };
  uses_simulated_sensors?: boolean;
  available_references?: Array<{ sample_id: string; selection_cost: number }>;
  [key: string]: unknown;
}

export interface SessionDetail extends SessionSummary {
  key_frames: string[];
  action_phases: ActionPhase[];
  dtw_metrics: { similarity_score: number; muda_detected_seconds: number };
  robot_trajectory_points: TrajectoryPoint[];
  analysis_result: AnalysisResult | null;
  analysis_image_urls: Record<'expert' | 'worker', Record<string, string>> | null;
  recording_url: string | null;
  source_data_url: string | null;
  sop_download_url: string | null;
  robot_json_url: string | null;
  robot_export_url: string | null;
  export_error: string | null;
}

export interface SessionListResponse {
  items: SessionSummary[];
  total: number;
  limit: number;
  offset: number;
}
