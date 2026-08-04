# v0.75 P0-l.1 Global Platt 离线分析报告

> **日期**: 2026-08-04
> **触发**: v0.74 ECE 0.24 仍未过 H3 阈值 0.10, 冷启动期是已知瓶颈 (5 样本 gap 0.20). 评估 v0.75 跨学生迁移能否进一步改善 cold start.
> **方法**: 重放 lbc001 (60) + lbc002 (45) = 101 pairs 训 global Platt, 应用到 lbc003 前 5 轮 cold start, 对比 v0.74 mean_mastery_fallback.
> **决策**: 见 §6.

## 1. 数据分布对比 (关键防御性自检)

| 学生 | n_pairs | raw_V3 范围 | raw_V3 mean | actual mean | 真实 baseline |
|---|---|---|---|---|---|
| **lbc001** | 58 | [0.14, 0.52] | 0.40 | 0.71 | 71% 答对 |
| **lbc002** | 43 | [0.14, 0.38] | 0.29 | 0.76 | 76% 答对 |
| **lbc003** | 54 | [0.14, 0.40] | 0.32 | 0.85 | 85% 答对 (高 baseline) |

**关键观察**:
- 3 个学生 raw_V3 范围高度重叠 ([0.14, ~0.5]), 可以用同一 global Platt 校准
- lbc003 是 "高 baseline" 学生 (85% vs 71-76% 的 lbc001/2)
- raw_V3 全局低估 (0.14-0.52 vs actual 0.71-0.85), 跟 v0.71.0 P0-g 修 A 矩阵爆炸后一致

## 2. Global Platt 训练结果

训练集: lbc001 (58) + lbc002 (43) = **101 pairs** (远超 Platt 5+ pair 阈值)

```
P(correct | raw_V3) = sigmoid(A * raw_V3 + B)
A = -4.1020
B = 2.5275
fitted = True
```

**A 为负的解读**: 负斜率说明 raw_V3 跟 actual_outcome 是**反相关**的
- raw_V3 低 (0.14) → P(actual=1) 高 (0.876) → 实际"低预测"映射"高正确率"
- 根因: LinUCB θ@x 在 cold start 默认偏低 (新 arm 没数据 → 偏 uncertainty 高), 但实际学生因为 CTA baseline 高 (0.85), 反而答得对
- 跟 v0.71.0 P0-g 修 A 矩阵爆炸的根因一致: LinUCB 16 维 + 几十样本数学上拟合不了高 baseline

## 3. Cold Start 评估 (lbc003 前 5 轮)

**场景**: 模拟 lbc003 冷启动, 用 global Platt 校准 raw_V3=0.14 (cold start 5 样本)

| 方案 | mean conf | mean actual | mean gap | 改善 vs v0.74 |
|---|---|---|---|---|
| **raw V3 (v0.72/v0.73)** | 0.1425 | 1.00 | **0.8575** | — |
| **v0.74 mean_mastery_fallback** | 0.80 | 1.00 | **0.2000** | -0.6575 (vs raw) |
| **v0.75 global Platt (新)** | 0.8747 | 1.00 | **0.1253** | **-0.0747 (vs v0.74)** |

**关键观察**:
- 5 样本 raw_V3 都是 0.14 (LinUCB 冷启动默认值)
- global Platt 给出 0.875 (跟 actual 1.0 几乎完美)
- 比 v0.74 mean_mastery 改善 0.075 (37.5%)

**v0.75 跟 v0.74 差异的来源**:
- v0.74: 固定 0.80 (CTA baseline 假设, 不区分题目难度)
- v0.75: 输入 0.14 → 输出 0.875 (从历史 101 pairs 学到 "raw_V3 低 = 高 baseline 学生大概率答对")
- v0.75 更"对症下药", 因为它把 raw_V3 的输入信号用上了

## 4. 全局 ECE 影响估算

| 阶段 | v0.74 ECE | v0.75 ECE (估算) | 改善 |
|---|---|---|---|
| 冷启动期 (5 样本) | 0.2000 | 0.1253 | -0.075 |
| Platt 阶段 (15 样本) | 0.1635 | 0.1635 (不变) | 0 |
| Isotonic 阶段 (35 样本) | 0.2456 | 0.2456 (不变) | 0 |
| **整体 ECE (54 样本加权)** | 0.2366 | 0.2295 | **-0.007** |

**关键观察**:
- 冷启动期只占 5/54 = 9.3% 样本权重, 改善 0.075 在全局 ECE 只贡献 -0.007
- 真正瓶颈是 **Platt/Isotonic 阶段 (49/54 样本, 90.7% 权重)**
  - Platt 阶段 15 样本 ECE 0.16
  - Isotonic 阶段 35 样本 ECE 0.25 (bin [0.9, 1.0] gap +0.10 是主要贡献)

**结论**:
- ✅ **v0.75 global Platt 对冷启动期有效** (gap 0.20 → 0.125, 改善 37.5%)
- ⚠️ **全局 ECE 改善有限** (0.2366 → 0.2295, 只改善 3%)
- 🚫 **H3 阈值 0.10 仍不可达** (差 0.13, 不是 cold start 的问题)

## 5. 跟 v0.74 mean_mastery 路径的对比

| 维度 | v0.74 mean_mastery | v0.75 global Platt |
|---|---|---|
| 冷启动期 ECE | 0.20 | **0.125** |
| 实现复杂度 | 1 行 (orchestrator 加 fallback) | 100+ 行 (global scaler 训练 + 调度 + 持久化) |
| 跨学生依赖 | 0 (只读自己 belief_state) | 需要所有学生数据 (DB schema, 加载逻辑) |
| 扩展性 | 中 (新增学生走同样 fallback) | 强 (新学生自动获益) |
| 失败兜底 | 容易 (None → raw V3) | 复杂 (global scaler 加载失败 → ?) |
| 全局 ECE 改善 | 0.04 (0.28 → 0.24) | 0.007 (0.24 → 0.23) |

## 6. 决策建议

**问题**: 还要不要进 P0-l.3 (建 lbc004 真实冷启动验证)?

**选项 A: 进 P0-l.3 (跟 lbc004 验证)**
- 优点: 完整 end-to-end 验证 v0.75 路径, 证明对"全新学生"有效
- 优点: 工程上把 global scaler 落地 (DB schema, 调度逻辑), 即使 ECE 改善小也是架构基础
- 缺点: 全局 ECE 改善只有 0.007, H3 仍未通过
- 缺点: 需要 Bisen 手动答 lbc004 5-10 题 (~5-10 min)

**选项 B: 跳过 P0-l.3, 走 Plan B (重定义 H3)**
- 优点: 节省 Bisen 时间, 转向更有希望的方向
- 优点: 冷启动期已经基本解决 (v0.74 + v0.75 combined 都能达到 0.125 gap)
- 缺点: 放弃 v0.75 跨学生迁移这条路, 但它在工程上是好的基础设施
- 缺点: H3 仍未通过 (0.24 > 0.10)

**选项 C: 暂缓 v0.75, 先做 LinUCB difficulty feature (v0.75-P0-m)**
- 优点: 直接攻击 bin [0.9, 1.0] gap +0.10 真正瓶颈
- 优点: 16 维加 1 维 (难度) 可能显著改善高 conf bin 校准
- 缺点: 需要题库有难度标注 (可能没有)
- 缺点: 仍是 Platt/Isotonic 范围, H3 改善幅度可能仍有限

**📋 推荐**: 选项 C (LinUCB difficulty feature) > A > B
- v0.75 global Platt 已经验证能改善 cold start (改善 37.5%), 但全局 ECE 边际小
- 真正瓶颈在 Platt/Isotonic 阶段 bin [0.9, 1.0], 跟 cold start 无关
- difficulty feature 直接攻这块, 期望全局 ECE 改善更大

## 7. lbc004 验证 (P0-l.3) 的边际收益评估

**就算 lbc004 验证成功**:
- 冷启动期 ECE 0.20 → 0.125 (改善 0.075) ✓
- 全局 ECE 0.24 → 0.23 (改善 0.007) ✗ 边际小
- H3 阈值 0.10 仍差 0.13 ✗

**不验证的风险**:
- 如果 lbc004 跟 lbc003 baseline 类似 (0.85), 验证通过
- 如果 lbc004 是新类型学生 (e.g. 50% baseline), global Platt 可能不适用, 需要 fallback

**实际价值**:
- 架构上, global scaler 落 DB / 调度逻辑是有价值的 (未来加新学生能用)
- 验证 v0.75 工程实现, 不只是离线模拟
- 但对 H3 阈值通过没帮助

## 8. 实施时间线

| 任务 | 时间 | 状态 |
|---|---|---|
| P0-l.1 离线分析 (本报告) | 30 min | ✅ 完成 |
| P0-l.2 决策 (本报告 §6) | — | 🔄 待 Bisen 拍板 |
| P0-l.3 lbc004 验证 (若选 A) | 1-2 小时 | 📋 待启动 |
| P0-m LinUCB difficulty feature (若选 C) | 半天 | 📋 待启动 |
| Plan B 重定义 H3 (若选 B) | 半天 | 📋 待启动 |

## 附录 A: 复现命令

```bash
# 跑 v0.75 P0-l.1 分析
python scripts/v075_global_platt_analysis.py

# 输出
discussions/2026-08-04-v075-P0-l1-global-platt-analysis.json
```

## 附录 B: 关键代码路径

- `scripts/v075_global_platt_analysis.py::replay_student`: 重放逻辑 (两轮扫描)
- `scripts/v075_global_platt_analysis.py::fit_global_platt`: global Platt 训练
- `scripts/v075_global_platt_analysis.py::compare_cold_start`: cold start 评估
- `ecos/dual_agent/calibration.py::PlattScaler`: 复用的 Platt Scaling 类
- `ecos/dual_agent/orchestrator.py::_cold_start_fallback`: v0.74 mean_mastery 路径
