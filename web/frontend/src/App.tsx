import { Link, Route, Routes } from "react-router-dom";
import RosterPage from "./pages/RosterPage";
import StudentDetailPage from "./pages/StudentDetailPage";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          ECOS 教师端
        </Link>
        <span className="topbar-sub">v0.95.2 · 证据链视图 · POMDP 诊断</span>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<RosterPage />} />
          <Route path="/students/:id" element={<StudentDetailPage />} />
        </Routes>
      </main>
    </div>
  );
}
