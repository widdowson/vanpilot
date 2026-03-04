"""Tests for the log collector module."""

import os
import tempfile
import threading
import time
import unittest

from instance_manager.src.instance_store import InstanceRecord, RUNNING
from instance_manager.src.log_collector import LogCollector, LogEntry, _clean_dhu_line


def _make_record(name="test-inst", log_path=None):
    return InstanceRecord(
        name=name,
        state=RUNNING,
        emulator_console_port=5554,
        adb_port=5555,
        aa_forward_port=5277,
        headful=False,
        created_at_ms=1000,
        avd_name="test_avd",
        log_path=log_path,
    )


class CleanDhuLineTest(unittest.TestCase):

    def test_bare_prompt_is_noise(self):
        self.assertIsNone(_clean_dhu_line("> "))
        self.assertIsNone(_clean_dhu_line(">"))
        self.assertIsNone(_clean_dhu_line(""))

    def test_nested_prompts_are_noise(self):
        self.assertIsNone(_clean_dhu_line("> > "))
        self.assertIsNone(_clean_dhu_line("> > > "))
        self.assertIsNone(_clean_dhu_line("> > >"))

    def test_command_echo_kept(self):
        # "> command" lines represent commands we sent — keep them
        self.assertEqual(_clean_dhu_line("> keycode home"), "> keycode home")
        self.assertEqual(_clean_dhu_line("> tap 300 430"), "> tap 300 430")

    def test_plain_output_passes_through(self):
        self.assertEqual(
            _clean_dhu_line("Phone reported protocol version 1.7"),
            "Phone reported protocol version 1.7",
        )
        self.assertEqual(_clean_dhu_line("SSL handshake complete"), "SSL handshake complete")


class LogCollectorGetSourcesTest(unittest.TestCase):

    def test_no_sources_when_files_missing(self):
        collector = LogCollector()
        record = _make_record(name="nonexistent")
        sources = collector.get_sources(record)
        self.assertEqual(sources, {})

    def test_dhu_source_when_log_exists(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            f.write(b"dhu line\n")
            dhu_path = f.name
        try:
            collector = LogCollector()
            record = _make_record(log_path=dhu_path)
            sources = collector.get_sources(record)
            self.assertIn("dhu", sources)
            self.assertEqual(sources["dhu"], dhu_path)
        finally:
            os.unlink(dhu_path)

    def test_emulator_source_when_log_exists(self):
        name = f"_test_emu_{os.getpid()}"
        emu_path = f"/tmp/emu_{name}.log"
        with open(emu_path, "w") as f:
            f.write("emu line\n")
        try:
            collector = LogCollector()
            record = _make_record(name=name)
            sources = collector.get_sources(record)
            self.assertIn("emulator", sources)
        finally:
            os.unlink(emu_path)

    def test_service_source_when_path_set(self):
        with tempfile.NamedTemporaryFile(suffix=".log", delete=False) as f:
            f.write(b"service line\n")
            svc_path = f.name
        try:
            collector = LogCollector(service_log_path=svc_path)
            record = _make_record()
            sources = collector.get_sources(record)
            self.assertIn("service", sources)
        finally:
            os.unlink(svc_path)

    def test_no_service_source_when_path_none(self):
        collector = LogCollector(service_log_path=None)
        record = _make_record()
        sources = collector.get_sources(record)
        self.assertNotIn("service", sources)


class LogCollectorReadRecentTest(unittest.TestCase):

    def test_reads_dhu_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            for i in range(5):
                f.write(f"dhu line {i}\n")
            dhu_path = f.name
        try:
            collector = LogCollector()
            record = _make_record(log_path=dhu_path)
            entries = collector.read_recent(record)
            self.assertEqual(len(entries), 5)
            self.assertEqual(entries[0].source, "dhu")
            self.assertEqual(entries[0].text, "dhu line 0")
            self.assertEqual(entries[4].text, "dhu line 4")
        finally:
            os.unlink(dhu_path)

    def test_max_lines_per_source_limits_output(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            for i in range(100):
                f.write(f"line {i}\n")
            path = f.name
        try:
            collector = LogCollector()
            record = _make_record(log_path=path)
            entries = collector.read_recent(record, max_lines_per_source=10)
            self.assertEqual(len(entries), 10)
            # Should be the last 10 lines
            self.assertEqual(entries[0].text, "line 90")
            self.assertEqual(entries[9].text, "line 99")
        finally:
            os.unlink(path)

    def test_source_filter(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as dhu_f:
            dhu_f.write("dhu line\n")
            dhu_path = dhu_f.name
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as svc_f:
            svc_f.write("service line\n")
            svc_path = svc_f.name
        try:
            collector = LogCollector(service_log_path=svc_path)
            record = _make_record(log_path=dhu_path)
            # Only request service logs
            entries = collector.read_recent(record, sources={"service"})
            sources = {e.source for e in entries}
            self.assertEqual(sources, {"service"})
        finally:
            os.unlink(dhu_path)
            os.unlink(svc_path)

    def test_empty_file_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            path = f.name
        try:
            collector = LogCollector()
            record = _make_record(log_path=path)
            entries = collector.read_recent(record)
            self.assertEqual(entries, [])
        finally:
            os.unlink(path)

    def test_dhu_noise_filtered_commands_kept(self):
        # Simulates combined log from DhuLineBuffer: commands appear
        # as "> command", DHU output appears without "> " prefix,
        # and bare "> " prompts are filtered out.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            f.write("SSL handshake complete\n")
            f.write("> \n")
            f.write("> keycode home\n")
            f.write("Video focus gained\n")
            f.write("> \n")
            f.write("> tap 300 430\n")
            path = f.name
        try:
            collector = LogCollector()
            record = _make_record(log_path=path)
            entries = collector.read_recent(record)
            texts = [e.text for e in entries]
            self.assertEqual(texts, [
                "SSL handshake complete",
                "> keycode home",
                "Video focus gained",
                "> tap 300 430",
            ])
        finally:
            os.unlink(path)

    def test_strips_trailing_newlines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            f.write("line with newline\n")
            f.write("another line\n")
            path = f.name
        try:
            collector = LogCollector()
            record = _make_record(log_path=path)
            entries = collector.read_recent(record)
            for e in entries:
                self.assertFalse(e.text.endswith("\n"))
        finally:
            os.unlink(path)


class LogCollectorTailTest(unittest.TestCase):

    def test_tail_yields_new_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            f.write("existing line\n")
            f.flush()
            dhu_path = f.name

        results = []

        def tail_thread():
            collector = LogCollector()
            record = _make_record(log_path=dhu_path)
            for entry in collector.tail(record, poll_interval=0.1):
                if entry is None:
                    continue
                results.append(entry)
                if len(results) >= 2:
                    break

        t = threading.Thread(target=tail_thread, daemon=True)
        t.start()

        # Give the tail time to seek to end
        time.sleep(0.2)

        # Write new lines
        with open(dhu_path, "a") as f:
            f.write("new line 1\n")
            f.write("new line 2\n")
            f.flush()

        t.join(timeout=3)
        os.unlink(dhu_path)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].text, "new line 1")
        self.assertEqual(results[1].text, "new line 2")
        self.assertEqual(results[0].source, "dhu")

    def test_tail_handles_file_truncation(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            f.write("original line\n")
            f.flush()
            dhu_path = f.name

        results = []

        def tail_thread():
            collector = LogCollector()
            record = _make_record(log_path=dhu_path)
            for entry in collector.tail(record, poll_interval=0.1):
                if entry is None:
                    continue
                results.append(entry)
                if len(results) >= 2:
                    break

        t = threading.Thread(target=tail_thread, daemon=True)
        t.start()
        time.sleep(0.2)

        # Append a line so tail reads past original content
        with open(dhu_path, "a") as f:
            f.write("before truncation\n")
            f.flush()
        time.sleep(0.3)

        # Truncate and write shorter content
        with open(dhu_path, "w") as f:
            f.write("after truncation\n")
            f.flush()

        t.join(timeout=5)
        os.unlink(dhu_path)

        self.assertGreaterEqual(len(results), 2)
        self.assertEqual(results[0].text, "before truncation")
        self.assertEqual(results[1].text, "after truncation")

    def test_tail_yields_none_on_idle(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False
        ) as f:
            f.write("initial\n")
            f.flush()
            dhu_path = f.name

        results = []

        def tail_thread():
            collector = LogCollector()
            record = _make_record(log_path=dhu_path)
            count = 0
            for entry in collector.tail(record, poll_interval=0.1):
                results.append(entry)
                count += 1
                if count >= 3:
                    break

        t = threading.Thread(target=tail_thread, daemon=True)
        t.start()
        t.join(timeout=3)
        os.unlink(dhu_path)

        # Should have yielded None values (no new content to read)
        self.assertTrue(any(r is None for r in results))


if __name__ == "__main__":
    unittest.main()
