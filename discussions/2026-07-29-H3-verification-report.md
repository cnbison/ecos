# H3 验证报告: lbc001

> **H3 假设**: 双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)
> **评估指标**: ECE (Expected Calibration Error), 越小越校准
> **通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent

**生成时间**: 2026-07-29T15:25:39.674401
**学生**: lbc001

---

## 1. 单 Agent Baseline (CTA only)

- 学生: lbc001
- 维度: K
- 样本数: 60
- **ECE**: `0.10813310240307028`
- 当前 mastery_prob: `0.6585335642635962`
- 平均 accuracy: `0.7666666666666667`
- 平均 confidence: `0.6585335642635964`
- 注: v0.63.0 简化: 用当前 mastery_prob 当所有问题的 confidence (实际应该是历史快照序列, 未来改进)

## 2. 双 Agent Experiment (CTA + LCA + 互校)

- 学生: lbc001
- 样本数: 5
- **ECE**: `0.48`
- 平均 confidence (expected_gain): `0.12`
- 平均 accuracy (actual_outcome): `0.6`
- 注: v0.63.0 改进: 5/5 行 actual_outcome 用 response_history.correct 兜底回填 (DB 写库 BUG 待修)

## 3. H3 验证结论

**结论**: ⚠️ **H3 暂未通过 (双 Agent 样本量不足)**

- 阈值: 双 Agent ECE ≤ 0.1
- 单 Agent baseline: ECE = 0.1081 (60 样本)
- 双 Agent experiment: ECE = 0.4800 (5 样本)
- 单 vs 双 差距: -0.3719

**理由**: 双 Agent 只有 5 行 calibration_log, 统计意义不足, 需要 lbc001 答 30+ 道 dual_agent 后再补完整 H3 验证 (跟 v0.63.0 路线 A + 后续 B 一致)

## 4. 限制与建议 (v0.63.0)

### 数据基础限制
- 单 Agent baseline: lbc001 response_history 60 条 (够 30+, 统计意义 OK)
- 双 Agent experiment: lbc001 calibration_log **5 条** (不足 30, 统计意义有限)

### 方法限制
- 单 Agent confidence 用当前 mastery_prob 简化 (实际应该是历史快照序列)
- 双 Agent confidence 用 message_payload.expected_gain (互校预测 gain, 不是直接的 confidence)
- 没做 p-value 显著性检验 (样本量不足, 跑也不显著)

### 后续 (v0.63.0+ 路线 B)
1. lbc001 答 30+ 道题 (feature flag on, ECOS_DUAL_AGENT_ENABLED=1)
2. 收集 calibration_log 30+ 行
3. 跑本脚本重算 H3 (单 vs 双 ECE 对比 + p-value)
4. 写完整 H3 报告 (含显著性检验)

### 改进方向
- 单 Agent confidence 存历史快照 (v0.64.0+ 路线: response_history 加 confidence 字段)
- 双 Agent confidence 改用 CalibratedLCAResult.intervention.confidence (更直接的校准信号)
- 加 reliability diagram 画图 (matplotlib 依赖待评估)
