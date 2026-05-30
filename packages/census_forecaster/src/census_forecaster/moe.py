"""Backward-compat re-export. Canonical location: common.moe."""
from common.moe import (  # noqa: F401
    ACS_MOE_Z,
    moe_to_se,
    se_to_moe,
    moe_sum,
    moe_difference,
    moe_ratio,
    moe_proportion,
    combine_se,
    ci_from_se,
    relative_se,
    CV_IMPRECISE_THRESHOLD,
    CV_UNRELIABLE_THRESHOLD,
    moe_reliability_note,
)

__all__ = [
    "ACS_MOE_Z", "moe_to_se", "se_to_moe", "moe_sum", "moe_difference",
    "moe_ratio", "moe_proportion", "combine_se", "ci_from_se", "relative_se",
    "CV_IMPRECISE_THRESHOLD", "CV_UNRELIABLE_THRESHOLD", "moe_reliability_note",
]
