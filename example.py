"""Example: run the OBR macro model and inspect key outputs.

This script sets illustrative exogenous inputs (broadly consistent with
recent UK macro data), runs the Gauss-Seidel solver over 2025Q1–2026Q4,
and prints a summary of selected outputs.
"""

import numpy as np
from rich.console import Console
from rich.table import Table

from obr_macro.model import OBRMacroModel

console = Console()

# Start from 1970Q1 so trend base periods (e.g. 1979Q4) are in range
m = OBRMacroModel(start="1970Q1", end="2030Q4")
v = m.v

# ------------------------------------------------------------------
# Exogenous / historical data (illustrative UK-consistent values)
# All monetary variables in £m unless noted.
# ------------------------------------------------------------------

# GDP and output
v["GDPM"][:] = 2_600_000.0       # Real GDP (£m, chained 2019 prices)
v["GDPMPS"][:] = 2_800_000.0     # Nominal GDP (£m)
v["PGDP"][:] = 107.0             # GDP deflator (2019 = 100)
v["GVA"][:] = 2_550_000.0
v["GVAPS"][:] = 2_740_000.0
v["MSGVA"][:] = 2_100_000.0      # Market-sector GVA
v["MSGVAPS"][:] = 2_260_000.0
v["NSGVA"][:] = 50_000.0         # North Sea GVA
v["NNSGVA"][:] = 2_500_000.0     # Non-North-Sea GVA

# Prices
v["CPI"][:] = 130.0              # CPI (2015 = 100)
v["PCE"][:] = 120.0              # Consumption deflator
v["PD"][:] = 115.0               # Domestic demand deflator
v["PPIY"][:] = 115.0             # PPI output
v["PMSGVA"][:] = 110.0
v["PIF"][:] = 115.0              # Investment deflator
v["WPG"][:] = 100.0              # World price of goods
v["PMNOG"][:] = 110.0            # Import price: non-oil goods
v["PMS"][:] = 110.0              # Import price: services
v["PXNOG"][:] = 108.0            # Export price: non-oil goods
v["PXS"][:] = 108.0              # Export price: services

# Wages
v["PSAVEI"][:] = 650.0           # AWE: whole economy (£/week)
v["GPW"][:] = 650.0              # Gross pay per worker
v["APH"][:] = 650.0              # Average pay: whole economy

# Interest rates (%)
v["R"][:] = 5.25                 # Bank Rate
v["RL"][:] = 4.5                 # Long gilt rate
v["RMORT"][:] = 5.8              # Mortgage rate
v["RDEP"][:] = 3.5               # Deposit rate

# Exchange rate
v["RX"][:] = 1.0                 # Sterling effective exchange rate index
v["RXD"][:] = 1.0                # Dollar exchange rate

# Commodity
v["PBRENT"][:] = 80.0            # Brent crude ($/bbl)

# Labour market
v["ETLFS"][:] = 33_000.0         # Employment: LFS basis (thousands)
v["ET"][:] = 33_000.0            # Total employment
v["EGG"][:] = 6_000.0            # Public sector employment
v["ECG"][:] = 2_500.0            # Central government employment
v["ELA"][:] = 1_800.0            # Local authority employment
v["EMS"][:] = 27_000.0           # Market-sector employment
v["LFSUR"][:] = 4.2              # Unemployment rate (%)
v["POP16"][:] = 54_000.0         # Working-age population (thousands)
v["HWA"][:] = 1_030_000.0        # Total hours worked (millions)
v["AVH"][:] = 31.5               # Average hours/week
v["NFWPE"][:] = 5_200_000.0      # Private-sector workforce

# Expenditure components
v["CONS"][:] = 1_650_000.0       # Household consumption (real)
v["CONSPS"][:] = 1_780_000.0
v["CGG"][:] = 420_000.0          # Government consumption (real)
v["CGGPS"][:] = 455_000.0
v["IF"][:] = 400_000.0           # Fixed investment (real)
v["IFPS"][:] = 435_000.0
v["X"][:] = 820_000.0            # Exports (real)
v["XPS"][:] = 885_000.0
v["M"][:] = 780_000.0            # Imports (real)
v["MPS"][:] = 845_000.0

# Income
v["WFP"][:] = 1_100_000.0        # Wages & salaries: private sector
v["RHHDI"][:] = 1_500_000.0      # Real household disposable income
v["FYEMP"][:] = 1_250_000.0      # Employment income: total
v["EMPSC"][:] = 170_000.0        # Employer social contributions
v["MI"][:] = 180_000.0           # Mixed income

# Balance of payments
v["BPAPS"][:] = 400_000.0        # Current account balancing item

# ------------------------------------------------------------------
# Run the model
# ------------------------------------------------------------------
console.print("\n[bold]OBR macro model — forecast run[/bold]")
console.print("Solving 2025Q1 to 2026Q4 (Gauss-Seidel)...\n")

iters = m.run("2025Q1", "2026Q4", verbose=False)

avg_iters = np.mean(list(iters.values()))
console.print(f"Converged. Average iterations per quarter: [cyan]{avg_iters:.1f}[/cyan]\n")

# ------------------------------------------------------------------
# Print summary table
# ------------------------------------------------------------------
quarters = ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q4"]

table = Table(title="Selected macro outputs", show_lines=True)
table.add_column("Variable", style="bold")
table.add_column("Description")
for q in quarters:
    table.add_column(q, justify="right")

rows = [
    ("GDPMPS", "Nominal GDP (£bn)",         1_000),
    ("GDPM",   "Real GDP (£bn, 2019 p.)",   1_000),
    ("PGDP",   "GDP deflator (2019=100)",    1),
    ("CPI",    "CPI (2015=100)",             1),
    ("LFSUR",  "Unemployment rate (%)",      1),
    ("ETLFS",  "Employment (thousands)",     1),
    ("CONS",   "Household consumption (£bn)", 1_000),
    ("X",      "Exports (£bn)",              1_000),
    ("M",      "Imports (£bn)",              1_000),
]

for var, desc, scale in rows:
    vals = []
    for q in quarters:
        t = v.period_to_idx(q)
        val = v[var][t] / scale
        vals.append(f"{val:,.1f}")
    table.add_row(var, desc, *vals)

console.print(table)
