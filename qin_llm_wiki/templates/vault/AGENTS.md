# {{WIKI_NAME}} AI contract

This is the mandatory entry contract for every AI that reads or writes this vault. Do not invent a second memory workflow.

## Visible root map

- `Projects/`: current project truth, organized by project and stable module sections.
- `Preferences/`: reusable UI, artwork, interaction, and working preferences.
- `Knowledge/`: current cross-project engineering and operating knowledge.
- `Knowledge/Reusable Lessons/`: bounded reusable patterns classified from verified outcomes.
- `Knowledge/Book References/`: generic, freshness-labeled pointers to optional local books; source files stay outside the vault.
- `Skills/`: current reusable capability and Skill contracts.
- `AI Memory/events.jsonl`: the only writable project/module chronology.
- `AI Memory/ai_memory.py`: the only supported history writer, bounded personal-memory candidate writer, query, renderer, and exact-ID invalid-record remover.
- `AI Memory/auto_classify.py`: the only supported reusable-lesson classifier.
- `Recent Work.md`: generated 30-day daily/project overview.
- `Issues.md`: generated active, monitoring, and recently resolved Bug view.
- `Memory Dashboard.md`: generated project/module coverage.

## Task-entry Memory gate and bounded query path

Before project, code, Bug, architecture, UI, performance, or reusable-technology work, report `Memory gate: project=<...> · module=<...> · lessons=<category or none> · events=<0-5> · books=<matched or no-match>` after actually running the lookup.

1. Resolve one project, working line, and functional module from the request and current source.
2. Read `Projects/<Project>/index.md` and only the matching section of `Projects/<Project>/Knowledge.md`.
3. Query at most five compact events by project, module, file, contract, symptom, or requested behavior.
4. Recall one matching [[Knowledge/Reusable Lessons/index|Reusable Lessons]] category. If a [[Knowledge/Book References/index|Book References]] trigger matches, read its freshness-labeled entry before opening the external source.
5. Read one relevant preference or cross-project page only when needed.
6. Treat current source and current Knowledge as behavior authority. Events explain rationale, regressions, and provenance.

macOS/Linux:

```text
python3 -B "AI Memory/ai_memory.py" search --project ProjectName --module feature.module --query symptom --limit 5 --compact
```

Windows PowerShell:

```text
py -3 -B "AI Memory\ai_memory.py" search --project ProjectName --module feature.module --query symptom --limit 5 --compact
```

Do not load complete event storage, generated dashboards, broad Skill records, or unrelated projects as ordinary task context.

Project-result session, task, and group fields are hashed provenance, not retrieval barriers. Search matching outcomes across sessions by project, module, working line, file, contract, symptom, or symbol. Relation-scoped isolation belongs only to a separate model-routing system.

## One outcome, one event

- Record exactly one event after a durable user-visible outcome.
- Ending may use `capture-memory` for a sanitized preference or technical-working-trait bundle; an empty bundle is a strict no-op.
- Put every affected module in that event with repeated `--module-change MODULE=SUMMARY` values.
- Reuse one stable `--issue-id` for the same Bug so a retry updates the lifecycle row and increments `attempt_count`.
- Use `amend` to add missing files, evidence, decisions, or risks without appending another event.
- Never create per-task, per-date, per-commit, per-file, per-method, per-module, or per-agent log pages.
- Project repository `AGENTS.md` files contain stable structure and commands only, never chronology.

After recording, run `AI Memory/auto_classify.py sync`, `AI Memory/ai_memory.py render`, and `AI Memory/memory_lint.py` with the platform's Python 3 command and `-B`.

## Bug lifecycle

- `ACTIVE`: present or unresolved.
- `MONITORING`: changed, but observable acceptance evidence is incomplete.
- `RESOLVED`: the current relevant path passed observable verification.
- `ARCHIVED`: current architecture proves the old owner, path, contract, or consumer is unreachable.

Do not mark a Bug resolved after one failed reproduction or a source-only check when its failure mode is runtime, visual, generated, API, or artifact-based.

## Write and privacy boundaries

- Current truth has exactly one owner in `Projects/`, `Preferences/`, `Knowledge/`, or `Skills/`.
- This vault has no archive layer. Promote useful current facts, keep chronology in the event store, and delete obsolete duplicates.
- Do not hand-edit generated root views or `events.jsonl`; use the runtime writer, `amend`, guarded exact-ID `redact-private`, or guarded `remove-invalid`.
- Remove a proven placeholder or semantic duplicate only with `AI Memory/ai_memory.py remove-invalid --event-id <exact-id>`; a valid event and an event referenced by a superseding result must be rejected.
- Sanitize a valid legacy event with a detected home path, email, or credential-like fragment only with `AI Memory/ai_memory.py redact-private --event-id <exact-id>`. Preserve the event ID, redact only matched fragments, reveal no removed value, refuse semantic-duplicate conflicts, and repair invalid `files` separately through `amend --replace-file`.
- After upgrading a legacy vault, use the guarded idempotent `AI Memory/ai_memory.py migrate-provenance` command once to replace normalized task labels with hash-only provenance while preserving event IDs and semantic fingerprints.
- Do not restore duplicate logs or hidden system folders.
- Store project-relative files. Never store credentials, secrets, raw prompts, private reasoning, user-machine home paths, or unrelated transcripts.
- Production probes are forbidden. Tests use an explicit disposable store and vault under the active project's `Cache/tests/` tree and run Python with `-B`.
- A structure change is complete only when every managed file is readable UTF-8 where applicable, every semantic Markdown page is reachable from a root entry, every wikilink and anchor resolves, and no placeholder event, semantic duplicate, malformed Cache path, `.DS_Store`, `__pycache__`, bytecode, empty canvas, or numbered Untitled canvas remains.
- User-owned `.obsidian/workspace*` stale references are warnings and are never edited automatically.
- If the runtime is missing or fails, stop and report the exact error. Do not create a fallback store.
