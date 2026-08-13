"""ECOS Plugin SDK —— v0.94.0-a.

第一方 plugin 库 (Kernel-only SDK, Phase 7+ 抽象推演 #7).
Plugin SDK 包含:
    - Plugin(ABC): SDK 基类 (4 abstract method + PluginMetadata frozen dataclass)
    - PluginRegistry: singleton 注册管理 (v0.94.0-b)
    - 3 first-party plugin: HintFatiguePlugin / ParentEngagementPlugin / TeacherProgressPlugin (v0.94.0-c)

Plugin lifecycle:
    instantiate → register → enable → on_event (多次) → disable → unregister

Kernel-first 战略:
    - Plugin SDK 是 Kernel-level (不引用 BeliefState / LCAEngine / Runtime)
    - Plugin 不 mutate Kernel state (defensive check [8] 仍 hard block)
    - Plugin 通过 Runtime API 读 Kernel state (e.g. Runtime.diagnose_pomdp)
"""

from __future__ import annotations

from ecos.plugins.base import (
    SCHEMA_VERSION,
    Plugin,
    PluginMetadata,
)

__version__ = SCHEMA_VERSION  # "0.94.0"

__all__ = [
    "SCHEMA_VERSION",
    "Plugin",
    "PluginMetadata",
]