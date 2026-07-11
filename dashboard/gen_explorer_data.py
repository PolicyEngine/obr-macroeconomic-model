"""Generate real solver output for the dashboard's interactive explorer.

Replays each of the five reform scenarios (matching reform_analysis.run_five_reforms)
and captures the baseline-vs-shock delta for a panel of variables across the full
horizon, then writes a compact JSON the dashboard embeds.
"""

import json
import numpy as np

from obr_macro.full_solver import FullOBRSolver
from obr_macro.reform_analysis import (
    GDPM_EQ,
    IBUS_EQ,
    IF_EQ,
    IBUSX_EQ,
    _ensure_ibusx_inputs,
)

START, END = "2025Q1", "2027Q4"

# Corporation-tax scenarios are excluded: under the cost-of-capital closure the
# re-solved path diverges (~x2 per quarter, reaching tens of £bn), which is
# solver behaviour, not economics — the same reason gen_reform_grid excludes
# the TCPRO lever. The £10bn-government-investment scenario is excluded because
# under the standard closure IF is a given input (CGIPS -> GGIPS -> GGI never
# reaches GDP), so it is structurally unable to move anything.
SCENARIOS = [
    dict(
        id="gov_spend",
        name="£5bn government spending",
        var="CGG",
        shock=1250,
        periods=12,
        closure=False,
        tag="Demand",
        shocklab="CGG +£1.25bn/qtr",
    ),
    dict(
        id="austerity",
        name="£10bn spending cut (austerity)",
        var="CGG",
        shock=-2500,
        periods=12,
        closure=False,
        tag="Demand",
        shocklab="CGG −£2.5bn/qtr",
    ),
    dict(
        id="export_rise",
        name="£10bn export boom",
        var="X",
        shock=2500,
        periods=12,
        closure=False,
        tag="Demand",
        shocklab="X +£2.5bn/qtr",
    ),
    dict(
        id="export_cut",
        name="£10bn export slump",
        var="X",
        shock=-2500,
        periods=12,
        closure=False,
        tag="Demand",
        shocklab="X −£2.5bn/qtr",
    ),
    dict(
        id="rate_rise",
        name="1pp Bank Rate rise",
        var="R",
        shock=1.0,
        periods=12,
        closure=False,
        tag="Monetary",
        shocklab="R +1pp",
    ),
]

# variable code -> (label, unit, kind). kind drives how the display number is computed.
VARS = [
    ("GDPM", "Real GDP", "£bn", "money"),
    ("CONS", "Household consumption", "£bn", "money"),
    ("IF", "Total investment", "£bn", "money"),
    ("IBUS", "Business investment", "£bn", "money"),
    ("ETLFS", "Employment", "000s jobs", "raw"),
    ("LFSUR", "Unemployment rate", "pp", "raw"),
    ("CPI", "Consumer prices (CPI)", "% vs base", "pct"),
    ("RHHDI", "Real household income", "£bn", "money"),
]


def build(closure):
    s = FullOBRSolver(verbose=False)
    s.swap_closure("DINV", GDPM_EQ)
    if closure:
        _ensure_ibusx_inputs(s)
        s.swap_closure("IBUSX", IBUSX_EQ)
        s.swap_closure("IBUS", IBUS_EQ)
        s.swap_closure("IF_PLACEHOLDER", IF_EQ)
    return s


def disp(kind, base, shock):
    if base is None or shock is None or not (np.isfinite(base) and np.isfinite(shock)):
        return None
    d = shock - base
    if kind == "money":
        return round(d / 1000.0, 4)  # £m -> £bn
    if kind == "pct":
        return round(100.0 * d / base, 4) if abs(base) > 1e-9 else None
    return round(d, 4)  # raw (000s jobs, pp)


# Plausibility caps per display unit (same rule as gen_reform_grid). A response
# beyond these is the solver diverging, not economics — drop the variable and
# warn rather than ship a runaway value to the dashboard.
SANE = {"money": 2000.0, "pct": 100.0, "raw": 10000.0}


def is_sane(kind, arr):
    cap = SANE.get(kind, 1e12)
    return all(v is None or abs(v) <= cap for v in arr)


# Minimum |Δ| per display unit before the divergence test applies — tiny
# responses are allowed to wobble.
SMALL = {"money": 2.0, "pct": 2.0, "raw": 200.0}


def is_diverging(kind, arr):
    """A response still accelerating at the end of the horizon is the solver
    diverging (the corp-tax failure mode: ~x2 per quarter), not economics.
    A genuine multiplier path flattens; require the final value to be less
    than 2x the value a year earlier once the response is material."""
    vals = [abs(v) for v in arr if v is not None]
    if not vals or max(vals) < SMALL.get(kind, 1e12):
        return False
    a, b = arr[-5], arr[-1]
    if a is None or b is None or abs(a) < 1e-9:
        return True  # material response appearing from nothing in the last year
    return abs(b) / abs(a) > 2.0


def is_symmetric(pos_arr, neg_arr):
    """Same guard as gen_reform_grid: a genuine response to ± shocks roughly
    mirrors; a response dominated by non-converged-equation noise is
    direction-invariant (or wildly lopsided) and fails this."""
    pairs = [
        (x, y) for x, y in zip(pos_arr, neg_arr) if x is not None and y is not None
    ]
    if not pairs:
        return False
    mag = max(max(abs(x) for x, _ in pairs), max(abs(y) for _, y in pairs))
    if mag < 0.05:
        return True
    worst = max(abs(x + y) for x, y in pairs)
    return worst <= 0.6 * mag


def _delta_series(bdat, sdat, t0, t1):
    """Per-variable display deltas (shock minus base) over the horizon."""
    out = {}
    for code, _lab, _unit, kind in VARS:
        if code not in bdat.columns or code not in sdat.columns:
            continue
        out[code] = [
            disp(kind, float(bdat.iloc[t][code]), float(sdat.iloc[t][code]))
            for t in range(t0, t1 + 1)
        ]
    return out


def run_scenario(sc):
    # Baseline and shocked runs share one build and the same structure (the
    # instrument exogenous in both): the delta then isolates the shock instead
    # of being contaminated by the baseline re-solving the instrument
    # endogenously and drifting off the databank.
    base = build(sc["closure"])
    base.make_exogenous(sc["var"])
    base._shock_active = True

    shock = base.clone()
    shock.apply_shock(sc["var"], sc["shock"], START, periods=sc["periods"])

    # Mirror run (same magnitude, opposite sign) purely for the symmetry
    # guard: channels whose ± responses do not roughly mirror are dominated
    # by non-converged-equation noise, not economics, and are dropped.
    mirror = base.clone()
    mirror.apply_shock(sc["var"], -sc["shock"], START, periods=sc["periods"])

    base.solve(START, END)
    bdat = base.data.copy()
    shock.solve(START, END)
    sdat = shock.data.copy()
    mirror.solve(START, END)
    mdat = mirror.data.copy()

    t0, t1 = base.period_idx(START), base.period_idx(END)
    periods = [str(base.index[t]) for t in range(t0, t1 + 1)]

    shock_series = _delta_series(bdat, sdat, t0, t1)
    mirror_series = _delta_series(bdat, mdat, t0, t1)

    series = {}
    for code, _lab, _unit, kind in VARS:
        if code not in shock_series:
            continue
        arr = shock_series[code]
        if not is_symmetric(arr, mirror_series.get(code, [])):
            print(
                f"[gen]   ! dropping {code} (± responses do not mirror; "
                "artifact-dominated)",
                flush=True,
            )
            continue
        if not is_sane(kind, arr):
            print(f"[gen]   ! dropping {code} (diverged, |Δ| over cap)", flush=True)
            continue
        if is_diverging(kind, arr):
            print(
                f"[gen]   ! dropping {code} (still accelerating at horizon end)",
                flush=True,
            )
            continue
        # keep only if something actually moves
        if any(v is not None and abs(v) > 1e-9 for v in arr):
            series[code] = arr
    return periods, series


def main():
    periods_ref = None
    out_scen = []
    for sc in SCENARIOS:
        print(f"[gen] running {sc['id']} ...", flush=True)
        periods, series = run_scenario(sc)
        periods_ref = periods_ref or periods
        if not series:
            print(
                f"[gen]   ! dropping scenario {sc['id']} entirely: no channel "
                "survived the divergence guards",
                flush=True,
            )
            continue
        out_scen.append(
            {
                "id": sc["id"],
                "name": sc["name"],
                "tag": sc["tag"],
                "var": sc["var"],
                "shock": sc["shocklab"],
                "closure": "investment" if sc["closure"] else "standard",
                "series": series,
            }
        )
        moved = ", ".join(series.keys())
        print(f"[gen]   moved: {moved}", flush=True)

    data = {
        "meta": {
            "start": START,
            "end": END,
            "note": "Emulator output (15 Oct 2025 OBR model code). Deltas are shocked-minus-control "
            "with identical model structure in both runs. Under the demand closure the shock "
            "lands directly in the GDP identity and the behavioural second round is largely "
            "inactive, so the impact multiplier is ~1 by construction (the OBR's own published "
            "impact multiplier for current spending is ~0.45). Corporation-tax scenarios are "
            "excluded: their closure does not solve stably in this emulator. Scenarios "
            "whose ± responses fail a symmetry check are likewise dropped (the "
            "export and Bank Rate scenarios: their solves do not converge under "
            "the corrected convergence test, so their responses are solver "
            "artifacts — previously shipped numbers for them were artifacts too). "
            "Illustrative, not an OBR forecast.",
        },
        "periods": periods_ref,
        "variables": [{"code": c, "label": lbl, "unit": u} for c, lbl, u, _ in VARS],
        "scenarios": out_scen,
    }
    path = "dashboard/public/data/explorer_data.json"
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))
    print(f"[gen] wrote {path}", flush=True)


if __name__ == "__main__":
    main()
