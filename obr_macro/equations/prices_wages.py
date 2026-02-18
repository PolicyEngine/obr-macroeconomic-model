"""Group 7: Prices and wages equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def _base_avg(v: Variables, name: str) -> float:
    """Average of a variable over 2009."""
    return (
        v.elem(name, "2009Q1") + v.elem(name, "2009Q2")
        + v.elem(name, "2009Q3") + v.elem(name, "2009Q4")
    ) / 4


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    PMSGVA = v["PMSGVA"]
    PSAVEI = v["PSAVEI"]
    LFSUR = v["LFSUR"]
    MSGVA = v["MSGVA"]
    EMS = v["EMS"]
    CPI = v["CPI"]
    EMPSC = v["EMPSC"]
    WFP = v["WFP"]
    PBRENT = v["PBRENT"]
    RXD = v["RXD"]
    BPAPS = v["BPAPS"]
    GVA = v["GVA"]
    PPIY = v["PPIY"]
    ULCMS = v["ULCMS"]
    PMNOG = v["PMNOG"]
    PMS = v["PMS"]
    PXNOG = v["PXNOG"]
    PXS = v["PXS"]
    PCE = v["PCE"]
    RX = v["RX"]

    # --- Wages: private sector average weekly earnings ---
    if t >= 4:
        OILBASE = _base_avg(v, "OILBASE") if "OILBASE" in v._data else 1.0
        ULCPSBASE = _base_avg(v, "ULCPS") if "ULCPS" in v._data else 1.0
        ULCMSBASE = _base_avg(v, "ULCMS") if "ULCMS" in v._data else 1.0
        PMNOGBASE = _base_avg(v, "PMNOG") if "PMNOG" in v._data else 1.0
        PMSBASE = _base_avg(v, "PMS") if "PMS" in v._data else 1.0
        TXRATEBASE = (
            (v.elem("BPAPS", "2009Q1") / v.elem("GVA", "2009Q1")
             + v.elem("BPAPS", "2009Q2") / v.elem("GVA", "2009Q2")
             + v.elem("BPAPS", "2009Q3") / v.elem("GVA", "2009Q3")
             + v.elem("BPAPS", "2009Q4") / v.elem("GVA", "2009Q4")) / 4
        )
        PPIYBASE = _base_avg(v, "PPIY") if "PPIY" in v._data else 1.0
        CPIXBASE = _base_avg(v, "CPIX") if "CPIX" in v._data else 1.0

        # Store bases
        v["OILBASE"][t] = OILBASE
        v["ULCPSBASE"][t] = ULCPSBASE
        v["ULCMSBASE"][t] = ULCMSBASE
        v["PMNOGBASE"][t] = PMNOGBASE
        v["PMSBASE"][t] = PMSBASE
        v["TXRATEBASE"][t] = TXRATEBASE
        v["PPIYBASE"][t] = PPIYBASE
        v["CPIXBASE"][t] = CPIXBASE

        # AWE equation (PSAVEI)
        NIS = v["NIS"][t]
        dlog_PSAVEI = (
            -0.0282
            + 0.575 * (np.log(PMSGVA[t]) - np.log(PMSGVA[t - 1]))
            + 0.250 * (np.log(PMSGVA[t - 1]) - np.log(PMSGVA[t - 2]))
            + 0.105 * (np.log(PMSGVA[t - 2]) - np.log(PMSGVA[t - 3]))
            + (1 - 0.575 - 0.250 - 0.105) * (np.log(PMSGVA[t - 3]) - np.log(PMSGVA[t - 4]))
            - 0.0096 * (LFSUR[t] - LFSUR[t - 1])
            + 0.264 * ((np.log(MSGVA[t]) - np.log(EMS[t])) - (np.log(MSGVA[t - 1]) - np.log(EMS[t - 1])))
            + 0.282 * ((np.log(CPI[t]) - np.log(PMSGVA[t])) - (np.log(CPI[t - 1]) - np.log(PMSGVA[t - 1])))
            - 0.04328 * (
                np.log(PSAVEI[t - 1])
                - np.log(max(MSGVA[t - 1] / max(EMS[t - 1], 1e-10), 1e-10))
                - np.log(max(PMSGVA[t - 1], 1e-10))
                + np.log(1 + (EMPSC[t - 1] / max(WFP[t - 1], 1e-10)))
                + 0.0137 * LFSUR[t - 1]
            )
        )
        PSAVEI[t] = PSAVEI[t - 1] * np.exp(dlog_PSAVEI)

    # Earnings derived variables
    ETLFS = v["ETLFS"]
    ESLFS = v["ESLFS"]
    v["EARN"][t] = WFP[t] / max(ETLFS[t] - ESLFS[t], 1e-10)
    PGVA = v["PGVA"][t]
    v["RPW"][t] = (v["FYEMP"][t] / max(PGVA, 1e-10)) / max(ETLFS[t] - ESLFS[t], 1e-10)
    v["RCW"][t] = (v["FYEMP"][t] / max(PCE[t], 1e-10)) / max(ETLFS[t] - ESLFS[t], 1e-10)

    # Unit labour costs
    MSGVAPSEMP = v["MSGVAPS"][t] - v["MI"][t]
    v["MSGVAPSEMP"][t] = MSGVAPSEMP
    FYEMPMS = v["FYEMP"][t] - v["CGWS"][t] - v["LAWS"][t]
    v["FYEMPMS"][t] = FYEMPMS

    ULCMS_val = 100 * 1.6715 * FYEMPMS * (1 + (v["MI"][t] / max(MSGVAPSEMP, 1e-10))) / max(MSGVA[t], 1e-10)
    ULCMS[t] = ULCMS_val

    # Cost indices (using 2009 bases)
    if t >= 4:
        OILBASE = v["OILBASE"][t]
        ULCMSBASE = v["ULCMSBASE"][t]
        PMNOGBASE = v["PMNOGBASE"][t]
        PMSBASE = v["PMSBASE"][t]
        TXRATEBASE = v["TXRATEBASE"][t]
        PPIYBASE = v["PPIYBASE"][t]

        oil_ratio = (PBRENT[t] / RXD[t]) / max(OILBASE, 1e-10)
        tx_ratio = (BPAPS[t] / max(GVA[t], 1e-10)) / max(TXRATEBASE, 1e-10)
        ulcms_ratio = ULCMS_val / max(ULCMSBASE, 1e-10)
        pmnog_ratio = PMNOG[t] / max(PMNOGBASE, 1e-10)
        pms_ratio = PMS[t] / max(PMSBASE, 1e-10)
        ppiy_ratio = PPIY[t] / max(PPIYBASE, 1e-10)

        SCOST = v["SCOST"]
        CCOST = v["CCOST"]
        UTCOST = v["UTCOST"]

        # Iterative cost block (simultaneous) - use lagged values for simultaneity
        scost_prev = SCOST[t - 1] / 100
        ccost_prev = CCOST[t - 1] / 100
        utcost_prev = UTCOST[t - 1] / 100

        SCOST_val = (
            70.54 * ulcms_ratio + 6.93 * pmnog_ratio + 6.41 * pms_ratio
            + 0.09 * oil_ratio + 3.52 * tx_ratio
            + 9.78 * ppiy_ratio + 1.64 * ccost_prev + 1.09 * utcost_prev
        )
        CCOST_val = (
            40.25 * ulcms_ratio + 2.80 * pmnog_ratio + 0.90 * pms_ratio
            + 0.03 * oil_ratio + 0.51 * tx_ratio
            + 27.06 * ppiy_ratio + 28.13 * scost_prev + 0.34 * utcost_prev
        )
        UTCOST_val = (
            14.85 * ulcms_ratio + 3.04 * pmnog_ratio + 0.51 * pms_ratio
            + 51.52 * oil_ratio + 2.90 * tx_ratio
            + 8.24 * ppiy_ratio + 16.00 * scost_prev + 2.95 * ccost_prev
        )
        MCOST_val = (
            36.83 * ulcms_ratio + 24.64 * pmnog_ratio + 4.04 * pms_ratio
            + 4.85 * oil_ratio + 1.01 * tx_ratio
            + 24.72 * (SCOST_val / 100) + 0.47 * (CCOST_val / 100) + 3.43 * (UTCOST_val / 100)
        )
        RPCOST_val = (
            13.18 * pmnog_ratio + 4.07 * pms_ratio
            + 11.56 * tx_ratio + 7.07 * ppiy_ratio
            + 59.96 * (SCOST_val / 100) + 0.92 * (CCOST_val / 100) + 3.24 * (UTCOST_val / 100)
        )
        ICOST_val = (
            18.40 * pmnog_ratio + 0.41 * pms_ratio + 0.19 * oil_ratio
            + 5.63 * ((BPAPS[t] / max(MSGVA[t], 1e-10)) / max(TXRATEBASE, 1e-10))
            + 8.18 * ppiy_ratio + 20.76 * (SCOST_val / 100) + 46.42 * (CCOST_val / 100)
        )
        XGCOST_val = (
            15.77 * pmnog_ratio
            + 2.92 * ((BPAPS[t] / max(MSGVA[t], 1e-10)) / max(TXRATEBASE, 1e-10))
            + 68.46 * ppiy_ratio + 12.80 * (SCOST_val / 100) + 0.05 * (UTCOST_val / 100)
        )
        XSCOST_val = (
            7.22 * pms_ratio
            + 5.99 * ((BPAPS[t] / max(MSGVA[t], 1e-10)) / max(TXRATEBASE, 1e-10))
            + 9.29 * ppiy_ratio + 75.39 * (SCOST_val / 100) + 1.90 * (CCOST_val / 100) + 0.21 * (UTCOST_val / 100)
        )

        v["SCOST"][t] = SCOST_val
        v["CCOST"][t] = CCOST_val
        v["UTCOST"][t] = UTCOST_val
        v["MCOST"][t] = MCOST_val
        v["RPCOST"][t] = RPCOST_val
        v["ICOST"][t] = ICOST_val
        v["XGCOST"][t] = XGCOST_val
        v["XSCOST"][t] = XSCOST_val

        # Manufacturing output price markup
        v["MKGW"][t] = 100 * (PPIY[t] / (MCOST_val / 100)) / PPIYBASE

    # --- Retail prices ---
    W1 = v["W1"][t]
    W4 = v["W4"][t]
    W5 = v["W5"][t]

    if t >= 1 and "RPCOST" in v._data and v["RPCOST"][t] > 0:
        RPCOST = v["RPCOST"][t]
        CPIRENT = v["CPIRENT"]
        dlog_MKR = (
            (np.log(CPI[t]) - np.log(CPI[t - 1])
             - W1 * (np.log(CPIRENT[t]) - np.log(CPIRENT[t - 1]))
             - (1 - W1) * (np.log(RPCOST) - np.log(v["RPCOST"][t - 1])))
            / max(1 - W1, 1e-10)
        )
        v["MKR"][t] = v["MKR"][t - 1] * np.exp(dlog_MKR)

        CPIXBASE = v["CPIXBASE"][t]
        v["CPIX"][t] = (RPCOST / 100) * (v["MKR"][t] / 100) * CPIXBASE

    # Rental prices
    HRRPW = v["HRRPW"]
    PRP = v["PRENT"]
    PRENT = v["PRENT"]
    earnings_ratio = (WFP[t] / max(ETLFS[t] - ESLFS[t], 1e-10)) / max(WFP[t - 1] / max(ETLFS[t - 1] - ESLFS[t - 1], 1e-10), 1e-10)
    PRENT[t] = PRENT[t - 1] * (
        0.62 * earnings_ratio
        + 0.15 * (HRRPW[t] / max(HRRPW[t - 1], 1e-10))
        + 0.23 * (PRP[t - 1] / max(PRP[t - 2] if t >= 2 else PRP[t - 1], 1e-10))
    )

    # CPIH (includes owner-occupier housing costs)
    OOH = v["OOH"]
    v["CPIH"][t] = v["CPIH"][t - 1] * (
        (CPI[t] ** (1 - W5)) * (OOH[t] ** W5)
    ) / max(((CPI[t - 1] ** (1 - W5)) * (OOH[t - 1] ** W5)), 1e-10)

    v["CPIRENT"][t] = v["CPIRENT"][t - 1] * (
        0.62 * earnings_ratio
        + 0.15 * (HRRPW[t] / max(HRRPW[t - 1], 1e-10))
        + 0.23 * (PRP[t - 1] / max(PRP[t - 2] if t >= 2 else PRP[t - 1], 1e-10))
    )

    # Mortgage payments index
    LHP = v["LHP"]
    GPW = v["GPW"]
    RMORT = v["RMORT"]
    RDEP = v["RDEP"]
    TPBRZ = v["TPBRZ"]
    HH = v["HH"]
    PRMIP = v["PRMIP"]
    v["RHF"][t] = RMORT[t] - (1 - 0.25 * TPBRZ[t]) * (RMORT[t] - RDEP[t]) * (1 - 0.001 * LHP[t] / max(GPW[t], 1e-10))
    v["HD"][t] = v["HD"][t - 1] * (v["APH"][t] / max(v["APH"][t - 1], 1e-10))
    v["PRMIP"][t] = (PRMIP[t - 1] * (RMORT[t] / max(RMORT[t - 1], 1e-10)) * (LHP[t] / max(LHP[t - 1], 1e-10))) / max(HH[t] / max(HH[t - 1], 1e-10), 1e-10)
    v["PRMIP"][t] += v["PRMIP_A"][t]  # add-factor

    # RPI
    PR = v["PR"]
    I7 = v["I7"][t]
    I9 = v["I9"][t]
    I4 = v["I4"][t]
    PRXMIP = v["PRXMIP"][t]
    PR[t] = I7 * ((1 - W4) * PRXMIP / max(I9, 1e-10) + W4 * PRMIP[t] / max(I4, 1e-10))
    v["RPI"][t] = PR[t] / max(PR[t - 4], 1e-10) * 100 - 100

    # Export and import prices
    WPG = v["WPG"]
    if t >= 2:
        dlog_PXNOG = (
            0.635957 * (np.log(PPIY[t - 1]) - np.log(PPIY[t - 2]))
            + 0.102727 * ((np.log(WPG[t]) - np.log(RXD[t])) - (np.log(WPG[t - 1]) - np.log(RXD[t - 1])))
            - 0.131253 * (np.log(RX[t]) - np.log(RX[t - 1]))
            - 0.000508 * v.trend(t, "1979Q4")
            + 0.100860 * v.date_equals(t, "1997Q1")
            - 0.063293 * v.date_equals(t, "1998Q1")
            + 0.034519 * v.date_equals(t, "1993Q1")
            - 0.161370 * (
                np.log(PXNOG[t - 1])
                + 0.330293 * np.log(RX[t - 1])
                - 0.921258 * np.log(max(PPIY[t - 1], 1e-10))
                - (1 - 0.921258) * np.log(max(WPG[t - 1] / max(RXD[t - 1], 1e-10), 1e-10))
            )
            + 0.297153
        )
        v["PXNOG"][t] = PXNOG[t - 1] * np.exp(dlog_PXNOG)
    else:
        v["PXNOG"][t] = PXNOG[t - 1]

    v["PXS"][t] = v["PXS"][t - 1] * (v["PXNOG"][t] / max(PXNOG[t - 1], 1e-10))

    if t >= 2:
        dlog_PMNOG = (
            0.606452 * (np.log(PPIY[t]) - np.log(PPIY[t - 1]))
            + 0.230808 * ((np.log(WPG[t]) - np.log(RXD[t])) - (np.log(WPG[t - 1]) - np.log(RXD[t - 1])))
            - 0.106493 * (np.log(RX[t]) - np.log(RX[t - 1]))
            + 0.066665 * v.date_equals(t, "1997Q1")
            - 0.038986 * v.date_equals(t, "1998Q1")
            - 0.000538 * v.trend(t, "1979Q4")
            - 0.160709 * (
                np.log(PMNOG[t - 1])
                + 0.139917 * np.log(RX[t - 1])
                - 0.552396 * np.log(max(PPIY[t - 1], 1e-10))
                - (1 - 0.552396) * np.log(max(WPG[t - 1] / max(RXD[t - 1], 1e-10), 1e-10))
            )
            + 0.183135
        )
        v["PMNOG"][t] = PMNOG[t - 1] * np.exp(dlog_PMNOG)
    else:
        v["PMNOG"][t] = PMNOG[t - 1]

    v["PMS"][t] = v["PMS"][t - 1] * (v["PMNOG"][t] / max(v["PMNOG"][t - 1], 1e-10))

    # Other price deflators
    INV = v["INV"]
    BV = v["BV"]
    v["PINV"][t] = 100 * BV[t] / max(INV[t], 1e-10)
    v["PCE"][t] = PCE[t - 4] * (CPI[t] / max(CPI[t - 4], 1e-10))

    # Investment deflator (residual)
    GDPMPS = v["GDPMPS"]
    CGGPS = v["CGGPS"]
    CONSPS = v["CONSPS"]
    DINVPS = v["DINVPS"]
    VALPS = v["VALPS"]
    XPS = v["XPS"]
    MPS = v["MPS"]
    SDEPS = v["SDEPS"]
    IF = v["IF"]
    v["PIF"][t] = (
        (GDPMPS[t] - CGGPS[t] - CONSPS[t] - DINVPS[t] - VALPS[t] - XPS[t] + MPS[t] - SDEPS[t])
        * 100 / max(IF[t], 1e-10)
    )

    v["PCDUR"][t] = v["PCDUR"][t - 1] * (v["PMNOG"][t] / max(v["PMNOG"][t - 1], 1e-10))

    # Market sector GVA deflator
    v["PMSGVA"][t] = 100 * (v["MSGVAPS"][t] / max(v["MSGVA"][t], 1e-10))
