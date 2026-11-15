"""Issue #62: the ended EU budget payments GNP4 (l.469) and EUVAT (l.471)
hold their data path (zero from 2021Q1) instead of being regenerated.

The fast tests use the real listing and a bare solver (no data build). The
slow tests solve the pinned reform template over 2025Q1-2027Q4. Before the
fix the solve wrote GNP4 6,321 and EUVAT 1,517 into 2025Q1, and a VAT rise of
2,200 a quarter raised EUVAT by 72-74, booked against the current balance.
"""

import warnings

import numpy as np
import pytest

from obr_macro.full_solver import ENDED_EU_PAYMENTS, FullOBRSolver
from obr_macro.transpiler import parse_model_file

warnings.filterwarnings("ignore")

S, E = "2025Q1", "2027Q4"
VAT = 2200.0  # VREC, GBP m a quarter (VAT +1pp, HMRC ready reckoner / 4)


def _bare():
    s = FullOBRSolver.__new__(FullOBRSolver)
    s.verbose = False
    return s


def test_the_ended_payments_are_live_equations_in_the_listing():
    # If the listing stops carrying them, ENDED_EU_PAYMENTS is stale.
    from obr_macro import DATA_DIR

    eqs = parse_model_file(str(DATA_DIR / "obr_model_code_october_2025.txt"))
    s = _bare()
    lhs = {s._extract_lhs_var(eq.lhs) for eq in eqs}
    assert set(ENDED_EU_PAYMENTS) == {"GNP4", "EUVAT"}
    assert set(ENDED_EU_PAYMENTS) <= lhs


def test_hold_drops_exactly_the_ended_payment_equations():
    from obr_macro import DATA_DIR

    s = _bare()
    s.equations = parse_model_file(str(DATA_DIR / "obr_model_code_october_2025.txt"))
    before = [s._extract_lhs_var(eq.lhs) for eq in s.equations]
    s._hold_ended_eu_payments()
    after = [s._extract_lhs_var(eq.lhs) for eq in s.equations]
    assert sorted(set(before) - set(after)) == ["EUVAT", "GNP4"]
    assert len(before) - len(after) == len(ENDED_EU_PAYMENTS)


@pytest.fixture(scope="module")
def vat_runs():
    from obr_macro.reform_analysis import _build_reform_template

    tpl = _build_reform_template("VREC", S, E, False)
    base = tpl.clone()
    base.solve(S, E)
    shocked = tpl.clone()
    shocked.apply_shock("VREC", VAT, S, periods=12)
    shocked.solve(S, E)
    return base.data.loc[S:E], (shocked.data - base.data).loc[S:E]


@pytest.mark.slow
def test_ended_payments_stay_at_zero_through_a_solve(vat_runs):
    base, _ = vat_runs
    for var in ENDED_EU_PAYMENTS:
        assert (base[var] == 0.0).all(), (var, base[var].abs().max())


@pytest.mark.slow
def test_vat_rise_is_not_booked_as_an_eu_payment(vat_runs):
    _, d = vat_runs
    for var in ("EUVAT", "GNP4"):
        np.testing.assert_allclose(d[var], 0.0, atol=1e-9, err_msg=var)
    # BPAPS carries the VAT rise one for one (was 2,271-2,274 with EUVAT live).
    np.testing.assert_allclose(d["BPAPS"], VAT, atol=1e-6)
