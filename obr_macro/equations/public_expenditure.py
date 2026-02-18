"""Group 9: Public expenditure equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    # Central government wage bill
    CGWADJ = v["CGWADJ"][t]
    ERCG = v["ERCG"][t]
    ECG = v["ECG"][t]
    EMPSC = v["EMPSC"][t]
    WFP = v["WFP"][t]

    v["CGWS"][t] = CGWADJ * ERCG * ECG * (52 / 4000) * (1 + (1.249 * EMPSC / max(WFP, 1e-10)))

    # Local authority wage bill
    LAWADJ = v["LAWADJ"][t]
    ERLA = v["ERLA"][t]
    ELA = v["ELA"][t]

    v["LAWS"][t] = LAWADJ * ERLA * ELA * (52 / 4000) * (1 + (1.418 * EMPSC / max(WFP, 1e-10)))

    # Operating surplus of general government
    RCGIM = v["RCGIM"][t]
    RLAIM = v["RLAIM"][t]
    v["OSGG"][t] = RCGIM + RLAIM + 100

    # Government consumption (current spending)
    CGGPSPSF = v["CGGPSPSF"][t]
    LAPR = v["LAPR"][t]
    v["CGP"][t] = CGGPSPSF - (v["CGWS"][t] + v["LAWS"][t]) - LAPR - (RCGIM + RLAIM)

    # Government consumption deflator
    CGGPS = v["CGGPS"][t]
    CGG = v["CGG"][t]
    v["GGFCD"][t] = 100 * CGGPS / max(CGG, 1e-10)

    # Government consumption volume (dynamic equation)
    if t >= 2:
        dlog_CGG = (
            0.0007011
            + 0.3739498 * (np.log(CGGPS) - np.log(v["CGGPS"][t - 1]))
            + 0.1802323 * (np.log(v["CGGPS"][t - 1]) - np.log(v["CGGPS"][t - 2]))
            - 0.4198339 * (np.log(CGG) - np.log(v["CGG"][t - 1]))
        )
        v["CGG"][t] = v["CGG"][t - 1] * np.exp(dlog_CGG)

    # Subsidies
    CGSUBP = v["CGSUBP"][t]
    CGSUBPR = v["CGSUBPR"][t]
    v["CGTSUB"][t] = CGSUBP + CGSUBPR

    # Local authority subsidy (indexed to GDP deflator)
    if t >= 5:
        PGDP = v["PGDP"]
        v["LASUBPR"][t] = (
            (v["LASUBPR"][t - 4] + v["LASUBPR"][t - 3] + v["LASUBPR"][t - 2] + v["LASUBPR"][t - 1]) * 0.25
            * (PGDP[t] * 4) / max(PGDP[t - 4] + PGDP[t - 3] + PGDP[t - 2] + PGDP[t - 1], 1e-10)
        )

    LASUBP = v["LASUBP"][t]
    v["LATSUB"][t] = LASUBP + v["LASUBPR"][t]

    # Cost-indexed spending aggregates
    CGWS_t = v["CGWS"][t]
    CGWS_tm1 = v["CGWS"][t - 1]

    v["CGASC"][t] = v["CGASC"][t - 1] * (CGWS_t / max(CGWS_tm1, 1e-10))
    v["CGISC"][t] = v["CGISC"][t - 1] * (CGWS_t / max(CGWS_tm1, 1e-10))
    v["EESCCG"][t] = v["EESCCG"][t - 1] * (CGWS_t / max(CGWS_tm1, 1e-10))

    LAWS_t = v["LAWS"][t]
    LAWS_tm1 = v["LAWS"][t - 1]

    v["LASC"][t] = v["LASC"][t - 1] * (LAWS_t / max(LAWS_tm1, 1e-10))
    v["EESCLA"][t] = v["EESCLA"][t - 1] * (LAWS_t / max(LAWS_tm1, 1e-10))

    # Non-cash charge
    v["CGNCGA"][t] = v["TROD"][t]
