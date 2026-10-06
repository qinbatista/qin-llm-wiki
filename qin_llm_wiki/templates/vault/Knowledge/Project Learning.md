# Project Learning

Read only the exact project's relevant current entries through `project-memory-skill/scripts/project_knowledge.py recall --project-root ROOT --vault VAULT` when a structured index exists. Otherwise `ai_memory.py recall --project ProjectName` returns bounded prose labeled unverified. History requires scoped `search` or explicit `--include-history`; it never overrides current authority. Missing or conflicting memory is a normal skip. Never fill a gap with another project's memory.

Keep current code structure, interfaces, preferences, document organization, durable decisions, and last verified project state in one current owner. Save the problem and user impact/correction, the attempted solution, observed result, evidence and date, unresolved items and next step when established by the task. Use the existing reason, result, decisions, verification and risks fields. Do not infer whole-project completion from a passing check or unchanged source. Session/task keys are provenance, not retrieval barriers. Source and current Knowledge outrank historical events.

The main task verifies changed behavior with the smallest useful check. Simple value edits may skip testing; avoid full builds or startup unless requested or necessary for the stated acceptance. Ending uses the user's selected model and effort to save useful memory and complete due synthesis. It creates no verification or repair loop. A no-change closeout still checks maintenance; if neither facts nor synthesis need updating, write nothing.

## Capture and refresh

| Established information | Existing field |
| --- | --- |
| Current contract or state and its scope | `summary`, module/file/symbol |
| Problem, cause when known, and user impact or correction | `reason`, `decisions` |
| Attempted fix and actual observed outcome | `decisions`, `result` |
| Last verified date, evidence and limits | `verification`, `verification_status` |
| Unresolved work, blocker and next useful step | `risks` |
| Ownership and dependencies | `relations` with explicit source owner |

Review affected entries after meaningful work, including a known failure or pause: preserve the established blocker, failed or partial result and next step. Merge sparse updates with existing facts; clear or replace context explicitly when it is resolved or superseded. Preserve failed attempts and prior proof in canonical history. Source changes, contradictory evidence, user corrections, ownership changes and removals trigger a scoped review; never refresh an old claim merely by hashing newer source. Capture per-entry source hashes for the minimal exact files and dependencies supporting that claim; use a shared outcome snapshot only when every entry depends on those files.

Keep a concise synthesis in the existing project index. It is due when a nonempty current project has no valid synthesis, and after 20 distinct writes or 30 days. Check before and after saving, complete it in the same Ending, and read back that maintenance is no longer due. Include architecture, important decisions, dated established state, remaining uncertainty and next steps; exclude stale or retired claims and label incomplete evidence. Summarization runs on task closeout, not while Codex is idle. No second status store, per-task note or automation chain is needed.

Use one event per distinct outcome and one stable issue ID for a repeated Bug. New attempts append linked revisions, preserving earlier struggles, causes and failed fixes; identical replays do not add history. Preserve actual verification status separately from issue state: `ACTIVE`, `MONITORING`, `RESOLVED`, and `ARCHIVED`. A passing check does not close an issue without explicit resolution. Generated issue views show its latest revision; scoped historical lookup can retrieve prior attempts. Use `amend` for missing details in the same observation and `record` for changed outcomes, then render generated views. Promote only evidence-backed general lessons; keep project-specific decisions with their project.
