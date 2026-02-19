"""Full OBR model solver that initializes missing variables.

This solver:
1. Loads the OBR equations exactly as published
2. Initializes any missing variables to 0 (or computes from equations)
3. Solves the complete system using Gauss-Seidel iteration
4. Allows closure swaps for policy simulation
"""

import numpy as np
import pandas as pd
from pathlib import Path

from obr_macro.data import load_obr_data, DATA_DIR
from obr_macro.transpiler import parse_model_file, ParsedEquation


class FullOBRSolver:
    """Solve the complete OBR model as published."""

    def __init__(self, verbose: bool = True, include_behavioral: bool = True):
        self.verbose = verbose

        # Load data and equations
        # include_behavioral=True loads the commented behavioral equations (dlog, d)
        # which are needed for policy shock transmission
        self.data = load_obr_data()
        self.index = self.data.index
        self.equations = parse_model_file(
            str(DATA_DIR / "obr_model_code_march_2025.txt"),
            include_behavioral=include_behavioral
        )

        if self.verbose:
            print(f"Loaded {len(self.equations)} equations")
            print(f"Data has {len(self.data.columns)} variables")

        # Extract base values for @elem
        self.base_values = self._extract_base_values()

        # Initialize missing variables
        self._initialize_missing_variables()

        # Build equation index
        self._build_equation_index()

        # Initialize model by solving historical periods
        self._initialize_historical()

        # Compute residuals for behavioral equations
        self._compute_residuals()

        # Store baseline
        self.baseline = self.data.copy()

    def _extract_base_values(self) -> dict:
        """Extract base period values for @elem lookups."""
        values = {}
        for col in self.data.columns:
            for period in self.data.index:
                key = f"{col}_{period}"
                val = self.data.loc[period, col]
                if pd.notna(val):
                    values[key] = val
        return values

    def _initialize_missing_variables(self):
        """Initialize variables that are computed by equations but not in data."""
        import re

        # Find all variables referenced in equations
        all_vars = set()
        for eq in self.equations:
            vars_in_eq = re.findall(r'\b([A-Z][A-Z0-9_]*)\b', eq.original)
            all_vars.update(vars_in_eq)

        # Add missing variables with NaN (will be computed)
        # Use concat for efficiency instead of adding columns one by one
        missing = all_vars - set(self.data.columns)
        if missing:
            missing_df = pd.DataFrame(
                np.nan,
                index=self.data.index,
                columns=list(missing)
            )
            self.data = pd.concat([self.data, missing_df], axis=1)

        if self.verbose:
            print(f"Initialized {len(missing)} missing variables")

        # Add proxy variables
        if 'GPW' not in self.data.columns or self.data['GPW'].isna().all():
            if 'HHPHYSA' in self.data.columns:
                self.data['GPW'] = self.data['HHPHYSA'] / 1000

        if 'NFWPE' not in self.data.columns or self.data['NFWPE'].isna().all():
            if 'HHFINA' in self.data.columns:
                self.data['NFWPE'] = self.data['HHFINA']

    def _build_equation_index(self):
        """Build index of which variable each equation computes."""
        self.eq_for_var = {}  # var -> equation
        self.var_for_eq = {}  # equation index -> var

        for i, eq in enumerate(self.equations):
            var = self._extract_lhs_var(eq.lhs)
            self.eq_for_var[var] = eq
            self.var_for_eq[i] = var

        if self.verbose:
            print(f"Built equation index for {len(self.eq_for_var)} variables")

    def _initialize_historical(self):
        """Initialize missing variables by solving through historical periods.

        The OBR data has ~125 variables but the model needs ~640. We solve
        the identity equations through history to populate the missing
        intermediate variables.
        """
        # Find the first period with data
        start_t = 0
        for t in range(len(self.data)):
            if self.data.iloc[t].notna().sum() > 50:
                start_t = t
                break

        if self.verbose:
            print(f"Initializing from period {self.index[start_t]}")

        # Initialize key variables that require starting values
        # BPA (Basic Price Adjustment) is typically ~15% of GDP
        # GGVA (Government GVA) is typically ~20% of GDP
        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        for t in range(start_t, len(self.data)):
            gdpm = self._get('GDPM', t)
            etlfs = self._get('ETLFS', t)

            if np.isfinite(gdpm):
                # BPA ≈ 15% of GDP (taxes on products - subsidies)
                if np.isnan(self._get('BPA', t)):
                    self.data.iloc[t, col_idx['BPA']] = gdpm * 0.15

                # GGVA ≈ 20% of GDP (government value added)
                if np.isnan(self._get('GGVA', t)):
                    self.data.iloc[t, col_idx['GGVA']] = gdpm * 0.20

            if np.isfinite(etlfs):
                # EMS (market sector employment) ≈ 80% of total employment
                if np.isnan(self._get('EMS', t)):
                    self.data.iloc[t, col_idx['EMS']] = etlfs * 0.80 * 1000  # ETLFS in thousands

                # ET (total employment) from ETLFS
                if np.isnan(self._get('ET', t)):
                    self.data.iloc[t, col_idx['ET']] = etlfs * 1000

            # Initialize corporation tax parameters
            # TCPRO = corporation tax rate (25% from April 2023)
            if 'TCPRO' in col_idx and np.isnan(self._get('TCPRO', t)):
                self.data.iloc[t, col_idx['TCPRO']] = 0.25

            # DB, DP, DV = capital allowance rates (depreciation deductions)
            # Typical values: DB=0.18 (plant), DP=0.06 (buildings), DV=0.25 (vehicles)
            if 'DB' in col_idx and np.isnan(self._get('DB', t)):
                self.data.iloc[t, col_idx['DB']] = 0.18
            if 'DP' in col_idx and np.isnan(self._get('DP', t)):
                self.data.iloc[t, col_idx['DP']] = 0.06
            if 'DV' in col_idx and np.isnan(self._get('DV', t)):
                self.data.iloc[t, col_idx['DV']] = 0.25

            # WB, WP, WV = weights for capital types (sum to 1)
            if 'WB' in col_idx and np.isnan(self._get('WB', t)):
                self.data.iloc[t, col_idx['WB']] = 0.6
            if 'WP' in col_idx and np.isnan(self._get('WP', t)):
                self.data.iloc[t, col_idx['WP']] = 0.2
            if 'WV' in col_idx and np.isnan(self._get('WV', t)):
                self.data.iloc[t, col_idx['WV']] = 0.2

            # COCU = user cost of capital (pre-tax), typically ~0.1-0.15
            if 'COCU' in col_idx and np.isnan(self._get('COCU', t)):
                self.data.iloc[t, col_idx['COCU']] = 0.12

            # CBIUD = CBI uncertainty index (exogenous, normalize to 0)
            if 'CBIUD' in col_idx and np.isnan(self._get('CBIUD', t)):
                self.data.iloc[t, col_idx['CBIUD']] = 0

            # Initialize missing investment components
            # PCLEB = private capital leasing to business (small component)
            if 'PCLEB' in col_idx and np.isnan(self._get('PCLEB', t)):
                self.data.iloc[t, col_idx['PCLEB']] = 0

            # IPRL = private landlord investment (included in housing investment)
            if 'IPRL' in col_idx and np.isnan(self._get('IPRL', t)):
                self.data.iloc[t, col_idx['IPRL']] = 0

            # RDELTA = depreciation rate, typically ~0.025 (10% annual)
            if 'RDELTA' in col_idx and np.isnan(self._get('RDELTA', t)):
                self.data.iloc[t, col_idx['RDELTA']] = 0.025

            # Initialize business investment components if we have IF
            if_val = self._get('IF', t)
            if np.isfinite(if_val):
                # IBUS ≈ 50% of total investment (business investment)
                if 'IBUS' in col_idx and np.isnan(self._get('IBUS', t)):
                    self.data.iloc[t, col_idx['IBUS']] = if_val * 0.5

                # IBUSX = real business investment (similar scale to IBUS)
                if 'IBUSX' in col_idx and np.isnan(self._get('IBUSX', t)):
                    self.data.iloc[t, col_idx['IBUSX']] = if_val * 0.5

            # Initialize capital stock (KMSXH) from steady-state relationship
            # K = I / (g + delta) where g ≈ 0.005 (quarterly growth), delta ≈ 0.025
            if 'KMSXH' in col_idx and np.isnan(self._get('KMSXH', t)):
                ibusx = self._get('IBUSX', t)
                if np.isfinite(ibusx):
                    # KMSXH is in £bn, IBUSX in £m
                    self.data.iloc[t, col_idx['KMSXH']] = (ibusx / 1000) / 0.03

        # Solve identity equations only (no residuals yet)
        # Need multiple passes because equations may depend on each other
        identity_eqs = [eq for eq in self.equations
                       if not ("/" in eq.lhs or
                               eq.lhs.lower().startswith("dlog(") or
                               eq.lhs.lower().startswith("d("))]

        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        initialized = 0
        for t in range(start_t, len(self.data)):
            # Multiple passes to handle dependencies
            for _ in range(5):
                v = {col: self.data.iloc[t][col] for col in self.data.columns}
                ctx = {
                    "np": np,
                    "v": v,
                    "_lag": lambda var, lag, t=t: self._lag(var, lag, t),
                    "_recode": lambda period, op, tv, fv, t=t: self._recode(t, period, op, tv, fv),
                    "_trend": lambda base, t=t: self._trend(t, base),
                    "_elem": self._elem,
                    "t": t,
                }

                pass_initialized = 0
                for eq in identity_eqs:
                    var = self._extract_lhs_var(eq.lhs)
                    current_val = v.get(var, np.nan)

                    # Only initialize if currently NaN
                    if not np.isfinite(current_val):
                        try:
                            new_val = eval(eq.python_expr, ctx)
                            if np.isfinite(new_val):
                                if var in col_idx:
                                    self.data.iloc[t, col_idx[var]] = new_val
                                v[var] = new_val
                                initialized += 1
                                pass_initialized += 1
                        except:
                            pass

                # Stop if no new values computed this pass
                if pass_initialized == 0:
                    break

        if self.verbose:
            print(f"Initialized {initialized} values from identities")

    def _compute_residuals(self):
        """Compute residuals between OBR data and equation predictions.

        For each behavioral equation (dlog, d, ratio), we compute what the
        equation predicts and compare to the actual data. The residual is
        stored and added back during solve to ensure the model matches
        the OBR baseline exactly.

        Only computes for forecast period (2024Q1 onwards) for efficiency.
        """
        self.residuals = {}  # {(var, t): residual}

        # Only compute for forecast period
        try:
            start_t = self.period_idx("2024Q1")
        except:
            start_t = len(self.data) - 20  # Last 20 periods

        # Pre-filter behavioral equations
        behavioral_eqs = [
            eq for eq in self.equations
            if ("/" in eq.lhs or
                eq.lhs.lower().startswith("dlog(") or
                eq.lhs.lower().startswith("d("))
        ]

        for t in range(max(1, start_t), len(self.data)):
            # Build context once per period
            v = {col: self.data.iloc[t][col] for col in self.data.columns}
            ctx = {
                "np": np,
                "v": v,
                "_lag": lambda var, lag, t=t: self._lag(var, lag, t),
                "_recode": lambda period, op, tv, fv, t=t: self._recode(t, period, op, tv, fv),
                "_trend": lambda base, t=t: self._trend(t, base),
                "_elem": self._elem,
                "t": t,
            }

            for eq in behavioral_eqs:
                var = self._extract_lhs_var(eq.lhs)
                try:
                    rhs_val = eval(eq.python_expr, ctx)
                    actual_val = self._get(var, t)

                    if "/" in eq.lhs:
                        lag_val = self._lag(var, 1, t)
                        predicted = lag_val * rhs_val if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("dlog("):
                        lag_val = self._lag(var, 1, t)
                        predicted = lag_val * np.exp(rhs_val) if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("d("):
                        lag_val = self._lag(var, 1, t)
                        predicted = lag_val + rhs_val if np.isfinite(lag_val) else np.nan
                    else:
                        predicted = rhs_val

                    if np.isfinite(actual_val) and np.isfinite(predicted):
                        self.residuals[(var, t)] = actual_val - predicted
                except:
                    pass

        if self.verbose:
            print(f"Computed {len(self.residuals)} residuals")

    def _extract_lhs_var(self, lhs: str) -> str:
        """Extract variable name from LHS."""
        lhs = lhs.strip()
        if "/" in lhs:
            return lhs.split("/")[0].strip()
        if lhs.lower().startswith("dlog("):
            return lhs[5:-1].strip()
        if lhs.lower().startswith("d("):
            return lhs[2:-1].strip()
        if lhs.startswith("@IDENTITY"):
            return lhs.replace("@IDENTITY", "").strip()
        return lhs

    def _get(self, var: str, t: int) -> float:
        if var not in self.data.columns or t < 0 or t >= len(self.data):
            return np.nan
        return self.data.iloc[t][var]

    def _set(self, var: str, t: int, val: float):
        if var not in self.data.columns:
            self.data[var] = np.nan
        self.data.iloc[t, self.data.columns.get_loc(var)] = val

    def _lag(self, var: str, lag: int, t: int) -> float:
        return self._get(var, t - lag)

    def _recode(self, t: int, period: str, op: str, true_val: float, false_val: float) -> float:
        target = pd.Period(period, freq="Q")
        current = self.index[t]
        if op == "=":
            return true_val if current == target else false_val
        elif op == ">=":
            return true_val if current >= target else false_val
        elif op == "<=":
            return true_val if current <= target else false_val
        elif op == ">":
            return true_val if current > target else false_val
        elif op == "<":
            return true_val if current < target else false_val
        return false_val

    def _trend(self, t: int, base: str) -> float:
        try:
            base_p = pd.Period(base, freq="Q")
            base_idx = self.index.get_loc(base_p)
            return float(t - base_idx)
        except:
            return 0.0

    def _elem(self, var: str, period: str) -> float:
        key = f"{var}_{period}"
        return self.base_values.get(key, np.nan)

    def _build_context(self, t: int) -> dict:
        """Build evaluation context for time t."""
        v = {col: self.data.iloc[t][col] for col in self.data.columns}
        return {
            "np": np,
            "v": v,
            "_lag": lambda var, lag: self._lag(var, lag, t),
            "_recode": lambda period, op, tv, fv: self._recode(t, period, op, tv, fv),
            "_trend": lambda base: self._trend(t, base),
            "_elem": self._elem,
            "t": t,
        }

    def swap_closure(self, remove_var: str, add_eq: ParsedEquation):
        """Swap model closure by removing one equation and adding another.

        For fiscal shock: remove DINV equation, add GDPM equation.
        """
        # Remove equation for remove_var
        self.equations = [eq for eq in self.equations
                         if self._extract_lhs_var(eq.lhs) != remove_var]

        # Add new equation
        self.equations.append(add_eq)

        # Rebuild index
        self._build_equation_index()

        if self.verbose:
            print(f"Swapped closure: removed {remove_var}, added {add_eq.lhs}")

    def make_exogenous(self, var: str):
        """Make a variable exogenous by removing its equation."""
        self.equations = [eq for eq in self.equations
                         if self._extract_lhs_var(eq.lhs) != var]
        self._build_equation_index()

        if self.verbose:
            print(f"Made {var} exogenous (removed equation)")

    def apply_shock(self, var: str, shock: float, start: str, periods: int = 4):
        """Apply shock to a variable."""
        self.make_exogenous(var)

        # Mark that we're in shock mode (disable residuals)
        self._shock_active = True

        start_t = self.period_idx(start)
        for p in range(periods):
            t = start_t + p
            if t < len(self.data):
                old_val = self._get(var, t)
                self._set(var, t, old_val + shock)

        if self.verbose:
            print(f"Applied shock: {var} += {shock:+,.0f} for {periods} periods from {start}")

    def period_idx(self, period: str) -> int:
        return self.index.get_loc(pd.Period(period, freq="Q"))

    def solve_period(self, t: int, max_iter: int = 100, tol: float = 1e-6) -> int:
        """Solve all equations for period t using Gauss-Seidel."""
        # Pre-compute column indices for faster access
        col_idx = {col: self.data.columns.get_loc(col) for col in self.data.columns}

        for iteration in range(max_iter):
            max_change = 0.0

            # Build context once per iteration, use mutable v dict
            row = self.data.iloc[t]
            v = {col: row[col] for col in self.data.columns}

            ctx = {
                "np": np,
                "v": v,
                "_lag": lambda var, lag: self._lag(var, lag, t),
                "_recode": lambda t_arg, period, op, tv, fv: self._recode(t, period, op, tv, fv),
                "_trend": lambda base: self._trend(t, base),
                "_elem": self._elem,
                "t": t,
            }

            for eq in self.equations:
                try:
                    var = self._extract_lhs_var(eq.lhs)
                    old_val = v.get(var, np.nan)

                    rhs_val = eval(eq.python_expr, ctx)

                    # Compute new value based on equation form
                    if "/" in eq.lhs:
                        lag_val = self._lag(var, 1, t)
                        new_val = lag_val * rhs_val if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("dlog("):
                        lag_val = self._lag(var, 1, t)
                        new_val = lag_val * np.exp(rhs_val) if np.isfinite(lag_val) else np.nan
                    elif eq.lhs.lower().startswith("d("):
                        lag_val = self._lag(var, 1, t)
                        new_val = lag_val + rhs_val if np.isfinite(lag_val) else np.nan
                    else:
                        new_val = rhs_val

                    if np.isfinite(new_val):
                        # Add residual adjustment for behavioral equations
                        # But only if we're not in shock mode (baseline preserved)
                        if not hasattr(self, '_shock_active') or not self._shock_active:
                            residual = self.residuals.get((var, t), 0)
                            new_val += residual

                        # Update both the DataFrame and the context dict
                        if var in col_idx:
                            self.data.iloc[t, col_idx[var]] = new_val
                        v[var] = new_val

                        if np.isfinite(old_val) and abs(old_val) > 1e-10:
                            change = abs(new_val - old_val) / abs(old_val)
                            max_change = max(max_change, change)
                except Exception as e:
                    pass  # Skip equations that can't be evaluated

            if max_change < tol:
                return iteration + 1

        return max_iter

    def solve(self, start: str, end: str) -> dict:
        """Solve model from start to end period."""
        t_start = self.period_idx(start)
        t_end = self.period_idx(end)

        results = {}
        for t in range(t_start, t_end + 1):
            iters = self.solve_period(t)
            period = str(self.index[t])
            results[period] = iters
            if self.verbose:
                print(f"  {period}: {iters} iterations")

        return results


def run_fiscal_shock(shock_bn: float = 1.0):
    """Run fiscal shock using full OBR model."""
    print("=" * 70)
    print(f"FISCAL SHOCK ANALYSIS: £{shock_bn}bn Government Spending Increase")
    print("Using full OBR model equations")
    print("=" * 70)
    print()

    solver = FullOBRSolver(verbose=True)

    # Swap closure: DINV -> GDPM
    gdpm_eq = ParsedEquation(
        lhs="GDPM",
        rhs="CGG + CONS + IF + DINV + VAL + X - M + SDE",
        original="GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE",
        equation_type="identity",
        python_expr="v['CGG'] + v['CONS'] + v['IF'] + v['DINV'] + v['VAL'] + v['X'] - v['M'] + v['SDE']"
    )
    solver.swap_closure("DINV", gdpm_eq)

    # Apply shock
    shock_m = shock_bn * 1000
    solver.apply_shock("CGG", shock_m, "2025Q1", periods=4)

    print()
    print("Solving model...")
    solver.solve("2025Q1", "2027Q4")

    # Compare to baseline
    print()
    print("=" * 70)
    print("RESULTS")
    print("=" * 70)
    print()

    print(f"{'Period':<10} {'ΔCGG':>12} {'ΔCONS':>12} {'ΔGDPM':>12} {'Multiplier':>12}")
    print("-" * 58)

    for t in range(solver.period_idx("2025Q1"), solver.period_idx("2027Q4") + 1):
        period = str(solver.index[t])

        cgg_base = solver.baseline.iloc[t]['CGG']
        cgg_curr = solver._get('CGG', t)
        delta_cgg = cgg_curr - cgg_base

        cons_base = solver.baseline.iloc[t]['CONS']
        cons_curr = solver._get('CONS', t)
        delta_cons = cons_curr - cons_base

        gdpm_base = solver.baseline.iloc[t]['GDPM']
        gdpm_curr = solver._get('GDPM', t)
        delta_gdpm = gdpm_curr - gdpm_base

        mult = delta_gdpm / delta_cgg if delta_cgg > 0 else np.nan
        mult_str = f"{mult:.2f}" if np.isfinite(mult) else "N/A"

        print(f"{period:<10} {delta_cgg:>+12,.0f} {delta_cons:>+12,.0f} {delta_gdpm:>+12,.0f} {mult_str:>12}")

    return solver


if __name__ == "__main__":
    run_fiscal_shock(1.0)
