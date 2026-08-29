# Lean checks

Treat `lakefile.lean` or `lakefile.toml`, `lean-toolchain`, and `lake-manifest.json` as the source of truth. Use the pinned Lean toolchain and committed manifest for reproducibility.

Baseline gates:

1. Fetch dependencies with the project's Lake workflow (`lake update` only when intentionally changing the manifest; otherwise prefer `lake exe cache get` when Mathlib caching is configured).
2. Build all declared targets: `lake build`.
3. Fail on incomplete proofs. Use a project-level check that rejects declarations depending on `sorryAx`; treating Lean's sorry warning as an error is acceptable only when the warning policy is controlled and clean. Text-searching for `sorry` is merely a supplementary fast check because it can miss aliases/macros and match comments or examples.
4. Audit the public or claimed main theorems with `#print axioms <name>` (or an equivalent environment-based audit). Reject `sorryAx` and undeclared project axioms. Define the allowed axiom set explicitly; for ordinary Mathlib proofs it is commonly a subset of `propext`, `Classical.choice`, and `Quot.sound`, but projects using trusted computation or domain axioms need a reviewed, documented policy.
5. Ensure the modules containing claimed theorems are imported by a built target. A valid theorem in an unbuilt file is not a verified project result.
6. Run `lake test` only when the project defines an effective test driver.
7. Run project-declared linters, executables, or `#lint` aggregation targets when present.

Lean elaboration during `lake build` is the primary syntax and type-correctness gate. Do not add an imaginary standalone syntax checker. Warnings should be addressed or intentionally configured; avoid globally turning all warnings into failures until the existing codebase is clean.

Passing these gates establishes that Lean accepted the compiled declarations under the audited trust assumptions; it does not establish that a theorem statement faithfully formalizes the informal mathematical claim. Require human review of important statement definitions, quantifiers, hypotheses, imported axioms, and the mapping from the paper/specification to Lean names.

## Optional agent-assisted review

When the Git platform and budget support it, an agent may search for existing lemmas, attempt independent proof reconstruction, identify suspiciously weak statements, review changed axioms/imports, or comment on proof maintainability. Keep this advisory by default: agent success is not proof, agent failure is not disproof, and nondeterministic agent output should not replace kernel checks or become a required status check unless the team has measured and accepted its reliability, cost, permissions, and data exposure.

Cache `.lake` or Mathlib artifacts only with keys that include OS, `lean-toolchain`, and `lake-manifest.json`. Never regenerate or update the dependency manifest as a side effect of an ordinary CI validation job.
