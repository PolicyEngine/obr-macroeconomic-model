"""Example: run the slim OBR macro model and inspect key outputs.

Sets illustrative exogenous inputs (broadly consistent with recent UK
macro data), runs the Gauss-Seidel solver over 2025Q1-2026Q4, and
prints a summary of selected outputs.

The slim model keeps 9 of the original 16 equation modules, focused on
the household signal chain: labour market -> prices/wages -> public
receipts/expenditure -> income accounts -> consumption/household balance,
with GDP closing the loop.
"""

import numpy as np
from rich.console import Console
from rich.table import Table

from obr_macro.model import OBRMacroModel

console = Console()

# Start from 1970Q1 so trend base periods (e.g. 1979Q4) are in range
m = OBRMacroModel(start="1970Q1", end="2030Q4")
v = m.v


def s(name: str, value: float) -> None:
    """Set an exogenous variable to a constant across all periods."""
    v[name][:] = value


# ------------------------------------------------------------------
# GDP and output (largely exogenous in scenario runs)
# ------------------------------------------------------------------
s("GDPM", 560_000)          # Real GDP per quarter (GBPm, 2019 prices)
s("IF", 100_000)             # Fixed investment volume (GBPm)
s("X", 205_000)              # Exports volume
s("M", 195_000)              # Imports volume
s("XPS", 220_000)            # Exports current prices
s("MPS", 210_000)            # Imports current prices
s("DINV", 2_000)             # Inventory changes volume
s("DINVPS", 2_200)           # Inventory changes current prices
s("DINVCG", 500)             # CG inventory changes
s("DINVHH", 400)             # HH inventory changes
s("VAL", 5_000)              # Valuables volume
s("SDE", 500)                # Statistical discrepancy volume
s("INV", 2_000)              # Inventories level
s("BV", 2_200)               # Book value of inventories
s("TRGDP", 560_000)          # Trend GDP
s("NSGVA", 3_000)            # North Sea GVA
s("SA", 1_000)               # Stock appreciation

# ------------------------------------------------------------------
# Prices and deflators
# ------------------------------------------------------------------
s("CPI", 133.0)              # CPI (2015=100)
s("PPIY", 118.0)             # PPI output
s("PBRENT", 78.0)            # Brent crude ($/bbl)
s("WPG", 105.0)              # World price of goods
s("PIH", 130.0)              # Housing investment deflator
s("OOH", 135.0)              # Owner-occupier housing costs

# RPI components
s("I4", 100.0)
s("I7", 100.0)
s("I9", 100.0)
s("PRXMIP", 100.0)           # RPI excl. mortgage interest

# CPI weights
s("W1", 0.06)                # CPI rental weight
s("W4", 0.03)                # RPI mortgage weight
s("W5", 0.17)                # CPIH OOH weight

# ------------------------------------------------------------------
# Interest rates (%)
# ------------------------------------------------------------------
s("R", 4.50)                 # Bank Rate
s("RL", 4.25)                # Long gilt rate
s("RMORT", 5.50)             # Mortgage rate
s("RDEP", 3.20)              # Deposit rate
s("ROCB", 5.50)              # Corporate bond rate
s("DISCO", 0.08)             # Discount rate (investment)

# ------------------------------------------------------------------
# Exchange rates
# ------------------------------------------------------------------
s("RX", 100.0)               # Sterling effective exchange rate index
s("RXD", 1.27)               # Dollar exchange rate

# ------------------------------------------------------------------
# Labour market
# ------------------------------------------------------------------
s("EGG", 5_500)              # General government employment (thousands)
s("HWA", 1_025)              # Total hours worked (millions per week)
s("AVH", 31.3)               # Average hours/week
s("GAD1", 12_000)            # Population group 1
s("GAD2", 35_000)            # Population group 2
s("GAD3", 12_500)            # Population group 3
s("POPAL", 68_000)           # Total population (thousands)
s("HRRPW", 0.28)             # Housing rent to wages ratio

# ------------------------------------------------------------------
# Income
# ------------------------------------------------------------------
s("FYEMP", 310_000)          # Employment income total
s("EMPSC", 42_000)           # Employer social contributions
s("ADJW", 1.0)               # Wage adjustment factor
s("CORP", 90_000)            # Corporate profits proxy
s("NDIV", 5.0)               # Net dividends (for investment equations)
s("FSMADJ", 0)               # FISIM adjustment
s("APIIH", 5_000)            # HH property income (other)
s("DIRHH", 8_000)            # HH deposit interest receipts
s("DIPHHuf", 500)            # HH interest (unfunded)
s("NIPD", -5_000)            # Net investment income from abroad

# ------------------------------------------------------------------
# Employment composition
# ------------------------------------------------------------------
s("ERCG", 1.0)               # CG relative earnings
s("ERLA", 1.0)               # LA relative earnings
s("CGWADJ", 600)             # CG wage adjustment
s("LAWADJ", 500)             # LA wage adjustment

# ------------------------------------------------------------------
# Government spending
# ------------------------------------------------------------------
s("CGGPS", 130_000)          # Government consumption current prices
s("CGGPSPSF", 130_000)       # Government consumption (PSF basis)
s("CGIPS", 15_000)           # CG investment current prices
s("LAIPS", 8_000)            # LA investment current prices
s("LAPR", 5_000)             # LA procurement
s("RCGIM", 4_000)            # CG imputed rent/depreciation
s("RLAIM", 2_000)            # LA imputed rent/depreciation
s("CGSB", 55_000)            # CG social benefits
s("LASBHH", 12_000)          # LA social benefits to households
s("CGOTR", 3_000)            # CG other transfers
s("CGSUBP", 2_000)           # CG product subsidies
s("CGSUBPR", 1_500)          # CG production subsidies
s("TROD", 500)               # Transfer of debt
s("CGNDIV", 1_200)           # CG dividend receipts
s("LANDIV", 200)             # LA dividend receipts
s("PCNDIV", 300)             # PC dividend receipts
s("HHTCG", 800)              # HH tax credits (CG)
s("RNCG", 1_500)             # CG rental income
s("CGKTA", 500)              # CG capital transfers
s("OPSKTA", 200)             # Other PS capital transfers
s("NPACG", 100)              # CG non-produced assets
s("NPALA", 50)               # LA non-produced assets

# ------------------------------------------------------------------
# Local authority
# ------------------------------------------------------------------
s("LASUBP", 800)             # LA product subsidies
s("LAPT", 2_000)             # LA production taxes
s("LARENT", 1_500)           # LA rental income
s("LAOTRHH", 1_000)          # LA other transfers to HH
s("LAVAT", 500)              # LA VAT
s("LAEPS", 300)              # LA employer pension surcharge

# ------------------------------------------------------------------
# Tax receipts (mostly exogenous in scenario runs)
# ------------------------------------------------------------------
s("TYEM", 55_000)            # Income tax on employment
s("TSEOP", 8_000)            # Tax on self-employment
s("TCINV", 3_500)            # Tax on investment income
s("EENIC", 38_000)           # Employee NICs
s("EMPNIC", 22_000)          # Employer NICs
s("VREC", 42_000)            # VAT receipts
s("TXFUEL", 6_500)           # Fuel duty
s("TXTOB", 2_500)            # Tobacco duty
s("TXALC", 3_200)            # Alcohol duty
s("TXCUS", 800)              # Customs excise
s("TXMIS", 1_500)            # Miscellaneous taxes
s("CUST", 1_200)             # Customs duties
s("CCL", 500)                # Climate change levy
s("AL", 200)                 # Aggregates levy
s("TSD", 4_500)              # Stamp duties
s("CGT", 4_000)              # Capital gains tax
s("INHT", 2_000)             # Inheritance tax
s("CC", 11_000)              # Council tax
s("PRT", 0)                  # Petroleum revenue tax
s("NNSCTP", 20_000)          # Non-NS corporation tax
s("NSCTP", 500)              # NS corporation tax
s("NNDRA", 8_000)            # National non-domestic rates
s("TCPRO", 0.25)             # Corporation tax rate
s("INCTAC", 500)             # Income tax accruals
s("EXDUTAC", 300)            # Excise duty accruals
s("XLAVAT", 200)             # Extra-legal VAT
s("FCACA", 100)              # Financial corps accruals
s("CCLACA", 50)              # CCL accruals
s("BETPRF", 400)             # Betting profits
s("BETLEVY", 100)            # Betting levy
s("OFGEM", 200)              # Ofgem receipts
s("NPISHTC", 300)            # NPISH tax credits
s("TYPCO", 200)              # Tax paid by public corps
s("PROV", 100)               # Provisions
s("OHT", 500)                # Other household taxes
s("OPT", 1_000)              # Other production taxes
s("VEDCO", 800)              # VED corporate
s("VEDHH", 1_800)            # VED household
s("BBC", 1_000)              # BBC licence fee
s("PASSPORT", 200)           # Passport receipts
s("RFP", 300)                # Regulatory fees
s("ROCS", 400)               # Regulatory charges
s("CIL", 500)                # Community infrastructure levy
s("ENVLEVY", 200)            # Environmental levy
s("BANKROLL", 300)           # Bank levy rollover
s("RULC", 100)               # Regulatory utility levy
s("BLEVY", 600)              # Bank levy
s("SWISSCAP", 50)            # Swiss capital
s("EUETS", 200)              # EU ETS
s("EUOT", 100)               # EU other taxes
s("EUSUBP", 500)             # EU product subsidies
s("EUSUBPR", 300)            # EU production subsidies
s("EUVAT", 100)              # EU VAT
s("EUSF", 200)               # EU social fund
s("EUKT", 100)               # EU capital transfers
s("NIS", 0)                  # National insurance surcharge

# ------------------------------------------------------------------
# Capital allowances / investment parameters
# ------------------------------------------------------------------
s("IIB", 0.0)                # Initial investment allowance
s("SIB", 0.25)               # Standard investment allowance rate
s("FP", 0.50)                # First-year allowance proportion
s("SP", 0.06)                # Standard allowance pool rate
s("SV", 0.04)                # Salvage value rate
s("DEBTW", 0.35)             # Debt weight in cost of capital
s("TPBRZ", 0.0)              # Tax relief on mortgage interest
s("PEHC", 50)                # Private enterprise housing completions

# ------------------------------------------------------------------
# Housing and investment volumes
# ------------------------------------------------------------------
s("IH", 18_000)              # Housing investment volume
s("IPRL", 5_000)             # Private landlord investment volume
s("IPRLPS", 5_800)           # Private landlord investment current prices
s("PCLEB", 2_000)            # PC leasing
s("LHP", 1_600_000)          # Lending to households (mortgages)
s("HH", 28_500)              # Number of households
s("APH", 280)                # Average house price (GBP thousands)
s("STUDENT", 180_000)        # Student loans outstanding

# ------------------------------------------------------------------
# Financial sector / balance sheet
# ------------------------------------------------------------------
s("M4IC", 500_000)           # M4 institutional
s("RIC", 5.0)                # Institutional lending rate
s("OSPC", 3_000)             # Operating surplus of PCs
s("PCRENT", 500)             # PC rental income
s("EQPR", 100)               # Equity price index
s("WEQPR", 100)              # World equity prices
s("SIPT", 0.01)              # Stock index ratio
s("FISIMROW", 1_000)         # FISIM rest of world
s("IBPC", 2_000)             # PC investment borrowing

# ------------------------------------------------------------------
# Transfer / benefit parameters
# ------------------------------------------------------------------
s("CTC", 1_500)              # Child tax credit
s("MILAPM", 200)             # Married couple's allowance
s("BENAB", 500)              # Benefit abatement
s("SBHH_A", 0)               # Social benefits add-factor
s("TYWHH_A", 0)              # Household tax add-factor
s("EESC_A", 0)               # Employer social contributions add-factor
s("PRMIP_A", 0)              # Mortgage interest add-factor
s("MGDPNSA_A", 0)            # GDP add-factor
s("DEPHHADJ", 0)             # Household deposits adjustment
s("NAEQHHADJ", 0)            # Household equity acquisition adj
s("NAINSADJ", 0)             # Insurance acquisition adj
s("NAOLPEADJ", 0)            # Other lending adj

# ------------------------------------------------------------------
# Balance of payments / capital (exogenous stubs)
# ------------------------------------------------------------------
s("NPAA", 500)               # Net purchase of assets abroad
s("NPAHH", 200)              # Household non-produced assets
s("HHTA", 300)               # Household transfers abroad
s("HHTFA", 400)              # Household transfers from abroad
s("CB", 2_000)               # Current balance
s("PSNBCY", 15_000)          # PSNB (cyclical)
s("NAFROW", -5_000)          # Net acquisition financial assets: RoW
s("KGLA", 500)               # LA capital grants
s("KLA", 300)                # LA capital transfers
s("KCGPSO", 200)             # CG capital grants (PSO)
s("SRES", 0)                 # Stock revaluations residual
s("DRES", 0)                 # Direct investment residual
s("ALROW", 5_000)            # Net acquisition of liabilities: RoW
s("OAHHADJ", 0)              # Other assets adjustment: HH
s("EECOMPC", 1_000)          # Employee compensation credits
s("EECOMPD", 500)            # Employee compensation debits
s("NNSGTP", 50_000)          # Non-NS gross trading profits
s("NSGTP", 1_500)            # NS gross trading profits

# ------------------------------------------------------------------
# Initial values for endogenous variables (needed for lagged terms)
# These bootstrap the dynamic equations which use t-1, t-2, etc.
# ------------------------------------------------------------------

# National accounts
s("GDPMPS", 665_000)         # Nominal GDP
s("PGDP", 118.0)             # GDP deflator
s("GVA", 540_000)            # GVA volume
s("GVAPS", 590_000)          # GVA current prices
s("MSGVA", 440_000)          # Market sector GVA volume
s("MSGVAPS", 490_000)        # Market sector GVA current prices
s("NNSGVA", 537_000)         # Non-NS GVA
s("GGVA", 100_000)           # Government GVA volume
s("GGVAPS", 132_000)         # Government GVA current prices
s("BPA", 80_000)             # Taxes less subsidies volume
s("SDI", 500)                # Statistical discrepancy volume (income)
s("SDEPS", 590)              # Statistical discrepancy current prices
s("RENTCO", 15_000)          # Rental income: corporates
s("MGDPNSA", 665_000)       # GDP NSA
s("OS", 200_000)             # Gross operating surplus

# Prices
s("PCE", 130.0)              # Consumption deflator
s("PD", 310)                 # House price index
s("PIF", 125.0)              # Investment deflator
s("PMSGVA", 111.0)           # Market sector GVA deflator
s("PMNOG", 110.0)            # Import price: non-oil goods
s("PMS", 110.0)              # Import price: services
s("PXNOG", 108.0)            # Export price: non-oil goods
s("PXS", 108.0)              # Export price: services
s("PGVA", 109.0)             # GVA deflator
s("PCDUR", 95.0)             # Durable goods deflator
s("PIBUS", 125.0)            # Business investment deflator
s("PSAVEI", 650)             # AWE (GBP/week)
s("PR", 380.0)               # RPI index level
s("PRENT", 130.0)            # Rental prices
s("CPIRENT", 130.0)          # CPI rental component
s("CPIH", 133.0)             # CPIH
s("PRMIP", 1_200)            # Mortgage interest payments index

# Cost indices
s("SCOST", 100.0)
s("CCOST", 100.0)
s("UTCOST", 100.0)
s("RPCOST", 100.0)

# Labour market
s("ECG", 2_500)              # CG employment
s("ELA", 1_800)              # LA employment
s("ET", 33_000)              # Total employment
s("ETLFS", 32_750)           # LFS employment
s("EMS", 27_000)             # Market sector employment
s("ES", 4_200)               # Self-employment
s("ESLFS", 4_100)            # LFS self-employment
s("POP16", 54_000)           # Working-age population
s("LFSUR", 4.2)              # Unemployment rate
s("WRGTP", 1_000)            # Workforce-related aggregates
s("HD", 310)                 # Housing demand

# Income
s("WFP", 260_000)            # Wages and salaries: private
s("MI", 45_000)              # Mixed income
s("FYCPR", 120_000)          # Corporate profits
s("FISIMPS", 20_000)         # FISIM
s("WYQC", 5_000)             # Windfall capital gains
s("RHHDI", 390_000)          # Real HH disposable income

# Consumption
s("CONS", 370_000)           # HH consumption volume
s("CONSPS", 430_000)         # HH consumption current prices
s("CDUR", 55_000)            # Durable goods volume
s("NFWPE", 4_500_000)        # HH net financial wealth
s("GPW", 290)                # Gross pay per worker

# Investment
s("IFPS", 125_000)           # Fixed investment current prices
s("IBUS", 60_000)            # Business investment volume
s("IBUSX", 60_000)           # Business investment (excl. one-offs)
s("KMSXH", 3_500)            # Capital stock (GBP bn)
s("KSTAR", 3_600_000)        # Desired capital stock
s("GGIDEF", 120.0)           # GG investment deflator
s("HIMPROV", 12_000)         # House improvement spending
s("PCIH", 15_000)            # PC investment: housing
s("IHPS", 23_400)            # Housing investment current prices
s("IHHPS", 30_000)           # HH investment current prices
s("HSALL", 29_000)           # Housing stock
s("CDEBT", 5.0)              # Debt cost of capital
s("VALPS", 6_250)            # Valuables current prices
s("VALHH", 1_563)            # HH valuables
s("ICCPS", 65_000)           # Corporate investment current prices
s("IPCPS", 8_000)            # PC investment current prices
s("IFCPS", 12_000)           # Financial corp investment

# Government wages
s("CGWS", 19_500)            # CG wage bill
s("LAWS", 11_700)            # LA wage bill
s("CGG", 105_000)            # Government consumption volume
s("CGP", 90_000)             # Government procurement
s("CGC", 4_000)              # Capital gains from CGT
s("CGASC", 2_000)            # CG admin social contributions
s("CGISC", 1_500)            # CG imputed social contributions
s("EESCCG", 3_000)           # CG employer social contributions
s("EESCLA", 2_000)           # LA employer social contributions
s("LASC", 1_800)             # LA social contributions
s("LASUBPR", 1_000)          # LA production subsidies

# Social contributions / benefits
s("HHISC", 5_000)            # HH imputed social contributions
s("EMPISC", 6_500)           # Employer imputed social contributions
s("EMPISCPP", 3_000)         # Employer imputed SC: pension
s("EMPCPP", 8_000)           # Employee pension contributions
s("OSB", 15_000)             # Other social benefits
s("HHSB", 10_000)            # HH social benefits

# Household balance sheet
s("DEPHH", 2_100_000)        # HH deposits
s("DEPHHx", 2_100_000)       # HH deposits (excl. adj)
s("EQHH", 1_200_000)         # HH equity holdings
s("PIHH", 3_800_000)         # HH pension/insurance assets
s("OAHH", 300_000)           # HH other assets
s("OAHHx", 300_000)          # HH other assets (excl. adj)
s("GFWPE", 7_400_000)        # HH gross financial wealth
s("OLPE", 250_000)           # Other lending to persons
s("OLPEx", 70_000)           # Other lending (excl. student)
s("DEBTU", 0.02)             # Debt unwind rate
s("NAFHH", 5_000)            # Net acquisition: HH
s("NAFHHNSA", 5_000)         # Net acquisition: HH NSA
s("DBR", 0.55)               # Discount bond ratio
s("NAINSx", 2_000)           # Insurance acquisitions
s("MKR", 100.0)              # Markup ratio
s("GMF", 0.04)               # Gross mortgage ratio
s("STLIC", 200_000)          # Short-term lending: institutional
s("BLIC", 100_000)           # Bond lending: institutional
s("FXLIC", 50_000)           # FX lending: institutional
s("EQLIC", 500_000)          # Equity liabilities: institutional
s("OLIC", 30_000)            # Other liabilities: institutional
s("LIC", 880_000)            # Total liabilities: institutional
s("AIC", 600_000)            # Assets: institutional
s("NWIC", -280_000)          # Net worth: institutional
s("NIIP", -500_000)          # Net international investment position

# Prices and wages intermediates
s("ULCMS", 100.0)            # Unit labour costs
s("OILBASE", 80.0)           # Oil price base
s("EARN", 750)               # Earnings per employee

# Rest of world balance sheet
s("DAROW", 800_000)          # Direct investment abroad
s("EQAROW", 300_000)         # RoW equity in UK
s("BAROW", 400_000)          # RoW bonds in UK
s("OTAROW", 200_000)         # RoW other assets in UK
s("AROW", 1_700_000)         # RoW total assets in UK
s("DLROW", 600_000)          # Direct liabilities: RoW
s("EQLROW", 400_000)         # Equity liabilities: RoW
s("BLROW", 300_000)          # Bond liabilities: RoW
s("OTLROW", 200_000)         # Other liabilities: RoW
s("LROW", 1_500_000)         # Total liabilities: RoW
s("NAFROWNSA", -5_000)       # Net acquisition: RoW NSA
s("NAEQAROW", 2_000)         # Net equity acquisition: RoW
s("NAOTLROW", 1_000)         # Net other liabilities: RoW

# Memo: total final expenditure
s("TFEPS", 750_000)          # TFE at current prices
s("TFE", 650_000)            # TFE volume

# Dividend / profit intermediates
s("NDIVHH", 12_000)
s("IROO", 25_000)            # Imputed rent
s("OSHH", 30_000)            # HH operating surplus
s("OSGG", 6_100)             # GG operating surplus
s("OSCO", 160_000)           # Corporate operating surplus
s("GTPFC", 50_000)           # Gross trading profits: FC
s("FC", 70_000)              # Financial corporations
s("SAVCO", 50_000)           # Corporate saving

# Income account intermediates
s("HHDI", 370_000)           # HH disposable income
s("SVHH", 5_000)             # HH saving
s("SY", 1.3)                 # Saving ratio
s("NEAHH", 3_000)            # Net equity acquisition: HH
s("KGHH", -1_000)            # Capital transfers: HH
s("NAFCO", 10_000)           # Net acquisition: corporates
s("NAFFC", 5_000)            # Net acquisition: financial
s("NAFIC", 5_000)            # Net acquisition: institutional
s("TYWHH", 75_000)           # HH taxes
s("NMTRHH", 2_000)           # Net misc transfers: HH
s("SBHH", 80_000)            # Social benefits: HH
s("PIRHH", 30_000)           # Property income received: HH
s("PIPHH", 8_000)            # Property income paid: HH
s("EECPP", 4_000)            # Employer pension contributions
s("EESC", 65_000)            # Total employer social contributions

# Investment intermediates
s("RWACC", 8.0)              # Weighted average cost of capital
s("COC", 6.0)                # Cost of capital
s("TAF", 1.05)               # Tax-adjusted factor
s("PKMSXHB", 125.0)          # Capital stock deflator
s("TQ", 0.8)                 # Tobin's Q
s("GGI", 19_000)             # GG investment volume
s("GGIX", 19_000)            # GG investment (excl. one-offs)
s("GGIPS", 23_000)           # GG investment current prices

# Wage/price intermediates
s("MSGVAPSEMP", 445_000)
s("FYEMPMS", 220_000)
s("RPW", 6_000)
s("RCW", 2_400)
s("MKGW", 100.0)
s("RHF", 5.0)
s("RPI", 3.5)
s("PINV", 110.0)

# GDP per capita
s("GDPMAL", 8.2)
s("TRGDPAL", 8.2)
s("GDPM16", 10.4)
s("TRGDP16", 10.4)
s("GAP", 0.0)

# Production taxes
s("TPRODPS", 12_000)

# GNI
s("GNIPS", 660_000)

# Other intermediates
s("BPAPS", 85_000)           # Taxes less subsidies on products
s("PART16", 63.0)            # Participation rate
s("ULFS", 1_400)             # Unemployment level
s("ER", 60.6)                # Employment rate
s("EPS", 24_700)             # Private sector employment
s("WFJ", 34_000)             # Workforce jobs
s("PRODH", 0.55)             # Productivity (output per hour)
s("GAD", 59_500)             # Population total
s("CETAX", 97_000)           # Customs/excise total
s("VED", 2_600)              # Vehicle excise duty
s("OCT", 3_500)              # Other current taxes
s("TAXCRED", 1_700)          # Tax credits
s("INCTAXG", 67_000)         # Income tax gross
s("PUBSTIW", 130_000)        # PS income/wealth taxes
s("PUBSTPD", 115_000)        # PS production/import taxes
s("PSCR", 270_000)           # PS current receipts
s("NATAXES", 245_000)        # National taxes
s("PSINTR", 1_700)           # PS interest
s("CGRENT", 2_300)           # CG rental income
s("CGTSUB", 3_500)           # CG subsidies total
s("LATSUB", 1_800)           # LA subsidies total
s("GGFCD", 124.0)            # GG consumption deflator
s("CGNCGA", 500)             # CG non-cash grants
s("OSGG", 6_100)             # Operating surplus GG
s("EMPASC", 35_500)          # Employer actual SC
s("DIPHHmf", 15_000)         # Mortgage interest payments
s("DIPHH", 20_000)           # HH interest payments
s("DIPHHx", 35_500)          # HH interest total
s("DIRHHf", -5_000)          # HH deposit interest (formula)
s("DIRHHx", 13_000)          # HH deposit interest (excl.)
s("DIRICf", 10_000)          # Institutional interest: formula
s("DIRIC", 25_000)           # Institutional interest
s("DIRICx", 15_000)          # Institutional interest: excl.
s("DIPICf", 8_000)           # Institutional interest paid: formula
s("DIPIC", 18_000)           # Institutional interest paid
s("DIPICx", 26_000)          # Institutional interest total
s("LFSUR", 4.2)              # Unemployment rate
s("NETAD", 0.076)            # Net additions to housing
s("PIPRL", 116.0)            # Private landlord investment deflator

# ------------------------------------------------------------------
# Bootstrap: find internally-consistent endogenous values.
# 1. Single-pass bootstrap to get all variables finite
# 2. Broadcast those values as initial conditions
# 3. Run the solver over a warm-up window so the G-S per-period
#    iterations produce a true steady state
# ------------------------------------------------------------------
# Snapshot exogenous values before bootstrap
exog_snapshot = {name: v[name][0] for name in v._data}

console.print("\n[bold]OBR macro model (slim) - forecast run[/bold]")
console.print("Bootstrapping...")

from obr_macro.equations import EQUATION_GROUPS

# Phase 1: single-pass to get all variables finite
t_boot = v.period_to_idx("2000Q1")
for _ in range(50):
    for group in EQUATION_GROUPS:
        group(v, t_boot)
    for name in list(v._data.keys()):
        val = v[name][t_boot]
        if np.isfinite(val):
            v[name][:] = val

# Phase 2: run 40 quarters of warm-up with full G-S to stabilise
m.run("2015Q1", "2024Q4", verbose=False)

# Broadcast the final warm-up period values as the initial state
t_final = v.period_to_idx("2024Q4")
for name in list(v._data.keys()):
    val = v[name][t_final]
    if np.isfinite(val):
        v[name][:] = val

nan_count = sum(1 for n in v._data if np.isnan(v[n][t_final]))
console.print(f"Bootstrap done. NaN vars: [cyan]{nan_count}[/cyan]")

# Re-apply exogenous values (bootstrap may have overwritten them
# with equation-computed values — we want the user's inputs).
for name, val in exog_snapshot.items():
    v[name][:] = val

console.print("Solving 2025Q1 to 2026Q4...\n")
iters = m.run("2025Q1", "2026Q4", verbose=True)

avg_iters = np.mean(list(iters.values()))
console.print(f"\nAverage iterations per quarter: [cyan]{avg_iters:.1f}[/cyan]\n")

# ------------------------------------------------------------------
# Check for NaNs
# ------------------------------------------------------------------
t = v.period_to_idx("2025Q4")
nan_vars = [name for name in sorted(v._data.keys()) if np.isnan(v[name][t])]
if nan_vars:
    console.print(f"[red]Warning: {len(nan_vars)} NaN variables at 2025Q4:[/red]")
    for n in nan_vars:
        console.print(f"  {n}")
else:
    console.print("[green]All variables solved - no NaNs.[/green]\n")

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
    ("GDPMPS", "Nominal GDP (GBPbn)",        1_000),
    ("GDPM",   "Real GDP (GBPbn, 2019 p.)",  1_000),
    ("PGDP",   "GDP deflator (2019=100)",     1),
    ("CPI",    "CPI (2015=100)",              1),
    ("LFSUR",  "Unemployment rate (%)",       1),
    ("ETLFS",  "Employment (thousands)",      1),
    ("CONS",   "HH consumption (GBPbn)",      1_000),
    ("CONSPS", "HH consumption nom. (GBPbn)", 1_000),
    ("RHHDI",  "Real HH disp. income (GBPbn)", 1_000),
    ("HHDI",   "Nominal HH disp. income (GBPbn)", 1_000),
    ("SVHH",   "HH saving (GBPm)",           1),
    ("SY",     "Saving ratio (%)",            1),
    ("NFWPE",  "HH net fin. wealth (GBPbn)",  1_000),
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
