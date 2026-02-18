"""Group 5: Exports of goods and services."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    X = v["X"]
    XS = v["XS"]
    XOIL = v["XOIL"]
    PXNOG = v["PXNOG"]
    RXD = v["RXD"]
    WPG = v["WPG"]
    PXS = v["PXS"]

    # Non-oil goods exports (residual)
    v["XNOG"][t] = X[t] - XS[t] - XOIL[t]

    # Relative export price
    if t >= 2:
        dlog_RPRICE = (
            (np.log(PXNOG[t]) - np.log(PXNOG[t - 1]))
            + (np.log(RXD[t]) - np.log(RXD[t - 1]))
            - 0.9351684 * (np.log(WPG[t]) - np.log(WPG[t - 1]))
        )
        v["RPRICE"][t] = v["RPRICE"][t - 1] * np.exp(dlog_RPRICE)
    else:
        v["RPRICE"][t] = v["RPRICE"][t - 1]

    # Exports at current prices
    v["XPS"][t] = (
        (PXNOG[t] / 100) * v["XNOG"][t]
        + (PXS[t] / 100) * XS[t]
        + (v["PXOIL"][t] / 100) * XOIL[t]
    )
