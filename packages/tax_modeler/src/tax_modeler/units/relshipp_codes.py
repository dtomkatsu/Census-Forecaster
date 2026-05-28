"""Canonical PUMS ``RELSHIPP`` relationship codes (Census 2019+).

Single source of truth for decoding the ACS/PUMS ``RELSHIPP`` variable.

PUMS replaced the old ``RELP`` variable (codes 0-17) with ``RELSHIPP``
(codes 20-38) in the 2019 1-year file. The two are NOT a simple +20 offset:
``RELSHIPP`` splits spouses/partners into opposite- and same-sex variants
and reorders several categories. Historically this module's consumers
decoded relationships three different (all wrong) ways -- a "RELP+20"
offset, raw old-RELP codes compared against 20-38 values, and ad-hoc
literals -- which silently dropped grandchildren, stepchildren, siblings,
and foster children from EITC qualifying-child counts and mis-assigned SPM
units. Route every relationship-code decision through the named constants
and semantic sets below so that error cannot recur.

Authoritative mapping (ACS PUMS RELSHIPP, 2019+):
    20 Reference person (householder)
    21 Opposite-sex husband/wife/spouse
    22 Opposite-sex unmarried partner
    23 Same-sex husband/wife/spouse
    24 Same-sex unmarried partner
    25 Biological son or daughter
    26 Adopted son or daughter
    27 Stepson or stepdaughter
    28 Brother or sister
    29 Father or mother
    30 Grandchild
    31 Parent-in-law
    32 Son-in-law or daughter-in-law
    33 Other relative
    34 Roommate or housemate
    35 Foster child
    36 Other nonrelative
    37 Institutionalized group quarters population
    38 Noninstitutionalized group quarters population
"""

from __future__ import annotations

# --- Individual codes ---
REFERENCE_PERSON = 20
SPOUSE_OPPOSITE = 21
PARTNER_OPPOSITE = 22
SPOUSE_SAME = 23
PARTNER_SAME = 24
BIO_CHILD = 25
ADOPTED_CHILD = 26
STEPCHILD = 27
SIBLING = 28
PARENT = 29
GRANDCHILD = 30
PARENT_IN_LAW = 31
CHILD_IN_LAW = 32
OTHER_RELATIVE = 33
ROOMMATE = 34
FOSTER_CHILD = 35
OTHER_NONRELATIVE = 36
GQ_INSTITUTIONAL = 37
GQ_NONINSTITUTIONAL = 38

# --- Semantic sets ---

#: Married spouses of the householder (opposite- and same-sex).
SPOUSE = frozenset({SPOUSE_OPPOSITE, SPOUSE_SAME})

#: Cohabiting unmarried partners of the householder.
UNMARRIED_PARTNER = frozenset({PARTNER_OPPOSITE, PARTNER_SAME})

#: Own children of the householder: biological, adopted, step.
OWN_CHILD = frozenset({BIO_CHILD, ADOPTED_CHILD, STEPCHILD})

#: Relationships that can make a dependent an EITC *qualifying child*
#: (IRC §32(c)(3)(B)): own child, sibling, grandchild, foster child.
#: Nieces/nephews fall under OTHER_RELATIVE (33) and cannot be distinguished,
#: so they are conservatively excluded. Age / student / "younger than the
#: filer" tests are applied separately by callers.
EITC_QUALIFYING_CHILD_RELS = frozenset(
    OWN_CHILD | {SIBLING, GRANDCHILD, FOSTER_CHILD}
)

#: Blood/marriage relatives of the householder eligible to be a *qualifying
#: relative* (IRC §152(d)(2)): children, siblings, parent, grandchild,
#: in-laws, other relative, foster child. Excludes the householder (20),
#: spouses (file jointly/separately) and unmarried partners. "Member of
#: household who lived with the taxpayer all year but is unrelated" is
#: intentionally NOT modeled here.
QUALIFYING_RELATIVE_RELS = frozenset({
    BIO_CHILD, ADOPTED_CHILD, STEPCHILD, SIBLING, PARENT, GRANDCHILD,
    PARENT_IN_LAW, CHILD_IN_LAW, OTHER_RELATIVE, FOSTER_CHILD,
})

#: People who pool into the household's primary SPM unit (Census P60-280):
#: householder + spouses + unmarried partners + all blood/marriage relatives
#: + foster children. Unrelated children under 15 are pooled by a separate
#: age rule in the caller.
SPM_PRIMARY = frozenset({
    REFERENCE_PERSON, SPOUSE_OPPOSITE, PARTNER_OPPOSITE, SPOUSE_SAME,
    PARTNER_SAME, BIO_CHILD, ADOPTED_CHILD, STEPCHILD, SIBLING, PARENT,
    GRANDCHILD, PARENT_IN_LAW, CHILD_IN_LAW, OTHER_RELATIVE, FOSTER_CHILD,
})

#: Unrelated household members aged 15+ who form their own one-person SPM
#: units: roommates/housemates and other nonrelatives.
SPM_UNRELATED = frozenset({ROOMMATE, OTHER_NONRELATIVE})

#: Group-quarters population, excluded from SPM accounting.
GROUP_QUARTERS = frozenset({GQ_INSTITUTIONAL, GQ_NONINSTITUTIONAL})
