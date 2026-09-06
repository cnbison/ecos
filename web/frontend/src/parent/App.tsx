// v0.98.0 (a-c): 家长端 SPA (第三入口, 跟 teacher App.tsx 同构)
import ParentHomePage from "./pages/ParentHomePage";
import "../index.css";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">ECOS 家长端</span>
        <span className="topbar-sub">v0.98.0 · 学习状态 · 成长概览</span>
      </header>
      <main className="content">
        <ParentHomePage />
      </main>
    </div>
  );
}
