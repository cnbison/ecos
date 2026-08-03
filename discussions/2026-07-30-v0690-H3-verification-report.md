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

