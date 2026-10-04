# Candidate request

- Evidence type: original
- Requirement/design version: replay/v1
- Environment: Python standard library; synthetic local data only
- Baseline: this standalone module is a newly proposed capability, not a patch to a live service

Review the proposed delivery validation, record import and result export module in candidate.py. The repository commit containing this packet is the candidate version; record that literal commit and the selected review scope in the report. Do not treat this small sample as a production acceptance run.

Normative requirements:

1. A delivery is usable only when qualified, closed and same_source are true AND its conditions include a nonempty upstream identifier and acceptance proof. Missing conditions are not a successful delivery. The declarations do not replace the evidence.
2. Records related by duplicate links represent the same cash event. Links may be directed, unordered or cyclic; count one amount per connected duplicate component. Samples in one component have equal amounts. Unrelated events must still count separately.
3. Import 100 records using the supplied source metadata as defaults. A normal user must not manually enter an internal source UUID for every row. The preview must support completing the batch, not just display a form.
4. Restricted row contents may be returned only to a viewer in row.allowed. This applies to package export, single export and single download. Public summary titles are intentionally public and do not require row access. No other fields are public.

The sample rows have source metadata already available as source_id. All amounts below are integer minor currency units. Tests and counterexamples may use invented data; no networks, real users, tokens or live databases are authorized. Reviewers may read the skill and this original directory and run in-memory Python experiments. Write reports only to an isolated temporary directory.

Select mode and topics from the supplied review/v1 configuration, otherwise use the skill defaults. Follow the skill's shared finding/status/score format. Scope exclusions constrain what is reviewed, not the requirements themselves. Preserve unknowns and limitations instead of assuming a successful review from an empty report.
