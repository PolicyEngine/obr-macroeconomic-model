"""Where does medium-term convergence come from? Write the decomposition.

Every number in ``docs/medium_term_convergence.md`` comes from the file this
script writes, ``results/convergence_decomposition.json``. It runs the same
sustained shock under each mechanism that could bring a shock response back
to zero, over 24 quarters (2025Q1-2030Q4), so the five-year fade and the
quarters after it are both visible:

* ``cgg_default``    -- government consumption +GBP 1,250m a quarter, the
  ``run_reform`` default: add-factors frozen into baseline and shocked run,
  no fade.
* ``cgg_free``       -- the same shock with the add-factors off in both runs
  (a free-running pair), to measure what the add-factors do to the DELTA.
* ``cgg_fade``       -- the same shock with ``published_conventions=True``:
  the OBR's 0.6 impact multiplier and five-year taper, imposed.
* ``cgg_temporary``  -- the default run with the shock ending after 4
  quarters, to show what the equations do once a shock is withdrawn.
* ``tax_default`` / ``tax_free`` -- a household tax rise of GBP 1,616m a
  quarter (the README's 1p basic-rate costing), the one channel with
  behavioural dynamics, anchored and free-running.

    uv run python scripts/convergence_decomposition.py            # all legs
    uv run python scripts/convergence_decomposition.py --leg cgg_default

Each leg is two or three 24-quarter solves; ``--leg`` runs one and merges it
into the JSON, so the legs can be run one at a time on a shared machine.
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np

from obr_macro import FullOBRSolver, run_reform
from obr_macro.published_conventions import TAPER_QUARTERS, multiplier_profile
from obr_macro.reform_analysis import (
    GDPM_EQ,
    HOUSEHOLD_COSTING_VAR,
    _apply_household_costing,
    _build_reform_template,
    apply_nominal_gdp_pin,
    apply_spending_shock,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "convergence_decomposition.json"
START, END = "2025Q1", "2030Q4"
QUARTERS = 24
CGG_SHOCK = 1250.0
TAX_SHOCK = 1616.0
COLS = ("GDPM", "GDPMPS", "CONS", "HHDI", "RHHDI", "PGDP", "PSNBNSA")


def _r(x, nd=3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _by_year(xs):
    """Mean of each block of four quarters (years 1..6 after the shock)."""
    return [_r(float(np.mean(xs[i : i + 4])), 4) for i in range(0, len(xs), 4)]


def _status(*solvers):
    out = {}
    for name, sv in solvers:
        rep = getattr(sv, "last_solve_report", None) or {}
        es = rep.get("exit_status", {})
        out[name] = {
            "tol": sum(1 for s in es.values() if s == "tol"),
            "quarters": len(es),
            "not_tol": {str(q): s for q, s in es.items() if s != "tol"},
        }
    return out


def _free_template(var):
    """The reform template with every add-factor off.

    ``_build_reform_template`` minus ``freeze_anchoring`` and
    ``_anchor_published_levels``: same closure swap, same nominal-GDP pin,
    same exogenous instrument. With ``_shock_active`` set and nothing frozen
    the solver applies no anchoring residual, so baseline and shocked run are
    both the raw equations (the README's "free-running" configuration).
    """
    s = FullOBRSolver(verbose=False)
    s.swap_closure("DINV", GDPM_EQ)
    apply_nominal_gdp_pin(s)
    if var != HOUSEHOLD_COSTING_VAR:
        s.make_exogenous(var)
    s._shock_active = True
    return s


def pair(var, shock, periods, anchored=True):
    """Baseline/shocked pair; returns per-quarter deltas and ratios."""
    tpl = (
        _build_reform_template(var, START, END, False)
        if anchored
        else _free_template(var)
    )
    base, k = tpl.clone(), tpl.clone()
    if var == HOUSEHOLD_COSTING_VAR:
        _apply_household_costing(k, shock, START, periods)
    else:
        apply_spending_shock(k, var, shock, START, periods, nominal_consistent=True)
    base.solve(START, END)
    k.solve(START, END)
    b, s = base.data.loc[START:END], k.data.loc[START:END]
    deltas = {
        c: [_r(x) for x in (s[c].astype(float) - b[c].astype(float))]
        for c in COLS
        if c in b.columns
    }
    path = [shock if q < periods else 0.0 for q in range(QUARTERS)]
    gdp = np.array(deltas["GDPM"], dtype=float)
    out = {
        "anchored": anchored,
        "shock_m": path,
        "status": _status(("baseline", base), ("shocked", k)),
        "deltas_m": deltas,
        "baseline_gdp_m": [_r(x, 1) for x in b["GDPM"].astype(float)],
        "gdp_pct": [_r(x, 5) for x in 100 * gdp / b["GDPM"].astype(float).to_numpy()],
    }
    if var == HOUSEHOLD_COSTING_VAR:
        # The OBR's basis: current-price GDP lost per pound of revenue raised,
        # quoted as a positive number (README, issue #63).
        nominal = -np.array(deltas["GDPMPS"], dtype=float) / shock
        out["ratio_basis"] = "current-price GDP lost per GBP of revenue, positive"
        out["ratio"] = [_r(x, 4) for x in nominal]
        out["ratio_real"] = [_r(x, 4) for x in -gdp / shock]
    else:
        out["ratio_basis"] = "real GDP gained per real GBP of spending, positive"
        out["ratio"] = [
            _r(g / p, 4) if p else None for g, p in zip(gdp, path, strict=True)
        ]
        # Everything beyond the shock's own entry in the expenditure identity.
        out["second_round_m"] = [_r(g - p) for g, p in zip(gdp, path, strict=True)]
    ratio = [x for x in out["ratio"] if x is not None]
    out["ratio_by_year"] = _by_year(ratio)
    out["gdp_by_year_m"] = _by_year(list(gdp))
    return out


def fade():
    df = run_reform(
        "CGG, published conventions",
        "CGG",
        CGG_SHOCK,
        start=START,
        end=END,
        periods=QUARTERS,
        published_conventions=True,
    )
    gdp = df["delta_gdp_m"].astype(float).to_numpy()
    ratio = gdp / CGG_SHOCK
    return {
        "anchored": True,
        "published_conventions": True,
        "shock_m": [CGG_SHOCK] * QUARTERS,
        "solver_converged": bool(df.attrs.get("solver_converged")),
        "solver_exit_status": json.loads(
            json.dumps(df.attrs.get("solver_exit_status"), default=str)
        ),
        "deltas_m": {
            "GDPM": [_r(x) for x in gdp],
            "CONS": [_r(x) for x in df["delta_cons_m"].astype(float)],
        },
        "ratio_basis": "real GDP gained per real GBP of spending, positive",
        "ratio": [_r(x, 4) for x in ratio],
        "ratio_by_year": _by_year(list(ratio)),
        "gdp_by_year_m": _by_year(list(gdp)),
        "imposed_profile": [
            _r(x, 4) for x in multiplier_profile("current_spending", QUARTERS)
        ],
        "taper_quarters": TAPER_QUARTERS,
        "note": str(df.attrs.get("published_conventions_note", "")),
    }


LEGS = {
    "cgg_default": lambda: pair("CGG", CGG_SHOCK, QUARTERS),
    "cgg_free": lambda: pair("CGG", CGG_SHOCK, QUARTERS, anchored=False),
    "cgg_fade": fade,
    "cgg_temporary": lambda: pair("CGG", CGG_SHOCK, 4),
    "tax_default": lambda: pair(HOUSEHOLD_COSTING_VAR, TAX_SHOCK, QUARTERS),
    "tax_free": lambda: pair(
        HOUSEHOLD_COSTING_VAR, TAX_SHOCK, QUARTERS, anchored=False
    ),
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--leg", choices=sorted(LEGS), action="append")
    args = parser.parse_args()
    legs = args.leg or list(LEGS)
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    doc = json.loads(OUT.read_text()) if OUT.exists() and args.leg else {}
    doc.update(
        {
            "source": "scripts/convergence_decomposition.py",
            "window": [START, END],
            "units": "GBP m per quarter, chained volumes unless stated; "
            "ratios are positive magnitudes",
        }
    )
    doc.setdefault("legs", {})
    for name in legs:
        t0 = time.time()
        leg = LEGS[name]()
        leg["model_commit"] = commit
        leg["machine"] = platform.platform()
        leg["python"] = platform.python_version()
        leg["runtime_s"] = round(time.time() - t0, 1)
        doc["legs"][name] = leg
        OUT.write_text(json.dumps(doc, indent=1) + "\n")
        print(f"{name}: {leg['runtime_s']}s, ratio by year {leg['ratio_by_year']}")


if __name__ == "__main__":
    main()
