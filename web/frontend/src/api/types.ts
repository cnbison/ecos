// v0.95.1: Teacher API 响应类型 (跟 web/api/teacher.py 返回契约逐字段对齐)

export interface RosterStudent {
  student_id: string;
  last_active_at: string | null;
  subject: string | null;
  grade_level: string | null;
  answered_count: number;
  correct_rate: number;
  bloom_dominant: string | null;
  overall_confidence: number;
  cold_start: boolean | null;
  most_likely_state: string | null;
  risk: "ok" | "attention";
  intervention_count: number;
}

export interface RosterResponse {
  students: RosterStudent[];
}

export interface BloomProfile {
  dominant: string | null;
  confidence: number;
  levels: { L1: number; L2: number; L3: number; L4: number; L5: number; L6: number };
}

export interface Theta5D {
  K: number;
  P: number;
  S: number;
  C: number;
  X: number;
}

export interface ProgressReport {
  student_id: string;
  most_likely_state: string;
  most_likely_state_index: number;
  belief: number[];
  min_coverage: number;
  cold_start: boolean;
  advice: string;
  updated_at: string | null;
}

export interface StudentDetail {
  student_id: string;
  answered_count: number;
  correct_rate: number;
  bloom_profile: BloomProfile | null;
  theta_5d: Theta5D | null;
  overall_confidence: number;
  report: ProgressReport | null;
  trajectory_summary: Array<{
    timestamp: string | null;
    theta_5d: number[] | null;
    confidence: number | null;
    bloom_dominant: string | null;
  }>;
}

export interface EvidenceResponseItem {
  problem_id: string;
  correct: boolean;
  score: number;
  bloom_level: string | null;
  timestamp: string | null;
  user_answer: string | null;
  correct_answer: string | null;
  ai_reasoning: string | null;
}

export interface DimensionEvidence {
  label: string;
  full: string;
  desc: string;
  theta: number;
  se: number;
  confidence: number;
  mastered: boolean;
  response_count: number;
  correct_rate: number;
  responses: EvidenceResponseItem[];
}

export interface Misconception {
  misc_id: string;
  confidence: number;
  timestamp: string | null;
}

export interface TcState {
  id: string;
  status: string;
  progress: number;
  confidence: number;
  irreversible: boolean;
}

export interface EvidenceResponse {
  student_id: string;
  summary: { answered_count: number; correct_rate: number };
  dimensions: Record<"K" | "P" | "S" | "C" | "X", DimensionEvidence>;
  misconceptions: Misconception[];
  tc_states: TcState[];
}

export interface DiagnosticResponse {
  student_id: string;
  diagnostic: Record<string, unknown> | null;
  report: ProgressReport | null;
  pomdp_state_names: string[];
}

export interface InterventionsResponse {
  student_id: string;
  interventions: Array<Record<string, unknown>>;
}

// v0.97.2: 自评校准视图 (teacher.py /calibration)
export interface CalibrationCurvePoint {
  bucket: string;
  n: number;
  correct: number;
  predicted: number;
  actual_rate: number;
  correction_factor: number;
}

export interface CalibrationResponse {
  student_id: string;
  has_data: boolean;
  n_total: number;
  n_self_assessed: number;
  n_skipped: number;
  curves: CalibrationCurvePoint[];
}
