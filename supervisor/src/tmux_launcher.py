"""Basic tmux session launcher for Claude Code agent sessions."""

import subprocess


class TmuxLauncher:
    """Manages tmux sessions for Claude Code agents."""

    def start_session(self, session_name: str) -> str:
        """Start a new detached tmux session.

        Args:
            session_name: Name for the tmux session.

        Returns:
            The session name on success.

        Raises:
            RuntimeError: If the tmux command fails.
        """
        result = subprocess.run(
            ["tmux", "new-session", "-d", "-s", session_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to start tmux session '{session_name}': {result.stderr}"
            )
        return session_name

    def session_exists(self, session_name: str) -> bool:
        """Check whether a tmux session with the given name exists."""
        result = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def send_keys(self, session_name: str, text: str) -> None:
        """Send keystrokes to a tmux session followed by Enter.

        This is the primary mechanism for injecting user input into
        a Claude Code TUI running inside the session.
        """
        result = subprocess.run(
            ["tmux", "send-keys", "-t", session_name, text, "Enter"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to send keys to '{session_name}': {result.stderr}"
            )

    def kill_session(self, session_name: str) -> None:
        """Kill a tmux session."""
        result = subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to kill session '{session_name}': {result.stderr}"
            )
