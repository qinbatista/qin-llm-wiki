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

`recall` returns up to two matching Knowledge sections and five compact events. It never substitutes another project, follows project-owner symlinks, or creates an absent vault. Session provenance does not hide another session's result for the same project. Advanced `search` requires `--project`; cross-project maintenance must explicitly use `--all-projects`.

## Memory workflow

The user's selected model and effort design tasks, perform Skill-guided work, and summarize memory. The original task verifies behavior with focused checks; simple value changes may skip tests. Ending only saves useful memory, and does nothing when no durable information changed.

Keep current code ownership, interfaces, UI preferences, document organization, and decisions in one concise owner. Project details stay in `Projects/<Project>/Knowledge.md`; only intentional global preferences and reusable concepts belong in `Preferences/`, `Knowledge/`, or `Skills/`. Historical model-routing records never override a user-selected model for Skill-guided work.

One outcome creates one event. Repeated Bugs reuse a stable issue ID; `amend` adds missing details without another row:

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

Focused tests exercise project isolation, absent-memory skips, bounded recall, writer privacy, guarded repairs, and safe updates. `verify` checks structure and links, runs runtime tests, and replays record/search/render in disposable `Cache/tmp-*` data without touching production events. See [Architecture](docs/ARCHITECTURE.md) and [Privacy](docs/PRIVACY.md).
