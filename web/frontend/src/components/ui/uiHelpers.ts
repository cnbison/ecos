// v0.98.2-P0: UI 纯函数 helpers (className 组合 + severity 映射)

/** 过滤 falsy 值, 用空格拼接 className */
export function cx(...classes: Array<string | false | null | undefined>): string {
  return classes.filter(Boolean).join(" ");
}

export type Severity = "info" | "warning" | "attention";

/** severity → 语义化 CSS 颜色变量 */
export function severityColor(severity: Severity | string): string {
  switch (severity) {
    case "info":
      return "var(--ok)";
    case "warning":
      return "var(--warn)";
    case "attention":
      return "var(--danger)";
    default:
      return "var(--muted)";
  }
}

/** severity → 边框/强调色 class (用于左侧色条等) */
export function severityBorderClass(severity: Severity | string): string {
  switch (severity) {
    case "info":
      return "ui-border-ok";
    case "warning":
      return "ui-border-warn";
    case "attention":
      return "ui-border-danger";
    default:
      return "ui-border-muted";
  }
}
