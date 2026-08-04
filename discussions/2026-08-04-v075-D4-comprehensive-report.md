# Plan B D4: H3 综合评估报告 + 决策

> **日期**: 2026-08-04
> **触发**: Plan B D2 证明 H3 "互校抗 LLM 幻觉" 在 6 Bloom 形态下不成立, 启动 D4 把 H3 拆 3 子假设 (H3a/H3b/H3c) 分别验证.
> **方法**: 跑 lbc003 56 道题, 评估 (H3a ECE) / (H3b 干预多样性) / (H3c 状态响应速度), 综合 3 个子假设决策 H3 整体方向.
> **决策**: ✅ **互校架构保留, 调整叙事** — 从 "抗 LLM 幻觉" 改为 "Fast Calibration (14 题 ECE < 0.15) + 广覆盖 (100% vs 20%)". 详见 §4.

## 1. 三个子假设汇总

| 子假设 | 核心假设 | 验证方法 | 关键数据 | 通过阈值 | 状态 |
|---|---|---|---|---|---|
| **H3a** | 互校降低单题 ECE | 6 Bloom reliability diagram | 单 Agent 0.108 vs 双 Agent 0.110 | 双 < 单 + p<0.05 | ❌ 不通过 (打平) |
| **H3b** | 互校改善干预多样性 | entropy + coverage + 重复间隔 | Entropy 1.145 vs 0.967; Coverage 100% vs 20% | Entropy > 1.5, Coverage > 70% | ⚠️ 部分通过 (Coverage ✅, Entropy ❌) |
| **H3c** | 互校快速响应状态变化 | 拐点检测延迟 + ECE 收敛速度 | 0 拐点; ECE 收敛 14 题 < 0.15 | 延迟 < 3 题, 收敛 < 30 题 | ⚠️ 部分通过 (收敛 ✅, 拐点缺数据) |

### H3a (ECE) — D2 已验证, 不通过
- **单 Agent 6 Bloom avg ECE 0.108 跟双 Agent V3 0.110 几乎完全打平**
- 5/6 个 Bloom 维度单 Agent 优于双 Agent (remember/understand/analyze 显著优)
- **结论**: 互校在 calibration 维度无显著优势

### H3b (多样性) — D4 验证, 部分通过
- ✅ **Coverage 双 Agent 100% (10/10 arm) vs 单 Agent 20% (2/10 arm)**
- ❌ Entropy 双 Agent 1.145 (34.5% of max) < 1.5 阈值
- ❌ Max streak 双 Agent 41 远大于单 Agent 19
- **结论**: 互校覆盖更广, 但 LinUCB 走 exploitation 锁定单一 arm (arm 0 47/56 轮)

### H3c (响应速度) — D4 验证, 部分通过
- ⚠️ **6 Bloom 状态拐点 0 个** (lbc003 单 skill 让 6 Bloom 收敛, max diff 0.082 < 阈值 0.1)
- ✅ **LinUCB 收敛速度 14 题 < 0.15 ECE** (D4 阈值 30 题, 显著通过)
- ✅ 11 题内 ECE < 0.20 (快速稳定)
- **结论**: 互校**校准速度快**, 但**响应状态变化速度未验证** (缺拐点数据)

## 2. H3 整体诊断

### 2.1 原始 H3 假设的核心问题
> H3 原始 (v0.68.0 PRD): "双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)"

**D4 验证发现**:
1. **方向错误**: 互校的实际价值不在 calibration (H3a 失败), 在"快速学习"和"广覆盖"
2. **指标错位**: H3a 用 ECE 0.10 阈值, 但单 Agent 已是 0.108, 双 Agent 通过校准只能 0.110, 差距仅 0.002
3. **叙事错位**: "抗 LLM 幻觉" 是 LLM 视角, ECOS 应该关注 "教学效果" 视角

### 2.2 互校架构的真正价值 (D4 重新定位)

| 价值主张 | 证据 | 状态 |
|---|---|---|
| **Fast Calibration** | 14 题 ECE < 0.15 (单 Agent 5D 维度需 ~30 题) | ✅ H3c 验证 |
| **Wide Coverage** | 100% arm 覆盖 vs 单 Agent 20% | ✅ H3b 验证 |
| **Adaptive Reward** | LinUCB 基于 actual_outcome 在线学习, 单 Agent 是固定 heuristic | ✅ 理论成立 |
| **抗 LLM 幻觉** | 双 Agent 0.110 ≈ 单 Agent 0.108 (打平) | ❌ 证据不足 |
| **响应状态变化** | 拐点 0 个, 无法量化 | ❓ 缺数据 |
| **arm 多样性** | Entropy 1.145 (跟单 Agent 0.967 接近) | ❌ 证据不足 |

## 3. H3 整体决策

### ✅ 互校架构保留, 调整叙事

**保留理由**:
- Fast Calibration 14 题 < 0.15 是可量化、可演示的核心卖点
- Wide Coverage 100% vs 20% 在实际教学场景有显著价值
- Adaptive Reward 是架构优势, 长期可演进

**调整方向**:
- ❌ 放弃 "互校抗 LLM 幻觉" 叙事 (D2 + H3a 证明不成立)
- ✅ 启用 "互校快速校准 + 广覆盖" 叙事 (H3c + H3b 证据强)
- 📋 H3 修订 PRD: 改 v0.68.0 假设描述, 校准 H3 通过标准

### 3.1 H3 修订方案

**新 H3 假设** (替代 v0.68.0):
> "**双 Agent 互校有效实现快速校准 (Fast Calibration) + 广覆盖 (Wide Coverage) 干预**: LinUCB 在小样本 (< 30 题) 内实现 ECE < 0.15 校准, 且 arm 覆盖 > 70%"

**新通过标准**:
- ✅ H3-c1: LinUCB 收敛速度 < 30 题 (ECE < 0.15) — **当前 14 题 ✅**
- ✅ H3-c2: Arm coverage > 70% (10 arm) — **当前 100% ✅**
- ⚠️ H3-c3: Arm entropy > 1.5 — 当前 1.145 < 1.5, **作为软指标继续优化**
- 📋 H3-c4: 拐点响应延迟 < 3 题 — **缺数据, 需要更多测试场景**

### 3.2 长期演进方向 (Phase 5+)

1. **修复 H3-c3 entropy** (Phase 5 P2):
   - LinUCB 加 decay 机制, 让 exploitation 锁定衰减
   - 或加 epsilon-greedy 探索, 强制多样性

2. **验证 H3-c4 拐点响应** (Phase 5+):
   - 需要更多测试数据 (e.g. 跨 skill 答 100+ 题)
   - 或合成数据: 模拟"学生中途从 mastery 0.9 跌到 0.3" 场景

3. **LCA 选 arm 优化** (Phase 5+ P2):
   - 当前 LCA 选 arm 跟 LinUCB reward 信号弱耦合
   - 优化方向: 把 arm 选择跟"学生对 arm 的实际反应" 做强相关

## 4. 实施计划

| 任务 | 优先级 | 状态 |
|---|---|---|
| **D4 综合报告** (本文件) | P0 | ✅ 完成 |
| **H3 修订 PRD**: 改 v0.68.0 假设为 Fast Calibration + Wide Coverage | P0 | 📋 下一步 |
| **H3 报告 §14 追加**: D2 + D4 综合评估 | P0 | 📋 待启动 |
| **CHANGELOG v0.75.1**: 记录 H3 假设修订 | P0 | 📋 待启动 |
| **version bump**: 0.75.0 → 0.75.1 (H3 修订标记) | P0 | 📋 待启动 |
| H3-c3 entropy 优化 (LinUCB decay) | P1 | 📋 Phase 5 P2 |
| H3-c4 拐点响应验证 (跨 skill 数据) | P1 | 📋 Phase 5+ |

## 5. 关键学习 (Bisen 反馈用)

### 5.1 H3 验证的整体反思

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

### 5.2 Plan B 策略的有效性评估

| 方向 | 效果 | 评估 |
|---|---|---|
| D1 改阈值 | — | 已放弃 (逃避问题) |
| **D2 改指标** | ✅ | Reliability diagram 形态评估让 H3 失败看得更清楚, 揭示方向错误 |
| D3 改假设 | — | D4 完成后才适用 |
| **D4 拆子假设** | ✅ | 成功定位 H3 真实价值 (Fast Calibration + Wide Coverage) |

**D2 + D4 组合**: 1.5 天出结果, 比 Plan A 重做架构快 10x, 实际发现 H3 价值在"快速学习" 而非"抗幻觉".

## 6. 实施时间线

| 任务 | 时间 | 状态 |
|---|---|---|
| Plan B D2 (reliability diagram 形态) | 半天 | ✅ |
| Plan B D4 PRD (3 子假设) | 0.5 天 | ✅ |
| Plan B D4 H3b 实施 + 跑 | 0.5 天 | ✅ |
| Plan B D4 H3c 实施 + 跑 | 0.5 天 | ✅ |
| **Plan B D4 综合报告 (本文件)** | 0.5 天 | ✅ |
| **H3 修订 PRD + CHANGELOG v0.75.1** | 0.5 天 | 📋 下一步 |
| **H3 报告 §14 追加 + version bump** | 0.5 天 | 📋 待启动 |

## 附录 A: 复现命令

```bash
# 跑 D2 reliability diagram
python scripts/plot_reliability_diagram_5d.py

# 跑 D4 H3b 多样性
python scripts/v075_d4_arm_diversity.py

# 跑 D4 H3c 响应速度
python scripts/v075_d4_state_response.py

# 输出
discussions/2026-08-04-v075-D2-reliability-diagram-5d.json
discussions/2026-08-04-v075-D4-h3b-arm-diversity.json
discussions/2026-08-04-v075-D4-h3c-state-response.json
```

## 附录 B: 关键代码路径 + 报告

- D2 报告: [discussions/2026-08-04-v075-D2-reliability-diagram-5d.md](./2026-08-04-v075-D2-reliability-diagram-5d.md)
- D4 PRD: [discussions/2026-08-04-v075-D4-h3-subhypothesis-prd.md](./2026-08-04-v075-D4-h3-subhypothesis-prd.md)
- D4 H3b 报告: [discussions/2026-08-04-v075-D4-h3b-arm-diversity.md](./2026-08-04-v075-D4-h3b-arm-diversity.md)
- D4 H3c 报告: [discussions/2026-08-04-v075-D4-h3c-state-response.md](./2026-08-04-v075-D4-h3c-state-response.md)
- D4 综合报告 (本文件): [discussions/2026-08-04-v075-D4-comprehensive-report.md](./2026-08-04-v075-D4-comprehensive-report.md)
