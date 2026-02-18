"""Group 12: Public sector totals equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    # Central government current expenditure (residual)
    v["CGSUBP"][t] = (
        v["PSCE"][t]
        - (v["CGWS"][t] + v["CGP"][t] + v["RCGIM"][t] + v["LAWS"][t] + v["LAPR"][t] + v["RLAIM"][t])
        - v["LATSUB"][t]
        - (v["CGSB"][t] + v["LASBHH"][t])
        - v["CGNCGA"][t]
        - v["ECNET"][t]
        - v["LANCGA"][t]
        - (v["CGOTR"][t] + v["LAOTRHH"][t])
        - (v["DICGOP"][t] + v["DILAPR"][t] + v["DIPCOP"][t])
        - v["EUVAT"][t]
        - v["GNP4"][t]
        - v["CGSUBPR"][t]
    )

    # Depreciation
    v["DEP"][t] = v["RCGIM"][t] + v["RLAIM"][t] + v["PCCON"][t]

    # Public sector current balance
    v["PSCB"][t] = v["PSCR"][t] - v["PSCE"][t] - v["DEP"][t]

    # Smoothed capital transfers
    for name in ("NPACG", "NPALA"):
        arr = v[name]
        if t >= 4:
            arr[t] = (arr[t - 1] + arr[t - 2] + arr[t - 3] + arr[t - 4]) / 4
        else:
            arr[t] = arr[t - 1]

    # Public sector gross investment
    v["PSGI"][t] = (
        v["CGIPS"][t] + v["LAIPS"][t] + v["IPCPS"][t] + v["IBPC"][t]
        + v["DINVCG"][t]
        + (v["NPACG"][t] + v["NPALA"][t])
        + (v["KCGPSO"][t] - v["KPSCG"][t])
        + (v["KLA"][t] - v["KGLAPC"][t] - v["KGLA"][t])
        + (v["KPCPS"][t] - v["KPSPC"][t])
        + v["ASSETSA"][t]
    )

    # Total managed expenditure
    v["TME"][t] = v["PSCE"][t] + v["DEP"][t] + v["PSNI"][t]

    # Central government net borrowing (CGNB)
    v["CGNB"][t] = (
        (v["CGWS"][t] + v["CGP"][t]) + v["CGTSUB"][t] + v["CGSB"][t]
        + v["CGNCGA"][t] + v["CGCGLA"][t] + v["CGOTR"][t]
        + v["GNP4"][t] + v["EUVAT"][t] + v["DICGOP"][t]
        + (v["CGIPS"][t] + v["NPACG"][t]) + v["DINVCG"][t]
        + (v["KCGLA"][t] + v["KCGPC"][t]) + v["KCGPSO"][t] - v["KPSCG"][t]
        - (v["PUBSTIW"][t] + v["TYPCO"][t])
        - (v["PUBSTPD"][t] - v["LAPT"][t])
        - (v["OCT"][t] + v["LANNDR"][t])
        - (v["INHT"][t] + v["LAEPS"][t] + v["SWISSCAP"][t])
        - (v["EMPNIC"][t] + v["EENIC"][t])
        - v["CGNDIV"][t] - v["CGINTRA"][t]
        - (v["RNCG"][t] + v["HHTCG"][t] + v["BLEVY"][t])
    )

    # Local authority net borrowing (LANB)
    v["LANB"][t] = (
        (v["LAWS"][t] + v["LAPR"][t]) + v["LATSUB"][t] + v["LASBHH"][t]
        + v["LANCGA"][t] - v["CGCGLA"][t] + v["LAOTRHH"][t]
        + v["DILAPR"][t] + (v["LAIPS"][t] + v["NPALA"][t])
        - v["KCGLA"][t] + (v["KLA"][t] - v["KGLAPC"][t]) - v["KGLA"][t]
        - v["LAPT"][t] - (v["CC"][t] - v["LANNDR"][t]) - v["LAINTRA"][t]
        - v["LANDIV"][t] - v["LARENT"][t] - v["CIL"][t]
    )

    # General government net borrowing
    v["GGNB"][t] = v["CGNB"][t] + v["LANB"][t]
    v["GGNBCY"][t] = v["GGNB"][t]

    # Public corporations net borrowing
    v["PCNB"][t] = (
        v["DIPCOP"][t] + v["IPCPS"][t] + v["IBPC"][t]
        - (v["KCGPC"][t] + v["KGLAPC"][t])
        + (v["KPCPS"][t] - v["KPSPC"][t])
        + v["TYPCO"][t] - v["OSPC"][t]
        - v["PCNDIV"][t] - v["PCINTRA"][t] - v["PCRENT"][t]
    )
    v["PCNBCY"][t] = v["PCNB"][t]

    # Public sector net borrowing
    v["PSNBNSA"][t] = -v["PSCB"][t] + v["PSNI"][t]
    v["PSNBCY"][t] = v["PSNBNSA"][t] + v["PSNBCY_A"][t]

    # Treaty deficit
    v["SWAPS"][t] = 0.0
    v["TDEF"][t] = v["CGNB"][t] + v["LANB"][t] + v["SWAPS"][t]

    # Lending and financial transactions
    v["CGLSFA"][t] = (v["LCGOS"][t] + v["LCGPR"][t]) + v["CGMISP"][t]
    v["PSLSFA"][t] = v["CGLSFA"][t] + (v["LALEND"][t] + v["LAMISE"][t]) + (v["PCLEND"][t] + v["PCMISE"][t])

    # Accruals adjustments
    v["CGACADJ"][t] = (
        (v["EXDUTAC"][t] + v["NICAC"][t] + v["INCTAC"][t])
        + v["FCACA"][t] + v["CGACRES"][t]
        + (v["ILGAC"][t] + v["CONACC"][t]) + v["MFTRAN"][t]
    )
    v["PSACADJ"][t] = (
        v["CGACADJ"][t] + v["LAAC"][t] + v["LAMFT"][t]
        + v["PCAC"][t] + v["PCGILT"][t] + v["MFTPC"][t]
    )

    # Gilt financing
    v["PSFL"][t] = v["CGGILTS"][t] + v["OFLPS"][t] + v["NATSAV"][t] + v["MKTIG"][t]

    # Tangible assets
    if t >= 1:
        v["PSTA"][t] = (
            v["PSTA"][t - 1] * (v["PIF"][t] / max(v["PIF"][t - 1], 1e-10))
            + 0.5 * (v["PSNI"][t] + v["KCGPC"][t] + v["KGLAPC"][t] - v["KLA"][t] - v["KCGPSO"][t])
            * (1 + v["GGIDEF"][t] / max(v["GGIDEF"][t - 1], 1e-10))
        )

    v["PSNW"][t] = v["PSTA"][t] + v["PSFA"][t] - v["PSFL"][t]

    # Net cash requirement
    v["CGNCR"][t] = v["CGNB"][t] + v["CGLSFA"][t] + v["CGACADJ"][t] + v["LCGLA"][t] + v["LCGPC"][t]
    v["PSNCR"][t] = v["PSNBNSA"][t] + v["PSLSFA"][t] + v["PSACADJ"][t]

    # Currency in circulation
    if t >= 4:
        v["COIN"][t] = v["COIN"][t - 4] * (v["M0"][t] / max(v["M0"][t - 4], 1e-10))

    # Net public sector debt
    v["PSND"][t] = (
        v["PSND"][t - 1]
        + v["PSNCR"][t] - v["ILGAC"][t]
        + (v["FLEASGG"][t] - v["FLEASGG"][t - 1])
        + (v["FLEASPC"][t] - v["FLEASPC"][t - 1])
        + v["PSNDRES"][t]
    )

    # Liquidity
    v["GGLIQ"][t] = v["CGLIQ"][t] + v["LALIQ"][t]

    v["LABRO"][t] = v["LANB"][t] + v["LALEND"][t] + v["LAMISE"][t] + v["LAAC"][t] + v["LAGILT"][t] + v["LAMFT"][t] - v["LCGLA"][t]

    # General government gross debt
    v["GGGD"][t] = (
        v["GGGD"][t - 1]
        + v["CGNCR"][t]
        + v["LABRO"][t]
        - v["ILGAC"][t]
        + (v["SRES"][t] - v["SRES"][t - 1])
        + (v["GGLIQ"][t] - v["GGLIQ"][t - 1])
        + v["GGGDRES"][t]
    )
