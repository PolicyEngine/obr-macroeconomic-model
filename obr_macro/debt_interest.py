"""Opt-in debt-interest overlay for ``run_reform(..., debt_interest=True)``.

In the OBR's listing central government debt interest ``DICGOP`` has no
equation (variable list: exogenous). It enters only as an input to the
spending residual (l.504) and to central government net borrowing (l.524).
The debt stocks ``PSND`` and ``GGGD`` (l.567, l.571) are first-difference
equations with no level history in the databank, so they are dropped. A
reform that changes borrowing, or the gilt rate, therefore leaves debt
interest exactly where the data put it.

The OBR forecasts debt interest outside the macro model, by financing
component: an effective interest rate on each outstanding stock, with new
issuance priced at market rates (Economic and fiscal outlook, detailed
forecast tables 6.12, 6.16 and 6.17, committed under ``obr_macro/_data``).
This overlay applies that approach to conventional gilts only, in deviation
form (shocked run minus baseline), because the levels are not in the model:

- **Stock effect.** Each quarter's extra central government borrowing
  (the change in ``CGNB``, including the extra interest itself) is financed
  by a gilt issued at that quarter's gilt yield ``RL`` (the EFO's 20-year
  yield, table 1.9, which is the column obr_macro/data.py loads) and pays
  that coupon from then on.
- **Rate effect.** If the gilt yield itself is shocked, the gilts the EFO
  already plans to issue (table 6.12, conventional gilts: redemptions being
  refinanced plus the cash requirement) are issued at the changed yield. The
  existing stock keeps its coupons.

A gilt issued during a quarter pays half a quarter's interest in that quarter
(issuance spread evenly through it) and a full quarter's after.

The extra interest is added to ``DICGOP`` and to public sector current
expenditure ``PSCE`` by the same amount. ``PSCE`` is imposed in the listing
and subsidies are its residual (l.504), so moving ``DICGOP`` alone would cut
subsidies one for one, leave public sector borrowing unchanged and move
profits through ``BPAPS`` (l.695).

It is a labelled judgement overlay, not model dynamics. Nothing in the
listing links debt interest received to household or company income, so the
overlay adds no GDP or consumption effect: both are the same with the flag
on or off. That is not the same as GDP not moving. A gilt-yield shock moves
GDP through the listing's own l.649 (employees' contributions to funded
pension schemes ``EECPP`` scale with ``RL``), with or without the overlay.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Conventional gilt issuance, GBP bn per fiscal year: the "Conventional
# gilts" line of EFO table 6.12 (total gross financing). October 2026 EFO for
# 2026-27 onwards; 2025-26 is an outturn year there, so it is taken from the
# November 2025 EFO. tests/test_debt_interest.py re-reads both workbooks.
CONVENTIONAL_GILT_ISSUANCE_BN = {
    "2025-26": 270.64,
    "2026-27": 224.78,
    "2027-28": 274.19,
    "2028-29": 267.94,
    "2029-30": 214.24,
    "2030-31": 251.06,
    "2031-32": 286.05,
}
CONVENTIONAL_GILT_ISSUANCE_SOURCE = {
    "2025-26": "OBR EFO November 2025, detailed forecast table 6.12",
    "default": "OBR EFO October 2026, detailed forecast table 6.12",
}

# The legs moved by the same cash amount (see the module docstring).
DEBT_INTEREST_LEGS = ("DICGOP", "PSCE")

# Financing components the overlay does not move, and why.
DEBT_INTEREST_OFF = {
    "index-linked gilts": (
        "Their interest follows RPI (EFO table 6.17), and RPI has no link to "
        "CPI or to any shock in this model."
    ),
    "gilts held in the Asset Purchase Facility": (
        "Their net cost follows Bank Rate through the Bank of England's "
        "balance sheet, which the listing does not contain."
    ),
    "Treasury bills and NS&I": (
        "They reprice with short rates; no sourced pass-through from the "
        "gilt yield is in the repo."
    ),
    "gilt yield response to borrowing": (
        "RL stays on the EFO path unless the user shocks it; no sourced "
        "coefficient from borrowing to yields is in the repo."
    ),
    "maturity mix of new issuance": (
        "All new conventional issuance is priced at the 20-year yield. "
        "Against EFO table 6.16 that overstates interest on new gilts by "
        "5% to 13% a year (tests/test_debt_interest.py)."
    ),
}

DEBT_INTEREST_NOTE = (
    "Judgement overlay, not the shipped listing: central government debt "
    "interest (DICGOP) and public sector current expenditure (PSCE) are "
    "raised by the interest on the extra borrowing the reform causes, and, "
    "if the gilt yield RL is shocked, by the change in interest on the "
    "conventional gilts the EFO plans to issue (table 6.12). New gilts are "
    "priced at RL, the EFO's 20-year yield, in the quarter of issue, and pay "
    "half a quarter's interest in that quarter. The listing holds debt "
    "interest exogenous. Conventional gilts only: index-linked gilts, the "
    "Asset Purchase Facility, Treasury bills and NS&I are not moved, and "
    "the gilt yield does not respond to borrowing. Interest paid does not "
    "reach household or company income in the listing, so the overlay adds "
    "no GDP effect: GDP is the same with it on or off. A gilt-yield shock "
    "still moves GDP through the listing's own l.649 (EECPP scales with RL), "
    "with or without the overlay."
)


def fiscal_year(period) -> str:
    """UK fiscal year of a quarter: 2026Q2..2027Q1 -> '2026-27'."""
    p = pd.Period(str(period), freq="Q")
    first = p.year if p.quarter >= 2 else p.year - 1
    return f"{first}-{str(first + 1)[-2:]}"


def quarterly_gilt_issuance_m(periods) -> np.ndarray:
    """Planned conventional gilt issuance per quarter, GBP m (a quarter of the
    fiscal-year figure). A quarter outside the published years raises: the
    rate effect would otherwise be silently zero there."""
    out = []
    for p in periods:
        fy = fiscal_year(p)
        if fy not in CONVENTIONAL_GILT_ISSUANCE_BN:
            raise ValueError(
                f"debt_interest: no published conventional gilt issuance for "
                f"fiscal year {fy} (quarter {p}); table 6.12 covers "
                f"{min(CONVENTIONAL_GILT_ISSUANCE_BN)} to "
                f"{max(CONVENTIONAL_GILT_ISSUANCE_BN)}."
            )
        out.append(CONVENTIONAL_GILT_ISSUANCE_BN[fy] * 1000.0 / 4.0)
    return np.asarray(out, dtype=float)


def debt_interest_path(
    delta_borrowing_m, gilt_yield_pct, delta_gilt_yield_pp=None, issuance_m=None
) -> dict:
    """Extra debt interest per quarter, GBP m, from a borrowing and yield path.

    Args:
        delta_borrowing_m: change in central government net borrowing per
            quarter BEFORE any extra interest (shocked minus baseline).
        gilt_yield_pct: gilt yield in the shocked run, per cent a year.
        delta_gilt_yield_pp: change in the gilt yield (shocked minus
            baseline), percentage points. None or all zero: no rate effect.
        issuance_m: planned conventional gilt issuance per quarter, GBP m.
            Needed only if the yield changes.

    Returns a dict of per-quarter lists: ``stock_effect_m``,
    ``rate_effect_m``, ``delta_debt_interest_m`` (their sum) and
    ``cumulative_extra_debt_m`` (end of quarter, interest included).

    Cohorts: the gilt issued in quarter s pays its coupon from s onwards, half
    a quarter's worth in s itself. The extra interest is itself borrowed, so
    the stock effect compounds.
    """
    pre = np.asarray(delta_borrowing_m, dtype=float)
    k = np.asarray(gilt_yield_pct, dtype=float) / 400.0
    n = len(pre)
    if len(k) != n:
        raise ValueError("debt_interest: borrowing and yield paths differ in length")
    if not (np.all(np.isfinite(pre)) and np.all(np.isfinite(k))):
        raise ValueError("debt_interest: non-finite borrowing or gilt yield path")
    dk = np.zeros(n)
    if delta_gilt_yield_pp is not None:
        dk = np.asarray(delta_gilt_yield_pp, dtype=float) / 400.0
    rate = np.zeros(n)
    if np.any(dk != 0.0):
        if issuance_m is None:
            raise ValueError("debt_interest: a yield change needs issuance_m")
        g = np.asarray(issuance_m, dtype=float)
        coupons = g * dk  # quarterly interest change on each planned cohort
        rate = np.cumsum(coupons) - 0.5 * coupons
    stock = np.zeros(n)
    debt = np.zeros(n)
    carried = 0.0  # quarterly coupons on cohorts issued in earlier quarters
    total_debt = 0.0
    for t in range(n):
        # New cohort = pre[t] + rate[t] + stock[t]; it pays half of k[t] now.
        half = 0.5 * k[t]
        stock[t] = (carried + half * (pre[t] + rate[t])) / (1.0 - half)
        cohort = pre[t] + rate[t] + stock[t]
        carried += cohort * k[t]
        total_debt += cohort
        debt[t] = total_debt
    return {
        "stock_effect_m": stock.tolist(),
        "rate_effect_m": rate.tolist(),
        "delta_debt_interest_m": (stock + rate).tolist(),
        "cumulative_extra_debt_m": debt.tolist(),
    }


def apply_debt_interest(shocked, baseline_data, start, end, t_start, t_end):
    """Add the extra debt interest to the solved shocked run and re-solve.

    ``shocked`` must already be solved over [start, end]. Returns the final
    shocked data, its solve report and a detail dict for ``df.attrs``. The
    recursion is triangular (nothing else in the listing reads ``DICGOP``),
    so one re-solve is enough; ``residual_m`` in the detail is the largest
    gap between the re-solved change in ``CGNB`` and the path imposed.
    """
    window = slice(t_start, t_end + 1)
    for col in (*DEBT_INTEREST_LEGS, "CGNB", "RL"):
        if col not in shocked.data.columns:
            raise KeyError(f"debt_interest: {col} not in the databank")

    def _col(frame, col):
        return frame[col].astype(float).to_numpy()[window]

    pre = _col(shocked.data, "CGNB") - _col(baseline_data, "CGNB")
    rl = _col(shocked.data, "RL")
    d_rl = rl - _col(baseline_data, "RL")
    issuance = None
    changed = d_rl != 0.0
    if np.any(changed):
        # Planned issuance is needed only where the yield changes; a quarter
        # outside the published fiscal years raises there, not elsewhere.
        index = shocked.data.index[window]
        issuance = np.zeros(len(d_rl))
        issuance[changed] = quarterly_gilt_issuance_m(index[changed])
    path = debt_interest_path(pre, rl, d_rl, issuance)
    extra = np.asarray(path["delta_debt_interest_m"])
    for leg in DEBT_INTEREST_LEGS:
        j = shocked.data.columns.get_loc(leg)
        shocked.data.iloc[t_start : t_end + 1, j] = _col(shocked.data, leg) + extra
    shocked.solve(start, end)
    report = getattr(shocked, "last_solve_report", None)
    after = _col(shocked.data, "CGNB") - _col(baseline_data, "CGNB")
    detail = {
        "legs": list(DEBT_INTEREST_LEGS),
        "gilt_yield_pct": [round(float(x), 4) for x in rl],
        "delta_gilt_yield_pp": [round(float(x), 4) for x in d_rl],
        "delta_borrowing_before_m": [round(float(x), 3) for x in pre],
        "delta_borrowing_after_m": [round(float(x), 3) for x in after],
        "residual_m": float(np.max(np.abs(after - pre - extra))),
    }
    for key, values in path.items():
        detail[key] = [round(float(x), 3) for x in values]
    if not np.any(pre != 0.0) and not np.any(changed):
        # e.g. the household costing instrument, which moves household income
        # but not receipts: say so instead of returning silent zeros.
        detail["no_effect_note"] = (
            "Neither central government net borrowing (CGNB) nor the gilt "
            "yield (RL) moved in this run, so the overlay added nothing."
        )
    return shocked.data.copy(), report, detail
