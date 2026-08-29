# Python checks

Derive commands from `pyproject.toml`, lockfiles, and existing tooling. Do not introduce parallel formatters or dependency managers without a migration request.

Recommended baseline when no convention exists:

1. Syntax/bytecode compilation: `python -m compileall -q <source-directories>`.
2. Ruff lint: `ruff check .`
3. Ruff format check: `ruff format --check .`
4. Static typing when the project is typed: `mypy .` or the already-selected type checker.
5. Unit tests: `pytest`; add integration tests only where component boundaries warrant them.
6. Import or CLI smoke tests for shipped entry points, especially when unit tests do not import every production module.
7. For distributable packages, run `python -m build`, `twine check dist/*`, and install the built wheel into a clean environment for a smoke test.

Treat `python -m compileall` as a narrow syntax/bytecode check, not a replacement for imports, lint, or tests: many missing dependencies, bad names, and runtime paths appear only during import or execution. Run tests against declared supported Python versions; avoid an arbitrary oversized matrix. Use the repository's locked, reproducible install command. Check in lockfiles according to project type and tool policy, and review dependency changes explicitly.

Do not build an artifact merely because the repository contains Python. Applications may build a wheel, container, executable, or platform package when that artifact is actually deployed; scripts and internal tooling may need only checks and tests. Test the same artifact that will be published or deployed.

Keep tool configuration in `pyproject.toml` when supported. Align target Python versions across package metadata, Ruff, type checking, and CI. For libraries, test the lowest supported dependency bounds only if the project promises them.
