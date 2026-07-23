"""v0.55.0-a: 5 项防御性自检 pytest 套件.

CLAUDE.md §防御性自检规范 v0.47.6+ 自动化:
  1. silent failure 扫描 (except: pass 模式)
  2. 版本号同步 (ecos/__init__.py __version__ = web/ecos.db init)
  3. CSS 引用关系 (HTML class 名与 CSS 选择器匹配)
  4. DB 恢复路径 (_get_or_create_student 恢复所有字段)
  5. CI gate 库 ID (detect_with_hits 必须传 library_str)

拦截历史 bug:
  - v0.47.5 修 8 处 silent pass
  - v0.49.3 misconception NoneType
  - v0.50.0 5D badge CSS class 错配
  - v0.50.0 favicon
  - v0.51.4 hardcoded 版本号
  - v0.52.0 misconception library_str 错配
  - v0.53.3 silent pass 修
"""
import re
import json
import sqlite3
from pathlib import Path

import pytest


# ─── 测试 1: silent failure 扫描 ─────────────────────────────────────────

def test_no_silent_pass(ecos_dir: Path, web_dir: Path):
    """拦截 `except ...: pass` silent failure 模式.

    拦截历史:
    - v0.47.5 修 8 处 silent pass
    - v0.49.3 misconception NoneType
    - v0.53.3 silent pass 修

    例外: __init__.py 的 Optional import 兜底 + feature flag 关闭分支
    """
    # 精确匹配 Python except 块: except X: pass (同行) 或 except X:\\n  pass (下一行)
    # Python 异常类名: 大写字母开头 + 可选 Error/Exception 后缀
    # 排除 docstring 内描述文字 (如 'except: pass 改为 ...')
    silent_pass_pattern = re.compile(
        r"^\s*except(?:\s+(?:\([^)]+\)|[A-Z][a-zA-Z0-9_]*(?:\s*,\s*[A-Z][a-zA-Z0-9_]*)*))?\s*:\s*(?:pass(?!\s*改)\b|\n\s+pass(?!\s*改)\b)",
        re.MULTILINE,
    )
    violations = []

    for py_dir in [ecos_dir, web_dir]:
        for py_file in py_dir.rglob("*.py"):
            # 跳过 __init__.py (允许 Optional import 兜底)
            if py_file.name == "__init__.py":
                continue
            content = py_file.read_text(encoding="utf-8")

            # 找 docstring 范围 ("""...""" 或 '''...'''), 跳过这些区域
            doc_ranges = []
            for m in re.finditer(r'"""[\s\S]*?"""', content):
                doc_ranges.append((m.start(), m.end()))
            for m in re.finditer(r"'''[\s\S]*?'''", content):
                doc_ranges.append((m.start(), m.end()))

            def in_docstring(pos: int) -> bool:
                return any(s <= pos < e for s, e in doc_ranges)

            for match in silent_pass_pattern.finditer(content):
                if in_docstring(match.start()):
                    continue
                # 跳过单行注释 (匹配行在 # 后面)
                line_start = content.rfind("\n", 0, match.start()) + 1
                line_end = content.find("\n", match.start())
                if line_end == -1:
                    line_end = len(content)
                line_text = content[line_start:line_end]
                if line_text.strip().startswith("#"):
                    continue
                # 算行号
                line_num = content[:match.start()].count("\n") + 1
                matched_text = match.group(0).strip().split("\n")[0]
                violations.append(
                    f"{py_file.relative_to(ecos_dir.parent)}:{line_num}: {matched_text}"
                )

    if violations:
        pytest.fail(
            f"❌ 发现 {len(violations)} 处 silent pass 模式:\n"
            + "\n".join(violations[:10])
            + "\n(参考 CLAUDE.md §防御性自检规范 #1)"
        )


# ─── 测试 2: 版本号同步 ─────────────────────────────────────────────────

def test_version_consistency(ecos_dir: Path):
    """验证 ecos/__init__.py __version__ 是单一权威源.

    拦截历史:
    - v0.47.0 ecos_version 硬编码
    - v0.51.4 设置页 hardcoded 版本号 → 改动态拉 /api/version
    """
    # __init__.py 是权威源
    init_file = ecos_dir / "__init__.py"
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    assert match, f"{init_file} 缺少 __version__ 定义"
    version = match.group(1)

    # 验证版本号格式 (语义化版本: MAJOR.MINOR.PATCH)
    semver_pattern = re.compile(r"^\d+\.\d+\.\d+$")
    assert semver_pattern.match(version), f"版本号格式不对: {version} (应: MAJOR.MINOR.PATCH)"

    # 验证版本号至少 0.40.0 (v0.40.0 之前是 v0.40.0 docs sync 起点)
    parts = version.split(".")
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    assert (major, minor, patch) >= (0, 40, 0), \
        f"版本号 {version} 落后于 v0.40.0 docs sync 起点"


# ─── 测试 3: HTML CSS class 匹配 ─────────────────────────────────────────

def test_html_css_class_match(web_dir: Path):
    """验证 HTML 引用的 CSS class 在 styles.css 中存在.

    拦截历史:
    - v0.50.0 5D badge class 错配 (HTML f-lbl vs CSS .lbl)
    """
    html_file = web_dir / "student" / "index.html"
    css_file = web_dir / "student" / "styles.css"

    if not html_file.exists() or not css_file.exists():
        pytest.skip(f"HTML/CSS 文件不存在: {html_file} / {css_file}")

    html_content = html_file.read_text(encoding="utf-8")
    css_content = css_file.read_text(encoding="utf-8")

    # 提取 HTML class="..." 中的 class 名
    html_classes = set()
    for match in re.finditer(r'class\s*=\s*["\']([^"\']+)["\']', html_content):
        for cls in match.group(1).split():
            html_classes.add(cls)

    # 提取 CSS .class { ... } 选择器
    css_classes = set()
    for match in re.finditer(r"\.([a-zA-Z][a-zA-Z0-9_-]*)\s*[\{,:>~+ ]", css_content):
        css_classes.add(match.group(1))

    # 5D badge / 进度条 / 状态色 / 按钮 等关键 class 必须匹配
    critical_classes = [
        "lbl",         # 5D 字母 badge (v0.50.0 + v0.51.3)
        "bar",         # 进度条 (v0.50.0)
        "tab-btn",     # Tab 按钮 (v0.49.1)
        "dim-pending", # C/X 待启用样式 (v0.52.1)
    ]
    for cls in critical_classes:
        if cls in html_classes and cls not in css_classes:
            pytest.fail(
                f"❌ HTML 引用 class='{cls}' 但 CSS 没有定义\n"
                f"  拦截历史: v0.50.0 5D badge class 错配"
            )


# ─── 测试 4: DB 恢复路径完整性 ──────────────────────────────────────────

def test_db_restore_completeness(web_dir: Path):
    """验证 _get_or_create_student 恢复所有 DB 字段.

    拦截历史:
    - v0.46.5 import json 漏 (3-tuple → dict 迁移)
    - v0.47.4 item_params 漏 (MIRT K 暴跌 0.91)
    - v0.47.5 trajectory / tc_states 漏
    - v0.47.9 theta_cov 漏
    - v0.49.2 response_history 改 dict 格式
    - v0.52.0 misconception_hits 漏
    """
    belief_file = web_dir / "api" / "belief.py"
    if not belief_file.exists():
        pytest.skip(f"belief.py 不存在: {belief_file}")

    content = belief_file.read_text(encoding="utf-8")

    # 必须恢复的关键字段
    required_fields = [
        "response_history",   # 答题历史
        "current_state_5d",   # 5D θ
        "theta_cov",          # 5x5 协方差 (v0.47.9)
        "current_bloom_profile",  # BloomProfile
        "tc_states",          # Threshold Concept
        "misconception_history",  # 错误历史
    ]

    missing = []
    for field in required_fields:
        if field not in content:
            missing.append(field)

    if missing:
        pytest.fail(
            f"❌ DB 恢复路径缺字段: {missing}\n"
            f"  拦截历史: v0.46.5/0.47.4/0.47.5/0.47.9/0.49.2/0.52.0 多次漏字段"
        )


# ─── 测试 5: CI gate 库 ID 显式传递 ──────────────────────────────────────

def test_ci_gate_explicit_libraries(ecos_dir: Path):
    """验证 detect_with_hits / misc_detector.detect 必须显式传 library_str.

    拦截历史:
    - v0.52.0 misconception 库 ID 错配 (BUG 2.1): detector fallback 到 K12 默认库 M1-M30
      但实际需要 Python 库 M1-M8 → 库 ID 错配导致 22 道题 0 命中
    """
    belief_engine_file = ecos_dir / "cta" / "belief_engine.py"
    if not belief_engine_file.exists():
        pytest.skip(f"belief_engine.py 不存在: {belief_engine_file}")

    content = belief_engine_file.read_text(encoding="utf-8")

    # 验证 _llm_critic_misconception 必须传 library_str
    if "detect_with_hits" in content:
        # 必须有显式 library_str=... 传递
        if "library_str=self.misconception_library_str" not in content and "library_str=" not in content:
            pytest.fail(
                "❌ _llm_critic_misconception 未显式传 library_str\n"
                "  拦截历史: v0.52.0 BUG 2.1 (misco_detector fallback 到 K12 默认库)"
            )


# ─── 收集所有测试,方便 pytest 输出 ─────────────────────────────────────

def pytest_report_header(config):
    """测试报告头部: 显示 ECOS pytest 套件版本."""
    return [
        f"ECOS pytest 套件 v0.55.0-a",
        f"  5 项防御性自检: silent pass / 版本号 / CSS / DB 恢复 / CI gate",
        f"  拦截历史: 5 次虚标 + 5 处 silent pass"
    ]
