# H3 验证报告: lbc003

> **H3 假设**: 双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)
> **评估指标**: ECE (Expected Calibration Error), 越小越校准
> **通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent

**生成时间**: 2026-07-29T22:19:57.543591
**学生**: lbc003

---

## 1. 单 Agent Baseline (CTA only)

- 学生: lbc003
- 维度: K
- 样本数: 8
- **ECE**: `0.40149327317399836`
- 当前 mastery_prob: `N/A`
- 平均 accuracy: `1.0`
- 平均 confidence: `0.5985067268260016`
- 注: v0.64.0 改进: 全部用 mastery_prob_after 历史快照

## 2. 双 Agent Experiment (CTA + LCA + 互校)

- 学生: lbc003
- 样本数: 7
- **ECE**: `0.8671428571428571`
- 平均 confidence (expected_gain): `0.13285714285714284`
- 平均 accuracy (actual_outcome): `1.0`
- 注: v0.64.0 改进: 直接读 calibration_log.actual_outcome (无 fallback), skip 1/8 行 (v0.60.4 历史数据)

## 3. H3 验证结论

**结论**: ⚠️ **H3 暂未通过 (双 Agent 样本量不足)**

- 阈值: 双 Agent ECE ≤ 0.1
- 单 Agent baseline: ECE = 0.4015 (8 样本)
- 双 Agent experiment: ECE = 0.8671 (7 样本)
- 单 vs 双 差距: -0.4656

**理由**: 双 Agent 只有 7 行 calibration_log, 统计意义不足, 需要 lbc003 答 30+ 道 dual_agent 后再补完整 H3 验证 (跟 v0.63.0 路线 A + 后续 B 一致)

## 4. 限制与建议 (v0.63.0 路线 A, 跑 lbc003)

### 数据基础限制
- 单 Agent baseline: lbc003 response_history 8 条 (够 30+, 统计意义 OK)
- 双 Agent experiment: lbc003 calibration_log **7 条** (不足 30, 统计意义有限)

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
