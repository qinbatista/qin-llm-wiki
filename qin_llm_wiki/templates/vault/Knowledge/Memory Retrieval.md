# Memory Retrieval

Choose the exact project before searching. Current project knowledge is the first owner; history explains earlier decisions and must not override current source.

## Find the right memory

| Need | Start with | Keep in scope |
| --- | --- | --- |
| A project task | Exact-root structured recall with task module/file/symbol selectors | One project and the relevant heading |
| A person, character, or role | Exact-root scoped recall, then an explicitly selected owner reference | Exact name, role, and project; never infer identity from another project |
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

Ordinary structured recall requires a task module, file, symbol or meaningful query; it does not attach whole-project context. Explicit `--include-project-context` without selectors returns only project facts and navigation, never arbitrary module facts. Generic prose recall also requires meaningful task terms, and a query miss never selects a module-only fallback. A no-match, stale or identity skip means inspect the owning source, never a whole Knowledge page or Codex-local memory. During a requested isolation repair, replace obsolete commands in the actual caller instead of retaining them below an override sentence. History stays explicitly selected and dated.

## Project, task and underlying logic

Read in order: exact project → relevant task memory → underlying logic. Use installed `project_knowledge.py logic` with task selectors to follow `applies-logic` links to shared `logic.*` principles and related case pointers. Stale/unverified task scopes retain reviewed logic metadata as ineligible pointers while their claims remain excluded; retired scopes supply no routes. Without a saved link, identify the causal principle from the current problem/source and select its shared owner/module explicitly. Keywords alone cannot establish equivalence.

Only selected reference facts are read from their exact owner. Compare the transferable rule, applies/avoid conditions, implementation differences and dated verification. A common parallelism principle does not transfer another project's APIs, capacity, lifecycle or measured result. Current-source changes leave old cases historical. Keep structured facts, shared principles and case history in their existing owners and event store, with relations connecting them rather than duplicate memory files.

Follow a historical event pointer with `AI Memory/ai_memory.py search --project OWNER --event-id ID`, not an ID placed in `--query`. The exact selector cannot substitute a later event that merely mentions that ID; returned history remains ineligible as current proof.

## Keep current pages useful

Use descriptive headings for a stable feature, role, or owner. Put the current decision, relevant files or interfaces, and known limits first. Keep detailed references linked from their owner. Do not append complete task reports, duplicate chronology, or create a page for every function or date. Replace a superseded current rule while retaining useful history in the event store.

Project-specific people and character facts stay under their project. Shared technical navigation links to current owners without copying their facts into a new global rule.

When source differs, a user corrects a claim, or observed behavior contradicts memory, inspect only the affected scope and save the established replacement with its actual evidence. Do not rehash old claims into current proof. Structured updates preserve omitted useful context and invalidate obsolete synthesis. At closeout, check maintenance even if no new fact was produced; a missing or invalidated summary is due for nonempty current knowledge, with 20 writes or 30 days as additional triggers. Synthesis remains a navigation summary with dated limits, never a substitute for scoped source checks.

## What a recall proves

The response identifies which sources matched this query. In the active task, state the useful source and how it affects the work, or say that nothing relevant matched. A successful lookup proves retrieval for that call; usefulness requires reading and applying the result. Event counts, model-routing records, and scope coverage do not prove that earlier tasks read or used memory. Do not invent historical read receipts or add a second event log to simulate them.

- [[AGENTS|Memory contract]]
- [[Knowledge/index|Knowledge]]
- [[Start Here]]
