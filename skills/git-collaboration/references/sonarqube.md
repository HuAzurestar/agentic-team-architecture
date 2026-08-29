# Optional SonarQube quality gate

Use SonarQube only when a maintained SonarQube Server/Cloud project, supported language analyzer, acceptable license/edition, runner connectivity, credentials, and a team-owned Quality Gate exist. It supplements—not replaces—compiler, tests, linters, sanitizers, dependency/security tools, Lean proof trust checks, or TeX builds.

Analyze after the build/tests needed to produce coverage and compilation data. Use full Git history where new-code/blame analysis requires it, keep tokens in the platform secret store, pin scanner integrations, exclude only generated/vendor/build outputs with justification, and never upload secrets. Monorepos may need separate Sonar projects/jobs according to the licensed feature set.

On GitHub, bind SonarQube through the supported GitHub App/integration when available, enable PR analysis/decoration, and optionally make `SonarQube Code Analysis` a required Ruleset/status check. Prefer native PR Quality Gate reporting; use explicit `sonar.qualitygate.wait=true` only where a synchronous blocking job is actually needed, especially before deployment.

Gitee is not in SonarQube's documented native DevOps binding list. Run the appropriate scanner in Gitee Go/external CI, pass PR parameters explicitly, and wait for the Quality Gate if the job must block. Native PR decoration must not be promised; a custom Gitee status/comment adapter is optional and must be separately secured and maintained.

Adopt in report-only mode first. Promote it to required only after the Quality Gate is tuned to new code, the baseline is understood, outage/timeout behavior is defined, and false positives are manageable. Do not use coverage percentage alone as a correctness target or let generated code distort the gate.
