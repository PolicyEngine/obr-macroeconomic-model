"""Tax-scenario regression suite under the nominal-GDP pin (#52).

Each measure is sized with HMRC's ready reckoner ("Direct effects of
illustrative tax changes", June 2025, 2026-27 column, divided by four for a
quarterly £m path) and applied to the receipts line the October 2025 listing
uses for it:

- income tax basic rate +1p, £6.9bn/yr -> TYEM (TYWHH, l.612 -> HHDI, l.654)
- employee NICs main rate +1pp, £5.35bn/yr -> EENIC (EESC, l.651 -> HHDI)
- VAT standard rate +1pp, £8.8bn/yr -> VREC (CETAX l.410 -> BPAPS l.695)
- corporation tax +1pp, £3.6bn/yr -> NNSCTP (CT, l.408)
- fuel duty +5% (petrol + diesel), £1.2bn/yr -> TXFUEL (CETAX)

All are exogenous receipts in this closure. Only the two that reach household
disposable income move real GDP. VAT and fuel duty change basic-price
taxes, but CPI (l.314) is commented out by the OBR, so there is no price
route to real consumption. Corporation tax reaches nothing but receipts; its
live channel (TCPRO, investment closure) cannot be combined with the pin.
The tests pin both facts so a change to either shows up.

The ratio checked is -dGDPMPS / revenue (nominal GDP per £ of nominal
revenue). PGDP is exogenous, so this equals the real ratio. For reference,
the OBR's published tax multiplier is 0.33 in year 0, 0.30 in year 1 and 0.23
in year 2, tapering to 0 by year 5 ("Dynamic scoring of policy measures in
OBR forecasts", OBR fiscal multipliers table), and 0.3 for income tax and
NICs (EFO July 2015, Box 3.2). This model's ratio builds up instead of
tapering, because nothing closes the gap (no monetary rule, no labour-market
feedback). The bounds below are regression bands on the model, not a claim
that it matches the OBR.

Every test is slow (one template build plus eight 12-quarter solves).
Measured values are in the comments. Full 25-quarter sweep with +/-1x, 2x and
sustained shocks: scratchpad r5/obrtax (see PR body).
"""

import warnings

import numpy as np
import pytest

warnings.filterwarnings("ignore")

START, END = "2025Q1", "2027Q4"
PERIODS = 12

# HMRC ready reckoner, June 2025 edition, 2026-27, £m per year.
HMRC_BASIC_RATE_1P = 6900
HMRC_EMPLOYEE_NICS_MAIN_1PP = 5350
HMRC_VAT_STANDARD_1PP = 8800
HMRC_CORPORATION_TAX_1PP = 3600
HMRC_FUEL_DUTY_1PCT = 100 + 140  # petrol + diesel

LIVE = {
    "income_tax": ("TYEM", HMRC_BASIC_RATE_1P / 4),
    "employee_nics": ("EENIC", HMRC_EMPLOYEE_NICS_MAIN_1PP / 4),
}
DEAD = {
    "vat": ("VREC", HMRC_VAT_STANDARD_1PP / 4),
    "corporation_tax": ("NNSCTP", HMRC_CORPORATION_TAX_1PP / 4),
    "fuel_duty": ("TXFUEL", 5 * HMRC_FUEL_DUTY_1PCT / 4),
}
# Measured: exactly 0 for all three over 25 quarters. £1m allows for solver
# noise if a closure change ever reintroduces one.
DEAD_GDP_NOISE_M = 1.0
COLS = ("GDPM", "GDPMPS", "CONS", "CPI", "PCE", "LFSUR", "HHDI", "PSCR", "CGNB")


@pytest.fixture(scope="module")
def tax_runs():
    from obr_macro.reform_analysis import (
        HOUSEHOLD_COSTING_VAR,
        _apply_household_costing,
        _build_reform_template,
    )

    # nominal_gdp_pin passed explicitly so the suite means the same thing
    # whichever closure is the default.
    tpl = _build_reform_template("TYEM", START, END, False, True)
    base = tpl.clone()
    base.solve(START, END)
    t0, t1 = base.period_idx(START), base.period_idx(END)

    def run(var, shock):
        k = tpl.clone()
        if var == HOUSEHOLD_COSTING_VAR:
            _apply_household_costing(k, shock, START, PERIODS)
        else:
            assert var not in k.eq_for_var, f"{var} is no longer exogenous"
            k.apply_shock(var, shock, START, periods=PERIODS)
        k.solve(START, END)
        out = {
            c: (k.data[c].iloc[t0 : t1 + 1] - base.data[c].iloc[t0 : t1 + 1]).to_numpy(
                dtype=float
            )
            for c in COLS
        }
        out["status"] = dict(k.last_solve_report["exit_status"])
        return out

    it_var, it_size = LIVE["income_tax"]
    runs = {
        "base_status": dict(base.last_solve_report["exit_status"]),
        "income_tax+1": run(it_var, it_size),
        "income_tax-1": run(it_var, -it_size),
        "income_tax+2": run(it_var, 2 * it_size),
        "income_tax_hhdi": run(HOUSEHOLD_COSTING_VAR, it_size),
        "employee_nics+1": run(*LIVE["employee_nics"]),
    }
    for name, (var, size) in DEAD.items():
        runs[f"{name}+1"] = run(var, size)
    return runs


def _ratio(run, size, q):
    return -run["GDPMPS"][q] / size


@pytest.mark.slow
def test_every_tax_scenario_converges_to_tolerance(tax_runs):
    for name, run in tax_runs.items():
        status = run if name == "base_status" else run["status"]
        bad = {q: s for q, s in status.items() if s != "tol"}
        assert not bad, f"{name}: quarters not at tolerance {bad}"


@pytest.mark.slow
def test_income_tax_and_nics_rises_lower_gdp_and_consumption(tax_runs):
    for name in ("income_tax+1", "employee_nics+1"):
        r = tax_runs[name]
        assert (r["GDPM"] < 0).all(), f"{name}: GDP must fall every quarter"
        assert (r["CONS"] < 0).all(), f"{name}: consumption must fall every quarter"
        # Imports are exogenous, so the whole GDP fall is consumption.
        np.testing.assert_allclose(r["GDPM"], r["CONS"], atol=1e-6)


@pytest.mark.slow
def test_income_tax_response_is_symmetric_and_linear(tax_runs):
    up, down, two = (
        tax_runs[k]["GDPM"] for k in ("income_tax+1", "income_tax-1", "income_tax+2")
    )
    peak = np.abs(up).max()
    # Measured over 25 quarters: symmetry 0.23%, linearity 0.12%.
    assert np.abs(up + down).max() / peak < 0.01
    assert np.abs(two - 2 * up).max() / (2 * peak) < 0.01


@pytest.mark.slow
def test_income_tax_lever_matches_the_household_costing_channel(tax_runs):
    """TYEM and the HHDI add-factor are the same channel into HHDI."""
    a, b = tax_runs["income_tax+1"]["GDPM"], tax_runs["income_tax_hhdi"]["GDPM"]
    assert np.abs(a - b).max() / np.abs(a).max() < 0.02


@pytest.mark.slow
def test_employee_nics_ratio_equals_income_tax_ratio(tax_runs):
    """Both reach HHDI one for one, so the GDP per £ raised is the same."""
    it, ni = LIVE["income_tax"][1], LIVE["employee_nics"][1]
    for q in (3, 11):
        a = _ratio(tax_runs["income_tax+1"], it, q)
        b = _ratio(tax_runs["employee_nics+1"], ni, q)
        assert abs(a - b) / a < 0.01, (q, a, b)


@pytest.mark.slow
def test_income_tax_gdp_per_pound_raised_is_pinned(tax_runs):
    """-dGDPMPS / revenue. Measured (25q sweep): 0.209 at q4, 0.372 at q12.
    OBR tax multiplier: 0.33 year 0, 0.30 year 1, 0.23 year 2. The model
    rises where the OBR's tapers; see the module docstring."""
    size = LIVE["income_tax"][1]
    assert 0.17 < _ratio(tax_runs["income_tax+1"], size, 3) < 0.25
    assert 0.32 < _ratio(tax_runs["income_tax+1"], size, 11) < 0.43


@pytest.mark.slow
def test_no_tax_moves_cpi_or_unemployment(tax_runs):
    """CPI (l.314) is commented out and the labour-market chain is
    unpopulated, so every tax measure leaves CPI, PCE and LFSUR exactly at
    baseline. A failure here means a price or labour channel came alive:
    good news, but re-check every sign in this file."""
    for name, run in tax_runs.items():
        if name == "base_status":
            continue
        for c in ("CPI", "PCE", "LFSUR"):
            assert np.abs(run[c]).max() < 1e-9, f"{name}: {c} moved"


@pytest.mark.slow
def test_vat_corporation_tax_and_fuel_duty_have_no_gdp_channel(tax_runs):
    """The OBR scores VAT at 0.35 (Box 3.2). Here VAT, fuel duty and
    corporation tax raise revenue with no effect on real GDP or household
    income, because their only routes (CPI, the cost of capital) are switched
    off in this closure. Pinned as a documented gap, not a result.

    Expected to flip for VAT and fuel duty when #56 lands: a live BPAPS
    lowers OS (l.719), and OSHH feeds HHDI (l.654). Re-pin with the
    measured values then."""
    for name in DEAD:
        r = tax_runs[f"{name}+1"]
        assert np.abs(r["GDPM"]).max() < DEAD_GDP_NOISE_M, (
            name,
            np.abs(r["GDPM"]).max(),
        )
        assert np.abs(r["HHDI"]).max() < DEAD_GDP_NOISE_M, name


@pytest.mark.slow
def test_employee_nics_reach_receipts_and_borrowing_one_for_one(tax_runs):
    """EENIC enters PSCR directly (l.430): +£1 of NICs is +£1 of receipts and
    -£1 of central government net borrowing."""
    size = LIVE["employee_nics"][1]
    r = tax_runs["employee_nics+1"]
    np.testing.assert_allclose(r["PSCR"], size, atol=1e-6)
    np.testing.assert_allclose(r["CGNB"], -size, atol=1e-6)


@pytest.mark.slow
@pytest.mark.parametrize("name", ["income_tax", "vat", "corporation_tax", "fuel_duty"])
def test_tax_receipts_reach_receipts_and_borrowing(tax_runs, name):
    """+£1 of any receipts line is +£1 of PSCR and -£1 of CGNB (#56: before
    the fix PUBSTIW, PUBSTPD and CETAX were silently dropped, so these four
    were exactly 0)."""
    var, size = {**LIVE, **DEAD}[name]
    r = tax_runs[f"{name}+1"]
    np.testing.assert_allclose(r["PSCR"][:PERIODS], size, rtol=1e-6)
    np.testing.assert_allclose(r["CGNB"][:PERIODS], -size, rtol=1e-6)
