"""Group 3: Investment equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def _safe_log(x: float) -> float:
    return np.log(max(x, 1e-10))


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    R = v["R"]
    DISCO = v["DISCO"]
    TCPRO = v["TCPRO"]
    NDIV = v["NDIV"]
    DEBTW = v["DEBTW"]
    RDEP = v["RDEP"]

    # --- Net present value of allowances ---
    IIB = v["IIB"][t]
    SIB = v["SIB"][t]
    FP = v["FP"][t]
    SP = v["SP"][t]
    SV = v["SV"][t]

    disco = DISCO[t]
    if disco <= 0:
        disco = 0.05  # fallback

    DB = (1 / (1 + disco)) * (IIB + (SIB / disco) * (1 - (1 + disco) ** (-(1 - IIB) / max(SIB + 1e-10, 1e-10))))
    DP = (1 / (1 + disco)) * ((disco * FP + SP) / (disco + SP))
    DV = SV / (disco + SV)

    WB, WP, WV, WG = 0.31, 0.54, 0.14, 0.03

    TAFB = (1 - TCPRO[t] * DB) / max(1 - TCPRO[t], 1e-10)
    TAFP = (1 - TCPRO[t] * DP) / max(1 - TCPRO[t], 1e-10)
    TAFV = (1 - TCPRO[t] * DV) / max(1 - TCPRO[t], 1e-10)
    TAF = WB * TAFB + WP * TAFP + WV * TAFV
    v["TAF"][t] = TAF

    # Debt cost
    v["CDEBT"][t] = v["CDEBT"][t - 1] + (v["RIC"][t] - v["RIC"][t - 1])

    # Equity cost
    CEQUITY = NDIV[t] * (1 + WG) + 100 * WG
    v["CEQUITY"][t] = CEQUITY

    # Weighted average cost of capital
    RWACC = DEBTW[t] * v["CDEBT"][t] + (1 - DEBTW[t]) * CEQUITY
    v["RWACC"][t] = RWACC

    RDELTA = 0.022
    v["RDELTA"][t] = RDELTA

    # Cost of capital for business investment
    PIBUS = v["PIBUS"][t]
    PGDP = v["PGDP"][t]
    elem_pgdp = v.elem("PGDP", "1970Q1")
    elem_pibus = v.elem("PIBUS", "1970Q1")
    if elem_pgdp > 0 and elem_pibus > 0:
        COCU = (PIBUS / PGDP) * (elem_pgdp / elem_pibus) * (RDELTA + RWACC)
    else:
        COCU = RDELTA + RWACC
    COC = TAF * COCU
    v["COC"][t] = COC

    # Desired capital stock
    MSGVA = v["MSGVA"][t]
    KSTAR = np.exp(_safe_log(MSGVA) - 0.4 * _safe_log(max(COC, 1e-10)) + 2.434202655)
    v["KSTAR"][t] = KSTAR

    # Actual capital stock (perpetual inventory)
    IBUSX = v["IBUSX"][t]
    v["KMSXH"][t] = (IBUSX / 1000) + v["KMSXH"][t - 1] * (1 - RDELTA)

    # Capital gap
    v["KGAP"][t] = _safe_log(v["KMSXH"][t] * 1000) - _safe_log(KSTAR)

    # Tobin's Q
    NWIC = v["NWIC"][t]
    PKMSXHB = PIBUS
    v["PKMSXHB"][t] = PKMSXHB
    v["TQ"][t] = -(NWIC / 1000) / max(v["KMSXH"][t] * (PKMSXHB / 100), 1e-10)

    # Business investment
    GGIPS = v["CGIPS"][t] + v["LAIPS"][t]
    v["GGIPS"][t] = GGIPS
    GGI = 100 * GGIPS / max(v["GGIDEF"][t], 1e-10)
    v["GGI"][t] = GGI

    GGIX = GGI + 17394 * v.date_equals(t, "2005Q2")
    v["GGIX"][t] = GGIX

    v["GGIDEF"][t] = v["GGIDEF"][t - 1] * (v["PIF"][t] / max(v["PIF"][t - 1], 1e-10))

    IBUS = v["IF"][t] - GGI - v["PCIH"][t] - v["PCLEB"][t] - v["IH"][t] - v["IPRL"][t]
    v["IBUS"][t] = IBUS
    IBUSX_val = IBUS - 17394 * v.date_equals(t, "2005Q2")
    v["IBUSX"][t] = IBUSX_val

    # House improvement spending
    if t >= 2:
        dlog_HIMPROV = (
            -1.936849
            + 0.0467091 * (v["RMORT"][t] - v["RMORT"][t - 1])
            - 0.09652566 * (np.log(v["PD"][t - 1]) - np.log(v["PD"][t - 2]))
            - 0.5129925 * (np.log(v["HIMPROV"][t - 1]) - np.log(v["CONSPS"][t - 1]))
            - 0.0834384 * v.date_equals(t, "2003Q1")
        )
        v["HIMPROV"][t] = v["HIMPROV"][t - 1] * np.exp(dlog_HIMPROV)
    else:
        v["HIMPROV"][t] = v["HIMPROV"][t - 1]

    v["PCIH"][t] = v["PCIH"][t - 1] * (v["IH"][t] / max(v["IH"][t - 1], 1e-10))

    # Investment price identities
    v["VALPS"][t] = v["VAL"][t] * v["PIF"][t] / 100
    v["VALHH"][t] = 0.25 * v["VALPS"][t]
    v["IFPS"][t] = v["IF"][t] * v["PIF"][t] / 100
    v["PIPRL"][t] = 100 * v["IPRLPS"][t] / max(v["IPRL"][t], 1e-10)
    v["IHPS"][t] = v["IH"][t] * v["PIH"][t] / 100

    # Household investment deflator
    IHHPS_denom = (
        0.8456 * v["IHPS"][t - 1]
        + 0.5674 * v["IPRLPS"][t - 1]
        + 0.0803 * (v["PIBUS"][t - 1] / 100) * v["IBUS"][t - 1]
    )
    IHHPS_num = (
        0.8456 * v["IHPS"][t]
        + 0.5674 * v["IPRLPS"][t]
        + 0.0803 * (v["PIBUS"][t] / 100) * v["IBUS"][t]
    )
    if IHHPS_denom != 0:
        v["IHHPS"][t] = v["IHHPS"][t - 1] * (IHHPS_num / IHHPS_denom)
    else:
        v["IHHPS"][t] = v["IHHPS"][t - 1]

    # Business investment deflator
    PIBUS_val = (
        (v["IFPS"][t] - v["IHPS"][t] - v["IPRLPS"][t]
         - (v["PIF"][t] * 0.9828 / 100) * (v["PCIH"][t] + v["PCLEB"][t]) - GGIPS)
        * 100 / max(IBUS, 1e-10)
    )
    v["PIBUS"][t] = PIBUS_val

    v["ICCPS"][t] = 0.1543 * v["IHPS"][t] + 0.4204 * v["IPRLPS"][t] + 0.8331 * (PIBUS_val / 100) * IBUS
    v["IPCPS"][t] = (v["PIF"][t] * 0.9828 / 100) * (v["PCIH"][t] + v["PCLEB"][t]) + 0.0456 * (PIBUS_val / 100) * IBUS
    v["IFCPS"][t] = v["IFPS"][t] - v["IHHPS"][t] - v["ICCPS"][t] - v["LAIPS"][t] - v["CGIPS"][t] - v["IPCPS"][t]

    # Housing stock
    NETAD = (v["PEHC"][t] / 1000) * 1.5166
    v["NETAD"][t] = NETAD
    v["HSALL"][t] = v["HSALL"][t - 1] + NETAD
