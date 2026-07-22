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

pytestmark = pytest.mark.slow  # needs OBR download + full solver build

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
    mixed = [
        v
        for v in solver.eq_for_var
        if any(c.islower() for c in v) and not v.startswith("log(")
    ]
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
        "plus": run_reform("plus", "CGG", 1250, periods=12),  # +£1.25bn/qtr
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


def test_reform_is_deterministic():
    """Same input -> same output. A second identical solve must reproduce the
    first bit-for-bit; any drift means hidden nondeterministic state."""
    from obr_macro.reform_analysis import run_reform

    a = run_reform("det", "CGG", 1250, end="2025Q4", periods=4)
    b = run_reform("det", "CGG", 1250, end="2025Q4", periods=4)
    assert np.array_equal(a["delta_gdp_m"].to_numpy(), b["delta_gdp_m"].to_numpy())
    assert np.array_equal(a["delta_if_m"].to_numpy(), b["delta_if_m"].to_numpy())


# --- Corporation-tax / investment-closure invariant ------------------------


@pytest.fixture(scope="module")
def corp_tax_reforms():
    """A corporation-tax cut and rise under the investment closure, which
    activates the cost-of-capital channel TCPRO -> ... -> IBUSX. Solved once."""
    from obr_macro.reform_analysis import run_reform

    return {
        "cut": run_reform("cut", "TCPRO", -0.05, periods=8, investment_closure=True),
        "rise": run_reform("rise", "TCPRO", 0.05, periods=8, investment_closure=True),
    }


def test_corp_tax_cut_raises_investment(corp_tax_reforms):
    """A corporation-tax CUT must raise business investment (lower user cost of
    capital -> higher desired capital -> more investment). This is the mandated
    fiscal-sign invariant for the investment closure."""
    final_if = corp_tax_reforms["cut"]["delta_if_m"].iloc[-1]
    assert final_if > 0, f"tax cut should raise investment, got {final_if:+,.0f}"


def test_corp_tax_rise_lowers_investment(corp_tax_reforms):
    """The symmetric case: a tax RISE must lower investment."""
    final_if = corp_tax_reforms["rise"]["delta_if_m"].iloc[-1]
    assert final_if < 0, f"tax rise should lower investment, got {final_if:+,.0f}"


def test_corp_tax_investment_response_is_bounded(corp_tax_reforms):
    """The cost-of-capital channel must transmit but not explode: a 5pp tax
    change should move investment by a non-trivial but plausible amount (not
    zero — dead channel — and not a runaway)."""
    cut = corp_tax_reforms["cut"]["delta_if_m"]
    assert cut.abs().max() > 1.0, "investment channel appears dead (no response)"
    # 5pp of corporation tax should not swing quarterly investment by >£50bn
    assert cut.abs().max() < 50_000, "investment response implausibly large"


# --- Anchored baseline: coherence, identities, no NaN/inf -------------------


@pytest.fixture(scope="module")
def anchored():
    """The anchored baseline (add-factors on) solved over the scored horizon.
    By construction it reproduces the EFO published aggregates; here we also
    check it is finite everywhere and that the expenditure identity closes."""
    from obr_macro.baseline import build

    s = build(anchored=True)
    s.solve("2025Q1", "2027Q4")
    return s


def test_anchored_reproduces_efo_published_aggregates(anchored):
    """Add-factors absorb the model's tracking error, so the anchored baseline
    must reproduce the OBR EFO path for the headline published aggregates to a
    tight tolerance. This is the by-construction invariant."""
    from obr_macro.data import load_obr_data

    efo = load_obr_data()
    t0 = anchored.period_idx("2025Q1")
    t1 = anchored.period_idx("2027Q4")
    for code in ("GDPM", "CONS"):
        errs = []
        for t in range(t0, t1 + 1):
            m = anchored.data.iloc[t][code]
            e = efo.iloc[t][code]
            if np.isfinite(m) and np.isfinite(e) and abs(e) > 1e-9:
                errs.append(abs(m - e) / abs(e))
        mape = 100 * np.mean(errs)
        assert mape < 1.0, f"anchored {code} MAPE {mape:.2f}% — not reproducing EFO"


def test_anchored_baseline_has_no_nan_or_inf_in_key_aggregates(anchored):
    """No published aggregate may be NaN/inf anywhere on the solved horizon —
    a non-finite value is a broken transmission chain, not a forecast."""
    t0 = anchored.period_idx("2025Q1")
    t1 = anchored.period_idx("2027Q4")
    key = ["GDPM", "GDPMPS", "CONS", "IF", "X", "M", "ETLFS", "CPI", "HHDI", "CB"]
    hor = anchored.data.iloc[t0 : t1 + 1]
    for code in key:
        if code not in hor.columns:
            continue
        vals = hor[code].to_numpy(dtype=float)
        assert np.isfinite(vals).all(), f"{code} has NaN/inf on the horizon"


def test_gdp_expenditure_identity_closes(anchored):
    """GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE must hold on the solved
    baseline (it is the demand-closure identity). Checks the accounting closes
    and every component is finite — within a small share of GDP."""
    t0 = anchored.period_idx("2025Q1")
    t1 = anchored.period_idx("2027Q4")
    comps = ["CGG", "CONS", "IF", "DINV", "VAL", "X", "M", "SDE"]
    for t in range(t0, t1 + 1):
        row = anchored.data.iloc[t]
        vals = {c: row[c] for c in comps + ["GDPM"]}
        assert all(np.isfinite(v) for v in vals.values()), (
            f"non-finite identity component at {anchored.index[t]}: {vals}"
        )
        rhs = (
            vals["CGG"]
            + vals["CONS"]
            + vals["IF"]
            + vals["DINV"]
            + vals["VAL"]
            + vals["X"]
            - vals["M"]
            + vals["SDE"]
        )
        # close to well within 0.5% of GDP
        assert abs(rhs - vals["GDPM"]) < 0.005 * abs(vals["GDPM"]), (
            f"expenditure identity fails to close at {anchored.index[t]}"
        )


def test_closure_freezes_pif_and_pirhh(corp_tax_rise_results=None):
    """Direct regression for the March-2026 demand-side leaks: under the
    investment closure, PIF and PIRHH must be frozen (finite, equation-free,
    zero base-vs-shock delta), or GGIDEF compounding and property-income
    leakage can flip the IF sign again."""
    import numpy as np

    from obr_macro import reform_analysis as ra

    ra._REFORM_TEMPLATE_CACHE.clear()
    tmpl = ra._build_reform_template("TCPRO", "2025Q1", "2027Q4", True)
    base, shock = tmpl.clone(), tmpl.clone()
    shock.apply_shock("TCPRO", 0.05, "2025Q1", periods=12)
    base.solve("2025Q1", "2027Q4")
    shock.solve("2025Q1", "2027Q4")
    t0, t1 = base.period_idx("2025Q1"), base.period_idx("2027Q4")
    for var in ("PIF", "PIRHH", "MSGVA"):
        assert var not in base.eq_for_var, f"{var} equation not removed"
        b = base.data[var].iloc[t0 : t1 + 1]
        s = shock.data[var].iloc[t0 : t1 + 1]
        assert np.isfinite(b).all(), f"{var} non-finite in baseline"
        assert np.allclose(b, s), f"{var} moved between base and shock"
