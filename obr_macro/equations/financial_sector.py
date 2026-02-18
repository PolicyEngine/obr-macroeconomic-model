"""Group 14: Domestic financial sector equations."""

from __future__ import annotations

import numpy as np
from obr_macro.variables import Variables


def solve_t(v: Variables, t: int) -> None:
    if t < 1:
        return

    R = v["R"]

    # Interbank rate
    v["RIC"][t] = (
        v["RIC"][t - 1]
        + 0.755375 * (R[t] - R[t - 1])
        - 0.286805 * (v["RIC"][t - 1] - 0.822845 * R[t - 1] - 2.583124)
    )

    # Equity prices (tracks nominal GDP)
    v["EQPR"][t] = v["EQPR"][t - 1] * (v["GDPMPS"][t] / max(v["GDPMPS"][t - 1], 1e-10))

    # Narrow money (tracks nominal GDP)
    v["M0"][t] = v["M0"][t - 1] * (v["GDPMPS"][t] / max(v["GDPMPS"][t - 1], 1e-10))

    # Institutional credit
    v["M4IC"][t] = v["M4IC"][t - 1] * (v["GDPMPS"][t] / max(v["GDPMPS"][t - 1], 1e-10))

    # Broad money
    v["M4"][t] = v["DEPHH"][t] + v["M4IC"][t] + v["M4OFC"][t]
