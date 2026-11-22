"""The gilt yield ``RL``: which maturity it is, and what a shock to it does.

Two things are pinned here.

1. ``RL`` is the 20-year gilt yield. The OBR's variables workbook (row 462)
   calls it "Long rates: 20 year gilt yield", and the loader takes it from the
   EFO table 1.9 column headed "Long-term interest rates (20-year gilts)".
   Earlier text in this repo called it the 10-year yield. The fast tests read
   the shipped workbooks and the repo's own wording so the two cannot drift
   apart again.

2. A gilt-yield shock reaches GDP through one equation, the listing's l.649:

       EECPP = ((1 + RL/100)^0.25 - 1) * PIHH(-1) * 0.729
             + ((1 + 0.05)^0.25 - 1) * PIHH(-1) * 0.271

   ``EECPP`` (employees' contributions to funded pension schemes, which in the
   ONS data includes the household contribution supplements, D.614) is
   subtracted from household disposable income through ``EESC`` (l.651). The
   matching income, the investment return attributed to pension holders, sits
   in ``APIIH``, which has no equation. So a higher yield lowers ``HHDI`` one
   for one with ``EECPP``, and consumption follows real income. The slow tests
   check that the response is the listing's arithmetic and nothing else, and
   pin its size. They are regression pins on the emulator, not a claim about
   the effect of gilt yields on the economy.
"""

from pathlib import Path

import openpyxl
import pytest

from obr_macro.data import DATA_DIR
from obr_macro.reform_analysis import MONETARY_CONDITIONING_OFF

ROOT = Path(__file__).resolve().parents[1]
START, END = "2026Q2", "2028Q4"


def test_variables_workbook_calls_rl_the_20_year_gilt_yield():
    wb = openpyxl.load_workbook(
        DATA_DIR / "obr_model_variables_october_2025.xlsx", read_only=True
    )
    rows = [
        r
        for ws in wb
        for r in ws.iter_rows(values_only=True)
        if r and len(r) > 2 and r[2] == "RL"
    ]
    assert len(rows) == 1, rows
    assert rows[0][1] == "Long rates: 20 year gilt yield"
    assert rows[0][5] == "Exogenous"


def test_efo_column_loaded_as_rl_is_headed_20_year_gilts():
    """data.py reads RL from column 4 (1-based) of table 1.9."""
    wb = openpyxl.load_workbook(
        DATA_DIR / "obr_efo_october_2026_economy.xlsx", read_only=True
    )
    header = [r for i, r in enumerate(wb["1.9"].iter_rows(values_only=True)) if i == 2][
        0
    ]
    assert header[3] == "Long-term interest rates (20-year gilts)"


def test_repo_wording_says_20_year_not_10_year():
    assert "20-year" in MONETARY_CONDITIONING_OFF["RL"]
    for rel in ("docs/monetary_conditioning.md", "obr_macro/reform_analysis.py"):
        text = (ROOT / rel).read_text()
        assert "10-year gilt" not in text, rel


@pytest.fixture(scope="module")
def gilt_runs():
    """Baseline and +1 point RL (sustained), default closure, 2026Q2-2028Q4."""
    from obr_macro import reform_analysis as ra

    template = ra._build_reform_template("RL", START, END, False, True)
    base, shocked = template.clone(), template.clone()
    ra.apply_spending_shock(shocked, "RL", 1.0, START, 12, nominal_consistent=False)
    base.solve(START, END)
    shocked.solve(START, END)
    return base, shocked, base.period_idx(START)


def _delta(runs, var, q):
    base, shocked, i0 = runs
    return shocked.data[var].iloc[i0 + q] - base.data[var].iloc[i0 + q]


@pytest.mark.slow
def test_eecpp_response_is_the_listing_l649_to_the_pound(gilt_runs):
    base, shocked, i0 = gilt_runs
    for q in (0, 3, 10):
        pihh_lag = base.data["PIHH"].iloc[i0 + q - 1]
        rl0 = base.data["RL"].iloc[i0 + q]
        rl1 = shocked.data["RL"].iloc[i0 + q]
        assert rl1 - rl0 == pytest.approx(1.0)
        expected = (
            ((1 + rl1 / 100) ** 0.25 - (1 + rl0 / 100) ** 0.25) * pihh_lag * 0.729
        )
        assert _delta(gilt_runs, "EECPP", q) == pytest.approx(expected, abs=1.0)
    # Measured 22 Nov 2026: 5,215 / 5,203 / 5,195 (GBP m a quarter).
    assert _delta(gilt_runs, "EECPP", 0) == pytest.approx(5215.1, rel=0.01)


@pytest.mark.slow
def test_household_income_falls_one_for_one_with_no_offsetting_receipt(gilt_runs):
    """HHDI = ... - EESC + PIRHH ...: EECPP goes through EESC (l.651), and the
    only other mover is WYQC inside PIRHH (profits, second round)."""
    for q in (0, 3, 10):
        d_eecpp = _delta(gilt_runs, "EECPP", q)
        assert _delta(gilt_runs, "EESC", q) == pytest.approx(d_eecpp, abs=1.0)
        # The pension adjustment NEAHH (l.660) rises by the same amount, so
        # the saving ratio rises instead of income being unchanged.
        assert _delta(gilt_runs, "NEAHH", q) == pytest.approx(d_eecpp, abs=1.0)
        assert _delta(gilt_runs, "HHDI", q) == pytest.approx(
            -d_eecpp + _delta(gilt_runs, "PIRHH", q), abs=1.0
        )
        # No receipts-side variable has a gilt-yield term.
        for exog in ("APIIH", "OSB", "EMPCPP", "DIPHH"):
            assert _delta(gilt_runs, exog, q) == 0.0, exog
    # Measured: -5,276 at q1, of which PIRHH (WYQC) is -61.
    assert _delta(gilt_runs, "HHDI", 0) == pytest.approx(-5275.9, rel=0.01)
    assert -100 < _delta(gilt_runs, "PIRHH", 0) < 0


@pytest.mark.slow
def test_pension_wealth_leg_is_not_in_the_figure(gilt_runs):
    """In the listing a higher yield also revalues the pension stock PIHH down
    (l.795, through DBR l.797). PIHH is held on its data path here (H4 in
    docs/published_model_review.md), so that leg is absent: DBR moves, PIHH
    does not."""
    assert _delta(gilt_runs, "DBR", 0) < 0
    for q in (0, 3, 10):
        assert _delta(gilt_runs, "PIHH", q) == 0.0


@pytest.mark.slow
def test_gdp_response_is_consumption_only_and_pinned(gilt_runs):
    for q in (0, 3, 10):
        assert _delta(gilt_runs, "GDPM", q) == pytest.approx(
            _delta(gilt_runs, "CONS", q), abs=0.5
        )
    # Measured 22 Nov 2026 (October 2026 EFO, default nominal-GDP pin):
    # -479 / -989 / -1,627 GBP m at q1 / q4 / q11.
    assert _delta(gilt_runs, "GDPM", 0) == pytest.approx(-478.8, rel=0.02)
    assert _delta(gilt_runs, "GDPM", 3) == pytest.approx(-989.5, rel=0.02)
    assert _delta(gilt_runs, "GDPM", 10) == pytest.approx(-1627.3, rel=0.02)
