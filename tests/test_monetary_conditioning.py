"""Bank Rate channels (#50): the opt-in monetary-conditioning overlay, the
retail-rate income audit and the cost-of-capital seed.

In the OBR's October 2025 listing Bank Rate R reaches only consumption (l.4)
and the interest flows in household and corporate income. Retail rates, gilts,
sterling and house prices are conditioning inputs with no equation.
``run_reform(..., monetary_conditioning=True)`` moves those inputs with R where
a pass-through can be sourced. The default is unchanged.

The first tests are hermetic. The rest build and solve the full model.
"""

import re
import warnings
from importlib import resources

import numpy as np
import pandas as pd
import pytest

warnings.filterwarnings("ignore")


def _listing():
    return (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
    )


def _variables():
    path = resources.files("obr_macro").joinpath(
        "_data/obr_model_variables_october_2025.xlsx"
    )
    df = pd.read_excel(path, header=None)
    out = {}
    for row in df.values.tolist():
        row = [str(c).strip() for c in row]
        if len(row) > 2:
            out[row[2]] = row
    return out


# --- Hermetic ----------------------------------------------------------------


def test_conditioning_is_refused_for_anything_but_bank_rate():
    """The overlay is a Bank Rate pass-through; on any other instrument it
    would be meaningless. It must fail before the (expensive) template build."""
    from obr_macro.reform_analysis import run_reform

    with pytest.raises(ValueError, match="var='R'"):
        run_reform("x", "CGG", 1000.0, monetary_conditioning=True)


def test_every_conditioned_channel_is_sourced_and_the_rest_are_off():
    """Only sourced coefficients are moved. RDEP, RL, RX and APH have no
    sourced point estimate, so they are listed as off, with the reason."""
    from obr_macro.reform_analysis import (
        MONETARY_CONDITIONING,
        MONETARY_CONDITIONING_OFF,
    )

    assert set(MONETARY_CONDITIONING) == {"RMORT"}
    assert set(MONETARY_CONDITIONING_OFF) == {"RDEP", "RL", "RX", "APH"}
    assert not set(MONETARY_CONDITIONING) & set(MONETARY_CONDITIONING_OFF)
    for coef, source in MONETARY_CONDITIONING.values():
        assert 0 < coef <= 1
        assert "l." in source or "Bank of England" in source
    for reason in MONETARY_CONDITIONING_OFF.values():
        assert reason


def test_mortgage_passthrough_is_the_obrs_own_l623():
    """The 0.9 on RMORT is the OBR's effective household loan rate in l.623,
    (0.9*R + 0.2), verbatim in the committed listing."""
    from obr_macro.reform_analysis import MONETARY_CONDITIONING

    lines = _listing().splitlines()
    assert lines[622].strip() == (
        "DIPHH  = (LHP(-1)  + OLPE(-1))  * ((1  + (0.9  * R  + 0.2)  / 100)^0.25  - 1)"
    )
    coef = float(re.search(r"\(([\d.]+)  \* R  \+ 0\.2\)", lines[622]).group(1))
    assert MONETARY_CONDITIONING["RMORT"][0] == coef


def test_conditioned_inputs_have_no_equation_in_the_listing():
    """Every input the overlay moves, and every input it leaves off, is a
    conditioning assumption: no equation defines it in the OBR's file."""
    from obr_macro.reform_analysis import (
        MONETARY_CONDITIONING,
        MONETARY_CONDITIONING_OFF,
    )

    lhs = set()
    for line in _listing().splitlines():
        s = line.strip()
        if not s or s.startswith("'") or "=" not in s:
            continue
        m = re.match(r"(?:d\(|dlog\()?([A-Za-z][A-Za-z0-9_]*)\)?\s*=", s)
        if m:
            lhs.add(m.group(1))
    for v in list(MONETARY_CONDITIONING) + list(MONETARY_CONDITIONING_OFF):
        assert v not in lhs, f"{v} has an equation; it is not a conditioning input"


def test_household_interest_receipts_have_no_equation():
    """Retail-rate audit, part 1: DIRHH (household interest receipts) is
    exogenous in the OBR's file, so no rate reaches it. Interest PAID (DIPHH,
    DIPHHmf) moves with R and RMORT, interest RECEIVED does not: the
    household-income response to rates is gross of deposit income by
    construction. Faithful to the OBR, and the reason it reads large."""
    v = _variables()
    assert v["DIRHH"][4] == "No Equation" and v["DIRHH"][5] == "Exogenous"
    lines = _listing().splitlines()
    assert lines[644].strip() == "PIRHH  = NDIVHH  + APIIH  + DIRHH  + WYQC"
    assert lines[646].strip() == "PIPHH  = DIPHH"


def test_cost_of_capital_inputs_are_unpublished():
    """The COCU seed is forced: l.68 needs DELTA and RWACC, and RWACC (l.64)
    needs DEBTW and NDIV. The OBR's variables workbook gives all three as
    exogenous with no equation and no series code (DEBTW, DELTA) or a ratio
    of unvendored codes (NDIV), so R -> RIC -> CDEBT cannot reach COC."""
    v = _variables()
    for name in ("DELTA", "DEBTW", "NDIV"):
        assert v[name][4] == "No Equation" and v[name][5] == "Exogenous", name
    assert v["DELTA"][3] == "No Codes" and v["DEBTW"][3] == "No Codes"
    from obr_macro.full_solver import UNPUBLISHED_COST_OF_CAPITAL_SEEDS

    assert UNPUBLISHED_COST_OF_CAPITAL_SEEDS["COCU"] == 0.12


# --- Full solves --------------------------------------------------------------

START, END = "2025Q1", "2028Q4"


def _solve(conditioned: bool, size: float = 1.0):
    from obr_macro.reform_analysis import MONETARY_CONDITIONING, _build_reform_template

    tpl = _build_reform_template("R", START, END, False, True)
    base = tpl.clone()
    base.solve(START, END)
    k = tpl.clone()
    path = [size] * 4
    k.apply_shock("R", path, START)
    if conditioned:
        for var, (coef, _) in MONETARY_CONDITIONING.items():
            k.apply_shock(var, [coef * x for x in path], START)
    k.solve(START, END)
    assert set(k.last_solve_report["exit_status"].values()) == {"tol"}
    t0, t1 = base.period_idx(START), base.period_idx(END)
    return base, k, t0, t1


@pytest.fixture(scope="module")
def default_run():
    return _solve(False)


@pytest.fixture(scope="module")
def conditioned_run():
    return _solve(True)


def _pct(run, var):
    b, k, t0, t1 = run
    bb = b.data[var].iloc[t0 : t1 + 1].to_numpy(float)
    kk = k.data[var].iloc[t0 : t1 + 1].to_numpy(float)
    return (kk / bb - 1) * 100


def _delta(run, var):
    b, k, t0, t1 = run
    return k.data[var].iloc[t0 : t1 + 1].to_numpy(float) - b.data[var].iloc[
        t0 : t1 + 1
    ].to_numpy(float)


@pytest.fixture(scope="module")
def conditioned_cut():
    return _solve(True, -1.0)


@pytest.mark.slow
def test_default_bank_rate_response_is_unchanged(default_run):
    """Default (no conditioning): +100bp x 4q peak GDP -0.0574% at q4, as
    measured in round 3 (#50 comment 6675785744) and again in round 4."""
    g = _pct(default_run, "GDPM")
    assert int(np.argmin(g)) == 3
    assert g.min() == pytest.approx(-0.0574, abs=0.001)


@pytest.mark.slow
def test_conditioning_deepens_the_response(default_run, conditioned_run):
    """Moving RMORT with R at the OBR's 0.9 raises mortgage interest paid, so
    GDP falls further: measured 6 Nov 2026, peak -0.1475% at q4 (default
    -0.0574%), q8 -0.0496%, q12 -0.0299%."""
    g0, g1 = _pct(default_run, "GDPM"), _pct(conditioned_run, "GDPM")
    assert int(np.argmin(g1)) == 3
    assert g1.min() == pytest.approx(-0.1475, abs=0.002)
    assert g1[7] == pytest.approx(-0.0496, abs=0.002)
    assert g1.min() < 2 * g0.min()


@pytest.mark.slow
def test_conditioned_response_is_symmetric(conditioned_run, conditioned_cut):
    """+100bp and -100bp give mirror-image GDP paths (measured: peak -0.1475%
    and +0.1475%). Bound 2% of the peak, quarter by quarter."""
    up, down = _pct(conditioned_run, "GDPM"), _pct(conditioned_cut, "GDPM")
    peak = np.abs(up).max()
    assert np.abs(up + down).max() <= 0.02 * peak


@pytest.mark.slow
@pytest.mark.parametrize("run", ["default_run", "conditioned_run"])
def test_cpi_and_unemployment_do_not_respond_by_design(run, request):
    """CPI (l.314) and PGDP (l.713) are commented out in the OBR's file and
    LFSUR (l.165) has no rate or demand term, so neither mode moves them."""
    r = request.getfixturevalue(run)
    assert np.all(_delta(r, "CPI") == 0)
    assert np.all(_delta(r, "PCE") == 0)
    assert np.all(_delta(r, "LFSUR") == 0)


def _quarterly(rate_pct):
    return (1 + rate_pct / 100) ** 0.25 - 1


@pytest.mark.slow
@pytest.mark.parametrize("run", ["default_run", "conditioned_run"])
def test_retail_rate_income_effect_is_the_published_cash_flow(run, request):
    """Retail-rate audit, part 2: the impact-quarter HHDI response is exactly
    the OBR's interest-flow arithmetic, with nothing extra.

    - DIPHH (l.623) rises by (LHP+OLPE)(-1) * the change in the quarterly
      rate on 0.9R+0.2 (about GBP 4.98bn per 100bp).
    - DIPHHmf (l.619), the mortgage spread, moves by LHP(-1) * the change in
      the quarterly rate on RMORT-R; it enters HHDI through OSHH (l.725) with
      a minus sign. Holding RMORT fixed (default) makes it offset 83% of the
      DIPHH rise; at the OBR's own 0.9 it offsets 8%.
    - WYQC (l.641) follows company profits and is the only other mover.
    - DIRHH, interest received, does not move.
    So dHHDI = -dDIPHH - dDIPHHmf + dWYQC, to the pound."""
    b, k, t0, _ = request.getfixturevalue(run)
    t = t0
    debt = b.data["LHP"].iloc[t - 1] + b.data["OLPE"].iloc[t - 1]
    r0, r1 = b.data["R"].iloc[t], k.data["R"].iloc[t]
    want_diphh = debt * (_quarterly(0.9 * r1 + 0.2) - _quarterly(0.9 * r0 + 0.2))
    assert _delta(request.getfixturevalue(run), "DIPHH")[0] == pytest.approx(
        want_diphh, rel=1e-6
    )
    lhp = b.data["LHP"].iloc[t - 1]
    s0 = b.data["RMORT"].iloc[t] - r0
    s1 = k.data["RMORT"].iloc[t] - r1
    want_mf = lhp * (_quarterly(s1) - _quarterly(s0))
    r = request.getfixturevalue(run)
    assert _delta(r, "DIPHHmf")[0] == pytest.approx(want_mf, rel=1e-6)
    assert np.all(_delta(r, "DIRHH") == 0)
    d_hhdi = _delta(r, "HHDI")[0]
    cash = -_delta(r, "DIPHH")[0] - _delta(r, "DIPHHmf")[0] + _delta(r, "WYQC")[0]
    assert d_hhdi == pytest.approx(cash, abs=1.0)
    assert d_hhdi < 0


@pytest.mark.slow
def test_cost_of_capital_does_not_move_with_bank_rate():
    """The COCU seed, under the investment closure (the only closure where the
    cost-of-capital chain is evaluated): R moves RIC, but COCU and COC
    (= TAF*COCU) do not, so KSTAR and IBUSX never see Bank Rate."""
    from obr_macro.reform_analysis import _build_reform_template

    tpl = _build_reform_template("R", START, END, True, False)
    base = tpl.clone()
    base.solve(START, END)
    k = tpl.clone()
    k.apply_shock("R", [1.0] * 4, START)
    k.solve(START, END)
    run = (base, k, base.period_idx(START), base.period_idx(END))
    d_ric = _delta(run, "RIC")
    assert np.isfinite(d_ric).all() and np.abs(d_ric).max() > 0.5
    for var in ("COCU", "COC"):
        d = _delta(run, var)
        assert np.isfinite(d).all() and np.all(d == 0), var


@pytest.mark.slow
def test_corporate_lending_rate_is_not_evaluated_under_the_default_closure(
    default_run,
):
    """Under the default (demand) closure RIC is NaN in the solve window, so
    the corporate-interest leg of the Bank Rate channel does not run there
    either. Pinned so a change is noticed (round 4 finding, #50)."""
    b, _, t0, t1 = default_run
    assert b.data["RIC"].iloc[t0 : t1 + 1].isna().all()


# --- run_reform wiring (hermetic, with a solver double) -----------------------


def _rate_double(monkeypatch):
    """A run_reform template double carrying R and RMORT; solve() is a no-op,
    so whatever the shocks wrote stays in each clone's frame."""
    import copy

    from obr_macro import reform_analysis
    from obr_macro.full_solver import FullOBRSolver

    index = pd.period_range("2025Q1", periods=8, freq="Q")
    proto = FullOBRSolver.__new__(FullOBRSolver)
    proto.verbose = False
    proto.equations = []
    proto._build_equation_index()
    proto.data = pd.DataFrame(
        {
            "R": [4.0] * 8,
            "RMORT": [4.5] * 8,
            "GDPM": [1000.0] * 8,
            "CONS": [600.0] * 8,
            "IF": [100.0] * 8,
        },
        index=index,
    )
    proto.index = index
    clones = []

    class _Template:
        def clone(self):
            c = copy.copy(proto)
            c.data = proto.data.copy()

            def _solve(start, end, _c=c):
                _c.data["GDPM"] = 1000.0 - 10.0 * (_c.data["RMORT"] - 4.5)

            c.solve = _solve
            clones.append(c)
            return c

    monkeypatch.setattr(
        reform_analysis, "_build_reform_template", lambda *a, **k: _Template()
    )
    return reform_analysis, clones


def test_run_reform_conditioning_moves_rmort_at_the_sourced_passthrough(monkeypatch):
    """The flag itself: run_reform shifts RMORT by 0.9 x the R path in the
    shocked run only, and labels the frame with what moved, what did not,
    and why CPI and unemployment cannot respond."""
    ra, clones = _rate_double(monkeypatch)
    df = ra.run_reform(
        "r", "R", [1.0, 1.0, 0.5], "2025Q1", "2025Q4", monetary_conditioning=True
    )
    base, shocked = clones
    d_rmort = (shocked.data["RMORT"] - base.data["RMORT"]).iloc[:4].tolist()
    assert d_rmort == pytest.approx([0.9, 0.9, 0.45, 0.0])
    assert (shocked.data["R"] - base.data["R"]).iloc[:4].tolist() == pytest.approx(
        [1.0, 1.0, 0.5, 0.0]
    )
    assert df.attrs["monetary_conditioning"] is True
    assert df.attrs["monetary_conditioning_on"]["RMORT"]["passthrough"] == 0.9
    assert "l.623" in df.attrs["monetary_conditioning_on"]["RMORT"]["source"]
    assert set(df.attrs["monetary_conditioning_off"]) == {"RDEP", "RL", "RX", "APH"}
    assert "by design" in df.attrs["inflation_unemployment_note"]
    assert "COCU" in df.attrs["cost_of_capital_channel"]
    assert df["delta_gdp_m"].tolist() == pytest.approx([-9.0, -9.0, -4.5, 0.0])


def test_run_reform_default_leaves_rmort_alone(monkeypatch):
    """Without the flag (the default) RMORT is untouched and the frame says so."""
    ra, clones = _rate_double(monkeypatch)
    df = ra.run_reform("r", "R", 1.0, "2025Q1", "2025Q4", periods=4)
    base, shocked = clones
    assert (shocked.data["RMORT"] == base.data["RMORT"]).all()
    assert df.attrs["monetary_conditioning"] is False
    assert "monetary_conditioning_on" not in df.attrs
    assert "by design" in df.attrs["inflation_unemployment_note"]
