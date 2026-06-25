# 持久化与会话管理（Persistence & Session Management）

> **版本**：v1.0（2026-06-25）
> **性质**：工程层第 5 份文档（最后 1 份）——ECOS 持久化层 + 长期会话管理
> **基于**：[02-architecture.md §7 持久化与长期会话管理](../00-overview/02-architecture.md)、[v2.0 §4.2 SGE 中保留价值 + §4.4 AiBeing 借鉴](../deep-research/Cognitive-Digital-Twin-Deep-Research.md)、[04-risks.md §B3 长期数据稀疏 + §D1 未成年人合规](../00-overview/04-risks.md)、[01-cta-belief-engine.md](01-cta-belief-engine.md)、[02-lca-policy-engine.md](02-lca-policy-engine.md)、[03-bloom-goal-library.md](03-bloom-goal-library.md)、[04-dual-agent-calibration.md](04-dual-agent-calibration.md)、[03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md)
> **维护者**：Bisen & Claude

---

## 0. 模块定位

### 0.1 核心职责

**持久化与会话管理**是 ECOS 的"记忆层"——把 CTA / LCA / 互校 / Bloom 的所有运行时状态安全、可靠、可恢复地存储。核心职责：

1. **学生核心状态持久化**——5D + BloomProfile + LearningDNA + Trajectory 的长期存储
2. **干预历史记录**——每次 LCA 推荐的干预 + rationale + 实际效果
3. **证据日志**——LLM Critic 感知层输出 + Misconception 检测结果
4. **互校历史**——双 Agent 互校的质疑/反思/降级记录
5. **长期会话管理**——跨会话状态继承（学生下次打开仍保持连续）
6. **chunk 隔离**——支持 6~12 年长期运行（防止状态丢失）
7. **隐私保护**——未成年人数据合规 + 差分隐私

### 0.2 与其他模块的接口

```
┌─────────────────────────────────────────────────────────────┐
│ CTA / LCA / Dual Agent / Bloom（运行时）                      │
│   ↓ read / write                                             │
│ Persistence Layer（本模块）                                  │
│   ├── SQLite 主存储（学生状态 + 干预 + 证据 + 互校）         │
│   ├── 4 层内存管理（Hawking / Crystallizer / Identity / Arch）│
│   ├── ECOSSession 跨会话状态                                 │
│   ├── chunk 隔离与状态恢复                                   │
│   └── 隐私保护 + 加密 + 差分隐私                            │
│   ↓ read / write                                             │
│ App 层（学生端 UI / 教师端 UI / 家长端 UI）                   │
└─────────────────────────────────────────────────────────────┘
```

### 0.3 与 04-risks.md 风险对应

| 风险 | 缓解策略 |
|---|---|
| **B3 长期数据稀疏** | 冷启动策略 + 跨学期衰减 + 不承诺早期个性化 |
| **B4 数据采集质量差** | 异常检测 + 质量权重 + 反思日志引导 |
| **D1 未成年人数据合规** | 最小化采集 + 家长同意 + 数据本地化 + 差分隐私 |
| **A1 双 Agent 工程复杂度** | chunk 隔离（防止长跑状态丢失） |

### 0.4 文档目标读者

- **工程实现者**：按本文档实现 `ecos/persistence/` + `ecos/session/` Python 模块
- **运维**：数据库维护 + 备份策略
- **合规审查员**：未成年人数据保护机制

---

## 1. 整体架构

### 1.1 持久化总览

[02-architecture.md §7.1 学生状态持久化](../00-overview/02-architecture.md) 已给出 SQL 结构，本文档完善实现细节。

**存储层次**：

```
┌───────────────────────────────────────────────────────┐
│ L1 短期记忆（Hawking 风格）—— 内存中                   │
│   最近 N 次观测 + 状态缓存（in-memory dict）         │
│   生命周期：单次会话（session）                      │
│   容量：100-1000 条目                                  │
└───────────────────────────────────────────────────────┘
                            ↓ 写入
┌───────────────────────────────────────────────────────┐
│ L2 中期记忆（Crystallizer 风格）—— SQLite 主表        │
│   近期干预效果 + BloomProfile 演化快照                │
│   生命周期：学期内（4 个月）                          │
│   容量：1000-10000 条目                                │
└───────────────────────────────────────────────────────┘
                            ↓ 持久化
┌───────────────────────────────────────────────────────┐
│ L3 长期记忆（Identity 风格）—— SQLite 主表            │
│   学生核心 5D + BloomProfile + LearningDNA            │
│   生命周期：6-12 年                                  │
│   容量：10000-50000 学生                              │
└───────────────────────────────────────────────────────┘
                            ↓ 归档
┌───────────────────────────────────────────────────────┐
│ L4 持久记忆（Archive 风格）—— SQLite 归档表            │
│   成长轨迹快照 + 跨学期/学段画像                     │
│   生命周期：永久（不可变）                            │
│   容量：50000-500000 快照                              │
└───────────────────────────────────────────────────────┘
```

### 1.2 模块目录结构

```
ecos/persistence/
├── __init__.py
├── db.py                        # SQLite 连接管理
├── schema.sql                   # 数据库 schema
├── migrations/                  # 数据库迁移脚本
│   └── v1_to_v2.sql
├── models/
│   ├── __init__.py
│   ├── student.py              # 学生 ORM
│   ├── intervention.py         # 干预历史 ORM
│   ├── evidence.py             # 证据日志 ORM
│   ├── calibration.py          # 互校历史 ORM
│   └── bloom_goal.py           # BloomGoal ORM
├── memory_layers/
│   ├── __init__.py
│   ├── short_term.py           # L1 短期（Hawking）
│   ├── mid_term.py             # L2 中期（Crystallizer）
│   ├── long_term.py            # L3 长期（Identity）
│   └── archive.py              # L4 持久（Archive）
├── privacy/
│   ├── __init__.py
│   ├── encryption.py           # 加密存储
│   ├── differential_privacy.py # 差分隐私
│   └── anonymization.py       # 匿名化
├── backup/
│   ├── __init__.py
│   ├── export.py               # 数据导出
│   └── import.py               # 数据导入
└── tests/
    ├── test_db.py
    ├── test_memory_layers.py
    ├── test_privacy.py
    └── test_integration.py

ecos/session/
├── __init__.py
├── ecos_session.py              # ECOSSession 主类
├── epoch_counter.py             # 滚动 epoch 计数器
├── chunk_isolation.py           # chunk 隔离
└── tests/
```

### 1.3 与 CTA / LCA / 互校 / Bloom 接口契约

**写入接口**：

```python
class PersistenceLayer:
    """持久化层主接口"""

    # 学生状态
    def save_student_state(self, student_id: str, belief_state: 'BeliefState') -> None: ...
    def load_student_state(self, student_id: str) -> 'BeliefState': ...

    # 干预历史
    def save_intervention(self, intervention: 'CalibratedLCAResult') -> None: ...
    def load_intervention_history(self, student_id: str, time_range: 'Tuple[datetime, datetime]') -> List['CalibratedLCAResult']: ...

    # 证据日志
    def save_evidence(self, evidence: 'Observation') -> None: ...
    def load_evidence(self, student_id: str, limit: int = 100) -> List['Observation']: ...

    # 互校历史
    def save_calibration(self, calibration: 'CalibrationMessage') -> None: ...
    def load_calibration_history(self, student_id: str) -> List['CalibrationMessage']: ...

    # BloomGoal 查询
    def query_bloom_goal(self, query: 'BloomGoalQuery') -> 'BloomGoalQueryResult': ...
```

---

## 2. SQLite Schema 设计

### 2.1 学生表（student）

```sql
CREATE TABLE students (
    student_id TEXT PRIMARY KEY,
    grade_level INTEGER,                              -- 年级
    subject TEXT DEFAULT 'math',                      -- 主要学科
    created_at TIMESTAMP NOT NULL,
    last_active_at TIMESTAMP,

    -- 当前状态（JSON 序列化 BeliefState）
    current_state_5d BLOB,                            -- MIRT 5D + Σ_θ（加密）
    current_bloom_profile BLOB,                       -- 6 层分布（加密）
    current_learning_dna BLOB,                        -- 5 维特征（加密）

    -- 内容库状态（v0.5.0）
    tc_states BLOB,                                    -- 每个 TC 的状态（加密）
    misconception_history BLOB,                        -- 命中的 misconception 历史（加密）

    -- 成长轨迹（最近 N 个快照的压缩）
    trajectory_summary BLOB,                           -- 压缩的轨迹摘要

    -- 元数据
    confidence REAL DEFAULT 0.5,                       -- 整体置信度 0-1
    version TEXT DEFAULT 'v1.0',                      -- 状态版本

    -- 隐私保护
    consent_version INTEGER,                           -- 家长同意版本号
    anonymized_id TEXT,                                -- 匿名化 ID（用于研究）

    -- 索引
    UNIQUE(anonymized_id)
);

CREATE INDEX idx_students_grade ON students(grade_level);
CREATE INDEX idx_students_last_active ON students(last_active_at);
```

### 2.2 干预历史表（intervention）

```sql
CREATE TABLE interventions (
    intervention_id TEXT PRIMARY KEY,
    student_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- 干预内容
    intervention_type TEXT NOT NULL,                  -- 5 类干预
    bloom_target TEXT NOT NULL,                       -- 6 层 Bloom
    target_skills TEXT,                               -- JSON array
    target_misconceptions TEXT,                       -- JSON array
    target_tcs TEXT,                                  -- JSON array

    -- 参数
    difficulty REAL,
    quantity INTEGER,
    feedback_density REAL,
    scaffolding_level REAL,
    clt_level INTEGER,
    ca_stage INTEGER,

    -- 触发 Bjork 策略
    bjork_triggers TEXT,                              -- JSON array

    -- 期望效果
    expected_gain REAL,
    expected_risk REAL,

    -- rationale
    rationale_text TEXT,

    -- 实际效果（事后填充）
    actual_state_delta REAL,                          -- CTA 测量的状态变化
    actual_bloom_delta TEXT,                          -- JSON

    -- 因果归因（与 CTA L4 共享）
    causal_effect REAL,                               -- ATE
    causal_p_value REAL,
    causal_significant INTEGER,                       -- boolean

    -- 互校元数据
    calibration_round INTEGER,
    is_degraded_mode INTEGER DEFAULT 0,
    human_review_requested INTEGER DEFAULT 0,

    -- 索引
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX idx_interventions_student ON interventions(student_id, timestamp);
CREATE INDEX idx_interventions_bloom ON interventions(bloom_target);
CREATE INDEX idx_interventions_significant ON interventions(causal_significant);
```

### 2.3 证据日志表（evidence_log）

```sql
CREATE TABLE evidence_log (
    evidence_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    problem_id TEXT,
    timestamp TIMESTAMP NOT NULL,

    -- 原始观测
    raw_response TEXT,                                 -- 学生原始作答
    raw_response_time REAL,                           -- 答题时间（秒）
    raw_explanation TEXT,                             -- 学生解释文本
    raw_reflection TEXT,                              -- 学生反思文本

    -- LLM Critic 感知层输出
    llm_critic_input TEXT,                            -- 输入 prompt
    llm_critic_output TEXT,                           -- 输出 JSON
    llm_critic_temperature REAL,
    llm_critic_tokens INTEGER,

    -- 结构化观测
    structured_correctness INTEGER,                    -- boolean
    structured_explanation_quality REAL,
    structured_confusion_signals TEXT,                -- JSON array
    structured_self_evaluation REAL,

    -- 关联 CTA 状态更新
    state_before_update BLOB,                         -- CTA 状态变更前
    state_after_update BLOB,                          -- CTA 状态变更后
    state_delta REAL,                                 -- 状态变化量

    -- Misconception 检测（v0.5.0）
    misc_hits TEXT,                                   -- JSON array of MisconceptionHit

    -- TC 跨越检测（v0.5.0）
    tc_signals TEXT,                                  -- JSON array

    -- 质量评分（异常检测）
    quality_score REAL,                               -- 0-1，异常作答低分

    -- 索引
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX idx_evidence_student ON evidence_log(student_id, timestamp);
CREATE INDEX idx_evidence_problem ON evidence_log(problem_id);
CREATE INDEX idx_evidence_quality ON evidence_log(quality_score);
```

### 2.4 互校历史表（calibration_log）

```sql
CREATE TABLE calibration_log (
    calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,
    calibration_round INTEGER NOT NULL,

    -- 互校消息
    message_type TEXT NOT NULL,                       -- 9 种 MessageType
    message_payload TEXT,                            -- JSON

    -- 状态机
    state_before TEXT,                                -- 互校前状态
    state_after TEXT,                                 -- 互校后状态

    -- 触发条件
    trigger_reason TEXT,                              -- 如"信念质疑触发"
    trigger_evidence TEXT,                            -- JSON

    -- 模式
    interaction_mode TEXT,                            -- normal/belief_challenge/strategy_challenge/meta_reflection

    -- 结果
    outcome TEXT,                                     -- 互校结果描述
    human_review_requested INTEGER DEFAULT 0,
    fallback_to_single_agent INTEGER DEFAULT 0,

    -- 性能
    duration_ms INTEGER,

    -- 索引
    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX idx_calibration_student ON calibration_log(student_id, timestamp);
CREATE INDEX idx_calibration_mode ON calibration_log(interaction_mode);
```

### 2.5 BloomGoal 表（bloom_goals）

```sql
CREATE TABLE bloom_goals (
    goal_id TEXT PRIMARY KEY,
    subject TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    skill_name TEXT,
    bloom_layer INTEGER NOT NULL,                     -- 1-6

    description TEXT,
    cognitive_objectives TEXT,                        -- JSON array
    assessment_criteria TEXT,                         -- JSON array

    -- 关联内容（v0.5.0）
    threshold_concepts TEXT,                          -- JSON array
    misconceptions TEXT,                              -- JSON array

    -- 学习路径
    prerequisites TEXT,                               -- JSON array of goal_id
    follow_ups TEXT,                                  -- JSON array of goal_id

    -- 课程标准
    curriculum_standard_ref TEXT,

    -- 评估题目（多对多）
    -- 单独的 problem_bloom_goal 表关联

    -- 元数据
    created_by TEXT,
    created_at TIMESTAMP,
    version TEXT DEFAULT 'v1.0',

    UNIQUE(subject, skill_id, bloom_layer)
);

CREATE INDEX idx_bloom_goals_subject ON bloom_goals(subject, bloom_layer);
CREATE INDEX idx_bloom_goals_skill ON bloom_goals(skill_id);

-- 题目-BloomGoal 关联表（多对多）
CREATE TABLE problem_bloom_goals (
    problem_id TEXT NOT NULL,
    goal_id TEXT NOT NULL,
    PRIMARY KEY (problem_id, goal_id),
    FOREIGN KEY (goal_id) REFERENCES bloom_goals(goal_id)
);
```

### 2.6 轨迹快照表（trajectory_snapshots）

```sql
CREATE TABLE trajectory_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL,

    -- 快照类型
    snapshot_type TEXT,                              -- 'session_end' / 'week' / 'month' / 'semester' / 'grade_transition'
    epoch INTEGER,

    -- 完整状态（压缩）
    state_snapshot BLOB,                              -- 完整 BeliefState 压缩
    bloom_profile_snapshot BLOB,
    learning_dna_snapshot BLOB,

    -- 跨学期元数据（Phase 5+）
    grade_level INTEGER,
    semester TEXT,
    transfer_metadata TEXT,                           -- 跨学期迁移元数据

    FOREIGN KEY (student_id) REFERENCES students(student_id)
);

CREATE INDEX idx_trajectory_student ON trajectory_snapshots(student_id, timestamp);
CREATE INDEX idx_trajectory_type ON trajectory_snapshots(snapshot_type);
```

---

## 3. 4 层记忆实现

### 3.1 L1 短期记忆（Hawking 风格）

[SelfLab SGE Hawking 短期记忆](https://github.com/cnbison/SelfLab) 是"挫败感冷却"——ECOS 中对应"最近 N 次观测 + 状态缓存"。

```python
# ecos/persistence/memory_layers/short_term.py
from collections import deque
from typing import Deque, Dict, Any, Optional
from datetime import datetime, timedelta

class ShortTermMemory:
    """
    L1 短期记忆——Hawking 风格

    类似 SelfLab SGE 的 Hawking 短期挫败感冷却：
    - 内存中保留最近 N 次观测
    - 单次会话内有效
    - 会话结束 → 写入 L2 中期记忆
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        # 每个学生的 deque
        self._buffers: Dict[str, Deque['Observation']] = {}

    def add(self, observation: 'Observation'):
        """添加观测"""
        student_id = observation.student_id
        if student_id not in self._buffers:
            self._buffers[student_id] = deque(maxlen=self.max_size)

        # 清理过期
        self._cleanup_expired(student_id)

        self._buffers[student_id].append({
            'observation': observation,
            'timestamp': datetime.now(),
        })

    def get_recent(self, student_id: str, n: int = 10) -> List['Observation']:
        """获取最近 n 个观测"""
        if student_id not in self._buffers:
            return []
        return [item['observation'] for item in list(self._buffers[student_id])[-n:]]

    def flush_to_mid_term(self, student_id: str, mid_term: 'MidTermMemory'):
        """会话结束 → 写入 L2 中期记忆"""
        if student_id not in self._buffers:
            return
        for item in self._buffers[student_id]:
            mid_term.add(item['observation'])
        del self._buffers[student_id]

    def _cleanup_expired(self, student_id: str):
        """清理过期观测"""
        now = datetime.now()
        while self._buffers[student_id] and \
              now - self._buffers[student_id][0]['timestamp'] > self.ttl:
            self._buffers[student_id].popleft()
```

### 3.2 L2 中期记忆（Crystallizer 风格）

```python
# ecos/persistence/memory_layers/mid_term.py
class MidTermMemory:
    """
    L2 中期记忆——Crystallizer 风格

    类似 SelfLab SGE 的 Crystallizer：
    - 学期内有效（约 4 个月）
    - 存储近期干预效果 + BloomProfile 演化
    - 学期结束 → 关键事件写入 L3 长期记忆
    """

    def __init__(self, db: 'Database', ttl_days: int = 120):
        self.db = db
        self.ttl = timedelta(days=ttl_days)

    def add(self, observation: 'Observation'):
        """添加观测到 evidence_log 表"""
        self.db.insert_evidence(observation)

    def get_recent_interventions(
        self,
        student_id: str,
        days: int = 30,
    ) -> List['CalibratedLCAResult']:
        """获取最近 N 天的干预历史"""
        since = datetime.now() - timedelta(days=days)
        return self.db.query_interventions(
            student_id=student_id,
            since=since,
            order_by='timestamp DESC',
        )

    def get_recent_bloom_evolution(
        self,
        student_id: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """获取最近 N 天的 BloomProfile 演化"""
        since = datetime.now() - timedelta(days=days)
        return self.db.query_bloom_evolution(
            student_id=student_id,
            since=since,
        )

    def consolidate_to_long_term(self, student_id: str, long_term: 'LongTermMemory'):
        """学期结束 → 关键事件归档到 L3 长期记忆"""
        # 取最近学期的所有干预
        interventions = self.get_recent_interventions(student_id, days=120)
        # 提取关键事件（显著因果归因的干预）
        key_events = [
            iv for iv in interventions
            if iv.causal_significant and abs(iv.causal_effect or 0) > 0.1
        ]
        for event in key_events:
            long_term.archive_event(event)
```

### 3.3 L3 长期记忆（Identity 风格）

```python
# ecos/persistence/memory_layers/long_term.py
class LongTermMemory:
    """
    L3 长期记忆——Identity 风格

    类似 SelfLab SGE 的 Identity Layer：
    - 6-12 年长期存储
    - 学生核心 5D + BloomProfile + LearningDNA
    - 永久持久化（SQLite 主表）
    """

    def __init__(self, db: 'Database'):
        self.db = db

    def save_state(
        self,
        student_id: str,
        belief_state: 'BeliefState',
    ):
        """保存学生核心状态"""
        # 加密 + 序列化
        encrypted_state = self._encrypt_state(belief_state)
        self.db.upsert_student_state(
            student_id=student_id,
            current_state_5d=encrypted_state['state_5d'],
            current_bloom_profile=encrypted_state['bloom_profile'],
            current_learning_dna=encrypted_state['learning_dna'],
            tc_states=encrypted_state['tc_states'],
            misconception_history=encrypted_state['misc_history'],
            trajectory_summary=encrypted_state['trajectory'],
            confidence=belief_state.overall_confidence,
            last_active_at=datetime.now(),
        )

    def load_state(self, student_id: str) -> Optional['BeliefState']:
        """加载学生核心状态"""
        row = self.db.get_student(student_id)
        if row is None:
            return None
        # 解密 + 反序列化
        return self._decrypt_state(row)

    def archive_event(self, event: 'CalibratedLCAResult'):
        """归档关键事件到 L4 持久记忆"""
        self.db.insert_intervention(event)

    def _encrypt_state(self, belief_state: 'BeliefState') -> Dict[str, bytes]:
        """加密状态（敏感字段）"""
        # 5D + BloomProfile + LearningDNA + TC + Misc 都加密
        # 见 §7 隐私保护
        pass

    def _decrypt_state(self, row) -> 'BeliefState':
        """解密状态"""
        pass
```

### 3.4 L4 持久记忆（Archive 风格）

```python
# ecos/persistence/memory_layers/archive.py
class ArchiveMemory:
    """
    L4 持久记忆——Archive 风格

    不像 SelfLab 的 Narrative（AI 自传），ECOS 的 L4 是：
    - 成长轨迹快照（不可变）
    - 跨学期/学段画像
    - 永久归档（用于学术研究 + 护城河）
    """

    def __init__(self, db: 'Database'):
        self.db = db

    def save_snapshot(
        self,
        student_id: str,
        belief_state: 'BeliefState',
        snapshot_type: str,  # 'session_end' / 'week' / 'month' / 'semester' / 'grade_transition'
        epoch: int,
    ):
        """保存轨迹快照（不可变）"""
        self.db.insert_trajectory_snapshot(
            student_id=student_id,
            timestamp=datetime.now(),
            snapshot_type=snapshot_type,
            epoch=epoch,
            state_snapshot=self._compress_state(belief_state),
            bloom_profile_snapshot=self._compress_bloom(belief_state.bloom_profile),
            learning_dna_snapshot=self._compress_dna(belief_state.learning_dna),
            grade_level=self._get_grade_level(student_id),
        )

    def get_growth_trajectory(
        self,
        student_id: str,
        time_range: 'Tuple[datetime, datetime]',
    ) -> List['TrajectorySnapshot']:
        """获取成长轨迹"""
        return self.db.query_trajectory_snapshots(
            student_id=student_id,
            time_range=time_range,
            order_by='timestamp ASC',
        )

    def handle_grade_transition(
        self,
        student_id: str,
        old_grade: int,
        new_grade: int,
    ):
        """学段切换处理（Phase 5+）"""
        # 1. 保存学段结束快照
        self.save_snapshot(student_id, ..., snapshot_type='grade_transition')
        # 2. BloomProfile 迁移到下一学段起点
        # 3. 5D 状态迁移（保留主要维度，重置次要维度）
        # 4. 保留 LearningDNA（跨学段稳定）

    def _compress_state(self, belief_state: 'BeliefState') -> bytes:
        """压缩状态（用于归档）"""
        # 使用 msgpack 或类似高效序列化
        pass
```

---

## 4. ECOSSession 类

### 4.1 类接口

```python
# ecos/session/ecos_session.py
from dataclasses import dataclass, field
from typing import Dict, Optional, List
from datetime import datetime

@dataclass
class ECOSSession:
    """
    ECOS Session——单次学生与 ECOS 交互的会话

    借鉴 SelfLab TwinSession + AiBeing chat_agent：
    - 滚动 epoch 计数器
    - session 期间状态驻内存
    - 会话结束 → 保存到持久化层
    """

    # 基本信息
    session_id: str                              # UUID
    student_id: str
    started_at: datetime
    last_active_at: datetime

    # 4 层记忆（在内存中）
    short_term: 'ShortTermMemory'
    mid_term: 'MidTermMemory'
    long_term: 'LongTermMemory'
    archive: 'ArchiveMemory'

    # 当前状态（驻内存）
    current_belief_state: Optional['BeliefState'] = None
    current_intervention: Optional['CalibratedLCAResult'] = None

    # Epoch 计数器
    epoch_counter: int = 0

    # Session 配置
    config: 'ECOSSessionConfig' = field(default_factory=lambda: ECOSSessionConfig())

    # 状态
    is_active: bool = True
    is_dirty: bool = False                       # 是否有未保存的变更

class ECOSSessionConfig:
    """Session 配置"""
    auto_save_interval_sec: int = 60           # 自动保存间隔
    short_term_max_size: int = 100             # L1 容量
    mid_term_ttl_days: int = 120               # L2 周期
    session_timeout_sec: int = 3600            # session 超时（1 小时）
```

### 4.2 多轮对话状态

```python
class ECOSSession:
    def process_observation(self, observation: 'Observation') -> 'CalibratedLCAResult':
        """处理一次观测——多轮对话的核心"""
        # 更新 epoch 计数器
        self.epoch_counter += 1
        self.last_active_at = datetime.now()

        # Step 1: LLM Critic 感知（CTA 处理）
        # （已在 CTA 引擎中处理）

        # Step 2: CTA 更新状态
        cta_output = self.cta.update(observation, self.current_intervention)

        # Step 3: LCA 选择干预
        lca_result = self.lca.select_intervention(cta_output)

        # Step 4: 更新 session 状态
        self.current_belief_state = cta_output.belief_state
        self.current_intervention = lca_result

        # Step 5: 标记 dirty（待持久化）
        self.is_dirty = True

        # Step 6: 自动保存（按间隔）
        if self._should_auto_save():
            self.save()

        # Step 7: 返回给 App 层
        return lca_result

    def save(self):
        """保存 session 到持久化层"""
        if not self.is_dirty:
            return
        # 保存 L3 长期记忆
        self.long_term.save_state(self.student_id, self.current_belief_state)
        # 保存当前干预到 L2
        self.mid_term.add(self.current_intervention)
        # 保存轨迹快照到 L4（按 snapshot_type）
        if self._should_snapshot():
            self.archive.save_snapshot(
                self.student_id,
                self.current_belief_state,
                snapshot_type='session_end',
                epoch=self.epoch_counter,
            )
        self.is_dirty = False
```

### 4.3 滚动 epoch 计数器

```python
# ecos/session/epoch_counter.py
class EpochCounter:
    """
    滚动 epoch 计数器——记录会话内的轮次

    类似 SelfLab SGE 的 epoch 概念：
    - 单次观测 = 1 epoch
    - epoch 计数器在 session 期间持续增加
    - 跨 session 时保留（用于累计追踪）
    """

    def __init__(self, db: 'Database'):
        self.db = db

    def get_current_epoch(self, student_id: str, session_id: str) -> int:
        """获取当前 epoch"""
        session = self.db.get_session(session_id)
        if session is None:
            return 0
        return session.epoch_counter

    def increment(self, session_id: str) -> int:
        """增加 epoch"""
        session = self.db.get_session(session_id)
        session.epoch_counter += 1
        self.db.update_session(session)
        return session.epoch_counter
```

### 4.4 跨会话继承

```python
class ECOSSession:
    @classmethod
    def load_or_create(
        cls,
        student_id: str,
        session_config: 'ECOSSessionConfig',
    ) -> 'ECOSSession':
        """
        加载已有 session 或创建新 session

        关键：跨会话状态继承——学生下次打开仍保持连续
        """
        # 尝试加载最近未结束的 session
        existing_session = cls._try_load_recent_session(student_id)
        if existing_session:
            return existing_session

        # 创建新 session
        return cls._create_new_session(student_id, session_config)

    def _try_load_recent_session(self, student_id: str) -> Optional['ECOSSession']:
        """尝试加载最近未结束的 session（30 分钟内）"""
        recent_sessions = self.db.query_sessions(
            student_id=student_id,
            since=datetime.now() - timedelta(minutes=30),
            is_active=True,
            order_by='last_active_at DESC',
            limit=1,
        )
        if recent_sessions:
            return self._restore_session(recent_sessions[0])
        return None

    def _restore_session(self, session_record) -> 'ECOSSession':
        """从持久化层恢复 session"""
        session = ECOSSession(
            session_id=session_record.session_id,
            student_id=session_record.student_id,
            started_at=session_record.started_at,
            last_active_at=session_record.last_active_at,
            # 从 L3 长期记忆加载状态
            current_belief_state=self.long_term.load_state(session_record.student_id),
            # 从 L1 短期记忆恢复最近观测
            short_term=self._restore_short_term(session_record.session_id),
            epoch_counter=session_record.epoch_counter,
        )
        return session

    def close(self):
        """关闭 session——保存到持久化层"""
        # 保存 L3 长期记忆
        self.long_term.save_state(self.student_id, self.current_belief_state)
        # L1 短期记忆 → L2 中期记忆
        self.short_term.flush_to_mid_term(self.student_id, self.mid_term)
        # L2 → L4 持久记忆（关键事件归档）
        self.mid_term.consolidate_to_long_term(self.student_id, self.archive)
        # 标记 session 关闭
        self.db.update_session(self.session_id, is_active=False)
        self.is_active = False
```

---

## 5. chunk 隔离

### 5.1 chunk 概念

参考 [SelfLab SGE M2.2 chunk 隔离](https://github.com/cnbison/SelfLab)——ECOS 支持 6~12 年长期运行，必须防止状态丢失。

```python
# ecos/session/chunk_isolation.py
class ChunkIsolation:
    """
    Chunk 隔离——支持 6-12 年长跑

    chunk 概念：
    - 每个 chunk 是一个独立的处理单元
    - chunk 完成后立即持久化
    - 下次启动从最后完成的 chunk 恢复
    - 防止长跑过程中状态丢失
    """

    def __init__(self, db: 'Database', chunk_duration_epochs: int = 100):
        self.db = db
        self.chunk_size = chunk_duration_epochs

    def should_create_new_chunk(self, student_id: str, current_epoch: int) -> bool:
        """判断是否应创建新 chunk"""
        last_chunk = self.db.get_last_chunk(student_id)
        if last_chunk is None:
            return True
        return current_epoch - last_chunk.end_epoch >= self.chunk_size

    def create_chunk_boundary(
        self,
        student_id: str,
        belief_state: 'BeliefState',
        end_epoch: int,
    ):
        """创建 chunk 边界"""
        self.db.create_chunk(
            student_id=student_id,
            start_epoch=self._get_last_chunk_end_epoch(student_id),
            end_epoch=end_epoch,
            state_snapshot=belief_state,
        )

    def recover_from_last_chunk(self, student_id: str) -> Optional['BeliefState']:
        """从最后一个 chunk 恢复"""
        last_chunk = self.db.get_last_chunk(student_id)
        if last_chunk is None:
            return None
        return self._decompress_state(last_chunk.state_snapshot)
```

### 5.2 chunk 边界处理

```python
class ECOSSession:
    def process_observation(self, observation):
        # ... 处理逻辑 ...

        # 检查 chunk 边界
        if self.chunk_isolation.should_create_new_chunk(
            self.student_id, self.epoch_counter
        ):
            # 保存 chunk 边界
            self.chunk_isolation.create_chunk_boundary(
                self.student_id,
                self.current_belief_state,
                self.epoch_counter,
            )
            self.last_chunk_epoch = self.epoch_counter
```

### 5.3 状态恢复

```python
@classmethod
def recover_from_crash(cls, student_id: str, session_config) -> 'ECOSSession':
    """从崩溃恢复"""
    chunk_isolation = ChunkIsolation(db, session_config.chunk_size)
    # 1. 从最后一个 chunk 恢复
    recovered_state = chunk_isolation.recover_from_last_chunk(student_id)
    if recovered_state is None:
        # 2. 没有 chunk，从 L3 长期记忆恢复
        recovered_state = long_term.load_state(student_id)
    if recovered_state is None:
        # 3. 全新学生，创建空 session
        return cls._create_new_session(student_id, session_config)

    # 4. 创建恢复 session
    session = ECOSSession(...)
    session.current_belief_state = recovered_state
    return session
```

---

## 6. 数据迁移与备份

### 6.1 数据库迁移

```python
# ecos/persistence/migrations/v1_to_v2.py
class V1ToV2Migration:
    """v1 → v2 迁移"""
    def up(self, db):
        # 添加新字段
        db.execute("ALTER TABLE students ADD COLUMN consent_version INTEGER DEFAULT 1")
        db.execute("ALTER TABLE students ADD COLUMN anonymized_id TEXT")
        # 创建新索引
        db.execute("CREATE INDEX idx_students_anonymized ON students(anonymized_id)")

    def down(self, db):
        # 回滚
        db.execute("ALTER TABLE students DROP COLUMN consent_version")
        db.execute("ALTER TABLE students DROP COLUMN anonymized_id")
```

### 6.2 数据备份

```python
# ecos/persistence/backup/export.py
class DataExporter:
    """数据导出——用于备份和迁移"""

    def export_student(self, student_id: str) -> Dict[str, Any]:
        """导出单个学生的完整数据"""
        return {
            'student': self.db.get_student(student_id),
            'belief_state': self._export_state(student_id),
            'interventions': self.db.query_interventions(student_id=student_id),
            'evidence': self.db.query_evidence(student_id=student_id, limit=10000),
            'calibration': self.db.query_calibration(student_id=student_id),
            'trajectory': self.db.query_trajectory(student_id=student_id),
        }

    def export_all(self) -> Dict[str, Any]:
        """导出所有数据"""
        return {
            'students': self.db.query_all_students(),
            'bloom_goals': self.db.query_all_bloom_goals(),
            'export_timestamp': datetime.now().isoformat(),
        }
```

---

## 7. 隐私保护

[04-risks.md §D1 未成年人数据合规](../00-overview/04-risks.md) 是关键风险。

### 7.1 端侧计算

```python
# ecos/persistence/privacy/encryption.py
class EncryptionLayer:
    """敏感字段加密"""

    def __init__(self, master_key: bytes):
        self.fernet = Fernet(master_key)

    def encrypt(self, data: Any) -> bytes:
        """加密任意数据"""
        serialized = msgpack.packb(data)
        return self.fernet.encrypt(serialized)

    def decrypt(self, encrypted: bytes) -> Any:
        """解密"""
        decrypted = self.fernet.decrypt(encrypted)
        return msgpack.unpackb(decrypted, raw=False)
```

**敏感字段**（必须加密）：
- `current_state_5d`（学生能力向量）
- `current_bloom_profile`（学习画像）
- `current_learning_dna`（个性化特征）
- `tc_states`（学习状态）
- `misconception_history`（错误记录）

**非敏感字段**（不加密）：
- `student_id`、`grade_level`、`last_active_at`、`confidence`

### 7.2 差分隐私（聚合数据发布）

```python
# ecos/persistence/privacy/differential_privacy.py
class DifferentialPrivacy:
    """差分隐私——聚合数据发布时"""

    def __init__(self, epsilon: float = 1.0):
        self.epsilon = epsilon

    def add_laplace_noise(self, value: float, sensitivity: float) -> float:
        """添加拉普拉斯噪声"""
        scale = sensitivity / self.epsilon
        noise = np.random.laplace(0, scale)
        return value + noise

    def anonymize_aggregate(
        self,
        aggregates: Dict[str, float],
        min_group_size: int = 10,
    ) -> Dict[str, float]:
        """聚合匿名化（最小组 10）"""
        anonymized = {}
        for key, value in aggregates.items():
            if aggregates.get('_group_size', 1) < min_group_size:
                anonymized[key] = None  # 隐藏小样本
            else:
                anonymized[key] = self.add_laplace_noise(value, sensitivity=0.1)
        return anonymized
```

### 7.3 匿名化（研究发布）

```python
# ecos/persistence/privacy/anonymization.py
class Anonymizer:
    """匿名化（用于学术研究 + 数据共享）"""

    def anonymize_student_id(self, student_id: str) -> str:
        """生成不可逆匿名 ID"""
        return hashlib.sha256(
            (student_id + self.salt).encode()
        ).hexdigest()[:16]

    def anonymize_text(self, text: str) -> str:
        """文本匿名化（移除 PII）"""
        # 移除姓名、学校、地点等
        # 使用 NER 模型或规则
        pass
```

### 7.4 数据最小化

```python
class DataMinimizationPolicy:
    """数据最小化策略（[04-risks.md §D1 缓解策略](../00-overview/04-risks.md)）"""
    # 不采集的数据
    NEVER_COLLECT = [
        'device_id',
        'ip_address',
        'precise_location',
        'biometric_data',
        'browsing_history_outside_ecos',
    ]

    # 必须家长同意的数据
    REQUIRES_PARENT_CONSENT = [
        'name',           # 学生姓名
        'school_name',    # 学校
        'grade_level',    # 年级
        'response_data',  # 学习行为数据
    ]

    def validate_collection(self, field_name: str, has_consent: bool) -> bool:
        """验证采集合法性"""
        if field_name in self.NEVER_COLLECT:
            return False
        if field_name in self.REQUIRES_PARENT_CONSENT and not has_consent:
            return False
        return True
```

---

## 8. 测试策略

### 8.1 单元测试（覆盖率 ≥ 80%）

| 模块 | 测试重点 | 覆盖率目标 |
|---|---|---|
| `db.py` | SQLite 连接、事务 | ≥ 85% |
| `memory_layers/short_term.py` | L1 Hawking 冷却 + TTL | ≥ 90% |
| `memory_layers/mid_term.py` | L2 中期持久化 | ≥ 85% |
| `memory_layers/long_term.py` | L3 长期加密 + 序列化 | ≥ 90% |
| `memory_layers/archive.py` | L4 压缩 + 跨学期 | ≥ 85% |
| `session/ecos_session.py` | 跨会话继承 + epoch | ≥ 90% |
| `session/chunk_isolation.py` | chunk 边界 + 崩溃恢复 | ≥ 85% |
| `privacy/encryption.py` | 加密 + 解密 | ≥ 90% |
| `privacy/differential_privacy.py` | 拉普拉斯噪声 + 聚合匿名化 | ≥ 85% |
| `backup/export.py` | 数据导出完整性 | ≥ 85% |

### 8.2 集成测试

```python
# ecos/persistence/tests/test_integration.py
def test_full_lifecycle():
    """完整生命周期测试"""
    # 1. 创建 session
    session = ECOSSession.load_or_create("S001", config)
    # 2. 100 次观测
    for i in range(100):
        observation = generate_observation("S001", i)
        lca_result = session.process_observation(observation)
        assert lca_result is not None
    # 3. 关闭 session
    session.close()
    # 4. 重新加载（验证状态保留）
    session2 = ECOSSession.load_or_create("S001", config)
    assert session2.epoch_counter == 100
    assert session2.current_belief_state is not None
    # 5. 验证 L4 归档
    snapshots = archive.get_growth_trajectory("S001", (start, end))
    assert len(snapshots) > 0

def test_crash_recovery():
    """崩溃恢复测试"""
    # 模拟处理 50 次观测
    session = ECOSSession.load_or_create("S001", config)
    for i in range(50):
        session.process_observation(generate_observation("S001", i))
    # 模拟崩溃（不调用 close）
    del session
    # 恢复
    session_recovered = ECOSSession.recover_from_crash("S001", config)
    assert session_recovered.epoch_counter == 50

def test_chunk_isolation():
    """chunk 隔离测试"""
    chunk = ChunkIsolation(db, chunk_size=10)
    for i in range(30):
        if chunk.should_create_new_chunk("S001", i):
            chunk.create_chunk_boundary("S001", state, i)
    # 验证有 3 个 chunk（0-10, 11-20, 21-30）
    chunks = db.query_chunks("S001")
    assert len(chunks) == 3
```

### 8.3 性能基准（对照 04-risks.md §B3 + §D1）

| 指标 | 阈值 | 测试场景 |
|---|---|---|
| **状态保存延迟** | P95 ≤ 100ms | 单次 save_state |
| **状态加载延迟** | P95 ≤ 200ms | 单次 load_state |
| **自动保存延迟** | P95 ≤ 500ms | 60 秒自动保存 |
| **崩溃恢复时间** | ≤ 5 秒 | chunk 恢复 |
| **差分隐私聚合延迟** | ≤ 1 秒 | 10000 学生聚合 |
| **加密/解密吞吐** | ≥ 1000 ops/sec | 批量测试 |

### 8.4 隐私合规测试

```python
def test_data_minimization():
    """数据最小化测试"""
    policy = DataMinimizationPolicy()
    # 验证禁止字段
    assert not policy.validate_collection('device_id', has_consent=True)
    # 验证需要同意的字段
    assert not policy.validate_collection('name', has_consent=False)
    assert policy.validate_collection('name', has_consent=True)

def test_anonymization():
    """匿名化测试"""
    anonymizer = Anonymizer(salt='secret')
    id1 = anonymizer.anonymize_student_id("S001")
    id2 = anonymizer.anonymize_student_id("S002")
    # 不同学生 → 不同 ID
    assert id1 != id2
    # 同一学生 → 相同 ID（确定性）
    assert anonymizer.anonymize_student_id("S001") == id1
    # 不可逆
    assert id1 != "S001"

def test_encryption():
    """加密测试"""
    encryption = EncryptionLayer(master_key)
    state = BeliefState(...)
    encrypted = encryption.encrypt(state)
    # 加密后不含明文
    assert b"student_id" not in encrypted
    # 解密恢复
    decrypted = encryption.decrypt(encrypted)
    assert decrypted.student_id == state.student_id
```

---

## 9. MVP 范围（Phase 4）

### 9.1 MVP 包含的组件

| 组件 | 实现状态 |
|---|---|
| SQLite 主存储 + Schema | ✅ MVP |
| 4 层记忆（L1-L4）| ✅ MVP（简化）|
| ECOSSession 跨会话继承 | ✅ MVP |
| epoch 计数器 | ✅ MVP |
| chunk 隔离（崩溃恢复）| ✅ MVP |
| 数据迁移基础 | ✅ MVP |
| 数据导出 | ✅ MVP |
| 加密存储 | ✅ MVP |
| 差分隐私（基础）| ✅ MVP |
| 数据最小化策略 | ✅ MVP |
| 匿名化（基础）| ✅ MVP |

### 9.2 MVP 不包含的组件

- ❌ 跨学期/学段画像迁移（Phase 5+）
- ❌ 高级差分隐私算法（Phase 5+）
- ❌ 端侧计算完整实现（Phase 5+）
- ❌ 实时数据流（Phase 5+）
- ❌ 跨设备同步（Phase 6+）

### 9.3 MVP 数据规模

| 数据 | MVP | Phase 5 | Phase 6 |
|---|---|---|---|
| 学生数 | 50-100 | 500-1000 | 5000-10000 |
| 每学生 evidence_log | 100-1000 | 1000-10000 | 10000-50000 |
| 每学生 interventions | 20-100 | 200-1000 | 2000-5000 |
| 每学生 trajectory_snapshots | 4-16 | 50-200 | 500-2000 |
| BloomGoal 库 | 32 条 | 235 条 | 670 条 |

---

## 10. 关联文档

- **同级工程层**：
  - [01-cta-belief-engine.md](01-cta-belief-engine.md) — CTA 引擎（写入状态到 L3）
  - [02-lca-policy-engine.md](02-lca-policy-engine.md) — LCA 引擎（写入干预到 L2）
  - [03-bloom-goal-library.md](03-bloom-goal-library.md) — Bloom 库（写入 bloom_goals 表）
  - [04-dual-agent-calibration.md](04-dual-agent-calibration.md) — 双 Agent 互校（写入 calibration_log 表）
- **上层文档**：
  - [02-architecture.md §7 持久化与长期会话管理](../00-overview/02-architecture.md) — 本文档的架构依据
  - [03-roadmap.md §2.2 M2 里程碑](../00-overview/03-roadmap.md) — 工程任务
  - [04-risks.md §B3 + §D1](../00-overview/04-risks.md) — 风险缓解策略
- **核心论证**：
  - [v2.0 §4.2 SGE 中保留价值 + §4.4 AiBeing 借鉴](../deep-research/Cognitive-Digital-Twin-Deep-Research.md) — 工程借鉴来源
- **背景**：
  - [MIGRATION-FROM-SELFLAB.md](../MIGRATION-FROM-SELFLAB.md) §2.2 共享基础文档

---

## 11. 版本与维护

- **v1.0**（2026-06-25）— 初版（工程层最后 1 份）

**待办（影响本文档时同步更新）**：
- 当 Phase 5+ 跨学期/学段迁移完成后，§3.4 L4 增加 grade_transition 处理
- 当 Phase 4 MVP 实验完成后，回填 §8.3 实际性能基准 vs 阈值

---

**创建日期**：2026-06-25
**维护者**：Bisen & Claude
