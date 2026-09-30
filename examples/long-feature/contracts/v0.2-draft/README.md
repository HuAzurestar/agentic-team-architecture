# PIRC-31 shared contract bundle (draft)

The versioned package contains C1, C2, and C3 specifications, a SHA-256 manifest, and 23 illustrative event sequences. `contract-fixtures/0.1` is the package format; each C contract has its own `*/0.1` version. The word `draft` in the directory name describes delivery status, not permission to silently reinterpret a version.

From the repository root, run:

```text
python scripts/check_long_feature_contracts.py --bundle examples/long-feature/contracts/v0.2-draft --format json
```

Exit 0 means the declared static positive and negative cases match their expected results. Exit 2 means invalid input, resource limit, or broken hash/path; exit 3 means a case or package semantic mismatch; exit 4 means an unsupported required version or feature. The output includes `valid`, `checked_cases`, `failures` with case/field/expected/observed, and `unsupported_versions`. It does not print full document content or secrets. The checker does not contact a service, mutate files, or perform real Git validation.

The manifest lists the three specs and all case files with relative paths and hashes. Rebuild only after a reviewed spec or case change with `python scripts/build_long_feature_fixtures.py --bundle examples/long-feature/contracts/v0.2-draft`, review the diff, then commit the entire package together. A consumer records `https://github.com/HuAzurestar/agentic-team-architecture.git@<full commit SHA>` for the accepted package; the package cannot contain a hash of its own commit.

Consumers: PIRC-31 F02/F03/F04 and PIRC-33 F07/F08/F09/F11/F13, plus PIRC-34 F15. Each consumer records its exact package repo/SHA, supported contract versions, affected interface, and test result. Unknown optional `display` fields may be ignored; an unknown `required_features` item or an unsupported format/contract version is a rejection. No silent 0.x compatibility is assumed. A changed spec or fixture requires a new package review and consumer retest.

This package is a static handoff. It does not show that any consumer accepted it, that F07/F08 writes are safe under concurrent processes, or that F03's original `task_context.py` and Git probe passed. Those checks have their own implementation and test tasks.
