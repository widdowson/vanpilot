"""Tests for the web dashboard server."""

import json
import unittest
import urllib.request

from instance_manager.src.instance_store import InstanceStore, RUNNING
from instance_manager.src.web_server import start_web_server


class WebServerTest(unittest.TestCase):

    def setUp(self):
        self.store = InstanceStore()
        self.http_server, self.thread = start_web_server(self.store, port=0)
        self.port = self.http_server.server_address[1]
        self.base_url = f"http://localhost:{self.port}"

    def tearDown(self):
        self.http_server.shutdown()
        self.http_server.server_close()

    def test_dashboard_empty(self):
        resp = urllib.request.urlopen(f"{self.base_url}/")
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("VanPilot Instance Manager", body)

    def test_dashboard_with_instance(self):
        self.store.create("agent-1", 5554, 5555, 5277, False, 1000, "test_avd")
        self.store.update("agent-1", state=RUNNING)
        resp = urllib.request.urlopen(f"{self.base_url}/")
        body = resp.read().decode()
        self.assertIn("agent-1", body)
        self.assertIn("RUNNING", body)

    def test_screenshot_route(self):
        self.store.create("snap", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("snap", last_screenshot_png=b"\x89PNG-fake")
        resp = urllib.request.urlopen(f"{self.base_url}/instances/snap/dhu-screenshot")
        self.assertEqual(resp.status, 200)
        self.assertEqual(resp.headers["Content-Type"], "image/png")
        self.assertEqual(resp.read(), b"\x89PNG-fake")

    def test_screenshot_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(f"{self.base_url}/instances/nope/dhu-screenshot")
        self.assertEqual(ctx.exception.code, 404)

    def test_api_instances(self):
        self.store.create("a", 5554, 5555, 5277, False, 1000, "avd")
        self.store.update("a", state=RUNNING)
        resp = urllib.request.urlopen(f"{self.base_url}/api/instances")
        data = json.loads(resp.read())
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "a")
        self.assertEqual(data[0]["state"], "RUNNING")

    def test_api_instances_empty(self):
        resp = urllib.request.urlopen(f"{self.base_url}/api/instances")
        data = json.loads(resp.read())
        self.assertEqual(data, [])


if __name__ == "__main__":
    unittest.main()
