"""Tests for SendUserInput RPC wiring to InputInjector."""

import unittest
from unittest.mock import MagicMock, patch

from supervisor.src.event_store import EventStore
from supervisor.src.input_injector import InputInjector
from supervisor.src.sync_service import SyncServiceServicer
from supervisor.src.tmux_launcher import TmuxLauncher
from proto.vanpilot.v1 import sync_pb2


class SendUserInputWithInjectorTest(unittest.TestCase):
    """Tests that SendUserInput delegates to InputInjector."""

    def setUp(self):
        self.store = EventStore()
        self.tmux = MagicMock(spec=TmuxLauncher)
        self.injector = InputInjector(
            tmux=self.tmux,
            event_store=self.store,
            log_dir="/tmp/test-logs",
            response_timeout_s=0.05,
            poll_interval_s=0.01,
        )
        self.servicer = SyncServiceServicer(
            store=self.store,
            input_injector=self.injector,
        )

    def test_send_user_input_accepted_with_injector(self):
        """SendUserInput should return accepted=True when injector is wired."""
        request = sync_pb2.SendUserInputRequest(
            text="build the project", target_agent_id="lead"
        )
        with patch.object(self.injector, "inject_async"):
            response = self.servicer.SendUserInput(request, context=None)
        self.assertTrue(response.accepted)

    def test_send_user_input_calls_inject_async(self):
        """SendUserInput should call inject_async on the injector."""
        request = sync_pb2.SendUserInputRequest(
            text="run tests", target_agent_id="lead"
        )
        with patch.object(self.injector, "inject_async") as mock_inject:
            self.servicer.SendUserInput(request, context=None)
        mock_inject.assert_called_once_with("vanpilot-lead", "run tests", "lead")

    def test_send_user_input_derives_session_name(self):
        """Session name should be vanpilot-{agent_id}."""
        request = sync_pb2.SendUserInputRequest(
            text="analyze code", target_agent_id="researcher"
        )
        with patch.object(self.injector, "inject_async") as mock_inject:
            self.servicer.SendUserInput(request, context=None)
        mock_inject.assert_called_once_with(
            "vanpilot-researcher", "analyze code", "researcher"
        )

    def test_send_user_input_defaults_agent_to_lead(self):
        """When target_agent_id is empty, it should default to 'lead'."""
        request = sync_pb2.SendUserInputRequest(text="hello")
        with patch.object(self.injector, "inject_async") as mock_inject:
            self.servicer.SendUserInput(request, context=None)
        mock_inject.assert_called_once_with("vanpilot-lead", "hello", "lead")


class SendUserInputWithoutInjectorTest(unittest.TestCase):
    """Tests SendUserInput when no injector is configured."""

    def setUp(self):
        self.store = EventStore()
        self.servicer = SyncServiceServicer(store=self.store)

    def test_send_user_input_rejected_without_injector(self):
        """SendUserInput should return accepted=False when no injector."""
        request = sync_pb2.SendUserInputRequest(
            text="hello", target_agent_id="lead"
        )
        response = self.servicer.SendUserInput(request, context=None)
        self.assertFalse(response.accepted)


if __name__ == "__main__":
    unittest.main()
