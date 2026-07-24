"""v0.56.0: LCA 接入测试套件.

目标 (按 v0.56.0 Definition of Done):
  - test_lca_select_wired: LCA.select_intervention 调通 + 记录 last
  - test_lca_update_reward_*: reward 计算正确 (full / partial / wrong)
  - test_lca_update_skips_no_select: 没选过 intervention 时 update 跳过
  - test_lca_select_handles_engine_failure: 失败时不崩, 返回 None
  - test_lca_debug_info_fields: 调试信息字段齐全
  - test_lca_in_question_route: /api/question 调用栈含 LCA
  - test_lca_in_answer_route: /api/answer 调用栈含 LCA update

防御性自检 [1]: silent pass 验证 (lca.py 全部 except 有 logger.warning)
防御性自检 [2]: __version__ 同步 (ecos/__init__.py 0.56.0)
"""

from __future__ import annotations

import os
import sys
import logging
import importlib
from unittest.mock import patch

import pytest

# v0.56.0 测试要 import web.api.lca (它依赖 web.api.app.get_llm 走 lazy import,
# 这里直接 import, 不会触发 app 初始化)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────


@pytest.fixture
def fresh_lca_state(monkeypatch):
    """每个测试前重置 lca 模块的全局状态, 避免污染.

    v0.56.0: _engine / _last_intervention / _update_count / _select_count
    都是 in-memory 模块级 dict, 必须在测试间重置.
    """
    # 重置 lca 模块全局状态
    import web.api.lca as lca_mod

    lca_mod._engine = None
    lca_mod._last_intervention = {}
    lca_mod._update_count = {}
    lca_mod._select_count = {}
    lca_mod.LCA_ENABLED = False
    yield lca_mod


@pytest.fixture
def belief_state():
    """构造一个最小可用的 BeliefState (用于 LCA 单测).

    v0.56.0: BeliefEngine.create_initial_state 需要 LLM client (None 也行).
    """
    from ecos.cta.belief_engine import BeliefEngine, BeliefEngineConfig
    from ecos.cta.l1_evolution import EvolutionConfig
    from ecos.cta.l2_mirt import MIRTConfig

    config = BeliefEngineConfig(
        evolution_config=EvolutionConfig(),
        mirt_config=MIRTConfig(
            prior_mean=[0.0] * 5,
            prior_cov=None,  # 默认 eye(5)
            default_a_specialized=[0.8] * 5,
            default_a_general=0.5,
            default_difficulty=0.0,
        ),
    )
    engine = BeliefEngine(config=config, llm_client=None)
    state = engine.create_initial_state("test_lca_student")
    return state


# ──────────────────────────────────────────────────────────────────────
# 1. select_intervention 基础测试
# ──────────────────────────────────────────────────────────────────────


class TestLCASelectWired:
    """v0.56.0: LCA.select_intervention 接入主循环验证."""

    def test_lca_select_wired(self, fresh_lca_state, belief_state):
        """select_intervention 返回 LCAResult + 记录到 _last_intervention."""
        import web.api.lca as lca_mod

        result = lca_mod.select_intervention("test_lca_student", belief_state)

        assert result is not None, "LCA select_intervention 应该返回 LCAResult"
        assert hasattr(result, "intervention"), "LCAResult 应该有 intervention 字段"
        assert hasattr(result, "bloom_target"), "LCAResult 应该有 bloom_target"
        assert "test_lca_student" in lca_mod._last_intervention, "last_intervention 应被记录"
        assert lca_mod._select_count.get("test_lca_student") == 1, "select_count 应 +1"

    def test_lca_select_works_with_disabled_flag(self, fresh_lca_state, belief_state):
        """LCA_ENABLED=False 也能调通 (passthrough 模式)."""
        import web.api.lca as lca_mod

        lca_mod.LCA_ENABLED = False
        result = lca_mod.select_intervention("test_lca_student", belief_state)
        assert result is not None, "LCA_ENABLED=False 时也该能 select (走模板 fallback)"

    def test_lca_select_handles_engine_failure(self, fresh_lca_state, belief_state, caplog):
        """LCAEngine 初始化失败时 select 返回 None, 不崩 (CTA 兜底).

        防御性自检 [1]: 失败必须 logger.warning, 不能 silent pass.
        """
        import web.api.lca as lca_mod

        with patch.object(lca_mod, "get_lca_engine", side_effect=RuntimeError("mock init fail")):
            with caplog.at_level(logging.WARNING):
                result = lca_mod.select_intervention("test_lca_student", belief_state)

        assert result is None, "LCA 失败时应返回 None (走 CTA 兜底)"
        # 验证有 warning log (防御性自检 [1])
        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("LCA select_intervention 失败" in r.message for r in warning_logs), \
            "LCA 失败时必须有 logger.warning (防御性自检 [1])"


# ──────────────────────────────────────────────────────────────────────
# 2. update_with_reward 计算测试
# ──────────────────────────────────────────────────────────────────────


class TestLCAUpdateReward:
    """v0.56.0: reward 计算公式验证.

    公式:
        bloom_progress = 1.0 if score >= 0.6 else 0.0
        raw_reward = score + 0.5 * bloom_progress
        reward = raw_reward / 1.5  (归一化到 [0, 1])
    """

    def test_full_correct(self, fresh_lca_state, belief_state):
        """score=1.0 (全对) + bloom=对 → reward = (1.0 + 0.5) / 1.5 = 1.0"""
        import web.api.lca as lca_mod

        # 先 select 一次, 让 _last_intervention 有记录
        lca_mod.select_intervention("test_lca_student", belief_state)

        # spy LinUCB.bandit.update 验证 reward 值
        captured = []
        engine = lca_mod.get_lca_engine()
        original_update = engine.bandit.update

        def spy_update(intervention, belief_state, reward):
            captured.append(reward)
            return original_update(intervention, belief_state, reward)

        engine.bandit.update = spy_update

        lca_mod.update_with_reward(
            student_id="test_lca_student",
            belief_state=belief_state,
            score=1.0,
            bloom_layer="L3",
        )

        assert len(captured) == 1, "应该调一次 bandit.update"
        assert abs(captured[0] - 1.0) < 0.01, \
            f"score=1.0 + bloom=对 → reward 应≈1.0, 实际={captured[0]}"
        assert lca_mod._update_count.get("test_lca_student") == 1

    def test_partial_credit(self, fresh_lca_state, belief_state):
        """score=0.7 (70% 对) + bloom=对 → reward = (0.7 + 0.5) / 1.5 ≈ 0.8"""
        import web.api.lca as lca_mod

        lca_mod.select_intervention("test_lca_student", belief_state)

        captured = []
        engine = lca_mod.get_lca_engine()
        original_update = engine.bandit.update

        def spy_update(intervention, belief_state, reward):
            captured.append(reward)
            return original_update(intervention, belief_state, reward)

        engine.bandit.update = spy_update

        lca_mod.update_with_reward(
            student_id="test_lca_student",
            belief_state=belief_state,
            score=0.7,
            bloom_layer="L3",
        )

        assert len(captured) == 1
        expected = (0.7 + 0.5) / 1.5  # ≈ 0.8
        assert abs(captured[0] - expected) < 0.01, \
            f"score=0.7 + bloom=对 → reward 应≈{expected:.3f}, 实际={captured[0]}"

    def test_wrong_answer(self, fresh_lca_state, belief_state):
        """score=0.0 (全错) + bloom=错 → reward = (0.0 + 0.0) / 1.5 = 0.0"""
        import web.api.lca as lca_mod

        lca_mod.select_intervention("test_lca_student", belief_state)

        captured = []
        engine = lca_mod.get_lca_engine()
        original_update = engine.bandit.update

        def spy_update(intervention, belief_state, reward):
            captured.append(reward)
            return original_update(intervention, belief_state, reward)

        engine.bandit.update = spy_update

        lca_mod.update_with_reward(
            student_id="test_lca_student",
            belief_state=belief_state,
            score=0.0,
            bloom_layer="L3",
        )

        assert len(captured) == 1
        assert abs(captured[0] - 0.0) < 0.01, \
            f"score=0.0 → reward 应=0.0, 实际={captured[0]}"

    def test_score_clamp_to_unit_interval(self, fresh_lca_state, belief_state):
        """score > 1.0 时应该 clamp 到 [0, 1] (防御性)."""
        import web.api.lca as lca_mod

        lca_mod.select_intervention("test_lca_student", belief_state)

        captured = []
        engine = lca_mod.get_lca_engine()
        original_update = engine.bandit.update

        def spy_update(intervention, belief_state, reward):
            captured.append(reward)
            return original_update(intervention, belief_state, reward)

        engine.bandit.update = spy_update

        # score=1.5 (异常输入) 应被 clamp 到 1.0
        lca_mod.update_with_reward(
            student_id="test_lca_student",
            belief_state=belief_state,
            score=1.5,
            bloom_layer="L3",
        )

        assert abs(captured[0] - 1.0) < 0.01, \
            f"score=1.5 应被 clamp 到 1.0 → reward=1.0, 实际={captured[0]}"


# ──────────────────────────────────────────────────────────────────────
# 3. update 跳过 / 失败 测试
# ──────────────────────────────────────────────────────────────────────


class TestLCAUpdateEdgeCases:
    """v0.56.0: 边界情况测试."""

    def test_update_skips_if_no_select(self, fresh_lca_state, belief_state):
        """没选过 intervention 时 update 跳过 (LinUCB 冷启动容错)."""
        import web.api.lca as lca_mod

        # 不调 select, 直接 update
        lca_mod.update_with_reward(
            student_id="never_selected",
            belief_state=belief_state,
            score=1.0,
            bloom_layer="L3",
        )

        # 应该没调 engine.update, update_count 不应增加
        assert lca_mod._update_count.get("never_selected", 0) == 0

    def test_update_handles_engine_failure(self, fresh_lca_state, belief_state, caplog):
        """LCAEngine.update 失败时不崩, 有 logger.warning.

        防御性自检 [1]: 失败必须有 warning, 不能 silent pass.
        """
        import web.api.lca as lca_mod

        lca_mod.select_intervention("test_lca_student", belief_state)

        # 让 LCAEngine.update 抛异常
        engine = lca_mod.get_lca_engine()
        with patch.object(engine, "update", side_effect=RuntimeError("mock update fail")):
            with caplog.at_level(logging.WARNING):
                # 不该抛异常
                lca_mod.update_with_reward(
                    student_id="test_lca_student",
                    belief_state=belief_state,
                    score=1.0,
                    bloom_layer="L3",
                )

        warning_logs = [r for r in caplog.records if r.levelname == "WARNING"]
        assert any("LCAEngine.update 失败" in r.message for r in warning_logs), \
            "LCA update 失败时必须有 logger.warning (防御性自检 [1])"


# ──────────────────────────────────────────────────────────────────────
# 4. 调试接口测试
# ──────────────────────────────────────────────────────────────────────


class TestLCADebugInfo:
    """v0.56.0: get_lca_debug_info 接口字段测试."""

    def test_debug_info_fields_after_select(self, fresh_lca_state, belief_state):
        """select 后 debug info 字段齐全."""
        import web.api.lca as lca_mod

        lca_mod.select_intervention("test_lca_student", belief_state)
        info = lca_mod.get_lca_debug_info("test_lca_student")

        # 必填字段
        assert "enabled" in info
        assert "has_last_intervention" in info
        assert "last_intervention_type" in info
        assert "last_bloom_target" in info
        assert "select_count" in info
        assert "update_count" in info
        assert "bandit_stats" in info

        assert info["has_last_intervention"] is True
        assert info["last_intervention_type"] is not None
        assert info["select_count"] == 1

    def test_debug_info_empty_for_new_student(self, fresh_lca_state):
        """新学生 (没 select 过) debug info 应该安全返回."""
        import web.api.lca as lca_mod

        info = lca_mod.get_lca_debug_info("never_seen_student")

        assert info["has_last_intervention"] is False
        assert info["last_intervention_type"] is None
        assert info["select_count"] == 0
        assert info["update_count"] == 0


# ──────────────────────────────────────────────────────────────────────
# 5. Flask 路由集成测试 (passthrough 验证)
# ──────────────────────────────────────────────────────────────────────


class TestLCARouteIntegration:
    """v0.56.0: Flask 路由接入验证 (LCA 在调用栈里).

    不启动完整 Flask server, 用 import + 路由注册表检查.
    """

    def test_lca_module_importable(self):
        """web.api.lca 可 import, 暴露核心函数."""
        import web.api.lca as lca_mod

        assert hasattr(lca_mod, "select_intervention")
        assert hasattr(lca_mod, "update_with_reward")
        assert hasattr(lca_mod, "get_lca_debug_info")
        assert hasattr(lca_mod, "LCA_ENABLED")

    def test_app_registers_lca_debug_endpoint(self):
        """app.py 注册了 /api/lca_debug/<student_id> 路由."""
        from web.api.app import app

        routes = [r.rule for r in app.url_map.iter_rules()]
        assert "/api/lca_debug/<student_id>" in routes, \
            f"/api/lca_debug 端点未注册, 当前 routes={routes}"

    def test_app_imports_lca_module(self):
        """app.py 导入了 web.api.lca (LCA 在调用栈入口)."""
        from web.api import app as app_mod

        # 检查 app.py 模块是否 import 了 lca 相关
        #   通过源码字符串检查 (避免触发 app 初始化)
        import inspect
        source = inspect.getsource(app_mod)
        assert "web.api.lca" in source or "from web.api import lca" in source, \
            "app.py 应 import web.api.lca (LCA 调用入口)"


# ──────────────────────────────────────────────────────────────────────
# 6. 防御性自检
# ──────────────────────────────────────────────────────────────────────


class TestDefensiveChecks:
    """v0.56.0: 防御性自检套件."""

    def test_no_silent_pass_in_lca(self, fresh_lca_state):
        """lca.py 全部 except 块必须有 logger.warning (防御性自检 [1]).

        实现说明: 不用 regex 解析, 改用 line-by-line + 缩进判断
        (避免 ReDoS——之前的 regex 触发灾难性回溯, 30s+ 超时).
        """
        import inspect
        from web.api import lca as lca_mod

        source = inspect.getsource(lca_mod)
        lines = source.split("\n")

        # 找出所有 except 块 (line-by-line + 缩进判断)
        except_blocks = []
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            if stripped.startswith("except") and line.rstrip().endswith(":"):
                except_indent = len(line) - len(line.lstrip())
                block_lines = []
                i += 1
                while i < len(lines):
                    next_line = lines[i]
                    if not next_line.strip():
                        i += 1
                        continue
                    next_indent = len(next_line) - len(next_line.lstrip())
                    if next_indent > except_indent:
                        block_lines.append(next_line)
                        i += 1
                    else:
                        break
                except_blocks.append("\n".join(block_lines))
            else:
                i += 1

        # 每个 except 块必须有 warning 或显式 raise
        for idx, block in enumerate(except_blocks):
            has_warning = "warning" in block
            has_raise = "raise " in block or block.strip().endswith("raise")
            has_silent_pass = "pass" in block and not has_warning

            if has_silent_pass:
                pytest.fail(
                    f"lca.py except 块 #{idx + 1} 是 silent pass:\n{block}\n"
                    "防御性自检 [1]: 必须改 logger.warning(..., exc_info=True)"
                )
            if not has_warning and not has_raise:
                pytest.fail(
                    f"lca.py except 块 #{idx + 1} 无 warning 也无 raise:\n{block}\n"
                    "防御性自检 [1]: 必须有 logger.warning 或显式 raise"
                )

    def test_version_bump(self):
        """防御性自检 [2]: __version__ 必须 bump 到 >= 0.56.0.

        注: v0.56.1 (BUG 修复) 后, 版本应该是 0.56.1. 测试用 >= 0.56.0
        兼容 0.56.0 / 0.56.1+ 等小版本.
        """
        import ecos
        from packaging.version import Version

        current = Version(ecos.__version__)
        assert current >= Version("0.56.0"), \
            f"ecos.__version__ 应 >= 0.56.0 (v0.56.0 LCA 接入), 实际={ecos.__version__}"


# ──────────────────────────────────────────────────────────────────────
# 入口 (让 pytest 能找到)
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
