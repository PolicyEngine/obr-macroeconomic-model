"""One-off: dashboard figures on the October 2026 EFO, default nominal-GDP pin (scratch, not for merge)."""
import json, time, warnings
import numpy as np
from obr_macro.reform_analysis import run_reform, _build_reform_template

warnings.simplefilter("always")
S, E = "2025Q1", "2027Q4"
out = {}

def r(x, n=4):
    return None if x is None or (isinstance(x, float) and not np.isfinite(x)) else round(float(x), n)

# 1. CGIPS under the pin, 12 quarters, three sizes; deltas from a rebuilt pair.
for size in (1500.0, 3000.0, 6000.0):
    t = time.time()
    with warnings.catch_warnings(record=True) as w:
        df = run_reform(name="cgips", var="CGIPS", shock=size, periods=12)
    tpl = _build_reform_template("CGIPS", S, E, False)
    b, k = tpl.clone(), tpl.clone()
    k.apply_shock("CGIPS", size, S, periods=12)
    b.solve(S, E); k.solve(S, E)
    rep = {n: (getattr(s, "last_solve_report", None) or {}).get("exit_status", {}) for n, s in (("baseline", b), ("shocked", k))}
    d = {c: [r(x, 3) for x in (k.data.loc[S:E, c].astype(float) - b.data.loc[S:E, c].astype(float))] for c in ("GDPM", "IBUSX", "IF", "CONS", "GGI", "LFSUR") if c in b.data.columns}
    out[f"cgips_{int(size)}"] = {
        "run_reform_delta_gdp_m": [r(x, 3) for x in df["delta_gdp_m"]],
        "solver_converged": df.attrs.get("solver_converged"),
        "solver_nonconverged_periods": list(df.attrs.get("solver_nonconverged_periods", [])),
        "pair_exit_status_counts": {n: {s: list(v.values()).count(s) for s in set(v.values())} for n, v in rep.items()},
        "pair_deltas_m": d,
        "warnings": sorted({str(x.message)[:300] for x in w}),
        "runtime_s": round(time.time() - t, 1),
    }
    print(json.dumps(out[f"cgips_{int(size)}"])[:600], flush=True)

# 3. Income tax worked example at GBP 6.55bn/yr = 1,637.5/qtr (and the old 1,615.75).
for var in ("HHDI_ADDFACTOR", "TYEM"):
    for rev in (1637.5, 1615.75):
        df = run_reform(name="hh", var=var, shock=rev, periods=12)
        a = df.attrs
        cp, re_ = a.get("gdp_per_revenue_current_price"), a.get("gdp_per_revenue_real")
        rec = {
            "delta_gdp_m": [r(x, 3) for x in df["delta_gdp_m"]],
            "current_price_ratio": [r(x) for x in cp] if cp else None,
            "real_ratio": [r(x) for x in re_] if re_ else None,
            "solver_converged": a.get("solver_converged"),
        }
        if cp:
            rec["current_price_q1_q4_q12"] = [r(cp[0]), r(cp[3]), r(cp[11])]
            rec["current_price_year1_mean"] = r(np.mean(cp[:4]))
            rec["real_q4_q12"] = [r(re_[3]), r(re_[11])]
        out[f"{var}_{rev}"] = rec
        print(var, rev, json.dumps({k: v for k, v in rec.items() if "q" in k or "mean" in k or "conv" in k}), flush=True)

# 4. Anchored horizon to the end of the October databank (2032Q1).
from obr_macro.baseline import build
from obr_macro.data import load_obr_data
efo = load_obr_data()
s = build(anchored=True)
s.solve("2025Q1", "2032Q1")
m = s.data.loc["2025Q1":"2032Q1"]
rep = getattr(s, "last_solve_report", None) or {}
out["anchored_to_2032Q1"] = {
    "lfsur": {p: {"model": r(m.loc[p, "LFSUR"]), "efo": r(efo.loc[p, "LFSUR"])} for p in ("2027Q4", "2029Q4", "2031Q1", "2031Q4", "2032Q1")},
    "gdp_mape_2025Q1_2032Q1": r(100 * float(np.mean(np.abs(m["GDPM"].astype(float) / efo.loc["2025Q1":"2032Q1", "GDPM"] - 1)))),
    "nonconverged_quarters": len(rep.get("nonconverged", [])),
}
print(json.dumps(out["anchored_to_2032Q1"]), flush=True)
json.dump(out, open("dashboard_numbers_oct26.json", "w"), indent=1)
