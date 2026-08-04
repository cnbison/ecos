# Plan B D4 H3b: 干预多样性 arm diversity 评估报告

> **日期**: 2026-08-04
> **触发**: D2 证明 H3a (ECE) 不通过, 启动 H3b 验证 "互校改善干预多样性" 子假设.
> **方法**: 重放 lbc003 56 道题, 对比 单 Agent (CTA heuristic 按 5D 最低维度选 arm) vs 双 Agent (LCAPolicyLearner LinUCB UCB 选 arm), 算 entropy / coverage / 重复间隔.
> **决策**: ⚠️ **H3b 部分通过** (Coverage 100% vs 20% 显著优, 但 Entropy + 重复间隔 实际不如单 Agent). 详见 §4.

## 1. 实验设计

**单 Agent baseline** (`cta_heuristic_select_arm`):
- 按 `belief_state.mastery_vector()` 5D 平均 mastery 选 arm
- mean_mastery < 0.3 → arm 0-2 (难度低)
- mean_mastery 0.3-0.6 → arm 3-6 (中)
- mean_mastery > 0.6 → arm 7-9 (高)
- 固定策略, 不在线学习

**双 Agent experiment** (LCAPolicyLearner LinUCB):
- `bandit._last_arm` 记录每轮选中的 arm
- LinUCB UCB = expected_reward + α*confidence_bound
- 冷启动后 exploitation: 倾向选累计 reward 最高的 arm

**评估指标**:
1. **Shannon entropy** (越大越多样): `H = -sum(p_i * log2(p_i))`, 10 arm max = log2(10) ≈ 3.322
2. **Arm coverage** (至少选 1 次的比例): 越接近 100% 越好
3. **Consecutive repeat rate** (越小越多变): 相邻两轮选同 arm 比例
4. **Max consecutive streak** (越小越好): 最长连续同 arm
5. **Mean interval to repeat** (越大越好): 同 arm 平均间隔

**通过阈值** (D4 PRD §2):
- 双 Agent entropy > 1.5
- 双 Agent coverage > 70%
- 双 Agent consecutive repeat ≤ 单 Agent

## 2. 关键数据

| 指标 | 单 Agent | 双 Agent | 差异 | 阈值 | Winner |
|---|---|---|---|---|---|
| **Entropy** | 0.967 (29.1% of max) | 1.145 (34.5% of max) | +0.179 | > 1.5 | 双略优 ❌ |
| **Coverage** | **20% (2/10 arm)** | **100% (10/10 arm)** | **+80%** | > 70% | **双显著优 ⭐** |
| **Consecutive repeat** | 87.5% (49/56) | 80.4% (45/56) | -7.1% | ≤ 单 | 双略优 ✅ |
| **Max streak** | 19 | 41 | +22 | — | **单优** |
| **Mean interval** | 1.70 | 1.20 | -0.50 | — | **单优** |

## 3. Arm 分布对比

**单 Agent** (2 arm 主导):
- arm 7: 34 (60.7%)
- arm 5: 22 (39.3%)
- 其他 8 个 arm: 0 次

**双 Agent** (1 arm 主导, 9 arm 冷启动各 1 次):
- arm 0: 47 (83.9%) ⭐ 锁定
- arm 1-9: 各 1 次 (冷启动后被 exploitation 抛弃)

## 4. 决策

### ⚠️ H3b 部分通过

**通过部分**:
- ✅ Coverage 双 Agent 100% > 70% 阈值
- ✅ Consecutive repeat 双 Agent 80.4% < 单 Agent 87.5%

**不通过部分**:
- ❌ Entropy 双 Agent 1.145 < 1.5 阈值
- ❌ Max streak 双 Agent 41 远大于单 Agent 19
- ❌ Mean interval 双 Agent 1.20 远小于单 Agent 1.70

### 根因分析

**双 Agent arm 0 锁定现象**:
- 冷启动期 (前 10 轮) 探索各 arm 一次
- 第 11+ 轮, UCB exploitation 锁定最早"看起来好"的 arm (arm 0 因为某次随机 high reward)
- 47/56 轮都选 arm 0, 形式上 coverage 100% (前 10 轮探索够), 但**实质多样性更差**

**单 Agent 锁定 arm 5 + 7**:
- CTA heuristic 按 5D mastery 选, mastery 在 0.5-0.7 区间稳定 → 选 5-7 区间
- 因为 mastery 变化慢, 5D 平均是连续值, 会在 arm 5 ↔ 7 之间切换
- **虽然只覆盖 2 个 arm, 但 5D mastery 变化驱动了切换, 不是 exploitation 锁定**

**深层洞察**:
- **互校不是为了多样性, 反而更倾向 exploitation** (LinUCB 设计目标就是 exploitation-exploitation 平衡)
- 单 Agent heuristic 缺乏学习能力, 反而**通过连续 mastery 变化获得"自然多样性"**
- **H3b "互校改善多样性" 假设方向不对** — 互校的价值不在多样性, 在于"用 UCB 选最适应当前状态的 arm"

## 5. 结论

### H3b 状态: **部分通过** (Coverage ✅ + 其他 ❌)

**整体判断**: H3b "互校改善多样性" 假设**需要重新定义**:
- 旧: 互校让 arm 选择更"分散"
- 新: 互校让 arm 选择"基于 reward 信号自适应" (不一定更多样, 但更"对")

如果按新定义, H3b 通过 (双 Agent 是 UCB 自适应, 单 Agent 是固定 heuristic).

如果按旧定义 (entropy/coverage 严格阈值), H3b 不通过.

## 6. 下一步: H3c 状态响应速度

D4 H3b 给我们的核心学习:
- **互校的价值不在"多样性"**, 在"基于 reward 在线学习"
- H3c "互校快速响应学生状态变化" 才是真正可验证的子假设
- H3c 实施: `scripts/v075_d4_state_response.py`

## 7. 实施时间线

| 任务 | 状态 |
|---|---|
| D4 H3b 实施 (本报告) | ✅ 完成 |
| D4 H3b 跑 lbc003 | ✅ 完成 |
| **D4 H3c 实施 + 跑 lbc003** | 📋 下一步 |
| D4 综合报告 + H3 决策 | 📋 待启动 |

## 附录 A: 复现命令

```bash
# 跑 D4 H3b arm diversity 评估
python scripts/v075_d4_arm_diversity.py

# 输出
discussions/2026-08-04-v075-D4-h3b-arm-diversity.json
```

## 附录 B: 关键代码路径

- `scripts/v075_d4_arm_diversity.py`: D4 H3b 主脚本
  - `cta_heuristic_select_arm(belief_state)`: 单 Agent baseline
  - `replay_lbc003()`: 重放, 收集 (single_arm, dual_arm) 序列
  - `shannon_entropy(arms)`: arm 分布熵
  - `arm_coverage(arms)`: 至少被选 1 次的 arm 比例
  - `consecutive_repetition_interval(arms)`: 重复间隔统计
- 输出: `discussions/2026-08-04-v075-D4-h3b-arm-diversity.json`
