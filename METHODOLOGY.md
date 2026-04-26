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
