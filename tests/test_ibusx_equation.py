"""Where the restored ')' goes in the reconstructed dlog(IBUSX) equation.

The October 2025 listing prints the business-investment equation (l.92)
commented out and one ')' short. The error-correction bracket closes after
KGAP(-2), as in the OBR's Briefing paper No. 5 (October 2013), equation 2.38,
so the impulse dummies and the constant are outside it. These tests evaluate
the transpiled expression directly; no model build.
"""

import numpy as np
import pytest

from obr_macro.reform_analysis import IBUSX_EQ

ECM = -0.0418036
CONSTANT = -0.0884031


def _rhs(lags=None, dummy_period=None):
    """Evaluate the RHS with every growth term and the bracket at zero unless
    overridden: IBUSX(-1) = 1000 and KMSXH(-2) = 1 make
    log(IBUSX(-1)) - log(KMSXH(-2)*1000) = 0."""
    values = {("IBUSX", 1): 1000.0, ("KGAP", 2): 0.0}
    values.update(lags or {})
    ctx = {
        "np": np,
        "__builtins__": {},
        "v": {"CBIUD": 0.0},
        "t": 0,
        "_lag": lambda var, lag: values.get((var, lag), 1.0),
        "_recode": lambda t, period, op, tv, fv: tv if period == dummy_period else fv,
    }
    return eval(IBUSX_EQ.python_expr, ctx)


def test_constant_is_outside_the_error_correction_bracket():
    # With the ')' at the end of the line this was -0.0418036 * -0.0884031
    # = +0.0037.
    assert _rhs() == pytest.approx(CONSTANT, abs=1e-12)


@pytest.mark.parametrize(
    "period, coefficient", [("1998Q1", 0.0544706), ("2005Q2", 0.0597525)]
)
def test_impulse_dummies_enter_at_their_own_coefficient(period, coefficient):
    assert _rhs(dummy_period=period) - _rhs() == pytest.approx(coefficient, abs=1e-12)


def test_bracket_holds_the_capital_gap_at_the_error_correction_coefficient():
    assert _rhs({("KGAP", 2): 1.0}) - _rhs() == pytest.approx(ECM, abs=1e-12)
    assert _rhs({("IBUSX", 1): 1000.0 * np.e}) - _rhs() == pytest.approx(ECM, abs=1e-12)
