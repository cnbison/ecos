// v0.96: 学生端 API 客户端 (fetch 封装, 无 silent 失败 — 错误显式抛出)
import type { JudgeResult, Question, Report, StudentState } from "./types";

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: { Accept: "application/json" } });
  if (!resp.ok) throw new Error(`API ${path} 失败: HTTP ${resp.status}`);
  return (await resp.json()) as T;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!resp.ok) throw new Error(`POST ${path} 失败: HTTP ${resp.status}`);
  return (await resp.json()) as T;
}

export function fetchState(sid: string): Promise<StudentState> {
  return getJson<StudentState>(`/api/state/${encodeURIComponent(sid)}`);
}

export function fetchReport(sid: string): Promise<Report> {
  return getJson<Report>(`/api/report/${encodeURIComponent(sid)}`);
}

export function fetchQuestion(sid: string): Promise<Question> {
  return getJson<Question>(`/api/question/${encodeURIComponent(sid)}`);
}

export function fetchRecentStudents(): Promise<{ students: string[] }> {
  return getJson<{ students: string[] }>("/api/students/recent");
}

export interface HistoryItem {
  problem_id: string;
  correct: boolean;
  bloom_level?: string;
  user_answer?: string | null;
  correct_answer?: string | null;
  timestamp?: string | null;
}

export function fetchHistory(sid: string): Promise<{
  items: HistoryItem[];
  total: number;
  correct_rate: number;
}> {
  return getJson<{ items: HistoryItem[]; total: number; correct_rate: number }>(
    `/api/history/${encodeURIComponent(sid)}`,
  );
}

export function judgeAnswer(body: {
  student_id: string;
  problem_id: string;
  user_answer: string;
}): Promise<JudgeResult> {
  return postJson<JudgeResult>("/api/judge", body);
}

export function submitAnswer(body: {
  student_id: string;
  problem_id: string;
  skill_id: string;
  correct: boolean;
  score: number;
  bloom_layer: string;
  user_answer: string;
  correct_answer: string;
  reasoning: string;
}): Promise<{ student_id: string }> {
  return postJson<{ student_id: string }>("/api/answer", body);
}

// v0.95.0: 4 行为事件 (best-effort 遥测, 失败 console.warn 不打断答题 — 不 silent pass)
// v0.96.7: 返回响应体 (hint 端点携带规则生成的提示内容), 失败仍不打断答题
export async function emitEvent(
  kind: "hint" | "idle" | "goal_change" | "reflection",
  payload: Record<string, unknown>,
): Promise<Record<string, unknown> | undefined> {
  try {
    return await postJson(`/api/event/${kind}`, payload);
  } catch (e) {
    console.warn(`emitEvent ${kind} 失败:`, e);
    return undefined;
  }
}
