# 2026-09-05 CogMirror A1-A4/B1-B2 对 ECOS 的适用性分析 + built≠wired 接线审计发现

**参与者**：Bisen × Claude（glm-5.3）
**背景**：CogMirror 依据 `docs/implementation-plan.md`（2026-08-27）从 PersonalAGI 移植 4 算法（A1-A4）+ 2 模式（B1-B2）。本文分析这些优化是否部分适用于 ECOS。
**前提变化（同日）**：**ECOS 决定恢复开发**——负责人判断"基于外部认知架构的学校教育"值得进一步推进。本文分析由此从假设性讨论变为恢复期 backlog 输入。

---

## 一、逐项映射（全部经源码核实，非印象）

| CogMirror 项 | ECOS 对应物（已核实） | 判定 |
|---|---|---|
| A1 自评置信度校准曲线 | `ecos/metrics/ece.py`（v0.63）+ `ecos/dual_agent/calibration.py` Platt/Isotonic（v0.72/0.73） | **同名不同物**：ECOS 校准系统置信度（V3/LinUCB），CogMirror 校准学生自评。ECOS **不采集学生自评置信度**（ecos/ + web/api/ 全链路无 self_confidence 字段；伪自信来源是 `belief_updater.py:126` 的 `llm_misc_illusory_flag`，纯 LLM 推断） |
| A2 misconception 证据闭环（Laplace 权重 + reconcile） | `MisconceptionHit`（LLM critic 生成）+ EvidenceEngine 落 `evidence_log` 表 | **原料已有、闭环缺失**：ECOS 无 per-misconception 证据驱动权重（全项目无 Laplace/reconcile）。但 CogMirror 的前置缺口 B（命中记录未落库）在 ECOS 不存在——evidence_log 已是对账原料 |
| A3 黄金回归基线 | 1365 单测 + 8 项防御自检 | **形态缺失**：防御体系对象是"已知 bug 模式复发"（同类扫描），A3 对象是"任何引擎改动的行为漂移"。两者正交，ECOS 缺后者 |
| A4 间隔衰减接线 | `cta/l1_evolution.py:149 apply_decay` + `lca/l3_selection/bjork/spacing.py` | **ECOS 同样 built ≠ wired**（见下清单）。CogMirror P3 的两个前置缺口（BKT 不持久化、双重衰减陷阱/原地乘法）在 ECOS 同样成立 |
| B1/B2 纵向档案 + 反思段 | session/persistence/interpretation 模块 | 已有更重的对应物，产品形态不同（web 双端 vs 本地 CLI），低优先级 |

## 二、built ≠ wired 接线审计清单（本日发现，恢复时优先处理）

> 这是本次分析最重要的产出。CogMirror 方案 A4 的核心教训"built ≠ wired"（P3 复核发现 `bkt.py:apply_decay` 是死代码）在 ECOS 有三个同类实例：

1. **`cta/l1_evolution.py:149 apply_decay`**（Ebbinghaus `P(L)·e^(-days/τ)`，与 CogMirror `bkt.py:137` 几乎同构）——`ecos/`、`web/`、`scripts/` 全部**零调用者**。死代码。
2. **`BjorkSpacingEffect`**——`lca/planner.py:130` 实例化后，`get_review_schedule` **从未被调用**（`self.bjork_spacing` 在 planner.py 全文只出现一次，即实例化行）。
3. **web 答题流未注入 Evidence/Event Engine**——`submit_answer → BeliefUpdator` 未注入 `evidence_engine`/`event_log`，`evidence_log`/`event_log`/`trajectory_snapshots` 三表在答题流为空。**已有文档记录**（`research/00-overview/12-kernel-mapping-current-vs-2.0.md` §1.4，v0.96.6 核验），注入点已预留（`BeliefUpdator.evidence_engine=` 参数），触发条件 = 家长透明化 / replay 审计消费方出现。

**共性问题**：ECOS 的"遗忘曲线 + 复习时机"能力（#1/#2）目前是纸面能力。v0.96.9 幽灵学生 bug 本质也是同类（代码存在、链路断裂）。

**方法论建议**：恢复时第一件事做全量接线审计——grep 每个 `def` 的真实 caller、每个实例化对象的真实方法调用（instantiate ≠ call）。可以并入防御性自检体系作为第 9 项候选（静态 AST 可做：模块内 `def` 无 repo 内 caller → 告警白名单制）。

**接线 #1/#2 的前置缺口**（与 CogMirror P3 同款，方案可原样借鉴）：
- BKT（l1）per-skill 状态不持久化——`persistence/db.py` 无 BKT/l1 相关字段，重启即失；"曾掌握峰值"需从 response 历史重放推导（CogMirror 方案：独立临时 BKTModel 历史重放，只读不改 l1）；
- 双重衰减陷阱——`apply_decay` 是原地乘法，每次会话按"距上次作答天数"调用会复合衰减；产品路径应走**无状态视图**（直接算公式，不经原地接口）。

## 三、三层"适用"（避免混淆）

1. **代码层：基本无需移植，方向甚至是反的。** ECOS 的校准（Platt/Isotonic vs 分桶曲线）、spacing（Cepeda 静态表 vs 同款）、misconception 检测（LLM vs 关键词库）都更深。仅有的两个增量：A1 的"学生自评"数据源（观测层缺口）、A2 的 reconcile 语义。
2. **设计层：适用的是否定性发现与纪律。** built ≠ wired 审计（上文）；黄金回归基线先行（"先固化当前行为，再改引擎"——直接对应 ECOS 防御文化，可作为恢复后第一项基建）；无状态视图规避复合衰减。
3. **战略层：CogMirror 可作 ECOS 的廉价确定性试验场。** A1/A2/A4 全是无 LLM、可复现的统计层，先在 CogMirror 单人环境验证（走其验证线），验证过的结论再考虑进 ECOS kernel——比在 ECOS 重 LLM 架构里直接试便宜一个量级，符合 v0.95 "验证优先"方向。

**哲学收尾**：CogMirror 砍 LLM 的取舍逼出"把判断权交给累积数据"的纪律（Laplace、对账、校准曲线）；ECOS 的 LLM-in-the-loop 架构恰恰缺对 LLM 判断做地面真值追责的机制。两个项目是同一问题——"认知模型的判断凭什么被信任"——的两种解法；融合点是"用确定性统计层校准 LLM 层"（如 A2 映射到 ECOS = 用学生后续表现 reconcile LLM critic 的 misconception 置信度）。

## 四、恢复期 backlog 提案（输入，排序待 Bisen 定夺）

按"先固基线再改引擎"纪律排序：

1. **接线审计**（§二清单 #1/#2/#3）+#1/#2 接线（含 BKT 持久化决策 + 无状态衰减视图）
2. **A3 式黄金回归基建**（deterministic 段：belief 更新 → 建议；LLM judge 层已有 retry/rubric 测试，可后置）
3. **观测层补学生自评**（A1 增量）：答题 UI 自评控件 + DB 列 → 9D Confidence 维度获得第二证据源（自报 + LLM 推断互校）
4. **A2 reconcile 语义**（evidence_log 原料已就位）：后续表现校准 LLM critic 检测置信度

注意与 SSOT roadmap（搁置前为 v0.97 家长端 + 小规模试点）的对齐：#1 的接线 #3（Evidence/Event Engine 注入）触发条件"家长透明化"恰好就是 v0.97 家长端——两线天然汇合。

## 五、开放问题

1. README「当前状态」仍标注搁置（commit 4712d69）——恢复决定何时落 README？随首个恢复期 commit，还是现在？
2. K12 场景学生自评的信号质量是否值得采集？（Bisen 待答；CogMirror A1 的校准曲线正是处理"自评是需要校准的噪声源"的方案）
3. 黄金回归覆盖范围：deterministic 段先行 vs 连 LLM judge 一起 mock？
4. 接线审计是否升格为防御性自检第 9 项（AST 静态扫描）？

## 产出文件

- 本文（讨论存档 + built≠wired 清单登记）
- memory 更新：ecos 恢复决定（2026-09-05）
