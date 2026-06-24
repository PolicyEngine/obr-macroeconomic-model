"""Tune the held-add-factor forecast to push the poor channels under 10%.

Builds the solver once, then sweeps add-factor windows (how many recent quarters
of residuals to average for the held add-factor) and the investment closure,
re-solving a clone per config. Reports the three problem channels (business
investment, trade balance, current account) plus the overall hit rate.

    uv run python -m obr_macro.forecast_tune
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np

from obr_macro.baseline import build
from obr_macro.reform_analysis import IBUS_EQ, IBUSX_EQ, IF_EQ, _ensure_ibusx_inputs
from obr_macro.data import load_obr_data
from obr_macro.forecast import PANEL, band, BASE_END, FC_START, FC_END

WINDOWS = [("mean 8q", 8), ("mean 4q", 4), ("mean 2q", 2), ("last 1q", 1)]
WATCH = {"IBUS": "Business investment", "TB": "Trade balance", "CB": "Current account"}


def held_addfactors(residuals, period_idx, base_end, window):
    bt1 = period_idx(base_end)
    bt0 = bt1 - window + 1
    acc = defaultdict(list)
    for (var, t), r in residuals.items():
        if bt0 <= t <= bt1 and np.isfinite(r):
            acc[var].append(r)
    return {var: float(np.mean(rs)) for var, rs in acc.items() if rs}


def score(sh, efo, t0, t1):
    has_eq = {sh._extract_lhs_var(eq.lhs) for eq in sh.equations}
    skipped = {d["var"] for d in sh.diagnose_period(t1)}
    rows, counts, computed = {}, {"OK": 0, "~": 0, "!": 0, "X": 0}, 0
    for code, label, kind in PANEL:
        if code not in efo.columns or code not in sh.data.columns:
            continue
        errs = []
        for t in range(t0, t1 + 1):
            m, e = sh.data.iloc[t][code], efo.iloc[t][code]
            if np.isfinite(m) and np.isfinite(e):
                errs.append(abs(m - e) if kind == "pp" else (100 * abs(m - e) / abs(e) if abs(e) > 1e-9 else None))
        errs = [x for x in errs if x is not None]
        err = float(np.mean(errs)) if errs else None
        if code in has_eq and code not in skipped:
            counts[band(kind, err)] += 1
            computed += 1
        rows[code] = (err, kind)
    good = counts["OK"] + counts["~"]
    return rows, computed, good


def run(base, base_residuals, efo, window, investment_closure):
    sh = base.clone()
    sh.residuals = dict(base_residuals)
    if investment_closure:
        _ensure_ibusx_inputs(sh)
        sh.swap_closure("IBUSX", IBUSX_EQ)
        sh.swap_closure("IBUS", IBUS_EQ)
        sh.swap_closure("IF_PLACEHOLDER", IF_EQ)
    held = held_addfactors(sh.residuals, sh.period_idx, BASE_END, window)
    ft0, ft1 = sh.period_idx(FC_START), sh.period_idx(FC_END)
    for var, af in held.items():
        for t in range(ft0, ft1 + 1):
            sh.residuals[(var, t)] = af
    sh._shock_active = False
    sh.solve(FC_START, FC_END)
    return score(sh, efo, ft0, ft1)


def main():
    efo = load_obr_data()
    base = build(anchored=True)
    base_residuals = dict(base.residuals)

    def fmt(rows, code):
        err, kind = rows.get(code, (None, "lvl"))
        if err is None:
            return "   —"
        return f"{err:6.2f}pp" if kind == "pp" else f"{err:6.2f}%"

    print(f"Tuning held-add-factor forecast ({FC_START}..{FC_END})\n")
    print(f"{'config':28}{'Bus.inv':>10}{'TradeBal':>10}{'CurrAcc':>10}{'within10%':>12}")
    for label, window in WINDOWS:
        for ic in (False, True):
            rows, computed, good = run(base, base_residuals, efo, window, ic)
            cfg = f"{label}{' +inv-closure' if ic else ''}"
            print(f"{cfg:28}{fmt(rows,'IBUS'):>10}{fmt(rows,'TB'):>10}{fmt(rows,'CB'):>10}"
                  f"{f'{good}/{computed}':>12}")


if __name__ == "__main__":
    main()
