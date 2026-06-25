# 2026-06-25 · 双 Agent 互校机制工程文档（v0.13.0，工程层第 4 份）

## 主题

完成工程层第 4 份文档 `research/10-engineering/04-dual-agent-calibration.md`（v1.0，1147 行），实现 CTA ↔ LCA 互校机制——ECOS 的"抗幻觉核心"。

## 日期

2026-06-25

## 背景

工程层第 4 份——双 Agent 互校机制基于：
- v2.0 §3.5（互校核心循环 + 4 模式 + 3 机制）
- 02-architecture.md §3.3（双 Agent 详细架构）
- [01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md)（CTA 接口）
- [02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md)（LCA 接口）
- [03-bloom-goal-library.md](../../research/10-engineering/03-bloom-goal-library.md)（共同语言）
- 04-risks.md §A1（双 Agent 工程复杂度）+ §A4（互校抗幻觉失败）

## 文档结构（10 章节）

| 章节 | 内容 |
|---|---|
| §0 | 模块定位 + 与 04-risks.md §A1 + §A4 对应 |
| §1 | 整体架构（互校循环 + 4 模式 + 3 机制 + 11 子目录）|
| §2 | 互校循环协议（消息 + 状态机 + version）|
| §3 | 4 个交互模式（常态 + 信念质疑 + 策略质疑 + 元反思）|
| §4 | 对抗幻觉的 3 个机制 + 人工审核触发 |
| §5 | 死锁避免（超时 + 优先级 + 单 Agent 降级）|
| §6 | 互校循环主流程编排（DualAgentOrchestrator）|
| §7 | 测试策略 + 性能基准 + 5 个关键测试场景 |
| §8 | MVP 范围（6 组件 + 性能预算）|
| §9-10 | 关联文档 + 版本维护 |

## 核心工程实现

### 1. 互校循环协议

```python
class CalibrationMessage:
    # 9 种 MessageType：CTA_OUTPUT / LCA_INTERVENTION / OBSERVATION /
    # CTA_UPDATE / CAUSAL_ATTRIBUTION / BELIEF_CHALLENGE / STRATEGY_CHALLENGE /
    # META_REFLECTION / HUMAN_REVIEW_REQUEST
    message_id, message_type, student_id, timestamp
    version="v1.0", calibration_round
    payload, priority, timeout_sec, metadata
```

### 2. 互校状态机（11 状态）

IDLE → CTA_HYPOTHESIS → LCA_EXPERIMENT → OBSERVATION_PENDING → CTA_UPDATE → LCA_CAUSAL → LCA_REPLAN → IDLE

特殊转移：BELIEF_CHALLENGE / STRATEGY_CHALLENGE / META_REFLECTION / HUMAN_REVIEW

### 3. 4 个交互模式

| 模式 | 触发条件 | 处理 |
|---|---|---|
| 常态循环 | 新观测 | 6 步骤流程 |
| 信念质疑 | CTA 高置信 + 学生表现差 | CTA 重审信念 |
| 策略质疑 | 连续 5 次干预改善 < 0.05 | LCA 调整策略空间 |
| 元反思 | 4 周 BloomProfile 提升 < 0.05 | 双 Agent 整体复盘 |

### 4. 3 个抗幻觉机制

1. **CTA 信念分布检查**：避免单一 confidence = 1.0（过度自信）+ 低置信度需 evidence_ids ≥ 3
2. **LCA 实验设计验证**：练习型需 difficulty 匹配、讲解型需目标技能、元认知型不能过频繁
3. **L4 因果归因强制**：每个干预效果必须经因果归因，缺失抛 ValueError

### 5. 死锁避免（3 重保护）

- 超时保护：30 秒（可用 `TimeoutGuard` context manager）
- 优先级仲裁：HUMAN_REVIEW > META_REFLECTION > CHALLENGE > NORMAL
- 单 Agent 降级：连续 3 次错误或超过 60 秒 → 降级

### 6. DualAgentOrchestrator 主流程

```python
def process_observation(observation) -> CalibratedLCAResult:
    # Step 0: 检查是否触发特殊模式（策略质疑 / 元反思）
    # Step 1: 常态循环（带超时保护）
    # Step 2: 抗幻觉检查（信念分布 + 实验设计 + 人工审核）
    # Step 3: 记录历史
```

## 关键决策

| 决策 | MVP 选择 |
|---|---|
| 互校循环模式 | 同步（不异步）|
| 状态机 | 11 状态完整覆盖 |
| 4 模式触发 | 自动检测 + 显式触发 |
| 抗幻觉机制 1 | CTA 信念分布 + confidence + evidence |
| 抗幻觉机制 2 | LCA 实验设计验证 |
| 抗幻觉机制 3 | L4 因果归因强制 |
| 人工审核 | 3 种触发条件（置信度/信念/连续无效）|
| 死锁避免 | 3 重保护（超时 + 优先级 + 降级）|

## 性能基准

| 指标 | 阈值 |
|---|---|
| 常态循环延迟 | P95 ≤ 5 秒 |
| 互校循环总延迟 | P95 ≤ 10 秒 |
| 接口错误率 | ≤ 0.1% |
| 信念质疑 F1 | ≥ 0.7 |
| 策略质疑 F1 | ≥ 0.6 |
| ECE | ≤ 0.10（H3 假设）|
| 人工审核触发率 | ≤ 5% |

## 产出文件

| 文件 | 角色 | 行数 |
|---|---|---|
| `research/10-engineering/04-dual-agent-calibration.md` | **主文档**——双 Agent 互校（v1.0，10 章节）| 1147 |
| `discussions/2026-06-25-ecos-dual-agent-doc.md` | **本文件**——本次会话简要记录 | ~130 |
| `CHANGELOG.md` | 升级到 v0.13.0 | — |

## 关联文档

- [README.md](../../README.md) — ECOS 项目入口
- [CHANGELOG.md](../../CHANGELOG.md) — 变更日志（v0.13.0）
- [research/10-engineering/01-cta-belief-engine.md](../../research/10-engineering/01-cta-belief-engine.md) — CTA 引擎（互校"理解"端）
- [research/10-engineering/02-lca-policy-engine.md](../../research/10-engineering/02-lca-policy-engine.md) — LCA 引擎（互校"改变"端）
- [research/10-engineering/04-dual-agent-calibration.md](../../research/10-engineering/04-dual-agent-calibration.md) — 本次主产出

## 下一步

工程层最后 1 份：
- **05-persistence-session.md**（持久化与会话管理）—— CTA 状态 + 干预历史 + 互校证据存储

待 5 份工程文档完成后，工程层 100% 完成。

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
**版本**：v0.13.0（工程层第 4 份）
