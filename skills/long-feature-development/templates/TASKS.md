# <feature> Tasks

Task state and refs belong in `STATUS.md`. This local file explains the work by task ID.

## REQ — Confirm requirement

- Goal: Turn the human-approved proposal into the confirmed requirement boundary.
- Inputs: `REQUIREMENT.md`
- Work: Resolve open requirement questions and record explicit human confirmation.
- Completion condition: `REQUIREMENT.md` is `CONFIRMED`, with confirmer and time recorded.
- Gists: none

## SOL — Baseline solution

- Goal: Establish the retained implementation plan for the confirmed requirement.
- Inputs: `REQUIREMENT.md`, `SOLUTION.md`
- Work: Resolve solution gaps and record explicit human baseline approval.
- Completion condition: `SOLUTION.md` is `BASELINED`, with baseliner and time recorded.
- Gists: none

## <task-id> — <task-title>

- Goal:
- Inputs:
- Work:
- Completion condition:
- Gists: none

Copy the final section for each additional task, then replace or remove every angle-bracket placeholder. List gists as comma-separated feature-relative paths under `gists/`, for example `gists/api-contract.md, gists/db-notes.md`.
