# OBR Macroeconomic Model — dashboard

A Next.js 14 (App Router) + React + Tailwind dashboard for the OBR model emulator,
built on PolicyEngine's design system. Five tabs: **About**, **How it works**,
**Explore scenarios** (interactive recharts), **Variables** (searchable glossary),
**Equations** (published EViews + transpiled Python).

## Run locally

```bash
cd dashboard
npm install
npm run dev      # http://localhost:3000
```

`npm run build && npm run start` runs the production build. Deploys on Vercel
(`vercel.json`, framework `nextjs`).

## Data

The tabs read three JSON files from `public/data/`, regenerated from the repo root:

```bash
uv run python dashboard/gen_model_data.py      # -> public/data/model_data.json   (variables + equations)
uv run python dashboard/gen_explorer_data.py   # -> public/data/explorer_data.json (scenario solver output; slow)
uv run python dashboard/gen_reform_grid.py     # -> public/data/reform_grid.json   (custom-reform grid; slow)
```

`gen_model_data.py` parses the OBR variable list and transpiles each equation.
`gen_explorer_data.py` solves the five reform scenarios (baseline vs shock); it is
slow (two full 12-quarter solves per scenario).

**Vintage.** The committed `explorer_data.json` and `reform_grid.json` were
generated on 6 Nov 2026 against the March 2026 EFO and have not been regenerated
since the October 2026 re-anchor (for example CGG +1,250 at q1: 1,269 here, 1,267
in `results/demo_shocks.json`; Bank Rate +100bp at q1: −143 here, −128 there).
Their captions (such as "multiplier 1.0, flat" in `reform_grid.json`) describe
that run. `results/` is the source of record; regenerating the dashboard data is
a follow-up.

## Structure

- `app/page.jsx` — tab routing, data fetch, layout
- `app/globals.css` — PolicyEngine design tokens + component classes
- `src/components/*Tab.jsx` — one component per tab
- `src/lib/` — `formatters`, `colors`, `chartUtils` (shared with the PolicyEngine template)
