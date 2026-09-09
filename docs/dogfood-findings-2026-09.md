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
- **复确认**：Bisen dogfood 独立观察到投入度/信心同样无实际信息输出（2026-09-08），与挫败感同根因，三维一体
- **附带可选项处置**：「样本积累中」诚实性标注 **Bisen 拍板暂不做**（2026-09-08，记下即可），与三维接线同批次考虑
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

### F-05 LLM judge 调用元数据不落库，无法事后审计（2026-09-08）

- **现象**：dogfood 期间 Bisen 询问"AI 评判是否用了 MiniMax"，DB 层无法直接回答——只能靠 response_history 的 reasoning 文本间接推断（内容为 LLM 定制生成 + 判定成功本身证明 LLM 被调用，因 judge 失败不降级 → 422）
- **根因（已查实）**：`evidence_log` 的 `llm_critic_output / llm_critic_temperature / llm_critic_tokens` 字段全空是**设计使然**——那组字段属于 v0.83 Evidence Critic 路径，与 `/api/judge` 是两条链路；judge 的调用元数据（model / attempts / tokens / latency）**没有任何落库点**
- **影响**：事后无法从 DB 审计每道题的评判来源（哪个模型 / 几次 retry / 多少 token / 是否降级重试过）。试点 5-10 学生 × ≥50 题 × 4 周会产生数百次 judge 调用，缺乏审计能力时，成本核算（LLM API 预算）与异常排查（某题判分可疑时回溯调用详情）都只能靠服务端 stdout，而 stdout 不持久
- **方案建议**：judge 落库元数据表（或复用 evidence_log 增列）——problem_id / student_id / provider + model / attempts / tokens / latency_ms / raw_output 摘要。改动小（judge 成功路径一处写入），试点前完成
- **优先级**：P2（不阻塞答题流，但试点前做完能直接支撑成本核算与判分审计）
- **状态**：📋 已拍板待做（试点前批次）

### F-06 PB-Q16 判分争议：概念对的代码题因语法瑕疵判 0 + judge 幻觉事实错误（2026-09-08）

- **现象**（global x 写代码题）：学生答案概念完全正确（`global x` 用法对、函数体 4 空格缩进完好、变量名不同但结构对），仅 `def prn()` 缺冒号 → 判 0 分；且 reasoning 声称「函数体缺少缩进」——**与原始作答矛盾**（DB 存证缩进完好，传输链无损）
- **取证结论（两层问题）**：
  1. **机制层（主因，成立）**：`partial_credit_rubric` 覆盖 30/56 题，**8 道"写代码"题缺 rubric**（PB-Q03/11/14/16/22/24/25/26）→ 走二元 judge prompt（"严格判断是否正确"，只输出 correct true/false），score 由 correct 派生 0/1——LLM 无 partial credit 指令，判 0 是 prompt 设计使然，不是模型不听话。连带效应：`correct=false` 使信念更新把"概念会但语法瑕疵"的学生向"不会"方向推，**实质污染 H1 数据**
  2. **模型层（次因，幻觉）**：「函数体缺少缩进」为事实性幻觉。无法进一步审计根因（raw_output 不落库，见 F-05——本例正好证明 F-05 的审计价值）
- **方案选项**：
  - **A（试点前，推荐）**：给 8 道写代码题补 `partial_credit_rubric`（4 档：1.0 概念+语法全对 / 0.6 概念对+可运行性受损的轻微语法瑕疵 / 0.3 概念部分对 / 0.0 概念错）——v0.58.0 机制现成，纯数据补齐；配套加 rubric 完整性测试（防止未来新增代码题漏配）
  - **B（配合 A）**：judge reasoning 要求"指出错误时引用学生答案原文"，压幻觉空间；真正审计闭环靠 F-05 落库
  - **不做**：给老 prompt 加通用 partial credit 指引（无题级 rubric 时 4 档标准不统一，违反 rubric 是题级设计的既有思路）
- **优先级**：P1（直接污染 5D/Bloom 数据 + 影响学生对系统的信任）
- **状态**：✅ 已落地（v0.98.8，Bisen 拍板执行）：12 道写代码题 rubric 补齐（回归测试宽判据又抓出 4 道漏网）+ PC-C04 历史缺陷顺手修 + prompt 双分支防幻觉 + 5 个测试；lbc 的 PB-Q16 记录已校正（轨迹 + evidence）。⚠️ 遗留注：增量信念状态已消费过 0 分观测，贝叶斯更新不可逆——dogfood 账号 lbc 已重置（Bisen 拍板，2026-09-08 全表清零）

### F-07 答题页「一句通俗化」备注冻结不更新（2026-09-08）

- **现象**：连续答了 2-3 题后，题目下方备注仍显示「已完成 0 次答题，整体置信度 0.00」
- **根因（已查实）**：`AnswerPage.tsx` 的 report query（`["report", studentId]`）**只在页面挂载时 fetch 一次**；提交答案后只 `question.refetch()` 刷下一题，report 从不失效/重取 → 备注冻结在进页时刻的快照。换 TAB 再回来才更新（之前 F-06 截图显示「2 次答题」正是一次重新挂载的结果）
- **次要点**：新账号「整体置信度 0.00」是 BeliefState 默认值 `overall_confidence=0.0`（`belief_state.py:333`）——数值本身非 bug，但冻结 + 0.00 组合让用户以为系统没在记录
- **影响**：答题页的通俗化总评（本应是"系统在看着我进步"的即时反馈）变成假数据；学生连续答题全程看到 0 次，直接损害对系统的信任
- **方案建议（一行级）**：`onSubmit` 成功后 `void report.refetch()`（或 `queryClient.invalidateQueries(["report"])`）；若答辩期想更讲究，可让备注显示"已含本题"语义并标注快照时间
- **优先级**：P2（纯前端展示，不碰数据层；但信任损害与 F-04 同类）
- **状态**：✅ 已修复（v0.98.9，Bisen 拍板"现在修"）：onSubmit 成功后 `void report.refetch()`；只读重取，不影响答题流与数据层

### F-08 刷新后「答题为 0」：debug reloader 静默重启 + 恢复异常（2026-09-08）

- **现象**：答了 3 题后刷新浏览器，界面显示 0 题
- **数据安全（最先确认）**：DB 完好——response_history 3 条（PB-Q05/12/15 全对）+ evidence 10 行 + event 6 条 + calibration 3 条，无中断写入
- **根因第一层（已实锤）**：Flask debug reloader 双进程（父监视 + 子 worker）。**15:21:49 Claude 为 v0.98.9 bump `ecos/__init__.py` → 15:21:50 reloader 自动重启 worker 子进程**（`ecos/__init__.py` mtime 与子进程启动时间精确匹配）——内存 `_STUDENT_STATES` 丢失。**修前端 bug 的版本号动作重启了正在答题的后端**，双方事先都不知道这个联动
- **根因第二层（未解，代码已排除）**：新 worker 本应从 DB 恢复（`_get_or_create_student` restore 路径），但实际返回 warmup=0 / trajectory=0。已三次验证恢复代码本身正确（隔离进程调 `_get_or_create_student` + 完整 `get_student_state` 均正确恢复 3 题/置信度 0.5151）——线上 worker 的缓存项被**无恢复路径**创建（fresh 分支），但 fresh 分支要求 `load_student_state` 返回 None，与行存在矛盾。诊断需要 worker 的 stderr（"DB 恢复失败" warning），该输出只在用户终端
- **即时处置**：重启后端 → 内存缓存从 DB 重建（恢复路径已验证）
- **预防方案（建议）**：
  1. **dogfood/试点不用 debug reloader**（如 `ECOS_FLASK_DEBUG=0` 或启动命令去 debug）——会话中任何后端 .py 变更都静默重启并丢内存状态，dev 便利性与会话连续性冲突
  2. **协作纪律**：dogfood 进行中 Claude 改任何后端 .py 前先声明"会触发后端重启"
  3. 恢复异常若复现，凭 stderr 日志追查（F-05 式审计思路）
- **优先级**：P1（会话连续性 + 系统性隐患；数据本身无损）
- **状态**：📋 已重启处置，预防项待拍板

### F-09 答题时延信号未采集，evidence `raw_response_time` 恒 0（2026-09-08）

- **现象**：dogfood 13 题的 evidence 行 `raw_response_time` 全部为 0.0
- **根因（已查实）**：全链路无采集——前端 `AnswerPage` 提交 payload 不含时延字段，后端 `submit_answer` 也不填写；`raw_response_time` 列是 v0.83 evidence schema 的一部分，但**从未有生产者**（又一处 built≠wired，schema 建了、链路没接）
- **影响**：F-02 的 frustration 候选信号之一（答题时延异常）与 H1 数据（作答速度与掌握的关系）都依赖此字段；试点前不接，试点数据回来这块就是空白
- **方案建议（试点前做，改动小）**：前端 CodeEditor 挂载→提交计时，`submitAnswer` payload 加 `response_time`；后端 evidence 写入该列。一处前端 + 一处后端
- **优先级**：P2（不阻塞答题流；但属"试点信号采集完整性"，建议与 F-05 同批次）
- **状态**：⏸ 待拍板

### F-10 误解检测链路空转：`explanation_text` 前端不传，misc_hits 恒空（2026-09-08）

- **现象**：21 题 `misc_hits` 全部 `[]`、`misconception_evidence` 表 0 行、LCA 干预 `target_misconceptions` 恒空——而 PB-Q04 出现教科书级误解（答 `[1,2]`，正是 M6"变量=存储值的盒子"引用语义误解，库里有现成条目），检测器却毫无反应
- **根因（已查实全链路）**：检测器输入是 `observation.explanation_text`（`ecos/cta/inference_engine.py:332` `detect_with_hits(student_explanation=...)`）；后端 `/api/answer` 从 body 读 `explanation_text`（`app.py:495`）——但**前端 `submitAnswer` payload 根本没有这个字段**（`api.ts:63-77`），所以每次提交 `explanation_text=""`，检测器面对空字符串永远返回 None
- **讽刺点**：学生的解释文字其实一直在传——都在 `user_answer` 里（如 PB-C06"因为 y=x 只是把 x 的值赋予 y…"），只是进了错误的字段，检测器拿不到
- **影响**：误解检测是 C 维折扣与 LCA 靶向干预（`target_misconceptions`）的输入；试点期间该链路等于不存在，M1-M8 误解库纯摆设
- **方案建议（试点前做）**：后端 fallback `explanation_text = data.get("explanation_text") or user_answer`（一处改动，user_answer 含解释文字可直接喂检测器）；或前端拆分答案/解释两个字段（交互更清晰，改动大）。推荐前者先行
- **优先级**：P1（试点核心信号链路空转，影响靶向干预与 C 维折扣的数据基础）
- **状态**：⏸ 待拍板

### F-11 行为事件（hint/idle/goal_change/reflection）不落库，进程重启即蒸发（2026-09-08）

- **现象**：21 题跨多个 topic，`event_log` 表只有 `observation` + `response_submitted`（belief.py 提交路径写的 2 行/题）——goal_change 按前端逻辑应已多次触发，但表里 0 条；hint/idle/reflection 同样无记录
- **根因（已查实）**：`web/api/event_stub.py` 的 4 个端点把事件 publish 到**进程内 EventBus**（`get_default_bus()`，`event_stub.py:106`）——订阅者只有 PluginRuntime 的内存态插件（HintFatigue 等），**没有任何 subscriber 把行为事件写进 event_log 表**。代码注释自证："Phase 7+ 计划: subscriber 可订阅这些 event…（留 v0.86+）"——bus 接线做了，持久化没接（又一处 built≠wired）
- **影响**：行为遥测（提示依赖、 idle 挫败信号、目标切换、反思文本）只活在内存里，重启即失（与 F-08/F-05 同族）。反思文本（reflection）是 F-02 候选信号 + 试点 H1 数据的一部分，现在落不了库
- **方案建议（试点前做）**：event_stub 四端点在 publish 后追加写 event_log 表（或挂一个 PersistSubscriber）—— belief.py 已有 EventLog 落库先例，复用即可
- **优先级**：P1（试点信号采集完整性缺口）
- **状态**：⏸ 待拍板

## 已知占位项（避免 dogfood 期间误报为 bug）

以下为 v0.98.5 时点已知的「有意未接」项，见 `docs/for-partners.md` §九诚实标注表：

| 项 | 现状 | 计划 |
|----|------|------|
| 挫败感 frustration 恒 0 | MotivationProfile 消费端已建（LCA evaluator/planner），**生产链路无信号生产者**，UI 显示默认值 | 详见 **F-02**（试点数据回来后回算标定，与 C 维折扣同批次） |
| C 维折扣未接在线流程 | `confidence_for → 信念更新` 离线校准中 | 试点数据回来后一并校准接入 |
| BKT 衰减参数 | replay 读时视图，先验值 | 试点数据校准（v0.97.1 决策） |
