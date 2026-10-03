#!/usr/bin/env python3
"""Actual loopback HTTP fixtures; not live provider authentication evidence."""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
import sys
import threading
import time
import unittest
from unittest.mock import patch
sys.dont_write_bytecode = True
import review_comments as rv
import review_native as native


def slow_start_worker(*args):
    # Actual spawned process: interpreter/module startup is not socket connect.
    time.sleep(0.6)
    native._worker(*args)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        state = self.server.state
        with state['lock']:
            state['gets'] += 1
            body, version = state['body'], state['version']
        time.sleep(state.get('delay', 0))
        self.send_response(state.get('status', 200))
        self.send_header('Content-Type', state.get('type', 'text/markdown; charset=utf-8'))
        for tag in state.get('etags', [version]):
            self.send_header('ETag', tag)
        self.send_header('Content-Length', state.get('length', str(len(body))))
        if state.get('encoding'):
            self.send_header('Content-Encoding', state['encoding'])
        if state.get('location'):
            self.send_header('Location', state['location'])
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_PUT(self):
        state = self.server.state
        body = self.rfile.read(int(self.headers['Content-Length']))
        with state['lock']:
            state['puts'] += 1
            state['seen_condition'] = self.headers.get('If-Match')
            if self.headers.get('If-Match') != state['version']:
                status = 412
            else:
                status = state.get('put_status', 204)
                if status == 204:
                    state['body'], state['version'] = body, '"opaque-two"'
        if state.get('drop'):
            self.connection.shutdown(socket.SHUT_RDWR)
            self.connection.close()
            return
        self.send_response(status)
        self.send_header('Content-Length', '0')
        self.end_headers()


class NativeTests(unittest.TestCase):
    def setUp(self):
        self.record = rv.new_review(dict(feature='PIRC-31', ref='REQ.md', selector='REQ-102'),
            dict(source_key='pm:REQ.md', source_text='Original.\n'), 'Check this.\n')
        self.state = dict(body=rv.render([self.record]).encode(), version='"opaque-one"',
                          puts=0, gets=0, lock=threading.Lock())
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.state = self.state
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.02}, daemon=True)
        self.thread.start()
        self.url = 'http://127.0.0.1:%d/reviews' % self.server.server_port

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def endpoint(self, **kwargs):
        return native.NativeDocument('test-provider', 'native:REVIEWS', 'PIRC-31', 'native:REVIEWS',
                                     kwargs.pop('url', self.url), allow_loopback_http=True, **kwargs)

    def test_actual_opaque_version_and_original_unicode_crlf(self):
        self.state['body'] = '原文\r\n保持。\r\n'.encode()
        got = self.endpoint().read_document()
        self.assertEqual(got['body'], self.state['body'].decode())
        self.assertEqual(got['source_version'], dict(kind='native', value='"opaque-one"'))
        self.assertEqual(got['content_digest'], hashlib.sha256(self.state['body']).hexdigest())

    def test_conditional_write_one_attempt_not_durable_or_consumed(self):
        result = self.endpoint().conditional_put('new 原文', '"opaque-one"', authority=True)
        self.assertEqual(result['status'], 'acknowledged')
        self.assertEqual(self.state['body'], 'new 原文'.encode())
        self.assertEqual(self.state['seen_condition'], '"opaque-one"')
        self.assertEqual(self.state['puts'], 1)
        self.assertFalse(result['draft_persisted'])
        self.assertFalse(result['agent_consumed'])
        self.assertEqual(result['decision_effect'], 'NONE')

    def test_stale_condition_conflicts_without_overwriting(self):
        before = self.state['body']
        result = self.endpoint().conditional_put('draft', '"stale"', authority=True)
        self.assertEqual(result['status'], 'conflict')
        self.assertEqual(result['http_status'], 409)
        self.assertEqual(self.state['body'], before)
        self.assertEqual(self.state['puts'], 1)

    def test_applied_but_response_lost_is_unknown_and_never_retried(self):
        self.state['drop'] = True
        endpoint = self.endpoint()
        result = endpoint.conditional_put('saved', '"opaque-one"', authority=True)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.state['puts'], 1)
        self.assertEqual(endpoint.read_document()['body'], 'saved')
        self.assertEqual(self.state['puts'], 1)

    def test_unexpected_write_status_is_unknown(self):
        self.state['put_status'] = 503
        result = self.endpoint().conditional_put('draft', '"opaque-one"', authority=True)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.state['puts'], 1)

    def test_authority_and_strong_condition_required_before_io(self):
        endpoint = self.endpoint()
        for grant in (False, 'true', 1):
            with self.assertRaisesRegex(native.NativeSourceError, 'AUTHORITY_REQUIRED'):
                endpoint.conditional_put('draft', '"opaque-one"', authority=grant)
        for version in ('*', 'W/"one"', '"one", "two"', 'one', '"one\n"'):
            with self.assertRaisesRegex(native.NativeSourceError, 'STRONG_NATIVE_CONDITION_REQUIRED'):
                endpoint.conditional_put('draft', version, authority=True)
        self.assertEqual(self.state['puts'], 0)

    def test_missing_weak_or_duplicate_response_etag_rejected(self):
        for tags in ([], ['W/"one"'], ['"one"', '"two"']):
            self.state['etags'] = tags
            with self.assertRaisesRegex(native.NativeSourceError, 'STRONG_NATIVE_CONDITION_REQUIRED'):
                self.endpoint().read_document()

    def test_declared_error_or_redirect_never_empty_or_followed(self):
        self.state['location'] = self.url + '/redirected'
        for status in (401, 403, 404, 302):
            self.state['status'] = status
            before = self.state['gets']
            with self.assertRaisesRegex(native.NativeSourceError, 'NATIVE_SOURCE_UNAVAILABLE'):
                native.read_for_purpose('review', endpoint=self.endpoint(headers={'Authorization': 'fake-only'}))
            self.assertEqual(self.state['gets'], before + 1)

    def test_representation_limits(self):
        for changes in (dict(type='application/json'), dict(type='text/plain; charset=latin1'),
                        dict(encoding='gzip'), dict(length=str(rv.MAX_BYTES + 1))):
            for key in ('type', 'encoding', 'length'):
                self.state.pop(key, None)
            self.state.update(changes)
            with self.assertRaises(native.NativeSourceError):
                self.endpoint().read_document()

    def test_invalid_utf8_response_and_oversized_write_rejected(self):
        self.state['body'] = b'\xff'
        with self.assertRaisesRegex(native.NativeSourceError, 'NATIVE_TRANSPORT_FAILED'):
            self.endpoint().read_document()
        with self.assertRaisesRegex(native.NativeSourceError, 'RESOURCE_LIMIT'):
            self.endpoint().conditional_put('界' * (rv.MAX_BYTES // 2), '"one"', authority=True)
        self.assertEqual(self.state['puts'], 0)

    def test_url_and_header_binding_refuses_unsafe_inputs(self):
        for url in ('http://example.com/a', 'https://user:secret@example.com/a',
                    'https://example.com/a?q=secret', 'https://example.com/a#b',
                    'https://example.com:bad/a', 'https://example.com:0/a', '\nhttps://example.com/a',
                    'https://example.com/a\tb', None):
            with self.assertRaises(native.NativeSourceError):
                self.endpoint(url=url)
        for headers in ({'If-Match': '*'}, {'Host': 'other'}, {'A': 'x\r\nY: z'},
                        {'X': 'one', 'x': 'two'}, {'Bad Key': 'v'}):
            with self.assertRaises(native.NativeSourceError):
                self.endpoint(headers=headers)
        self.assertEqual(self.state['gets'], 0)

    def test_invalid_budgets_rejected(self):
        for values in (dict(connect_timeout=True), dict(read_timeout='2'), dict(total_timeout=float('nan')),
                       dict(total_timeout=0.5), dict(connect_timeout=4)):
            with self.assertRaisesRegex(native.NativeSourceError, 'INVALID_QUERY_BUDGET'):
                self.endpoint(**values)

    def test_timeout_is_bounded_and_does_not_retry(self):
        self.state['delay'] = 2
        start = time.monotonic()
        with self.assertRaises(native.NativeSourceError):
            self.endpoint(read_timeout=0.2, total_timeout=2).read_document()
        self.assertLess(time.monotonic() - start, 3)
        self.assertLessEqual(self.state['gets'], 1)

    def test_worker_startup_does_not_consume_socket_connect_budget(self):
        with patch.object(native, '_worker', slow_start_worker):
            result = self.endpoint(connect_timeout=0.2, total_timeout=5).read_document()
        self.assertEqual(result['condition'], '"opaque-one"')
        self.assertEqual(self.state['gets'], 1)

    def test_worker_startup_still_obeys_total_deadline(self):
        started = time.monotonic()
        with patch.object(native, '_worker', slow_start_worker):
            with self.assertRaisesRegex(native.NativeSourceError, 'NATIVE_START_TIMEOUT'):
                self.endpoint(total_timeout=0.8).read_document()
        self.assertLess(time.monotonic() - started, 2)
        self.assertEqual(self.state['gets'], 0)

    def test_foreground_default_and_explicit_status_selection(self):
        endpoint = self.endpoint()
        self.record['Status'] = 'VERIFIED'
        self.record['Verification'] = 'Recorded only; not independent evidence.'
        self.state['body'] = rv.render([self.record]).encode()
        self.assertEqual(native.read_for_purpose('development', endpoint=endpoint)['status'], 'NOT_REQUESTED')
        self.assertEqual(self.state['gets'], 0)
        self.assertEqual(native.read_for_purpose('review', endpoint=endpoint)['records'], [])
        result = native.read_for_purpose('review', endpoint=endpoint, rv_ids=[self.record['rv_id']])
        self.assertEqual(result['records'], [self.record])
        self.assertFalse(result['application_authorized'])
        self.assertFalse(result['agent_consumed'])
        self.assertEqual(native.read_for_purpose('review')['status'], 'UNBOUND_EMPTY')
        with self.assertRaisesRegex(native.NativeSourceError, 'REVIEW_NOT_BOUND'):
            native.read_for_purpose('review', rv_ids=[self.record['rv_id']])


if __name__ == '__main__':
    unittest.main()
