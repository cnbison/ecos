// v0.98.0 (a-c): 家长端展示 helpers (纯函数, vitest 覆盖)
import type { AdviceEntry, PomdpStateName } from "./api";

/** POMDP 状态名 → 家长可读中文 */
export function stateLabel(state: PomdpStateName | null | undefined): string {
  if (!state) return "暂无数据";
  switch (state) {
    case "Engaged":
      return "投入";
    case "Frustrated":
      return "受挫";
    case "Bored":
      return "无聊";
    case "Confused":
      return "困惑";
    default:
      return String(state);
  }
}

/** 状态 → 徽标 CSS class (index.css 对齐: badge ok / badge cold / badge attention) */
export function stateBadgeClass(state: PomdpStateName | null | undefined): string {
  if (state === "Engaged") return "badge ok";
  if (state === "Frustrated" || state === "Bored") return "badge cold";
  if (state === "Confused") return "badge attention";
  return "badge";
}

/** 建议条目 → 徽标 class (severity 三档) */
export function severityBadgeClass(severity: AdviceEntry["severity"]): string {
  switch (severity) {
    case "info":
      return "badge ok";
    case "warning":
      return "badge cold";
    case "attention":
      return "badge attention";
    default:
      return "badge";
  }
}

/** 正确率格式化 (无数据显示 —) */
export function formatCorrectRate(rate: number | undefined | null): string {
  if (rate === undefined || rate === null) return "—";
  return `${(rate * 100).toFixed(1)}%`;
}
