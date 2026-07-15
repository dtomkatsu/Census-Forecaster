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

---

### 8. v4 phi calibration — implementation and null result (May 2026)

**What was built.** The v4 calibration layer adds a Pass 0 that derives a
per-cell damping constant (phi) from the ACS series' own margin-of-error
data, rather than using the global default `phi=0.85` everywhere. The idea:
counties with high sampling noise relative to real economic signal should be
damped more aggressively; precise large counties less so.

Noise/signal is estimated by decomposing the observed year-over-year variance
into a sampling component (derived from published ACS MOEs via
`SE = MOE / 1.645`, then `var_sampling ≈ SE_log(t)² + SE_log(t-1)²`) and a
residual signal component (`var_signal = max(0, var_total − var_sampling)`).
The noise share maps to phi via an affine function bounded in `[0.70, 0.95]`:
`phi = 0.70 + 0.25 × noise_share`.

Published ACS MOEs are used rather than PUMS replicate weights — they are
mathematically equivalent (Census Bureau computes MOEs internally from the
same 80 replicates) and avoid a 16+ hour data fetch for a 50-state panel.

**Walk-forward evaluation.** A held-out ablation was run on the 147-county
multi-state panel: train on anchors 2014–2020, evaluate on 2021–2022,
h ∈ {1, 2, 3}. Results:

| Metric | v3 (φ = 0.85) | v4 (per-cell φ) |
|---|---|---|
| Median MAPE | 5.59% | 5.64% |
| Any CI90 coverage < 80% | no | no |

Acceptance bar (median MAPE drop ≥ 3% relative) was not met.

**Why phi doesn't help at short horizons.** The damped trend model uses phi
to shrink the trend component toward zero over time: the trend contribution
at horizon h scales as `Σᵢ₌₁ʰ φⁱ`. At h = 1–3, the level component
dominates the forecast and the trend's cumulative contribution is small.
Varying phi in `[0.70, 0.95]` changes that contribution by less than 25%,
which is not enough to move MAPE materially. The calibrated phi values
further clustered near the default (median = 0.87, stdev = 0.07), so most
cells were already close to `phi = 0.85` anyway.

Phi would become a meaningful lever at h = 4–5, where the trend compounds
across more steps and damping choices diverge. The current primary use case
(revenue forecasting at 1–3 year horizons) sits in the insensitive range.

**Status.** The phi infrastructure is implemented and ships in v4
(`acs/acs_volatility.py`, Pass 0 in `acs/calibration.py`, `_lookup_phi` in
`acs/ensemble.py`). It is included in the calibration output but has no
practical effect at h ≤ 3. It is **not the default** — the bundled
calibration index remains v3. Re-enable and re-evaluate if longer-horizon
forecasting becomes a requirement.

### 9. 2020 1-year ACS hole

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

## Cross-county ML trend (experimental, April 2026)

The ACS forecaster ships an optional third ensemble member —
`ml_trend` — alongside the classical `trend_ensemble` (damped log trend
+ AR(1)) and the multi-source `multi_anchor`. It is **opt-in** via
`project_ensemble_multi(..., use_ml=True, ml_series_by_key=...,
ml_populations=...)` and is not on the default projection path.

### Why ML, why now

The classical trend models operate on a single (geoid, indicator) series
in isolation. With the multi-state calibration panel (147 counties × 16
indicators × 15 years = 19,638 observations) we now have enough cross-
county and cross-indicator structure for a tree-based learner to add
signal the per-series models cannot see — county-size effects, regional
patterns, and cross-indicator dependencies (e.g. rent ↔ wages,
unemployment ↔ educational attainment).

### Architecture

`ml_trend` is sklearn's `HistGradientBoostingRegressor` (histogram-based
gradient boosting, same algorithmic family as LightGBM but bundled in
sklearn so no libomp/OpenMP runtime dependency). One model is trained
per `(indicator, cutoff_year)`; cutoff_year defaults to the most recent
observed year. Features per row:

* Lagged target levels in log space at anchor, anchor-1, anchor-2.
* YoY log-growth diffs and 3-yr trailing mean diff.
* County metadata: log 2020 population, pop-bucket one-hot, state FIPS.
* **Cross-indicator panel**: same county's log values for every *other*
  indicator at the anchor year (15 columns). This is the genuinely new
  signal not exposed to the classical models or the macro anchor.
* Horizon as a feature (h ∈ 1..5) so a single model serves all horizons
  per indicator.

Target: `log(y[target_year] / y[anchor_year])` — log-growth from anchor.
Walk-forward training filter: `target_year ≤ cutoff_year` strictly,
matching the back-test discipline used elsewhere in this package.

### Ensemble integration

When `use_ml=True`, the combiner uses a two-stage Bates-Granger:

1. **Inner (target-side)**: `trend_ensemble` + `ml_trend` at ρ=0.7 (both
   consume the same series so high correlation is appropriate).
2. **Outer (target vs macro)**: inner + `multi_anchor` at ρ=0.5,
   blended at the calibrated `_calibrated_macro_weight` per indicator.

Each member is bias-corrected and SE-overridden via the v3 stratified
κ table before combination — the same pre-blend correction order used
for the existing two-member ensemble.

### Walk-forward ablation (April 2026 panel)

Run on the bundled 147-county / 16-indicator panel, anchors 2014-2022,
horizons 1-5. Both calibrations apply v3 bias + κ corrections to each
member before combining; the ensemble metrics below are
production-equivalent.

| Indicator | RMSE Δ | Cov90 (no-ml → with-ml) |
|---|---:|:---:|
| B19013_001E (median income) | -5.0% | 88.9% → 88.9% |
| B25058_001E (median rent, contract) | -5.8% | 86.2% → 85.0% |
| B25064_001E (gross rent) | -5.7% | 87.4% → 86.3% |
| B25077_001E (median home value) | -4.7% | 88.7% → 87.5% |
| B20002_001E (worker earnings) | -10.7% | 89.1% → 88.3% |
| B01002_001E (median age) | -16.3% | 91.0% → 88.6% |
| S1501 (BA+, HS+) | -25.5% / -17.1% | 91% → 88-90% |
| S1701 (poverty rate) | -5.3% | 86.3% → 85.6% |
| homeownership_rate | -18.1% | 88.7% → 87.4% |
| in_migration_rate | -20.9% | 92.8% → 90.4% |
| pct_professional, pct_service | -16% / -12% | 91-92% → 89-90% |
| vacancy_rate | -10.6% | 92.2% → 88.0% |

Point accuracy improves on every indicator (5-25% RMSE drop). The
stand-alone `ml_trend` method has CI90 coverage of 89-94% on all 16
indicators — the model itself is well-calibrated.

### Why opt-in (not default)

After v3 calibration the ensemble-level CI90 coverage with ml_trend is
85-90% on every indicator, with one indicator (B25058) at exactly 85.0%
(below the lower bound by less than 1 fold out of 2,984). The classical
ensemble's coverage is uniformly 86-93% — slightly more conservative.
The conservative call is to ship the ML member as opt-in until we have
either:

1. A "ensemble_with_ml"-level κ stratum in the v3 calibration (so the
   joint CI gets its own bisection-on-coverage rather than relying on
   the per-method κ to compose well under inverse-variance combination), or
2. A cross-correlation parameter sweep showing ρ values that put the
   ensemble coverage uniformly inside [85%, 95%].

Both are mechanical follow-ups; the ML implementation itself is
production-ready and tested.

### How to enable

```python
from census_forecaster.acs import project_ensemble_multi, build_panel_index
from census_forecaster.scripts.load_calibration_panel import load_panel

series, populations, _ = load_panel()
panel = build_panel_index(series)
ml_cache: dict = {}  # reuse across many forecasts at same cutoff

fp = project_ensemble_multi(
    series_observations=obs_for_one_county_indicator,
    target_year=2026,
    populations=populations,
    use_ml=True,
    ml_series_by_key=series,
    ml_populations=populations,
    ml_model_cache=ml_cache,
    ml_panel=panel,
)
```

The training cost is ~2 seconds per `(indicator, cutoff_year)` model
fit; the cache amortises that across many forecasts at the same cutoff.

### Reproducing the ablation

```bash
python -m census_forecaster.scripts.compare_ml_ablation --output report.md
```

Runs the v3 calibration twice (with `include_ml=True` and `False`),
applies v3 corrections to each method's residuals, synthesises the
two-stage ensemble, and writes a per-indicator comparison table. Total
runtime: ~6-8 minutes (the ML half adds ~5 min of HGB training).

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

## Federal EITC / CTC by geography (May 2026)

Year-keyed federal credit calculators (`tax_modeler.credits.eitc`,
`tax_modeler.credits.ctc`) carry IRS Rev. Proc. parameters for TY
2022 → TY 2025 — max-credit, phase-in completion income, single-
and joint-filer phaseout starts, ACTC refundable cap. Statutory rates
(phase-in / phase-out percentages, $200K/$400K phaseout thresholds,
$2,000/child max under TCJA) do not move year-to-year and live in
shared constants.

### Parameter vintages

| Year | EITC max (2 kids) | ACTC refundable cap | IRS Rev. Proc. |
|-----:|------------------:|--------------------:|----------------|
| 2022 |           $6,164 |              $1,500 |        2021-45 |
| 2023 |           $6,604 |              $1,600 |        2022-38 |
| 2024 |           $6,960 |              $1,700 |        2023-34 |
| 2025 |           $7,152 |              $1,700 |        2024-40 |

`project_tax_units_forward(target_year=Y)` plumbs `Y` into both
`_recalculate_ctc` and `calculate_eitc_for_tax_units` so projected
nominal incomes are credited against `Y`'s statutory parameters
(this matches the IRS chained-CPI inflation-indexing treatment).
For `target_year` beyond the latest published Rev. Proc., the
projector clamps to the most recent supported year and logs the
substitution — older callers projecting to 2026+ continue to work.

### Take-up imputation

Eligibility ≠ claim. PUMS-derived eligible amounts overstate IRS
take-up. The `tax_modeler.pipeline.apply_credit_takeup` helper
(opt-in via `run_pipeline(apply_credit_takeup=True)`) ranks eligible
filers by their eligible credit dollars descending and zeroes credits
on non-claimants until weighted recipient counts match the IRS
state-total benchmark. Anchors (IRS SOI ZIP=00000 row, TY 2022):

* **EITC**: 84,010 returns / $184.7M
* **CTC** (nonref + ACTC): 154,580 returns / $469.5M
* **ACTC alone**: 60,600 returns / $117.8M

The take-up *rate* is treated as behavioral and constant across
forward projection; only the target count is anchored at the 2022
vintage. Re-run when newer IRS SOI Hawaii state-totals publish.

### CBPP comparison caveats

`scripts/eitc_ctc_geo_report.py --compare-cbpp` produces a senate-
district delta table against CBPP table 367 (TY 2022). Two systematic
caveats apply:

1. **Geographic resolution**: CBPP uses IRS SOI ZIP-code claims data
   raked to 2024 SLDs. The modeler uses PUMA-level signal hashed to
   HD/SD via the bundled crosswalk, which preserves PUMA-level
   variance but smears within-PUMA. A future enhancement would
   ingest IRS SOI ZIP data and rake the modeler's LD column to it.
2. **Suppression and AGI<$1**: CBPP suppresses small-cell districts
   and excludes AGI<$1 returns; the modeler does neither. Expect
   some absolute discrepancy on small-population SDs even with
   perfect raking.

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

---

## SPM unit of analysis (Tier 4, May 2026)

The poverty pipeline reports the Supplemental Poverty Measure at the
**SPM-unit** level per Census P60-280, not at the tax-unit level.
Tax-unit-grained calculations remain available for revenue-side
forecasts and for backward-compatibility checks (the
`--by-tax-unit` flag on `scripts/poverty_impact_report.py`).

### SPM unit construction

SPM units are built bottom-up from PUMS persons using the RELSHIPP
relationship-to-householder code:

* **Primary SPM unit per household** (`{SERIALNO}_primary`): the
  householder + all relatives (RELSHIPP 20–30) + unmarried partner
  (33) + foster children (34) + *any unrelated child under 15*
  (RELSHIPP 31, 32, or 35 with AGEP < 15, per the standard P60-280
  exception).
* **Unrelated adult SPM units** (`{SERIALNO}_unrel_{SPORDER}`):
  roomers/boarders/other non-relatives aged 15+ (RELSHIPP 31, 32, 35
  with AGEP ≥ 15) — one one-person SPM unit each.
* **Group quarters** (RELSHIPP 36, 37): excluded from SPM accounting
  entirely (per P60-280; SPM is defined for the household population).

Implementation: `tax_modeler.units.spm_unit_assembly.build_spm_unit_assignment`.

### Tax-unit → SPM-unit aggregation

After all tax/credit/benefit dollars have been computed at tax-unit
granularity (the methodologically correct level for tax-return-based
quantities), the pipeline rolls them up to SPM-unit granularity
before threshold comparison:

* **Sum across tax units in the same SPM unit**: every SPM-resource
  component — `total_cash_income`, `eitc_amount`, `ctc_refundable`,
  `hi_eitc_amount`, all benefit imputations (SNAP, housing subsidy,
  WIC, LIHEAP, CCSP, school lunch), all tax liabilities (federal,
  state, payroll), MOOP, childcare expense, work expense, RxKids
  (if enabled).
* **Representative columns** (constant within a household): SERIALNO,
  PUMA, county, house district, senate district, tenure — taken
  from the highest-income constituent tax unit (deterministic
  tiebreak: lowest filer_id).
* **Composition counts** (`n_adults`, `n_children`, `n_persons`)
  computed from PUMS person ages restricted to members of the SPM
  unit, used both for the threshold lookup and for the
  persons-in-poverty numerator.
* **Weight**: raw household `WGTP` from PUMS, one value per SPM
  unit. The tax-unit hybrid weight (calibrated to DOTAX filer
  totals via per-filing-status multipliers) is dropped because it
  is a tax-filer concept, not a person concept; SPM-unit weighted
  persons hits the ACS person count (~1.3M for Hawaii) directly.

Implementation: `tax_modeler.poverty.spm_aggregation.aggregate_to_spm_units`.

### Threshold lookup

`tax_modeler.poverty.thresholds.threshold_for_units` auto-detects
SPM-unit input via the presence of `n_adults` and `n_children`
columns and uses them directly when present, applying the Betson
(1996) three-parameter equivalence scale to the published Hawaii
2A2C reference threshold. When the composition columns are absent
(tax-unit fallback path used by `forecast_*.py` revenue scripts),
the function derives `n_adults = 1 + (filing_status == MFJ)` and
`n_children = num_dependents` for backward compatibility.

### Result (TY2024, real Hawaii PUMS)

The Tier 4 SPM-unit pipeline produces a baseline rate of **12.43 %**
on real PUMS, matching the upper bound of Census-published Hawaii
SPM (~10–12 %). The Tier 3 tax-unit baseline of 24.62 % was
inflated by the well-known unit-of-analysis bias: multi-tax-unit
households were each scored against single-person thresholds with
only their individual income, missing the resource-pooling that
happens in real households.

### References

* Short, K. (2012). *The Research Supplemental Poverty Measure:
  2010.* Census P60-241.
* Renwick, T., & Fox, L. (2016). *The Supplemental Poverty Measure:
  2015.* Census P60-258.
* US Census Bureau (annual). *The Supplemental Poverty Measure:
  P60-280 series.*

---

## Margin of error on the poverty-impact pipeline

`scripts/poverty_impact_report.py` historically returned point
estimates (`persons_lifted_<scenario>`, `poverty_rate_<scenario>`,
`gap_closed_<scenario>_$`) with no margin of error. Two dominant
sources of uncertainty are now quantified — and reported as
**separate sibling columns** rather than combined in quadrature, so
the source of any uncertainty is legible to reviewers.

### Source 1 — PUMS sampling variance (SDR)

The Census Bureau ships 80 replicate weights with every PUMS vintage
(`PWGTP1`–`PWGTP80` on persons, `WGTP1`–`WGTP80` on households),
generated via the successive-difference perturbation method (Fay's
modified BRR with `k = 0.5`). The standard variance estimator is

    V(θ) = (4 / R) · Σ_{r=1..R} (θ_r − θ_0)²

where θ_0 is the headline estimate on the main weight and θ_r is the
same estimate recomputed under replicate weight r. The leading factor
of 4 comes from `1 / k²` (with `k = 0.5`). `R = 80` is the default;
truncating to fewer replicates inflates the SE estimate and is
intended for smoke testing only.

**Implementation:** `tax_modeler.poverty.impact.compute_poverty_impact_with_se`
wraps the headline function. After computing the main estimate, it
swaps the SPM-unit `weight` column for each `weight_r{01..80}` in
turn and re-runs the `_aggregate` step (NOT the upstream credit
calculation, which is weight-invariant). The function emits
`<col>_se` siblings for every persons-lifted, poverty-rate, and
gap-closed cell on every aggregated DataFrame.

**Calibration interaction.** This codebase calibrates *tax-unit*
weights via IPF in `tax_modeler.calibration.*` to match DOTAX
filer-status totals. The SPM aggregator
(`aggregate_to_spm_units`) discards the calibrated tax-unit weight
and uses raw household `WGTP` for the SPM-unit weight, because
person-level poverty accounting needs a person-grained denominator
that matches the ACS published count (~1.3M for Hawaii). The
replicate weights ride the same raw-WGTP path; *no per-replicate
IPF re-run is performed*. Doing so would multiply runtime by 80×
without changing the SE materially: sampling variance dominates the
residual calibration variance by roughly an order of magnitude on
state-level poverty counts. This is the standard post-calibration
approximation used by ACS estimation guides.

**CLI:** pass `--replicate-weights` (and optionally `--n-replicates N`)
to `scripts/poverty_impact_report.py`. The flag is OFF by default
because the supporting columns (`WGTP1`..`WGTP80`) are not present in
the bundled synthetic fixture; production PUMS parquet/CSV does ship
them.

### Source 2 — Parameter sensitivity sweep

Four parameters in the poverty-impact pipeline are bare scalars in
the codebase but are empirically uncertain:

| Parameter | Default | Low / Mid / High | Empirical anchor |
|---|---|---|---|
| `hi_ctc_takeup_rate` | 0.70 | 0.65 / 0.70 / 0.75 | **Hawaii-empirical**: federal-EITC take-up in HI 2022 = 84,010 admin claims / 120,535 PUMS-eligible filers ≈ 0.697 (±5pp judgment band). See `tax_modeler.calibration.hi_eitc_takeup_estimate` for the SDR-bootstrap variant. |
| `hi_eitc_100pct_takeup_rate` | 0.98 | 0.95 / 0.98 / 1.00 | **Conditional take-up given existing HI EITC claim**. HI EITC auto-computes as fixed percentage of federal on Form N-15 (Act 209, 2023); conditional rate is near-perfect (0.02 captures rare elect-out cases). Composite friction (non-claimers of federal EITC) is upstream in `hi_eitc_amount`. |
| `arpa_ctc_takeup_rate` | 0.94 | 0.92 / 0.94 / 0.95 | **Empirical mean** of Karpman et al. (Urban Institute, 2022) and US Treasury reports on actual ARPA monthly-CTC participation among eligible families. Band: 0.92–0.95. |
| `eitc_poverty_alpha` | 0.5 | 0.3 / 0.5 / 0.7 | Half-elasticity convention from Tax Policy Center / ITEP state models. **Empirical fit attempted (2026-Q2)**: 5-year Hawaii panel (IRS SOI Historic Table 2 TY 2015–2022 + ACS 1-year Honolulu B19013/S1701) yielded α ≈ 0.71 with RMSE 0.03, but n=2 year-pairs after excluding 2019→20 (COVID), 2020→21 (ARPA up), 2021→22 (ARPA expiration). Per-pair α swings −0.43 to 1.01, so the OLS fit is statistically unidentified. Keep 0.5 as production default; 0.71 lies inside the 0.3/0.5/0.7 sweep band so the existing band brackets the empirical range. Module shipped as infrastructure at `tax_modeler.calibration.eitc_alpha_calibration` — re-run after IRS publishes TY 2023 or when pre-2015 IRS files become accessible. |

The per-child HI CTC dollar amount (formerly a swept parameter at
$300 / $650 / $1000) is no longer in the sweep — it is a
**policy-design counterfactual**, not parameter uncertainty.
Different bills ask different things. The pipeline now ships three
named scenarios (`hi_ctc_300`, `hi_ctc_650`, `hi_ctc_1000`) in the
default scenario menu; each gets its own SE and parameter range.
Ad-hoc dollar amounts for amendment analysis are supported via the
scenario name (e.g. `hi_ctc_500`).

#### Policy-choice axes vs parameter uncertainty

We distinguish two stakeholder questions:

* "Given SB 3125 specifies $650, what's the estimated poverty effect
  ± behavioral uncertainty?" — the **parameter MOE**, surfaced in
  `<col>_param_min` / `<col>_param_max` columns.
* "What if SB 3125 had specified $300 instead?" — a **scenario**,
  surfaced as a separate named row (`persons_lifted_hi_ctc_300`).

Mixing the two conflates "uncertainty about the bill as drafted"
with "uncertainty about which bill to draft." Splitting them by
construction tightens the parameter MOE on `persons_lifted_hi_ctc_650`
from ±37 % (when the per-child amount was in the sweep) to ~±10 %.

`scripts/poverty_impact_sweep.py` runs all four parameters in a
one-at-a-time (OAT) sweep around the mid point by default (9 unique
cells after de-duplication of the shared mid-point), or as a full
factorial of 3^4 = 81 cells with `--factorial`. Each cell invokes
`poverty_impact_report.py` in-process via its `main(argv)` entry
point, collates the state-level `by_state.csv` into `summary.csv`,
and emits `param_ranges.csv` (per-column min / max / median across
all cells).

**Merging back into the headline report:** pass `--merge-sweep
<path>/param_ranges.csv` to `poverty_impact_report.py`. Every
`persons_lifted_*` and `poverty_rate_*` column gains three siblings:
`<col>_param_min`, `<col>_param_max`, `<col>_param_median`. These are
populated only for state-level rows; other geographies receive
NaN-filled siblings for schema parity until per-district sweeps land.

### Why separate columns instead of a combined band

Quadrature combination (`SE_total² = SE_sampling² + SE_param²`)
implicitly assumes independence of the two sources, which is not
true here: a take-up rate move correlates with the credit-amount
columns that the replicate-weighted aggregation reads. More
importantly, **decomposition is informative**. A reviewer can see
whether the band around "persons lifted by EITC" is dominated by
sampling (n=80 is a small sub-state count) or by take-up
uncertainty (a policy assumption that future enactment could
verify). A combined headline band would hide that.

A reader who wants a single conservative envelope can take

    headline ± 1.65 · √(_se² + ((_param_max − _param_min) / 3.29)²)

with the caveat that this treats the parameter range as a 90 %
band and assumes the two sources are independent — a defensible
back-of-envelope but not a rigorous CI.

### Federal-tax fallback removal (2026-Q2 hardening)

`compute_spm_resources` previously used a 10 % flat effective rate
on positive money income as a federal-tax stand-in when no
`federal_tax_liability` column was supplied. For SPM-eligible
filers (low income, standard deduction wipes out taxable income),
the true federal liability is typically $0 — the 10 % fallback was
subtracting $1,000–$3,000 of phantom federal tax per return,
biasing the modeled Hawaiʻi SPM poverty rate ~4–6 pp upward.

The fallback is now wired to the real federal-tax calculator at
`tax_modeler.liability.federal.compute_federal_income_tax_for_units`
(TY 2022–2025 brackets + standard deduction per IRS Rev. Procs.).
The 10 % flat path remains only as a last resort when neither the
`federal_tax_liability` column nor a `tax_year` argument is
supplied; it now logs a warning so direct callers know to upgrade.
The `SPMResourceMeta.federal_tax_source` field reports which path
fired (`"column" | "computed" | "fallback_rate" | "zero"`).

### What's still uncalibrated

* **Behavioral response** — `compute_poverty_impact` is a static
  counterfactual. EITC repeal would reduce single-mother LFP by
  2–7 pp per Eissa-Liebman / Meyer-Rosenbaum; no elasticity
  knob is exposed yet. This bounds removal-scenario estimates
  *above* and expansion-scenario estimates *below*.
* **`eitc_poverty_alpha` empirical calibration** — currently a
  literature half-elasticity (0.5); backtest spec documented in
  `adjustments/eitc_poverty_scaling.py`. Deferred pending a
  multi-year ACS S1701 × IRS SOI panel build.
* **HI Renters Credit take-up** — `compute_hi_renters_for_units`
  uses an unanchored 0.30 default. Not currently invoked in the
  poverty-impact pipeline (the `hi_renters_amount` column is not
  populated upstream of `compute_spm_resources` in the report);
  affects only revenue-forecast outputs. TODO to anchor empirically
  is in the credit module's docstring.
* **Replicate-weight propagation through tax-unit constructor**
  (2026-Q2 closed) — `weight_r01..weight_r80` now ride from PUMS
  households → persons → tax units → SPM aggregator via the
  `include_replicate_weights: bool = True` flag on
  `TaxUnitConstructor`. Each replicate inherits the same hybrid-weight
  + per-filing-status calibration formula as the main `weight` column.
  This unlocks the SDR bootstrap on `τ_HI_EITC` at the tax-unit level
  (the `estimate_hi_eitc_takeup` function now returns a real SE
  instead of the 2-replicate judgment band when run post-constructor).
* **HI Renters Credit** (2026-Q2 wired) — `_apply_hi_renters` now runs
  in `scripts/poverty_impact_report.py` after `_apply_hi_eitc`, so
  `hi_renters_amount` flows into `compute_spm_resources` as a positive
  SPM resource. On real Hawaii PUMS 2024, ~15K tax units qualify with
  aggregate disbursement ~$10.7M; SPM rate shifts by <0.1 pp. The
  underlying take-up rate stays at the 0.30 placeholder pending a
  DOTAX caseload pull (documented TODO in `credits/hi_renters.py`).
* **District-level uncertainty** — within-PUMA HD/SD assignment
  is a deterministic SERIALNO hash. The `--rake-to-irs-zip`
  flag is wired but the supporting IRS SOI ZIP + crosswalk data
  is not bundled, so district point estimates carry roughly
  ±20% uncertainty that the SDR SE alone does not capture.
* **SPM threshold MRI / tenure factors** — fixed constants per
  Renwick (2015) / Burns-Fox (2021); not swept.

### CLI quick reference

    # SDR SE only
    python scripts/poverty_impact_report.py --tax-year 2024 \
        --replicate-weights --n-replicates 80 \
        --out reports/poverty_impact_2024_with_se/

    # Sensitivity sweep (OAT)
    python scripts/poverty_impact_sweep.py --tax-year 2024 \
        --out reports/poverty_sweep_2024/

    # Both together: per-cell SDR SE + cross-cell param ranges
    python scripts/poverty_impact_sweep.py --tax-year 2024 \
        --replicate-weights \
        --out reports/poverty_sweep_2024/
    python scripts/poverty_impact_report.py --tax-year 2024 \
        --replicate-weights \
        --merge-sweep reports/poverty_sweep_2024/param_ranges.csv \
        --out reports/poverty_impact_2024_full/

### References

* US Census Bureau (2024). *PUMS Accuracy of the Data (2018–2022)*,
  §3 (Variance Estimation via Replicate Weights). The
  successive-difference replicate-weight construction and the
  `(4 / R) · Σ(θ_r − θ_0)²` formula are documented there.
* Fay, R.E. (1989). *Theory and application of replicate weighting
  for variance calculations.* Proc. ASA Survey Research Methods.
* Eissa, N., & Liebman, J. (1996). *Labor Supply Response to the EITC.*
  Quarterly Journal of Economics 111(2). (Source of the LFP
  elasticity caveat above.)

---

## Market signals (July 2026)

The `census_forecaster.markets` subpackage tracks a pre-registered
universe of 12 exchange-traded securities and screens them as *leading
indicators* for the Hawaii series the forecaster consumes. It is NOT
part of the Housing-Affordability-Tracker cherry-pick.

### Data

Monthly adjusted closes, fetched keylessly (`markets/client.py`):
yfinance when installed → Yahoo v8 chart API via stdlib → Stooq CSV
(Stooq now serves a JS proof-of-work challenge to headless clients, so
the stdlib Yahoo path is the effective fallback). The incomplete
current calendar month is dropped at fetch time. Bundled panels live in
`data/markets/` (schema mirrors `data/bls_panel/`); the refresh script
(`scripts/refresh_market_panel.py`) runs in the monthly `refresh-data`
workflow with keep-last-committed per-ticker failure tolerance.

The universe (`markets/universe.py`) is three tiers — broad (SPY, QQQ,
VTI), sector (JETS, XLRE, VNQ, XLF, XLE), Hawaii-listed (BOH, FHB, HE,
MATX) — each ticker carrying an explicit *hypothesis* naming the
economic mechanism and the ACS cells it plausibly leads. ALEX
(Alexander & Baldwin, the natural B25077 candidate) was taken private
2026-03-12 and free sources purge delisted histories.

### Ticker trend forecasts (`markets/trend.py`)

Tracker-grade context only. Point = damped drift via
`bls.projection.project_forward_full` at the repo's monthly φ=0.92
(§2.3.1 cadence rule — never a new φ). The honest content is the band:
`point × exp(±z·σ_m·√h)` with σ_m the trailing-36-month return SD and
`z` the **empirical** 90% quantile of walk-forward standardised
absolute errors (`calibrate_band_multiplier`) — the direct empirical
analogue of a z-score, per the repo's calibrated-not-analytical PI
discipline. Calibrated multipliers on the real universe land at
1.8–2.6 (vs the Gaussian 1.645): equity returns are fat-tailed and the
calibration prices that in. Equities are near-random-walks; these
forecasts are context for the tracker report, never trading advice and
never census-forecaster inputs.

### Causal screen (`markets/screen.py`)

**Granger causality is not causation** — a pass means the ticker's
past adds predictive content for the target beyond the target's own
past. Confounders survive this screen by design; the Phase-3
forecaster ablation (walk-forward RMSE + CI90 coverage ∈ [85%, 95%])
is the final arbiter of whether a signal touches any forecast.

Design, in the order the guards bind:

1. **Pre-registration.** Only the ticker→target pairs in
   `HYPOTHESIS_PAIRS` (16 pairs derived from the universe's hypothesis
   map) are tested. This caps the multiple-testing burden before any
   data is seen.
2. **Monthly cadence for inference.** Targets: HI/US unemployment
   (levels, first-differenced), Honolulu ZHVI/ZORI (log-differenced),
   Honolulu CPI (bimonthly; differences computed against the nearest
   previous print within 3 months and scaled to per-month rates).
   Annual pairs (ACS anchors, n≈10–15) are reported as descriptive
   lead-lag correlations only, labelled "no test".
3. **Test.** OLS restricted-vs-unrestricted Granger F
   (numpy lstsq + `scipy.stats.f`; statsmodels is not a dependency) on
   monthly log-returns at lags 3/6/12, refused entirely below
   8 observations per parameter. 12-month momentum is screened by
   cross-correlation only — its overlapping windows induce serial
   correlation that invalidates the F-test's residual assumptions.
4. **FDR control.** Benjamini–Hochberg at q=0.10 across ALL Granger
   tests actually run in a screen invocation.
5. **Regime sensitivity.** The screen re-runs with 2020 excluded;
   `selected_signals.json` records `robust_to_2020_exclusion` and the
   review doc shows both tables. A signal that exists only because of
   the COVID crash is a one-event artifact.

Outputs: `backtests/results/market_signal_screen_<date>.md` (human
review is a gate before Phase-3 integration) and
`data/markets/selected_signals.json` (machine-readable survivors).

First run (2026-07-14, unemployment targets pending the CI BLS key):
16 tests, 9 BH passes, 8 robust to 2020 exclusion. The survivors are
the economically prior-backed mechanisms — XLE→Honolulu CPI (imported
energy), MATX→CPI (shipping), XLRE/VNQ→ZHVI/ZORI (forward rent/value
pricing) — which is what a screen behaving honestly should find.

### Known limitations

- Granger ≠ causation (worth stating twice).
- Ticker inceptions truncate samples: JETS/XLRE 2015, FHB 2016,
  ZORI 2015.
- Annual-cadence relationships are structurally untestable at n≈10–15;
  anything cited from the annual table is descriptive.
- National/sector tickers are geoid-constant: in the pooled ML panel
  they act as year-effects and are near-collinear with
  `anchor_year_norm`. The Phase-3 ablation must check permutation
  importance before trusting them.
