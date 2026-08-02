# {{WIKI_NAME}} AI contract

This is the mandatory entry contract for every AI that reads or writes this vault. Do not invent a second memory workflow.

## Visible root map

- `Projects/`: current project truth, organized by project and stable module sections.
- `Preferences/`: reusable UI, artwork, interaction, and working preferences.
- `Knowledge/`: current cross-project engineering and operating knowledge.
- `Skills/`: current reusable capability and Skill contracts.
- `AI Memory/events.jsonl`: the only writable project/module chronology.
- `AI Memory/ai_memory.py`: the only supported history writer, query, and renderer.
- `Recent Work.md`: generated 30-day daily/project overview.
- `Issues.md`: generated active, monitoring, and recently resolved Bug view.
- `Memory Dashboard.md`: generated project/module coverage.

## Mandatory bounded query path

1. Resolve one project, working line, and functional module from the request and current source.
2. Read `Projects/<Project>/index.md` and only the matching section of `Projects/<Project>/Knowledge.md`.
3. Query at most five compact events by project, module, file, contract, symptom, or requested behavior.
4. Read one relevant preference or cross-project page only when needed.
5. Treat current source and current Knowledge as behavior authority. Events explain rationale, regressions, and provenance.

macOS/Linux:

```text
python3 "AI Memory/ai_memory.py" search --project ProjectName --module feature.module --query symptom --limit 5 --compact
```

Windows PowerShell:

```text
py -3 "AI Memory\ai_memory.py" search --project ProjectName --module feature.module --query symptom --limit 5 --compact
```

Do not load complete event storage, generated dashboards, broad Skill records, or unrelated projects as ordinary task context.

## One outcome, one event

- Record exactly one event after a durable user-visible outcome.
- Put every affected module in that event with repeated `--module-change MODULE=SUMMARY` values.
- Reuse one stable `--issue-id` for the same Bug so a retry updates the lifecycle row and increments `attempt_count`.
- Use `amend` to add missing files, evidence, decisions, or risks without appending another event.
- Never create per-task, per-date, per-commit, per-file, per-method, per-module, or per-agent log pages.
- Project repository `AGENTS.md` files contain stable structure and commands only, never chronology.

After recording, run `AI Memory/ai_memory.py render` and `AI Memory/memory_lint.py` with the platform's Python 3 command.

## Bug lifecycle

- `ACTIVE`: present or unresolved.
- `MONITORING`: changed, but observable acceptance evidence is incomplete.
- `RESOLVED`: the current relevant path passed observable verification.

Do not mark a Bug resolved after one failed reproduction or a source-only check when its failure mode is runtime, visual, generated, API, or artifact-based.

## Write and privacy boundaries

- Current truth has exactly one owner in `Projects/`, `Preferences/`, `Knowledge/`, or `Skills/`.
- This vault has no archive layer. Promote useful current facts, keep chronology in the event store, and delete obsolete duplicates.
- Do not hand-edit generated root views or `events.jsonl`; use the runtime.
- Do not restore duplicate logs or hidden system folders.
- Store project-relative files. Never store credentials, secrets, raw prompts, private reasoning, user-machine home paths, or unrelated transcripts.
- If the runtime is missing or fails, stop and report the exact error. Do not create a fallback store.
