# qin-llm-wiki repository contract

- `qin_llm_wiki/cli.py` owns portable vault creation, architecture updates, comparison, verification, and privacy checks.
- `qin_llm_wiki/templates/vault/` is the canonical public vault skeleton. It must contain architecture only, never a user's projects, history, paths, credentials, preferences, or private notes.
- Generated vault chronology has one owner: `AI Memory/events.jsonl`. Never add Journal, History, Activity, Archive, raw, per-task, per-date, or per-agent log layers.
- `tests/` owns public regression coverage. Disposable generated vaults and comparison evidence belong under `Cache/tests/llm-wiki-architecture/` and remain untracked.
- `Cache/cache_path.json` is an untracked AI-only external-path registry; project code, tests, packages, and published documentation must never read it.
- Host-run code supports Windows, macOS, and Linux through one Python entry point, runtime-derived paths, standard-library APIs, and `sys.executable` for child Python execution.
- Update managed contracts and runtime files only through the generator. Preserve user-owned Projects, Knowledge, Preferences, Skills, and `AI Memory/events.jsonl`.
- Definition of done: unit tests, generated-vault lint, record/search/render replay, architecture comparison, tracked-file privacy scan, package build, and clean diff all pass before publication.
