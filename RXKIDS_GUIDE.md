# RxKids Hawaiʻi — Reader's Guide (start here)

A self-guided tour for investigating the RxKids Hawaiʻi cost estimate: what it
is, how to run it, where every decision lives, and how to check it yourself.
For the full methodology, read **[`RXKIDS_METHODOLOGY.md`](RXKIDS_METHODOLOGY.md)**.

## 1. What this is

An estimate of the **annual cost and household impact** of a hypothetical
Hawaiʻi RxKids program — unrestricted cash "prescribed" during pregnancy and
infancy — modeled on the real RxKids program in Flint, Michigan. Eligibility
follows a draft Hawaiʻi statute: a family qualifies if it **(1) qualifies for
the State's Medicaid program, OR (2) has family income ≤ 300% of the federal
poverty level**, including the expected unborn child.

**Headline (TY2028, conservative default):** ~**$54M/yr** (range ~$33–69M),
serving ~24,000 births. A Flint-equivalent scenario (98% take-up, +10%
fertility) is ~$65M. The estimate is dominated by *specification* uncertainty,
not sampling — see §6.

**The one open question to know about:** "family income" is modeled as **MAGI
at the tax-unit (MAGI-household) grain**, because the statute anchors clause 1
to Medicaid (which uses MAGI households). If the bill defines "family" more
broadly, the alternative SPM-family grain gives ~$45M — a ~$9M / ~18% lever.
This is a legal-definitional question, not a modeling one.

## 2. Set up (one time)

The repo is a [`uv`](https://docs.astral.sh/uv/)-managed Python package.

```bash
uv sync --package census-forecaster --extra dev   # creates .venv with all deps
```

## 3. Run it yourself

```bash
# Conservative default (real Hawaiʻi PUMS, committed in the repo):
uv run python forecast_rxkids_2028.py \
    --tax-year 2028 \
    --pums-data-dir packages/data/raw/pums_2024_1yr \
    --out reports/rxkids_2028/

# Flint-equivalent scenario:
uv run python forecast_rxkids_2028.py --tax-year 2028 \
    --pums-data-dir packages/data/raw/pums_2024_1yr \
    --takeup-rate 0.98 --fertility-response 0.10 \
    --out reports/rxkids_2028_flint/

# No PUMS download needed for a smoke run — synthetic fixture:
uv run python forecast_rxkids_2028.py --use-fixture --out /tmp/rxkids_smoke
```

Each run writes a workbook, a one-page PDF, CSVs, and the SPM-unit parquet to
the `--out` directory. Run `--help` to see every knob (take-up, fertility,
launch-year ramp, 12-month-extension, etc.).

## 4. The file map

| File | What it is |
|---|---|
| **[`RXKIDS_METHODOLOGY.md`](RXKIDS_METHODOLOGY.md)** | The full methodology — sourcing, eligibility, every parameter, limitations, cross-checks, MOE. **Read this for the substance.** |
| **[`forecast_rxkids_2028.py`](forecast_rxkids_2028.py)** | The runnable end-to-end script (the *process*): load PUMS → project to 2028 → eligibility → cost + impact → workbook/PDF. |
| `packages/tax_modeler/src/tax_modeler/programs/rxkids_hi.py` | Core eligibility + benefit math (`compute_rxkids_for_units`). The two clauses, both arms, the birth proxy. |
| `packages/tax_modeler/src/tax_modeler/benefits/medicaid_hi_quest.py` | Clause 1 — Medicaid eligibility (`medicaid_receives`). |
| `packages/tax_modeler/src/tax_modeler/benefits/_fpl.py` | HHS Hawaiʻi FPL tables (2024–2025 published; 2026–2028 projected). |
| `tests/tax_modeler/programs/test_rxkids.py` | The rules as executable tests — a precise, runnable spec of who qualifies and what they get. |
| `reports/rxkids_2028/` , `reports/rxkids_2028_flint/` | The committed outputs (xlsx workbook, PDF, CSVs, parquet). |

## 5. Check it yourself

```bash
# The eligibility/benefit rules, as ~18 fast tests:
uv run pytest tests/tax_modeler/programs/test_rxkids.py -v

# The whole suite (excluding tests that need large external data):
uv run pytest tests/ -m "not requires_dotax_raw and not requires_irs_external"

# Reproduce the headline: re-run §3 and diff the CSV against the committed one:
uv run python forecast_rxkids_2028.py --tax-year 2028 \
    --pums-data-dir packages/data/raw/pums_2024_1yr --out /tmp/check
diff /tmp/check/cost_by_state.csv reports/rxkids_2028/cost_by_state.csv
```

The workbook's **Assumptions** and **Notes** tabs list every parameter and
caveat behind that specific run, so a reviewer can audit a result without
reading code.

## 6. Trace the methodology — *the process*, decision by decision

Every methodology choice is a separate git commit with a full explanation of
*why*. To read the evolution of the model:

```bash
git log --oneline -- forecast_rxkids_2028.py \
    packages/tax_modeler/src/tax_modeler/programs/rxkids_hi.py \
    RXKIDS_METHODOLOGY.md
```

Notable decisions in the trail (each is a commit message worth reading):
postnatal stock→flow correction · prenatal birth-anchor → unified birth-driven
arms · recipients vs eligible base · joint-corner assumption band · launch-year
ramp · take-up & fertility scenarios · cash income → MAGI proxy · SPM-family →
MAGI-household grain. `git show <hash>` on any of these shows the exact code
change and the reasoning.

## 7. The assumptions that drive the number

These are the soft inputs (all in §2/§10 of the methodology, all overridable by
CLI flag). They — not sampling error — are why the honest MOE is ±30–40%:

| Assumption | Default | Why it's uncertain |
|---|---|---|
| Take-up rate | 0.90 | No Hawaiʻi program to anchor against (Flint observed 0.98) |
| Birth rate / dependent | 0.066 | Hawaiʻi births ÷ ACS dependents; scales the whole estimate |
| Fertility response | 0 (off) | Flint saw ~+10% births; a real upside risk, off by default |
| "Family income" grain | MAGI household | Legal-definitional (see §1); ~18% lever |
| Payment design / 6-vs-12 mo | $1,500 + $500×6 | Policy choices; not yet fixed in a bill |

There is **no administrative caseload** to calibrate against (RxKids doesn't
exist in Hawaiʻi yet), so these are judgment calls, transparently parameterized
rather than hidden.
