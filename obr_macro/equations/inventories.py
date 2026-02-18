"""Group 2: Inventories equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    GDPM = v["GDPM"]
    M = v["M"]
    SDE = v["SDE"]
    CGG = v["CGG"]
    CONS = v["CONS"]
    VAL = v["VAL"]
    IF = v["IF"]
    X = v["X"]
    PINV = v["PINV"]
    INV = v["INV"]
    PDINV = v["PDINV"]

    # Change in inventories: residual from national accounts identity
    v["DINV"][t] = (GDPM[t] + M[t] - SDE[t]) - CGG[t] - CONS[t] - VAL[t] - IF[t] - X[t]

    # Inventory level
    v["INV"][t] = INV[t - 1] + v["DINV"][t]

    # Stock appreciation (revaluation gain on inventories)
    v["SA"][t] = INV[t - 1] * (PINV[t] / PINV[t - 1] - 1)

    # Inventories at current prices
    v["DINVPS"][t] = v["DINV"][t] * PDINV[t] / 100

    # Household share of inventory change (7%)
    v["DINVHH"][t] = 0.07 * v["DINVPS"][t]

    # Public sector share of inventory change (PSNI identity - see public sector totals)
    # DINVCG computed in public_sector_totals; left for that module

    # Inventory price deflator
    v["PINV"][t] = 100 * v["BV"][t] / max(1, INV[t]) if INV[t] != 0 else PINV[t - 1]
