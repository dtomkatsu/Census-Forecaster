"""Hawaii-empirical take-up anchor for HI EITC (proxy for a hypothetical HI CTC).

The poverty-impact sweep prior to 2026-Q2 used a pooled-literature band
of 0.60 / 0.80 / 0.95 for the ``hi_ctc_takeup_rate`` parameter — wide
because it mixed a first-year-program estimate (Minnesota 2023 = 0.60)
with a steady-state federal-EITC ceiling (0.95). The resulting ±18-pp
band drove most of the ±37% parameter range on the headline
``persons_lifted_hi_ctc_650`` cell.

This module produces a tighter, Hawaii-specific anchor by computing the
observed take-up of Hawaii's existing state EITC and applying the same
composite friction profile to the hypothetical state CTC.

Why HI EITC is a good proxy for HI CTC take-up
----------------------------------------------

Both are state-level credits that auto-attach to a federal claim on
Form N-15. The composite take-up rate decomposes as:

    τ = (filing rate)
        × (federal-claim rate | filing)
        × (state-auto-attach rate | federal claim ≈ 1.0)

For HI EITC, this composite is *directly observable*:

    Numerator   = federal EITC returns filed in Hawaii (IRS SOI 2022;
                  84,010 returns per ``data/admin_caseload/hawaii_caseload.csv``)
    Denominator = PUMS-weighted count of tax units with positive
                  federally-eligible EITC

A hypothetical HI CTC piggybacking on the same Form N-15 inherits the
same composite friction profile (assuming the bill design is auto-attach
to federal CTC, the standard pattern in enacted state CTCs as of 2024).

SDR-bootstrapped band
---------------------

We already build ``weight_r01..weight_r80`` replicate weights for the
SPM aggregator. The take-up ratio itself can be re-computed under each
replicate weight to derive its SDR sampling SE. The band reported is
``(τ − 2·SE, τ, τ + 2·SE)`` — a 95% credible interval under PUMS
sampling, clipped to ``[0, 1]``.

Important caveat: this captures *sampling variance only*. It does NOT
capture:

  * Year-to-year behavioral drift (e.g., the HI EITC has been refundable
    only since 2023; long-run steady-state take-up may differ from the
    2022 IRS SOI ratio).
  * Differences between HI EITC and a new HI CTC in administrative
    friction (e.g., outreach, advance-payment options).

Document these limitations in METHODOLOGY.md when citing the band.

Public API
----------

``estimate_hi_eitc_takeup(units, *, weight_col, replicate_cols, ...)``
returns a :class:`TakeupEstimate` whose ``band()`` method yields the
``(low, mid, high)`` tuple consumed by the parameter sweep.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

import numpy as np
import pandas as pd

from tax_modeler.poverty.impact import _sdr_se_from_replicates

# Default numerator: federal EITC returns filed in Hawaii per IRS SOI 2022,
# carried in ``packages/tax_modeler/src/tax_modeler/data/admin_caseload/
# hawaii_caseload.csv`` row ``eitc,2022``. Override at call time if
# benchmarking against a different vintage.
_DEFAULT_ADMIN_TARGET = 84_010.0
_DEFAULT_ADMIN_TARGET_YEAR = 2022
_DEFAULT_ADMIN_TARGET_SOURCE = (
    "IRS SOI ZIP Code Data 2022 (Hawaii state-total row), "
    "Earned income credit column N59660. See "
    "tax_modeler/data/admin_caseload/hawaii_caseload.csv."
)


@dataclass(frozen=True)
class TakeupEstimate:
    """Empirical take-up estimate with SDR-bootstrapped sampling SE.

    Attributes
    ----------
    point:
        Headline take-up ratio ``τ = admin_target / weighted_eligible``.
    se:
        SDR sampling SE on ``τ``, bootstrapped over the PUMS replicate
        weights. Zero when no replicate columns are present.
    n_replicates:
        Number of replicate-weight columns used. Zero ⇒ ``se == 0``.
    admin_target:
        Numerator passed to the estimator (administrative claim count).
    denom_eligible:
        Weighted-eligible denominator computed under the main weight.
    """

    point: float
    se: float
    n_replicates: int
    admin_target: float
    denom_eligible: float

    def band(self, k: float = 2.0) -> tuple[float, float, float]:
        """Return ``(low, mid, high)`` clipped to ``[0, 1]``.

        ``k`` is the multiplier on the SE: ``k=2`` gives a ~95% credible
        interval; ``k=1`` gives ~68%. Default ``k=2`` is consistent with
        Census ACS published 90% MOE conventions.
        """
        low = max(0.0, self.point - k * self.se)
        high = min(1.0, self.point + k * self.se)
        return (low, self.point, high)

    def to_dict(self) -> dict[str, float | int | str]:
        """Serializable summary for ``hi_eitc_takeup_anchor.json`` artifact."""
        low, mid, high = self.band()
        return {
            "point": self.point,
            "se": self.se,
            "n_replicates": self.n_replicates,
            "admin_target": self.admin_target,
            "admin_target_year": _DEFAULT_ADMIN_TARGET_YEAR,
            "admin_target_source": _DEFAULT_ADMIN_TARGET_SOURCE,
            "denom_eligible": self.denom_eligible,
            "band_low": low,
            "band_mid": mid,
            "band_high": high,
        }


def _weighted_eligible_count(
    units: pd.DataFrame, *, weight_col: str, eligible_mask: np.ndarray,
) -> float:
    """Σ weight × eligible — the denominator under one weight column."""
    w = units[weight_col].astype(float).to_numpy()
    return float(np.sum(w * eligible_mask))


def _resolve_eligibility(
    units: pd.DataFrame, *, eligibility_col: Optional[str], eitc_col: str,
) -> np.ndarray:
    """Boolean mask of federally-EITC-eligible tax units.

    If ``eligibility_col`` is given and present, use it directly (it
    should already be a 0/1 or bool column). Otherwise default to
    ``units[eitc_col] > 0`` — which works because the EITC calculator
    emits ``$0`` for ineligible units.
    """
    if eligibility_col and eligibility_col in units.columns:
        return units[eligibility_col].fillna(0).astype(bool).to_numpy()
    if eitc_col not in units.columns:
        raise KeyError(
            f"estimate_hi_eitc_takeup: neither {eligibility_col!r} nor "
            f"{eitc_col!r} present on units. Pass an explicit "
            "eligibility_col, or compute federal EITC first."
        )
    return (units[eitc_col].fillna(0).astype(float) > 0).to_numpy()


def _detect_replicate_cols(
    units: pd.DataFrame, *, explicit: Optional[Sequence[str]],
) -> list[str]:
    """Return the list of replicate-weight columns to bootstrap over.

    If ``explicit`` is given, use it (filtered to columns actually
    present). Otherwise auto-detect ``weight_r01..weight_r80``.
    """
    if explicit is not None:
        return [c for c in explicit if c in units.columns]
    return [f"weight_r{r:02d}" for r in range(1, 81) if f"weight_r{r:02d}" in units.columns]


def estimate_hi_eitc_takeup(
    units: pd.DataFrame,
    *,
    weight_col: str = "weight",
    replicate_cols: Optional[Sequence[str]] = None,
    eligibility_col: Optional[str] = None,
    eitc_col: str = "eitc_amount",
    admin_target: float = _DEFAULT_ADMIN_TARGET,
) -> TakeupEstimate:
    """Compute the Hawaii-empirical EITC take-up rate with SDR SE.

    Parameters
    ----------
    units:
        Tax-unit DataFrame post-:func:`compute_base_tax` (so
        ``eitc_amount`` reflects the federally-eligible amount).
        Required columns: ``weight_col`` plus the eligibility signal.
    weight_col:
        Main PUMS weight column. Default ``"weight"``.
    replicate_cols:
        Optional explicit list of replicate-weight columns. If ``None``
        (default), auto-detects ``weight_r01..weight_r80``. Pass ``()``
        to suppress SDR (returns ``se=0.0, n_replicates=0``).
    eligibility_col:
        Optional explicit boolean eligibility column. If ``None``
        (default), eligibility is ``eitc_col > 0``.
    eitc_col:
        Federal EITC dollar column (used for the default eligibility
        signal). Default ``"eitc_amount"``.
    admin_target:
        Administrative numerator. Default ``84,010`` (IRS SOI 2022
        federal EITC returns filed in Hawaii). Override for other
        vintages or for benchmarking against alternative caseload
        targets.

    Returns
    -------
    :class:`TakeupEstimate` with point, SDR SE, and replicate count.
    Call ``.band()`` to get the (low, mid, high) tuple suitable for
    seeding the ``hi_ctc_takeup`` ``SweepParam`` low/mid/high values.

    Notes
    -----
    The point estimate is
        τ_0 = admin_target / Σ(weight × eligible).
    For each replicate ``r``, τ_r = admin_target / Σ(weight_r × eligible).
    SE(τ) follows the standard SDR variance formula
        V(τ) = (4/R) · Σ_r (τ_r − τ_0)²
    delegated to ``_sdr_se_from_replicates`` for consistency with the
    SPM aggregator's SE wrapper.

    Sampling variance only — does not capture year-to-year drift,
    program-design heterogeneity (HI EITC vs hypothetical HI CTC), or
    behavioral evolution since 2022. See module docstring.
    """
    if weight_col not in units.columns:
        raise KeyError(
            f"estimate_hi_eitc_takeup: weight_col={weight_col!r} not on units."
        )
    eligible = _resolve_eligibility(
        units, eligibility_col=eligibility_col, eitc_col=eitc_col,
    )

    denom_0 = _weighted_eligible_count(
        units, weight_col=weight_col, eligible_mask=eligible,
    )
    if denom_0 <= 0:
        raise ValueError(
            "estimate_hi_eitc_takeup: weighted-eligible denominator is "
            f"{denom_0!r}. Confirm that {eitc_col!r} carries positive "
            "values for federally-EITC-eligible units."
        )
    tau_0 = admin_target / denom_0

    rep_cols = _detect_replicate_cols(units, explicit=replicate_cols)
    if not rep_cols:
        return TakeupEstimate(
            point=tau_0, se=0.0, n_replicates=0,
            admin_target=admin_target, denom_eligible=denom_0,
        )

    tau_r = np.empty(len(rep_cols), dtype=float)
    for i, rc in enumerate(rep_cols):
        denom_r = _weighted_eligible_count(
            units, weight_col=rc, eligible_mask=eligible,
        )
        # Replicate with zero eligible weight ⇒ take-up undefined;
        # treat as no-variance contribution (τ_r ≡ τ_0).
        tau_r[i] = admin_target / denom_r if denom_r > 0 else tau_0

    se = float(_sdr_se_from_replicates(tau_0, tau_r))
    return TakeupEstimate(
        point=tau_0, se=se, n_replicates=len(rep_cols),
        admin_target=admin_target, denom_eligible=denom_0,
    )


__all__ = ["TakeupEstimate", "estimate_hi_eitc_takeup"]
