"use client";

import { useState } from "react";
import {
  Area,
  ComposedChart,
  CartesianGrid,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { colors } from "../lib/colors";
import { getNiceTicks, getTickDomain } from "../lib/chartUtils";
import SectionHeading from "./SectionHeading";

const AXIS_STYLE = { fontSize: 12, fill: colors.gray[500] };

function qlab(p) {
  return p ? p.slice(2) : p;
}

function fmt(n, dp = 2) {
  if (n == null || Number.isNaN(n)) return "—";
  const s = n.toLocaleString("en-GB", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
  return (n > 0 ? "+" : "") + s;
}

// Format the slider value with its unit, e.g. "+2.5 pp", "−4 £bn/yr".
function fmtShock(v, unit) {
  const s = Number(v).toLocaleString("en-GB", { maximumFractionDigits: 2 });
  return `${v > 0 ? "+" : ""}${s} ${unit}`;
}

// Response at slider value `v`. The endpoints are solved as EViews-style
// overrides against a calibrated baseline (scenario − baseline), so each is
// already the clean policy impact. We scale the endpoint on the slider's side
// toward 0 (no change → no effect), which keeps any asymmetry between a rise
// and a cut.
function interpolate(lever, varCode, v) {
  if (v === 0) return null;
  const end = lever.points.find((p) => p.shock === (v >= 0 ? lever.hi : lever.lo));
  if (!end || !end.series[varCode]) return null;
  const denom = v >= 0 ? lever.hi : lever.lo;
  if (denom === 0) return null;
  const factor = v / denom;
  return end.series[varCode].map((x) => (x == null ? null : x * factor));
}

// Variables present (and bounded) in BOTH endpoints — the slope needs both.
function variablesForLever(grid, lever) {
  const lo = lever.points.find((p) => p.shock === lever.lo);
  const hi = lever.points.find((p) => p.shock === lever.hi);
  if (!lo || !hi) return [];
  return grid.variables.filter((vv) => lo.series[vv.code] && hi.series[vv.code]);
}

export default function CustomReformTab({ grid, embedded = false }) {
  const [leverId, setLeverId] = useState(grid ? grid.levers[0]?.id : null);
  const [value, setValue] = useState(null);
  const [varCode, setVarCode] = useState("GDPM");

  if (!grid) {
    return (
      <div className="space-y-6">
        <div className="section-card">
          {!embedded && (
            <SectionHeading
              title="Build a reform"
              description="Dial a policy lever to any size and see the modelled forecast."
            />
          )}
          <p className="text-sm text-slate-500">
            Reform grid has not been generated yet. Run{" "}
            <code>gen_reform_grid.py</code> and re-deploy.
          </p>
        </div>
      </div>
    );
  }

  const lever = grid.levers.find((l) => l.id === leverId) || grid.levers[0];
  // default slider to half the positive range on first render / lever change
  const v = value == null ? Math.round((lever.hi / 2) * 100) / 100 : value;

  const vlist = variablesForLever(grid, lever);
  let activeVar = varCode;
  if (!vlist.find((x) => x.code === activeVar)) {
    activeVar = (vlist.find((x) => x.code === "GDPM") || vlist[0] || {}).code;
  }
  const varMeta =
    grid.variables.find((x) => x.code === activeVar) || { label: activeVar, unit: "" };

  const { periods } = grid;
  const path = interpolate(lever, activeVar, v) || periods.map(() => 0);
  const chartData = periods.map((p, i) => ({ period: qlab(p), value: path[i] ?? null }));

  const allValues = [0, ...path.filter((x) => x != null && !Number.isNaN(x))];
  const yTicks = getNiceTicks([Math.min(...allValues), Math.max(...allValues)], 5);
  const yDomain = getTickDomain(yTicks);
  const axisLabel = `Δ ${varMeta.label} (${varMeta.unit})`;
  // Headline the largest-magnitude effect and its quarter, not the final value:
  // some channels (e.g. Bank Rate) peak then partly unwind, so the last quarter
  // can understate or even mis-sign the response.
  let pk = 0;
  path.forEach((x, i) => {
    if (x != null && Math.abs(x) > Math.abs(path[pk] ?? 0)) pk = i;
  });
  const peak = path[pk] ?? 0;
  const peakQ = periods[pk];

  return (
    <div className="space-y-6">
      {!embedded && (
        <div className="section-card">
          <SectionHeading
            title="Build a reform"
            description="Pick a policy lever, dial its size with the slider, and choose a variable to see the modelled impact, quarter by quarter, against an unchanged baseline. The reform is run the way the OBR runs one in EViews: the instrument is overridden in a scenario and solved against an add-factor-calibrated baseline, so the path shown is scenario minus baseline."
          />
        </div>
      )}

      {/* Controls */}
      <div className="section-card space-y-5">
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
            Policy lever
          </p>
          {grid.levers.length > 1 ? (
            <select
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm"
              value={lever.id}
              onChange={(e) => {
                setLeverId(e.target.value);
                setValue(null); // reset slider to the new lever's default
              }}
            >
              {grid.levers.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.name}
                </option>
              ))}
            </select>
          ) : (
            <p className="text-base font-semibold text-slate-800">{lever.name}</p>
          )}
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Each lever is solved against the add-factor-calibrated baseline, which
            keeps the behavioural blocks on track and gives a stable, correctly
            signed response. Corporation tax is not offered: its
            business-investment-to-GDP transmission is the one channel still dead
            in this model (a rise and a cut move GDP the same way), so it needs
            that channel re-calibrated before it can be shown honestly.
          </p>
        </div>

        <div>
          <div className="mb-2 flex items-baseline justify-between">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
              Reform size
            </p>
            <span className="font-mono text-lg font-semibold text-primary-700">
              {fmtShock(v, lever.unit)}
            </span>
          </div>
          <input
            type="range"
            min={lever.lo}
            max={lever.hi}
            step={lever.step}
            value={v}
            onChange={(e) => setValue(Number(e.target.value))}
            className="w-full accent-[color:var(--pe-color-primary-600)]"
          />
          <div className="flex justify-between text-xs text-slate-500">
            <span>{fmtShock(lever.lo, lever.unit)}</span>
            <span>0</span>
            <span>{fmtShock(lever.hi, lever.unit)}</span>
          </div>
        </div>

        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
            Variable
          </p>
          <div className="flex flex-wrap gap-2">
            {vlist.map((vv) => (
              <button
                key={vv.code}
                type="button"
                className={`selector-chip compact ${activeVar === vv.code ? "active" : ""}`}
                onClick={() => setVarCode(vv.code)}
              >
                {vv.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Headline + description */}
      <div className="section-card">
        <div className="note-card rounded-2xl p-4">
          <p className="m-0 text-sm leading-6 text-slate-700">
            <strong>{lever.name} {fmtShock(v, lever.unit)}</strong> &rarr;{" "}
            {varMeta.label} moves by up to{" "}
            <strong className={peak < 0 ? "text-red-700" : "text-primary-700"}>
              {fmt(peak)} {varMeta.unit}
            </strong>{" "}
            (largest by {peakQ}) vs an unchanged baseline. {lever.desc}
          </p>
        </div>
      </div>

      {/* Chart */}
      <div className="section-card space-y-4">
        <p className="text-sm font-semibold text-slate-700">{axisLabel}</p>
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            <ComposedChart data={chartData} margin={{ top: 10, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={colors.border.light} />
              <XAxis dataKey="period" tick={AXIS_STYLE} />
              <YAxis
                tick={AXIS_STYLE}
                domain={yDomain}
                ticks={yTicks}
                tickFormatter={(x) => fmt(x)}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip formatter={(x) => [`${fmt(x)} ${varMeta.unit}`, varMeta.label]} />
              <ReferenceLine y={0} stroke={colors.gray[400]} strokeWidth={1.2} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="none"
                fill={colors.primary[500]}
                fillOpacity={0.1}
                isAnimationActive={false}
                connectNulls
              />
              <Line
                type="monotone"
                dataKey="value"
                name={varMeta.label}
                stroke={colors.primary[500]}
                strokeWidth={2.4}
                dot={{ r: 2.4 }}
                activeDot={{ r: 4 }}
                isAnimationActive={false}
                connectNulls
              />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs leading-5 text-slate-500">
          Only the slider&rsquo;s two endpoint reforms are solved through the
          model. Values at in-between slider positions are{" "}
          <strong>linearly interpolated</strong> from the solved endpoint on that
          side; the model itself is nonlinear, so treat intermediate values as
          approximations.
        </p>
      </div>

      {/* Table */}
      <div className="section-card">
        <SectionHeading title="Quarter-by-quarter" size="lg" />
        <div className="mt-4 overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Quarter</th>
                <th>{axisLabel}</th>
              </tr>
            </thead>
            <tbody>
              {periods.map((p, i) => (
                <tr key={p}>
                  <td>{p}</td>
                  <td className={path[i] < 0 ? "text-red-700" : ""}>{fmt(path[i])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-xs text-slate-500">
          {grid.meta.note}
        </p>
      </div>
    </div>
  );
}
