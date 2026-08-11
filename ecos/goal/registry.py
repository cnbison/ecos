"""Goal Ontology — 默认 Capability Registry (v0.86.0-d).

对应 12-kernel-mapping §2.3 Goal Ontology (Capability 5 条默认):
    Python 学科默认 5 条 Capability:
      1. python_variables:  变量赋值与使用
      2. python_loops:      循环 (for / while)
      3. python_functions:  函数定义与调用
      4. python_conditionals: 条件分支 (if / elif / else)
      5. python_strings:    字符串操作

设计:
    - DEFAULT_CAPABILITIES_LIST: 5 条 Capability 列表 (cold-start 用)
    - register_default_capabilities(onto=None): 把 5 条注入 ontology singleton
    - 向后兼容: 现有 GoalOntology registry 行为不变

向后兼容:
    - 注册是 idempotent (覆盖同名 capability)
    - 没业务代码强依赖 DEFAULT_CAPABILITY_REGISTRY, 仅 cold-start 友好
    - 防御性自检 [8] 仍 hard block (registry 不 mutate state)
"""

from __future__ import annotations

import logging
from typing import List, Optional

from .goal import Capability
from .ontology import GoalOntology, get_default_ontology

_log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 5 条 Python 默认 Capability
# ---------------------------------------------------------------------------

DEFAULT_CAPABILITIES_LIST: List[Capability] = [
    Capability(
        name="python_variables",
        description="Python 变量赋值、命名与使用",
        domain="python",
    ),
    Capability(
        name="python_loops",
        description="Python 循环结构 (for / while)",
        domain="python",
    ),
    Capability(
        name="python_functions",
        description="Python 函数定义、参数与返回值",
        domain="python",
    ),
    Capability(
        name="python_conditionals",
        description="Python 条件分支 (if / elif / else)",
        domain="python",
    ),
    Capability(
        name="python_strings",
        description="Python 字符串操作 (切片 / 拼接 / 格式化)",
        domain="python",
    ),
]


def register_default_capabilities(onto: Optional[GoalOntology] = None) -> int:
    """注册 5 条 Python 默认 Capability 到 ontology.

    Args:
        onto: 目标 ontology (None = 用 default singleton)

    Returns:
        注册数量 (默认 5)

    防御性: 重复注册同名 capability 走覆盖式 (per register_capability), 不 raise
    """
    if onto is None:
        onto = get_default_ontology()
    for cap in DEFAULT_CAPABILITIES_LIST:
        onto.register_capability(cap)
    _log.info(
        "register_default_capabilities: 注册 %d 条 Python 默认 Capability",
        len(DEFAULT_CAPABILITIES_LIST),
    )
    return len(DEFAULT_CAPABILITIES_LIST)


__all__ = [
    "DEFAULT_CAPABILITIES_LIST",
    "register_default_capabilities",
]
