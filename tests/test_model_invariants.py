"""Behavioural invariants for the OBR solver.

Unlike test_solver.py (smoke tests: "did it run, is the number non-zero"),
these pin down the properties the multi-agent review found violated — the ones
a vacuous `assert abs(delta) > 0` cannot catch. They are the regression guard
for the baseline/shock-asymmetry, LHS-parsing and silent-failure fixes.

The solver build is expensive, so the shared baseline solver is built once per
module via a fixture.
"""
import warnings

import numpy as np
import pytest

warnings.filterwarnings("ignore")  # the model overflows a few dead equations by design


@pytest.fixture(scope="module")
def solver():
    from obr_macro import FullOBRSolver
    return FullOBRSolver(verbose=False)


# --- LHS parsing (ratio lag, growth form, mixed-case identifiers) -----------

def test_ratio_lhs_lag_is_parsed_not_hardcoded(solver):
    """'PCE / PCE(-4) = ...' must resolve to lag 4, not the old hardcoded 1."""
    assert solver._parse_lhs("PCE / PCE(-4)") == ("PCE", "ratio", 4)
    assert solver._parse_lhs("GGVA / GGVA(-1)") == ("GGVA", "ratio", 1)


def test_growth_lhs_is_supported(solver):
    """'d(CGC) / CGC(-1) = ...' is a growth-rate LHS: var is CGC, not 'd(CGC)'."""
    var, kind, lag = solver._parse_lhs("d(CGC) / CGC(-1)")
    assert var == "CGC"
    assert kind == "growth"
    # and it must actually be indexed as an equation the solver computes
    assert "CGC" in solver.eq_for_var
    assert not any(k.startswith("d(") for k in solver.eq_for_var)


def test_mixed_case_equations_are_indexed(solver):
    """The uppercase-only regex silently dropped 18 mixed-case equations
    (OAHHx, DIPHHmf, ...). They must now be parsed and indexed."""
    mixed = [v for v in solver.eq_for_var if any(c.islower() for c in v)
             and not v.startswith("log(")]
    assert len(mixed) >= 10, f"expected the mixed-case block back, got {mixed}"


# --- Silent-failure visibility ----------------------------------------------

def test_solve_reports_failures_and_convergence(solver):
    """solve() must expose a report: what failed and which periods converged,
    instead of swallowing every equation error with `except: pass`."""
    s = solver.clone()
    s.solve("2025Q1", "2025Q4")
    rep = s.last_solve_report
    assert rep["periods"] == 4
    assert "eq_failures" in rep and isinstance(rep["eq_failures"], dict)
    assert "exit_status" in rep and set(rep["exit_status"]) >= {"2025Q1", "2025Q4"}
    # exit status must be a known category, never silently "unknown"
    assert all(v in ("tol", "stall", "max_iter") for v in rep["exit_status"].values())


# --- Reform invariants (the baseline/shock-asymmetry fix) -------------------

@pytest.fixture(scope="module")
def spending_reforms():
    """A +/- symmetric pair of CGG shocks plus a zero-shock control, solved once."""
    from obr_macro.reform_analysis import run_reform
    return {
        "zero": run_reform("zero", "CGG", 0, periods=12),
        "plus": run_reform("plus", "CGG", 1250, periods=12),   # +£1.25bn/qtr
        "minus": run_reform("minus", "CGG", -1250, periods=12),
    }


def test_zero_shock_is_exactly_baseline(spending_reforms):
    """A zero shock must reproduce the baseline: identical structure in both
    runs means every delta is exactly zero. This is the guard against the
    asymmetry where the baseline drifted away from the shocked run."""
    z = spending_reforms["zero"]
    assert z["delta_gdp_bn"].abs().max() < 1e-9
    assert z["delta_cons_m"].abs().max() < 1e-6


def test_spending_increase_raises_gdp_on_impact(spending_reforms):
    """A government-consumption increase must raise GDP in the impact quarter.
    Pre-fix, baseline drift flipped this negative."""
    q1 = spending_reforms["plus"]["delta_gdp_bn"].iloc[0]
    assert q1 > 0, f"impact-quarter GDP response should be positive, got {q1}"


def test_demand_multiplier_is_in_plausible_band(spending_reforms):
    """Under the demand closure the impact multiplier is ~1 by construction
    (shock lands in the GDP identity). It must be positive and bounded — a
    runaway (divergence) or a wrong-signed value both fail here."""
    df = spending_reforms["plus"]
    shock_bn = 1.25  # £1.25bn/qtr
    impact_mult = df["delta_gdp_bn"].iloc[0] / shock_bn
    assert 0.3 <= impact_mult <= 1.5, f"impact multiplier {impact_mult:.2f} out of band"
    # and it must not explode over the horizon (divergence check)
    assert df["delta_gdp_bn"].abs().max() < 5 * shock_bn


def test_opposite_shocks_are_antisymmetric(spending_reforms):
    """+shock and -shock must roughly mirror. Gross asymmetry means the result
    is dominated by solver drift, not the policy."""
    plus = spending_reforms["plus"]["delta_gdp_bn"].to_numpy()
    minus = spending_reforms["minus"]["delta_gdp_bn"].to_numpy()
    assert np.abs(plus + minus).max() < 0.05
