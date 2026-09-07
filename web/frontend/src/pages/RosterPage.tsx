import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchRoster } from "../api/client";
import type { RosterStudent } from "../api/types";
import ClickableRow from "../components/ui/ClickableRow";
import EmptyState from "../components/ui/EmptyState";
import { Users } from "../components/ui/icons";
import useMediaQuery, { ROSTER_MOBILE_QUERY } from "../components/ui/useMediaQuery";

export default function RosterPage() {
  const navigate = useNavigate();
  const isMobile = useMediaQuery(ROSTER_MOBILE_QUERY);
  const { data, isLoading, isError } = useQuery({
    queryKey: ["roster"],
    queryFn: fetchRoster,
  });

  if (isLoading) return <p className="muted">加载班级列表…</p>;
  if (isError) return <div className="error-box">班级列表加载失败</div>;

  const students = data?.students ?? [];
  const atRisk = students.filter((s) => s.risk === "attention").length;

  return (
    <div>
      <div className="card">
        <h2>
          班级列表{" "}
          <span className="muted">
            ({students.length} 人 · 需关注 {atRisk} 人)
          </span>
        </h2>
        {students.length === 0 ? (
          <EmptyState
            icon={<Users size={28} />}
            title="暂无学生"
            description="学生答题后班级列表会逐步填充。"
          />
        ) : isMobile ? (
          <div className="roster-cards">
            {students.map((s) => (
              <RosterCard
                key={s.student_id}
                s={s}
                onOpen={() => navigate(`/students/${s.student_id}`)}
              />
            ))}
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>学生</th>
                <th>答题</th>
                <th>正确率</th>
                <th>Bloom 主导</th>
                <th>置信</th>
                <th>状态</th>
                <th>干预</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s: RosterStudent) => (
                <ClickableRow
                  key={s.student_id}
                  onClick={() => navigate(`/students/${s.student_id}`)}
                  ariaLabel={`查看 ${s.student_id} 详情`}
                >
                  <td>
                    <strong>{s.student_id}</strong>
                    <div className="muted" style={{ fontSize: 12 }}>
                      {s.subject ?? "—"}
                      {s.last_active_at ? ` · ${s.last_active_at.slice(0, 10)}` : ""}
                    </div>
                  </td>
                  <td>{s.answered_count}</td>
                  <td>{s.answered_count ? `${(s.correct_rate * 100).toFixed(1)}%` : "—"}</td>
                  <td>{s.bloom_dominant ?? "—"}</td>
                  <td>{s.overall_confidence.toFixed(2)}</td>
                  <td>
                    <StatusBadge s={s} />
                  </td>
                  <td>{s.intervention_count}</td>
                </ClickableRow>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function RosterCard({
  s,
  onOpen,
}: {
  s: RosterStudent;
  onOpen: () => void;
}) {
  return (
    <button type="button" className="roster-card" onClick={onOpen}>
      <div className="roster-card-head">
        <strong>{s.student_id}</strong>
        <StatusBadge s={s} />
      </div>
      <div className="muted" style={{ fontSize: 12, marginBottom: 10 }}>
        {s.subject ?? "—"}
        {s.last_active_at ? ` · ${s.last_active_at.slice(0, 10)}` : ""}
      </div>
      <div className="roster-card-grid">
        <div className="roster-card-item">
          <span className="roster-card-label">答题</span>
          <span>{s.answered_count}</span>
        </div>
        <div className="roster-card-item">
          <span className="roster-card-label">正确率</span>
          <span>{s.answered_count ? `${(s.correct_rate * 100).toFixed(1)}%` : "—"}</span>
        </div>
        <div className="roster-card-item">
          <span className="roster-card-label">Bloom</span>
          <span>{s.bloom_dominant ?? "—"}</span>
        </div>
        <div className="roster-card-item">
          <span className="roster-card-label">置信</span>
          <span>{s.overall_confidence.toFixed(2)}</span>
        </div>
        <div className="roster-card-item">
          <span className="roster-card-label">干预</span>
          <span>{s.intervention_count}</span>
        </div>
      </div>
    </button>
  );
}

function StatusBadge({ s }: { s: RosterStudent }) {
  if (s.risk === "attention" && s.most_likely_state) {
    return (
      <span className="badge attention">
        {s.most_likely_state} {s.cold_start ? "· 冷启动" : ""}
      </span>
    );
  }
  if (s.cold_start) return <span className="badge cold">冷启动</span>;
  return <span className="badge ok">正常</span>;
}
