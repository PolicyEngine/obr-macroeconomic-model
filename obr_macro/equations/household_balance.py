"""Group 18: Financial account and balance sheets - households, RoW, PNFC."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def _safe_log(x: float) -> float:
    return np.log(max(x, 1e-10))


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    # ------------------------------------------------------------------ #
    # Household balance sheet
    # ------------------------------------------------------------------ #

    # Rolling 4-quarter sum of household net acquisitions
    if t >= 4:
        NAFHH_sum = v["NAFHH"][t] + v["NAFHH"][t - 1] + v["NAFHH"][t - 2] + v["NAFHH"][t - 3]
        NAFHHNSA_sum = v["NAFHHNSA"][t - 1] + v["NAFHHNSA"][t - 2] + v["NAFHHNSA"][t - 3]
        v["NAFHHNSA"][t] = NAFHH_sum - NAFHHNSA_sum
    else:
        v["NAFHHNSA"][t] = v["NAFHH"][t]

    v["SDLHH"][t] = 0.0
    v["NLHH"][t] = v["NAFHHNSA"][t] - v["SDLHH"][t]

    NLHH = v["NLHH"][t]
    DEPHH = v["DEPHH"]
    PD = v["PD"]
    APH = v["APH"]
    CONSPS = v["CONSPS"]
    RDEP = v["RDEP"]
    R = v["R"]
    LFSUR = v["LFSUR"]

    # Gross mortgage-financed house price ratio
    v["GMF"][t] = (PD[t] * APH[t] * 0.858) / max(DEPHH[t - 1], 1e-10)

    # Household deposits (dynamic equation)
    GMF_val = v["GMF"][t]
    DEPHHx_prev = v["DEPHHx"][t - 1]
    d_DEPHHx = (
        3.9056 * (CONSPS[t] - CONSPS[t - 1])
        + np.exp(5.1811 * (RDEP[t] - R[t])) - np.exp(5.1811 * (RDEP[t - 1] - R[t - 1]))
        + np.exp(0.8206 * LFSUR[t]) - np.exp(0.8206 * LFSUR[t - 1])
        + np.exp(106.3011 * GMF_val)
        - 0.0369 * (
            DEPHH[t - 1]
            - 5.5399 * CONSPS[t - 1]
            - np.exp(0.8479 * RDEP[t - 1])
            - np.exp(1.0821 * LFSUR[t - 1])
            + 233379.6
        )
    )
    v["DEPHHx"][t] = DEPHHx_prev + d_DEPHHx
    DEPHH[t] = (v["DEPHHx"][t] - v["DEPHHx"][t - 1]) + v["DEPHHADJ"][t] + DEPHH[t - 1]

    # Net equity acquisition
    NAEQHHx = 0.4560 * NLHH - 12867
    v["NAEQHHx"][t] = NAEQHHx
    v["NAEQHH"][t] = NAEQHHx + v["NAEQHHADJ"][t]

    # Equity holdings
    EQPR = v["EQPR"]
    WEQPR = v["WEQPR"]
    RX = v["RX"]
    v["EQHH"][t] = (
        (1 + 0.844 * (EQPR[t] / max(EQPR[t - 1], 1e-10) - 1)
         + 0.156 * ((WEQPR[t] / max(WEQPR[t - 1], 1e-10)) / max(RX[t] / max(RX[t - 1], 1e-10), 1e-10) - 1))
        * v["EQHH"][t - 1]
        + v["NAEQHH"][t]
    )

    # Pension and insurance assets
    v["NAPEN"][t] = v["NEAHH"][t]

    NAINSx_prev = v["NAINSx"][t - 1]
    SIPT = v["SIPT"]
    NAINSx = 13293.71 + 0.627 * NAINSx_prev - 236267.3 * (SIPT[t - 3] if t >= 3 else SIPT[0])
    v["NAINSx"][t] = NAINSx
    v["NAINS"][t] = NAINSx + v["NAINSADJ"][t]

    RL = v["RL"]
    DBR = 1 / ((1 + (RL[t] / 100)) ** 15)
    v["DBR"][t] = DBR

    PIHH = v["PIHH"]
    PIHH[t] = (
        (1 + 0.200 * (EQPR[t] / max(EQPR[t - 1], 1e-10) - 1)
         + 0.098 * (RX[t - 1] / max(RX[t], 1e-10) - 1)
         + 0.170 * ((WEQPR[t] / max(WEQPR[t - 1], 1e-10)) / max(RX[t] / max(RX[t - 1], 1e-10), 1e-10) - 1)
         + 0.574 * (DBR / max(v["DBR"][t - 1], 1e-10) - 1))
        * PIHH[t - 1]
        + v["NAPEN"][t] + v["NAINS"][t]
    )

    # Other assets
    if t >= 2:
        GDPMPS = v["GDPMPS"]
        OAHHx_prev = v["OAHHx"][t - 1]
        dlog_OAHHx = (
            1.6091
            - 0.1607 * _safe_log(OAHHx_prev)
            + 0.0169 * _safe_log(GDPMPS[t - 1])
            - 0.57443 * (np.log(max(GDPMPS[t], 1e-10)) - np.log(max(GDPMPS[t - 1], 1e-10)))
            + 0.001796 * v.trend(t, "1986Q4")
        )
        v["OAHHx"][t] = OAHHx_prev * np.exp(dlog_OAHHx)
    else:
        v["OAHHx"][t] = v["OAHHx"][t - 1]

    v["OAHH"][t] = v["OAHH"][t - 1] + (v["OAHHx"][t] - v["OAHHx"][t - 1]) + v["OAHHADJ"][t]

    # Gross financial wealth
    v["GFWPE"][t] = DEPHH[t] + v["EQHH"][t] + PIHH[t] + v["OAHH"][t]

    # Other lending
    LHP = v["LHP"]
    OLPEx_prev = v["OLPEx"][t - 1]
    DEBTU_prev = v["DEBTU"][t - 1]
    NAOLPEx = OLPEx_prev * DEBTU_prev
    v["NAOLPEx"][t] = NAOLPEx

    STUDENT = v["STUDENT"]
    v["NAOLPE"][t] = NAOLPEx + (STUDENT[t] - STUDENT[t - 1]) + v["NAOLPEADJ"][t]

    DEBTU_new = (
        0.0812616
        + 0.4338504 * DEBTU_prev
        - 0.0248383 * _safe_log(OLPEx_prev)
        + 0.013581 * _safe_log(CONSPS[t - 1])
        - 0.0014364 * LFSUR[t - 1]
        + 0.0143662 * _safe_log(PD[t - 1])
    )
    v["DEBTU"][t] = DEBTU_new

    v["OLPEx"][t] = OLPEx_prev - 0.00219 * OLPEx_prev + NAOLPEx + v["NAOLPEADJ"][t]
    v["OLPE"][t] = v["OLPEx"][t] + STUDENT[t]

    # Balance sheet aggregates
    v["AAHH"][t] = (
        (v["OAHH"][t] - v["OAHH"][t - 1])
        + (DEPHH[t] - DEPHH[t - 1])
        + v["NAEQHH"][t] + v["NAPEN"][t] + v["NAINS"][t]
    )
    v["ALHH"][t] = v["NAOLPE"][t] + (LHP[t] - LHP[t - 1])

    HHRES = NLHH - (
        (v["DEPHHx"][t] - v["DEPHHx"][t - 1] + NAEQHHx + v["NAPEN"][t] + NAINSx + v["OAHHx"][t] - v["OAHHx"][t - 1])
        - (NAOLPEx + (STUDENT[t] - STUDENT[t - 1]) + (LHP[t] - LHP[t - 1]))
    )
    v["HHRES"][t] = HHRES
    v["OAHHADJ"][t] = HHRES - v["DEPHHADJ"][t] - v["NAEQHHADJ"][t] - v["NAINSADJ"][t] + v["NAOLPEADJ"][t]

    # Net financial wealth
    v["NFWPE"][t] = v["GFWPE"][t] - LHP[t] - v["OLPE"][t]

    # House prices (GPW proxy)
    v["GPW"][t] = 0.9933 * v["GPW"][t - 1] * (APH[t] / max(APH[t - 1], 1e-10)) + 0.001 * v["IHHPS"][t]

    # ------------------------------------------------------------------ #
    # Rest of world balance sheet
    # ------------------------------------------------------------------ #

    if t >= 4:
        NAFROW_sum = v["NAFROW"][t] + v["NAFROW"][t - 1] + v["NAFROW"][t - 2] + v["NAFROW"][t - 3]
        NAFROWNSA_sum = v["NAFROWNSA"][t - 1] + v["NAFROWNSA"][t - 2] + v["NAFROWNSA"][t - 3]
        v["NAFROWNSA"][t] = NAFROW_sum - NAFROWNSA_sum
    else:
        v["NAFROWNSA"][t] = v["NAFROW"][t]

    v["SDLROW"][t] = 0.0
    v["NLROW"][t] = v["NAFROWNSA"][t] - v["SDLROW"][t]

    NLROW = v["NLROW"][t]
    TFEPS = v["TFEPS"][t]
    ICCPS = v["ICCPS"][t]

    # Direct investment abroad
    d_DAROW = (
        (0.3813 * (v["XPS"][t] + v["MPS"][t]) / max(TFEPS, 1e-10) + 0.7067 * ICCPS / max(TFEPS, 1e-10) - 0.1872)
        * TFEPS
    )
    v["DAROW"][t] = v["DAROW"][t - 1] + d_DAROW

    # Rest of world equity holdings in UK
    EQPR_ratio = EQPR[t] / max(EQPR[t - 1], 1e-10)
    NAEQAROW_prev = v["NAEQAROW"][t - 1]

    EQAROW_prev = v["EQAROW"][t - 1]
    BAROW_prev = v["BAROW"][t - 1]
    EQAROW_4q = (v["EQAROW"][t - 1] + v["EQAROW"][t - 2] + v["EQAROW"][t - 3] + v["EQAROW"][t - 4]) / 4 if t >= 4 else v["EQAROW"][t - 1]
    BAROW_4q = (v["BAROW"][t - 1] + v["BAROW"][t - 2] + v["BAROW"][t - 3] + v["BAROW"][t - 4]) / 4 if t >= 4 else v["BAROW"][t - 1]

    AAROW = v["ALROW"][t] + NLROW
    v["AAROW"][t] = AAROW

    NAOTAROW = v["NAOTLROW"][t - 1] if t >= 1 else 0.0

    NAEQAROW = (
        EQAROW_4q / max(EQAROW_4q + BAROW_4q, 1e-10)
    ) * (AAROW - d_DAROW - NAOTAROW)
    v["NAEQAROW"][t] = NAEQAROW
    v["EQAROW"][t] = EQAROW_prev * EQPR_ratio + NAEQAROW

    RX_ratio = RX[t] / max(RX[t - 1], 1e-10)
    NABAROW = (
        BAROW_4q / max(EQAROW_4q + BAROW_4q, 1e-10)
    ) * (AAROW - d_DAROW - NAOTAROW)
    v["NABAROW"][t] = NABAROW
    v["BAROW"][t] = BAROW_prev * (0.40 / max(RX_ratio, 1e-10) + 0.60) + NABAROW

    NAOTAROW_new = NAOTAROW
    v["NAOTAROW"][t] = NAOTAROW_new
    OTAROW_prev = v["OTAROW"][t - 1]
    v["OTAROW"][t] = OTAROW_prev * (0.84 / max(RX_ratio, 1e-10) + 0.16) + NAOTAROW_new

    v["AROW"][t] = v["DAROW"][t] + v["EQAROW"][t] + v["BAROW"][t] + v["OTAROW"][t]

    # Rest of world liabilities (UK external assets)
    DLROW_prev = v["DLROW"][t - 1]
    LROW_prev_total = v["DLROW"][t - 1] + v["EQLROW"][t - 1] + v["BLROW"][t - 1] + v["OTLROW"][t - 1]
    EQLIC = v["EQLIC"][t]

    NADLROW = (
        DLROW_prev * (
            -0.0375
            - 0.2124 * DLROW_prev / max(LROW_prev_total, 1e-10)
            - 0.2004 * (v["FYCPR"][t - 1] + v["FISIMPS"][t - 1]) / max(EQLIC, 1e-10)
            + 0.1026 * WEQPR[t] / max(WEQPR[t - 1], 1e-10)
        )
    )
    v["NADLROW"][t] = NADLROW
    v["DLROW"][t] = DLROW_prev / max(RX_ratio, 1e-10) + NADLROW

    NAEQLROW = 0.196 * (v["NAINS"][t] + v["NAPEN"][t]) + 0.132 * v["NAEQHH"][t] + 0.003 * v["GDPMPS"][t]
    v["NAEQLROW"][t] = NAEQLROW
    v["EQLROW"][t] = v["EQLROW"][t - 1] * (WEQPR[t] / max(WEQPR[t - 1], 1e-10)) / max(RX_ratio, 1e-10) + NAEQLROW

    NABLROW = 0.17 * (v["NAINS"][t] + v["NAPEN"][t]) + 0.0325 * v["GDPMPS"][t]
    v["NABLROW"][t] = NABLROW
    v["BLROW"][t] = v["BLROW"][t - 1] / max(RX_ratio, 1e-10) + NABLROW

    NAOTLROW = v["OTLROW"][t - 1] * (v["GDPMPS"][t] / max(v["GDPMPS"][t - 1], 1e-10) - 1)
    v["NAOTLROW"][t] = NAOTLROW
    v["OTLROW"][t] = v["OTLROW"][t - 1] * (0.90 / max(RX_ratio, 1e-10) + 0.10) + NAOTLROW

    v["LROW"][t] = v["DLROW"][t] + v["EQLROW"][t] + v["BLROW"][t] + v["OTLROW"][t]
    v["ALROW"][t] = NADLROW + NAEQLROW + NABLROW + NAOTLROW - v["DRES"][t]

    # Net international investment position
    v["NIIP"][t] = v["NIIP"][t - 1] + (v["LROW"][t] - v["LROW"][t - 1]) + (v["SRES"][t] - v["SRES"][t - 1]) - (v["AROW"][t] - v["AROW"][t - 1])

    # ------------------------------------------------------------------ #
    # PNFC (private non-financial corporations) balance sheet
    # ------------------------------------------------------------------ #
    NALIC = -27362 + 1.513178 * v["IBUS"][t] * (v["PIF"][t] / 100)
    v["NALIC"][t] = NALIC

    v["NABLIC"][t] = 0.14 * NALIC
    v["BLIC"][t] = v["BLIC"][t - 1] + v["NABLIC"][t]

    v["STLIC"][t] = v["STLIC"][t - 1] + 0.09 * NALIC

    v["NAFXLIC"][t] = 0.07 * NALIC
    v["FXLIC"][t] = v["FXLIC"][t - 1] * (RX[t - 1] / max(RX[t], 1e-10)) + v["NAFXLIC"][t]

    FYCPR = v["FYCPR"][t]
    FISIMPS = v["FISIMPS"][t]
    EQLIC_prev = v["EQLIC"][t - 1]
    NAEQLIC = (
        (1.6035 + 0.9385 * EQLIC_prev / max(v["FYCPR"][t - 1] + v["FISIMPS"][t - 1], 1e-10))
        * (FYCPR + FISIMPS)
        - EQLIC_prev * v["GDPMPS"][t] / max(v["GDPMPS"][t - 1], 1e-10)
    )
    v["NAEQLIC"][t] = NAEQLIC
    v["EQLIC"][t] = EQLIC_prev * EQPR_ratio + NAEQLIC

    v["OLIC"][t] = v["OLIC"][t - 1] + 0.04 * NALIC
    v["LIC"][t] = v["BLIC"][t] + v["STLIC"][t] + v["FXLIC"][t] + v["EQLIC"][t] + v["OLIC"][t]

    # PNFC assets
    NAAIC = v["AIC"][t - 1] * (v["GDPMPS"][t] / max(v["GDPMPS"][t - 1], 1e-10) - 1)
    v["NAAIC"][t] = NAAIC
    v["AIC"][t] = v["AIC"][t - 1] + (NAAIC - (v["M4IC"][t] - v["M4IC"][t - 1]))

    v["NWIC"][t] = v["AIC"][t] - v["LIC"][t]
