# LLM Wiki architecture

## Ownership model

| Concern | Canonical owner | Update rule |
|---|---|---|
| AI access contract | `AGENTS.md` | Generator-managed |
| Current project truth | `Projects/<Project>/Knowledge.md` | User/AI maintained, no chronology |
| Reusable engineering truth | `Knowledge/` | Promote only current reusable rules |
| Reusable preferences | `Preferences/` | Store stable cross-project preferences |
| Skill contracts | `Skills/` | Store current reusable capability rules |
| Project/module chronology | `AI Memory/events.jsonl` | Runtime-managed, one outcome per event |
| Recent work | `Recent Work.md` | Generated from the event store |
| Current/recent Bugs | `Issues.md` | Generated from stable issue lifecycles |
| Coverage | `Memory Dashboard.md` | Generated from the event store |

## Query contract

An AI resolves one project and module, reads the project index and matching Knowledge section, queries at most five events, and reads at most one relevant preference or cross-project pattern. It must not load all events, all projects, generated dashboards, or broad logs for an ordinary task.

## Event contract

One durable user-visible outcome creates one event. An event records project, working line, modules, summary, reason, result, verification, decisions, risks, and touched project-relative files. Multiple modules belong in one event through repeated module changes.

A repeated Bug uses one stable `issue_id`. A new attempt updates that row, changes its lifecycle status, and increments `attempt_count`.

## Architecture update contract

The generator owns only the root AI contract, AI pointers, runtime, lint, and runtime tests. User content and event data are never overwritten. An update stops on locally modified managed files unless the user explicitly accepts replacement with `--force-managed`.

## Forbidden growth patterns

- per-day, per-task, per-agent, per-file, or per-module log pages;
- duplicate History, Activity, Journal, Archive, raw, or hidden system layers;
- chronology inside a project repository `AGENTS.md`;
- absolute user-machine paths in tracked files or event records;
- secrets, raw prompts, private reasoning, credentials, or unrelated transcripts.
