# Registry-pattern migration — scope for remaining bespoke channels

**Status: scoping only (2026-07-15).** Written after the `natl_unemp` →
`NATIONAL_SERIES` registry migration proved the pattern: one registry tuple
drives fetch, injection, column names, and the row-builder loop, so adding
or moving a series is a one-line spec instead of a 3-file edit. This doc
scopes where else the same cleanup applies.

## The pattern being replicated

A "channel" is a family of auxiliary ML feature columns fed from an external
dataset. The registry form gives each channel: a spec tuple (single source
of truth), one generic injection block, generated column names, one generic
`_build_row` reader loop, and one loader. The bespoke form scatters ~30
references per channel across `ml_features.py`, `ml_trend.py`, and
`calibration.py` (sentinel + param + injection + column block + reader block
+ loader + threading at 2 sites + calibration threading).

## Inventory of remaining bespoke channels

Measured references across the three files (2026-07-15):

| channel | shape | refs | status |
|---|---|---|---|
| `bps_data` (building permits) | `{geoid: {year: val}}` | ~39 | **bespoke** — candidate |
| `saipe_data` (county poverty) | `{geoid: {year: val}}` | ~40 | **bespoke** — candidate |
| `laus_data` (county unemployment) | `{geoid: {year: val}}` | ~40 | **bespoke** — candidate |
| `market_data` (screen-gated momenta) | `{name: {year: val}}` | ~30 | **half-generic** — injection is generic, reader hardcoded |
| `national_data` (national macro) | `{name: {year: val}}` | — | ✅ registry (14 series) |

Already registry/spec-driven elsewhere (no work needed): the anchor registry
(`_REGISTRY_SPEC`), `BEA_ANCHOR_SPECS`, the BLS panel area×kind grid,
`markets/universe.TICKERS`, and the screen's `MONTHLY_TARGETS` /
`NATIONAL_PREDICTORS` / `HYPOTHESIS_PAIRS`.

## Candidate 1 — county-level registry (`bps`/`saipe`/`laus`) — RECOMMENDED

The three county channels are structurally identical: per-geoid annual
values feeding a lag0/lag1/lag2 + 3yr-mean column block (BPS log-scales
first). A `COUNTY_SERIES` registry needs exactly **two column policies**:

- `log_lags3_mean` (BPS): log-transformed lag0/1/2 + mean of valid lags
- `level_lags3_mean` (SAIPE, LAUS): raw lag0/1/2 + mean of valid lags

Migration would collapse three params → one `county_data:
{name: {geoid: {year: val}}}` param, three loaders → one registry-driven
loader, three reader blocks → one loop. **The same equivalence discipline as
the natl_unemp migration applies**: policies must reproduce the existing
column names and values exactly (they can — the blocks are already uniform),
so the shipped BPS ablation (`phase_c_bps_ablation.md`) stays valid, verified
by an equivalence test + a re-run ablation.

Effort: comparable to the natl_unemp migration (~1 session). Risk: low with
the exact-equivalence approach; the column-order regression test already
guards the layout. Payoff: ~120 scattered references become ~30, and any
future county-level indicator (e.g. county building costs, migration flows)
becomes a one-line registry entry.

## Candidate 2 — market channel reader — OPTIONAL, LOWER PRIORITY

`market_data` injection is already generic, but the reader hardcodes the
three channel sentinels into four `mkt_*` columns. Folding the channels into
a registry (source `MARKET_SIGNALS`, policies `level1` / `level_lag1`) is a
small win (4 columns) and slightly awkward: market channels are
**screen-gated** — they appear/disappear with `selected_signals.json` — so
their spec is dynamic where the registry is static. Recommendation: leave
as-is unless the screen grows more channels; the mkt block is small and
stable.

## Not candidates

- `tax_modeler` growth-rate blending — different package, different pattern.
- The anchor registry — already the repo's original registry precedent.
- Kalman / projection internals — cherry-picked by
  Housing-Affordability-Tracker; do not touch for cosmetic reasons.

## Suggested order

1. County registry (candidate 1) as its own PR with equivalence tests +
   BPS ablation re-run.
2. Revisit the market reader (candidate 2) only if a future screen run
   promotes new channels.
