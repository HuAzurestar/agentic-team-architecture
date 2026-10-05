"""One native-readback/real-Git flow; server identity is a labelled fixture."""
from contextlib import redirect_stdout
from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import decision_host as human
from decision_commit import CommitError
from decision_evidence import decision_digest
from decision_native import NativeDecisionSession
from decision_workflow import PointWorkflow, main
from review_native import NativeDocument
import test_decision_apply as fixture
from test_task_context import git


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        value = self.server.documents.get(self.path)
        if value is None:
            self.send_error(404)
            return
        raw = json.dumps(value).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('ETag', '"' + decision_digest_for_bytes(raw) + '"')
        self.end_headers()
        self.wfile.write(raw)


def decision_digest_for_bytes(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


class WorkflowIntegration(unittest.TestCase):
    def test_native_policy_revoke_apply_and_completed_cli_reentry(self):
        case = fixture.PointApplyTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        record = case.case.record
        grant = asdict(case.case.grant)
        grant['exact_scope'], grant['outcomes'] = list(grant['exact_scope']), list(grant['outcomes'])
        message = dict(schema='human-message-v1', source_ref=record['human_source_ref'],
            actor=record['actor'], actor_kind='human', received_at=record['received_at'],
            text=record['original_reply'], interpretations=[dict(decision_digest=decision_digest(record),
                                                               basis_ref='fixture:explicit-human-interpretation')])
        policy = dict(schema='human-authorization-v1', grants=[])
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.documents = {'/message': message, '/policy': policy}
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.shutdown)
        def endpoint(path, ref):
            return NativeDocument('fixture', ref, case.root.name, 'fixture:unused-review-ref',
                f'http://127.0.0.1:{server.server_port}{path}', allow_loopback_http=True)
        session = NativeDecisionSession(feature=case.root.name, source_key='pm:solution',
            message=endpoint('/message', record['human_source_ref']),
            authorization=endpoint('/policy', 'fixture:authorization'))
        operation = PointWorkflow(case.root, session=session)
        with self.assertRaisesRegex(human.HostFailure, 'HUMAN_AUTHORITY_UNVERIFIED'):
            operation.inspect(case.point, record)
        with self.assertRaisesRegex(CommitError, 'POINT_SOURCE_UNAVAILABLE'):
            operation.apply(case.point, record)
        self.assertEqual(git(case.pm, 'rev-parse', 'HEAD'), case.base)
        self.assertEqual(git(case.pm, 'for-each-ref', '--format=%(refname)', 'refs/lfd/'), '')
        policy['grants'] = [grant]
        self.assertTrue(operation.inspect(case.point, record)['applicable'])
        result = operation.apply(case.point, record)
        self.assertTrue(result['complete'])
        self.assertEqual(git(case.pm, 'rev-list', '--count', case.base + '..HEAD'), '2')
        self.assertEqual(git(case.pm, 'status', '--porcelain'), '')
        head = git(case.pm, 'rev-parse', 'HEAD')
        server.documents.clear()
        # Completed local recovery neither needs nor invents a new human reply.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'decision.json'
            path.write_text(json.dumps(record), encoding='utf-8')
            with redirect_stdout(io.StringIO()) as output:
                exit_code = main([str(case.root), case.point, '--decision', str(path), '--apply', '--format', 'json'],
                                 session=session)
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(output.getvalue()), result)
        self.assertEqual(git(case.pm, 'rev-parse', 'HEAD'), head)


if __name__ == '__main__':
    unittest.main(verbosity=2)
