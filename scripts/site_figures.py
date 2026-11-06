"""Regenerate the OBR-emulator figures quoted on the PolicyEngine Macro site.

PolicyEngine/macro issue #207 lists figures on ``obr/validation/index.html``
that had no committed output behind them. This script recomputes each one
from committed code and the committed ONS snapshot, and writes them to
``results/site_figures.json`` so the page can cite a file instead of a commit
message.

    uv run python scripts/site_figures.py

Every figure is a full model solve (about a dozen in all), so this is a heavy
job: run it on its own.

What each block measures, and the window it uses:

* ``anchored_horizon`` -- the anchored baseline (``baseline.build``) solved
  over the whole databank, 2025Q1..2031Q1, against the March 2026 EFO. Site
  claim: GDP MAPE 0.67% out to 2031Q1; LFSUR drifts to 0.9% against the EFO's
  4.1% by 2031Q1.
* ``bank_rate`` -- Bank Rate (``R``) +/-1.0 (100bp) sustained for 12 quarters
  from 2025Q1, scored around the anchored reform baseline (``run_reform``'s
  default window). Site claim: GDP -121/-431/-482/-416 GBP m at q1/4/8/12; a
  cut +126 to +579.
* ``corporation_tax_5pp`` -- TCPRO +0.05 for 12 quarters from 2025Q1 under the
  investment closure. Site claim: FYCPR moves by -1,780m and NDIVHH by zero;
  IBUSX -0.24bn at q8, -0.38bn at q12.
* ``cgips_size_sweep`` -- CGIPS +1500/+3000/+6000 GBP m per quarter for 8
  quarters from 2026Q1 (the window ``tests/test_sign_conventions.py`` pins).
  Site claim: IBUSX mean -6.8/-8.8/-11.6bn; IF exactly zero.

Each shock is a baseline/shocked pair cloned from the same cached template,
exactly as ``run_reform`` and the sign-convention tests do, so the deltas
isolate the shock. Solver convergence is recorded with every pair.
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np

from obr_macro.baseline import build
from obr_macro.data import load_obr_data
from obr_macro.reform_analysis import _build_reform_template

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "site_figures.json"

COLS = ("GDPM", "CONS", "IF", "IBUSX", "FYCPR", "NDIVHH", "LFSUR")


def _r(x, nd=3):
    return None if x is None or not np.isfinite(x) else round(float(x), nd)


def anchored_horizon(efo):
    start, end, scored_end = "2025Q1", "2031Q1", "2027Q4"
    s = build(anchored=True)
    s.solve(start, end)
    model, official = s.data.loc[start:end], efo.loc[start:end]

    def mape(code, lo, hi):
        m = model.loc[lo:hi, code].astype(float).values
        o = official.loc[lo:hi, code].astype(float).values
        return 100 * float(np.mean(np.abs(m - o) / np.abs(o)))

    gdp_dev = 100 * (model["GDPM"] / official["GDPM"] - 1)
    report = getattr(s, "last_solve_report", None) or {}
    lfsur = {
        str(p): {
            "model": _r(model.loc[p, "LFSUR"]),
            "efo": _r(official.loc[p, "LFSUR"]),
        }
        for p in ("2027Q4", "2028Q4", "2029Q4", "2030Q4", "2031Q1")
    }
    return {
        "window": [start, end],
        "gdp_mape_pct_2025Q1_2031Q1": _r(mape("GDPM", start, end)),
        "gdp_mape_pct_2025Q1_2027Q4": _r(mape("GDPM", start, scored_end)),
        "cons_mape_pct_2025Q1_2027Q4": _r(mape("CONS", start, scored_end)),
        "cons_mape_pct_2025Q1_2031Q1": _r(mape("CONS", start, end)),
        "gdp_max_abs_dev_pct": _r(gdp_dev.abs().max()),
        "gdp_max_abs_dev_quarter": str(gdp_dev.abs().idxmax()),
        "gdp_dev_pct_2031Q1": _r(gdp_dev.loc["2031Q1"]),
        "lfsur_pct": lfsur,
        "nonconverged_quarters": len(report.get("nonconverged", [])),
    }


def pair(var, shock, start, end, periods, investment_closure):
    """Baseline/shocked pair from one template; per-quarter deltas."""
    template = _build_reform_template(var, start, end, investment_closure)
    base, shocked = template.clone(), template.clone()
    shocked.apply_shock(var, shock, start, periods=periods)
    base.solve(start, end)
    shocked.solve(start, end)
    nonconv = set()
    for sv in (base, shocked):
        rep = getattr(sv, "last_solve_report", None) or {}
        nonconv |= {str(p) for p in rep.get("nonconverged", [])}
    out = {
        "var": var,
        "shock": shock,
        "window": [start, end],
        "shocked_quarters": periods,
        "investment_closure": investment_closure,
        "nonconverged_quarters": sorted(nonconv),
        "deltas_m": {},
    }
    for col in COLS:
        if col not in base.data.columns:
            continue
        d = shocked.data.loc[start:end, col].astype(float) - base.data.loc[
            start:end, col
        ].astype(float)
        out["deltas_m"][col] = {
            "mean": _r(d.mean()),
            "path": [_r(x) for x in d],
            "max_abs": _r(d.abs().max()),
        }
    return out


def at_quarters(path, qs=(1, 4, 8, 12)):
    return {f"q{q}": path[q - 1] for q in qs}


def main():
    t0 = time.time()
    efo = load_obr_data()
    figures = {"anchored_horizon": anchored_horizon(efo)}

    up = pair("R", 1.0, "2025Q1", "2027Q4", 12, False)
    down = pair("R", -1.0, "2025Q1", "2027Q4", 12, False)
    figures["bank_rate"] = {
        "plus_100bp_gdp_m": at_quarters(up["deltas_m"]["GDPM"]["path"]),
        "minus_100bp_gdp_m": at_quarters(down["deltas_m"]["GDPM"]["path"]),
        "minus_100bp_gdp_m_range": [
            min(x for x in down["deltas_m"]["GDPM"]["path"] if x is not None),
            max(x for x in down["deltas_m"]["GDPM"]["path"] if x is not None),
        ],
        "runs": {"plus_100bp": up, "minus_100bp": down},
    }

    ct = pair("TCPRO", 0.05, "2025Q1", "2027Q4", 12, True)
    figures["corporation_tax_5pp"] = {
        "fycpr_mean_m": ct["deltas_m"]["FYCPR"]["mean"],
        "fycpr_q12_m": ct["deltas_m"]["FYCPR"]["path"][-1],
        "ndivhh_max_abs_m": ct["deltas_m"].get("NDIVHH", {}).get("max_abs"),
        "ibusx_m": at_quarters(ct["deltas_m"]["IBUSX"]["path"], (8, 12)),
        "run": ct,
    }

    sweep = {}
    for shock in (1500.0, 3000.0, 6000.0):
        run = pair("CGIPS", shock, "2026Q1", "2027Q4", 8, False)
        sweep[f"{shock:.0f}"] = {
            "ibusx_mean_m": run["deltas_m"]["IBUSX"]["mean"],
            "ibusx_share_of_shock": _r(run["deltas_m"]["IBUSX"]["mean"] / shock),
            "if_mean_m": run["deltas_m"].get("IF", {}).get("mean"),
            "run": run,
        }
    figures["cgips_size_sweep"] = sweep

    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    manifest = json.loads(
        (ROOT / "obr_macro" / "seeds" / "snapshot_manifest.json").read_text()
    )
    payload = {
        "source": "scripts/site_figures.py",
        "model_commit": commit,
        "ons_snapshot": {
            k: manifest.get(k) for k in ("n_series", "pulled", "recovered")
        },
        "machine": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "runtime_s": round(time.time() - t0, 1),
        "units": "GBP m per quarter, model units; LFSUR in percent",
        "figures": figures,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=1) + "\n")
    print(json.dumps({k: v for k, v in payload.items() if k != "figures"}, indent=1))
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
