"""v0.93.0-d: POMDP Diagnostic 文档化 doctest 校验 (Phase 7+ 抽象推演 #6).

对应设计: discussions/2026-08-12-v093-design.md §4 v0.93.0-d.

本文件不增加 unit test (doctest only), 验证:
  1. docs/pomdp_diagnostic.md 存在 + 含 8 个标准 section (§一~§八)
  2. docs/pomdp_diagnostic.md 链接目标真实存在 (避免 docs dead link)
  3. examples/plugin_sample_pomdp_diagnostic.py 可 import (3 use case 函数存在)
  4. examples/plugin_sample_pomdp_diagnostic.py smoke test PASS

测试范围 (0 unit tests, 4 doctest assertions):
  - test_docs_exists_and_has_eight_sections
  - test_docs_links_point_to_existing_files
  - test_examples_module_imports_and_exposes_use_cases
  - test_examples_smoke_test_passes
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
EXAMPLES_DIR = REPO_ROOT / "examples"


# ── 1. docs/pomdp_diagnostic.md 存在 + 8 section 校验 ──────────────────────


def test_docs_exists_and_has_eight_sections():
    """docs/pomdp_diagnostic.md 存在 + 含 8 个标准 section (§一~§八).

    8 section 定义 (per docs/pomdp_diagnostic.md 当前内容):
      §一   POMDP Diagnostic 原则
      §二   POMDPDiagnostic 字段 (Frozen Dataclass)
      §三   Runtime.diagnose_pomdp API
      §四   LCAEngine.get_pomdp_diagnostic API
      §五   Plugin SDK 第 8 Subscriber
      §六   演化追踪 (Timed Snapshots)
      §七   防御性自检
      §八   调用样例
    """
    doc_path = DOCS_DIR / "pomdp_diagnostic.md"
    assert doc_path.exists(), f"POMDP Diagnostic docs missing: {doc_path}"

    content = doc_path.read_text(encoding="utf-8")

    expected_sections = [
        "## 一、POMDP Diagnostic 原则",
        "## 二、POMDPDiagnostic 字段",
        "## 三、Runtime.diagnose_pomdp API",
        "## 四、LCAEngine.get_pomdp_diagnostic API",
        "## 五、Plugin SDK 第 8 Subscriber",
        "## 六、演化追踪",
        "## 七、防御性自检",
        "## 八、调用样例",
    ]
    for section_heading in expected_sections:
        assert section_heading in content, (
            f"POMDP Diagnostic docs missing section: {section_heading!r}"
        )


# ── 2. docs/pomdp_diagnostic.md 链接目标真实存在 (avoid dead link) ─────────


def test_docs_links_point_to_existing_files():
    """docs/pomdp_diagnostic.md 内部链接目标真实存在.

    POMDP Diagnostic docs 引用以下文件 (per §一+§八):
      - discussions/2026-08-12-v093-design.md
      - ecos/lca/l4_optimization/pomdp_diagnostic.py
      - ecos/lca/l4_optimization/pomdp.py
      - ecos/lca/orchestrator.py
      - ecos/runtime/api.py
      - web/api/plugin_runtime.py
      - examples/plugin_sample_pomdp_diagnostic.py
    """
    doc_path = DOCS_DIR / "pomdp_diagnostic.md"
    assert doc_path.exists()

    content = doc_path.read_text(encoding="utf-8")

    referenced_paths = [
        "discussions/2026-08-12-v093-design.md",
        "ecos/lca/l4_optimization/pomdp_diagnostic.py",
        "ecos/lca/l4_optimization/pomdp.py",
        "ecos/lca/orchestrator.py",
        "ecos/runtime/api.py",
        "web/api/plugin_runtime.py",
        "examples/plugin_sample_pomdp_diagnostic.py",
    ]
    for ref in referenced_paths:
        target = REPO_ROOT / ref
        assert target.exists(), (
            f"POMDP Diagnostic docs references missing path: {ref}"
        )


# ── 3. examples/plugin_sample_pomdp_diagnostic.py 可 import (3 use case) ───


def test_examples_module_imports_and_exposes_use_cases():
    """examples/plugin_sample_pomdp_diagnostic.py 可 import + 暴露 3 use case.

    3 use case (per docs/pomdp_diagnostic.md §八):
      1. use_case_teacher_progress_review
      2. use_case_parent_engagement_dashboard
      3. use_case_student_self_reflection
    + smoke_test (entry point).
    """
    # 1) Module-level import (per docs §八 linkage)
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import importlib
        examples_module = importlib.import_module(
            "examples.plugin_sample_pomdp_diagnostic"
        )
    finally:
        sys.path.pop(0)

    # 2) 3 use case 函数 + smoke entry 暴露
    expected_use_cases = [
        "use_case_teacher_progress_review",
        "use_case_parent_engagement_dashboard",
        "use_case_student_self_reflection",
        "smoke_test",
    ]
    for fn_name in expected_use_cases:
        assert hasattr(examples_module, fn_name), (
            f"POMDP Diagnostic examples missing use case: {fn_name}"
        )


# ── 4. examples/plugin_sample_pomdp_diagnostic.py smoke test PASS ──────────


def test_examples_smoke_test_passes():
    """examples/plugin_sample_pomdp_diagnostic.py smoke_test() PASS (doctest 校验).

    验证 POMDP Diagnostic examples 文件的 smoke_test() helper 真能 register 3 use case
    subscribers + 调用 student self_reflection signature (跟 docs/pomdp_diagnostic.md §八
    linkage 一致).
    """
    sys.path.insert(0, str(REPO_ROOT))
    try:
        import importlib
        examples_module = importlib.import_module(
            "examples.plugin_sample_pomdp_diagnostic"
        )
        # smoke_test() 不应抛异常
        examples_module.smoke_test()
    finally:
        sys.path.pop(0)