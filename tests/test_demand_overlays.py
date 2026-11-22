"""Opt-in demand overlays: import leakage and the employment response.

In the OBR's October 2025 listing total imports M have no equation and
non-oil goods imports are the residual MNOG = M - MS - MOIL (l.217); total
employment is ETLFS = 1000*HWA/AVH (l.153) with both terms inputs.
``run_reform(..., import_response=True)`` and
``run_reform(..., employment_response=True)`` add labelled overlays on the
shocked run. The defaults are unchanged.

The first tests are hermetic. The rest build and solve the full model.
"""

import re
import warnings
from importlib import resources

import numpy as np
import pytest

from obr_macro import demand_overlays as overlays

warnings.filterwarnings("ignore")


def _listing_lines():
    text = (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
    )
    return text.splitlines()


def _live(lines, lhs):
    """Uncommented listing lines whose left-hand side is ``lhs``."""
    pattern = re.compile(rf"^\s*{re.escape(lhs)}\s*=")
    return [ln for ln in lines if pattern.match(ln)]


def _numbers(expr):
    return [float(x) for x in re.findall(r"\d+\.\d+", expr)]


# --- Hermetic ----------------------------------------------------------------


@pytest.mark.parametrize("flag", ["import_response", "employment_response"])
def test_overlays_are_refused_where_they_were_not_built(flag):
    """Fail before the (expensive) template build."""
    from obr_macro.reform_analysis import run_reform

    with pytest.raises(ValueError, match="demand closure only"):
        run_reform("x", "TCPRO", 0.01, investment_closure=True, **{flag: True})
    with pytest.raises(ValueError, match="published_conventions"):
        run_reform("x", "CGG", 1000.0, published_conventions=True, **{flag: True})
    with pytest.raises(ValueError, match="default nominal-GDP pin only"):
        run_reform("x", "CGG", 1000.0, nominal_gdp_pin=False, **{flag: True})
    with pytest.raises(ValueError, match="price_passthrough"):
        run_reform("x", "VREC", 1000.0, price_passthrough=True, **{flag: True})
    with pytest.raises(ValueError, match="monetary_conditioning"):
        run_reform("x", "R", 1.0, monetary_conditioning=True, **{flag: True})
    own = "M" if flag == "import_response" else "HWA"
    with pytest.raises(ValueError, match="its own equation"):
        run_reform("x", own, 1000.0, **{flag: True})


def test_listing_holds_total_imports_fixed_and_goods_as_the_residual():
    """The fact the import overlay answers: M has no equation and MNOG is
    what is left after services and oil (l.217)."""
    lines = _listing_lines()
    assert _live(lines, "M") == []
    (mnog,) = _live(lines, "MNOG")
    assert mnog.split() == "MNOG = M - MS - MOIL".split()
    assert len(_live(lines, "dlog(MS)")) == 1


def test_services_coefficients_are_the_listings_own_l223():
    (eq,) = _live(_listing_lines(), "dlog(MS)")
    c = overlays.SERVICES_IMPORT_COEFFICIENTS
    rhs = eq.split("=", 1)[1].replace(" ", "")
    for k, coef in enumerate(c["dlog_mstfe"]):
        lag = "" if k == 0 else f"(-{k})"
        sign = "-" if coef < 0 else "+" if k else ""
        assert f"{sign}{abs(coef)}*dlog(MSTFE{lag})" in rhs
    assert f"-{abs(c['dlog_ms_lag1'])}*dlog(MS(-1))" in rhs
    assert (
        f"-{abs(c['error_correction'])}*(log(MS(-1))"
        f"-{c['long_run_mstfe']}*log(MSTFE(-1))" in rhs
    )


def test_goods_and_services_weights_sum_to_the_listings_import_content():
    """MGTFE (l.211) and MSTFE (l.219) split the total import-content weights
    of l.195-l.201, which is what makes MGTFE the goods import content."""
    lines = _listing_lines()
    (mgtfe,) = _live(lines, "MGTFE")
    (mstfe,) = _live(lines, "MSTFE")
    goods = dict(zip(("CONS", "CGG", "IF", "DINV"), _numbers(mgtfe)))
    services = dict(zip(("CONS", "CGG", "IF", "DINV"), _numbers(mstfe)))
    total = {
        "CONS": _numbers(_live(lines, "MC")[0])[0],
        "CGG": _numbers(_live(lines, "MCGG")[0])[0],
        "IF": _numbers(_live(lines, "MIF")[0])[0],
        "DINV": _numbers(_live(lines, "MDINV")[0])[0],
    }
    for name, weight in total.items():
        assert goods[name] + services[name] == pytest.approx(weight, abs=1e-9)
    assert goods["CGG"] == 0.064


def test_goods_elasticity_is_declared_as_an_assumption():
    assert overlays.IMPORT_RESPONSE_GOODS_ELASTICITY == 1.0
    assert "this repo's assumption" in overlays.IMPORT_RESPONSE_NOTE
    assert "this repo's assumption" in overlays.EMPLOYMENT_RESPONSE_NOTE


def test_listing_sets_employment_from_hours_and_has_one_labour_demand_equation():
    lines = _listing_lines()
    (etlfs,) = _live(lines, "ETLFS")
    assert etlfs.replace(" ", "") == "ETLFS=1000*(HWA/AVH)"
    assert _live(lines, "HWA") == [] and _live(lines, "AVH") == []
    (ems,) = _live(lines, "dlog(EMS)")
    assert "0.1713792  * dlog(MSGVA(-1))" in ems
    assert "0.0062207  * (log(EMS(-1)  / MSGVA(-1))" in ems


def test_services_deviation_equation_is_zero_at_baseline():
    """With every variable on its baseline path the deviation form returns
    the baseline level exactly, so the overlay adds nothing without a shock."""
    eq = overlays._parse(overlays._SERVICES_SRC)
    path = {
        "MS": [80.0, 82.0, 81.0, 83.0, 84.0],
        "MSTFE": [60.0, 61.0, 61.5, 62.0, 63.0],
    }
    v = {"MS_BASE": 85.0, "MSTFE": 63.5, "MSTFE_BASE": 63.5}

    def lag(name, n):
        return path[name.replace("_BASE", "")][-n]

    value = eval(eq.python_expr, {"np": np, "v": v, "_lag": lag})
    assert value == pytest.approx(85.0, rel=1e-12)


def test_services_deviation_equation_moves_by_the_impact_coefficient():
    """The equation the solver actually runs (not the Python re-statement in
    services_imports_partial_response): a 1% rise in import-weighted demand
    this quarter, from baseline, raises services imports by 0.819114%."""
    eq = overlays._parse(overlays._SERVICES_SRC)
    path = {
        "MS": [80.0, 82.0, 81.0, 83.0, 84.0],
        "MSTFE": [60.0, 61.0, 61.5, 62.0, 63.0],
    }
    v = {"MS_BASE": 85.0, "MSTFE": 63.5 * 1.01, "MSTFE_BASE": 63.5}

    def lag(name, n):
        return path[name.replace("_BASE", "")][-n]

    value = eval(eq.python_expr, {"np": np, "v": v, "_lag": lag})
    assert np.log(value / 85.0) / np.log(1.01) == pytest.approx(0.819114, rel=1e-9)


def test_goods_equation_scales_all_goods_and_nets_off_oil():
    """Oil is counted once: goods imports including oil move in proportion
    to MGTFE, and non-oil goods are that total less the oil imports the
    listing computes. So MNOG + MOIL does not depend on the oil response."""
    eq = overlays._parse(
        overlays._GOODS_SRC.format(elasticity=overlays.IMPORT_RESPONSE_GOODS_ELASTICITY)
    )
    base = {"MNOG_BASE": 140.0, "MOIL_BASE": 18.0, "MGTFE_BASE": 150.0}

    def mnog(mgtfe, moil):
        v = dict(base, MGTFE=mgtfe, MOIL=moil)
        return eval(eq.python_expr, {"np": np, "v": v, "_lag": None})

    assert mnog(150.0, 18.0) == pytest.approx(140.0, rel=1e-12)
    for moil in (18.0, 19.0, 25.0):
        assert mnog(153.0, moil) + moil == pytest.approx(158.0 * 1.02, rel=1e-12)
    assert "MOIL" in overlays.IMPORT_RESPONSE_BASE_VARS


# --- Full solve ---------------------------------------------------------------

START, END = "2025Q1", "2027Q4"


def _one_percent_of_gdp():
    from obr_macro.reform_analysis import _build_reform_template

    tpl = _build_reform_template("CGG", START, END, False, None)
    t0, t1 = tpl.period_idx(START), tpl.period_idx(END)
    return [0.01 * float(x) for x in tpl.data["GDPM"].iloc[t0 : t1 + 1]]


@pytest.fixture(scope="module")
def shock():
    return _one_percent_of_gdp()


@pytest.fixture(scope="module")
def default_run(shock):
    from obr_macro.reform_analysis import run_reform

    return run_reform("default", "CGG", shock)


@pytest.fixture(scope="module")
def import_run(shock):
    from obr_macro.reform_analysis import run_reform

    return run_reform("imports", "CGG", shock, import_response=True)


@pytest.mark.slow
def test_default_is_labelled_off_and_keeps_the_passthrough(default_run, shock):
    assert default_run.attrs["import_response"] is False
    assert default_run.attrs["mechanical_passthrough"] is True
    assert default_run.attrs["employment_response"] is False
    assert "import_response_detail" not in default_run.attrs
    mult = default_run["delta_gdp_m"].to_numpy() / np.array(shock)
    assert mult[0] == pytest.approx(1.0128, abs=2e-4)
    assert mult[11] == pytest.approx(1.0394, abs=2e-4)


@pytest.mark.slow
def test_import_response_measured_profile(import_run, shock):
    """+1% of GDP on government consumption: imports rise by about 9% to 12%
    of the shock and the GDP delta per pound falls from 1.01 to about 0.91.
    Re-measured 22 Nov 2026 after the goods leg was changed to count oil
    once (before: 0.9164 / 0.8877 / 0.9009, MNOG +428.3, M +966.4 at q12)."""
    assert import_run.attrs["solver_converged"]
    mult = import_run["delta_gdp_m"].to_numpy() / np.array(shock)
    assert mult[0] == pytest.approx(0.9086, abs=5e-4)
    assert mult[3] == pytest.approx(0.9066, abs=5e-4)
    assert mult[11] == pytest.approx(0.9176, abs=5e-4)
    d = import_run.attrs["import_response_detail"]["delta_m"]
    assert d["MNOG"][0] == pytest.approx(482.5, abs=0.5)
    assert d["MS"][0] == pytest.approx(240.9, abs=0.5)
    assert d["MOIL"][0] == pytest.approx(0.0, abs=1e-6)
    assert d["M"][11] == pytest.approx(849.5, abs=0.5)
    # Every import series rises or is unchanged; goods no longer fall.
    assert min(d["MNOG"]) > 0 and min(d["MS"]) > 0
    # l.217 inverted holds on the deltas.
    total = np.array(d["MNOG"]) + np.array(d["MS"]) + np.array(d["MOIL"])
    assert np.allclose(total, d["M"], atol=1e-6)
    assert "import_response=True is on" in import_run.attrs["multiplier_warning"]
    assert import_run.attrs["mechanical_passthrough"] is False


@pytest.mark.slow
def test_goods_imports_are_proportional_to_import_weighted_demand(import_run, shock):
    """Goods imports including oil are unit-elastic to MGTFE in every
    quarter, whatever the listing's oil equation does. On impact, before
    consumption or oil has moved much, that is close to the l.211 weight on
    government consumption times baseline goods-import intensity with oil
    (0.064 x about 1.04)."""
    from obr_macro.reform_analysis import _build_reform_template

    d = import_run.attrs["import_response_detail"]["delta_m"]
    assert d["MNOG"][0] / shock[0] == pytest.approx(0.064 * 1.04, abs=0.004)
    tpl = _build_reform_template("CGG", START, END, False, None)
    base = tpl.clone()
    base.solve(START, END)
    w = slice(base.period_idx(START), base.period_idx(END) + 1)
    b = {n: base.data[n].astype(float).to_numpy()[w] for n in ("MNOG", "MOIL")}
    goods = np.array(d["MNOG"]) + np.array(d["MOIL"])
    # With unit elasticity the goods response is at least the direct
    # government-consumption term of MGTFE at baseline intensity, and it
    # stays within 15% above it (measured 3% to 10%: consumption adds little).
    mgtfe = base.data["MGTFE"].astype(float).to_numpy()[w]
    direct = (b["MNOG"] + b["MOIL"]) * 0.064 * np.array(shock) / mgtfe
    assert np.all(goods >= direct - 1e-6)
    assert np.all(goods <= 1.15 * direct)


@pytest.mark.slow
def test_overlays_add_nothing_without_a_shock():
    from obr_macro.reform_analysis import run_reform

    r = run_reform(
        "zero", "CGG", [0.0] * 12, import_response=True, employment_response=True
    )
    assert np.max(np.abs(r["delta_gdp_m"])) < 1e-2
    for path in r.attrs["import_response_detail"]["delta_m"].values():
        assert np.max(np.abs(path)) < 1e-2
    assert (
        np.max(np.abs(r.attrs["employment_response_detail"]["delta_lfsur_pp"])) < 1e-6
    )


HOUSEHOLD_TAX = 1616.0  # 1p on the basic rate, GBP m a quarter (README)


@pytest.fixture(scope="module")
def household_pair():
    from obr_macro.reform_analysis import run_reform

    off = run_reform("off", "HHDI_ADDFACTOR", HOUSEHOLD_TAX, periods=12)
    on = run_reform(
        "on", "HHDI_ADDFACTOR", HOUSEHOLD_TAX, periods=12, employment_response=True
    )
    return off, on


@pytest.mark.slow
def test_employment_response_to_a_household_tax_rise(household_pair):
    """A sustained 1p basic-rate rise: market sector employment falls with
    lagged market sector GVA (l.145), total employment follows one for one,
    unemployment rises and consumption falls further."""
    off, on = household_pair
    assert on.attrs["solver_converged"]
    d = on.attrs["employment_response_detail"]
    assert d["delta_etlfs_thousands"][0] == pytest.approx(0.0, abs=1e-6)
    assert d["delta_etlfs_thousands"][3] == pytest.approx(-4.19, abs=0.05)
    assert d["delta_etlfs_thousands"][11] == pytest.approx(-14.52, abs=0.05)
    assert np.allclose(d["delta_etlfs_thousands"], d["delta_ems_thousands"], atol=1e-6)
    assert np.allclose(
        d["delta_ulfs_thousands"], -np.array(d["delta_etlfs_thousands"]), atol=1e-6
    )
    assert d["delta_lfsur_pp"][11] == pytest.approx(0.040, abs=0.002)
    assert off["delta_gdp_m"].iloc[11] == pytest.approx(-529.4, abs=0.5)
    assert on["delta_gdp_m"].iloc[11] == pytest.approx(-609.2, abs=0.5)
    assert "employment_response_warning" not in on.attrs


@pytest.mark.slow
def test_employment_response_to_government_consumption_is_near_zero(shock):
    """Government GVA takes nearly all of a CGG shock, so market sector GVA
    and employment barely move. The run carries a warning saying so."""
    from obr_macro.reform_analysis import run_reform

    r = run_reform("jobs", "CGG", shock, employment_response=True)
    d = r.attrs["employment_response_detail"]
    assert np.max(np.abs(d["delta_etlfs_thousands"])) < 10.0
    assert d["delta_etlfs_thousands"][1] == pytest.approx(-1.90, abs=0.05)
    assert d["delta_etlfs_thousands"][11] == pytest.approx(6.95, abs=0.05)
    assert "Do not read this" in r.attrs["employment_response_warning"]


def test_services_response_converges_to_the_listings_long_run_elasticity():
    """A permanent 1% rise in import-weighted demand raises services imports
    by 0.82% on impact and settles at the l.223 long-run elasticity."""
    n = 80
    path = overlays.services_imports_partial_response(
        [100.0] * n, [50.0] * n, [50.5] * n
    )
    dlog = np.log1p(np.array(path) / 100.0) / np.log(1.01)
    assert dlog[0] == pytest.approx(0.819114, rel=1e-9)
    assert dlog[-1] == pytest.approx(1.079017, abs=1e-4)


def test_a_dropped_overlay_equation_raises():
    """MS and EMS are allowed to drop in an ordinary solve; under an overlay
    that would be a silent zero response."""
    report = {"dropped": ["BV", "MS"]}
    overlays.require_overlay_equations_live(report, False, False)
    overlays.require_overlay_equations_live(report, False, True)
    with pytest.raises(RuntimeError, match="MS"):
        overlays.require_overlay_equations_live(report, True, False)
    overlays.require_overlay_equations_live(None, True, True)
