// v0.98.0 (a-c): 家长端首页 — roster 选择 + 单聚合 overview 四卡
// v0.98.4-P1: 学生选择持久化为 URL query (?student=<id>)，支持刷新/分享
import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
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
import ClickableRow from "../../components/ui/ClickableRow";
import EmptyState from "../../components/ui/EmptyState";
import { UsersRound } from "../../components/ui/icons";
import {
  isKnownStudent,
  readStudentParam,
  studentSearch,
} from "../urlState";
import { formatCorrectRate, stateBadgeClass, stateLabel } from "../ui";

export default function ParentHomePage() {
  const [searchParams, setSearchParams] = useSearchParams();

  const roster = useQuery({ queryKey: ["parentRoster"], queryFn: fetchParentRoster });
  const students = useMemo(() => roster.data?.students ?? [], [roster.data]);

  const paramId = readStudentParam(`?${searchParams.toString()}`);
  const selectedId = roster.isSuccess && isKnownStudent(paramId, students) ? paramId : null;

  // 非法/不存在的学生 id 出现在 URL 时，清空参数（不在 render 中 setState）
  useEffect(() => {
    if (roster.isSuccess && paramId && !isKnownStudent(paramId, students)) {
      setSearchParams(studentSearch(null), { replace: true });
    }
  }, [roster.isSuccess, paramId, students, setSearchParams]);

  const overview = useQuery({
    queryKey: ["parentOverview", selectedId],
    queryFn: () => fetchParentOverview(selectedId!),
    enabled: selectedId !== null,
  });

  if (roster.isLoading) return <p className="muted">加载学生列表…</p>;
  if (roster.isError) return <div className="error-box">学生列表加载失败</div>;

  // 未选择学生 → roster 选择视图
  if (!selectedId) {
    return (
      <div className="card">
        <h2>
          我的孩子 <span className="muted">({students.length} 人)</span>
        </h2>
        {students.length === 0 ? (
          <EmptyState
            icon={<UsersRound size={28} />}
            title="暂无学生数据"
            description="家长账号关联的学生答题后会在此显示。"
          />
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
                <ClickableRow
                  key={s.student_id}
                  onClick={() => setSearchParams(studentSearch(s.student_id))}
                  ariaLabel={`查看 ${s.student_id} 学习概览`}
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
                </ClickableRow>
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
        <button onClick={() => setSearchParams(studentSearch(null), { replace: true })}>
          返回列表
        </button>
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
        <button onClick={() => setSearchParams(studentSearch(null), { replace: true })}>
          返回列表
        </button>
      </div>
      <EngagementCard engagement={data.engagement} />
      <AdviceCard engagement={data.engagement} />
      <FiveDOverviewCard fiveD={data.five_d} />
      <InterventionHistoryCard interventions={data.interventions} />
    </div>
  );
}
