"""OBR Macroeconomic Model Emulator.

This package runs the OBR's published macroeconomic model equations in Python,
enabling policy shock analysis (fiscal multipliers, tax changes, etc.)
"""

from obr_macro.data import load_obr_data, DATA_DIR
from obr_macro.transpiler import parse_model_file, ParsedEquation
from obr_macro.full_solver import FullOBRSolver
from obr_macro.reform_analysis import run_reform, run_five_reforms

__all__ = [
    "load_obr_data",
    "DATA_DIR",
    "parse_model_file",
    "ParsedEquation",
    "FullOBRSolver",
    "run_reform",
    "run_five_reforms",
]
