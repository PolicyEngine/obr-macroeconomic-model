"""Shared scoring helpers for the forecast / calibration scorecards.

One place for the error bands and the per-variable error loop, so
``forecast.py``, ``forecast_tune.py`` and ``calibration_score.py`` cannot
drift apart.

Three different error metrics share the four marks [OK]/[~]/[!]/[X]:

  - kind "pp"  : mean absolute error in percentage points (rates, inflation)
  - kind "gdp" : mean absolute error as % of GDP (net balances, the OBR's
                 own convention — a % error against a tiny net value is
                 meaninglessly amplified)
  - kind "lvl" : mean absolute % error vs the variable's own value (MAPE)

"Within band" means OK or ~ under the matching thresholds below. It is NOT a
single "within 10%" cut: 10% is only the lvl fair threshold.
"""
from __future__ import annotations

import numpy as np

# Band thresholds: value < GOOD -> "OK", < FAIR -> "~", < POOR -> "!", else "X".
PP_GOOD, PP_FAIR, PP_POOR = 0.3, 1.0, 3.0      # percentage points
GDP_GOOD, GDP_FAIR, GDP_POOR = 0.5, 1.5, 3.0   # % of GDP
LVL_GOOD, LVL_FAIR, LVL_POOR = 2.0, 10.0, 25.0  # % of own value (MAPE)

# One-line legend for printed scorecards ("within band" = OK or ~).
BAND_LEGEND = (f"within band = [OK] or [~]: rates <{PP_FAIR}pp | "
               f"net balances <{GDP_FAIR}% of GDP | levels <{LVL_FAIR}% MAPE")

WORDS = {"OK": "good", "~": "fair", "!": "poor", "X": "off"}


def band(kind, err):
    """Classify a scored error into a mark: OK / ~ / ! / X."""
    if err is None or not np.isfinite(err):
        return "X"
    if kind == "pp":
        g, f, p = PP_GOOD, PP_FAIR, PP_POOR
    elif kind == "gdp":
        g, f, p = GDP_GOOD, GDP_FAIR, GDP_POOR
    else:
        g, f, p = LVL_GOOD, LVL_FAIR, LVL_POOR
    return "OK" if err < g else "~" if err < f else "!" if err < p else "X"


def gdp_col(efo):
    """The GDP column used to normalise 'gdp'-kind errors."""
    return "GDPMPS" if "GDPMPS" in efo.columns else "GDPM"


def var_error(model, efo, code, kind, t0, t1):
    """Mean absolute error for one variable over periods t0..t1 (inclusive).

    model/efo are DataFrames indexed the same way. Returns the mean error in
    the metric implied by ``kind`` (see module docstring), or None if no
    finite observation pairs exist.
    """
    if code not in model.columns or code not in efo.columns:
        return None
    gdp_code = gdp_col(efo)
    errs = []
    for t in range(t0, t1 + 1):
        m, e = model.iloc[t][code], efo.iloc[t][code]
        if not (np.isfinite(m) and np.isfinite(e)):
            continue
        if kind == "pp":
            errs.append(abs(m - e))
        elif kind == "gdp":
            g = efo.iloc[t][gdp_code]
            if np.isfinite(g) and g > 0:
                errs.append(100 * abs(m - e) / g)
        elif abs(e) > 1e-9:
            errs.append(100 * abs(m - e) / abs(e))
    return float(np.mean(errs)) if errs else None
