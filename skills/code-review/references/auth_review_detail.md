# Weak review: authorization and disclosure

Authorization of one entry point does not establish protection of all data exits.

## Content points

- Are actor, resource, scope, inherited permissions and intended data-use restrictions resolved before disclosure or side effects?
- Can a single result, full package, preview, download, import/export, cache, API, CLI or background task bypass the same policy?
- Can object IDs or ownership changes expose another user's data or let an attacker choose a privileged context?
- Do serializers, partial results, metadata, errors and logs disclose fields that normal access would hide?
- Are tokens, passwords and private payloads excluded from outputs and persisted diagnostics?
- Are policy checks repeated at the correct boundary when data or permissions change after preview/validation?
- Do restore/retry and service identities preserve the user's actual authority instead of silently widening it?
- Are external paths, URLs, uploaded files and untrusted values validated at the appropriate trust boundary?

## Scan and challenge

Search authorize/permission/access plus export/download/serialize/cache and equivalent business terms. Trace all exits from restricted data, including sibling serializers. Use a permitted restricted test identity and assert denial before reading/disclosing protected data. Test a guessed foreign ID, inherited restriction, stale permission and alternative output. No successful full-package check may stand in for single-result protection.
