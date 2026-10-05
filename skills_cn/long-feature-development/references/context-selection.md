# Context selection

`scripts/context.py` returns one purpose prompt plus common constraints. It is read-only: no state transition, configuration writer, cache, service connection or link fetching. `complete=true` means the selected material is complete, not that Git or a task has passed recovery.

Without background, give an existing project/feature directory and a purpose. The route is `DIRECT`; the existing `task_context.py` remains the execution validator. An explicitly supplied missing background file is an error, not a fallback to DIRECT.

For optional background or an existing README, specify the environment path and the common, route, evidence and purpose sections. Paths are JSON arrays of exact heading strings; a slash inside a title is literal. Example argument vector (Python notation avoids shell-dependent JSON quoting):

```python
argv = ["python", "scripts/context.py", "--task-ref", "/work/project/PIRC-31",
        "--purpose", "development", "--file", "/work/BACKGROUND.md",
        "--environment-section", '["Example environment"]',
        "--common-section", '["Common"]',
        "--route-section", '["Example environment", "Route"]',
        "--evidence-section", '["Example environment", "Evidence"]',
        "--purpose-section", '["Example environment", "development"]']
```

Use the host's structured argument API or its correct shell quoting. `--common-section` and `--section-path` are repeatable. Additional sections must belong to the selected environment. Choose leaf sections: selecting an environment parent would disclose other purposes and returns `NEEDS_SCOPE`. If the environment is omitted, only candidate heading paths are returned, never their bodies. Required paths are explicit so arbitrary README titles need no migration or keyword guessing.

ATX headings support up to three leading spaces, closing hashes, Unicode, BOM and LF/CRLF, with backtick/tilde fences excluded from the index. Only a single opening H1 is treated as the title. Duplicate paths, later H1, Setext and HTML blocks fail closed; use explicit manual reading for those formats. Selected text preserves original bytes after UTF-8 decoding, and includes half-open raw byte ranges and SHA-256 digests. No Markdown contents become commands or permissions.

The hard limits are 4 MiB per file, 100 selectors, 10,000 headings and 64 KiB for the successful UTF-8 JSON result. `--max-output-bytes` can lower the budget. Exceeding it returns `complete=false`, `NEEDS_SCOPE`, required bytes and a scope hint; no truncated prompt/body is presented as complete. The small failure diagnostic can exceed a deliberately tiny requested budget. Stdout is JSON and exit code 2 signals incomplete/invalid selection; argument syntax errors use argparse's normal stderr and exit code 2.

Each call reads current bytes without a persisted cache and rechecks those bytes after repository probes; a changed source returns `SOURCE_CHANGED`. `source_refs` identifies the exact prompt and background snapshots; `required_facts` points back to the explicit project entry and the necessary execution validator. Do not copy live branch/HEAD/task facts into background. Run the task validator and real Git checks before acting.

For explicit repository checks, repeat `--repo` with JSON `{ "name": "product", "path": "/work/product", "expected_remote": "https://host/owner/repo.git" }`. The path must be the actual Git root. Identity mismatch or unavailable Git makes the result incomplete. Raw remote URLs, credentials and Git stderr are not returned. This check is not write authorization, does not fetch, and does not prove a remote branch is current. Providers/configuration remain outside this helper; read [capability boundaries](capability-boundaries.md) before using those routes.
