"""Read human decisions and current permissions from configured native sources.

Endpoints are trusted host configuration. Neither credentials nor authority
endpoints are selected by an uploaded decision. The services must authenticate
the message author, retain the original message, and own their permission and
interpretation records. This adapter performs GETs only.
"""
import sys
sys.dont_write_bytecode = True
import decision_host as human
from decision_evidence import MAX_BYTES, canonical, decision_digest, line
from review_native import NativeDocument
from review_resume import _object


def require(condition, code):
    if not condition:
        raise human.HostFailure(code)


class NativeDecisionSession:
    """One host-bound feature/source with separate message and policy endpoints.

    A message endpoint serves human-message-v1 as UTF-8 text/plain with a strong
    ETag. A policy endpoint serves human-authorization-v1 the same way. Existing
    NativeDocument supplies HTTPS, no redirects, bounded reads and credentials.
    Host/service ACLs, not these schemas, establish trust in the two endpoints.
    """
    def __init__(self, *, feature, source_key, message, authorization):
        require(all(line(value) and len(value) <= 1024 for value in (feature, source_key)),
                'INVALID_HUMAN_BINDING')
        require(type(message) is NativeDocument and type(authorization) is NativeDocument,
                'INVALID_HUMAN_BINDING')
        require(message.feature == authorization.feature == feature
                and message.provider_key == authorization.provider_key
                and message.source_ref != authorization.source_ref
                and message.url != authorization.url, 'INVALID_HUMAN_BINDING')
        self.feature, self.source_key = feature, source_key
        self.message, self.authorization = message, authorization

    def _read(self, endpoint, schema):
        try:
            observed = endpoint.read_document()
            require(observed['source_ref'] == endpoint.source_ref
                    and observed['provider_key'] == endpoint.provider_key,
                    'HUMAN_SOURCE_MISMATCH')
            body = observed['body']
            require(isinstance(body, str) and len(body.encode('utf-8')) <= MAX_BYTES,
                    'RESOURCE_LIMIT')
            value = _object(body, schema)
            return value, observed['condition']
        except human.HostFailure:
            raise
        except Exception:
            raise human.HostFailure('HUMAN_SOURCE_UNAVAILABLE') from None

    def _message(self, source_ref):
        require(source_ref == self.message.source_ref, 'HUMAN_SOURCE_MISMATCH')
        value, version = self._read(self.message, 'human-message-v1')
        require(set(value) == {'schema', 'source_ref', 'actor', 'actor_kind', 'received_at',
                               'text', 'interpretations'}, 'INVALID_HUMAN_MESSAGE')
        require(value['source_ref'] == source_ref and value['actor_kind'] == 'human'
                and all(line(value[key]) for key in ('actor', 'received_at'))
                and isinstance(value['text'], str), 'INVALID_HUMAN_MESSAGE')
        require(type(value['interpretations']) is list and len(value['interpretations']) <= 1000,
                'INVALID_HUMAN_INTERPRETATION')
        seen = set()
        for item in value['interpretations']:
            require(type(item) is dict and set(item) == {'decision_digest', 'basis_ref'}
                    and all(line(item[key]) for key in item), 'INVALID_HUMAN_INTERPRETATION')
            require(item['decision_digest'] not in seen, 'INVALID_HUMAN_INTERPRETATION')
            seen.add(item['decision_digest'])
        reply = human.HumanReply(source_ref, value['actor'], 'human', value['received_at'],
            value['text'], 'platform-readback', version,
            self.message.provider_key + ':message:' + observed_ref(source_ref, version))
        return reply, value['interpretations']

    def read_reply(self, source_ref):
        return self._message(source_ref)[0]

    def interpret(self, reply, record):
        # Interpretation is read from the host's authenticated message service,
        # never inferred by this adapter or copied from the uploaded record.
        require(type(reply) is human.HumanReply, 'HUMAN_SOURCE_MISMATCH')
        current, interpretations = self._message(reply.source_ref)
        require(current == reply, 'HUMAN_SOURCE_CHANGED')
        digest = decision_digest(record)
        matching = [item for item in interpretations if item['decision_digest'] == digest]
        require(len(matching) == 1, 'HUMAN_INTERPRETATION_UNVERIFIED')
        return human.HumanInterpretation(digest, matching[0]['basis_ref'])

    def read_grant(self, request, record):
        # request is deliberately not used as a grant or a source locator.
        # The fresh server-side policy is independent of the evidence file.
        require(record.get('feature') == self.feature
                and record.get('target_ref', {}).get('source_key') == self.source_key,
                'HUMAN_AUTHORITY_UNVERIFIED')
        value, _ = self._read(self.authorization, 'human-authorization-v1')
        require(set(value) == {'schema', 'grants'} and type(value['grants']) is list
                and len(value['grants']) <= 1000, 'INVALID_HUMAN_POLICY')
        matching = []
        identities = set()
        for entry in value['grants']:
            require(type(entry) is dict and set(entry) == {'actor', 'feature', 'decision_kind',
                    'source_key', 'exact_scope', 'outcomes'}, 'INVALID_HUMAN_POLICY')
            require(all(line(entry[key]) for key in ('actor', 'feature', 'decision_kind', 'source_key'))
                    and entry['decision_kind'] in ('point', 'acceptance', 'scope-exception'),
                    'INVALID_HUMAN_POLICY')
            require(type(entry['exact_scope']) is list and 0 < len(entry['exact_scope']) <= 1000
                    and all(line(item) for item in entry['exact_scope'])
                    and len(set(entry['exact_scope'])) == len(entry['exact_scope']), 'INVALID_HUMAN_POLICY')
            outcomes = {'point': {'CONFIRMED', 'REJECTED', 'OUT-OF-SCOPE', 'INFEASIBLE', 'REOPENED'},
                        'acceptance': {'CONFIRMED', 'REJECTED', 'REWORK'},
                        'scope-exception': {'APPROVED', 'REJECTED'}}[entry['decision_kind']]
            require(type(entry['outcomes']) is list and len(entry['outcomes']) <= len(outcomes)
                    and all(type(item) is str and item in outcomes for item in entry['outcomes'])
                    and len(set(entry['outcomes'])) == len(entry['outcomes']), 'INVALID_HUMAN_POLICY')
            key = canonical({key: entry[key] for key in entry if key != 'outcomes'})
            require(key not in identities, 'INVALID_HUMAN_POLICY')
            identities.add(key)
            if (entry['actor'] == record.get('actor') and entry['feature'] == self.feature
                    and entry['decision_kind'] == record.get('decision_kind')
                    and entry['source_key'] == self.source_key
                    and set(entry['exact_scope']) == set(record.get('exact_scope', []))):
                matching.append(entry)
        require(len(matching) == 1, 'HUMAN_AUTHORITY_UNVERIFIED')
        entry = matching[0]
        return human.HumanGrant(entry['actor'], self.feature, entry['decision_kind'], self.source_key,
                                tuple(entry['exact_scope']), tuple(entry['outcomes']))

    def acceptance_reader(self, preparation, *, decision_document, candidate_repository, exact_scope):
        from state_acceptance import AcceptanceReader
        require(preparation.root.name == self.feature, 'HUMAN_SOURCE_MISMATCH')
        return AcceptanceReader(preparation, decision_document=decision_document,
            candidate_repository=candidate_repository, source_key=self.source_key,
            exact_scope=exact_scope, read_reply=self.read_reply, interpret=self.interpret,
            read_grant=self.read_grant)


def observed_ref(source_ref, version):
    # A bounded non-secret observation reference; the original remains remote.
    import hashlib
    return hashlib.sha256(canonical(dict(source_ref=source_ref, version=version))).hexdigest()
