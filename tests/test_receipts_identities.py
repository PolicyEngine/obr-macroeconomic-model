"""Fast tests for issue #56: receipts identities and the silent-drop guard.

No model build or full solve. A bare solver with a toy frame and equations
parsed by the real transpiler covers (a) the drop guard in solve() and (b) the
identity-residual closure in _close_receipts_identities. The EFO loader is
checked against the committed October 2026 receipts workbook. The full-model
check (VAT, CT, fuel duty and income tax reach PSCR/CGNB one for one) is the
slow test in tests/test_tax_scenarios.py.
"""

import warnings

import numpy as np
import pandas as pd
import pytest

from obr_macro.data import (
    EFO_RECEIPT_COMPONENTS,
    ZERO_RECEIPT_COMPONENTS,
    load_efo_receipt_components,
    load_obr_data,
)
from obr_macro.full_solver import (
    KNOWN_NONFINITE_EQUATIONS,
    RECEIPTS_IDENTITIES,
    DroppedEquationError,
    FullOBRSolver,
)
from obr_macro.transpiler import EViewsTranspiler

warnings.filterwarnings("ignore")


def _toy(equations, columns, periods=4):
    s = FullOBRSolver.__new__(FullOBRSolver)
    s.verbose = False
    s._code_cache = {}
    s._hist_floor = "2025Q1"
    s.base_values = {}
    s.residuals = {}
    s.add_factors = {}
    s.log_add_factors = {}
    s.anchor_residuals = False
    s.anchor_terms = None
    s._shock_active = False
    s.max_iter = 20
    tr = EViewsTranspiler()
    s.equations = [tr.parse_equation(e) for e in equations]
    s._build_equation_index()
    index = pd.period_range("2025Q1", periods=periods, freq="Q")
    s.data = pd.DataFrame(
        {k: [float(v)] * periods for k, v in columns.items()}, index=index
    )
    s.index = s.data.index
    s.baseline = s.data.copy()
    return s


def test_solve_raises_when_an_identity_input_is_nan():
    # Before #56 this solve silently left CETAX at its data value.
    s = _toy(["CETAX = VREC + CUST"], {"CETAX": 100, "VREC": 90, "CUST": np.nan})
    with pytest.raises(DroppedEquationError, match="CETAX"):
        s.solve("2025Q1", "2025Q4")


def test_listed_exclusion_is_allowed_and_reported():
    s = _toy(["CETAX = VREC + CUST"], {"CETAX": 100, "VREC": 90, "CUST": np.nan})
    s.allowed_nonfinite = frozenset({"CETAX"})
    s.solve("2025Q1", "2025Q4")
    assert s.last_solve_report["dropped"] == ["CETAX"]
    assert (s.data["CETAX"] == 100).all()


def test_receipts_identities_are_not_listed_exclusions():
    assert not set(RECEIPTS_IDENTITIES) & set(KNOWN_NONFINITE_EQUATIONS)
    # PSCR and CGNB carry every receipts shock; they must never be excluded.
    assert not {"PSCR", "CGNB"} & set(KNOWN_NONFINITE_EQUATIONS)


def test_identity_residual_keeps_baseline_and_passes_shock_one_for_one():
    # CUST is absent, as in the real databank: _close_receipts_identities seeds
    # it from the EFO and holds CETAX's data path with an identity residual.
    s = _toy(
        ["CETAX = VREC + TXFUEL + CUST"],
        {"CETAX": 70000, "VREC": 45000, "TXFUEL": 6000},
    )
    s._close_receipts_identities()
    assert np.isfinite(s.data["CUST"]).all()
    base = s.clone()
    base.solve("2025Q1", "2025Q4")
    np.testing.assert_allclose(base.data["CETAX"], 70000, atol=1e-9)

    shocked = s.clone()
    shocked.apply_shock("VREC", 2200, "2025Q1", periods=4)
    shocked.solve("2025Q1", "2025Q4")
    np.testing.assert_allclose(shocked.data["CETAX"] - base.data["CETAX"], 2200)


def test_efo_receipt_components_follow_the_fiscal_year():
    idx = pd.period_range("2024Q1", "2031Q4", freq="Q")
    c = load_efo_receipt_components(idx)
    assert set(c) == set(EFO_RECEIPT_COMPONENTS)
    # EFO October 2026 table 4.8, customs duties 2025-26 (outturn) = £4.972bn,
    # spread over 2025Q2-2026Q1; 2026-27 = £5.117bn.
    assert c["CUST"][pd.Period("2025Q2", "Q")] == pytest.approx(4972.0 / 4, abs=0.01)
    assert c["CUST"][pd.Period("2026Q1", "Q")] == pytest.approx(4972.0 / 4, abs=0.01)
    assert c["CUST"][pd.Period("2026Q2", "Q")] == pytest.approx(5116.98 / 4, abs=0.01)
    # Table 4.2, lorry road user levy 2025-26 = £0.160bn; held before. The
    # October tables start at 2025-26 (March started at 2024-25), so 2025Q1
    # now takes the 2025-26 value; the level only splits each identity
    # between component and residual, so the identity's data path is kept.
    assert c["RULC"][pd.Period("2024Q1", "Q")] == pytest.approx(160 / 4)
    for s in c.values():
        assert np.isfinite(s).all() and (s >= 0).all()
    assert not set(ZERO_RECEIPT_COMPONENTS) & set(EFO_RECEIPT_COMPONENTS)


def test_household_tax_identity_is_closed_on_its_data_path():
    """TYWHH (l.612) sums non-seasonally-adjusted ONS cash components (self-
    assessment and capital gains tax land in January) against a seasonally
    adjusted aggregate. It is closed with an identity residual like the #56
    receipts identities, mirroring the OBR's own TYWHH_A (l.613)."""
    assert "TYWHH" in RECEIPTS_IDENTITIES


def test_household_tax_gap_is_seasonal_in_the_data():
    """The data gap TYWHH - (TYEM + TSEOP + CC + CGT + OCT - NPISHTC) is large
    and negative every Q1 and nets to roughly zero over a calendar year: a
    seasonal-basis artefact, not a level error. Measured 16 Nov 2026: Q1 gaps
    -33.7bn (2024) and -35.4bn (2025); annual sums -0.9bn and -0.7bn."""
    e = load_obr_data()
    rhs = e["TYEM"] + e["TSEOP"] + e["CC"] + e["CGT"] + e["OCT"] - e["NPISHTC"]
    gap = (e["TYWHH"] - rhs).loc["2024Q1":"2025Q4"]
    for y in (2024, 2025):
        q = gap.loc[f"{y}Q1" : f"{y}Q4"]
        assert q.iloc[0] < -25000, (y, q.iloc[0])
        assert abs(q.sum()) < 3000, (y, q.sum())


@pytest.mark.slow
def test_raw_household_income_has_no_q1_spike():
    """With TYWHH closed, the raw (free-running) solve's household income moves
    by revision-size amounts quarter to quarter; before, it fell 10.6% in
    2025Q1 and 12.5% in 2026Q1 and rebounded the next quarter."""
    from obr_macro.calibration_score import raw_solve

    s, *_ = raw_solve(nominal_gdp_pin=True)
    g = s.data.loc["2025Q1":"2027Q4", "HHDI"].astype(float).pct_change().dropna()
    assert g.abs().max() < 0.05, g.round(4).to_dict()


@pytest.mark.slow
def test_income_tax_still_passes_one_for_one_with_tywhh_closed():
    """The residual is additive and cancels in a delta: an income-tax shock
    still moves TYWHH, receipts and borrowing one for one."""
    from obr_macro.reform_analysis import _build_reform_template

    tpl = _build_reform_template("TYEM", "2025Q1", "2027Q4", False)
    base, k = tpl.clone(), tpl.clone()
    k.apply_shock("TYEM", 1725.0, "2025Q1", periods=12)
    base.solve("2025Q1", "2027Q4")
    k.solve("2025Q1", "2027Q4")
    for col, sign in (("TYWHH", 1), ("PSCR", 1), ("CGNB", -1)):
        d = (k.data[col] - base.data[col]).loc["2025Q1":"2027Q4"].to_numpy(float)
        np.testing.assert_allclose(d, sign * 1725.0, atol=1e-6, err_msg=col)
