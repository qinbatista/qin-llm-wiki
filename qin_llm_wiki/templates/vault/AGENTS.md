# {{WIKI_NAME}} memory contract

Read relevant memory at the start of every task that uses Skills. If no vault, project, or matching memory exists, continue without it; never substitute another project. Use the user-selected model and effort for Skill-guided work and memory summarization. The main task owns verification; Ending only saves useful memory.

## Read

1. Resolve one exact project from the workspace or user request. Current source and current project Knowledge outrank old events; session keys are provenance, not retrieval barriers.
2. When the project's `Memory.json` exists, use the installed `project-memory-skill/scripts/project_knowledge.py recall --project-root ROOT --vault VAULT` with the relevant module/file/symbol filters. It checks exact root identity and source freshness; never fall back to the readable page on a mismatch, stale result, or missing current entry. For projects without a structured index, `AI Memory/ai_memory.py recall --project ProjectName --module feature.module --query "task terms"` returns up to two project-prose sections labeled unverified. Read the returned sources and briefly identify their useful effect, or state no related match.
3. Read a relevant global preference or reusable lesson only if it affects this task. Project-specific preferences remain in their owning project. Read only required Skill references. Do not preload dashboards, full event stores, routing history, or unrelated projects.

Use Python 3 with `-B`: `python3` on macOS/Linux, `py -3` on Windows. Unscoped `search` is rejected; `--all-projects` is for an explicitly requested memory audit.

Ordinary recall does not read event history. Use scoped `search` or explicit `recall --include-history` only for a provenance or past-outcome question; returned events are historical evidence, never current authority. A retrieval or coverage record proves neither useful comprehension nor earlier memory use. Codex's automatically injected summaries can contain multiple projects; keep automatic memory use/generation disabled when this vault is the memory owner. Previously injected context must be checked against the selected project and current source.

Run commands and tests in the background without opening terminals, browsers, or apps unless the user asks to see them. Prefer portable Python, preserve needed platform branches, and pass `AI Memory/hidden_process.py` options to every child process; capture output and errors. GUI tools also need their own headless mode.

## Remember

Save useful project continuity: prior problems and user struggles/corrections, attempted solutions, last verified state and date, actual results and evidence, unresolved items and next steps, alongside ownership, interfaces, preferences, organization and decisions. Structured project knowledge belongs in `Projects/<Project>/Memory.json`; `Knowledge.md` is its readable view. Keep intentional shared preferences under their explicit shared owner. Never promote a project-specific rule into a global preference without evidence that the user intended it globally.

At a known outcome, including a failure or pause, review the affected current entries for durable changes: user corrections, recurring failures, contracts or ownership changes, established results, blockers and next steps. Save applicable facts through the supported current-knowledge writer so the index, readable view and canonical history agree. Preserve omitted context; explicitly reconcile resolved or superseded facts. Unknown causes and untested outcomes stay unknown. Trivial work and identical replays add no memory.

Ending uses the user's selected model and effort to consolidate these facts. Check exact-project maintenance even when no new durable fact exists. A nonempty current project needs synthesis when its summary is missing or invalidated, or after 20 distinct writes or 30 days. Complete due synthesis in that same Ending and read back the result; an unavailable vault or unfinished synthesis remains pending. Use only eligible current facts, retain verification dates and limits, and link unresolved work without promoting stale or retired claims. This runs on task closeout, including later no-change closeouts; it is not an unattended background service. Ending does not test, launch projects, repair code or create task chains. Verification evidence comes from the original task.

Use `project-memory-skill/scripts/ending_memory.py` for structured current entries and their canonical history. `AI Memory/ai_memory.py record` records a distinct historical outcome; it alone does not update `Memory.json`. Group related modules. Reuse a stable issue ID for repeated Bugs; new attempts append linked revisions and issue views select the latest state. A passing check requires explicit issue resolution. Use `amend` for missing details in the same observation, not a changed outcome. `capture-memory` accepts durable global preferences and is a no-op for an empty candidate list. Current owner pages summarize current truth; `AI Memory/events.jsonl` is the only chronology. Historical routing records never override the user's selected model for Skill-guided work or memory.

After changed memory, render the generated views and check only the affected links and stored readback. Full `memory_lint.py` belongs to memory maintenance, not every product task. `auto_classify.py` may organize evidence into reusable lessons; it must not turn project details into global instructions.

## Keep safe and compact

- Preserve unrelated notes and useful history. Replace redundant current rules instead of appending contradictory instructions or duplicate log layers.
- Never hand-edit `events.jsonl` or generated root views. Use guarded `remove-invalid`, `redact-private`, or `migrate-provenance` for exact legacy repairs.
- Store project-relative files and sanitized facts, never credentials, raw prompts, reasoning, machine paths, or unrelated transcripts. Tests use disposable stores under project `Cache/temp-<task>/`.
- The generator updates managed contracts and runtimes. User Projects, Knowledge, Preferences, Skills, and event history remain user-owned.

## Navigation

- [[Projects/index|Projects]] — project-specific current truth.
- [[Preferences/index|Preferences]] — intentional global taste and working preferences.
- [[Knowledge/index|Knowledge]] — reusable concepts; [[Knowledge/Reusable Lessons/index|lessons]] and [[Knowledge/Book References/index|optional references]].
- [[Knowledge/Memory Retrieval|Memory Retrieval]] — exact-project people, roles, bilingual technical queries, and retrieval evidence.
- [[Skills/index|Skills]] — concise capability and preference summaries.
- [[Recent Work]], [[Issues]], [[Memory Dashboard]] — generated views for browsing only.
