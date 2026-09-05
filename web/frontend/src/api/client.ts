// v0.95.1: Teacher API 客户端 (fetch 封装, 无 silent 失败 — 错误显式抛出)
import type {
  CalibrationResponse,
  DiagnosticResponse,
  EvidenceResponse,
  InterventionsResponse,
  RosterResponse,
  StudentDetail,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const resp = await fetch(path, { headers: { Accept: "application/json" } });
  if (!resp.ok) {
    throw new Error(`API ${path} 失败: HTTP ${resp.status}`);
  }
  return (await resp.json()) as T;
}

export function fetchRoster(): Promise<RosterResponse> {
  return getJson<RosterResponse>("/api/teacher/students");
}

export function fetchStudentDetail(id: string): Promise<StudentDetail> {
  return getJson<StudentDetail>(`/api/teacher/students/${encodeURIComponent(id)}`);
}

export function fetchEvidence(id: string): Promise<EvidenceResponse> {
  return getJson<EvidenceResponse>(`/api/teacher/students/${encodeURIComponent(id)}/evidence`);
}

export function fetchDiagnostic(id: string): Promise<DiagnosticResponse> {
  return getJson<DiagnosticResponse>(`/api/teacher/students/${encodeURIComponent(id)}/diagnostic`);
}

export function fetchInterventions(id: string): Promise<InterventionsResponse> {
  return getJson<InterventionsResponse>(`/api/teacher/students/${encodeURIComponent(id)}/interventions`);
}

// v0.97.2: 自评校准视图
export function fetchCalibration(id: string): Promise<CalibrationResponse> {
  return getJson<CalibrationResponse>(`/api/teacher/students/${encodeURIComponent(id)}/calibration`);
}

// 供 vitest 校验的端点契约 (跟 teacher.py 路由逐条对应)
export const TEACHER_ENDPOINTS = {
  roster: "/api/teacher/students",
  student: (id: string) => `/api/teacher/students/${id}`,
  evidence: (id: string) => `/api/teacher/students/${id}/evidence`,
  diagnostic: (id: string) => `/api/teacher/students/${id}/diagnostic`,
  interventions: (id: string) => `/api/teacher/students/${id}/interventions`,
  calibration: (id: string) => `/api/teacher/students/${id}/calibration`,
} as const;
