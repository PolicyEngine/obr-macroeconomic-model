"""Opt-in indirect-tax price pass-through (#60) and the government-investment
route under the investment closure.

``run_reform(..., price_passthrough=True)`` passes a VAT or fuel-duty rise into
CPI through the listing's own cost-push weights with the retail markup held at
baseline. The shipped listing holds CPI exogenous (l.314 is commented out and
the markup is the residual, l.284), so the default is unchanged.

The first tests are hermetic. The rest build and solve the full model.
"""

import re
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


def _rhs(name):
    for line in _listing().splitlines():
        m = re.match(rf"^{name}\s+=\s+(.*)", line)
        if m:
            return m.group(1)
    raise AssertionError(f"{name} has no live level equation")


def _weight(rhs, term):
    m = re.search(r"([\d.]+)\s*\*\s*\(\(?" + term, rhs)
    return float(m.group(1)) / 100 if m else 0.0


# --- Hermetic ----------------------------------------------------------------


def test_passthrough_is_refused_outside_indirect_taxes():
    """It is a cost-push overlay for indirect taxes only, and it must fail
    before the expensive template build."""
    from obr_macro.reform_analysis import run_reform

    with pytest.raises(ValueError, match="indirect-tax"):
        run_reform("x", "TYEM", 1000.0, price_passthrough=True)
    with pytest.raises(ValueError, match="demand closure"):
        run_reform("x", "VREC", 1000.0, price_passthrough=True, investment_closure=True)


def test_tax_weight_is_derived_from_the_listing():
    """The 13.84 weight is RPCOST's own 11.56 plus what SCOST, CCOST and
    UTCOST pass through (they are markup-free identities that also carry
    BPAPS/GVA), solved with PPIY held. Recomputed from the listing here so an
    edit to the constant cannot drift from its source."""
    from obr_macro.reform_analysis import (
        PRICE_PASSTHROUGH_ELASTICITY,
        PRICE_PASSTHROUGH_TAX_WEIGHT,
        PRICE_PASSTHROUGH_W1,
    )

    tax = r"\(BPAPS"
    names = ["SCOST", "CCOST", "UTCOST"]
    a = np.array([[_weight(_rhs(n), k) for k in names] for n in names])
    b = np.array([_weight(_rhs(n), tax) for n in names])
    cost = np.linalg.solve(np.eye(3) - a, b)
    rp = _rhs("RPCOST")
    total = _weight(rp, tax) + sum(_weight(rp, k) * c for k, c in zip(names, cost))
    assert total == pytest.approx(PRICE_PASSTHROUGH_TAX_WEIGHT, abs=5e-5)
    # RPCOST is an index: its weights sum to 100.
    assert sum(float(x) for x in re.findall(r"([\d.]+)\s*\*", rp)) == pytest.approx(
        100.0, abs=0.05
    )
    # W1 is the listing's commented constant, and l.314 is commented out.
    assert re.search(r"^'W1\s+=\s+0\.084", _listing(), re.M)
    assert re.search(r"^'CPI\s+=\s+CPI\(-1\)", _listing(), re.M)
    assert PRICE_PASSTHROUGH_ELASTICITY == pytest.approx(
        (1 - PRICE_PASSTHROUGH_W1) * PRICE_PASSTHROUGH_TAX_WEIGHT
    )


def test_cpi_has_no_live_equation_in_the_shipped_listing():
    """The overlay exists because the shipped listing makes CPI exogenous and
    the markup the residual. If the OBR ever ships a live CPI equation, this
    overlay must be revisited rather than stacked on top of it."""
    from obr_macro.full_solver import FullOBRSolver

    s = FullOBRSolver(verbose=False)
    assert "CPI" not in s.eq_for_var


# --- Full solves --------------------------------------------------------------

S, E, VAT = "2025Q1", "2027Q4", 8800 / 4


@pytest.fixture(scope="module")
def vat_pair():
    """Baseline, VAT-only shocked run, and the same run with pass-through."""
    from obr_macro import reform_analysis as ra

    tpl = ra._build_reform_template("VREC", S, E, False)
    base = tpl.clone()
    base.solve(S, E)
    t0, t1 = base.period_idx(S), base.period_idx(E)
    k = tpl.clone()
    k.apply_shock("VREC", VAT, S, periods=12)
    k.solve(S, E)
    off = k.data.copy()
    on, report, detail = ra._apply_price_passthrough(k, base.data.copy(), S, E, t0, t1)
    return base.data.copy(), off, on, report, detail, (t0, t1)


def _delta(d, base, col, w):
    return (d[col] - base[col]).iloc[w[0] : w[1] + 1].to_numpy(dtype=float)


@pytest.mark.slow
def test_passthrough_raises_cpi_and_keeps_receipts(vat_pair):
    """CPI rises by the listing's cost-push share of the tax (about 0.37% to
    0.41%, measured 16 Nov 2026 on the October 2026 EFO), the fixed point is
    reached, receipts still move one for one with the revenue, and every
    quarter converges."""
    base, off, on, report, detail, w = vat_pair
    cpi = 100 * (on["CPI"] / base["CPI"] - 1).iloc[w[0] : w[1] + 1].to_numpy()
    assert (_delta(off, base, "CPI", w) == 0).all(), "default path moved CPI"
    assert 0.33 < cpi.min() and cpi.max() < 0.45, cpi
    assert detail["residual_vs_final_take"] < 1e-5
    np.testing.assert_allclose(_delta(on, base, "PSCR", w), VAT, atol=1e-6)
    es = (report or {}).get("exit_status", {})
    assert es and all(v == "tol" for v in es.values()), es


@pytest.mark.slow
def test_passthrough_vat_ratio_measured_profile(vat_pair):
    """Current-price GDP per pound of VAT, measured 16 Nov 2026: 0.175 / 0.345
    / 0.551 / 0.643 at q1 / q4 / q8 / q12 (year-1 mean 0.263) with the overlay,
    0.013 / 0.026 / 0.037 / 0.043 without. The OBR's convention is 0.35,
    fading; the overlay matches it near q4 and keeps building after, because
    nothing in the published equations makes consumption fade. Pinned at the
    measured values with a 10% band, not at 0.35."""
    base, off, on, _, _, w = vat_pair
    on_r = -_delta(on, base, "GDPMPS", w) / VAT
    off_r = -_delta(off, base, "GDPMPS", w) / VAT
    for q, ref in ((0, 0.175), (3, 0.345), (7, 0.551), (11, 0.643)):
        assert on_r[q] == pytest.approx(ref, rel=0.10), (q, on_r[q])
    for q, ref in ((3, 0.026), (11, 0.043)):
        assert off_r[q] == pytest.approx(ref, rel=0.10), (q, off_r[q])
    assert (on_r > off_r).all()


@pytest.mark.slow
def test_government_investment_reaches_gdp_under_the_investment_closure():
    """With the listing's commented-out IF identity live (investment closure),
    real government investment enters IF and GDP one for one: measured 16 Nov
    2026, CGIPS +3,000 gives GDP +3,075 / +2,901 / +2,932 at q1 / q4 / q12.
    Labelled as identity passthrough, not a validated multiplier."""
    from obr_macro.reform_analysis import run_reform

    df = run_reform("cgips", "CGIPS", 3000.0, periods=12, investment_closure=True)
    assert df.attrs["solver_converged"] is True
    assert df.attrs["mechanical_passthrough"] is True
    assert df.attrs["dead_channel"] is False
    assert "identity passthrough" in df.attrs["transmission_note"]
    g = df["delta_gdp_m"].to_numpy()
    np.testing.assert_allclose(g, df["delta_if_m"].to_numpy(), atol=10.0)
    assert ((g / 3000.0 > 0.93) & (g / 3000.0 < 1.06)).all(), g
