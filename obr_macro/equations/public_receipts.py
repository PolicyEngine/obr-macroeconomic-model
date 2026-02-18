"""Group 10: Public sector receipts equations."""

from __future__ import annotations

from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    # Corporation tax
    v["CT"][t] = v["NSCTP"][t] + v["NNSCTP"][t]

    # Customs and excise taxes
    v["CETAX"][t] = (
        v["VREC"][t] + v["TXFUEL"][t] + v["TXTOB"][t] + v["TXALC"][t]
        + v["CUST"][t] + v["CCL"][t] + v["AL"][t] + v["TXCUS"][t]
    )

    # Vehicle excise duty
    v["VED"][t] = v["VEDHH"][t] + v["VEDCO"][t]

    # Other current taxes
    v["OCT"][t] = v["VEDHH"][t] + v["BBC"][t] + v["PASSPORT"][t] + v["OHT"][t]

    # Capital gains tax (linked to bond yields)
    if t >= 1:
        ROCB = v["ROCB"][t]
        ROCB_tm1 = v["ROCB"][t - 1]
        CGC_tm1 = v["CGC"][t - 1]
        v["CGC"][t] = CGC_tm1 + 0.21 * (ROCB - ROCB_tm1) * CGC_tm1

    # Property income from public sector investments
    v["PSINTR"][t] = v["CGNDIV"][t] + v["LANDIV"][t] + v["PCNDIV"][t]

    # Government rental income
    v["CGRENT"][t] = v["RNCG"][t] + v["HHTCG"][t]

    # Tax credits
    v["TAXCRED"][t] = v["MILAPM"][t] + v["CTC"][t]

    # Income tax gross
    v["INCTAXG"][t] = (
        v["TYEM"][t] + v["TSEOP"][t] + v["TCINV"][t]
        - v["INCTAC"][t] + v["CTC"][t] - v["NPISHTC"][t]
    )

    # Public sector income/wealth taxes
    v["PUBSTIW"][t] = (
        v["TYEM"][t] + v["TSEOP"][t] + v["PRT"][t] + v["TCINV"][t]
        + v["CT"][t] + v["CGT"][t] + v["FCACA"][t]
        + v["BETPRF"][t] + v["BETLEVY"][t] + v["OFGEM"][t]
        - v["NPISHTC"][t] - v["TYPCO"][t] + v["PROV"][t] - v["LAEPS"][t]
    )

    # Taxes on production and imports
    v["PUBSTPD"][t] = (
        (v["CETAX"][t] - v["BETPRF"][t]) + v["EXDUTAC"][t] + v["XLAVAT"][t]
        + v["LAVAT"][t] - v["EUOT"][t] + v["TSD"][t] + v["ROCS"][t]
        + v["TXMIS"][t] + v["RFP"][t]
        + (v["NNDRA"][t] + v["VEDCO"][t] + v["LAPT"][t] + v["OPT"][t] + v["EUETS"][t])
        + v["CIL"][t] + v["ENVLEVY"][t] + v["BANKROLL"][t] + v["RULC"][t]
    )

    # Total public sector current receipts
    v["PSCR"][t] = (
        v["PUBSTIW"][t] + v["PUBSTPD"][t] + v["OCT"][t] + v["CC"][t]
        + v["INHT"][t] + v["EENIC"][t] + v["EMPNIC"][t]
        + (RCGIM := v["RCGIM"][t]) + v["RLAIM"][t] + v["OSPC"][t]
        + v["PSINTR"][t] + (v["RNCG"][t] + v["HHTCG"][t])
        + v["LARENT"][t] + v["PCRENT"][t] + v["BLEVY"][t]
        + v["LAEPS"][t] + v["SWISSCAP"][t]
    )

    # National taxes
    v["NATAXES"][t] = (
        v["PUBSTIW"][t] + v["PUBSTPD"][t] + v["OCT"][t]
        + v["BLEVY"][t] + v["INHT"][t] + v["LAEPS"][t]
        + v["SWISSCAP"][t] + v["EENIC"][t] + v["EMPNIC"][t]
        + v["CC"][t] + v["EUOT"][t]
    )
