// v0.96.3: 我在哪 — 5D/Bloom/TC/LearningDNA 通俗化呈现 (interpretation 全接)
// 视觉统一: 顶部概览 hero + 5D 每维独立色 + 全页统一 track/fill 条样式
import { useQuery } from "@tanstack/react-query";
import { fetchReport, fetchState } from "../api";

const DIM_ORDER = ["K", "P", "S", "C", "X"] as const;
const BLOOM_LABELS: Record<string, string> = {
  L1: "记忆",
  L2: "理解",
  L3: "应用",
  L4: "分析",
  L5: "评价",
  L6: "创造",
};
const LEVEL_TAG_CLASS: Record<string, string> = {
  strong: "ok",
  medium: "",
  weak: "attention",
};
// v0.96.3: 5D 每维独立主题色 (badge 底色 + 进度条), 打破整页单色堆叠
const DIM_STYLE: Record<string, { badge: string; fill: string }> = {
  K: { badge: "#eff6ff", fill: "#3b82f6" },
  P: { badge: "#ecfdf5", fill: "#10b981" },
  S: { badge: "#fffbeb", fill: "#f59e0b" },
  C: { badge: "#f5f3ff", fill: "#8b5cf6" },
  X: { badge: "#ecfeff", fill: "#06b6d4" },
};

export default function WherePage({ studentId }: { studentId: string }) {
  const report = useQuery({
    queryKey: ["report", studentId],
    queryFn: () => fetchReport(studentId),
  });
  const state = useQuery({
    queryKey: ["state", studentId],
    queryFn: () => fetchState(studentId),
  });

  if (report.isError || state.isError) {
    return <div className="error-box">学习画像加载失败（请确认学生 ID 有效）</div>;
  }
  if (report.isLoading || state.isLoading) return <p className="muted">加载画像…</p>;

  const interp = report.data!.interpretation;
  const st = state.data!;

  return (
    <div className="where-page">
      {/* 顶部整体概览 */}
      <section className="card where-hero">
        <div className="where-hero-head">
          <h2>📍 我在哪</h2>
          <span className="where-hero-conf">画像置信 {(st.overall_confidence * 100).toFixed(0)}%</span>
        </div>
        <p className="where-hero-overall">{interp.overall}</p>
        <div className="where-hero-chips">
          <span className="chip ok">
            🎯 Bloom 主导 · <strong>{interp.bloom.dominant_label || "—"}</strong>
          </span>
          {interp.bloom.next_layer && (
            <span className="chip">
              下一层 <strong>{interp.bloom.next_layer}</strong>（gap{" "}
              {interp.bloom.gap_to_next?.toFixed(3) ?? "—"}）
            </span>
          )}
        </div>
      </section>

      {/* 五项能力 */}
      <section className="card">
        <div className="sec-head">
          <h2>📊 五项能力</h2>
          <span className="sec-sub">认知状态 5 维</span>
        </div>
        <div className="where-5d">
          {DIM_ORDER.map((d) => {
            const v = interp.five_d[d];
            if (!v) return null;
            const style = DIM_STYLE[d];
            const pct = Math.round(((v.theta + 2.5) / 5) * 100);
            return (
              <div className="dim-row" key={d}>
                <div className="dim-row-head">
                  <span className="dim-badge" style={{ background: style.badge, color: style.fill }}>
                    {d}
                  </span>
                  <span className="dim-name">{v.name}</span>
                  <span className={`report-tag ${LEVEL_TAG_CLASS[v.level] ?? ""}`}>
                    {v.level_label}
                  </span>
                  <span className="dim-val">{v.theta.toFixed(2)}</span>
                </div>
                <div className="track">
                  <div
                    className="fill"
                    style={{ width: `${Math.min(100, pct)}%`, background: style.fill }}
                  />
                </div>
                <div className="dim-comment">{v.comment}</div>
              </div>
            );
          })}
        </div>
      </section>

      {/* 认知深度 (Bloom) */}
      <section className="card">
        <div className="sec-head">
          <h2>🎯 认知深度</h2>
          <span className="sec-sub">Bloom 六层</span>
        </div>
        <div className="bloom-rows">
          {(["L1", "L2", "L3", "L4", "L5", "L6"] as const).map((lvl) => {
            const probed = st.bloom_profile.bloom_levels[lvl] !== undefined;
            const v = st.bloom_profile.bloom_levels[lvl];
            const isProbed = probed && Math.abs((v ?? 0.5) - 0.5) > 0.01;
            const isDominant = interp.bloom.dominant === lvl;
            const pct = Math.round((v ?? 0.5) * 100);
            return (
              <div className={`br${isDominant ? " dominant" : ""}`} key={lvl}>
                <span className="b-lbl">{lvl}</span>
                <span className="b-name">{BLOOM_LABELS[lvl]}</span>
                <div className="track">
                  {isProbed ? (
                    <div className="fill" style={{ width: `${pct}%` }} />
                  ) : (
                    <div className="fill unprobed" />
                  )}
                </div>
                <span className="pct">{isProbed ? `${pct}%` : "—"}</span>
              </div>
            );
          })}
        </div>
        <p className="where-comment">{interp.bloom.comment}</p>
      </section>

      {/* 阈值概念 TC */}
      <section className="card">
        <div className="sec-head">
          <h2>🧠 关键概念掌握</h2>
          <span className="sec-sub">阈值概念 TC</span>
        </div>
        <p className="where-comment">{interp.tc.comment}</p>
        {interp.tc.topics.length === 0 && (
          <div className="empty-state">暂无 TC 数据（答对高水平题触发）</div>
        )}
        {interp.tc.topics.map((t) => (
          <div className="row" key={t.id}>
            <span className="row-label">{t.id}</span>
            <div className="track">
              <div className="fill" style={{ width: `${Math.round(t.progress * 100)}%` }} />
            </div>
            <span className="val">
              {t.tag} {Math.round(t.progress * 100)}%
            </span>
          </div>
        ))}
      </section>

      {/* LearningDNA 待启用 */}
      <section className="card">
        <div className="sec-head">
          <h2>🧬 学习特质</h2>
          <span className="badge cold">待启用</span>
        </div>
        <p className="where-comment">
          学习特质画像（输入/反馈偏好等）将在数据积累后启用，暂不展示分项。
        </p>
      </section>
    </div>
  );
}
