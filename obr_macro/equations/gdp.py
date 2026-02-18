"""Group 16: Gross domestic product equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    CGGPS = v["CGGPS"]
    CONSPS = v["CONSPS"]
    DINVPS = v["DINVPS"]
    VALPS = v["VALPS"]
    IFPS = v["IFPS"]
    XPS = v["XPS"]
    MPS = v["MPS"]
    SDEPS = v["SDEPS"]
    CGG = v["CGG"]
    CONS = v["CONS"]
    DINV = v["DINV"]
    VAL = v["VAL"]
    IF = v["IF"]
    X = v["X"]
    M = v["M"]
    GDPMPS = v["GDPMPS"]
    GDPM = v["GDPM"]
    PGDP = v["PGDP"]
    GVA = v["GVA"]
    BPA = v["BPA"]

    # Total final expenditure at current prices
    TFEPS = CGGPS[t] + CONSPS[t] + DINVPS[t] + VALPS[t] + IFPS[t] + XPS[t]
    v["TFEPS"][t] = TFEPS

    # Statistical discrepancy
    v["SDEPS"][t] = PGDP[t] * v["SDE"][t] / 100

    # Nominal GDP
    GDPMPS[t] = TFEPS - MPS[t] + SDEPS[t]

    # GDP add-factor
    v["MGDPNSA"][t] = GDPMPS[t] + v["MGDPNSA_A"][t]

    # Taxes less subsidies on products
    BPAPS = v["BPAPS"]
    BPAPS[t] = (
        (v["CETAX"][t] - v["BETPRF"][t]) + v["EXDUTAC"][t] + v["XLAVAT"][t]
        + v["LAVAT"][t] + v["TSD"][t] + v["TXMIS"][t] + v["ROCS"][t]
        - (v["EUSUBP"][t] + v["LASUBP"][t] + v["CGSUBP"][t] + v["CCLACA"][t])
        + v["BANKROLL"][t] + v["BLEVY"][t]
    )

    # GVA at basic prices (current prices)
    v["GVAPS"][t] = GDPMPS[t] - BPAPS[t]

    # TFE volume
    TFE = CGG[t] + CONS[t] + DINV[t] + VAL[t] + IF[t] + X[t]
    v["TFE"][t] = TFE

    # Taxes less subsidies (volume proxy)
    BPA[t] = BPA[t - 1] * (GDPM[t] / max(GDPM[t - 1], 1e-10))

    # GVA volume
    GVA[t] = GDPM[t] - BPA[t]

    # GVA deflator
    v["PGVA"][t] = 100 * v["GVAPS"][t] / max(GVA[t], 1e-10)

    # Production taxes and subsidies
    v["TPRODPS"][t] = (
        v["NNDRA"][t] + v["NIS"][t] + v["VEDCO"][t] + v["OPT"][t] + v["LAPT"][t]
        + v["EUETS"][t] - v["CGSUBPR"][t] - v["LASUBPR"][t] - v["EUSUBPR"][t]
    )

    # Statistical discrepancy (volume)
    v["SDI"][t] = v["SDI"][t - 1]

    # Gross operating surplus
    OS = (
        GDPMPS[t] - v["FYEMP"][t] - v["MI"][t] - BPAPS[t]
        - v["TPRODPS"][t] - v["SDI"][t]
    )
    v["OS"][t] = OS

    # Rental income
    v["RENTCO"][t] = v["RENTCO"][t - 1] * (GDPMPS[t] / max(GDPMPS[t - 1], 1e-10))

    # Imputed rent
    POP16 = v["POP16"][t]
    PRENT = v["PRENT"][t]
    v["IROO"][t] = (PRENT * POP16) / 1000

    # Household operating surplus (including imputed rent)
    DIPHHmf = v["DIPHHmf"][t]
    v["OSHH"][t] = 12874 + 0.85 * v["IROO"][t] - DIPHHmf

    # FISIM
    v["FISIMGG"][t] = 0.0
    v["FISIMPS"][t] = (
        v["DIRHHf"][t] + v["DIPHHuf"][t] + DIPHHmf
        + v["DIRICf"][t] + v["DIPICf"][t]
        + v["FISIMGG"][t] + v["FISIMROW"][t]
    )

    # Corporate profits
    FISIMPS = v["FISIMPS"][t]
    OSGG = v["OSGG"][t]
    OSPC = v["OSPC"][t]
    OSHH = v["OSHH"][t]
    RENTCO = v["RENTCO"][t]
    SA = v["SA"][t]
    v["FYCPR"][t] = OS - OSHH - OSGG - OSPC - RENTCO + SA - FISIMPS

    v["OSCO"][t] = OS - OSHH - OSGG - OSPC

    # Trading profits components
    NNSGTP = v["NNSGTP"][t] if "NNSGTP" in v._data else 0.0
    NSGTP = v["NSGTP"][t]
    v["GTPFC"][t] = v["FYCPR"][t] - NNSGTP - NSGTP

    # Financial corporations FISIM
    v["FC"][t] = FISIMPS + v["GTPFC"][t]

    # Gross national income
    v["GNIPS"][t] = (
        GDPMPS[t] + v["NIPD"][t]
        + (v["EECOMPC"][t] - v["EECOMPD"][t])
        + (v["EUSUBPR"][t] + v["EUSUBP"][t])
        - (v["EUOT"][t] + v["EUVAT"][t])
    )

    # Non-North Sea GVA
    NSGVA = v["NSGVA"][t]
    v["NNSGVA"][t] = GVA[t] - NSGVA

    # Output gap
    TRGDP = v["TRGDP"][t]
    v["GAP"][t] = GDPM[t] / max(TRGDP, 1e-10) * 100 - 100

    # Per-capita output
    POPAL = v["POPAL"][t]
    v["GDPMAL"][t] = GDPM[t] / max(POPAL, 1e-10)
    v["TRGDPAL"][t] = TRGDP / max(POPAL, 1e-10)
    POP16_v = v["POP16"][t]
    v["GDPM16"][t] = GDPM[t] / max(POP16_v, 1e-10)
    v["TRGDP16"][t] = TRGDP / max(POP16_v, 1e-10)

    # Government GVA
    CGWS = v["CGWS"][t]
    LAWS = v["LAWS"][t]
    OSGG_v = OSGG
    v["GGVAPS"][t] = CGWS + LAWS + OSGG_v

    # Market sector GVA
    v["MSGVAPS"][t] = v["GVAPS"][t] - v["GGVAPS"][t]
    v["GGVA"][t] = v["GGVA"][t - 1] * (CGG[t] / max(v["CGG"][t - 1], 1e-10))
    v["MSGVA"][t] = GVA[t] - v["GGVA"][t]

    # GDP deflator
    PGDP[t] = 100 * GDPMPS[t] / max(GDPM[t], 1e-10)
