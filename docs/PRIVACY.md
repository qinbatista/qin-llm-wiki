# Privacy and publication safety

The public repository contains architecture, generic examples, tests, and empty templates only. A generated user vault is private by default and must not be committed to this repository.

The privacy checker rejects common credential prefixes, private keys, home-directory paths, email addresses, and credential-bearing URLs in publishable text files. It excludes Git internals, ignored Cache artifacts, virtual environments, and build output.

Before publication:

1. Generate tests only under the repository `Cache/` directory.
2. Run the privacy checker against tracked source.
3. Inspect `git status` and the staged diff.
4. Confirm no generated vault, event store, Obsidian workspace, cache registry, or personal note is staged.
5. Publish only after tests and the privacy gate pass.

The repository name and license author are public identity choices. They are not copied from a private vault.
