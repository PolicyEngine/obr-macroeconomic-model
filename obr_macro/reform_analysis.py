"""Analyse policy reforms using OBR model and generate visualisations."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

from obr_macro.full_solver import FullOBRSolver
from obr_macro.transpiler import ParsedEquation, EViewsTranspiler


# Standard equations for closure swaps
GDPM_EQ = ParsedEquation(
    lhs="GDPM",
    rhs="CGG + CONS + IF + DINV + VAL + X - M + SDE",
    original="GDPM = CGG + CONS + IF + DINV + VAL + X - M + SDE",
    equation_type="identity",
    python_expr="v['CGG'] + v['CONS'] + v['IF'] + v['DINV'] + v['VAL'] + v['X'] - v['M'] + v['SDE']"
)

IBUS_EQ = ParsedEquation(
    lhs="IBUS",
    rhs="IBUSX + adjustment",
    original="IBUS = IBUSX + 17394 * @recode(...)",
    equation_type="identity",
    python_expr="v['IBUSX'] + 17394 * _recode(t, '2005Q2', '=', 1, 0)"
)

IF_EQ = ParsedEquation(
    lhs="IF",
    rhs="IBUS + GGI + PCIH + PCLEB + IH + IPRL",
    original="IF = IBUS + GGI + PCIH + PCLEB + IH + IPRL",
    equation_type="identity",
    python_expr="v['IBUS'] + v['GGI'] + v['PCIH'] + v['PCLEB'] + v['IH'] + v['IPRL']"
)

# Business-investment error-correction equation, dlog(IBUSX).
# The OBR publishes this equation commented out and missing its closing
# parenthesis (identical in the March and October 2025 model code). It is
# reconstructed here (the single missing ')' restored) and transpiled with the
# real transpiler so it stays consistent with the parser. Under the investment
# closure it replaces the IBUSX residual identity, activating the
# cost-of-capital channel TCPRO -> TAF -> COC -> KSTAR -> KGAP -> IBUSX; without
# it, business investment is a pure residual and corporation-tax shocks have no
# effect on investment.
_IBUSX_SRC = (
    'dlog(IBUSX) = 0.1992007 * dlog(IBUSX(-3)) + 1.00573 * dlog(MSGVA(-1)) '
    '- 0.0012369*CBIUD - 0.0418036*(log(IBUSX(-1)) - log(KMSXH(-2) * 1000) '
    '+ KGAP(-2) + 0.0544706 * @recode(@date = @dateval("1998:01") , 1 , 0) '
    '+ 0.0597525 * @recode(@date = @dateval("2005:02") , 1 , 0) - 0.0884031)'
)
IBUSX_EQ = EViewsTranspiler().parse_equation(_IBUSX_SRC)


def _ensure_ibusx_inputs(solver):
    """Ensure inputs to the reconstructed IBUSX equation exist on the solver.

    CBIUD (a business-investment uncertainty differential) is referenced only by
    the reconstructed dlog(IBUSX) equation, so it is never seen by the solver's
    missing-variable initialisation and is absent from the EFO data. Default it
    to zero: it is neutral and cancels between the baseline and shocked runs, so
    it does not distort the corporation-tax differential.
    """
    if "CBIUD" not in solver.data.columns:
        # (May emit a benign pandas fragmentation PerformanceWarning, as
        # elsewhere in the solver; harmless for a single added column.)
        solver.data["CBIUD"] = 0.0


def run_reform(name: str, var: str, shock: float, start: str = "2025Q1",
               end: str = "2027Q4", periods: int = 12, investment_closure: bool = False):
    """Run a reform scenario and return results DataFrame.

    Args:
        name: Name of the reform for labeling
        var: Variable to shock (must be exogenous - no equation computes it)
        shock: Size of shock (units depend on variable)
        start: Start quarter (e.g., "2025Q1")
        end: End quarter for simulation
        periods: Number of quarters to apply shock
        investment_closure: If True, use investment closure (for corp tax shocks)
    """
    # Build once; the baseline and shocked runs must be structurally identical
    # (same closures, same exogenous instrument, same starting data) so the
    # delta isolates the shock. If `var` is made exogenous only in the shocked
    # run, the baseline re-solves it endogenously and drifts away from the
    # databank — the drift can exceed the shock and flip the sign of Q1 deltas.
    baseline = FullOBRSolver(verbose=False)
    baseline.swap_closure("DINV", GDPM_EQ)
    if investment_closure:
        _ensure_ibusx_inputs(baseline)
        baseline.swap_closure("IBUSX", IBUSX_EQ)
        baseline.swap_closure("IBUS", IBUS_EQ)
        baseline.swap_closure("IF_PLACEHOLDER", IF_EQ)
    baseline.make_exogenous(var)
    baseline._shock_active = True

    shocked = baseline.clone()
    shocked.apply_shock(var, shock, start, periods=periods)

    baseline.solve(start, end)
    baseline_data = baseline.data.copy()
    shocked.solve(start, end)
    shocked_data = shocked.data.copy()

    # Build results
    t_start = baseline.period_idx(start)
    t_end = baseline.period_idx(end)

    results = []
    for t in range(t_start, t_end + 1):
        period = str(baseline.index[t])
        gdp_base = baseline_data.iloc[t]["GDPM"]
        gdp_shock = shocked_data.iloc[t]["GDPM"]
        delta_gdp = gdp_shock - gdp_base
        pct_gdp = 100 * delta_gdp / gdp_base

        cons_base = baseline_data.iloc[t]["CONS"]
        cons_shock = shocked_data.iloc[t]["CONS"]
        delta_cons = cons_shock - cons_base

        if_base = baseline_data.iloc[t]["IF"]
        if_shock = shocked_data.iloc[t]["IF"]
        delta_if = if_shock - if_base

        results.append({
            "period": period,
            "reform": name,
            "delta_gdp_m": delta_gdp,
            "delta_gdp_bn": delta_gdp / 1000,
            "pct_gdp": pct_gdp,
            "delta_cons_m": delta_cons,
            "delta_if_m": delta_if,
        })

    return pd.DataFrame(results)


def run_five_reforms():
    """Run five interesting policy reforms."""

    reforms = []

    # 1. Government spending increase: £5bn/year (£1.25bn/quarter)
    print("Running Reform 1: £5bn government spending increase...")
    df = run_reform(
        name="£5bn Gov Spending",
        var="CGG",
        shock=1250,  # £1.25bn per quarter = £5bn/year
        periods=12,
        investment_closure=False
    )
    reforms.append(df)

    # 2. Corporation tax cut: -5pp (from 25% to 20%)
    print("Running Reform 2: 5pp corporation tax cut...")
    df = run_reform(
        name="5pp Corp Tax Cut",
        var="TCPRO",
        shock=-0.05,  # -5pp
        periods=12,
        investment_closure=True
    )
    reforms.append(df)

    # 3. Corporation tax rise: +5pp (from 25% to 30%)
    print("Running Reform 3: 5pp corporation tax rise...")
    df = run_reform(
        name="5pp Corp Tax Rise",
        var="TCPRO",
        shock=0.05,  # +5pp
        periods=12,
        investment_closure=True
    )
    reforms.append(df)

    # 4. Government investment boost: £10bn/year
    # Chain: CGIPS (exog) → GGIPS = CGIPS + LAIPS → GGI = 100 * GGIPS / GGIDEF
    # GGIDEF ≈ 119, so to get £2.5bn real GGI, need ~£3bn nominal CGIPS
    print("Running Reform 4: £10bn government investment...")
    df = run_reform(
        name="£10bn Gov Investment",
        var="CGIPS",
        shock=3000,  # £3bn nominal per quarter ≈ £2.5bn real
        periods=12,
        investment_closure=False
    )
    reforms.append(df)

    # 5. Austerity scenario: -£10bn government spending
    print("Running Reform 5: £10bn spending cut...")
    df = run_reform(
        name="£10bn Spending Cut",
        var="CGG",
        shock=-2500,  # -£2.5bn per quarter
        periods=12,
        investment_closure=False
    )
    reforms.append(df)

    return pd.concat(reforms, ignore_index=True)


def create_visualisations(results: pd.DataFrame, output_dir: str = None):
    """Create reform impact visualisations."""

    if output_dir is None:
        output_dir = Path(__file__).parent.parent / "outputs"
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    # Set style
    plt.style.use('seaborn-v0_8-whitegrid')

    reforms = results["reform"].unique()
    colors = plt.cm.tab10(np.linspace(0, 1, len(reforms)))
    color_map = dict(zip(reforms, colors))

    # Figure 1: GDP impact over time (£bn)
    fig, ax = plt.subplots(figsize=(12, 6))
    for reform in reforms:
        df = results[results["reform"] == reform]
        ax.plot(df["period"], df["delta_gdp_bn"],
                label=reform, color=color_map[reform], linewidth=2)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.set_xlabel("Quarter", fontsize=12)
    ax.set_ylabel("Change in GDP (£bn)", fontsize=12)
    ax.set_title("GDP Impact of Policy Reforms\n(OBR Model)", fontsize=14)
    ax.legend(loc="best", fontsize=10)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "reform_gdp_impact.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_gdp_impact.png'}")

    # Figure 2: GDP impact (% change)
    fig, ax = plt.subplots(figsize=(12, 6))
    for reform in reforms:
        df = results[results["reform"] == reform]
        ax.plot(df["period"], df["pct_gdp"],
                label=reform, color=color_map[reform], linewidth=2)
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.set_xlabel("Quarter", fontsize=12)
    ax.set_ylabel("Change in GDP (%)", fontsize=12)
    ax.set_title("GDP Impact of Policy Reforms (% Change)\n(OBR Model)", fontsize=14)
    ax.legend(loc="best", fontsize=10)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "reform_gdp_pct.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_gdp_pct.png'}")

    # Figure 3: Final period comparison (bar chart)
    final_period = results["period"].iloc[-1]
    final_results = results[results["period"] == final_period].copy()

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(final_results))
    bars = ax.bar(x, final_results["delta_gdp_bn"],
                  color=[color_map[r] for r in final_results["reform"]])
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(final_results["reform"], rotation=30, ha="right")
    ax.set_ylabel("Change in GDP (£bn)", fontsize=12)
    ax.set_title(f"Cumulative GDP Impact by {final_period}\n(OBR Model)", fontsize=14)

    # Add value labels
    for bar, val in zip(bars, final_results["delta_gdp_bn"]):
        height = bar.get_height()
        ax.annotate(f'{val:+.1f}',
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3 if height >= 0 else -12),
                    textcoords="offset points",
                    ha='center', va='bottom' if height >= 0 else 'top',
                    fontsize=10)

    plt.tight_layout()
    plt.savefig(output_dir / "reform_comparison.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_comparison.png'}")

    # Figure 4: Spending vs Tax reforms
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))

    # Spending reforms
    spending_reforms = ["£5bn Gov Spending", "£10bn Gov Investment", "£10bn Spending Cut"]
    for reform in spending_reforms:
        if reform in reforms:
            df = results[results["reform"] == reform]
            ax1.plot(df["period"], df["delta_gdp_bn"],
                    label=reform, linewidth=2)
    ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax1.set_xlabel("Quarter")
    ax1.set_ylabel("Change in GDP (£bn)")
    ax1.set_title("Spending Policy Reforms")
    ax1.legend()
    ax1.tick_params(axis='x', rotation=45)

    # Tax reforms
    tax_reforms = ["5pp Corp Tax Cut", "5pp Corp Tax Rise"]
    for reform in tax_reforms:
        if reform in reforms:
            df = results[results["reform"] == reform]
            ax2.plot(df["period"], df["delta_gdp_bn"],
                    label=reform, linewidth=2)
    ax2.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
    ax2.set_xlabel("Quarter")
    ax2.set_ylabel("Change in GDP (£bn)")
    ax2.set_title("Corporation Tax Reforms")
    ax2.legend()
    ax2.tick_params(axis='x', rotation=45)

    plt.tight_layout()
    plt.savefig(output_dir / "reform_spending_vs_tax.png", dpi=150)
    plt.close()
    print(f"Saved: {output_dir / 'reform_spending_vs_tax.png'}")

    return output_dir


def main():
    """Run all reforms and create visualisations."""
    print("=" * 70)
    print("OBR MODEL: POLICY REFORM ANALYSIS")
    print("=" * 70)
    print()

    # Run reforms
    results = run_five_reforms()

    # Save results
    output_dir = Path(__file__).parent.parent / "outputs"
    output_dir.mkdir(exist_ok=True)
    results.to_csv(output_dir / "reform_results.csv", index=False)
    print(f"\nSaved results: {output_dir / 'reform_results.csv'}")

    # Create visualisations
    print("\nCreating visualisations...")
    create_visualisations(results, output_dir)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY: Final Period GDP Impacts")
    print("=" * 70)
    final = results[results["period"] == results["period"].iloc[-1]]
    for _, row in final.iterrows():
        print(f"{row['reform']:<25} {row['delta_gdp_bn']:>+8.1f} £bn ({row['pct_gdp']:>+6.2f}%)")

    return results


if __name__ == "__main__":
    main()
