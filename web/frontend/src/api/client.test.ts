// v0.95.1: vitest 最小集 — 端点契约 + URL 编码 (check_defensive.sh 前端段)
import { describe, expect, it } from "vitest";
import { TEACHER_ENDPOINTS } from "./client";

describe("teacher API endpoint contract", () => {
  it("roster path", () => {
    expect(TEACHER_ENDPOINTS.roster).toBe("/api/teacher/students");
  });

  it("student detail path", () => {
    expect(TEACHER_ENDPOINTS.student("lbc001")).toBe("/api/teacher/students/lbc001");
  });

  it("evidence path", () => {
    expect(TEACHER_ENDPOINTS.evidence("lbc001")).toBe(
      "/api/teacher/students/lbc001/evidence",
    );
  });

  it("diagnostic path", () => {
    expect(TEACHER_ENDPOINTS.diagnostic("lbc001")).toBe(
      "/api/teacher/students/lbc001/diagnostic",
    );
  });

  it("interventions path", () => {
    expect(TEACHER_ENDPOINTS.interventions("lbc001")).toBe(
      "/api/teacher/students/lbc001/interventions",
    );
  });
});
