"""Tests for tmux input injection with delivery verification."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock

from supervisor.src.event_store import EventStore
from supervisor.src.input_injector import InputInjector


class _FakeTmux:
    """Fake TmuxLauncher that records send_keys calls."""

    def __init__(self):
        self.calls = []

    def send_keys(self, session_name: str, text: str) -> None:
        self.calls.append((session_name, text))


class InputInjectorSendKeysTest(unittest.TestCase):
    """Tests that inject() calls tmux send_keys correctly."""

    def setUp(self):
        self.tmux = _FakeTmux()
        self.store = EventStore()
        self.tmpdir = tempfile.mkdtemp()
        self.injector = InputInjector(
            self.tmux, self.store,
            log_dir=self.tmpdir, response_timeout_s=0.1, poll_interval_s=0.02,
        )

    def test_send_keys_called_with_session_and_text(self):
        self.injector.inject("agent-lead", "hello world")
        self.assertEqual(len(self.tmux.calls), 1)
        self.assertEqual(self.tmux.calls[0], ("agent-lead", "hello world"))

    def test_send_keys_called_once_per_inject(self):
        self.injector.inject("s1", "a")
        self.injector.inject("s2", "b")
        self.assertEqual(len(self.tmux.calls), 2)


class InputInjectorResponseDetectionTest(unittest.TestCase):
    """Tests that log-file growth is detected as a successful response."""

    def setUp(self):
        self.tmux = _FakeTmux()
        self.store = EventStore()
        self.tmpdir = tempfile.mkdtemp()
        self.injector = InputInjector(
            self.tmux, self.store,
            log_dir=self.tmpdir, response_timeout_s=0.5, poll_interval_s=0.02,
        )

    def test_returns_true_when_log_grows(self):
        log_file = os.path.join(self.tmpdir, "agent-lead.jsonl")
        with open(log_file, "w") as f:
            f.write("initial\n")

        def grow_log():
            time.sleep(0.05)
            with open(log_file, "a") as f:
                f.write("new data\n")

        threading.Thread(target=grow_log, daemon=True).start()
        result = self.injector.inject("agent-lead", "test")
        self.assertTrue(result)

    def test_returns_false_when_log_does_not_grow(self):
        log_file = os.path.join(self.tmpdir, "agent-lead.jsonl")
        with open(log_file, "w") as f:
            f.write("static\n")
        result = self.injector.inject("agent-lead", "test")
        self.assertFalse(result)

    def test_returns_false_when_no_log_file(self):
        result = self.injector.inject("no-such-session", "test")
        self.assertFalse(result)


class InputInjectorFailureEventTest(unittest.TestCase):
    """Tests that timeout emits InputDeliveryFailure events."""

    def setUp(self):
        self.tmux = _FakeTmux()
        self.store = EventStore()
        self.tmpdir = tempfile.mkdtemp()
        self.injector = InputInjector(
            self.tmux, self.store,
            log_dir=self.tmpdir, response_timeout_s=0.1, poll_interval_s=0.02,
        )

    def test_failure_event_emitted_on_timeout(self):
        self.injector.inject("agent-lead", "prompt text", agent_id="lead")
        events = self.store.get_events(since_timestamp_ms=0, max_count=100)
        failure_events = [
            e for e in events if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failure_events), 1)
        self.assertEqual(
            failure_events[0].input_delivery_failure.attempted_input,
            "prompt text",
        )
        self.assertEqual(
            failure_events[0].input_delivery_failure.target_agent_id, "lead"
        )

    def test_no_failure_event_when_response_detected(self):
        log_file = os.path.join(self.tmpdir, "agent-lead.jsonl")
        with open(log_file, "w") as f:
            f.write("initial\n")

        def grow_log():
            time.sleep(0.02)
            with open(log_file, "a") as f:
                f.write("response\n")

        threading.Thread(target=grow_log, daemon=True).start()
        self.injector.inject("agent-lead", "prompt text")
        events = self.store.get_events(since_timestamp_ms=0, max_count=100)
        failure_events = [
            e for e in events if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failure_events), 0)

    def test_failure_event_has_timestamp(self):
        before = int(time.time() * 1000)
        self.injector.inject("agent-lead", "test")
        after = int(time.time() * 1000)
        events = self.store.get_events(since_timestamp_ms=0, max_count=100)
        failure_events = [
            e for e in events if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failure_events), 1)
        ts = failure_events[0].timestamp_ms
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)


class InputInjectorLogPathTest(unittest.TestCase):
    """Tests for log path derivation."""

    def test_log_path_uses_session_name(self):
        tmux = _FakeTmux()
        store = EventStore()
        injector = InputInjector(
            tmux, store, log_dir="/my/logs",
            response_timeout_s=0.01, poll_interval_s=0.01,
        )
        path = injector._log_path("my-session")
        self.assertEqual(path, "/my/logs/my-session.jsonl")


class InputInjectorAsyncTest(unittest.TestCase):
    """Tests for fire-and-forget async injection."""

    def setUp(self):
        self.tmux = _FakeTmux()
        self.store = EventStore()
        self.tmpdir = tempfile.mkdtemp()

    def test_inject_async_returns_immediately(self):
        injector = InputInjector(
            self.tmux, self.store,
            log_dir=self.tmpdir, response_timeout_s=5.0, poll_interval_s=0.1,
        )
        start = time.monotonic()
        thread = injector.inject_async("agent-lead", "hello")
        elapsed = time.monotonic() - start
        self.assertLess(elapsed, 1.0, "inject_async should return immediately")
        self.assertIsInstance(thread, threading.Thread)
        self.assertTrue(thread.is_alive())

    def test_inject_async_completes_with_response(self):
        """Join the thread and verify injection completed successfully."""
        log_file = os.path.join(self.tmpdir, "agent-lead.jsonl")
        with open(log_file, "w") as f:
            f.write("initial\n")

        def grow_log():
            time.sleep(0.05)
            with open(log_file, "a") as f:
                f.write("response data\n")

        threading.Thread(target=grow_log, daemon=True).start()

        injector = InputInjector(
            self.tmux, self.store,
            log_dir=self.tmpdir, response_timeout_s=2.0, poll_interval_s=0.02,
        )
        thread = injector.inject_async("agent-lead", "test prompt")
        thread.join(timeout=3.0)
        self.assertFalse(thread.is_alive(), "Thread should have completed")
        # Verify send_keys was called
        self.assertEqual(len(self.tmux.calls), 1)
        self.assertEqual(self.tmux.calls[0], ("agent-lead", "test prompt"))
        # No failure event since log grew
        events = self.store.get_events(since_timestamp_ms=0, max_count=100)
        failure_events = [
            e for e in events if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failure_events), 0)

    def test_inject_async_emits_failure_on_timeout(self):
        """Join the thread and verify failure event emitted on timeout."""
        injector = InputInjector(
            self.tmux, self.store,
            log_dir=self.tmpdir, response_timeout_s=0.1, poll_interval_s=0.02,
        )
        thread = injector.inject_async("agent-lead", "doomed prompt", "lead")
        thread.join(timeout=2.0)
        self.assertFalse(thread.is_alive(), "Thread should have completed")
        # Verify failure event was emitted
        events = self.store.get_events(since_timestamp_ms=0, max_count=100)
        failure_events = [
            e for e in events if e.HasField("input_delivery_failure")
        ]
        self.assertEqual(len(failure_events), 1)
        self.assertEqual(
            failure_events[0].input_delivery_failure.attempted_input,
            "doomed prompt",
        )


if __name__ == "__main__":
    unittest.main()
