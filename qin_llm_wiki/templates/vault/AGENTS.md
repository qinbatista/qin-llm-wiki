# {{WIKI_NAME}} memory contract

This vault helps users and AI avoid repeating project explanations and failed attempts. It owns project current knowledge and useful task history. Read the [project AI index](.agents/skills/ai-index/SKILL.md), then only the relevant route. Detailed rules are in its memory contract.

## Read

- Resolve one exact project. Use `project-memory-skill/scripts/project_knowledge.py recall --project-root ROOT --vault VAULT` for structured owners and relevant module/file/symbol filters. No-match, stale or wrong-root results never authorize a whole Knowledge page, another project or Codex-local memory fallback. Ordinary recall requires a task selector; explicit `--include-project-context` without selectors returns only project facts and navigation, never arbitrary modules.
- Only an owner without Memory.json uses `AI Memory/ai_memory.py recall` for bounded unverified prose. History is explicit and separate; `--all-projects` is reserved for a user-requested memory audit.
- Preserve important project contracts, user corrections, failed attempts, dated results, blockers and next steps. Update through the supported current writer, keep omitted useful facts, and reconcile superseded claims. `AI Memory/events.jsonl` is the sole chronology; Knowledge.md is a readable projection.
- Keep project facts in their exact owner. Cross-project links are unloaded references. Shared preferences require explicitly shared intent. Disable Codex automatic memory generation and use while this vault owns memory; settings apply to future sessions.
- Retrieve project → task → underlying logic. Follow explicit shared-principle links for relevant cross-project experience; compare applicability and implementation differences before reuse, keeping foreign facts and dated proof in their original owner.
- Use the user-selected model and effort. The main task verifies changes; Ending only saves established facts and performs scoped closure. Check necessary synthesis without turning it into current evidence.
- Preserve private notes and unrelated work. Never hand-edit generated stores or copy private memory to public templates. Use Python 3 with `-B`, portable hidden execution and the active task's Cache for temporary support. Do not open apps unless requested.

See [the full memory contract](.agents/skills/ai-index/memory-contract.md) for identity, writing, recovery and closure requirements. The generator owns managed runtime/contracts; Projects, user Knowledge, Preferences, Skills and event history remain user-owned. Back up the whole vault regularly.
