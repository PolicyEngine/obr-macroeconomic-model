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
from obr_macro.scoring import BAND_LEGEND, WORDS, band, var_error

START, END = "2025Q1", "2027Q4"

# (code, label, kind) grouped by block. kind: "lvl" -> MAPE %, "pp" -> abs pp.
PANEL = {
    "Demand (expenditure)": [
        ("GDPM", "Real GDP", "lvl"),
        ("CONS", "Consumption", "lvl"),
        ("IF", "Total investment", "lvl"),
        ("IBUS", "Business investment", "lvl"),
        ("X", "Exports", "lvl"),
        ("M", "Imports", "lvl"),
    ],
    "Labour market": [
        ("ETLFS", "Employment", "lvl"),
        ("EEES", "Employees", "lvl"),
        ("LFSUR", "Unemployment rate", "pp"),
        ("AWEI", "Average earnings", "lvl"),
    ],
    "Prices & wages": [
        ("CPI", "CPI index", "lvl"),
        # The model's RPI is the year-on-year RPI *inflation rate*
        # (RPI = PR/PR(-4)*100-100), not the RPI price index. Score it against
        # the EFO RPIGR inflation series (a rate, in pp) — comparing this rate
        # to the EFO RPI *index* (~400) is a category error that read as a
        # meaningless ~99.6% "level" gap. The residual pp error reflects the
        # real weakness: the RPI index PR (≈ the exogenous I7 normaliser)
        # freezes once its unpublished history runs out, so modelled inflation
        # decays toward zero over the horizon (see docs/calibration_scorecard.md).
        ("RPI", "RPI inflation", "pp", "RPIGR"),
        ("CPIGR", "CPI inflation", "pp"),
        ("PGDP", "GDP deflator", "lvl"),
        ("WFP", "Wages & salaries", "lvl"),
    ],
    "Incomes": [
        ("HHDI", "Household income", "lvl"),
        ("COMP", "Compensation", "lvl"),
        ("RHHDI", "Real household income", "lvl"),
        ("FYCPR", "Company profits", "lvl"),
    ],
    # Net balances are scored as % of GDP — the same convention forecast.py
    # uses. A % error against a tiny net balance (a difference of two ~£240bn
    # gross flows) is meaninglessly amplified; scoring both scorecards the same
    # way avoids applying the favourable metric only where it helps a headline.
    "External": [
        ("CB", "Current account", "gdp"),
        ("TB", "Trade balance", "gdp"),
    ],
}


def raw_solve():
    """Raw solve (residuals off) with the EFO seed removed from the horizon.

    The solver's data frame is pre-filled with the EFO path, so a period whose
    Gauss-Seidel iteration exits on a stall-break would otherwise sit near the
    EFO seed and flatter the raw scorecard. Pass 1 does a plain raw solve to
    find which equations are actually live; pass 2 re-solves on a fresh solver,
    reseeding every live computed variable at each period from the model's own
    previous-period value before solving that period, so no computed variable
    can score well merely by inheriting the EFO seed.
    """
    probe = build(anchored=False)
    t0, t1 = probe.period_idx(START), probe.period_idx(END)
    probe.solve(START, END)
    has_eq = {probe._extract_lhs_var(eq.lhs) for eq in probe.equations}
    skipped = {d["var"] for d in probe.diagnose_period(t1)}
    live = sorted(has_eq - skipped)

    s = build(anchored=False)
    col_locs = [s.data.columns.get_loc(c) for c in live if c in s.data.columns]
    for t in range(t0, t1 + 1):
        if t > 0:
            s.data.iloc[t, col_locs] = s.data.iloc[t - 1, col_locs].values
        s.solve_period(t)
    return s, has_eq, skipped, t0, t1


def main():
    efo = load_obr_data()
    s, has_eq, skipped, t0, t1 = raw_solve()  # raw model: no add-factor residuals
    raw = s.data

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
        for entry in items:
            # entries are (code, label, kind) or (code, label, kind, efo_code)
            code, label, kind = entry[0], entry[1], entry[2]
            efo_code = entry[3] if len(entry) > 3 else None
            err = var_error(raw, efo, code, kind, t0, t1, efo_code)
            st = status(code)
            if st == "computed":
                mark = band(kind, err)
                word = (
                    WORDS[mark]
                    if err is not None and np.isfinite(err)
                    else "no data / dead"
                )
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
        print(f"   computed: {nc}/21 variables   (the other {21 - nc} are passthrough,")
        print(
            "   i.e. held at the OBR's published value because their channel is dead/exogenous)"
        )
        print(
            f"   of the computed: good [OK] {counts['OK']}  fair [~] {counts['~']}  "
            f"poor [!] {counts['!']}  off [X] {counts['X']}"
        )
        print(f"   within band: {good}/{nc} computed = {100 * good / nc:.0f}%")
        print(f"   ({BAND_LEGEND})")
    else:
        print("   none computed.")


if __name__ == "__main__":
    main()
