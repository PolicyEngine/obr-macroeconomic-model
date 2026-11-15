"""The optional nominal-GDP pin (#42): the OBR's commented-out l.690.

The published code writes one identity twice. l.337 makes the investment
deflator PIF the residual of nominal GDP, and l.688 builds nominal GDP from
its components, which include IFPS = IF*PIF/100 (l.114). Substituting one into
the other gives back the same equation, so nominal GDP and PIF are one
equation short and a solve leaves PIF wherever its starting value puts it.
``nominal_gdp_pin=True`` replaces l.688 with l.690, ``GDPMPS = PGDP*GDPM/100``.
See docs/nominal_gdp_pin.md.

The first tests are hermetic. The rest build and solve the full model.
"""

import warnings
from importlib import resources

import numpy as np
import pytest

warnings.filterwarnings("ignore")


def _listing():
    return (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
    )


def test_pin_is_the_obrs_own_commented_out_line():
    """The pinned equation is the OBR's l.690, verbatim, and it is commented out."""
    from obr_macro.reform_analysis import NOMINAL_GDP_PIN_EQ

    lines = _listing().splitlines()
    assert lines[689].strip() == "' GDPMPS  = PGDP  * GDPM  / 100"
    assert lines[687].strip() == "GDPMPS  = TFEPS  - MPS  + SDEPS"
    assert lines[336].startswith("PIF  = (GDPMPS  - CGGPS")
    # PGDP's own identity is the third member of the set, also switched off.
    assert lines[712].strip() == "'PGDP  = 100  * GDPMPS  / GDPM"
    assert "exogenised to enable indirect T2 fix" in lines[710]
    assert NOMINAL_GDP_PIN_EQ.lhs == "GDPMPS"
    assert NOMINAL_GDP_PIN_EQ.python_expr == "v['PGDP'] * v['GDPM'] / 100"


def test_pin_with_investment_closure_is_refused_before_any_build():
    """The investment closure holds PIF. With the pin as well, l.337 and l.688
    would both be gone and nothing would tie nominal GDP to its components."""
    from obr_macro.reform_analysis import _build_reform_template

    with pytest.raises(ValueError, match="investment_closure"):
        _build_reform_template("TCPRO", "2025Q1", "2027Q4", True, True)


def test_pin_default_resolves_by_closure():
    """#42: the pin is the default wherever it applies. None means on under
    the demand closure and off under the investment closure (which holds PIF
    and so already determines nominal GDP); an explicit False keeps the
    published closure available."""
    from obr_macro.reform_analysis import resolve_nominal_gdp_pin

    assert resolve_nominal_gdp_pin(None, False) is True
    assert resolve_nominal_gdp_pin(None, True) is False
    assert resolve_nominal_gdp_pin(False, False) is False
    assert resolve_nominal_gdp_pin(False, True) is False
    assert resolve_nominal_gdp_pin(True, False) is True
    with pytest.raises(ValueError, match="investment_closure"):
        resolve_nominal_gdp_pin(True, True)


def test_builders_default_to_the_pin_and_keep_the_published_closure():
    """baseline.build, raw_solve, build_scorecard and forecast default to the
    pin; nominal_gdp_pin=False still gives the published l.688 closure."""
    import inspect

    from obr_macro import baseline, calibration_score, forecast
    from obr_macro.reform_analysis import NOMINAL_GDP_PIN_EQ

    for fn in (
        baseline.build,
        calibration_score.raw_solve,
        calibration_score.build_scorecard,
        forecast.forecast,
    ):
        assert inspect.signature(fn).parameters["nominal_gdp_pin"].default is True

    def gdpmps_rhs(s):
        return s.eq_for_var["GDPMPS"].python_expr

    assert gdpmps_rhs(baseline.build()) == NOMINAL_GDP_PIN_EQ.python_expr
    published = gdpmps_rhs(baseline.build(nominal_gdp_pin=False))
    assert published != NOMINAL_GDP_PIN_EQ.python_expr
    assert "TFEPS" in published and "SDEPS" in published


def test_efo_satisfies_the_pin():
    """The OBR's own forecast obeys l.690: nominal GDP is the deflator times
    real GDP to rounding. Measured 6 Nov 2026: max 0.049% over 2021Q1-2031Q1,
    all of it in outturn quarters (2022Q2); every forecast quarter
    (2025Q4-2031Q1) is exactly 0. The outturn bound is 0.1%, about twice the
    measured gap, so an ONS revision to outturn cannot flip a data-only test;
    the forecast quarters, which are what the pin imposes, are held to 1e-6."""
    from obr_macro.data import load_obr_data

    e = load_obr_data().loc["2021Q1":"2031Q1"]
    gap = (e["PGDP"] * e["GDPM"] / 100 / e["GDPMPS"] - 1).abs()
    assert gap.max() < 1e-3, f"EFO breaks GDPMPS = PGDP*GDPM/100 by {gap.max():.2%}"
    assert gap.loc["2025Q4":].max() < 1e-6, gap.loc["2025Q4":].max()


# --- Full solves --------------------------------------------------------------


@pytest.fixture(scope="module")
def raw_pinned():
    from obr_macro.calibration_score import raw_solve

    s, _, _, t0, t1 = raw_solve(nominal_gdp_pin=True)
    return s.data.iloc[t0 : t1 + 1]


@pytest.mark.slow
def test_pinned_raw_solve_keeps_both_nominal_identities(raw_pinned):
    """Under the pin, l.690 holds by construction and l.688 still holds,
    because l.337 makes PIF the residual that closes it."""
    d = raw_pinned
    pin_gap = (d["GDPMPS"] - d["PGDP"] * d["GDPM"] / 100).abs().max()
    exp_gap = (d["GDPMPS"] - (d["TFEPS"] - d["MPS"] + d["SDEPS"])).abs().max()
    assert pin_gap < 1.0, f"l.690 broken by {pin_gap:.1f}m"
    assert exp_gap < 1.0, f"expenditure identity broken by {exp_gap:.1f}m"


@pytest.mark.slow
def test_pinned_raw_solve_stops_pif_drifting(raw_pinned):
    """Without the pin, the de-seeded raw solve sends PIF 106.7 -> -4.6 -> 317
    (6 Nov 2026). With it, PIF stays within 10% of the EFO path every quarter
    (measured: 106.8 to 114.3 against an EFO of 102.7 to 107.4)."""
    from obr_macro.data import load_obr_data

    efo = load_obr_data()["PIF"].reindex(raw_pinned.index)
    dev = (raw_pinned["PIF"] / efo - 1).abs()
    assert np.isfinite(raw_pinned["PIF"]).all()
    assert dev.max() < 0.10, (
        f"PIF drifts under the pin: {raw_pinned['PIF'].round(1).tolist()}"
    )


@pytest.mark.slow
def test_pinned_profits_error_is_pinned():
    """Company profits under the pin: 17.90% raw MAPE (11 Nov 2026, receipts
    identities live, #56; 18.04% before), against 41.71% under the published
    closure (82.78% before). Same 20% + 0.05 slack as the scorecard gate in
    test_model_invariants.py."""
    from obr_macro.calibration_score import build_scorecard

    rows = {
        r["variable"]: r
        for b in build_scorecard(nominal_gdp_pin=True)["blocks"]
        for r in b["rows"]
    }
    row = rows["FYCPR"]
    assert row["status"] == "computed"
    assert row["error"] <= 17.90 * 1.20 + 0.05, row


@pytest.fixture(scope="module")
def household_pinned():
    """Household costing lever over 25 quarters, pinned closure."""
    from obr_macro.reform_analysis import (
        HOUSEHOLD_COSTING_VAR,
        _apply_household_costing,
        _build_reform_template,
    )

    start, end = "2025Q1", "2031Q1"
    tpl = _build_reform_template(HOUSEHOLD_COSTING_VAR, start, end, False, True)
    base = tpl.clone()
    base.solve(start, end)
    t0, t1 = base.period_idx(start), base.period_idx(end)
    out = {"base_pif": base.data["PIF"].iloc[t0 : t1 + 1].copy()}
    for label, shock in (("up", 1615.75), ("down", -1615.75), ("up4", 4 * 1615.75)):
        k = tpl.clone()
        _apply_household_costing(k, shock, start, 12)
        k.solve(start, end)
        out[label] = (
            k.data["GDPM"].iloc[t0 : t1 + 1] - base.data["GDPM"].iloc[t0 : t1 + 1]
        ).to_numpy(dtype=float)
    return out


@pytest.mark.slow
def test_pinned_reform_baseline_pif_stays_near_the_efo_over_25_quarters(
    household_pinned,
):
    """The pin determines PIF, but over the 25-quarter reform baseline it
    sits above the EFO path: +0.4% in 2025Q1, up to +6.0% within the first
    12 quarters (2027Q4) and +7.8% by 2031Q1 (6 Nov 2026; PIF 121.7 against
    an EFO of 112.9). Deltas are unaffected (base and shocked share it), but
    PIF levels feed PIBUS, sectoral nominal investment, VALPS and GGIDEF.
    Bounds: 10% over the full horizon, 7.5% in the first 12 quarters (the
    default scoring window), about 1.25-1.3x the measured gaps."""
    from obr_macro.data import load_obr_data

    pif = household_pinned["base_pif"]
    efo = load_obr_data()["PIF"].reindex(pif.index)
    dev = (pif / efo - 1).to_numpy(dtype=float)
    assert np.isfinite(dev).all()
    assert np.abs(dev).max() < 0.10, (100 * dev).round(1).tolist()
    assert np.abs(dev[:12]).max() < 0.075, (100 * dev[:12]).round(1).tolist()


@pytest.mark.slow
def test_pinned_household_response_is_symmetric_over_25_quarters(household_pinned):
    """Rise + cut, per quarter over 25 quarters: 0.2% of the peak under the pin
    (125% under the published closure, 6 Nov 2026). Bound 2%."""
    up, down = household_pinned["up"], household_pinned["down"]
    assert np.abs(up + down).max() <= 0.02 * np.abs(up).max()


@pytest.mark.slow
def test_pinned_household_response_is_linear_over_25_quarters(household_pinned):
    """4x vs 4 x 1x, per quarter over 25 quarters: 0.3% of the peak under the
    pin (51% under the published closure). Bound 3%."""
    up, up4 = household_pinned["up"], household_pinned["up4"]
    assert np.abs(up4 - 4 * up).max() <= 0.03 * np.abs(4 * up).max()


@pytest.mark.slow
def test_pinned_household_response_fades_after_the_shock(household_pinned):
    """A 12-quarter rise: GDP falls in the window, then returns towards
    baseline without changing sign. By q24 it is under a quarter of its peak
    (measured -93m against a -533m peak; the published closure gives -853m)."""
    up = household_pinned["up"]
    peak = np.abs(up[:12]).max()
    assert (up < 0).all(), up.round(0).tolist()
    assert abs(up[24]) < 0.25 * peak, up.round(0).tolist()
    assert all(abs(b) <= abs(a) + 0.02 * peak for a, b in zip(up[12:], up[13:]))


@pytest.mark.slow
def test_pinned_bank_rate_response_is_proportional_to_its_size():
    """#50: under the pin, peak GDP per 100bp is the same for +25bp, +100bp
    and +200bp, held for 4 quarters (measured 6 Nov 2026 over 2025Q1-2031Q1:
    -0.0580%, -0.0574%, -0.0566%; within 2.5%). Under the published closure
    the same runs give -0.138%, -0.061% and -0.076%, because of a late
    PIF jump. Bound 10%, the #50 criterion. Every quarter converges to tol."""
    from obr_macro.reform_analysis import _build_reform_template

    start, end = "2025Q1", "2031Q1"
    tpl = _build_reform_template("R", start, end, False, True)
    base = tpl.clone()
    base.solve(start, end)
    t0, t1 = base.period_idx(start), base.period_idx(end)
    b = base.data["GDPM"].iloc[t0 : t1 + 1].to_numpy(dtype=float)
    per100 = {}
    for size in (0.25, 1.0, 2.0):
        k = tpl.clone()
        k.apply_shock("R", size, start, periods=4)
        k.solve(start, end)
        d = k.data["GDPM"].iloc[t0 : t1 + 1].to_numpy(dtype=float) - b
        per100[size] = np.abs(d / b * 100 / size).max()
        status = set(k.last_solve_report["exit_status"].values())
        assert status == {"tol"}, f"{size}pp: not every quarter converged: {status}"
    lo, hi = min(per100.values()), max(per100.values())
    assert hi <= 1.10 * lo, f"peak GDP per 100bp not proportional: {per100}"
