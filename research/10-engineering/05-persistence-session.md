# 05 - 持久化与长期会话管理

> **状态**：📋 占位（待 Phase 4.1 填充详细设计）
> **关联**：[deep-research v2.0 §4.2 SGE 中保留价值 + §4.4 AiBeing 借鉴](../../deep-research/Cognitive-Digital-Twin-Deep-Research.md)

## 持久化

- SQLite + JSON（参考 SelfLab SGE TwinStateDB）
- Per-user 隔离
- 4 层记忆（Hawking 短期 / Crystallizer 中期 / Identity / Narrative）

## 长期会话

- ECOSSession 类（借鉴 SelfLab TwinSession + AiBeing chat_agent）
- 多轮对话状态维护
- 滚动 epoch 计数器
- session 期间状态驻内存

## 待填充章节

1. SQLite Schema 设计
2. 4 层记忆实现
3. ECOSSession 类接口
4. chunk 隔离（防止 6~12 年长跑状态丢失）
5. 数据迁移与备份
6. 隐私保护（端侧计算 + 差分隐私）

---

**创建日期**：2026-06-24
**维护者**：Bisen & Claude
