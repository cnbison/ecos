// v0.96: 我在哪 — 5D/Bloom/TC/LearningDNA 通俗化呈现 (interpretation 全接)
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
      {/* 5D 维度解读 */}
      <section className="card">
        <h2>📊 五项能力</h2>
        <div className="where-5d">
          {DIM_ORDER.map((d) => {
            const v = interp.five_d[d];
            if (!v) return null;
            const pct = Math.round(((v.theta + 2.5) / 5) * 100);
            return (
              <div className="where-5d-row" key={d}>
                <div className="where-5d-head">
                  <span className="badge">{d}</span>
                  <span className="f-name">{v.name}</span>
                  <span className={`report-tag ${LEVEL_TAG_CLASS[v.level] ?? ""}`}>
                    {v.level_label}
                  </span>
                  <span className="val">{v.theta.toFixed(2)}</span>
                </div>
                <div className="track">
                  <div className="fill" style={{ width: `${Math.min(100, pct)}%` }} />
                </div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {v.comment}
                </div>
              </div>
            );
          })}
        </div>
      </section>

      {/* Bloom 认知深度 */}
      <section className="card">
        <h2>🎯 认知深度 (Bloom)</h2>
        <div className="muted">
          主导层 <strong>{interp.bloom.dominant_label || "—"}</strong>
          {interp.bloom.next_layer && (
            <>
              {" "}
              · 下一层 <strong>{interp.bloom.next_layer}</strong>（gap{" "}
              {interp.bloom.gap_to_next?.toFixed(3) ?? "—"}）
            </>
          )}
        </div>
        <div className="bloom-rows">
          {(["L1", "L2", "L3", "L4", "L5", "L6"] as const).map((lvl) => {
            const probed = st.bloom_profile.bloom_levels[lvl] !== undefined;
            const v = st.bloom_profile.bloom_levels[lvl];
            const isProbed = probed && Math.abs((v ?? 0.5) - 0.5) > 0.01;
            const pct = Math.round((v ?? 0.5) * 100);
            return (
              <div className="br" key={lvl}>
                <span className="b-lbl">{lvl}</span>
                <span className="b-name">{BLOOM_LABELS[lvl]}</span>
                <div className="fill">
                  <div
                    className={isProbed ? "" : "unprobed-bar"}
                    style={isProbed ? { width: `${pct}%` } : undefined}
                  />
                </div>
                <span className="pct">{isProbed ? `${pct}%` : "—"}</span>
              </div>
            );
          })}
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          {interp.bloom.comment}
        </p>
      </section>

      {/* 阈值概念 TC */}
      <section className="card">
        <h2>🧠 关键概念掌握</h2>
        <p className="muted" style={{ fontSize: 12 }}>
          {interp.tc.comment}
        </p>
        {interp.tc.topics.length === 0 && (
          <div className="muted">暂无 TC 数据（答对高水平题触发）</div>
        )}
        {interp.tc.topics.map((t) => (
          <div className="row" key={t.id}>
            <span>{t.id}</span>
            <div className="track">
              <div
                className="fill"
                style={{ width: `${Math.round(t.progress * 100)}%` }}
              />
            </div>
            <span className="val">
              {t.tag} {Math.round(t.progress * 100)}%
            </span>
          </div>
        ))}
      </section>

      {/* LearningDNA 待启用 */}
      <section className="card">
        <h2>🧬 学习特质 <span className="badge cold">待启用</span></h2>
        <p className="muted" style={{ fontSize: 12 }}>
          学习特质画像（输入/反馈偏好等）将在数据积累后启用，暂不展示分项。
        </p>
      </section>
    </div>
  );
}
