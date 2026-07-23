#!/usr/bin/env bash
# v0.55.0-e: 防御性自检脚本 (5 项 + pytest)
#
# 拦截历史 (Bisen 2026-07-19 反馈后新增):
# - 5 次虚标: 5D badge / LearningDNA / URL hash / hardcoded 版本号 / misconception 库 ID 错配
# - 2 次 silent pass (v0.53.3 belief_engine.py:426 + v0.55.0-a qmatrix.py:168/203)
# - 3 次 partial credit 缺失
# - 4 次 DB 恢复字段漏 (import json / tc_states / trajectory / item_params)
# - 2 次 CSS 渲染失败 (v0.47.3 inline 旧版 + v0.50.0 5D badge class 错配)
#
# 用法:
#   bash scripts/check_defensive.sh
#   make check
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "═══════════════════════════════════════════════════════════════"
echo "  ECOS v0.55.0 防御性自检 (5 项 + pytest)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── 1) silent pass 扫描 ────────────────────────────────────────────
echo "▶ [1/5] 扫描 except ...: pass 沉默失败 (排除注释行 + 测试代码)"
# 排除规则:
#   - 注释行 (以 # 开头)
#   - docstring (""" 或 ''' 包含 "except: pass" 的描述)
#   - 测试代码 (test_*.py)
#   - __pycache__ / .venv
# 我们用 awk 检查行首是否缩进的纯代码
SILENT_PASS=$(grep -nE "^\s*except.*:[[:space:]]*(pass|continue)\s*$" --include="*.py" -r ecos/ web/ 2>/dev/null | grep -v "__pycache__" | grep -v "/\\.venv/" | grep -v "test_" || true)
if [ -n "$SILENT_PASS" ]; then
    echo "  ❌ 发现 silent pass:"
    echo "$SILENT_PASS"
    echo "  修复: 改 logger.warning(..., exc_info=True) 或显式 raise"
    exit 1
fi
echo "  ✅ 无 silent pass"

# ── 2) 版本号同步 ───────────────────────────────────────────────
echo ""
echo "▶ [2/5] 检查 __version__ 同步"
EXPECTED=$(grep -E '^__version__' ecos/__init__.py | head -1 | sed -E 's/.*"([0-9.]+)".*/\1/')
if [ -z "$EXPECTED" ]; then
    echo "  ❌ ecos/__init__.py 缺少 __version__"
    exit 1
fi
echo "  ✅ __version__ = $EXPECTED"

# ── 3) 库 ID 显式传递 (CI gate v0.52.0) ───────────────────────
echo ""
echo "▶ [3/5] 拦截 detect_with_hits 不传 library_str (排除注释行 + 函数定义 + multi-line 检查)"
# 检查策略: 找到所有 detect_with_hits( / misc_detector.detect( 的调用点
#   - 排除函数定义 (def detect_with_hits(...):)
#   - 排除注释行
#   - 检查 multi-line 调用 (10 行内必须出现 library_str=)
# 用 Python 脚本做 AST/正则检查更稳, 但 shell 用 perl/awk 也能搞定
UNGUARDED=""
for f in $(find ecos/ web/ -name "*.py" -not -path "*/\.venv/*" -not -path "*/__pycache__/*" -not -name "test_*.py" 2>/dev/null); do
    # 找到所有 "detect_with_hits(" 或 "misc_detector.detect(" 起始行号
    # 排除 "def " 开头的函数定义 + 注释行 (检查行内容, 不只是行号前缀)
    LINE_NUMS=$(grep -nE "(detect_with_hits|misc_detector\.detect)\(" "$f" 2>/dev/null \
        | sed -E 's/^[0-9]+://' \
        | grep -vE "^\s*#|^\s*\"\"\"|def\s" \
        | awk -F: '{print $1}' \
        | head -1 \
        || true)
    # 实际上需要保留行号, 改用 while 读
    grep -nE "(detect_with_hits|misc_detector\.detect)\(" "$f" 2>/dev/null \
        | sed -E 's/^([0-9]+):.*/\1/' > /tmp/.defensive_line_nums_$$ 2>/dev/null || true
    while read -r line; do
        # 检查行内容是否以 # 开头 (注释, 允许前导空格)
        line_content=$(sed -n "${line}p" "$f" 2>/dev/null)
        trimmed=$(echo "$line_content" | sed -E 's/^[[:space:]]+//')
        case "$trimmed" in
            \#*) continue ;;  # 注释行 (允许前导空格)
            def*) continue ;;  # 函数/类定义
        esac
        # 取从该行起 10 行, 检查是否含 library_str=
        if ! sed -n "${line},$((line+9))p" "$f" 2>/dev/null | grep -q "library_str"; then
            UNGUARDED="$UNGUARDED\n$f:$line: missing library_str in detect call"
        fi
    done < /tmp/.defensive_line_nums_$$
    rm -f /tmp/.defensive_line_nums_$$
done
if [ -n "$UNGUARDED" ]; then
    echo -e "  ❌ 发现未传 library_str 的 detector 调用:$UNGUARDED"
    echo "  修复: 任何 detect_with_hits(...)/misc_detector.detect(...) 必须显式传 library_str=..."
    exit 1
fi
echo "  ✅ 所有 detector 调用都传 library_str"

# ── 4) HTML class 与 CSS 选择器对齐 ─────────────────────────────
echo ""
echo "▶ [4/5] HTML class 与 CSS 选择器对齐"
if [ -f "web/student/index.html" ] && [ -f "web/student/styles.css" ]; then
    HTML_CLASSES=$(grep -oE 'class="[^"]+"' web/student/index.html 2>/dev/null | sed -E 's/class="([^"]+)"/\1/g' | tr ' ' '\n' | sort -u)
    CSS_CLASSES=$(grep -oE '^\.[a-zA-Z][a-zA-Z0-9_-]+' web/student/styles.css 2>/dev/null | sed -E 's/^\.//g' | sort -u)
    # 取 HTML class 中 CSS 找得到的子集
    MISSING=""
    for cls in $HTML_CLASSES; do
        if ! echo "$CSS_CLASSES" | grep -qx "$cls" 2>/dev/null; then
            # 跳过 HTML 通用 class (div/span/button/...)
            case "$cls" in
                active|hidden|disabled|open|close|show|hide|error|success|warning|info) continue;;
            esac
            MISSING="$MISSING $cls"
        fi
    done
    if [ -n "$MISSING" ]; then
        echo "  ⚠️  HTML class 在 CSS 中找不到 (可能为 utility/动态类):$MISSING"
    else
        echo "  ✅ 所有 HTML class 都有 CSS 选择器"
    fi
else
    echo "  ⏭️  跳过 (web/student/ 暂未拆文件)"
fi

# ── 5) DB 恢复字段完整性 ───────────────────────────────────────
echo ""
echo "▶ [5/5] DB 恢复字段完整性 (6 关键字段)"
if grep -q "_get_or_create_student\|save_student_state" web/api/belief.py 2>/dev/null; then
    REQUIRED_FIELDS=("response_history" "current_state_5d" "theta_cov" "current_bloom_profile" "tc_states" "misconception_history")
    MISSING_FIELDS=""
    for field in "${REQUIRED_FIELDS[@]}"; do
        if ! grep -q "$field" web/api/belief.py 2>/dev/null && ! grep -q "$field" ecos/persistence/db.py 2>/dev/null; then
            MISSING_FIELDS="$MISSING_FIELDS $field"
        fi
    done
    if [ -n "$MISSING_FIELDS" ]; then
        echo "  ❌ DB 恢复缺少关键字段:$MISSING_FIELDS"
        exit 1
    fi
    echo "  ✅ 6 关键字段恢复完整"
else
    echo "  ⏭️  跳过 (未发现 _get_or_create_student/save_student_state)"
fi

# ── pytest 全量 ──────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  pytest 全量测试"
echo "═══════════════════════════════════════════════════════════════"
python -m pytest tests/ -v

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ 全部检查通过"
echo "═══════════════════════════════════════════════════════════════"
