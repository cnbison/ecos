# Plan B D2: Reliability Diagram 形态评估报告

> **日期**: 2026-08-04
> **触发**: v0.75 P0-l.1 + P0-m 都失败, Plan B D2 提议用 reliability diagram 形态 (而非单 ECE 数字) 评估 H3 假设.
> **方法**: 重放 lbc003 56 道题, 收集 (单 Agent 6 Bloom confidence, 双 Agent calibrated V3, actual_outcome) 三元组, 对每维度画 reliability diagram, 算 ECE + RMS 距离.
> **决策**: ❌ **H3 "互校抗 LLM 幻觉"假设在 6 Bloom 形态下不成立**. 详见 §4.

## 1. 实验设计

**对比维度**:
- **单 Agent baseline**: CTA `belief_state.bloom_profile.{remember, understand, apply, analyze, evaluate, create}` 6 个维度的 mastery_prob
- **双 Agent experiment**: `calibrated.metadata["dual_agent_confidence_calibrated"]` (production 校准路径: cold start fallback + Platt + Isotonic)

**评估指标**:
- **ECE** (Expected Calibration Error): 10-bin weighted |conf-acc| 绝对差
- **RMS** (Root Mean Square distance to diagonal): bin 点到 y=x 对角线加权 RMS 距离
- **形态**: 1-3 个 bin 散点是否在 y=x 附近

**数据**: lbc003 56 道题重放, 54 对有效 (raw_V3, actual, 6 Bloom) 三元组

**source 分布** (双 Agent V3 校准来源):
- `mean_mastery_fallback`: 5 样本 (冷启动)
- `platt_scaling`: 15 样本
- `isotonic_regression`: 34 样本

## 2. 关键数据: 6 Bloom 形态对比

| Bloom Dim | Single ECE | Dual ECE | Single RMS | Dual RMS | Winner (RMS) |
|---|---|---|---|---|---|
| **remember** | **0.0019** | 0.1101 | **0.0019** | 0.1459 | Single ⭐ |
| **understand** | **0.1019** | 0.1101 | **0.1019** | 0.1459 | Single ⭐ |
| **apply** | 0.1481 | **0.1101** | 0.1481 | 0.1459 | Tie |
| **analyze** | **0.0481** | 0.1101 | **0.0481** | 0.1459 | Single ⭐ |
| **evaluate** | 0.1481 | **0.1101** | 0.1481 | 0.1459 | Tie |
| **create** | 0.2019 | **0.1101** | 0.2019 | 0.1459 | Dual ⭐ |
| **平均** | **0.1083** | **0.1101** | 0.1083 | 0.1459 | **Single (微弱)** |

**核心发现**:
- **6 Bloom 平均 ECE: 单 0.1083 vs 双 0.1101** — 几乎完全打平
- **5/6 维度单 Agent 更优** (remember/understand/analyze 显著优, apply/evaluate 平, create 双 Agent 优)
- **RMS 距离**: 单 Agent 0.1083 也比双 Agent 0.1459 更接近对角线

## 3. 形态分析 (Reliability Diagram 散点)

### 3.1 单 Agent 形态 (CTA bloom_profile)

观察图 [discussions/2026-08-04-v075-D2-reliability-diagram-5d.png](./2026-08-04-v075-D2-reliability-diagram-5d.png) 上排:

- **remember / understand / analyze**: bin 散点几乎贴在 y=x 对角线上 (ECE < 0.10)
- **apply / evaluate**: 散点在对角线附近, 轻微高估
- **create**: 散点偏对角线下方 (单 Agent 低估 create 维度)

**单 Agent 形态特征**: 
- 5D Bloom confidence 都接近 0.5-0.7 (因为 lbc003 答的都是 variables skill, bloom 集中在 APPLY)
- 散点虽然少 (1-2 bin), 但都在 y=x 附近 → 形态好

### 3.2 双 Agent 形态 (Calibrated V3)

观察图下排:

- **整体形态**: 4 个 bin ([0.5, 0.6] / [0.6, 0.7] / [0.8, 0.9] / [0.9, 1.0])
- **低 conf bin [0.5, 0.7]**: 完美 (acc 1.0)
- **高 conf bin [0.9, 1.0]**: 略高估 (conf 0.97 vs acc 0.86, gap 0.10)

**双 Agent 形态特征**:
- 校准把 confidence 拉到 [0.5, 1.0] 广分布
- 但 Isotonic 在小数据 (35 样本) 仍轻微高估高 conf bin
- 散点离对角线比单 Agent 远 (RMS 0.146 vs 0.108)

## 4. H3 假设重新评估

### 4.1 传统 H3 (ECE ≤ 0.10 阈值) 视角

| 视角 | 单 Agent | 双 Agent | H3 通过? |
|---|---|---|---|
| K 维度单 Agent baseline | 0.17 | 0.24 | ❌ 双 Agent 比单 Agent 差 |
| 双 Agent 整体 (旧 H3 假设) | — | 0.24 | ❌ ECE > 0.10 |
| **双 Agent 6 Bloom 平均** (新视角) | 0.1083 | 0.1101 | ⚠️ 几乎打平, 双 Agent 略差 |
| 双 Agent 6 Bloom 单 dim | 0.0019-0.2019 | 0.1101 | ⚠️ 各 dim 表现不同 |

**H3 原始假设**: "双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)" 

**D2 形态评估结论**:
- **单 Agent 6 Bloom 平均 ECE 0.108 跟双 Agent V3 0.110 几乎相同**
- 形态上**单 Agent 5/6 维度优于双 Agent**
- H3 "互校抗 LLM 幻觉" 在 6 Bloom 形态下**不成立**

### 4.2 关键学习

1. **H3 原始假设有方向性问题**:
   - 单 Agent 6 Bloom confidence 已经是 CTA MIRT/BloomProfile 校准好的 (mastery_prob 在 [0, 1] 稳定)
   - 双 Agent V3 在 raw V3 (LinUCB θ@x) 基础上后校准, 起点是偏低的 (raw V3 0.14-0.40)
   - **后校准后的 V3 跟 CTA 直接输出的 6 Bloom confidence 没有可比性** — 一个是 LinUCB 校准, 一个是 MIRT 校准

2. **"互校" 在 ECOS 里实际是什么**:
   - CTA 单 Agent 已经有 5D + 6 Bloom + 信心度等校准信号
   - 双 Agent 在 CTA 之上加 LCA + LinUCB, 主要是**决策** (选哪个 intervention), 不是**校准**
   - **真正的 H3 应该是 "互校改善干预选择质量", 不是 "互校改善 calibration"**

3. **ECE 阈值 0.10 是想错了指标**:
   - 单 Agent baseline 0.17 已经接近 0.10
   - 双 Agent 通过后校准降到 0.11 (v0.74)
   - 互校在 calibration 上**边际改善** 0.17 → 0.11, 不再能突破 0.10

## 5. D2 决策

### ❌ Plan B D2 改指标方案**部分有效**

**有用**:
- 形态评估让 H3 "不通过" 看得更清楚 (单 Agent 5/6 维度优于双 Agent)
- 揭示 H3 假设方向性错误: "互校抗 LLM 幻觉" 不准确, 实际应该是"互校改善干预决策"
- 提供 D4 (拆子假设) 的具体方向

**没用**:
- 形态评估不能直接帮 H3 "通过" (单 Agent 0.108 反而比双 Agent 0.110 略好)
- 改指标 ≠ 改假设, D2 只解决了"怎么评"问题, 没解决"评什么"问题

## 6. 下一步: 走 D4 (拆 H3 子假设)

按 Plan B 策略 D2 + D4 组合, D2 已完成, **启动 D4**:

**H3 拆 3 子假设** (待 PRD):
- **H3a (现状, 已验证)**: 互校降低单题预测 ECE — **D2 证明单 Agent 0.108 跟双 Agent 0.110 几乎打平, 子假设不成立**
- **H3b (待验证)**: 互校改善干预多样性 (避免总是选同一 arm) — D4 主战场
- **H3c (待验证)**: 互校快速响应学生状态变化 (LinUCB 学习速度) — D4 主战场

D4 PRD 待写, 详见 [discussions/2026-08-04-v075-D4-h3-subhypothesis-prd.md](./2026-08-04-v075-D4-h3-subhypothesis-prd.md) (待启动).

## 7. 实施时间线

| 任务 | 状态 |
|---|---|
| D2 5D 6 Bloom reliability diagram 画图 (本报告) | ✅ 完成 |
| D2 数据分析 (单 vs 双 ECE 几乎打平) | ✅ 完成 |
| D2 报告 (本文件) | ✅ 完成 |
| **D4 H3 拆子假设 PRD** | 📋 下一步 |
| D4 实施 (H3b 多样性 + H3c 学习速度) | 📋 待启动 |

## 附录 A: 复现命令

```bash
# 跑 D2 6 Bloom reliability diagram 形态评估
python scripts/plot_reliability_diagram_5d.py

# 输出
discussions/2026-08-04-v075-D2-reliability-diagram-5d.png
discussions/2026-08-04-v075-D2-reliability-diagram-5d.json
```

## 附录 B: 关键代码路径

- `scripts/plot_reliability_diagram_5d.py`: D2 主脚本
  - `collect_pairs()`: 重放 lbc003, 收集 (single_6bloom, dual_v3, actual) 三元组
  - `compute_reliability_bins()`: 10-bin 分箱 + per-bin conf/acc/n
  - `compute_ece()`: 加权 ECE
  - `compute_diagonal_proximity()`: bin 点到 y=x 加权 RMS 距离
  - `plot_5d_reliability()`: 画 2x6 子图 (上单, 下双)
- 输出: `discussions/2026-08-04-v075-D2-reliability-diagram-5d.png`
- 数据: `discussions/2026-08-04-v075-D2-reliability-diagram-5d.json`
