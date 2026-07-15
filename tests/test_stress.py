"""Stress tests for the OBR solver.

These push the model outside the gentle reforms in test_model_invariants:
extreme shocks, multiple simultaneous instruments, long horizons and boundary
cases. The property under test is always *robustness* — the solver must stay
finite, deterministic, correctly-signed and non-explosive — not calibration.

All are full-solver tests (marked slow). To keep the wall-clock bounded the
baseline solver is built ONCE per module and every scenario is a cheap clone of
it (the build, not the solve, dominates), mirroring how reform_analysis isolates
a shock: identical structure in the control and shocked runs so the delta is the
policy, not solver drift.
"""

import numpy as np
import pytest

pytestmark = pytest.mark.slow

# Instruments made exogenous on the shared baseline so scenarios can shock them.
# All are direct terms in the demand-closure GDP identity
# (GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE), so each moves GDP on
# impact. (Government investment CGIPS is deliberately excluded: with no live IF
# equation under the demand closure, its GGI -> IF channel does not propagate.)
INSTRUMENTS = ["CGG", "X", "M"]


class ShockLab:
    """Build the demand-closure baseline once; run shocked/control pairs by
    cloning it. `run` returns (base_data, shocked_data) over the horizon."""

    def __init__(self):
        from obr_macro.full_solver import FullOBRSolver
        from obr_macro.reform_analysis import GDPM_EQ

        s = FullOBRSolver(verbose=False)
        s.swap_closure("DINV", GDPM_EQ)  # demand closure: shock lands in GDP
        for v in INSTRUMENTS:
            s.make_exogenous(v)
        s._shock_active = True  # deviation mode: no residual re-anchoring
        self.baseline = s

    def run(self, shocks, start="2025Q1", end="2025Q4", periods=4):
        base = self.baseline.clone()
        shocked = self.baseline.clone()
        for var, amt in shocks.items():
            shocked.apply_shock(var, amt, start, periods=periods)
        base.solve(start, end)
        shocked.solve(start, end)
        return base.data, shocked.data

    def gdp_delta_bn(self, shocks, **kw):
        base, shocked = self.run(shocks, **kw)
        t0 = self.baseline.period_idx(kw.get("start", "2025Q1"))
        t1 = self.baseline.period_idx(kw.get("end", "2025Q4"))
        d = (shocked["GDPM"] - base["GDPM"]).iloc[t0 : t1 + 1]
        return d.to_numpy() / 1000.0  # £bn


@pytest.fixture(scope="module")
def lab():
    return ShockLab()


# --- Boundary: zero shock is exactly the baseline ---------------------------


def test_zero_shock_gives_zero_deviation(lab):
    d = lab.gdp_delta_bn({"CGG": 0.0})
    assert np.abs(d).max() < 1e-9, "zero shock must reproduce the baseline exactly"


# --- Determinism ------------------------------------------------------------


def test_repeated_solve_is_bit_identical(lab):
    d1 = lab.gdp_delta_bn({"CGG": 2000})
    d2 = lab.gdp_delta_bn({"CGG": 2000})
    assert np.array_equal(d1, d2)


# --- Extreme shocks stay finite and correctly signed ------------------------


@pytest.mark.parametrize("shock_m", [50_000, 200_000, -50_000, -200_000])
def test_extreme_spending_shock_finite_and_signed(lab, shock_m):
    """A very large (+/-£50-200bn/qtr) government-spending shock must stay
    finite and move GDP in the shock's direction — no NaN, no sign flip."""
    d = lab.gdp_delta_bn({"CGG": shock_m})
    assert np.isfinite(d).all(), "extreme shock produced NaN/inf GDP"
    assert np.sign(d[0]) == np.sign(shock_m), "impact GDP moved the wrong way"


def test_extreme_shock_does_not_explode(lab):
    """Even a huge shock must not blow the multiplier up: under the demand
    closure the impact multiplier is ~1, so ΔGDP should stay within a few times
    the shock rather than diverging by orders of magnitude."""
    shock_bn = 200.0  # £200bn/qtr
    d = lab.gdp_delta_bn({"CGG": shock_bn * 1000})
    assert np.abs(d).max() < 10 * shock_bn, "response diverged from the shock scale"


# --- Monotonicity: bigger shock, bigger response ----------------------------


def test_response_grows_with_shock_size(lab):
    small = lab.gdp_delta_bn({"CGG": 1000})[0]
    big = lab.gdp_delta_bn({"CGG": 10_000})[0]
    assert big > small > 0, "impact response is not monotone in shock size"
    # roughly linear under the demand closure: 10x shock -> ~10x response
    assert 5 < big / small < 20, f"response scaling {big / small:.1f} implausible"


# --- Multiple simultaneous shocks -------------------------------------------


def test_multiple_simultaneous_shocks_are_finite_and_additive(lab):
    """Two positive demand instruments together must raise GDP, stay finite,
    and land near the sum of their individual effects (approximate linearity of
    the demand closure). Government consumption + exports, both +£3bn/qtr."""
    only_cgg = lab.gdp_delta_bn({"CGG": 3000})[0]
    only_x = lab.gdp_delta_bn({"X": 3000})[0]
    both = lab.gdp_delta_bn({"CGG": 3000, "X": 3000})[0]
    assert np.isfinite(both) and both > 0
    assert only_cgg > 0 and only_x > 0, "each instrument must move GDP on its own"
    # additive to within 25% (some nonlinearity / cross-effects allowed)
    assert abs(both - (only_cgg + only_x)) < 0.25 * abs(only_cgg + only_x) + 1e-6


# --- Long horizon -----------------------------------------------------------


def test_long_horizon_stays_finite_and_bounded(lab):
    """Solve many periods with a sustained shock; the path must remain finite
    and bounded (no slow blow-up from accumulating lag terms)."""
    d = lab.gdp_delta_bn({"CGG": 1250}, start="2025Q1", end="2027Q4", periods=12)
    assert np.isfinite(d).all(), "long-horizon solve produced NaN/inf"
    assert np.abs(d).max() < 50.0, "long-horizon response blew up"
    assert (d > 0).all(), "sustained spending increase should keep GDP above baseline"
