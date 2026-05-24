# No Kind→style table in cc segment

`render_cc_segment` keeps its if-chain over `Kind` rather than a
`KIND_STYLE: dict[Kind, Style]` lookup table.

## Why

The four current Kinds carry three structurally distinct render rules,
not four values of one rule:

- `TTL_REFRESH` — red+bold with a `(TTL!)` suffix
- `FIRST_TURN` — uniformly dim, ignores `cc` magnitude
- `DATA_LOAD` / `NORMAL` — size-based palette (4 thresholds, ⚠ at 10k+, ‼ at 30k+)

A table would either need a per-entry `apply()` method (reintroducing
branches one layer down) or a `by_size: bool` fallback flag that
re-implements the if-chain as data. Either way the indirection costs
more than the explicit branches at today's scale.

## When to revisit

Open this ADR if a fifth `Kind` is added (e.g. explicit "compaction"
or "tool-output spike") and the new Kind shares its render rule with
an existing one — at that point a table starts earning its keep.

## Considered options

- **`KIND_STYLE` table now** — rejected, see above.
- **Strategy per Kind (subclasses of a Style ABC)** — even heavier; same payoff.
