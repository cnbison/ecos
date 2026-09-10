// v0.96: 设置 — 退出登录 / 学习报告 / 关于
// v0.99.4 (F-01): 主入口改为 HTML 报告页 (/report, 可打印即 PDF);
// JSON 原始数据导出降级为开发者次按钮。
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { NavLink } from "react-router-dom";
import Icon from "../../components/ui/Icon";
import { FileText, Info, Settings, Upload, User } from "../../components/ui/icons";
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
      a.download = `ecos_report_raw_${studentId}_${new Date().toISOString().slice(0, 10)}.json`;
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
        <h2><Icon icon={Settings} size={20} /> 设置</h2>
        <div className="row" style={{ marginBottom: 14 }}>
          <span>当前学生</span>
          <span className="val"><Icon icon={User} size={16} /> {studentId}</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {/* v0.99.4 (F-01): 主入口 = HTML 报告页 (interpretation 为主体, 打印即 PDF) */}
          <NavLink
            to="/report"
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "10px 16px", borderRadius: 8,
              background: "var(--accent, #2563eb)", color: "#fff",
              textDecoration: "none", fontWeight: 500,
            }}
          >
            <Icon icon={FileText} size={16} /> 查看学习报告（可打印 / PDF）
          </NavLink>
          <button className="ghost" onClick={exportReport} disabled={exporting}>
            {exporting ? "导出中…" : <><Icon icon={Upload} size={16} /> 导出原始数据 (JSON, 开发者)</>}
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
        <h2><Icon icon={Info} size={20} /> 关于</h2>
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
