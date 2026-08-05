# v0.76 跨学生验证 fingerprint 修复普适性报告

> **日期**: 2026-08-05
> **作者**: Mavis (Claude Code)
> **关联**: [v0.75.3 PRD](./2026-08-05-v0753-H3-c3-linucb-decay-PRD.md) | [replay JSON](./2026-08-05-v076-cross-student-fingerprint-validation.json)

## 1. 背景

v0.75.3 发现并修复了 LinUCB fingerprint 覆盖 BUG:
- `_arm_fingerprints[arm]` 在同 arm 连续被选时被覆盖
- 上一轮 intervention_id 丢失, `_lookup_arm` 返回 None
- LinUCB.update 被跳过, A/b 矩阵不更新
- lbc003 受影响最严重: 47 次 arm 0 选择只有 1 次 update 成功

修复: 新增 `_intervention_to_arm: Dict[str, int]` (只追加, 不覆盖).

**问题**: 修复效果是否只在 lbc003 上显著? 其他学生是否也受益?

## 2. 验证设计

### 2.1 数据

- lbc001: 27 道题 response_history
- lbc002: 32 道题 response_history
- lbc003: 56 道题 response_history

### 2.2 方法

对每个学生跑两次:
- **A. BUG 修复 (v0.75.3 默认)**: `_intervention_to_arm` 启用
- **B. BUG 模拟 (v0.75.1 行为)**: 每轮清空 `_intervention_to_arm`, 强制走 `_arm_fingerprints` (会被覆盖)

对比 entropy / arm_coverage / max_streak.

## 3. 结果

| 学生 | 模式 | entropy | %max | coverage | streak | h3c3 |
|------|------|---------|------|----------|--------|------|
| lbc001 | BUG 修复 | 2.776 | 83.6% | 1.0 | 20 | PASS |
| lbc001 | BUG 模拟 | 1.496 | 45.0% | 1.0 | 41 | FAIL |
| lbc002 | BUG 修复 | 2.680 | 80.7% | 1.0 | 12 | PASS |
| lbc002 | BUG 模拟 | 1.734 | 52.2% | 1.0 | 30 | PASS |
| lbc003 | BUG 修复 | 2.546 | 76.7% | 1.0 | 20 | PASS |
| lbc003 | BUG 模拟 | 1.146 | 34.5% | 1.0 | 41 | FAIL |

### 3.1 Delta 分析

| 学生 | entropy delta | streak delta | fingerprint 修复有效 |
|------|---------------|--------------|---------------------|
| lbc001 | +1.280 | -21 | ✅ |
| lbc002 | +0.946 | -18 | ✅ |
| lbc003 | +1.401 | -21 | ✅ |

**平均 entropy delta = +1.209**, 所有学生 fingerprint 修复都有效 (delta > 0.3).

## 4. 结论

### 4.1 fingerprint 修复普适

- **所有学生 BUG 修复后 entropy > 1.5** (H3-c3 全通过)
- **BUG 模拟下 entropy 显著降低** (平均 delta +1.21)
- **max_streak 平均降低 20** (从 30-41 -> 12-20)

### 4.2 学生间差异

- **lbc003 受 BUG 影响最严重** (delta +1.401, BUG 模拟下 entropy 仅 1.146)
- **lbc001 受 BUG 影响次之** (delta +1.280, BUG 模拟下 entropy 1.496)
- **lbc002 受 BUG 影响最小** (delta +0.946, BUG 模拟下 entropy 1.734 仍过 1.5)

lbc002 受影响较小的原因: 可能是该学生答题模式较少触发同 arm 连续选择, fingerprint 覆盖机会少.

### 4.3 H3-c3 在所有学生上通过

| 学生 | H3-c3 (>1.5) | entropy |
|------|--------------|---------|
| lbc001 | ✅ PASS | 2.776 |
| lbc002 | ✅ PASS | 2.680 |
| lbc003 | ✅ PASS | 2.546 |

**H3-c3 跨学生普适**, 不只是 lbc003 特例.

## 5. 局限性

1. **样本量小**: 仅 3 个学生, 不足以做统计显著性检验
2. **同 skill 数据**: 三个学生都答 variables 技能, 跨 skill 验证留 v0.77+
3. **BUG 模拟方法**: 清空 `_intervention_to_arm` 是近似 v0.75.1 行为, 不是完全精确 (v0.75.1 没有 `_intervention_to_arm` 字段)

## 6. 建议

1. **v0.75.3 fingerprint 修复确认有效**, 无需进一步改动
2. **v0.77+ 跨 skill 验证**: 收集其他 skill 数据, 验证 fingerprint 修复在不同 skill 上的普适性
3. **更多学生数据**: 收集 lbc004+, 扩大样本量做统计检验
