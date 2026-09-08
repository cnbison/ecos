# Dogfood 发现清单（2026-09，试点前全流程自测）

> **背景**：v0.98.5 生产库清理后，Bisen 以真实用户身份跑通全流程（试点第 0 步）。
> 本文档记录 dogfood 过程中的发现，测完一轮后统一排优先级批量处理。
> **协作模式**：Claude 只读观察（DB/日志），发现 bug 只记录 + 给方案，Bisen 拍板后才动代码。

## 发现记录

### F-01 学生端导出报告只有 JSON 格式（2026-09-08）

- **现象**：学生端设置 TAB「导出学习报告 (JSON)」直接下载原始 JSON blob
- **评估**：后端 `/api/report/<sid>` 内容不简陋（summary + interpretation 规则引擎自然语言解读 + 完整 state），简陋的是交付形态——`interpretation` 已生成的人话被埋在 JSON 里，家长/学生无法阅读
- **方案（已拍板）**：选 C —— 前端 React 渲染 HTML 报告页（interpretation 为主体 + summary 数字，`window.print()` 打印即 PDF）作为主路径；JSON 降级为「导出原始数据（开发者）」次按钮保留
- **优先级**：P2（不阻塞试点，纯体验项）
- **状态**：📋 已拍板待做（dogfood 一轮结束后统一处理）

### F-02 今天 TAB「近况感知」挫败感等三维数据恒为默认值（2026-09-08）

- **现象**：学生端首页 MotivationPanel 的挫败感恒 0、投入度/信心恒 0.5（中性默认值），`observation_count` 恒 0
- **根因（已全链路排查）**：**生产链路无信号生产者**。MotivationProfile（v0.87.0 Kernel）消费端已建成（`ecos/lca/evaluator.py:156` frustration>0.7 → gain×0.7；`experiment_designer.py:266` → 强制 EXPLANATORY 降难度），`/api/state` 原样序列化默认值（`web/api/belief.py:477`），但答题流中没有任何代码从行为信号推导并写入 motivation observation——唯一写入入口 `plan_motivation_aware(motivation_observation=...)`（`ecos/runtime/api.py:340`）只是透传通道，生产路径从不传。built≠wired：数据结构 + 消费端 + UI 呈现三段齐备，中间的**信号推导段从未实现**
- **与数据库清理无关**：v0.98.5 清理前后行为一致，均为默认值
- **候选信号（实现时选）**：连续错误次数（response_history）/ 答题时延异常（evidence_log `raw_response_time`）/ 自评 4 档最悲观档（v0.97.2，试点要收集的信号之一）/ hint 请求频率（HintFatiguePlugin 已有 per-student 计数）
- **方案（已拍板）**：排 backlog，**试点数据回来后**从 evidence 回算标定映射再接实时路径——与 BKT 阈值、C 维折扣同批次；试点范围冻结，不提前接线引入新变量
- **附带可选项**：试点面向真实学生时，MotivationPanel 可加 `observation_count === 0` →「样本积累中」状态，避免默认值被误读（P2，UI 诚实性修正）
- **优先级**：P2（数据是派生量，不接不影响试点原始信号落库）
- **状态**：📋 已拍板待做（试点后批次）

### F-03 第一题就出「信心元问题」，答题流对元问题完全不适配（2026-09-08）

- **现象**：新学生首题 = PC-C01（"这道题你能答对的可能性有多大? A-F"），标签 L3 / cross_subject / 热身；下方却是代码编辑器（"输入代码或答案…"）+ 提示按钮 + **又一套** 4 档自评（"提交前先猜一猜"）
- **根因链（已查实）**：
  1. **选题池不过滤元问题**：Q 矩阵 56 题中 10 道 cross_subject 元问题（PC-C01-C05 自评 + PC-X01-X05 外部支持）与普通题混在一起；`web/api/qmatrix.py` warmup/adaptive 选题均无 `c_dimension_type` / `domain_agnostic` 过滤
  2. **warmup 游标按 topic 字母序轮询**，`cross_subject` 排最前 → 新学生第一题必然是 PC-C01（L3），后续 warmup 还会持续轮到元问题（约 1/6 概率）
  3. **判分锚定失效**：PC-C01 的 correct_answer / rubric 硬编码「基于 lbc001 实际 K/P 维度评估，答对可能性约 70-80%」——对任何新学生，「选 B = 1.0 分」毫无校准意义（其真实掌握未知）。C 问题的本意是测校准度，但静态锚定使它测的不是被测者自己的校准
  4. **交互不适配**：A-F 选择题走了代码题渲染路径（编辑器 + 提示 + LLM judge 输入框）；且与 v0.97.2 强制 4 档自评**语义重复**——一道"自评题"要求先做另一次自评才能提交
- **方案选项**：
  - **A（试点前必须，改动小）**：选题池过滤 `topic == "cross_subject"`（warmup + adaptive 双路径），C/X 元问题暂不入池。C 维自评信号已由 v0.97.2 强制 4 档自评覆盖，静态 PC-C 题对试点 H1 数据是冗余且污染性的（锚定错误 + 打断答题节奏）
  - **B（试点后）**：元问题专用渲染（A-F 按钮、无编辑器/提示）+ 判分锚定动态化（绑定该生配套题的实际表现做校准判定）+ 与 4 档自评的去重设计
- **优先级**：P1（污染答题流首因，直接影响新学生第一印象与数据质量）
- **状态**：✅ 方案 A 已落地（v0.98.6，`select_question_for_student` 选题池过滤 + 8 个回归测试；Bisen 补充的设计级缺陷——元探针无配套题上下文、只有 F 可逃——已记入方案 B 的输入）；方案 B（专用渲染 + 动态锚定）试点后
- **补充发现（实施时）**：Q 矩阵另有 20 道 `PB-C*` 题（调试题/错误分析/代码阅读/调试策略）同样带 `c_dimension_type` 字段，但**有真实题目上下文**（在真实任务中嵌入元认知），不属于本问题，保留在池内——判据必须用 topic 而非字段（测试先于实现抓出此区别）

### F-04 提交答案后按钮仍可点击，存在重复提交风险（2026-09-08）

- **现象**：提交答案拿到评判结果后，「提交答案」按钮未变为禁用态，仍可再次点击
- **根因（已查实）**：`AnswerPage.tsx` 提交按钮的 disabled 条件为 `judging || !answer.trim() || selfConf === null`，**不含 `!!result`**——出结果后按钮保持可点。对比：自评 4 档 chips 已有 `disabled={!!result}`（同一批提交后禁用），提交按钮漏了
- **影响（不止 UX）**：再次点击会重跑 `/api/judge` + `/api/answer` → 同一 problem_id 在 response_history / evidence_log / 信念更新中**重复计入**，直接污染 H1 数据。且二次点击时按钮文案回到「提交答案」（`selfConf !== null` 且非 judging），用户无从知道已经提交过
- **方案建议**：
  - **前端（必修，一行级）**：disabled 加 `!!result`，出结果后文案改「已提交 ✓」之类终态；`onSubmit` 内加 `if (result) return` 双保险
  - **后端（可选，试点前评估）**：`/api/answer` 对同一 `(student_id, problem_id)` 的重复提交做幂等保护（拒绝或覆盖），防其他客户端路径重放。前端修复已覆盖 dogfood 场景，后端幂等可作为独立小项排期
- **优先级**：P1（一行修复 + 直接污染数据质量）
- **状态**：✅ 已修复（v0.98.7，Bisen 拍板"现在修"）：disabled 加 `!!result` + 出结果后文案终态「已提交 ✓」+ `onSubmit` 内 `if (result) return` 双保险；后端幂等保护仍为可选项，试点前再评估

## 已知占位项（避免 dogfood 期间误报为 bug）

以下为 v0.98.5 时点已知的「有意未接」项，见 `docs/for-partners.md` §九诚实标注表：

| 项 | 现状 | 计划 |
|----|------|------|
| 挫败感 frustration 恒 0 | MotivationProfile 消费端已建（LCA evaluator/planner），**生产链路无信号生产者**，UI 显示默认值 | 详见 **F-02**（试点数据回来后回算标定，与 C 维折扣同批次） |
| C 维折扣未接在线流程 | `confidence_for → 信念更新` 离线校准中 | 试点数据回来后一并校准接入 |
| BKT 衰减参数 | replay 读时视图，先验值 | 试点数据校准（v0.97.1 决策） |
