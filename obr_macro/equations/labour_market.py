"""Group 4: Labour market equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    ECG = v["ECG"]
    ELA = v["ELA"]
    EGG = v["EGG"]
    ET = v["ET"]
    ETLFS = v["ETLFS"]
    ES = v["ES"]
    ESLFS = v["ESLFS"]
    GAD1 = v["GAD1"]
    GAD2 = v["GAD2"]
    GAD3 = v["GAD3"]
    POP16 = v["POP16"]
    ULFS = v["ULFS"]
    LFSUR = v["LFSUR"]
    HWA = v["HWA"]
    AVH = v["AVH"]
    MSGVA = v["MSGVA"]
    PSAVEI = v["PSAVEI"]
    PMSGVA = v["PMSGVA"]
    WRGTP = v["WRGTP"]

    # Central government employment tracks general government employment
    ECG[t] = ECG[t - 1] * (EGG[t] / max(EGG[t - 1], 1e-10))

    # Local authority employment tracks general government
    ELA[t] = ELA[t - 1] * (EGG[t] / max(EGG[t - 1], 1e-10))

    # Private sector employment identity
    v["EPS"][t] = ET[t] - ECG[t] - ELA[t]

    # Market sector employment (dynamic equation)
    if t >= 3:
        dlog_EMS = (
            -0.0113474
            + 0.4369834 * (np.log(v["EMS"][t - 1]) - np.log(v["EMS"][t - 2]))
            + 0.1932386 * (np.log(v["EMS"][t - 2]) - np.log(v["EMS"][t - 3]))
            + 0.1713792 * (np.log(MSGVA[t - 1]) - np.log(MSGVA[t - 2]))
            - 0.0062207 * (np.log(v["EMS"][t - 1]) - np.log(MSGVA[t - 1]) + 0.4 * (np.log(PSAVEI[t - 1]) - np.log(PMSGVA[t - 1])))
            - 0.0103188 * v.date_equals(t, "2010Q4")
        )
        v["EMS"][t] = v["EMS"][t - 1] * np.exp(dlog_EMS)
    else:
        v["EMS"][t] = v["EMS"][t - 1]

    # Total employment tracks LFS-based measure
    ET[t] = ET[t - 1] * (ETLFS[t] / max(ETLFS[t - 1], 1e-10))

    # Workforce-related aggregates
    WRGTP[t] = WRGTP[t - 1] * (ET[t] / max(ET[t - 1], 1e-10))
    v["WFJ"][t] = ET[t] + WRGTP[t]

    # LFS employment (hours basis)
    v["ETLFS"][t] = 1000 * (HWA[t] / max(AVH[t], 1e-10))

    # Self-employment
    ES[t] = ES[t - 1] * (ET[t] / max(ET[t - 1], 1e-10))
    ESLFS[t] = ESLFS[t - 1] * (ES[t] / max(ES[t - 1], 1e-10))

    # Demographics
    v["GAD"][t] = GAD1[t] + GAD2[t] + GAD3[t]
    POP16[t] = POP16[t - 1] * ((GAD2[t] + GAD3[t]) / max(GAD2[t - 1] + GAD3[t - 1], 1e-10))

    # Unemployment
    ULFS[t] = (POP16[t] * v["PART16"][t] / 100) - ETLFS[t]
    LFSUR[t] = 100 * ULFS[t] / max(ETLFS[t] + ULFS[t], 1e-10)

    # Productivity
    v["PRODH"][t] = v["GDPM"][t] / max(HWA[t], 1e-10)

    # Participation and employment rates
    v["PART16"][t] = 100 * (ULFS[t] + ETLFS[t]) / max(POP16[t], 1e-10)
    v["ER"][t] = 100 * ETLFS[t] / max(POP16[t], 1e-10)
