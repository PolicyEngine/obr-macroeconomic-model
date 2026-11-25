"""The numbers quoted in the docs against the committed results files.

The README's rule is that every number quoted in the docs traces to a file in
``results/`` or a test. Nothing enforced it: the docs were written by hand
from the JSON, so regenerating a results file (or editing a page) could leave
the two disagreeing without any check failing.

Each test here recomputes a quoted figure from the committed JSON, formats it
the way the page does, and asserts that the page contains it. A failure means
one of two things: a results file was regenerated and the page was not
updated, or the page was edited away from the file. Fix the page, not the
JSON: the results files are written only by their scripts (docs/testing.md).

These tests read files only. They say nothing about whether the JSON still
matches the current model; ``tests/test_tax_scenarios.py`` checks that for
the tax rows of the demo battery with full solves.
"""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MINUS = "−"  # the docs write negative numbers with a true minus sign


def _results(name):
    return json.loads((ROOT / "results" / f"{name}.json").read_text())


def _doc(relpath):
    return (ROOT / relpath).read_text()


def money(x, signed=True):
    """£m rounded to the pound, as the docs print it: +1,266, −161, 0."""
    n = int(round(x))
    if n == 0:
        return "0"
    sign = MINUS if n < 0 else ("+" if signed else "")
    return f"{sign}{abs(n):,}"


def ratio(x, places):
    return f"{x:.{places}f}"


def triple(values, fmt, quarters=(0, 3, 11), **kwargs):
    """'a / b / c' for the first, fourth and twelfth quarter."""
    return " / ".join(fmt(values[q], **kwargs) for q in quarters)


@pytest.fixture(scope="module")
def demo():
    return _results("demo_shocks")["shocks"]


@pytest.fixture(scope="module")
def demo_md():
    return _doc("docs/demo.md")


@pytest.fixture(scope="module")
def examples_md():
    return _doc("docs/examples.md")


@pytest.fixture(scope="module")
def limitations_md():
    return _doc("docs/limitations.md")


def _demo_table_rows(demo_md):
    """The shock table of docs/demo.md as {row id: [cells]}."""
    rows = {}
    for line in demo_md.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 5 and re.fullmatch(r"\d+b?", cells[0]):
            rows[cells[0]] = cells
    return rows


# demo.md table row -> key in results/demo_shocks.json
DEMO_ROWS = {
    "1": "cgg",
    "1b": "cgg_conventions",
    "2": "income_tax",
    "3": "employee_nics",
    "4": "vat",
    "4b": "vat_passthrough",
    "5": "corporation_tax_rate",
    "6": "bank_rate",
    "6b": "bank_rate_conditioned",
    "7": "cgips_investment_closure",
}


def test_demo_table_has_a_row_for_every_mapped_shock(demo, demo_md):
    rows = _demo_table_rows(demo_md)
    assert set(rows) == set(DEMO_ROWS), sorted(rows)
    assert set(DEMO_ROWS.values()) <= set(demo)


@pytest.mark.parametrize("row,key", sorted(DEMO_ROWS.items()))
def test_demo_table_gdp_matches_results(demo, demo_md, row, key):
    """Column 'GDP £m: q1 / q4 / q12' is delta_gdp_m at those quarters."""
    cell = _demo_table_rows(demo_md)[row][2]
    expected = triple(demo[key]["run_reform"]["delta_gdp_m"], money)
    assert cell == expected, f"demo.md row {row} ({key}): {cell!r} != {expected!r}"


def _per_pound(demo, key, series):
    """Positive magnitude of a pair delta per unit of the shock, per quarter."""
    size = abs(demo[key]["shock"])
    return [abs(v) / size for v in demo[key]["pair"]["deltas_m"][series]]


@pytest.mark.parametrize(
    "row,key,series,places",
    [
        # Real GDP per real pound of spending.
        ("1", "cgg", "GDPM", 2),
        # Current-price GDP per pound of revenue (the OBR's basis, #63).
        ("2", "income_tax", "GDPMPS", 2),
        ("3", "employee_nics", "GDPMPS", 2),
        ("4", "vat", "GDPMPS", 3),
        ("4b", "vat_passthrough", "GDPMPS", 3),
    ],
)
def test_demo_table_ratio_matches_results(demo, demo_md, row, key, series, places):
    cell = _demo_table_rows(demo_md)[row][3]
    expected = triple(_per_pound(demo, key, series), ratio, places=places)
    assert cell == expected, f"demo.md row {row} ({key}): {cell!r} != {expected!r}"


def test_demo_table_convention_and_investment_ratios(demo, demo_md):
    """Rows 1b and 7 have no solve pair in the file; the ratio is
    delta_gdp_m over the shock."""
    rows = _demo_table_rows(demo_md)
    for row, key in (("1b", "cgg_conventions"), ("7", "cgips_investment_closure")):
        size = demo[key]["shock"]
        per_pound = [v / size for v in demo[key]["run_reform"]["delta_gdp_m"]]
        expected = triple(per_pound, ratio, places=2)
        assert rows[row][3].startswith(expected), (row, rows[row][3], expected)


@pytest.mark.parametrize(
    "row,key", [("6", "bank_rate"), ("6b", "bank_rate_conditioned")]
)
def test_bank_rate_peak_matches_results(
    demo, demo_md, examples_md, limitations_md, row, key
):
    pct = demo[key]["run_reform"]["pct_gdp"]
    peak = min(pct)
    quarter = pct.index(peak) + 1
    cell = _demo_table_rows(demo_md)[row][3]
    assert cell == f"peak {MINUS}{abs(peak):.3f}% of GDP (q{quarter})", cell
    assert f"{MINUS}{abs(peak):.3f} (q{quarter})" in examples_md
    # limitations.md states the peaks as positive falls.
    assert f"{abs(peak):.3f}%" in limitations_md


def test_demo_borrowing_line_matches_results(demo, demo_md, examples_md):
    cgnb = triple(demo["cgg"]["pair"]["deltas_m"]["CGNB"], money)
    assert cgnb in demo_md
    assert cgnb in examples_md


@pytest.mark.parametrize(
    "key",
    ["income_tax", "employee_nics", "vat", "fuel_duty", "corporation_tax_receipts"],
)
def test_receipts_and_borrowing_move_one_for_one_in_results(demo, key):
    """The docs say PSCR rises and CGNB falls by exactly the revenue in every
    quarter for a receipts shock. Also a sign check on the committed file."""
    size = demo[key]["shock"]
    deltas = demo[key]["pair"]["deltas_m"]
    assert deltas["PSCR"] == pytest.approx([size] * 12, abs=0.01)
    assert deltas["CGNB"] == pytest.approx([-size] * 12, abs=0.01)


def test_results_signs_match_the_documented_conventions(demo):
    """Shocked minus baseline: spending raises GDP; tax rises, a Bank Rate
    rise and a corporation-tax rate rise lower it or leave it unchanged."""
    for key in ("cgg", "cgg_real_only", "cgg_conventions", "cgips_investment_closure"):
        assert min(demo[key]["run_reform"]["delta_gdp_m"]) > 0, key
    for key in (
        "income_tax",
        "household_costing",
        "employee_nics",
        "vat",
        "fuel_duty",
        "vat_passthrough",
        "fuel_duty_passthrough",
        "bank_rate",
        "bank_rate_conditioned",
    ):
        assert max(demo[key]["run_reform"]["delta_gdp_m"]) < 0, key
    assert max(demo["corporation_tax_rate"]["run_reform"]["delta_gdp_m"]) <= 0
    # The household costing lowers household income by about the revenue.
    hhdi = demo["household_costing"]["pair"]["deltas_m"]["HHDI"]
    assert all(-1.1 * 1616 < v < -1616 for v in hhdi), hhdi


def test_every_demo_solve_exited_on_tolerance(demo):
    """The docs say every baseline and shocked solve in the battery converges
    in 12 of 12 quarters, and that run_reform and the solve pair agree."""
    for key, entry in demo.items():
        attrs = entry["attrs"]
        assert attrs["solver_converged"] is True, key
        assert attrs["solver_nonconverged_periods"] == [], key
        if "pair" in entry:
            for side in ("baseline", "shocked"):
                status = entry["pair"]["status"][side]
                assert status["tol"] == status["quarters"] == 12, (key, side)
            assert entry["pair_matches_run_reform_max_abs_m"] == 0.0, key


def test_dropped_equation_count_matches_results(demo, demo_md):
    """The docs say 82 equations are dropped (an input has no data) in the
    default window, the same in every run of the battery."""
    counts = {
        entry["pair"]["status"][side]["dropped"]
        for entry in demo.values()
        if "pair" in entry
        for side in ("baseline", "shocked")
    }
    assert len(counts) == 1, counts
    (dropped,) = counts
    assert f"the same {dropped} equations are dropped" in demo_md
    assert f"{dropped} equations lack an input" in _doc("docs/index.md")
    assert f"{dropped} are skipped at solve time" in _doc("docs/ROADMAP.md")


def test_examples_tables_match_results(demo, examples_md):
    cgg = demo["cgg"]["run_reform"]
    assert (
        f"| GDP, £m | {' | '.join(money(cgg['delta_gdp_m'][q]) for q in (0, 3, 11))} |"
        in examples_md
    )
    assert (
        f"| Consumption, £m | "
        f"{' | '.join(money(cgg['delta_cons_m'][q]) for q in (0, 3, 11))} |"
    ) in examples_md

    hh = demo["household_costing"]
    assert (
        f"| GDP, £m | "
        f"{' | '.join(money(hh['run_reform']['delta_gdp_m'][q]) for q in (0, 3, 11))} |"
    ) in examples_md
    for attr, label in (
        ("gdp_per_revenue_current_price", "Current-price GDP per £ of revenue"),
        ("gdp_per_revenue_real", "Real GDP per £ of revenue"),
    ):
        cells = " | ".join(ratio(hh["attrs"][attr][q], 3) for q in (0, 3, 11))
        assert f"| {label} (`{attr}`) | {cells} |" in examples_md, attr
    hhdi = hh["pair"]["deltas_m"]["HHDI"]
    assert " | ".join(money(hhdi[q]) for q in (0, 3, 11)) in examples_md

    ct = demo["corporation_tax_rate"]
    for label, series in (
        ("GDP, £m", ct["run_reform"]["delta_gdp_m"]),
        ("Total investment `IF`, £m", ct["run_reform"]["delta_if_m"]),
    ):
        cells = " | ".join(money(series[q]) for q in (0, 3, 7, 11))
        assert f"| {label} | {cells} |" in examples_md, label
    plateau = ct["attrs"]["investment_closure_plateau_fraction"]
    assert f"is {plateau:.3f}" in examples_md

    for key in (
        "cgg_real_only",
        "cgg_conventions",
        "income_tax",
        "vat",
        "vat_passthrough",
    ):
        expected = triple(demo[key]["run_reform"]["delta_gdp_m"], money)
        assert expected in examples_md, (key, expected)


def test_sustained_bank_rate_figures_match_site_figures(examples_md):
    bank = _results("site_figures")["figures"]["bank_rate"]
    for run in ("plus_100bp_gdp_m", "minus_100bp_gdp_m"):
        expected = " / ".join(money(bank[run][q]) for q in ("q1", "q4", "q8", "q12"))
        assert expected in examples_md, (run, expected)


def test_anchored_fit_figures_match_site_figures(limitations_md):
    fit = _results("site_figures")["figures"]["anchored_horizon"]
    readme = _doc("README.md")
    gdp = f"{fit['gdp_mape_pct_2025Q1_2027Q4']:.2f}%"
    cons = f"{fit['cons_mape_pct_2025Q1_2027Q4']:.2f}%"
    assert f"GDP {gdp} MAPE, consumption {cons}" in limitations_md
    assert f"to {gdp} (2025Q1 to 2027Q4)" in readme
    assert f"to {fit['gdp_dev_pct_2031Q1']:.2f}% by 2031Q1" in limitations_md
    lfsur = fit["lfsur_pct"]
    assert (
        f"{lfsur['2027Q4']['model']:.2f}% at 2027Q4, "
        f"{lfsur['2031Q1']['model']:.2f}% at 2031Q1"
    ) in limitations_md
    # Unemployment reproduces the EFO by construction.
    for quarter, pair in lfsur.items():
        assert pair["model"] == pytest.approx(pair["efo"], abs=0.005), quarter
    assert fit["nonconverged_quarters"] == 0


def test_limitations_shock_figures_match_results(demo, limitations_md):
    for key in ("vat", "vat_passthrough"):
        expected = triple(_per_pound(demo, key, "GDPMPS"), ratio, places=3)
        assert expected in limitations_md, (key, expected)

    # Government investment under the investment closure, in £bn.
    cgips = demo["cgips_investment_closure"]["run_reform"]["delta_gdp_m"]
    expected = " / ".join(f"+£{cgips[q] / 1000:.2f}bn" for q in (0, 3, 11))
    assert expected in limitations_md, expected

    # Household tax: year-1 average and quarter 12, on both bases.
    hh = demo["household_costing"]["attrs"]
    nominal, real = hh["gdp_per_revenue_current_price"], hh["gdp_per_revenue_real"]
    assert (
        f"averages {sum(nominal[:4]) / 4:.2f} in year 1, rising to "
        f"{nominal[11]:.2f} by quarter 12"
    ) in limitations_md
    assert f"is {sum(real[:4]) / 4:.3f} and {real[11]:.2f}" in limitations_md

    # Corporation tax: business investment at q8 and q12, in £bn.
    ibusx = _results("site_figures")["figures"]["corporation_tax_5pp"]["ibusx_m"]
    assert (
        f"£{abs(ibusx['q8']) / 1000:.2f}bn at q8, "
        f"£{abs(ibusx['q12']) / 1000:.2f}bn at q12"
    ) in limitations_md


def test_government_consumption_ratio_matches_results(demo, limitations_md):
    """'1.01 on impact, drifting up to 1.04 by quarter 12', and the second
    round '+£16m to +£50m'."""
    per_pound = _per_pound(demo, "cgg", "GDPM")
    assert (
        f"{per_pound[0]:.2f} on impact, drifting up to {per_pound[11]:.2f} by quarter 12"
    ) in limitations_md
    cons = demo["cgg"]["run_reform"]["delta_cons_m"]
    assert f"+£{cons[0]:.0f}m to +£{cons[11]:.0f}m" in limitations_md
    # The convergence decomposition reports the same run.
    leg = _results("convergence_decomposition")["legs"]["cgg_default"]
    assert leg["deltas_m"]["GDPM"][:12] == pytest.approx(
        demo["cgg"]["run_reform"]["delta_gdp_m"], abs=0.01
    )


def test_debt_interest_figures_match_results(
    demo, examples_md, limitations_md, demo_md
):
    scenarios = _results("debt_interest_examples")["scenarios"]
    cgg = scenarios["cgg"]["on"]["debt_interest_detail"]
    interest = cgg["delta_debt_interest_m"]
    assert triple(interest, money) in examples_md
    assert triple(interest, money) in demo_md
    assert " / ".join(f"£{interest[q]:.0f}m" for q in (0, 3, 11)) in limitations_md
    assert triple(cgg["delta_borrowing_after_m"], money) in examples_md
    assert triple(cgg["delta_borrowing_before_m"], money) in examples_md
    # 'x% on the cost over three years'.
    share = 100 * sum(interest) / sum(cgg["delta_borrowing_before_m"])
    assert f"({share:.1f}% on the cost over three years)" in limitations_md

    vat = scenarios["vat"]["on"]["debt_interest_detail"]["delta_debt_interest_m"]
    assert triple(vat, money) in examples_md

    gilt = scenarios["gilt_yield"]["on"]
    extra = gilt["debt_interest_detail"]["delta_debt_interest_m"]
    assert (
        f"{money(extra[0])} £m in 2026Q2, rising to {money(extra[-1])} £m in 2028Q4"
        in examples_md
    )
    first, second = sum(extra[:4]) / 1000, sum(extra[4:8]) / 1000
    assert f"adds £{first:.1f}bn and over the second £{second:.1f}bn" in examples_md
    assert (
        f"adds £{first:.1f}bn in the first year and £{second:.1f}bn in the second"
    ) in limitations_md
    gdp = gilt["delta_gdp_m"]
    assert (
        f"GDP: {money(gdp[0])} £m in 2026Q2, {money(gdp[-1])} £m in 2028Q4"
        in examples_md
    )

    # 'GDP is the same with it on or off', and the same CGG run as the demo.
    for name, scenario in scenarios.items():
        assert scenario["on"]["delta_gdp_m"] == pytest.approx(
            scenario["off"]["delta_gdp_m"], abs=0.01
        ), name
    assert scenarios["cgg"]["off"]["delta_gdp_m"] == pytest.approx(
        demo["cgg"]["run_reform"]["delta_gdp_m"], abs=0.01
    )


def test_demand_overlay_figures_match_results(demo, examples_md, limitations_md):
    shocks = _results("demand_overlays")["shocks"]
    cgg = shocks["cgg_1pct_gdp"]
    for mode in ("default", "import_response"):
        expected = triple(cgg[mode]["gdp_per_pound"], ratio, places=3)
        assert expected in examples_md, (mode, expected)
    leaky = cgg["import_response"]["gdp_per_pound"]
    assert f"to {min(leaky):.2f}–{max(leaky):.2f}" in limitations_md
    # 'imports then rise by 9% to 12% of the shock'.
    share = [
        100 * m / s
        for m, s in zip(cgg["import_response"]["delta_imports_m"]["M"], cgg["shock_m"])
    ]
    assert (
        f"rise by {min(share):.0f}% to {max(share):.0f}% of the shock" in limitations_md
    )
    # The household leg is the same run as the demo battery's.
    assert shocks["household_tax_1p"]["default"]["delta_gdp_m"] == pytest.approx(
        demo["household_costing"]["run_reform"]["delta_gdp_m"], abs=0.01
    )
