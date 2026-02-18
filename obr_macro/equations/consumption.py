"""Group 1: Consumption equations.

Translated from OBR EViews model code.
"""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    """Solve consumption equations for period t."""
    CONS = v["CONS"]
    RHHDI = v["RHHDI"]
    LFSUR = v["LFSUR"]
    GPW = v["GPW"]
    PCE = v["PCE"]
    NFWPE = v["NFWPE"]
    R = v["R"]
    CDUR = v["CDUR"]
    PCDUR = v["PCDUR"]
    PD = v["PD"]
    APH = v["APH"]

    if t < 1:
        return

    # --- CONS: Total consumer spending (real, chained) ---
    # dlog(CONS) = 0.2645906
    #   + 0.1029795 * dlog(RHHDI)
    #   - 0.0083736 * d(LFSUR)
    #   + 0.1269445 * dlog(GPW*1000 / (PCE/100))
    #   - 0.0004036 * d(R(-1) - ...)
    #   - 0.1250582 * ECM
    dlog_CONS = (
        0.2645906
        + 0.1029795 * (np.log(RHHDI[t]) - np.log(RHHDI[t - 1]))
        - 0.0083736 * (LFSUR[t] - LFSUR[t - 1])
        + 0.1269445 * (np.log(GPW[t] * 1000 / (PCE[t] / 100)) - np.log(GPW[t - 1] * 1000 / (PCE[t - 1] / 100)))
        - 0.0004036 * ((R[t - 1] - ((-1 + PCE[t - 1] / PCE[t - 5]) * 100)) - (R[t - 2] - ((-1 + PCE[t - 2] / PCE[t - 6]) * 100)))
        - 0.1250582 * (
            np.log(CONS[t - 1])
            - 0.4392933 * np.log(RHHDI[t - 1])
            - 0.1059181 * np.log(GPW[t - 1] * 1000 / (PCE[t - 1] / 100))
            - 0.2215558 * np.log(NFWPE[t - 1] / (PCE[t - 1] / 100))
        )
    )
    CONS[t] = CONS[t - 1] * np.exp(dlog_CONS)

    # CONSPS: Consumption at current prices (£m)
    v["CONSPS"][t] = CONS[t] * PCE[t] / 100

    # --- CDUR: Durable goods component ---
    if t >= 2:
        dlog_CDUR = (
            (np.log(CONS[t]) - np.log(CONS[t - 1]))
            - 0.6408491 * ((np.log(PCDUR[t]) - np.log(PCE[t])) - (np.log(PCDUR[t - 1]) - np.log(PCE[t - 1])))
            + 0.0378296 * (np.log(PD[t]) - np.log(PD[t - 1]))
            + 0.4517152 * (np.log(RHHDI[t]) - np.log(RHHDI[t - 1]))
            + 0.3438288 * (np.log(RHHDI[t - 1]) - np.log(RHHDI[t - 2]))
            - 0.0421498 * np.log(CDUR[t - 1] / CONS[t - 1])
            - 0.0145656 * np.log(
                max(1e-6, PCDUR[t - 1] * (((1 + R[t - 1] / 100) ** 0.25) - 1) + ((1.25 ** 0.25) - 1) - (PCDUR[t - 1] - PCDUR[t - 2]) / PCDUR[t - 1]) / 100
            )
            + 0.0313983 * np.log(NFWPE[t - 1] / (PCE[t - 1] / 100))
            - 0.6203775
            + 0.0636941 * (v.date_equals(t, "2009Q4") - v.date_equals(t, "2010Q1"))
        )
        CDUR[t] = CDUR[t - 1] * np.exp(dlog_CDUR)
    else:
        CDUR[t] = CDUR[t - 1]

    v["CDURPS"][t] = (PCDUR[t] / 100) * CDUR[t]

    # --- PD: House prices ---
    # dlog(PD) = dlog(GPW/APH) - 0.1278181 * log(PD(-1)/(GPW(-1)/APH(-1))) + ...
    dlog_PD = (
        (np.log(GPW[t] / APH[t]) - np.log(GPW[t - 1] / APH[t - 1]))
        - 0.1278181 * np.log(PD[t - 1] / (GPW[t - 1] / APH[t - 1]))
        + 1.54494 * ((np.log(APH[t]) - np.log(PCE[t])) - (np.log(APH[t - 1]) - np.log(PCE[t - 1])))
        + 0.2058841 * (v.date_equals(t, "1992Q3") - v.date_equals(t, "1992Q4"))
        + 0.340128 * v.date_equals(t, "2004Q1")
        + 0.1437075 * (v.date_equals(t, "2009Q4") - v.date_equals(t, "2010Q1"))
        + 0.2732277 * (v.date_equals(t, "2016Q1") - v.date_equals(t, "2016Q2"))
        + 0.2217687
    )
    PD[t] = PD[t - 1] * np.exp(dlog_PD)
