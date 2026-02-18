"""Variable store for the OBR macroeconomic model.

Wraps a pandas DataFrame indexed by quarterly dates, with variable names as
columns. Provides convenient access via __getitem__ and lag notation.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


class Variables:
    """Quarterly time-series variable store.

    Parameters
    ----------
    start : str
        Start quarter, e.g. "1970Q1".
    end : str
        End quarter, e.g. "2030Q4".
    """

    def __init__(self, start: str = "1970Q1", end: str = "2030Q4"):
        self.index = pd.period_range(start=start, end=end, freq="Q")
        self._data: dict[str, np.ndarray] = {}

    @property
    def n(self) -> int:
        return len(self.index)

    def _ensure(self, name: str) -> np.ndarray:
        if name not in self._data:
            self._data[name] = np.full(self.n, np.nan)
        return self._data[name]

    def __getitem__(self, name: str) -> np.ndarray:
        return self._ensure(name)

    def __setitem__(self, name: str, value):
        arr = self._ensure(name)
        arr[:] = np.broadcast_to(np.asarray(value, dtype=float), arr.shape)

    def set(self, name: str, t: int, value: float):
        self._ensure(name)[t] = value

    def get(self, name: str, t: int) -> float:
        return self._ensure(name)[t]

    def period_to_idx(self, period_str: str) -> int:
        """Convert a period string like '2009Q1' to an integer index."""
        p = pd.Period(period_str, freq="Q")
        loc = self.index.get_loc(p)
        return int(loc)

    def elem(self, name: str, period_str: str) -> float:
        """EViews @elem equivalent: get value at a specific date."""
        return self.get(name, self.period_to_idx(period_str))

    def date_equals(self, t: int, period_str: str) -> float:
        """EViews @recode(@date = @dateval(...)) equivalent."""
        return 1.0 if self.index[t] == pd.Period(period_str, freq="Q") else 0.0

    def date_gte(self, t: int, period_str: str) -> float:
        """EViews @recode(@date >= @dateval(...)) equivalent."""
        return 1.0 if self.index[t] >= pd.Period(period_str, freq="Q") else 0.0

    def date_lte(self, t: int, period_str: str) -> float:
        """EViews @recode(@date <= @dateval(...)) equivalent."""
        return 1.0 if self.index[t] <= pd.Period(period_str, freq="Q") else 0.0

    def trend(self, t: int, base_period: str) -> float:
        """EViews @TREND equivalent: quarters since base period."""
        base_idx = self.period_to_idx(base_period)
        return float(t - base_idx)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame(self._data, index=self.index)

    def names(self) -> list[str]:
        return list(self._data.keys())

    def load_from_dataframe(self, df: pd.DataFrame):
        """Load historical data from a DataFrame with quarterly PeriodIndex."""
        for col in df.columns:
            arr = self._ensure(col)
            for period, val in df[col].items():
                if period in self.index:
                    idx = self.index.get_loc(period)
                    arr[idx] = val
