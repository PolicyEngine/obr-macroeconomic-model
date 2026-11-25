"""The transmission audit (obr_macro/transmission_audit.py).

The module writes docs/transmission_audit.md. It had no test, and the page
drifted: the module kept the published closure after run_reform moved to the
nominal-GDP pin, and the committed table was last regenerated in October
2026. The fast tests here cover the classification and how the runs are
built; tests/test_model_invariants.py has the slow check that the committed
page matches what the module produces.
"""

import re
from pathlib import Path

import pytest

from obr_macro import transmission_audit as ta
from tests.test_apply_shock import _FakeTemplate

PAGE = Path(__file__).resolve().parents[1] / "docs" / "transmission_audit.md"


def page_rows(text):
    """{shock label: (verdict, [numbers])} from the page's table."""
    rows = {}
    for line in text.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 2 + len(ta.PANEL) and cells[1].startswith("**"):
            numbers = [float(re.sub(r"[%p]", "", c)) for c in cells[2:]]
            rows[cells[0]] = (cells[1].strip("*"), numbers)
    return rows


def _row(**moves):
    return {code: moves.get(code, 0.0) for code, _label, _kind in ta.PANEL}


def test_classification_of_a_response_row():
    assert ta.classify(_row()) == ("dead", [])
    assert ta.classify(_row(GDPM=0.18)) == ("identity-only", [])
    assert ta.classify(_row(GDPM=-0.06, CONS=-0.10)) == ("transmitting", ["CONS"])
    assert ta.classify(_row(LFSUR=0.02))[0] == "transmitting"
    # Within 20% of the threshold is a borderline call and is flagged.
    assert ta.classify(_row(GDPM=0.18, CONS=0.021)) == (
        "transmitting (marginal)",
        ["CONS"],
    )
    # Below the threshold is no move.
    assert ta.classify(_row(GDPM=0.002, CONS=0.004)) == ("dead", [])


def test_residual_business_investment_does_not_count_under_the_default_closure():
    """Under the default closure IBUS is the listing's residual identity with
    total investment exogenous, so a move in it alone is not transmission.
    run_reform calls the same government-investment shock a dead channel."""
    only_ibus = _row(IBUS=-3.84)
    assert ta.classify(only_ibus, "standard") == ("dead", [])
    assert ta.classify(_row(GDPM=0.18, IBUS=0.5), "standard") == ("identity-only", [])
    # Under the investment closure it has its own equation and counts.
    assert ta.classify(only_ibus, "investment") == ("transmitting", ["IBUS"])
    assert ta.classify(_row(CONS=-0.1, IBUS=1.0), "standard") == (
        "transmitting",
        ["CONS"],
    )


def test_audit_runs_are_built_and_shocked_the_way_run_reform_does_it(monkeypatch):
    """The audit must use run_reform's own template builder and spending
    shock, so its closure cannot fall behind run_reform's default again."""
    built = []

    def fake_builder(var, start, end, investment_closure, nominal_gdp_pin=None):
        built.append((var, start, end, investment_closure, nominal_gdp_pin))
        template = _FakeTemplate()
        for col in ("CGGPS", "CGGPSPSF", "PSCE", var):
            if col not in template._proto.data:
                template._proto.data[col] = 200.0
        return template

    monkeypatch.setattr(ta, "_build_reform_template", fake_builder)
    template = ta.build_template("standard", "CGG")
    assert built == [("CGG", ta.START, ta.END, False, None)]
    ta.build_template("investment", "TCPRO")
    assert built[-1] == ("TCPRO", ta.START, ta.END, True, None)

    applied = []
    real = ta.apply_spending_shock

    def spy(solver, var, shock, start, periods, nominal_consistent):
        applied.append((var, shock, start, periods, nominal_consistent))
        return real(solver, var, shock, start, periods, nominal_consistent)

    monkeypatch.setattr(ta, "apply_spending_shock", spy)
    cgg = next(s for s in ta.SHOCKS if s["var"] == "CGG")
    row = ta.run_one(cgg, template)
    # Government consumption carries its nominal legs, as in run_reform.
    assert applied == [("CGG", 1250.0, ta.START, ta.PERIODS, True)]
    assert set(row) == {code for code, _label, _kind in ta.PANEL}

    tax = next(s for s in ta.SHOCKS if s["var"] == "TCPRO")
    ta.run_one(tax, ta.build_template("investment", "TCPRO"))
    assert applied[-1] == ("TCPRO", 0.01, ta.START, ta.PERIODS, False)


def test_audit_refuses_a_run_that_did_not_converge(monkeypatch):
    template = _FakeTemplate()
    clone = template.clone

    def unconverged():
        k = clone()
        k.last_solve_report = {"exit_status": {"2025Q1": "tol", "2025Q2": "stall"}}
        return k

    template.clone = unconverged
    cgg = next(s for s in ta.SHOCKS if s["var"] == "R")
    template._proto.data["R"] = 4.0
    with pytest.raises(RuntimeError, match="did not reach the solver tolerance"):
        ta.run_one(cgg, template)


def test_committed_page_is_a_rendering_of_the_module():
    """The page carries the site's front matter, one row per shock, and a
    summary that counts the verdicts in its own table. (That the numbers are
    current is the slow test in test_model_invariants.py.)"""
    text = PAGE.read_text()
    assert text.startswith(ta.FRONT_MATTER)
    rows = page_rows(text)
    assert list(rows) == [s["label"] for s in ta.SHOCKS]
    counts = {}
    for verdict, _numbers in rows.values():
        counts[verdict] = counts.get(verdict, 0) + 1
    summary = ", ".join(f"{n} {k}" for k, n in sorted(counts.items()))
    assert f"**Summary:** {summary}." in text

    # render() of the page's own rows reproduces the page exactly.
    results = []
    for shock in ta.SHOCKS:
        verdict, numbers = rows[shock["label"]]
        row = {code: v for (code, _l, _k), v in zip(ta.PANEL, numbers)}
        results.append((shock, row, verdict, []))
    rendered = ta.render(results)
    assert page_rows(rendered) == rows
    assert rendered.split("## Reading this")[1] == text.split("## Reading this")[1]
