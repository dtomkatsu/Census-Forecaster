"""Tests for versioned forecast artifacts (calibrated bases + cache sidecars)."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from tax_modeler.artifacts import (
    ARTIFACT_VERSION,
    canonical_deduction_params_path,
    check_cache_sidecar,
    load_calibrated_base,
    load_canonical_deduction_params,
    params_fingerprint,
    save_calibrated_base,
    write_cache_sidecar,
)


@pytest.fixture
def units_df():
    return pd.DataFrame({
        "income": [50_000.0, 1_200_000.0],
        "weight": [10.0, 1.5],
        "filing_status": ["single", "married_filing_jointly"],
    })


_PARAMS = {"mortgage_share": 0.31, "salt_cap": 10_000, "tax_year": 2023}


def test_canonical_params_exist_and_load():
    assert canonical_deduction_params_path().exists()
    params = load_canonical_deduction_params()
    assert isinstance(params, dict) and params


def test_fingerprint_stable_and_order_insensitive():
    a = {"x": 1, "y": [1, 2]}
    b = {"y": [1, 2], "x": 1}
    assert params_fingerprint(a) == params_fingerprint(b)
    assert len(params_fingerprint(a)) == 16
    assert params_fingerprint(a) != params_fingerprint({"x": 2, "y": [1, 2]})


def test_calibrated_base_round_trip(tmp_path, units_df):
    path = tmp_path / "base.pkl"
    save_calibrated_base(
        units_df, path, deduction_params=_PARAMS, tax_year=2023,
        extra_meta={"built_by": "test"},
    )
    units, params, meta = load_calibrated_base(path)

    pd.testing.assert_frame_equal(units, units_df)
    assert params == _PARAMS
    assert meta["tax_year"] == 2023
    assert meta["n_units"] == 2
    assert meta["built_by"] == "test"
    assert meta["params_fingerprint"] == params_fingerprint(_PARAMS)
    assert "created_at" in meta and "git_sha" in meta


def test_round_trip_with_expected_params_ok(tmp_path, units_df):
    path = tmp_path / "base.pkl"
    save_calibrated_base(units_df, path, deduction_params=_PARAMS, tax_year=2023)
    units, params, _ = load_calibrated_base(path, expected_params=_PARAMS)
    assert params == _PARAMS


def test_fingerprint_mismatch_raises(tmp_path, units_df):
    path = tmp_path / "base.pkl"
    save_calibrated_base(units_df, path, deduction_params=_PARAMS, tax_year=2023)
    stale = dict(_PARAMS, salt_cap=99_999)
    with pytest.raises(ValueError, match="Stale calibrated-base artifact"):
        load_calibrated_base(path, expected_params=stale)


def test_legacy_bare_dataframe_falls_back_to_canonical(tmp_path, units_df, caplog):
    path = tmp_path / "legacy.pkl"
    units_df.to_pickle(path)  # old format: bare DataFrame

    with caplog.at_level("WARNING"):
        units, params, meta = load_calibrated_base(path)

    pd.testing.assert_frame_equal(units, units_df)
    assert params == load_canonical_deduction_params()
    assert meta["artifact_version"] == 0
    assert any("Legacy bare-DataFrame" in r.message for r in caplog.records)


def test_unrecognized_payload_raises(tmp_path):
    path = tmp_path / "bad.pkl"
    pd.to_pickle({"not_units": 1}, path)
    with pytest.raises(ValueError, match="Unrecognized calibrated-base artifact"):
        load_calibrated_base(path)


def test_save_creates_parent_dirs(tmp_path, units_df):
    path = tmp_path / "deep" / "nested" / "base.pkl"
    save_calibrated_base(units_df, path, deduction_params=_PARAMS, tax_year=2023)
    assert path.exists()


def test_artifact_version_recorded(tmp_path, units_df):
    path = tmp_path / "base.pkl"
    save_calibrated_base(units_df, path, deduction_params=_PARAMS, tax_year=2023)
    payload = pd.read_pickle(path)
    assert payload["artifact_version"] == ARTIFACT_VERSION


# ---------------------------------------------------------------------------
# Parquet cache sidecars
# ---------------------------------------------------------------------------

def test_sidecar_round_trip(tmp_path, units_df):
    cache = tmp_path / "cache.parquet"
    units_df.to_parquet(cache, index=False)
    sidecar = write_cache_sidecar(cache, extra={"built_by": "test", "n_units": 2})
    assert sidecar == tmp_path / "cache.meta.json"

    meta = check_cache_sidecar(cache)
    assert meta is not None
    assert meta["built_by"] == "test"
    assert meta["n_units"] == 2
    assert "git_sha" in meta and "created_at" in meta


def test_missing_sidecar_warns_and_returns_none(tmp_path, units_df, capsys, caplog):
    cache = tmp_path / "cache.parquet"
    units_df.to_parquet(cache, index=False)

    with caplog.at_level("WARNING"):
        meta = check_cache_sidecar(cache)

    assert meta is None
    out = capsys.readouterr().out
    assert "no provenance sidecar" in out
    assert any("no provenance sidecar" in r.message for r in caplog.records)


def test_git_sha_mismatch_warns_but_returns_meta(tmp_path, units_df, capsys):
    cache = tmp_path / "cache.parquet"
    units_df.to_parquet(cache, index=False)
    sidecar = tmp_path / "cache.meta.json"
    sidecar.write_text(json.dumps({
        "created_at": "2026-01-01T00:00:00+00:00",
        "git_sha": "deadbeef",  # never the current HEAD
    }))

    meta = check_cache_sidecar(cache)
    assert meta is not None  # never aborts — warning only
    assert meta["git_sha"] == "deadbeef"
    assert "was built at git deadbeef" in capsys.readouterr().out
