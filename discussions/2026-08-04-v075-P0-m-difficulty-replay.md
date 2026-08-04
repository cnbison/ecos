# v0.75 P0-m: LinUCB Difficulty Feature ECE 评估报告

> **日期**: 2026-08-04
> **触发**: v0.75 P0-l.1 (Global Platt) 离线分析显示全局 ECE 只改善 0.007, 真正瓶颈是 Platt/Isotonic 阶段 bin [0.9, 1.0] gap +0.10 (49/54 样本, 90.7% 权重). 按 P0-l.1 报告 §6 选项 C, 启用 LinUCB difficulty feature (16→17 维 context) 看能否改善高 conf bin.
> **方法**: 重放 lbc003, 对比 use_arm_features=False (v0.74 行为) vs True (v0.75 P0-m), 跑 production 校准 (cold start fallback + Platt + Isotonic), 算 calibrated V3 全局 ECE + 分段.
> **决策**: ❌ P0-m **无效**, calibrated ECE 反向恶化. 见 §6.

## 1. 实验设计

**改动**:
- `BanditConfig.use_arm_features: bool = False` (默认, 向后兼容)
- `LinUCB.score_arm(arm, context)` 新方法 (P0-m 加)
- `LCAPolicyLearner._build_context(state, intervention=None)`: 启用 arm features 时追加 1 维 `intervention.difficulty` → 17 维
- `LCAPolicyLearner.select_intervention`: 启用 arm features 时, 每个候选独立 17 维 context 评估, 选 UCB 最高的
- `LCAPolicyLearner.update`: 重建跟 select 时一致的 17 维 context
- `DualAgentOrchestrator._compute_dual_agent_confidence`: 传 intervention 到 `_build_context` 让 17 维路径生效

**10 个候选 Intervention 难度分布** (默认 10 个):
```
[0.3, 0.5, 0.4, 0.6, 0.5, 0.4, 0.5, 0.7, 0.7, 0.7]
```
→ 只有 5 个不同难度值, 最大区分度有限.

**评估**: 重放 lbc003 56 题 response_history, 提取 54 pairs (跟 v0.74 一致), 跑 production calibration, 算 calibrated V3 全局 ECE.

## 2. 关键数据

| 指标 | use_arm_features=False (v0.74) | use_arm_features=True (v0.75 P0-m) | 变化 |
|---|---|---|---|
| **n_pairs** | 54 | 54 | — |
| **Raw V3 std** | 0.108 | 0.110 | +0.002 (几乎无变化) |
| **Raw V3 ECE** | 0.5358 | 0.5243 | -0.012 |
| **Calibrated V3 std** | 0.109 | 0.114 | +0.005 |
| **Calibrated V3 ECE** | 0.1101 | 0.1210 | **+0.011 (变差)** ⭐ |
| **冷启动期 ECE (前 5 轮)** | 0.3946 | 0.3946 | 0 (一致) |
| **非冷启动期 ECE (6+)** | 0.0811 | 0.0931 | +0.012 (变差) |
| **Bin [0.9, 1.0] gap** | 0.108 (28 样本) | 0.186 (19 样本) | **+0.078 (显著变差)** ⭐ |

## 3. Bin 分布对比

**use_arm_features=False (v0.74)**:
| Bin | n | conf | acc | gap |
|---|---|---|---|---|
| [0.5, 0.6] | 2 | 0.59 | 1.00 | 0.41 |
| [0.6, 0.7] | 3 | 0.62 | 1.00 | 0.38 |
| [0.8, 0.9] | 21 | 0.85 | 0.81 | 0.05 |
| **[0.9, 1.0]** | **28** | **0.97** | **0.86** | **0.11** |

**use_arm_features=True (v0.75 P0-m)**:
| Bin | n | conf | acc | gap |
|---|---|---|---|---|
| [0.5, 0.6] | 2 | 0.59 | 1.00 | 0.41 |
| [0.6, 0.7] | 3 | 0.62 | 1.00 | 0.38 |
| [0.8, 0.9] | 25 | 0.86 | 0.80 | 0.06 |
| **[0.9, 1.0]** | **19** | **0.98** | **0.79** | **0.19** ⭐ |

**关键观察**:
- P0-m 让更多样本从 [0.9, 1.0] (28) 滑落到 [0.8, 0.9] (25), 但 [0.9, 1.0] bin 内部 gap 反而从 0.108 恶化到 0.186
- 留下来的 19 个 [0.9, 1.0] 样本 acc 反而下降 (0.86 → 0.79), conf 上升 (0.97 → 0.98)
- 净效果: bin [0.9, 1.0] gap 加剧, 全局 ECE 恶化

## 4. Source 分布 (跟 v0.74 完全一致)

| Source | off | on |
|---|---|---|
| mean_mastery_fallback | 5 | 5 |
| platt_scaling | 15 | 15 |
| isotonic_regression | 34 | 34 |

→ P0-m 没改变 calibration 调度, 真正起作用的是 LinUCB θ@x 的 raw 预测变化 (但变化很小).

## 5. 为什么 P0-m 失败?

### 5.1 Raw V3 std 几乎没变 (0.108 → 0.110)

**预期**: difficulty 让 LinUCB 区分易/难干预, raw V3 std 应该显著增加 (P0-m 测试 `test_arm_features_changes_v3_distribution` 假设).

**实际**: 0.108 → 0.110, +0.002. difficulty 信号在 raw V3 输出中几乎不体现.

**根因分析**:
- 10 个候选只有 5 个不同难度值: {0.3, 0.4, 0.5, 0.6, 0.7}
- lbc003 答题的 5D mastery 在中间区间 (~0.5), LinUCB θ 还没学到"难度 vs 答对率"的强关系
- LinUCB 是 per-arm learning, 16→17 维多 1 维 signal, 但跟其他 16 维比权重低, 短时间内影响小
- **关键**: lbc003 重放是从新初始化的 LinUCB, 没有累积数据. 真实场景下 (lbc003 答 100+ 题后) 可能有不同结果.

### 5.2 Bin [0.9, 1.0] gap 反而恶化 (0.108 → 0.186)

**意外**: 不仅没改善, 反而显著恶化.

**可能根因**:
- P0-m 让 LinUCB 预测更"激进" (偏向选高 UCB arm), 18 轮中 [0.9, 1.0] 区间 raw V3 上限从 0.399 → 0.408
- 但 actual_outcome 没同步改善 (lbc003 是高 baseline 85% 学生, 答对率天花板固定)
- 校准后 (Platt/Isotonic) 把 raw 上限提升到 ~1.0, 实际 acc 还是 ~0.79
- **Isotonic Regression 把 P0-m 的"raw 噪声"放大成"calibrated 系统误差"**

### 5.3 冷启动期 (前 5 轮) 0 改善

**根因**: 冷启动 5 轮走 mean_mastery_fallback, **完全没用到 LinUCB 17 维 context**, 所以 P0-m 对冷启动期 ECE 0 影响.

## 6. 决策

### ❌ v0.75 P0-m (LinUCB difficulty feature) **无效**

**理由**:
- 校准后 ECE 0.110 → 0.121 (恶化 0.011)
- Bin [0.9, 1.0] gap 0.108 → 0.186 (恶化 0.078)
- 冷启动期 0 改善 (跟理论预期一致)
- Raw V3 std 几乎没变 (difficulty 信号被噪声淹没)

**跟 P0-l.1 (Global Platt) 的对比**:
| 方案 | 冷启动期 | 校准后全局 ECE | 实施复杂度 |
|---|---|---|---|
| P0-l.1 (Global Platt) | gap 0.20 → 0.125 (-37.5%) | -0.007 (边际) | 高 (100+ 行) |
| P0-m (Difficulty) | 0 改善 | +0.011 (**恶化**) | 中 (~50 行) |
| **v0.74 (当前)** | gap 0.20 (mean_mastery) | baseline 0.24 | 已落地 |

### 7. Plan B 触发条件达成

按 P0-l.1 报告 §6 决策:
> "Plan B (重定义 H3) 触发条件: P0-m 也无效 → 3 个方案 (P0-l + P0-m + Plan A global Platt) 全失败"

**v0.75 攻击 bin [0.9, 1.0] gap 的努力正式失败**. 走 Plan B: 重定义 H3 假设.

## 7. 实施时间线

| 任务 | 状态 |
|---|---|
| P0-m LinUCB difficulty feature (实现) | ✅ 完成 |
| P0-m 单测 (10 个) | ✅ 10/10 通过 |
| P0-m lbc003 ECE 评估 (本报告) | ✅ 完成, 决策: 无效 |
| 备份 v0.75 P0-m 实现 (use_arm_features=False 默认, 不破坏 v0.74) | ✅ 已保留, 默认关闭 |
| **下一步: Plan B 重定义 H3** | 📋 待启动 |

## 8. 保留 P0-m 实现的原因

虽然 P0-m 验证无效, **保留实现** 而非删除:

1. **设计正确性**: 17 维 LinUCB with arm features 是工业标准做法 (Li et al. 2010 paper 通用扩展), 实施无误
2. **未来场景**: 真实新学生 (不是 lbc003 replay) 累积 100+ 题后, difficulty 信号可能显现
3. **默认值 = False**: 跟 v0.74 完全兼容, 不影响生产
4. **测试覆盖完整**: 10 个单测保护, 不会回归

**未来启用条件**:
- lbc003 真实答题 (非 replay) 100+ 题
- 新学生 lbc004 完整冷启动 30+ 题
- 题库难度标注更细 (10+ 个不同难度值)

## 附录 A: 复现命令

```bash
# 跑 v0.75 P0-m lbc003 ECE 评估
python scripts/v075_p0m_difficulty_replay.py

# 输出
discussions/2026-08-04-v075-P0-m-difficulty-replay.json
```

## 附录 B: 关键代码路径

- `ecos/lca/l4_optimization/linucb.py::score_arm`: 新增方法 (P0-m)
- `ecos/lca/l4_optimization/policy_learner.py::_build_context`: 接受 intervention 参数
- `ecos/lca/l4_optimization/policy_learner.py::select_intervention`: per-candidate context 路径
- `ecos/dual_agent/orchestrator.py::_compute_dual_agent_confidence`: 传 intervention 到 `_build_context`
- `tests/test_v075_difficulty_feature.py`: 10 个单测
- `scripts/v075_p0m_difficulty_replay.py`: ECE 评估脚本
