"""Borrowing and gilt-yield scenarios with and without the debt-interest
overlay. Writes ``results/debt_interest_examples.json``, the source of every
number in ``docs/debt_interest.md``.

    uv run python scripts/debt_interest_examples.py

Six ``run_reform`` calls on one cached template family (about five minutes on
a laptop).
"""

from __future__ import annotations

import json
import platform
import subprocess
import time
import warnings
from pathlib import Path

from obr_macro import run_reform

warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "results" / "debt_interest_examples.json"
START, END = "2025Q1", "2027Q4"
# The gilt-yield scenario starts in 2026Q2, the first quarter of the October
# 2026 EFO's first forecast fiscal year, so its planned issuance comes from
# that EFO's table 6.12 alone. (2025Q1 is in 2024-25, which no committed
# table covers, so a yield shock from 2025Q1 raises.)
GILT_START, GILT_END = "2026Q2", "2028Q4"

# (key, label, var, shock per quarter, start, end, quarters)
SCENARIOS = [
    (
        "cgg",
        "Government consumption +GBP 1.25bn a quarter",
        "CGG",
        1250.0,
        START,
        END,
        12,
    ),
    ("vat", "VAT standard rate +1pp (GBP 8.8bn/yr)", "VREC", 8800 / 4, START, END, 12),
    (
        "gilt_yield",
        "Gilt yield +1 percentage point",
        "RL",
        1.0,
        GILT_START,
        GILT_END,
        11,
    ),
]


def _run(var, shock, start, end, periods, **kwargs):
    t = time.time()
    df = run_reform(
        "example", var, shock, start=start, end=end, periods=periods, **kwargs
    )
    out = {
        "periods": df["period"].tolist(),
        "delta_gdp_m": [round(float(x), 3) for x in df["delta_gdp_m"]],
        "delta_cons_m": [round(float(x), 3) for x in df["delta_cons_m"]],
        "solver_converged": bool(df.attrs.get("solver_converged")),
        "debt_interest": bool(df.attrs["debt_interest"]),
        "runtime_s": round(time.time() - t, 1),
    }
    if "debt_interest_detail" in df.attrs:
        out["debt_interest_detail"] = df.attrs["debt_interest_detail"]
    return out


def main():
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=ROOT
    ).stdout.strip()
    dirty = bool(
        subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            cwd=ROOT,
        ).stdout.strip()
    )
    result = {
        "source": "scripts/debt_interest_examples.py",
        "model_commit": commit,
        "worktree_dirty": dirty,
        "machine": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "units": "GBP m per quarter; yields in per cent a year",
        "scenarios": {},
    }
    for key, label, var, shock, start, end, periods in SCENARIOS:
        result["scenarios"][key] = {
            "label": label,
            "var": var,
            "shock": shock,
            "window": [start, end],
            "off": _run(var, shock, start, end, periods),
            "on": _run(var, shock, start, end, periods, debt_interest=True),
        }
        OUT.write_text(json.dumps(result, indent=1) + "\n")
    OUT.write_text(json.dumps(result, indent=1) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
