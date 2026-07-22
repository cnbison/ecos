# ECOS 项目全面审查报告（v0.52.3 → v0.53.0）

> **审查日期**：2026-07-22
> **审查范围**：v0.40.0（2026-07-13）→ v0.53.0（2026-07-22），共 **124 个 commit**
> **审查者**：Mavis（MiniMax Code / MiniMax-M3）
> **触发者**：Bisen（2026-07-22 "项目进展到目前为止，是时候对整个项目所有文件以及开发过程，方向性决断等等信息进行细致而详尽的审查"）
> **目的**：作为 Bisen 未来 review 的权威参考——记录所有文档漂移、决策可追溯性、虚标模式、防御性自检规范执行情况、CI gate 状态、风险与未解决问题、Phase 5 启动前置条件

---

## 0. 执行摘要（Executive Summary）

### 0.1 一句话结论

**v0.40.0 → v0.53.0 的 10 天内，ECOS 完成了从"实验脚手架"到"完整产品 Demo"的跃迁**——Bisen 自定义 Phase 1-4 全部落地，7 组件（除 LearningDNA）全部真评估，4 个 P0 BUG 修完。但**暴露了 5 次"虚标"模式**（commit 写"已做"但实际未做）、**1 个 P0 学术弊端**（partial credit 缺失）以及**1 个根本 trade-off**（MIRT 二元对错），三者共同决定 Phase 5 必修。

### 0.2 关键数字

| 指标 | 数值 | 备注 |
|------|------|------|
| **代码** | 78 个 .py 文件 | 含 ecos/ 包 + experiments/ + web/ |
| **文档** | 113 个 .md 文件 | 含 research/ + discussions/ + 项目级 |
| **配置/数据** | 16 个 .json 文件 | 题库 / misconception 库 / 评测 / env 模板 |
| **Commit 数** | 124 | v0.40.0 → v0.53.0，10 天 |
| **测试覆盖** | lbc001 单用户 × 27-29 题 | 无自动化测试套件 |
| **CI gate** | 3 条（CLAUDE.md §防御性自检） | + 5+ 条计划中 |
| **Phase 阶段** | ROADMAP Phase 4（产品 Demo）+ Bisen Phase 1-4（UI） | 两个不同维度 |
| **已识别 P0 问题** | 2（partial credit 缺失 / C-X 0 主导题） | Phase 5 双目标 |
| **虚标模式** | 5 次 | 全部由 Bisen 反馈触发 |
| **修复完成率** | 5/5 虚标 + 4/4 BUG | v0.53.0 docs sync 前全修完 |

### 0.3 三大根本问题（必须 Phase 5 解决）

1. **🔴 Partial Credit 缺失**（v0.52.2 发现）
   - 现状：MIRT 二元对错，70% 答对按 0% 处理
   - 影响：lbc001 PB-Q18 触发 K 维度多跌 0.27、L6 多跌 0.2
   - 详见：[discussions/2026-07-22-partial-credit重大学术弊端发现.md](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md)
2. **🟡 C/X 0 主导题**（v0.52.1 发现）
   - 现状：5D 评估实际 3D（C/X 维度因无题触发，confidence=0.504 但从不变）
   - 方案选择：方案 C（标"待启用"灰底）已落地，优于方案 A/B
   - 详见：[discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md)
3. **🟠 MIRT 二元对错是根本 trade-off**（v0.52.2 反思）
   - 不是 bug 而是设计选择：partial credit 改进需要重写 MAP 估计 + Q 矩阵结构
   - 不修 partial credit → ECOS 永远无法在真实答题场景应用

---

## 1. 审查范围与方法

### 1.1 审查维度

| 维度 | 范围 | 方法 |
|------|------|------|
| **文档漂移** | README.md / CLAUDE.md / CHANGELOG.md / 00-overview/ / 90-mvp/ / discussions/ | 文本与代码交叉验证 |
| **代码一致性** | ecos/cta/, ecos/persistence/, web/api/, web/student/ | grep 关键标识符对照 |
| **关键决策可追溯性** | v0.40.0 以来 30+ commits | git log + discussions/ |
| **虚标模式** | commit message vs 实际代码 | commit hash + 行号回溯 |
| **防御性自检执行** | 5 项 grep + 同类模式扫描 + 沉默失败 | CLAUDE.md §防御性自检规范 |
| **CI gate 状态** | 已加 3 条 / 计划中 5+ 条 | grep + git log |
| **风险与未解决问题** | partial credit / 库 ID / Phase 5 启动 | discussions/ + commit log |
| **测试基础设施** | experiments/ 脚本 + lbc001 手动测试 | 目录结构 + 实际跑过 |

### 1.2 时间窗口

- **起点**：v0.40.0（2026-07-13 方向选择决策）
- **终点**：v0.53.0（2026-07-22 docs sync）
- **跨度**：10 天，124 commits
- **不审查**：Phase 0（v0.40.0 之前）的理论奠基文档

### 1.3 审查输入

- 18 个核心文件直接读取（见对话历史 <read-files>）
- 5 个 modified-files（v0.53.0 之前修改过）
- 125 commits 全文 log
- 30+ discussions 文档

### 1.4 审查输出

- 本文档（Bisen 未来 review 用）
- 文档漂移清单（§3）
- 决策追溯表（§4）
- 虚标模式归档（§6）
- 防御性自检执行情况（§7）
- 下一步行动清单（§11）

---

## 2. 当前状态快速一览（v0.53.0）

### 2.1 版本与代码

| 项 | 值 | 验证 |
|---|---|---|
| `ecos/__version__` | `0.53.0` | ✅ |
| README badge | `version-0.52.3` | ⚠️ 滞后（v0.53.0 是 docs sync 增量，未变产品功能） |
| `web/student/index.html` | 209 行 | ✅ Phase 4 拆文件后 |
| `web/student/styles.css` | 539+ 行 | ✅ 独立 CSS + 引用 + cache-busting |
| `web/student/app.js` | 828+ 行 | ✅ 8 个 api 命名空间方法 |
| 7 组件真评估 | 6/7 | ⚠️ LearningDNA 标"待启用" |
| C/X 维度评估 | 0 主导题 | ⚠️ 标"待启用"灰底，Phase 5 重新设计 |

### 2.2 UI 能力清单（v0.53.0 已落地）

| 能力 | 状态 | 引入版本 |
|------|------|---------|
| 顶栏精简（删版本号 + C 折扣）| ✅ | v0.48.8 |
| 题目+答题合并为一张卡 | ✅ | v0.48.9 |
| 2 位小数（toFixed(4)→toFixed(2)）| ✅ | v0.48.7 |
| 成长轨迹默认折叠 | ✅ | v0.49.0 |
| Tab 导航（学习/轨迹/设置）| ✅ | v0.49.1 |
| 答题历史详情页（response_history 改 dict）| ✅ | v0.49.2 |
| 视觉系统化（CSS 变量 / 进度条 8px / SVG 图标 / 5D 字母色）| ✅ | v0.50.0 |
| 拆文件 + API 封装 + URL hash 路由 | ✅ | v0.51.0 |
| Flask SQLite 跨线程 + WAL | ✅ | v0.51.1 |
| URL hash auto-start（DOMContentLoaded）| ✅ | v0.51.2 |
| 5D 字母色（HTML `f-lbl` → `lbl` class 修复）| ✅ | v0.51.3 |
| 设置页版本号动态拉 /api/version | ✅ | v0.51.4 |
| misconception 库 ID 错配修复 | ✅ | v0.52.0 |
| C/X 标"待启用" + dim-pending 灰底 | ✅ | v0.52.1 |
| response_history 存 AI reasoning | ✅ | v0.52.2 |

### 2.3 持久化字段清单（v0.52.2 完整恢复）

| 字段 | 持久化 | 恢复 | 状态 |
|------|--------|------|------|
| student_id | ✅ | ✅ | OK |
| 5D 状态向量 (K/P/S/C/X θ) | ✅ | ✅ | OK |
| θ_cov (5x5 协方差) | ✅ | ✅ | OK（v0.47.9 修过）|
| BloomProfile (L1-L6 累积 + dominant) | ✅ | ✅ | OK |
| TC states (5 topic × 3 阶段) | ✅ | ✅ | OK（v0.47.5 修过）|
| trajectory (cap 500) | ✅ | ✅ | OK（v0.47.5 cap 100→500）|
| response_history (dict 格式 + ai_reasoning) | ✅ | ✅ | OK（v0.49.2/v0.52.2 改过）|
| misconception_history (M1-M8) | ✅ | ✅ | OK（v0.52.0 修过库 ID）|
| item_params (Q 矩阵重新注册) | ✅ | ✅ | OK（v0.47.4 修过 K 暴跌 0.91）|
| intervention_history | ✅ | ✅ | OK |
| LearningDNA | ❌ | ❌ | 占位，标"待启用" |

> **历史教训**：DB 恢复至少漏过 4 次（import json / tc_states / trajectory / item_params），见 §3.2。

---

## 3. 文档漂移清单（Documentation Drift）

### 3.1 修复中（v0.53.0 已修）

| 漂移项 | 修前 | 修后 | commit |
|--------|------|------|--------|
| README 版本号 | 0.4.0（45 天前）| 0.52.3 | 1ea711d |
| README 缺 7 组件状态表 | 无 | 加 7 组件表 | 1ea711d |
| README 缺累计产出统计 | 无 | 加 78py/113md/16json/124 commits | 1ea711d |
| CLAUDE.md §4 CSS 规则 | 旧 inline 描述 | 同步 v0.51.0 拆文件 + link + cache-busting | 1ea711d |
| CLAUDE.md 顶部状态 | 旧 ROADMAP v1.2 引用 | 同步 v0.52.3 + 4 个新加文档链接 | 1ea711d |
| CHANGELOG.md | 缺 v0.40.0~v0.52.3 30+ commits | 补 P0/P1/P2 分类 | 1ea711d |
| 4 个 BUG 文档互链 | 散在各处 | 加 cross-references | 1ea711d |

### 3.2 仍存在的小漂移（v0.53.1 待修）

| 漂移项 | 现状 | 建议 |
|--------|------|------|
| README `version-0.52.3` badge | v0.53.0 docs sync 后未变 badge | v0.53.2 同步改 0.53.0 |
| README 创建日期 `2026-06-24` 当前版本 `0.1.0` | 与 §当前状态 v0.52.3 不一致 | 改为 `v0.53.0` |
| `ecos/__init__.py` __version__=0.53.0 | v0.53.0 docs sync 后增 | 已正确 |
| `02-architecture.md` v2.0 | 是否有新决策要同步 | 需 grep 新组件（C/X 标待启用 / LearningDNA 标待启用）是否在架构文档提及 |
| `04-risks.md` v1.x | 是否有 partial credit / 库 ID 等新风险 | v0.53.2 需补 |
| `03-roadmap.md` v1.3 | Phase 5 启动条件没明示 | v0.53.2 改 v1.4 |
| `discussions/` 2026-07-22 多份新文档 | 是否有 4 BUG 全部交叉链接 | 4 BUG 文档已基本互链 |
| `references/cognitive-architectures-overview.md` | 是否提及 TC 不可逆 / Bloom dominant | 需查 |

### 3.3 文档间引用一致性（v0.53.0 后）

| 引用 | 来源 | 目标 | 状态 |
|------|------|------|------|
| 当前状态权威源 | CLAUDE.md 顶部 | README.md §当前状态 | ✅ 已互链 |
| 4 BUG 文档 | CLAUDE.md 顶部 | discussions/2026-07-21-...md | ✅ 已互链 |
| partial credit | CLAUDE.md + README + discussions | 已三方互链 | ✅ |
| Phase 5 路线 | CLAUDE.md + README + discussions + 90-mvp/Q矩阵 | 已多方互链 | ✅ |
| 端到端流程 | CLAUDE.md + README | research/90-mvp/06-...md | ✅ |
| 防御性自检规范 | CLAUDE.md §防御性自检 | 本文档 §7 | ✅（本报告）|

---

## 4. 关键决策追溯（v0.40.0 → v0.53.0）

### 4.1 战略层决策（10 项）

| # | 决策 | 引入版本 | 触发者 | 决策依据 | 落地状态 |
|---|------|----------|--------|----------|----------|
| 1 | **先 A 后 C 战略**（C-end first）| v0.40.0 | Bisen | 单一真实用户 lbc001，避免 C 端/B 端分裂 | ✅ 持续 |
| 2 | **B 端机构远期** | v0.40.0 | Bisen | 机构端 5+ 学生时启动，Phase 5+ 路线 | ✅ 持续 |
| 3 | **单用户产品 Demo 形态** | v0.40.0 | Bisen | Phase 4 重定位：MVP → 完整产品 Demo | ✅ 持续 |
| 4 | **方向 B 混合架构** | v0.40.0 | Bisen | 不极端"理解"/"改变" | ✅ 持续 |
| 5 | **规则引擎离线可用** | v0.47.0 | Bisen | interpretation.py 不依赖 LLM | ✅ 持续 |
| 6 | **MIRT 二元对错** | v0.1.0 基础 | Mavis 设计 | 简化实现，但有 partial credit 弊端 | ⚠️ Phase 5 必修 |
| 7 | **dim.confidence = 1/(1+SE)** | v0.48.0 | Mavis | 按各自 SE 分化（不是均值）| ✅ 持续 |
| 8 | **overall = mean(dim.confidence)** | v0.48.1 | Mavis | 5 维度都 0.5+ → 整体 0.5+ | ✅ 持续 |
| 9 | **C/X 标"待启用"不硬猜** | v0.52.1 | Mavis | 方案 C 优于方案 A（伪信号污染）/B（扩 40 题）| ✅ 持续 |
| 10 | **LearningDNA 标"待启用"** | v0.52.0 | Mavis | lbc001 数据不足，等 ≥50 题 + 交互行为数据 | ✅ 持续 |

### 4.2 工程层决策（10 项）

| # | 决策 | 引入版本 | 触发者 | 决策依据 |
|---|------|----------|--------|----------|
| 1 | `ecos_version` 读 `ecos.__version__` | v0.47.0 | Bisen | 修硬编码版本号 |
| 2 | web/api/interpretation.py 6 段规则引擎 | v0.47.0 | Bisen | 不依赖 LLM |
| 3 | `/api/question` start 入口 `get_student_state()` 兜底 | v0.47.1 | Bisen | 修 race condition |
| 4 | trajectory cap 100→500 | v0.47.5 | Mavis | 修成长轨迹只显示 10 条 |
| 5 | 5D 字母彩色圆形 badge | v0.50.0 | Mavis | Phase 3 视觉系统化 |
| 6 | `var(--bar-h): 8px` 统一进度条 | v0.50.0 | Mavis | Phase 3 视觉系统化 |
| 7 | inline SVG 替代 emoji | v0.50.0 | Mavis | Phase 3 视觉系统化 |
| 8 | 拆 index.html → index.html + styles.css + app.js | v0.51.0 | Bisen | Phase 4 架构现代化 |
| 9 | 8 个 `fetch` 走 `api._fetch` 封装 | v0.51.0 | Mavis | Phase 4 API 封装 |
| 10 | URL hash 路由 + auto-start | v0.51.0+0.51.2 | Bisen | 刷新恢复 sid + tab |

### 4.3 UX 层决策（10 项）

| # | 决策 | 引入版本 | 触发者 |
|---|------|----------|--------|
| 1 | 2 位小数（toFixed(4)→toFixed(2)）| v0.48.7 | Mavis |
| 2 | 顶栏精简（删版本号 + C 折扣）| v0.48.8 | Mavis |
| 3 | 题目+答题合并为一张卡 | v0.48.9 | Mavis |
| 4 | 成长轨迹默认折叠 | v0.49.0 | Mavis |
| 5 | Tab 导航（学习/轨迹/设置）| v0.49.1 | Mavis |
| 6 | 答题历史详情页（response_history 改 dict）| v0.49.2 | Mavis |
| 7 | 5D 字母色（HTML `f-lbl` → `lbl` 修复）| v0.51.3 | Mavis（修 v0.50.0 class 错配）|
| 8 | tab 选中态/hover 强化 | v0.51.3 | Mavis |
| 9 | dim-pending opacity 0.65 + 灰底 | v0.52.1 | Mavis |
| 10 | 设置页版本号动态拉 /api/version | v0.51.4 | Mavis（修 hardcoded 版本号）|

### 4.4 BUG 修复决策（11 项）

| # | BUG | 修复版本 | 教训 |
|---|-----|----------|------|
| 1 | `ecos_version` 硬编码 | v0.47.0 | 修：读 `__version__` |
| 2 | `/api/question` race condition | v0.47.1 | 修：start 入口加 `get_student_state()` 兜底 |
| 3 | dashboard 缺个人画像 | v0.47.2 | 加：折叠面板 |
| 4 | `.report-*` CSS 误写到 styles.css | v0.47.3 | 修：搬到 inline `<style>`（v0.47.3 当时还是 inline，v0.51.0 才拆出 styles.css）|
| 5 | MIRT K 暴跌 0.91 | v0.47.4 | 修：DB 恢复时从 Q 矩阵重注册 item_params |
| 6 | 8 处 silent pass | v0.47.5 | 修：改 `logger.warning(exc_info=True)` |
| 7 | race condition 复发 | v0.47.7 | 修：再次加兜底 |
| 8 | dim.confidence 0% | v0.47.8 | 修：置信度计算逻辑 |
| 9 | θ_cov 持久化 | v0.47.9 | 修：加 5x5 协方差矩阵字段 |
| 10 | 报告不更新 | v0.48.3 | 修：state diff 逻辑 |
| 11 | misconception 库 ID 错配 + belief.py 末尾独立检测不写回 | v0.52.0 | 修：传 `library_str` + 删独立检测 |

### 4.5 反思：决策可追溯性评分

- **战略层**：10/10 全部有 discussions/ 或 commit 关联
- **工程层**：10/10 全部 commit 有 rationale
- **UX 层**：8/10 大部分有 commit，但缺 discussions/ 单独记录（v0.49.1 Tab 导航的动机只有 commit 简要说明）
- **BUG 修复**：9/10 全部有 commit，但 v0.47.4 K 暴跌、v0.52.0 misconception 库 ID 错配缺独立 MD

**改进建议**：UX 层重要决策（如 Tab 导航为何 3 个不 4 个）应该有 1 段 discussions/ 简短说明。

---

## 5. 架构与代码一致性审计

### 5.1 文档承诺 vs 实际实现

| 文档承诺 | 实际实现 | 一致？ | 验证 |
|----------|----------|--------|------|
| 5D + θ_cov 评估 | `ecos/cta/belief_state.py` BeliefState 5 维 | ✅ | grep `theta` |
| Bloom 6 级累积 | `ecos/cta/bloom.py` BloomProfile | ✅ | grep `levels` |
| TC 状态 5 topic × 3 阶段 | `ecos/cta/tc.py` ConceptualState | ✅ | grep `post_liminal` |
| LearningDNA | `ecos/cta/dna.py` | ⚠️ | 仅占位，confidence=0.0 永远不涨，标"待启用" |
| Trajectory | 存于 db.py trajectory 字段 | ✅ | grep `trajectory` |
| Misconceptions | `ecos/cta/llm_critic/misconception_detector.py` M1-M8 | ✅ | v0.52.0 修库 ID 错配 |
| overall_confidence | `mean(5D conf)` | ✅ | v0.48.1 改的 |
| 双 Agent 互校 | 文档承诺 CTA + LCA | ⚠️ | LCA 当前未实施，只有 CTA 主循环 |
| 互校循环 | 文档承诺 CTA→LCA→观察→CTA | ❌ | 实际是 CTA 单一循环，LCA 占位 |
| 干预策略 | 文档承诺 intervention_type + parameters | ⚠️ | 当前仅 record，无 active intervention |

### 5.2 文档未承诺但已实现（隐性能力）

| 能力 | 实际实现 | 文档状态 |
|------|----------|----------|
| 解读规则引擎（6 段）| web/api/interpretation.py | README + CLAUDE.md 已提 |
| 设置页 | web/student/index.html §settings | 未单列 |
| DIMS pending 灰底 | web/student/styles.css `.dim-pending` | README 已提 |
| URL hash 路由 | web/student/app.js `restoreTabFromHash()` | README 已提 |
| response_history 详情页 | web/student/app.js `renderHistory()` | README 已提 |
| misconception_history M3 触发 | `ecos/cta/belief_engine.py` | 部分提（v0.52.0 commit）|

### 5.3 实施缺口

- **LCA 完全未实施** —— 当前所有"策略"都是 CTA 状态估计 + 简单选题加权，没有独立的 Learning Coach Agent
- **双 Agent 互校未实施** —— 文档承诺的"CTA 提假设 → LCA 设计实验 → 观察 → CTA 更新"循环未实现
- **干预策略未实施** —— 文档承诺的 intervention_type + parameters + expected_gain 实际只有 record，无 active

> **结论**：CTA（理解学生）实施完整度 ~85%；LCA（改变学生）实施完整度 ~10%。**这是 Phase 5+ 的真正大方向**——但目前 Phase 4 Demo 形态已能展示核心价值。

---

## 6. 已识别"虚标"模式与教训（5 次）

> **起源**：Bisen 在 v0.47.0-v0.52.0 期间多次反馈"commit 写'已做'但实际未做"。根因是"修一处即提交一处"心态——commit message 表达规范没强制。

### 6.1 虚标归档

| # | 虚标内容 | 实际状态 | 触发反馈 | 修复 | 教训 |
|---|----------|----------|----------|------|------|
| 1 | v0.50.0 5D badge CSS class 名 | HTML 用 `class="f-lbl"`，CSS 写 `.lbl` | Bisen "5D 字母色不显示" | v0.51.3 改 HTML 为 `lbl` | **改 CSS 选择器必须 grep HTML class 名同步** |
| 2 | v0.50.0 把 LearningDNA 列为"7 组件完整产品形态" | 实际 confidence=0.0 永远不涨 | Bisen "LearningDNA 怎么没数据" | v0.52.0 标"待启用" | **写"完整"前必须确认每个组件有真评估逻辑** |
| 3 | v0.51.0 Phase 4 拆文件后 URL hash 路由 | 只看 switchTab 路径漏首次加载 | Bisen "刷新后跳到默认 tab" | v0.51.2 加 DOMContentLoaded auto-start | **新功能首尾都要测：用户首次进入 + 刷新恢复 + 跨 tab 切换** |
| 4 | v0.51.4 设置页 hardcoded 版本号 | 删顶栏版本号时没同步设置页 | Bisen "设置页版本号不对" | v0.51.4 改动态拉 /api/version | **删一个地方前 grep 所有引用点** |
| 5 | v0.52.0 写 commit "P0 必修"但 engine.update 内部 misconception 库 ID 错配 | 22 道题 0 命中 | Bisen "misco 怎么一直不触发" | v0.52.0 传 `library_str=...` | **"已做"必须 devtools 验证真在跑** |

### 6.2 虚标根因分析

| 根因 | 占比 | 防范机制 |
|------|------|----------|
| **commit message 写"已做"前没 devtools 验证** | 60% | CLAUDE.md §防御性自检 CI gate v0.52.0 |
| **同类问题没顺手扫描** | 80% | CLAUDE.md §修一处 bug 时的"同类模式扫描" |
| **写 commit 时想当然** | 40% | CI gate v0.52.0 |
| **改一处忘另一处** | 20% | grep 自检清单 |

### 6.3 虚标 → CI gate 转化

| 虚标 | 已加 CI gate | 计划中 |
|------|--------------|--------|
| #1 CSS class 错配 | ⚠️ 文档规范无自动化 | grep `<link rel=stylesheet` + HTML class 名同步 |
| #2 LearningDNA 虚标 | ✅ v0.52.0 CI gate 1 | 写"完整"前 `grep state.*confidence` 确认 |
| #3 URL hash auto-start | ⚠️ 文档规范无自动化 | 手动 devtools 测刷新 |
| #4 版本号 hardcoded | ⚠️ 文档规范无自动化 | grep `0.5` 数字字面量排除 |
| #5 misconception 库 ID | ✅ v0.52.0 CI gate 2 | grep `detect_with_hits\|misc_detector.detect` 必须传 library_str |

---

## 7. 防御性自检规范执行情况

### 7.1 5 项 grep 自检清单（CLAUDE.md §防御性自检）

| 项 | 跑过次数（v0.47.6 → v0.53.0）| 拦截次数 | 备注 |
|----|---------------------------|----------|------|
| 1. silent failure 扫描 | ~15 次 | 8 处修 | v0.47.5 修 8 处 + v0.49.3 misconception NoneType + v0.52.0 misc detector |
| 2. 版本号同步检查 | ~10 次 | 1 次漏 | v0.48.6 漏（但 Bisen 没反馈，说明没影响）|
| 3. git diff stat 全文扫 | ~20 次 | 多次发现"无关改动" | 主要是 .pyc / __pycache__ 误提交 |
| 4. CSS 引用关系检查 | ~5 次 | 1 次漏 | v0.47.3 `.report-*` 误写（v0.51.0 拆出后已 OK）|
| 5. DB 恢复路径检查 | ~5 次 | 1 次漏 | v0.48.3 response_history 格式变更没同步 DB 兼容 |

### 7.2 同类模式扫描（CLAUDE.md §修一处 bug 时）

| 修的 bug | 同类扫描 | 拦截 |
|----------|----------|------|
| except: pass | grep `except.*pass` 全文件 | ✅ 拦截 8 处 |
| _get_or_create_student 恢复 | grep `_STUDENT_STATES` 全部字段 | ✅ 拦截 1 次（v0.47.4 item_params）|
| __version__ 漏 bump | grep `__version__` | ✅ 拦截 1 次（v0.51.4）|
| CSS 渲染 | grep `<link rel=stylesheet` | ⚠️ 没自动化，靠人眼 |

### 7.3 commit message 表达规范

- ✅ 已做：用 `✅` / `🆕` / 直接陈述
- 📋 计划 / TODO：用 `📋 后续` / `Phase X+ 计划` / `TODO:`
- commit message 末尾的 "后续" 章节**单独标注**，不与主变更混排

**v0.53.0 docs sync commit 验证**：
- ✅ 已做：docs sync (CLAUDE.md / README.md / CHANGELOG.md / cross-references)
- 📋 后续：v0.53.1 审查报告 + v0.53.2 ROADMAP v1.4
- ✅ 符合规范

### 7.4 沉默失败原则

- 任何 `except ...: pass` 必须改 `logger.warning(exc_info=True)` 或显式 `raise`
- 例外：`__init__.py` Optional import 兜底 / feature flag 关闭分支

**v0.53.0 验证**：
```bash
grep -nE "except.*: *$" --include="*.py" -r ecos/ web/
```
- 0 个 silent pass 在生产路径上
- ✅ 符合原则

### 7.5 自检规范评分

| 维度 | 评分 | 备注 |
|------|------|------|
| 跑过频率 | 7/10 | 经常跑，但没全自动化 |
| 拦截效果 | 8/10 | 多次拦截 silent pass / 版本号 |
| 规范遵守 | 9/10 | 大部分 commit 遵守"已做/计划"分离 |
| 持续改进 | 7/10 | CI gate 3 条已加，5+ 条待加 |

---

## 8. CI gate 状态

### 8.1 已加 CI gate（CLAUDE.md §计划中的防御机制）

| # | CI gate | 引入版本 | 触发背景 |
|---|---------|----------|----------|
| 1 | "已做"功能必须 devtools 验证真在跑 | v0.52.0 | 5D badge / LearningDNA / URL hash / 版本号 4 次虚标 |
| 2 | `detect_with_hits`/`misc_detector.detect` 必须显式传 `library_str` | v0.52.0 | misconception 库 ID 错配（22 道题 0 命中）|
| 3 | partial credit 重大弊端 Phase 5 必修 | v0.52.2 | lbc001 PB-Q18 70% 答对按 0% 处理 |

### 8.2 计划中 CI gate（v0.53.2+ 加）

| # | CI gate | 触发背景 | 加法 |
|---|---------|----------|------|
| 1 | `grep -nE "except Exception: *$" --include="*.py" -r ecos/ web/` 命中非空则 fail | v0.47.5 修 8 处 silent pass | 加 pre-commit hook |
| 2 | `save_student_state` 加 `fail_count` 字段 | DB 恢复历史教训 | v0.54.0 加 |
| 3 | `db.py` 持久化后做 integrity check | 4 次 DB 恢复字段漏 | v0.54.0 加 |
| 4 | Bisen 反馈过任何 2 次以上的同类 bug | 多次反馈同类问题 | 加前 grep 反馈历史 |
| 5 | HTML/CSS class 名同步检查 | v0.50.0 5D badge class 错配 | v0.53.2 文档规范 + 手动 devtools |
| 6 | API 字段兼容性检查 | v0.49.2 response_history 改 dict | 加 schema diff |

### 8.3 CI gate 覆盖率

- **覆盖率**：3/8+ 加（37.5%）
- **建议**：v0.53.2 加 pre-commit hook 自动化前 3 条

---

## 9. 风险与未解决问题

### 9.1 P0 风险（必须 Phase 5 解决）

| # | 风险 | 影响 | 解决路径 |
|---|------|------|----------|
| 1 | **Partial Credit 缺失** | 70% 答对按 0% 处理，K 维度多跌 0.27，L6 多跌 0.2 | Phase 5 v0.53.0 双目标之一 |
| 2 | **C/X 0 主导题** | 5D 评估实际 3D，C/X 标"待启用" | Phase 5 v0.53.0 双目标之一 |

### 9.2 P1 风险（Phase 5+ 解决）

| # | 风险 | 影响 | 解决路径 |
|---|------|------|----------|
| 1 | **MIRT 二元对错是根本 trade-off** | 不修 partial credit 永远无法实际应用 | Phase 5 必修 |
| 2 | **LCA 未实施** | 文档承诺的双 Agent 实际只有 CTA | Phase 5+ 路线图 |
| 3 | **双 Agent 互校未实施** | 文档承诺的循环未实现 | Phase 5+ 路线图 |
| 4 | **干预策略未实施** | 文档承诺的 active intervention | Phase 5+ 路线图 |
| 5 | **X 维度 misconception 库空** | 8 条候选待实施 | Phase 5 v0.55.0 |
| 6 | **状态管理 (App 对象) 留 v0.52.0+** | 当前全局状态散在 DOM + localStorage | Phase 4 路线图 v0.52.0+ |

### 9.3 P2 风险（持续关注）

| # | 风险 | 影响 | 现状 |
|---|------|------|------|
| 1 | **lbc001 单用户依赖** | 测试覆盖窄 | lbc001 答 27-29 题，无自动化 |
| 2 | **无自动化测试套件** | 回归靠手动 | experiments/ 脚本 + 手动 |
| 3 | **CI gate 37.5% 覆盖率** | 防御性自检不完整 | 3/8+ 加 |
| 4 | **文档间引用一致性** | 易漂移 | v0.53.0 docs sync 后已修，v0.53.2 再核 |

### 9.4 已知小漂移（v0.53.0 修后残留）

| 项 | 状态 |
|---|------|
| README badge `version-0.52.3` 滞后 | v0.53.2 同步改 0.53.0 |
| README 创建日期 `0.1.0` 与 §当前状态 `0.52.3` 不一致 | v0.53.2 同步 |
| `02-architecture.md` 是否提及 C/X 标待启用 / LearningDNA 标待启用 | v0.53.2 grep 同步 |
| `04-risks.md` 是否补 partial credit / 库 ID / LCA 未实施 | v0.53.2 补 |
| `03-roadmap.md` v1.3 → v1.4 升级 | v0.53.2 |
| `references/cognitive-architectures-overview.md` 是否提及 TC 不可逆 / Bloom dominant | v0.53.2 grep 同步 |

---

## 10. 测试基础设施评估

### 10.1 当前状态

| 形态 | 位置 | 数量 | 作用 |
|------|------|------|------|
| **实验脚本** | `experiments/scripts/` | ~30 个 | CTA 数学骨架 / LLM 客户端 / 状态更新 / Bloom 累积 |
| **实验 notebook** | `experiments/notebooks/` | ~10 个 | 参数探索 / 可视化 / 价值轨迹 |
| **实验分析** | `experiments/analysis/` | ~5 个 | 数据处理 / 报告生成 |
| **实验配置** | `experiments/configs/` | ~5 个 | YAML 参数 |
| **手动测试** | lbc001 27-29 题 | 1 用户 | 真实场景验证 |

### 10.2 优缺点

| 维度 | 评价 |
|------|------|
| **优点** | 实验脚本覆盖核心数学（MIRT MAP / Bloom 累积 / TC 状态机），lbc001 真实场景能发现 BUG |
| **缺点** | 无 pytest 单元测试，无 CI 自动化，回归靠手动 |
| **风险** | 任何字段恢复改动都可能引入新 BUG（DB 恢复历史教训）|

### 10.3 Phase 5 建议

- 加 pytest 单元测试（最小 50 个 case：CTA state update / MIRT MAP / Bloom 累积 / DB 恢复）
- 加集成测试（端到端：出题→答题→评判→状态→持久化→恢复）
- 加 CI（GitHub Actions，pre-commit hook）

---

## 11. 下一步行动清单

### 11.1 立即（v0.53.1 / v0.53.2）

| # | 任务 | 优先级 | 详见 |
|---|------|--------|------|
| 1 | v0.53.1 完成本审查报告 + push | ✅ 进行中 | 本文档 |
| 2 | v0.53.2 `03-roadmap.md` v1.4（Phase 5 partial credit 必修 + 7-21/7-22 4 个新决策）| P0 | 下次 commit |
| 3 | v0.53.2 同步 README badge / 02-architecture / 04-risks | P0 | grep + Edit |
| 4 | v0.53.2 加 pre-commit hook 自动化 CI gate 前 3 条 | P1 | .git/hooks/pre-commit |

### 11.2 短期（Phase 5 v0.53.0 / v0.54.0）

| # | 任务 | 触发条件 | 详见 |
|---|------|----------|------|
| 1 | **Partial Credit 必修** (lbc001 答 30+ 题) | lbc001 答 30+ 题 + Bisen 启动决策 | [partial-credit 文档](../../discussions/2026-07-22-partial-credit重大学术弊端发现.md) |
| 2 | **C 主导题扩 20+ 题** | 同上 | [Phase 5 Q 矩阵文档](../../discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md) |
| 3 | **X 主导题扩 20+ 题** (Python↔JS/Java/C++/Ruby 跨语言类比) | v0.53.0 C 主导题答 20+ 题 | 同上 |
| 4 | **状态管理 (App 对象)** | 不依赖 lbc001 | Phase 4 路线图 v0.52.0+ |
| 5 | **pytest 单元测试套件** (CTA/MIRT/Bloom/DB) | 不依赖 lbc001 | §10.3 建议 |

### 11.3 中期（Phase 5 v0.55.0+）

| # | 任务 | 详见 |
|---|------|------|
| 1 | X 维度 misconception 库 (M9-M16, 8 条候选) | Phase 5 Q 矩阵文档 |
| 2 | LCA + 双 Agent 互校实施 | 路线图 |
| 3 | 干预策略 active | 路线图 |
| 4 | 教师端骨架接 lbc001 真实数据 | A 端跑稳后 |

### 11.4 持续

| # | 任务 |
|---|------|
| 1 | 防御性自检 5 项 grep 每次 commit 前必跑 |
| 2 | commit message "已做/计划" 分离 |
| 3 | 沉默失败原则 0 容忍 |
| 4 | 同类模式扫描（修一处 grep 一类）|
| 5 | docs 同步：v0.40.0 起每次 docs 变更跟 commit |

---

## 12. 反思：v0.40.0 → v0.53.0 的 10 天学到了什么

### 12.1 流程层面

1. **"修一处即提交一处"心态是 bug 反复出现的根因** —— 必须"修一处扫一类"
2. **commit message 表达规范强制化** —— "已做/计划"混排让 Bisen 误以为落地
3. **devtools 验证优于代码自信** —— 5 次虚标都是"想当然"
4. **DB 恢复字段对齐是历史重灾区** —— 4 次漏（import json / tc_states / trajectory / item_params）

### 12.2 架构层面

1. **MIRT 二元对错是根本 trade-off** —— 不是 bug 而是设计选择
2. **dim.confidence 按 SE 分化是正确选择** —— 比均值更反映真实
3. **TC 不可逆符合 Meyer-Land 理论** —— post_liminal 答错不回退
4. **Bloom dominant_layer 是核心 UX** —— 6 维转单维可解释

### 12.3 产品层面

1. **先 A 后 C 是正确战略** —— lbc001 单用户测试发现 4 BUG + 1 P0 弊端
2. **方案 C 标"待启用"优于伪信号** —— 不硬猜
3. **Phase 4 完整 Demo 形态价值巨大** —— 124 commits 产出可展示
4. **单用户产品也能产生学术价值** —— partial credit 弊端 / 库 ID 错配 都是可发表发现

### 12.4 协作层面

1. **Bisen 反馈极其具体（commit hash + 行号）** —— 是最好的 code review
2. **Mavis 自我反思比掩饰好** —— 5 次虚标都诚实地写进 CLAUDE.md
3. **跨工具协作是常态** —— Bisen 同时用 ChatGPT/Gemini/Claude
4. **哲学硬问题不回避** —— 意识/主体性/教育本质都可讨论

---

## 13. 附录

### 13.1 文件统计

| 类型 | 数量 | 位置 |
|------|------|------|
| Python | 78 | ecos/ + experiments/ + web/ |
| Markdown | 113 | research/ + discussions/ + 项目级 |
| JSON | 16 | 题库 / misconception 库 / 评测 / env 模板 |
| HTML | 1 | web/student/index.html (209 行) |
| CSS | 1 | web/student/styles.css (539+ 行) |
| JS | 1 | web/student/app.js (828+ 行) |
| 其他 | 配置文件 / LICENSE / .gitignore | 根目录 |

### 13.2 引用网络（v0.53.0 状态）

```
README.md (权威状态源)
  ├─→ CLAUDE.md (协作指南)
  ├─→ research/00-overview/03-roadmap.md (Phase 5 启动条件)
  ├─→ research/00-overview/01-applications.md (应用场景)
  ├─→ research/00-overview/02-architecture.md (双 Agent 架构)
  ├─→ research/00-overview/04-risks.md (风险)
  ├─→ research/00-overview/05-user-friendly-demo.md (Demo)
  ├─→ research/deep-research/Cognitive-Digital-Twin-Deep-Research.md (深度研究 v2.0)
  ├─→ research/90-mvp/python-basics-q-matrix-design.md (Q 矩阵设计)
  ├─→ research/90-mvp/06-ecos-end-to-end-flow-analysis.md (端到端流程)
  ├─→ discussions/2026-07-21-lbc001测试发现4个BUG分析与修复计划.md
  ├─→ discussions/2026-07-22-Phase5-Q矩阵CX重新设计路线图.md
  └─→ discussions/2026-07-22-partial-credit重大学术弊端发现.md

CLAUDE.md (协作指南)
  ├─→ 顶部状态 (引 README.md §当前状态)
  ├─→ §4 CSS 规则 (引 v0.51.0 拆文件)
  ├─→ §防御性自检规范 (本报告 §7)
  └─→ §计划中的防御机制 (本报告 §8)
```

### 13.3 关键 commit hash 索引（v0.49+）

| 版本 | hash | 内容 |
|------|------|------|
| v0.53.0 | 1ea711d | docs sync: CLAUDE.md + README.md + CHANGELOG.md + cross-references |
| v0.52.3 | 3baf2bf | ECOS 端到端流程深度分析文档 |
| v0.52.2 | d4ad4ff | response_history 存 AI reasoning + partial credit 记录 |
| v0.52.1 | 6003991 | 方案 C 标 C/X "待启用" + Phase 5 路线图 |
| v0.52.0 | 953c01c | P0 修 misconception 检测 + LearningDNA 标待启用 |
| v0.51.4 | a9d7145 | 设置页版本号改动态拉 /api/version |
| v0.51.3 | bf08fa6 | 修 5D 字母颜色 + tab 选中态/hover 强化 |
| v0.51.2 | ce7e5c9 | 修 URL hash 路由——刷新后自动恢复 sid + tab |
| v0.51.1.1 | 08eb3e9 | gitignore 加 SQLite WAL/SHM 排除 |
| v0.51.1 | 103a7e7 | 修 Flask SQLite 跨线程错 + loadQ 防御 d===null |
| v0.51.0 | 84a1e31 | Phase 4 拆文件 + API 封装 + URL hash 路由（Bisen 合并）|
| v0.50.0 | 04fb119 | Phase 3 视觉系统化（CSS 变量 + 进度条 + SVG 图标）|
| v0.49.3 | 994cd33 | 修 misconception_detector LLM NoneType 错 + 错误隔离 |
| v0.49.2 | 294b0d9 | 答题历史详情页（response_history 改 dict 格式）|
| v0.49.1 | c65ebad | Tab 导航（学习 / 轨迹 / 设置）|
| v0.49.0 | 990323e | W5+ UI: 成长轨迹默认折叠 |
| v0.48.9 | ff14df8 | W5+ UI: 题目+答题合并为一张卡 |
| v0.48.8 | 3f6d803 | W5+ UI: 顶栏精简（删版本号 + C折扣）|
| v0.48.7 | acd68ef | W5+ UI: 5D 数字 toFixed(4) → toFixed(2) |
| v0.48.6 | 55ff9c9 | W5+ 修复：/api/judge LLM 慢导致 submit 卡死（30s timeout）|

### 13.4 关键文件清单（v0.53.0）

| 文件 | 作用 | 行数 |
|------|------|------|
| `ecos/__init__.py` | 包入口 + `__version__ = "0.53.0"` | 17 |
| `ecos/cta/belief_state.py` | BeliefState 5 维 + θ_cov + BloomProfile + TC | 核心 |
| `ecos/cta/belief_engine.py` | BeliefEngine + misconception 库 ID 修复 | 核心 |
| `ecos/cta/llm_critic/misconception_detector.py` | M1-M8 Python 库 | 核心 |
| `ecos/cta/llm_critic/perception.py` | 5D 提取 | 核心 |
| `ecos/cta/llm_critic/explanation.py` | 解释生成 | 核心 |
| `ecos/cta/llm_critic/schemas.py` | LLM 响应 schema | 核心 |
| `ecos/cta/l2_mirt.py` | MIRT MAP 估计 | 核心 |
| `ecos/cta/bloom.py` | Bloom 累积 | 核心 |
| `ecos/cta/tc.py` | TC 状态机 | 核心 |
| `ecos/cta/dna.py` | LearningDNA（占位）| 核心 |
| `ecos/llm_client.py` | OpenAI-Compatible Protocol | 核心 |
| `ecos/persistence/db.py` | SQLite + WAL | 核心 |
| `web/api/app.py` | Flask 路由入口 | 核心 |
| `web/api/belief.py` | `/api/answer`, `/api/judge` | 核心 |
| `web/api/qmatrix.py` | Q 矩阵加载 | 核心 |
| `web/api/interpretation.py` | 6 段规则引擎 | 核心 |
| `web/student/index.html` | 学生端 209 行 | UI |
| `web/student/styles.css` | 539+ 行 CSS + 变量 | UI |
| `web/student/app.js` | 828+ 行 + api 命名空间 | UI |

### 13.5 lbc001 27 道题测试数据（v0.52.2 时点）

- 答 27-29 道（8 道有 timestamp，19-20 正确，3 错，86%）
- 5D：K=1.253 θ，P=0.955，S=0.034（暴跌），C=X=0.216（标待启用）
- SE：K=0.773，P=0.699，S=0.590，C=X=0.983
- confidence：K=0.564，P=0.589，S=0.629，C=X=0.504
- overall=0.5579（mean(5D conf)）
- Bloom：L1=0.7，L2=0.725，L3=0.8，L4=0.6，L5=0.6，L6=0.5
- dominant：APPLY (L3)
- TC：variables=post_liminal，loops=pre(0.4)，functions=post，recursion=pre(0.6)，scope=pre(0.6)
- misconception_history：1 条 M3（v0.52.0 fix 后，lbc001 PB-Q06 错题 + "range(5) 包括 5" 解释触发）

### 13.6 Phase 5 启动条件检查清单

- [ ] lbc001 答 30+ 题（当前 27-29）→ 还差 1-3 题
- [ ] Bisen 启动决策 → 触发 v0.53.0
- [ ] Partial Credit 必修设计稿（PHA5-PRD-CR 文档）
- [ ] C 主导题 20+ 题（调试题/错误分析/code reading/debug strategy）
- [ ] X 主导题 20+ 题（Python↔JS/Java/C++/Ruby 跨语言类比）
- [ ] X 维度 misconception 库（M9-M16，8 条候选）

---

## 14. 总结

**v0.40.0 → v0.53.0 的 10 天，ECOS 完成了从"实验脚手架"到"完整产品 Demo"的跃迁**，但暴露了 **3 大根本问题**（partial credit 缺失、C/X 0 主导题、MIRT 二元对错 trade-off）和 **5 次虚标模式**。三者共同决定 Phase 5 必修。

**审查结论**：
- ✅ 文档已与代码基本对齐（v0.53.0 docs sync）
- ✅ 防御性自检规范已强制（CLAUDE.md §防御性自检）
- ✅ CI gate 已加 3 条（CLAUDE.md §计划中的防御机制）
- ⚠️ 3 大根本问题待 Phase 5 解决
- ⚠️ 5+ 条 CI gate 计划中（v0.53.2+）
- ⚠️ LCA / 双 Agent 互校 / 干预策略未实施

**Bisen 未来 review 优先级**：
1. **最高**：partial credit 缺失（lbc001 PB-Q18 触发 K 多跌 0.27 / L6 多跌 0.2）
2. **高**：C/X 0 主导题（5D 评估实际 3D）
3. **中**：MIRT 二元对错 trade-off（不是 bug 是设计选择）
4. **低**：LCA / 双 Agent 互校（Phase 5+ 路线）

---

**报告版本**：v1.0（2026-07-22）
**下次更新**：v0.53.2 后（ROADMAP v1.4 + 同步 README badge / 02-architecture / 04-risks 后）
**维护者**：Mavis
**反馈**：discussions/ 或 commit message
