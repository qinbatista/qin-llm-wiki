# Privacy and publication safety

The public repository contains architecture, generic examples, tests, and empty templates only. A generated user vault is private by default and must not be committed to this repository or copied back as a source mirror.

The privacy checker rejects common credential prefixes, private keys, home-directory paths, email addresses, and credential-bearing URLs in publishable text files. It excludes Git internals, ignored Cache artifacts, virtual environments, and build output.

Generated vault writers reject the same private-value classes before an event is persisted. A valid legacy event is repaired only by exact-ID `redact-private`, which never prints the removed value; invalid file lists use `amend --replace-file`. Direct JSONL editing is not a supported migration.

Before publication:

1. Generate tests only under the repository `Cache/` directory.
2. Run the privacy checker against tracked source.
3. Run a fresh generated-vault deep verify, including strict lint, runtime tests, and disposable record/search/render replay.
4. Inspect `git status` and the staged diff.
5. Confirm no generated vault, event store, promoted user lesson, book-library path, Obsidian workspace, cache registry, session/thread ID, or personal note is staged.
6. Publish only after tests, package build, architecture comparison, and the privacy gate pass.

The repository name and license author are public identity choices. They are not copied from a private vault.
