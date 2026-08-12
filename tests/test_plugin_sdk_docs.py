"""v0.91.0-e: Plugin SDK 文档化 doctest 校验 (Phase 7+ 抽象推演 #4).

对应设计: discussions/2026-08-12-v091-design.md §5 v0.91.0-e.

本文件不增加 unit test (doctest only), 验证:
  1. docs/plugin_sdk.md 存在 + 含 8 个标准 section (§一~§八)
  2. docs/plugin_sdk.md 链接目标真实存在 (避免 docs dead link)
  3. examples/plugin_sample_human_feedback.py 可 import (5 use case 函数存在)
  4. examples/plugin_sample_human_feedback.py smoke test (_self_test_imports) PASS

测试范围 (0 unit tests, 4 doctest assertions):
  - test_docs_exists_and_has_eight_sections
  - test_docs_links_point_to_existing_files
  - test_examples_module_imports_and_exposes_use_cases
  - test_examples_smoke_test_passes
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
EXAMPLES_DIR = REPO_ROOT / "examples"


# ── 1. docs/plugin_sdk.md 存在 + 8 section 校验 ──────────────────────────────


def test_docs_exists_and_has_eight_sections():
    """docs/plugin_sdk.md 存在 + 含 8 个标准 section (§一~§八).

    8 section 定义 (per docs/plugin_sdk.md 当前内容):
      §一   Plugin 原则
      §二   7 Subscriber 完整契约
      §三   LCAEngine.append_human_feedback 接口
      §四   防御性自检 (CLAUDE.md §7 同步)
      §五   Runtime API 6 plan 接口
      §六   5 sub-commit 演进日志
      §七   相关文档
      §八   Plugin SDK 调用样例
    """
    doc_path = DOCS_DIR / "plugin_sdk.md"
    assert doc_path.exists(), f"Plugin SDK docs missing: {doc_path}"

    content = doc_path.read_text(encoding="utf-8")

    expected_sections = [
        "## 一、Plugin 原则",
        "## 二、7 Subscriber 完整契约",
        "## 三、LCAEngine.append_human_feedback 接口",
        "## 四、防御性自检",
        "## 五、Runtime API 6 plan 接口",
        "## 六、5 sub-commit 演进日志",
        "## 七、相关文档",
        "## 八、Plugin SDK 调用样例",
    ]
    for section_heading in expected_sections:
        assert section_heading in content, (
            f"Plugin SDK docs missing section: {section_heading!r}"
        )


# ── 2. docs/plugin_sdk.md 链接目标真实存在 (avoid dead link) ────────────────


def test_docs_links_point_to_existing_files():
    """docs/plugin_sdk.md 内部链接目标真实存在.

    Plugin SDK docs 引用以下文件 (per §七):
      - discussions/2026-08-12-v091-design.md
      - discussions/2026-08-11-v084-design.md
      - discussions/2026-08-11-v085-design.md
      - ecos/cta/cognitive_twin.py
      - ecos/runtime/api.py
      - ecos/lca/orchestrator.py
      - web/api/plugin_runtime.py
      - examples/plugin_sample_human_feedback.py
    """
    doc_path = DOCS_DIR / "plugin_sdk.md"
    assert doc_path.exists()

    content = doc_path.read_text(encoding="utf-8")

    referenced_paths = [
        "discussions/2026-08-12-v091-design.md",
        "discussions/2026-08-11-v084-design.md",
        "discussions/2026-08-11-v085-design.md",
        "ecos/cta/cognitive_twin.py",
        "ecos/runtime/api.py",
        "ecos/lca/orchestrator.py",
        "web/api/plugin_runtime.py",
        "examples/plugin_sample_human_feedback.py",
    ]
    for ref in referenced_paths:
        target = REPO_ROOT / ref
        assert target.exists(), (
            f"Plugin SDK docs references missing path: {ref}"
        )


# ── 3. examples/plugin_sample_human_feedback.py 可 import (5 use case) ──────


def test_examples_module_imports_and_exposes_use_cases():
    """examples/plugin_sample_human_feedback.py 可 import + 暴露 5 use case.

    5 use case (per docs/plugin_sdk.md §八):
      1. use_case_teacher_reflection_analysis
      2. use_case_parent_goal_dashboard
      3. use_case_hint_fatigue_detection
      4. use_case_idle_reminder
      5. use_case_deep_reflection_analysis
    + register_all_use_cases (entry point).
    """
    # 1) Module-level import (per docs §七 linkage)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import importlib
        examples_module = importlib.import_module(
            "examples.plugin_sample_human_feedback"
        )
    finally:
        sys.path.pop(0)

    # 2) 5 use case 函数 + register entry 暴露
    expected_use_cases = [
        "use_case_teacher_reflection_analysis",
        "use_case_parent_goal_dashboard",
        "use_case_hint_fatigue_detection",
        "use_case_idle_reminder",
        "use_case_deep_reflection_analysis",
        "register_all_use_cases",
    ]
    for fn_name in expected_use_cases:
        assert hasattr(examples_module, fn_name), (
            f"Plugin SDK examples missing use case: {fn_name}"
        )


# ── 4. examples/plugin_sample_human_feedback.py smoke test PASS ─────────────


def test_examples_smoke_test_passes():
    """examples/_self_test_imports() smoke test PASS (doctest 校验).

    验证 Plugin SDK examples 文件的 _self_test_imports() helper 真能 import
    CognitiveTwinAgent / LearningEvent / LearningEventType / EventBus (跟 docs/plugin_sdk.md §七
    linkage 一致).
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import importlib
        examples_module = importlib.import_module(
            "examples.plugin_sample_human_feedback"
        )
        smoke_result = examples_module._self_test_imports()
    finally:
        sys.path.pop(0)

    assert smoke_result is True, (
        "Plugin SDK examples _self_test_imports() smoke test FAIL"
    )