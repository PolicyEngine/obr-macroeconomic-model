"use client";

import { useState } from "react";
import ExploreTab from "./ExploreTab";
import CustomReformTab from "./CustomReformTab";
import SectionHeading from "./SectionHeading";

// One tab, two ways in: pick a ready-made preset scenario, or build your own by
// dialling a lever to any size. Both show a policy change's effect on a variable
// over the forecast, quarter by quarter, against an unchanged baseline.
export default function ScenariosTab({ explorer, grid }) {
  const hasPreset = !!explorer;
  const hasCustom = !!grid;
  const [source, setSource] = useState(hasPreset ? "preset" : "custom");

  const active =
    source === "custom" && hasCustom
      ? "custom"
      : source === "preset" && hasPreset
        ? "preset"
        : hasPreset
          ? "preset"
          : "custom";

  const MODES = [
    { id: "preset", label: "Preset scenarios", enabled: hasPreset },
    { id: "custom", label: "Build your own", enabled: hasCustom },
  ];

  return (
    <div className="space-y-6">
      <div className="section-card">
        <SectionHeading
          title="Explore scenarios"
          description="See how a policy change moves the economy, quarter by quarter, against an unchanged baseline. Start from a ready-made scenario, or build your own by dialling a lever to any size."
        />
        <div className="mt-4 flex flex-wrap gap-2">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              disabled={!m.enabled}
              className={`toggle-button ${active === m.id ? "active" : ""} ${
                m.enabled ? "" : "cursor-not-allowed opacity-40"
              }`}
              onClick={() => m.enabled && setSource(m.id)}
            >
              {m.label}
            </button>
          ))}
        </div>
        <p className="mt-3 text-xs leading-5 text-slate-500">
          {active === "preset"
            ? "Preset scenarios are fixed shocks solved against the standard demand closure. Switch to compare mode to overlay them on one variable."
            : "Build-your-own solves each lever against an add-factor-calibrated baseline (the way the OBR runs a reform in EViews); the slider scales linearly between two solved endpoints."}
        </p>
      </div>

      {active === "preset" ? (
        <ExploreTab explorer={explorer} embedded />
      ) : (
        <CustomReformTab grid={grid} embedded />
      )}
    </div>
  );
}
