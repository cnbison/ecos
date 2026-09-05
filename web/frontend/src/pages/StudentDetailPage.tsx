import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import {
  fetchCalibration,
  fetchDiagnostic,
  fetchEvidence,
  fetchInterventions,
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
