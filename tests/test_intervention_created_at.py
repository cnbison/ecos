"""v0.99.2 (F-12): Intervention.created_at 时间戳 + to_dict/from_dict 对齐.

背景 (dogfood-findings-2026-09.md F-12):
  - 家长端 Cards.tsx 曾读 `timestamp` / `rationale_text`, 而 Intervention.to_dict()
    的真实字段是 `created_at` (本版本新增) / `rationale` → 时间列全空、说明列全 "—"
  - 修复 = 前端改读 `rationale` / `created_at` + 后端 Intervention 增加 created_at

本文件测后端契约:
  1. 构造时自动打点 created_at (isoformat 字符串, JSON 可序列化)
  2. to_dict / from_dict 往返保真
  3. 历史持久化记录 (无 created_at 键) from_dict 恢复为 None —
     硬规则 #6: 旧记录不写迁移脚本, UI 显示 "—" 可接受
"""

from __future__ import annotations

from datetime import datetime

from ecos.cta.belief_state import BloomLevel
from ecos.lca.intervention import Intervention, InterventionType


def _make_intervention(**overrides) -> Intervention:
    kwargs = dict(
        intervention_type=InterventionType.PRACTICE,
        bloom_target=BloomLevel.CREATE,
        rationale="推荐你做 8 道 CREATE 层的练习。",
    )
    kwargs.update(overrides)
    return Intervention(**kwargs)


class TestCreatedAtAutoStamp:
    def test_construction_stamps_created_at(self):
        """构造时自动打点 isoformat 时间戳."""
        before = datetime.now()
        itv = _make_intervention()
        after = datetime.now()
        assert itv.created_at is not None
        stamped = datetime.fromisoformat(itv.created_at)
        assert before <= stamped <= after

    def test_created_at_is_json_serializable_str(self):
        """created_at 是 str, 无 datetime 残留 (JSON 持久化安全, 同 F-02 检查口径)."""
        import json

        itv = _make_intervention()
        payload = json.dumps(itv.to_dict(), ensure_ascii=False)
        assert itv.created_at in payload


class TestCreatedAtRoundtrip:
    def test_to_dict_contains_created_at_and_rationale(self):
        """to_dict 暴露 created_at + rationale (家长端/教师端消费的真实字段名)."""
        d = _make_intervention().to_dict()
        assert "created_at" in d
        assert "rationale" in d
        # F-12 错配回归锚: 不存在旧错配字段名
        assert "timestamp" not in d
        assert "rationale_text" not in d

    def test_from_dict_roundtrip_preserves_created_at(self):
        itv = _make_intervention()
        restored = Intervention.from_dict(itv.to_dict())
        assert restored.created_at == itv.created_at
        assert restored.rationale == itv.rationale

    def test_legacy_record_without_created_at_restores_none(self):
        """历史持久化记录无 created_at 键 → 恢复为 None (不写迁移脚本)."""
        legacy = _make_intervention().to_dict()
        del legacy["created_at"]
        restored = Intervention.from_dict(legacy)
        assert restored.created_at is None
        assert restored.rationale is not None

    def test_explicit_created_at_survives_roundtrip(self):
        """显式传入 created_at (如回放/测试固定时间) 不被 default_factory 覆盖."""
        itv = _make_intervention(created_at="2026-09-09T13:13:11")
        assert itv.created_at == "2026-09-09T13:13:11"
        assert Intervention.from_dict(itv.to_dict()).created_at == "2026-09-09T13:13:11"
