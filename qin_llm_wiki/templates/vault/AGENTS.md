# {{WIKI_NAME}} memory contract

Read relevant memory at the start of every task that uses Skills. If no vault, project, or matching memory exists, continue without it; never substitute another project. Use the user-selected model and effort for Skill-guided work and memory summarization. The main task owns verification; Ending only saves useful memory.

## Read

1. Resolve one exact project from the workspace or user request. Current source and current project Knowledge outrank old events; session keys are provenance, not retrieval barriers.
2. Run `AI Memory/ai_memory.py recall --project ProjectName --module feature.module --query "task terms"`. It returns up to two relevant Knowledge sections and five compact events from that project, ranked by query relevance with the module as a hint. Read the returned sources; in the active task, briefly identify the useful memory and its effect, or explicitly state no related match. A retrieval result or coverage record alone does not prove that memory was useful or that previous tasks read it. Missing memory is a read-only skip.
3. Read a relevant global preference or reusable lesson only if it affects this task. Project-specific preferences remain in their owning project. Read only required Skill references. Do not preload dashboards, full event stores, routing history, or unrelated projects.

Use Python 3 with `-B`: `python3` on macOS/Linux, `py -3` on Windows. Unscoped `search` is rejected; `--all-projects` is for an explicitly requested memory audit.

Run commands and tests in the background without opening terminals, browsers, or apps unless the user asks to see them. Prefer portable Python, preserve needed platform branches, and pass `AI Memory/hidden_process.py` options to every child process; capture output and errors. GUI tools also need their own headless mode.

## Remember

Save only durable changes: code ownership and interfaces, design preferences, document organization, decisions, and useful regressions. Keep one concise current owner under `Projects/<Project>/Knowledge.md`, `Preferences/`, `Knowledge/`, or `Skills/`. Never promote a project-specific rule into a global preference without evidence that the user intended it globally.

Ending uses the user's selected model and effort to summarize these facts. It does not test, compile, launch projects, reroute work, or create Repair tasks. If nothing durable changed, write nothing. Verification evidence comes from the original task and retains its actual limits.

Use `AI Memory/ai_memory.py record` for one outcome, grouping related modules. Reuse a stable issue ID for repeated Bugs; use `amend` for missing details. `capture-memory` accepts durable global preferences and is a no-op for an empty candidate list. Current owner pages summarize current truth; `AI Memory/events.jsonl` is the only chronology. Historical routing records never override the user's selected model for Skill-guided work or memory.

After changed memory, render the generated views and check only the affected links and stored readback. Full `memory_lint.py` belongs to memory maintenance, not every product task. `auto_classify.py` may organize evidence into reusable lessons; it must not turn project details into global instructions.

## Keep safe and compact

- Preserve unrelated notes and useful history. Replace redundant current rules instead of appending contradictory instructions or duplicate log layers.
- Never hand-edit `events.jsonl` or generated root views. Use guarded `remove-invalid`, `redact-private`, or `migrate-provenance` for exact legacy repairs.
- Store project-relative files and sanitized facts, never credentials, raw prompts, reasoning, machine paths, or unrelated transcripts. Tests use disposable stores under project `Cache/tmp-*`.
- The generator updates managed contracts and runtimes. User Projects, Knowledge, Preferences, Skills, and event history remain user-owned.

## Navigation

- [[Projects/index|Projects]] — project-specific current truth.
- [[Preferences/index|Preferences]] — intentional global taste and working preferences.
- [[Knowledge/index|Knowledge]] — reusable concepts; [[Knowledge/Reusable Lessons/index|lessons]] and [[Knowledge/Book References/index|optional references]].
- [[Knowledge/Memory Retrieval|Memory Retrieval]] — exact-project people, roles, bilingual technical queries, and retrieval evidence.
- [[Skills/index|Skills]] — concise capability and preference summaries.
- [[Recent Work]], [[Issues]], [[Memory Dashboard]] — generated views for browsing only.
