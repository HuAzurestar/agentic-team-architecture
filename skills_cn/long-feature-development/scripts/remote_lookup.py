#!/usr/bin/env python3
"""Bounded GET-only JSON object lookup configured by the actual host."""
from __future__ import annotations

import hashlib
import http.client
import json
import multiprocessing
import re
import time
from urllib.parse import quote, urlsplit

MAX_RESPONSE = 1024 * 1024


def content_digest(title, body):
    if not isinstance(title, str) or not isinstance(body, str):
        raise ValueError("INVALID_CONTENT")
    return hashlib.sha256(json.dumps({"title": title, "body": body}, ensure_ascii=False,
                                     sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def request_worker(pipe, url, headers, fields):
    connection = None
    try:
        parsed = urlsplit(url)
        cls = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = cls(parsed.hostname, parsed.port, timeout=3)
        connection.connect()
        pipe.send(("connected", None))
        connection.sock.settimeout(10)
        connection.request("GET", parsed.path + ("?" + parsed.query if parsed.query else ""), headers=headers)
        response = connection.getresponse()
        if response.status != 200:
            pipe.send(("error", {"code": "REMOTE_HTTP_ERROR", "retryable": response.status >= 500 or response.status == 429}))
            return
        raw = response.read(MAX_RESPONSE + 1)
        if len(raw) > MAX_RESPONSE:
            pipe.send(("error", {"code": "REMOTE_RESPONSE_LIMIT", "retryable": False}))
            return
        data = json.loads(raw)
        object_id = data[fields["id"]]
        if isinstance(object_id, bool) or not isinstance(object_id, (str, int)):
            raise ValueError()
        observed = {"object_id": str(object_id)}
        title, body = data.get(fields["title"]), data.get(fields["body"])
        if isinstance(title, str) and (body is None or isinstance(body, str)) and fields["body"] in data:
            observed["content_digest"] = content_digest(title, body or "")
        version = data.get(fields["version"])
        if isinstance(version, (str, int)) and not isinstance(version, bool):
            observed["version"] = str(version)
        if len(json.dumps(observed).encode()) > 8192:
            raise ValueError()
        pipe.send(("result", observed))
    except (OSError, http.client.HTTPException):
        pipe.send(("error", {"code": "REMOTE_READ_FAILED", "retryable": True}))
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        pipe.send(("error", {"code": "REMOTE_RESPONSE_INVALID", "retryable": False}))
    finally:
        if connection is not None:
            connection.close()
        pipe.close()


class ObjectReader:
    """One host-authorized endpoint; file contents cannot supply a new URL."""
    def __init__(self, provider_key, url_template, *, headers=None, fields=None,
                 allow_loopback_http=False, connect_timeout=3, read_timeout=10, total_timeout=15):
        parsed = urlsplit(url_template)
        if (not provider_key or url_template.count("{id}") != 1 or "{id}" not in parsed.path
                or parsed.username is not None or parsed.password is not None or parsed.fragment
                or parsed.query or not parsed.hostname):
            raise ValueError("INVALID_LOOKUP_ENDPOINT")
        if parsed.scheme != "https" and not (allow_loopback_http and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}):
            raise ValueError("HTTPS_REQUIRED")
        if not (0 < connect_timeout <= 3 and 0 < read_timeout <= 10 and 0.5 < total_timeout <= 15):
            raise ValueError("INVALID_QUERY_BUDGET")
        self.provider_key, self.url_template = provider_key, url_template
        self.headers = dict(headers or {})
        if any(k.lower() in {"host", "content-length", "transfer-encoding"} for k in self.headers):
            raise ValueError("UNSAFE_HEADER")
        self.fields = fields or {"id": "id", "title": "title", "body": "body", "version": "version"}
        if set(self.fields) != {"id", "title", "body", "version"} or not all(isinstance(v, str) and v for v in self.fields.values()):
            raise ValueError("INVALID_FIELD_MAPPING")
        self.connect_timeout, self.read_timeout, self.total_timeout = connect_timeout, read_timeout, total_timeout

    def lookup(self, object_id):
        if not isinstance(object_id, str) or object_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", object_id):
            return {"code": "INVALID_OBJECT_ID", "attempts": 0}
        deadline = time.monotonic() + self.total_timeout
        last = {"code": "REMOTE_QUERY_TIMEOUT"}
        attempts = 0
        for attempt in range(1, 3):
            if time.monotonic() >= deadline - 0.5:
                break
            context = multiprocessing.get_context("spawn")
            receive, send = context.Pipe(duplex=False)
            process = context.Process(target=request_worker, args=(send, self.url_template.replace("{id}", quote(object_id, safe="")), self.headers, self.fields))
            try:
                process.start()
                attempts += 1
                send.close()
                remaining = min(self.connect_timeout, deadline - time.monotonic() - 0.5)
                if remaining <= 0 or not receive.poll(remaining):
                    last = {"code": "REMOTE_CONNECT_TIMEOUT", "retryable": True}
                else:
                    kind, payload = receive.recv()
                    if kind == "connected":
                        remaining = min(self.read_timeout, deadline - time.monotonic() - 0.5)
                        if remaining <= 0 or not receive.poll(remaining):
                            kind, payload = "error", {"code": "REMOTE_READ_TIMEOUT", "retryable": True}
                        else:
                            kind, payload = receive.recv()
                    if kind == "result" and time.monotonic() <= deadline - 0.5:
                        return {"object": payload, "attempts": attempts}
                    last = payload if kind == "error" else {"code": "REMOTE_QUERY_TIMEOUT", "retryable": True}
            except (EOFError, OSError):
                last = {"code": "REMOTE_READ_FAILED", "retryable": True}
            finally:
                if process.pid is not None:
                    if process.is_alive():
                        process.terminate()
                    process.join(timeout=0.25)
                    if process.is_alive():
                        process.kill()
                        process.join(timeout=0.25)
                    process.close()
                receive.close()
                send.close()
            if not last.get("retryable"):
                break
        return {"code": last["code"], "attempts": attempts}


def inspect_remote(record, reader):
    result = dict(operation_id=record["operation_id"], observed_result={"status": "unknown"},
                  next_check="query-unique-object-before-retry", effect="NOT_APPLIED", recorded_fields=[], conflicts=[])
    object_id = record["observed_result"].get("object_id")
    if object_id is None or object_id == "":
        result["conflicts"] = [{"code": "REMOTE_OUTCOME_UNKNOWN"}]
        return result
    if isinstance(object_id, int) and not isinstance(object_id, bool):
        object_id = str(object_id)
    if reader is None or record["target_identity"] != {"provider_key": reader.provider_key}:
        result["conflicts"] = [{"code": "LOOKUP_AUTHORITY_REQUIRED"}]
        return result
    expected = record["expected_source"]
    if not expected or set(expected) - {"content_digest", "version"} or not all(isinstance(v, str) and v for v in expected.values()):
        result["conflicts"] = [{"code": "INVALID_REMOTE_INTENT"}]
        return result
    if "content_digest" in expected and not re.fullmatch(r"[a-f0-9]{64}", expected["content_digest"]):
        result["conflicts"] = [{"code": "INVALID_REMOTE_INTENT"}]
        return result
    found = reader.lookup(object_id)
    result["query_attempts"] = found["attempts"]
    if "object" not in found:
        result["conflicts"] = [{"code": "REMOTE_OUTCOME_UNKNOWN", "query_code": found["code"]}]
        return result
    observed = found["object"]
    if observed["object_id"] != object_id:
        result["conflicts"] = [{"code": "REMOTE_IDENTITY_MISMATCH"}]
        return result
    if any(observed.get(field) != value for field, value in expected.items()):
        result["conflicts"] = [{"code": "REMOTE_CONTENT_CHANGED"}]
        return result
    result["observed_result"] = {"status": "success", **observed, "evidence": "current-readback-not-call-receipt"}
    result["next_check"] = "authorized-record-only"
    return result
