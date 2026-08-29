# Bash and POSIX shell checks

Discover each script's declared interpreter from its shebang and repository policy. Do not run Bash-specific code under `sh`, or silently rewrite POSIX scripts as Bash. Include executable scripts without `.sh` extensions in discovery while excluding vendored/generated files.

Baseline gates:

1. parse each script with its declared shell (`bash -n`, `dash -n`, and so on) and/or the selected static parser;
2. run ShellCheck with the correct dialect and a checked-in, narrowly justified exclusion policy;
3. check formatting with pinned `shfmt -d` using `.editorconfig` or documented flags;
4. run unit/integration tests with Bats or the existing harness, isolating filesystem/environment side effects;
5. smoke-test public CLI help, invalid inputs, exit codes, stdout/stderr separation, quoting, whitespace/path edge cases, and cleanup/trap behavior;
6. where promised, run on every supported shell and operating system rather than assuming Bash/Linux.

Never print secrets or use `set -x` around credentials. Treat download-and-execute patterns, unchecked variables, unsafe temporary files, missing `set -e` assumptions, pipelines, globbing, and destructive paths as review risks; do not impose `set -euo pipefail` mechanically when it changes intended semantics.

Shell scripts normally have no compilation CD. If shipped as part of an archive, installer, container, or release bundle, package and test that exact artifact, preserve executable modes, generate checksums/signatures as required, and test installation/uninstallation in an isolated environment.
