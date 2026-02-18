"""Example: run the slim OBR macro model calibrated to OBR November 2025 EFO.

Loads actual OBR forecast data for prices, interest rates, exchange rates,
national accounts, and labour market variables. Remaining variables use
illustrative defaults. Runs the Gauss-Seidel solver over 2025Q1-2026Q4.
"""

import sys
from pathlib import Path

import numpy as np
from rich.console import Console
from rich.table import Table

from obr_macro.model import OBRMacroModel
from obr_macro.calibration import load_obr_efo, calibrate_all

console = Console()

# ------------------------------------------------------------------
# Check for OBR data file
# ------------------------------------------------------------------
OBR_FILE = Path(__file__).parent / "data" / "obr_efo_november_2025_economy.xlsx"
if not OBR_FILE.exists():
    # Also check /tmp for development
    OBR_FILE = Path("/tmp/obr_economy_tables.xlsx")
if not OBR_FILE.exists():
    console.print("[red]OBR economy tables not found. Download from:[/red]")
    console.print("  https://obr.uk/download/november-2025-economic-and-fiscal-outlook-detailed-forecast-tables-economy/")
    console.print(f"  Place at: {Path(__file__).parent / 'data' / 'obr_efo_november_2025_economy.xlsx'}")
    sys.exit(1)

# ------------------------------------------------------------------
# Initialise model and load OBR data
# ------------------------------------------------------------------
m = OBRMacroModel(start="1970Q1", end="2031Q4")
v = m.v

console.print("\n[bold]OBR macro model — calibrated to November 2025 EFO[/bold]")
console.print(f"Loading OBR data from {OBR_FILE.name}...")

obr_data = load_obr_efo(OBR_FILE)
calibrate_all(v, obr_data)


def s(name: str, value: float) -> None:
    """Set a variable to a constant across all periods."""
    v[name][:] = value


# ------------------------------------------------------------------
# Variables NOT covered by OBR tables — keep as illustrative defaults
# ------------------------------------------------------------------

# PPI output (not in OBR economy tables — approximate)
s("PPIY", 118.0)

# World price of goods
s("WPG", 105.0)

# Housing investment deflator
s("PIH", 130.0)

# RPI components / weights
s("I4", 100.0)
s("I7", 100.0)
s("I9", 100.0)
s("PRXMIP", 100.0)
s("W1", 0.06)
s("W4", 0.03)
s("W5", 0.17)

# Discount / cost of capital
s("ROCB", 5.50)
s("DISCO", 0.08)

# Government employment and demographics
s("EGG", 5_500)
s("GAD1", 12_000)
s("GAD2", 35_000)
s("GAD3", 12_500)
s("POPAL", 68_000)
s("HRRPW", 0.28)

# Income variables not in OBR tables
s("ADJW", 1.0)
s("CORP", 90_000)
s("NDIV", 5.0)
s("FSMADJ", 0)
s("APIIH", 5_000)
s("DIRHH", 8_000)
s("DIPHHuf", 500)
s("NIPD", -5_000)

# Employment composition
s("ERCG", 1.0)
s("ERLA", 1.0)
s("CGWADJ", 600)
s("LAWADJ", 500)

# Government spending
s("CGGPSPSF", 130_000)
s("CGIPS", 15_000)
s("LAIPS", 8_000)
s("LAPR", 5_000)
s("RCGIM", 4_000)
s("RLAIM", 2_000)
s("CGSB", 55_000)
s("LASBHH", 12_000)
s("CGOTR", 3_000)
s("CGSUBP", 2_000)
s("CGSUBPR", 1_500)
s("TROD", 500)
s("CGNDIV", 1_200)
s("LANDIV", 200)
s("PCNDIV", 300)
s("HHTCG", 800)
s("RNCG", 1_500)
s("CGKTA", 500)
s("OPSKTA", 200)
s("NPACG", 100)
s("NPALA", 50)

# Local authority
s("LASUBP", 800)
s("LAPT", 2_000)
s("LARENT", 1_500)
s("LAOTRHH", 1_000)
s("LAVAT", 500)
s("LAEPS", 300)

# Tax receipts
s("TYEM", 55_000)
s("TSEOP", 8_000)
s("TCINV", 3_500)
s("EENIC", 38_000)
s("EMPNIC", 22_000)
s("VREC", 42_000)
s("TXFUEL", 6_500)
s("TXTOB", 2_500)
s("TXALC", 3_200)
s("TXCUS", 800)
s("TXMIS", 1_500)
s("CUST", 1_200)
s("CCL", 500)
s("AL", 200)
s("TSD", 4_500)
s("CGT", 4_000)
s("INHT", 2_000)
s("CC", 11_000)
s("PRT", 0)
s("NNSCTP", 20_000)
s("NSCTP", 500)
s("NNDRA", 8_000)
s("TCPRO", 0.25)
s("INCTAC", 500)
s("EXDUTAC", 300)
s("XLAVAT", 200)
s("FCACA", 100)
s("CCLACA", 50)
s("BETPRF", 400)
s("BETLEVY", 100)
s("OFGEM", 200)
s("NPISHTC", 300)
s("TYPCO", 200)
s("PROV", 100)
s("OHT", 500)
s("OPT", 1_000)
s("VEDCO", 800)
s("VEDHH", 1_800)
s("BBC", 1_000)
s("PASSPORT", 200)
s("RFP", 300)
s("ROCS", 400)
s("CIL", 500)
s("ENVLEVY", 200)
s("BANKROLL", 300)
s("RULC", 100)
s("BLEVY", 600)
s("SWISSCAP", 50)
s("EUETS", 200)
s("EUOT", 100)
s("EUSUBP", 500)
s("EUSUBPR", 300)
s("EUVAT", 100)
s("EUSF", 200)
s("EUKT", 100)
s("NIS", 0)

# Capital allowances / investment parameters
s("IIB", 0.0)
s("SIB", 0.25)
s("FP", 0.50)
s("SP", 0.06)
s("SV", 0.04)
s("DEBTW", 0.35)
s("TPBRZ", 0.0)
s("PEHC", 50)

# Housing and investment volumes
s("IPRL", 5_000)
s("IPRLPS", 5_800)
s("PCLEB", 2_000)
s("LHP", 1_600_000)
s("HH", 28_500)
s("STUDENT", 180_000)

# National accounts not in OBR
s("DINV", 2_000)
s("DINVPS", 2_200)
s("DINVCG", 500)
s("DINVHH", 400)
s("VAL", 5_000)
s("SDE", 500)
s("INV", 2_000)
s("BV", 2_200)
s("NSGVA", 3_000)
s("SA", 1_000)

# Financial sector / balance sheet
s("M4IC", 500_000)
s("RIC", 5.0)
s("OSPC", 3_000)
s("PCRENT", 500)
s("EQPR", 100)
s("WEQPR", 100)
s("SIPT", 0.01)
s("FISIMROW", 1_000)
s("IBPC", 2_000)

# Transfer / benefit parameters
s("CTC", 1_500)
s("MILAPM", 200)
s("BENAB", 500)
s("SBHH_A", 0)
s("TYWHH_A", 0)
s("EESC_A", 0)
s("PRMIP_A", 0)
s("MGDPNSA_A", 0)
s("DEPHHADJ", 0)
s("NAEQHHADJ", 0)
s("NAINSADJ", 0)
s("NAOLPEADJ", 0)

# Balance of payments / capital
s("NPAA", 500)
s("NPAHH", 200)
s("HHTA", 300)
s("HHTFA", 400)
s("CB", 2_000)
s("PSNBCY", 15_000)
s("NAFROW", -5_000)
s("KGLA", 500)
s("KLA", 300)
s("KCGPSO", 200)
s("SRES", 0)
s("DRES", 0)
s("ALROW", 5_000)
s("OAHHADJ", 0)
s("EECOMPC", 1_000)
s("EECOMPD", 500)
s("NNSGTP", 50_000)
s("NSGTP", 1_500)

# ------------------------------------------------------------------
# Initial values for endogenous variables (needed for lagged terms)
# ------------------------------------------------------------------
s("GVA", 540_000)
s("GVAPS", 590_000)
s("MSGVA", 440_000)
s("MSGVAPS", 490_000)
s("NNSGVA", 537_000)
s("GGVA", 100_000)
s("GGVAPS", 132_000)
s("BPA", 80_000)
s("SDI", 500)
s("SDEPS", 590)
s("RENTCO", 15_000)
s("MGDPNSA", 665_000)
s("OS", 200_000)

# Price intermediates
s("PD", 310)
s("PIF", 125.0)
s("PMSGVA", 111.0)
s("PMNOG", 110.0)
s("PMS", 110.0)
s("PXNOG", 108.0)
s("PXS", 108.0)
s("PGVA", 109.0)
s("PCDUR", 95.0)
s("PIBUS", 125.0)

# AWE (£/week) — derive from OBR AWE index if available
# OBR AWE index base = 2008Q1=100; 2008Q1 AWE ≈ £420/week
if "AWE_IDX" in obr_data and obr_data["AWE_IDX"]:
    awe_base = 420.0  # £/week in 2008Q1
    for period, idx_val in obr_data["AWE_IDX"].items():
        try:
            t = v.period_to_idx(period)
            v["PSAVEI"][t] = awe_base * idx_val / 100.0
        except (KeyError, IndexError):
            continue
    # Backfill/forward-fill
    sorted_p = sorted(obr_data["AWE_IDX"].keys())
    first_val = awe_base * obr_data["AWE_IDX"][sorted_p[0]] / 100.0
    last_val = awe_base * obr_data["AWE_IDX"][sorted_p[-1]] / 100.0
    try:
        t_first = v.period_to_idx(sorted_p[0])
        v["PSAVEI"][:t_first] = first_val
    except (KeyError, IndexError):
        pass
    try:
        t_last = v.period_to_idx(sorted_p[-1])
        v["PSAVEI"][t_last + 1:] = last_val
    except (KeyError, IndexError):
        pass
else:
    s("PSAVEI", 650)

# Cost indices
s("SCOST", 100.0)
s("CCOST", 100.0)
s("UTCOST", 100.0)
s("RPCOST", 100.0)

# Labour market intermediates
s("ECG", 2_500)
s("ELA", 1_800)
s("ES", 4_200)
s("ESLFS", 4_100)
s("POP16", 54_000)
s("WRGTP", 1_000)
s("HD", 310)

# Income intermediates
s("FISIMPS", 20_000)
s("WYQC", 5_000)
s("RHHDI", 390_000)

# Consumption
s("CDUR", 55_000)
s("NFWPE", 4_500_000)
s("GPW", 290)

# Investment intermediates
s("IBUSX", 60_000)
s("KMSXH", 3_500)
s("KSTAR", 3_600_000)
s("GGIDEF", 120.0)
s("HIMPROV", 12_000)
s("PCIH", 15_000)
s("IHPS", 23_400)
s("IHHPS", 30_000)
s("HSALL", 29_000)
s("CDEBT", 5.0)
s("VALPS", 6_250)
s("VALHH", 1_563)
s("ICCPS", 65_000)
s("IPCPS", 8_000)
s("IFCPS", 12_000)

# Government wages
s("CGWS", 19_500)
s("LAWS", 11_700)
s("CGP", 90_000)
s("CGC", 4_000)
s("CGASC", 2_000)
s("CGISC", 1_500)
s("EESCCG", 3_000)
s("EESCLA", 2_000)
s("LASC", 1_800)
s("LASUBPR", 1_000)

# Social contributions / benefits
s("HHISC", 5_000)
s("EMPISC", 6_500)
s("EMPISCPP", 3_000)
s("EMPCPP", 8_000)
s("OSB", 15_000)
s("HHSB", 10_000)

# Household balance sheet
s("DEPHH", 2_100_000)
s("DEPHHx", 2_100_000)
s("EQHH", 1_200_000)
s("PIHH", 3_800_000)
s("OAHH", 300_000)
s("OAHHx", 300_000)
s("GFWPE", 7_400_000)
s("OLPE", 250_000)
s("OLPEx", 70_000)
s("DEBTU", 0.02)
s("NAFHH", 5_000)
s("NAFHHNSA", 5_000)
s("DBR", 0.55)
s("NAINSx", 2_000)
s("MKR", 100.0)
s("GMF", 0.04)
s("STLIC", 200_000)
s("BLIC", 100_000)
s("FXLIC", 50_000)
s("EQLIC", 500_000)
s("OLIC", 30_000)
s("LIC", 880_000)
s("AIC", 600_000)
s("NWIC", -280_000)
s("NIIP", -500_000)

# Wage/price intermediates
s("ULCMS", 100.0)
s("OILBASE", 80.0)
s("EARN", 750)

# Rest of world balance sheet
s("DAROW", 800_000)
s("EQAROW", 300_000)
s("BAROW", 400_000)
s("OTAROW", 200_000)
s("AROW", 1_700_000)
s("DLROW", 600_000)
s("EQLROW", 400_000)
s("BLROW", 300_000)
s("OTLROW", 200_000)
s("LROW", 1_500_000)
s("NAFROWNSA", -5_000)
s("NAEQAROW", 2_000)
s("NAOTLROW", 1_000)

# Memo items
s("TFEPS", 750_000)
s("TFE", 650_000)

# Dividend / profit intermediates
s("NDIVHH", 12_000)
s("IROO", 25_000)
s("OSHH", 30_000)
s("OSGG", 6_100)
s("OSCO", 160_000)
s("GTPFC", 50_000)
s("FC", 70_000)
s("SAVCO", 50_000)

# Income account intermediates
s("SVHH", 5_000)
s("SY", 1.3)
s("NEAHH", 3_000)
s("KGHH", -1_000)
s("NAFCO", 10_000)
s("NAFFC", 5_000)
s("NAFIC", 5_000)
s("TYWHH", 75_000)
s("NMTRHH", 2_000)
s("SBHH", 80_000)
s("PIRHH", 30_000)
s("PIPHH", 8_000)
s("EECPP", 4_000)
s("EESC", 65_000)

# Investment intermediates
s("RWACC", 8.0)
s("COC", 6.0)
s("TAF", 1.05)
s("PKMSXHB", 125.0)
s("TQ", 0.8)
s("GGIPS", 23_000)

# Wage/price intermediates
s("MSGVAPSEMP", 445_000)
s("FYEMPMS", 220_000)
s("RPW", 6_000)
s("RCW", 2_400)
s("MKGW", 100.0)
s("RHF", 5.0)
s("PINV", 110.0)

# GDP per capita
s("GDPMAL", 8.2)
s("TRGDPAL", 8.2)
s("GDPM16", 10.4)
s("TRGDP16", 10.4)
s("GAP", 0.0)

# Other
s("TPRODPS", 12_000)
s("ULFS", 1_400)
s("EPS", 24_700)
s("WFJ", 34_000)
s("PRODH", 0.55)
s("GAD", 59_500)
s("CETAX", 97_000)
s("VED", 2_600)
s("OCT", 3_500)
s("TAXCRED", 1_700)
s("INCTAXG", 67_000)
s("PUBSTIW", 130_000)
s("PUBSTPD", 115_000)
s("PSCR", 270_000)
s("NATAXES", 245_000)
s("PSINTR", 1_700)
s("CGRENT", 2_300)
s("CGTSUB", 3_500)
s("LATSUB", 1_800)
s("GGFCD", 124.0)
s("CGNCGA", 500)
s("EMPASC", 35_500)
s("DIPHHmf", 15_000)
s("DIPHH", 20_000)
s("DIPHHx", 35_500)
s("DIRHHf", -5_000)
s("DIRHHx", 13_000)
s("DIRICf", 10_000)
s("DIRIC", 25_000)
s("DIRICx", 15_000)
s("DIPICf", 8_000)
s("DIPIC", 18_000)
s("DIPICx", 26_000)
s("NETAD", 0.076)
s("PIPRL", 116.0)

# ------------------------------------------------------------------
# Re-apply OBR calibration on top of defaults (calibration takes
# priority over the constant defaults above for overlapping vars)
# ------------------------------------------------------------------
calibrate_all(v, obr_data)

# ------------------------------------------------------------------
# Bootstrap: find internally-consistent endogenous values
# ------------------------------------------------------------------
console.print("Bootstrapping...")

from obr_macro.equations import EQUATION_GROUPS

# Snapshot all values before bootstrap (including OBR time-varying data)
exog_snapshot = {}
for name in v._data:
    exog_snapshot[name] = v[name].copy()

# Phase 1: single-pass bootstrap at a mid-sample point to get finite values
t_boot = v.period_to_idx("2020Q1")
for _ in range(50):
    for group in EQUATION_GROUPS:
        group(v, t_boot)
    # Broadcast any finite values found
    for name in list(v._data.keys()):
        val = v[name][t_boot]
        if np.isfinite(val):
            v[name][:] = val

# Restore exogenous values after phase 1 (bootstrap overwrites them)
for name, arr in exog_snapshot.items():
    v[name][:] = arr

# Phase 2: run warm-up with full G-S over the historical OBR data range
m.run("2010Q1", "2024Q4", verbose=False)

# Broadcast final warm-up values to all periods as initial conditions
t_final = v.period_to_idx("2024Q4")
for name in list(v._data.keys()):
    val = v[name][t_final]
    if np.isfinite(val):
        v[name][:] = val

# Restore exogenous values again (broadcast overwrites them)
for name, arr in exog_snapshot.items():
    v[name][:] = arr

nan_count = sum(1 for n in v._data if np.isnan(v[n][v.period_to_idx("2024Q4")]))
console.print(f"Bootstrap done. NaN vars: [cyan]{nan_count}[/cyan]")

# ------------------------------------------------------------------
# Solve forecast
# ------------------------------------------------------------------
console.print("Solving 2025Q1 to 2030Q4...\n")
iters = m.run("2025Q1", "2030Q4", verbose=True)

avg_iters = np.mean(list(iters.values()))
console.print(f"\nAverage iterations per quarter: [cyan]{avg_iters:.1f}[/cyan]\n")

# ------------------------------------------------------------------
# Re-apply OBR calibration after solve: pin OBR-provided variables
# to their target values (solver may have overwritten endogenous ones)
# ------------------------------------------------------------------
calibrate_all(v, obr_data)

# ------------------------------------------------------------------
# Check for NaNs
# ------------------------------------------------------------------
t_check = v.period_to_idx("2026Q4")
nan_vars = [name for name in sorted(v._data.keys()) if np.isnan(v[name][t_check])]
if nan_vars:
    console.print(f"[red]Warning: {len(nan_vars)} NaN variables at 2026Q4:[/red]")
    for n in nan_vars[:20]:
        console.print(f"  {n}")
    if len(nan_vars) > 20:
        console.print(f"  ... and {len(nan_vars) - 20} more")
else:
    console.print("[green]All variables solved — no NaNs.[/green]\n")

# ------------------------------------------------------------------
# Print summary table
# ------------------------------------------------------------------
quarters = ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q4", "2028Q4", "2030Q4"]

table = Table(title="Selected macro outputs (OBR-calibrated)", show_lines=True)
table.add_column("Variable", style="bold")
table.add_column("Description")
for q in quarters:
    table.add_column(q, justify="right")

rows = [
    ("GDPMPS", "Nominal GDP (£bn)",         1_000),
    ("GDPM",   "Real GDP (£bn, const. p.)", 1_000),
    ("PGDP",   "GDP deflator",              1),
    ("CPI",    "CPI (2015=100)",            1),
    ("CPIH",   "CPIH (2015=100)",           1),
    ("RPI",    "RPI inflation (%)",         1),
    ("R",      "Bank Rate (%)",             1),
    ("RMORT",  "Mortgage rate (%)",         1),
    ("LFSUR",  "Unemployment rate (%)",     1),
    ("ETLFS",  "Employment (thousands)",    1),
    ("PSAVEI", "AWE (£/week)",             1),
    ("CONS",   "HH consumption (£bn)",     1_000),
    ("CONSPS", "HH consumption nom. (£bn)", 1_000),
    ("HHDI",   "HH disp. income (£bn)",    1_000),
    ("RHHDI",  "Real HH disp. income (£bn)", 1_000),
    ("SVHH",   "HH saving (£m)",           1),
    ("SY",     "Saving ratio (%)",          1),
    ("NFWPE",  "HH net fin. wealth (£bn)", 1_000),
    ("PBRENT", "Oil price ($/bbl)",         1),
]

for var, desc, scale in rows:
    vals = []
    for q in quarters:
        t_q = v.period_to_idx(q)
        val = v[var][t_q] / scale
        if abs(val) >= 100:
            vals.append(f"{val:,.0f}")
        else:
            vals.append(f"{val:,.2f}")
    table.add_row(var, desc, *vals)

console.print(table)
