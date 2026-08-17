// v0.96: 学生端 App shell — 登录门 + 底部导航 (信息架构三问落地)
import { useEffect, useState } from "react";
import { NavLink, Route, Routes, useNavigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage";
import HomePage from "./pages/HomePage";
import AnswerPage from "./pages/AnswerPage";
import WherePage from "./pages/WherePage";
import GrowthPage from "./pages/GrowthPage";
import SettingsPage from "./pages/SettingsPage";

const LAST_SID_KEY = "ecos_last_student_id";

export default function App() {
  const [studentId, setStudentId] = useState<string | null>(
    () => localStorage.getItem(LAST_SID_KEY),
  );
  const navigate = useNavigate();

  useEffect(() => {
    if (!studentId) navigate("/login", { replace: true });
  }, [studentId, navigate]);

  const onLogin = (sid: string) => {
    localStorage.setItem(LAST_SID_KEY, sid);
    setStudentId(sid);
    navigate("/", { replace: true });
  };

  const onLogout = () => {
    localStorage.removeItem(LAST_SID_KEY);
    setStudentId(null);
  };

  if (!studentId) {
    return <LoginPage onLogin={onLogin} />;
  }

  return (
    <div className="app">
      <header className="student-topbar">
        <strong>ECOS 学习</strong>
        <span className="sid">👤 {studentId}</span>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<HomePage studentId={studentId} />} />
          <Route path="/answer" element={<AnswerPage studentId={studentId} />} />
          <Route path="/where" element={<WherePage studentId={studentId} />} />
          <Route path="/growth" element={<GrowthPage studentId={studentId} />} />
          <Route path="/settings" element={<SettingsPage studentId={studentId} onLogout={onLogout} />} />
        </Routes>
      </main>
      <nav className="bottom-nav">
        <NavLink to="/" end>
          🏠 今天
        </NavLink>
        <NavLink to="/answer">✏️ 答题</NavLink>
        <NavLink to="/where">📍 我在哪</NavLink>
        <NavLink to="/growth">📈 成长</NavLink>
        <NavLink to="/settings">⚙️ 设置</NavLink>
      </nav>
    </div>
  );
}
