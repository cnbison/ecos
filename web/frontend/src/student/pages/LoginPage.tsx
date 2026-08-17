// v0.96: 登录页 (最近学生快捷选择 + 手动输入)
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { fetchRecentStudents } from "../api";

export default function LoginPage({ onLogin }: { onLogin: (sid: string) => void }) {
  const [sid, setSid] = useState("");
  const recent = useQuery({ queryKey: ["recent-students"], queryFn: fetchRecentStudents });

  const submit = () => {
    const v = sid.trim();
    if (v) onLogin(v);
  };

  return (
    <div className="login">
      <h2>ECOS Python 基础</h2>
      <p className="muted">输入学生 ID 进入学习（或从最近学生选择）</p>
      <input
        value={sid}
        onChange={(e) => setSid(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && submit()}
        placeholder="学生 ID，如 lbc001"
        autoFocus
      />
      <button onClick={submit} disabled={!sid.trim()}>
        进入学习
      </button>

      <div className="recent-list">
        <div className="recent-label">📚 最近学生</div>
        <div className="recent-btns">
          {(recent.data?.students ?? []).map((s) => (
            <button key={s} className="ghost" onClick={() => onLogin(s)}>
              {s}
            </button>
          ))}
          {recent.data?.students.length === 0 && (
            <span className="muted">暂无最近学生</span>
          )}
        </div>
      </div>
    </div>
  );
}
