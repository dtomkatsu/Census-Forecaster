# TY 2025 projection — notes

## Source

`scripts/eitc_ctc_geo_report.py --tax-year 2025 --apply-takeup`
on Hawaii ACS PUMS 5-year (2018–2022, FIPS 15). Income projected forward
to 2025 via `project_tax_units_forward` (county-specific B19013 growth +
chained-CPI on credit parameters). Year-specific EITC/CTC params come from
IRS Rev. Proc. 2024-40 (TY 2025).

## State totals

| Metric                | TY 2022    | TY 2025    | Δ       |
|-----------------------|------------|------------|---------|
| Weighted filers       | 810,152    | 810,152    | (fixed) |
| EITC claimants        | 84,063     | 84,018     | -0.1%   |
| EITC dollars          | $124.3M    | $166.4M    | +33.8%  |
| HI EITC dollars (40%) | $50.1M     | $67.9M     | +35.5%  |
| CTC claimants         | 186,157    | 186,034    | -0.1%   |
| CTC dollars (total)   | $670.1M    | $669.1M    | -0.1%   |
| Refundable CTC (ACTC) | $247.1M    | $279.2M    | +13.0%  |

**EITC** grew 34% because TY 2025 maxima (`$649 / $4,328 / $7,152 / $8,046`
for 0/1/2/3+ kids per Rev. Proc. 2024-40) are well above TY 2022 maxima
(`$560 / $3,733 / $6,164 / $6,935` per Rev. Proc. 2021-45), and the
phase-out thresholds also move upward with chained CPI. Earned-income
levels are projected forward via B19013 county growth rates.

**ACTC** grew 13% because the per-child refundable cap moved from $1,500
(TY 2022) → $1,700 (TY 2025). Total CTC is flat because TCJA's $2,000/child
non-refundable headline number didn't change.

**HI state EITC** scales linearly off federal (40% per HRS §235-55.75).

## Geographic coverage

Same caveats as TY 2022 backtest — see `../eitc_ctc_2022_backtest/NOTES.md`
for PUMS→district hashing notes. Same modeling caveats on
CTC over-counting (synthetic age=10 dependents) also apply.

## Caveats

The TY 2025 EITC dollar gap vs IRS administrative records is expected to
be of similar magnitude to TY 2022 (~33% low), since the upstream PUMS
microsim issues (synthetic dependent ages, earned-income coverage) carry
forward. The TY 2022 backtest establishes the calibration ceiling for
relative-change analysis.
