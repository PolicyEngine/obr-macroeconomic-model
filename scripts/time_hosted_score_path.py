"""Time the OBR half of the hosted ``score_reform`` call (macro #243).

The hosted ``score_reform(model="obr")`` costs a reform with the
PolicyEngine-UK microsimulation for each of five fiscal years, then calls
``run_reform(var="HHDI_ADDFACTOR", shock=<20-quarter path>,
start="2026Q2", end="2031Q1", investment_closure=False)``. This script
replays that call with the quarterly path the hosted server produced for a
1p basic-rate rise on 13 Nov 2026 (job fc-01M79WBAVFWAF8K05Q36X236G5), cold
(template build included) and warm, and reports convergence.

    uv run python scripts/time_hosted_score_path.py
"""

import json
import time
import warnings

warnings.filterwarnings("ignore")

PATH = [1636.5] * 4 + [1696.5] * 4 + [1751.5] * 4 + [1807.5] * 4 + [1870.0] * 4


def main():
    from obr_macro import run_reform

    out = {}
    for label in ("cold", "warm"):
        t = time.time()
        df = run_reform(
            name="hosted score path",
            var="HHDI_ADDFACTOR",
            shock=PATH,
            start="2026Q2",
            end="2031Q1",
            investment_closure=False,
        )
        out[label] = {
            "seconds": round(time.time() - t, 1),
            "converged": df.attrs.get("solver_converged"),
            "nonconverged_quarters": len(
                df.attrs.get("solver_nonconverged_periods", []) or []
            ),
            "delta_gdp_m": [round(float(x), 1) for x in df["delta_gdp_m"]],
        }
        print(label, out[label]["seconds"], "s", out[label]["converged"], flush=True)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
