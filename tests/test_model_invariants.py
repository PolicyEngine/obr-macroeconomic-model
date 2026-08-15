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


def test_demand_closure_results_carry_passthrough_warning(spending_reforms):
    """Demand-closure reform output must be honestly labelled: the GDP delta
    is mechanical passthrough (flat ~1.0 multiplier, no behavioural
    second-round effects), and run_reform must say so in metadata rather than
    presenting it as a validated multiplier profile."""
    df = spending_reforms["plus"]
    assert df.attrs.get("mechanical_passthrough") is True
    assert "passthrough" in df.attrs.get("multiplier_warning", "")
    # The warning must name the published benchmark it FAILS, not a benchmark
    # it happens to match. (It previously claimed the impact quarter matched
    # "the OBR's ~1.0 multiplier for government consumption"; 1.0 is the OBR's
    # CAPITAL-spending multiplier — its current-spending one is 0.6.)
    assert df.attrs["obr_published_impact_multiplier"]["current_spending"] == 0.6
    assert "0.6" in df.attrs["multiplier_warning"]


def test_government_consumption_multiplier_gap_vs_obr_is_pinned(spending_reforms):
    """THE model's most important weakness, measured rather than described.

    The OBR's published impact multiplier for CURRENT spending is 0.6, decaying
    to zero as the output gap closes. This model returns a flat accounting
    passthrough. Both facts are pinned here so neither can drift unnoticed: if
    a genuine behavioural channel is ever activated the multiplier will leave
    the passthrough band and this test will fail, which is the signal to
    re-measure against the OBR range rather than to widen the band.
    """
    df = spending_reforms["plus"]
    shock_bn = 1.25
    mult = (df["delta_gdp_bn"] / shock_bn).to_numpy()

    # 1. It is passthrough: 1.0 on impact, to well within a tenth of a percent.
    assert abs(mult[0] - 1.0) < 1e-3, f"impact multiplier {mult[0]:.4f} is not 1.0"
    # 2. It is FLAT: no decay anywhere on a 12-quarter horizon (the OBR's
    #    would be materially below its impact value by the end).
    assert abs(mult[-1] - mult[0]) < 0.01, (
        f"multiplier moved from {mult[0]:.4f} to {mult[-1]:.4f} — if a decay "
        "channel is now live, re-benchmark against the OBR profile"
    )
    # 3. Consumption does not respond: the income->consumption chain is inert,
    #    so the "multiplier" contains no behaviour at all.
    assert df["delta_cons_m"].abs().max() < 0.001 * 1250, (
        "consumption now responds to a spending shock — the multiplier is no "
        "longer pure passthrough and must be re-benchmarked"
    )
    # 4. The gap against the published OBR figure, stated as a number.
    obr_current_spending = df.attrs["obr_published_impact_multiplier"][
        "current_spending"
    ]
    overstatement = mult[0] / obr_current_spending
    assert 1.6 < overstatement < 1.75, (
        f"impact multiplier is {overstatement:.2f}x the OBR's published "
        f"current-spending multiplier of {obr_current_spending}"
    )


def test_government_investment_channel_is_dead_and_says_so():
    """CGIPS has no path to GDP under the demand closure (IF has no live
    equation), so a GBP 12bn/year public investment programme moves total
    investment by EXACTLY zero and GDP by a wrong-signed deflator residue.
    That is a defect this repo cannot fix without inventing an equation the
    OBR did not publish — so it must be announced, not silently returned as a
    public-investment multiplier."""
    from obr_macro.reform_analysis import run_reform

    with pytest.warns(UserWarning, match="NO transmission path"):
        df = run_reform("cgips", "CGIPS", 3000.0, periods=12)
    assert df.attrs["dead_channel"] is True
    # Exactly zero, not approximately: nothing connects the chain.
    assert (df["delta_if_m"] == 0.0).all(), (
        "CGIPS now reaches total investment — the channel is alive; delete "
        "this test and benchmark it against the OBR's 1.0 capital multiplier"
    )
    # And the GDP residue is negligible next to the shock, so nobody can read
    # it as a multiplier of either sign.
    assert df["delta_gdp_bn"].abs().max() < 0.1 * 3.0


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
    activates the cost-of-capital channel TCPRO -> ... -> IBUSX. Solved once.

    Deliberately NOT promoted to the PR-gating fast suite: even at the
    shortest meaningful horizon (the investment response only starts in the
    3rd shocked quarter) one run costs ~2 minutes, dominated by the
    FullOBRSolver build (~100s) rather than the solve, so no horizon trim can
    reach the fast suite's seconds-scale budget. It stays a --runslow gate."""
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


def test_corp_tax_rate_cannot_leave_its_usable_domain():
    """The cost-of-capital block has a pole at TCPRO = 1: above it, TAF and COC
    go negative, log(COC) in KSTAR is undefined, solve_period silently drops
    the equation, and the run returns a FINITE, WRONG-SIGNED answer. Measured
    before the guard: shocking TCPRO 0.25 -> 1.05 reported delta_IF = +£3.2bn,
    i.e. a 105% corporation tax raising business investment, with no error and
    no warning. Both ends of the domain must now be refused up front.

    (Uses the same start/end as the other corporation-tax tests so it reuses the
    cached reform template rather than paying for another solver build.)"""
    from obr_macro.reform_analysis import run_reform

    for shock, why in ((0.80, "TCPRO -> 1.05"), (-0.30, "TCPRO -> -0.05")):
        with pytest.raises(ValueError, match="usable domain"):
            run_reform(
                why,
                "TCPRO",
                shock,
                start="2025Q1",
                end="2027Q4",
                periods=12,
                investment_closure=True,
            )
    # A rate at the edges of the domain is fine: 0% corporation tax is a
    # policy, 100% is a pole.
    from obr_macro.reform_analysis import _check_instrument_domain
    from obr_macro import reform_analysis as ra

    tmpl = ra._build_reform_template("TCPRO", "2025Q1", "2027Q4", True)
    _check_instrument_domain(tmpl, "TCPRO", [-0.25] * 4, "2025Q1")  # -> 0.0, ok
    with pytest.raises(ValueError, match="usable domain"):
        _check_instrument_domain(tmpl, "TCPRO", [0.75] * 4, "2025Q1")  # -> 1.0


def test_corp_tax_deviation_converges_to_its_steady_state():
    """The investment closure's deviation now has a steady state — the genuine
    improvement the predecessor of this test (
    test_corp_tax_deviation_never_settles_and_says_so) reserved as its escape
    hatch: "if the deviation now converges ... that is a real improvement:
    retire the flag". Retired 2026-08 and re-pinned here.

    Before: LEVEL add-factors on the log-difference dlog(IBUSX) anchor
    multiplied the base-vs-shock deviation by rho = 1 - af/level ~ 1.18-1.28
    every quarter (af/level measured at -0.18 to -0.27), which was the whole
    of the observed 1.21-1.27x compounding — |delta_IF| for a sustained +5pp
    rise hit £2.88bn at q12 and £43.4bn at q25 with no steady state.

    After (log-space anchoring restores the published equation's -0.0418
    error-correction root, and the estimated allowance PVs reset the target):
    the deviation converges monotonically from below towards
    dlog(KSTAR) = -0.4*dlog(TAF), measured |delta_IF| £0.24bn at q8, £0.38bn
    at q12, £0.68bn at q25 against an analytic plateau of ~£0.95bn/q, with
    q-on-q growth falling 1.90 -> 1.023 by q25 and never rising. The root is
    slow (~0.958/quarter), so the 12-quarter figure is ~40% of the plateau —
    pinned below via the plateau_fraction attr so nobody mistakes a partial
    response for a settled one.
    """
    from obr_macro.reform_analysis import run_reform

    # Record warnings rather than erroring on them: a fresh template build can
    # legitimately emit unrelated model-file warnings; what must NOT appear is
    # the divergence warning.
    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        short = run_reform(
            "12q",
            "TCPRO",
            0.05,
            start="2025Q1",
            end="2027Q4",
            periods=12,
            investment_closure=True,
        )
    assert not [w for w in rec if "does not converge" in str(w.message)], (
        "the divergence warning is back — the deviation dynamics regressed"
    )
    assert short.attrs["investment_closure_diverging"] is False
    growth = short.attrs["investment_closure_tail_qoq_growth"]
    assert 1.0 < growth < 1.15, (
        f"q12 tail growth {growth:.3f} outside the converging band (measured "
        "1.095: still rising towards the plateau, no longer compounding at "
        "1.21-1.27)"
    )
    frac = short.attrs["investment_closure_plateau_fraction"]
    assert 0.2 < frac < 1.02, (
        f"q12 deviation is {frac:.2f}x its steady-state target (measured 0.40); "
        "a stable path must approach 1 from below, never overshoot"
    )
    # The path rises monotonically towards the plateau (no oscillation).
    d = short["delta_if_m"].abs().to_numpy()
    live = d[d > 1e-9]
    assert (np.diff(live) > 0).all(), "path towards the plateau is not monotone"

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        long = run_reform(
            "25q",
            "TCPRO",
            0.05,
            start="2025Q1",
            end="2031Q1",
            periods=25,
            investment_closure=True,
        )
    assert not [w for w in rec if "does not converge" in str(w.message)], (
        "the divergence warning is back at 25 quarters"
    )
    assert long.attrs["investment_closure_diverging"] is False
    dl = long["delta_if_m"].abs().to_numpy()
    # Plateau criterion (issue #31): by the far end the response must be
    # flattening, not compounding. Measured: final q-on-q growth 1.023 and
    # every quarter's growth smaller than the one before.
    qoq = dl[13:] / dl[12:-1]  # growth over the back half of the path
    assert qoq[-1] < 1.03, f"final q-on-q growth {qoq[-1]:.3f} — not flattening"
    assert (np.diff(qoq) < 0).all(), "q-on-q growth is no longer declining"
    # No overshoot of the steady-state target even at 25 quarters.
    assert long.attrs["investment_closure_plateau_fraction"] < 1.02
    # Doubling the horizon now approaches the plateau (~1.8x the q12 figure,
    # measured 677/381); the broken dynamics multiplied it by ~15x.
    ratio = abs(long["delta_if_m"].iloc[-1]) / abs(short["delta_if_m"].iloc[-1])
    assert ratio < 2.5, f"horizon doubling scaled the response {ratio:.1f}x"


def test_corp_tax_response_tracks_the_tax_rate_not_drift():
    """The drift symptom the predecessor of this test (
    test_corp_tax_response_is_dominated_by_drift_not_by_the_tax_rate) pinned
    is gone — the "if the response now tracks the tax rate ... that is a real
    fix" escape hatch it reserved, exercised 2026-08 with the log-anchoring
    fix (see test_corp_tax_deviation_converges_to_its_steady_state).

    Before: truncating the shock from 12 quarters to 8 left the q11/q12
    response almost unchanged AND STILL GROWING (measured 2,170 -> 2,662 £m
    with the tax rate back at baseline) — the number was accumulated drift.
    After: once the tax rate returns to baseline the truncated response turns
    around and decays (measured q11 308 -> q12 303 £m, vs the sustained run
    still rising 348 -> 381), i.e. the deviation follows its steady-state
    target back down. The decay is slow — the same ~0.958/quarter
    error-correction root that makes the build-up gradual (q12 truncated/full
    = 0.79) — so the response carries genuine capital-stock history, but it
    now has the right SHAPE: rate off, response falling."""
    from obr_macro.reform_analysis import run_reform

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        full = run_reform(
            "12q", "TCPRO", 0.05, end="2027Q4", periods=12, investment_closure=True
        )
        trunc = run_reform(
            "8q", "TCPRO", 0.05, end="2027Q4", periods=8, investment_closure=True
        )
    # Same reporting window, four fewer shocked quarters.
    assert len(full) == len(trunc) == 12
    # The qualitative signature: with the shock switched off after q8, the
    # truncated response must be FALLING by q12 while the sustained one still
    # rises towards its plateau. Under the old drift dynamics both grew.
    t_11, t_12 = abs(trunc["delta_if_m"].iloc[10]), abs(trunc["delta_if_m"].iloc[11])
    f_11, f_12 = abs(full["delta_if_m"].iloc[10]), abs(full["delta_if_m"].iloc[11])
    assert t_12 < t_11, (
        f"truncated response still growing after the shock ended "
        f"({t_11:.0f} -> {t_12:.0f} £m): drift dynamics are back"
    )
    assert f_12 > f_11, "sustained response should still be approaching plateau"
    # And the magnitude must depend on the shock actually being in force:
    # dropping a third of the shocked quarters must show up in the tail
    # (measured ratio 0.79; drift dynamics measured 0.92).
    tail_ratio = t_12 / f_12
    assert tail_ratio < 0.85, (
        f"q12 response is {tail_ratio:.2f}x the sustained run's despite four "
        "unshocked quarters — the tail is drift, not the tax rate"
    )


def test_corp_tax_response_is_convex_but_not_divergent_over_shock_size():
    """Sanity on the shock-size dimension (as opposed to the horizon). The
    per-pp investment response is convex in the rate — TAF = (1-T*D)/(1-T)
    steepens as T rises — so a rise bites harder per pp than a cut helps.
    Measured at 12 quarters (2026-08, after the estimated allowance PVs and
    the log-anchoring fix): -69 £m/pp for a 5pp cut vs -76 £m/pp for a 5pp
    rise, widening to -97 £m/pp for a 25pp rise. (Pre-fix these were -541 /
    -575 / -859: the old rate-as-PV constants overstated (1-D) and the level
    add-factors compounded the deviation.) The asymmetry is the arithmetic
    of the user-cost formula and is expected; what must NOT happen is the
    response ceasing to scale monotonically or blowing past the shock's own
    scale."""
    from obr_macro.reform_analysis import run_reform

    per_pp = {}
    for pp in (-0.05, 0.05, 0.25):
        df = run_reform(
            f"{pp}",
            "TCPRO",
            pp,
            start="2025Q1",
            end="2027Q4",
            periods=12,
            investment_closure=True,
        )
        assert np.isfinite(df["delta_if_m"]).all(), f"{pp}: non-finite response"
        per_pp[pp] = df["delta_if_m"].iloc[-1] / (pp * 100)
    # every size gives the same sign of response per pp (a rise lowers, a cut
    # raises investment) ...
    assert all(v < 0 for v in per_pp.values()), f"sign flip across sizes: {per_pp}"
    # ... convex, so a bigger rise costs more per pp than a cut gains ...
    assert abs(per_pp[0.25]) > abs(per_pp[0.05]) > abs(per_pp[-0.05])
    # ... but bounded: no size may run away by an order of magnitude per pp.
    assert max(abs(v) for v in per_pp.values()) < 10 * min(
        abs(v) for v in per_pp.values()
    )


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


def _mape(model, efo, code, t0, t1):
    errs = []
    for t in range(t0, t1 + 1):
        m, e = model.iloc[t][code], efo.iloc[t][code]
        if np.isfinite(m) and np.isfinite(e) and abs(e) > 1e-9:
            errs.append(abs(m - e) / abs(e))
    assert errs, f"no finite {code} pairs to score"
    return 100 * float(np.mean(errs))


def test_anchored_reproduces_efo_published_aggregates(anchored):
    """Add-factors absorb the model's tracking error, so the anchored baseline
    must reproduce the OBR EFO path for the headline published aggregates to a
    tight tolerance.

    WHAT THIS DOES AND DOES NOT PROVE. It is a by-construction invariant, not a
    forecast test: the residuals are computed as (EFO - model prediction) and
    added back, so a small MAPE means the add-factor machinery works, not that
    the model forecasts anything. Two further caveats, both measurable:

    - Consumption is effectively the only source of GDP error here. Under the
      demand closure GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE; IF, X,
      M, VAL and SDE have no equation at all, DINV's is removed by the closure
      swap, and CGG's dlog equation is driven by exogenous EFO nominal
      spending and pinned by its own residual. So the GDP fit is the
      consumption fit scaled by the consumption share, and it is measurably
      exactly that: GDPM 0.1567%, CONS 0.2573%, ratio 0.6088 against a
      consumption share of GDP of 0.6092.
    - HHDI is not scored here at all. baseline.build(anchored=True) makes HHDI
      and RHHDI EXOGENOUS (_PUBLISHED_LEVEL_ANCHORS), so their "MAPE 0.00%" was
      the tautology "a series held at its EFO value equals its EFO value" — an
      assertion that could never fail. It is replaced below by the assertion
      that actually has content: that they are held, and why.
    """
    from obr_macro.data import load_obr_data

    efo = load_obr_data()
    t0 = anchored.period_idx("2025Q1")
    t1 = anchored.period_idx("2027Q4")

    mapes = {c: _mape(anchored.data, efo, c, t0, t1) for c in ("GDPM", "CONS")}
    for code, mape in mapes.items():
        assert mape < 1.0, f"anchored {code} MAPE {mape:.2f}% — not reproducing EFO"

    # The GDP fit is not independent evidence: it is the consumption fit
    # diluted by the exogenous expenditure components. Pin that so the headline
    # "GDP reproduces the EFO to 0.16%" cannot be read as a second success.
    for code in ("IF", "X", "M", "DINV", "VAL", "SDE"):
        assert code not in anchored.eq_for_var, (
            f"{code} became endogenous — the anchored GDP fit is no longer just "
            "the consumption fit and this test's reasoning needs revisiting"
        )
    cons_share = float(
        np.mean(
            [
                efo.iloc[t]["CONS"] / efo.iloc[t]["GDPM"]
                for t in range(t0, t1 + 1)
                if np.isfinite(efo.iloc[t]["GDPM"])
            ]
        )
    )
    assert mapes["GDPM"] / mapes["CONS"] == pytest.approx(cons_share, abs=0.05), (
        f"GDP MAPE / CONS MAPE = {mapes['GDPM'] / mapes['CONS']:.4f} vs a "
        f"consumption share of {cons_share:.4f}. They match because the GDP "
        "fit IS the consumption fit; if they stop matching, another "
        "expenditure component has become live and the headline needs "
        "re-explaining."
    )


def test_anchored_household_income_is_held_not_reproduced(anchored):
    """HHDI/RHHDI are pinned to the EFO by removing their equations, not by
    being solved to it. Assert the MECHANISM, since asserting the outcome is
    vacuous: `build(anchored=True)` strips the HHDI identity so the databank's
    published series survives the solve untouched.

    This matters for the honesty of the anchored headline. It is legitimate
    anchoring — the EFO publishes HHDI, so this is anchoring to ground truth —
    but it means the anchored baseline demonstrates nothing whatsoever about
    the model's household-income block, whose raw error is 6.27% MAPE.
    """
    from obr_macro.baseline import _PUBLISHED_LEVEL_ANCHORS
    from obr_macro.data import load_obr_data

    efo = load_obr_data()
    t0 = anchored.period_idx("2025Q1")
    t1 = anchored.period_idx("2027Q4")

    assert set(_PUBLISHED_LEVEL_ANCHORS) == {"HHDI", "RHHDI"}
    for code in _PUBLISHED_LEVEL_ANCHORS:
        assert code not in anchored.eq_for_var, (
            f"{code} has a live equation again — its anchored fit is no longer "
            "tautological and it can rejoin the by-construction test"
        )
        # Held exactly, not approximately: any deviation would mean something
        # is writing to it after all.
        assert _mape(anchored.data, efo, code, t0, t1) == pytest.approx(0.0, abs=1e-9)

    # The raw (un-anchored) model does NOT reproduce it — that is the number
    # the anchored fit hides. Kept as a lower bound so the two cannot be
    # confused: if this ever drops near zero the anchoring stopped mattering.
    from obr_macro.calibration_score import build_scorecard

    scored = {
        row["variable"]: row
        for block in build_scorecard()["blocks"]
        for row in block["rows"]
    }
    assert scored["HHDI"]["error"] > 1.0, (
        "raw HHDI error is now under 1% — the anchored 0.00% is no longer "
        "hiding anything and this test can be simplified"
    )


def test_anchored_unemployment_divergence_is_bounded(anchored):
    """EXPECTED DIVERGENCE, explicitly documented: unlike GDPM/CONS/HHDI, the
    anchored unemployment rate does NOT reproduce the EFO path — LFSUR drifts
    from the published values once its unpublished labour-market inputs run
    out (max abs gap 1.23pp on the March-2026 vintage; the EFO peaks near
    5.3%, the model overshoots then undershoots). This test does not bless
    the drift as correct; it pins its current size so it cannot silently
    worsen. If it starts failing, the labour block regressed; if the drift is
    ever fixed, promote LFSUR into
    test_anchored_reproduces_efo_published_aggregates and delete this."""
    from obr_macro.data import load_obr_data

    efo = load_obr_data()
    t0 = anchored.period_idx("2025Q1")
    t1 = anchored.period_idx("2027Q4")
    m = anchored.data["LFSUR"].iloc[t0 : t1 + 1].to_numpy(dtype=float)
    e = efo["LFSUR"].iloc[t0 : t1 + 1].to_numpy(dtype=float)
    ok = np.isfinite(m) & np.isfinite(e)
    assert ok.any(), "no finite LFSUR pairs to score"
    gap = np.abs(m[ok] - e[ok])
    assert gap.max() < 1.5, (
        f"anchored LFSUR drift grew to {gap.max():.2f}pp (was 1.23pp) — the "
        "documented divergence got worse"
    )
    # And the rate itself must stay economically sane on the horizon (the
    # failure mode on record is a decay toward zero, vs the EFO's ~4-5%).
    assert (m[ok] > 2.0).all() and (m[ok] < 8.0).all(), (
        "anchored unemployment rate left the plausible band"
    )


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


# --- External validation gates ----------------------------------------------
#
# The paper (papers/obr-macro) benchmarks the worked 1p basic-rate reform
# against HMRC's ready reckoner. Until now that comparison lived only in the
# paper's prose — nothing in CI failed if the pipeline drifted away from the
# official number. These tests gate it.
#
# Scope: the £6.46bn static costing is produced by the PolicyEngine
# microsimulation, which lives in another repository and is not runnable
# here. What THIS repo computes is the costing *path*: an externally costed
# annual yield arrives as a quarterly £m HHDI_ADDFACTOR shock, and
# run_reform must (a) inject exactly minus the costing as an HHDI add-factor
# and (b) deliver a household-income fall of the right sign and magnitude
# class. The microsim number itself is frozen here as a constant and gated
# against the HMRC reckoner; regenerating it is out of scope for this repo's
# CI.
#
# Be precise about what that deferral buys, because it was overstated. The
# recomputation lives in policyengine-macro's
# test_population_impact_uk_real_basic_rate, which is marked slow AND skipped
# without HUGGING_FACE_TOKEN, so it does not run in ordinary CI either -- and
# until 2026-08 it asserted only 4.0 < x < 9.0 GBP bn, a band admitting both
# HMRC figures, so it could not have distinguished our costing from the
# benchmark it is compared against. It now pins +/-5% of the published 6.46.
# The gate below therefore compares four constants to each other: it detects
# an inconsistent edit, not a modelling regression. That is worth having and
# it is not evidence.

# PolicyEngine static costing of basic rate 20p->21p from April 2026, first
# full year (2026-27), £bn — the paper's Table "reform" / fig_reform.py value.
PE_BASIC_RATE_1PP_YIELD_2026_27_BN = 6.46
# Same costing at the end of the paper's horizon (2030), £bn.
PE_BASIC_RATE_1PP_YIELD_2030_BN = 7.38
# HMRC "Direct effects of illustrative tax changes" (the ready reckoner),
# June 2025 edition: 1p change in the basic rate, 2026-27 and 2028-29, £bn.
HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN = 6.9
HMRC_RECKONER_BASIC_RATE_1PP_2028_29_BN = 8.2


def test_basic_rate_costing_is_within_15pct_of_hmrc_reckoner():
    """The frozen first-year basic-rate +1pp costing must sit within +/-15% of
    HMRC's ready-reckoner value. This fails if either side is updated
    inconsistently (a new microsim costing or a new reckoner vintage that
    breaks the paper's headline external-validation claim)."""
    rel = (
        abs(
            PE_BASIC_RATE_1PP_YIELD_2026_27_BN - HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN
        )
        / HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN
    )
    assert rel <= 0.15, (
        f"basic-rate +1pp costing £{PE_BASIC_RATE_1PP_YIELD_2026_27_BN}bn is "
        f"{100 * rel:.1f}% away from HMRC's £"
        f"{HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN}bn (limit 15%)"
    )


def test_basic_rate_costing_out_year_gap_is_wider_and_recorded():
    """The 15% gate above covers the year where the agreement is BEST. The
    out-year is worse and had no gate at all.

    HMRC's reckoner grows the 1p yield 18.8% from 2026-27 (£6.9bn) to 2028-29
    (£8.2bn). The frozen costing grows 14.2% from £6.46bn (2026) to £7.38bn
    (2030) — over a horizon two years LONGER, so per year it grows about a
    third as fast. Comparing like years (the paper interpolates £6.92bn for
    2028) the gap widens from 6.4% to 15.6%, i.e. past the band the first-year
    test enforces.

    That is a real limitation of the external validation, not a bug in this
    repo: only one point of a five-year path is genuinely benchmarked, and the
    2028 figure is an interpolation rather than a computed costing. Pinned here
    so the widening cannot be quietly lost, with a deliberately loose 20% bound
    — tightening it would mean fitting the costing to HMRC, which is exactly
    what must not happen.
    """
    first_year_gap = (
        abs(
            PE_BASIC_RATE_1PP_YIELD_2026_27_BN - HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN
        )
        / HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN
    )
    # The paper's own linear interpolation of the costing path to 2028.
    span = 2030 - 2026
    interpolated_2028 = PE_BASIC_RATE_1PP_YIELD_2026_27_BN + (
        PE_BASIC_RATE_1PP_YIELD_2030_BN - PE_BASIC_RATE_1PP_YIELD_2026_27_BN
    ) * ((2028 - 2026) / span)
    out_year_gap = (
        abs(interpolated_2028 - HMRC_RECKONER_BASIC_RATE_1PP_2028_29_BN)
        / HMRC_RECKONER_BASIC_RATE_1PP_2028_29_BN
    )
    assert out_year_gap > first_year_gap, (
        "the out-year gap is no longer the wider one — re-check which year the "
        "headline external-validation claim is quoting"
    )
    assert out_year_gap <= 0.20, (
        f"interpolated 2028 costing £{interpolated_2028:.2f}bn is "
        f"{100 * out_year_gap:.1f}% away from HMRC's £"
        f"{HMRC_RECKONER_BASIC_RATE_1PP_2028_29_BN}bn (limit 20%)"
    )
    # And the shape difference: HMRC's yield grows materially faster.
    pe_growth = PE_BASIC_RATE_1PP_YIELD_2030_BN / PE_BASIC_RATE_1PP_YIELD_2026_27_BN - 1
    hmrc_growth = (
        HMRC_RECKONER_BASIC_RATE_1PP_2028_29_BN
        / HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN
        - 1
    )
    assert pe_growth < hmrc_growth, (
        f"costing path grows {100 * pe_growth:.1f}% over four years against "
        f"HMRC's {100 * hmrc_growth:.1f}% over two — if this flips, the "
        "divergence direction changed and the paper's framing needs revisiting"
    )


def test_household_costing_injects_exact_hhdi_add_factors(solver):
    """This repo's half of the costing path is deterministic arithmetic: a
    quarterly £m costing must land as exactly minus that value on the HHDI
    add-factor for each shocked quarter (positive = revenue raised =
    disposable income falls)."""
    from obr_macro.reform_analysis import _apply_household_costing

    s = solver.clone()
    quarterly = PE_BASIC_RATE_1PP_YIELD_2026_27_BN * 1000 / 4  # £m/qtr
    _apply_household_costing(s, [quarterly] * 4, "2026Q2", 4)
    t0 = s.period_idx("2026Q2")
    for offset in range(4):
        assert s.add_factors[("HHDI", t0 + offset)] == pytest.approx(-quarterly)


def test_basic_rate_costing_path_moves_hhdi_by_the_static_yield():
    """Running the paper's first-year costing through run_reform must reduce
    household disposable income by the static yield, up to bounded
    second-round amplification. The reported delta_hhdi_m includes the
    model's endogenous income feedback (consumption falls -> incomes fall),
    so the fall exceeds the pure static injection — but it must have the
    right sign and stay in the same magnitude class. A dead HHDI channel
    (delta ~0) or a runaway (>1.6x static) both fail."""
    from obr_macro.reform_analysis import run_reform

    quarterly = PE_BASIC_RATE_1PP_YIELD_2026_27_BN * 1000 / 4  # £1,615m/qtr
    df = run_reform(
        "basic rate +1pp (2026-27 static costing)",
        "HHDI_ADDFACTOR",
        [quarterly] * 4,
        start="2025Q1",
        end="2025Q4",
    )
    dh = df.attrs["delta_hhdi_m"]
    assert len(dh) == 4
    static = quarterly
    for q, d in enumerate(dh):
        assert d < 0, f"quarter {q}: revenue raised must LOWER HHDI, got {d:+,.0f}"
        assert static * 0.9 <= -d <= static * 1.6, (
            f"quarter {q}: HHDI fall £{-d:,.0f}m vs static £{static:,.0f}m — "
            "outside the pass-through-plus-bounded-feedback band"
        )
    # Second-round GDP effect: negative (a tax rise is contractionary under
    # the demand closure) and small relative to the ~£6.5bn/yr costing.
    assert (df["delta_gdp_bn"] < 0).all()
    assert df["delta_gdp_bn"].abs().max() < 2.0


# --- Calibration scorecard regression gate -----------------------------------


def test_raw_calibration_scorecard_does_not_regress():
    """docs/calibration_scorecard.md promises the raw MAPEs are 'gated against
    regression'; this is that gate. The reference values below are the
    scorecard as of the March-2026 EFO vintage (August 2026 run of
    `obr_macro.calibration_score`). Each computed variable may not worsen by
    more than 20% relative (plus a small absolute slack for near-zero
    values). Improvements are always allowed — tighten the reference when
    they land.

    ETLFS is excluded: it scores ~0 as a trivial identity (see the
    scorecard's 'headline trap' note), so a relative bound is meaningless.
    """
    from obr_macro.calibration_score import build_scorecard

    reference = {
        # code: (kind, reference error)
        "GDPM": ("lvl", 4.49),  # % MAPE
        "CONS": ("lvl", 7.49),
        "IBUS": ("lvl", 15.73),
        "LFSUR": ("pp", 1.01),  # mean abs pp
        "RPI": ("pp", 1.71),
        "HHDI": ("lvl", 6.27),
        "RHHDI": ("lvl", 6.04),
        "FYCPR": ("lvl", 63.30),
        "CB": ("gdp", 3.61),  # % of GDP
        "TB": ("gdp", 0.69),
    }
    report = build_scorecard()
    scored = {
        row["variable"]: row for block in report["blocks"] for row in block["rows"]
    }
    failures = []
    for code, (kind, ref) in reference.items():
        row = scored.get(code)
        assert row is not None, f"{code} vanished from the scorecard panel"
        assert row["status"] == "computed", (
            f"{code} is no longer computed ({row['status']}) — a live channel "
            "went dead, which the scorecard would silently record as 0.00%"
        )
        assert row["metric"] == kind, f"{code} metric changed {kind}->{row['metric']}"
        err = row["error"]
        assert err is not None and np.isfinite(err), f"{code} scored no data"
        limit = ref * 1.20 + 0.05
        if err > limit:
            failures.append(f"{code}: {err:.2f} > limit {limit:.2f} (ref {ref})")
    assert not failures, "raw calibration regressed:\n  " + "\n  ".join(failures)


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
