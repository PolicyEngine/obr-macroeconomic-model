"""ONS time-series fetcher (Stage 1c proof-of-concept).

Resolves a model variable's ONS CDID to a series and returns it on a quarterly
PeriodIndex, ready to merge into the model data. The old api.ons.gov.uk was
retired (Nov 2024); this uses the beta search API to resolve a CDID to its
timeseries URI, then the website `/data` JSON endpoint.

Monthly and annual series are converted to quarterly according to the series
type (see SERIES_TYPE): cash flows in £m are summed over the months of a
quarter (an annual flow is divided by 4), while stocks, indices and rates are
averaged over months (an annual value is held flat across the four quarters).

    uv run python -m obr_macro.ons_fetch
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pandas as pd

_HEADERS = {"User-Agent": "Mozilla/5.0"}
_SEARCH = (
    "https://api.beta.ons.gov.uk/v1/search?q={cdid}&content_type=timeseries&limit=10"
)
_DATA = "https://www.ons.gov.uk{uri}/data"

# A handful of model variables -> CDID, for the proof of concept.
POC = {
    "CGIPS": "NMES",  # CG gross fixed capital formation (£m)
    "PPIY": "GB7S",  # producer output price index
    "POPAL": "EBAQ",  # population, all ages
    "EMPNIC": "CEAN",  # employers' NICs (£m)
    "VREC": "EYOO",  # net VAT receipts (£m)
}

# Per-CDID series type, used to pick the monthly->quarterly / annual->quarterly
# aggregation:
#   flow  : a cash amount per period (£m) — sum months into a quarter,
#           divide an annual value by 4.
#   stock : a level at (or averaged over) a point in time — balance-sheet
#           positions, money stocks, population and employment head-counts —
#           mean of months, annual value held flat.
#   index : a price index, deflator, weight, rate or ratio — mean of months,
#           annual value held flat.
# Classified from the model variables glossary descriptions
# (obr_macro/seeds/model_glossary.json). Unknown CDIDs default to "flow",
# since the vast majority of pulled series are £m National-Accounts flows.
SERIES_TYPE: dict[str, str] = {
    "AAZK": "flow",  # LABRO: LA market borrowing net CG/PC debt
    "ABEC": "flow",  # LCGLA: Net lending by CG to LAs
    "ABEI": "flow",  # LCGPC: Net lending by CG to PCs
    "ABIF": "flow",  # CGMISP: CG miscellaneous payments
    "ABJR": "index",  # MSTFE: index of final demand weighted by import intensity (servic
    "ABMF": "flow",  # TFEPS: Total Final Expenditure at current prices
    "ABML": "flow",  # GVAPS: Gross Value Added at basic prices
    "ABMM": "flow",  # GVA: Gross Value Added at basic prices, CVM
    "ABNG": "flow",  # OS: Whole economy Gross Operating Surplus
    "ACAC": "flow",  # CETAX: Customs & Excise taxes
    "ACCH": "flow",  # INHT: Inheritance tax
    "ACCI": "flow",  # TSD: Stamp duty receipts
    "ACCJ": "flow",  # PRT: Petroleum Revenue Tax
    "ACDD": "flow",  # TXFUEL: Hydrocarbon oils duty receipts
    "ACDE": "flow",  # TXTOB: Tobacco duty
    "ACDF": "flow",  # TXALC: Alcohol duties: beer, wines & spirits
    "ACDG": "flow",  # TXALC: Alcohol duties: beer, wines & spirits
    "ACDH": "flow",  # TXALC: Alcohol duties: beer, wines & spirits
    "ACDI": "flow",  # TXALC: Alcohol duties: beer, wines & spirits
    "ACDJ": "flow",  # TXCUS: Misc. C&E taxes
    "ACDO": "flow",  # TXCUS: Misc. C&E taxes
    "ACDP": "flow",  # TXCUS: Misc. C&E taxes
    "ACJY": "flow",  # NICAC: National Insurance accruals adjustment
    "ACUA": "stock",  # NATSAV: Stock of National Savings
    "ADAK": "flow",  # LATSUB: LA total subsidies: products & production
    "ADDU": "flow",  # LALEND: LA net lending to private sector & RoW
    "ADSE": "flow",  # KPSPC: PC capital grants from private sector
    "AIIH": "flow",  # EENIC: Employees' (& self-employed) payments of NICs
    "AIPA": "flow",  # DRES: Changes in reserve assets
    "ANBX": "flow",  # LARENT: LA rent & other current transfers
    "ANCW": "flow",  # PCRENT: PC rent & other current transfers
    "ANML": "flow",  # LAAC: LA accounts receivable/payable
    "ANMW": "flow",  # LAMFT: LA misc. financial transactions
    "ANMY": "flow",  # DINVCG: Change in inventories of Central Govt.
    "ANND": "flow",  # KCGPC: PC capital grants from Central Government
    "ANNI": "flow",  # KCGPSO: Capital grants by CG to private sector & ROW
    "ANNN": "flow",  # KPSCG: Capital grants by private sector (&RoW) to CG
    "ANNO": "flow",  # KGLA: Capital grants by private sector (&RoW) to LA
    "ANNQ": "flow",  # IPCPS: GFCF & net acquisition of land: PCs
    "ANNY": "flow",  # CGINTRA: CG NET interest & dividends from Public Sector
    "ANPZ": "flow",  # LAINTRA: LA NET interest & dividends from Public Sector
    "ANRH": "flow",  # CGLSFA: CG loans & sales of financial assets
    "ANRS": "flow",  # CGLSFA: CG loans & sales of financial assets
    "ANRT": "flow",  # CGACADJ: Central Govt accruals adjustments
    "ANRU": "flow",  # CGACADJ: Central Govt accruals adjustments
    "ANRV": "flow",  # MFTRAN: CG misc. financial transactions
    "ANRW": "flow",  # PCINTRA: PC NET interest & dividends from Public Sector
    "ANRY": "flow",  # PCLEND: PC net lending to private sector & RoW
    "ANRZ": "flow",  # PCMISE: PC misc. expenditure
    "ANSO": "flow",  # PUBSTIW: Public Sector taxes on Income & Wealth
    "ANVQ": "flow",  # PCAC: Public Corp. accounts rec./paid
    "ANVU": "flow",  # MFTPC: Public Corp. other financial transactions
    "AVAB": "stock",  # M0: Notes & coins in circulation outside BoE
    "BKQG": "stock",  # LALIQ: LA liquid assets
    "BKQJ": "stock",  # GGLIQ: General Government Liquid Assets
    "BKSM": "stock",  # CGLIQ: CG liquid assets
    "BKSN": "stock",  # CGLIQ: CG liquid assets
    "BKSO": "stock",  # LALIQ: LA liquid assets
    "BKSP": "stock",  # GGLIQ: General Government Liquid Assets
    "BKSQ": "stock",  # GGLIQ: General Government Liquid Assets
    "BOKG": "index",  # PXNOG: AVI of exports of non-oil goods
    "BOKH": "index",  # PMNOG: AVI of imports of non-oil goods
    "BOXX": "flow",  # XOIL: Exports of oil
    "BPIX": "flow",  # MOIL: Imports of oil
    "BQKO": "flow",  # MNOG: Imports of non-oil goods CVM
    "BQKQ": "index",  # MSTFE: index of final demand weighted by import intensity (servic
    "C625": "flow",  # LAEPS: Tax on Local Authority Equal Pay Settlements
    "C626": "flow",  # LANCGA: LA net current grants abroad
    "C6FP": "flow",  # FISIMGG: FISIM generated from General Government
    "C6FQ": "flow",  # FISIMGG: FISIM generated from General Government
    "C6G9": "flow",  # FISIMGG: FISIM generated from General Government
    "C6GA": "flow",  # FISIMGG: FISIM generated from General Government
    "C9K9": "index",  # ERCG: CG average earnings index
    "C9KA": "index",  # ERLA: LA average earnings index
    "CAEN": "flow",  # OSHH: Household & NPISH Gross Operating Surplus
    "CAEQ": "flow",  # OSPC: Gross Operating Surplus of Public Corporations
    "CAEX": "index",  # PDINV: Inventories deflator (change)
    "CAFU": "index",  # MSTFE: index of final demand weighted by import intensity (servic
    "CAGD": "flow",  # NSGTP: North Sea Gross Trading Profits:PNFCs
    "CDDZ": "flow",  # VEDHH: VED paid by HH; currrent taxes
    "CEAN": "flow",  # EMPNIC: Employers' payments of NICs
    "CFGW": "flow",  # NPISHTC: NPISH tax credits
    "CFZG": "flow",  # SWAPS: Swap adjustments
    "CGBV": "index",  # PGVA: Gross Value Added deflator
    "CGDN": "flow",  # CGITFA: Tax receipts from abroad
    "CGDO": "flow",  # HHTFA: HH transfer receipts from abroad
    "CGDS": "flow",  # HHTA: HH transfer payments abroad
    "CHAW": "index",  # I7: January base year indices for consumer prices RPI
    "CHMK": "index",  # I9: January base year indices for consumer prices RPIX
    "CMVL": "flow",  # TPRODPS: Taxes less subsidies on production
    "CPCM": "flow",  # PCNB: Public Corporations Net Borrowing (NSA)
    "CPRN": "flow",  # CT: Corporation tax (gross of tax credits)
    "CQOQ": "flow",  # LANNDR: LA payments of NNDR
    "CQTC": "flow",  # OHT: Other household taxes
    "CRSN": "flow",  # OPT: Other taxes on production
    "CRWF": "flow",  # NDIVHH: Dividend receipts of HH (&NPISH)
    "CRWH": "flow",  # WYQC: Withdrawals of income from quasi-corporations
    "CSH8": "flow",  # TXMIS: Misc. taxes on products
    "CT9E": "stock",  # STUDENT: HH stock of student debt
    "CT9U": "flow",  # OPT: Other taxes on production
    "CUCZ": "flow",  # LAVAT: VAT refunds to LAs
    "CUDB": "flow",  # OPT: Other taxes on production
    "CUKY": "flow",  # NNDRA: National Non-Domestic Rates Accrued receipts
    "CUNW": "flow",  # XLAVAT: VAT refunds (except to LAs)
    "CWR7": "flow",  # TXMIS: Misc. taxes on products
    "CWUX": "flow",  # TXMIS: Misc. taxes on products
    "CWV7": "flow",  # TXMIS: Misc. taxes on products
    "CX3X": "flow",  # EESCCG: CG employee social contributions
    "CYNX": "flow",  # INCTAC: Income tax accruals adjustment
    "CZXD": "index",  # W1: Weights for RPI components Rents
    "CZXE": "index",  # W4: Weights for RPI components MIPS
    "D69U": "flow",  # CGC: CG interest receipts: earnings on reserves
    "D7CE": "index",  # CPIRENT: Housing: Rent CPI
    "DBBO": "flow",  # TYEM: Taxes on income from employment
    "DBJY": "flow",  # NSCTP: North Sea Corporation Tax Payments
    "DBKE": "flow",  # INCTAC: Income tax accruals adjustment
    "DFT5": "flow",  # OPT: Other taxes on production
    "DH7A": "flow",  # BBC: BBC license fees
    "DHHL": "flow",  # IBPC: Public Corp's change in inventories & valuables
    "DKHE": "flow",  # INCTAC: Income tax accruals adjustment
    "DKHH": "flow",  # FCACA: Company IT withheld accruals adjustment
    "DLRA": "flow",  # SA: Stock appreciation
    "DLWF": "index",  # GGIDEF: General Government investment deflator
    "DMUM": "flow",  # ALAD: Alignemnt adjustment applied to change in inventories
    "DOBP": "index",  # PRENT: Housing: Rent RPI
    "DOBQ": "index",  # I4: January base year indices for RPI components MIPS
    "DOLC": "flow",  # TXCUS: Misc. C&E taxes
    "DPIH": "flow",  # TXMIS: Misc. taxes on products
    "DTWR": "flow",  # RENTCO: Private sector companies rental income
    "DTWS": "flow",  # RENTCO: Private sector companies rental income
    "DW9E": "flow",  # BETLEVY: Betting levies scored as taxes on income & wealth
    "DYZN": "stock",  # ES: Employers & self-employed (WFJ)
    "E8A6": "flow",  # PASSPORT: Passport fees
    "EBAQ": "stock",  # POPAL: Population all ages
    "EBFE": "flow",  # LAOTRHH: LA other current grants (to HH)
    "EED5": "flow",  # HIMPROV: Improvements to dwellings
    "ELBL": "index",  # PXNOG: AVI of exports of non-oil goods
    "ENXO": "index",  # PMNOG: AVI of imports of non-oil goods
    "EO2E": "flow",  # OFGEM: OFGEM renewable energy tax
    "EP89": "flow",  # ROCS: Renewable Obligation Certificates (tax on products)
    "EQCB": "flow",  # SA: Stock appreciation
    "EYOO": "flow",  # VREC: Net VAT receipts
    "F8YF": "stock",  # FLEASGG: Imputed GG debt from finance leases
    "F8YH": "stock",  # FLEASGG: Imputed GG debt from finance leases
    "F8YJ": "stock",  # FLEASPC: Imputed PC debt from finance leases
    "FCCS": "flow",  # TYPCO: Public Corp. onshore coporation tax payments
    "FHJL": "flow",  # NPAA: Net acquisition of non-produced non-fin. assets
    "FHLK": "flow",  # EUSUBPR: EU subsidies on production
    "FHLS": "flow",  # HHTA: HH transfer payments abroad
    "FJBH": "flow",  # EESCCG: CG employee social contributions
    "FJCK": "flow",  # TROD: CG non-EC transfer debits
    "FJUO": "flow",  # TROD: CG non-EC transfer debits
    "FJWE": "flow",  # EUOT: Payments of taxes on products to EU
    "FJWG": "flow",  # EUOT: Payments of taxes on products to EU
    "FKIJ": "flow",  # ECNET: Net EC contributions (BoP basis)
    "FKKL": "flow",  # ECNET: Net EC contributions (BoP basis)
    "FKKM": "flow",  # TROD: CG non-EC transfer debits
    "FKNG": "flow",  # EUSUBP: EU subsidies on products
    "FKNN": "flow",  # HHTFA: HH transfer receipts from abroad
    "FLUK": "flow",  # BENAB: Social security benefits paid abroad
    "FLVE": "flow",  # ITA: Tax payments abroad
    "FLVY": "flow",  # HHTA: HH transfer payments abroad
    "FLWB": "flow",  # CGKTA: Central Govt capital transfers abroad
    "FLWI": "flow",  # OPSKTA: Other private sector capital transfers abroad
    "FLWT": "flow",  # NPAA: Net acquisition of non-produced non-fin. assets
    "FLYE": "flow",  # HHTFA: HH transfer receipts from abroad
    "FSVL": "flow",  # EUVAT: UK VAT payments to the EU
    "G6NQ": "stock",  # ECG: Central Government employment
    "G6NT": "stock",  # ELA: Local Authority employment
    "G6NW": "stock",  # EGG: General Government Employment
    "GAN8": "flow",  # IBUSX: Business investment ex. BNFL transfer to CG
    "GB7S": "index",  # PPIY: Producer output Price Index ex. taxes
    "GCJG": "flow",  # MILAPM: MIRAS, LAPRAS & PMI scored as receipts
    "GCMP": "flow",  # CGASC: GG actual social contributions
    "GCMR": "flow",  # CONACC: Accruals adjustment on conventional gilts
    "GCSW": "flow",  # CONACC: Accruals adjustment on conventional gilts
    "GIXM": "flow",  # SDEPS: Statistical Discrepancy: GDP(E)
    "GIXQ": "flow",  # SDI: Statistical Discrepancy: GDP(I)
    "GRXE": "flow",  # TCINV: Other company taxes on investment
    "GTAX": "flow",  # VEDCO: VED paid by other sectors; production tax
    "GTAY": "flow",  # NIS: Employers' Natl Insurance Surcharge
    "GTTY": "flow",  # EUKT: Capital transfer payments from EU
    "GVHE": "flow",  # CGNDIV: CG interest & dividends from Private sector & RoW
    "GVHF": "flow",  # LANDIV: LA interest & dividends from Private sector & RoW
    "GVHG": "flow",  # PCNDIV: PC interest & dividends from PS % ROW
    "GZSI": "flow",  # CGNCGA: CG net current grants abroad
    "GZSJ": "flow",  # CGSB: CG net social benefits to households
    "GZSK": "flow",  # LASBHH: LA net social benefits to HH
    "GZSO": "flow",  # DIPCOP: PC interest payments to private sector & RoW
    "H5U3": "flow",  # EUSF: Receipts from EU social fund
    "HAYO": "index",  # MSTFE: index of final demand weighted by import intensity (servic
    "HBNR": "flow",  # ALROW: Total acquisition of UK claims on ROW (NSA)
    "HBNS": "flow",  # AAROW: Total acquisition of ROW claims on UK (NSA)
    "HBOK": "flow",  # CIPD: BoP investment income credits (ex reserve assets)
    "HBOL": "flow",  # DIPD: BoP investment income debits
    "HBQA": "stock",  # LROW: Total stock of UK claims on ROW ex reserve assets (NSA)
    "HBQB": "stock",  # AROW: Total stock of ROW claims on UK (NSA)
    "HBVI": "flow",  # NAEQLROW: Acquisition of UK portfolio equity claims on ROW (NSA)
    "HCML": "flow",  # EUVAT: UK VAT payments to the EU
    "HCSM": "flow",  # GNP4: UK 4th resource contribution to EU
    "HCSO": "flow",  # GNP4: UK 4th resource contribution to EU
    "HEPX": "stock",  # EQLROW: Stock of UK portfolio equity claims on ROW (NSA)
    "HEUC": "flow",  # LCGOS: CG net lending to RoW
    "HHCC": "flow",  # CGCBOP: CG IPD credits: earnings on reserves (BoP)
    "HHZX": "stock",  # BLROW: Stock of UK portfolio debt claims on ROW (NSA)
    "HLXV": "stock",  # OTLROW: Stock of UK Other claims on ROW (NSA)
    "HLXX": "stock",  # EQAROW: Stock of ROW portfolio equity claims on UK (NSA)
    "HLXY": "stock",  # BAROW: Stock of ROW portfolio debt claims on UK (NSA)
    "HLYD": "stock",  # OTAROW: Stock of ROW Other claims on UK (NSA)
    "IE9R": "flow",  # FISIMPS: Total nominal FISIM
    "IJAH": "flow",  # EECOMPC: Employees compensation from abroad
    "IJAI": "flow",  # EECOMPD: Employees compensation due abroad
    "IKBB": "index",  # PXS: AVI of exports of services
    "IKBC": "index",  # PMS: AVI of imports of services
    "IKBE": "flow",  # XS: Exports of services, CVM
    "IKBF": "flow",  # MS: Imports of services (CVM)
    "IKBN": "flow",  # TRANC: Transfer credits
    "IKBO": "flow",  # TRAND: Transfer debits
    "IV8E": "flow",  # FISIMROW: FISIM generated from Rest of World
    "IV8F": "flow",  # FISIMROW: FISIM generated from Rest of World
    "IY9O": "flow",  # OHT: Other household taxes
    "J5II": "flow",  # PSNBNSA: Public Sector Net Borrowing (NSA)
    "JT2Q": "flow",  # BANKROLL: Bank payroll tax
    "JW29": "flow",  # PCNDIV: PC interest & dividends from PS % ROW
    "JW2L": "flow",  # PSINTR: Public Sector interest & dividend receipts
    "JW2M": "flow",  # PSINTR: Public Sector interest & dividend receipts
    "JW2O": "flow",  # PSCR: Public Sector Current Receipts
    "JW2Q": "flow",  # PSCE: Public Sector Current Expenditure
    "JW2S": "flow",  # DEP: Public Sector Depreciation
    "JW2T": "flow",  # PSCB: Public Sector Current Budget
    "JW2Z": "flow",  # PSNI: Public Sector Net Investment
    "JW33": "flow",  # PSLSFA: Public Sector loans & sales of financial assets
    "JW34": "flow",  # PSLSFA: Public Sector loans & sales of financial assets
    "JW35": "flow",  # PSACADJ: Public Sector accruals adjustments
    "JW36": "flow",  # PSACADJ: Public Sector accruals adjustments
    "JW37": "flow",  # PSACADJ: Public Sector accruals adjustments
    "JW38": "flow",  # PSNCR: Public Sector Net Cash Requirement
    "JX96": "stock",  # LROW: Total stock of UK claims on ROW ex reserve assets (NSA)
    "JX97": "stock",  # AROW: Total stock of ROW claims on UK (NSA)
    "JXJ4": "flow",  # PCAC: Public Corp. accounts rec./paid
    "KAC4": "index",  # PSAVEI: Private sector average earnings index (inc. bonus)
    "KIH3": "flow",  # BLEVY: Bank Levy
    "KIY5": "flow",  # INCTAC: Income tax accruals adjustment
    "KLS2": "flow",  # NNSGVA: Non-North sea GVA
    "KW69": "flow",  # SWISSCAP: Swiss Capital Tax
    "KYHL": "index",  # PRP: Private Registered Provider rents per house per week
    "KYHM": "index",  # HRRPW: LA gross rent per house per week
    "L5PA": "index",  # W5: Weights for CPI components OOH
    "L62T": "flow",  # IHPS: Private sector investment in dwellings (CP)
    "L62U": "flow",  # IPRLPS: Private sector transfer costs on non-produced non-fin. Ass
    "L635": "flow",  # PCLEB: PC investment in existing buildings & transfer costs
    "L636": "index",  # PIH: Private sector investment in dwellings deflator
    "L637": "flow",  # IPRL: Private sector transfer costs on non-produced non-fin. ass
    "L8LQ": "flow",  # EECPP: Employees' contributions to funded pension schemes
    "L8LU": "flow",  # EESC: Employees' social contributions
    "L8N8": "flow",  # EMPCPP: Employers' contributions to funded pension schemes
    "L8ND": "flow",  # EESCLA: LA employee social contributions
    "L8PE": "flow",  # EECPP: Employees' contributions to funded pension schemes
    "L8PS": "flow",  # EESC: Employees' social contributions
    "L8Q2": "flow",  # EECPP: Employees' contributions to funded pension schemes
    "L8Q8": "flow",  # EESC: Employees' social contributions
    "L8R4": "flow",  # OSB: HH private funded social benefits (pensions)
    "L8RF": "flow",  # HHISC: Household imputed social contributions
    "L8UA": "flow",  # OPT: Other taxes on production
    "LITK": "flow",  # OPT: Other taxes on production
    "LITR": "flow",  # OPT: Other taxes on production
    "LITT": "flow",  # RFP: Rail Franchise Payments
    "LIUC": "flow",  # LASUBPR: LA subsidies on production
    "LIYH": "flow",  # TXMIS: Misc. taxes on products
    "LOJU": "flow",  # WRGTP: Work related govt training programmes
    "LSIB": "flow",  # LAMISE: LA miscellaneous expenditure
    "LSNS": "flow",  # CCL: Climate Change Levy
    "LSON": "flow",  # INHT: Inheritance tax
    "LTEB": "stock",  # SRES: Stock of reserve assets
    "M9VL": "stock",  # OLIC: Stock of other financial liabilities issued by PNFCs
    "M9WF": "flow",  # NAINS: Net acquisition of insurance assets : HH (NSA)
    "M9WU": "flow",  # CGISC: CG imputed social contributions
    "M9WY": "flow",  # LASC: LA imputed social contributions
    "M9WZ": "flow",  # EMPISC: Employers' imputed social contributions
    "M9X6": "flow",  # EMPISCPP: Employers' imputed social contributions to funded pensions
    "MA2H": "flow",  # NAPEN: Net acquisition of pension assets: HH (NSA)
    "MDUP": "flow",  # AL: Aggregates Levy
    "MDYL": "flow",  # CTC: Child tax credit
    "MGRT": "stock",  # EMS: Market sector employment (LFS)
    "MGRW": "stock",  # EMS: Market sector employment (LFS)
    "MGRZ": "stock",  # EMS: Market sector employment (LFS)
    "MGSC": "stock",  # ULFS: LFS unemployment (ILO)
    "MGSL": "stock",  # POP16: Population of 16+ (LFS)
    "MIYF": "flow",  # BETPRF: Betting tax scored as taxes on income & wealth
    "MIYZ": "flow",  # KPCPS: Net PC capital grants to private sector
    "MMW5": "stock",  # OAHH: Other assets: HH (NSA)
    "MMX4": "stock",  # OLIC: Stock of other financial liabilities issued by PNFCs
    "MUV5": "flow",  # TROD: CG non-EC transfer debits
    "MUV6": "flow",  # TROD: CG non-EC transfer debits
    "MVPC": "flow",  # TXMIS: Misc. taxes on products
    "N2SV": "flow",  # NADLROW: Acquisition of UK Direct Investment claims on ROW (NSA)
    "N2UG": "stock",  # DAROW: Stock of ROW Direct Investment claims on UK (NSA)
    "N2V3": "stock",  # DLROW: Stock of UK Direct Investment claims on ROW (NSA)
    "N3DV": "flow",  # TXMIS: Misc. taxes on products
    "NCBV": "flow",  # LAGILT: Local authority adjustment for gilt interest
    "NCXS": "flow",  # PCGILT: Public Corp. adjustment for gilt interest
    "NEQA": "flow",  # NAAIC: Net acquisition of financial assets by PNFCs
    "NETE": "flow",  # NALIC: Total net acquisition of financial liabilities by PNFCs
    "NETR": "flow",  # NABLIC: Net issuance of bonds & MMIs by PNFCs
    "NETZ": "index",  # NDIV: Dividend yield of UK non-financials
    "NEUX": "flow",  # NAFXLIC: Flow of FX lending to PNFCs
    "NEUZ": "flow",  # NAFXLIC: Flow of FX lending to PNFCs
    "NEVL": "flow",  # NAEQLIC: Net issuance of shares by PNFCs
    "NFXV": "flow",  # NAEQHH: Net acqusition of equity assets: HH (NSA)
    "NFYO": "flow",  # NAINS: Net acquisition of insurance assets : HH (NSA)
    "NFYS": "flow",  # NAOLPE: HH net acquisition of other financial liabilities (NSA)
    "NG4K": "stock",  # PSTA: Public Sector Tangible Assets (end period)
    "NGAS": "flow",  # NAOLPE: HH net acquisition of other financial liabilities (NSA)
    "NHRB": "flow",  # NAFROWNSA: Net lending (from capital account): ROW (NSA)
    "NIJI": "stock",  # OFLPS: Other Public Sector Financial Liabilities
    "NKFB": "stock",  # PSFA: Public Sector Financial Assets
    "NKIF": "stock",  # OFLPS: Other Public Sector Financial Liabilities
    "NKWX": "stock",  # AIC: Stock of financial assets held by PNFCs
    "NKZA": "stock",  # BLIC: Stock of bonds and Money Mkt instruments issued by PNFCs
    "NLBB": "stock",  # LIC: Total stock of financial liabilities of PNFCs
    "NLBC": "stock",  # OLIC: Stock of other financial liabilities issued by PNFCs
    "NLBE": "stock",  # OLIC: Stock of other financial liabilities issued by PNFCs
    "NLBG": "stock",  # FXLIC: Stock of FX Bank lending to PNFCs
    "NLBI": "stock",  # FXLIC: Stock of FX Bank lending to PNFCs
    "NLBU": "stock",  # EQLIC: Stock of shares issued by PNFCs
    "NLCO": "stock",  # OLIC: Stock of other financial liabilities issued by PNFCs
    "NMAI": "index",  # ERCG: CG average earnings index
    "NMCB": "flow",  # CGSUBP: CG subsidies on products
    "NMCC": "flow",  # CGSUBPR: CG subsidies on production
    "NMCD": "flow",  # CGTSUB: CG total subsidies: products & production
    "NMCK": "flow",  # RNCG: CG rent receipts
    "NMCV": "flow",  # OCT: Other current taxes: rec'd by CG
    "NMES": "flow",  # CGIPS: CG gross fixed capital formation
    "NMEZ": "flow",  # HHTCG: Household transfers to CG
    "NMFC": "flow",  # CGOTR: CG other current grants
    "NMFG": "flow",  # NPACG: CG net acquisitions Non-Produced Non-Fin. Assets
    "NMFJ": "flow",  # CGNB: Central Government Net Borrowing
    "NMFX": "flow",  # DICGOP: CG interest/dividends paid to private sector & RoW
    "NMGR": "flow",  # KCGLA: Capital grants by CG to LA
    "NMGT": "flow",  # KCGLA: Capital grants by CG to LA
    "NMIS": "flow",  # CC: Council tax accruals
    "NMJF": "index",  # ERLA: LA average earnings index
    "NMKK": "flow",  # LAPR: LA procurement expenditure
    "NMNL": "flow",  # KLA: Total capital transfers by LA
    "NMOA": "flow",  # LAIPS: LA gross fixed capital formation
    "NMOD": "flow",  # NPALA: LA net acquisitions Non-Produced Non-Fin. Assets
    "NMOE": "flow",  # LANB: Local Authority Net Borrowing
    "NMQZ": "flow",  # ILGAC: Accruals adjustment on index-linked gilts
    "NMRP": "flow",  # CGGPSPSF: General Govt final consumption
    "NMRY": "index",  # GGFCD: General Govt final consumption deflator
    "NMXS": "flow",  # GGVAPS: Nominal General Govt GVA
    "NMYE": "flow",  # PUBSTPD: Public Sector taxes on Production (& products)
    "NMYH": "flow",  # LAPT: LA receipts of production taxes
    "NNBK": "flow",  # GGNB: General Govt Net Borrowing (NSA)
    "NNML": "stock",  # GFWPE: Total HH financial assets (NSA)
    "NNMP": "flow",  # DEPHH: Currency and deposit assets: HH (NSA)
    "NNMY": "stock",  # OAHH: Other assets: HH (NSA)
    "NNOA": "stock",  # OAHH: Other assets: HH (NSA)
    "NNOS": "stock",  # EQHH: Stock of equity assets: HH (NSA)
    "NNPM": "stock",  # OAHH: Other assets: HH (NSA)
    "NNPP": "stock",  # OLPE: HH stock of other financial liabilities (NSA)
    "NNRP": "stock",  # LHP: HH liabilities secured on dwellings (NSA)
    "NPQT": "index",  # MSTFE: index of final demand weighted by import intensity (servic
    "NPUP": "stock",  # PSFA: Public Sector Financial Assets
    "NPVQ": "stock",  # OFLPS: Other Public Sector Financial Liabilities
    "NPYL": "stock",  # PIHH: Stock of pension & insurance assets: HH (NSA)
    "NRQB": "flow",  # OHT: Other household taxes
    "NSEZ": "flow",  # OPT: Other taxes on production
    "NSFA": "flow",  # OHT: Other household taxes
    "NSRM": "flow",  # PCCON: Public Corp. capital consumption
    "NSRN": "flow",  # RCGIM: CG non-trading capital consumption
    "NSRO": "flow",  # RLAIM: LA non-trading capital consumption
    "NSSZ": "flow",  # NAFHHNSA: Net lending (from capital account): HH (NSA)
    "NTAO": "flow",  # BPA: Basic Price Adjustment, CVM
    "NTAP": "flow",  # TPRODPS: Taxes less subsidies on production
    "NTAR": "flow",  # OSGG: General Govt Gross Operating Surplus
    "NUGW": "flow",  # DILAPR: LA interest/dividends paid to private sector & RoW
    "NYOD": "flow",  # NLROW: Net lending (from financial account): HH (NSA)
    "NYOT": "stock",  # NWIC: PNFC Net wealth
    "NYPO": "flow",  # SDLROW: Net lending stat. discrp. between capital and fin a/c: HH
    "NZDV": "flow",  # SDLHH: Net lending stat. discrp. between capital and fin a/c: HH
    "NZDY": "flow",  # NLHH: Net lending (from financial account): HH (NSA)
    "NZEA": "stock",  # NFWPE: HH net financial assets (NSA)
    "NZFS": "flow",  # OPT: Other taxes on production
    "NZFV": "flow",  # OPT: Other taxes on production
    "QWMZ": "flow",  # HHSB: Household social benefits
    "QWPS": "flow",  # CGWS: CG compensation of employees
    "QWPT": "flow",  # CGP: CG procurement expenditure
    "QWRY": "flow",  # LAWS: LA compensation of employees
    "QWRZ": "flow",  # LAPR: LA procurement expenditure
    "QYJR": "flow",  # CGCGLA: Total grants from CG to LA
    "QYJX": "flow",  # CGT: Capital Gains tax (paid by HH)
    "RITQ": "flow",  # GTPFC: Gross Trading Profits: FINCOs
    "RNKX": "flow",  # MI: Mixed income
    "ROAW": "flow",  # ICCPS: Gross fixed capital formation by PNFCs
    "ROAY": "flow",  # DIRIC: Total interest receipts of PNFCs
    "ROCG": "flow",  # DIPIC: Total interest payments of PNFCs
    "ROYL": "flow",  # PIRHH: Property income rec'd by HH (&NPISH)
    "ROYM": "flow",  # DIRHH: Total interest receipts of HH (&NPISH)
    "ROYP": "flow",  # APIIH: Other investment income
    "ROYT": "flow",  # PIPHH: Property income paid by HH (&NPISH)
    "ROYU": "flow",  # DIPHH: Total interest payments of HH (&NPISH)
    "RPHL": "flow",  # SBHH: Household social benefits
    "RPHO": "flow",  # NMTRHH: Net misc. transfer receipts of HH (&NPISH)
    "RPHS": "flow",  # TYWHH: Household current taxes on income & wealth
    "RPHT": "flow",  # TYWHH: Household current taxes on income & wealth
    "RPID": "flow",  # NMTRHH: Net misc. transfer receipts of HH (&NPISH)
    "RPQJ": "flow",  # NEAHH: Adj. for change in net equity of HH pension funds
    "RPQL": "flow",  # SVHH: Household (&NPISH) gross saving
    "RPVO": "flow",  # KGHH: Net capital transfers of HH (&NPISH)
    "RPVP": "flow",  # KGHH: Net capital transfers of HH (&NPISH)
    "RPVS": "flow",  # KGHH: Net capital transfers of HH (&NPISH)
    "RPVT": "flow",  # KGHH: Net capital transfers of HH (&NPISH)
    "RPYN": "flow",  # NAFFC: Net lending (from capital account): FINCOs (SA)
    "RPZD": "flow",  # PSNBCY: Public Sector Net Borrowing (CYSA)
    "RPZG": "index",  # GGIDEF: General Government investment deflator
    "RPZU": "flow",  # NPAHH: HH net acquisitions of non-produced non-fin. assets
    "RPZW": "flow",  # IHHPS: Gross fixed capital formation by HH&NPISH
    "RPZX": "flow",  # DINVHH: Change in inventories of HH and NPISH
    "RPZY": "flow",  # VALHH: HH Net acquisitions of valuables
    "RQBN": "flow",  # PSNBCY: Public Sector Net Borrowing (CYSA)
    "RUDY": "flow",  # CGISC: CG imputed social contributions
    "RUSD": "flow",  # EXDUTAC: HMRC indirect taxes accruals adjustments
    "RUTC": "flow",  # INCTAC: Income tax accruals adjustment
    "RUUW": "flow",  # CGNCR: CG Net Cash Requirement
    "THAP": "index",  # ECUPO: Sterling-euro exchange rate: Euro/£
    "UTIB": "index",  # PCDUR: Consumer durables deflator
    "UTID": "flow",  # CDUR: HH final consumption expenditure: durable goods (CVM)
    "VQSH": "stock",  # M4IC: Holdings of M4 by PNFCs
    "VQSJ": "stock",  # M4OFC: Holdings of M4 by OFCs
    "XBLW": "flow",  # NAEQAROW: Acquisition of ROW portfolio equity claims on UK (NSA)
    "XBLX": "flow",  # NABAROW: Acquisition of ROW portfolio debt claims on UK (NSA)
    "XBMM": "flow",  # NAOTLROW: Acquisition of UK Other claims on ROW (NSA)
    "XBMN": "flow",  # NAOTAROW: Acquisition of ROW Other claims on UK (NSA)
    "XBMW": "flow",  # NABLROW: Acquisition of UK portfolio debt claims on ROW (NSA)
    "ZAFG": "flow",  # TSEOP: Taxes on self-employment incomes
    "ZYBE": "flow",  # FCACA: Company IT withheld accruals adjustment
}


def series_type(cdid: str) -> str:
    """The aggregation type for a CDID: 'flow' (default), 'stock' or 'index'."""
    return SERIES_TYPE.get(cdid.upper(), "flow")


def _get_json(url, tries=4):
    """GET a JSON document, retrying only transient failures.

    Retries: timeouts, connection errors, HTTP 5xx and 429 (ONS intermittently
    502s). Does NOT retry: other HTTP errors (e.g. 404) or an invalid JSON
    payload — those are deterministic and retrying just wastes 4 round-trips.
    """
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code >= 500 or e.code == 429:
                last = e  # transient server-side failure
            else:
                raise  # 404 etc: permanent, don't retry
        except json.JSONDecodeError:
            raise  # bad payload won't fix itself
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            last = e  # network trouble: back off, retry
        time.sleep(1.5 * (i + 1))
    raise last


def resolve_uris(cdid):
    d = _get_json(_SEARCH.format(cdid=cdid))
    uris = []
    for it in d.get("items", []):
        u = (it.get("uri") or "").strip("/")
        parts = u.split("/")
        if len(parts) >= 2 and parts[-2].lower() == cdid.lower():
            uris.append("/" + u)
    return uris


def fetch_series(cdid):
    """Fetch a CDID and return ``(series, meta)``.

    ``series`` is on a quarterly PeriodIndex (or None if no data);
    ``meta`` is a dict with keys cdid, title, dataset, source_freq,
    aggregation and type — or None if the CDID could not be resolved.
    """
    best = None
    best_n = -1
    for uri in resolve_uris(cdid):
        try:
            d = _get_json(_DATA.format(uri=uri))
        except Exception:
            continue
        n = (
            len(d.get("quarters", []))
            or len(d.get("months", []))
            or len(d.get("years", []))
        )
        if n > best_n:
            best_n, best = n, d
    if best is None:
        return None, None

    desc = best.get("description", {})
    kind = series_type(cdid)
    meta = {
        "cdid": cdid,
        "title": desc.get("title", cdid),
        "dataset": desc.get("datasetId", ""),
        "type": kind,
        "source_freq": None,
        "aggregation": None,
    }
    q, m, y = best.get("quarters", []), best.get("months", []), best.get("years", [])

    if q:
        idx, vals = [], []
        for o in q:
            try:
                p = pd.Period(f"{o['year']}{o['quarter']}", freq="Q")
                v = float(o["value"])
            except Exception:
                continue  # keep idx and vals in lock-step (skip empty values)
            idx.append(p)
            vals.append(v)
        if not idx:
            return None, meta
        meta["source_freq"], meta["aggregation"] = "quarterly", "none"
        return pd.Series(vals, index=pd.PeriodIndex(idx, freq="Q")).sort_index(), meta

    if m:
        idx, vals = [], []
        for o in m:
            try:
                p = pd.Period(f"{o['year']}-{o['month'][:3]}", freq="M")
                v = float(o["value"])
            except Exception:
                continue
            idx.append(p)
            vals.append(v)
        if not idx:
            return None, meta
        s = pd.Series(vals, index=pd.PeriodIndex(idx, freq="M")).sort_index()
        meta["source_freq"] = "monthly"
        if kind == "flow":
            # A monthly cash flow must be SUMMED into its quarter. Drop
            # quarters with fewer than 3 observed months (a partial sum would
            # understate the quarterly flow).
            n_obs = s.resample("Q").count()
            qs = s.resample("Q").sum()
            qs = qs[n_obs == 3]
            meta["aggregation"] = "monthly->Q sum"
            return qs, meta
        meta["aggregation"] = "monthly->Q mean"
        return s.resample("Q").mean(), meta

    if y:
        idx, vals = [], []
        for o in y:
            try:
                yr = int(o["year"])
                v = float(o["value"])
            except Exception:
                continue
            idx.append(yr)
            vals.append(v)
        if not idx:
            return None, meta
        ys = pd.Series(vals, index=idx).sort_index()
        meta["source_freq"] = "annual"
        recs = {}
        if kind == "flow":
            # An annual cash flow held flat per quarter would be 4x the true
            # quarterly rate — spread it evenly instead.
            meta["aggregation"] = "annual->Q (/4)"
            for yr, val in ys.items():
                for qn in range(1, 5):
                    recs[pd.Period(f"{yr}Q{qn}", freq="Q")] = val / 4.0
        else:
            # stocks / indices / rates: hold the annual level flat.
            meta["aggregation"] = "annual->Q (held flat)"
            for yr, val in ys.items():
                for qn in range(1, 5):
                    recs[pd.Period(f"{yr}Q{qn}", freq="Q")] = val
        return pd.Series(recs).sort_index(), meta

    return None, meta


def main():
    print(
        f"Fetching {len(POC)} ONS series via the beta search + website data endpoints\n"
    )
    for code, cdid in POC.items():
        try:
            s, meta = fetch_series(cdid)
        except Exception as e:
            print(f"  {code:7} ({cdid})  FAILED: {type(e).__name__}: {e}")
            continue
        if s is None or s.empty:
            print(f"  {code:7} ({cdid})  no data")
            continue
        s = s.dropna()
        title, agg = meta["title"], meta["aggregation"]
        tail = ", ".join(f"{p}={v:,.0f}" for p, v in s.tail(3).items())
        print(
            f"  {code:7} ({cdid})  {agg:22}  {len(s):3} obs  {s.index.min()}..{s.index.max()}"
        )
        print(f"           {title[:60]}")
        print(f"           latest: {tail}\n")


if __name__ == "__main__":
    main()
