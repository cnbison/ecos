# ECOS Product Demo 业务逻辑流程

**日期**：2026-07-10
**版本**：v0.4.0
**状态**：Product Demo 完整实现

---

## 一、系统架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                        学生端浏览器                                   │
│                  web/student/index.html                              │
│           (7 组件可视化：5D / Bloom / TC / DNA / Trajectory)           │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP REST API
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Flask Web 服务 (port 5173)                      │
│                                                                   │
│   /api/state/<id>    ← 获取学生完整信念状态（7 组件）                  │
│   /api/question      ← 获取下一道题目                                │
│   /api/judge        ← LLM 评判学生答案                               │
│   /api/answer       ← 提交答案 → BeliefEngine 更新                   │
│   /api/intervention ← 获取干预建议                                  │
│                                                                   │
│   web/api/belief.py  ← BeliefEngine 封装 + 会话状态管理              │
└────────────────────────────┬────────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
┌─────────────────┐ ┌──────────────┐ ┌─────────────────┐
│  BeliefEngine   │ │  Q-matrix     │ │   SQLite DB     │
│  ecos/cta/      │ │  data/        │ │   web/ecos.db   │
│                 │ │               │ │                  │
│ L1 BKT          │ │  26 道题目    │ │  学生状态持久化   │
│ L2 MIRT 5D      │ │  L1-L6 Bloom │ │  跨会话恢复       │
│ LLM Critic      │ │  a_specialized│ │                  │
│ TC Detector     │ │               │ │                  │
└─────────────────┘ └──────────────┘ └─────────────────┘
```

---

## 二、完整业务流程（用户视角）

### 2.1 启动与进入

```
用户打开浏览器 → http://localhost:5173/student
```

学生端页面加载，显示 **7 组件 Dashboard**：

| 组件 | 初始状态 |
|------|---------|
| 5D theta | K=P=S=C=X=0.0 |
| Bloom Profile | L1-L6 均为 0.5（中立） |
| TC States | 空（无记录） |
| LearningDNA | 示例驱动 / 即时反馈 |
| Trajectory | 空 |
| Misconceptions | 空 |
| overall_confidence | 0.0 |

### 2.2 答题主循环

```
┌─────────────────────────────────────────────────────┐
│                   答题主循环                          │
│                                                     │
│  ① 获取题目                                          │
│     学生点击"下一题" → GET /api/question             │
│     ← 返回题目内容（描述 / 选项）                      │
│                                                     │
│  ② 提交作答 → LLM 评判                                │
│     学生提交答案 → POST /api/judge                   │
│     ┌───────────────────────────────────────────┐   │
│     │ LLM 扮演老师角色判断：                      │   │
│     │ - 答案是否正确？                            │   │
│     │ - 推理过程如何？                           │   │
│     │ - 是否触发 Misconception？                  │   │
│     └───────────────────────────────────────────┘   │
│     ← 返回 {correct, reasoning}                     │
│                                                     │
│  ③ 提交答案 → BeliefEngine 更新                      │
│     学生确认 LLM 判断 → POST /api/answer             │
│     ← BeliefEngine 更新 7 组件状态                   │
│     ← 返回更新后的 theta / bloom / TC 等             │
│                                                     │
│  ④ Dashboard 实时刷新                                │
│     前端轮询 /api/state/<id> → 展示最新状态           │
│                                                     │
│  ⑤ 循环直到 session 结束                             │
└─────────────────────────────────────────────────────┘
```

---

## 三、后端核心模块

### 3.1 BeliefEngine（CTA 信念引擎）

`ecos/cta/belief_engine.py`

主入口：`engine.update(state, observation)`

每次学生答题后，按顺序执行 10 个步骤：

```
Step 1: L1 BKT 更新
         skill_id 对应的知识点掌握概率（BKT 模型）
         正确 → 掌握概率 ↑，错误 → 掌握概率 ↓

Step 2: 累积响应历史
         将本次 (problem_id, correct, bloom_level) 存入 _response_history
         用于后续 MIRT 估计

Step 3: L2 MIRT 5D MAP 估计
         基于 Q-matrix 的 a_specialized 加载向量
         估计 K/P/S/C/X 五维能力值
         关键：不同题目有不同的 loading vector → theta 分化

Step 4: BloomProfile 更新
         根据本次正确性更新 L1-L6 各层概率
         正确 → +0.05，错误 → -0.025
         更新 dominant_layer

Step 5: LLM Critic 感知层（M2 W3）
         若有 explanation_text，LLM 推断学生实际 Bloom 层
         仅当推断层高于当前 dominant_layer 时才采纳

Step 6: LLM Critic Misconception 检测（M2 W3）
         若有 explanation_text，LLM 检测常见 misconception
         命中 → C 维度折扣因子生效（最多折扣 30%）

Step 7: TC 状态检测
         挂在 C 维度的 tc_states 上
         状态机：pre_liminal → liminal → post_liminal（不可逆）
         触发条件：
           pre_liminal → liminal：L3+ 正确 + 无 active misconception
           liminal → post_liminal：持续 3 次 L3+ 正确

Step 8: 整体置信度
         overall_confidence = 0.6 × mean(各维度 confidence)
                           + 0.4 × bloom_profile.confidence

Step 9: 追加轨迹快照
         保存本次 state.snapshot() 到 trajectory

Step 10: 更新时间戳
```

### 3.2 MIRT 5D 估计算法

`ecos/cta/l2_mirt.py`

**BiFactorMIRT5D**：5 维能力估计，每维对应：

| 维度 | 含义 | 典型 loading |
|------|------|-------------|
| K（Knowledge） | 概念理解 | a=[0.9, 0.2, 0.4, 0.1, 0.1] |
| P（Procedural） | 程序知识 | a=[0.2, 0.9, 0.3, 0.1, 0.1] |
| S（Strategic） | 策略知识 | a=[0.3, 0.3, 0.8, 0.1, 0.1] |
| C（Cognitive） | 元认知 | a=[0.1, 0.1, 0.1, 0.9, 0.1] |
| X（Cross-domain） | 跨域迁移 | a=[0.1, 0.1, 0.1, 0.1, 0.9] |

**关键机制**：`register_item(problem_id, a_specialized)` 将题目特有的 loading 向量注册进 MIRT，使不同知识点对应的题目自然激活不同维度。

### 3.3 Q-matrix

`data/python_basics_q_matrix.json`

26 道 Python 基础题目（L1-L6）：

| Topic | L1-L2 | L3（应用） | L4（分析） | L5（评价） | L6（创造） |
|-------|-------|-----------|-----------|-----------|-----------|
| variables | Q01-Q02 | Q03 | Q17 | Q17-L5 | Q18-L6 |
| loops | Q04-Q05 | Q06 | Q19 | Q19-L5 | Q20-L6 |
| functions | Q07-Q08 | Q09 | Q21 | Q21-L5 | Q22-L6 |
| recursion | Q10-Q11 | Q12 | Q23 | Q23-L5 | Q24-L6 |
| scope | Q13-Q14 | Q15 | Q25 | Q25-L5 | Q26-L6 |

每道题目包含：
- `bloom_goal_id`：Bloom 层级（如 PB-Q01 → L1）
- `a_specialized`：5 维 loading 向量（控制该题激活哪些维度）
- `skill_ids`：涉及的知识点

### 3.4 TC 状态检测器

`ecos/cta/tc_detector.py`

TC = Threshold Concept（阈值概念），指学习过程中认知跳跃的关键节点。

```
状态机：

  pre_liminal ──(L3+ 正确 + 无 misconception)──→ liminal
      ↑                                              │
      │                                              ▼
      └────────(持续 3 次 L3+ 正确)────── post_liminal
                                                  (不可逆)
```

进度（progress）累积规则：

| 当前状态 | 触发条件 | progress 变化 |
|---------|---------|--------------|
| pre_liminal | L3+ 正确，无 misconception | +0.30 |
| pre_liminal | L1-L2 正确 | +0.05 |
| pre_liminal | 错误 | 不变 |
| liminal | L3+ 正确 | +0.25 |
| liminal | 错误 | -0.15（但不低于阈值×0.8）|

---

## 四、API 端点详解

### 4.1 GET /api/state/<student_id>

**用途**：获取学生当前完整 7 组件状态

**响应**：
```json
{
  "student_id": "student_001",
  "theta": {"K": 0.65, "P": 0.20, "S": 0.33, "C": 0.14, "X": 0.14},
  "theta_cov_diag": {"K": 0.72, "P": 0.97, "S": 0.93, "C": 0.99, "X": 0.99},
  "theta_confidence": {"K": 0.07, "P": 0.07, "S": 0.07, "C": 0.07, "X": 0.07},
  "theta_se": {"K": 0.85, "P": 0.99, "S": 0.96, "C": 0.99, "X": 0.99},
  "bloom_profile": {
    "dominant": "APPLY",
    "confidence": 0.07,
    "bloom_levels": {"L1": 0.5, "L2": 0.5, "L3": 0.60, "L4": 0.5, "L5": 0.5, "L6": 0.5}
  },
  "tc_states": [
    {"id": "python.variables", "status": "pre_liminal", "progress": 0.30, "confidence": 0.1, "irreversible": false}
  ],
  "learning_dna": {"input_preference": "示例驱动", "feedback_preference": "即时反馈", "confidence": 0.0},
  "trajectory": [
    {"timestamp": "2026-07-10T14:00:00", "theta_5d": [0.65, 0.20, 0.33, 0.14, 0.14], "confidence": 0.07, "bloom_dominant": "APPLY"}
  ],
  "misc_history": [],
  "overall_confidence": 0.07,
  "c_discount_factor": 1.0
}
```

### 4.2 GET /api/question

**用途**：获取下一道推荐题目

**响应**：
```json
{
  "problem_id": "PB-Q03",
  "skill_id": "python.variables",
  "bloom_goal_id": "PB-Q03-L3",
  "title": "变量赋值与引用",
  "description": "以下代码执行后，a 和 b 的值分别是多少？",
  "options": ["A. a=1, b=1", "B. a=1, b=2", "C. a=2, b=1", "D. a=2, b=2"],
  "answer": "C"
}
```

**选题策略**：当前为随机选题（M2 W4+ 将实现 PWKL/CD-CAT 最优选题）。

### 4.3 POST /api/judge

**用途**：LLM 扮演老师评判学生答案

**请求**：
```json
{
  "student_id": "student_001",
  "problem_id": "PB-Q03",
  "student_answer": "a = 2, b = 1",
  "explanation": "因为 a 是引用，修改 a 同时修改了 b"
}
```

**LLM Prompt 模板**（`ecos/cta/content.py`）：
```
你是一位 Python 编程老师。请判断学生的答案是否正确。
题目：<problem_text>
正确答案：<correct_answer>
学生答案：<student_answer>
学生解释：<student_explanation>

请判断：正确/错误，并给出简短理由。
```

**响应**：
```json
{
  "correct": true,
  "reasoning": "学生正确理解了变量引用机制"
}
```

### 4.4 POST /api/answer

**用途**：提交正式答案 → BeliefEngine 更新状态 → 持久化到 SQLite

**请求**：
```json
{
  "student_id": "student_001",
  "problem_id": "PB-Q03",
  "skill_id": "python.variables",
  "correct": true,
  "bloom_layer": "L3",
  "explanation_text": "变量是引用而非赋值"
}
```

**处理流程**：
```
1. 注册 Q-matrix a_specialized 到 MIRT
2. 创建 Observation 对象
3. BeliefEngine.update(state, observation)
   └── 执行 Steps 1-10（见 §3.1）
4. db.save_student_state() → SQLite 持久化
```

**响应**：
```json
{
  "correct": true,
  "theta": {"K": 0.65, "P": 0.20, "S": 0.33, "C": 0.14, "X": 0.14},
  "misc_triggered": false,
  "misc_id": "",
  "misc_confidence": 0.0,
  "c_discount_factor": 1.0
}
```

---

## 五、持久化层

### 5.1 SQLite Schema

`ecos/persistence/db.py` — 6 张核心表：

| 表名 | 用途 |
|------|------|
| `students` | 学生基本信息 + 当前 BeliefState JSON |
| `interventions` | 干预记录（未来 LCA 使用） |
| `evidence_log` | 每次答题的原始证据 |
| `calibration_log` | 双 Agent 互校记录 |
| `bloom_goals` | Bloom 目标定义 |
| `trajectory_snapshots` | 轨迹快照（不可变历史） |

### 5.2 状态恢复流程

```
Flask 重启 → _get_or_create_student(id)
                       │
                       ▼
           db.load_student_state(id)
                       │
           ┌───────────┴───────────┐
           │ DB 有记录               │ DB 无记录
           ▼                        ▼
     从 JSON 恢复：           engine.create_initial_state()
     - theta_mean            + db.upsert_student()
     - bloom_profile
     - learning_dna
```

**当前恢复范围**：theta_mean / bloom_profile / learning_dna（完整 BeliefState 的部分字段）。

---

## 六、7 组件计算公式

### 6.1 5D theta（MIRT MAP 估计）

```python
theta_hat = argmax_theta P(theta | responses, item_params)
           ≈ MAP 估计（先验 N(0, I)，似然由 bi-factor MIRT 模型给出）
```

初始：`theta = [0, 0, 0, 0, 0]`，协方差 `cov = I`

### 6.2 Bloom Profile

```python
# 正确
bloom.<level> = min(1.0, bloom.<level> + 0.05)
# 错误
bloom.<level> = max(0.0, bloom.<level> - 0.025)
```

dominant_layer：L1-L6 中概率最高的层级

### 6.3 TC 进度

```python
# pre_liminal → liminal
if status == "pre_liminal" and L3+_correct and no_misc:
    progress += 0.30
    if progress >= threshold(0.7):
        status = "liminal"

# liminal → post_liminal
if status == "liminal" and L3+_correct:
    progress += 0.25
    streak += 1
    if progress >= 1.0 or streak >= 3:
        status = "post_liminal"
        irreversible = True
```

### 6.4 overall_confidence

```python
mean_dim_conf = mean([K.confidence, P.confidence, S.confidence, C.confidence, X.confidence])
overall_confidence = 0.6 * mean_dim_conf + 0.4 * bloom_profile.confidence
```

### 6.5 C 维度折扣因子

```python
# 有 misconception 命中时
discount = 1.0 - min(misc_confidence * 0.3, 0.3)
c_discount_factor *= discount
mastery_prob_c = mastery_prob_c * c_discount_factor
```

---

## 七、文件结构

```
ecos/
├── cta/
│   ├── belief_engine.py      # CTA 信念引擎主入口（10 Steps）
│   ├── belief_state.py       # BeliefState / DimensionState 等数据类
│   ├── l1_evolution.py        # BKT 知识追踪
│   ├── l2_mirt.py            # MIRT 5D 估计
│   ├── tc_detector.py        # TC 阈值概念检测
│   ├── llm_critic.py         # LLM Critic（M2 W3 占位）
│   └── content.py           # Prompt 模板 / Misconception 库
│
├── persistence/
│   └── db.py                 # SQLite 数据库层
│
web/
├── api/
│   ├── app.py                # Flask 路由定义
│   ├── belief.py             # BeliefEngine Web 封装 + 7 组件 API
│   └── qmatrix.py            # Q-matrix 读取接口
├── ecos.db                   # SQLite 数据库文件（自动创建）
└── student/
    └── index.html            # 学生端 7 组件可视化 UI
│
data/
└── python_basics_q_matrix.json  # 26 道题目 Q-matrix
```

---

## 八、关键设计决策

### 8.1 为什么 MIRT 需要 2 次答题才能估计 theta？

MIRT 的 MAP 估计依赖似然函数：
```python
P(response | theta) = bernoulli(sigmoid(a·theta + d))
```

只有 1 次观测时，似然函数信息不足，无法区分各维度贡献。2 次以上才能通过不同的 loading 向量（a_specialized）分解出各维度能力。

### 8.2 为什么 TC 状态挂在 C 维度而不是独立？

TC（阈值概念）是元认知（C）层面的认知跳跃检测，与 Misconception 检测共享 C 维度的折扣机制，放在同一维度符合认知架构的统一性。

### 8.3 为什么选 SQLite 而不是 PostgreSQL？

Product Demo 阶段：
- 单文件数据库，无需额外服务
- `.db` 文件可直接分发
- 未来可无损迁移到 PostgreSQL（Schema 兼容）

---

## 九、当前限制与未来扩展

| 限制 | 当前状态 | 未来方向 |
|------|---------|---------|
| 选题策略 | 随机 | CD-CAT（PWKL 最优选题） |
| LearningDNA | placeholder | 真实数据采集 |
| LCA 干预 | 无 | M2 W4 双 Agent 互校 |
| TC 数量 | 5 个 topic | 扩展到全 Q-matrix |
| 多学生支持 | 单学生 | 教师端批量管理 |
| 数据导出 | SQLite 文件 | JSON/CSV 导出 |

---

*文档版本：v0.4.0 — ECOS Product Demo 业务逻辑流程*
