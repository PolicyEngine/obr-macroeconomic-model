# API reference

Generated from the docstrings in `obr_macro`. The main entry point is `run_reform`; `FullOBRSolver` is the solver it builds on.

## Running a reform

::: obr_macro.reform_analysis.run_reform

::: obr_macro.reform_analysis.run_five_reforms

## The solver

::: obr_macro.full_solver.FullOBRSolver
    options:
      members:
        - clone
        - freeze_anchoring
        - swap_closure
        - make_exogenous
        - apply_shock
        - solve_period
        - diagnose_period
        - solve

## Parsing the OBR listing

::: obr_macro.transpiler.parse_model_file

::: obr_macro.transpiler.ParsedEquation

## Data

::: obr_macro.data.load_obr_data

## Published multiplier conventions

::: obr_macro.published_conventions
    options:
      show_root_heading: false
