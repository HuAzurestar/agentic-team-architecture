#!/usr/bin/env python3
"""Real loopback HTTP queries: no remote mutation or simulated forge claim."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import multiprocessing
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
import uuid
from unittest.mock import patch

sys.dont_write_bytecode = True
import remote_lookup as remote
import task_operation as op
import test_task_reconcile as fixtures


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def handle(self):
        try:
            super().handle()
        except (ConnectionResetError, ConnectionAbortedError):
            pass  # Expected when a bounded query worker is terminated.

    def do_POST(self):
        self.server.writes += 1
        self.send_error(405)

    def do_GET(self):
        self.server.reads.append(self.path)
        mode = self.server.mode
        code = 200
        data = dict(id="42", title="标题", body="body\ntext", version="v1")
        if mode == "changed":
            data["body"] = "third-party change"
        elif mode == "wrong-id":
            data["id"] = "43"
        elif mode == "slow":
            time.sleep(0.5)
        elif (mode == "retry" and len(self.server.reads) == 1) or mode == "unavailable":
            code = 503
        elif mode == "redirect":
            code = 302
        raw = json.dumps(data, ensure_ascii=False).encode()
        if mode == "large":
            raw = b"x" * (remote.MAX_RESPONSE + 1)
        elif mode == "invalid":
            raw = b"NOT JSON"
        try:
            self.send_response(code)
            self.send_header("Content-Length", str(len(raw)))
            if code == 302:
                self.send_header("Location", "http://127.0.0.1:1/private")
            self.end_headers()
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass


def delayed_connect(pipe, url, headers, fields):
    time.sleep(5)


class RemoteTests(unittest.TestCase):
    def setUp(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.server.mode, self.server.reads, self.server.writes = "ok", [], 0
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_port}/objects/{{id}}"
        self.record = dict(operation_version="operation-v1", operation_id=str(uuid.uuid4()), kind="remote-write",
                           feature="PIRC-23", task="DEV-02", authority_source_ref="session:actual-request",
                           target_identity={"provider_key": "test-provider"},
                           expected_source={"content_digest": remote.content_digest("标题", "body\ntext")},
                           owned_paths=[], intent_ref="gists/parser.md", observed_result={"status": "unknown", "object_id": "42"}, recorded_fields=[])

    def reader(self, **kwargs):
        return remote.ObjectReader("test-provider", self.url, allow_loopback_http=True, **kwargs)

    def test_F03_T07_unique_id_reads_exact_object_without_creating(self):
        result = remote.inspect_remote(self.record, self.reader())
        self.assertFalse(result["conflicts"], result)
        self.assertEqual(result["observed_result"]["object_id"], "42")
        self.assertEqual(self.server.reads, ["/objects/42"])
        self.assertEqual(self.server.writes, 0)

    def test_F03_T07_unknown_without_id_performs_no_query(self):
        self.record["observed_result"] = {"status": "unknown"}
        reader = self.reader()
        with patch.object(reader, "lookup", side_effect=AssertionError("must not query by title")):
            result = remote.inspect_remote(self.record, reader)
        self.assertEqual(result["conflicts"][0]["code"], "REMOTE_OUTCOME_UNKNOWN")
        self.assertEqual(self.server.reads, [])

    def test_host_provider_must_match_before_query(self):
        self.record["target_identity"]["provider_key"] = "unapproved-provider"
        self.assertEqual(remote.inspect_remote(self.record, self.reader())["conflicts"][0]["code"], "LOOKUP_AUTHORITY_REQUIRED")
        self.assertEqual(self.server.reads, [])

    def test_changed_content_or_wrong_object_id_is_not_accepted(self):
        self.server.mode = "changed"
        self.assertEqual(remote.inspect_remote(self.record, self.reader())["conflicts"][0]["code"], "REMOTE_CONTENT_CHANGED")
        self.server.mode = "wrong-id"
        self.assertEqual(remote.inspect_remote(self.record, self.reader())["conflicts"][0]["code"], "REMOTE_IDENTITY_MISMATCH")

    def test_expected_version_can_be_verified_without_content_basis(self):
        self.record["expected_source"] = {"version": "v1"}
        self.assertFalse(remote.inspect_remote(self.record, self.reader())["conflicts"])
        self.record["expected_source"] = {"version": "v0"}
        self.assertEqual(remote.inspect_remote(self.record, self.reader())["conflicts"][0]["code"], "REMOTE_CONTENT_CHANGED")

    def test_one_read_retry_is_allowed_no_write_retry_exists(self):
        self.server.mode = "retry"
        result = remote.inspect_remote(self.record, self.reader())
        self.assertEqual(result["query_attempts"], 2)
        self.assertFalse(result["conflicts"])
        self.assertEqual(self.server.writes, 0)

    def test_repeated_error_stops_after_two_queries(self):
        self.server.mode = "unavailable"
        result = remote.inspect_remote(self.record, self.reader())
        self.assertEqual(result["query_attempts"], 2)
        self.assertEqual(len(self.server.reads), 2)
        self.assertEqual(result["conflicts"][0]["code"], "REMOTE_OUTCOME_UNKNOWN")

    def test_redirect_is_not_followed(self):
        self.server.mode = "redirect"
        result = remote.inspect_remote(self.record, self.reader())
        self.assertEqual(result["query_attempts"], 1)
        self.assertEqual(len(self.server.reads), 1)
        self.assertTrue(result["conflicts"])

    def test_large_or_invalid_response_is_rejected_without_retry(self):
        for mode, code in (("large", "REMOTE_RESPONSE_LIMIT"), ("invalid", "REMOTE_RESPONSE_INVALID")):
            self.server.mode = mode
            result = remote.inspect_remote(self.record, self.reader())
            self.assertEqual(result["query_attempts"], 1)
            self.assertEqual(result["conflicts"][0]["query_code"], code)

    def test_read_deadline_terminates_worker_and_leaves_no_child(self):
        self.server.mode = "slow"
        before = {p.pid for p in multiprocessing.active_children()}
        result = remote.inspect_remote(self.record, self.reader(read_timeout=0.1, total_timeout=2))
        self.assertEqual(result["conflicts"][0]["code"], "REMOTE_OUTCOME_UNKNOWN")
        self.assertLessEqual(result["query_attempts"], 2)
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_credentials_and_nonapproved_plain_http_are_rejected(self):
        with self.assertRaises(ValueError):
            remote.ObjectReader("x", "https://user:secret@example.invalid/{id}")
        with self.assertRaises(ValueError):
            remote.ObjectReader("x", "http://example.invalid/{id}", allow_loopback_http=True)
        with self.assertRaises(ValueError):
            remote.ObjectReader("x", self.url, allow_loopback_http=True, read_timeout=11)
        result = remote.inspect_remote(self.record, self.reader(headers={"Authorization": "Bearer TEST-SECRET"}))
        self.assertNotIn("TEST-SECRET", json.dumps(result))

    def test_connect_and_total_budgets_bound_stalled_worker(self):
        before = {p.pid for p in multiprocessing.active_children()}
        started = time.monotonic()
        with patch.object(remote, "request_worker", delayed_connect):
            result = remote.inspect_remote(self.record, self.reader(connect_timeout=0.5, total_timeout=1.2))
        self.assertLess(time.monotonic() - started, 2)
        self.assertLessEqual(result["query_attempts"], 2)
        self.assertEqual(result["conflicts"][0]["code"], "REMOTE_OUTCOME_UNKNOWN")
        self.assertEqual({p.pid for p in multiprocessing.active_children()}, before)

    def test_missing_expected_basis_or_invalid_id_never_queries(self):
        self.record["expected_source"] = {}
        self.assertEqual(remote.inspect_remote(self.record, self.reader())["conflicts"][0]["code"], "INVALID_REMOTE_INTENT")
        self.record["expected_source"] = {"version": "v1"}
        self.record["observed_result"]["object_id"] = "../private"
        result = remote.inspect_remote(self.record, self.reader())
        self.assertEqual(result["conflicts"][0]["query_code"], "INVALID_OBJECT_ID")
        self.assertEqual(self.server.reads, [])

    def test_dot_path_ids_and_invalid_digest_never_query(self):
        for value in (".", "..", True):
            self.record["observed_result"]["object_id"] = value
            result = remote.inspect_remote(self.record, self.reader())
            self.assertEqual(result["conflicts"][0]["query_code"], "INVALID_OBJECT_ID")
        self.record["observed_result"]["object_id"] = "42"
        self.record["expected_source"] = {"content_digest": "not-a-digest"}
        self.assertEqual(remote.inspect_remote(self.record, self.reader())["conflicts"][0]["code"], "INVALID_REMOTE_INTENT")
        self.assertEqual(self.server.reads, [])

    def test_integer_id_from_original_response_is_preserved_as_identity(self):
        self.record["observed_result"]["object_id"] = 42
        result = remote.inspect_remote(self.record, self.reader())
        self.assertFalse(result["conflicts"], result)
        self.assertEqual(result["observed_result"]["object_id"], "42")

    def test_remote_operation_cli_only_records_readback(self):
        fixture = fixtures.RecoveryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        raw = (fixture.root / fixture.plan_ref).read_bytes()
        op.save(fixture.root, fixture.plan_ref, self.record, raw)
        command = [sys.executable, str(Path(op.recovery.__file__)), str(fixture.root),
                   "--plan-gist", fixture.plan_ref, "--operation-id", self.record["operation_id"],
                   "--repo", f"pm={fixture.pm}", "--repo", f"app={fixture.app}",
                   "--lookup-url", self.url, "--lookup-provider", "test-provider", "--lookup-allow-loopback-http",
                   "--apply", "--authorized"]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual(json.loads(result.stdout)["effect"], "APPLIED")
        self.assertEqual(self.server.writes, 0)

    def test_remote_record_only_reentry_preserves_original_unknown(self):
        fixture = fixtures.RecoveryTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        raw = (fixture.root / fixture.plan_ref).read_bytes()
        op.save(fixture.root, fixture.plan_ref, self.record, raw)
        overrides = {"pm": fixture.pm, "app": fixture.app}
        before = (fixture.root / fixture.plan_ref).read_bytes()
        result = op.reconcile(fixture.root, fixture.plan_ref, self.record["operation_id"], overrides, remote_reader=self.reader())
        self.assertFalse(result["conflicts"], result)
        self.assertEqual((fixture.root / fixture.plan_ref).read_bytes(), before)
        result = op.reconcile(fixture.root, fixture.plan_ref, self.record["operation_id"], overrides, apply=True, authority=True, remote_reader=self.reader())
        self.assertEqual(result["effect"], "APPLIED", result)
        saved = op.read_gist(fixture.root, fixture.plan_ref)[3][self.record["operation_id"]]
        self.assertEqual(saved["initial_observed_result"]["status"], "unknown")
        with patch.object(op.recovery, "atomic_replace", side_effect=AssertionError("repeat write")):
            repeated = op.reconcile(fixture.root, fixture.plan_ref, self.record["operation_id"], overrides, apply=True, authority=True, remote_reader=self.reader())
        self.assertEqual(repeated["effect"], "UNCHANGED", repeated)
        self.assertEqual(self.server.writes, 0)


if __name__ == "__main__":
    unittest.main()
