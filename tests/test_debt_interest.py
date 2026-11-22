"""Opt-in debt-interest overlay (``run_reform(..., debt_interest=True)``).

The listing holds central government debt interest ``DICGOP`` exogenous. The
overlay finances the extra borrowing a reform causes with gilts at the gilt
yield, and reprices the gilts the EFO plans to issue if the yield is shocked.
The default is unchanged.

The first tests are hermetic. The rest build and solve the full model.
"""

import warnings
from importlib import resources

import numpy as np
import pytest

from obr_macro.debt_interest import (
    CONVENTIONAL_GILT_ISSUANCE_BN,
    DEBT_INTEREST_LEGS,
    debt_interest_path,
    fiscal_year,
    quarterly_gilt_issuance_m,
)

warnings.filterwarnings("ignore")


def _table(vintage, workbook, sheet):
    import openpyxl

    path = resources.files("obr_macro").joinpath(
        f"_data/obr_efo_{vintage}_{workbook}.xlsx"
    )
    with resources.as_file(path) as p:
        wb = openpyxl.load_workbook(p, read_only=True, data_only=True)
        return [
            [v for v in row if v is not None]
            for row in wb[sheet].iter_rows(values_only=True)
        ]


def _row(rows, label, nth=0):
    hits = [r for r in rows if r and str(r[0]).strip() == label]
    return [float(x) for x in hits[nth][1:]]


def _years(rows):
    return next(r for r in rows if r and str(r[0]).startswith("20") and "-" in r[0])


# --- Hermetic ----------------------------------------------------------------


def test_overlay_is_refused_where_it_was_not_measured():
    """It must fail before the expensive template build."""
    from obr_macro.reform_analysis import run_reform

    with pytest.raises(ValueError, match="debt_interest"):
        run_reform("x", "CGG", 1000.0, debt_interest=True, investment_closure=True)
    with pytest.raises(ValueError, match="debt_interest"):
        run_reform("x", "CGG", 1000.0, debt_interest=True, published_conventions=True)
    with pytest.raises(ValueError, match="price_passthrough"):
        run_reform("x", "VREC", 1000.0, debt_interest=True, price_passthrough=True)
    with pytest.raises(ValueError, match="nominal-GDP pin"):
        run_reform("x", "CGG", 1000.0, debt_interest=True, nominal_gdp_pin=False)
    for flag in ("import_response", "employment_response"):
        with pytest.raises(ValueError, match=flag):
            run_reform("x", "CGG", 1000.0, debt_interest=True, **{flag: True})


def test_fiscal_year_mapping():
    assert fiscal_year("2026Q1") == "2025-26"
    assert fiscal_year("2026Q2") == "2026-27"
    assert fiscal_year("2027Q1") == "2026-27"
    assert fiscal_year("1999Q4") == "1999-00"


def test_issuance_constants_match_the_committed_efo_tables():
    """Conventional gilt issuance is the 'Conventional gilts' line of table
    6.12: October 2026 EFO from 2026-27, November 2025 EFO for 2025-26."""
    rows = _table("october_2026", "aggregates", "6.12")
    published = dict(zip(_years(rows), _row(rows, "Conventional gilts")))
    assert set(published) == set(CONVENTIONAL_GILT_ISSUANCE_BN) - {"2025-26"}
    for fy, value in published.items():
        assert CONVENTIONAL_GILT_ISSUANCE_BN[fy] == pytest.approx(value, abs=0.005)
    rows = _table("november_2025", "aggregates", "6.12")
    published = dict(zip(_years(rows), _row(rows, "Conventional gilts")))
    assert CONVENTIONAL_GILT_ISSUANCE_BN["2025-26"] == pytest.approx(
        published["2025-26"], abs=0.005
    )


def test_issuance_outside_the_published_years_raises():
    assert quarterly_gilt_issuance_m(["2026Q2"])[0] == pytest.approx(224780 / 4)
    with pytest.raises(ValueError, match="2032-33"):
        quarterly_gilt_issuance_m(["2032Q2"])


def test_stock_effect_compounds_at_the_gilt_yield():
    """GBP 1,000m a quarter at 4%: the first cohort pays half a quarter
    (about 5), then 10 a quarter more for each earlier cohort, plus interest
    on the interest."""
    p = debt_interest_path([1000.0] * 4, [4.0] * 4)
    stock = p["stock_effect_m"]
    assert p["rate_effect_m"] == [0.0] * 4
    assert stock[0] == pytest.approx(0.5 * 0.01 * 1000 / (1 - 0.005))
    assert stock[1] == pytest.approx(
        (0.01 * (1000 + stock[0]) + 0.005 * 1000) / (1 - 0.005)
    )
    # Debt is cumulative borrowing plus the interest on it.
    assert p["cumulative_extra_debt_m"][-1] == pytest.approx(4000 + sum(stock))
    # No interest on interest would give 5, 15, 25, 35.
    assert np.all(np.asarray(stock) > np.array([5.0, 15.0, 25.0, 35.0]))
    assert stock[-1] < 36.0


def test_zero_borrowing_and_no_yield_change_gives_zero():
    p = debt_interest_path([0.0] * 6, [5.0] * 6, [0.0] * 6)
    assert p["delta_debt_interest_m"] == [0.0] * 6


def test_tax_rise_lowers_debt_interest_symmetrically():
    up = debt_interest_path([800.0] * 8, [5.5] * 8)["delta_debt_interest_m"]
    down = debt_interest_path([-800.0] * 8, [5.5] * 8)["delta_debt_interest_m"]
    np.testing.assert_allclose(up, -np.asarray(down))


def test_rate_effect_reprices_planned_issuance_only():
    """+1pp on GBP 60bn a quarter of planned issuance: 150m a quarter of
    coupon per cohort, half in the quarter of issue. The existing stock keeps
    its coupons, so the effect starts small and builds."""
    p = debt_interest_path([0.0] * 4, [5.0] * 4, [1.0] * 4, [60000.0] * 4)
    assert p["rate_effect_m"] == pytest.approx([75.0, 225.0, 375.0, 525.0])
    # The extra interest is borrowed too, so a small stock effect follows.
    assert 0 < p["stock_effect_m"][0] < 1.0
    with pytest.raises(ValueError, match="issuance"):
        debt_interest_path([0.0] * 4, [5.0] * 4, [1.0] * 4)


def test_cohort_rule_against_efo_new_stock_interest():
    """Evidence for the pricing rule. EFO table 6.16 splits interest on
    conventional gilts into existing and new stock. Applying the overlay's
    cohort rule to the EFO's own planned issuance (6.12) at the EFO's 20-year
    yield (1.9) gives 6.13 / 20.13 / 35.70 / 49.84 / 63.78 / 80.14 GBP bn for
    2026-27 to 2031-32 against the EFO's 5.55 / 19.12 / 33.99 / 46.66 / 58.08 /
    70.85: 5% to 13% high every year. The 20-year yield overstates the
    average yield at issue, and the rule ignores new gilts that redeem
    inside the window. Pinned as measured (21 Nov 2026), not tuned."""
    rows = _table("october_2026", "aggregates", "6.16")
    new_stock = dict(zip(_years(rows)[1:], _row(rows, "New stock")[1:]))
    econ = _table("october_2026", "economy", "1.9")
    rl = {
        str(r[0]): float(r[2])
        for r in econ
        if len(r) > 2 and str(r[0])[:2] == "20" and "Q" in str(r[0])
    }
    quarters = [f"{y}Q{q}" for y in range(2026, 2033) for q in (1, 2, 3, 4)][1:25]
    assert quarters[0] == "2026Q2" and quarters[-1] == "2032Q1"
    coupons = (
        quarterly_gilt_issuance_m(quarters)
        * np.array([rl[q] for q in quarters])
        / 400.0
    )
    interest = np.cumsum(coupons) - 0.5 * coupons
    by_year = {}
    for q, x in zip(quarters, interest):
        by_year[fiscal_year(q)] = by_year.get(fiscal_year(q), 0.0) + x / 1000.0
    ratios = {fy: by_year[fy] / new_stock[fy] for fy in new_stock}
    assert len(ratios) == 6
    assert all(1.04 < r < 1.14 for r in ratios.values()), ratios
    assert by_year["2027-28"] == pytest.approx(20.13, abs=0.05)


def test_legs_keep_the_subsidy_residual_out_of_it():
    """PSCE is imposed and subsidies are its residual (l.504), so DICGOP must
    move with PSCE or subsidies would fall one for one."""
    assert DEBT_INTEREST_LEGS == ("DICGOP", "PSCE")
    listing = (
        resources.files("obr_macro")
        .joinpath("_data/obr_model_code_october_2025.txt")
        .read_text()
        .splitlines()
    )
    cgsubp = next(line for line in listing if line.startswith("CGSUBP  ="))
    cgnb = next(line for line in listing if line.startswith("CGNB  ="))
    assert "PSCE" in cgsubp and "DICGOP" in cgsubp
    assert "+ DICGOP" in cgnb
    live = [line for line in listing if "DICGOP" in line and not line.startswith("'")]
    assert len(live) == 2, "DICGOP now feeds another live equation"


class _FakeSolver:
    """Solved stand-in: CGNB is its baseline plus whatever DICGOP gained."""

    def __init__(self, data, base):
        self.data, self._base = data, base

    def solve(self, start, end):
        self.data["CGNB"] = self._cgnb0 + self.data["DICGOP"] - self._base["DICGOP"]

    def prime(self):
        self._cgnb0 = self.data["CGNB"].copy()
        return self


def _frames(d_cgnb, rl=5.0, n=4):
    import pandas as pd

    idx = pd.period_range("2026Q2", periods=n, freq="Q")
    base = pd.DataFrame(
        {"DICGOP": 100.0, "PSCE": 900.0, "CGNB": 50.0, "RL": rl}, index=idx
    )
    shocked = base.copy()
    shocked["CGNB"] += d_cgnb
    return base, shocked


def test_apply_moves_both_legs_by_the_same_amount():
    from obr_macro.debt_interest import apply_debt_interest

    base, shocked = _frames(1000.0)
    solver = _FakeSolver(shocked, base).prime()
    data, _, detail = apply_debt_interest(solver, base, None, None, 0, 3)
    extra = np.asarray(detail["delta_debt_interest_m"])
    assert extra[0] > 0 and np.all(np.diff(extra) > 0)
    np.testing.assert_allclose(data["DICGOP"] - base["DICGOP"], extra, atol=1e-3)
    np.testing.assert_allclose(data["PSCE"] - base["PSCE"], extra, atol=1e-3)
    assert detail["residual_m"] < 1e-9
    assert "no_effect_note" not in detail


def test_apply_says_so_when_nothing_moved():
    from obr_macro.debt_interest import apply_debt_interest

    base, shocked = _frames(0.0)
    solver = _FakeSolver(shocked, base).prime()
    _, _, detail = apply_debt_interest(solver, base, None, None, 0, 3)
    assert detail["delta_debt_interest_m"] == [0.0] * 4
    assert "added nothing" in detail["no_effect_note"]


# --- Full model --------------------------------------------------------------

S, E = "2025Q1", "2027Q4"
COLS = ("GDPM", "CONS", "CGNB", "PSNBNSA", "PSCB", "TME", "CGSUBP", "BPAPS", "FYCPR")


@pytest.fixture(scope="module")
def cgg_pair():
    from obr_macro.reform_analysis import run_reform

    off = run_reform("cgg", "CGG", 1250.0, periods=12)
    on = run_reform("cgg", "CGG", 1250.0, periods=12, debt_interest=True)
    return off, on


@pytest.mark.slow
def test_borrowing_shock_adds_interest_and_leaves_gdp(cgg_pair):
    """Government consumption +1,250 a quarter. Measured 21 Nov 2026 on the
    October 2026 EFO: extra debt interest 8 / 61 / 140 / 230 at q1 / q4 / q8 /
    q12, borrowing higher by exactly that, GDP unchanged, every quarter
    converged."""
    off, on = cgg_pair
    assert off.attrs["debt_interest"] is False
    assert "debt_interest_detail" not in off.attrs
    d = on.attrs["debt_interest_detail"]
    extra = np.asarray(d["delta_debt_interest_m"])
    assert on.attrs["solver_converged"] is True
    assert d["residual_m"] < 1e-3
    assert np.all(np.asarray(d["rate_effect_m"]) == 0.0)
    assert np.all(np.diff(extra) > 0)
    for q, ref in ((0, 8.3), (3, 60.7), (7, 139.7), (11, 229.8)):
        assert extra[q] == pytest.approx(ref, rel=0.05), (q, extra[q])
    np.testing.assert_allclose(
        np.asarray(d["delta_borrowing_after_m"])
        - np.asarray(d["delta_borrowing_before_m"]),
        extra,
        atol=1e-3,
    )
    np.testing.assert_allclose(on["delta_gdp_m"], off["delta_gdp_m"], atol=1e-3)
    np.testing.assert_allclose(on["delta_cons_m"], off["delta_cons_m"], atol=1e-3)


@pytest.mark.slow
def test_interest_reaches_every_borrowing_aggregate_and_not_subsidies():
    from obr_macro import reform_analysis as ra
    from obr_macro.debt_interest import apply_debt_interest

    tpl = ra._build_reform_template("CGG", S, E, False)
    base = tpl.clone()
    base.solve(S, E)
    t0, t1 = base.period_idx(S), base.period_idx(E)
    k = tpl.clone()
    ra.apply_spending_shock(k, "CGG", 1250.0, S, 12, nominal_consistent=True)
    k.solve(S, E)
    off = k.data.copy()
    on, report, detail = apply_debt_interest(k, base.data.copy(), S, E, t0, t1)
    extra = np.asarray(detail["delta_debt_interest_m"])

    def moved(col):
        return (on[col] - off[col]).iloc[t0 : t1 + 1].to_numpy(dtype=float)

    for col in ("DICGOP", "PSCE", "CGNB", "PSNBNSA", "TME"):
        np.testing.assert_allclose(moved(col), extra, atol=1e-3, err_msg=col)
    np.testing.assert_allclose(moved("PSCB"), -extra, atol=1e-3)
    for col in ("CGSUBP", "BPAPS", "FYCPR", "GDPM", "CONS", "HHDI"):
        np.testing.assert_allclose(moved(col), 0.0, atol=1e-3, err_msg=col)
    es = (report or {}).get("exit_status", {})
    assert es and all(v == "tol" for v in es.values()), es
