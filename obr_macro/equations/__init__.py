from obr_macro.equations.labour_market import solve_t as labour_market
from obr_macro.equations.prices_wages import solve_t as prices_wages
from obr_macro.equations.consumption import solve_t as consumption
from obr_macro.equations.investment import solve_t as investment
from obr_macro.equations.gdp import solve_t as gdp
from obr_macro.equations.income_account import solve_t as income_account
from obr_macro.equations.public_receipts import solve_t as public_receipts
from obr_macro.equations.public_expenditure import solve_t as public_expenditure
from obr_macro.equations.household_balance import solve_t as household_balance

# Solve order for the household-focused signal chain:
# labour_market -> prices_wages -> public_receipts + public_expenditure
# -> income_account -> consumption + household_balance
# GDP closes the loop (operating surplus feeds income accounts).
EQUATION_GROUPS = [
    labour_market,
    prices_wages,
    consumption,
    investment,
    gdp,
    income_account,
    public_receipts,
    public_expenditure,
    household_balance,
]
