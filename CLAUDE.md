In all interactions and commit messages, be extremely concise and sacrifice grammar for the sake of concision.

## Release Notes Format

When creating GitHub releases:

- Start with **Highlights** — short paragraph: what it is and why it matters
- Categorize changes: **Features**, **Bug Fixes**, **Breaking Changes**, **Improvements**
- User-focused language — describe what user gains, not internal details
- Include **Installation** section with commands
- Link to PRs/issues where relevant
- Keep bullet points concise, bold the feature name

## Agent skills

### Issue tracker

GitHub issues in `malcolmpl/claude-statusline` via `gh` CLI. See `docs/agents/issue-tracker.md`.

### Triage labels

Canonical names: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: `CONTEXT.md` + `docs/adr/` at repo root. See `docs/agents/domain.md`.

## Version bump hook

`githooks/post-commit` (enabled via `git config core.hooksPath githooks`) auto-bumps `version` in `.claude-plugin/plugin.json` + `marketplace.json` and amends it into the commit. Fires only when commit touches `.claude-plugin/plugin.json`, `commands/` or `scripts/`.

- `feat:` → minor + local tag `vX.Y.0`; `fix:`/`chore:`/other → patch, no tag; `BREAKING CHANGE` → major + tag; `[release]` forces tag; `[skip-bump]` skips.
- Never set version manually in a normal commit — just commit.
- Hook fires on EVERY commit creation, incl. `rebase`, `cherry-pick`, `commit --amend` → double bump (e.g. 1.4.0 → 1.5.0) + extra tag. Before such ops: `touch .git/.version-bump-lock` (hook deletes it and skips once; one lock = one commit). On rebase conflict in `version`: keep the value from the commit being replayed.
- After accidental double bump: restore version in both JSONs, `touch .git/.version-bump-lock`, `git commit --amend --no-edit`, delete extra tag, `git tag -f vX.Y.Z HEAD`.
- Push order: `git push origin master` first; only after it succeeds push the tag. Pushing a tag on a rejected master leaves the remote tag on an orphaned commit.
