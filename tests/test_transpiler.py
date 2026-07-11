"""Pure transpiler / LHS-algebra unit tests. Hermetic: no network, no solver build."""

import numpy as np
import pandas as pd
import pytest

from obr_macro.transpiler import EViewsTranspiler
from obr_macro.full_solver import FullOBRSolver


@pytest.fixture
def tp():
    return EViewsTranspiler()


def make_bare_solver(df: pd.DataFrame) -> FullOBRSolver:
    """Construct a solver without running __init__ (no data download/build)."""
    s = FullOBRSolver.__new__(FullOBRSolver)
    s.data = df
    s.index = df.index
    return s


# ---------------------------------------------------------------------------
# d(X)/X(-n) growth-form reconstruction algebra
# ---------------------------------------------------------------------------

def test_parse_lhs_growth_lag4():
    s = make_bare_solver(pd.DataFrame())
    assert s._parse_lhs("d(X) / X(-4)") == ("X", "growth", 4)
    assert s._parse_lhs("d(CGC)  / CGC(-1)") == ("CGC", "growth", 1)
    assert s._parse_lhs("PCE  / PCE(-4)") == ("PCE", "ratio", 4)


def test_lhs_new_value_growth_roundtrip_lag4():
    # d(X)/X(-4) = rhs  <=>  X = X(-1) + rhs * X(-4)
    idx = pd.period_range("2020Q1", periods=6, freq="Q")
    x = [100.0, 102.0, 104.0, 106.0, 108.0, np.nan]
    s = make_bare_solver(pd.DataFrame({"X": x}, index=idx))
    t = 5
    rhs = 0.05
    new = s._lhs_new_value("X", "growth", 4, rhs, t)
    # X(-1)=108, X(-4)=102 -> 108 + 0.05*102 = 113.1
    assert new == pytest.approx(108.0 + 0.05 * 102.0)
    # Round-trip: d(X)/X(-4) computed from the reconstruction equals rhs
    assert (new - 108.0) / 102.0 == pytest.approx(rhs)


def test_lhs_new_value_growth_lag1_matches_classic_form():
    idx = pd.period_range("2020Q1", periods=3, freq="Q")
    s = make_bare_solver(pd.DataFrame({"Y": [50.0, 60.0, np.nan]}, index=idx))
    # lag 1: X = X(-1)*(1+rhs)
    assert s._lhs_new_value("Y", "growth", 1, 0.1, 2) == pytest.approx(60.0 * 1.1)


def test_lhs_new_value_growth_nan_when_missing_lag():
    idx = pd.period_range("2020Q1", periods=6, freq="Q")
    s = make_bare_solver(pd.DataFrame({"X": [np.nan] * 6}, index=idx))
    assert np.isnan(s._lhs_new_value("X", "growth", 4, 0.05, 5))


def test_parse_lhs_tolerates_whitespace():
    s = make_bare_solver(pd.DataFrame())
    assert s._parse_lhs("dlog (X)") == ("X", "dlog", 1)
    assert s._parse_lhs("d (X) / X( - 4 )") == ("X", "growth", 4)


# ---------------------------------------------------------------------------
# @dateval month vs quarter mapping
# ---------------------------------------------------------------------------

def test_dateval_month_maps_to_quarter(tp):
    out = tp.transpile('@recode(@date = @dateval("2008:07") , 1 , 0)')
    assert "'2008Q3'" in out  # July -> Q3
    out = tp.transpile('@recode(@date = @dateval("2008:05") , 1 , 0)')
    assert "'2008Q2'" in out  # May -> Q2
    out = tp.transpile('@recode(@date = @dateval("2008:12") , 1 , 0)')
    assert "'2008Q4'" in out  # December -> Q4


def test_dateval_quarter_passthrough(tp):
    out = tp.transpile('@recode(@date >= @dateval("2005:02") , 1 , 0)')
    assert "'2005Q2'" in out
    assert "'>='" in out
    out = tp.transpile('@recode(@date = @dateval("1998:01") , 1 , 0)')
    assert "'1998Q1'" in out


# ---------------------------------------------------------------------------
# Lag whitespace and identifiers
# ---------------------------------------------------------------------------

def test_lag_whitespace_tolerated(tp):
    assert tp.transpile("PCE(- 1)") == "_lag('PCE', 1)"
    assert tp.transpile("PCE( -1 )") == "_lag('PCE', 1)"
    assert tp.transpile("PCE(-1)") == "_lag('PCE', 1)"


def test_mixed_case_identifiers(tp):
    out = tp.transpile("OAHHx + DIPHHmf(-1)")
    assert "v['OAHHx']" in out
    assert "_lag('DIPHHmf', 1)" in out


# ---------------------------------------------------------------------------
# dlog / d with whitespace before the paren
# ---------------------------------------------------------------------------

def test_dlog_with_space(tp):
    tight = tp.transpile("dlog(PCE)")
    spaced = tp.transpile("dlog (PCE)")
    assert spaced == tight
    assert "np.log(v['PCE'])" in spaced
    assert "np.log(_lag('PCE', 1))" in spaced


def test_d_with_space(tp):
    tight = tp.transpile("d(GDPM)")
    spaced = tp.transpile("d (GDPM)")
    assert spaced == tight
    assert "v['GDPM']" in spaced
    assert "_lag('GDPM', 1)" in spaced


def test_d_space_normalisation_does_not_touch_identifiers_ending_in_d(tp):
    # 'RXD (' must not be rewritten as a d() difference of RXD's tail.
    out = tp.transpile("RXD + d (GDPM)")
    assert "v['RXD']" in out
    assert "v['GDPM']" in out and "_lag('GDPM', 1)" in out
