from obr_macro.variables import Variables
from obr_macro.solver import solve_model
from obr_macro.equations import EQUATION_GROUPS


class OBRMacroModel:
    def __init__(self, start: str = "1970Q1", end: str = "2030Q4"):
        self.v = Variables(start=start, end=end)

    def run(self, from_period: str, to_period: str, verbose: bool = False):
        start_t = self.v.period_to_idx(from_period)
        end_t = self.v.period_to_idx(to_period)
        return solve_model(self.v, EQUATION_GROUPS, start_t, end_t, verbose=verbose)

    def set(self, name: str, value):
        self.v[name][:] = value

    def get(self, name: str):
        return self.v[name]

    def to_dataframe(self):
        return self.v.to_dataframe()
