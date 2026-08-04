# SB 3125 CD2 forecast pipeline
# Full pipeline:       make sb3125_cd2
# Just rebuild HTML:   make report
#
# The full pipeline requires the venv (uv sync --all-packages).
# generate_itep_report.py only needs pandas and is safe to run with system python3.

PYTHON      := .venv/bin/python3
PYTHON_PLAIN := python3

# Canonical outputs live in the manifested runs/ store (Phase 1,
# DASHBOARD_PIPELINE_SCOPE.md); scripts still mirror to /tmp during the
# transition.
ENHANCED_CSV := runs/sb3125_cd2_enhanced/enhanced.csv
QUINTILE_CSV := runs/sb3125_cd2_fy26base/quintile.csv
HTML_REPORT  := /tmp/SB3125_CD_analysis_charts.html

.PHONY: all sb3125_cd2 enhanced distributional report clean help

all: sb3125_cd2

## Full pipeline: enhanced fiscal → distributional → HTML report
sb3125_cd2: $(ENHANCED_CSV) $(QUINTILE_CSV)
	$(PYTHON_PLAIN) generate_itep_report.py
	@echo "Report: file://$(HTML_REPORT)"

## Step 1 — Enhanced fiscal impact (REEC/CGEC/TCRA) — needs venv
enhanced $(ENHANCED_CSV):
	$(PYTHON) forecast_sb3125_enhanced.py --cd 2

## Step 2 — ITEP-comparable distributional analysis — needs venv
distributional $(QUINTILE_CSV): $(ENHANCED_CSV)
	$(PYTHON) forecast_sb3125_vs_fy26base.py --cd 2

## Regenerate HTML report from existing CSVs (no venv required)
report:
	$(PYTHON_PLAIN) generate_itep_report.py
	@echo "Report: file://$(HTML_REPORT)"

## Remove all intermediate files to force full rebuild
clean:
	rm -f $(ENHANCED_CSV) $(QUINTILE_CSV) $(HTML_REPORT) \
	      /tmp/cd2_vs_fy26base_bracket_mid_2027_2031.csv \
	      /tmp/sb3125_cd2_fiscal_impact_2027_2031.csv

help:
	@grep -E '^## ' Makefile | sed 's/## /  /'
