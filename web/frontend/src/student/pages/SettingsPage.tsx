// v0.96: 设置 — 退出登录 / 导出学习报告 / 关于
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchReport } from "../api";

export default function SettingsPage({
  studentId,
  onLogout,
}: {
  studentId: string;
  onLogout: () => void;
}) {
  const [exporting, setExporting] = useState(false);
  const report = useQuery({
    queryKey: ["report", studentId],
    queryFn: () => fetchReport(studentId),
  });

  const exportReport = async () => {
    setExporting(true);
    try {
      const data = await fetchReport(studentId);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ecos_report_${studentId}_${new Date().toISOString().slice(0, 10)}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e) {
      window.alert("导出失败：" + (e as Error).message);
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="settings-page" style={{ maxWidth: 520 }}>
      <section className="card">
        <h2>⚙️ 设置</h2>
        <div className="row" style={{ marginBottom: 14 }}>
          <span>当前学生</span>
          <span className="val">👤 {studentId}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          <button className="ghost" onClick={exportReport} disabled={exporting}>
            {exporting ? "导出中…" : "📤 导出学习报告 (JSON)"}
          </button>
          <button
            style={{ background: "var(--danger)", color: "#fff" }}
            onClick={onLogout}
          >
            退出登录
          </button>
        </div>
      </section>

      <section className="card">
        <h2>ℹ️ 关于</h2>
        <div className="muted" style={{ fontSize: 13, lineHeight: 1.8 }}>
          <div>ECOS 学习端 · 学生版 v{__APP_VERSION__}</div>
          <div>
            引擎版本：ECOS v{report.data?.ecos_version ?? "—"} ·{" "}
            {report.data?.interpretation ? "规则引擎通俗化" : ""}
          </div>
          <div>Educational Cognitive Operating System</div>
        </div>
      </section>
    </div>
  );
}
