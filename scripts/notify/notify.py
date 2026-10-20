"""Small HTTP inbox for AOPC; Windows desktop notifications live in bridge.py."""

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import sqlite3
from string import Template
import threading
import time
from urllib.error import URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import build_opener, ProxyHandler, Request
import uuid


SERVICE = "aopc-notify-v2"
DEFAULT_URL = "http://127.0.0.1:17654"
MAX_MESSAGE_BYTES = 32_768
MAX_BODY_BYTES = MAX_MESSAGE_BYTES * 6 + 1024


def _validate_message(message):
    if not isinstance(message, str):
        raise TypeError("message must be a string")
    if not message.strip():
        raise ValueError("message must not be empty")
    if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ValueError("message must be at most 32768 UTF-8 bytes")


def request_json(path, payload=None, *, base_url=None, timeout=5):
    """Use a direct local connection, independent of system proxy settings."""
    base_url = (base_url or os.environ.get("AOPC_NOTIFY_URL", DEFAULT_URL)).rstrip("/")
    if urlsplit(base_url).scheme not in ("http", "https"):
        raise ValueError("AOPC_NOTIFY_URL must use http or https")
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(base_url + path, data=body, headers={"Content-Type": "application/json"})
    with build_opener(ProxyHandler({})).open(request, timeout=timeout) as response:
        return json.load(response)


def notify(message: str) -> None:
    """Store text in the background inbox; the Windows bridge sends its toast.

    Start the service and desktop bridge with start.ps1 once before calling.
    The function returns after durable storage, not after the user reads it.
    """
    _validate_message(message)
    try:
        result = request_json("/notify", {"message": message})
    except (OSError, URLError) as error:
        raise RuntimeError("Cannot send notification. Start scripts/notify/start.ps1 first; "
                           "check AOPC_NOTIFY_URL if sending from a container.") from error
    if not isinstance(result, dict) or result.get("ok") is not True:
        raise RuntimeError("The inbox did not acknowledge the message")


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.condition = threading.Condition()
        with self.connect() as connection:
            connection.execute("CREATE TABLE IF NOT EXISTS messages "
                               "(id INTEGER PRIMARY KEY AUTOINCREMENT, message TEXT NOT NULL, "
                               "created_at TEXT NOT NULL)")
            connection.execute("CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT)")
            connection.execute("INSERT OR IGNORE INTO metadata VALUES ('instance', ?)", (str(uuid.uuid4()),))
            self.instance = connection.execute("SELECT value FROM metadata WHERE key='instance'").fetchone()[0]

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def latest_id(self):
        with self.connect() as connection:
            return connection.execute("SELECT COALESCE(MAX(id), 0) FROM messages").fetchone()[0]

    def add(self, message):
        _validate_message(message)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self.condition:
            with self.connect() as connection:
                cursor = connection.execute("INSERT INTO messages (message, created_at) VALUES (?, ?)",
                                            (message, created_at))
                item = {"id": cursor.lastrowid, "message": message, "created_at": created_at}
            self.condition.notify_all()
        return item

    def get(self, message_id):
        with self.connect() as connection:
            row = connection.execute("SELECT * FROM messages WHERE id=?", (message_id,)).fetchone()
            return None if row is None else dict(row)

    def recent(self):
        with self.connect() as connection:
            return [dict(row) for row in connection.execute("SELECT * FROM messages ORDER BY id DESC LIMIT 100")]

    def events(self, after, wait):
        deadline = time.monotonic() + wait
        with self.condition:
            while True:
                with self.connect() as connection:
                    items = [dict(row) for row in connection.execute(
                        "SELECT * FROM messages WHERE id>? ORDER BY id LIMIT 100", (after,))]
                remaining = deadline - time.monotonic()
                if items or remaining <= 0:
                    return items
                self.condition.wait(remaining)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, database):
        self.store = Store(database)
        self.bridge_seen = None
        self.slots = threading.BoundedSemaphore(32)
        self.template = Template(Path(__file__).with_name("web.html").read_text(encoding="utf-8"))
        super().__init__(address, _Handler)

    def process_request(self, request, client_address):
        if not self.slots.acquire(blocking=False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, client_address)
        except Exception:
            self.slots.release()
            raise

    def process_request_thread(self, request, client_address):
        try:
            super().process_request_thread(request, client_address)
        finally:
            self.slots.release()


class _Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(5)

    def log_message(self, *_args):
        pass

    def reply(self, status, data, content_type="application/json; charset=utf-8"):
        body = (json.dumps(data) if content_type.startswith("application/json") else data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def page(self, title, content):
        self.reply(200, self.server.template.substitute(title=escape(title), content=content),
                   "text/html; charset=utf-8")

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/health":
            seen = self.server.bridge_seen
            self.reply(200, {"service": SERVICE, "instance": self.server.store.instance,
                             "last_id": self.server.store.latest_id(),
                             "bridge_connected": seen is not None and time.monotonic() - seen < 60})
        elif url.path == "/api/messages":
            self.reply(200, {"messages": self.server.store.recent()})
        elif url.path == "/api/events":
            try:
                query = parse_qs(url.query)
                after = int(query.get("after", ["0"])[0])
                wait = int(query.get("wait", ["25"])[0])
                if not (0 <= after <= 2**63 - 1 and 0 <= wait <= 25):
                    raise ValueError()
            except ValueError:
                self.reply(400, {"error": "after must be nonnegative; wait must be 0..25"})
                return
            self.server.bridge_seen = time.monotonic()
            self.reply(200, {"instance": self.server.store.instance,
                             "messages": self.server.store.events(after, wait)})
        elif url.path == "/":
            items = self.server.store.recent()
            content = '<div class="intro"><h1>消息收件箱</h1><p>从 Windows 通知点进来，在这里查看完整内容。</p></div>'
            if not items:
                content += '<section class="empty">还没有消息。调用 notify("你好") 发送第一条。</section>'
            for item in items:
                content += (f'<a class="card" href="/messages/{item["id"]}">'
                            f'<div class="meta">#{item["id"]} · {escape(item["created_at"])}</div>'
                            f'<p>{escape(item["message"][:180])}</p><span class="more">查看全文 →</span></a>')
            self.page("消息收件箱", content)
        elif url.path.startswith("/messages/"):
            try:
                message_id = int(url.path.removeprefix("/messages/"))
                if not 0 < message_id <= 2**63 - 1:
                    raise ValueError()
                item = self.server.store.get(message_id)
            except ValueError:
                item = None
            if item is None:
                self.reply(404, {"error": "message not found"})
                return
            self.page(f'消息 #{item["id"]}',
                      f'<div class="intro"><a href="/">← 返回收件箱</a><h1>消息 #{item["id"]}</h1>'
                      f'<p>{escape(item["created_at"])}</p></div>'
                      f'<article class="detail">{escape(item["message"])}</article>')
        else:
            self.reply(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/notify":
            self.reply(404, {"error": "not found"})
            return
        try:
            origin = self.headers.get("Origin")
            if origin and urlsplit(origin).netloc != self.headers.get("Host"):
                raise ValueError("cross-origin requests are not allowed")
            if self.headers.get_content_type() != "application/json":
                raise ValueError("Content-Type must be application/json")
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError("invalid message body size")
            payload = json.loads(self.rfile.read(length))
            if not isinstance(payload, dict):
                raise ValueError("body must be an object with a message field")
            message = payload.get("message")
            _validate_message(message)
        except (TypeError, ValueError) as error:
            self.reply(400, {"error": str(error)})
            return
        item = self.server.store.add(message)
        self.reply(200, {"ok": True, "id": item["id"], "path": f'/messages/{item["id"]}'})


def main():
    parser = argparse.ArgumentParser(description="AOPC background inbox and notify(message) sender")
    parser.add_argument("message", nargs="?")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=17654)
    parser.add_argument("--database", default=str(Path(__file__).with_name("data") / "messages.db"))
    args = parser.parse_args()
    if args.serve == (args.message is not None):
        parser.error("provide either a message or --serve")
    try:
        if args.serve:
            with _Server((args.host, args.port), args.database) as server:
                print(f"AOPC Notify listening on {args.host}:{args.port}", flush=True)
                try:
                    server.serve_forever()
                except KeyboardInterrupt:
                    pass
        else:
            notify(args.message)
    except (OSError, RuntimeError, ValueError) as error:
        parser.exit(1, f"notify: {error}\n")


if __name__ == "__main__":
    main()
