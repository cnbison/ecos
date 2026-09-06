// v0.98.0 (a-c): 家长端首页 — roster 选择 + 单聚合 overview 四卡
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  fetchParentOverview,
  fetchParentRoster,
} from "../api";
import {
  AdviceCard,
  EngagementCard,
  FiveDOverviewCard,
  InterventionHistoryCard,
} from "../components/Cards";
import { formatCorrectRate, stateBadgeClass, stateLabel } from "../ui";

export default function ParentHomePage() {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const roster = useQuery({ queryKey: ["parentRoster"], queryFn: fetchParentRoster });
  const overview = useQuery({
    queryKey: ["parentOverview", selectedId],
    queryFn: () => fetchParentOverview(selectedId!),
    enabled: selectedId !== null,
  });

  if (roster.isLoading) return <p className="muted">加载学生列表…</p>;
  if (roster.isError) return <div className="error-box">学生列表加载失败</div>;

  const students = roster.data?.students ?? [];

  // 未选择学生 → roster 选择视图
  if (!selectedId) {
    return (
      <div className="card">
        <h2>
          我的孩子 <span className="muted">({students.length} 人)</span>
        </h2>
        {students.length === 0 ? (
          <p className="muted">暂无学生数据</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>答题</th>
                <th>正确率</th>
                <th>当前状态</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr
                  key={s.student_id}
                  className="clickable"
                  onClick={() => setSelectedId(s.student_id)}
                >
                  <td>
                    <strong>{s.student_id}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {s.subject ?? "—"}
                      {s.last_active_at ? ` · ${s.last_active_at.slice(0, 10)}` : ""}
                    </div>
                  </td>
                  <td>{s.answered_count}</td>
                  <td>{formatCorrectRate(s.answered_count ? s.correct_rate : null)}</td>
                  <td>
                    <span className={stateBadgeClass(s.current_state)}>
                      {stateLabel(s.current_state)}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    );
  }

  // 已选择 → 四卡 overview
  if (overview.isLoading) return <p className="muted">加载学习概览…</p>;
  if (overview.isError)
    return (
      <div>
        <div className="error-box">学习概览加载失败</div>
        <button onClick={() => setSelectedId(null)}>返回列表</button>
      </div>
    );

  const data = overview.data;
  if (!data) return null;

  return (
    <div>
      <div className="card">
        <h2>
          {data.student_id}{" "}
          <span className="muted">({data.subject ?? "—"})</span>
        </h2>
        <button onClick={() => setSelectedId(null)}>返回列表</button>
      </div>
      <EngagementCard engagement={data.engagement} />
      <AdviceCard engagement={data.engagement} />
      <FiveDOverviewCard fiveD={data.five_d} />
      <InterventionHistoryCard interventions={data.interventions} />
    </div>
  );
}
