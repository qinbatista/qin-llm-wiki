# Privacy and Safety

- Store no credentials, secrets, cookies, raw prompts, private reasoning, personal home paths, or unrelated transcripts.
- Use project-relative paths in events and current knowledge.
- Reject private or secret-like values before recording. Repair a valid legacy event only through guarded exact-ID `redact-private`; never edit JSONL directly or expose the removed value in evidence.
- Keep public architecture repositories separate from generated private vaults.
- Run production memory writes only for real outcomes. Put probes, fixtures, and failure simulations in an explicit disposable store and vault under the active project's `Cache/temp-<task>/` tree.
- Treat malformed path components, bytecode, system metadata, empty canvases, placeholder events, and unreachable pages as integrity failures rather than hidden clutter.
- Before publishing a template change, run the repository privacy checker and inspect the staged diff.
