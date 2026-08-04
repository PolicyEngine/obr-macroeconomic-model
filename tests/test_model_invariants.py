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
    # HHDI joins GDPM/CONS: the anchored solve reproduces the EFO household
    # income path exactly (MAPE 0.00% as of the March-2026 vintage), so it is
    # held to the same by-construction tolerance.
    for code in ("GDPM", "CONS", "HHDI"):
        errs = []
        for t in range(t0, t1 + 1):
            m = anchored.data.iloc[t][code]
            e = efo.iloc[t][code]
            if np.isfinite(m) and np.isfinite(e) and abs(e) > 1e-9:
                errs.append(abs(m - e) / abs(e))
        mape = 100 * np.mean(errs)
        assert mape < 1.0, f"anchored {code} MAPE {mape:.2f}% — not reproducing EFO"


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
# CI (it is validated in the policyengine-macro integration suite).

# PolicyEngine static costing of basic rate 20p->21p from April 2026, first
# full year (2026-27), £bn — the paper's Table "reform" / fig_reform.py value.
PE_BASIC_RATE_1PP_YIELD_2026_27_BN = 6.46
# HMRC "Direct effects of illustrative tax changes" (the ready reckoner),
# June 2025 edition: 1p change in the basic rate, 2026-27, £bn.
HMRC_RECKONER_BASIC_RATE_1PP_2026_27_BN = 6.9


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
