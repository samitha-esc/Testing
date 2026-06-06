import json
import os
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from utils.mapping_engine import (
    ABSOLUTE_SOURCES, RELATIVE_SOURCES, TRIGGER_GESTURES,
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
}


def get_lan_ip():
    """Best-effort LAN IP so we can print a clickable URL."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class ControllerServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, addr, shared_state, mapping_engine):
        super().__init__(addr, _Handler)
        self.shared_state = shared_state
        self.mapping_engine = mapping_engine


def start_server(shared_state, mapping_engine, port=8080):
    """Start the server in a background thread. Returns (server, thread, url)."""
    server = ControllerServer(("0.0.0.0", port), shared_state, mapping_engine)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://{get_lan_ip()}:{port}"
    return server, thread, url


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # keep the console clean

    # ------------------------------------------------------------------ #
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/":
            self._serve_static("index.html")
        elif path == "/stream.mjpg":
            self._serve_mjpeg()
        elif path == "/state":
            self._serve_json(self.server.shared_state.get_status())
        elif path == "/mappings":
            self._serve_json({
                "config": self.server.mapping_engine.get_config(),
                "sources": {
                    "absolute": ABSOLUTE_SOURCES,
                    "relative": RELATIVE_SOURCES,
                    "trigger": TRIGGER_GESTURES,
                },
            })
        elif path.startswith("/static/"):
            self._serve_static(path[len("/static/"):])
        else:
            self._send(404, "text/plain", b"Not found")

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        body = self._read_body()
        ss = self.server.shared_state

        if path == "/mode":
            mode = (body or {}).get("mode")
            if mode in ("PLAY", "EXPRESSION", "DJ"):
                ss.push_command("mode", mode)
                self._serve_json({"ok": True, "mode": mode})
            else:
                self._serve_json({"ok": False, "error": "bad mode"}, code=400)

        elif path == "/recalibrate":
            ss.push_command("recalibrate")
            self._serve_json({"ok": True})

        elif path == "/mappings":
            try:
                cleaned = self.server.mapping_engine.set_config(body)
                self._serve_json({"ok": True, "config": cleaned})
            except Exception as e:
                self._serve_json({"ok": False, "error": str(e)}, code=400)

        elif path == "/quit":
            ss.push_command("quit")
            self._serve_json({"ok": True})

        else:
            self._send(404, "text/plain", b"Not found")

    # ------------------------------------------------------------------ #
    def _serve_mjpeg(self):
        self.send_response(200)
        self.send_header("Content-Type",
                         "multipart/x-mixed-replace; boundary=frame")
        self.send_header("Cache-Control", "no-cache, private")
        self.send_header("Connection", "close")
        self.end_headers()
        ss = self.server.shared_state
        seq = 0
        try:
            while True:
                frame, seq = ss.wait_frame(seq, timeout=2.0)
                if frame is None:
                    continue
                self.wfile.write(b"--frame\r\n")
                self.wfile.write(b"Content-Type: image/jpeg\r\n")
                self.wfile.write(
                    f"Content-Length: {len(frame)}\r\n\r\n".encode())
                self.wfile.write(frame)
                self.wfile.write(b"\r\n")
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _serve_static(self, rel):
        # Prevent path traversal.
        safe = os.path.normpath(rel).lstrip(os.sep)
        full = os.path.join(STATIC_DIR, safe)
        if not full.startswith(STATIC_DIR) or not os.path.isfile(full):
            self._send(404, "text/plain", b"Not found")
            return
        ext = os.path.splitext(full)[1]
        ctype = _CONTENT_TYPES.get(ext, "application/octet-stream")
        with open(full, "rb") as f:
            self._send(200, ctype, f.read())

    def _serve_json(self, obj, code=200):
        self._send(code, "application/json", json.dumps(obj).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0) or 0)
        if not length:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except Exception:
            return {}

    def _send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass
