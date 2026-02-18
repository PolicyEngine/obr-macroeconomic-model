from obr_macro.equations.consumption import solve_t as consumption
from obr_macro.equations.inventories import solve_t as inventories
from obr_macro.equations.investment import solve_t as investment
from obr_macro.equations.labour_market import solve_t as labour_market
from obr_macro.equations.exports import solve_t as exports
from obr_macro.equations.imports import solve_t as imports
from obr_macro.equations.prices_wages import solve_t as prices_wages
from obr_macro.equations.north_sea_oil import solve_t as north_sea_oil
from obr_macro.equations.public_expenditure import solve_t as public_expenditure
from obr_macro.equations.public_receipts import solve_t as public_receipts
from obr_macro.equations.balance_of_payments import solve_t as balance_of_payments
from obr_macro.equations.public_sector_totals import solve_t as public_sector_totals
from obr_macro.equations.financial_sector import solve_t as financial_sector
from obr_macro.equations.income_account import solve_t as income_account
from obr_macro.equations.gdp import solve_t as gdp
from obr_macro.equations.household_balance import solve_t as household_balance

# Recommended solve order (Gauss-Seidel will iterate to handle simultaneity)
EQUATION_GROUPS = [
    north_sea_oil,
    labour_market,
    prices_wages,
    consumption,
    exports,
    imports,
    investment,
    inventories,
    gdp,
    income_account,
    public_receipts,
    public_expenditure,
    balance_of_payments,
    public_sector_totals,
    financial_sector,
    household_balance,
]
