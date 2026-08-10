"""v0.84.0-b: EventBus tests.

Covers:
  - subscribe/publish basic (sync mode)
  - multi-handler per topic
  - unsubscribe
  - handler raise doesn't block others (defensive)
  - topic isolation
  - max_subscribers limit
  - module singleton lazy init + reset
  - kwargs injection pattern (for Runtime subscriber integration)
  - get_subscribers + get_topic_count

Per discussions/2026-08-11-v084-design.md §3.
"""
from __future__ import annotations

import logging

import pytest

from ecos.event import (
    EventBus,
    EventBusConfig,
    get_default_bus,
    reset_default_bus,
)
from ecos.cta.event_log import LearningEvent, LearningEventType


# ── Basic subscribe/publish (3 tests) ───────────────────────────────────────


class TestEventBusBasic:
    """EventBus basic subscribe + publish in sync mode."""

    def test_subscribe_publish_single_handler(self):
        """subscribe returns sub_id; publish invokes handler."""
        bus = EventBus()
        received = []

        def handler(event):
            received.append(event)

        sub_id = bus.subscribe("observation", handler)
        assert sub_id.startswith("sub_")
        assert len(sub_id) > 5

        event = LearningEvent(
            event_id="evt_001",
            student_id="stu-001",
            timestamp=__import__("datetime").datetime.now(),
            source="test",
            event_type=LearningEventType.OBSERVATION.value,
        )
        success = bus.publish("observation", event)
        assert success == 1
        assert received == [event]

    def test_publish_no_subscribers_returns_zero(self):
        """Publishing to topic with no subscribers returns 0."""
        bus = EventBus()
        success = bus.publish("nonexistent_topic", "payload")
        assert success == 0

    def test_publish_returns_success_count(self):
        """publish returns count of handlers successfully invoked."""
        bus = EventBus()
        received_count = [0]

        def handler(event):
            received_count[0] += 1

        bus.subscribe("t1", handler)
        bus.subscribe("t1", handler)
        bus.subscribe("t1", handler)

        success = bus.publish("t1", "payload")
        assert success == 3
        assert received_count[0] == 3


# ── Multi-handler (1 test) ────────────────────────────────────────────────


class TestMultiHandler:
    """One topic, multiple handlers — all invoked."""

    def test_multi_handlers_all_invoked_in_order(self):
        """3 handlers on same topic all invoked; order is subscription order."""
        bus = EventBus()
        log = []

        bus.subscribe("t", lambda e: log.append(("h1", e)))
        bus.subscribe("t", lambda e: log.append(("h2", e)))
        bus.subscribe("t", lambda e: log.append(("h3", e)))

        bus.publish("t", "payload")
        assert log == [("h1", "payload"), ("h2", "payload"), ("h3", "payload")]


# ── Unsubscribe (2 tests) ─────────────────────────────────────────────────


class TestUnsubscribe:
    """unsubscribe removes handler; unknown sub_id returns False."""

    def test_unsubscribe_removes_handler(self):
        """unsubscribe returns True and stops handler invocation."""
        bus = EventBus()
        received = []

        sub_id = bus.subscribe("t", lambda e: received.append(e))
        assert bus.publish("t", "p1") == 1
        assert received == ["p1"]

        assert bus.unsubscribe(sub_id) is True
        assert bus.publish("t", "p2") == 0
        assert received == ["p1"]  # no new entry

    def test_unsubscribe_unknown_id_returns_false(self):
        """unsubscribe returns False for unknown sub_id (defensive, no raise)."""
        bus = EventBus()
        assert bus.unsubscribe("sub_does_not_exist") is False


# ── Handler exception isolation (2 tests) ────────────────────────────────


class TestHandlerExceptionIsolation:
    """Handler raise doesn't block other handlers (defensive)."""

    def test_handler_raise_does_not_block_other_handlers(self):
        """One handler raises; others still invoked; publish returns partial count."""
        bus = EventBus()
        log = []

        def bad_handler(event):
            raise RuntimeError("simulated handler failure")

        def good_handler(event):
            log.append(("good", event))

        bus.subscribe("t", bad_handler)
        bus.subscribe("t", good_handler)

        success = bus.publish("t", "payload")
        # 1 handler raised (counted as failure), 1 succeeded
        assert success == 1
        assert log == [("good", "payload")]

    def test_handler_raise_logs_warning(self, caplog):
        """Handler raise triggers _log.warning (defensive self-check [1])."""
        bus = EventBus()

        def bad_handler(event):
            raise RuntimeError("simulated failure")

        bus.subscribe("t", bad_handler)
        with caplog.at_level(logging.WARNING):
            bus.publish("t", "payload")
        # Logger name is ecos.event.bus; check message contains expected substring
        assert any(
            "handler" in r.message.lower() and "topic" in r.message.lower()
            for r in caplog.records
        )


# ── Topic isolation (1 test) ──────────────────────────────────────────────


class TestTopicIsolation:
    """Publishing to topic X doesn't invoke handlers for topic Y."""

    def test_publish_to_topic_a_does_not_invoke_topic_b_handlers(self):
        """publish is topic-scoped; cross-topic publish is no-op."""
        bus = EventBus()
        received_a = []
        received_b = []

        bus.subscribe("topic_a", lambda e: received_a.append(e))
        bus.subscribe("topic_b", lambda e: received_b.append(e))

        bus.publish("topic_a", "for_a")
        assert received_a == ["for_a"]
        assert received_b == []


# ── Max subscribers limit (1 test) ────────────────────────────────────────


class TestMaxSubscribersLimit:
    """max_subscribers_per_topic is enforced."""

    def test_max_subscribers_limit_emits_warning(self, caplog):
        """Exceeding max_subscribers logs warning but still records sub_id."""
        config = EventBusConfig(max_subscribers_per_topic=2)
        bus = EventBus(config=config)

        bus.subscribe("t", lambda e: None)
        bus.subscribe("t", lambda e: None)

        with caplog.at_level(logging.WARNING):
            sub_id = bus.subscribe("t", lambda e: None)

        assert sub_id.startswith("sub_")  # still returned
        assert any(
            "max_subscribers" in r.message.lower() for r in caplog.records
        )
        assert bus.get_topic_count("t") == 3  # all recorded


# ── Module singleton (2 tests) ────────────────────────────────────────────


class TestModuleSingleton:
    """Module-level _default_bus singleton: lazy init + reset."""

    def test_get_default_bus_lazy_init(self):
        """First call to get_default_bus constructs the singleton."""
        reset_default_bus()  # ensure clean state
        bus1 = get_default_bus()
        bus2 = get_default_bus()
        # Same instance (singleton)
        assert bus1 is bus2

    def test_reset_default_bus_clears_singleton(self):
        """reset_default_bus clears singleton; next call constructs fresh instance."""
        bus1 = get_default_bus()
        reset_default_bus()
        bus2 = get_default_bus()
        # Different instance after reset
        assert bus1 is not bus2


# ── Kwargs injection pattern (1 test) ──────────────────────────────────────


class TestKwargsInjectionPattern:
    """EventBus is kwargs-injectable (mirrors Runtime API pattern)."""

    def test_constructor_accepts_custom_bus(self):
        """Caller can pass a custom EventBus instance (test isolation pattern)."""
        custom = EventBus(EventBusConfig(mode="sync"))
        received = []

        # Simulate subscriber registration pattern: caller injects bus + handler
        sub_id = custom.subscribe("t", lambda e: received.append(e))
        custom.publish("t", "payload")

        assert received == ["payload"]
        assert custom.get_topic_count("t") == 1


# ── Defensive: get_subscribers + get_topic_count (1 test) ────────────────


class TestBusIntrospection:
    """get_subscribers + get_topic_count for debugging/testing."""

    def test_get_subscribers_and_topic_count(self):
        """get_subscribers returns handlers list; get_topic_count returns int."""
        bus = EventBus()

        def h1(event):
            pass

        def h2(event):
            pass

        bus.subscribe("t", h1)
        bus.subscribe("t", h2)
        bus.subscribe("other", h1)

        assert bus.get_topic_count("t") == 2
        assert bus.get_topic_count("other") == 1
        assert bus.get_topic_count("nonexistent") == 0

        handlers = bus.get_subscribers("t")
        assert h1 in handlers
        assert h2 in handlers
        # Mutating returned list doesn't affect bus (defensive copy)
        handlers.clear()
        assert bus.get_topic_count("t") == 2


# ── Defense: no silent pass in event/bus.py (1 test) ─────────────────────


class TestDefensiveChecks:
    """防御性自检 [1]: no silent pass in new code."""

    def test_no_silent_pass_in_event_bus(self):
        """Grep 'except ...: pass' or 'except ...: continue' in ecos/event/bus.py."""
        import subprocess
        pattern = r"^\s*except.*:[[:space:]]*(pass|continue)\s*$"
        result = subprocess.run(
            ["grep", "-nE", pattern, "ecos/event/bus.py"],
            capture_output=True, text=True,
        )
        assert result.stdout.strip() == "", (
            f"silent pass detected: {result.stdout}"
        )
