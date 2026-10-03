#!/usr/bin/env python3
"""Bounded native UTF-8 document transport with real strong ETag conditions."""
from __future__ import annotations
import hashlib
import http.client
import multiprocessing
import re
import time
from urllib.parse import urlsplit
import sys
sys.dont_write_bytecode = True
from decision_evidence import line
import review_comments as rv

ETAG = re.compile(r'"[\x21\x23-\x7e\x80-\xff]*"\Z')
TOKEN = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+\Z")


class NativeSourceError(ValueError):
    pass


def condition(value):
    if not isinstance(value, str) or len(value) > 1024 or not ETAG.fullmatch(value):
        raise NativeSourceError('STRONG_NATIVE_CONDITION_REQUIRED')
    return value


def _worker(pipe, url, headers, method, body, expected, connect_timeout, read_timeout):
    connection = None
    try:
        pipe.send(('started', None))
        parsed = urlsplit(url)
        cls = http.client.HTTPSConnection if parsed.scheme == 'https' else http.client.HTTPConnection
        connection = cls(parsed.hostname, parsed.port, timeout=connect_timeout)
        connection.connect()
        pipe.send(('connected', None))
        connection.sock.settimeout(read_timeout)
        outgoing = dict(headers, Accept='text/markdown, text/plain', **{'Accept-Encoding': 'identity', 'Cache-Control': 'no-cache'})
        if method == 'PUT':
            outgoing.update({'If-Match': expected, 'Content-Type': 'text/markdown; charset=utf-8'})
        connection.request(method, parsed.path or '/', body=body, headers=outgoing)
        response = connection.getresponse()
        if method == 'PUT':
            # Acknowledgement is not readback. Never retry this request here.
            result = {'status': 'acknowledged'} if response.status in (200, 204) else (
                {'status': 'conflict', 'http_status': 409} if response.status in (409, 412)
                else {'status': 'unknown', 'code': 'NATIVE_WRITE_OUTCOME_UNKNOWN'})
            pipe.send(('result', result))
            return
        if response.status != 200:
            raise NativeSourceError('NATIVE_SOURCE_UNAVAILABLE')
        versions = [v for k, v in response.getheaders() if k.lower() == 'etag']
        if len(versions) != 1:
            raise NativeSourceError('STRONG_NATIVE_CONDITION_REQUIRED')
        version = condition(versions[0])
        if (response.headers.get_content_type() not in ('text/plain', 'text/markdown')
                or response.headers.get_content_charset('utf-8') != 'utf-8'
                or response.getheader('Content-Encoding', 'identity').lower() != 'identity'):
            raise NativeSourceError('UNSUPPORTED_NATIVE_REPRESENTATION')
        lengths = [v for k, v in response.getheaders() if k.lower() == 'content-length']
        if len(lengths) > 1 or lengths and (not lengths[0].isdigit() or int(lengths[0]) > rv.MAX_BYTES):
            raise NativeSourceError('RESOURCE_LIMIT')
        raw = response.read(rv.MAX_BYTES + 1)
        if len(raw) > rv.MAX_BYTES or lengths and len(raw) != int(lengths[0]):
            raise NativeSourceError('INVALID_NATIVE_RESPONSE')
        pipe.send(('result', dict(body=raw.decode('utf-8'), condition=version,
                                  content_digest=hashlib.sha256(raw).hexdigest())))
    except NativeSourceError as exc:
        pipe.send(('error', str(exc)))
    except (OSError, http.client.HTTPException, UnicodeError, ValueError):
        pipe.send(('error', 'NATIVE_TRANSPORT_FAILED'))
    finally:
        if connection is not None:
            connection.close()
        pipe.close()


class NativeDocument:
    """Host-configured existing raw-document endpoint, not a generic JSON API.

    Only bind APIs that actually implement strong If-Match conditional writes.
    Credentials stay in host memory; URLs/headers never come from review content.
    This transport does not provide workflow authorization or a durable journal.
    """
    def __init__(self, provider_key, source_ref, feature, reviews_ref, url, *, headers=None,
                 allow_loopback_http=False, connect_timeout=3, read_timeout=10, total_timeout=15):
        try:
            if not isinstance(url, str) or not url or any(ord(c) <= 32 or ord(c) > 126 for c in url):
                raise ValueError()
            parsed = urlsplit(url)
            port = parsed.port
        except ValueError:
            raise NativeSourceError('INVALID_NATIVE_BINDING') from None
        if (not all(line(v) and len(v) <= 1024 for v in (provider_key, source_ref, feature, reviews_ref))
                or not parsed.hostname or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment or any(c in url for c in '\r\n\x00')
                or port is not None and not 0 < port <= 65535):
            raise NativeSourceError('INVALID_NATIVE_BINDING')
        if parsed.scheme != 'https' and not (allow_loopback_http is True and parsed.scheme == 'http'
                                             and parsed.hostname in ('127.0.0.1', '::1')):
            raise NativeSourceError('HTTPS_REQUIRED')
        if (any(type(v) not in (int, float) for v in (connect_timeout, read_timeout, total_timeout))
                or not (0 < connect_timeout <= 3 and 0 < read_timeout <= 10 and 0.5 < total_timeout <= 15)):
            raise NativeSourceError('INVALID_QUERY_BUDGET')
        headers = dict(headers or {})
        reserved = {'host', 'content-length', 'transfer-encoding', 'if-match', 'if-none-match',
                    'content-type', 'accept-encoding', 'cache-control', 'accept', 'connection'}
        seen, size = set(), 0
        for key, value in headers.items():
            if (not isinstance(key, str) or not TOKEN.fullmatch(key) or key.lower() in reserved | seen
                    or not isinstance(value, str) or any(ord(c) < 32 or ord(c) > 255 or ord(c) == 127 for c in value)):
                raise NativeSourceError('UNSAFE_NATIVE_HEADER')
            seen.add(key.lower())
            size += len(key) + len(value)
        if size > 16384:
            raise NativeSourceError('RESOURCE_LIMIT')
        self.provider_key, self.source_ref = provider_key, source_ref
        self.feature, self.reviews_ref, self.url, self.headers = feature, reviews_ref, url, headers
        self.connect_timeout, self.read_timeout, self.total_timeout = connect_timeout, read_timeout, total_timeout

    def _request(self, method, body=None, expected=None):
        context = multiprocessing.get_context('spawn')
        receive, send = context.Pipe(duplex=False)
        process = context.Process(target=_worker, args=(send, self.url, self.headers, method, body, expected,
                                                        self.connect_timeout, self.read_timeout))
        deadline = time.monotonic() + self.total_timeout
        try:
            process.start()
            send.close()
            # Spawn/import startup has its own place in the total budget. The
            # socket-connect budget starts only when the worker is ready.
            remaining = deadline - time.monotonic() - 0.5
            if remaining <= 0 or not receive.poll(remaining):
                raise NativeSourceError('NATIVE_START_TIMEOUT')
            kind, payload = receive.recv()
            if kind == 'started':
                remaining = min(self.connect_timeout, deadline - time.monotonic() - 0.5)
                if remaining <= 0 or not receive.poll(remaining):
                    raise NativeSourceError('NATIVE_CONNECT_TIMEOUT')
                kind, payload = receive.recv()
            if kind == 'connected':
                remaining = min(self.read_timeout, deadline - time.monotonic() - 0.5)
                if remaining <= 0 or not receive.poll(remaining):
                    raise NativeSourceError('NATIVE_READ_TIMEOUT')
                kind, payload = receive.recv()
            if kind != 'result' or time.monotonic() > deadline - 0.5:
                raise NativeSourceError(payload if kind == 'error' else 'NATIVE_REQUEST_TIMEOUT')
            return payload
        except (EOFError, OSError):
            raise NativeSourceError('NATIVE_TRANSPORT_FAILED') from None
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

    def read_document(self):
        result = self._request('GET')
        result.update(provider_key=self.provider_key, source_ref=self.source_ref,
                      source_version=dict(kind='native', value=result['condition']))
        return result

    def conditional_put(self, text, expected_condition, *, authority=False):
        if authority is not True:
            raise NativeSourceError('AUTHORITY_REQUIRED')
        condition(expected_condition)
        if not isinstance(text, str) or len(text) > rv.MAX_BYTES:
            raise NativeSourceError('RESOURCE_LIMIT')
        try:
            raw = text.encode('utf-8')
        except UnicodeError:
            raise NativeSourceError('INVALID_NATIVE_ENCODING') from None
        if len(raw) > rv.MAX_BYTES:
            raise NativeSourceError('RESOURCE_LIMIT')
        try:
            result = self._request('PUT', raw, expected_condition)
        except NativeSourceError as exc:
            result = dict(status='unknown', code=str(exc))
        result.update(draft_persisted=False, attempts=1, agent_consumed=False, decision_effect='NONE')
        return result


def read_for_purpose(purpose, *, endpoint=None, explicit_review=False, statuses=None, rv_ids=None):
    if purpose not in ('requirement', 'solution', 'development', 'review', 'delivery') or type(explicit_review) is not bool:
        raise NativeSourceError('INVALID_REVIEW_PURPOSE')
    if purpose != 'review' and not explicit_review:
        return dict(status='NOT_REQUESTED', read_executed=False, records=[], agent_consumed=False)
    if endpoint is None:
        if statuses is not None or rv_ids is not None:
            raise NativeSourceError('REVIEW_NOT_BOUND')
        return dict(status='UNBOUND_EMPTY', read_executed=False, records=[], agent_consumed=False)
    observed = endpoint.read_document()
    parsed = rv.parse(observed['body'], feature=endpoint.feature, reviews_ref=endpoint.reviews_ref)
    return dict(status='READ', read_executed=True, source_ref=endpoint.source_ref, reviews_ref=endpoint.reviews_ref,
                source_version=observed['source_version'], source_digest=observed['content_digest'],
                original=observed['body'], records=rv.select(parsed, statuses=statuses, rv_ids=rv_ids),
                legacy=parsed['legacy'], agent_consumed=False, application_authorized=False, decision_effect='NONE')
