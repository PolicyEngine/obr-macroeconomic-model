"""Group 11: Balance of payments equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    RX = v["RX"]
    RXD = v["RXD"]

    # Exchange rate
    RXD[t] = RXD[t - 1] * (RX[t] / max(RX[t - 1], 1e-10))

    # Euro/pound rate
    v["ECUPO"][t] = v["ECUPO"][t - 1] * (RX[t] / max(RX[t - 1], 1e-10))

    # Reserve change (exogenous)
    v["DRES"][t] = 0.0

    # Sterling reserves (valuation effects)
    v["SRES"][t] = (
        -v["DRES"][t]
        + (1 + 0.227 * (RXD[t - 1] / max(RXD[t], 1e-10) - 1) + 0.364 * (RX[t - 1] / max(RX[t], 1e-10) - 1))
        * v["SRES"][t - 1]
    )

    # Current-price investment income debits and credits
    LROW = v["LROW"][t - 2] if t >= 2 else v["LROW"][t - 1]
    LROW_tm1 = v["LROW"][t - 1]
    AROW = v["AROW"][t - 2] if t >= 2 else v["AROW"][t - 1]
    AROW_tm1 = v["AROW"][t - 1]

    WEQPR = v["WEQPR"]
    R = v["R"]
    ROCB = v["ROCB"]
    ROLT = v["ROLT"]
    RL = v["RL"]

    DLROW = v["DLROW"][t - 1]
    EQLROW = v["EQLROW"][t - 1]
    BLROW = v["BLROW"][t - 1]
    OTLROW = v["OTLROW"][t - 1]
    LROW_prev = DLROW + EQLROW + BLROW + OTLROW

    REXC = (
        (DLROW / max(LROW_prev, 1e-10)) * (1.24 + 1.91 * (np.log(max(WEQPR[t], 1e-10)) - np.log(max(WEQPR[t - 4], 1e-10))) + 0.57 * R[t] / 4)
        + (EQLROW / max(LROW_prev, 1e-10)) * (0.41 + 0.17 * (np.log(max(WEQPR[t], 1e-10)) - np.log(max(WEQPR[t - 4], 1e-10))))
        + (BLROW / max(LROW_prev, 1e-10)) * (0.30 + 0.82 * ROLT[t] / 4)
        + (OTLROW / max(LROW_prev, 1e-10)) * (0.09 + 0.8 * ROCB[t] / 4)
    )
    v["REXC"][t] = REXC

    v["CIPD"][t] = (
        0.7173 * v["CIPD"][t - 1] / max(LROW, 1e-10)
        + (1 - 0.7173) * REXC / 100
    ) * LROW_tm1

    DAROW = v["DAROW"][t - 1]
    EQAROW = v["EQAROW"][t - 1]
    BAROW = v["BAROW"][t - 1]
    OTAROW = v["OTAROW"][t - 1]
    AROW_prev = DAROW + EQAROW + BAROW + OTAROW

    FYCPR = v["FYCPR"][t]
    GDPMPS = v["GDPMPS"][t]
    NDIVHH = v["NDIVHH"][t]
    EQHH = v["EQHH"][t - 1] if t >= 1 else 1.0

    REXD = (
        (DAROW / max(AROW_prev, 1e-10)) * (0.62 + 2.36 * FYCPR / max(GDPMPS, 1e-10) - 1.64 * v.date_equals(t, "1998Q3"))
        + (EQAROW / max(AROW_prev, 1e-10)) * (0.57 + 15.33 * NDIVHH / max(EQHH, 1e-10))
        + (BAROW / max(AROW_prev, 1e-10)) * (0.23 + 1.04 * RL[t] / 4)
        + (OTAROW / max(AROW_prev, 1e-10)) * (0.18 + 0.14 * R[t] / 4 + 0.78 * ROCB[t] / 4)
    )
    v["REXD"][t] = REXD

    v["DIPD"][t] = (
        0.6283 * v["DIPD"][t - 1] / max(AROW, 1e-10)
        + (1 - 0.6283) * REXD / 100
    ) * AROW_tm1

    # Capital gain/loss on public debt
    CGC_tm1 = v["CGC"][t - 1]
    v["CGCBOP"][t] = v["CGCBOP"][t - 1] + (v["CGC"][t] - CGC_tm1) / max(CGC_tm1, 1e-10) * v["CGCBOP"][t - 1]

    # Net investment income
    v["NIPD"][t] = v["CIPD"][t] - v["DIPD"][t] + v["CGCBOP"][t]

    # Employee compensation (cross-border)
    if t >= 1:
        dlog_EECOMPD = (
            -0.492198 * np.log(max(v["EECOMPD"][t - 1], 1e-10))
            + 0.693337 * np.log(max(v["FYEMP"][t - 1], 1e-10))
            + 2.148955 * (np.log(max(v["FYEMP"][t], 1e-10)) - np.log(max(v["FYEMP"][t - 1], 1e-10)))
            + 0.107609 * v.date_gte(t, "2005Q1")
            - 0.004629 * v.trend(t, "1979Q4")
            - 5.105951
        )
        v["EECOMPD"][t] = v["EECOMPD"][t - 1] * np.exp(dlog_EECOMPD)

    MAJGDP = v["MAJGDP"]
    v["EECOMPC"][t] = v["EECOMPC"][t - 1] * (MAJGDP[t] / max(MAJGDP[t - 1], 1e-10))

    # EU transfers (exogenous post-Brexit)
    v["EUSUBP"][t] = 0.0
    v["EUSUBPR"][t] = v["EUSUBPR"][t - 1] * (v["ECUPO"][t - 1] / max(v["ECUPO"][t], 1e-10))
    v["EUSF"][t] = v["EUSF"][t - 1] * (v["ECUPO"][t - 1] / max(v["ECUPO"][t], 1e-10))
    v["ECNET"][t] = (1 - 0.5 * (v["ECUPO"][t - 1] / max(v["ECUPO"][t], 1e-10) - 1)) * v["ECNET"][t - 1]

    # EU contributions
    ECUPO4 = v["ECUPO"][t - 4] if t >= 4 else v["ECUPO"][0]
    v["GNP4"][t] = 0.010 * ((v["GDPMPS"][t] + v["NIPD"][t] + v["EECOMPC"][t] - v["EECOMPD"][t]) / max(ECUPO4, 1e-10))
    v["EUVAT"][t] = 0.0325 * v["VREC"][t] / max(0.8267 * ECUPO4, 1e-10)

    # Benefits abroad
    v["BENAB"][t] = 0.012 * v["CGSB"][t]

    # International transfers
    ITA = 0.001115 * v["WFP"][t]
    v["ITA"][t] = ITA
    v["CGITFA"][t] = ITA

    v["HHTFA"][t] = v["HHTFA"][t - 1] * (MAJGDP[t] / max(MAJGDP[t - 1], 1e-10))
    v["HHTA"][t] = v["HHTA"][t - 1] * (v["WFP"][t] / max(v["WFP"][t - 1], 1e-10))

    # Current transfers
    v["TRANC"][t] = (
        v["EUSUBP"][t] + v["HHTFA"][t] + v["EUSF"][t]
        + v["CGITFA"][t] + v["EUSUBPR"][t] + v["INSURE"][t]
    )
    v["TRAND"][t] = (
        v["TROD"][t] + v["ECNET"][t] + v["EUVAT"][t] + v["EUOT"][t]
        + v["HHTA"][t] + v["GNP4"][t] + v["BENAB"][t] + ITA + v["INSURE"][t]
    )
    v["TRANB"][t] = v["TRANC"][t] - v["TRAND"][t]

    # Capital transfers from government
    v["CGKTA"][t] = 0.02351 * v["KCGPSO"][t]

    # Trade balances
    v["TB"][t] = v["XPS"][t] - v["MPS"][t]
    v["CB"][t] = (
        v["TB"][t]
        + (v["EECOMPC"][t] - v["EECOMPD"][t])
        + v["NIPD"][t]
        + v["TRANC"][t] - v["TRAND"][t]
    )
    v["CBPCNT"][t] = (v["CB"][t] / max(v["GDPMPS"][t], 1e-10)) * 100

    # Net acquisition of foreign assets
    v["NAFROW"][t] = -(
        v["CB"][t] + v["EUKT"][t]
        - (v["CGKTA"][t] + v["OPSKTA"][t])
        + v["NPAA"][t]
    )
