"""v0.93.0-c: POMDP 演化追踪测试 (timed snapshots N=50/K=10).

对应设计: discussions/2026-08-12-v093-design.md §3.

v0.93.0-c 演化追踪 (v0.95+ Teacher/Parent Dashboard 趋势渲染用):
  - POMDPPolicy._evolution: List[POMDPDiagnostic] (cap K=10 FIFO)
  - _update_count: int (累计 _update_t_r 调用次数)
  - _next_snapshot_at: int (下次触发阈值, 默认 50)
  - _take_evolution_snapshot: 每 N=50 次 _update_t_r 截一个 POMDPDiagnostic 写 _evolution
  - get_evolution / evolution_snapshot_count: getter (跟 v0.81 EventLog retention 同 pattern)

测试范围 (4 tests):
  1. evolution 触发阈值 N=50 (1 test): _update_count < 50 不触发, == 50 触发
  2. evolution FIFO cap K=10 (1 test): 超过 cap 丢最早
  3. get_evolution 返 copy (1 test): 外部 mutation 不影响内部
  4. evolution_snapshot_count 监控 (1 test): 当前长度返回 0 <= N <= 10
"""

from __future__ import annotations

import numpy as np

from ecos.lca.l4_optimization.pomdp import POMDPPolicy
from ecos.lca.l4_optimization.pomdp_diagnostic import POMDPDiagnostic


# ---------------------------------------------------------------------------
# 1. evolution 触发阈值 N=50 (1 test)
# ---------------------------------------------------------------------------


def test_evolution_snapshot_triggers_at_threshold_50():
    """_update_t_r 调用 50 次时 _take_evolution_snapshot 触发一次 (_evolution.append).

    防御性自检 [1]: get_diagnostic 派生失败 _log.warning 不 raise (演化 snapshot graceful).
    """
    p = POMDPPolicy(seed=42)
    assert len(p.get_evolution()) == 0
    assert p.evolution_snapshot_count() == 0

    # _update_t_r 49 次 → 不应触发 (默认 N=50)
    for i in range(49):
        p.update(arm=0, reward=0.5, observation=0)
    assert len(p.get_evolution()) == 0
    assert p._update_count == 49

    # 第 50 次触发 snapshot
    p.update(arm=0, reward=0.5, observation=0)
    assert p._update_count == 50
    assert len(p.get_evolution()) == 1
    assert isinstance(p.get_evolution()[0], POMDPDiagnostic)
    # _next_snapshot_at 推进到 100
    assert p._next_snapshot_at == 100


# ---------------------------------------------------------------------------
# 2. evolution FIFO cap K=10 (1 test)
# ---------------------------------------------------------------------------


def test_evolution_caps_at_10_fifo():
    """_evolution cap K=10, 超过时最早 snapshot 被丢弃 (FIFO).

    模拟: 把 _next_snapshot_at 设 5, _evolution_interval 设 5, 跑 12 次 snapshot (60 次 update_t_r)
    → 12 个 snapshot 应 cap 到 10, 最早 2 个丢.
    """
    p = POMDPPolicy(seed=42)
    p._next_snapshot_at = 5  # 加快触发
    p._evolution_interval = 5

    # 60 次 _update_t_r → 12 个 snapshot (5/10/15/20/25/30/35/40/45/50/55/60)
    for i in range(60):
        p.update(arm=0, reward=0.5, observation=0)

    # cap K=10 → 应保留最后 10 个 (5th ~ 12th snapshot)
    assert len(p.get_evolution()) == 10

    # 所有 snapshot 都是 POMDPDiagnostic frozen dataclass
    for snap in p.get_evolution():
        assert isinstance(snap, POMDPDiagnostic)


# ---------------------------------------------------------------------------
# 3. get_evolution 返 copy (1 test)
# ---------------------------------------------------------------------------


def test_get_evolution_returns_copy_not_internal_list():
    """get_evolution 返 list(self._evolution) copy, 外部 mutation 不影响 self._evolution.

    防御性: 防止 caller 误 mutation 内部 list 干扰后续 snapshot.
    """
    p = POMDPPolicy(seed=42)
    p._next_snapshot_at = 1  # 每次 update_t_r 都 snapshot
    p._evolution_interval = 1  # 触发后下次阈值 +1 (而非默认 +50)
    p.update(arm=0, reward=0.5, observation=0)
    p.update(arm=1, reward=0.7, observation=1)

    assert len(p.get_evolution()) == 2

    # 外部 mutation
    external = p.get_evolution()
    external.clear()
    # 内部不应被影响
    assert len(p.get_evolution()) == 2
    assert p.evolution_snapshot_count() == 2


# ---------------------------------------------------------------------------
# 4. evolution_snapshot_count 监控 (1 test)
# ---------------------------------------------------------------------------


def test_evolution_snapshot_count_increments_per_snapshot():
    """evolution_snapshot_count 返当前 self._evolution 长度 (0 <= N <= 10)."""
    p = POMDPPolicy(seed=42)
    assert p.evolution_snapshot_count() == 0

    p._next_snapshot_at = 1
    p._evolution_interval = 1
    for i in range(15):
        p.update(arm=0, reward=0.5, observation=0)

    # cap K=10: 15 次 update_t_r 全 snapshot, 但 cap 到 10
    assert p.evolution_snapshot_count() == 10
    # _update_count 应累计 15
    assert p._update_count == 15
    # _next_snapshot_at 应推进到 16 (1 + 15)
    assert p._next_snapshot_at == 16