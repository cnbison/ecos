# ECOS 认知干预闭环工作流

> **对应**：research/10-engineering/01-cta-belief-engine.md §9 集成点
> **版本**：v0.34.0（基于 Claude Skills Demo 2026-07-05 验证）

---

## 1. 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      ECOS 双 Agent 系统                       │
│                                                             │
│   ┌─────────────┐     ┌─────────────┐                      │
│   │    CTA      │◄────│    LCA      │                      │
│   │ 认知追踪 Agent │    │ 干预决策 Agent │                      │
│   └──────┬──────┘     └──────┬──────┘                      │
│          │                   │                              │
│          │  干预建议          │ 策略决策                      │
│          ▼                   ▼                              │
│   ┌─────────────────────────────────┐                       │
│   │          BeliefEngine           │                       │
│   │  ┌─────┐  ┌─────┐  ┌─────┐     │                       │
│   │  │ 5D  │  │Bloom│  │  C  │     │                       │
│   │  │State │  │Profile│  │折扣 │     │                       │
│   │  └─────┘  └─────┘  └─────┘     │                       │
│   └─────────────────────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

---

## 2. 完整工作流（分步骤）

### 流程图

```
学生答题
    │
    ▼
┌─────────────────┐
│ Observation      │
│ 捕获学生回答      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ BeliefEngine    │
│ .update()       │
└────────┬────────┘
         │
    ┌────┴──────────────────────────────────┐
    │  分 6 步处理（perception.py §感知流程）  │
    ├────────────────────────────────────────┤
    │ Step 1: L1 BKT 更新（K/P/S 维度）        │
    │ Step 2: L2 MIRT 更新（X 维度）           │
    │ Step 3: BloomProfile 更新               │
    │ Step 4: ExplanationCritic 解释层评估     │
    │ Step 5: PerceptionCritic 感知层评估  ◄──┼──┐
    │ Step 6: MisconceptionDetector C 维度折扣 │  │
    └────────────────────────────────────────┘  │
         │                                       │
         │ C 维度 discount_factor 变化              │
         │ (misconception 命中 → 折扣)              │
         ▼                                       │
┌─────────────────┐                               │
│ BeliefState     │◄──────────────────────────────┘
│ C 维度更新完成   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ LCA 干预决策    │◄── 基于 discount_factor 决定是否干预
└────────┬────────┘
         │
    ┌────┴──────────┐
    │ discount_factor│
    │ < 0.7 ？       │
    └────┬──────────┘
         │
    ┌────┴────────────────────┐
    │ 是                      │ 否
    ▼                         ▼
┌──────────┐            ┌──────────────┐
│ 触发干预 │            │ 继续观测       │
│ 流程     │            │ （不干预）     │
└────┬─────┘            └───────────────┘
     │
     ▼
┌─────────────────────────┐
│ 执行干预                │
│ （LLM 直接对学生说话）   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 学生重新答题             │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ BeliefEngine           │
│ 重新测量 belief state   │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ 验证干预效果             │
│ （misconception 清除？） │
└─────────────────────────┘
```

---

## 3. 详细步骤说明

### Step 1-4：基础 Belief State 更新

```
见 belief_engine.py § BeliefEngine.update()
L1 BKT → L2 MIRT → BloomProfile → ExplanationCritic
```

### Step 5：PerceptionCritic 感知层

**文件**：`ecos/cta/llm_critic/perception.py`

**输入**：

- `problem`：题目描述
- `correct_answer`：正确答案
- `student_correctness`：学生作答是否正确
- `student_explanation`：学生写的解释文本

**处理**：

```
输入文本
   │
   ▼
LLM（PerceptionCritic.perceive()）
   │
   ├── correctness：学生是否真正理解（≠ 作答对错）
   ├── explanation_quality：0.0-1.0
   ├── confusion_signals：困惑信号列表
   ├── self_evaluation：学生自信度
   ├── skill_ids：推断的知识点 ID
   ├── bloom_level：L1-L4 认知层级
   └── key_concepts：涉及的概念列表
```

**输出**：`PerceptionOutput`

---

### Step 6：MisconceptionDetector C 维度折扣

**文件**：`ecos/cta/llm_critic/misconception_detector.py`

**核心逻辑**：

```
学生解释文本
   │
   ▼
MisconceptionDetector.detect()
   │
   ├── library_str：可选，领域专属 misconception 库
   │                （默认使用数学库，可注入 Claude Skills 等其他库）
   │
   ▼
LLM 判断是否触发 misconception
   │
   ├── misc_id：命中的 ID（如 "M1"）或空字符串 ""
   ├── confidence：0.0-1.0
   ├── evidence_text：学生原文片段（直接引用）
   └── correction_strategy：修正策略 ID
   │
   ▼
misconception_hits + discount_factor 更新
   │
   └── discount_factor = 1.0 - Σ(misconception_confidence × 0.3)
```

**C 维度折扣规则**：

```
无 misconception 命中：discount_factor = 1.0（完整置信）
M1 命中（置信 0.95）：discount_factor = 1.0 - 0.95×0.3 = 0.715
M1+M2 同时命中：discount_factor = 1.0 - (0.95+0.95)×0.3 = 0.43
全部清除：discount_factor = 1.0
```

---

### Step 7：LCA 干预决策

**决策条件**：

```
discount_factor < 0.7  →  触发干预
discount_factor ≥ 0.7  →  继续观测（不干预）
```

**干预类型（LCA 选择）**：

| 类型 | 适用场景 | 效果 |
|------|---------|------|
| EXPLANATORY | misconception 明确，需要概念澄清 | 直接解释 + 类比 |
| Socratic | 学生似懂非懂，需要引导 | 提问引导学生自己发现 |
| WORKED_EXAMPLE | 程序性知识缺失 | 演示完整解题过程 |
| HINT | 轻微困惑 | 轻量提示，不直接给答案 |

**干预执行后**：

- 学生重新答题
- BeliefEngine 重新测量
- 验证 discount_factor 是否恢复

---

## 4. 关键代码接口

### BeliefEngine.update()

```python
# ecos/cta/belief_engine.py

def update(
    self,
    observation: Observation,
) -> UpdateResult:
    """完整 belief state 更新流程。

    Step 1: L1 BKT（K/P/S）
    Step 2: L2 MIRT（X）
    Step 3: BloomProfile
    Step 4: ExplanationCritic
    Step 5: PerceptionCritic  ← 感知层
    Step 6: MisconceptionDetector  ← C 维度折扣
    """
```

### MisconceptionDetector.detect()

```python
# ecos/cta/llm_critic/misconception_detector.py

def detect(
    self,
    student_explanation: str,
    problem: str = "",
    library_str: str | None = None,  # ← 可注入领域专属库
) -> MisconceptionDetectionOutput:
    """检测 misconception 命中。

    Args:
        library_str: 领域专属库（如 ClaudeSkillsMisconceptionLibrary）。
                    默认使用数学 misconception 库。
    """
```

### BeliefEngine.C 维度折扣

```python
# ecos/cta/belief_state.py

@dataclass
class ConfidenceDimensionState:
    discount_factor: float = 1.0
    misconception_hits: list[MisconceptionHit] = field(default_factory=list)
    pseudo_confidence: bool = False  # True = C 是"挣来的"

    def apply_misconception_discount(self, hits: list[MisconceptionHit]):
        """每次 misconception 命中时调用，计算 discount_factor。"""
        if not hits:
            self.discount_factor = 1.0
            self.misconception_hits = []
            return
        total = sum(h.confidence for h in hits)
        self.discount_factor = max(0.0, 1.0 - total * 0.3)
        self.misconception_hits = hits
```

---

## 5. 领域专属 Library 注入示例

### 数学库（默认）

```python
detector = MisconceptionDetector(llm_client)
result = detector.detect(student_explanation)  # 使用默认数学库
```

### Claude Skills 库（注入）

```python
from ecos.cta.content.claude_skills_misconceptions import ClaudeSkillsMisconceptionLibrary

lib = ClaudeSkillsMisconceptionLibrary()
lines = ['候选 Misconception 条目：']
for e in lib.all_entries():
    lines.append(f'{e.misc_id} | {e.name} | {e.description}')
library_str = '\n'.join(lines)

result = detector.detect(
    student_explanation="skill不就是/command吗？",
    library_str=library_str,  # ← 注入 Claude Skills 库
)
# → misc_id='M1', confidence=0.95
```

---

## 6. 完整闭环验证（Demo）

```
Round 1: 初始测量
  Q1: "skill可以用斜杠命令来直接调用"
  → M1 触发（0.95），discount_factor=0.715

Round 2: 干预生成
  CTA → LCA: EXPLANATORY + 类比策略

Round 3: 干预执行 + 重新测量
  Q1: "skill不能用斜杠命令来直接调用，而是LLM自主决定"
  → 无 misconception（0.0），discount_factor=1.0
  ✅ 闭环验证通过
```

---

## 7. 相关文件索引

| 文件 | 作用 |
|------|------|
| `ecos/cta/belief_engine.py` | BeliefEngine.update() 主流程 |
| `ecos/cta/belief_state.py` | BeliefState + ConfidenceDimensionState |
| `ecos/cta/llm_critic/perception.py` | PerceptionCritic 感知层 |
| `ecos/cta/llm_critic/misconception_detector.py` | MisconceptionDetector C 维度 |
| `ecos/cta/llm_critic/schemas.py` | 输出 schema 定义 |
| `ecos/cta/content/claude_skills_misconceptions.py` | Claude Skills Misconception 库 |
| `ecos/cta/content/math_misconceptions.py` | 数学 Misconception 库（默认）|
| `discussions/2026-07-05-claude-skills-demo-round1-3.md` | Demo 完整存档 |
