# LLM Wiki architecture

## Ownership model

| Concern | Canonical owner | Update rule |
|---|---|---|
| AI access contract | `AGENTS.md` | Generator-managed |
| Current project truth | `Projects/<Project>/Memory.json`, with `Knowledge.md` as its readable view | Exact project identity, scoped entries, no chronology |
| Reusable engineering truth | `Knowledge/` | Promote only current reusable rules |
| Classified reusable patterns | `Knowledge/Reusable Lessons/` | Only explicit global preferences auto-promote; project outcomes remain candidates |
| Optional external references | `Knowledge/Book References/` | Store trigger, citation range, edition/date, and freshness; never a local path |
| Reusable preferences | `Preferences/` | Store stable cross-project preferences |
| Skill contracts | `Skills/` | Store current reusable capability rules |
| Project/module chronology | `AI Memory/events.jsonl` | Runtime-managed, one outcome per event |
| Recent work | `Recent Work.md` | Generated from the event store |
| Current/recent Bugs | `Issues.md` | Generated from stable issue lifecycles |
| Coverage | `Memory Dashboard.md` | Generated from the event store |

## Query contract

Every Skill-guided task selects one exact project. Structured owners use `project-memory-skill/scripts/project_knowledge.py recall` with the real project root, scoped filters, and source freshness checks. `ai_memory.py recall` skips structured owners; for projects without an index it returns at most two prose sections labeled unverified and never reads the event store by default. Missing vaults, projects, or matches skip without creating files. Unscoped search requires explicit `--all-projects` audit intent. Another project is never a fallback.

Prose/history recall uses bounded lexical ranking with common bilingual technical terms. Module names are hints and query matches rank first. Historical events require explicit `--include-history`; they exclude superseded events within the selected project and are labeled historical evidence ineligible for current context. Long prose sections return a bounded excerpt with a truncation flag; explicitly marked legacy history blocks are excluded. Strict `search` remains an exact module/all-query-term history lookup. `recall_evidence` identifies this call's sources and limits, not comprehension or earlier memory use.

Project-result session, task, and group fields are hashed provenance, not retrieval barriers. Matching outcomes remain recallable across sessions by project, module, working line, file, contract, symptom, or symbol. A separate model-routing system may apply relation isolation, but that policy never hides project results.

## Event contract

Ending uses the user-selected model and effort to summarize useful changes, update current knowledge and complete due synthesis. Verification stays in the original task, with focused checks for meaningful changes and no obligatory full startup or build. A no-change closeout still checks exact-project maintenance; it writes nothing when both durable updates and synthesis are unnecessary.

One durable user-visible outcome creates one event. An event records project, working line, modules, summary, reason, result, verification, decisions, risks, and touched project-relative files. Multiple modules belong in one event through repeated module changes.

A repeated Bug uses one stable project-scoped `issue_id`. Each distinct attempt appends a revision with its own event ID, links the previous revision through `supersedes`, and increments `attempt_count`. Earlier causes, user corrections, failed solutions and verification remain in the same canonical chronology. Identical replays are no-ops. Issue dashboards and status-filtered search select only the latest revision; explicit historical search and recall retain earlier issue attempts. Compact history includes bounded cause, decisions, evidence and remaining risks, with truncation marked. A passing check defaults to `MONITORING`; resolving an issue requires an explicit outcome.

Current project state is the last established state, with its verification date, limits, unresolved work and next step. Matching source hashes prove source identity, not current runtime or deployment status. The existing reason, result, decisions, verification and risks fields carry this continuity; no additional status log or archive is needed.

The installed Project Memory writer owns structured index updates, their readable projection and event provenance. The generic event writer alone does not update that index. Sparse updates retain omitted current context, while changed claims require their own evidence and invalidate synthesis. A nonempty current project with missing or invalidated synthesis is due immediately; 20 distinct writes or 30 days also trigger maintenance. Closeout checks before and after saving, including no-change outcomes, and cannot claim memory completion while synthesis remains due. Synthesis uses eligible current facts and dated evidence limits; stale, retired or unsupported claims cannot become current by summarization. This is task-closeout maintenance, not an idle scheduler.

Production writes reject placeholder-only semantics. Semantic duplicates ignore session/task/group provenance. `remove-invalid` deletes only an exact placeholder event or a duplicate proven against a retained canonical event and rejects any target referenced by a superseding result.

Legacy `working_line` JSON objects and strings encoding the same object share one semantic identity. `normalize-working-lines` previews canonicalization and removes only strictly equivalent duplicate outcomes with matching business fields. Application requires the previewed SHA-256, checked under the event-store lock. Referenced IDs survive, different `supersedes` values remain separate, ordinary branch strings are unchanged, and retained outcomes preserve timestamp and attempt-count bounds. The operation reports ID mappings without emitting private payloads; malformed or conflicting inputs do not receive a partial write.

Valid legacy events with detected private values use guarded exact-ID `redact-private`. It preserves the event ID, redacts only matched fragments without printing them, recomputes the semantic fingerprint, refuses duplicate-producing rewrites, and leaves file-list repair to `amend --replace-file`.

Only hashed session/task/group provenance is persisted. The guarded, idempotent `migrate-provenance` command converts legacy normalized labels to those hashes while preserving event IDs and semantic fingerprints.

## Integrity contract

`AI Memory/memory_lint.py` validates strict UTF-8 readability, required runtime files, JSON containers, project ownership, generated markers, wikilinks and anchors, root-entry reachability, project-relative event files, placeholder and duplicate events, forbidden legacy owners, ghost artifacts, and malformed path components. Empty fresh `events.jsonl` is valid. User-owned Obsidian workspace stale references are warnings and are never edited automatically.

Numbered copies of generated root views are reported for review, and auxiliary JSONL files receive syntax checks. Historical source copies may describe a retired structure without being treated as current instructions; their readability, links, and reachability are still checked. Wikilink aliases inside Markdown tables use an escaped pipe.

`repair-jsonl --vault VAULT --path RELATIVE_JSONL --expected-sha256 DIGEST` repairs only missing newlines between complete objects in an auxiliary store. It preserves every original byte except inserted separators, rejects the primary event store, validates the full file and confined paths before writing, and rechecks the digest under compatible file locks before atomic replacement. It does not discard malformed records or invent their contents. Main-store cleanup uses the guarded `ai_memory.py` APIs.

Tests and probes use explicit disposable vaults and stores under `Cache/temp-<task>/` and run Python with `-B`. A real production store is never used to prove failure behavior.

Routine execution stays hidden/headless. The package and generated vault carry the same portable `hidden_process_options` helper: Windows child processes use no-console creation and hidden startup options; macOS/Linux receive no Windows flags. Callers retain streams, exit status, timeout, and lifecycle ownership. GUI programs require their own headless mode. A parity test keeps both standalone copies aligned, and source checks cover test subprocesses as well as runtime launches.

## Architecture update contract

The generator owns only the root AI contract, AI pointers, runtime, classifier, lint, and runtime tests. Before creating a directory, writing a file, or rendering a generated view, it preflights every managed file, seed file, event store, generated output, and vault-local ancestor; any symlink, wrong path type, or resolved path escape rejects the whole update before its first write. Generic lesson and book-reference pages are created only when missing. An older generic seed owner receives only missing canonical navigation and protocol fragments appended after its existing bytes, so user additions remain intact and a repeated update is a no-op for those fragments. Classifier recall filters candidates by exact project and returns only explicit global preferences when no project is supplied. It never promotes repeated project outcomes merely because their text matches. The classifier exclusively rewrites `Knowledge/Reusable Lessons/Candidates.md` and explicit `<!-- AUTO-LESSON:... -->` blocks; curated content outside those blocks, external-reference entries, all other user content, and event data are preserved. An update stops on locally modified managed files and reports digests unless the user explicitly accepts replacement with `--force-managed`.

## Forbidden growth patterns

- per-day, per-task, per-agent, per-file, or per-module log pages;
- duplicate History, Activity, Journal, Archive, raw, or hidden system layers;
- chronology inside a project repository `AGENTS.md`;
- absolute user-machine paths in tracked files or event records;
- secrets, raw prompts, private reasoning, credentials, or unrelated transcripts.
