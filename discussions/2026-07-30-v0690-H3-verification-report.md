# H3 验证报告: lbc003

> **H3 假设**: 双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)
> **评估指标**: ECE (Expected Calibration Error), 越小越校准
> **通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent

**生成时间**: 2026-08-03T18:04:11.996763
**学生**: lbc003

---

## 1. 单 Agent Baseline (CTA only)

- 学生: lbc003
- 维度: K
- 样本数: 56
- **ECE**: `0.17404955325015395`
- 当前 mastery_prob: `N/A`
- 平均 accuracy: `0.8571428571428571`
- 平均 confidence: `0.6830933038927033`
- 注: v0.64.0 改进: 全部用 mastery_prob_after 历史快照

## 2. 双 Agent Experiment (CTA + LCA + 互校)

- 学生: lbc003
- 样本数: 41
- **ECE**: `0.6210048378408038`
- 平均 confidence (v0.69.0 V3 优先): `0.23265369874456207`
- 平均 accuracy (actual_outcome): `0.8536585365853658`
- 注: v0.69.0 V3 优先 (dual_agent_confidence) / V2 (overall_confidence) / V1 (expected_gain) 兜底, skip 1/42 行 (v0.60.4 历史数据), v0.68.0 DISTINCT 去重 drop 14 行重复 round

## 3. H3 验证结论

**结论**: ❌ **H3 未通过 (双 Agent ECE > 0.10)**

- 阈值: 双 Agent ECE ≤ 0.1
- 单 Agent baseline: ECE = 0.1740 (56 样本)
- 双 Agent experiment: ECE = 0.6210 (41 样本)
- 单 vs 双 差距: -0.4470

**理由**: 双 Agent ECE = 0.6210 > 阈值 0.1, 互校未显著减少 LLM 幻觉

## 4. 限制与建议 (v0.63.0 路线 A, 跑 lbc003)

### 数据基础限制
- 单 Agent baseline: lbc003 response_history 56 条 (够 30+, 统计意义 OK)
- 双 Agent experiment: lbc003 calibration_log **41 条** (不足 30, 统计意义有限)

### 方法限制
- v0.64.0 改进: 单 Agent confidence 用 mastery_prob_after 历史快照 (老 data 兜底)
- 双 Agent confidence 用 message_payload.expected_gain (互校预测 gain, 不是直接的 confidence)
- 没做 p-value 显著性检验 (样本量不足, 跑也不显著)

### 后续 (v0.63.0+ 路线 B)
1. lbc003 答 30+ 道题 (feature flag on, ECOS_DUAL_AGENT_ENABLED=1)
2. 收集 calibration_log 30+ 行
3. 跑本脚本重算 H3 (单 vs 双 ECE 对比 + p-value)
4. 写完整 H3 报告 (含显著性检验)

### 改进方向
- v0.64.0 已落地: mastery_prob_after 字段 (response_history 历史快照)
- 双 Agent confidence 改用 CalibratedLCAResult.intervention.confidence (更直接的校准信号)
- 加 reliability diagram 画图 (matplotlib 依赖待评估)

## 5. 显著性检验 (v0.68.0 新增)

**检验方法**: Welch t-test + Mann-Whitney U (max p)
**校准误差定义**: per 样本 |confidence - accuracy| (越小越校准)

- 单 Agent 校准误差均值: `0.3719` (56 样本)
- 双 Agent 校准误差均值: `0.6798` (41 样本)
- Welch's t-test: t = -6.8192, p = 0.0000
- Mann-Whitney U: U = 369.0000, p = 0.0000
- **综合 p-value (取 max)**: `0.0000`

**结论**: ❌ 方向反: 双 Agent (0.6798) > 单 Agent (0.3719), 互校没起作用, p=0.0000

### 显著性解读
- p < 0.05: 强烈支持 H3 (双 Agent 显著降低校准误差)
- 0.05 ≤ p < 0.10: 趋势支持, 建议增大样本量再验
- p ≥ 0.10: 当前数据不足以支持 H3, 方向对但需更多样本

## 6. v0.69.0 Confidence 版本分布 + 冷启动分段

### 6.1 Confidence 来源版本分布 (V3 优先 / V2 其次 / V1 兜底)

- V3 (dual_agent_confidence, LinUCB θ@x): **0 样本**
- V2 (state_overall_confidence, belief_state 5D 平均): **10 样本**
- V1 (expected_gain, _estimate_gain 简化估算): **31 样本**
- 合计: 41 样本

### 6.2 冷启动期 vs 非冷启动期分段 (仅 V3 数据有 source 标记)

- LinUCB 预测 (source="linucb"): **0 样本**
- _estimate_gain fallback (source="estimate_gain_fallback"): **0 样本**
- source 缺失 (V2/V1 老数据): **41 样本**

### 6.3 分段 ECE 对比

- 冷启动期 ECE: 数据不足 (无 source=estimate_gain_fallback 样本)
- 非冷启动期 ECE: `0.6210` (41 样本)


## 7. v0.70.0-d 修复后重放结果 (2026-08-03 更新)

> **触发**: v0.69.0 跑出来 V3=0 样本, 诊断发现策略质疑路径绕过 BUG.
> **修复**: v0.70.0 抽出 `_post_process_calibration` 方法, 常态循环 + 特殊模式两路径都调.
> **重放**: 用 lbc003 的 response_history 56 道, 全新 DualAgentOrchestrator 重跑 (in-memory, 不污染 DB).

### 7.1 修复后 V3 字段写入情况

- 总答题数: 56
- 触发策略质疑次数: **50 (89.3%)** -- lbc003 K mastery 早期饱和, 后期 50/56 道全触发
- V3 dual_agent_confidence 写入: **55/56 (98.2%)** ✅ (修复前 0/56)
- V3 source 分布:
  - linucb (LinUCB θ@x 预测): **40 样本** (修复前 0)
  - estimate_gain_fallback (冷启动 fallback): **15 样本** (修复前 0)
  - None (prev=None 第 1 道): 1 样本
- LinUCB 总 pull 次数: 50 (B4 reward=actual_outcome 已训练)
- 是否冷启动 (pulls < 10)? **False** (足够样本走 LinUCB θ@x)

### 7.2 修复后 V3 ECE

- 有效配对数 (V3 配 actual_outcome): **54**
- 平均 V3 confidence: **0.1096**
- 平均 actual_outcome: **0.8519**
- **ECE (per-sample |V3 - actual| 平均): 0.7596** ❌

### 7.3 新发现 BUG: LinUCB A 矩阵被策略质疑反复放大

诊断 LinUCB 内部状态:
- 每个 arm 的 A 矩阵最大特征值 ≈ 1.6e+05 (放大 16 万倍!)
- 每个 arm 的 θ 范数 ≈ 1e-4 (几乎为 0)
- θ = A^-1 b ≈ 0 -> expected_reward = θ @ x ≈ 0

**根因**: `ecos/dual_agent/modes/strategy_challenge.py:107` 的 `bandit.bandit.A[last_arm] *= LINUCB_PENALTY_FACTOR` (10.0).
lbc003 触发 50 次策略质疑, 每次 *10, A 矩阵累计放大 10^5 倍. θ 严重衰减, 预测永远接近 0.

**影响**: 即使 v0.70.0-d 修复了路径绕过 BUG, V3 仍 ECE 0.76 (比 V1=0.62 还差), H3 仍未通过.

### 7.4 后续修复方向 (v0.71+ P0-g)

1. **限制每 arm 惩罚次数** (每个 arm 最多惩罚 N 次, 超过不再 *10)
2. **用 LinUCB 标准 regularization** (A += λI, λ=1.0) 替代 *= 10
3. **完全移除惩罚机制** (让 B4 reward=actual_outcome 自己训练, LinUCB 自我修正)

### 7.5 H3 验证当前结论

- ✅ v0.69.0 B4+C1+D1 修复策略质疑路径绕过 BUG (v0.70.0-d)
- ❌ H3 仍未通过: V3 ECE=0.76 > 阈值 0.10
- 📋 后续必修: LinUCB 惩罚机制无上限 BUG (v0.71+ P0-g)
- 📋 后续观察: 修 LinUCB 惩罚后重跑 V3 ECE, 看是否 < 0.30

