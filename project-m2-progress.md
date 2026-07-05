---
name: project-m2-progress
description: "ECOS M2 phase progress snapshot as of 2026-07-05 — Claude Skills Demo 验证通过，新方向：不依赖学校招募"
metadata:
  node_type: memory
  type: project
  originSessionId: d3feb773-611e-4ed2-839c-2b206e51bd9d
---

ECOS M2 阶段（Phase 4 MVP 实施）进度快照（截至 2026-07-05）：

| MVP Week | 任务 | 版本标签 | 状态 | commit |
|---|---|---|---|---|
| W1 | CTA 基础 (BKT + MIRT 5D + BeliefEngine) | v0.28.0 | ✅ | 5724e90 |
| W2 | LCA 策略 (LinUCB + Bjork + CLT + CA + rationale) | v0.30.0 | ✅ | 330b387 |
| W2 | Bloom 库 + TC 库 + Misconceptions 库 | v0.32.0 | ✅ | 30f3535 |
| W3 | LLM Critic 完整集成（3 类 prompt）| v0.32.0 | ✅ | 30f3535 |
| W3 | 持久化 (SQLite 6 张表 + ECOSSession + chunk) | v0.32.0 | ✅ | 6d3db0c |
| W3 | LLM Critic e2e 验证脚本 | v0.32.0 | ✅ 7/7 | 8590e57 |
| W4 | UI 学生端 + 教师端骨架 | v0.33.0 | ✅ | bf536b0 |
| W4 | 双 Agent 互校 | v0.31.0 | ✅ | 7628834 |
| W5 | Q 矩阵协作模板 | — | ✅ | e1a2adc |
| W5 | Claude Skills 领域库 + library_str 注入 | v0.34.0 | ✅ | aa54341 |
| W5 | Claude Skills Demo Round 1-3 闭环验证 | — | ✅ | b841aff |
| W5 | strip_think_blocks 修复（贪婪匹配）| — | ✅ | 3dea91a |
| W6+ | Demo 深化（M3-M5 全清除 + Bloom L1→L4）| — | 🔜 进行中 | — |
| W6+ | 跨领域 Demo（注入新领域 misconception 库）| — | 🔜 待开始 | — |
| W6 | 教师协作（TC/Misc 审核）| — | 🔜 待开始 | — |
| W6 | 合作学校招募 + 家长同意书 | — | 🔜 待开始 | — |
| W7-8 | Beta 测试（10-20 学生）| — | 待办 | — |
| W9-10 | 正式实验 + 评估 | — | 待办 | — |

**战略调整（2026-07-05）**：

ECOS 是**领域无关**的，Claude Skills Demo 证明核心价值无需等待学校招募即可验证。
新路径：自我演示 + 跨领域泛化 → 学校招募并行推进（不阻塞工程）。

**下一步工程任务（不依赖学校）**：
1. Claude Skills M3-M5 misconception 完整清除（Hook/MCP、Prompt 模板、概率性加载）
2. Bloom L1→L4 路径完整验证（4-gate 达标检测）
3. TC_skill 跨越验证（LLM 直接评估）
4. 跨领域 Demo（快速注入新领域，如"批判性思维"或"编程初学者"）
5. Demo 完整报告（用于对外展示 ECOS 价值）

**相关文件**：
- `discussions/2026-07-05-claude-skills-demo-round1-3.md` — Demo 存档
- `research/90-mvp/ECOS-Cognitive-Intervention-Workflow.md` — 认知干预工作流
- `research/00-overview/03-roadmap.md §2.4` — 新战略路径说明
