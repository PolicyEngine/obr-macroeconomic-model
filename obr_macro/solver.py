"""Gauss-Seidel iterative solver for the OBR macroeconomic model."""

from __future__ import annotations

from typing import Callable
import numpy as np

from obr_macro.variables import Variables


SolveGroup = Callable[[Variables, int], None]


def solve_period(
    v: Variables,
    t: int,
    groups: list[SolveGroup],
    max_iter: int = 500,
    tol: float = 1e-6,
) -> int:
    """Solve all equation groups for period t via Gauss-Seidel iteration.

    Returns the number of iterations taken.
    """
    for iteration in range(max_iter):
        # Snapshot all current values
        prev = {name: v[name][t] for name in v.names()}

        for group in groups:
            group(v, t)

        # Check convergence: max absolute change across all variables
        max_delta = 0.0
        for name in v.names():
            old = prev.get(name, np.nan)
            new = v[name][t]
            if np.isfinite(old) and np.isfinite(new) and old != 0:
                delta = abs((new - old) / old)
            else:
                delta = abs(new - old) if np.isfinite(new - old) else 0.0
            if delta > max_delta:
                max_delta = delta

        if max_delta < tol:
            return iteration + 1

    return max_iter


def solve_model(
    v: Variables,
    groups: list[SolveGroup],
    start_t: int,
    end_t: int,
    max_iter: int = 500,
    tol: float = 1e-6,
    verbose: bool = False,
) -> dict[int, int]:
    """Solve the model from start_t to end_t (inclusive).

    Returns a dict of {t: iterations_taken}.
    """
    iterations = {}
    for t in range(start_t, end_t + 1):
        iters = solve_period(v, t, groups, max_iter=max_iter, tol=tol)
        iterations[t] = iters
        if verbose:
            period_label = str(v.index[t])
            print(f"  {period_label}: converged in {iters} iterations")
    return iterations
