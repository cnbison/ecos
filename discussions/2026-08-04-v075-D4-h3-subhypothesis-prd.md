# Plan B D4: H3 拆 3 子假设 PRD

> **日期**: 2026-08-04
> **触发**: Plan B D2 形态评估显示, H3 原始假设 "互校抗 LLM 幻觉" 在 6 Bloom 维度下不成立 (单 Agent 0.108 ≈ 双 Agent 0.110). 需要拆 H3 为可独立验证的子假设.
> **目标**: 把 H3 拆成 H3a (ECE, 已部分失败) / H3b (干预多样性, 待验证) / H3c (LinUCB 学习速度, 待验证), 各自跑评估, 决定哪些子假设成立.
> **决策**: 见 §6.

## 1. 背景

### 1.1 H3 原始假设 (v0.68.0 PRD)
> "双 Agent 互校有效减少 LLM 幻觉 (双 Agent vs 单 Agent 信念校准度)"
> **评估指标**: ECE (Expected Calibration Error), 越小越校准
> **通过阈值**: 双 Agent ECE ≤ 0.10 + 显著优于单 Agent

### 1.2 历史 H3 状态 (累计 v0.69-v0.75)
- v0.69.0: V3 设计 (B4+C1+D1 方案)
- v0.70.0-d: 修策略质疑路径绕过
- v0.71.0: 修 A 矩阵爆炸
- v0.72.0: Platt Scaling (ECE 0.76 → 0.28)
- v0.73.0: Isotonic (ECE 持平)
- v0.74.0: 冷启动 fallback (ECE 0.28 → 0.24)
- v0.75.0 P0-l.1: Global Platt 冷启动 -37.5% / 全局 -0.007 (边际)
- v0.75.0 P0-m: LinUCB difficulty 反向恶化 0.011

**H3 状态**: 双 Agent ECE 0.24 vs 单 Agent baseline 0.17, **互校反而比单 Agent 差**.

### 1.3 D2 关键发现
6 Bloom 形态评估 (本会话):
- 单 Agent 6 Bloom 平均 ECE 0.108
- 双 Agent V3 ECE 0.110
- 5/6 个 Bloom 维度单 Agent 优于双 Agent
- **H3 "互校改善 calibration" 在 6 Bloom 视角下不成立**

## 2. H3 拆 3 子假设

### H3a: 互校降低单题预测 ECE
**原假设**: 双 Agent V3 校准后 ECE 显著低于单 Agent 5D/6 Bloom baseline.

**当前状态** (D2 验证):
- 6 Bloom 视角: 单 Agent 0.108 vs 双 Agent 0.110, **打平**
- 5D K 维度视角: 单 Agent 0.17 vs 双 Agent 0.11, **双 Agent 优**
- 整体 H3a: **不通过** (互校在 calibration 维度无显著优势)

**重新定义** (D4 修订):
- 单维度评估 ≠ 整体校准
- H3a 应该改为: "**互校显著优于单 Agent 在某些特定维度** (e.g. 5D K 维度), 但不是所有维度"
- 验证方法: 跑 5D + 6 Bloom 各自的 single vs dual 配对 t 检验, 看哪些维度有显著优势

### H3b: 互校改善干预多样性
**假设**: 互校下 LCA 选出的 intervention 比纯 CTA heuristic 更**多样** (避免总是选同一 arm), 从而探索更广的策略空间.

**评估指标**:
1. **Arm 分布熵 (Entropy)**: Shannon entropy of arm selection distribution (10 个 arm 各选比例)
2. **Arm 重复间隔**: 同 arm 连续选中的平均间隔 (越大越多样)
3. **覆盖度**: 答 N 道题后, 至少被选过 1 次的 arm 数 (接近 n_arms 越好)

**通过阈值**:
- 双 Agent arm entropy > 单 Agent entropy
- 双 Agent 同 arm 重复间隔 > 单 Agent
- 双 Agent arm 覆盖度 > 单 Agent

**实施**:
- `scripts/v075_d4_arm_diversity.py`: 重放 lbc003, 提取 (单 Agent 决策, 双 Agent LCA 选 arm) 序列
- 单 Agent: 用 CTA heuristic 选 arm (e.g. 5D 最低维度对应的干预类型)
- 双 Agent: 用 `LCAPolicyLearner.select_intervention` 选 arm
- 算 entropy + 重复间隔 + 覆盖度

**预期**:
- 双 Agent LinUCB 探索机制应该比 CTA heuristic 更"系统化多样"
- 阈值: 暂定 entropy > 1.5 (10 arm max entropy = log2(10) ≈ 3.32), 覆盖度 > 7/10

### H3c: 互校快速响应学生状态变化
**假设**: 互校 (LinUCB 在线学习) 比单 Agent (固定 heuristic) **更快响应**学生 5D 状态变化, 调整 intervention 选择.

**评估指标**:
1. **状态变化检测延迟**: 学生 5D 出现拐点 (e.g. K 从 0.6 跌到 0.4) 后, 多少题内 intervention 切换?
2. **reward-trajectory 相关性**: LinUCB reward (actual_outcome) 跟 belief_state 变化的相关性
3. **收敛速度**: LinUCB 预测 ECE 从 cold start 到稳定的题数 (越少越快响应)

**通过阈值**:
- 双 Agent 检测延迟 < 单 Agent (例如 < 3 题)
- 双 Agent reward-trajectory 相关性 > 单 Agent
- 双 Agent 收敛速度 < 单 Agent (e.g. < 30 题到 ECE 0.15 以下)

**实施**:
- `scripts/v075_d4_state_response.py`: 重放 lbc003, 找 5D 拐点, 算 detection delay
- 单 Agent: CTA heuristic 不会响应 (固定策略)
- 双 Agent: LinUCB reward 信号触发 A 矩阵更新 → 后续 UCB 选择变化

**预期**:
- 双 Agent 收敛速度 < 30 题
- 单 Agent 没有"响应"概念, 双 Agent 必胜

## 3. 通过/不通过决策

| 子假设 | 验证方法 | 通过阈值 | 状态 |
|---|---|---|---|
| H3a (ECE) | 5D + 6 Bloom 配对 t 检验 | 双 Agent ECE < 单 Agent + p<0.05 | ❌ D2 已证明不通过 |
| H3b (多样性) | entropy + 重复间隔 + 覆盖度 | entropy > 1.5, 覆盖 > 7/10 | 📋 待跑 |
| H3c (学习速度) | 检测延迟 + 收敛速度 | 检测延迟 < 3 题, 收敛 < 30 题 | 📋 待跑 |

**整体 H3 决策**:
- H3a 失败 + H3b 通过 + H3c 通过 → "互校价值在干预多样性 + 学习速度, 不在 calibration"
- H3a 失败 + H3b 失败 + H3c 失败 → "互校整体无显著优势, 走 P2 State Engine 重设计"
- 任意子假设失败 → 报告 + 文档化根因, 避免未来重蹈覆辙

## 4. 实施时间线

| 任务 | 时间估计 | 状态 |
|---|---|---|
| D4 PRD (本文件) | 30 min | ✅ 完成 |
| D4 H3b 实施: 干预多样性评估 | 半天 | 📋 待启动 |
| D4 H3b 跑 lbc003 | 1h | 📋 待启动 |
| D4 H3c 实施: 状态响应速度评估 | 半天 | 📋 待启动 |
| D4 H3c 跑 lbc003 | 1h | 📋 待启动 |
| D4 报告 (合并 H3b + H3c) | 1h | 📋 待启动 |
| H3 整体决策 + 文档化 | 1h | 📋 待启动 |

## 5. 不在 D4 范围

- **D1 (改阈值)**: 已被 D2 + D3 证明是逃避, 不做
- **D3 (改假设)**: 在 D4 完成后, 视子假设结果决定是否需要改
- **Plan A (重做架构)**: 仅在 H3b + H3c 都失败时启动

## 6. 决策建议

**Bisen 拍板**: 启动 D4 实施 H3b + H3c 吗? 还是先看 H3a 失败根因, 决定是否调整方向?

**我的建议**: 直接启动 D4, 原因:
1. D2 已明确 H3a 不通过, 无需再花时间
2. H3b + H3c 是真正可验证的子假设, 1-2 天可出结果
3. 即使 H3b + H3c 也失败, 也比"卡在 ECE 0.10"有方向感

**风险**:
- H3b + H3c 都失败的话, 整个 ECOS 互校架构需要重新评估
- 但这是真实信号, 早暴露比晚暴露好

## 附录 A: 复现命令

```bash
# D2 (已完成)
python scripts/plot_reliability_diagram_5d.py

# D4 H3b (待实施)
python scripts/v075_d4_arm_diversity.py

# D4 H3c (待实施)
python scripts/v075_d4_state_response.py
```

## 附录 B: 关键代码路径

- `scripts/plot_reliability_diagram_5d.py`: D2 主脚本 (已实施)
- `scripts/v075_d4_arm_diversity.py`: D4 H3b 主脚本 (待实施)
- `scripts/v075_d4_state_response.py`: D4 H3c 主脚本 (待实施)
- `discussions/2026-08-04-v075-D2-reliability-diagram-5d.md`: D2 报告
- `discussions/2026-08-04-v075-D2-reliability-diagram-5d.png`: D2 形态图
- `discussions/2026-08-04-v075-D2-reliability-diagram-5d.json`: D2 数据
- `discussions/2026-08-04-v075-D4-h3-subhypothesis-prd.md`: D4 PRD (本文件)
