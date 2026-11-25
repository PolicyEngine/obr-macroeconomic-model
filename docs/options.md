---
icon: material/tune-variant
---

# Options and overlays

`run_reform` is the one entry point. This page lists every keyword argument it takes, with its default, what it does and where it is explained in depth. The signature is in [`obr_macro/reform_analysis.py`](https://github.com/PolicyEngine/obr-macroeconomic-model/blob/main/obr_macro/reform_analysis.py); the full docstring is on the [API reference](api.md) page.

```python
run_reform(
    name, var, shock,
    start="2025Q1", end="2027Q4", periods=12,
    investment_closure=False,
    published_conventions=False,
    nominal_gdp_pin=None,
    monetary_conditioning=False,
    price_passthrough=False,
    nominal_consistent=None,
    import_response=False,
    employment_response=False,
    debt_interest=False,
)
```

The arguments fall into three groups: what to shock, how the model is closed, and opt-in judgement overlays. Line numbers such as l.690 refer to lines of the OBR's published model listing. The EFO is the OBR's Economic and fiscal outlook, whose forecast is the baseline. An add-factor is a fixed term added to an equation to move its result onto a chosen path.

!!! warning "Judgement overlays are off by default"
    Six options add assumptions that are **not** in the OBR's published listing: `published_conventions`, `monetary_conditioning`, `price_passthrough`, `import_response`, `employment_response` and `debt_interest`. Each is off by default. When one is on, `df.attrs` carries a note saying it is a labelled judgement overlay, not model dynamics. Quote such a result as "the model plus this assumption".

## :material-target: What to shock { #what-to-shock }

| Argument | Default | What it does |
|---|---|---|
| `name` | required | A label. It is copied into the `reform` column of the output. |
| `var` | required | The variable to shock. It must be exogenous (no equation computes it), or the virtual instrument `"HHDI_ADDFACTOR"` for an externally costed household reform. A variable that is missing or non-finite over the shocked window raises an error rather than returning a zero effect. |
| `shock` | required | The size of the shock, in the units of `var`. It is added to the variable. A single number is applied for `periods` quarters from `start`. A list gives one value per quarter from `start`, and its length overrides `periods`. For `HHDI_ADDFACTOR`, values are £m a quarter and positive means revenue raised, so household income falls. |
| `start` | `"2025Q1"` | First quarter of the shock and of the solve window. |
| `end` | `"2027Q4"` | Last quarter of the solve window. The output has one row per quarter from `start` to `end`. |
| `periods` | `12` | How many quarters a single-number shock lasts. Ignored when `shock` is a list. If the shock runs past `end`, the extra quarters are not solved and `df.attrs["horizon_warning"]` says so. |

Units and sign conventions for the common instruments are on the [worked examples](examples.md) page.

## :material-lock-outline: How the model is closed { #how-the-model-is-closed }

A **closure** is the choice of which variables the model solves for and which it takes as given. These three options are model choices, not judgement overlays, but they change results and are recorded in `df.attrs`.

| Argument | Default | What it does | Read more |
|---|---|---|---|
| `nominal_gdp_pin` | `None`, which resolves to on under the default closure and off under `investment_closure` | Closes nominal GDP with the OBR's commented-out l.690, `GDPMPS = PGDP*GDPM/100`, instead of the l.688 expenditure identity. This makes the investment deflator `PIF` determined rather than free. `False` selects the published closure, under which no quarter converges in a demand-closure run. `True` together with `investment_closure=True` raises an error. | [Nominal-GDP pin](nominal_gdp_pin.md) |
| `investment_closure` | `False` | Switches on the reconstructed business-investment equation `dlog(IBUSX)` and the listing's commented-out `IF` identity, so the corporation tax rate (`TCPRO`) reaches investment through the cost of capital and government investment reaches GDP. To keep it stable it freezes `MSGVA`, `PIF` and `PIRHH` at a reference path. A stop-gap; it turns the nominal-GDP pin off. | [How it works](how-it-works.md#the-investment-closure) |
| `nominal_consistent` | `None`, which resolves to on for a `CGG`, `CGSB` or `CGOTR` shock under the nominal-GDP pin and off otherwise | For government consumption (`CGG`), social benefits (`CGSB`) and other current grants (`CGOTR`). When on, the real `CGG` shock is matched by the same cash amount on the nominal spending totals `CGGPS`, `CGGPSPSF` and `PSCE`, and a `CGSB` or `CGOTR` shock is matched by the same amount on `PSCE`, so borrowing rises by the cash cost. When off, only the shocked line moves and borrowing does not change; for `CGSB` and `CGOTR` the run then carries `subsidy_residual_warning`. `True` for any other variable raises an error. | [Nominal-GDP pin](nominal_gdp_pin.md), [Limits](limitations.md) |

## :material-layers-triple: Judgement overlays (off by default) { #judgement-overlays-off-by-default }

| Argument | Default | What it does | Applies to | Read more |
|---|---|---|---|---|
| `published_conventions` | `False` | Imposes the OBR's published multiplier convention (EFO July 2015, Box 3.2) as a GDP add-factor path on the shocked run: impact multiplier 0.6 for current spending or 1.0 for capital spending, fading linearly to zero over 20 quarters. The linear shape is this repo's choice. Component columns (`delta_cons_m`, `delta_if_m`) are not overridden. For any other instrument the flag is accepted but not applied, and `df.attrs["published_conventions_note"]` says so; for the household channel that is deliberate, because it has live behaviour. | `CGG`, `CGIPS`, `LAIPS`, `GGIPS` | [Medium-term convergence](medium_term_convergence.md), [decisions](decisions.md) |
| `monetary_conditioning` | `False` | Also moves the mortgage rate `RMORT` with Bank Rate at 0.9 per point, the pass-through in the OBR's own l.623. Deposit rates, gilt yields, sterling and house prices stay on the EFO path because no sourced coefficient exists; `df.attrs["monetary_conditioning_off"]` lists them with the reason. | `R` only | [Monetary conditioning](monetary_conditioning.md) |
| `price_passthrough` | `False` | Passes an indirect-tax rise into CPI through the listing's own cost-push weights, with the retail markup held at baseline. The shipped listing holds CPI exogenous instead. | `VREC`, `TXFUEL` | [Price pass-through](price_passthrough.md) |
| `import_response` | `False` | Lets imports respond to demand on the shocked run: services through the listing's l.223, goods in proportion to import-weighted demand with a unit elasticity that is this repo's assumption. | Any `var` except `M`, `MNOG`, `MS`, `MOIL` | [Demand overlays](demand_overlays.md) |
| `employment_response` | `False` | Passes the change in market-sector employment from the listing's l.145 one for one to total employment, so unemployment responds. For a government-consumption shock the result is near zero and can have the wrong sign; that run carries a warning. | Any `var` except `HWA`, `AVH`, `ETLFS`, `EMS` | [Demand overlays](demand_overlays.md) |
| `debt_interest` | `False` | Makes central government debt interest respond: extra borrowing is financed with gilts at the 20-year gilt yield `RL`, and a shock to `RL` reprices planned gilt issuance. The interest is added to `DICGOP` and `PSCE`, so borrowing rises by it. GDP is the same with it on or off. Conventional gilts only. | Any `var` | [Debt interest](debt_interest.md) |

## :material-alert-circle: Combinations that raise an error { #combinations-that-raise-an-error }

`run_reform` checks these before building the model, so a bad combination fails in milliseconds:

- `published_conventions` with `investment_closure`.
- `nominal_gdp_pin=True` with `investment_closure`.
- `monetary_conditioning` with any `var` other than `R`.
- `price_passthrough` with any `var` other than `VREC` or `TXFUEL`, or with `investment_closure`.
- `nominal_consistent=True` with any `var` other than `CGG`, `CGSB` or `CGOTR`.
- `import_response` or `employment_response` with `investment_closure`, `published_conventions`, `price_passthrough`, `monetary_conditioning` or `nominal_gdp_pin=False`. The two can be combined with each other.
- `debt_interest` with `investment_closure`, `published_conventions`, `price_passthrough`, `monetary_conditioning`, `import_response`, `employment_response` or `nominal_gdp_pin=False`.

One more check runs after the model template is built: a `TCPRO` shock that would put the corporation tax rate outside `[0, 1)` is refused.

## :material-tag-search: How to tell which options a result used { #how-to-tell-which-options-a-result-used }

Every result records its options in `df.attrs`: `nominal_gdp_pin`, `nominal_consistent`, `published_conventions`, `price_passthrough`, `import_response`, `employment_response`, `debt_interest` and `monetary_conditioning` are always set. Each overlay that is on adds a `..._note` and usually a `..._detail` entry. [Getting started](getting-started.md#reading-dfattrs) lists the other keys.
