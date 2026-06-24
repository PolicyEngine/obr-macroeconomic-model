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

BASE_START, BASE_END = "2024Q1", "2025Q4"   # window the add-factors are fit over
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


def band(kind, err):
    if err is None or not np.isfinite(err):
        return "X"
    if kind == "pp":
        return "OK" if err < 0.3 else "~" if err < 1.0 else "!" if err < 3.0 else "X"
    if kind == "gdp":   # error as % of GDP, the convention for net balances
        return "OK" if err < 0.5 else "~" if err < 1.5 else "!" if err < 3.0 else "X"
    return "OK" if err < 2 else "~" if err < 10 else "!" if err < 25 else "X"


def main():
    efo = load_obr_data()
    s, held = forecast()
    has_eq = {s._extract_lhs_var(eq.lhs) for eq in s.equations}
    t1 = s.period_idx(FC_END)
    skipped = {d["var"] for d in s.diagnose_period(t1)}
    t0 = s.period_idx(FC_START)

    print(f"Held-add-factor forecast: fit {BASE_START}..{BASE_END}, project {FC_START}..{FC_END}\n")
    print(f"  add-factors held for {len(held)} behavioural equations\n")
    gdp_code = "GDPMPS" if "GDPMPS" in efo.columns else "GDPM"
    counts = {"OK": 0, "~": 0, "!": 0, "X": 0}
    computed = 0
    for code, label, kind in PANEL:
        if code not in efo.columns or code not in s.data.columns:
            continue
        errs = []
        for t in range(t0, t1 + 1):
            m, e = s.data.iloc[t][code], efo.iloc[t][code]
            if np.isfinite(m) and np.isfinite(e):
                if kind == "pp":
                    errs.append(abs(m - e))
                elif kind == "gdp":
                    g = efo.iloc[t][gdp_code]
                    errs.append(100 * abs(m - e) / g if np.isfinite(g) and g > 0 else None)
                else:
                    errs.append(100 * abs(m - e) / abs(e) if abs(e) > 1e-9 else None)
        errs = [x for x in errs if x is not None]
        err = float(np.mean(errs)) if errs else None
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
    print(f"\n   computed {computed}/{len(PANEL)} | within 10%: {good}/{computed} computed "
          f"({100*good/computed:.0f}%)" if computed else "\n   none computed")


if __name__ == "__main__":
    main()
