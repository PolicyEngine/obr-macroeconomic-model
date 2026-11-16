"""Measure the unguarded zero-shock business-investment path (README,
corporation-tax row; issue #59).

The README says the investment closure is a stop-gap because, without the
stabilisation in ``_stabilise_investment_closure``, a zero-shock solve with the
reconstructed ``dlog(IBUSX)`` equation explodes. This replays that unguarded
solve (closures swapped, no stabilisation, no shock) under both nominal-GDP
closures and prints IBUSX from 2024Q4 to 2027Q4.

    uv run python scripts/unguarded_ibusx.py
"""

import json
import warnings

warnings.filterwarnings("ignore")

S, E = "2025Q1", "2027Q4"


def run(pin):
    import obr_macro.reform_analysis as ra
    from obr_macro.full_solver import FullOBRSolver

    u = FullOBRSolver(verbose=False)
    u.swap_closure("DINV", ra.GDPM_EQ)
    if pin:
        ra.apply_nominal_gdp_pin(u)
    ra._ensure_ibusx_inputs(u)
    for var, eq in (("IBUSX", ra.IBUSX_EQ), ("IBUS", ra.IBUS_EQ), ("IF", ra.IF_EQ)):
        u.swap_closure(var, eq)
    u._shock_active = True
    t0, t1 = u.period_idx(S), u.period_idx(E)
    rec = {"data": [round(float(x)) for x in u.data["IBUSX"].iloc[t0 - 1 : t1 + 1]]}
    try:
        u.solve(S, E)
        rec["solved"] = [round(float(x)) for x in u.data["IBUSX"].iloc[t0 - 1 : t1 + 1]]
        rep = getattr(u, "last_solve_report", {}) or {}
        rec["dropped"] = rep.get("dropped")
    except Exception as e:  # report, don't hide
        rec["error"] = repr(e)[:400]
    return rec


def main():
    import obr_macro.reform_analysis as ra

    out = {"ibusx_expr": ra.IBUSX_EQ.python_expr}
    for pin in (False, True):
        out["pinned" if pin else "published"] = run(pin)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
