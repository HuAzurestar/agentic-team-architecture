# Java checks

Discover the supported JDKs, Maven/Gradle wrapper, multi-module structure, framework, style/static-analysis plugins, integration-test lifecycle, packaging, and deployment target. Use the committed `mvnw`/`gradlew` wrapper when present and verify wrapper integrity according to project policy; do not substitute a runner's arbitrary Maven/Gradle version.

Baseline gates:

1. compile with the project's configured release/source/target level;
2. run formatting/style gates already selected (for example Spotless or Checkstyle) and static analysis such as SpotBugs/Error Prone when configured;
3. run unit tests and preserve standard test reports;
4. run integration tests in the build tool's intended lifecycle (`verify` or the declared Gradle task), provisioning real service dependencies only when needed;
5. package JAR/WAR/distribution and run a smoke test against that artifact, not only IDE/test classpaths;
6. scan dependencies/SBOM when the project risk and release policy require it.

For Maven, prefer the wrapper and a lifecycle ending in `verify` when integration and verification plugins are bound. For Gradle, use the wrapper and the project's `check`/`build` tasks rather than guessing individual tasks. Test the declared supported JDK matrix; run expensive analysis once on a canonical JDK unless compatibility requires otherwise.

CD publishes only real deliverables: Maven-compatible packages, signed archives, containers, or service bundles. Use trusted short-lived publishing credentials where supported, keep snapshot and release repositories separate, verify version/tag agreement, and promote the same tested artifact. Do not deploy directly from a PR build.
