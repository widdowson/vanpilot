"""HTTP dashboard for instance manager status."""

from __future__ import annotations

import html
import json
import re
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import urlparse, parse_qs

from instance_manager.src.instance_store import InstanceStore
from instance_manager.src.log_collector import LogCollector

_STATE_NAMES = {0: "UNSPECIFIED", 1: "CREATING", 2: "RUNNING", 3: "ERROR", 4: "DESTROYING"}
_STATE_COLORS = {1: "#f0ad4e", 2: "#5cb85c", 3: "#d9534f", 4: "#999"}
_INSTANCE_SCREENSHOT_RE = re.compile(
    r"^/instances/([a-zA-Z0-9][a-zA-Z0-9._-]*)/(dhu-screenshot|emu-screenshot)$"
)
_LOGS_PAGE_RE = re.compile(r"^/logs/([a-zA-Z0-9][a-zA-Z0-9._-]*)$")
_LOGS_STREAM_RE = re.compile(r"^/logs/([a-zA-Z0-9][a-zA-Z0-9._-]*)/stream$")
_API_LOGS_RE = re.compile(r"^/api/logs/([a-zA-Z0-9][a-zA-Z0-9._-]*)$")


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class DashboardHandler(BaseHTTPRequestHandler):
    """HTTP handler for the instance manager dashboard."""

    store: Optional[InstanceStore] = None
    log_collector: Optional[LogCollector] = None

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._serve_dashboard()
            return
        m = _INSTANCE_SCREENSHOT_RE.match(path)
        if m:
            name = m.group(1)
            kind = "emu" if m.group(2) == "emu-screenshot" else "dhu"
            self._serve_screenshot(name, kind)
            return
        if path == "/api/instances":
            self._serve_api_instances()
            return
        m = _API_LOGS_RE.match(path)
        if m:
            self._serve_api_logs(m.group(1), parse_qs(parsed.query))
            return
        m = _LOGS_STREAM_RE.match(path)
        if m:
            self._serve_log_stream(m.group(1), parse_qs(parsed.query))
            return
        m = _LOGS_PAGE_RE.match(path)
        if m:
            self._serve_log_viewer(m.group(1))
            return
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
                f'<td><a href="/logs/{safe_name}">logs</a></td>'
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
            "th{background:#333;color:#fff}"
            "a{color:#4fc3f7}</style>"
            "</head><body>"
            "<h1>VanPilot Instance Manager</h1>"
            "<table><tr><th>Name</th><th>State</th>"
            "<th>Console</th><th>ADB</th><th>AA Fwd</th>"
            "<th>Uptime</th><th>Headful</th><th>AVD</th>"
            "<th>DHU</th><th>Phone</th><th>Logs</th></tr>"
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

    def _serve_api_logs(self, name: str, params: dict):
        if not self.store:
            self.send_error(404)
            return
        record = self.store.get(name)
        if record is None:
            self.send_error(404)
            return
        collector = self.log_collector or LogCollector()
        source_filter = None
        if "sources" in params:
            source_filter = set(params["sources"][0].split(","))
        entries = collector.read_recent(record, sources=source_filter)
        data = [{"source": e.source, "text": e.text} for e in entries]
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def _serve_log_stream(self, name: str, params: dict):
        if not self.store:
            self.send_error(404)
            return
        record = self.store.get(name)
        if record is None:
            self.send_error(404)
            return
        collector = self.log_collector or LogCollector()
        source_filter = None
        if "sources" in params:
            source_filter = set(params["sources"][0].split(","))

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        try:
            last_event = time.monotonic()
            for entry in collector.tail(record, sources=source_filter,
                                        poll_interval=0.5):
                if entry is None:
                    # Keepalive: send SSE comment every ~15s of silence
                    if time.monotonic() - last_event >= 15:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_event = time.monotonic()
                    continue
                data = json.dumps({"source": entry.source, "text": entry.text})
                self.wfile.write(f"data: {data}\n\n".encode())
                self.wfile.flush()
                last_event = time.monotonic()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass

    def _serve_log_viewer(self, name: str):
        if not self.store:
            self.send_error(404)
            return
        record = self.store.get(name)
        if record is None:
            self.send_error(404)
            return
        safe_name = html.escape(name)
        page = _LOG_VIEWER_HTML.replace("{instance_name}", safe_name)
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode())

    def log_message(self, format, *args):
        """Suppress default access log output."""
        pass


_LOG_VIEWER_HTML = """\
<!DOCTYPE html><html><head>
<meta charset="utf-8">
<title>Logs: {instance_name}</title>
<style>
body{font-family:monospace;margin:20px;background:#1e1e1e;color:#d4d4d4}
h1{color:#fff}
a{color:#4fc3f7}
.controls{margin:10px 0}
.controls label{margin-right:15px;color:#ccc;cursor:pointer}
#log-output{background:#0d0d0d;border:1px solid #333;padding:10px;
  height:70vh;overflow-y:auto;white-space:pre-wrap;word-wrap:break-word}
.source-dhu{color:#4ec9b0}
.source-emulator{color:#ce9178}
.source-service{color:#569cd6}
</style></head><body>
<h1><a href="/">&larr;</a> Logs: {instance_name}</h1>
<div class="controls">
<label><input type="checkbox" class="src-filter" data-src="dhu" checked> DHU</label>
<label><input type="checkbox" class="src-filter" data-src="emulator" checked> Emulator</label>
<label><input type="checkbox" class="src-filter" data-src="service" checked> Service</label>
<label><input type="checkbox" id="auto-scroll" checked> Auto-scroll</label>
</div>
<div id="log-output"></div>
<script>
var output=document.getElementById('log-output');
var autoScroll=document.getElementById('auto-scroll');
var filters=document.querySelectorAll('.src-filter');
function appendEntry(e){
  var d=document.createElement('div');
  d.className='log-line source-'+e.source;
  d.dataset.source=e.source;
  d.textContent='['+e.source.toUpperCase()+'] '+e.text;
  output.appendChild(d);
  applyFilter(d);
  if(autoScroll.checked) output.scrollTop=output.scrollHeight;
}
function applyFilter(el){
  var src=el.dataset.source;
  var cb=document.querySelector('.src-filter[data-src="'+src+'"]');
  el.style.display=(!cb||cb.checked)?'':'none';
}
fetch('/api/logs/{instance_name}')
  .then(function(r){return r.json()})
  .then(function(entries){
    entries.forEach(appendEntry);
    output.scrollTop=output.scrollHeight;
  });
var evtSource=new EventSource('/logs/{instance_name}/stream');
evtSource.onmessage=function(event){appendEntry(JSON.parse(event.data))};
filters.forEach(function(cb){
  cb.addEventListener('change',function(){
    document.querySelectorAll('.log-line').forEach(applyFilter);
  });
});
</script></body></html>
"""


def start_web_server(
    store: InstanceStore,
    port: int = 8080,
    log_collector: Optional[LogCollector] = None,
) -> tuple[HTTPServer, threading.Thread]:
    """Start the HTTP dashboard server in a daemon thread.

    Returns:
        (server, thread) -- caller can use server.shutdown() to stop.
    """
    handler_class = type(
        "BoundHandler",
        (DashboardHandler,),
        {"store": store, "log_collector": log_collector},
    )
    server = _ThreadingHTTPServer(("0.0.0.0", port), handler_class)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
