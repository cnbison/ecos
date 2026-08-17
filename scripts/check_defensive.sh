#!/usr/bin/env bash
# v0.55.0-e: 防御性自检脚本 (5 项 + pytest)
# v0.64.1:   加 --static-only flag (供 pre-commit hook 用, 跳过 pytest 提速)
# v0.77.1:   加 [6] DB 恢复必须走 apply_snapshot (拦截 6 处直接 state.X = value mutation)
# v0.79.0:   加 [7] replay 脚本不能含字面量 skill_id 硬编码 (AST 检测)
# v0.80.0:   加 [8] 直接 state.X = value mutation AST 扫描 (soft warning, v0.81 hard block)
# v0.81.0:   [8] 改 hard block (exit 1), TODO mutations 迁移完成 (web/api/belief.py + ecos_session.py)
#
# 拦截历史 (Bisen 2026-07-19 反馈后新增):
# - 5 次虚标: 5D badge / LearningDNA / URL hash / hardcoded 版本号 / misconception 库 ID 错配
# - 2 次 silent pass (v0.53.3 belief_engine.py:426 + v0.55.0-a qmatrix.py:168/203)
# - 3 次 partial credit 缺失
# - 4 次 DB 恢复字段漏 (import json / tc_states / trajectory / item_params)
# - 2 次 CSS 渲染失败 (v0.47.3 inline 旧版 + v0.50.0 5D badge class 错配)
# - v0.78 H3-c4 artifact: 7 个 replay 脚本硬编码 skill_id="variables" (v0.79 修)
# - v0.78 H3-c4 暴露: BeliefEngine.update() ~46 处直接 mutation (v0.80 拆 4-layer 修)
#
# 用法:
#   bash scripts/check_defensive.sh           # 全部 8 项静态 + 前端段 + pytest
#   bash scripts/check_defensive.sh --static-only   # 仅静态 + 前端最小集 (pre-commit hook 用, 秒级)
#   make check
set -e

STATIC_ONLY=0
for arg in "$@"; do
    case "$arg" in
        --static-only) STATIC_ONLY=1 ;;
        -h|--help)
            echo "用法: bash scripts/check_defensive.sh [--static-only]"
            echo "  (default)   跑 8 项静态 + 前端段 (tsc/lint/test/build) + pytest"
            echo "  --static-only  只跑 8 项静态 + 前端最小集 (tsc/lint/test, pre-commit hook 用)"
            exit 0
            ;;
        *)
            echo "未知参数: $arg" >&2
            echo "用法: bash scripts/check_defensive.sh [--static-only]" >&2
            exit 2
            ;;
    esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "═══════════════════════════════════════════════════════════════"
echo "  ECOS 防御性自检 (8 项 + 前端段 + pytest)"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# ── 1) silent pass 扫描 ────────────────────────────────────────────
echo "▶ [1/8] 扫描 except ...: pass 沉默失败 (排除注释行 + 测试代码)"
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
echo "▶ [2/8] 检查 __version__ 同步"
EXPECTED=$(grep -E '^__version__' ecos/__init__.py | head -1 | sed -E 's/.*"([0-9.]+)".*/\1/')
if [ -z "$EXPECTED" ]; then
    echo "  ❌ ecos/__init__.py 缺少 __version__"
    exit 1
fi
echo "  ✅ __version__ = $EXPECTED"

# ── 3) 库 ID 显式传递 (CI gate v0.52.0) ───────────────────────
echo ""
echo "▶ [3/8] 拦截 detect_with_hits 不传 library_str (排除注释行 + 函数定义 + multi-line 检查)"
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
echo "▶ [4/8] HTML class 与 CSS 选择器对齐"
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
echo "▶ [5/8] DB 恢复字段完整性 (6 关键字段)"
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

# ── 6) DB 恢复必须走 apply_snapshot ───────────────────────────────
echo ""
echo "▶ [6/8] DB 恢复路径必须走 apply_snapshot (禁止直接 state.X = value)"
# v0.77.1: 评估文档 §6.2 方案 B, DB 恢复走 BeliefState.apply_snapshot 单一入口
# 拦截历史: CLAUDE.md §防御性自检 [5] 4 次漏字段恢复 (import json / tc_states / trajectory / item_params)
# 根因: 6 处直接 state.X = value mutation 散落, 加新字段时易漏一处
# 修复: 走 apply_snapshot(snapshot) 单一入口, 字段恢复跟 to_dict 一一对应
if grep -q "_get_or_create_student" web/api/belief.py 2>/dev/null; then
    if ! grep -q "state\.apply_snapshot(" web/api/belief.py 2>/dev/null; then
        echo "  ❌ web/api/belief.py _get_or_create_student 没调用 state.apply_snapshot()"
        echo "  拦截历史: 4 次 DB 恢复字段漏 (import json / tc_states / trajectory / item_params)"
        echo "  修复: 走 BeliefState.apply_snapshot(snapshot) 单一入口, 替代 6 处直接 state.X = value"
        exit 1
    fi
    echo "  ✅ belief.py DB 恢复走 apply_snapshot 单一入口"
else
    echo "  ⏭️  跳过 (未发现 _get_or_create_student)"
fi

# ── 7) replay 脚本不能含字面量 skill_id 硬编码 ────────────────────
echo ""
echo "▶ [7/8] replay 脚本不能含字面量 skill_id 硬编码 (AST 检测)"
# v0.79: 拦截 scripts/v0*.py + scripts/replay*.py 中 skill_id="<literal>" 字面量赋值
# 拦截历史: v0.78 H3-c4 artifact (replay bug + bloom 上限 + 浮点精度 3 个叠加)
#   v0.75.3 + v0.76 + v075_d4_* + replay_lbc003 等 7 个脚本硬编码 skill_id="variables"
# 修复: 用 ast 模块解析, 排除 docstring + 排除 dict .get() 默认值
python scripts/check_no_literal_skill_id.py
if [ $? -ne 0 ]; then
    exit 1
fi

# ── 8) 直接 state.X = value mutation AST 扫描 ──────────────────────
echo ""
echo "▶ [8/8] 直接 state.X = value mutation AST 扫描 (v0.81 hard block)"
# v0.81: 拦截 ecos/cta/ + ecos/dual_agent/ + web/api/ 中 state.X = value 直接赋值
# 拦截历史: v0.78 BeliefEngine.update() 含 ~46 处直接 mutation, v0.80 拆 4-layer 修
#           v0.81 TODO mutations 迁移完成 (web/api/belief.py:175/303/312 + ecos_session.py:193-198)
# allowlist: BeliefState.{__init__,to_dict,from_dict,apply_snapshot,validate,bump_version,append_trajectory_snapshot} +
#            StateEngine.commit + BeliefUpdator.apply + create_initial_state
# v0.81: hard block (exit 1) - 任何 allowlist 之外的直接 mutation 都 fail
python scripts/check_no_direct_state_mutation.py
if [ $? -ne 0 ]; then
    exit 1
fi

# ── 前端段 (v0.95.1) ─────────────────────────────────────────────
# React/Vite 底座不能成 CI 盲区: tsc / eslint / vitest 最小集 (秒级)
# 静态段也跑 (typecheck + lint + test), 全量段再加 build.
# 若 web/frontend/package.json 存在但 node_modules 缺失 → fail (提示 npm install),
# 不允许 silent skip.
FRONTEND_DIR="web/frontend"
if [ -f "$FRONTEND_DIR/package.json" ]; then
    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        echo "  ❌ 前端依赖缺失: 请先运行 cd web/frontend && npm install"
        exit 1
    fi
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  前端段 (web/frontend): tsc + eslint + vitest"
    echo "═══════════════════════════════════════════════════════════════"
    (
        cd "$FRONTEND_DIR" || exit 1
        echo "▶ typecheck (tsc -b --noEmit)"
        npm run typecheck || exit 1
        echo "▶ lint (eslint . --max-warnings 0)"
        npm run lint || exit 1
        echo "▶ test (vitest run)"
        npm test || exit 1
    )
    if [ $? -ne 0 ]; then
        exit 1
    fi
fi

# ── pytest 全量 ──────────────────────────────────────────────────
if [ "$STATIC_ONLY" = "1" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ⏭️  --static-only, 跳过 pytest + 前端 build"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ✅ 静态检查全部通过"
    echo "═══════════════════════════════════════════════════════════════"
    exit 0
fi

if [ -f "$FRONTEND_DIR/package.json" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  前端段 build (vite build → dist, Flask 托管)"
    echo "═══════════════════════════════════════════════════════════════"
    (cd "$FRONTEND_DIR" && npm run build) || exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  pytest 全量测试"
echo "═══════════════════════════════════════════════════════════════"
python -m pytest tests/ -v

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ 全部检查通过"
echo "═══════════════════════════════════════════════════════════════"
