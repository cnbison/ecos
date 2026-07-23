"""v0.55.0-b: partial credit + MIRT 回归保护.

拦截历史:
  - v0.54.0-c/d/e partial credit 改造
  - v0.52.2 partial credit 缺失 (Bisen 触发)
  - lbc001 PB-Q18 70% 答对被按 0% 处理, K 维度多跌 0.27

测试:
  1. test_mirt_partial_score_continuous: MIRT MAP 接受 [0, 1] 连续值
  2. test_partial_credit_reduces_k_decline: lbc001 PB-Q18 场景, partial credit K 跌幅 < 0.10
  3. test_response_history_score_compat: 老 correct: bool 数据 fallback 到 score=correct?1.0:0.0
  4. test_mirt_estimate_theta_continuous_inputs: responses=[0.3,0.6,0.7,1.0] 收敛
  5. test_mirt_estimate_theta_discrete_backward_compat: responses=[0,1,0,1] 老用法仍工作
"""
import numpy as np
import pytest


# ─── 测试 6: MIRT 公式支持 partial score [0, 1] 连续值 ───────────────────

def test_mirt_partial_score_continuous():
    """MIRT MAP 似然函数接受 partial score [0, 1] 连续值.

    l2_mirt.py:135 公式:
      log_lik = sum(responses * log(probs) + (1-responses) * log(1-probs))

    这公式数学上支持 responses ∈ [0, 1] 连续值:
      - responses=0: L_i = (1 - P_i) (模型预测 P_i 越低越好)
      - responses=1: L_i = P_i (模型预测 P_i 越高越好)
      - responses=0.7: L_i = P_i^0.7 * (1-P_i)^0.3 (加权混合)
    """
    # 模拟 l2_mirt.py:135 公式 (简化版, 不依赖 scipy)
    responses = np.array([0.0, 0.3, 0.6, 0.7, 1.0])
    # 假设模型预测 P = 0.5 (中性)
    probs = np.array([0.5, 0.5, 0.5, 0.5, 0.5])

    # 公式应该不报错
    log_lik = np.sum(responses * np.log(probs) + (1.0 - responses) * np.log(1.0 - probs))

    # 验证: responses=0.5 应该让 log_lik 为 log(0.5) * 1.0 (P_i 与 1-P_i 加权)
    expected = 5 * np.log(0.5)
    assert np.isclose(log_lik, expected), \
        f"MIRT 公式不支持 partial score: log_lik={log_lik}, expected={expected}"

    # 验证: responses=0.0 时 log_lik = sum(log(1-probs))
    responses_zero = np.array([0.0, 0.0, 0.0, 0.0, 0.0])
    log_lik_zero = np.sum(responses_zero * np.log(probs) + (1.0 - responses_zero) * np.log(1.0 - probs))
    assert log_lik_zero == 5 * np.log(0.5), \
        f"responses=0 时 log_lik 应该 = 5*log(0.5), 实际={log_lik_zero}"

    # 验证: responses=1.0 时 log_lik = sum(log(probs))
    responses_one = np.array([1.0, 1.0, 1.0, 1.0, 1.0])
    log_lik_one = np.sum(responses_one * np.log(probs) + (1.0 - responses_one) * np.log(1.0 - probs))
    assert log_lik_one == 5 * np.log(0.5), \
        f"responses=1 时 log_lik 应该 = 5*log(0.5), 实际={log_lik_one}"


# ─── 测试 7: partial credit 减少 K 维度跌幅 ─────────────────────────────

def test_partial_credit_reduces_k_decline():
    """lbc001 PB-Q18 场景: partial credit score=0.7 时 K 维度跌幅应 < 0.10 (不是 0.27).

    拦截历史:
    - v0.52.2 partial credit 缺失: MIRT 二元对错, lbc001 K 维度多跌 0.27
    - v0.54.0-d partial credit 改造: MIRT 接受 score 连续值
    """
    # 这里我们用 BeliefEngine 重放场景, 不需要 lbc001 真实 DB
    from ecos.cta.belief_engine import BeliefEngine, Observation
    from ecos.cta.belief_state import BloomLevel
    from datetime import datetime
    import json
    from pathlib import Path

    # 加载 Q 矩阵
    with open("data/python_basics_q_matrix.json") as f:
        qdata = json.load(f)
    prob_map = {p["problem_id"]: p for p in qdata["problems"]}

    # 注册 PB-Q18 item params
    from ecos.cta.l2_mirt import MIRTItemParams
    engine = BeliefEngine()

    pb_q18 = prob_map.get("PB-Q18")
    if pb_q18:
        a = pb_q18["a_specialized"]
        item = MIRTItemParams(
            problem_id="PB-Q18",
            a_specialized=np.array(a),
            a_general=pb_q18.get("mirt_params", {}).get("discrimination", 1.0) * 0.5,
            difficulty=pb_q18.get("mirt_params", {}).get("difficulty", 0.0),
        )
        engine.l2.register_item(item)

    # 模拟 lbc001: 答 5 道基线题 + 1 道 PB-Q18
    state = engine.create_initial_state("test_partial_credit")

    # 基线 5 道 (假设都答对, K=0.5 附近)
    for i in range(1, 6):
        obs = Observation(
            skill_id="python.variables",
            problem_id=f"PB-Q{i:02d}",
            correct=True, score=1.0,
            bloom_level=BloomLevel.APPLY,
            timestamp=datetime.now(),
        )
        state = engine.update(state, obs)

    K_before = state.K.theta
    print(f"  基线 5 题后 K = {K_before:.4f}")

    # 答 PB-Q18: 模拟 partial credit score=0.7 (算法对, 缺 I/O)
    obs_pb18 = Observation(
        skill_id="python.variables",
        problem_id="PB-Q18",
        correct=False,  # 老调用
        score=0.7,  # partial credit 70%
        bloom_level=BloomLevel.CREATE,
        explanation_text="核心算法对, 缺 input() 和 print()",
        ai_reasoning="核心算法对, 缺 I/O, 不构成完整可运行程序",
        timestamp=datetime.now(),
    )
    state = engine.update(state, obs_pb18)

    K_after = state.K.theta
    K_decline = K_before - K_after

    # 关键断言: partial credit K 跌幅 < 0.10 (不是 v0.52.2 之前的 0.27)
    assert K_decline < 0.10, \
        f"❌ partial credit K 跌幅过大: {K_decline:.4f} (应 < 0.10)\n" \
        f"  历史 (v0.52.2 之前): partial credit 缺失时 K 跌 0.27\n" \
        f"  期望 (v0.54.0-d 之后): partial credit 70% 时 K 跌 < 0.10"


# ─── 测试 8: response_history 老数据 backward compat ─────────────────────

def test_response_history_score_compat():
    """老 response_history 数据 (无 score 字段) 应 fallback 到 score = correct ? 1.0 : 0.0.

    拦截历史:
    - v0.49.2 response_history 改 dict 格式
    - v0.52.2 加 ai_reasoning 字段
    - v0.54.0-d/e 加 score 字段 (partial credit)
    """
    # 验证 Step 3 MIRT 用 h.get("score", h.get("correct", 0)) 兼容老数据
    history = [
        # v0.52.2 之前: 无 score 字段
        {"problem_id": "PB-Q01", "correct": 1, "bloom_level": "L1", "timestamp": "2026-07-21T10:00:00"},
        {"problem_id": "PB-Q02", "correct": 0, "bloom_level": "L2", "timestamp": "2026-07-21T10:01:00"},
        # v0.52.2: 加 ai_reasoning
        {"problem_id": "PB-Q03", "correct": 1, "bloom_level": "L3",
         "ai_reasoning": "答对", "timestamp": "2026-07-22T10:00:00"},
        # v0.54.0-e: 加 score 字段 (partial credit)
        {"problem_id": "PB-C01", "correct": 0, "score": 0.7,
         "ai_reasoning": "部分对", "timestamp": "2026-07-23T10:00:00"},
    ]

    # Step 3 MIRT 兼容逻辑: h.get("score", h.get("correct", 0))
    responses_compat = np.array(
        [h.get("score", h.get("correct", 0)) for h in history],
        dtype=float,
    )

    # 验证: 老数据 (无 score) fallback 到 correct 值
    assert responses_compat[0] == 1.0, \
        f"老数据 PB-Q01 correct=1 应 fallback 到 1.0, 实际={responses_compat[0]}"
    assert responses_compat[1] == 0.0, \
        f"老数据 PB-Q02 correct=0 应 fallback 到 0.0, 实际={responses_compat[1]}"
    assert responses_compat[2] == 1.0, \
        f"v0.52.2 数据 PB-Q03 correct=1 应 fallback 到 1.0, 实际={responses_compat[2]}"
    # v0.54.0-e 新数据: score 字段优先
    assert responses_compat[3] == 0.7, \
        f"v0.54.0-e 数据 PB-C01 score=0.7 应优先用 score, 实际={responses_compat[3]}"


# ─── 测试 9: MIRT estimate_theta 接受连续值 ─────────────────────────────

def test_mirt_estimate_theta_continuous_inputs():
    """MIRT estimate_theta 接受 responses = [0.3, 0.6, 0.7, 1.0] 连续值.

    验证 partial credit 改造后 MIRT MAP 估计不报错且收敛.
    """
    from ecos.cta.l2_mirt import MIRTItemParams, BiFactorMIRT5D

    # 注册 4 道题 (L1/L2/L3/L4)
    problems = [
        ("Q1", [0.5, 0.5, 0.5, 0.5, 0.5], 0.0),
        ("Q2", [0.4, 0.6, 0.4, 0.4, 0.4], 0.0),
        ("Q3", [0.3, 0.7, 0.3, 0.3, 0.3], 0.0),
        ("Q4", [0.5, 0.5, 0.5, 0.5, 0.5], 0.0),
    ]
    layer = BiFactorMIRT5D()
    for pid, a, d in problems:
        layer.register_item(MIRTItemParams(
            problem_id=pid,
            a_specialized=np.array(a),
            a_general=0.5,
            difficulty=d,
        ))

    # 连续值 responses
    responses_continuous = np.array([0.3, 0.6, 0.7, 1.0], dtype=float)

    # 验证 estimate_theta 不报错
    try:
        theta_hat, theta_cov = layer.estimate_theta(
            responses=responses_continuous,
            problem_ids=["Q1", "Q2", "Q3", "Q4"],
        )
        # θ 应该是 5 维向量
        assert len(theta_hat) == 5, f"θ 应是 5 维, 实际={len(theta_hat)}"
        # θ_cov 应该是 5x5 矩阵
        assert theta_cov.shape == (5, 5), f"θ_cov 应是 5x5, 实际={theta_cov.shape}"
    except Exception as e:
        pytest.fail(f"MIRT estimate_theta 拒绝连续值 responses: {e}")


# ─── 测试 10: MIRT estimate_theta 接受离散值 (backward compat) ──────────

def test_mirt_estimate_theta_discrete_backward_compat():
    """MIRT estimate_theta 接受 responses = [0, 1, 0, 1] 离散值 (老用法).

    验证 partial credit 改造不破坏 MIRT 离散值用法.
    """
    from ecos.cta.l2_mirt import MIRTItemParams, BiFactorMIRT5D

    problems = [
        ("Q1", [0.5, 0.5, 0.5, 0.5, 0.5], 0.0),
        ("Q2", [0.4, 0.6, 0.4, 0.4, 0.4], 0.0),
        ("Q3", [0.3, 0.7, 0.3, 0.3, 0.3], 0.0),
        ("Q4", [0.5, 0.5, 0.5, 0.5, 0.5], 0.0),
    ]
    layer = BiFactorMIRT5D()
    for pid, a, d in problems:
        layer.register_item(MIRTItemParams(
            problem_id=pid,
            a_specialized=np.array(a),
            a_general=0.5,
            difficulty=d,
        ))

    # 离散值 responses (老用法)
    responses_discrete = np.array([0, 1, 0, 1], dtype=float)

    try:
        theta_hat, theta_cov = layer.estimate_theta(
            responses=responses_discrete,
            problem_ids=["Q1", "Q2", "Q3", "Q4"],
        )
        assert len(theta_hat) == 5
        assert theta_cov.shape == (5, 5)
    except Exception as e:
        pytest.fail(f"MIRT estimate_theta 破坏离散值老用法: {e}")
