# data/markets — bundled market time series

Written by `python -m census_forecaster.scripts.refresh_market_panel`
(monthly via the `refresh-data` workflow; keyless except the BLS
unemployment block).

## Files

- **`prices_panel.json`** — monthly adjusted closes for the pre-registered
  ticker universe (`markets/universe.py`; 12 tickers across broad/sector/
  hawaii tiers — ALEX was dropped: delisted 2026-03 via take-private). Schema mirrors `data/bls_panel/cpi_panel.json`:
  `{version, fetch_date, start_year, n_series, series: {SYMBOL: [{year,
  period: "Mxx", adj_close, volume}]}, provenance, limitations}`.
- **`manifest.json`** — per-ticker coverage summary (first/last month,
  n_obs, source, tier, hypothesis).
- **`macro_monthly.json`** — monthly macro screen targets:
  `LNS14000000` (national unemployment, CPS SA), `LASST150000000000003`
  (Hawaii statewide unemployment, LAUS SA), `ZHVI_HONOLULU_MONTHLY`,
  `ZORI_HONOLULU_MONTHLY`. Schema: `{version, fetch_date, series:
  {NAME: [{year, period, value}]}, sources, limitations}`.
- **`selected_signals.json`** — (Phase 2) machine-readable output of the
  market-signal causal screen; absent until the first screen run.

## Sources & caveats

- Prices: **yfinance** (unofficial Yahoo scraper, splits+dividends
  adjusted) when installed, else **Stooq** public CSV (split-adjusted
  only). Provenance is recorded per symbol; `+stale` marks a series
  carried forward from the previous commit after a fetch failure.
- The incomplete current calendar month is always dropped at fetch time.
- Prices are market-sentiment-laden; nothing in this directory is a
  causal claim. See the market-signal screen limitations
  (`METHODOLOGY.md` §Market signals) before interpreting.

The annual-aggregated national unemployment anchor derived from
`LNS14000000` lands in `../anchors/bls_national_unemployment.json`
(inert until registered in `_REGISTRY_SPEC`, Phase 3).
