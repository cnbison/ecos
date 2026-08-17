import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { fetchRoster } from "../api/client";
import type { RosterStudent } from "../api/types";

export default function RosterPage() {
  const navigate = useNavigate();
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
              <tr
                key={s.student_id}
                className="clickable"
                onClick={() => navigate(`/students/${s.student_id}`)}
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
              </tr>
            ))}
            {students.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  暂无学生
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
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
