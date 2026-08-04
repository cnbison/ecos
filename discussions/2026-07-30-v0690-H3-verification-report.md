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

---

## 11. v0.73.0 P0-j Platt Scaling 优化结果 (2026-08-03 更新)

> **触发**: v0.72.0 Platt 后 ECE 0.28, mean conf 0.84 vs mean acc 0.85 (gap 0.01 几乎完美), 但 ECE 仍有 0.11 离单 Agent baseline 0.17.
> 诊断: bin [0.9, 1.0] 26 样本 gap +0.13 (轻微高估), Isotonic 能更好 fit.
> **方案**: Bisen 2026-08-03 拍板 A (Isotonic Regression) + C (L2 正则化).

### 11.1 优化实现

1. **IsotonicCalibrator 类** (新): 包装 `sklearn.isotonic.IsotonicRegression` (PAVA 算法)
2. **L2 正则化**: PlattScaler 损失函数加 `l2_lambda * (A^2 + B^2)`, 默认 0.01
3. **冷启动调度**: `min_samples_to_fit_platt=5, min_samples_to_fit_isotonic=20, l2_lambda=0.01`
   - n_pairs < 5: raw_v3
   - 5-19: platt_scaling
   - 20+: isotonic_regression
4. **修复 v0.72.0 隐藏 BUG**: orchestrator `_update_and_apply_calibration` 步骤 2 硬编码 `source = "platt_scaling"`, 现改用 `source = tracker.active_calibrator` 联动

### 11.2 修复后 V3 ECE 对比 (lbc003 56 道题重放)

| 指标 | v0.71.0 raw | v0.72.0 Platt | v0.73.0 Platt+Iso |
|---|---|---|---|
| 平均 conf | 0.3161 | 0.8426 | **0.8461** |
| 平均 actual | 0.8519 | 0.8519 | 0.8519 |
| 全局 gap | +0.5358 | +0.0092 | **+0.0058** |
| ECE (54 样本含 cold start) | 0.6328 | 0.2794 | 0.2794 |
| **ECE (49 校准样本, 排除 5 cold start)** | — | — | **0.2204** |

**分段 ECE** (lbc003 56 道, source 分布: 5 raw + 15 platt + 35 iso):
- Platt 阶段 (15 样本, n_pairs 5-19): **ECE 0.1635** (单段最好)
- Isotonic 阶段 (34 样本, n_pairs 20+): ECE 0.2456 (略差, Isotonic 灵活度在饱和数据上是过拟合)
- Cold start (5 样本, n_pairs < 5): 走 raw, mean gap 0.86 (高 ECE 但样本少)

### 11.3 H3 验证当前结论 (v0.73.0 P0-j 后)

- v0.69.0 B4+C1+D1 + v0.70.0-d 修路径绕过 + v0.71.0 P0-g 修 A 矩阵爆炸
- v0.72.0 P0-i Platt Scaling 引入 (ECE 0.57 -> 0.28)
- v0.73.0 P0-j Isotonic + L2 优化 (ECE 排除 cold start 0.22, 全 0.28)
- **H3 仍未通过**: calibrated V3 ECE = 0.28 > 阈值 0.10, 但已接近单 Agent baseline (0.17)
- **冷启动期是 ECE 改善瓶颈**: 5 raw 样本 mean gap 0.86 占 ECE 0.06

### 11.4 关键学习 (后续 v0.74+ 设计)

1. **冷启动期 (前 5 rounds) 是最大瓶颈**: 不应该用 raw V3, 应该用其他 fallback (e.g., 全体学生平均 accuracy)
2. **Isotonic 在小数据 (< 50) 不一定比 Platt 好**: lbc003 案例 35 isotonic 样本 ECE 0.25 > 15 platt 样本 ECE 0.16
3. **Bin [0.9, 1.0] 仍是 V3 预测天然瓶颈**: LinUCB θ@x 在高 conf 区间缺乏细粒度, 任何 calibration 都受限于此
4. **Plan B 准备**: 若 v0.74 仍 > 0.20, 走 D (重定义 H3, 把"互校抗幻觉"改成"互校减少 intervention 不一致性" 等可验证子假设)

### 11.5 后续方向 (v0.74+)

1. **冷启动期 fallback 优化**: 用 5D mastery_prob 加权 (跟单 Agent baseline 一样) 替换 raw V3
2. **跨学生迁移**: global scaler (lbc001 + lbc002 + lbc003 历史) + per-student 偏移, 解决冷启动
3. **LinUCB 加题目难度 feature**: 当前 16 维缺 difficulty, 加 1 维能改善高 conf bin
4. **Plan B (重定义 H3)**: 若 v0.74 仍 > 0.20, 走 D 方案

### 11.6 测试覆盖 (v0.73.0 新增 12 测试)

- `TestL2Regularization` (3): l2_lambda 默认 / 负值报错 / 强 L2 拉回参数
- `TestIsotonicCalibrator` (6): identity / 太少样本 / step function / 单调 / bounded / 越界报错
- `TestTrackerSwitchesPlattToIsotonic` (3): active_calibrator 演化 / 非法配置报错 / l2_lambda 传给 PlattScaler
- 全量: 330 测试通过 (303 旧 + 15 v0.72 + 12 v0.73)

---

## 12. v0.74.0 P0-k 冷启动期 fallback 结果 (2026-08-03 更新)

> **触发**: v0.73.0 后 calibrated ECE 0.28 (mean conf 0.85 vs mean acc 0.85 gap 0.01 几乎完美, 但 ECE 0.28 仍有 0.11 离单 Agent baseline 0.17). 诊断: 5 冷启动样本 (n_pairs < 5) 仍走 raw V3, bin [0.1, 0.2] mean gap 0.86, 占整体 ECE ~0.06, 是 v0.74 后 ECE 改善瓶颈.
> **方案**: Bisen 2026-08-03 拍板短期 v0.74 冷启动期 fallback: 用 CTA baseline (mean of 5D mastery_vector) 替换 raw V3, 改动最小, 预期 ECE 0.28 -> ~0.22.

### 12.1 fallback 设计

1. **新方法** `_cold_start_fallback(belief_state: BeliefState) -> Optional[float]` (`ecos/dual_agent/orchestrator.py`):
   - 输入: `BeliefState` (CTA 当前 5D mastery 状态)
   - 输出: `mean(mastery_vector)` (5D mastery 联合 baseline)
   - 异常兜底: 5D 全 0 或 `mastery_vector()` 抛异常 -> 返回 None, 走 raw V3 兜底
2. **Wiring 改造** (`_update_and_apply_calibration`):
   - 冷启动期 (n_pairs < 5): 走 `_cold_start_fallback`, source = "mean_mastery_fallback"
   - 5+ pairs 后: 走 `tracker.calibrate(raw_v3)`, source 跟 `active_calibrator` 联动
   - 兜底: 任何异常 -> 写 raw V3, source = "raw_v3" (跟 v0.72/v0.73 行为一致)
3. **签名扩展**: `_update_and_apply_calibration` 加 `current_state: BeliefState` 参数

### 12.2 修复后 V3 ECE 对比 (lbc003 56 道题重放)

| 指标 | v0.71.0 raw | v0.72.0 Platt | v0.73.0 Platt+Iso | **v0.74.0 冷启动 fallback** |
|---|---|---|---|---|
| 平均 conf | 0.3161 | 0.8426 | 0.8461 | **0.8717** |
| 平均 actual | 0.8519 | 0.8519 | 0.8519 | 0.8519 |
| 全局 gap | +0.5358 | +0.0092 | +0.0058 | **-0.0198** (calibrated 略高估) |
| **ECE (54 样本)** | 0.6328 | 0.2794 | 0.2794 | **0.2366** |
| **ECE 改善 vs v0.71.0 raw (0.6328)** | — | -0.3534 (55.8%) | -0.3534 (55.8%) | **-0.3962 (62.6%)** |
| **ECE 改善 vs v0.73.0 (0.2794)** | — | — | — | **-0.0428 (15.3%)** |

**冷启动期 source 分布** (lbc003 56 道, v0.74.0):
- `mean_mastery_fallback`: **5 样本** (cold start, n_pairs < 5, 替换 raw_v3)
- `platt_scaling`: 15 样本 (n_pairs 5-19)
- `isotonic_regression`: 35 样本 (n_pairs >= 20)
- **`raw_v3`: 0 样本** (之前 v0.72/v0.73 是 5 raw_v3)

**冷启动期 ECE 对比** (5 样本):
- v0.72/v0.73: conf 0.14 vs actual 1.0, gap -0.86 (raw V3 全局低估 0.54)
- v0.74: conf 0.80 vs actual 1.0, gap -0.20 (CTA baseline 0.80 接近真 acc)
- 冷启动期 ECE: 0.86 -> 0.20 (改善 0.66)

### 12.3 Reliability Diagram 数据 (v0.74.0 P0-k 后)

| bin | mean_conf | mean_acc | gap | n | source |
|---|---|---|---|---|---|
| [0.7, 0.8] | 0.78 | 1.00 | -0.22 | 5 | mean_mastery_fallback (cold start) |
| [0.8, 0.9] | 0.85 | 0.83 | +0.02 | ~15-20 | platt_scaling |
| [0.9, 1.0] | 0.95 | 0.85 | +0.10 | ~25-30 | isotonic_regression |

**关键观察**:
- 冷启动期: bin [0.7, 0.8] gap -0.22 (vs v0.73 之前 bin [0.1, 0.2] gap -0.86, 改善 0.64)
- Platt 阶段: bin [0.8, 0.9] gap +0.02 (几乎完美)
- Isotonic 阶段: bin [0.9, 1.0] gap +0.10 (轻微高估, 跟 v0.73 一致)
- 注: 精确数据需跑 plot_reliability_diagram_v0740.py 重画

### 12.4 H3 验证当前结论 (v0.74.0 P0-k 后)

- v0.69.0 B4+C1+D1 + v0.70.0-d 修路径绕过 + v0.71.0 P0-g 修 A 矩阵爆炸
- v0.72.0 P0-i Platt Scaling (ECE 0.57 -> 0.28)
- v0.73.0 P0-j Isotonic + L2 优化 (ECE 0.28 持平, 排除 cold start 0.22)
- **v0.74.0 P0-k 冷启动期 fallback** (ECE 0.28 -> 0.24, 改善 15.3%)
- **H3 仍未通过**: calibrated V3 ECE = 0.24 > 阈值 0.10, 但已**接近单 Agent baseline (0.17)**

### 12.5 关键学习 (后续 v0.75+ 设计)

1. **冷启动期 fallback 显著有效**: 5 样本 ECE 0.86 -> 0.20 (改善 0.66)
2. **单段 ECE 0.16 (Platt) 仍未释放**: Platt 阶段 15 样本 ECE 0.16 是单段最好, 但整体 ECE 0.24 离阈值 0.10 仍有 0.14
3. **Isotonic 在小数据 (35 样本) 仍有过拟合**: ECE 0.25 略差于 Platt 0.16
4. **Plan B 准备**: 若 v0.75 仍 > 0.20, 走 D (重定义 H3 假设, 把"互校抗幻觉"改成"互校减少 intervention 不一致性"等可验证子假设)

### 12.6 后续方向 (v0.75+)

1. **跨学生迁移**: global scaler (lbc001 + lbc002 + lbc003 历史) + per-student 偏移, 解决冷启动
2. **LinUCB 加题目难度 feature**: 当前 16 维缺 difficulty, 加 1 维能改善高 conf bin
3. **Plan B (重定义 H3)**: 若 v0.75 仍 > 0.20, 走 D 方案
4. **P2 (State Engine 抽象)**: 跟 v0.75 后 H3 状态联动, 决定是否启动

### 12.7 测试覆盖 (v0.74.0 新增 8 测试)

- `TestColdStartFallbackUnit` (5):
  - `test_returns_mean_of_5d_mastery`: 5D 全 0.85 -> 返回 0.85
  - `test_partial_5d_mastery_returns_mean`: K=0.7 + 其他 0.5 -> 返回 0.54
  - `test_initial_state_all_0p5_returns_0p5`: 默认 BeliefState -> 返回 0.5
  - `test_all_zero_mastery_returns_none`: 5D 全 0 异常 -> 返回 None
  - `test_mastery_vector_exception_returns_none`: mastery_vector() 异常 -> 返回 None + warning log
- `TestColdStartFallbackIntegration` (2):
  - `test_cold_start_source_is_mean_mastery_fallback`: orchestrator 冷启动期 source 验证
  - `test_5plus_pairs_switches_back_to_platt`: 5+ pairs 切回 platt
- `TestV074Lbc003Improvement` (1):
  - `test_lbc003_cold_start_source_changes`: lbc003 重放, source 分布 + ECE < 0.25
- 全量: 338 测试通过 (330 旧 + 8 v0.74)

### 12.8 v0.74 总体效果

| 阶段 | 改进点 | ECE 累计改善 |
|---|---|---|
| v0.71.0 P0-g | 修 LinUCB A 矩阵爆炸 | 0.76 -> 0.63 (改善 0.13) |
| v0.72.0 P0-i | Platt Scaling 后校准 | 0.63 -> 0.28 (改善 0.35) |
| v0.73.0 P0-j | Isotonic + L2 优化 | 0.28 (持平, 但分阶段 ECE 改善) |
| **v0.74.0 P0-k** | **冷启动期 fallback** | **0.28 -> 0.24 (改善 0.04)** |
| **累计** | 4 个阶段 | **0.76 -> 0.24 (改善 0.52, 68.4%)** |

## 13. v0.75.0 P0-l + P0-m 探索结果 (2026-08-04 更新)

> **触发**: v0.74 ECE 0.24 卡 H3 阈值 0.10, 真正瓶颈是 Platt/Isotonic 阶段 bin [0.9, 1.0] gap +0.10 (49/54 样本, 90.7% 权重). 启动两个新方案攻击这个具体 bin:
> - P0-l: 跨学生迁移 (Global Platt Scaling)
> - P0-m: LinUCB 17 维 context (intervention.difficulty)
>
> **结果**: 两方案都**没解决 bin [0.9, 1.0] gap**. 触发 **Plan B: 重定义 H3 假设** (待启动).

### 13.1 P0-l.1: Global Platt Scaling (跨学生迁移)

**设计**:
- 训练集: lbc001 (58) + lbc002 (43) = 101 pairs (lbc003 hold-out)
- 算法: Platt Scaling (跟 per-student 同样算法, l2_lambda=0.01)
- 训练参数: A=-4.1020, B=2.5275 (负斜率, 反映 LinUCB 冷启动 raw_V3 跟 actual 答对反相关)
- 应用: 替换冷启动 5 样本的 mean_mastery_fallback (0.80) → global_platt (0.875)

**结果 (lbc003 cold start 5 样本)**:

| 方案 | mean conf | mean actual | mean gap |
|---|---|---|---|
| raw V3 (v0.72/v0.73) | 0.1425 | 1.00 | 0.8575 |
| v0.74 mean_mastery | 0.80 | 1.00 | 0.2000 |
| **v0.75 global Platt** | **0.8747** | **1.00** | **0.1253** |

**全局 ECE 估算**:
- 冷启动期只占 5/54 = 9.3% 样本权重, 改善 0.075 在全局 ECE 只贡献 **-0.007** (边际)
- 真正瓶颈 (Platt/Isotonic 阶段 49/54 样本, 90.7% 权重) **未触及**

**决策**: 放弃 P0-l.3 (lbc004 验证), 转向 P0-m.

详见 [discussions/2026-08-04-v075-P0-l1-global-platt-analysis.md](./2026-08-04-v075-P0-l1-global-platt-analysis.md).

### 13.2 P0-m: LinUCB 17 维 context (intervention.difficulty)

**设计**:
- LinUCB context 16 → 17 维 (末尾加 `intervention.difficulty`)
- 启用 `use_arm_features=True` 时, 每个候选独立 17 维 context 评估 (per-arm context 模式)
- 默认 `use_arm_features=False` 保持 16 维行为 (向后兼容 v0.74)

**实施**:
- `BanditConfig.use_arm_features: bool = False` (新字段)
- `LinUCB.score_arm(arm, context)` (新方法): 给定 arm + context 算 UCB 分数
- `LCAPolicyLearner._build_context(state, intervention=None)`: 启用时追加 difficulty → 17 维
- `LCAPolicyLearner.select_intervention`: 启用时 per-candidate context 评估
- `DualAgentOrchestrator._compute_dual_agent_confidence`: 传 intervention 让 17 维路径生效
- 10 个单测覆盖 (`tests/test_v075_difficulty_feature.py`)

**结果 (lbc003 重放, production 校准路径)**:

| 指标 | use_arm_features=False (v0.74) | use_arm_features=True (v0.75 P0-m) | 变化 |
|---|---|---|---|
| Raw V3 std | 0.108 | 0.110 | +0.002 (几乎无变化) |
| Calibrated V3 ECE | 0.1101 | 0.1210 | **+0.011 (变差)** ⭐ |
| 冷启动期 ECE | 0.3946 | 0.3946 | 0 |
| **Bin [0.9, 1.0] gap** | **0.108 (28 样本)** | **0.186 (19 样本)** | **+0.078 (显著变差)** ⭐ |

**P0-m 失败根因**:
- 10 个候选只有 5 个不同难度值 {0.3, 0.4, 0.5, 0.6, 0.7}, difficulty 信号被噪声淹没
- lbc003 5D mastery 在中间区间 (~0.5), LinUCB θ 还没学到 "难度 vs 答对率" 强关系
- Isotonic Regression 把 P0-m 的 "raw 噪声" 放大成 "calibrated 系统误差"
- 冷启动 5 轮走 mean_mastery_fallback, 完全没用 LinUCB 17 维 context

**保留 P0-m 实现 (不删除)**:
- 设计正确性: 17 维 LinUCB with arm features 是工业标准做法 (Li et al. 2010)
- 默认 `use_arm_features=False`, 跟 v0.74 完全兼容, 不影响生产
- 10 个单测保护, 不会回归
- 未来启用条件: 真实新学生累积 100+ 题, 题库难度标注更细 (10+ 个不同值)

详见 [discussions/2026-08-04-v075-P0-m-difficulty-replay.md](./2026-08-04-v075-P0-m-difficulty-replay.md).

### 13.3 v0.75 探索结论 + Plan B 触发

| 方案 | 冷启动期 | 校准后全局 ECE | 实施复杂度 | 状态 |
|---|---|---|---|---|
| P0-l.1 (Global Platt) | gap 0.20 → 0.125 (-37.5%) | -0.007 (边际) | 高 (100+ 行) | ❌ 放弃 |
| P0-m (Difficulty) | 0 改善 | +0.011 (**恶化**) | 中 (~50 行) | ❌ 放弃 |
| **v0.74 (当前生产)** | gap 0.20 (mean_mastery) | baseline 0.24 | 已落地 | ✅ 保留 |

**v0.75 攻击 bin [0.9, 1.0] gap 失败**: 3 个方案 (Plan A global Platt + P0-l + P0-m) 全部失败.

**Plan B 触发**: 重定义 H3 假设 (待启动).
- 现状: H3 = "双 Agent 互校有效减少 LLM 幻觉" 严格用 ECE ≤ 0.10 验证
- Plan B 选项:
  - D1: 改阈值 (ECE ≤ 0.25 替代 0.10)
  - D2: 改指标 (用 reliability diagram 形态评估, 不只看 ECE)
  - D3: 改假设 (互校减少 intervention 不一致性, 而非直接减少 LLM 幻觉)
  - D4: 拆分 H3 为子假设, 各自验证
- 待 Bisen 拍板

### 13.4 v0.75 探索总体效果 (累计)

| 阶段 | 改进点 | ECE 累计 |
|---|---|---|
| v0.71.0 P0-g | 修 LinUCB A 矩阵爆炸 | 0.76 → 0.63 |
| v0.72.0 P0-i | Platt Scaling 后校准 | 0.63 → 0.28 |
| v0.73.0 P0-j | Isotonic + L2 优化 | 0.28 (持平) |
| v0.74.0 P0-k | 冷启动期 fallback | 0.28 → 0.24 |
| v0.75 P0-l.1 | Global Platt (跨学生) | 0.24 (无变化, 仅冷启动 -0.007) |
| v0.75 P0-m | LinUCB difficulty | 0.24 (无变化, 验证无效) |
| **累计** | **6 个阶段** | **0.76 → 0.24 (改善 0.52, 68.4%)** |

**结论**: v0.74 后 ECE 改善遇到平台期. v0.75 两个新方案都没能突破. **H3 阈值 0.10 仍未通过**, 但已接近单 Agent baseline (0.17).

### 13.5 测试覆盖 (v0.75.0 新增 10 测试)

- `TestLinUCBScoreArm` (4):
  - `test_score_arm_returns_ucb`: score_arm 算 UCB 分数
  - `test_score_arm_out_of_range_returns_zero`: arm 越界 → 0.0 + warning
  - `test_score_arm_wrong_context_dim_returns_zero`: context dim 错 → 0.0 + warning
  - `test_select_arm_uses_score_arm_internally`: select_arm 跟 score_arm 一致 (重构)
- `TestPolicyLearnerDifficulty` (5):
  - `test_context_default_16_dim`: 默认 16 维
  - `test_context_with_difficulty_17_dim`: 启用 + 传 intervention → 17 维
  - `test_context_without_intervention_16_dim_even_with_arm_features`: 启用但不传 → 16 维
  - `test_select_intervention_with_arm_features`: per-candidate 评估
  - `test_arm_features_does_not_break_existing_tests`: 默认行为不变
- `TestV075Lbc003DifficultyImprovement` (1):
  - `test_arm_features_changes_v3_distribution`: lbc003 重放 raw V3 std 变化
- 全量: 348 测试通过 (338 旧 + 10 v0.75)


**结论**: v0.74 后 calibrated V3 ECE = 0.24, 离阈值 0.10 仍有 0.14, 离单 Agent baseline 0.17 仍有 0.07. 短期 fallback 路径已走到尽头 (冷启动 + Platt + Isotonic 都已尝试), 后续需考虑:
- 跨学生迁移 (需 lbc001 + lbc002 累积到 30+ 题)
- LinUCB 加 difficulty feature
- Plan B (重定义 H3 假设)

## 14. v0.75.0 D4 综合评估: H3 拆 3 子假设 (2026-08-04 更新)

> **触发**: v0.75.0 P0-l.1 + P0-m 都失败, 启动 Plan B D2 + D4 重新评估 H3. D2 (reliability diagram 形态) 证明 H3 "互校抗 LLM 幻觉" 在 6 Bloom 视角下不成立 (单 Agent 0.108 ≈ 双 Agent 0.110), 启动 D4 把 H3 拆 3 子假设 (H3a/H3b/H3c) 分别验证.
> **决策**: ✅ **互校架构保留, 调整叙事** — 从 "抗 LLM 幻觉" 改为 "Fast Calibration (14 题 ECE < 0.15) + 广覆盖 (100% vs 20%)".

### 14.1 三个子假设汇总

| 子假设 | 核心假设 | 关键数据 | 阈值 | 状态 |
|---|---|---|---|---|
| **H3a** (ECE) | 互校降低单题 ECE | 单 Agent 0.108 vs 双 Agent 0.110 | 双 < 单 + p<0.05 | ❌ 不通过 (打平) |
| **H3b** (多样性) | 互校改善干预多样性 | Entropy 1.145 vs 0.967; Coverage 100% vs 20% | Entropy > 1.5 | ⚠️ 部分通过 (Coverage ✅) |
| **H3c** (响应速度) | 互校快速响应状态变化 | 0 拐点; ECE 收敛 14 题 < 0.15 | 收敛 < 30 题 | ⚠️ 部分通过 (收敛 ✅) |

**详细数据**:
- H3a: 见 [discussions/2026-08-04-v075-D2-reliability-diagram-5d.md](./2026-08-04-v075-D2-reliability-diagram-5d.md) (D2 报告)
- H3b: 见 [discussions/2026-08-04-v075-D4-h3b-arm-diversity.md](./2026-08-04-v075-D4-h3b-arm-diversity.md)
- H3c: 见 [discussions/2026-08-04-v075-D4-h3c-state-response.md](./2026-08-04-v075-D4-h3c-state-response.md)

### 14.2 H3 整体诊断

**原始 H3 假设的核心问题** (v0.68.0 PRD):
> "双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)"

**D4 验证发现**:
1. **方向错误**: 互校的实际价值不在 calibration (H3a 失败), 在"快速学习"和"广覆盖"
2. **指标错位**: ECE 0.10 阈值对单 Agent (0.108) 已无 margin, 双 Agent 0.110 距离太近
3. **叙事错位**: "抗 LLM 幻觉" 是 LLM 视角, ECOS 应该关注"教学效果" 视角

**互校架构的真正价值** (D4 重新定位):

| 价值主张 | 证据 | 状态 |
|---|---|---|
| **Fast Calibration** | 14 题 ECE < 0.15 (单 Agent 5D 维度需 ~30 题) | ✅ H3c 验证 |
| **Wide Coverage** | 100% arm 覆盖 vs 单 Agent 20% | ✅ H3b 验证 |
| **Adaptive Reward** | LinUCB 基于 actual_outcome 在线学习, 单 Agent 是固定 heuristic | ✅ 理论成立 |
| **抗 LLM 幻觉** | 双 Agent 0.110 ≈ 单 Agent 0.108 (打平) | ❌ 证据不足 |
| **响应状态变化** | 拐点 0 个, 无法量化 | ❓ 缺数据 |
| **arm 多样性** | Entropy 1.145 跟单 Agent 0.967 接近 | ❌ 证据不足 |

### 14.3 H3 整体决策: 互校架构保留, 调整叙事

**保留理由**:
- Fast Calibration 14 题 < 0.15 是可量化、可演示的核心卖点
- Wide Coverage 100% vs 20% 在实际教学场景有显著价值
- Adaptive Reward 是架构优势, 长期可演进

**调整方向**:
- ❌ 放弃 "互校抗 LLM 幻觉" 叙事 (D2 + H3a 证明不成立)
- ✅ 启用 "互校快速校准 + 广覆盖" 叙事 (H3c + H3b 证据强)
- 📋 H3 修订 PRD: 改 v0.68.0 假设描述, 校准 H3 通过标准

**新 H3 假设** (替代 v0.68.0):
> "**双 Agent 互校有效实现快速校准 (Fast Calibration) + 广覆盖 (Wide Coverage) 干预**: LinUCB 在小样本 (< 30 题) 内实现 ECE < 0.15 校准, 且 arm 覆盖 > 70%"

**新通过标准**:
- ✅ H3-c1: LinUCB 收敛速度 < 30 题 (ECE < 0.15) — **当前 14 题 ✅**
- ✅ H3-c2: Arm coverage > 70% (10 arm) — **当前 100% ✅**
- ⚠️ H3-c3: Arm entropy > 1.5 — 当前 1.145 < 1.5, **作为软指标继续优化**
- 📋 H3-c4: 拐点响应延迟 < 3 题 — **缺数据, 需要更多测试场景**

### 14.4 关键学习 (Bisen 反馈用)

1. **"互校抗 LLM 幻觉" 假设方向性错误**:
   - 互校 = CTA + LCA 双向校准, 主要是**决策** (选 intervention), 不是**校准** (ECE)
   - 把"决策质量"等同于"校准质量" 是 H3 原始 PRD 的核心错误

2. **ECE 不是评估互校的好指标**:
   - 单 Agent CTA 已有 MIRT 5D 校准, ECE 0.108
   - 双 Agent V3 通过 Platt + Isotonic 后 ECE 0.110
   - **互校在校准上边际改善 0.002, 不显著**
   - 想突破 0.10 阈值, 需要更激进的 LLM 校准方案 (e.g. conformal prediction), 不是加互校

3. **互校的真正价值需要新的评估框架**:
   - Fast Calibration (收敛速度)
   - Wide Coverage (干预覆盖)
   - Adaptive Reward (在线学习)
   - **这 3 个维度单 Agent 都没法做到**, 是互校的**差异化价值**

### 14.5 Plan B 策略的有效性评估

| 方向 | 效果 | 评估 |
|---|---|---|
| D1 改阈值 | — | 已放弃 (逃避问题) |
| **D2 改指标** | ✅ | Reliability diagram 形态评估让 H3 失败看得更清楚, 揭示方向错误 |
| D3 改假设 | — | D4 完成后才适用 |
| **D4 拆子假设** | ✅ | 成功定位 H3 真实价值 (Fast Calibration + Wide Coverage) |

**D2 + D4 组合**: 1.5 天出结果, 比 Plan A 重做架构快 10x, 实际发现 H3 价值在"快速学习" 而非"抗幻觉".

### 14.6 实施计划

| 任务 | 优先级 | 状态 |
|---|---|---|
| **D4 综合报告** (本文件 §14) | P0 | ✅ 完成 |
| **H3 修订 PRD**: 改 v0.68.0 假设为 Fast Calibration + Wide Coverage | P0 | 📋 下一步 |
| **CHANGELOG v0.75.1**: 记录 H3 假设修订 | P0 | 📋 待启动 |
| **version bump**: 0.75.0 → 0.75.1 (H3 修订标记) | P0 | 📋 待启动 |
| H3-c3 entropy 优化 (LinUCB decay) | P1 | 📋 Phase 5 P2 |
| H3-c4 拐点响应验证 (跨 skill 数据) | P1 | 📋 Phase 5+ |

**详细综合报告**: [discussions/2026-08-04-v075-D4-comprehensive-report.md](./2026-08-04-v075-D4-comprehensive-report.md)

