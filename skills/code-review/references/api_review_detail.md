# Weak review: API

Scan public and internal contracts and all applicable consumers. Each point can reveal several independent defects.

## Content points

- Do names communicate behavior, inputs, outputs and side effects without reading implementation?
- Are booleans, optional/null/default values and parameter combinations unambiguous?
- Does an endpoint or function combine unrelated actions or expose storage structure unnecessarily?
- Are methods, response envelopes, errors, pagination, filtering and ordering consistent with existing conventions?
- Are users required to provide internal IDs that the system can resolve or select?
- Are duplicate APIs or one-consumer special interfaces adding unnecessary complexity?
- Have existing API meanings, defaults, exceptions, ordering, null behavior or compatibility changed?
- Do direct and indirect consumers handle the new contract, including serialization and empty/error results?
- Do alternate endpoints bypass validation, permissions, transaction boundaries or filtering?

## Scan and challenge

Trace route/schema → service → serializers → clients/tests; search export, download, serialize and equivalent routes. Try malformed, omitted, contradictory and stale inputs. Invoke an old consumer shape and verify expected output/errors. Inspect batch and single-object siblings together. Cite a concrete contract mismatch rather than a preferred naming style.
