# Birth-cohort projection back-test — 2026-08-07

Reproduce: `python scripts/backtest_birth_projection.py`

Two rounds ran the same day. Round 1 (7 finals, 6 folds — preserved at the
bottom) picked the projector. Round 2 (below) extended the series to the full
CDC WONDER window (**2007–2024, 18 finals, 46 folds**) and turned the sanity
gate into an actual calibration, deriving the bias and conformal-κ constants
now applied in production.

## Why

The RxKids birth cohort is the least externally-anchored input in the model. It
has no entry in the anchor-source registry, gets none of the v3 bias/κ/conformal
calibration, and its 90% PI had never been coverage-tested. Worse, a direct
`project_kalman` call applies **no empirical SE calibration at all** — the PI is
purely analytical, which the repo's own hard rule forbids quoting
("empirically calibrated 90% PIs via backtest, NOT analytical").

## Round 2 — 46-fold calibration

Expanding-window walk-forward on the NVSR finals (nowcasts are not ground truth
and are excluded), horizons capped at 4 (the 2028 target sits at h=2 from the
last nowcast, h=4 from the last final). Minimum training window 5 finals.

| method | n | MAPE | bias | RMSE | CI90 coverage |
|---|---|---|---|---|---|
| persistence | 46 | 5.18% | +5.14% | 1,018 | — |
| ensemble (legacy) | 46 | 3.43% | +3.12% | 715 | **69.6%** |
| **kalman (default)** | 46 | **3.27%** | **+2.11%** | **658** | 97.8% |

By horizon:

| method | h=1 | h=2 | h=3 | h=4 |
|---|---|---|---|---|
| ensemble MAPE | 1.78% | 2.77% | 3.95% | 5.82% |
| ensemble CI90 cov | 92.3% | 83.3% | 54.5% | **40.0%** |
| kalman MAPE | 1.93% | 2.55% | 3.40% | 5.75% |
| kalman CI90 cov | 92.3% | 100% | 100% | 100% |

The 6-fold round-1 findings replicate with real n: Kalman wins point accuracy,
and the ensemble's interval genuinely collapses with horizon — **40% coverage at
h=4**, the horizon the 2028 target actually sits at from the last final. The
50%-coverage number from round 1 was signal, not small-sample noise.

New finding at n=46: **Kalman's analytical interval over-covers** (97.8%) — too
*wide*, where the ensemble's was too narrow. And both methods carry a
**systematic positive point bias** on this persistently-declining series
(+2.11% pooled for Kalman, monotone in horizon: +0.4% h=1 → +4.2% h=4). The
mechanism is the φ=0.85 damping pulling the growth state toward zero while the
real series keeps declining — the filter under-extrapolates the decline.

## Derived calibration (now applied in production)

Repo-canonical order (see `ensemble.py`): geometric bias correction first, then
the SE calibration on bias-corrected residuals. Pooled across horizons — the
per-horizon cells are n=10–13, below the n≥20 threshold at which the repo's v3
strata machinery trusts a cell.

```
BIRTH_KALMAN_LOG_BIAS = 0.0203     # point × exp(−b) ≈ ×0.9799
BIRTH_KALMAN_SE_KAPPA = 0.862      # half-width = 1.645·κ·se·exp(−b)
```

κ uses the same finite-sample convention as `acs/conformal.py`
(⌈(n+1)·0.9⌉-th order statistic of |actual − p_corr| / se_corr, ÷1.645).
In-sample after both: coverage 93.5%, MAPE 3.27% → **2.62%**.

Production effect (TY2028, finals + DOH nowcasts): raw Kalman 14,126 →
**calibrated 13,842**, 90% PI [12,779, 14,905]. Cross-check: the 2026 nowcast
is ~14,416 and two further years at the recent ~1.5%/yr decline lands ~13,990 —
the calibrated point sits slightly below the naive continuation, which is
exactly the direction the fold evidence demands.

## Caveats

* Pooled bias slightly overcorrects at h=2 (+1.5% measured) and undercorrects
  at h=4 (+4.2%); production h=2-from-nowcast sits closest to the former.
* The 46 folds come from one series with overlapping windows — they are
  correlated, so the effective sample is smaller than 46. The conformal
  exchangeability assumption is approximate here, as it is everywhere the repo
  uses walk-forward folds.
* The bias correction encodes "the recent decline continues to be
  under-extrapolated." If Hawaiʻi fertility genuinely flattens (2024 did
  tick up), the correction overshoots downward by up to ~2%. Re-run the script
  when the 2025 final lands; the constants are one paste away.
* Folds score finals only. Production adds nowcast-specific risks (DOH
  revisions, occurrence/residence drift) that the folds cannot price; the
  nowcasts' wider MOEs enter the filter's R, which partially covers this.

## Round 1 (historical) — 7 finals, 6 folds

| method | MAPE | bias | RMSE | CI90 coverage |
|---|---|---|---|---|
| persistence | 3.42% | +3.18% | 589 | — |
| ensemble | 3.28% | −2.49% | 635 | 50.0% |
| kalman | 2.34% | +0.57% | 395 | 100.0% |

Round 1 chose Kalman as the default. Its headline numbers were direction-correct
but small-sample-flattered (Kalman MAPE 2.34% became 3.27% at n=46; the
ensemble's 50% coverage became 69.6% pooled but 40% at h=4). The decision it
drove survives round 2 on every axis.
