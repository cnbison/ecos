// v0.98.0 (a-c): 家长端 API 客户端 (fetch 封装, 无 silent 失败 — 跟 teacher/client.ts 同约定)
export type PomdpStateName = "Engaged" | "Frustrated" | "Bored" | "Confused" | string;

export interface AdviceEntry {
  trigger: string;
  severity: "info" | "warning" | "attention";
  message: string;
}

export interface EngagementReport {
  student_id: string;
  current_state: PomdpStateName;
  current_state_index: number;
  recent_states: PomdpStateName[];
  evolution_count: number;
  state_changed: boolean;
  cold_start: boolean;
  advice: AdviceEntry[];
  updated_at: string;
}

export interface ParentRosterStudent {
  student_id: string;
  subject: string | null;
  grade_level: string | null;
  last_active_at: string | null;
  answered_count: number;
  correct_rate: number;
  current_state: PomdpStateName | null;
}

export interface ParentRosterResponse {
  students: ParentRosterStudent[];
}

export interface FiveDOverview {
  mastery: Record<string, number> | null;
  bloom: {
    dominant: string | null;
    confidence: number;
    levels: Record<string, number>;
  } | null;
  overall_confidence: number;
}

export interface InterventionItem {
  intervention_id: string;
  timestamp: string;
  intervention_type?: string;
  rationale_text?: string | null;
  [key: string]: unknown;
}

export interface ParentOverviewResponse {
  student_id: string;
  subject: string | null;
  engagement: EngagementReport | null;
  five_d: FiveDOverview;
  interventions: InterventionItem[];
}

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: { Accept: "application/json" } });
  if (!resp.ok) throw new Error(`API ${path} 失败: HTTP ${resp.status}`);
  return (await resp.json()) as T;
}

export function fetchParentRoster(): Promise<ParentRosterResponse> {
  return getJson<ParentRosterResponse>("/api/parent/students");
}

export function fetchParentOverview(id: string): Promise<ParentOverviewResponse> {
  return getJson<ParentOverviewResponse>(
    `/api/parent/students/${encodeURIComponent(id)}/overview`,
  );
}
