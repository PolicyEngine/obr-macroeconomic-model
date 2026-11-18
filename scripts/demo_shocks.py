"""Run the standard demo shocks and write ``results/demo_shocks.json``.

Every number in ``docs/demo.md`` comes from this file. Each shock is sized
with HMRC's ready reckoner (June 2025, 2026-27, divided by four for a
quarterly GBP m path) or the README's examples, and run through the public
``run_reform`` API over its default window (2025Q1-2027Q4, default closure:
the nominal-GDP pin). For the receipts and household columns ``run_reform``
does not return, the same baseline/shocked pair is rebuilt from the cached
template (as ``tests/test_tax_scenarios.py`` does) and checked against
``run_reform``'s GDP delta.

    uv run python scripts/demo_shocks.py

About 55 solves (14 run_reform calls plus 12 rebuilt pairs; the pass-through rows re-solve three times; about 35 minutes): run it on GitHub Actions (``.github/workflows/demo.yml``).
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np

from obr_macro import run_reform
from obr_macro.reform_analysis import (
    HOUSEHOLD_COSTING_VAR,
    _apply_household_costing,
    _apply_price_passthrough,
    _build_reform_template,
)

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "demo_shocks.json"
START, END = "2025Q1", "2027Q4"
COLS = (
    "GDPM",
    "GDPMPS",
    "CONS",
    "IF",
    "IBUSX",
    "HHDI",
    "PSCR",
    "CGNB",
    "CPI",
    "BPAPS",
    "CB",
    "FYCPR",
    "EUVAT",
    "GNP4",
    "LFSUR",
)

# (key, label, var, shock, periods, run_reform kwargs)
SHOCKS = [
    (
        "cgg",
        "Government consumption +GBP 1.25bn a quarter (README)",
        "CGG",
        1250.0,
        12,
        {},
    ),
    (
        "cgg_conventions",
        "Same, OBR published conventions",
        "CGG",
        1250.0,
        12,
        {"published_conventions": True},
    ),
    (
        "income_tax",
        "Income tax basic rate +1p (GBP 6.9bn/yr)",
        "TYEM",
        6900 / 4,
        12,
        {},
    ),
    (
        "household_costing",
        "Household costing path GBP 1,616m a quarter (README)",
        HOUSEHOLD_COSTING_VAR,
        1616.0,
        12,
        {},
    ),
    (
        "employee_nics",
        "Employee NICs main rate +1pp (GBP 5.35bn/yr)",
        "EENIC",
        5350 / 4,
        12,
        {},
    ),
    ("vat", "VAT standard rate +1pp (GBP 8.8bn/yr)", "VREC", 8800 / 4, 12, {}),
    ("fuel_duty", "Fuel duty +5% (GBP 1.2bn/yr)", "TXFUEL", 5 * 240 / 4, 12, {}),
    (
        "corporation_tax_receipts",
        "Corporation tax +1pp as receipts (GBP 3.6bn/yr)",
        "NNSCTP",
        3600 / 4,
        12,
        {},
    ),
    (
        "corporation_tax_rate",
        "Corporation tax rate +5pp, investment closure (README)",
        "TCPRO",
        0.05,
        12,
        {"investment_closure": True},
    ),
    ("bank_rate", "Bank Rate +1pp for 4 quarters", "R", 1.0, 4, {}),
    (
        "bank_rate_conditioned",
        "Bank Rate +1pp for 4 quarters, monetary_conditioning",
        "R",
        1.0,
        4,
        {"monetary_conditioning": True},
    ),
    (
        "vat_passthrough",
        "VAT standard rate +1pp, price_passthrough (#60)",
        "VREC",
        8800 / 4,
        12,
        {"price_passthrough": True},
    ),
    (
        "fuel_duty_passthrough",
        "Fuel duty +5%, price_passthrough (#60)",
        "TXFUEL",
        5 * 240 / 4,
        12,
        {"price_passthrough": True},
    ),
    (
        "cgips_investment_closure",
        "Government investment +GBP 3bn a quarter, investment closure",
        "CGIPS",
        3000.0,
        12,
        {"investment_closure": True},
    ),
]
PAIR_SKIP = {"cgg_conventions", "bank_rate_conditioned"}  # run_reform-only paths


def _r(x, nd=3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def _attrs(df):
    keep = {}
    for k, v in df.attrs.items():
        if isinstance(v, (bool, int, float, str)) or v is None:
            keep[k] = v if not isinstance(v, float) else _r(v, 6)
        elif isinstance(v, (list, tuple)) and all(
            isinstance(x, (int, float, type(None))) for x in v
        ):
            keep[k] = [_r(x, 6) if isinstance(x, float) else x for x in v]
        elif isinstance(v, dict):
            try:
                keep[k] = json.loads(json.dumps(v, default=str))
            except (TypeError, ValueError):
                keep[k] = str(v)
        else:
            keep[k] = str(v)
    return keep


def pair(var, shock, periods, investment_closure, price_passthrough=False):
    tpl = _build_reform_template(var, START, END, investment_closure)
    base, k = tpl.clone(), tpl.clone()
    if var == HOUSEHOLD_COSTING_VAR:
        _apply_household_costing(k, shock, START, periods)
    else:
        k.apply_shock(var, shock, START, periods=periods)
    base.solve(START, END)
    k.solve(START, END)
    if price_passthrough:
        t0, t1 = base.period_idx(START), base.period_idx(END)
        _apply_price_passthrough(k, base.data.copy(), START, END, t0, t1)
    status = {}
    for name, sv in (("baseline", base), ("shocked", k)):
        rep = getattr(sv, "last_solve_report", None) or {}
        es = rep.get("exit_status", {})
        status[name] = {
            "tol": sum(1 for s in es.values() if s == "tol"),
            "quarters": len(es),
            "not_tol": {str(q): s for q, s in es.items() if s != "tol"},
            "dropped": len(rep.get("dropped", [])),
        }
    deltas = {}
    for c in COLS:
        if c not in base.data.columns:
            continue
        d = k.data.loc[START:END, c].astype(float) - base.data.loc[START:END, c].astype(
            float
        )
        deltas[c] = [_r(x) for x in d]
    levels = {
        c: [_r(x) for x in base.data.loc[START:END, c].astype(float)]
        for c in ("GDPM", "GDPMPS", "PGDP", "IBUSX", "CB", "EUVAT", "GNP4")
        if c in base.data.columns
    }
    return {"status": status, "deltas_m": deltas, "baseline_levels": levels}


def main():
    t0 = time.time()
    out = {}
    for key, label, var, shock, periods, kw in SHOCKS:
        t = time.time()
        df = run_reform(name=key, var=var, shock=shock, periods=periods, **kw)
        rec = {
            "label": label,
            "var": var,
            "shock": shock,
            "shocked_quarters": periods,
            "kwargs": kw,
            "periods": df["period"].tolist(),
            "run_reform": {
                c: [_r(x) for x in df[c]]
                for c in ("delta_gdp_m", "pct_gdp", "delta_cons_m", "delta_if_m")
            },
            "attrs": _attrs(df),
        }
        if key not in PAIR_SKIP:
            rec["pair"] = pair(
                var,
                shock,
                periods,
                kw.get("investment_closure", False),
                kw.get("price_passthrough", False),
            )
            g_rr = np.array(rec["run_reform"]["delta_gdp_m"], dtype=float)
            g_pair = np.array(rec["pair"]["deltas_m"]["GDPM"], dtype=float)
            rec["pair_matches_run_reform_max_abs_m"] = _r(
                np.nanmax(np.abs(g_rr - g_pair)), 6
            )
            # Fail rather than write numbers the doc would quote unchecked.
            assert rec["pair_matches_run_reform_max_abs_m"] < 0.01, key
            for name, st in rec["pair"]["status"].items():
                assert st["tol"] == st["quarters"], (key, name, st["not_tol"])
        assert rec["attrs"].get("solver_converged", True), key
        rec["runtime_s"] = round(time.time() - t, 1)
        out[key] = rec
        print(
            f"{key}: q1 {rec['run_reform']['delta_gdp_m'][0]} "
            f"q4 {rec['run_reform']['delta_gdp_m'][3]} "
            f"q12 {rec['run_reform']['delta_gdp_m'][11]} ({rec['runtime_s']}s)",
            flush=True,
        )

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    payload = {
        "source": "scripts/demo_shocks.py",
        "model_commit": commit,
        "machine": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "runtime_s": round(time.time() - t0, 1),
        "window": [START, END],
        "units": "GBP m per quarter (GDPM, CONS, IF, IBUSX chained-volume; the rest current prices); pct_gdp in percent",
        "shocks": out,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} in {payload['runtime_s']}s")


if __name__ == "__main__":
    main()
