import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SCRIPT = Path(__file__).resolve().parents[1] / "search.py"
SPEC = importlib.util.spec_from_file_location("agentmemory_search", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        self.server.requests.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"]))), self.headers.get("Authorization")))
        code, body = self.server.reply
        self.send_response(code)
        if code == 302:
            self.send_header("Location", self.server.redirect)
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.requests = []
        self.server.reply = (200, {"results": []})
        self.server.redirect = "https://example.org/"
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join()

    def run_cli(self, *args, env=None):
        environment = {**os.environ, "AGENTMEMORY_TOKEN": "test-only", "AGENTMEMORY_TOKEN_FILE": "", "AGENTMEMORY_SECRET": ""}
        environment.update(env or {})
        return subprocess.run([sys.executable, "-B", str(SCRIPT), "--api-url", self.url, *args], cwd=tempfile.gettempdir(), env=environment, capture_output=True, text=True, encoding="utf-8", timeout=10)

    def test_all_five_search_routes_and_utf8(self):
        for kind, endpoint in MODULE.ENDPOINTS.items():
            with self.subTest(kind=kind):
                result = self.run_cli("论文", "--kind", kind)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), {"results": []})
                path, body, auth = self.server.requests[-1]
                self.assertEqual(path, endpoint)
                self.assertEqual(body.get("query", body.get("queryText")), "论文")
                self.assertEqual(auth, "Bearer test-only")
                self.assertNotIn("targetLayer", body)

    def test_token_file_can_be_read_only_and_bom_prefixed(self):
        with tempfile.TemporaryDirectory() as folder:
            token = Path(folder) / "token"
            token.write_text("Bearer mounted-test-token\n", encoding="utf-8-sig")
            token.chmod(0o444)
            try:
                result = self.run_cli("test", "--token-file", str(token))
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.server.requests[-1][2], "Bearer mounted-test-token")
                self.assertNotIn("mounted-test-token", result.stdout + result.stderr)
            finally:
                token.chmod(0o644)

    def test_invalid_or_inapplicable_flags_never_make_requests(self):
        for args in [("test", "--limit", "0"), ("test", "--session-id", "s1"), ("test", "--kind", "vision", "--project", "demo"), ("test", "--kind", "lessons", "--min-confidence", "nan"), ("test", "--token-budget", "0"), ("test", "--min-confidence", "0")]:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(result.stdout)
        self.assertEqual(self.server.requests, [])

    def test_error_status_and_logical_failure_use_stderr(self):
        for reply in [(401, {"error": "unauthorized"}), (200, {"success": False, "error": "feature disabled"})]:
            self.server.reply = reply
            result = self.run_cli("test")
            self.assertEqual(result.returncode, 1)
            self.assertFalse(result.stdout)
            self.assertIn("error", json.loads(result.stderr))

    def test_does_not_follow_redirects(self):
        self.server.reply = (302, {})
        result = self.run_cli("test")
        self.assertEqual(result.returncode, 1)
        self.assertIn("302", result.stderr)
        self.assertEqual(len(self.server.requests), 1)

    def test_layer_opt_in_and_vision_input(self):
        args = MODULE.parser().parse_args(["topic", "--layer", "observation"])
        self.assertEqual(MODULE.make_body(args)["targetLayer"], "observation")
        args = MODULE.parser().parse_args(["--kind", "vision", "--image-ref", "/images/a.png", "--session-id", "s1"])
        self.assertEqual(MODULE.make_body(args), {"topK": 5, "queryImageRef": "/images/a.png", "sessionId": "s1"})

    def test_reference_image_is_read_without_upload_or_file_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "reference.png"
            image.write_bytes(b"\x00\x01\x02")
            result = self.run_cli("--kind", "vision", "--image-file", str(image))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.server.requests[-1][1]["queryImageBase64"], "data:image/png;base64,AAEC")
            self.assertEqual(list(Path(folder).iterdir()), [image])


if __name__ == "__main__":
    unittest.main()
