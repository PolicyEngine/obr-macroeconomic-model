"""Group 15: Income account equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    WFP = v["WFP"]
    EMPSC = v["EMPSC"]
    ETLFS = v["ETLFS"]
    ESLFS = v["ESLFS"]
    PCE = v["PCE"]
    R = v["R"]
    RDEP = v["RDEP"]
    RL = v["RL"]
    RMORT = v["RMORT"]

    # Total wages and salaries
    PSAVEI = v["PSAVEI"][t]
    EMS = v["EMS"][t]
    ECG = v["ECG"][t]
    ELA = v["ELA"][t]
    CGWADJ = v["CGWADJ"][t]
    ERCG = v["ERCG"][t]
    LAWADJ = v["LAWADJ"][t]
    ERLA = v["ERLA"][t]

    WFP[t] = (
        v["ADJW"][t] * (52 / 4000) * PSAVEI * (EMS - ESLFS[t])
        + (52 / 4000) * CGWADJ * ERCG * ECG
        + (52 / 4000) * LAWADJ * ERLA * ELA
    )

    # Mixed income
    v["MI"][t] = v["MI"][t - 1] * (WFP[t] / max(WFP[t - 1], 1e-10))

    # Employers' social contributions
    HHISC = v["HHISC"]
    LASC = v["LASC"]
    CGISC = v["CGISC"]
    EMPISC = v["EMPISC"]

    EMPISC[t] = v["HHISC"][t] + LASC[t] + CGISC[t]
    v["EMPASC"][t] = EMPSC[t] - EMPISC[t]
    v["EMPISCPP"][t] = v["EMPISCPP"][t - 1] * (EMPISC[t] / max(EMPISC[t - 1], 1e-10))
    HHISC[t] = HHISC[t - 1] * (WFP[t] / max(WFP[t - 1], 1e-10))

    # Household social benefits
    v["HHSB"][t] = 2 * HHISC[t]
    v["OSB"][t] = v["OSB"][t - 1] * (PCE[t] / max(PCE[t - 1], 1e-10)) * (v["GAD3"][t] / max(v["GAD3"][t - 1], 1e-10))

    # Total household social benefits received
    SBHH_val = (
        EMPISC[t] + v["OSB"][t]
        + (v["HHSB"][t] - HHISC[t] - v["EMPISCPP"][t])
        + v["CGSB"][t] + v["LASBHH"][t]
        + v["EESCLA"][t] + v["EESCCG"][t] + v["CGASC"][t]
        - v["BENAB"][t]
    )
    v["SBHH"][t] = SBHH_val + v["SBHH_A"][t]

    # Household taxes
    v["TYWHH"][t] = v["TYEM"][t] + v["TSEOP"][t] + v["CC"][t] + v["CGT"][t] + v["OCT"][t] - v["NPISHTC"][t]
    v["TYWHH"][t] += v["TYWHH_A"][t]

    # Net miscellaneous transfers
    v["NMTRHH"][t] = v["LAOTRHH"][t] + (v["CGOTR"][t] - v["HHTCG"][t]) + (v["HHTFA"][t] - v["HHTA"][t]) + v["EUSF"][t] + 100

    # Investment income - households
    LHP = v["LHP"]
    OLPE = v["OLPE"]
    DEPHH = v["DEPHH"]
    M4IC = v["M4IC"]
    STLIC = v["STLIC"]
    FXLIC = v["FXLIC"]
    BLIC = v["BLIC"]

    # Mortgage interest payments
    DIPHHmf = LHP[t - 1] * ((1 + (RMORT[t] - R[t]) / 100) ** 0.25 - 1)
    v["DIPHHmf"][t] = DIPHHmf

    # Other household interest payments
    DIPHH = (LHP[t - 1] + OLPE[t - 1]) * ((1 + (0.9 * R[t] + 0.2) / 100) ** 0.25 - 1)
    v["DIPHH"][t] = DIPHH
    v["DIPHHx"][t] = DIPHH + DIPHHmf + v["DIPHHuf"][t]

    # Household deposit interest receipts
    DIRHHf = -(0.75 * DEPHH[t - 1] * ((1 + (RDEP[t] - R[t]) / 100) ** 0.25 - 1))
    v["DIRHHf"][t] = DIRHHf
    v["DIRHHx"][t] = v["DIRHH"][t] - DIRHHf

    # Institutional investment income (credits)
    DIRICf_prev = v["DIRICf"][t - 1]
    DIRICf_new = DIRICf_prev - (
        2.75 * M4IC[t - 1] * (((1 + (0.9 * R[t] - 0.2 - R[t]) / 100) ** 0.25) - 1)
        - 2.75 * M4IC[t - 2] * (((1 + (0.9 * R[t - 1] - 0.2 - R[t - 1]) / 100) ** 0.25) - 1) if t >= 2 else 0
    )
    v["DIRICf"][t] = DIRICf_new

    DIRIC_new = v["DIRIC"][t - 1] + (
        M4IC[t - 1] * (((1 + R[t] / 100) ** 0.25) - 1) - M4IC[t - 2] * (((1 + R[t - 1] / 100) ** 0.25) - 1) if t >= 2 else 0
    ) * 1.3 + (
        M4IC[t - 1] * (((1 + v["ROCB"][t] / 100) ** 0.25) - 1) - M4IC[t - 2] * (((1 + v["ROCB"][t - 1] / 100) ** 0.25) - 1) if t >= 2 else 0
    ) * 0.6
    v["DIRIC"][t] = DIRIC_new
    v["DIRICx"][t] = DIRIC_new - DIRICf_new

    # Institutional investment income (debits)
    RIC = v["RIC"]
    DIPICf_prev = v["DIPICf"][t - 1]
    DIPICf_new = DIPICf_prev + (
        STLIC[t - 1] * (((1 + (RIC[t] - R[t]) / 100) ** 0.25) - 1)
        + FXLIC[t - 1] * (((1 + 2.9 / 100) ** 0.25) - 1)
        - STLIC[t - 2] * (((1 + (RIC[t - 1] - R[t - 1]) / 100) ** 0.25) - 1) if t >= 2 else 0
        + FXLIC[t - 2] * (((1 + 2.9 / 100) ** 0.25) - 1) if t >= 2 else 0
    )
    v["DIPICf"][t] = DIPICf_new

    DIPIC_new = v["DIPIC"][t - 1] + (
        (STLIC[t - 1] * (((1 + R[t] / 100) ** 0.25) - 1) - (STLIC[t - 2] * (((1 + R[t - 1] / 100) ** 0.25) - 1) if t >= 2 else 0))
        + (FXLIC[t - 1] * (((1 + v["ROCB"][t] / 100) ** 0.25) - 1) - (FXLIC[t - 2] * (((1 + v["ROCB"][t - 1] / 100) ** 0.25) - 1) if t >= 2 else 0))
        + (BLIC[t - 1] * (((1 + RL[t] / 100) ** 0.25) - 1) - (BLIC[t - 2] * (((1 + RL[t - 1] / 100) ** 0.25) - 1) if t >= 2 else 0))
    ) if t >= 2 else v["DIPIC"][t - 1]
    v["DIPIC"][t] = DIPIC_new
    v["DIPICx"][t] = DIPIC_new + DIPICf_new

    # Windfall capital gains (corporations)
    v["WYQC"][t] = v["WYQC"][t - 1] * (v["FYCPR"][t] / max(v["FYCPR"][t - 1], 1e-10))

    # Dividends
    FYCPR = v["FYCPR"][t]
    CORP = v["CORP"][t]
    log_NDIVHH = -8.605599 + 0.8092696 * np.log(max(v["FYCPR"][t - 4] if t >= 4 else FYCPR, 1e-10)) + 0.6597959 * np.log(max(CORP, 1e-10))
    v["NDIVHH"][t] = np.exp(log_NDIVHH)

    # Household property income
    v["PIRHH"][t] = v["NDIVHH"][t] + v["APIIH"][t] + v["DIRHH"][t] + v["WYQC"][t]
    v["PIPHH"][t] = DIPHH

    # Occupational pension contributions
    PIHH = v["PIHH"]
    v["EECPP"][t] = (
        ((1 + (RL[t] / 100)) ** 0.25 - 1) * (PIHH[t - 1] * 0.729)
        + ((1 + 0.05) ** 0.25 - 1) * (PIHH[t - 1] * 0.271)
    )

    # Total employer social contributions
    EESC_val = v["EESCLA"][t] + v["EENIC"][t] + v["EECPP"][t] + v["EESCCG"][t]
    v["EESC"][t] = EESC_val + v["EESC_A"][t]

    # Household disposable income
    v["HHDI"][t] = (
        v["MI"][t] + v["FYEMP"][t] - EMPSC[t] - EESC_val
        - v["TYWHH"][t] + v["NMTRHH"][t] + SBHH_val
        + (v["PIRHH"][t] - v["PIPHH"][t] + v["FSMADJ"][t])
        - v["HHSB"][t] + HHISC[t]
        + (v["EECOMPC"][t] - v["EECOMPD"][t])
        + v["OSHH"][t]
    )
    v["RHHDI"][t] = 100 * v["HHDI"][t] / max(PCE[t], 1e-10)

    # Pension contributions
    v["EMPCPP"][t] = v["EMPCPP"][t - 1] * (WFP[t] / max(WFP[t - 1], 1e-10))

    # Net acquisitions of pension entitlements
    v["NEAHH"][t] = v["EMPCPP"][t] + v["EECPP"][t] + v["EMPISCPP"][t] - v["OSB"][t]

    # Household saving
    v["SVHH"][t] = v["HHDI"][t] + v["NEAHH"][t] - v["CONSPS"][t]
    v["SY"][t] = 100 * (v["SVHH"][t] / max(v["NEAHH"][t] + v["HHDI"][t], 1e-10))

    # Capital transfers
    v["KGHH"][t] = (
        -v["INHT"][t]
        + 0.95 * v["KLA"][t]
        + 0.55 * v["KCGPSO"][t]
        + 0.4 * v["EUKT"][t]
    )

    # Net acquisition of financial assets - households
    v["NAFHH"][t] = (
        v["SVHH"][t] + v["KGHH"][t] - v["DINVHH"][t]
        - v["VALHH"][t] - v["NPAHH"][t] - v["IHHPS"][t]
    )

    # Corporate sector
    v["NAFCO"][t] = (
        -v["NAFHH"][t] + v["CB"][t] + v["EUKT"][t]
        - v["CGKTA"][t] - v["OPSKTA"][t]
        + v["NPAA"][t] + v["SDEPS"][t] - v["SDI"][t]
        + v["PSNBCY"][t]
    )

    # Financial corporations
    v["NAFFC"][t] = -12012 + v["FISIMPS"][t] - v["NEAHH"][t] - v["BLEVY"][t]
    v["NAFIC"][t] = v["NAFCO"][t] - v["NAFFC"][t]

    # Corporate saving
    v["SAVCO"][t] = (
        v["NAFCO"][t] + v["KGHH"][t] - v["DINVHH"][t]
        + v["DINVPS"][t] - v["DINVCG"][t]
        + v["VALPS"][t] - v["VALHH"][t] - v["NPAHH"][t]
        + v["IFPS"][t] - v["IHHPS"][t] - v["NPACG"][t] - v["CGIPS"][t]
        - v["KLA"][t] - v["KCGPSO"][t] - v["LAIPS"][t] - v["NPALA"][t]
        + v["INHT"][t] + v["KGLA"][t] - v["EUKT"][t] + v["CGKTA"][t]
        + v["OPSKTA"][t] - v["NPAA"][t] - v["IPCPS"][t] - v["IBPC"][t]
    )
