# Beacon: recover each target separately

This is a walkthrough for the fictional Beacon Git first plan. It is not a log of an actual push or platform write. Before any side effect, record target identities and expected source refs in the task's declared gist. Keep the original content and authorization boundary.

| Operation | Target identity | Expected condition | Observed result | Receipt/ref | Next check |
| --- | --- | --- | --- | --- | --- |
| Save text | `beacon-api.git:project/BEACON-PLAN.md` | Observed source file hash `h0` | success | Read back hash `h1` | Inspect intended diff; do not save the same replacement again. |
| Commit | `beacon-api.git` on authorized work branch | Parent was the recorded start SHA; only the plan file is staged | success | Candidate full commit `c1` from `git rev-parse HEAD` | Inspect commit path list and record `repo@c1`; do not make a duplicate commit. |
| Push | Exact configured remote and target ref | Remote identity and observed target SHA `r0` | unknown: response lost | none | Query that exact remote ref; check whether `c1` is reachable. Do not infer failure from the lost response. |
| Publish provider copy | `beacon-docs:beacon:plan` | Observed object ID and native condition `r17` | failure, or unknown if the response was lost | Error/request ID if returned | Query the same object ID and native revision; if no stable identity is queryable, stop automatic recovery. |

`h0`, `h1`, `c1`, and `r0` are placeholders for recorded hashes or full SHAs; replace them with observations in a real gist. The table must never be used as an executable command with these placeholders.

## Decision after the interruption

1. Reopen the exact task and compare the saved document and candidate commit with its declared source. If the commit succeeded, retain `repo@c1` and its file list. A missing bookkeeping SHA is repaired from Git history, not by a second commit.
2. Query the exact remote and target ref. If `c1` is reachable there, mark that target published with the observed remote SHA. If the remote has advanced in an incompatible way, report conflict and retain the local candidate. If the query fails, leave push `unknown`; do not push automatically.
3. Query `beacon:plan` using the previously recorded object identity and revision. If the provider accepted the content, record the observed object state while leaving causal attribution unknown without a receipt. If it did not, a new write needs current native conditions and the original authorization. If the query itself fails, keep the target `unknown`.
4. Report the four results independently. Neither a successful save nor a successful commit means push or provider publication succeeded. Do not roll back the successful source to hide a failed replica.

If saving succeeded but commit did not start, inspect the diff and checkpoint only intended files. If a provider create returned `unknown`, query the recorded object or association ID before any retry; without a queryable ID, stop rather than create a possible duplicate. Resume only the targets whose state and preconditions are known. A later operator change to the source or provider condition requires a fresh comparison and decision.
