"""Calibration scorecard.

How well does the *raw* model (residuals/add-factors OFF) reproduce the OBR's
published baseline? The anchored model matches by construction (the residuals
absorb every error), so the raw-vs-OBR gap is the true measure of calibration
quality across the model's blocks.

Scores, over the horizon vs the EFO baseline:
  - level variables : mean absolute % error (MAPE)
  - rate/growth vars : mean absolute error in percentage points

    uv run python -m obr_macro.calibration_score
"""
from __future__ import annotations

import numpy as np

from obr_macro.baseline import build
from obr_macro.data import load_obr_data

START, END = "2025Q1", "2027Q4"

# (code, label, kind) grouped by block. kind: "lvl" -> MAPE %, "pp" -> abs pp.
PANEL = {
    "Demand (expenditure)": [
        ("GDPM", "Real GDP", "lvl"), ("CONS", "Consumption", "lvl"),
        ("IF", "Total investment", "lvl"), ("IBUS", "Business investment", "lvl"),
        ("X", "Exports", "lvl"), ("M", "Imports", "lvl"),
    ],
    "Labour market": [
        ("ETLFS", "Employment", "lvl"), ("EEES", "Employees", "lvl"),
        ("LFSUR", "Unemployment rate", "pp"), ("AWEI", "Average earnings", "lvl"),
    ],
    "Prices & wages": [
        ("CPI", "CPI index", "lvl"), ("RPI", "RPI index", "lvl"),
        ("CPIGR", "CPI inflation", "pp"), ("PGDP", "GDP deflator", "lvl"),
        ("WFP", "Wages & salaries", "lvl"),
    ],
    "Incomes": [
        ("HHDI", "Household income", "lvl"), ("COMP", "Compensation", "lvl"),
        ("RHHDI", "Real household income", "lvl"), ("FYCPR", "Company profits", "lvl"),
    ],
    # Net balances are scored as % of GDP — the same convention forecast.py
    # uses. A % error against a tiny net balance (a difference of two ~£240bn
    # gross flows) is meaninglessly amplified; scoring both scorecards the same
    # way avoids applying the favourable metric only where it helps a headline.
    "External": [
        ("CB", "Current account", "gdp"), ("TB", "Trade balance", "gdp"),
    ],
}


def band(kind, err):
    if err is None or not np.isfinite(err):
        return "X", "no data / dead"
    if kind == "pp":
        return ("OK", "good") if err < 0.3 else ("~", "fair") if err < 1.0 \
            else ("!", "poor") if err < 3.0 else ("X", "off")
    if kind == "gdp":   # error as % of GDP
        return ("OK", "good") if err < 0.5 else ("~", "fair") if err < 1.5 \
            else ("!", "poor") if err < 3.0 else ("X", "off")
    return ("OK", "good") if err < 2 else ("~", "fair") if err < 10 \
        else ("!", "poor") if err < 25 else ("X", "off")


def score_one(model, efo, code, kind, t0, t1):
    if code not in model.columns or code not in efo.columns:
        return None
    gdp_code = "GDPMPS" if "GDPMPS" in efo.columns else "GDPM"
    errs = []
    for t in range(t0, t1 + 1):
        m, e = model.iloc[t][code], efo.iloc[t][code]
        if not (np.isfinite(m) and np.isfinite(e)):
            continue
        if kind == "pp":
            errs.append(abs(m - e))
        elif kind == "gdp":
            g = efo.iloc[t][gdp_code]
            if np.isfinite(g) and g > 0:
                errs.append(100 * abs(m - e) / g)
        elif abs(e) > 1e-9:
            errs.append(100 * abs(m - e) / abs(e))
    return float(np.mean(errs)) if errs else None


def main():
    efo = load_obr_data()
    s = build(anchored=False)          # raw model: no add-factor residuals
    t0, t1 = s.period_idx(START), s.period_idx(END)
    s.solve(START, END)
    raw = s.data

    # which variables does the model ACTUALLY compute vs just pass through?
    has_eq = {s._extract_lhs_var(eq.lhs) for eq in s.equations}
    skipped = {d["var"] for d in s.diagnose_period(t1)}

    def status(code):
        if code not in has_eq:
            return "passthrough (exogenous — held at OBR value)"
        if code in skipped:
            return "passthrough (equation dead — held at OBR value)"
        return "computed"

    print(f"Calibration scorecard — raw model vs OBR baseline, {START}..{END}\n")
    counts = {"OK": 0, "~": 0, "!": 0, "X": 0}
    computed_scores = []
    for block, items in PANEL.items():
        print(f"  {block}")
        for code, label, kind in items:
            err = score_one(raw, efo, code, kind, t0, t1)
            st = status(code)
            if st == "computed":
                mark, word = band(kind, err)
                counts[mark] += 1
                computed_scores.append((label, kind, err, mark))
                tag = word
            else:
                mark, tag = "·", st
            unit = {"pp": "pp", "gdp": "%GDP"}.get(kind, "%")
            errstr = "    —" if err is None else f"{err:6.2f}{unit}"
            print(f"     [{mark:2}] {label:24} {errstr:>9}   {tag}")
        print()

    print("Honest score — only the variables the model actually COMPUTES count:")
    nc = len(computed_scores)
    if nc:
        good = counts["OK"] + counts["~"]
        print(f"   computed: {nc}/21 variables   (the other {21-nc} are passthrough,")
        print(f"   i.e. held at the OBR's published value because their channel is dead/exogenous)")
        print(f"   of the computed: good [OK] {counts['OK']}  fair [~] {counts['~']}  "
              f"poor [!] {counts['!']}  off [X] {counts['X']}")
        print(f"   within a usable band: {good}/{nc} computed = {100*good/nc:.0f}%")
    else:
        print("   none computed.")


if __name__ == "__main__":
    main()
