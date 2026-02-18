"""Group 6: Imports of goods and services."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    CONS = v["CONS"]
    CGG = v["CGG"]
    IF = v["IF"]
    XS = v["XS"]
    XOIL = v["XOIL"]
    XNOG = v["XNOG"]
    M = v["M"]
    PMNOG = v["PMNOG"]
    PMS = v["PMS"]
    PMOIL = v["PMOIL"]
    PCE = v["PCE"]
    GGFCD = v["GGFCD"]
    PIF = v["PIF"]
    PINV = v["PINV"]
    PXNOG = v["PXNOG"]

    DINV = v["DINV"][t]
    ALAD = v["ALAD"][t]

    # Import content of each expenditure component
    MC = 0.257 * CONS[t]
    MCGG = 0.094 * CGG[t]
    MIF = 0.234 * IF[t]
    MDINV = 0.106 * (DINV - ALAD)
    MXS = 0.142 * XS[t]
    MXG = 0.376 * (XOIL[t] + XNOG[t])

    MTFE = MC + MCGG + MIF + MDINV + MXS + MXG
    v["MTFE"][t] = MTFE

    v["MINTY"][t] = 100 * M[t] / max(MTFE, 1e-10)

    # Goods import demand
    MGTFE = (
        0.176 * CONS[t]
        + 0.064 * CGG[t]
        + 0.175 * IF[t]
        + 0.094 * DINV
        + 0.410 * XNOG[t]
        + 0.049 * XS[t]
    )
    v["MGTFE"][t] = MGTFE

    # Relative goods import price
    PMGREL = PMNOG[t] / max(
        0.156 * PCE[t] + 0.097 * GGFCD[t] + 0.203 * PIF[t] + 0.096 * PINV[t] + 0.352 * PXNOG[t] + 0.063 * v["PXS"][t],
        1e-10,
    )
    v["PMGREL"][t] = PMGREL

    # Non-oil goods imports (residual)
    v["MNOG"][t] = M[t] - v["MS"][t] - v["MOIL"][t]

    # Services import demand total
    MSTFE = (
        0.081 * CONS[t]
        + 0.030 * CGG[t]
        + 0.059 * IF[t]
        + 0.012 * DINV
        + 0.029 * XNOG[t]
        + 0.093 * XS[t]
    )
    v["MSTFE"][t] = MSTFE

    # Relative services import price
    PMSREL = PMS[t] / max(
        0.060 * PCE[t] + 0.040 * GGFCD[t] + 0.067 * PIF[t] + 0.040 * PINV[t] + 0.024 * PXNOG[t] + 0.098 * v["PXS"][t],
        1e-10,
    )
    v["PMSREL"][t] = PMSREL

    # Services imports (dynamic equation)
    if t >= 4:
        SPECX = v["SPECX"][t]
        dlog_MS = (
            0.819114 * (np.log(MSTFE) - np.log(v["MSTFE"][t - 1]))
            + 0.389511 * (np.log(v["MSTFE"][t - 1]) - np.log(v["MSTFE"][t - 2]))
            - 0.525436 * (np.log(v["MSTFE"][t - 2]) - np.log(v["MSTFE"][t - 3]))
            + 0.288639 * (np.log(v["MSTFE"][t - 3]) - np.log(v["MSTFE"][t - 4]))
            - 0.477411 * (np.log(PMSREL) - np.log(v["PMSREL"][t - 1]))
            - 0.292804 * (np.log(v["PMSREL"][t - 1]) - np.log(v["PMSREL"][t - 2]))
            - 0.271392 * (np.log(v["MS"][t - 1]) - np.log(v["MS"][t - 2]))
            - 0.171294 * (
                np.log(v["MS"][t - 1])
                - 1.079017 * np.log(v["MSTFE"][t - 1])
                - 0.662445 * np.log(max(SPECX, 1e-10))
                + 0.112661 * (v.date_gte(t - 1, "2007Q1") * SPECX)
                + 0.874335 * np.log(max(v["PMSREL"][t - 1], 1e-10))
                - 0.126418 * (v.date_gte(t - 1, "2007Q1") - v.date_gte(t - 1, "2013Q1"))
            )
            - 0.031665
        )
        v["MS"][t] = v["MS"][t - 1] * np.exp(dlog_MS)
    elif t >= 1:
        v["MS"][t] = v["MS"][t - 1]

    # Imports at current prices
    v["MPS"][t] = (
        v["MNOG"][t] * (PMNOG[t] / 100)
        + v["MS"][t] * (PMS[t] / 100)
        + v["MOIL"][t] * (PMOIL[t] / 100)
    )
