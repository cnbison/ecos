"""ECOS 第一方 Plugin 库 —— v0.94.0-c (Phase 7+ 抽象推演 #7).

3 first-party plugin (Kernel-only SDK reference implementations):
    - HintFatiguePlugin: 订阅 hint_requested, 计数 > 5 告警
    - ParentEngagementPlugin: 订阅 pomdp_diagnostic_updated, 读 POMDPDiagnostic.evolution
    - TeacherProgressPlugin: 订阅 pomdp_diagnostic_updated, 读 POMDPDiagnostic.coverage 冷启动判断

设计原则 (per 12-kernel-mapping §6 + docs/plugin_library.md):
    - Plugin 不调 LCAEngine / Runtime write API, 只读 Kernel state (event.payload)
    - Plugin 不 mutate BeliefState (defensive check [8] 仍 hard block)
    - Plugin 通过 PluginRegistry.register + PluginRuntime.start() 联合挂载
    - 3 first-party plugin 覆盖 3 类 audience (学生 hint 疲劳 / 家长 engagement / 教师 progress)

用法:
    >>> from ecos.plugins.registry import PluginRegistry
    >>> from ecos.plugins.first_party import (
    ...     HintFatiguePlugin, ParentEngagementPlugin, TeacherProgressPlugin,
    ... )
    >>> registry = PluginRegistry()
    >>> registry.register(HintFatiguePlugin())
    >>> registry.register(ParentEngagementPlugin())
    >>> registry.register(TeacherProgressPlugin())
    >>> registry.list_names()
    ['hint_fatigue', 'parent_engagement', 'teacher_progress']
"""

from __future__ import annotations

from ecos.plugins.first_party.hint_fatigue import HINT_FATIGUE_THRESHOLD, HintFatiguePlugin
from ecos.plugins.first_party.parent_engagement import ParentEngagementPlugin
from ecos.plugins.first_party.teacher_progress import (
    COLD_START_COVERAGE_THRESHOLD,
    TeacherProgressPlugin,
)

__all__ = [
    "HintFatiguePlugin",
    "ParentEngagementPlugin",
    "TeacherProgressPlugin",
    "HINT_FATIGUE_THRESHOLD",
    "COLD_START_COVERAGE_THRESHOLD",
]