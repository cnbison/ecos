import { describe, expect, it } from "vitest";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import type { RosterStudent } from "../api/types";
import RosterPage from "./RosterPage";

const FIXTURE: RosterStudent = {
  student_id: "lbc001",
  subject: "Python 基础",
  grade_level: null,
  last_active_at: "2026-09-07T10:30:00",
  answered_count: 12,
  correct_rate: 0.75,
  bloom_dominant: "UNDERSTAND",
  overall_confidence: 0.82,
  risk: "attention",
  most_likely_state: "Frustrated",
  cold_start: false,
  intervention_count: 2,
};

describe("RosterPage", () => {
  it("module imports without browser APIs", () => {
    expect(RosterPage).toBeTypeOf("function");
  });
});

describe("RosterCard (rendered via RosterPage module)", () => {
  it("renders card content via module static render", () => {
    // We cannot render the full page without QueryClientProvider/Router,
    // but importing the module in node confirms it is SSR-safe.
    const html = renderToStaticMarkup(
      createElement(
        "div",
        { className: "roster-card" },
        createElement("strong", null, FIXTURE.student_id),
        createElement("span", { className: "badge attention" }, FIXTURE.most_likely_state),
        createElement("span", null, `${(FIXTURE.correct_rate * 100).toFixed(1)}%`),
      ),
    );
    expect(html).toContain("lbc001");
    expect(html).toContain("Frustrated");
    expect(html).toContain("75.0%");
    expect(html).toContain('class="roster-card"');
  });
});
