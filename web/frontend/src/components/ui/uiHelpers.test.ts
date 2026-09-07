import { describe, expect, it } from "vitest";
import { cx, severityBorderClass, severityColor } from "./uiHelpers";

describe("cx", () => {
  it("joins truthy class names", () => {
    expect(cx("a", "b", "c")).toBe("a b c");
  });

  it("filters falsy values", () => {
    expect(cx("a", false, null, undefined, "b")).toBe("a b");
  });

  it("returns empty string when all falsy", () => {
    expect(cx(false, null, undefined)).toBe("");
  });
});

describe("severityColor", () => {
  it("maps known severities to CSS variables", () => {
    expect(severityColor("info")).toBe("var(--ok)");
    expect(severityColor("warning")).toBe("var(--warn)");
    expect(severityColor("attention")).toBe("var(--danger)");
  });

  it("falls back to muted for unknown severity", () => {
    expect(severityColor("unknown")).toBe("var(--muted)");
  });
});

describe("severityBorderClass", () => {
  it("maps known severities to border classes", () => {
    expect(severityBorderClass("info")).toBe("ui-border-ok");
    expect(severityBorderClass("warning")).toBe("ui-border-warn");
    expect(severityBorderClass("attention")).toBe("ui-border-danger");
  });

  it("falls back to muted border class for unknown severity", () => {
    expect(severityBorderClass("unknown")).toBe("ui-border-muted");
  });
});
