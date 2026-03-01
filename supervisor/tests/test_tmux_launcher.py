"""Tests for the tmux session launcher."""

import subprocess
import unittest
from unittest.mock import patch, MagicMock

from supervisor.src.tmux_launcher import TmuxLauncher


class TmuxLauncherTest(unittest.TestCase):

    @patch("subprocess.run")
    def test_start_session_calls_tmux_new(self, mock_run):
        """Starting a session should invoke 'tmux new-session'."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = TmuxLauncher()
        launcher.start_session("vanpilot-lead")
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        self.assertIn("tmux", args)
        self.assertIn("new-session", args)
        self.assertIn("vanpilot-lead", args)

    @patch("subprocess.run")
    def test_start_session_uses_detached_mode(self, mock_run):
        """Session should be started in detached mode (-d flag)."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = TmuxLauncher()
        launcher.start_session("vanpilot-lead")
        args = mock_run.call_args[0][0]
        self.assertIn("-d", args)

    @patch("subprocess.run")
    def test_start_session_returns_session_name(self, mock_run):
        """start_session should return the session name on success."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = TmuxLauncher()
        result = launcher.start_session("vanpilot-lead")
        self.assertEqual(result, "vanpilot-lead")

    @patch("subprocess.run")
    def test_start_session_raises_on_failure(self, mock_run):
        """Should raise RuntimeError if tmux command fails."""
        mock_run.return_value = MagicMock(
            returncode=1, stderr="tmux error"
        )
        launcher = TmuxLauncher()
        with self.assertRaises(RuntimeError):
            launcher.start_session("vanpilot-lead")

    @patch("subprocess.run")
    def test_session_exists_returns_true(self, mock_run):
        """session_exists should return True when the session is running."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = TmuxLauncher()
        self.assertTrue(launcher.session_exists("vanpilot-lead"))

    @patch("subprocess.run")
    def test_session_exists_returns_false(self, mock_run):
        """session_exists should return False when the session is not running."""
        mock_run.return_value = MagicMock(returncode=1)
        launcher = TmuxLauncher()
        self.assertFalse(launcher.session_exists("vanpilot-lead"))

    @patch("subprocess.run")
    def test_send_keys(self, mock_run):
        """send_keys should invoke tmux send-keys with the given text."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = TmuxLauncher()
        launcher.send_keys("vanpilot-lead", "hello world")
        args = mock_run.call_args[0][0]
        self.assertIn("tmux", args)
        self.assertIn("send-keys", args)
        self.assertIn("hello world", args)
        self.assertIn("Enter", args)

    @patch("subprocess.run")
    def test_kill_session(self, mock_run):
        """kill_session should invoke tmux kill-session."""
        mock_run.return_value = MagicMock(returncode=0)
        launcher = TmuxLauncher()
        launcher.kill_session("vanpilot-lead")
        args = mock_run.call_args[0][0]
        self.assertIn("tmux", args)
        self.assertIn("kill-session", args)


if __name__ == "__main__":
    unittest.main()
