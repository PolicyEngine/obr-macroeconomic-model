"""Held-add-factor forecasting framework.

The OBR's own method: compute add-factors (residuals) over a base window of
recent data, HOLD them constant, then project the model forward. The forecast is
the model's structural dynamics anchored by the held add-factors — a genuine
forecast, not a reproduction of the input (which is what anchoring at every
period gives).

    uv run python -m obr_macro.forecast
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from obr_macro.baseline import build
from obr_macro.data import load_obr_data
from obr_macro.scoring import BAND_LEGEND, band, var_error

# Window the add-factors are fit over. CAVEAT: the EFO tables only contain
# outturn for the early part of this window — the later quarters (2025H2 in the
# November-2025 EFO) are the OBR's own forecast, so residuals there are fit
# against the OBR's judgement, not data. See docs/forecasting_framework.md.
BASE_START, BASE_END = "2024Q1", "2025Q4"
FC_START, FC_END = "2026Q1", "2027Q4"        # the projected horizon

PANEL = [
    ("GDPM", "Real GDP", "lvl"), ("CONS", "Consumption", "lvl"),
    ("IF", "Total investment", "lvl"), ("IBUS", "Business investment", "lvl"),
    ("X", "Exports", "lvl"), ("M", "Imports", "lvl"),
    ("ETLFS", "Employment", "lvl"), ("LFSUR", "Unemployment rate", "pp"),
    ("CPI", "CPI index", "lvl"), ("CPIGR", "CPI inflation", "pp"),
    ("WFP", "Wages & salaries", "lvl"), ("HHDI", "Household income", "lvl"),
    ("RHHDI", "Real household income", "lvl"), ("FYCPR", "Company profits", "lvl"),
    # net balances are scored as % of GDP (the OBR convention): a % error against
    # their own tiny value is meaninglessly amplified.
    ("CB", "Current account", "gdp"), ("TB", "Trade balance", "gdp"),
]


def forecast(base_start=BASE_START, base_end=BASE_END, fc_start=FC_START, fc_end=FC_END):
    """Project the model forward with add-factors held from the base window."""
    s = build(anchored=True)   # residuals computed over 2024Q1+
    bt0, bt1 = s.period_idx(base_start), s.period_idx(base_end)

    held = {}
    acc = defaultdict(list)
    for (var, t), r in s.residuals.items():
        if bt0 <= t <= bt1 and np.isfinite(r):
            acc[var].append(r)
    for var, rs in acc.items():
        held[var] = float(np.mean(rs))

    ft0, ft1 = s.period_idx(fc_start), s.period_idx(fc_end)
    for var, af in held.items():
        for t in range(ft0, ft1 + 1):
            s.residuals[(var, t)] = af

    s._shock_active = False    # apply the (now held) add-factors
    s.solve(fc_start, fc_end)
    return s, held


def main():
    efo = load_obr_data()
    s, held = forecast()
    has_eq = {s._extract_lhs_var(eq.lhs) for eq in s.equations}
    t1 = s.period_idx(FC_END)
    skipped = {d["var"] for d in s.diagnose_period(t1)}
    t0 = s.period_idx(FC_START)

    print(f"Held-add-factor forecast: fit {BASE_START}..{BASE_END}, project {FC_START}..{FC_END}\n")
    print(f"  add-factors held for {len(held)} behavioural equations\n")
    counts = {"OK": 0, "~": 0, "!": 0, "X": 0}
    computed = 0
    for code, label, kind in PANEL:
        if code not in efo.columns or code not in s.data.columns:
            continue
        err = var_error(s.data, efo, code, kind, t0, t1)
        if code not in has_eq:
            st = "passthrough (exogenous)"
        elif code in skipped:
            st = "passthrough (dead)"
        else:
            st = "computed"
            counts[band(kind, err)] += 1
            computed += 1
        mark = band(kind, err) if st == "computed" else "·"
        unit = {"pp": "pp", "gdp": "%GDP"}.get(kind, "%")
        es = "   —" if err is None else f"{err:6.2f}{unit}"
        print(f"   [{mark:2}] {label:22}{es:>9}   {st}")

    good = counts["OK"] + counts["~"]
    if computed:
        print(f"\n   computed {computed}/{len(PANEL)} | within band: {good}/{computed} computed "
              f"({100*good/computed:.0f}%)")
        print(f"   ({BAND_LEGEND})")
    else:
        print("\n   none computed")


if __name__ == "__main__":
    main()
