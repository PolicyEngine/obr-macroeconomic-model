"""Measure the opt-in import and employment overlays.

    uv run python scripts/demand_overlays.py

Writes ``results/demand_overlays.json``, the source of every figure in
``docs/demand_overlays.md``. Two shocks, each sustained for 12 quarters from
2025Q1 and scored around the anchored reform baseline as ``run_reform`` does:

* ``cgg_1pct_gdp`` -- government consumption ``CGG`` raised by 1% of baseline
  real GDP each quarter (GBP 7.0bn to 7.2bn a quarter).
* ``household_tax_1p`` -- the household costing instrument at GBP 1,616m a
  quarter (1p on the basic rate, the README's figure).

Each is run four ways: default, ``import_response``, ``employment_response``
and both. The default run is solved here as a baseline/shocked pair cloned
from the same template (exactly what ``run_reform`` does) so the import and
labour series, which ``run_reform`` does not return, can be read off.
``published_model_goods_residual`` is a partial calculation, not a solve: the
services response l.223 implies for the default run's demand path, and the
goods residual that follows with total imports fixed (l.217).

Eleven baseline/shocked pairs (the last a goods-elasticity-0 sensitivity
for the government-consumption shock), about seven minutes on a laptop.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np

from obr_macro import demand_overlays as overlays
from obr_macro import reform_analysis as ra

START, END = "2025Q1", "2027Q4"
HOUSEHOLD_TAX = 1616.0
SERIES = ("GDPM", "CONS", "M", "MNOG", "MS", "MOIL", "MSTFE", "MGTFE")
LABOUR = ("EMS", "ETLFS", "ULFS", "LFSUR", "MSGVA", "GGVA", "PSAVEI", "PMSGVA")
MODES = {
    "default": {},
    "import_response": {"import_response": True},
    "employment_response": {"employment_response": True},
    "both": {"import_response": True, "employment_response": True},
}


def _round(values, digits=3):
    return [round(float(x), digits) for x in values]


def _default_pair(var, shock):
    """Baseline and shocked data for the default run, as run_reform builds it."""
    template = ra._build_reform_template(var, START, END, False, None)
    t0, t1 = template.period_idx(START), template.period_idx(END)
    baseline, shocked = template.clone(), template.clone()
    if var == ra.HOUSEHOLD_COSTING_VAR:
        ra._apply_household_costing(shocked, shock, START, 12)
    else:
        ra.apply_spending_shock(shocked, var, shock, START, 12, nominal_consistent=True)
    baseline.solve(START, END)
    shocked.solve(START, END)
    window = slice(t0, t1 + 1)
    return baseline.data.iloc[window], shocked.data.iloc[window]


def _measure(var, shock):
    out = {}
    base, shocked = _default_pair(var, shock)
    out["baseline_levels"] = {name: _round(base[name]) for name in SERIES + LABOUR}
    out["default_series_deltas"] = {
        name: _round(shocked[name].to_numpy(float) - base[name].to_numpy(float))
        for name in SERIES + LABOUR
    }
    ms_partial = overlays.services_imports_partial_response(
        base["MS"], base["MSTFE"], shocked["MSTFE"]
    )
    moil = shocked["MOIL"].to_numpy(float) - base["MOIL"].to_numpy(float)
    out["published_model_goods_residual"] = {
        "note": "partial, no feedback: l.223 on the default run's MSTFE path, "
        "M fixed, MNOG = M - MS - MOIL",
        "delta_ms": _round(ms_partial),
        "delta_moil": _round(moil),
        "delta_mnog": _round(-np.array(ms_partial) - moil),
    }
    for mode, kwargs in MODES.items():
        frame = ra.run_reform(mode, var, shock, start=START, end=END, **kwargs)
        row = {
            "delta_gdp_m": _round(frame["delta_gdp_m"]),
            "delta_cons_m": _round(frame["delta_cons_m"]),
            "solver_converged": bool(frame.attrs.get("solver_converged")),
        }
        if "import_response_detail" in frame.attrs:
            row["delta_imports_m"] = {
                k: _round(v)
                for k, v in frame.attrs["import_response_detail"]["delta_m"].items()
            }
        if "employment_response_detail" in frame.attrs:
            detail = frame.attrs["employment_response_detail"]
            row["delta_etlfs_thousands"] = _round(detail["delta_etlfs_thousands"])
            row["delta_lfsur_pp"] = _round(detail["delta_lfsur_pp"], 4)
        if "gdp_per_revenue_current_price" in frame.attrs:
            row["gdp_per_revenue_current_price"] = _round(
                frame.attrs["gdp_per_revenue_current_price"], 4
            )
        out[mode] = row
    return out


def main():
    warnings.filterwarnings("ignore")
    started = time.time()
    template = ra._build_reform_template("CGG", START, END, False, None)
    t0, t1 = template.period_idx(START), template.period_idx(END)
    cgg_shock = [0.01 * float(x) for x in template.data["GDPM"].iloc[t0 : t1 + 1]]
    periods = [str(p) for p in template.index[t0 : t1 + 1]]

    results = {
        "cgg_1pct_gdp": {"var": "CGG", "shock_m": _round(cgg_shock)},
        "household_tax_1p": {
            "var": ra.HOUSEHOLD_COSTING_VAR,
            "shock_m": [HOUSEHOLD_TAX] * 12,
        },
    }
    results["cgg_1pct_gdp"].update(_measure("CGG", cgg_shock))
    cgg = results["cgg_1pct_gdp"]
    for mode in MODES:
        cgg[mode]["gdp_per_pound"] = _round(
            np.array(cgg[mode]["delta_gdp_m"]) / np.array(cgg_shock), 4
        )
    # Sensitivity: goods elasticity 0. Only the listing's own legs respond
    # (services l.223; oil is offset inside the fixed goods total), which
    # shows how much of the import response rests on the assumed elasticity.
    assumed = overlays.IMPORT_RESPONSE_GOODS_ELASTICITY
    overlays.IMPORT_RESPONSE_GOODS_ELASTICITY = 0.0
    try:
        frame = ra.run_reform(
            "services only",
            "CGG",
            cgg_shock,
            start=START,
            end=END,
            import_response=True,
        )
    finally:
        overlays.IMPORT_RESPONSE_GOODS_ELASTICITY = assumed
    cgg["import_response_goods_elasticity_0"] = {
        "note": "sensitivity, not an option of run_reform: goods imports "
        "including oil held at baseline, services follow l.223",
        "delta_gdp_m": _round(frame["delta_gdp_m"]),
        "solver_converged": bool(frame.attrs.get("solver_converged")),
        "delta_imports_m": {
            k: _round(v)
            for k, v in frame.attrs["import_response_detail"]["delta_m"].items()
        },
        "gdp_per_pound": _round(
            frame["delta_gdp_m"].to_numpy() / np.array(cgg_shock), 4
        ),
    }
    results["household_tax_1p"].update(
        _measure(ra.HOUSEHOLD_COSTING_VAR, HOUSEHOLD_TAX)
    )

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    payload = {
        "source": "scripts/demand_overlays.py",
        "model_commit": commit,
        "machine": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "runtime_s": round(time.time() - started, 1),
        "window": [START, END],
        "periods": periods,
        "units": "GBP m per quarter, chained volume; employment in thousands; "
        "LFSUR in percentage points",
        "goods_elasticity": overlays.IMPORT_RESPONSE_GOODS_ELASTICITY,
        "services_coefficients": overlays.SERVICES_IMPORT_COEFFICIENTS,
        "shocks": results,
    }
    path = Path(__file__).resolve().parents[1] / "results" / "demand_overlays.json"
    path.write_text(json.dumps(payload, indent=1) + "\n")
    print(f"wrote {path} in {payload['runtime_s']}s")


if __name__ == "__main__":
    main()
