"""Tests for the web dashboard log endpoints."""

import http.client
import json
import os
import tempfile
import threading
import time
import unittest
import urllib.request

from instance_manager.src.instance_store import InstanceStore, RUNNING
from instance_manager.src.log_collector import LogCollector
from instance_manager.src.web_server import start_web_server


class WebServerLogsApiTest(unittest.TestCase):
    """Tests for /api/logs/<name> endpoint."""

    def setUp(self):
        self.store = InstanceStore()
        self._tmp_files = []
        self.log_collector = LogCollector()
        self.http_server, self.thread = start_web_server(
            self.store, port=0, log_collector=self.log_collector,
        )
        self.port = self.http_server.server_address[1]
        self.base_url = f"http://localhost:{self.port}"

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        for path in self._tmp_files:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _make_dhu_log(self, content="dhu log line\n"):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False,
        )
        f.write(content)
        f.close()
        self._tmp_files.append(f.name)
        return f.name

    def test_api_logs_returns_entries(self):
        dhu_path = self._make_dhu_log("line 1\nline 2\n")
        self.store.create("inst1", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("inst1", state=RUNNING, log_path=dhu_path)

        resp = urllib.request.urlopen(f"{self.base_url}/api/logs/inst1")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "application/json")
        data = json.loads(resp.read())
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]["source"], "dhu")
        self.assertEqual(data[0]["text"], "line 1")
        self.assertEqual(data[1]["text"], "line 2")

    def test_api_logs_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/api/logs/missing")
        self.assertEqual(ctx.exception.code, 404)

    def test_api_logs_empty_when_no_files(self):
        self.store.create("inst2", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("inst2", state=RUNNING)

        resp = urllib.request.urlopen(f"{self.base_url}/api/logs/inst2")
        data = json.loads(resp.read())
        self.assertEqual(data, [])

    def test_api_logs_source_filter(self):
        dhu_path = self._make_dhu_log("dhu content\n")
        svc_path = self._make_dhu_log("svc content\n")
        collector = LogCollector(service_log_path=svc_path)

        # Restart server with the custom collector
        self.http_server.shutdown()
        self.http_server.server_close()
        self.http_server, self.thread = start_web_server(
            self.store, port=0, log_collector=collector,
        )
        self.port = self.http_server.server_address[1]
        self.base_url = f"http://localhost:{self.port}"

        self.store.create("inst3", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("inst3", state=RUNNING, log_path=dhu_path)

        resp = urllib.request.urlopen(
            f"{self.base_url}/api/logs/inst3?sources=service"
        )
        data = json.loads(resp.read())
        sources = {e["source"] for e in data}
        self.assertEqual(sources, {"service"})


class WebServerLogViewerTest(unittest.TestCase):
    """Tests for /logs/<name> HTML viewer endpoint."""

    def setUp(self):
        self.store = InstanceStore()
        self.http_server, self.thread = start_web_server(
            self.store, port=0, log_collector=LogCollector(),
        )
        self.port = self.http_server.server_address[1]
        self.base_url = f"http://localhost:{self.port}"

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()

    def test_log_viewer_page(self):
        self.store.create("view1", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("view1", state=RUNNING)

        resp = urllib.request.urlopen(f"{self.base_url}/logs/view1")
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("Logs: view1", body)
        self.assertIn("EventSource", body)
        self.assertIn("auto-scroll", body)
        self.assertIn("src-filter", body)

    def test_log_viewer_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/logs/missing")
        self.assertEqual(ctx.exception.code, 404)

    def test_dashboard_has_logs_link(self):
        self.store.create("linked", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("linked", state=RUNNING)

        resp = urllib.request.urlopen(f"{self.base_url}/")
        body = resp.read().decode()
        self.assertIn('/logs/linked', body)
        self.assertIn(">logs</a>", body)


class WebServerLogStreamTest(unittest.TestCase):
    """Tests for /logs/<name>/stream SSE endpoint."""

    def setUp(self):
        self.store = InstanceStore()
        self._tmp_files = []
        self.log_collector = LogCollector()
        self.http_server, self.thread = start_web_server(
            self.store, port=0, log_collector=self.log_collector,
        )
        self.port = self.http_server.server_address[1]

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()
        for path in self._tmp_files:
            try:
                os.unlink(path)
            except OSError:
                pass

    def _make_log_file(self, content=""):
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False,
        )
        f.write(content)
        f.close()
        self._tmp_files.append(f.name)
        return f.name

    def test_stream_returns_sse_content_type(self):
        dhu_path = self._make_log_file("initial\n")
        self.store.create("sse1", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("sse1", state=RUNNING, log_path=dhu_path)

        conn = http.client.HTTPConnection("localhost", self.port, timeout=3)
        conn.request("GET", "/logs/sse1/stream")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.getheader("Content-Type"), "text/event-stream")
        conn.close()

    def test_stream_delivers_events(self):
        """Test SSE delivers events using polling instead of fixed sleep."""
        dhu_path = self._make_log_file()
        self.store.create("sse2", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("sse2", state=RUNNING, log_path=dhu_path)

        events = []

        def read_events():
            conn = http.client.HTTPConnection("localhost", self.port, timeout=5)
            conn.request("GET", "/logs/sse2/stream")
            resp = conn.getresponse()
            buf = b""
            while len(events) < 2:
                chunk = resp.read(1)
                if not chunk:
                    break
                buf += chunk
                while b"\n\n" in buf:
                    event, buf = buf.split(b"\n\n", 1)
                    line = event.decode().strip()
                    if line.startswith("data: "):
                        events.append(json.loads(line[6:]))
            conn.close()

        reader = threading.Thread(target=read_events, daemon=True)
        reader.start()

        # Give the SSE handler time to connect before writing data.
        time.sleep(0.3)

        with open(dhu_path, "a") as f:
            f.write("streamed line 1\n")
            f.write("streamed line 2\n")
            f.flush()

        # Poll for results with deadline instead of fixed sleep
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and len(events) < 2:
            time.sleep(0.1)

        reader.join(timeout=1)

        self.assertGreaterEqual(len(events), 2)
        self.assertEqual(events[0]["source"], "dhu")
        self.assertEqual(events[0]["text"], "streamed line 1")
        self.assertEqual(events[1]["text"], "streamed line 2")

    def test_stream_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(
                f"http://localhost:{self.port}/logs/missing/stream"
            )
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
