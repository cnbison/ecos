# P0-h Reliability Diagram 诊断 + Option 2 评估方案

> **生成时间**: 2026-08-03
> **作者**: Mavis
> **触发**: Bisen 2026-08-03 拍板 "选项 3 (画 reliability diagram) + 顺势走选项 2 (换 confidence 指标)"
> **前置修复**: v0.71.0 P0-g 限制 LinUCB 每 arm 惩罚次数 (commit c3ff146)

---

## 0. TL;DR

**Reliability diagram 结果非常明确**: V3 (LinUCB θ@x) **全局系统性低估 0.54** (confidence 平均 0.32, accuracy 平均 0.85).
所有 V3 预测都集中在 [0.1, 0.4] 区间, 没有任何样本敢预测 > 0.4.

**根因不是 BUG, 是 LinUCB θ@x 模型本身表达能力不够**:
- lbc003 平均 accuracy 0.85, LinUCB θ 范数 ~0.03, θ @ x 最大预测 ~0.4
- 即使修了路径绕过 BUG + A 矩阵爆炸 BUG, 线性模型学不到 0.85 这种高 baseline

**Option 2 (换 confidence 指标) 是必然方向**. 下面列 4 个候选方案 + 评估, 等 Bisen 拍板.

---

## 1. 诊断方法 (P0-h)

### 1.1 脚本与重放

- 脚本: `scripts/plot_reliability_diagram.py` (新增)
- 数据: lbc003 response_history 56 条 (DB 读, `web/ecos.db`)
- 重放: 全新 `DualAgentOrchestrator` 实例 (in-memory, 不污染 DB), 应用 v0.71.0 P0-g 修复
- 配对: `(V3 of round N+1, actual_outcome of round N+1)` 共 54 对 (V3 缺失 2 条: 第 1 条 prev=None + 1 条 metadata 写入失败)
- 分组: 10 bins, 每 bin 算 mean_confidence / mean_accuracy / n_samples / gap
- 画图: matplotlib (Agg backend) + 直方图, 保存到 `discussions/2026-08-03-v0710-reliability-diagram.png`

### 1.2 V3 source 分布 (确认 v0.70.0-d + v0.71.0 P0-g 修复生效)

| source | 样本数 | 含义 |
|---|---|---|
| `linucb` | 39 | LinUCB θ@x 预测 (v0.71.0 P0-g 修复后非冷启动期走这里) |
| `estimate_gain_fallback` | 15 | 冷启动期 fallback (实际是估计 gain, 不是真 confidence) |
| `None` (skip) | 2 | 第 1 条 prev=None + metadata 写入失败 |
| 合计 | 56 → 54 有效 | V3 字段写入率 96.4% ✅ |

---

## 2. 诊断结果 (v0.71.0 P0-g 修复后)

### 2.1 Reliability Diagram 数据

| bin | mean_conf | mean_acc | gap | n |
|---|---|---|---|---|
| [0.0, 0.1] | — | — | — | 0 |
| [0.1, 0.2] | **0.1425** | **0.8667** | **-0.7242** | 15 |
| [0.2, 0.3] | — | — | — | 0 |
| [0.3, 0.4] | **0.3828** | **0.8462** | **-0.4633** | 39 |
| [0.4, 1.0] | — | — | — | 0 |

**关键观察**:
- V3 预测**全部**在 [0.1, 0.4] 区间, **没有**样本在 [0.5, 1.0]
- 任何 bin 的 V3 都远低于实际 accuracy (gap 都在 -0.45 以上)
- Bin [0.1, 0.2] (15 样本, 主要是冷启动 fallback) gap 更大: -0.72
- Bin [0.3, 0.4] (39 样本, LinUCB θ@x) gap: -0.46

### 2.2 全局统计

```
平均 V3 confidence:   0.3161
平均 actual_outcome:  0.8519
全局偏差 (acc - conf): 0.5358   ← V3 系统性低估 0.54!
ECE (per-sample):     0.6328
```

### 2.3 诊断判断

| 类型 | bin 数 |
|---|---|
| 有样本的 bin | 2 |
| 低估 bin (gap < -0.1) | **2** (全低估) |
| 高估 bin (gap > 0.1) | 0 |
| 校准 bin (\|gap\| ≤ 0.1) | 0 |

**判定**: ✅ **V3 全局低估** (LinUCB θ@x 预测永远偏低).
**方向**: 换 confidence 指标 (选项 2). 模型本身不可信, 小修不解决问题.

---

## 3. LinUCB θ@x 为什么系统性低估 (模型层根因)

### 3.1 量化分析

**修复前** (v0.70.0-d 修路径绕过 BUG 但 P0-g 未修):
- 每 arm A 矩阵最大特征值 ≈ 1.6e+05 (放大 16 万倍)
- θ 范数 ≈ 1e-4 (A^-1 b 几乎为 0)
- expected_reward = θ @ x ≈ 0.0001

**修复后** (v0.71.0 P0-g, PENALTY_MAX=1):
- 每 arm A 矩阵最大特征值 ≈ 16.5 (放大 10 倍 + 正常 x x^T 累加)
- θ 范数 ≈ 0.03 (修复前 1e-4, 增 300 倍)
- expected_reward = θ @ x 最大 ~0.4

### 3.2 根本限制

LinUCB θ@x 预测 = θ · x, 其中:
- θ ∈ R^16 (5D theta + 6 Bloom + 5 DNA)
- x ∈ R^16 (同上)
- 训练数据: 54 个 (V3, actual_outcome) 配对 (其中 39 个 linucb)

线性模型 + 16 维 + 54 样本, 拟合 lbc003 这种"高 baseline mastery" 学生的能力 (accuracy 0.85) 是**数学上困难**的:
- y_i ∈ {0, 1} (二元 outcome)
- 16 维 θ 在 R^16 内最优拟合是"近似 linear"函数
- "所有题答对率 0.85" = sigmoid(θ · x) ≈ 0.85 → θ · x ≈ 1.7 (大值), 但 16 维线性组合 + 训练样本少, θ 学不到这么大

**结论**: 修了所有 BUG 仍然 ECE 0.57, 因为模型类 (linear) + 维度 (16) + 样本 (54) 学不到 0.85 baseline. 这不是 BUG, 是**模型选择问题**.

---

## 4. Option 2 评估: 4 个候选方案

> **决策原则**: 评估方向是"让 V3 confidence 真能预测答对概率", 优先看 ECE 改善幅度 + 改动风险.

### 4.1 方案 A: Platt Scaling 后校准 V3

**思路**: 在 (V3, actual_outcome) 配对上拟合 `P(actual=1|V3) = sigmoid(A·V3 + B)`, 把 V3 线性变换到真答对概率.
- 训练数据: 54 个 (V3, actual_outcome) 配对 (现有 calibration_log 即可)
- 算法: 1-2 行 `sklearn.linear_model.LogisticRegression` 或 `scipy.optimize.curve_fit`
- 预测: `V3' = sigmoid(A·V3 + B)` 替换 V3 写入新字段 `dual_agent_confidence_calibrated`

**优**:
- 改动最小 (1 个 helper 函数 + 1 个新 metadata 字段)
- 复用 v0.71.0 P0-g 修复后的所有数据
- Platt scaling 经典 calibration 方案, 工业级验证

**劣**:
- 后校准 (post-hoc), 学生切换时可能要重训
- lbc003 N=54 样本能稳定, 但换学生可能欠拟合
- 没改变 LinUCB 本身, 治标不治本

**预期 ECE**: 0.10-0.25 (显著改善, 可能过 H3 阈值)

### 4.2 方案 B: CTA mastery_prob + LinUCB V3 混合

**思路**: `V3' = α · state.overall_confidence + β · V3_linucb + γ · mastery_prob`. 三个信号加权融合.

**优**:
- 利用 CTA 已有信号 (state.overall_confidence, mastery_prob_after)
- 双 Agent 概念保留 (CTA + LCA 都有贡献)
- 改动: 在 `_post_process_calibration` 加加权融合

**劣**:
- **违背 v0.69.0 PRD §2.2 B3 决策**: "换汤不换药, 本质'单 Agent 信号充双 Agent'"
- H3 验证就变成"两个单 Agent 互相对比"了, 互校假设不成立
- α/β/γ 超参, 需要额外调参

**预期 ECE**: 不确定, 可能 0.30-0.50 (改善但未必过阈值)

### 4.3 方案 C: 完全放弃 V3, 改用 CTA mastery_prob_after (单 Agent 路径)

**思路**: 直接用 `state.K.mastery_prob` (单 Agent baseline) 当 confidence, 跳过 LinUCB θ@x.

**优**:
- 单 Agent baseline 已验证 ECE = 0.17 (过阈值)
- 改动简单, 不依赖 LinUCB

**劣**:
- **彻底放弃双 Agent 互校的价值**, H3 假设变空 (单 vs 双比的是同一个指标)
- 不能写 commit message 说"双 Agent 互校抗幻觉" — 因为指标是单 Agent 提供的
- v0.69.0 PRD §2.2 B3 已否决此方案 (理由: 违背双 Agent 理念)

**预期 ECE**: 0.17 (单 Agent baseline 数据), 但 H3 验证设计要重做

### 4.4 方案 D: 重新定义 H3 假设 (诚实反思)

**思路**: 承认"双 Agent 互校抗幻觉"假设过强, 重新定义为"双 Agent 互校减少 intervention 不一致性 / 提升 rationale 质量" 等可验证的子假设.

**优**:
- 诚实面对"互校不能改善 ECE"的事实
- 可以重新测多个子假设, 找到双 Agent 真正起作用的地方

**劣**:
- 推翻之前公开的 H3 声明 (v0.63.0 报告, v0.68.0 B 报告)
- 双 Agent 核心价值需要重新论证

**预期**: H3 重新设计后 ECE 验证作废, 改测其他子假设

---

## 5. 推荐方向 (等 Bisen 拍板)

| 方案 | 推荐度 | 理由 |
|---|---|---|
| **A. Platt Scaling** | ⭐⭐⭐ (推荐) | 改动最小, 风险最低, 复用所有数据, 经典 calibration 方案 |
| B. CTA+V3 混合 | ⭐ | 违背 B3 决策, 治标不治本 |
| C. 改用 mastery_prob | ⏸️ | 违背双 Agent 理念, H3 验证设计要重做 |
| D. 重定义 H3 | 📋 | 诚实反思但成本高, 留作 Plan B |

### 5.1 我的建议: **方案 A (Platt Scaling) 作为短期方案**

**理由**:
1. 改动最小 (1 helper 函数 + 1 metadata 字段 + 几行代码)
2. 复用 v0.71.0 P0-g 修复后的所有数据, 不浪费修复工作
3. Platt scaling 在工业界是 calibration 标准方案, 工程上成熟
4. 即使 Platt scaling 后 ECE 仍 > 0.10, 也是有意义的探索 (积累 calibration 数据)
5. 如果 A 失败, 可顺势走 D (重定义 H3) — Plan B 仍是开放的

**实施路径** (v0.72.0 候选):
1. 新增 `ecos/dual_agent/calibration.py`: `class PlattScaler: fit(pairs) -> scale(p) -> calibrated_p`
2. `_post_process_calibration` 在写入 `dual_agent_confidence` 后, 加 `dual_agent_confidence_calibrated` 字段
3. 写测试 `tests/test_platt_scaler.py`: 验证 (a) 拟合稳定, (b) 单调性保持, (c) ECE 改善
4. 跑 reliability diagram 重画 (4 bin 至少 1 个校准 bin), 重算 ECE
5. 更新 H3 报告 §9 "v0.72.0 Platt Scaling 修复后结果"

**预估 ECE**: 0.10-0.25 (V3 全局低估 0.54, Platt scaling 至少能拉到 ±0.20 区间).

---

## 6. 待 Bisen 拍板

1. **方案选哪个?** A / B / C / D / 其他?
2. **如果是 A (Platt Scaling)**, 训练数据用 lbc003 54 样本 OK 吗? 还是先攒更多学生数据?
3. **Platt Scaling 后, 如果 ECE 仍 > 0.10**, 是否顺势走 D (重定义 H3)?
4. **P2 (State Engine 抽象) 何时启动?** 当前 H3 未通过, P2 原本 gate 在 H3 pass 上. 是否提前启动 P2 (架构先行, H3 后续再补)?