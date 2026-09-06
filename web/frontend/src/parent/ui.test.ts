// v0.98.0 (a-c): 家长端展示 helpers 测试 (3 tests)
import { describe, expect, it } from "vitest";
import {
  formatCorrectRate,
  severityBadgeClass,
  stateBadgeClass,
  stateLabel,
} from "./ui";

describe("stateLabel", () => {
  it("POMDP 状态名映射家长可读中文, null 返暂无数据", () => {
    expect(stateLabel("Engaged")).toBe("投入");
    expect(stateLabel("Frustrated")).toBe("受挫");
    expect(stateLabel("Bored")).toBe("无聊");
    expect(stateLabel("Confused")).toBe("困惑");
    expect(stateLabel(null)).toBe("暂无数据");
    expect(stateLabel(undefined)).toBe("暂无数据");
  });
});

describe("severityBadgeClass", () => {
  it("severity 三档映射三色徽标", () => {
    expect(severityBadgeClass("info")).toBe("badge ok");
    expect(severityBadgeClass("warning")).toBe("badge cold");
    expect(severityBadgeClass("attention")).toBe("badge attention");
  });
});

describe("formatCorrectRate + stateBadgeClass", () => {
  it("正确率百分比格式化; Engaged 正向徽标, 其他状态中性/警示", () => {
    expect(formatCorrectRate(0.5)).toBe("50.0%");
    expect(formatCorrectRate(null)).toBe("—");
    expect(stateBadgeClass("Engaged")).toBe("badge ok");
    expect(stateBadgeClass("Bored")).toBe("badge cold");
    expect(stateBadgeClass(null)).toBe("badge");
  });
});
