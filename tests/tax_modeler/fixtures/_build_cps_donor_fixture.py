"""Build a deterministic synthetic CPS-ASEC-style donor fixture for MOOP imputation.

Run::

    python tests/tax_modeler/fixtures/_build_cps_donor_fixture.py

Writes
``packages/tax_modeler/src/tax_modeler/data/cps_donor/cps_moop_donors.csv``
which is bundled with the package and used by
:func:`tax_modeler.calibration.donor_match.impute_moop` when no
external donors_df is supplied.

Distribution targets (BLS Consumer Expenditure Survey + Census P60-280):
  * Mean MOOP ~$2,200/year/family
  * Higher MOOP at older ages (Medicare gap costs, supplemental drugs)
  * Higher MOOP at low income (no insurance) AND high income (premium plans)
  * U-shape at moderate income (Medicaid covers most costs, ESI covers rest)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT_PATH = (
    Path(__file__).resolve().parents[3]
    / "packages" / "tax_modeler" / "src" / "tax_modeler"
    / "data" / "cps_donor" / "cps_moop_donors.csv"
)
SEED = 0xC0DECAFE
N_DONORS = 200


def build_donors(rng: np.random.Generator) -> pd.DataFrame:
    rows = []
    # Stratify across age × HH size × income tiers to give the matcher
    # diverse neighbors at every recipient point.
    for _ in range(N_DONORS):
        age = float(rng.integers(20, 90))
        hh_size = int(rng.choice([1, 2, 3, 4, 5], p=[0.27, 0.32, 0.18, 0.15, 0.08]))
        # Income: lognormal around tier, clipped
        log_mean = float(rng.choice([10.5, 11.0, 11.5, 12.0]))
        income = float(np.exp(rng.normal(log_mean, 0.3)))
        income = float(np.clip(income, 5_000, 500_000))

        # MOOP model: base $1,200 + age premium + HH-size premium + income U-shape
        base = 1_200
        age_prem = max(0.0, (age - 50)) * 60          # +$60/yr per year over 50
        hh_prem = (hh_size - 1) * 350                  # ~$350/extra member
        if income < 30_000:
            income_factor = 1.4   # uninsured / underinsured
        elif income < 80_000:
            income_factor = 0.7   # ESI / Medicaid covers most
        else:
            income_factor = 1.1   # premium plans + elective care
        noise = float(rng.lognormal(mean=0.0, sigma=0.4))
        moop = (base + age_prem + hh_prem) * income_factor * noise
        moop = float(np.clip(moop, 0.0, 35_000))

        rows.append({
            "age": age,
            "hh_size": hh_size,
            "income": income,
            "moop": round(moop, 2),
        })
    df = pd.DataFrame(rows)
    return df


def main() -> int:
    rng = np.random.default_rng(SEED)
    df = build_donors(rng)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False)
    print(f"Wrote {len(df)} donors → {OUT_PATH}")
    print(f"  mean MOOP: ${df['moop'].mean():,.0f} (target ~$2,200)")
    print(f"  median MOOP: ${df['moop'].median():,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
