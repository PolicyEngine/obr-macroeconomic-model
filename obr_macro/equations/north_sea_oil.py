"""Group 8: North Sea oil equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    PBRENT = v["PBRENT"]
    RXD = v["RXD"]
    GDPMPS = v["GDPMPS"]
    BPAPS = v["BPAPS"]
    NSGVA = v["NSGVA"]
    NNSGVA = v["NNSGVA"]
    TDOIL = v["TDOIL"]
    XOIL = v["XOIL"]
    NSGTP = v["NSGTP"]

    OILBASE = v.elem("OILBASE", "2009Q1") if "OILBASE" in v._data else (
        (v.elem("PBRENT", "2009Q1") / v.elem("RXD", "2009Q1")
         + v.elem("PBRENT", "2009Q2") / v.elem("RXD", "2009Q2")
         + v.elem("PBRENT", "2009Q3") / v.elem("RXD", "2009Q3")
         + v.elem("PBRENT", "2009Q4") / v.elem("RXD", "2009Q4")) / 4
    )
    v["OILBASE"][t] = OILBASE

    # Oil trade volumes (dynamic equation)
    if t >= 2 and GDPMPS[t - 1] > 0 and GDPMPS[t - 2] > 0:
        # Domestic North Sea cost base (proxy)
        cost_t1 = (
            GDPMPS[t - 1] - BPAPS[t - 1]
            - (NSGVA[t - 1] * PBRENT[t - 1] / max(OILBASE * RXD[t - 1], 1e-10))
        ) / max(NNSGVA[t - 1], 1e-10)
        cost_t2 = (
            GDPMPS[t - 2] - BPAPS[t - 2]
            - (NSGVA[t - 2] * PBRENT[t - 2] / max(OILBASE * RXD[t - 2], 1e-10))
        ) / max(NNSGVA[t - 2], 1e-10)

        dlog_TDOIL = (
            -0.2444325 * (np.log(max(TDOIL[t - 1], 1e-10)) - np.log(max(TDOIL[t - 2], 1e-10)))
            + 1.896486 * (np.log(max(NNSGVA[t - 1], 1e-10)) - np.log(max(NNSGVA[t - 2], 1e-10)))
            - 0.1077816 * (
                np.log(max(PBRENT[t] / max(RXD[t] * cost_t1, 1e-10), 1e-10))
                - np.log(max(PBRENT[t - 1] / max(RXD[t - 1] * cost_t2, 1e-10), 1e-10))
            )
            + 0.0780697 * (v.date_gte(t, "1984Q1") * v.date_lte(t, "1985Q1"))
            - 0.0143727
            - 0.2216107 * (v.date_equals(t, "1986Q1") - v.date_equals(t, "1986Q2"))
            - 0.2457494 * (v.date_equals(t, "2001Q3") - v.date_equals(t, "2001Q4"))
            + 0.1907036 * (v.date_equals(t, "2010Q3") - v.date_equals(t, "2010Q4"))
            - 0.4334139 * v.date_equals(t, "2013Q1")
        )
        TDOIL[t] = TDOIL[t - 1] * np.exp(dlog_TDOIL)
    else:
        TDOIL[t] = TDOIL[t - 1]

    # Oil imports = trade + exports - North Sea output
    v["MOIL"][t] = TDOIL[t] + XOIL[t] - NSGVA[t]

    # Oil export/import prices
    v["PXOIL"][t] = PBRENT[t] / RXD[t]
    v["PMOIL"][t] = v["PXOIL"][t]

    # North Sea gross trading profit
    NSGTP[t] = NSGTP[t - 1] * (
        (NSGVA[t] / max(NSGVA[t - 1], 1e-10))
        * (PBRENT[t] / max(PBRENT[t - 1], 1e-10))
        / max(RXD[t] / max(RXD[t - 1], 1e-10), 1e-10)
    )
