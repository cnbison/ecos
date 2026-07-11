# 战略转型记录：MVP → Product Demo

**日期**：2026-07-10
**参与者**：Bisen
**主题**：Phase 4 战略方向调整

---

## 转型背景

### 原方向：学校场景 + MVP 能用就行

初始 Phase 4 定位：
- **目标用户**：初中学生（学校场景）
- **MVP 原则**：能用就行，验证核心假设（H1: CTA 5D 预测力、H2: Bloom 可行性、H3: 双 Agent 抗幻觉）
- **交付物**：50-100 学生 × 4 周实验数据
- **风险**：需要合作学校招募、伦理审查、家长知情同意

### 新方向：Python 基础自学 + 完整产品 Demo

转型后的 Phase 4：
- **目标用户**：自学者（Bisen 作为第一个真实用户）+ 跨领域 Demo 展示
- **Demo 原则**：完整友好产品形态，7 组件全部可视化展示
- **交付物**：一键启动 + 可分发 Demo + 完整 UI + 教师/家长最小版
- **优势**：无需外部依赖，完整展示 ECOS 核心价值

---

## 为什么现在转型

1. **学校方向推进困难**：合作学校招募、伦理审查流程长，不适合当前阶段
2. **Python 基础 Demo 已跑通**：4-gate Demo + 跨领域 Demo 已验证核心闭环
3. **wu-ecos 的 7 组件设计**：比原 MVP 更有产品价值，需要完整展示
4. **用户可感知价值**：真实用户（而非实验学生）使用 Demo，反馈更直接

---

## 7 组件定义（wu-ecos 对齐）

| # | 组件 | 说明 |
|---|------|------|
| 1 | **5D mean + 协方差** | K/P/S/C/X 每维带置信度，不是单一数值 |
| 2 | **6 级 Bloom** | Remember → Understand → Apply → Analyze → Evaluate → Create |
| 3 | **TC 状态** | 阈值概念跨越（liminal → post_liminal）|
| 4 | **LearningDNA** | 学习者特征（input偏好/avoid模式）|
| 5 | **Trajectory** | A→B 成长轨迹历史 |
| 6 | **Misconceptions** | 各有置信度的 misconception 集合 |
| 7 | **overall_confidence** | CTA 对总状态估计的置信度 |

---

## Phase 4 M2-M5 Definition of Done

- [ ] `ecos/` Python 包完整实现
- [ ] Python 基础 Q 矩阵 26 道（L1-L6）
- [ ] TC 库 8 个 + Misconceptions 库 8 条
- [ ] LLM Judge + LLM Intervention 端点
- [ ] TC 检测器骨架
- [ ] 持久化层接入
- [ ] **Product Demo UI（学生端）**：7 组件完整展示
- [ ] **Product Demo UI（教师端）**：最小可用版
- [ ] 一键启动脚本 + 部署文档

---

## 与原 roadmap 的差异

| 维度 | 原 MVP | 新 Product Demo |
|------|--------|----------------|
| 用户 | 50-100 学生（学校）| 单用户自学者 |
| 范围 | 能用就行 | 完整产品形态 |
| Bloom | L1-L4 | L1-L6 |
| TC | 无 | 有（liminal 检测）|
| UI | 基础 | 7 组件完整展示 |
| 持久化 | 无 | 有（跨会话）|
| 教师端 | 无 | 最小版 |
| 部署 | 无 | 一键启动 |

---

## 待完成工作

详见 [README.md §下一步](../README.md)。

**文档变更**：
- README.md（已完成）
- CLAUDE.md（已完成）
- research/00-overview/03-roadmap.md（已完成 v1.2）
- research/90-mvp/ → research/90-demo/（待完成）
- research/00-overview/01-applications.md（待更新）
- research/00-overview/02-architecture.md（待更新）
