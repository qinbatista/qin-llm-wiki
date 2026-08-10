# Project Learning

## One outcome, one event

Record one durable result in `AI Memory/events.jsonl`. Group changes by project and functional module, retain reason and verification, and list only project-relative touched files.

## Repeated Bugs

Use one stable issue ID. Lifecycle status is `ACTIVE`, `MONITORING`, `RESOLVED`, or `ARCHIVED`; repeated attempts update the same row and increment `attempt_count`. Archive only when current architecture proves that the old owner, path, contract, or consumer is unreachable.

## Current truth

Promote reusable current rules to Projects, Knowledge, Preferences, or Skills. Generated `Recent Work.md`, `Issues.md`, and `Memory Dashboard.md` summarize the event store and must not be edited manually.

Project-result session, task, and group fields are provenance rather than recall barriers. Search matching results across sessions. Run `AI Memory/auto_classify.py sync` after a verified outcome so uncertain patterns stay in the candidate queue and only high-confidence evidence becomes a reusable lesson.
