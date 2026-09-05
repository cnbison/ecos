"""黄金回归 runner（v0.97.0 恢复期 backlog P1: A3 式黄金回归基建）.

对应:
  - README §下一步 P1「A3 式黄金回归基建」
  - docs/wiring-audit-2026-09-05.md §六（接线动作的前置护栏）

覆盖范围（第一版, deterministic 段）:
  做题 → BeliefEngine.update (BKT + MIRT + Bloom + TC, llm_client=None) → LCAEngine.select_intervention
  LLM judge / interpretation / LLM critic 层后置（改 prompt 已有 test_judge_* 系列; mock LLM
  的黄金序列会固化 prompt 偶然形态, 反而脆弱——CogMirror P1 方案讨论结论）。

回归判定:
  - 意图断言（INTENT_CHECKS）: 人工撰写的行为窗口, 编码"这个序列应该表现出什么"
  - 基线断言: tests/golden/baseline.json 快照 + 容差比较（atol=1e-8, 吸收 BLAS 微漂移）
  - 任何基线偏差 → FAIL（首版从严: 工程纪律 > 平滑）
  - 基线更新流程: ECOS_GOLDEN_REGEN=1 pytest tests/test_golden_regression.py
    → 重新生成 baseline.json → **必须带文档化 diff（commit message 说明改了什么/为什么）,
    禁止静默覆盖**（防"基线跟着代码跑"让回归检测形同虚设）

自检（证伪测试, CogMirror P1 验收标准）:
  - test_comparator_detects_seeded_drift: 扰动 1e-3 必须被抓到——抓不到 = 本基建失效
  - test_comparator_tolerance_absorbs_blas_drift: 1e-12 扰动不误报
  - test_sequence_run_is_deterministic: 同序列跑两次快照全等（抓 RNG/时间泄漏）
"""

from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from ecos.cta.belief_engine import BeliefEngine, Observation
from ecos.cta.belief_state import BloomLevel
from ecos.lca.orchestrator import LCAEngine
from ecos.lca.cta_input import CTAInput

from tests.golden.sequences import GOLDEN_BASE_DATETIME, GOLDEN_SEQUENCES

GOLDEN_DIR = Path(__file__).parent / "golden"
BASELINE_PATH = GOLDEN_DIR / "baseline.json"

# 容差: 同机同代码应精确复现; 跨 BLAS/scipy 版本允许 1e-9 级微漂移, 1e-8 覆盖之
ATOL = 1e-8
# 快照数值保留 9 位小数, 避免 JSON float 噪声
ROUND_DIGITS = 9


# ─── 序列执行 → 快照 ────────────────────────────────────────────────


def _r(value: float) -> float:
    return round(float(value), ROUND_DIGITS)


def _dim_snapshot(dim) -> list:
    """单维度快照: [theta, se, mastery_prob, confidence]（mastered 二值在数值上冗余）."""
    return [_r(dim.theta), _r(dim.se), _r(dim.mastery_prob), _r(dim.confidence)]


def run_sequence(seq: dict) -> dict:
    """执行一条黄金序列, 返回数值快照（不依赖 baseline）."""
    engine = BeliefEngine(llm_client=None)
    student_id = f"golden::{seq['name']}"
    state = engine.create_initial_state(student_id)
    base = datetime(*GOLDEN_BASE_DATETIME)

    steps_snapshot = []
    for i, step in enumerate(seq["steps"]):
        obs = Observation(
            skill_id=step["skill_id"],
            problem_id=step["problem_id"],
            correct=step["score"] >= 0.6,
            score=step["score"],
            bloom_level=BloomLevel[step["bloom"]],
            timestamp=base + timedelta(minutes=5 * i),
        )
        engine.update(state, obs)
        steps_snapshot.append({
            "K": _dim_snapshot(state.K), "P": _dim_snapshot(state.P),
            "S": _dim_snapshot(state.S), "C": _dim_snapshot(state.C),
            "X": _dim_snapshot(state.X),
            "overall": _r(state.overall_confidence),
            "dominant": state.bloom_profile.dominant_layer.name,
        })

    # LCA 干预选择（fresh engine, 无 LLM）
    lca = LCAEngine(llm_client=None)
    result = lca.select_intervention(CTAInput(
        student_id=student_id,
        belief_state=state,
        timestamp=base + timedelta(minutes=5 * len(seq["steps"])),
    ))
    intervention = result.intervention

    bkt = {sid: _r(engine.get_bkt_mastery(sid))
           for sid in sorted({s["skill_id"] for s in seq["steps"]})}
    tc = {sid: [st.status, _r(st.progress)]
          for sid, st in sorted(state.C.tc_states.items())}
    bloom = {level.name: _r(getattr(state.bloom_profile, level.name.lower()))
             for level in BloomLevel}

    return {
        "steps": steps_snapshot,
        "final": {
            "theta_mean": [_r(v) for v in state.theta_mean],
            "theta_cov_diag": [_r(state.theta_cov[i][i]) for i in range(5)],
            "bloom": bloom,
            "dominant": state.bloom_profile.dominant_layer.name,
            "bkt": bkt,
            "tc": tc,
            "overall": _r(state.overall_confidence),
        },
        "lca": {
            "itype": intervention.intervention_type.name,
            "bloom_target": intervention.bloom_target.name,
            "target_skills": sorted(intervention.target_skills),
            "difficulty": _r(intervention.difficulty),
            "quantity": intervention.quantity,
            "feedback_density": _r(intervention.feedback_density),
            "scaffolding_level": _r(intervention.scaffolding_level),
            "clt_level": intervention.clt_level.name,
            "ca_stage": intervention.ca_stage.name,
            "bjork_triggers": sorted(intervention.bjork_triggers),
            "expected_gain": _r(intervention.expected_gain),
            "expected_risk": _r(intervention.expected_risk),
        },
    }


def run_all() -> dict:
    return {seq["name"]: run_sequence(seq) for seq in GOLDEN_SEQUENCES}


# ─── 容差比较器 ─────────────────────────────────────────────────────


def compare_snapshots(expected: object, actual: object, path: str = "$",
                      atol: float = ATOL) -> list[str]:
    """递归比较两份快照, 返回偏差路径列表（空 = 一致）."""
    mismatches: list[str] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            if key not in expected:
                mismatches.append(f"{path}.{key}: 基线缺失 (新字段)")
            elif key not in actual:
                mismatches.append(f"{path}.{key}: 当前缺失 (字段被删)")
            else:
                mismatches.extend(
                    compare_snapshots(expected[key], actual[key], f"{path}.{key}", atol))
    elif isinstance(expected, list) and isinstance(actual, list):
        if len(expected) != len(actual):
            mismatches.append(f"{path}: 长度 {len(expected)} != {len(actual)}")
        for i, (e, a) in enumerate(zip(expected, actual)):
            mismatches.extend(compare_snapshots(e, a, f"{path}[{i}]", atol))
    elif isinstance(expected, (int, float)) and isinstance(actual, (int, float)) \
            and not isinstance(expected, bool) and not isinstance(actual, bool):
        if abs(float(expected) - float(actual)) > atol:
            mismatches.append(f"{path}: {expected} != {actual}")
    else:
        if expected != actual:
            mismatches.append(f"{path}: {expected!r} != {actual!r}")
    return mismatches


# ─── 意图断言（人工撰写的行为窗口, 编码"应该表现出什么"）────────────

# K 维度 mastery_prob 索引（_dim_snapshot: [theta, se, mastery_prob, confidence]）
_MASTERY = 2


def _intent_all_correct(snap: dict) -> None:
    final_k = snap["final"]["theta_mean"][0]  # theta_mean[0] = K 能力
    k_prob = snap["steps"][-1]["K"][_MASTERY]
    assert k_prob > 0.6, f"全对学习者 K.mastery_prob 应 > 0.6, 实际 {k_prob}"
    assert final_k > 0, f"全对学习者 K theta 应为正, 实际 {final_k}"
    for sid, mastery in snap["final"]["bkt"].items():
        assert mastery > 0.6, f"全对学习者 BKT[{sid}] 应 > 0.6, 实际 {mastery}"
    bloom = snap["final"]["bloom"]
    # Bloom 保守小步更新: 访问过的层抬升 (>0.6), 未访问层保持默认 0.5
    assert bloom["ANALYZE"] > 0.6, f"ANALYZE 被练习过应 > 0.6, 实际 {bloom['ANALYZE']}"
    assert bloom["CREATE"] == 0.5, f"CREATE 未被练习应保持默认 0.5, 实际 {bloom['CREATE']}"
    order = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"]
    assert order.index(snap["final"]["dominant"]) >= 1, \
        f"全对学习者 dominant bloom 应 >= UNDERSTAND, 实际 {snap['final']['dominant']}"


def _intent_all_wrong(snap: dict) -> None:
    final_k = snap["final"]["theta_mean"][0]
    k_prob = snap["steps"][-1]["K"][_MASTERY]
    assert k_prob < 0.4, f"全错学习者 K.mastery_prob 应 < 0.4, 实际 {k_prob}"
    assert final_k < 0, f"全错学习者 K theta 应为负, 实际 {final_k}"
    for sid, mastery in snap["final"]["bkt"].items():
        assert mastery < 0.5, f"全错学习者 BKT[{sid}] 应 < 0.5, 实际 {mastery}"
    # 全错应把练习过的 bloom 层压到默认 (0.5) 之下, TC 停在 pre_liminal
    assert snap["final"]["bloom"]["UNDERSTAND"] < 0.5, \
        f"全错应压低 UNDERSTAND 概率, 实际 {snap['final']['bloom']['UNDERSTAND']}"
    for sid, (status, progress) in snap["final"]["tc"].items():
        assert status == "pre_liminal" and progress == 0.0, \
            f"全错 TC[{sid}] 应停在 pre_liminal/0.0, 实际 {status}/{progress}"


def _intent_partial_credit(snap: dict) -> None:
    k_prob = snap["steps"][-1]["K"][_MASTERY]
    assert 0.2 < k_prob < 0.9, \
        f"混合学习者 K.mastery_prob 应落在 (0.2, 0.9), 实际 {k_prob}"
    # partial credit 混合下两 skill 应分化（scope 均值高, dicts 均值低）
    scope = snap["final"]["bkt"].get("python.scope", 0.5)
    dicts = snap["final"]["bkt"].get("python.dicts", 0.5)
    assert scope > dicts, f"scope ({scope}) 应高于 dicts ({dicts})"


def _intent_liminal_crossing(snap: dict) -> None:
    tc = snap["final"]["tc"].get("python.loops")
    assert tc is not None, "liminal 序列应产生 python.loops 的 TC 状态"
    status, progress = tc
    assert status == "post_liminal", \
        f"'先错后对'的 liminal 跨越设计应走到 post_liminal, 实际 {status} (progress={progress})"
    assert progress > 0.9, f"跨越进度应 > 0.9, 实际 {progress}"


def _intent_dense(snap: dict) -> None:
    mastery = snap["final"]["bkt"]["python.functions"]
    assert mastery > 0.85, f"20 步全对应使 BKT 接近收敛上限, 实际 {mastery}"
    # Bloom 全谱覆盖 (含 L6 CREATE): 累积层级均应抬升, dominant 高于低层
    assert snap["final"]["bloom"]["CREATE"] > 0.5, \
        f"CREATE 被练习过应 > 0.5, 实际 {snap['final']['bloom']['CREATE']}"
    order = ["REMEMBER", "UNDERSTAND", "APPLY", "ANALYZE", "EVALUATE", "CREATE"]
    assert order.index(snap["final"]["dominant"]) >= 3, \
        f"密集全谱练习 dominant 应 >= ANALYZE, 实际 {snap['final']['dominant']}"


INTENT_CHECKS = {
    "all_correct_learner": _intent_all_correct,
    "all_wrong_learner": _intent_all_wrong,
    "partial_credit_mixed": _intent_partial_credit,
    "liminal_crossing_single_skill": _intent_liminal_crossing,
    "dense_single_skill": _intent_dense,
}


# ─── 基线 IO ────────────────────────────────────────────────────────


def _load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        pytest.fail(
            f"基线缺失: {BASELINE_PATH} 不存在。首次生成:\n"
            f"  ECOS_GOLDEN_REGEN=1 python -m pytest {Path(__file__).name}\n"
            f"生成后 commit 基线文件。后续基线更新必须带文档化 diff, 禁止静默覆盖。",
            pytrace=False,
        )
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _save_baseline(snapshots: dict) -> None:
    BASELINE_PATH.write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
        encoding="utf-8",
    )


# ─── 测试入口 ───────────────────────────────────────────────────────

pytestmark = pytest.mark.regression


def test_golden_regression():
    """黄金回归主测试: 意图断言 + 基线断言。

    FAIL 语义: 当前引擎行为偏离基线（容差 1e-8）或违反行为意图。
    这是后续所有引擎改动（含接线审计 A 类接线动作）的行为护栏。
    """
    regen = os.environ.get("ECOS_GOLDEN_REGEN") == "1"
    snapshots = run_all()

    # 1) 意图断言（与基线无关, 编码行为语义）
    for seq in GOLDEN_SEQUENCES:
        check = INTENT_CHECKS[seq["name"]]
        check(snapshots[seq["name"]])

    # 2) 基线断言
    if regen:
        _save_baseline(snapshots)
        # regen 模式下仍跑意图断言（上面已跑）, 然后提示提交
        pytest.skip(
            "基线已重新生成——请 git diff tests/golden/baseline.json 核对变更, "
            "并在 commit message 中文档化 diff 后提交; 禁止未经核对的基线覆盖。",
        )

    baseline = _load_baseline()
    all_mismatches = []
    for seq in GOLDEN_SEQUENCES:
        name = seq["name"]
        if name not in baseline:
            all_mismatches.append(f"{name}: 基线未收录 (新序列)")
            continue
        all_mismatches.extend(
            f"{name} {m}" for m in compare_snapshots(baseline[name], snapshots[name]))
    for name in sorted(set(baseline) - {s["name"] for s in GOLDEN_SEQUENCES}):
        all_mismatches.append(f"{name}: 基线有但序列已删除")

    assert not all_mismatches, (
        "黄金回归检测到行为漂移 (回归判定: FAIL):\n  "
        + "\n  ".join(all_mismatches)
        + "\n若为有意变更: 先在分支上确认行为变化符合预期, 再 "
          "ECOS_GOLDEN_REGEN=1 重生成基线并文档化 diff。"
    )


# ─── 证伪自检（验收标准: 审计基建本身必须能被抓到失效）──────────────


def test_comparator_detects_seeded_drift():
    """扰动 1e-3 必须被抓到——抓不到 = 回归检测形同虚设（DISPROVEN 条件）."""
    expected = {"final": {"bkt": {"python.loops": 0.81}}, "lca": {"itype": "PRACTICE"}}
    actual = copy.deepcopy(expected)
    actual["final"]["bkt"]["python.loops"] += 1e-3
    actual["lca"]["itype"] = "EXPLANATORY"
    mismatches = compare_snapshots(expected, actual)
    assert any("python.loops" in m for m in mismatches), "数值扰动未被检测"
    assert any("itype" in m for m in mismatches), "枚举扰动未被检测"


def test_comparator_tolerance_absorbs_blas_drift():
    """1e-12 扰动（BLAS 微漂移量级）不应误报."""
    expected = {"final": {"bkt": {"python.loops": 0.81}, "overall": 0.5}}
    actual = copy.deepcopy(expected)
    actual["final"]["bkt"]["python.loops"] += 1e-12
    actual["final"]["overall"] -= 1e-12
    assert compare_snapshots(expected, actual) == []


def test_sequence_run_is_deterministic():
    """同序列跑两次快照必须全等——抓 RNG/时间泄漏（如未固定 timestamp/seed）."""
    seq = GOLDEN_SEQUENCES[0]
    snap_a, snap_b = run_sequence(seq), run_sequence(seq)
    mismatches = compare_snapshots(snap_a, snap_b)
    assert not mismatches, f"同序列两次执行不一致 (非确定性泄漏):\n  {mismatches}"
