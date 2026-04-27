# Methodology

This document records the non-obvious design choices in Census Forecaster
that aren't fully captured by source-code docstrings. It supplements
(not replaces) the README and module docstrings.

---

## v3 stratified calibration (April 2026)

The v3 calibration layer extends v2 along three axes: population
stratification, multi-horizon evaluation, and geometric bias correction.
The motivation for each, the parameter choices, and the fallback
behavior are below.

### 1. Population stratification

**Why stratify by population at all?** Counties differ enormously in
ACS sample sizes — Honolulu (1M people) gets thousands of survey
responses per year; rural counties under 50K get a few hundred. The
sampling-error component of forecast SE scales with the inverse square
root of sample size, so a single global SE inflator κ either overcalibrates
the noisy small-county tail or undercalibrates the precise large-county
head. Stratifying lets each population bucket receive its own κ.

**Bucket boundaries** are based on 2020 ACS B01003_001E (5-year vintage):

| Bucket | Range | Approximate count (US counties) |
|---|---|---|
| `small`  | < 50K            | ~1,800 |
| `medium` | 50K–200K          | ~700 |
| `large`  | 200K–1M           | ~280 |
| `xlarge` | ≥ 1M              | ~50 |

Boundaries are coarse (4 levels) to keep cells statistically reliable on
the ~150-county v3 calibration panel. Finer buckets (e.g. octiles) would
fragment the small-county tail below n=20.

**Frozen at 2020.** Bucket assignments are computed once per calibration
vintage and don't drift between runs. Re-running the build script with
the same seed produces identical bucket assignments. When the 2030 ACS
becomes the dominant vintage, re-freeze.

Why frozen rather than year-by-year: bucket-shifting would create a
moving-target stratification — a county that grew from medium to large
between 2015 and 2024 would appear in different cells across folds,
contaminating per-cell calibration.

### 2. Horizon stratification

Exponential smoothing models systematically under-cover at longer
horizons because the variance formula compounds smoothing-noise across
steps. A single κ calibrated at h=2 over-widens 1-year forecasts and
still under-widens 5-year ones.

**Bucket scheme: 2 levels.**

| Bucket | Horizons |
|---|---|
| `short` | h ∈ {1, 2} |
| `long`  | h ∈ {3, 4, 5} |

A 3-bucket scheme (medium = {3, 4}) was considered but fragments
`(small × long)` cells below n≈30 once 2020-1y-ACS holes are accounted
for. 2-bucket retains the dominant horizon-coverage signal — κ at
`long` is materially larger than at `short` — without overfitting.

The h-bucket assignment includes clamping: horizons beyond the longest
defined bucket clamp to `long` so extrapolation stays well-defined.
Horizons ≤ 0 (passthrough projections, target ≤ anchor) skip the bucket
classification entirely; the lookup falls through to the
globally-marginalised cell.

### 3. Geometric bias correction

**Formulation.** For each calibration cell, compute
`b = mean(log(point_raw / actual))`. Apply
`point_corrected = point_raw / exp(b)`. SE components and CI bounds
rescale by the same factor (in log-space, a level shift is multiplicative
on dollar-space SEs by the delta method).

**Why geometric, not arithmetic.** ACS dollar series grow multiplicatively
(income, rent, value all compound). Arithmetic bias correction
(`point − b̂`) doesn't generalize cleanly across counties of different
magnitudes — a $2K bias is a different fraction at $50K vs $500K.
Geometric correction handles all magnitudes uniformly.

**Clamp: ±10% multiplicative.** The applied bias is clamped to
`[log(0.9), log(1.10)]` — i.e. the multiplicative correction stays
within ±10%. Larger bias estimates almost always indicate panel
contamination (pathological growth in the synthetic data, suspended
1-year ACS revisions, or unrepresentative sampling) rather than
genuine systematic miscalibration. Clamping is the safety net.

The unclamped bias is preserved in the `extra["b_raw"]` field of each
calibration record so an analyst can identify which cells hit the clamp
and investigate.

**n-threshold: n ≥ 20 folds.** Bias and κ are gated at this minimum
fold count. Below n=20, the cell receives no calibrated correction
(b=0, κ=base_inflator); the consumer's fallback chain finds a
more-aggregated cell instead.

The 20-fold threshold derives from the standard error on a binomial
coverage estimator: at n=20, SE on a 90% coverage probability is
sqrt(0.9 × 0.1 / 20) ≈ 6.7%. Smaller n produces coverage estimates
with SEs comparable to or larger than the in-band tolerance (90% ±
5pp = ±5 percentage points), at which point κ calibration is fitting
noise. A tighter threshold (n=50) would reject too many small-county
cells; looser (n=10) admits noise.

### 4. Order of operations

**Bias first, then κ.** During calibration the order is fixed:

1. Pass A: estimate `b` per cell from raw fold residuals.
2. Pass A.5: apply bias to fold residuals in memory
   (`point' = point / exp(b)`).
3. Pass B: bisect κ per cell against the **bias-corrected** residuals
   to bring CI90 coverage into [85%, 95%].

Reversing the order would double-count level miscalibration in the κ
because the bisection's residual variance estimate would include both
random forecast error and the systematic bias.

Consumers must follow the same order: `_apply_bias_correction` first,
then `_apply_se_override`. Both are applied **pre-blend** to each
component (`trend_ensemble`, `multi_anchor`) — the v3 calibration
records are keyed by component method, not by the blended
`ensemble_multi_anchor` label.

### 5. Fallback chain

The lookup for both `b` and κ walks four levels. At each level, a
strata record is *qualified* if its `n_folds ≥ n_threshold`:

1. **Exact cell** `(indicator, method, pop_bucket, h_bucket)`.
2. **h-marginalised cell** `(indicator, method, pop_bucket, "*")`.
3. **Globally marginalised cell** `(indicator, method, "*", "*")`.
4. **v2 single-key fallback** `se_inflator_override_by_indicator_method[indicator][method]`.
5. **Floor**: κ = `EMPIRICAL_SE_INFLATOR` (1.30) or `b = 0`.

The "*" sentinel marks records pre-aggregated by the calibration
generator (the marginalisation isn't computed at lookup time, keeping
lookups O(1)). Records with insufficient n are *kept* in the index
but skipped at lookup time — diagnostic round-trips stay lossless.

### 6. Computational note

The v3 calibration replaces the v2 verify-pass approach (re-projecting
the entire panel inside the bisection iteration) with **cached fold
residuals**. The bisection applies a multiplicative SE factor to the
cached `(point, se_total, ci_low, ci_high)` tuples directly,
recomputing coverage in O(folds) per iteration without re-running any
projection model.

On the multi-state, 5-horizon panel (~50K folds across ~96 cells), this
is roughly 100× faster than the v2 approach. The bisection runs in
milliseconds per cell; total calibration runtime is dominated by the
initial Pass-2 fold construction, not by the iterative override search.

### 8. Multi-state calibration panel (April 2026)

The v3 ACS calibration now runs on a **147-county, 8-indicator, 15-year
panel** rather than the original 4-county Hawaii fixture.

**Panel composition (seed=42, frozen):**

| Bucket | Selection | Count |
|---|---|---|
| `xlarge` (≥ 1M) | Top 50 US counties by 2020 population, deterministic | 50 |
| `medium` (50K–200K) | Random sample, seed-stable | 50 |
| `small` (<50K) | Random sample, seed-stable | 50 |
| Hawaii always-include | 15001 / 15003 / 15007 / 15009 | 4 (overlap with above) |

Total: 147 distinct counties across 35 states. The `large` bucket (200K–1M)
is not sampled separately — it receives counties that naturally land there
(Honolulu 15003, plus any xlarge-overflow).

**Indicators (v0.4 expands to 13):**

| Code | Description | Table type |
|---|---|---|
| `B19013_001E` | Median household income | Detail (B*) |
| `B25058_001E` | Median contract rent | Detail |
| `B25064_001E` | Median gross rent | Detail |
| `B25077_001E` | Median home value | Detail |
| `B25071_001E` | Median gross rent as % of household income | Detail |
| `B20002_001E` | Median earnings for workers 16+ | Detail |
| `B01002_001E` | Median age | Detail |
| `S1501_C02_014E` | % age 25+ with HS diploma or higher | Subject (S*) |
| `S1501_C02_015E` | % age 25+ with bachelor's or higher | Subject |
| `S1701_C03_001E` | % below poverty (all people) | Subject |
| `S2301_C04_001E` | Unemployment rate (%) | Subject |
| `homeownership_rate` | Owner-occupied / total occupied units | Derived (B25003) |
| `vacancy_rate` | Vacant / total housing units | Derived (B25002) |

Subject-table indicators use the `/acs/acs1/subject` Census API endpoint.
The `AcsClient` routes automatically based on the `S`-prefix. Derived
indicators are computed post-fetch as numerator ÷ denominator (see
`scripts/build_calibration_panel.py::DERIVED_INDICATORS`).

**Note on `S0101_C02_030E` (% population 65+):** This code was tested but
rejected — the Census S-table schema was restructured around 2016–2018 and
the column assignment for C02/row 30 changed between vintages, producing
~35–40% values pre-2019 vs. correct ~18–22% values post-2019. `B01002_001E`
(median age) is the stable B-table substitute with the same demographic
signal and no structural break.

**Observed κ values from the multi-state calibration (anchors 2014–2022):**

| Indicator / method | κ range | CI90 coverage |
|---|---|---|
| Income (`B19013`) / trend_ensemble | 1.01–1.30 | 90.5% |
| Income (`B19013`) / multi_anchor | 0.35–1.30 | 97.7% |
| Worker earnings (`B20002`) / trend_ensemble | — | 90.3% |
| Rent (`B25058`, `B25064`) / trend_ensemble | **1.30–2.60** | 82–84% |
| Rent (`B25058`, `B25064`) / multi_anchor | 0.42–1.30 | 98–99% |
| Home value (`B25077`) / trend_ensemble | 1.30–1.95 | 89.9% |
| Median age (`B01002`) / trend_ensemble | — | 87.5% |
| HS+ % / trend_ensemble | 0.72–1.30 | 94.9% |
| BA+ % / trend_ensemble | 0.72–1.30 | 96.0% |
| Poverty % / trend_ensemble | 1.01–1.95 | 88.9% |
| Unemployment (`S2301`) / trend_ensemble | — | **79.7%** |
| Homeownership rate / trend_ensemble | — | 88.7% |
| Vacancy rate / trend_ensemble | — | 84.6% |

Key patterns:
- **Rent is the most uncertain series** — trend_ensemble κ up to 2.60 on
  long-horizon, small-county cells (heterogeneous rent dynamics nationwide).
- **Multi-anchor CIs are inherently conservative** — bisection correctly
  deflates κ below 1.0 for income/rent/home-value multi_anchor cells.
  The model's blended uncertainty already exceeds actual error.
- **Educational attainment is stable** — κ < 1 on some cells; near-zero
  bias; series is well-specified by the trend model alone.
- **Unemployment is under-covered at 79.7%.** This is a known model
  misspecification, not a data issue. Unemployment is mean-reverting
  (3%→15%→3% over a recession cycle) whereas the trend model assumes
  continuity. Even with the bisected κ applied, the CI *shape* is wrong
  for recession shocks — no multiplier can make a Gaussian interval capture
  a sudden spike. For applications that require calibrated unemployment
  uncertainty, a dedicated mean-reversion model (AR(1) toward a long-run
  mean) would be appropriate. For the current use case — contextual signal
  in housing affordability tracking — the point estimate is reliable and
  the under-coverage is acceptable.

**Observed bias values (post-clamp, expressed as % level shift):**

| Indicator | Typical bias | Interpretation |
|---|---|---|
| Dollar series (income, rent, value) | −7% to −9% | Model under-projected the 2020–2022 inflation surge |
| Poverty rate / multi_anchor | +6% to +10% | Model over-predicted poverty reduction from income growth |
| Education attainment | −0.5% to +4% | Essentially unbiased |

The negative bias on dollar series is systematic: the pre-2023 anchor
sources (CPI, QCEW, PCE) didn't anticipate the post-COVID inflation spike,
so the ensemble consistently projected below actual. Bias correction shifts
all dollar forecasts up ~7–9%, reducing the systematic over-optimism.

**Rebuilding the panel:**

```bash
CENSUS_API_KEY=<key> python3 -m census_forecaster.scripts.build_calibration_panel
python3 -m census_forecaster.scripts.run_acs_calibration
```

The panel build issues ~3,050 Census API calls (~5–10 minutes with a key).
The calibration regeneration reads the bundled panel and needs no key
(~30 seconds). Both are idempotent.

### 7. 2020 1-year ACS hole

The 2020 1-year ACS was suspended due to COVID-19 data quality issues.
Folds whose target year would be 2020 (e.g. anchor=2018 with h=2;
anchor=2015 with h=5) are dropped silently by the calibration generator.
This means cells in the `long` horizon bucket have systematically fewer
folds than `short` cells in any vintage that spans 2020 — a confound
between the bucket variable and the data-availability structure. Track
per-cell `n_folds` carefully when interpreting calibration output;
the manifest exposes counts at all granularities.

---

---

## v3 stratified calibration — BLS side (April 2026)

The BLS CPI projection layer received the same stratification treatment
as ACS, with three structural differences reflecting the different
data geometry.

### 1. Three-axis stratification

ACS uses (indicator, method, pop_bucket, h_bucket). BLS uses
**(series_id, h_bucket, vol_regime)**:

* `series_id` — the BLS series (e.g. `CUURS49ASA0`, `CUUR0000SEHA`).
* `h_bucket` — `short` for h ∈ {1–5} months, `long` for h ∈ {6+} months.
* `vol_regime` — `low` if the rolling 24-month return SD ≤ per-series
  median; `high` otherwise.

The volatility regime axis captures the 2021–2023 inflation spike vs
the 2010s calm period. Rent CPI's median 24-month SD is ~0.001/mo;
gasoline's is ~0.05/mo (50× larger). A single κ over both regimes
either over-pads the calm or under-pads the spike.

### 2. Log-space CI rescaling

ACS rescales SE in dollar space (`new_half = factor × old_half`). BLS
rescales SE in **log space** because the projection is log-space
multiplicative:

```
CI_new = point × exp(±Z · factor · SE_log)
```

This matters for the bisection: changing `factor` produces a
**multiplicative** widening/narrowing of the CI, not additive. The
shared bisection algorithm in `acs/calibration_common.py` is
parameterised over a `coverage_fn(factor)` so both modules use the same
search procedure.

### 3. Multi-MSA panel

The v2 calibration ran on 5 Honolulu series. v3 runs on **55 series**:
11 areas (national + Honolulu + 9 top-population MSAs) × 5 CPI
subindexes (all-items, food-at-home, rent, housing, gasoline). The
panel is bundled at `data/bls_panel/cpi_panel.json` (~750 KB) and
refreshed via `python -m census_forecaster.scripts.refresh_bls_panel`
with a `BLS_API_KEY`.

Empirical κ values from the v3 calibration on this panel:

| Cell | Approx. κ |
|---|---:|
| Rent, short horizon, low vol | 1.5 |
| Rent, long horizon, low vol | 3.0 |
| All-items, long, low | 2.0–3.0 |
| Housing, long, high vol | 4.0 |
| Gasoline, short | 1.5–2.0 |
| Gasoline, long | 2.0 |

The legacy global κ=1.50 was severely under-padding long-horizon CIs
(true κ at h=long is 2.0–4.0 across most series) and modestly
over-padding short-horizon rent (κ at h=short for rent is 1.5).

### 4. BEA anchor integration

The macro-anchor pool gained three BEA Regional series in v3:

| File | BEA Identifier | Anchors |
|---|---|---|
| `bea_hi_percapita_income.json` | SAINC1 LineCode=3, GeoFips=15000 | B19013, S1701 |
| `bea_honolulu_rpp_all.json` | MARPP LineCode=1, GeoFips=46520 | B19013 |
| `bea_hi_rpp_housing.json` | SARPP LineCode=3, GeoFips=15000 | B25058, B25064 |

After registration, `B19013_001E` has 5 anchor sources (was 3); rent
indicators have 3 (was 2); poverty rate (`S1701_C03_001E`) has its
first anchor (was 0).

On the Hawaii calibration, BEA per-capita personal income gets the
**highest weight** in the income anchor ensemble (~25%), beating QCEW
wages (~23%), the Cleveland Fed-style CPI all-items (~19%), the PCE
deflator (~19%), and Honolulu metro RPP (~13%).

### Auto-refresh

A monthly GitHub Actions workflow (`.github/workflows/refresh-data.yml`)
re-fetches the BLS panel, BEA anchors, and regenerates both the BLS v3
and ACS v3 calibrations. The workflow auto-commits with `[skip ci]`
so the test workflow doesn't recurse on data-only changes. The ACS
calibration regeneration reads the already-bundled panel and needs no
`CENSUS_API_KEY` — only the BLS/BEA refresh steps need their respective
secrets.

---

## Backwards compatibility

A v2 calibration payload (no `strata_records` key) loads and runs
through every v3-aware consumer unchanged. The legacy single-key
`se_inflator_override_by_indicator_method` lookup is the v2 fallback at
level 4 of the chain; bias correction is a no-op when no strata records
are present.

The v3 generator additionally writes marginalised v2-style tables at
the top level of the JSON payload (`rmse_by_indicator_method`,
`ci90_coverage_by_indicator_method`, etc.) so any v2-only consumer
sees exactly the keys it expects.

---

## References

* **Damped trend, ETS variance:** Hyndman, R., Koehler, A., Ord, J.,
  Snyder, R. (2008). *Forecasting with Exponential Smoothing: The State
  Space Approach.* Springer.
* **Small-area discipline:** Wilson, T., Grossman, I., Alexander, M.,
  et al. (2021). "Methods for Small Area Population Forecasts: State
  of the Art." *Population Research and Policy Review.*
* **Inverse-variance combination:** Granger, C., Ramanathan, R. (1984).
  "Improved methods of combining forecasts." *Journal of Forecasting.*
* **Bates-Granger optimal weight:** Bates, J., Granger, C. (1969). "The
  combination of forecasts." *OR Quarterly.*
* **Multi-model ensemble correlation:** Tebaldi, C., Knutti, R. (2007).
  "The use of the multi-model ensemble in probabilistic climate
  projections." *Phil. Trans. R. Soc. A.*
* **ACS MOE conversions:** US Census Bureau (2018). "ACS General
  Handbook, Chapter 8: Calculating Measures of Error for Derived
  Estimates."
* **Cleveland Fed rent blending:** Adams, B., Hertz, B., Verbrugge, R.
  (2022). "New-Tenant Repeat Rent Inflation." *Cleveland Fed
  Working Paper 22-38r.*
