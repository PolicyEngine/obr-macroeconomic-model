"use client";

import { useState } from "react";
import {
  Area,
  ComposedChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
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

// 5 distinct colours for the compare-mode multi-line palette.
const SERIES_COLORS = [
  colors.primary[500],
  "#c2543d",
  "#c9871f",
  "#3b6ea5",
  "#7d5ba6",
];

const SCEN_DESC = {
  gov_spend:
    "Government consumption is a direct part of the GDP identity, so output moves one-for-one with the shock. In this emulator the behavioural second round (consumption, prices, imports) is largely inactive under the demand closure, so the multiplier stays ≈1 by construction — the OBR's own published impact multiplier for current spending is ~0.45.",
  austerity:
    "The stimulus in reverse: lower public demand subtracts one-for-one from the GDP identity. The same ≈1-by-construction multiplier caveat applies.",
  export_rise:
    "Stronger external demand for UK exports (e.g. faster world growth). Exports add directly to the GDP identity; the import and price offsets are largely inactive here.",
  export_cut:
    "Weaker external demand for UK exports. The mirror of the export boom, with the same identity-driven caveat.",
  rate_rise:
    "A 1pp Bank Rate rise feeds the household income and consumption equations. The investment and exchange-rate channels of monetary policy are not active in this emulator, so responses are smaller and narrower than the OBR's published ready-reckoners.",
};

// 2025Q1 -> 25Q1
function qlab(p) {
  return p ? p.slice(2) : p;
}

// Signed delta formatting, "—" for missing.
function fmt(n, dp = 2) {
  if (n == null || Number.isNaN(n)) {
    return "—";
  }
  const s = n.toLocaleString("en-GB", {
    minimumFractionDigits: dp,
    maximumFractionDigits: dp,
  });
  return (n > 0 ? "+" : "") + s;
}

function variablesForScenario(explorer, scenIdx) {
  const sc = explorer.scenarios[scenIdx];
  if (!sc) {
    return [];
  }
  return explorer.variables.filter((v) => sc.series[v.code]);
}

function variablesAll(explorer) {
  return explorer.variables.filter((v) =>
    explorer.scenarios.some((sc) => sc.series[v.code]),
  );
}

function ScenarioCard({ scenario }) {
  const tagClass =
    scenario.tag === "Demand"
      ? "bg-primary-50 text-primary-700"
      : "bg-amber-50 text-amber-700";
  return (
    <div className="note-card rounded-2xl p-4">
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <span
          className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tagClass}`}
        >
          {scenario.tag}
        </span>
        <strong className="text-base text-slate-900">{scenario.name}</strong>
        <span className="font-mono text-xs text-slate-500">
          {scenario.shock} &middot; {scenario.closure} closure
        </span>
      </div>
      <p className="note-body m-0 text-sm leading-6 text-slate-700">
        {SCEN_DESC[scenario.id] || ""}
      </p>
    </div>
  );
}

export default function ExploreTab({ explorer }) {
  const [mode, setMode] = useState("single");
  const [scenIdx, setScenIdx] = useState(0);
  const [varCode, setVarCode] = useState("GDPM");

  if (!explorer) {
    return (
      <div className="space-y-6">
        <div className="section-card">
          <SectionHeading
            title="Explore scenarios"
            description="Pick a policy scenario and a variable to see the modelled path, quarter by quarter, against an unchanged baseline."
          />
          <p className="text-sm text-slate-500">
            Scenario data has not been generated yet.
          </p>
        </div>
      </div>
    );
  }

  const { meta, periods, scenarios } = explorer;

  // Which variables are selectable depends on the mode.
  const vlist =
    mode === "single"
      ? variablesForScenario(explorer, scenIdx)
      : variablesAll(explorer);

  // If the current variable isn't available, default to GDPM else first.
  let activeVar = varCode;
  if (!vlist.find((v) => v.code === activeVar)) {
    const fallback = vlist.find((v) => v.code === "GDPM") || vlist[0];
    activeVar = fallback ? fallback.code : null;
    if (activeVar !== varCode) {
      setVarCode(activeVar);
    }
  }

  const varMeta =
    explorer.variables.find((v) => v.code === activeVar) || {
      label: activeVar,
      unit: "",
    };

  const sampleBanner =
    meta && meta.sample ? (
      <div
        className="rounded-2xl border-l-4 p-4 text-sm leading-6"
        style={{
          borderColor: "#c2543d",
          background: "#fbf1ee",
          color: "#7a3727",
        }}
      >
        <strong>Sample data.</strong> These are illustrative shapes shown while
        the live solver run finishes &mdash; directionally indicative, not
        actual model output. They will be replaced with real solver results
        automatically.
      </div>
    ) : null;

  const modeToggle = (
    <div className="flex flex-wrap gap-2">
      {[
        { id: "single", label: "One scenario" },
        { id: "compare", label: "Compare all" },
      ].map((m) => (
        <button
          key={m.id}
          type="button"
          className={`toggle-button ${mode === m.id ? "active" : ""}`}
          onClick={() => setMode(m.id)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );

  const scenarioSelector =
    mode === "single" ? (
      <div className="flex flex-wrap gap-2">
        {scenarios.map((s, i) => (
          <button
            key={s.id}
            type="button"
            className={`selector-chip compact ${scenIdx === i ? "active" : ""}`}
            onClick={() => setScenIdx(i)}
          >
            {s.name}
          </button>
        ))}
      </div>
    ) : null;

  const variableSelector = (
    <div className="flex flex-wrap gap-2">
      {vlist.map((v) => (
        <button
          key={v.code}
          type="button"
          className={`selector-chip compact ${activeVar === v.code ? "active" : ""}`}
          onClick={() => setVarCode(v.code)}
        >
          {v.label}
        </button>
      ))}
    </div>
  );

  const controls = (
    <div className="section-card space-y-5">
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
          Mode
        </p>
        {modeToggle}
      </div>
      {mode === "single" && (
        <div>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
            Scenario
          </p>
          {scenarioSelector}
        </div>
      )}
      <div>
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
          Variable
        </p>
        {variableSelector}
      </div>
    </div>
  );

  // --- Empty-scenario graceful state (single mode, no moving variables) ---
  if (mode === "single" && vlist.length === 0) {
    const sc = scenarios[scenIdx];
    return (
      <div className="space-y-6">
        {sampleBanner}
        <div className="section-card">
          <SectionHeading
            title="Explore scenarios"
            description="Pick a policy scenario and a variable to see the modelled path, quarter by quarter, against an unchanged baseline. Or switch to compare to see how the scenarios move one variable."
          />
        </div>
        {controls}
        <div className="section-card space-y-4">
          <p className="text-sm leading-6 text-slate-600">
            This scenario produced no material change in the tracked variables —
            the transmission channel it relies on is not active in this
            emulator. Pick another scenario, or switch to compare mode.
          </p>
          <ScenarioCard scenario={sc} />
        </div>
      </div>
    );
  }

  const axisLabel = `Δ ${varMeta.label} (${varMeta.unit})`;

  // Build chart data + series.
  let chartData;
  let seriesScenarios; // scenarios participating (compare mode)
  if (mode === "single") {
    const sc = scenarios[scenIdx];
    const arr = sc.series[activeVar] || [];
    chartData = periods.map((p, i) => ({
      period: qlab(p),
      value: arr[i] ?? null,
    }));
  } else {
    seriesScenarios = scenarios.filter((sc) => sc.series[activeVar]);
    chartData = periods.map((p, i) => {
      const row = { period: qlab(p) };
      seriesScenarios.forEach((sc) => {
        row[sc.id] = sc.series[activeVar][i] ?? null;
      });
      return row;
    });
  }

  // Y domain: include 0 plus all values.
  const allValues = [0];
  if (mode === "single") {
    chartData.forEach((d) => {
      if (d.value != null && !Number.isNaN(d.value)) {
        allValues.push(d.value);
      }
    });
  } else {
    chartData.forEach((d) => {
      seriesScenarios.forEach((sc) => {
        const v = d[sc.id];
        if (v != null && !Number.isNaN(v)) {
          allValues.push(v);
        }
      });
    });
  }
  const yTicks = getNiceTicks(
    [Math.min(...allValues), Math.max(...allValues)],
    5,
  );
  const yDomain = getTickDomain(yTicks);

  const tooltipFormatter = (value) =>
    value == null ? "—" : `${fmt(value)} ${varMeta.unit}`;

  return (
    <div className="space-y-6">
      {sampleBanner}
      <div className="section-card">
        <SectionHeading
          title="Explore scenarios"
          description="Pick a policy scenario and a variable to see the modelled path, quarter by quarter, against an unchanged baseline. Or switch to compare to see how the scenarios move one variable."
        />
      </div>
      {controls}

      <div className="section-card space-y-4">
        <p className="text-sm font-semibold text-slate-700">{axisLabel}</p>
        <div className="h-[360px] w-full">
          <ResponsiveContainer width="100%" height="100%">
            {mode === "single" ? (
              <ComposedChart
                data={chartData}
                margin={{ top: 10, right: 20, bottom: 5, left: 10 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={colors.border.light}
                />
                <XAxis dataKey="period" tick={AXIS_STYLE} />
                <YAxis
                  tick={AXIS_STYLE}
                  domain={yDomain}
                  ticks={yTicks}
                  tickFormatter={(v) => fmt(v)}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  formatter={(v) => [tooltipFormatter(v), varMeta.label]}
                />
                <ReferenceLine
                  y={0}
                  stroke={colors.gray[400]}
                  strokeWidth={1.2}
                />
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
            ) : (
              <LineChart
                data={chartData}
                margin={{ top: 10, right: 20, bottom: 5, left: 10 }}
              >
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={colors.border.light}
                />
                <XAxis dataKey="period" tick={AXIS_STYLE} />
                <YAxis
                  tick={AXIS_STYLE}
                  domain={yDomain}
                  ticks={yTicks}
                  tickFormatter={(v) => fmt(v)}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip formatter={(v) => tooltipFormatter(v)} />
                <Legend />
                <ReferenceLine
                  y={0}
                  stroke={colors.gray[400]}
                  strokeWidth={1.2}
                />
                {seriesScenarios.map((sc, i) => (
                  <Line
                    key={sc.id}
                    type="monotone"
                    dataKey={sc.id}
                    name={sc.name}
                    stroke={SERIES_COLORS[i % SERIES_COLORS.length]}
                    strokeWidth={2.4}
                    dot={{ r: 2 }}
                    activeDot={{ r: 4 }}
                    isAnimationActive={false}
                    connectNulls
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>

      {/* Description card */}
      {mode === "single" ? (
        <div className="section-card">
          <ScenarioCard scenario={scenarios[scenIdx]} />
        </div>
      ) : (
        <div className="section-card">
          <div className="note-card rounded-2xl p-4">
            <p className="note-body m-0 text-sm leading-6 text-slate-700">
              Comparing how each scenario moves{" "}
              <strong>{varMeta.label}</strong> ({varMeta.unit}), vs. an
              unchanged baseline.
            </p>
          </div>
        </div>
      )}

      {/* Quarter-by-quarter table */}
      <div className="section-card">
        <SectionHeading title="Quarter-by-quarter" size="lg" />
        <div className="mt-4 overflow-x-auto">
          {mode === "single" ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quarter</th>
                  <th>{axisLabel}</th>
                </tr>
              </thead>
              <tbody>
                {periods.map((p, i) => {
                  const v = (scenarios[scenIdx].series[activeVar] || [])[i];
                  return (
                    <tr key={p}>
                      <td>{p}</td>
                      <td className={v < 0 ? "text-red-700" : ""}>{fmt(v)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Quarter</th>
                  {seriesScenarios.map((sc) => (
                    <th key={sc.id}>{sc.name}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {periods.map((p, i) => (
                  <tr key={p}>
                    <td>{p}</td>
                    {seriesScenarios.map((sc) => {
                      const v = sc.series[activeVar][i];
                      return (
                        <td
                          key={sc.id}
                          className={v < 0 ? "text-red-700" : ""}
                        >
                          {fmt(v)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          Emulator output from the 15 Oct 2025 OBR model code &mdash;
          illustrative, not an OBR forecast.
        </p>
      </div>
    </div>
  );
}
