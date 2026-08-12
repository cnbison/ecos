"""v0.80.0 防御性自检 [8]: 直接 state.X = value mutation 扫描.

拦截历史:
- v0.78 H3-c4 暴露 BeliefEngine.update() 含 ~46 处 state.X = value 直接 mutation, 散落 3 方法
- v0.80.0-b/c 拆分 4-layer (InferenceEngine + BeliefUpdator + ObservationEngine + FeatureExtractor)
- v0.80.0 final: 加 AST 扫描, 堵住未来回退到 inline mutation 的可能
- v0.81.0-d: TODO mutations 迁移完成 (web/api/belief.py + ecos_session.py), hard block 启用 (exit 1)

规则:
- 禁止: state.X = value / state.X.Y = value / state.X[i] = value 直接赋值 (在 ecos/cta/ + ecos/dual_agent/ + web/api/)
- 允许: BeliefState.{__init__, to_dict, from_dict, apply_snapshot, validate, bump_version, snapshot, append_trajectory_snapshot}
- 允许: StateEngine.commit + 内部 helpers (_copy_state_fields, _apply_delta_fields)
- 允许: BeliefUpdator.apply (sole mutation site, by design)
- 允许: test_*.py (test fixtures exempt)
- 允许: 行 allowlist (orchestrator.py:842, factory pattern permanent exception)

实现:
- v0.81: hard block (exit 1) - 任何 allowlist 之外的直接 mutation 都 fail
"""
import ast
import sys
from pathlib import Path
from typing import List, Tuple


# 行 allowlist: 这些位置永久例外
LINE_ALLOWLIST = {
    # orchestrator.py:842: state[sid].student_id = sid (allowed exception per plan, factory pattern)
    ("ecos/dual_agent/orchestrator.py", 842): "student_id",
}

# 函数 allowlist: 这些方法内允许直接 state mutation
FUNC_ALLOWLIST = {
    "__init__",  # BeliefState.__init__ / DimensionState.__init__ 等
    "to_dict",  # 序列化
    "from_dict",  # 反序列化
    "apply_snapshot",  # BeliefState.apply_snapshot (委托 StateEngine)
    "validate",  # BeliefState.validate
    "bump_version",  # BeliefState.bump_version (StateEngine.commit 调)
    "snapshot",  # BeliefState.snapshot
    "append_trajectory_snapshot",  # v0.81.0-d: BeliefState.append_trajectory_snapshot (DB restore path)
    "add_evidence",  # v0.83.0-b: BeliefState.add_evidence (Belief-Evidence 关联, Evidence Engine 注入)
    "append_goal",  # v0.86.0-a: BeliefState.append_goal (Goal Ontology 关联, 取代直接 state.current_goals.append)
    "remove_goal",  # v0.86.0-a: BeliefState.remove_goal (Goal Ontology 移除, discard 模式)
    "add_motivation_observation",  # v0.87.0-a: BeliefState.add_motivation_observation (Motivation Profile 关联, 取代直接 state.motivation.add_observation)
    "set_domain_extension",  # v0.88.0-b: BeliefState.set_domain_extension (Domain Extension 关联, 取代直接 state.domain_extension[k] = v)
    "append_human_feedback",  # v0.91.0-a: CognitiveTwinAgent.append_human_feedback (Twin → Human Twin 关联, 取代直接 cognitive_twin.human_feedback.entries.append)
    "_apply_delta_fields",  # BeliefState._apply_delta_fields (StateEngine 调)
    "_copy_state_fields",  # StateEngine._copy_state_fields
    "commit",  # StateEngine.commit
    "apply",  # BeliefUpdator.apply (sole mutation site, by design)
    "update_dominant",  # BloomProfileState.update_dominant
    "__post_init__",  # dataclass post-init
    "create_initial_state",  # BeliefEngine.create_initial_state (factory, creates NEW state)
}


def find_direct_state_mutation(py_file: Path) -> List[Tuple[int, str, str]]:
    """用 AST 找 state.X = value / state.X.Y = value 直接赋值.

    Returns:
        list of (line_no, code_snippet, func_name)
    """
    try:
        source = py_file.read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return []

    violations = []

    # Track current function context for allowlist check
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_name = node.name
            # 检查函数体内的赋值
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Assign):
                    continue
                for target in sub.targets:
                    if _is_state_mutation_target(target):
                        line_no = sub.lineno
                        line = source.split("\n")[line_no - 1].strip()
                        violations.append((line_no, line, func_name))

    return violations


def _is_state_mutation_target(node: ast.expr) -> bool:
    """判断 target 是否是 state.X = ... / state.X.Y = ... / state.X[i] = ... 形式.

    - state.X = value (ast.Attribute)
    - state.X.Y = value (ast.Attribute on ast.Attribute)
    - state.X[i] = value (ast.Subscript on ast.Attribute)
    """
    if isinstance(node, ast.Attribute):
        # state.X = ... (chain root must be `state` Name)
        return _root_is_state(node)
    if isinstance(node, ast.Subscript):
        # state.X[i] = ...
        return _root_is_state(node.value)
    return False


def _root_is_state(node: ast.expr) -> bool:
    """Walk down attribute chain, check if root is `state` identifier."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return isinstance(node, ast.Name) and node.id == "state"


def main():
    root = Path(__file__).resolve().parent.parent

    # 扫描 ecos/cta/ + ecos/dual_agent/ + web/api/
    targets = []
    for pattern in ["ecos/cta/**/*.py", "ecos/dual_agent/**/*.py", "web/api/**/*.py"]:
        targets.extend(root.glob(pattern))
    # 排除 __pycache__ + test_*.py
    targets = [
        p for p in targets
        if "__pycache__" not in p.parts and not p.name.startswith("test_")
    ]

    all_violations = []
    for py in sorted(targets):
        for line_no, snippet, func_name in find_direct_state_mutation(py):
            # 跳过 allowlist 函数
            if func_name in FUNC_ALLOWLIST:
                continue
            # 跳过 allowlist 行
            rel_path = str(py.relative_to(root))
            if (rel_path, line_no) in LINE_ALLOWLIST:
                continue
            all_violations.append((rel_path, line_no, snippet, func_name))

    if all_violations:
        print("❌ 发现直接 state.X = value mutation (v0.81 hard block):")
        for rel_path, line_no, snippet, func_name in all_violations:
            print(f"  {rel_path}:{line_no} (in {func_name}()): {snippet}")
        print()
        print("修复: 改用 StateEngine.commit(state, delta, source=...) 或 BeliefUpdator.apply()")
        print("拦截历史: v0.78 BeliefEngine.update() 含 ~46 处直接 mutation, v0.80 拆 4-layer 收口")
        print("allowlist: BeliefState.{__init__,to_dict,from_dict,apply_snapshot,validate,bump_version,append_trajectory_snapshot,add_evidence} + StateEngine.commit + BeliefUpdator.apply")
        # v0.81: hard block (exit 1)
        sys.exit(1)

    print(f"✅ 扫描 {len(targets)} 个文件, 无直接 state.X = value mutation (allowlist 之外)")


if __name__ == "__main__":
    main()
