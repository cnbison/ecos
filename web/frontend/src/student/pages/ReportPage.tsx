// v0.99.4 (F-01): 学习报告页 — HTML 渲染 /api/report 的 interpretation 为主体,
// window.print() 打印即 PDF (方案 C, F-01 已拍板); JSON 原始数据导出保留在设置页次按钮。
// 数据契约: student/types.ts Report (summary + interpretation 六段), 与
// web/api/interpretation.py build_interpretation 输出对齐。
import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import Icon from "../../components/ui/Icon";
import { FileText, Printer } from "../../components/ui/icons";
import { fetchReport } from "../api";
import type { Report } from "../types";

const DIM_ORDER = ["K", "P", "S", "C", "X"] as const;

function pct(v: number | undefined | null): string {
  return v === undefined || v === null ? "—" : `${(v * 100).toFixed(0)}%`;
}

function fmt2(v: number | undefined | null): string {
  return v === undefined || v === null ? "—" : v.toFixed(2);
}

export default function ReportPage({ studentId }: { studentId: string }) {
  const report = useQuery({
    queryKey: ["report", studentId],
    queryFn: () => fetchReport(studentId),
  });

  if (report.isLoading) return <p className="muted">生成报告中…</p>;
  if (report.isError || !report.data) {
    return <div className="error-box">报告加载失败（请稍后重试）</div>;
  }

  const r: Report = report.data;
  const interp = r.interpretation;
  const summary = r.summary;
  // interpretation 失败时后端降级为 {error: string} (app.py 666-669), 此时六段缺失
  const interpAvailable = !("error" in interp);

  return (
    <div className="report-page" style={{ maxWidth: 720, margin: "0 auto" }}>
      {/* 打印控制行 (打印时隐藏) */}
      <div className="print-hide" style={{ display: "flex", gap: 10, marginBottom: 14 }}>
        <button className="amber" onClick={() => window.print()}>
          <Icon icon={Printer} size={16} /> 打印 / 存为 PDF
        </button>
        <NavLink className="go-link" to="/settings" style={{ alignSelf: "center" }}>
          ← 返回设置
        </NavLink>
      </div>

      <div className="card">
        <h2><Icon icon={FileText} size={20} /> 学习报告</h2>
        <div className="muted" style={{ fontSize: 13, lineHeight: 1.8 }}>
          <div>学生：{r.student_id} · 生成时间：{r.generated_at.slice(0, 16).replace("T", " ")}</div>
          <div>
            已答题数：{summary.answered_count} · 整体置信度：{pct(summary.overall_confidence)}
            {summary.warmup_complete ? "" : ` · 热身中 (${summary.warmup_progress?.count ?? 0}/${summary.warmup_progress?.total ?? 5})`}
          </div>
          <div>ECOS v{r.ecos_version} · 规则引擎生成（无 LLM 参与，离线可复算）</div>
        </div>

        {!interpAvailable ? (
          <div className="error-box" style={{ marginTop: 12 }}>
            解读生成失败：{(interp as { error?: string }).error}
          </div>
        ) : (
          <>
            {/* 总评 */}
            <section style={{ marginTop: 16 }}>
              <h3>总评</h3>
              <p style={{ lineHeight: 1.8 }}>{interp.overall}</p>
            </section>

            {/* 5D 画像 */}
            <section style={{ marginTop: 16 }}>
              <h3>五维画像（K 知识 / P 实践 / S 策略 / C 元认知 / X 习惯）</h3>
              <table>
                <thead>
                  <tr><th>维度</th><th>掌握度</th><th>置信度</th><th>强度</th><th>解读</th></tr>
                </thead>
                <tbody>
                  {DIM_ORDER.map((dim) => {
                    const d = interp.five_d[dim];
                    if (!d) return null;
                    return (
                      <tr key={dim}>
                        <td>{d.name}</td>
                        <td>{fmt2(d.theta)}</td>
                        <td>{pct(d.confidence)}</td>
                        <td>{d.level_label}</td>
                        <td className="muted">{d.comment}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </section>

            {/* Bloom */}
            <section style={{ marginTop: 16 }}>
              <h3>Bloom 认知层级</h3>
              <p style={{ lineHeight: 1.8 }}>
                主导层级：{interp.bloom.dominant_label}（{interp.bloom.dominant}）
                {interp.bloom.next_layer && interp.bloom.gap_to_next !== null && (
                  <> · 下一层 {interp.bloom.next_layer}（差距 {fmt2(interp.bloom.gap_to_next)}）</>
                )}
              </p>
              <p className="muted" style={{ lineHeight: 1.8 }}>{interp.bloom.comment}</p>
            </section>

            {/* TC */}
            <section style={{ marginTop: 16 }}>
              <h3>概念边界（TC）进展</h3>
              {interp.tc.topics.length > 0 ? (
                <table>
                  <thead>
                    <tr><th>概念</th><th>进展</th><th>状态</th></tr>
                  </thead>
                  <tbody>
                    {interp.tc.topics.map((t) => (
                      <tr key={t.id}>
                        <td>{t.id}</td>
                        <td>{pct(t.progress)}</td>
                        <td>{t.tag}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="muted">暂无 TC 追踪数据。</p>
              )}
              <p className="muted" style={{ lineHeight: 1.8, marginTop: 8 }}>{interp.tc.comment}</p>
            </section>

            {/* 轨迹 */}
            <section style={{ marginTop: 16 }}>
              <h3>成长轨迹</h3>
              <p style={{ lineHeight: 1.8 }}>
                趋势：{interp.trajectory.trend}
                {interp.trajectory.significant_dims?.length
                  ? ` · 显著变化维度：${interp.trajectory.significant_dims.join("、")}`
                  : ""}
              </p>
              <p className="muted" style={{ lineHeight: 1.8 }}>{interp.trajectory.comment}</p>
            </section>

            {/* 下一步建议 */}
            <section style={{ marginTop: 16 }}>
              <h3>下一步建议</h3>
              <ol style={{ lineHeight: 2, paddingLeft: 20 }}>
                {interp.next_steps.map((s, i) => <li key={i}>{s}</li>)}
              </ol>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
