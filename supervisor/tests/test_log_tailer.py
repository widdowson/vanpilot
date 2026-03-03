"""Tests for the LogTailer that reads Claude Code JSONL conversation logs.

The LogTailer watches JSONL log files in a directory and emits TextMessage
events into the EventStore when new assistant messages appear.

Claude Code JSONL log format (each line is a JSON object):
  {"type": "assistant", "message": {"role": "assistant", "content": [{"type": "text", "text": "Hello"}]}, ...}
  {"type": "human", "message": {"role": "user", "content": [...]}, ...}
  {"type": "system", ...}
"""

import atexit
import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Patch proto module before importing anything from supervisor
_mock_sync = MagicMock()
_proto_patches = patch.dict("sys.modules", {
    "proto": MagicMock(),
    "proto.vanpilot": MagicMock(),
    "proto.vanpilot.v1": MagicMock(),
    "proto.vanpilot.v1.sync_pb2": _mock_sync,
})
_proto_patches.start()
atexit.register(_proto_patches.stop)

from supervisor.src.log_tailer import parse_log_entry, LogTailer


class LogTailerParseTest(unittest.TestCase):
    """Tests for parsing individual JSONL log entries."""

    def test_parse_assistant_text_message(self):
        """Assistant message with text content should return agent_id and text."""
        entry = json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": "Hello, world!"}],
            },
        })
        result = parse_log_entry(entry)
        self.assertIsNotNone(result)
        self.assertEqual(result["text"], "Hello, world!")

    def test_parse_assistant_multiple_text_blocks(self):
        """Multiple text blocks should be concatenated with space separator."""
        entry = json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Part one."},
                    {"type": "tool_use", "name": "Read", "input": {}},
                    {"type": "text", "text": "Part two."},
                ],
            },
        })
        result = parse_log_entry(entry)
        self.assertIsNotNone(result)
        self.assertEqual(result["text"], "Part one. Part two.")

    def test_parse_human_message_returns_none(self):
        """Human/user messages should be ignored."""
        entry = json.dumps({
            "type": "human",
            "message": {"role": "user", "content": [{"type": "text", "text": "Hi"}]},
        })
        result = parse_log_entry(entry)
        self.assertIsNone(result)

    def test_parse_system_message_returns_none(self):
        """System messages should be ignored."""
        entry = json.dumps({"type": "system", "content": "init"})
        result = parse_log_entry(entry)
        self.assertIsNone(result)

    def test_parse_tool_only_assistant_returns_none(self):
        """Assistant message with only tool_use (no text) should return None."""
        entry = json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "tool_use", "name": "Bash", "input": {}}],
            },
        })
        result = parse_log_entry(entry)
        self.assertIsNone(result)

    def test_parse_malformed_json_returns_none(self):
        """Malformed JSON should return None (not raise)."""
        result = parse_log_entry("{not valid json")
        self.assertIsNone(result)

    def test_parse_empty_line_returns_none(self):
        result = parse_log_entry("")
        self.assertIsNone(result)

    def test_parse_string_content(self):
        """Some entries have content as a plain string instead of array."""
        entry = json.dumps({
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": "Simple text response",
            },
        })
        result = parse_log_entry(entry)
        self.assertIsNotNone(result)
        self.assertEqual(result["text"], "Simple text response")


class LogTailerTailTest(unittest.TestCase):
    """Tests for tailing a single log file and emitting events."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.events = []

    def _make_tailer(self):
        mock_store = MagicMock()
        mock_store.add_event = lambda e: self.events.append(e)
        return LogTailer(
            event_store=mock_store,
            log_dir=self.tmpdir,
            poll_interval_s=0.05,
        )

    def _write_log(self, session_name, entries):
        """Write JSONL entries to a log file."""
        path = os.path.join(self.tmpdir, f"{session_name}.jsonl")
        with open(path, "a") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")
        return path

    def test_tail_reads_new_entries(self):
        """New lines appended to a log file should produce events via add_event."""
        tailer = self._make_tailer()

        self._write_log("lead", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "First message"}],
                },
            },
        ])

        tailer.poll_once()
        self.assertEqual(len(self.events), 1)

    def test_tail_skips_already_read_lines(self):
        """Lines that were already processed should not produce duplicate events."""
        tailer = self._make_tailer()

        self._write_log("lead", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Msg 1"}],
                },
            },
        ])
        tailer.poll_once()
        count_after_first = len(self.events)

        # Second poll with no new data
        tailer.poll_once()
        self.assertEqual(len(self.events), count_after_first)

    def test_tail_picks_up_new_lines_after_poll(self):
        """New lines added after the first poll should be picked up."""
        tailer = self._make_tailer()

        self._write_log("lead", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Msg 1"}],
                },
            },
        ])
        tailer.poll_once()
        count_first = len(self.events)

        self._write_log("lead", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Msg 2"}],
                },
            },
        ])
        tailer.poll_once()
        self.assertEqual(len(self.events), count_first + 1)

    def test_tail_multiple_sessions(self):
        """Should tail log files from multiple agent sessions."""
        tailer = self._make_tailer()

        self._write_log("lead", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "From lead"}],
                },
            },
        ])
        self._write_log("researcher", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "From researcher"}],
                },
            },
        ])

        tailer.poll_once()
        self.assertEqual(len(self.events), 2)

    def test_tail_ignores_human_entries(self):
        """Human messages in the log should not produce events."""
        tailer = self._make_tailer()

        self._write_log("lead", [
            {
                "type": "human",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "User input"}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Reply"}],
                },
            },
        ])

        tailer.poll_once()
        self.assertEqual(len(self.events), 1)

    def test_tail_handles_new_log_file_appearing(self):
        """A log file created after the tailer starts should be picked up."""
        tailer = self._make_tailer()
        tailer.poll_once()  # No files yet
        self.assertEqual(len(self.events), 0)

        self._write_log("newagent", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "I'm new!"}],
                },
            },
        ])
        tailer.poll_once()
        self.assertEqual(len(self.events), 1)

    def test_tail_handles_log_rotation(self):
        """If a log file is truncated (rotated), tailer should reset offset."""
        tailer = self._make_tailer()

        path = self._write_log("lead", [
            {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "Before rotation"}],
                },
            },
        ])
        tailer.poll_once()
        count_first = len(self.events)

        # Simulate rotation: truncate and write new content
        with open(path, "w") as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "After rotation"}],
                },
            }) + "\n")

        tailer.poll_once()
        self.assertEqual(len(self.events), count_first + 1)


    def test_tail_recursive_subdirectory(self):
        """Should discover JSONL files in subdirectories (per-project dirs)."""
        tailer = self._make_tailer()

        # Create a subdirectory mimicking Claude Code's per-project structure
        subdir = os.path.join(self.tmpdir, "project-abc123")
        os.makedirs(subdir)
        path = os.path.join(subdir, "lead.jsonl")
        with open(path, "w") as f:
            f.write(json.dumps({
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [{"type": "text", "text": "From subdirectory"}],
                },
            }) + "\n")

        tailer.poll_once()
        self.assertEqual(len(self.events), 1)


class LogTailerBackgroundTest(unittest.TestCase):
    """Tests for the background tailing thread."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_start_and_stop(self):
        """Background thread should start and stop cleanly."""
        mock_store = MagicMock()
        tailer = LogTailer(
            event_store=mock_store,
            log_dir=self.tmpdir,
            poll_interval_s=0.02,
        )
        tailer.start()
        time.sleep(0.05)
        tailer.stop()
        # Should not hang or raise


if __name__ == "__main__":
    unittest.main()
