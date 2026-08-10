# LLM Wiki architecture

## Ownership model

| Concern | Canonical owner | Update rule |
|---|---|---|
| AI access contract | `AGENTS.md` | Generator-managed |
| Current project truth | `Projects/<Project>/Knowledge.md` | User/AI maintained, no chronology |
| Reusable engineering truth | `Knowledge/` | Promote only current reusable rules |
| Classified reusable patterns | `Knowledge/Reusable Lessons/` | Promote only verified, privacy-safe evidence |
| Optional external references | `Knowledge/Book References/` | Store trigger, citation range, edition/date, and freshness; never a local path |
| Reusable preferences | `Preferences/` | Store stable cross-project preferences |
| Skill contracts | `Skills/` | Store current reusable capability rules |
| Project/module chronology | `AI Memory/events.jsonl` | Runtime-managed, one outcome per event |
| Recent work | `Recent Work.md` | Generated from the event store |
| Current/recent Bugs | `Issues.md` | Generated from stable issue lifecycles |
| Coverage | `Memory Dashboard.md` | Generated from the event store |

## Query contract

An AI resolves one project and module, reads the project index and matching Knowledge section, queries at most five events, and reads at most one relevant preference or cross-project pattern. It must not load all events, all projects, generated dashboards, or broad logs for an ordinary task.

Project-result session, task, and group fields are hashed provenance, not retrieval barriers. Matching outcomes remain recallable across sessions by project, module, working line, file, contract, symptom, or symbol. A separate model-routing system may apply relation isolation, but that policy never hides project results.

## Event contract

One durable user-visible outcome creates one event. An event records project, working line, modules, summary, reason, result, verification, decisions, risks, and touched project-relative files. Multiple modules belong in one event through repeated module changes.

A repeated Bug uses one stable `issue_id`. A new attempt updates that row, changes its lifecycle status, and increments `attempt_count`.

Production writes reject placeholder-only semantics. Semantic duplicates ignore session/task/group provenance. `remove-invalid` deletes only an exact placeholder event or a duplicate proven against a retained canonical event and rejects any target referenced by a superseding result.

Valid legacy events with detected private values use guarded exact-ID `redact-private`. It preserves the event ID, redacts only matched fragments without printing them, recomputes the semantic fingerprint, refuses duplicate-producing rewrites, and leaves file-list repair to `amend --replace-file`.

Only hashed session/task/group provenance is persisted. The guarded, idempotent `migrate-provenance` command converts legacy normalized labels to those hashes while preserving event IDs and semantic fingerprints.

## Integrity contract

`AI Memory/memory_lint.py` validates strict UTF-8 readability, required runtime files, JSON containers, project ownership, generated markers, wikilinks and anchors, root-entry reachability, project-relative event files, placeholder and duplicate events, forbidden legacy owners, ghost artifacts, and malformed path components. Empty fresh `events.jsonl` is valid. User-owned Obsidian workspace stale references are warnings and are never edited automatically.

Tests and probes use explicit disposable vaults and stores under `Cache/tests/` and run Python with `-B`. A real production store is never used to prove failure behavior.

## Architecture update contract

The generator owns only the root AI contract, AI pointers, runtime, classifier, lint, and runtime tests. Before creating a directory, writing a file, or rendering a generated view, it preflights every managed file, seed file, event store, generated output, and vault-local ancestor; any symlink, wrong path type, or resolved path escape rejects the whole update before its first write. Generic lesson and book-reference pages are created only when missing. An older generic seed owner receives only missing canonical navigation and protocol fragments appended after its existing bytes, so user additions remain intact and a repeated update is a no-op for those fragments. The classifier exclusively rewrites `Knowledge/Reusable Lessons/Candidates.md` and explicit `<!-- AUTO-LESSON:... -->` blocks; curated content outside those blocks, external-reference entries, all other user content, and event data are preserved. An update stops on locally modified managed files and reports digests unless the user explicitly accepts replacement with `--force-managed`.

## Forbidden growth patterns

- per-day, per-task, per-agent, per-file, or per-module log pages;
- duplicate History, Activity, Journal, Archive, raw, or hidden system layers;
- chronology inside a project repository `AGENTS.md`;
- absolute user-machine paths in tracked files or event records;
- secrets, raw prompts, private reasoning, credentials, or unrelated transcripts.
