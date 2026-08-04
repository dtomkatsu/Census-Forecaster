"""Guards for the reporting.brief package after its move out of scripts/.

`REPO_ROOT` in brief.data is resolved by counting parent directories, so a
future move of that file would silently point it at the wrong directory —
data loading would then fail with a confusing "no reports found" instead
of an import error. These tests pin the resolution and the palette
single-sourcing.
"""

from __future__ import annotations

from pathlib import Path

from tax_modeler.reporting import palette
from tax_modeler.reporting.brief import (
    BriefData,
    build_html,
    build_pdf,
    load_brief_data,
    make_figures,
)
from tax_modeler.reporting.brief import data as brief_data


def test_repo_root_resolves_to_an_actual_checkout():
    root = brief_data.REPO_ROOT
    assert (root / "pyproject.toml").is_file(), f"REPO_ROOT wrong: {root}"
    assert (root / "reports").is_dir(), f"REPO_ROOT wrong: {root}"
    assert (root / "packages" / "tax_modeler").is_dir(), f"REPO_ROOT wrong: {root}"


def test_repo_root_is_ancestor_of_this_module():
    module_path = Path(brief_data.__file__).resolve()
    assert brief_data.REPO_ROOT in module_path.parents


def test_public_api_importable_from_package():
    """The whole point of the move: importable without a sys.path hack."""
    for obj in (BriefData, load_brief_data, make_figures, build_pdf, build_html):
        assert obj is not None


def test_brief_palette_is_single_sourced():
    assert brief_data.TEAL is palette.TEAL
    assert brief_data.GOLD is palette.GOLD
    assert brief_data.SLATE is palette.SLATE
    assert brief_data.CHARCOAL is palette.CHARCOAL
    assert brief_data.LIGHT_GRAY is palette.LIGHT_GRAY
    assert brief_data.LIGHT_TEAL is palette.LIGHT_TEAL


def test_palette_hex_values_unchanged():
    """Brand guide values — changing these changes published deliverables."""
    assert palette.TEAL == "#005F73"
    assert palette.GOLD == "#E9B949"
    assert palette.SLATE == "#4A4E69"
    assert palette.CHARCOAL == "#2D2D2D"
    assert palette.LIGHT_GRAY == "#F5F5F5"
    assert palette.LIGHT_TEAL == "#E8F4F6"


def test_hex_to_rgb():
    assert palette.hex_to_rgb("#005F73") == (0, 95, 115)
    assert palette.hex_to_rgb("FFFFFF") == (255, 255, 255)


def test_css_vars_cover_dashboard_template():
    assert palette.CSS_VARS["teal"] == palette.TEAL
    assert palette.CSS_VARS["callout"] == palette.LIGHT_TEAL
    assert set(palette.CSS_VARS) == {
        "teal", "gold", "slate", "charcoal", "light", "callout",
    }
