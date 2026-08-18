// v0.96: 我的成长 — 5D 折线 (ECharts) + 轨迹趋势 + 答题历史
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import type { EChartsOption } from "echarts";
import { fetchHistory, fetchReport, fetchState } from "../api";
import EChart from "../../components/EChart";

const DIM_ORDER = ["K", "P", "S", "C", "X"] as const;
const DIM_COLORS = ["#1e40af", "#7c3aed", "#059669", "#ea580c", "#0891b2"];

// v0.96.4: /api 返回 BloomLevel 枚举名 ("APPLY"), 映射为用户可读 "L3 应用"
const BLOOM_LABEL: Record<string, string> = {
  REMEMBER: "L1 记忆",
  UNDERSTAND: "L2 理解",
  APPLY: "L3 应用",
  ANALYZE: "L4 分析",
  EVALUATE: "L5 评价",
  CREATE: "L6 创造",
};
function bloomLabel(v?: string | null): string {
  return v ? (BLOOM_LABEL[v] ?? v) : "—";
}

function fmtTs(iso?: string | null): string {
  if (!iso) return "—";
  const m = iso.match(/^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})/);
  return m ? `${m[1]} ${m[2]}` : iso;
}

export default function GrowthPage({ studentId }: { studentId: string }) {
  const [openDetail, setOpenDetail] = useState<number | null>(null);
  const state = useQuery({
    queryKey: ["state", studentId],
    queryFn: () => fetchState(studentId),
  });
  const report = useQuery({
    queryKey: ["report", studentId],
    queryFn: () => fetchReport(studentId),
  });
  const history = useQuery({
    queryKey: ["history", studentId],
    queryFn: () => fetchHistory(studentId),
  });

  const lineOption = useMemo<EChartsOption | null>(() => {
    const traj = state.data?.trajectory ?? [];
    if (traj.length < 2) return null;
    const times = traj.map((t) => fmtTs(t.timestamp).slice(5));
    return {
      tooltip: { trigger: "axis" },
      legend: { data: [...DIM_ORDER], top: 0, textStyle: { fontSize: 11 } },
      grid: { left: 40, right: 12, top: 30, bottom: 24 },
      xAxis: { type: "category", data: times, axisLabel: { fontSize: 10 } },
      yAxis: { type: "value", scale: true, axisLabel: { fontSize: 10 } },
      series: DIM_ORDER.map((d, i) => ({
        name: d,
        type: "line" as const,
        smooth: true,
        showSymbol: false,
        data: traj.map((t) => t.theta_5d[i] ?? null),
        lineStyle: { width: 2, color: DIM_COLORS[i] },
        itemStyle: { color: DIM_COLORS[i] },
      })),
    };
  }, [state.data?.trajectory]);

  if (state.isError || report.isError || history.isError) {
    return <div className="error-box">成长数据加载失败</div>;
  }
  if (state.isLoading || report.isLoading || history.isLoading) {
    return <p className="muted">加载成长轨迹…</p>;
  }

  const st = state.data!;
  const interp = report.data!.interpretation;
  const hist = history.data!;

  return (
    <div className="growth-page">
      <section className="card">
        <h2>📈 5D 成长曲线</h2>
        {lineOption ? (
          <EChart option={lineOption} height={280} />
        ) : (
          <p className="muted">样本不足 2 个轨迹点，先答几道题看看曲线</p>
        )}
        <div className="muted" style={{ fontSize: 12, marginTop: 8 }}>
          {interp.trajectory.trend}（共 {st.trajectory.length} 个轨迹点）
        </div>
        {interp.trajectory.delta_5d && (
          <div className="delta-chips">
            {(Object.entries(interp.trajectory.delta_5d) as Array<[string, number]>).map(
              ([dim, val]) => (
                <span
                  key={dim}
                  className={`delta-chip ${val > 0.01 ? "up" : val < -0.01 ? "down" : ""}`}
                >
                  {dim} {val > 0 ? "+" : ""}
                  {val.toFixed(2)}
                </span>
              ),
            )}
          </div>
        )}
        <p className="muted" style={{ fontSize: 12 }}>
          {interp.trajectory.comment}
        </p>
      </section>

      <section className="card">
        <h2>🕒 轨迹快照</h2>
        <div className="traj-list">
          {st.trajectory.length === 0 && <div className="muted">暂无轨迹</div>}
          {[...st.trajectory].reverse().map((t, i) => (
            <div className="traj-row" key={i}>
              <span className="traj-ts">{fmtTs(t.timestamp)}</span>
              {DIM_ORDER.map((d, di) => (
                <span className="traj-dim" key={d}>
                  {d}
                  {t.theta_5d[di]?.toFixed(2) ?? "—"}
                </span>
              ))}
              <span className="traj-bloom">{bloomLabel(t.bloom_dominant)}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card">
        <h2>📚 答题历史</h2>
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
          共 {hist.total} 题 · 正确率 {(hist.correct_rate * 100).toFixed(0)}%
        </div>
        {hist.items.length === 0 && <div className="muted">还没有答题记录</div>}
        {hist.items.map((h, i) => (
          <div key={h.problem_id + i}>
            <button
              className={`hist-row ${h.correct ? "correct" : "wrong"}`}
              onClick={() => setOpenDetail(openDetail === i ? null : i)}
            >
              <span className="hist-mark">{h.correct ? "✅" : "❌"}</span>
              <span className="hist-pid">{h.problem_id}</span>
              <span className="hist-bloom">{bloomLabel(h.bloom_level)}</span>
              <span className="hist-ts">{fmtTs(h.timestamp)}</span>
            </button>
            {openDetail === i && (
              <div className="hist-detail">
                <div className="label">你的答案：</div>
                <div className="val">{h.user_answer || "(空)"}</div>
                <div className="label" style={{ marginTop: 6 }}>
                  正确答案：
                </div>
                <div className="val">{h.correct_answer || "(未存)"}</div>
              </div>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
