import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  fetchCalibration,
  fetchDiagnostic,
  fetchEvidence,
  fetchInterventions,
  fetchMisconceptions,
  fetchStudentDetail,
} from "../api/client";
import type { DimensionEvidence, EvidenceResponse } from "../api/types";
import EChart from "../components/EChart";

export default function StudentDetailPage() {
  const { id = "" } = useParams();

  const detail = useQuery({
    queryKey: ["student", id],
    queryFn: () => fetchStudentDetail(id),
    enabled: !!id,
  });
  const evidence = useQuery({
    queryKey: ["evidence", id],
    queryFn: () => fetchEvidence(id),
    enabled: !!id,
  });
  const diagnostic = useQuery({
    queryKey: ["diagnostic", id],
    queryFn: () => fetchDiagnostic(id),
    enabled: !!id,
  });
  const interventions = useQuery({
    queryKey: ["interventions", id],
    queryFn: () => fetchInterventions(id),
    enabled: !!id,
  });
  const calibration = useQuery({
    queryKey: ["calibration", id],
    queryFn: () => fetchCalibration(id),
    enabled: !!id,
  });
  // v0.97.3: per-misconception 证据 (A2 reconcile 校准后 LLM 检测可信度)
  const misconceptions = useQuery({
    queryKey: ["misconceptions", id],
    queryFn: () => fetchMisconceptions(id),
    enabled: !!id,
  });

  if (detail.isError) return <div className="error-box">学生详情加载失败 (404?)</div>;
  if (detail.isLoading) return <p className="muted">加载中…</p>;

  const d = detail.data!;

  return (
    <div>
      <Link to="/" className="back-link">
        ← 返回班级列表
      </Link>

      <div className="card">
        <h2>
          {d.student_id}{" "}
          <span className="muted">
            · {d.answered_count} 题 · 正确率{" "}
            {d.answered_count ? `${(d.correct_rate * 100).toFixed(1)}%` : "—"} · 置信{" "}
            {d.overall_confidence.toFixed(2)}
          </span>
        </h2>
        {d.report && <ReportBanner report={d.report} />}
      </div>

      <Theta5DCard detail={d} />

      <div className="card">
        <h2>5D 证据链 — “系统为什么这么判断”</h2>
        {evidence.isLoading ? (
          <p className="muted">加载证据链…</p>
        ) : evidence.isError ? (
          <div className="error-box">证据链加载失败</div>
        ) : (
          <EvidenceChain evidence={evidence.data!} />
        )}
      </div>

      <div className="card">
        <h2>POMDP 诊断</h2>
        {diagnostic.isLoading ? (
          <p className="muted">加载诊断…</p>
        ) : diagnostic.isError ? (
          <div className="error-box">POMDP 诊断加载失败</div>
        ) : diagnostic.data?.diagnostic ? (
          <PomdpView diagnostic={diagnostic.data} />
        ) : (
          <p className="muted">
            该学生当前无 POMDP 后验 (非 POMDP policy 或 LCA 状态不足), 诊断不可用。
          </p>
        )}
      </div>

      <div className="card">
        <h2>自评校准 — 学生觉得自己会 vs 实际答对</h2>
        {calibration.isLoading ? (
          <p className="muted">加载校准视图…</p>
        ) : calibration.isError ? (
          <div className="error-box">校准视图加载失败</div>
        ) : (
          <CalibrationViewCard data={calibration.data!} />
        )}
      </div>

      <div className="card">
        <h2>per-misconception 证据 — A2 闭环校准后的 LLM 检测可信度</h2>
        {misconceptions.isLoading ? (
          <p className="muted">加载 per-misc 证据…</p>
        ) : misconceptions.isError ? (
          <div className="error-box">per-misc 证据加载失败</div>
        ) : (
          <MisconceptionsCard data={misconceptions.data!} />
        )}
      </div>

      <div className="card">
        <h2>干预历史</h2>
        {interventions.isLoading ? (
          <p className="muted">加载干预历史…</p>
        ) : interventions.data?.interventions.length ? (
          <table>
            <thead>
              <tr>
                <th>类型</th>
                <th>Bloom 目标</th>
                <th>期望增益</th>
                <th>风险</th>
              </tr>
            </thead>
            <tbody>
              {interventions.data.interventions.map((it, i) => (
                <tr key={i}>
                  <td>{String(it.intervention_type ?? it.type ?? "—")}</td>
                  <td>{String(it.bloom_target ?? "—")}</td>
                  <td>{String(it.expected_gain ?? "—")}</td>
                  <td>{String(it.expected_risk ?? "—")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">暂无干预记录。</p>
        )}
      </div>
    </div>
  );
}

function ReportBanner({ report }: { report: NonNullable<import("../api/types").ProgressReport> }) {
  return (
    <div className="banner" style={{ padding: "10px 14px", borderRadius: 8, background: "#f0f6ff" }}>
      <strong>{report.most_likely_state}</strong>
      <span className="muted" style={{ marginLeft: 10 }}>
        {report.advice}
      </span>
    </div>
  );
}

function Theta5DCard({
  detail,
}: {
  detail: NonNullable<import("../api/types").StudentDetail>;
}) {
  const theta = detail.theta_5d;
  const levels = detail.bloom_profile?.levels;
  const radar: Parameters<typeof EChart>[0]["option"] = {
    radar: {
      indicator: ["K", "P", "S", "C", "X"].map((k) => ({ name: k, max: 2.5, min: -2.5 })),
      radius: "65%",
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: theta ? [theta.K, theta.P, theta.S, theta.C, theta.X] : [0, 0, 0, 0, 0],
            name: "theta",
          },
        ],
      },
    ],
  };
  return (
    <div className="card">
      <h2>能力画像 (5D θ)</h2>
      <div style={{ display: "flex", gap: 24, alignItems: "center", flexWrap: "wrap" }}>
        <div style={{ flex: "1 1 320px", minWidth: 280 }}>
          <EChart option={radar} height={240} />
        </div>
        <div style={{ flex: "1 1 280px" }}>
          <dl>
            <dt>Bloom 主导</dt>
            <dd>{detail.bloom_profile?.dominant ?? "—"}</dd>
            <dt>Bloom 置信</dt>
            <dd>{detail.bloom_profile?.confidence.toFixed(2) ?? "—"}</dd>
            {levels &&
              (Object.entries(levels) as Array<[string, number]>).map(([k, v]) => (
                <div key={k}>
                  <dt>{k}</dt>
                  <dd>{v.toFixed(2)}</dd>
                </div>
              ))}
          </dl>
        </div>
      </div>
    </div>
  );
}

function EvidenceChain({ evidence }: { evidence: EvidenceResponse }) {
  return (
    <div>
      <div className="grid-5d">
        {(["K", "P", "S", "C", "X"] as const).map((k) => (
          <DimCard key={k} dim={k} d={evidence.dimensions[k]} />
        ))}
      </div>
      <div style={{ marginTop: 14 }}>
        <p className="muted" style={{ marginBottom: 6 }}>
          跨维度证据: {evidence.misconceptions.length} 个 misconception ·{" "}
          {evidence.tc_states.length} 个 TC 状态
        </p>
        {evidence.misconceptions.map((m) => (
          <span key={m.misc_id} className="badge attention" style={{ marginRight: 8 }}>
            {m.misc_id} ({m.confidence.toFixed(2)})
          </span>
        ))}
        {evidence.tc_states.map((t) => (
          <span key={t.id} className="badge cold" style={{ marginRight: 8 }}>
            {t.id}: {t.status}
          </span>
        ))}
      </div>
    </div>
  );
}

function DimCard({ dim, d }: { dim: string; d: DimensionEvidence }) {
  return (
    <div className="dim-card">
      <div className="dim-head">
        <span className="dim-key">{dim}</span>
        <span className="dim-label">
          {d.label} ({d.full})
        </span>
      </div>
      <dl>
        <dt>θ</dt>
        <dd>{d.theta.toFixed(2)}</dd>
        <dt>置信</dt>
        <dd>{d.confidence.toFixed(2)}</dd>
        <dt>掌握</dt>
        <dd>{d.mastered ? "是" : "否"}</dd>
        <dt>证据</dt>
        <dd>
          {d.response_count} 题 · {d.response_count ? `${(d.correct_rate * 100).toFixed(0)}%` : "—"}
        </dd>
      </dl>
      <details>
        <summary>下钻 {d.response_count} 条答题证据</summary>
        {d.responses.length === 0 ? (
          <p className="muted">该维度暂无答题证据</p>
        ) : (
          d.responses.map((r) => (
            <div key={r.problem_id} style={{ marginTop: 8 }}>
              <strong>
                {r.problem_id} ({r.bloom_level ?? "—"}) {r.correct ? "✓" : "✗"} score={r.score}
              </strong>
              <p className="muted" style={{ margin: "4px 0" }}>
                AI 评判: {r.ai_reasoning ?? "—"}
              </p>
            </div>
          ))
        )}
      </details>
    </div>
  );
}

// v0.97.2: 自评校准视图 (CogMirror A1 移植; 读时派生, 不持久化)
function CalibrationViewCard({
  data,
}: {
  data: NonNullable<import("../api/types").CalibrationResponse>;
}) {
  if (!data.has_data) {
    return (
      <p className="muted">
        自评数据不足 (自评 {data.n_self_assessed}/{data.n_total} 题, 每档需 ≥5 题才能出校准曲线)。
        学生答题时提交"把握程度"后此处逐步呈现。
      </p>
    );
  }
  const chart: Parameters<typeof EChart>[0]["option"] = {
    // 校准曲线: x = 自评标称置信度 (桶中点), y = 实际答对率; 对角线 = 完全校准
    xAxis: { type: "value", min: 0, max: 1, name: "自评" },
    yAxis: { type: "value", min: 0, max: 1, name: "实际答对率" },
    series: [
      {
        type: "line",
        data: data.curves.map((c) => [c.predicted, c.actual_rate]),
        symbolSize: 10,
        itemStyle: { color: "#2563eb" },
      },
      {
        // 完全校准参考线 (自评 = 实绩)
        type: "line",
        data: [[0, 0], [1, 1]],
        symbol: "none",
        lineStyle: { type: "dashed", color: "#9ca3af" },
        tooltip: { show: false },
      },
    ],
  };
  return (
    <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 320px", minWidth: 280 }}>
        <EChart option={chart} height={260} />
      </div>
      <div style={{ flex: "1 1 300px" }}>
        <p className="muted" style={{ marginBottom: 6 }}>
          自评 {data.n_self_assessed}/{data.n_total} 题 (未自评 {data.n_skipped})。
          点在对角线下方 = 该档自评偏高 (伪自信), 上方 = 偏低 (欠自信)。
        </p>
        <table>
          <thead>
            <tr>
              <th>自评档</th>
              <th>题数</th>
              <th>答对率</th>
              <th>校准比</th>
            </tr>
          </thead>
          <tbody>
            {data.curves.map((c) => (
              <tr key={c.bucket}>
                <td>{c.bucket}</td>
                <td>{c.n}</td>
                <td>{(c.actual_rate * 100).toFixed(0)}%</td>
                <td>{c.correction_factor.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PomdpView({
  diagnostic,
}: {
  diagnostic: NonNullable<import("../api/types").DiagnosticResponse>;
}) {
  const names = diagnostic.pomdp_state_names;
  const belief = diagnostic.report?.belief ?? [];
  const bar: Parameters<typeof EChart>[0]["option"] = {
    xAxis: { type: "category", data: names },
    yAxis: { type: "value", max: 1 },
    series: [{ type: "bar", data: belief, itemStyle: { color: "#2563eb" } }],
  };
  return (
    <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
      <div style={{ flex: "1 1 300px", minWidth: 240 }}>
        <EChart option={bar} height={220} />
      </div>
      <div style={{ flex: "1 1 300px" }}>
        <dl>
          <dt>最可能状态</dt>
          <dd>{diagnostic.report?.most_likely_state ?? "—"}</dd>
          <dt>min_coverage</dt>
          <dd>{diagnostic.report?.min_coverage ?? "—"}</dd>
          <dt>冷启动</dt>
          <dd>{diagnostic.report?.cold_start ? "是" : "否"}</dd>
          <dt>建议</dt>
          <dd>{diagnostic.report?.advice ?? "—"}</dd>
        </dl>
      </div>
    </div>
  );
}

// v0.97.3: per-misconception 证据卡
//   - A2 闭环校准后的 LLM 检测可信度 (CogMirror A2 移植 + ECOS 适配)
//   - success = 检测被证实的次数 (后续仍错/重触发), failure = 检测被证伪
//   - Laplace 置信度 (s+1)/(s+f+2); quarantined = 长期被证伪, 查询辅助
//   - 本期不挂 C 维度折扣 (v0.97.2 拍板纪律: C 等试点数据, 试点回来同批接)
function MisconceptionsCard({
  data,
}: {
  data: NonNullable<import("../api/types").MisconceptionsResponse>;
}) {
  if (!data.has_data) {
    return (
      <p className="muted">
        暂无 A2 证据。学生在答题中触发 LLM misconception 检测 + 完成后续同 skill 答题后,
        此处逐步呈现每条 misconception 的证据可信度 (Laplace 校准后)。
      </p>
    );
  }
  return (
    <div>
      <p className="muted" style={{ marginBottom: 8 }}>
        每条 LLM 检测到的 misconception 在后续同 skill 答题中的"被证实 / 被证伪"次数。
        Laplace 置信度越接近 1 表示该检测模式对该学生越可靠; quarantined 标记的检测模式
        已长期被证伪, 教师可降低对它的关注。数据不进入 BeliefState (v0.97.2 拍板纪律)。
      </p>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>名称 / 描述</th>
            <th>证实</th>
            <th>证伪</th>
            <th>Laplace 置信度</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((it) => (
            <tr key={it.misc_id}>
              <td>
                <code>{it.misc_id}</code>
              </td>
              <td>
                <strong>{it.name}</strong>
                {it.description && (
                  <div className="muted" style={{ fontSize: "0.85em" }}>
                    {it.description}
                  </div>
                )}
              </td>
              <td>{it.success_count}</td>
              <td>{it.failure_count}</td>
              <td>
                <span
                  style={{
                    color: it.laplace_confidence >= 0.6 ? "#16a34a" : it.laplace_confidence < 0.3 ? "#dc2626" : "#6b7280",
                    fontWeight: 600,
                  }}
                >
                  {it.laplace_confidence.toFixed(2)}
                </span>
              </td>
              <td>
                {it.quarantined ? (
                  <span style={{ color: "#dc2626" }}>已隔离 (≤0.3, ≥3 证据)</span>
                ) : it.laplace_confidence >= 0.6 ? (
                  <span style={{ color: "#16a34a" }}>可信</span>
                ) : (
                  <span className="muted">观察中</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
