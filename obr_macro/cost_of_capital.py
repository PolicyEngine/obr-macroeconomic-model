"""Derive the cost-of-capital constants DB/DP/DV from published data.

The OBR model computes the tax-adjustment factor TAF from the present value of
capital allowances for three asset classes (model file lines 38-56; the asset
labels below are the OBR's own, from the committed variables workbook
``obr_model_variables_october_2025.xlsx`` rows 20-22):

    DB = PV of depreciation allowances for BUILDINGS
       = [date <= 2011Q2] * (IIB + ...)/(1+DISCO)          (line 38)
    DP = PV of depreciation allowances for PLANT
       = 1/(1+DISCO) * (DISCO*FP + SP)/(DISCO + SP)        (line 40)
    DV = PV of depreciation allowances for VEHICLES
       = SV/(DISCO + SV)                                   (line 42)

The OBR publishes the equations but not their inputs (IIB, SIB, FP, SP, SV,
DISCO are exogenous with "No Codes" and no data). This module supplies those
inputs from sources that ARE published — the statutory capital-allowance rates
set in legislation and the OBR's own market-derived interest-rate assumption —
and evaluates the OBR's published formulas over them. Nothing here is fitted
to make a costing come out anywhere in particular.

Inputs and their provenance
---------------------------
DB: needs NO inputs for the model's solve window. The published equation
    multiplies everything by @recode(@date <= "2011:02", 1, 0), i.e. the OBR's
    own equation pins DB = 0 for every quarter after 2011Q2 (the Industrial
    Buildings Allowance was abolished from April 2011, FA 2008 s.84/FA 2011).
    The solver only initialises/solves 2016Q1 onwards, so the published value
    is identically zero regardless of DISCO/IIB/SIB — the "NaN" that made a
    seed necessary is the float artefact 0 * NaN, not genuine indeterminacy.
    NB the OBR's October-2025 file does NOT model the Structures and Buildings
    Allowance introduced in October 2018 (3% straight line, which would give
    DB ~ 0.45 at these discount rates); this repo follows the published file.

FP (rate of first-year allowances for plant) = 1.0
    Full expensing: a 100% first-year deduction for companies' main-rate plant
    and machinery expenditure, Finance (No. 2) Act 2023 s.7, made permanent by
    Finance Act 2024 s.1. TCPRO shocks are corporation-tax shocks, so the
    company treatment is the relevant margin. Caveat, bounded below.

SP (rate of annual writing down allowance for plant) = 0.18
    Main-pool WDA, 18% reducing balance, CAA 2001 s.56(1) as amended by
    FA 2011 s.10 (in force from April 2012). With FP = 1 the published DP
    formula collapses to 1/(1+DISCO) and SP no longer matters at the margin;
    it is supplied so the formula is evaluated as published.

SV (rate of annual writing down allowance for vehicles) = 0.18
    The model's design assumes a single vehicles WDA rate (the variables
    workbook calls SV "Rate of annual writing down allowance for vehicles").
    The statutory main-rate WDA that applies to business cars with CO2
    emissions up to 50g/km is 18% reducing balance (CAA 2001 s.104AA as
    amended; commercial vehicles are main-pool plant, so 18% is also their
    floor before AIA/full expensing). Two statutory departures pull in
    opposite directions and are not separately weightable from published
    data: higher-emission cars get the 6% special rate (pulls DV down,
    to 0.06/(DISCO+0.06) ~ 0.54) and new zero-emission cars get a 100%
    first-year allowance (pulls DV up, towards 1/(1+DISCO) ~ 0.95).

DISCO (discount factor): mean of the OBR's published "Long-term interest
    rate" market-derived assumption (20-year gilt) over the model's solve
    window, EFO March 2026 economy workbook Table 1.9 — committed in this
    repo at obr_macro/_data/obr_efo_march_2026_economy.xlsx. A nominal
    risk-free rate; a corporate financing spread would push DP/DV modestly
    further from 1 (sensitivity: +200bp moves DP by ~-0.02 and DV by ~-0.03),
    but no published OBR artefact carries a corporate-spread assumption, so
    the OBR's own published rate is used unadorned.

Known bounded caveats (documented, not silently absorbed)
---------------------------------------------------------
- Special-rate plant (integral features, long-life assets) gets a 50%
  first-year allowance plus 6% WDA rather than full expensing: PV ~ 0.77
  instead of ~0.95. The special-rate share of plant expenditure is not
  identifiable from any source this repo vendors; even at a one-fifth share
  the aggregate DP would fall by only ~0.04, so the main-rate statutory value
  is used and the wrinkle is recorded here rather than guessed at.
- The seeds are single constants but the statutory regime is time-varying
  (AIA/super-deduction before April 2023). The investment closure only
  solves 2025Q1 onwards, where full expensing is permanent law, so the
  forecast-window regime is the one the constants must represent.

COCU is NOT derived here — see UNPUBLISHED_COST_OF_CAPITAL_SEEDS in
full_solver.py for why its seed is kept (its level provably cancels in the
corporation-tax deviation, and its published equation needs a 1970Q1 rebasing
anchor that predates every committed series, so no estimate can be shown to
beat the seed on evidence).

Run ``python -m obr_macro.cost_of_capital`` to print the derivation.
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "_data"
EFO_ECONOMY = DATA_DIR / "obr_efo_march_2026_economy.xlsx"

# Statutory capital-allowance rates (provenance in the module docstring).
FP_PLANT_FIRST_YEAR = 1.0  # full expensing, F(No.2)A 2023 s.7 / FA 2024 s.1
SP_PLANT_WDA = 0.18  # main-pool WDA, CAA 2001 s.56(1)
SV_VEHICLES_WDA = 0.18  # main-rate WDA for cars <=50g/km, CAA 2001 s.104AA

# The window over which DISCO is averaged = the window the investment closure
# actually solves (run_reform's published defaults).
SOLVE_WINDOW = ("2025Q1", "2027Q4")


def efo_long_rate_mean(start: str = SOLVE_WINDOW[0], end: str = SOLVE_WINDOW[1]):
    """Mean of the OBR's 'Long-term interest rate' (20-year gilt, per cent)
    over [start, end], from EFO March 2026 economy Table 1.9.

    Located by header text rather than position so a re-download that inserts
    a column fails loudly instead of silently reading the wrong series.
    """
    import re

    raw = pd.read_excel(EFO_ECONOMY, sheet_name="1.9", header=None)
    # Header row and value column: located by the long-rate label text.
    hdr_mask = raw.apply(
        lambda r: r.astype(str).str.contains("Long-term interest rate").any(), axis=1
    )
    if not hdr_mask.any():
        raise ValueError("Table 1.9 no longer has a 'Long-term interest rate' column")
    hdr_row = int(hdr_mask.idxmax())
    col = int(
        raw.iloc[hdr_row].astype(str).str.contains("Long-term interest rate").idxmax()
    )
    # Row labels: the column that carries quarterly labels like "2025Q1"
    # (annual and fiscal-year rows share it and are excluded by the regex).
    q_re = re.compile(r"^\d{4}Q[1-4]$")
    is_q = raw.map(lambda x: bool(q_re.match(str(x).strip())))
    if not is_q.any().any():
        raise ValueError("Table 1.9 has no quarterly row labels")
    label_col = int(is_q.sum().idxmax())
    lo, hi = pd.Period(start, freq="Q"), pd.Period(end, freq="Q")
    vals = []
    for i in range(hdr_row + 1, len(raw)):
        lab = str(raw.iloc[i, label_col]).strip()
        if not q_re.match(lab):
            continue
        if lo <= pd.Period(lab, freq="Q") <= hi:
            vals.append(float(raw.iloc[i, col]))
    expected = (hi - lo).n + 1
    if len(vals) != expected:
        raise ValueError(
            f"expected {expected} quarterly long-rate observations in "
            f"[{start}, {end}], found {len(vals)}"
        )
    return sum(vals) / len(vals) / 100.0  # per cent -> rate


def derive_allowance_pvs() -> dict:
    """Evaluate the OBR's published DB/DP/DV formulas over the sourced inputs.

    Returns {"DB": ..., "DP": ..., "DV": ...} at full float precision; the
    seeds in full_solver round these to 4 decimal places (a <0.01% distortion,
    far inside the discount-rate sensitivity) so the declaration stays
    readable.
    """
    disco = efo_long_rate_mean()
    # DB: the published equation's own date gate pins it to zero for every
    # quarter after 2011Q2, which covers the whole initialise/solve window.
    db = 0.0
    # DP = 1/(1+DISCO) * (DISCO*FP + SP)/(DISCO + SP)   (model file line 40)
    dp = (
        1.0
        / (1.0 + disco)
        * (disco * FP_PLANT_FIRST_YEAR + SP_PLANT_WDA)
        / (disco + SP_PLANT_WDA)
    )
    # DV = SV/(DISCO + SV)                              (model file line 42)
    dv = SV_VEHICLES_WDA / (disco + SV_VEHICLES_WDA)
    return {"DB": db, "DP": dp, "DV": dv, "DISCO": disco}


def main():
    d = derive_allowance_pvs()
    print("Inputs (statute + OBR EFO March 2026 Table 1.9):")
    print(
        f"  DISCO (mean 20y gilt {SOLVE_WINDOW[0]}-{SOLVE_WINDOW[1]}): {d['DISCO']:.6f}"
    )
    print(f"  FP = {FP_PLANT_FIRST_YEAR}  SP = {SP_PLANT_WDA}  SV = {SV_VEHICLES_WDA}")
    print("Present values of capital allowances (OBR published formulas):")
    for k in ("DB", "DP", "DV"):
        print(f"  {k} = {d[k]:.6f}  (seed rounds to {round(d[k], 4)})")


if __name__ == "__main__":
    main()
