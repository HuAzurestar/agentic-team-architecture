# Weak review: UI

Review information design and actual task execution together. Source code alone cannot establish usability.

## Information points

- Is enough information visible to decide and act, without excessive prose, scrolling, unused space or crowded controls?
- Are key fields and the main action easy to find, with appropriate list density and no required horizontal hunt?
- Are labels and states expressed in user terms rather than UUIDs, internal enums, abbreviations or technical mechanisms?
- Do button labels identify the action? Are unlabeled icons, ellipses, plus/cross/arrows and colors unambiguous?
- Is status conveyed beyond color alone, and are interaction/focus/error affordances usable with the project's supported inputs?
- Are actions near their object and secondary controls kept from obscuring the main task?

## Operation points

- Write the steps from entry to completion of the core task and count repeated operations.
- Can a 100-record task be performed in batches rather than item-by-item selection or internal-ID typing?
- Are derivable values automatic, defaults useful and confirmation steps justified?
- Do search/filter/sort support the task without requiring memory from another page?
- Are loading, progress, success, partial success and failure feedback meaningful?
- Can users recover in place, retain input/navigation state and avoid duplicate submissions?
- Has the delivered UI covered the explicitly agreed acceptance scope, not merely provided buttons?

## Scan and challenge

Operate the default, bulk and failure/recovery flows at realistic list sizes. Capture the actual action sequence and interface evidence. Try double click, interrupted work, back navigation and an item-level failure inside a batch. Trace UI → API → resulting state to expose apparent batch operations that still issue unsafe single-item work. If runtime access is unavailable, mark the usability conclusions unknown rather than inventing observations.
