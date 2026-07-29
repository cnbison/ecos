#!/usr/bin/env bash
# ECOS v0.64.1: 一键安装 git hooks
#
# 用法: bash scripts/install-hooks.sh
#
# 作用: 把 githooks/ 目录设为本地仓库的 hooks 源.
#       之后所有 git commit / git push 都会自动跑防御性自检 (pre-commit)
#       和全量 pytest (pre-push).
#
# 为什么需要这个:
#   - .git/hooks/ 里的 hook 文件不入仓, 新人 clone 拿不到
#   - 改用 core.hooksPath = githooks/, hook 文件本身在仓库里 tracked
#   - 这个脚本帮新机器一键启用 (不需要手动 git config)
#
# 验证 (跑完应该看到 hooks 路径已设):
#   git config --get core.hooksPath
#   # 输出: githooks

set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

HOOKS_SRC="githooks"

if [ ! -d "$HOOKS_SRC" ]; then
    echo "❌ $HOOKS_SRC/ 目录不存在, 请确认仓库完整" >&2
    exit 1
fi

# 确保 hooks 文件可执行
chmod +x "$HOOKS_SRC"/* 2>/dev/null || true

# 设为本地仓库的 hooks 源 (不污染全局 git config)
git config core.hooksPath "$HOOKS_SRC"

echo "═══════════════════════════════════════════════════════════════"
echo "  ✅ ECOS git hooks 安装完成"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "  hooks 源: $HOOKS_SRC/ (仓库内 tracked)"
echo "  core.hooksPath 已设: $(git config --get core.hooksPath)"
echo ""
echo "  接下来:"
echo "    - git commit  → 自动跑 5 项静态检查 (~0.5s)"
echo "    - git push    → 自动跑 5 项静态 + pytest 全量 (~10-30s)"
echo ""
echo "  紧急绕过 (不推荐):"
echo "    git commit --no-verify"
echo "    git push --no-verify"
echo ""
