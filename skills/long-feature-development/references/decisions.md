# Detailed design and decisions

Read when preserving intent, doing detailed design or relating INT/REQ/SOL. Use [protocol.md](protocol.md) when creating or changing their YAML/preview format.

First preserve external intent as an INT point: original wording, source and an optional intent type when supplied. Its title briefly summarizes the concrete intent; decided by retains the original proposer's supplied identity, whether person, agent, platform or combination, without a fixed format or substitution of the recorder. An expressed, retained intent is already RECORDED, not awaiting approval; unknown source time/reason may stay null. Review, test and refactor requests are also INT; the interpretation is not automatically a new product requirement. Converting intent into core REQ and appropriate SOL belongs to detailed design, with versioned inputs tracing the relationship.

All three types are indexed in DESIGN and read in design/<id>.md, not separate REQUIREMENT.md/SOLUTION.md/INTENT.md state stores. The assigned agent authors concrete content using the INT/REQ/SOL templates; scripts do not compose new solutions or judgments. INT classification and initial opinion are optional external intake capabilities: intent type and initial opinion fields/sections may be omitted, not required generic steps. Interpret common fields by type: INT records provenance while REQ/SOL record approval decisions, as specified in [protocol.md](protocol.md). Specialized relations are summarized in detail spec.

A comment, recommendation and authorized decision are different facts. A DECISION task records its target revision, actual decider, conclusion, authority, mode and explanatory comment. Delegated mode also records on behalf of. For approval-bearing points such as REQ/SOL, mirror the relevant result into decided by, decided at and decided with, and then the index row. Do not replace an INT originator with a later reviewer or decider.

An authorized agent may decide within its external mandate without mandatory human reconfirmation. An applicable AGENTS.md role mandate may provide conditional REQ/SOL confirmation authority; use the mandate and mandatory-reason rules in [confirmation.md](confirmation.md). The host determines scope and effective authority. Confidence, difficulty assessment or learning does not create authority. Learning and approval-policy changes remain external capabilities.

For partial decisions, decided-point changes and reopening, read [confirmation.md](confirmation.md); it owns revision and prior-decision handling. For a user-facing acceptance brief and response, read [acceptance.md](acceptance.md). Neither operation relies on disposable attachments.

Quality findings produced by TEST/REVIEW belong in FEEDBACK records, rather than automatically creating INT. User requests to test/review are still external intent. See [task contracts](task-contracts.md) for handling and the distinction between developer testing and independent TEST.
