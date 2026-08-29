# TeX and LaTeX checks

Discover the root document, engine, bibliography backend, glossary/index steps, and existing build recipe before choosing commands. Prefer a checked-in `latexmkrc`, `Makefile`, or project task over a hard-coded one-pass compiler command.

Baseline gates when compatible with the document:

1. Style/static checks: `chktex` with a project configuration and documented suppressions.
2. Reproducible build: `latexmk -interaction=nonstopmode -halt-on-error -file-line-error <root.tex>` using the required engine (`-pdf`, `-lualatex`, or `-xelatex`).
3. Inspect the log for undefined references and citations plus rerun behavior; a zero process exit alone may not establish a clean document.
4. Preserve the successfully compiled PDF as a downloadable CI artifact. Use an explicit short retention period for branch/PR previews and identify the source commit in the artifact name or accompanying metadata.

Use `lacheck` only if already selected; it overlaps with and is generally less configurable than ChkTeX. Use `tectonic` only when the project has chosen its bundle/reproducibility model and its package coverage is adequate.

Do not commit auxiliary build files. Commit generated PDFs only when they are intentionally tracked by repository policy. A TeX project CI is incomplete if it only reports that compilation succeeded but makes no PDF available for inspection: upload the PDF artifact after every successful document build. Releases attach an immutable PDF built from a tag. Pin the TeX distribution or container image sufficiently to keep builds reproducible, while retaining a planned update path.

## PDF delivery and versioning

- On every PR and relevant branch build, build the PDF and upload a short-retention preview artifact. Name it with the document/language, workflow run, and commit SHA; it is not a release. Retention may be brief because the file is reproducible from the commit.
- On a protected version tag such as `v1.2.0` or a paper-specific scheme such as `paper-v1.2.0`, build once, package the PDF with any required source/bibliography/license files, generate checksums, and attach the immutable archive and PDF to the forge release.
- Derive the displayed document version from an explicit source file or injected tag metadata. Do not silently rewrite tracked TeX sources during CI.
- If the repository publishes a continuously updated latest PDF, deploy it separately (for example to Pages) and label it with the source commit. Keep versioned releases immutable so a cited version remains recoverable.
- Retain CI artifacts only as operational previews; use release assets or archival repositories for long-term scholarly versions. For formal publication, record DOI/journal/arXiv identifiers in metadata rather than treating a Git tag as their replacement.

For multilingual papers, discover every supported root document or locale. Build and check each language independently, name artifacts unambiguously (for example `paper-zh-<sha>.pdf` and `paper-en-<sha>.pdf`), then package all required language editions together in the same versioned release. Add a cross-language consistency check when titles, version strings, theorem numbering, bibliography data, or generated tables are expected to stay synchronized.
