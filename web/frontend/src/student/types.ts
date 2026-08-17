// v0.96: 学生端 API 类型 (跟 web/api/app.py / interpretation.py 返回契约对齐)

export interface Theta5D {
  K: number;
  P: number;
  S: number;
  C: number;
  X: number;
}

export interface BloomProfile {
  dominant: string | null;
  confidence: number;
  bloom_levels: { L1: number; L2: number; L3: number; L4: number; L5: number; L6: number };
}

export interface TcState {
  id: string;
  status: string;
  progress: number;
  confidence: number;
  irreversible: boolean;
}

export interface LearningDna {
  input_preference: string;
  feedback_preference: string;
  confidence: number;
}

export interface TrajectorySnapshot {
  timestamp: string;
  theta_5d: number[];
  confidence: number;
  bloom_dominant: string | null;
}

export interface Motivation {
  frustration: number;
  engagement: number;
  confidence: number;
  observation_count: number;
}

export interface StudentState {
  student_id: string;
  theta: Theta5D;
  theta_cov_diag: Theta5D;
  theta_confidence: Theta5D;
  theta_se: Theta5D;
  bloom_profile: BloomProfile;
  bloom_layer_distance: { next: string | null; gap: number } | null;
  tc_states: TcState[];
  learning_dna: LearningDna;
  trajectory: TrajectorySnapshot[];
  misc_history: unknown[];
  overall_confidence: number;
  c_discount_factor: number;
  motivation: Motivation;
  is_warmup: boolean;
  warmup_count?: number;
  warmup_total?: number;
}

export interface Question {
  problem_id: string;
  bloom_goal_id: string;
  topic: string;
  skill_name: string;
  bloom_layer: string;
  problem_text: string;
  misconceptions: string[];
  intervention_types: string[];
  is_warmup: boolean;
  strategy: string;
  warmup_group?: string;
  adaptive_dim_star?: string;
  is_probe: boolean;
  probe_dim_star?: string;
  lca_decision?: {
    intervention_type: string;
    bloom_target: string;
    clt_level: string;
    ca_stage: string;
    expected_gain: number;
    expected_risk: number;
  };
}

export interface JudgeResult {
  judged: boolean;
  problem_id?: string;
  student_id?: string;
  correct?: boolean;
  score?: number;
  reasoning?: string;
  attempts?: number;
  error?: string;
  error_code?: string;
  needs_rejudge?: boolean;
}

export interface Interpretation {
  overall: string;
  five_d: Record<
    string,
    {
      name: string;
      theta: number;
      confidence: number;
      level: "strong" | "medium" | "weak";
      level_label: string;
      tag: string;
      comment: string;
    }
  >;
  bloom: {
    dominant: string;
    dominant_label: string;
    levels: Record<string, number>;
    next_layer: string | null;
    gap_to_next: number | null;
    unprobed_layers: string[];
    comment: string;
  };
  tc: {
    topics: Array<{ id: string; progress: number; status: string; tag: string }>;
    approaching_liminal: string[];
    progressing: string[];
    untouched: string[];
    comment: string;
  };
  trajectory: {
    length: number;
    first_timestamp: string | null;
    last_timestamp: string | null;
    delta_5d: Theta5D;
    trend: string;
    significant_dims: string[];
    comment: string;
  };
  next_steps: string[];
}

export interface Report {
  student_id: string;
  generated_at: string;
  ecos_version: string;
  summary: {
    answered_count: number;
    current_bloom_layer: string;
    bloom_layer_distance: unknown;
    warmup_complete: boolean;
    overall_confidence: number;
  };
  interpretation: Interpretation;
  state: StudentState;
}
