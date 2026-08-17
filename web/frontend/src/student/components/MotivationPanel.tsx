// v0.96-b: 动机层呈现 (克制成长反馈 — 不做游戏化堆砌, 守"情感陪伴明确不做"边界)
// 3 维: 投入度 engagement / 信心 confidence / 挫败感 frustration (越低越好)
import type { Motivation } from "../types";

export default function MotivationPanel({ motivation }: { motivation: Motivation }) {
  const rows = [
    { key: "engagement", label: "投入度", value: motivation.engagement, good: "高" },
    { key: "confidence", label: "信心", value: motivation.confidence, good: "高" },
    { key: "frustration", label: "挫败感", value: motivation.frustration, good: "低" },
  ] as const;

  return (
    <div className="motivation">
      <div className="motivation-note muted" style={{ fontSize: 13, marginBottom: 10 }}>
        近况感知 (基于最近答题行为, {motivation.observation_count} 条观测)
      </div>
      <div className="grid-5d">
        {rows.map((r) => (
          <div key={r.key} className="dim-card">
            <div className="dim-head">
              <span className="dim-key" style={{ fontSize: 14 }}>
                {r.label}
              </span>
            </div>
            <div className="mot-bar">
              <div
                className="mot-bar-fill"
                style={{
                  width: `${Math.round(Math.min(1, Math.max(0, r.value)) * 100)}%`,
                }}
              />
            </div>
            <div className="muted" style={{ fontSize: 12, marginTop: 6 }}>
              {(r.value * 100).toFixed(0)}% · 偏低表示{r.key === "frustration" ? "状态良好" : "需关注"}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
