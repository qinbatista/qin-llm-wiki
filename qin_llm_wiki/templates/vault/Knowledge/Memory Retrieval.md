# Memory Retrieval

Choose the exact project before searching. Current project knowledge is the first owner; history explains earlier decisions and must not override current source.

## Find the right memory

| Need | Start with | Keep in scope |
| --- | --- | --- |
| A project task | [[Projects/index\|Project index]], then its Knowledge page | One project and the relevant heading |
| A person, character, or role | The owning project's Knowledge page and its linked reference | Exact name, role, and project; never infer identity from another project |
| A similar technical task | [[Knowledge/Reusable Lessons/index\|Reusable lessons]], then the exact project's recall | Shared principles may transfer; project facts do not |
| Style or interaction | [[Preferences/index\|Preferences]] | The relevant shared owner, plus any project-specific override |
| Past outcome or failure | Scoped event search | Read the result and its verification limits |

Run with Python 3: `python3 -B` on macOS/Linux, `py -3 -B` on Windows. Replace the project and query in this example:

```text
python3 -B "AI Memory/ai_memory.py" recall --project GameOne --module combat --query "damage rounding"
```

This prose reader returns at most two relevant sections labeled unverified and does not read event history by default. When `Projects/<owner>/Memory.json` exists, use the installed `project-memory-skill/scripts/project_knowledge.py recall --project-root ROOT --vault VAULT` for exact identity, module/file/symbol filtering, and freshness checks. A skipped structured lookup must not fall back to old prose or another project.

Use scoped `search` or explicit `recall --include-history` only to investigate provenance or a past outcome. Historical events are labeled `historical_evidence` and cannot become current authority. Common Chinese and English technical selectors help bilingual prose/history lookup; this is a bounded keyword matcher, not a semantic model. Strict `search` retains exact module filtering and requires all query terms.

Issue history retains prior attempts, causes, user corrections, fixes and remaining limits. `issue_is_current` identifies the latest saved revision for that issue; status-filtered search selects only that revision. Compact history includes bounded reason, decisions, verification and risks. When `details_truncated` is true, read the needed full scoped event before relying on omitted details. A latest saved status is dated evidence, not a live deployment check.

## Keep current pages useful

Use descriptive headings for a stable feature, role, or owner. Put the current decision, relevant files or interfaces, and known limits first. Keep detailed references linked from their owner. Do not append complete task reports, duplicate chronology, or create a page for every function or date. Replace a superseded current rule while retaining useful history in the event store.

Project-specific people and character facts stay under their project. Shared technical navigation links to current owners without copying their facts into a new global rule.

When source differs, a user corrects a claim, or observed behavior contradicts memory, inspect only the affected scope and save the established replacement with its actual evidence. Do not rehash old claims into current proof. Structured updates preserve omitted useful context and invalidate obsolete synthesis. At closeout, check maintenance even if no new fact was produced; a missing or invalidated summary is due for nonempty current knowledge, with 20 writes or 30 days as additional triggers. Synthesis remains a navigation summary with dated limits, never a substitute for scoped source checks.

## What a recall proves

The response identifies which sources matched this query. In the active task, state the useful source and how it affects the work, or say that nothing relevant matched. A successful lookup proves retrieval for that call; usefulness requires reading and applying the result. Event counts, model-routing records, and scope coverage do not prove that earlier tasks read or used memory. Do not invent historical read receipts or add a second event log to simulate them.

- [[AGENTS|Memory contract]]
- [[Knowledge/index|Knowledge]]
- [[Start Here]]
