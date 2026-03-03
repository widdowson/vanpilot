"""HTTP dashboard for instance manager status."""

from __future__ import annotations

import html
import json
import re
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional

from instance_manager.src.instance_store import InstanceStore

_STATE_NAMES = {0: "UNSPECIFIED", 1: "CREATING", 2: "RUNNING", 3: "ERROR", 4: "DESTROYING"}
_STATE_COLORS = {1: "#f0ad4e", 2: "#5cb85c", 3: "#d9534f", 4: "#999"}
_INSTANCE_SCREENSHOT_RE = re.compile(
    r"^/instances/([a-zA-Z0-9][a-zA-Z0-9._-]*)/(dhu-screenshot|emu-screenshot)$"
)


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the instance manager dashboard."""

    store: Optional[InstanceStore] = None

    def do_GET(self):
        if self.path == "/":
            self._serve_dashboard()
            return
        m = _INSTANCE_SCREENSHOT_RE.match(self.path)
        if m:
            name = m.group(1)
            kind = "emu" if m.group(2) == "emu-screenshot" else "dhu"
            self._serve_screenshot(name, kind)
        elif self.path == "/api/instances":
            self._serve_api_instances()
        else:
            self.send_error(404)

    def _serve_dashboard(self):
        instances = self.store.list_all() if self.store else []
        now_ms = int(time.time() * 1000)
        rows = ""
        for inst in instances:
            state_name = _STATE_NAMES.get(inst.state, "UNKNOWN")
            color = _STATE_COLORS.get(inst.state, "#999")
            safe_name = html.escape(inst.name)
            safe_avd = html.escape(inst.avd_name or "")
            elapsed_s = (now_ms - inst.created_at_ms) // 1000
            uptime = f"{elapsed_s // 3600}h {(elapsed_s % 3600) // 60}m {elapsed_s % 60}s"
            dhu_html = ""
            if inst.last_screenshot_png:
                dhu_html = (
                    f'<a href="/instances/{safe_name}/dhu-screenshot">'
                    f'<img src="/instances/{safe_name}/dhu-screenshot" '
                    f'width="160" alt="DHU"></a>'
                )
            emu_html = ""
            if inst.last_emulator_screenshot_png:
                emu_html = (
                    f'<a href="/instances/{safe_name}/emu-screenshot">'
                    f'<img src="/instances/{safe_name}/emu-screenshot" '
                    f'width="90" alt="Phone"></a>'
                )
            rows += (
                f"<tr>"
                f"<td>{safe_name}</td>"
                f'<td style="color:{color};font-weight:bold">{state_name}</td>'
                f"<td>{inst.emulator_console_port}</td>"
                f"<td>{inst.adb_port}</td>"
                f"<td>{inst.aa_forward_port}</td>"
                f"<td>{uptime}</td>"
                f"<td>{'yes' if inst.headful else 'no'}</td>"
                f"<td>{safe_avd}</td>"
                f"<td>{dhu_html}</td>"
                f"<td>{emu_html}</td>"
                f"</tr>\n"
            )

        page = (
            "<!DOCTYPE html><html><head>"
            '<meta charset="utf-8">'
            '<meta http-equiv="refresh" content="5">'
            "<title>VanPilot Instance Manager</title>"
            "<style>body{font-family:monospace;margin:20px}"
            "table{border-collapse:collapse;width:100%}"
            "th,td{border:1px solid #ddd;padding:8px;text-align:left}"
            "th{background:#333;color:#fff}</style>"
            "</head><body>"
            "<h1>VanPilot Instance Manager</h1>"
            "<table><tr><th>Name</th><th>State</th>"
            "<th>Console</th><th>ADB</th><th>AA Fwd</th>"
            "<th>Uptime</th><th>Headful</th><th>AVD</th><th>DHU</th><th>Phone</th></tr>"
            f"{rows}</table></body></html>"
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode())

    def _serve_screenshot(self, name: str, kind: str = "dhu"):
        if not self.store:
            self.send_error(404)
            return
        record = self.store.get(name)
        if record is None:
            self.send_error(404)
            return
        if kind == "emu":
            png = record.last_emulator_screenshot_png
        else:
            png = record.last_screenshot_png
        if not png:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()
        self.wfile.write(png)

    def _serve_api_instances(self):
        instances = self.store.list_all() if self.store else []
        data = [
            {
                "name": inst.name,
                "state": _STATE_NAMES.get(inst.state, "UNKNOWN"),
                "emulator_console_port": inst.emulator_console_port,
                "adb_port": inst.adb_port,
                "aa_forward_port": inst.aa_forward_port,
                "headful": inst.headful,
                "avd_name": inst.avd_name,
                "created_at_ms": inst.created_at_ms,
            }
            for inst in instances
        ]
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        """Suppress default access log output."""
        pass


def start_web_server(
    store: InstanceStore,
    port: int = 8080,
) -> tuple[HTTPServer, threading.Thread]:
    """Start the HTTP dashboard server in a daemon thread.

    Returns:
        (server, thread) — caller can use server.shutdown() to stop.
    """
    handler_class = type(
        "BoundHandler",
        (DashboardHandler,),
        {"store": store},
    )
    server = HTTPServer(("0.0.0.0", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
