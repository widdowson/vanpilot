"""Tests for the watchdog monitoring system."""

import time
import unittest
from unittest.mock import MagicMock, patch

from proto.vanpilot.v1 import sync_pb2
from supervisor.src.event_store import EventStore
from supervisor.src.watchdog import Watchdog


class FakeClock:
    """Deterministic clock for testing; avoids timing-sensitive sleeps."""

    def __init__(self, start: float = 0.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


class WatchdogRegistrationTest(unittest.TestCase):
    """Tests for session registration and unregistration."""

    def test_register_session(self):
        """Registering a session should track it for monitoring."""
        store = EventStore()
        wd = Watchdog(event_store=store, timeout_seconds=60)
        wd.register_session("lead", "vanpilot-lead")
        self.assertIn("lead", wd.monitored_agents)

    def test_unregister_session(self):
        """Unregistering a session should stop monitoring it."""
        store = EventStore()
        wd = Watchdog(event_store=store, timeout_seconds=60)
        wd.register_session("lead", "vanpilot-lead")
        wd.unregister_session("lead")
        self.assertNotIn("lead", wd.monitored_agents)

    def test_unregister_nonexistent_session_is_noop(self):
        """Unregistering a session that was never registered should not raise."""
        store = EventStore()
        wd = Watchdog(event_store=store, timeout_seconds=60)
        wd.unregister_session("nonexistent")  # Should not raise

    def test_register_multiple_sessions(self):
        """Multiple sessions can be registered simultaneously."""
        store = EventStore()
        wd = Watchdog(event_store=store, timeout_seconds=60)
        wd.register_session("lead", "vanpilot-lead")
        wd.register_session("researcher", "vanpilot-researcher")
        self.assertIn("lead", wd.monitored_agents)
        self.assertIn("researcher", wd.monitored_agents)


class WatchdogCheckTest(unittest.TestCase):
    """Tests for the check cycle that detects silent sessions."""

    def _make_watchdog(self, timeout_seconds=5, capture_fn=None, clock=None):
        """Helper to create a Watchdog with a mock capture function.

        Returns the watchdog, store, and the baseline count of
        WatchdogTimeout events already in the store (from hardcoded seeds).
        """
        store = EventStore()
        baseline = len([
            e for e in store.get_events(since_timestamp_ms=0, max_count=1000)
            if e.WhichOneof("payload") == "watchdog_timeout"
        ])
        wd = Watchdog(
            event_store=store,
            timeout_seconds=timeout_seconds,
            capture_pane_fn=capture_fn,
            clock=clock,
        )
        return wd, store, baseline

    def test_no_timeout_when_output_changes(self):
        """No WatchdogTimeout should be emitted when output keeps changing."""
        call_count = 0

        def changing_output(session_name):
            nonlocal call_count
            call_count += 1
            return f"output line {call_count}"

        wd, store, baseline = self._make_watchdog(
            timeout_seconds=1, capture_fn=changing_output
        )
        wd.register_session("lead", "vanpilot-lead")

        # First check establishes baseline
        wd.check_sessions()
        # Second check sees changed output
        wd.check_sessions()

        events = store.get_events(since_timestamp_ms=0, max_count=1000)
        watchdog_events = [
            e for e in events if e.WhichOneof("payload") == "watchdog_timeout"
        ]
        self.assertEqual(len(watchdog_events), baseline)

    def test_timeout_emitted_when_output_stale(self):
        """WatchdogTimeout should be emitted when output hasn't changed past timeout."""
        clock = FakeClock()
        wd, store, baseline = self._make_watchdog(
            timeout_seconds=5,
            capture_fn=lambda session: "static output",
            clock=clock,
        )
        wd.register_session("lead", "vanpilot-lead")

        # First check sets baseline
        wd.check_sessions()
        # Advance past the timeout
        clock.advance(6)
        # Second check detects stale output
        wd.check_sessions()

        events = store.get_events(since_timestamp_ms=0, max_count=1000)
        watchdog_events = [
            e for e in events if e.WhichOneof("payload") == "watchdog_timeout"
        ]
        self.assertGreater(len(watchdog_events), baseline)
        self.assertEqual(watchdog_events[-1].watchdog_timeout.agent_id, "lead")

    def test_timeout_event_contains_silent_duration(self):
        """The WatchdogTimeout event should report how long the agent was silent."""
        clock = FakeClock()
        wd, store, baseline = self._make_watchdog(
            timeout_seconds=5,
            capture_fn=lambda session: "static output",
            clock=clock,
        )
        wd.register_session("lead", "vanpilot-lead")

        wd.check_sessions()
        clock.advance(7)
        wd.check_sessions()

        events = store.get_events(since_timestamp_ms=0, max_count=1000)
        watchdog_events = [
            e for e in events if e.WhichOneof("payload") == "watchdog_timeout"
        ]
        self.assertEqual(
            watchdog_events[-1].watchdog_timeout.silent_duration_ms, 7000
        )

    def test_no_timeout_before_threshold(self):
        """No timeout should be emitted if silence hasn't exceeded the threshold."""
        clock = FakeClock()
        wd, store, baseline = self._make_watchdog(
            timeout_seconds=10,
            capture_fn=lambda session: "static output",
            clock=clock,
        )
        wd.register_session("lead", "vanpilot-lead")

        wd.check_sessions()
        clock.advance(3)
        wd.check_sessions()

        events = store.get_events(since_timestamp_ms=0, max_count=1000)
        watchdog_events = [
            e for e in events if e.WhichOneof("payload") == "watchdog_timeout"
        ]
        self.assertEqual(len(watchdog_events), baseline)

    def test_multiple_agents_checked_independently(self):
        """Each agent is checked independently; one silent agent doesn't affect others."""
        call_count = {"lead": 0, "researcher": 0}

        def capture(session_name):
            if session_name == "vanpilot-lead":
                call_count["lead"] += 1
                return f"lead output {call_count['lead']}"
            else:
                return "researcher static"

        clock = FakeClock()
        wd, store, baseline = self._make_watchdog(
            timeout_seconds=5, capture_fn=capture, clock=clock,
        )
        wd.register_session("lead", "vanpilot-lead")
        wd.register_session("researcher", "vanpilot-researcher")

        # Record a high-water mark timestamp to filter only new events
        import time as _time
        before_ms = int(_time.time() * 1000) - 1

        wd.check_sessions()
        clock.advance(6)
        wd.check_sessions()

        # Only look at events created by the watchdog (after our timestamp)
        events = store.get_events(since_timestamp_ms=before_ms, max_count=1000)
        watchdog_events = [
            e for e in events if e.WhichOneof("payload") == "watchdog_timeout"
        ]
        timed_out_agents = [e.watchdog_timeout.agent_id for e in watchdog_events]
        self.assertIn("researcher", timed_out_agents)
        self.assertNotIn("lead", timed_out_agents)

    def test_output_change_resets_timer(self):
        """When output changes after being stale, the timer should reset."""
        outputs = {"lead": "initial"}

        def capture(session_name):
            return outputs["lead"]

        clock = FakeClock()
        wd, store, baseline = self._make_watchdog(
            timeout_seconds=5, capture_fn=capture, clock=clock,
        )
        wd.register_session("lead", "vanpilot-lead")

        # Baseline check
        wd.check_sessions()
        clock.advance(6)

        # Output changes — should reset timer, no new timeout
        outputs["lead"] = "new output"
        wd.check_sessions()

        mid_events = store.get_events(since_timestamp_ms=0, max_count=1000)
        mid_wd_count = len(
            [e for e in mid_events if e.WhichOneof("payload") == "watchdog_timeout"]
        )
        self.assertEqual(mid_wd_count, baseline)

        # Now output goes stale again
        clock.advance(6)
        wd.check_sessions()

        events = store.get_events(since_timestamp_ms=0, max_count=1000)
        new_wd_events = [
            e for e in events if e.WhichOneof("payload") == "watchdog_timeout"
        ]
        # Should have a timeout now since output went stale after reset
        self.assertGreater(len(new_wd_events), baseline)

    def test_capture_failure_does_not_crash(self):
        """If capturing pane output raises, the check should not crash."""

        def failing_capture(session_name):
            raise RuntimeError("tmux not available")

        clock = FakeClock()
        wd, store, _ = self._make_watchdog(
            timeout_seconds=5, capture_fn=failing_capture, clock=clock,
        )
        wd.register_session("lead", "vanpilot-lead")

        # Should not raise
        wd.check_sessions()


class WatchdogBackgroundTest(unittest.TestCase):
    """Tests for the background monitoring thread."""

    def test_start_and_stop(self):
        """The watchdog should be able to start and stop its background thread."""
        store = EventStore()
        wd = Watchdog(
            event_store=store,
            timeout_seconds=60,
            check_interval_seconds=0.05,
            capture_pane_fn=lambda s: "output",
        )
        wd.register_session("lead", "vanpilot-lead")

        wd.start()
        self.assertTrue(wd.is_running)

        time.sleep(0.1)  # Let at least one check cycle run

        wd.stop()
        self.assertFalse(wd.is_running)

    def test_stop_without_start_is_noop(self):
        """Stopping a watchdog that was never started should not raise."""
        store = EventStore()
        wd = Watchdog(event_store=store, timeout_seconds=60)
        wd.stop()  # Should not raise

    def test_double_start_is_safe(self):
        """Calling start() twice should not create duplicate threads."""
        store = EventStore()
        wd = Watchdog(
            event_store=store,
            timeout_seconds=60,
            check_interval_seconds=0.05,
            capture_pane_fn=lambda s: "output",
        )

        wd.start()
        wd.start()  # Should be safe
        self.assertTrue(wd.is_running)

        wd.stop()


class WatchdogDefaultCaptureTest(unittest.TestCase):
    """Tests for the default tmux capture-pane integration."""

    @patch("subprocess.run")
    def test_default_capture_calls_tmux(self, mock_run):
        """The default capture function should invoke tmux capture-pane."""
        mock_run.return_value = MagicMock(returncode=0, stdout="pane output\n")

        store = EventStore()
        # Use default capture_pane_fn (None -> uses tmux capture-pane)
        wd = Watchdog(event_store=store, timeout_seconds=60)
        wd.register_session("lead", "vanpilot-lead")
        wd.check_sessions()

        mock_run.assert_called()
        args = mock_run.call_args[0][0]
        self.assertIn("tmux", args)
        self.assertIn("capture-pane", args)
        self.assertIn("vanpilot-lead", args)


if __name__ == "__main__":
    unittest.main()
