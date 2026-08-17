// v0.96: 首页三卡 — 信息架构三问 (我在哪 / 我的成长 / 下一步学什么)
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchReport, fetchState } from "../api";
import MotivationPanel from "../components/MotivationPanel";

const DIM_ORDER = ["K", "P", "S", "C", "X"] as const;

export default function HomePage({ studentId }: { studentId: string }) {
  const navigate = useNavigate();
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
  if (report.isLoading || state.isLoading) return <p className="muted">加载今天学什么…</p>;

  const interp = report.data!.interpretation;
  const st = state.data!;
  const nextSteps = interp.next_steps;

  return (
    <div>
      <div className="home-cards">
        {/* 卡 1: 我在哪 */}
        <section className="home-card">
          <h3>📍 我在哪</h3>
          <p className="overall">{interp.overall}</p>
          <div className="muted" style={{ fontSize: 13, marginTop: 12 }}>
            Bloom 主导 {interp.bloom.dominant_label} · 置信{" "}
            {(st.overall_confidence * 100).toFixed(0)}%
          </div>
        </section>

        {/* 卡 2: 我的成长 */}
        <section className="home-card">
          <h3>📈 我的成长</h3>
          <div className="mini-5d">
            {DIM_ORDER.map((d) => {
              const v = st.theta[d];
              const pct = Math.round(((v + 2.5) / 5) * 100);
              return (
                <div className="row" key={d}>
                  <span>{d}</span>
                  <div className="track">
                    <div className="fill" style={{ width: `${Math.min(100, pct)}%` }} />
                  </div>
                  <span className="val">{v.toFixed(2)}</span>
                </div>
              );
            })}
          </div>
          <div className="muted" style={{ fontSize: 13, marginTop: 8 }}>
            已作答 {st.trajectory.length} 题 · 成长见「成长」页
          </div>
        </section>

        {/* 卡 3: 下一步学什么 */}
        <section className="home-card">
          <h3>🎯 下一步学什么</h3>
          <ul className="next-steps">
            {nextSteps.length === 0 && <li className="muted">样本不足，先答几道题建立画像</li>}
            {nextSteps.map((s, i) => (
              <li key={i}>{s}</li>
            ))}
          </ul>
          <button onClick={() => navigate("/answer")} className="green">
            开始做题 →
          </button>
        </section>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <h2>近况感知</h2>
        <MotivationPanel motivation={st.motivation} />
      </div>
    </div>
  );
}
