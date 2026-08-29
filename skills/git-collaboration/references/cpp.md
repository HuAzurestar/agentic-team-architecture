# C and C++ checks

Discover the declared language standard, compiler support matrix, build system, dependency manager, presets/toolchain files, test framework, and produced libraries/binaries. Use the repository's canonical build commands; do not replace CMake, Meson, Bazel, Make, Conan, or vcpkg merely to standardize CI.

Baseline gates when no stronger convention exists:

1. format check with the pinned `clang-format` version and checked-in `.clang-format`;
2. configure and compile with warnings enabled; treat warnings as errors only after the supported compiler/platform baseline is clean;
3. run `clang-tidy` or the selected static analyzer against an accurate compilation database;
4. run unit tests and fail if zero tests were discovered (for CMake, use CTest with `--no-tests=error` where supported);
5. run integration/CLI tests against the actual built library or executable;
6. maintain at least one sanitizer configuration on a supported platform—typically AddressSanitizer plus UndefinedBehaviorSanitizer; add ThreadSanitizer for concurrent code when feasible;
7. build install/package targets and test consuming the installed artifact when the project distributes a library or application.

Use `CMakePresets.json` and matching test/package presets when the project chooses CMake presets; do not commit user-local `CMakeUserPresets.json`. A practical CI matrix covers only supported compiler/OS/standard combinations: one fast canonical job can run format/static analysis, while build/tests exercise the promised matrix. Sanitizer binaries are test artifacts, not production releases.

CD is deliverable-driven. Tag releases build, test, strip/sign when required, checksum, and publish each supported binary/library/archive. Record compiler, standard library, ABI, target architecture, runtime dependencies, source tag/SHA, and build options. Do not label a single Linux build as a portable C/C++ release.
