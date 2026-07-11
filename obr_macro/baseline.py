"""Stage 2 — forward baseline forecast.

Solves the model forward over the projection horizon to produce one coherent
baseline path for every variable. The published aggregates are anchored to the
OBR's EFO forecast via add-factor residuals (the device the OBR itself uses to
impose judgement); the ~150 intermediate variables the EFO does not publish are
filled by solving the model. This baseline is the foundation that scenario
shocks perturb.

Two modes:
  - anchored=True  : residuals on -> the published variables reproduce the OBR
                     baseline; this is the usable forecast foundation.
  - anchored=False : residuals off -> the raw model generates its own path; the
                     gap vs the OBR baseline is the honest measure of how much of
                     the forecast is the model versus the OBR's judgement.

    uv run python -m obr_macro.baseline
"""

from __future__ import annotations


from obr_macro.full_solver import FullOBRSolver
from obr_macro.reform_analysis import GDPM_EQ
from obr_macro.data import load_obr_data

START, END = "2025Q1", "2031Q1"
CHECK = [
    ("GDPM", "Real GDP", "£m"),
    ("CONS", "Consumption", "£m"),
    ("ETLFS", "Employment", "000s"),
    ("LFSUR", "Unemployment rate", "%"),
    ("CPIGR", "CPI inflation", "%q"),
]


def build(anchored=True):
    s = FullOBRSolver(verbose=False)
    s.swap_closure("DINV", GDPM_EQ)
    s._shock_active = not anchored
    return s


def main():
    efo = load_obr_data()

    s = build(anchored=True)
    t0, t1 = s.period_idx(START), s.period_idx(END)

    # anchored baseline (residuals on -> reproduces the published OBR forecast)
    s.solve(START, END)
    anchored = s.data.copy()

    # raw model path (residuals off -> the model's own forward solve).
    # Built as a FRESH solver, not by re-solving `s`: reusing the anchored
    # solver would start Gauss-Seidel from the anchored (≈EFO) values, and a
    # stall-break exit then leaves values near that seed — biasing the reported
    # "raw vs OBR" gap toward zero.
    s_raw = build(anchored=False)
    s_raw.solve(START, END)
    raw = s_raw.data.copy()

    print(f"Forward baseline {START}..{END}\n")
    print(
        f"{'Variable':22}{'OBR (EFO)':>14}{'Anchored':>14}{'Raw model':>14}   at {END}"
    )
    for code, label, unit in CHECK:
        if code not in efo.columns:
            continue
        e = efo.iloc[t1][code]
        a = anchored.iloc[t1][code] if code in anchored.columns else float("nan")
        r = raw.iloc[t1][code] if code in raw.columns else float("nan")
        print(f"{label:22}{e:14,.1f}{a:14,.1f}{r:14,.1f}   ({unit})")

    # coherence + coverage over the horizon
    hor = anchored.iloc[t0 : t1 + 1]
    finite_full = int(hor.notna().all().sum())
    finite_any = int(hor.notna().any().sum())
    print(
        f"\nCoverage over horizon: {finite_full}/{hor.shape[1]} variables fully finite, "
        f"{finite_any} partially."
    )

    # how closely the anchored baseline reproduces the OBR aggregates
    gdp_e = efo.iloc[t1]["GDPM"]
    gdp_a = anchored.iloc[t1]["GDPM"]
    gdp_r = raw.iloc[t1]["GDPM"]
    print(
        f"\nReal GDP at {END}: anchored reproduces OBR to "
        f"{100 * abs(gdp_a - gdp_e) / gdp_e:.2f}%; raw model is "
        f"{100 * (gdp_r - gdp_e) / gdp_e:+.2f}% vs OBR."
    )


if __name__ == "__main__":
    main()
