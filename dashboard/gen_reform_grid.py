"""Generate the dashboard's reform grid — EViews-style overrides on a calibrated baseline.

This mirrors how the OBR runs a reform in EViews: you don't free-run the model,
you solve it against a baseline that already carries add-factors (residual
adjustments) set so the equations track judgement, then *override* the policy
instrument in a scenario and re-solve. The reform impact is scenario - baseline,
and because both share the same held add-factors, the model's common drift
cancels and the marginal response comes out clean and correctly signed.

Concretely:
  - Baseline: the held-add-factor forecast (obr_macro/forecast.py method) -
    add-factors fit over a base window, held forward, residuals ON. The
    demand closure (DINV -> GDPM) is already applied by baseline.build.
  - Scenario: clone the baseline, make the instrument exogenous, set it to
    baseline + shock, keep residuals ON, re-solve. (== EViews `model.override`.)
  - The solver is slow, so we solve only the + and - endpoints per lever and let
    the dashboard scale linearly to any slider value (0 = baseline).

    uv run python -m dashboard.gen_reform_grid
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np

from obr_macro.baseline import build as build_baseline

BASE_START, BASE_END = "2024Q1", "2025Q4"   # window the add-factors are fit over
START, END = "2026Q1", "2027Q4"             # reform horizon (the validated window)
NQ = 8                                       # quarters in START..END inclusive

VARS = [
    ("GDPM",  "Real GDP",              "£bn",       "money"),
    ("CONS",  "Household consumption", "£bn",       "money"),
    ("IF",    "Total investment",      "£bn",       "money"),
    ("IBUS",  "Business investment",   "£bn",       "money"),
    ("ETLFS", "Employment",            "000s jobs", "raw"),
    ("LFSUR", "Unemployment rate",     "pp",        "raw"),
    ("CPI",   "Consumer prices (CPI)", "% vs base", "pct"),
    ("RHHDI", "Real household income", "£bn",       "money"),
]

# Each lever overrides one instrument. `to_internal` maps a display value to the
# instrument's own units. Only levers that stay bounded and correctly signed
# against the held baseline are kept; corporation tax is excluded because its
# business-investment-to-GDP transmission is dead in this model (a rise and a cut
# move GDP the same way under the demand closure, and the cost-of-capital closure
# diverges) — it needs that channel re-calibrated before it can be shown honestly.
LEVERS = [
    dict(id="CGG", name="Government consumption", var="CGG", unit="£bn/yr",
         lo=-10.0, hi=10.0, step=0.5, to_internal=lambda v: v * 1000.0 / 4.0,
         desc="Day-to-day government spending — a direct part of GDP. Higher spending lifts demand; the multiplier builds over time."),
    dict(id="X", name="Export demand", var="X", unit="£bn/yr",
         lo=-10.0, hi=10.0, step=0.5, to_internal=lambda v: v * 1000.0 / 4.0,
         desc="External demand for UK exports (e.g. stronger or weaker world growth). Exports add directly to GDP."),
    dict(id="R", name="Bank Rate", var="R", unit="pp",
         lo=-1.0, hi=1.0, step=0.25, to_internal=lambda v: v,
         desc="Bank Rate. A rise weighs on investment and demand; the effect is clearest over the first six quarters."),
]


def held_baseline():
    """The calibrated baseline: add-factors fit over the base window, held
    forward, residuals applied. baseline.build already swaps in the demand
    closure (DINV -> GDPM), so government and trade flows feed GDP directly."""
    s = build_baseline(anchored=True)
    bt0, bt1 = s.period_idx(BASE_START), s.period_idx(BASE_END)
    acc = defaultdict(list)
    for (var, t), r in s.residuals.items():
        if bt0 <= t <= bt1 and np.isfinite(r):
            acc[var].append(r)
    ft0, ft1 = s.period_idx(START), s.period_idx(END)
    for var, rs in acc.items():
        af = float(np.mean(rs))
        for t in range(ft0, ft1 + 1):
            s.residuals[(var, t)] = af
    s._shock_active = False    # held add-factors APPLIED (not a free run)
    s.solve(START, END)
    return s


def disp(kind, base, shock):
    if base is None or shock is None or not (np.isfinite(base) and np.isfinite(shock)):
        return None
    d = shock - base
    if kind == "money":
        return round(d / 1000.0, 4)
    if kind == "pct":
        return round(100.0 * d / base, 4) if abs(base) > 1e-9 else None
    return round(d, 4)


# Plausibility caps per display unit. A reform response that exceeds these is the
# solver diverging, not economics — we drop the variable and warn rather than
# ship a runaway value to the dashboard.
SANE = {"money": 2000.0, "pct": 100.0, "raw": 10000.0}


def is_sane(kind, arr):
    cap = SANE.get(kind, 1e12)
    return all(v is None or abs(v) <= cap for v in arr)


def solve_override(base, lever, value):
    """Override the instrument (EViews `model.override`) and re-solve against the
    held baseline. Residuals stay ON, shared with the baseline, so the held
    add-factors cancel in the difference. Returns the re-solved data frame."""
    sh = base.clone()                       # inherits residuals + _shock_active=False
    var = lever["var"]
    sh.make_exogenous(var)
    t0 = sh.period_idx(START)
    size = lever["to_internal"](value)
    for p in range(NQ):
        t = t0 + p
        old = float(base.data.iloc[t][var])
        sh._set(var, t, old + size)
    sh.solve(START, END)
    return sh.data


def run_point(base, lever, value, control):
    """Reform impact for one slider endpoint: shocked re-solve minus the
    zero-shock control re-solve. Differencing against the control (same
    exogeneity, same starting data, same solve) cancels the re-solve drift of
    non-converged equations exactly; differencing against the baseline does
    not, and that drift can dwarf the policy response."""
    sdat = solve_override(base, lever, value)
    t0, t1 = base.period_idx(START), base.period_idx(END)
    series = {}
    for code, _l, _u, kind in VARS:
        if code in control.columns and code in sdat.columns:
            arr = [disp(kind, float(control.iloc[t][code]), float(sdat.iloc[t][code]))
                   for t in range(t0, t1 + 1)]
            if not is_sane(kind, arr):
                print(f"[grid]   ! dropping {code} (diverged, |Δ| over cap)", flush=True)
                continue
            if any(v is not None and abs(v) > 1e-9 for v in arr):
                series[code] = arr
    return series


def main():
    print("[grid] building held-add-factor baseline ...", flush=True)
    base = held_baseline()
    t0, t1 = base.period_idx(START), base.period_idx(END)
    periods_ref = [str(base.index[t]) for t in range(t0, t1 + 1)]

    out_levers = []
    for lev in LEVERS:
        print(f"[grid] {lev['id']} zero-shock control ...", flush=True)
        control = solve_override(base, lev, 0.0)
        points = []
        for value in (lev["lo"], lev["hi"]):
            print(f"[grid] {lev['id']} = {value}{lev['unit']} ...", flush=True)
            points.append({"shock": value, "series": run_point(base, lev, value, control)})
        # The dashboard scales each endpoint, so a variable is only usable if BOTH
        # endpoints kept it. Drop any var missing from either.
        common = set(points[0]["series"]) & set(points[1]["series"])
        for p in points:
            p["series"] = {k: v for k, v in p["series"].items() if k in common}
        out_levers.append({
            "id": lev["id"], "name": lev["name"], "var": lev["var"], "unit": lev["unit"],
            "lo": lev["lo"], "hi": lev["hi"], "step": lev["step"], "desc": lev["desc"],
            "points": points,
        })
        print(f"[grid]   moved: {', '.join(sorted(common))}", flush=True)

    data = {
        "meta": {"start": START, "end": END,
                 "note": "Emulator output (15 Oct 2025 OBR model code). The reform is run as in "
                         "EViews: the policy instrument is overridden in a scenario and solved "
                         "against a baseline that already carries the OBR's held add-factors, so "
                         "the impact is scenario − baseline with the model's common drift cancelled. "
                         "Endpoints are solved; the slider scales linearly between them. "
                         "Illustrative, not an OBR forecast."},
        "periods": periods_ref,
        "variables": [{"code": c, "label": l, "unit": u} for c, l, u, _ in VARS],
        "levers": out_levers,
    }
    out = "dashboard/public/data/reform_grid.json"
    with open(out, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"[grid] wrote {out}", flush=True)


if __name__ == "__main__":
    main()
