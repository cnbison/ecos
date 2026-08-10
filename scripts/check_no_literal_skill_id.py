"""v0.79.0 防御性自检 [7]: replay 脚本不能含字面量 skill_id 硬编码.

拦截历史:
- v0.78 发现 v0.75.3 + v0.76 replay 脚本硬编码 skill_id="variables", 导致 H3-c4
  "0 拐点" 结论是 3 个 artifact 叠加 (replay bug + bloom_update_step 上限 + 浮点精度).
- v0.79 扫描发现还有 5 个 v075_* 脚本 + replay_lbc003 含同类硬编码.

规则:
- 禁止: skill_id="<literal>" 直接字面量赋值 (在 Observation() 调用中)
- 允许: skill_id=<variable> 或 skill_id=<function_call> 或 skill_id=<dict>[<key>]
- 允许: skill_id=h.get("skill_id", "default") 中的 default 字符串
- 允许: docstring / 注释内的描述文字

实现:
- 用 Python AST 解析, 找 keyword argument skill_id 是 Str literal 的情况
- 排除 docstring (ast.get_docstring) + 排除注释行 (ast 跳过)
- 排除 dict .get() 第二参数 (默认值, 不是直接赋值)
"""
import ast
import sys
from pathlib import Path


def find_literal_skill_id(py_file: Path) -> list:
    """用 AST 找字面量 skill_id 赋值.

    Returns:
        list of (line_no, code_snippet)
    """
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []
    for node in ast.walk(tree):
        # 找函数调用 (e.g. Observation(...))
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "skill_id":
                continue
            # kw.value 是 ast.Str (Python <3.8) 或 ast.Constant (3.8+)
            val = kw.value
            # Python 3.8+: ast.Constant, 3.7 及以下: ast.Str
            if isinstance(val, ast.Constant) and isinstance(val.value, str):
                # 字面量 skill_id="..."
                line_no = val.lineno
                line = source.split("\n")[line_no - 1].strip()
                violations.append((line_no, line))
            # 处理 skill_id=h.get("k", "default") - default 是字面量但不算
            # 这种情况下 val 是 ast.Call, 不是 ast.Constant, 不会触发
    return violations


def main():
    root = Path(__file__).resolve().parent.parent
    scripts_dir = root / "scripts"

    # 扫描 scripts/v0*.py + scripts/replay*.py
    targets = list(scripts_dir.glob("v0*.py")) + list(scripts_dir.glob("replay*.py"))

    all_violations = []
    for py in sorted(targets):
        for line_no, snippet in find_literal_skill_id(py):
            all_violations.append(f"{py.relative_to(root)}:{line_no}: {snippet}")

    if all_violations:
        print("❌ 发现字面量 skill_id 硬编码:")
        for v in all_violations:
            print(f"  {v}")
        print()
        print("修复: 改成 skill_id=pid_to_topic.get(pid, 'python.variables') 或类似动态查询")
        print("拦截历史: v0.78 H3-c4 artifact (replay bug + bloom 上限 + 浮点精度 3 个叠加)")
        sys.exit(1)

    print(f"✅ 扫描 {len(targets)} 个 replay 脚本, 无字面量 skill_id 硬编码")


if __name__ == "__main__":
    main()
