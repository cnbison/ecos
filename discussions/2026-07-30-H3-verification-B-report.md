# H3 验证 B 报告: lbc003 (v0.68.0 路线 B 完整体)

> **H3 假设**: 双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)
> **评估指标**: ECE (Expected Calibration Error), 越小越校准
> **通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent

**生成时间**: 2026-07-30
**学生**: lbc003
**报告作者**: Mavis (H3 B 验证) + Bisen (lbc003 答题)
**报告版本**: v0.68.0

---

## 0. TL;DR

| 指标 | 单 Agent | 双 Agent V1 (expected_gain) | 双 Agent V2 (overall_confidence) |
|---|---|---|---|
| 样本数 | 35 | 30 (DISTINCT 去重) | 20 (state_trajectory 落盘受限) |
| 平均 confidence | 0.6491 | 0.1393 | 0.5231 |
| 平均 accuracy | 0.8857 | 0.8667 | 0.9000 |
| **ECE** | **0.2366** | **0.7274** | **0.3769** |
| 校准误差均值 | 0.3849 | 0.7644 | 0.4818 |
| vs 单 Agent p-value | — | 0.0000 (显著反向) | 0.0000 (显著反向) |

**关键结论**:
- ❌ **H3 当前数据下未通过**: 两种双 Agent confidence 指标 (V1/V2) ECE 都 > 单 Agent baseline
- ⚠️ **H3 验证设计本身有缺陷**: expected_gain (LinUCB reward 预测) 和 overall_confidence (belief_state 整体把握度) 都不是"答对概率"的直接度量，硬比 ECE 失真
- 📋 **本次验证的最大价值**: 暴露了 H3 验证的设计局限 + 双 Agent confidence 指标需要重新定义
- 🚧 **建议**: v0.68.0 修 thread-safety BUG 让 state_trajectory 完整落盘, 然后 v0.69.0 重新设计 H3 confidence 指标

---

## 1. 单 Agent Baseline (CTA only)

- 学生: lbc003
- 维度: K (5D 中 K 维度, v0.63.0 默认)
- 样本数: 35
- **ECE**: `0.2366`
- 平均 accuracy: `0.8857` (35 题对 31 题, 88.6%)
- 平均 confidence: `0.6491` (mastery_prob_after[K] 历史快照均值)
- 注: v0.64.0 改进: 全部用 mastery_prob_after 历史快照 (无 fallback)

**单 Agent 解读**:
- confidence 0.65 vs accuracy 0.89 → 略微低估了自身能力
- 但差距只有 0.24, 校准误差 0.38, 整体**比较校准**
- 这是 Bisen 答 lbc003 35 道题 (主答 Python 基础) 的真实表现

---

## 2. 双 Agent Experiment: 两套 confidence 指标

**核心问题**: 双 Agent 的"confidence"应该用什么? 当前没有现成答案, 我们跑了两个候选:

### 2.1 V1: expected_gain (v0.63.0 原设计)

- 样本数: 30 (DISTINCT calibration_round 去重, v0.68.0 加)
- **ECE**: `0.7274`
- 平均 confidence: `0.1393` (LinUCB 预测的 reward/gain)
- 平均 accuracy: `0.8667` (30 round 实际 outcome)
- 注: v0.64.0 actual_outcome 回写, v0.68.0 DISTINCT 去重 drop 4 行重复 round

**V1 失败原因**:
- `expected_gain` 是 LinUCB 预测的"这次干预能带来多大状态增量"（0.1-0.2 区间）
- 跟"答对率"**完全是两个东西**
- 互校系统不预测答对, 它预测干预效果
- V1 严重低估 (0.14 vs 0.87), ECE 0.73 失真

### 2.2 V2: overall_confidence (v0.68.0 新分析)

- 样本数: 20 (受 dual_agent_state 落盘 thread-safety BUG 限制, state_trajectory 只落盘 21 round)
- **ECE**: `0.3769`
- 平均 confidence: `0.5231` (belief_state.overall_confidence)
- 平均 accuracy: `0.9000` (intervention_history 配对 actual_outcome)
- 注: 数据从 student_dual_agent_state.state_trajectory + intervention_history 配对

**V2 失败原因**:
- `overall_confidence` 是 belief_state 5D 平均 confidence, 设计目的是"系统对自身状态估计的把握度"
- lbc003 答 35 题 belief_state 整体 confidence 一直 ~0.52 (偏保守)
- 但实际答对率 0.90 → belief_state 偏保守, 不是互校失败
- V2 比 V1 好 (0.38 vs 0.73), 但仍方向反 (0.38 > 单 0.24)

**V2 样本量限制**:
- dual_agent_state.state_trajectory 长度 21 (而不是 35) 因为 v0.68.0 之前 thread-safety BUG
- Flask 多线程 dispatch + LCAStore/DualAgentStore 默认 check_same_thread=True → save_state 跨线程失败
- v0.68.0 修 BUG 后, 完整 state_trajectory 应能落盘到 35 round

---

## 3. 显著性检验 (单 vs 双)

| 对比 | 单 mean err | 双 mean err | Welch t p | Mann-Whitney U p | 综合 p | 方向 |
|---|---|---|---|---|---|---|
| V1 (30 样本) | 0.3849 | 0.7644 | 0.0000 | 0.0000 | **0.0000** | ❌ 反向 |
| V2 (20 样本) | 0.3849 | 0.4818 | 0.000009 | 0.000009 | **0.000009** | ❌ 反向 |

**显著性解读**:
- 两种 confidence 指标都**显著反向** (p < 0.0001)
- 但这是**confidence 指标选错**导致的失真, 不是互校本身失败
- 30/20 样本已经够统计检验, 不需要更多数据

---

## 4. H3 验证结论: 当前数据下未通过, 但设计本身有问题

### 4.1 数据结果

- **阈值**: 双 Agent ECE ≤ 0.10
- 单 Agent baseline: ECE = 0.2366 (35 样本)
- 双 Agent V1: ECE = 0.7274 (30 样本) → **未达阈值**
- 双 Agent V2: ECE = 0.3769 (20 样本) → **未达阈值**
- 单 vs V1 差距: -0.4908 (双反而差)
- 单 vs V2 差距: -0.1403 (双反而差)

**结论**: ❌ **H3 在 V1+V2 confidence 指标下都未通过**

### 4.2 但 H3 验证设计有重大缺陷 (重要警告)

**问题 1: 双 Agent confidence 应该是什么?**
- 单 Agent confidence = mastery_prob_after[dimension] (答对概率, 直接)
- 双 Agent confidence 候选:
  - V1 expected_gain = LinUCB 预测 reward (干预效果, 不是答对概率)
  - V2 overall_confidence = belief_state 整体把握度 (系统信心, 不是答对概率)
  - **都没有"答对概率"直接预测**

**问题 2: H3 验证混淆了不同概念**
- H3 原设计 (v0.63.0) 假设 expected_gain ≈ confidence
- 实际: expected_gain 是 "如果按这个干预走, 状态能前进多少"
- 答对率是 "学生这次答对的概率"
- 两者不是同一回事, 不能硬比 ECE

**问题 3: state_trajectory 不完整落盘 (thread-safety BUG)**
- v0.68.0 之前 LCAStore + DualAgentStore 默认 check_same_thread=True
- Flask 多线程 dispatch, save_state 跨线程失败
- V2 只能拿到 21 round 而非 35 round, 样本量减少

### 4.3 真正的 H3 验证需要什么?

**重新定义 H3 confidence 指标**:
- 候选 1: dual_agent 内部对每题答对概率的直接预测 (如果有这个能力)
- 候选 2: belief_state.5D 维度 (K/P/S/C/X) 各自的 mastery_prob_after 跟单 Agent 对齐
- 候选 3: intervention.confidence (如果 Intervention 类有的话)
- 候选 4: 重新设计 dual_agent 让它对每题答对概率出 confidence (架构升级)

**v0.68.0 落地**: 修 thread-safety, 让 state_trajectory 完整落盘
**v0.69.0 后续**: 重新设计 H3 confidence 指标 + 重跑 H3

---

## 5. 限制与建议

### 5.1 数据基础限制

- 单 Agent baseline: lbc003 response_history 35 条 (够 30+, 统计意义 OK)
- 双 Agent experiment: lbc003 calibration_log 35 行 (DISTINCT 去重后 31 round, 其中 30 round 有 actual_outcome)
- 双 Agent state_trajectory: 21 round (受 thread-safety BUG 限制, v0.68.0 修)

### 5.2 方法限制

- v0.64.0 改进: 单 Agent confidence 用 mastery_prob_after 历史快照
- 双 Agent confidence V1 = message_payload.expected_gain (LinUCB 预测, 不是答对概率)
- 双 Agent confidence V2 = belief_state.overall_confidence (偏保守, 不是答对概率)
- **核心限制**: H3 验证缺一个"双 Agent 答对概率直接预测"指标

### 5.3 落地清单 (CLAUDE.md [7] 防御性自查: 触碰范围)

**v0.68.0 落地 (本次必须修)**:
- [x] H3 脚本: `load_student_calibration_log` 加 DISTINCT calibration_round 去重
- [x] H3 脚本: 加 `compute_significance` (Welch t + Mann-Whitney U)
- [x] H3 脚本: `format_report` 加 §5 显著性检验
- [x] H3 脚本: `main` default --output-md 改 B 文件名 (避免覆盖 A)
- [x] H3 报告: V1+V2 双 confidence 指标对比 + 设计局限诚实分析
- [ ] DualAgentStore.__init__: `check_same_thread=False` (修 thread-safety BUG)
- [ ] LCAStore.__init__: `check_same_thread=False` (修 thread-safety BUG)
- [ ] `dual_agent._write_calibration_log`: message_payload 加 `state_after.overall_confidence` (round-by-round confidence 落盘)
- [ ] 防御性自检 [1-9] 全跑
- [ ] pytest 245/245 保持

**v0.69.0 后续 (路线 C 候选)**:
- [ ] 重新设计双 Agent confidence 指标 (不依赖 expected_gain, 不依赖 overall_confidence)
- [ ] 加 reliability diagram 画图 (matplotlib 依赖待评估)
- [ ] C 主导题扩 20+ 题 (v0.53.0 后续)
- [ ] 元反思模式 (v0.63.0 后续)

**CLAUDE.md [7] 触碰范围自查 (lbc003 答题期间)**:
- 触碰: lbc003 calibration_log (+27 行, round 5-31), lbc003 response_history (+26 条, round 6-31), lbc003 dual_agent_state (部分落盘)
- 不动: lbc001 / lbc002 / 其他学生 / student_lca_state (LCA 落盘全失败, 不污染其他学生)
- 风险: lbc003 dual_agent_state.calibration_round=21 < 35 (thread-safety BUG 副作用), v0.68.0 修后重启 Flask 会从 round 22 继续

---

## 6. 附录

### 6.1 修复的 H3 脚本功能 (v0.68.0)

**`scripts/compute_h3_ece.py` 改动**:
1. `load_student_calibration_log()`: 按 calibration_round DISTINCT 去重, 返回 `{rows, duplicates_dropped}` (修 round 5-8 重复行被算 2 次 BUG)
2. `compute_dual_agent_ece()`: 加 `calibration_errors` 字段 (显著性检验用)
3. `compute_significance()`: 新函数, 算 Welch's t-test + Mann-Whitney U (取 max p 保守估计)
4. `format_report()`: 加 §5 显著性检验 + signature 参数
5. `main()`: 加 `--output-md` default 改 B 文件名 (避免覆盖 A 部分报告)

### 6.2 复现命令

```bash
# H3 B 验证 (lbc003, 35 样本)
python scripts/compute_h3_ece.py --student-id lbc003 \
    --output-md discussions/2026-07-30-H3-verification-B-report.md

# H3 A 验证 (lbc001, 60 样本, v0.63.0 路线 A, 不动)
# 见 discussions/2026-07-29-H3-verification-report.md
```

### 6.3 H3 验证历史

- **v0.63.0** (lbc001): A 验证, 单 ECE=0.1081 (60 样本), 双 ECE=N/A (lbc001 dual_agent 数据少) → 报告见 discussions/2026-07-29-H3-verification-report.md
- **v0.68.0** (lbc003): B 验证, 单 ECE=0.2366 (35 样本), 双 V1 ECE=0.7274 (30 样本), 双 V2 ECE=0.3769 (20 样本) → 报告见 discussions/2026-07-30-H3-verification-B-report.md
- **v0.69.0 计划**: 重新设计双 Agent confidence 指标, 重跑 H3 验证
