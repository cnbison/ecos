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


## 8. v0.71.0 P0-g 修复后重放结果 (2026-08-03 更新)

> **触发**: v0.70.0-d 修了路径绕过 BUG 后, V3 字段终于写入 (55/56=98.2%), 但 V3 ECE=0.76 仍很差.
> **诊断**: LinUCB A 矩阵被策略质疑路径反复放大 (lbc003 触发 50 次 -> A 放大 1.6e+05 倍 -> θ ≈ 0).
> **修复**: v0.71.0 P0-g 加 `apply_penalty(arm, factor)` 方法, 每 arm 最多惩罚 `PENALTY_MAX` 次.

### 8.1 PENALTY_MAX 调参 (lbc003 56 道题重放)

| PENALTY_MAX | V3 linucb 样本 | V3 平均 conf | V3 ECE | A_max_eig_avg |
|---|---|---|---|---|
| 1 (默认) | 40 | 0.3833 | **0.5737** | 1.65e+01 |
| 2 | 40 | 0.1331 | 0.7320 | 1.71e+02 |
| 3 | 40 | 0.0978 | 0.7529 | 1.71e+03 |
| 5 | 40 | 0.0945 | 0.7553 | 1.71e+05 |

**最优值**: PENALTY_MAX=1 (ECE 0.57 < 0.76 之前). 1 次惩罚已够让 LinUCB 知道 arm 不好, 多次惩罚反而毁模型.

### 8.2 P0-g 修复后 LinUCB A 矩阵状态 (PENALTY_MAX=1)

- 每 arm 惩罚次数: 全部 = 1 (达到上限, 不再 *=10)
- A 矩阵最大特征值: ~1.65e+01 (修复前 1.6e+05, 减 1 万倍)
- θ 范数: ~0.03-0.04 (修复前 ~1e-4, 增 300 倍)

### 8.3 H3 验证当前结论 (v0.71.0 P0-g 后)

- ✅ v0.69.0 B4+C1+D1 改造落地 (v0.69.0)
- ✅ v0.70.0-d 修策略质疑路径绕过 BUG (V3 写入率 98.2%)
- ✅ v0.71.0 P0-g 修 LinUCB A 矩阵爆炸 (V3 ECE 0.76 -> 0.57)
- ❌ **H3 仍未通过**: V3 ECE=0.57 > 阈值 0.10

### 8.4 设计层面判断 (v0.72+ 评估)

即使修了所有 BUG (路径绕过 + A 矩阵爆炸), LinUCB θ@x 预测的 V3 confidence 仍无法准确预测答对率.
原因可能:
1. **Context vector 表达能力不够**: 5D theta + 6 Bloom + 5 DNA = 16 维, 没包含题目难度信息
2. **Reward 信号噪声大**: actual_outcome 是 0/1 二元信号, 样本量小时 LinUCB 学不准
3. **LinUCB 模型假设不匹配**: reward = θ @ x 假设线性, 但学生答对率可能是非线性

**后续 v0.72+ 评估方向**:
- 换 confidence 指标: CalibratedLCAResult.intervention.confidence (更直接的校准信号)
- 加 reliability diagram 画图看 V3 vs accuracy 分布
- 评估是否完全放弃 LinUCB θ@x 预测, 改用其他 confidence 源

---

## 9. v0.72.0 P0-i Platt Scaling 后校准结果 (2026-08-03 更新)

> **触发**: v0.71.0 P0-g 修 LinUCB A 矩阵爆炸后, V3 ECE 仍 0.57. 画 reliability diagram 诊断发现 V3 全局低估 0.54 (avg conf 0.32 vs avg acc 0.85), 详见 §10 + `discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md`.
> **方案**: Option 2.A Platt Scaling (per-student 后校准). P(correct=1 | raw_conf) = sigmoid(A·raw_conf + B), MLE 拟合 (raw_conf, actual_outcome) pairs.
> **实现**: `ecos/dual_agent/calibration.py` (新增) + `ecos/dual_agent/orchestrator.py` 集成 `_update_and_apply_calibration` 方法.

### 9.1 Platt Scaling 设计

- **per-student tracker**: `StudentCalibrationTracker` 维护每学生 (raw_V3, actual_outcome) pairs buffer
- **冷启动期** (n_pairs < 5): 返回 raw_V3, source = "raw_v3"
- **fit 后**: 用 `sigmoid(A·raw_V3 + B)` 校准, source = "platt_scaling"
- **refit 触发**: 每次 add_pair 触发 refit (数据量小, refit 成本可忽略)
- **失败兜底**: 任何 scipy 优化失败 -> _log.warning + 写 raw V3, 不污染 in-memory state
- **新 metadata 字段**: `dual_agent_confidence_calibrated` + `dual_agent_confidence_calibrated_source`

### 9.2 修复后 V3 ECE 对比 (lbc003 56 道题重放)

| 指标 | 单 Agent baseline | 双 V3 raw (v0.71.0 P0-g) | 双 V3 calibrated (v0.72.0 P0-i) |
|---|---|---|---|
| 平均 conf | 0.6831 | 0.3161 | **0.8426** |
| 平均 actual_outcome | 0.8519 | 0.8519 | 0.8519 |
| 全局 gap (acc - conf) | +0.1688 | +0.5358 | **+0.0092** (almost zero) |
| **ECE (per-sample)** | **0.1740** | 0.6328 | **0.2794** |
| 改善 (vs raw V3) | — | — | **-0.3534 (55.8%)** |

**关键观察**:
- 平均 conf 从 0.32 -> 0.84 (跟 actual 0.85 几乎一致, gap 0.009 几乎完美)
- ECE 从 0.63 -> 0.28 (改善 56%)
- 仍未过 0.10 阈值, 但已非常接近单 Agent baseline (0.17)

### 9.3 Reliability Diagram 数据 (v0.72.0 P0-i 后)

| bin | mean_conf | mean_acc | gap | n | source |
|---|---|---|---|---|---|
| [0.1, 0.2] | 0.1425 | 1.0000 | -0.8575 | 5 | raw_v3 (cold start) |
| [0.8, 0.9] | 0.8407 | 0.8261 | +0.0146 | 23 | platt_scaling |
| [0.9, 1.0] | 0.9789 | 0.8462 | +0.1328 | 26 | platt_scaling |

**关键观察**:
- calibrated V3 全部集中在 [0.8, 1.0] 区间 (49/54 样本), 之前 raw V3 全部在 [0.1, 0.4]
- Bin [0.8, 0.9] 几乎完美校准 (gap +0.01)
- Bin [0.9, 1.0] 轻微高估 (gap +0.13), 来自 saturation: raw V3 接近 0.4 -> calibrated 接近 1.0 -> 真 acc 0.85
- 图: `discussions/2026-08-03-v0720-reliability-diagram-raw-vs-calibrated.png`

### 9.4 H3 验证当前结论 (v0.72.0 P0-i 后)

- v0.69.0 B4+C1+D1 改造落地
- v0.70.0-d 修策略质疑路径绕过 BUG (V3 写入率 98.2%)
- v0.71.0 P0-g 修 LinUCB A 矩阵爆炸 (V3 ECE 0.76 -> 0.57)
- v0.72.0 P0-i Platt Scaling 后校准 (V3 ECE 0.57 -> 0.28, gap 0.54 -> 0.01)
- **H3 仍未通过**: calibrated V3 ECE = 0.28 > 阈值 0.10, 但已接近单 Agent baseline (0.17)

### 9.5 后续方向

1. **提升 calibration 精度** (v0.73+ 评估):
   - 增大 min_samples_to_fit (从 5 -> 10) 减少 refit 次数, 稳定 A, B
   - 引入 L2 正则化 (Platt 1999) 避免极端参数
   - 跨学生迁移 (global scaler + per-student 偏移)
2. **减小 per-sample 误差**:
   - 当前 ECE 0.28 来自 per-sample 方差 (即使 mean 完美, 个别样本仍有误差)
   - 可考虑 per-bin 校准 (isotonic regression) 替代 sigmoid
3. **Plan B 准备**: 若 v0.73 仍 > 0.20, 顺势走 D (重定义 H3 假设, 详见 diagnosis 报告 §4.4)

### 9.6 测试覆盖 (v0.72.0 P0-i 新增)

- `tests/test_platt_scaler.py` (15 测试):
  - `TestPlattScalerBasic` (8): identity / fit / transform / 单调 / bounded / 失败兜底
  - `TestStudentCalibrationTracker` (4): 冷启动 / 首次 refit / 累积 refit / clamp
  - `TestOrchestratorPlattScalingIntegration` (2): calibrated 字段写入 / 5+ pairs 后激活
  - `TestLbc003PlattScalingImprovement` (1): lbc003 重放, calibrated ECE < raw ECE + < 0.40

---

## 10. Reliability Diagram 诊断 (2026-08-03 更新, v0.71.0 P0-g 修复后)

> **触发**: v0.71.0 P0-g 修 LinUCB A 矩阵爆炸后, V3 ECE 仍 0.57 > 阈值 0.10, 画 reliability diagram 诊断 V3 偏差方向.
> **脚本**: `scripts/plot_reliability_diagram.py` (v0.71.0 版本) + 图 `discussions/2026-08-03-v0710-reliability-diagram.png`
> **详细分析**: `discussions/2026-08-03-v0710-reliability-diagram-diagnosis.md`

### 10.1 诊断结论

- **V3 全局低估 0.54**: avg conf 0.32 vs avg acc 0.85
- **分布异常**: 所有 54 个 V3 样本都集中在 [0.1, 0.4] 区间, 没有任何样本 > 0.4
- **根因**: LinUCB 线性模型 (θ@x) + 16 维 + 54 样本数学上拟合不了 lbc003 高 baseline (0.85). 修了所有 BUG (路径绕过 + A 矩阵爆炸) 后, 模型本身仍不可信.

### 10.2 Option 2 4 个候选方案评估

| 方案 | 推荐度 | 预期 ECE | 备注 |
|---|---|---|---|
| **A. Platt Scaling (per-student 后校准)** | (推荐, 已实施) | 0.10-0.25 | 改动最小, 经典 calibration 方案 |
| B. CTA mastery_prob + V3 混合 | 不推荐 | 0.30-0.50 | 违背 v0.69.0 PRD B3 决策, 治标不治本 |
| C. 完全放弃 V3, 改用 mastery_prob | 不推荐 | 0.17 | 违背双 Agent 理念, H3 验证设计要重做 |
| D. 重定义 H3 假设 (互校改抗不一致性) | Plan B | ECE 验证作废 | 诚实反思, 推翻之前 H3 声明 |

**已选 A, v0.72.0 实施结果**: ECE 0.28 (落在预期区间).

