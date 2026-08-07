# Birth-cohort projection back-test — 2026-08-07

Reproduce: `python scripts/backtest_birth_projection.py`

## Why

The RxKids birth cohort is the least externally-anchored input in the model. It
has no entry in the anchor-source registry, gets none of the v3 bias/κ/conformal
calibration, and its 90% PI had **never been coverage-tested**. It simply
inherited `EMPIRICAL_SE_INFLATOR = 1.30`, which was calibrated on ACS *survey*
dollar series (income, rent, home value) — a different noise regime from
vital-statistics counts.

Two questions, answered with data rather than intuition:

1. Should the cohort be driven by the legacy damped-trend + AR(1) ensemble or by
   the Kalman state-space filter?
2. Is the quoted 90% interval honest?

## Setup

Expanding-window walk-forward on the **NVSR finals only** — the DOH nowcasts are
not ground truth and cannot be scored. Minimum training window 4 finals; each
cutoff predicts every later final, giving horizons 1–3. Persistence (carry the
last value forward) is included as the floor: a projector that cannot beat
persistence is not earning its keep.

Series (corrected against CDC WONDER the same day — see
`RXKIDS_METHODOLOGY.md` §3):
2018 16,972 · 2019 16,797 · 2020 15,785 · 2021 15,620 · 2022 15,535 ·
2023 14,808 · 2024 14,917

## Results

| method | n | MAPE | bias | RMSE | CI90 coverage |
|---|---|---|---|---|---|
| persistence | 6 | 3.42% | +3.18% | 589 | — |
| ensemble (legacy default) | 6 | 3.28% | −2.49% | 635 | **50.0%** |
| **kalman (new default)** | 6 | **2.34%** | **+0.57%** | **395** | 100.0% |

By horizon (MAPE):

| method | h=1 | h=2 | h=3 |
|---|---|---|---|
| persistence | 2.06% | 4.81% | 4.71% |
| ensemble | 3.17% | 1.02% | **8.13%** |
| kalman | 3.01% | 2.28% | **0.41%** |

## Reading

**Kalman wins on every point metric** — 29% lower MAPE, a quarter the bias, 38%
lower RMSE — and the gap *widens with horizon*, which is what matters for a
2028 target: at h=3 the ensemble degrades to 8.13% while Kalman improves to
0.41%.

**The ensemble's interval was not usable.** 50% coverage against a 90% target
means roughly every other fold fell outside its own 90% PI. Any uncertainty
range quoted from that path was materially too narrow.

**The ensemble barely beat persistence** (3.28% vs 3.42%), i.e. the legacy
projector was adding almost nothing over "assume next year equals this year".

**Mechanism.** `project_kalman` consumes each observation's MOE as measurement
noise (`R = (se/estimate)²`). `fit_damped_trend` and `fit_ar1_log_diff` ignore
per-observation MOE entirely — they read only the *latest* observation's MOE, and
only for the sampling-SE term. So under the ensemble, the DOH nowcasts'
uncertainty could reach the interval but never the point estimate. That is the
concrete reason the two diverge on a series whose newest points are nowcasts.

## Caveats

* **n=6 folds, 7 finals.** This is a sanity gate, not a calibration. It is
  enough to catch a clearly-worse method or a clearly-broken interval; it is not
  enough to tune a κ, and the 100% Kalman coverage may well mean *too wide*
  rather than correctly sized — 6 folds cannot distinguish those.
* Nowcasts are excluded from scoring, so this measures the projector, not the
  nowcast machinery.
* The nowcast MOEs (199 / 347) land close to the finals' nominal Poisson MOEs
  (~201), so Kalman's down-weighting of nowcasts is real but modest. It also
  does not price the risk that DOH revises a preliminary count, or that the
  occurrence/residence ratio drifts.

## Outcome

`BIRTH_PROJECTION_METHOD = "kalman"` is now the default in
`forecast_rxkids_2028.py`. `--birth-projection-method ensemble` restores the
legacy path for comparison. On the production series (finals + DOH nowcasts) the
switch moves the TY2028 cohort 13,923 → 14,126 and widens the 90% PI from
±820 to ±1,258 — the interval getting wider is the point, given the coverage
result above.
