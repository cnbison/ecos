// v0.98.0 (a-c): 家长端四卡组件 (Engagement / Advice / FiveD / Intervention)
import type {
  AdviceEntry,
  EngagementReport,
  FiveDOverview,
  InterventionItem,
} from "../api";
import { severityBadgeClass, stateBadgeClass, stateLabel } from "../ui";

const DIM_LABELS: Record<string, string> = {
  K: "知识",
  P: "程序",
  S: "策略",
  C: "置信",
  X: "支架",
};

/** 卡 1: Engagement 状态 + K=10 时间线 + state_changed 徽标 */
export function EngagementCard({ engagement }: { engagement: EngagementReport | null }) {
  if (!engagement) {
    return (
      <div className="card">
        <h2>学习状态</h2>
        <p className="muted">画像建立中, 暂无状态数据 (学生答题后逐步生成)</p>
      </div>
    );
  }
  return (
    <div className="card">
      <h2>
        学习状态{" "}
        <span className={stateBadgeClass(engagement.current_state)}>
          {stateLabel(engagement.current_state)}
        </span>
        {engagement.state_changed && (
          <span className="badge cold" style={{ marginLeft: 8 }}>
            状态有变化
          </span>
        )}
      </h2>
      {engagement.recent_states.length > 0 ? (
        <p>
          最近轨迹:{" "}
          {engagement.recent_states.map((s, i) => (
            <span key={i} className="muted">
              {stateLabel(s)}
              {i < engagement.recent_states.length - 1 ? " → " : ""}
            </span>
          ))}
        </p>
      ) : (
        <p className="muted">暂无演化轨迹 (需要更多答题数据)</p>
      )}
    </div>
  );
}

/** 卡 2: 规则建议 (severity 三色) */
export function AdviceCard({ engagement }: { engagement: EngagementReport | null }) {
  const advice: AdviceEntry[] = engagement?.advice ?? [];
  return (
    <div className="card">
      <h2>给家长的建议</h2>
      {advice.length === 0 ? (
        <p className="muted">暂无建议 (学生答题后生成)</p>
      ) : (
        <ul>
          {advice.map((a, i) => (
            <li key={i} style={{ marginBottom: 6 }}>
              <span className={severityBadgeClass(a.severity)}>{a.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** 卡 3: 5D + Bloom 概览 (只读, 不做解读 — 专业视图在教师端) */
export function FiveDOverviewCard({ fiveD }: { fiveD: FiveDOverview }) {
  const mastery = fiveD.mastery ?? {};
  const bloom = fiveD.bloom;
  return (
    <div className="card">
      <h2>
        学习概览 <span className="muted">({(fiveD.overall_confidence * 100).toFixed(0)}% 置信)</span>
      </h2>
      <div className="grid-5d">
        {Object.entries(DIM_LABELS).map(([dim, label]) => (
          <div key={dim}>
            <strong>{label}</strong>{" "}
            <span className="muted">
              {mastery[dim] !== undefined ? mastery[dim].toFixed(2) : "—"}
            </span>
          </div>
        ))}
      </div>
      {bloom && (
        <p className="muted" style={{ marginTop: 8 }}>
          Bloom 主导层级: {bloom.dominant ?? "—"}
        </p>
      )}
    </div>
  );
}

/** 卡 4: 干预历史 (教师/系统下发的学习安排) */
export function InterventionHistoryCard({
  interventions,
}: {
  interventions: InterventionItem[];
}) {
  return (
    <div className="card">
      <h2>学习安排记录 ({interventions.length})</h2>
      {interventions.length === 0 ? (
        <p className="muted">暂无干预记录</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>时间</th>
              <th>类型</th>
              <th>说明</th>
            </tr>
          </thead>
          <tbody>
            {interventions.map((it) => (
              <tr key={it.intervention_id}>
                <td className="muted">{(it.timestamp ?? "").slice(0, 10)}</td>
                <td>{it.intervention_type ?? "—"}</td>
                <td className="muted">{it.rationale_text ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
