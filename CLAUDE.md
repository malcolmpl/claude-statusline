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
