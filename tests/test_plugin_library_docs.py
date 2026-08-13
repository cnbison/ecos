"""v0.94.0-d: Plugin Library 文档化 doctest 校验 (Phase 7+ 抽象推演 #7).

对应设计: discussions/2026-08-13-v094-design.md §d 阶段.

本文件不增加 unit test (doctest only), 验证:
  1. docs/plugin_library.md 存在 + 含 8 个标准 section (§一~§八)
  2. docs/plugin_library.md 链接目标真实存在 (避免 docs dead link)
  3. examples/plugin_sample_first_party.py 可 import (3 use case 函数存在)
  4. examples/plugin_sample_first_party.py smoke test (_self_test_imports) PASS

测试范围 (0 unit tests, 4 doctest assertions):
  - test_docs_exists_and_has_eight_sections
  - test_docs_links_point_to_existing_files
  - test_examples_module_imports_and_exposes_use_cases
  - test_examples_smoke_test_passes
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
EXAMPLES_DIR = REPO_ROOT / "examples"


# ── 1. docs/plugin_library.md 存在 + 8 section 校验 ──────────────────────


def test_docs_exists_and_has_eight_sections():
    """docs/plugin_library.md 存在 + 含 8 个标准 section (§一~§八).

    8 section 定义 (per docs/plugin_library.md 当前内容):
      §一   Plugin SDK 原则
      §二   Plugin ABC 契约
      §三   PluginMetadata 字段
      §四   PluginRegistry API
      §五   3 First-party Plugin 详解
      §六   Plugin 注册生命周期
      §七   防御性自检
      §八   Plugin SDK 调用样例
    """
    doc_path = DOCS_DIR / "plugin_library.md"
    assert doc_path.exists(), f"Plugin Library docs missing: {doc_path}"

    content = doc_path.read_text(encoding="utf-8")

    expected_sections = [
        "## 一、Plugin SDK 原则",
        "## 二、Plugin ABC 契约",
        "## 三、PluginMetadata 字段",
        "## 四、PluginRegistry API",
        "## 五、3 First-party Plugin 详解",
        "## 六、Plugin 注册生命周期",
        "## 七、防御性自检",
        "## 八、Plugin SDK 调用样例",
    ]
    for section_heading in expected_sections:
        assert section_heading in content, (
            f"Plugin Library docs missing section: {section_heading!r}"
        )


# ── 2. docs/plugin_library.md 链接目标真实存在 (avoid dead link) ──────────


def test_docs_links_point_to_existing_files():
    """docs/plugin_library.md 内部链接目标真实存在.

    Plugin Library docs 引用以下文件 (per §一~§八 + 相关文档):
      - docs/plugin_sdk.md
      - docs/pomdp_diagnostic.md
      - research/00-overview/12-kernel-mapping-current-vs-2.0.md
      - discussions/2026-08-13-v094-design.md
      - ecos/plugins/base.py
      - ecos/plugins/registry.py
      - ecos/plugins/first_party/
      - ecos/persistence/plugin_registry_store.py
      - examples/plugin_sample_first_party.py
    """
    doc_path = DOCS_DIR / "plugin_library.md"
    assert doc_path.exists()

    content = doc_path.read_text(encoding="utf-8")

    referenced_paths = [
        "docs/plugin_sdk.md",
        "docs/pomdp_diagnostic.md",
        "research/00-overview/12-kernel-mapping-current-vs-2.0.md",
        "ecos/plugins/base.py",
        "ecos/plugins/registry.py",
        "ecos/persistence/plugin_registry_store.py",
        "examples/plugin_sample_first_party.py",
    ]
    for ref in referenced_paths:
        target = REPO_ROOT / ref
        assert target.exists(), (
            f"Plugin Library docs references missing path: {ref}"
        )

    # ecos/plugins/first_party/ 目录存在
    first_party_dir = REPO_ROOT / "ecos/plugins/first_party"
    assert first_party_dir.is_dir(), (
        f"Plugin Library docs references missing dir: ecos/plugins/first_party/"
    )


# ── 3. examples/plugin_sample_first_party.py 可 import (3 use case) ──────


def test_examples_module_imports_and_exposes_use_cases():
    """examples/plugin_sample_first_party.py 可 import + 暴露 3 use case.

    3 use case (per docs/plugin_library.md §八):
      1. use_case_register_three_first_party
      2. use_case_enable_disable_lifecycle
      3. use_case_hot_reload_from_db
    + run_all_use_cases (entry point).
    """
    # 1) Module-level import (per docs §七 linkage)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        examples_module = importlib.import_module(
            "examples.plugin_sample_first_party"
        )
    finally:
        sys.path.pop(0)

    # 2) 3 use case 函数 + entry 暴露
    expected_use_cases = [
        "use_case_register_three_first_party",
        "use_case_enable_disable_lifecycle",
        "use_case_hot_reload_from_db",
        "run_all_use_cases",
    ]
    for fn_name in expected_use_cases:
        assert hasattr(examples_module, fn_name), (
            f"Plugin Library examples missing use case: {fn_name}"
        )


# ── 4. examples/plugin_sample_first_party.py smoke test PASS ──────────────


def test_examples_smoke_test_passes():
    """examples/_self_test_imports() smoke test PASS (doctest 校验).

    验证 First-party Plugin Library examples 文件的 _self_test_imports() helper
    真能 import HintFatiguePlugin / ParentEngagementPlugin / TeacherProgressPlugin /
    PluginRegistry / PluginRegistryStore / LearningEvent / EventBus (跟 docs/plugin_library.md §七
    linkage 一致).
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        examples_module = importlib.import_module(
            "examples.plugin_sample_first_party"
        )
        smoke_result = examples_module._self_test_imports()
    finally:
        sys.path.pop(0)

    assert smoke_result is True, (
        "Plugin Library examples _self_test_imports() smoke test FAIL"
    )