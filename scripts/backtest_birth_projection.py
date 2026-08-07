"""Walk-forward back-test of the RxKids birth-cohort projection.

Why this exists
---------------
The birth series is the least externally-anchored input in the RxKids model.
Unlike every dollar indicator in the repo it has no entry in the anchor-source
registry, gets no v3 bias/kappa calibration, and — critically — its prediction
interval had never been coverage-tested against anything. It simply inherits
``EMPIRICAL_SE_INFLATOR = 1.30``, which was calibrated on ACS *survey* dollar
series (income, rent, home value). Vital-statistics counts are far less noisy
than ACS estimates, so that inflator is a guess in the wrong direction.

This script answers two questions with data instead of intuition:

  1. Which method should drive the birth cohort — the legacy damped-trend +
     AR(1) ensemble (current default), or the Kalman state-space filter?
     They differ in a way that matters here: ``project_kalman`` consumes each
     observation's MOE as measurement noise (``R = (se/estimate)^2``), whereas
     ``fit_damped_trend`` / ``fit_ar1_log_diff`` ignore per-observation MOE
     entirely. Since the DOH nowcasts carry deliberately wide MOEs, only the
     Kalman path can let that uncertainty reach the POINT estimate rather than
     just the interval.
  2. Is the 90% PI honest? Coverage should land near 90%; materially below
     means the interval is too tight to quote.

Design
------
Expanding-window walk-forward on the NVSR finals only (the nowcasts are not
ground truth, so they cannot be scored). For each cutoff year the model sees
finals up to and including that year and predicts every later final, giving
horizons 1..N. Also scores a naive persistence baseline (carry the last value
forward) — a projection that cannot beat persistence is not earning its keep.

The series is short (7 finals), so treat this as a sanity gate rather than a
precise calibration: it is enough to catch a method that is clearly worse or an
interval that is clearly miscalibrated, not enough to tune a kappa.

Usage
-----
    python scripts/backtest_birth_projection.py
    python scripts/backtest_birth_projection.py --min-train 4
"""
from __future__ import annotations

import argparse
import math
import statistics
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))


def _obs(year: int, value: float):
    from common.models import AcsObservation
    return AcsObservation(
        estimate=float(value), moe=1.645 * math.sqrt(value), year=year,
        vintage="1y", geoid="15", indicator="births",
    )


def _predict(method: str, train: list, target_year: int):
    """Return (point, ci_low, ci_high) or None."""
    if method == "persistence":
        last = max(train, key=lambda o: o.year)
        return last.estimate, float("nan"), float("nan")

    if method == "ensemble":
        from census_forecaster import project_acs_ensemble
        fp = project_acs_ensemble(train, target_year=target_year)
    elif method == "kalman":
        from census_forecaster.kalman import project_kalman
        # end_year MUST be passed explicitly as an int: project_kalman's default
        # is `max(effective_year(o))`, which is a float, and it then feeds that
        # to range() -> TypeError. Latent because every in-repo caller
        # (ensemble.project_ensemble_multi) already passes an int.
        fp = project_kalman(train, target_year=target_year,
                            end_year=int(max(o.year for o in train)), geoid="15")
    else:
        raise ValueError(method)
    if fp is None:
        return None
    return float(fp.point), float(fp.ci90_low), float(fp.ci90_high)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--min-train", type=int, default=4,
                    help="Minimum number of finals in the training window (default 4).")
    args = ap.parse_args(argv)

    import forecast_rxkids_2028 as F
    series = dict(sorted(F.HI_BIRTHS_BY_YEAR.items()))
    years = sorted(series)
    print(f"NVSR finals: {years[0]}-{years[-1]}  "
          f"({', '.join(f'{y}:{series[y]:,}' for y in years)})\n")

    methods = ["persistence", "ensemble", "kalman"]
    rows = []  # (method, horizon, actual, point, lo, hi)

    for i in range(args.min_train, len(years)):
        cutoff = years[i - 1]
        train = [_obs(y, series[y]) for y in years[:i]]
        for j in range(i, len(years)):
            ty = years[j]
            horizon = ty - cutoff
            for m in methods:
                out = _predict(m, train, ty)
                if out is None:
                    continue
                point, lo, hi = out
                rows.append((m, horizon, cutoff, series[ty], point, lo, hi))

    if not rows:
        print("No folds produced — series too short for --min-train.", file=sys.stderr)
        return 1

    print(f"{'method':>12} {'n':>3} {'MAPE':>7} {'bias':>8} {'RMSE':>8} {'CI90 cov':>9}")
    summary = {}
    for m in methods:
        sub = [r for r in rows if r[0] == m]
        if not sub:
            continue
        ape = [abs(p - a) / a for _, _, _, a, p, _, _ in sub]
        bias = [(p - a) / a for _, _, _, a, p, _, _ in sub]
        se = [(p - a) ** 2 for _, _, _, a, p, _, _ in sub]
        covered = [lo <= a <= hi for _, _, _, a, _, lo, hi in sub
                   if math.isfinite(lo) and math.isfinite(hi)]
        cov = (sum(covered) / len(covered)) if covered else float("nan")
        summary[m] = {"mape": statistics.fmean(ape), "bias": statistics.fmean(bias),
                      "rmse": math.sqrt(statistics.fmean(se)), "cov": cov,
                      "n": len(sub)}
        cov_s = f"{100*cov:8.1f}%" if covered else "       —"
        print(f"{m:>12} {len(sub):>3} {100*summary[m]['mape']:>6.2f}% "
              f"{100*summary[m]['bias']:>+7.2f}% {summary[m]['rmse']:>8.0f} {cov_s:>9}")

    print(f"\n{'method':>12} {'h':>3} {'MAPE':>7}   (by horizon)")
    for m in methods:
        for h in sorted({r[1] for r in rows}):
            sub = [r for r in rows if r[0] == m and r[1] == h]
            if not sub:
                continue
            ape = statistics.fmean(abs(p - a) / a for _, _, _, a, p, _, _ in sub)
            print(f"{m:>12} {h:>3} {100*ape:>6.2f}%   (n={len(sub)})")

    # ---- verdict ---------------------------------------------------------
    print("\n--- verdict ---")
    if "ensemble" in summary and "persistence" in summary:
        e, p = summary["ensemble"]["mape"], summary["persistence"]["mape"]
        verdict = "beats" if e < p else "LOSES TO"
        print(f"ensemble {verdict} persistence ({100*e:.2f}% vs {100*p:.2f}% MAPE)")
    if "ensemble" in summary and "kalman" in summary:
        e, k = summary["ensemble"]["mape"], summary["kalman"]["mape"]
        better = "kalman" if k < e else "ensemble"
        print(f"better point accuracy: {better} "
              f"(ensemble {100*e:.2f}% vs kalman {100*k:.2f}% MAPE)")
        ec, kc = summary["ensemble"]["cov"], summary["kalman"]["cov"]
        print(f"CI90 coverage: ensemble {100*ec:.0f}%, kalman {100*kc:.0f}% "
              f"(target 90%; well below => interval too tight to quote)")
    print("\nNOTE: 7 finals only. This is a sanity gate, not a calibration — "
          "enough to catch a clearly-worse method or a clearly-broken interval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
