# qin-llm-wiki

A portable Obsidian memory skeleton with compact current knowledge, exact-project recall, and one event store. The public generator contains no private projects or preferences.

## Use

Run with Python 3 (`python3` on macOS/Linux, `py -3` on Windows):

```text
python3 -B -m qin_llm_wiki init --vault "path/to/MyWiki" --name "My LLM Wiki"
python3 -B -m qin_llm_wiki update --vault "path/to/MyWiki"
python3 -B -m qin_llm_wiki verify --vault "path/to/MyWiki"
```

Open the folder in Obsidian. Agents enter through `AGENTS.md` (or agent-specific pointers `CLAUDE.md`, `GEMINI.md`) and read only memory relevant to the exact project and task. Missing memory is a normal skip.

```text
python3 -B "path/to/MyWiki/AI Memory/ai_memory.py" recall --project GameOne --module combat.damage --query "critical rounding"
```

`recall` returns up to two relevant project-prose sections labeled unverified, without reading event history. Projects with a structured `Memory.json` use the installed Project Memory reader with the exact project root and freshness checks; the prose reader skips instead of bypassing that owner. Explicit `--include-history` returns up to five compact historical events labeled ineligible for current context. It accepts module hints and Chinese/English technical selectors, rejects project-owner symlinks, and never creates an absent vault or substitutes another project. Advanced `search` retains exact module and all-keyword matching; cross-project maintenance requires explicit `--all-projects`.

Read the returned source and explain its relevance in the active task. A lookup response establishes only that call's retrieval; coverage and routing records cannot establish historical memory usage. The generated `Knowledge/Memory Retrieval.md` explains project, people/role, technical, and shared-preference entry points.

## Memory workflow

The user's selected model and effort design tasks, perform Skill-guided work, and summarize memory. The original task verifies behavior with focused checks; simple value changes may skip tests. Ending saves useful memory and completes due synthesis. No-change closeouts still check maintenance; when neither facts nor synthesis need updating, they write nothing.

Keep current code ownership, interfaces, preferences, document organization, decisions, and last verified project state in one concise owner. Structured project details live in `Projects/<Project>/Memory.json`, with `Knowledge.md` as their readable view; only intentional global preferences and reusable concepts belong in shared owners. Save recurring problems and user corrections, attempted solutions, actual results and evidence, unresolved items and next steps under the exact project. Historical model-routing records never override a user-selected model for Skill-guided work.

With Project Memory installed, use its supported Ending writer to reconcile current entries and canonical history together; the generic `record` command below writes history only. Preserve omitted existing context and explicitly retire or supersede obsolete claims. A project summary becomes due immediately when nonempty current knowledge lacks a valid synthesis, and after 20 distinct writes or 30 days. Ending checks before and after the write, synthesizes eligible current facts with their evidence limits, and reads back completion. This automatic maintenance runs at task closeout, including no-change closeouts; it does not run unattended while the app is idle. The public generator supplies the generic skeleton and event runtime; the installed Project Memory skill supplies the structured writer and synthesis lifecycle.

One distinct outcome creates one event. Repeated Bugs reuse a stable issue ID and append linked revisions, preserving earlier failures and fixes. Identical replays do not add events or attempts. Issue views show the latest revision; a passing check requires an explicit `RESOLVED` outcome to close the issue. `amend` fills missing details in the same observation; use `record` for a changed outcome:

```text
python3 -B "path/to/MyWiki/AI Memory/ai_memory.py" record --project GameOne --module combat.damage --event-type bug-fix --summary "Fixed critical hit rounding" --reason "Multiplier applied after rounding" --result "Focused damage checks pass" --verification-status passed --issue-id combat-critical-001 --issue-status RESOLVED --file src/combat/damage.py
python3 -B "path/to/MyWiki/AI Memory/ai_memory.py" render
```

`capture-memory --candidate-file candidates.json` saves only explicitly global preferences (project-scoped writes are rejected) and is a no-op for empty input. `auto_classify.py sync` organizes review candidates; only explicit global preferences auto-promote. `auto_classify.py recall --project GameOne` keeps candidate retrieval scoped. Project-specific details remain with their owner. Guarded `remove-invalid`, `redact-private`, and `migrate-provenance` repair exact legacy records without revealing removed private values. Never edit `events.jsonl` manually.

## Ownership and updates

- `Projects/`, `Knowledge/`, `Preferences/`, `Skills/`: current user-owned knowledge.
- `AI Memory/events.jsonl`: the only chronology.
- `Recent Work.md`, `Issues.md`, `Memory Dashboard.md`: generated browsing views, excluded from ordinary task startup.
- `AGENTS.md`, AI entry pointers, and runtime/tests: generator-managed architecture.

Updates preserve user content and events, reject unsafe paths before writing, and report drift in locally modified managed files. Review the diff before intentional `--force-managed` replacement. Generic seed additions are idempotent and preserve user bytes. A private vault is a downstream installation, never a public source mirror.

## Maintenance checks

```text
python3 -B -m unittest discover -s tests -p "test_*.py" -v
python3 -B -m qin_llm_wiki privacy-check --path .
```

Focused tests exercise project isolation, absent-memory skips, bounded recall, writer privacy, guarded repairs, and safe updates. `verify` checks structure and links, runs runtime tests, and replays record/search/render in disposable `Cache/temp-<task>/` data without touching production events. See [Architecture](docs/ARCHITECTURE.md) and [Privacy](docs/PRIVACY.md).

For reviewed legacy stores, `ai_memory.py normalize-working-lines` previews JSON-object/string normalization and strictly equivalent duplicate removal. Applying that exact preview requires `--apply --expected-sha256 DIGEST`; referenced IDs and different business facts are preserved. For auxiliary JSONL files with complete objects joined without a newline, use the generator's `repair-jsonl --vault VAULT --path RELATIVE_JSONL --expected-sha256 DIGEST`. Back up the private vault before either migration. Neither command uploads private memory.
