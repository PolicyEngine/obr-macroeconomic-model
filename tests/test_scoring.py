"""Unit tests for the shared scoring helpers (obr_macro/scoring.py).

Hermetic: no network, no solver build. These lock the *metric* semantics the
scorecards depend on — the band thresholds and the three error metrics
(pp / gdp / lvl) — so a future refactor cannot silently change what "within
band" means or which yardstick a variable is scored against.
"""

import numpy as np
import pandas as pd
import pytest

from obr_macro.scoring import (
    GDP_FAIR,
    LVL_FAIR,
    PP_FAIR,
    band,
    gdp_col,
    var_error,
)


# --- band() thresholds ------------------------------------------------------


@pytest.mark.parametrize(
    "kind,err,mark",
    [
        ("pp", 0.1, "OK"),
        ("pp", 0.5, "~"),
        ("pp", 2.0, "!"),
        ("pp", 5.0, "X"),
        ("gdp", 0.2, "OK"),
        ("gdp", 1.0, "~"),
        ("gdp", 2.0, "!"),
        ("gdp", 10.0, "X"),
        ("lvl", 1.0, "OK"),
        ("lvl", 5.0, "~"),
        ("lvl", 20.0, "!"),
        ("lvl", 99.0, "X"),
    ],
)
def test_band_classification(kind, err, mark):
    assert band(kind, err) == mark


def test_band_nonfinite_is_off():
    assert band("lvl", None) == "X"
    assert band("lvl", float("nan")) == "X"
    assert band("lvl", float("inf")) == "X"


def test_band_thresholds_are_boundaries():
    # A value exactly on the fair threshold is NOT within the fair band.
    assert band("pp", PP_FAIR) == "!"
    assert band("gdp", GDP_FAIR) == "!"
    assert band("lvl", LVL_FAIR) == "!"
    # Just under is fair.
    assert band("pp", PP_FAIR - 1e-9) == "~"
    assert band("gdp", GDP_FAIR - 1e-9) == "~"
    assert band("lvl", LVL_FAIR - 1e-9) == "~"


# --- var_error() metrics ----------------------------------------------------


def _frames(model_vals, efo_vals, gdp_vals=None, code="Z"):
    idx = pd.period_range("2025Q1", periods=len(model_vals), freq="Q")
    m = pd.DataFrame({code: model_vals}, index=idx)
    cols = {code: efo_vals}
    if gdp_vals is not None:
        cols["GDPM"] = gdp_vals
    e = pd.DataFrame(cols, index=idx)
    return m, e


def test_var_error_lvl_is_mape():
    # |110-100|/100 = 10%, |90-100|/100 = 10% -> mean 10%
    m, e = _frames([110.0, 90.0], [100.0, 100.0])
    assert var_error(m, e, "Z", "lvl", 0, 1) == pytest.approx(10.0)


def test_var_error_pp_is_absolute_gap():
    # rates: mean(|m-e|) in points, no normalisation
    m, e = _frames([4.4, 2.0], [4.0, 4.0])
    assert var_error(m, e, "Z", "pp", 0, 1) == pytest.approx((0.4 + 2.0) / 2)


def test_var_error_gdp_normalises_by_gdp_not_own_value():
    # net balance: |m-e| as % of GDP, not % of the tiny balance itself
    m, e = _frames([-20.0], [-10.0], gdp_vals=[1000.0])
    # |(-20)-(-10)| / 1000 * 100 = 1.0% of GDP
    assert var_error(m, e, "Z", "gdp", 0, 0) == pytest.approx(1.0)


def test_var_error_skips_nonfinite_pairs():
    m, e = _frames([np.nan, 110.0], [100.0, 100.0])
    # only the finite pair (110 vs 100) counts
    assert var_error(m, e, "Z", "lvl", 0, 1) == pytest.approx(10.0)


def test_var_error_none_when_no_finite_pairs():
    m, e = _frames([np.nan], [np.nan])
    assert var_error(m, e, "Z", "lvl", 0, 0) is None


def test_var_error_none_when_code_absent():
    m, e = _frames([1.0], [1.0])
    assert var_error(m, e, "MISSING", "lvl", 0, 0) is None


def test_gdp_col_prefers_market_price_gdp():
    assert gdp_col(pd.DataFrame(columns=["GDPMPS", "GDPM"])) == "GDPMPS"
    assert gdp_col(pd.DataFrame(columns=["GDPM"])) == "GDPM"


def test_var_error_efo_code_override_scores_against_named_series():
    # The RPI case: model column "RPI" (an inflation rate) must be scored
    # against the EFO "RPIGR" series, not against an EFO "RPI" index. The
    # override selects the right EFO column even when both exist.
    idx = pd.period_range("2025Q1", periods=2, freq="Q")
    model = pd.DataFrame({"RPI": [3.4, 4.4]}, index=idx)
    efo = pd.DataFrame(
        {"RPI": [400.0, 405.0], "RPIGR": [3.4, 4.0]},  # index vs inflation rate
        index=idx,
    )
    # Without the override, RPI-vs-RPI(index) is a nonsense ~99% gap.
    naive = var_error(model, efo, "RPI", "pp", 0, 1)
    assert naive > 100
    # With the override, RPI-vs-RPIGR is the true pp gap: mean(|3.4-3.4|,|4.4-4.0|)
    scored = var_error(model, efo, "RPI", "pp", 0, 1, efo_code="RPIGR")
    assert scored == pytest.approx((0.0 + 0.4) / 2)


def test_var_error_efo_code_override_missing_column_is_none():
    idx = pd.period_range("2025Q1", periods=1, freq="Q")
    model = pd.DataFrame({"RPI": [3.4]}, index=idx)
    efo = pd.DataFrame({"RPI": [400.0]}, index=idx)
    assert var_error(model, efo, "RPI", "pp", 0, 0, efo_code="RPIGR") is None


def test_held_addfactors_average_the_base_window_only():
    """The held add-factor is the mean residual over the last ``window``
    quarters up to the base end; quarters outside it and non-finite residuals
    are left out, and a variable with no usable residual gets no add-factor."""
    from obr_macro.forecast_tune import held_addfactors

    quarters = {"2025Q1": 4, "2025Q2": 5, "2025Q3": 6, "2025Q4": 7}
    residuals = {
        ("CONS", 3): 100.0,  # before a 2-quarter window ending 2025Q4
        ("CONS", 6): 10.0,
        ("CONS", 7): 30.0,
        ("CONS", 8): 1000.0,  # after the base window
        ("IBUS", 6): float("nan"),
        ("IBUS", 7): -4.0,
        ("M", 7): float("inf"),
    }
    held = held_addfactors(residuals, quarters.__getitem__, "2025Q4", window=2)
    assert held == {"CONS": 20.0, "IBUS": -4.0}
    assert held_addfactors(residuals, quarters.__getitem__, "2025Q4", window=1) == {
        "CONS": 30.0,
        "IBUS": -4.0,
    }
    wide = held_addfactors(residuals, quarters.__getitem__, "2025Q4", window=5)
    assert wide["CONS"] == pytest.approx((100.0 + 10.0 + 30.0) / 3)
