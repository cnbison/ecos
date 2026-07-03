"""ECOSSession——跨会话状态管理.

对应 research/10-engineering/05-persistence-session.md §4。

MVP 范围：
  - 单次会话内状态驻内存
  - 会话结束 → 写入持久化层
  - 滚动 epoch 计数器
  - 自动保存（按时间间隔）
  - chunk 隔离（滚动快照，防止状态丢失）
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from ..cta.belief_engine import BeliefEngine, BeliefEngineConfig
from ..cta.belief_state import BeliefState, BloomLevel
from ..persistence.db import Database, DatabaseConfig
from .chunk_isolation import ChunkIsolation


@dataclass
class ECOSSessionConfig:
    """Session 配置（MVP）。"""
    auto_save_interval_sec: int = 60
    short_term_max_size: int = 100
    session_timeout_sec: int = 3600
    snapshot_interval_epochs: int = 20
    chunk_threshold_epochs: int = 100


@dataclass
class ECOSSession:
    """ECOS 单次会话管理。

    用法：
        db = Database("ecos.db")
        db.init_schema()
        session = ECOSSession(student_id="student_001", db=db)
        session.start()

        result = session.process_observation(observation)
        session.save()  # 或等 auto_save 触发

        session.close()
    """

    session_id: str
    student_id: str
    started_at: datetime
    last_active_at: datetime
    config: ECOSSessionConfig = field(default_factory=ECOSSessionConfig)
    db: Optional[Database] = field(default=None, repr=False)

    # CTA 引擎
    cta_engine: BeliefEngine = field(default=None)
    # 当前状态
    current_belief_state: Optional[BeliefState] = field(default=None, repr=False)
    # Epoch 计数器
    epoch_counter: int = 0
    # 脏标记
    is_dirty: bool = False
    # chunk 管理
    chunk: Optional[ChunkIsolation] = field(default=None)

    def __post_init__(self) -> None:
        if self.cta_engine is None:
            self.cta_engine = BeliefEngine()

    @classmethod
    def create(
        cls,
        student_id: str,
        db: Database | None = None,
        config: ECOSSessionConfig | None = None,
    ) -> "ECOSSession":
        """工厂方法：创建并初始化一个新 session。"""
        session = cls(
            session_id=str(uuid.uuid4()),
            student_id=student_id,
            started_at=datetime.now(),
            last_active_at=datetime.now(),
            config=config or ECOSSessionConfig(),
            db=db,
        )
        session.start()
        return session

    def start(self) -> None:
        """启动 session——从持久化恢复或创建新状态。"""
        if self.db is not None:
            self.db.upsert_student(self.student_id)
            saved = self.db.load_student_state(self.student_id)
            if saved is not None:
                # MVP：从 dict 重建 BeliefState（简化版本）
                self.current_belief_state = self._restore_state(saved)
            else:
                self.current_belief_state = self.cta_engine.create_initial_state(self.student_id)
        else:
            self.current_belief_state = self.cta_engine.create_initial_state(self.student_id)

        # 初始化 chunk
        self.chunk = ChunkIsolation(
            student_id=self.student_id,
            threshold_epochs=self.config.chunk_threshold_epochs,
        )

    def process_observation(
        self,
        observation: "Observation",
    ) -> BeliefState:
        """处理一次学生观测——更新 CTA 状态 + epoch 计数。

        Args:
            observation: 来自 BeliefEngine.Observation

        Returns:
            更新后的 BeliefState
        """
        self.epoch_counter += 1
        self.last_active_at = datetime.now()

        # CTA 更新
        self.current_belief_state = self.cta_engine.update(
            self.current_belief_state, observation
        )
        self.is_dirty = True

        # 自动保存
        if self._should_auto_save():
            self.save()

        # chunk 检查（学期边界等）
        self._check_chunk_boundary()

        return self.current_belief_state

    def save(self) -> None:
        """保存 session 到持久化层。"""
        if not self.is_dirty or self.db is None:
            return

        state = self.current_belief_state
        self.db.save_student_state(self.student_id, state)

        # 按周期快照
        if self.epoch_counter % self.config.snapshot_interval_epochs == 0:
            self.db.save_trajectory_snapshot(
                student_id=self.student_id,
                snapshot_type="session_end",
                epoch=self.epoch_counter,
            )

        self.is_dirty = False

    def close(self) -> None:
        """关闭 session——强制保存 + 清理。"""
        self.save()
        if self.db:
            self.db.close()

    # ─── 内部 ────────────────────────────────────────────────────────────────

    def _should_auto_save(self) -> bool:
        """检查是否应自动保存（按时间间隔）。"""
        if not self.is_dirty:
            return False
        elapsed = (datetime.now() - self.last_active_at).total_seconds()
        return elapsed >= self.config.auto_save_interval_sec

    def _check_chunk_boundary(self) -> None:
        """检查是否到达 chunk 边界（epoch 阈值）。"""
        if self.chunk is None:
            return
        if self.chunk.should_snapshot(self.epoch_counter):
            self.save()
            self.chunk.reset_counter()

    def _restore_state(self, saved: dict) -> BeliefState:
        """从 dict 重建 BeliefState（MVP 简化）。"""
        state = self.cta_engine.create_initial_state(self.student_id)

        # 恢复 5D theta
        import json
        import numpy as np

        if saved.get("current_state_5d"):
            theta_list = json.loads(saved["current_state_5d"])
            state.theta_mean = np.array(theta_list)
            state.theta_cov = np.eye(5)

        # 恢复 confidence
        if saved.get("confidence"):
            state.overall_confidence = saved["confidence"]

        return state
