"""v0.95.0: 前端 4 行为事件端点接通测试 (hint / idle / goal_change / reflection).

app.js + index.html 是纯静态资源 (项目无 JS 测试基建), 本测试以 grep 契约方式
守护"前端接线不能删" — 后端 /api/event/* 端点行为已在 test_event_stub.py 覆盖。

Per discussions/2026-08-17-v095方向审查-验证滞后于抽象与应用层产品化规划.md
决策 2-1 (数据通道打通, 不依赖 React): 接通后 v0.91 human feedback /
v0.92 action history / v0.94 HintFatiguePlugin 的 Kernel 投资才有数据来源。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "web/student/app.js"
INDEX_HTML = ROOT / "web/student/index.html"


def _read(p: Path) -> str:
    assert p.exists(), f"missing: {p.relative_to(ROOT)}"
    return p.read_text(encoding="utf-8")


class TestAppJsEventWiring:
    """app.js 4 个行为事件端点的 api 方法与调用点存在."""

    def setup_method(self):
        self.js = _read(APP_JS)

    def test_4_api_methods_defined(self):
        """api 对象暴露 4 个 emit 方法."""
        for m in ("emitHint", "emitIdle", "emitGoalChange", "emitReflection"):
            assert re.search(rf"\bapi\.{m}\s*\(", self.js), f"api.{m}( 未定义"

    def test_4_endpoint_paths_present(self):
        """4 个端点路径写进 api 对象 (跟 event_stub.py 路由一致)."""
        for p in ("'/event/hint'", "'/event/idle'", "'/event/goal_change'", "'/event/reflection'"):
            assert p in self.js, f"endpoint {p} 缺失"

    def test_each_event_called_from_ui(self):
        """每个 event 都有 UI 触发点 (不能是死代码)."""
        # hint: askHint() 按钮
        assert "function askHint()" in self.js
        assert "api.emitHint(" in self.js
        # idle: 输入监听 + 定时器
        assert "function _scheduleIdleDetect()" in self.js
        assert "addEventListener('input', _scheduleIdleDetect)" in self.js
        assert "api.emitIdle(" in self.js
        # goal_change: loadQ 里检测 topic:bloom_layer 切换
        assert "_emitGoalChange(" in self.js
        assert "api.emitGoalChange(" in self.js
        # reflection: submitReflection()
        assert "function submitReflection()" in self.js
        assert "api.emitReflection(" in self.js

    def test_hint_payload_matches_backend_contract(self):
        """hint body: {student_id, problem_id, hint_level} 跟 event_stub 契约一致."""
        assert "hint_level: 1" in self.js

    def test_idle_payload_matches_backend_contract(self):
        """idle body: {student_id, idle_seconds} 跟 event_stub 契约一致."""
        assert "idle_seconds: IDLE_SECONDS" in self.js

    def test_goal_change_payload_matches_backend_contract(self):
        """goal_change body: {student_id, old_goal_id, new_goal_id}."""
        assert "old_goal_id: _lastGoalId" in self.js
        assert "new_goal_id: newGoalId" in self.js

    def test_reflection_payload_matches_backend_contract(self):
        """reflection body: {student_id, reflection_text, problem_id optional}."""
        assert "reflection_text: text" in self.js
        assert "problem_id: q ? q.problem_id : undefined" in self.js

    def test_best_effort_not_silent(self):
        """best-effort 遥测必须 console.warn, 不允许 silent pass."""
        assert self.js.count("console.warn(") >= 4


class TestIndexHtmlEventWiring:
    """index.html 提示按钮 + 课后反思区存在且接到 JS."""

    def setup_method(self):
        self.html = _read(INDEX_HTML)

    def test_hint_button(self):
        assert 'id="btnHint"' in self.html
        assert 'onclick="askHint()"' in self.html

    def test_reflection_ui(self):
        assert 'id="reflRow"' in self.html
        assert 'id="reflInput"' in self.html
        assert 'id="btnRefl"' in self.html
        assert 'onclick="submitReflection()"' in self.html

    def test_reflection_row_hidden_by_default(self):
        assert 'id="reflRow" style="display:none;"' in self.html

    def test_cache_bust_bumped(self):
        """改 app.js/styles.css 必须 bump ?v= 避免浏览器缓存旧版 (v0.47.3 教训)."""
        assert "?v=0.66.0" not in self.html
        assert "?v=0.65.0" not in self.html
        assert "?v=" in self.html
